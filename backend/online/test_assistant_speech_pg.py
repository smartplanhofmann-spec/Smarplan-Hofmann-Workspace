"""Bound-company PostgreSQL dictation metadata, restart and disaster recovery.

Only the existing guarded disposable loopback database is used. All audio,
identities and transcription responses are synthetic; there is no provider I/O.
"""
import base64
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

import psycopg

import business_schema
from business_assistant_speech import AssistantSpeech, protected_tables
from core import Problem
from online import test_customer_execution_journey_pg as journey
from online import test_business_asset_provenance_pg as login_fixture
from online import test_postgres_accounting_integration as financial_fixture
from online.instance import bind
from online.storage import Storage
from online.store import PostgresOffice
from online.web import create_app
from online.test_postgres_accounting_components_integration import disposable_restore
from test_business_assistant_speech import SyntheticSpeech, wav


@unittest.skipUnless(journey.fixture.DSN,'Guarded disposable loopback PostgreSQL required')
class SpeechPostgres(unittest.TestCase):
    call=login_fixture.AssetDeliveryPostgresTests.call
    login=login_fixture.AssetDeliveryPostgresTests.login

    def setUp(self):
        self.instance=uuid.uuid4().hex
        temporary=tempfile.TemporaryDirectory(prefix='synthetic-speech-company-')
        self.addCleanup(temporary.cleanup)
        self.storage_config={'server':{'path':str(Path(temporary.name)/'originals')}}
        self.bound=False
        journey.CustomerExecutionJourneyPostgres.setUp(self)
        self.env={'SMARTPLAN_ASSISTANT_SPEECH_ENABLED':'1','SMARTPLAN_ASSISTANT_SPEECH_DATA_TRANSFER_APPROVED':'1',
            'SMARTPLAN_ASSISTANT_SPEECH_INSTANCE_ID':self.instance,
            'SMARTPLAN_ASSISTANT_SPEECH_ENDPOINT':'https://speech.example.test/v1/audio/transcriptions',
            'SMARTPLAN_ASSISTANT_SPEECH_MODEL':'synthetic-transcription',
            'SMARTPLAN_ASSISTANT_SPEECH_API_KEY':'synthetic-never-transmitted-secret'}
        environment=patch.dict(os.environ,self.env);environment.start();self.addCleanup(environment.stop)
        self.transport=SyntheticSpeech()
        transport=patch('business_assistant_speech.OpenAICompatibleSpeech',return_value=self.transport)
        transport.start();self.addCleanup(transport.stop)

    def reopen(self):
        if hasattr(self,'office'):self.office.db.close()
        if not self.bound:
            operator=PostgresOffice(journey.fixture.DSN)
            try:
                storage=Storage(operator,self.key,'office.example.test',config=self.storage_config)
                bind(operator,self.instance,'office.example.test',self.key,storage)
            finally:operator.db.close()
            self.bound=True
        self.office=PostgresOffice(self.runtime)
        self.addCleanup(self.office.db.close)
        self.app=create_app(office=self.office,key=self.key,host='office.example.test',
            instance_id=self.instance,storage_config=self.storage_config)
        self.client=self.app.test_client()

    def test_real_bound_mfa_http_runtime_acl_restart_and_dump_restore(self):
        project=self.call('/projects',dict(name='Synthetic speech order',customer='Synthetic buyer'),status=201).json['id']
        self.call('/business/settings/branding',financial_fixture.issuer_settings(self.today))
        draft=self.call('/business/documents',financial_fixture.invoice_data(project,self.today)).json
        invoice=self.call('/business/documents/'+draft['id']+'/finalize',journey.request(revision=draft['revision'])).json
        context=self.call('/business/assistant/contexts',journey.request(project_id=project,sources=[dict(kind='project',id=project)])).json
        command=journey.request(context_id=context['id'],data_transfer_confirmed=True,audio_base64=base64.b64encode(wav(960000)).decode())
        self.assertTrue(self.call('/business/assistant/speech/status?project_id='+project).json['provider']['configured'])
        competitor=PostgresOffice(self.runtime)
        competing_transport=SyntheticSpeech()
        def retry_during_provider():
            with self.assertRaises(Problem) as caught:
                AssistantSpeech(competitor,transport=competing_transport).transcribe(self.office.user(self.token),command)
            self.assertEqual(caught.exception.status,409)
        self.transport.effect=retry_during_provider
        try:result=self.call('/business/assistant/speech/transcribe',command).json
        finally:
            competitor.db.close()
            self.transport.effect=None
        self.assertEqual(competing_transport.calls,[])
        self.assertEqual(result['status'],'completed')
        self.assertEqual(self.office.db.execute('SELECT current_user').fetchone()[0],'smartplan-online')
        self.assertTrue(business_schema.require_runtime_security(self.office))

        # A crash after transmission but before the completion commit retains
        # the durable claim. Restore must append interruption, never replay it.
        interrupted={**command,'request_id':uuid.uuid4().hex}
        crash=SyntheticSpeech(effect=lambda:(_ for _ in ()).throw(KeyboardInterrupt()))
        with self.assertRaises(KeyboardInterrupt):
            AssistantSpeech(self.office,transport=crash).transcribe(self.office.user(self.token),interrupted)
        requests=[dict(row) for row in self.office.db.execute('SELECT * FROM business_assistant_speech_requests ORDER BY id')]
        completed=dict(self.office.db.execute('SELECT * FROM business_assistant_speech_outcomes').fetchone())
        unchanged={table:[dict(row) for row in self.office.db.execute('SELECT * FROM '+table)]
            for table in ('projects',)+financial_fixture.SOURCE_TABLES}
        for table in protected_tables():
            for statement in ('UPDATE '+table+' SET created_at=created_at','DELETE FROM '+table,'TRUNCATE '+table):
                with self.subTest(table=table,statement=statement),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db:self.office.db.execute(statement)
            with psycopg.connect(journey.fixture.DSN,autocommit=True) as operator:
                for statement in ('UPDATE '+table+' SET created_at=created_at','DELETE FROM '+table):
                    with self.subTest(table=table,guard=statement),self.assertRaisesRegex(psycopg.Error,'immutable speech metadata'):
                        with operator.transaction():
                            operator.execute('SET LOCAL ROLE "smartplan-migrator"')
                            operator.execute(statement)
        self.reopen()
        self.call('/business/assistant/speech/transcribe',command,status=409)
        self.call('/business/assistant/speech/transcribe',interrupted,status=409)
        self.assertEqual(len(self.transport.calls),1)
        self.assertEqual(self.call('/business/assistant/speech/requests/'+interrupted['request_id']).json['status'],'started')
        self.assertTrue(business_schema.validate_integrity(self.office))
        previous_token=self.token
        self.office.db.close()
        with disposable_restore(self.runtime) as (_,restored_runtime,_):
            self.runtime=restored_runtime
            self.reopen()
            try:
                self.call('/business/assistant/speech/requests/'+command['request_id'],token=previous_token,status=401)
                self.token=self.login('order-owner@example.test','Synthetic-owner-password-123')
                for body,expected in ((command,'completed'),(interrupted,'interrupted')):
                    metadata=self.call('/business/assistant/speech/requests/'+body['request_id']).json
                    self.assertEqual(metadata['status'],expected);self.assertNotIn('text',metadata)
                    self.assertFalse(metadata['retry_automatically'])
                    self.call('/business/assistant/speech/transcribe',body,status=409)
                self.assertEqual([dict(row) for row in self.office.db.execute('SELECT * FROM business_assistant_speech_requests ORDER BY id')],requests)
                self.assertEqual(dict(self.office.db.execute('SELECT * FROM business_assistant_speech_outcomes WHERE request_id=?',(command['request_id'],)).fetchone()),completed)
                self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_assistant_speech_outcomes').fetchone()[0],2)
                for table,rows in unchanged.items():
                    self.assertEqual([dict(row) for row in self.office.db.execute('SELECT * FROM '+table)],rows)
                self.assertEqual(self.call('/business/documents/'+invoice['id']).json['totals'],invoice['totals'])
                self.assertTrue(business_schema.validate_integrity(self.office))
                self.assertTrue(business_schema.require_runtime_security(self.office))
                self.assertEqual(len(self.transport.calls),1)
            finally:self.office.db.close()


if __name__=='__main__':unittest.main()
