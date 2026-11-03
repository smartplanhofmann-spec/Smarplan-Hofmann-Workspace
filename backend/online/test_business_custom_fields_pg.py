"""Real HTTP/MFA, SQL roles, competing writers and actual custom-field restore."""
from concurrent.futures import ThreadPoolExecutor
import tempfile
import threading
import unittest
import psycopg
from psycopg.conninfo import make_conninfo
from core import Problem
import business_schema
from business_custom_fields import CustomFields,protected_tables,validate_integrity
from online import test_customer_execution_journey_pg as journey,release
from online.backup import backup
from online.restore import complete_restore,restore
from online.store import PostgresOffice

fixture=journey.fixture
request=journey.request

@unittest.skipUnless(fixture.DSN,'Disposable loopback PostgreSQL fixture required')
class CustomFieldsPostgres(unittest.TestCase):
    setUp=journey.CustomerExecutionJourneyPostgres.setUp
    reopen=journey.CustomerExecutionJourneyPostgres.reopen
    login=journey.CustomerExecutionJourneyPostgres.login
    call=journey.CustomerExecutionJourneyPostgres.call

    def workflow(self):
        actor=self.office.user(self.token)
        with self.office.db:project=self.office.add_project(actor,'Synthetic fields project','Synthetic fields customer')
        definition_body=request(revision=0,reason='',definition=dict(entity_type='project',label='Prüfmaß',help_text='Synthetischer Messnachweis',field_type='text',required=True,active=True,options=[]))
        definition=self.call('POST','/business/custom-fields/definitions',definition_body).json
        path='/business/custom-fields/entities/project/'+project
        view=self.call('GET',path).json
        body=request(revision=0,definitions_hash=view['definitions_hash'],values={definition['id']:'42'},reason='')
        saved=self.call('POST',path,body).json
        self.assertEqual(self.call('POST',path,body).json,saved)
        return dict(actor=actor,project=project,definition=definition,definition_body=definition_body,path=path,body=body,saved=saved)

    def test_real_http_immutable_roles_and_atomic_definition_value_race(self):
        value=self.workflow();self.assertTrue(validate_integrity(self.office))
        tech=self.call('POST','/users',dict(email='custom-tech@example.test',password='Synthetic-tech-password-123',role='technician'),status=201).json
        token=self.login('custom-tech@example.test','Synthetic-tech-password-123')
        with self.office.db:self.office.assign(value['actor'],value['project'],tech['id'])
        view=self.call('GET',value['path'],token=token).json;self.assertFalse(view['can_write'])
        self.call('POST',value['path'],value['body'],token=token,status=403)
        self.call('GET','/business/custom-fields/definitions',token=token,status=403)
        self.call('POST',value['path']+'?ignored=1',value['body'],status=400)
        device=self.call('POST','/business/offline/access',{},status=201).json['token']
        self.call('GET',value['path'],token=device,status=403)
        for table in protected_tables():
            column=self.office.db.execute('SELECT * FROM '+table+' LIMIT 1').description[0].name
            for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table,'TRUNCATE '+table):
                with self.subTest(statement=statement),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db:self.office.db.execute(statement)
        unused=self.call('POST','/business/custom-fields/definitions',request(revision=0,reason='',definition={**value['definition_body']['definition'],'label':'Race field'})).json
        preview=self.call('GET',value['path']).json
        body=request(revision=1,definitions_hash=preview['definitions_hash'],values={value['definition']['id']:'42',unused['id']:'123'},reason='Concurrent source')
        change=request(id=unused['id'],revision=1,reason='Concurrent type',definition={**value['definition_body']['definition'],'label':'Race field','field_type':'number'})
        barrier=threading.Barrier(2)
        def worker(is_definition):
            office=PostgresOffice(self.runtime)
            try:
                api=CustomFields(office);barrier.wait(timeout=10)
                try:
                    if is_definition:api.save_definition(value['actor'],change)
                    else:api.save_values(value['actor'],'project',value['project'],body)
                    return 200
                except Problem as error:return error.status
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(worker,[True,False]))
        self.assertEqual(sorted(results),[200,409])
        self.reopen();self.assertEqual(self.call('POST',value['path'],value['body']).json,value['saved'])
        self.assertTrue(validate_integrity(self.office));business_schema.validate_integrity(self.office)

    def test_real_dump_restore_keeps_historical_labels_values_and_receipts(self):
        value=self.workflow();old=value['definition']
        self.call('POST','/business/custom-fields/definitions',request(id=old['id'],revision=1,reason='Archive field',definition={**value['definition_body']['definition'],'active':False})).json
        current=self.call('GET',value['path']).json
        self.call('POST',value['path'],request(revision=1,definitions_hash=current['definitions_hash'],values={},reason='Archived value preserved'))
        view=self.call('GET',value['path']).json;history=self.call('GET',value['path']+'/history').json
        before=release.snapshot_fingerprint(fixture.DSN);self.office.db.close()
        target=make_conninfo(fixture.DSN,dbname='smartplan_release_check');release.validate_dsns(fixture.DSN,target,test_mode=True)
        with psycopg.connect(fixture.DSN,autocommit=True) as admin:
            if admin.execute("SELECT 1 FROM pg_database WHERE datname='smartplan_release_check'").fetchone():raise RuntimeError('Existing restore target must remain untouched')
            admin.execute('CREATE DATABASE smartplan_release_check OWNER "smartplan-migrator" TEMPLATE template0')
        try:
            with tempfile.TemporaryDirectory(prefix='custom-fields-restore-') as directory:
                saved=backup(fixture.DSN,directory);self.assertTrue(restore(saved,fixture.DSN,target,privileged_operator=True,test_mode=True)['restore_pending'])
            restored_dsn=make_conninfo(self.runtime,dbname='smartplan_release_check');verifier=PostgresOffice(restored_dsn,allow_restore_pending=True)
            try:self.assertFalse(complete_restore(verifier)['restore_pending'])
            finally:verifier.db.close()
            restored=PostgresOffice(restored_dsn)
            try:
                api=CustomFields(restored);self.assertEqual(api.entity(value['actor'],'project',value['project']),view)
                self.assertEqual(api.history(value['actor'],{},entity_type='project',entity_id=value['project']),history)
                self.assertEqual(api.save_values(value['actor'],'project',value['project'],value['body']),value['saved'])
                self.assertTrue(validate_integrity(restored));business_schema.validate_integrity(restored)
                after=release.snapshot_fingerprint(target)
                for table in protected_tables():self.assertEqual(after[table],before[table])
            finally:restored.db.close()
        finally:
            with psycopg.connect(fixture.DSN,autocommit=True) as admin:admin.execute('DROP DATABASE smartplan_release_check')

if __name__=='__main__':unittest.main()
