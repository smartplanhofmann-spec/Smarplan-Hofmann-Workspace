"""Real PostgreSQL/MFA service chain, native scheduling and immutable restore."""
from concurrent.futures import ThreadPoolExecutor
import tempfile
import unittest

import psycopg
from psycopg.conninfo import make_conninfo
import business_schema
from business_service import Service,protected_tables
from online import release,test_customer_execution_journey_pg as journey
from online.backup import backup
from online.restore import complete_restore,restore
from online.store import PostgresOffice,migrate
import test_business_service as domain

fixture=journey.fixture
req=domain.req


@unittest.skipUnless(fixture.DSN,'Guarded disposable PostgreSQL fixture required')
class ServicePostgres(unittest.TestCase):
    setUp=journey.CustomerExecutionJourneyPostgres.setUp
    reopen=journey.CustomerExecutionJourneyPostgres.reopen
    login=journey.CustomerExecutionJourneyPostgres.login
    call=journey.CustomerExecutionJourneyPostgres.call
    values=domain.ServiceTests.values
    report=domain.ServiceTests.report

    def workflow(self):
        self.owner=self.office.user(self.token);self.manager=self.owner;self.api=Service(self.office)
        self.customer=self.call('POST','/business/contacts',req(name='Synthetic PG service customer',persons=[dict(name='Synthetic contact',role_label='Site',email='site@example.test',phone='')]),status=201).json
        self.project=None
        inquiry=self.call('POST','/inquiries',req(subject='Synthetic PG complaint',message='Please inspect the synthetic equipment.',sender_email='site@example.test'),status=201).json
        body=self.values(project_id=None,responsible_id=self.owner['id'],inquiry_id=inquiry['id'])
        item=self.call('POST','/business/service/cases',body).json;path='/business/service/cases/'+item['id']
        project_body=req(revision=item['revision'],source_sha256=item['source_sha256'],confirmation=True,project_id=None,project_name='Synthetic canonical service project')
        adopted=self.call('POST',path+'/project',project_body).json;self.project=adopted['case']['project_id']
        self.assertEqual(self.call('POST',path+'/project',project_body).json,adopted)
        self.assertEqual(self.call('POST','/business/service/cases',body).json,item)
        self.assertEqual(self.call('GET','/inquiries/'+inquiry['id']).json['project_id'],self.project)
        options=self.call('GET','/business/service/options?project_id='+self.project).json
        self.assertEqual(options['customer_id'],self.customer['id'])
        current=self.call('GET',path).json
        dispatch_body=req(revision=current['revision'],source_sha256=current['source_sha256'],confirmation=True,title='Synthetic actual visit',
            start_at='2026-11-04T09:00:00+01:00',end_at='2026-11-04T10:00:00+01:00',timezone='Europe/Berlin',employee_ids=[],resource_ids=[],details='Synthetic dispatch')
        def dispatch_once():
            office=PostgresOffice(self.runtime)
            try:return Service(office).command(self.owner,item['id'],'dispatch',dispatch_body)
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:dispatched=list(pool.map(lambda _:dispatch_once(),range(2)))
        self.assertEqual(dispatched[0],dispatched[1])
        self.assertEqual(self.call('POST',path+'/dispatch',dispatch_body).json,dispatched[0])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_appointments').fetchone()[0],1)
        signed=self.report();current=self.call('GET',path).json
        evidence_body=req(revision=current['revision'],source_sha256=current['source_sha256'],confirmation=True,report_id=signed['id'])
        evidence=self.call('POST',path+'/evidence',evidence_body).json
        self.assertEqual(self.call('POST',path+'/evidence',evidence_body).json,evidence)
        for status in ('resolved','closed','triaged'):
            current=self.call('GET',path).json
            self.call('POST',path+'/transition',req(revision=current['revision'],source_sha256=current['source_sha256'],status=status,reason='Synthetic reviewed '+status,resolution='Synthetic repair verified' if status in ('resolved','closed') else ''))
        history=self.call('GET',path+'/history').json
        self.assertIn('closed',[v['status'] for v in history['versions']])
        # A second case reuses the existing native maintenance occurrence and completion.
        asset=self.api.maintenance.save_asset(self.owner,self.project,req(name='Synthetic PG device',serial_number='SYN-SERVICE-PG'))
        self.api.maintenance.save_contract(self.owner,self.project,req(asset_id=asset['id'],title='Synthetic annual contract',anchor_date='2026-11-01',interval_unit='months',interval_count=12))
        visit=self.api.maintenance.schedule_due(self.owner,req(project_id=self.project,as_of='2026-11-01'))['items'][0]
        maintenance=self.call('POST','/business/service/cases',self.values(kind='maintenance',visit_id=visit['id'])).json
        maintenance_path='/business/service/cases/'+maintenance['id'];maintenance_report=self.report()
        maintenance_evidence=req(revision=maintenance['revision'],source_sha256=maintenance['source_sha256'],confirmation=True,report_id=maintenance_report['id'])
        linked=self.call('POST',maintenance_path+'/evidence',maintenance_evidence).json
        self.assertEqual(self.call('POST',maintenance_path+'/evidence',maintenance_evidence).json,linked)
        completed=self.api.maintenance.history(self.owner,self.project)[0]
        self.assertEqual((completed['status'],completed['report_pdf_sha256']),('completed',maintenance_report['pdf_sha256']))
        return dict(item=item,body=body,path=path,project_body=project_body,adopted=adopted,dispatch_body=dispatch_body,dispatched=dispatched[0],evidence_body=evidence_body,evidence=evidence,history=history)

    def test_real_http_native_chain_concurrent_receipts_current_scope_and_immutable_runtime(self):
        data=self.workflow()
        self.call('GET',data['path'],{'ignored':True},status=400)
        self.call('POST',data['path']+'/dispatch?ignored=1',data['dispatch_body'],status=400)
        collision=self.call('POST',data['path']+'/dispatch',dict(data['dispatch_body'],title='Different nonce body'),status=409).json
        self.assertNotIn('request_resolution',collision)
        rejected=self.call('POST',data['path']+'/dispatch',dict(data['dispatch_body'],request_id=req()['request_id']),status=409).json
        self.assertEqual(rejected['request_resolution'],'not_accepted')
        tech=self.call('POST','/users',dict(email='service-tech-pg@example.test',password='Synthetic-service-tech-password-123',role='technician'),status=201).json
        token=self.login('service-tech-pg@example.test','Synthetic-service-tech-password-123')
        self.call('GET',data['path'],token=token,status=404)
        self.call('POST',data['path']+'/dispatch',data['dispatch_body'],token=token,status=404)
        device=self.call('POST','/business/offline/access',{},status=201).json['token']
        self.call('GET',data['path'],token=device,status=403)
        for table in protected_tables():
            column=self.office.db.execute('SELECT * FROM '+table+' LIMIT 1').description[0].name
            for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table,'TRUNCATE '+table):
                with self.subTest(table=table,statement=statement),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db:self.office.db.execute(statement)
            with psycopg.connect(fixture.DSN,autocommit=True) as migrator:
                for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table):
                    with self.subTest(table=table,statement=statement),self.assertRaisesRegex(psycopg.Error,'immutable service history'):
                        with migrator.transaction():migrator.execute('SET LOCAL ROLE "smartplan-migrator"');migrator.execute(statement)
        self.reopen()
        self.assertEqual(self.call('POST',data['path']+'/dispatch',data['dispatch_body']).json,data['dispatched'])
        self.assertEqual(self.call('POST','/business/service/cases',data['body']).json,data['item'])
        business_schema.validate_integrity(self.office)

    def test_actual_backup_restore_preserves_original_cases_dispatch_and_signed_evidence(self):
        data=self.workflow();actor,runtime=self.owner,self.runtime
        before=release.snapshot_fingerprint(fixture.DSN);self.office.db.close()
        migrate(fixture.DSN,owner_role='smartplan-migrator',compatibility_mode='business',require_business_modules=True)
        self.assertEqual(release.snapshot_fingerprint(fixture.DSN),before)
        target=make_conninfo(fixture.DSN,dbname='smartplan_release_check');release.validate_dsns(fixture.DSN,target,test_mode=True)
        with psycopg.connect(fixture.DSN,autocommit=True) as admin:
            if admin.execute("SELECT 1 FROM pg_database WHERE datname='smartplan_release_check'").fetchone():raise RuntimeError('Existing restore target must remain untouched')
            admin.execute('CREATE DATABASE smartplan_release_check OWNER "smartplan-migrator" TEMPLATE template0')
        try:
            with tempfile.TemporaryDirectory(prefix='service-pg-restore-') as directory:
                saved=backup(fixture.DSN,directory);self.assertTrue(restore(saved,fixture.DSN,target,privileged_operator=True,test_mode=True)['restore_pending'])
            restored_runtime=make_conninfo(runtime,dbname='smartplan_release_check');verifier=PostgresOffice(restored_runtime,allow_restore_pending=True)
            try:self.assertFalse(complete_restore(verifier)['restore_pending'])
            finally:verifier.db.close()
            recovered=PostgresOffice(restored_runtime)
            try:
                api=Service(recovered)
                self.assertEqual(api.save(actor,data['body']),data['item'])
                self.assertEqual(api.command(actor,data['item']['id'],'project',data['project_body']),data['adopted'])
                self.assertEqual(api.command(actor,data['item']['id'],'dispatch',data['dispatch_body']),data['dispatched'])
                self.assertEqual(api.command(actor,data['item']['id'],'evidence',data['evidence_body']),data['evidence'])
                self.assertEqual(api.history(actor,data['item']['id']),data['history'])
                business_schema.validate_integrity(recovered);after=release.snapshot_fingerprint(target)
                for table in protected_tables():self.assertEqual(after[table],before[table],table)
                self.assertEqual(release.snapshot_fingerprint(fixture.DSN),before)
            finally:recovered.db.close()
        finally:
            with psycopg.connect(fixture.DSN,autocommit=True) as admin:admin.execute('DROP DATABASE smartplan_release_check')


if __name__=='__main__':unittest.main()
