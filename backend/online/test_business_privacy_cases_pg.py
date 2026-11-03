"""Real MFA/runtime ACL and pre-purge PostgreSQL backup recovery."""
from datetime import timedelta
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid
import zipfile

import psycopg

from core import Problem
import business_schema
from business_privacy_cases import PrivacyCases,protected_tables
from privacy_case_sources import MANUAL_AREAS
from online import test_customer_execution_journey_pg as journey
from online import test_business_asset_provenance_pg as login_fixture
from online import test_postgres_accounting_integration as finance_fixture
from online.backup import backup
from online.store import PostgresOffice
from online.web import create_app
from online.test_postgres_accounting_components_integration import disposable_restore


@unittest.skipUnless(journey.fixture.DSN,'Guarded disposable PostgreSQL fixture required')
class PrivacyPostgres(unittest.TestCase):
    call=login_fixture.AssetDeliveryPostgresTests.call
    login=login_fixture.AssetDeliveryPostgresTests.login
    reopen=journey.CustomerExecutionJourneyPostgres.reopen

    def setUp(self):
        journey.CustomerExecutionJourneyPostgres.setUp(self)
        temporary=tempfile.TemporaryDirectory(prefix='synthetic-pg-privacy-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);key=self.root/'privacy.key';key.write_bytes(b'k'*32);key.chmod(0o600)
        self.environment={'SMARTPLAN_PRIVACY_CHECKPOINT_FILE':str(self.root/'independent.json'),
            'SMARTPLAN_PRIVACY_CHECKPOINT_KEY_FILE':str(key),'SMARTPLAN_PRIVACY_INSTALLATION_ID':'f'*32}
        environment=patch.dict(os.environ,self.environment);environment.start();self.addCleanup(environment.stop)
        business_schema.initialize_privacy_checkpoint(self.office)

    def action(self,case,operation,**values):
        return self.call('/business/privacy/cases/'+case['id']+'/'+operation,
            journey.request(revision=case['revision'],**values)).json['case']

    def prepared(self,kind,name):
        contact=self.call('/business/contacts',journey.request(name=name,email='private-'+kind+'@example.test',entity_type='person'),status=201).json
        case=self.call('/business/privacy/cases',journey.request(id=uuid.uuid4().hex,subject_kind='customer',subject_id=contact['id'],request_kind=kind,
            received_date=self.today,due_date=(self.now+timedelta(days=25)).date().isoformat(),assigned_to=self.office.user(self.token)['id'],
            scope='Synthetic precise subject request',retain_until=self.today,retention_reason='Synthetic temporary working purpose')).json
        case=self.action(case,'identity',method='in_person',evidence='Synthetic identity checked without document retention',confirmed=True)
        case=self.action(case,'scan')
        for source in case['inventory']['sources']:
            decision='erase_master' if kind=='erasure' and source['table']=='customers' else 'include'
            case=self.action(case,'review',source_key=source['key'],source_sha256=source['sha256'],decision=decision,
                reason='Subject and third parties reviewed',redacted_value=None,include_originals=False)
        for area in MANUAL_AREAS:case=self.action(case,'manual',area=area,decision='checked',evidence='Synthetic source review '+area)
        return contact,case

    def test_real_mfa_acl_private_purge_missing_checkpoint_and_pre_purge_dump_restore(self):
        project=self.call('/projects',dict(name='Unchanged synthetic commercial project',customer='Independent buyer'),status=201).json['id']
        self.call('/business/settings/branding',finance_fixture.issuer_settings(self.today))
        draft=self.call('/business/documents',finance_fixture.invoice_data(project,self.today)).json
        self.call('/business/documents/'+draft['id']+'/finalize',journey.request(revision=draft['revision']))
        contact,erase_case=self.prepared('erasure','Synthetic erasable person')
        exported,export_case=self.prepared('export','Synthetic exported person')
        value=self.call('/business/privacy/cases/'+export_case['id']+'/export',journey.request(revision=export_case['revision'],expires_on=self.today,confirmed=True)).json
        export_case=value['case'];export_id=value['receipt']['export_id']
        archive_path='/business/privacy/cases/'+export_case['id']+'/exports/'+export_id
        raw=self.call(archive_path).data
        with zipfile.ZipFile(io.BytesIO(raw)) as package:
            self.assertEqual(json.loads(package.read('subject-data.json'))['subject_id'],exported['id'])
        self.call(archive_path,token='SPCT_'+'a'*43,status=401)
        self.call('/business/privacy/cases',{},method='GET',status=400)
        self.call('/business/privacy/cases/'+export_case['id']+'/scan?ignored=1',journey.request(revision=export_case['revision']),status=400)
        self.assertTrue(business_schema.require_runtime_security(self.office))
        for table in protected_tables():
            for statement in ('DELETE FROM '+table,'TRUNCATE '+table):
                with self.subTest(table=table,statement=statement),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db:self.office.db.execute(statement)
        for table in ('business_privacy_case_contents','business_privacy_case_export_blobs'):
            with self.assertRaisesRegex(psycopg.Error,'privacy purge proof required'):
                with self.office.db:self.office.db.execute('DELETE FROM '+table)
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with self.office.db:self.office.db.execute('UPDATE '+table+' SET content=content')
        self.reopen()
        self.assertEqual(self.call(archive_path).data,raw)
        preserved={table:[dict(row) for row in self.office.db.execute('SELECT * FROM '+table)]
            for table in ('projects',)+finance_fixture.SOURCE_TABLES}
        # The retained backup deliberately contains both personal case copies
        # and the original contact before either real deletion occurs.
        older_archive=backup(journey.fixture.DSN,self.root/'before-purge')
        erase_case=self.action(erase_case,'erase',contact_revision=contact['revision'],reason='Isolated contact, all sources reviewed',confirmed=True)
        self.assertEqual(erase_case['actions'][-1]['result']['status'],'erased')
        erase_case=self.action(erase_case,'close',outcome='partially_fulfilled',response_date=self.today,
            response_evidence='Synthetic direct reply documented',reason='Contact master erased; minimal case evidence retained for its stated purpose',confirmed=True)
        export_purge=journey.request(revision=export_case['revision'],confirmed=True,reason='Revoke temporary personal export copy')
        self.call(archive_path+'/purge',export_purge)
        self.call(archive_path,status=410)
        with self.assertRaisesRegex(psycopg.Error,'purged privacy content cannot return'):
            with self.office.db:self.office.db.execute('INSERT INTO business_privacy_case_export_blobs(export_id,content) VALUES(?,?)',(export_id,b'private reanimation'))
        case_purge=journey.request(revision=erase_case['revision'],confirmed=True,reason='Case closed and explicitly documented retention elapsed')
        future=(self.now+timedelta(days=1)).isoformat(timespec='seconds')
        with patch.object(PrivacyCases,'now',return_value=future):
            result=self.call('/business/privacy/cases/'+erase_case['id']+'/purge',case_purge).json
            self.assertTrue(result['case']['purged'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_privacy_case_contents WHERE case_id=?',(erase_case['id'],)).fetchone()[0],0)
        self.assertTrue(business_schema.validate_integrity(self.office))
        previous_token=self.token;runtime=self.runtime;self.office.db.close()
        with patch('online.test_postgres_accounting_components_integration.backup',return_value=older_archive):
            with patch.dict(os.environ,{'SMARTPLAN_PRIVACY_CHECKPOINT_FILE':str(self.root/'missing-independent.json')}):
                with self.assertRaises(Problem):
                    with disposable_restore(runtime):self.fail('Missing independent checkpoint released an old backup')
            with disposable_restore(runtime) as (_,restored_runtime,_):
                self.runtime=restored_runtime;self.reopen()
                try:
                    self.call('/business/privacy/cases',token=previous_token,status=401)
                    self.token=self.login('order-owner@example.test','Synthetic-owner-password-123')
                    self.assertTrue(self.call('/business/privacy/cases/'+erase_case['id']).json['purged'])
                    self.assertEqual(self.call('/business/contacts/'+contact['id']).json['email'],'')
                    self.call(archive_path,status=410)
                    self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_privacy_case_contents WHERE case_id=?',(erase_case['id'],)).fetchone()[0],0)
                    self.assertGreater(self.office.db.execute('SELECT COUNT(*) FROM business_privacy_case_contents WHERE case_id=?',(export_case['id'],)).fetchone()[0],0)
                    for table,rows in preserved.items():self.assertEqual([dict(row) for row in self.office.db.execute('SELECT * FROM '+table)],rows)
                    self.assertTrue(business_schema.validate_integrity(self.office));self.assertTrue(business_schema.require_runtime_security(self.office))
                finally:self.office.db.close()


if __name__=='__main__':unittest.main()
