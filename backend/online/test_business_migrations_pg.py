"""Actual PostgreSQL, authenticated HTTP, file limits, runtime ACL and restore."""
import base64
from concurrent.futures import ThreadPoolExecutor
import tempfile
import unittest

import psycopg
from psycopg.conninfo import make_conninfo
import business_schema
from business_migrations import Migrations, MAX_FILE, protected_tables
from online import release, test_customer_execution_journey_pg as journey
from online.backup import backup
from online.restore import complete_restore, restore
from online.store import PostgresOffice, migrate
from test_business_migrations import req, csv_bytes

fixture=journey.fixture


@unittest.skipUnless(fixture.DSN,'Guarded disposable PostgreSQL fixture required')
class MigrationPostgres(unittest.TestCase):
    setUp=journey.CustomerExecutionJourneyPostgres.setUp
    reopen=journey.CustomerExecutionJourneyPostgres.reopen
    login=journey.CustomerExecutionJourneyPostgres.login
    call=journey.CustomerExecutionJourneyPostgres.call

    def stage(self):
        package=self.call('POST','/business/migrations',req(source_system='sevdesk',source_account='Synthetic PG source account',
            label='Synthetic source export',period_from='2026-01-01',period_to='2026-11-03',scope='One synthetic CRM chain; no accounting entries')).json
        path='/business/migrations/'+package['id'];tables=[]
        rows={'contact':dict(source_id='C1',name='Synthetic PG migrated customer',email='migration-pg@example.test'),
            'project':dict(source_id='P1',customer_source_id='C1',name='Synthetic PG migrated project'),
            'document':dict(source_id='D1',customer_source_id='C1',project_source_id='P1',kind='invoice',number='SYN-OLD-1',issue_date='2026-05-31',net='100.00',tax='19.00',gross='119.00',currency='EUR',original_filename='original.pdf')}
        for kind,values in rows.items():
            body=req(filename=kind+'.csv',media_type='text/csv',content_base64=base64.b64encode(csv_bytes([values])).decode())
            original=self.call('POST',path+'/files',body).json
            self.assertEqual(self.call('POST',path+'/files',body).json,original)
            inspection=self.call('GET',path+'/files/'+original['id']+'/inspect?format=csv&encoding=utf-8-sig&delimiter=%3B').json
            self.assertEqual(inspection['row_count'],1)
            tables.append(dict(file_id=original['id'],kind=kind,format='csv',encoding='utf-8-sig',delimiter=';',decimal_separator='.',columns={k:k for k in values}))
        raw=b'%PDF-1.7\n'+b'Synthetic historical original.\n'*40000+b'%%EOF'
        self.assertGreater(len(raw),1_000_000)
        original=self.call('POST',path+'/files',req(filename='original.pdf',media_type='application/pdf',content_base64=base64.b64encode(raw).decode())).json
        downloaded=self.call('GET',path+'/files/'+original['id']+'/original')
        self.assertEqual(downloaded.data,raw)
        self.call('POST',path+'/mapping',req(revision=0,tables=tables,decisions=[]))
        preview=self.call('GET',path+'/preview').json
        self.assertTrue(preview['ready'],preview)
        body=req(revision=1,preview_sha256=preview['preview_sha256'],confirmation=True)
        return dict(package=package,path=path,body=body,original=original,raw=raw)

    def test_actual_mfa_http_large_original_concurrent_apply_fresh_acl_and_limits(self):
        data=self.stage();actor=self.office.user(self.token)
        def apply():
            connection=PostgresOffice(self.runtime)
            try:return Migrations(connection).apply(actor,data['package']['id'],data['body'])
            finally:connection.db.close()
        with ThreadPoolExecutor(max_workers=2) as workers:
            reports=list(workers.map(lambda _:apply(),range(2)))
        self.assertEqual(reports[0],reports[1]);report=reports[0]
        self.assertEqual(self.call('POST',data['path']+'/apply',data['body']).json,report)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM customers').fetchone()[0],1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM projects').fetchone()[0],1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_documents').fetchone()[0],0)
        self.assertEqual(report['totals'][0]['selected']['gross'],11900)
        ack=req(report_sha256=report['report_sha256'],confirmation=True,note='Synthetic exact counts, relationships and source amounts checked.')
        receipt=self.call('POST',data['path']+'/reconcile',ack).json
        self.assertEqual(self.call('POST',data['path']+'/reconcile',ack).json,receipt)
        # Upload boundary is exercised against a fresh writable package.
        fresh=self.call('POST','/business/migrations',req(source_system='other',source_account='Limits',label='Limits',period_from=None,period_to=None,scope='Synthetic upload limits')).json
        upload='/business/migrations/'+fresh['id']+'/files'
        self.call('POST',upload,req(filename='too-large.pdf',media_type='application/pdf',content_base64=base64.b64encode(b'x'*(MAX_FILE+1)).decode()),status=413)
        self.call('POST',upload,req(filename='transport-too-large.pdf',media_type='application/pdf',content_base64='x'*2_850_001),status=413)
        self.call('POST','/business/migrations',req(source_system='other',source_account='Limits',label='x'*1_010_000,period_from=None,period_to=None,scope='Oversized regular command'),status=413)
        self.call('GET',data['path'],{'extra':True},status=400)
        self.call('POST',data['path']+'/apply?extra=1',data['body'],status=400)
        device=self.call('POST','/business/offline/access',{},status=201).json['token']
        self.call('GET',data['path'],token=device,status=403)
        tech=self.call('POST','/users',dict(email='migration-tech-pg@example.test',password='Synthetic-migration-tech-password-123',role='technician'),status=201).json
        token=self.login('migration-tech-pg@example.test','Synthetic-migration-tech-password-123')
        self.call('GET',data['path'],token=token,status=403)
        self.call('GET',data['path']+'/files/'+data['original']['id']+'/original',token=token,status=403)
        self.call('POST',data['path']+'/apply',data['body'],token=token,status=403)
        for table in protected_tables():
            column=self.office.db.execute('SELECT * FROM '+table+' LIMIT 1').description[0].name
            for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table,'TRUNCATE '+table):
                with self.subTest(table=table,statement=statement),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db:self.office.db.execute(statement)
            with psycopg.connect(fixture.DSN,autocommit=True) as migrator:
                for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table):
                    with self.subTest(table=table,guard=statement),self.assertRaisesRegex(psycopg.Error,'immutable migration evidence'):
                        with migrator.transaction():
                            migrator.execute('SET LOCAL ROLE "smartplan-migrator"');migrator.execute(statement)
        self.reopen()
        self.assertEqual(self.call('GET',data['path']+'/report').json,report)
        self.assertEqual(self.call('POST',data['path']+'/apply',data['body']).json,report)
        business_schema.validate_integrity(self.office)

    def test_actual_backup_restore_retains_originals_mappings_reports_and_exact_receipts(self):
        data=self.stage();report=self.call('POST',data['path']+'/apply',data['body']).json;actor=self.office.user(self.token)
        ack=req(report_sha256=report['report_sha256'],confirmation=True,note='Synthetic source scope compared')
        acknowledgement=self.call('POST',data['path']+'/reconcile',ack).json
        before=release.snapshot_fingerprint(fixture.DSN);runtime=self.runtime;self.office.db.close()
        migrate(fixture.DSN,owner_role='smartplan-migrator',compatibility_mode='business',require_business_modules=True)
        self.assertEqual(release.snapshot_fingerprint(fixture.DSN),before)
        target=make_conninfo(fixture.DSN,dbname='smartplan_release_check');release.validate_dsns(fixture.DSN,target,test_mode=True)
        with psycopg.connect(fixture.DSN,autocommit=True) as admin:
            if admin.execute("SELECT 1 FROM pg_database WHERE datname='smartplan_release_check'").fetchone():raise RuntimeError('Existing restore target must remain untouched')
            admin.execute('CREATE DATABASE smartplan_release_check OWNER "smartplan-migrator" TEMPLATE template0')
        try:
            with tempfile.TemporaryDirectory(prefix='migration-pg-restore-') as directory:
                saved=backup(fixture.DSN,directory)
                self.assertTrue(restore(saved,fixture.DSN,target,privileged_operator=True,test_mode=True)['restore_pending'])
            restored_runtime=make_conninfo(runtime,dbname='smartplan_release_check');verifier=PostgresOffice(restored_runtime,allow_restore_pending=True)
            try:self.assertFalse(complete_restore(verifier)['restore_pending'])
            finally:verifier.db.close()
            recovered=PostgresOffice(restored_runtime)
            try:
                api=Migrations(recovered)
                self.assertEqual(api.apply(actor,data['package']['id'],data['body']),report)
                self.assertEqual(api.reconcile(actor,data['package']['id'],ack),acknowledgement)
                self.assertEqual(bytes(api.original(actor,data['package']['id'],data['original']['id'])[0]),data['raw'])
                business_schema.validate_integrity(recovered)
                after=release.snapshot_fingerprint(target)
                for table in protected_tables():self.assertEqual(after[table],before[table],table)
                self.assertEqual(release.snapshot_fingerprint(fixture.DSN),before)
            finally:recovered.db.close()
        finally:
            with psycopg.connect(fixture.DSN,autocommit=True) as admin:admin.execute('DROP DATABASE smartplan_release_check')


if __name__=='__main__':unittest.main()
