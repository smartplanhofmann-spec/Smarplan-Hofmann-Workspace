"""Actual MFA/HTTP, PostgreSQL concurrent custody, native calendar and restore."""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import tempfile
import unittest

import psycopg
from psycopg.conninfo import make_conninfo
import business_schema
from business_resource_custody import ResourceCustody,MAX_FILE,RETURN_FIELDS,protected_tables
from online import release,test_customer_execution_journey_pg as journey
from online.backup import backup
from online.restore import complete_restore,restore
from online.store import PostgresOffice,migrate
from test_business_resource_custody import req

fixture=journey.fixture


@unittest.skipUnless(fixture.DSN,'Guarded disposable PostgreSQL fixture required')
class ResourceCustodyPostgres(unittest.TestCase):
    setUp=journey.CustomerExecutionJourneyPostgres.setUp
    reopen=journey.CustomerExecutionJourneyPostgres.reopen
    login=journey.CustomerExecutionJourneyPostgres.login
    call=journey.CustomerExecutionJourneyPostgres.call

    def workflow(self):
        self.owner=self.office.user(self.token);self.api=ResourceCustody(self.office)
        employee=self.call('POST','/business/employees',req(user_id=self.owner['id'],name='Synthetic actual PG employee'),status=201).json
        resource=self.call('POST','/business/resources',req(name='Synthetic real PG tool',kind='tool',code='SYN-PG-TOOL'),status=201).json
        resource_id=resource['id'];path='/business/resource-custody/'+resource_id
        project=self.office.add_project(self.owner,'Synthetic actual resource project',customer='Synthetic actual resource customer')
        def command(action,**values):
            current=self.call('GET',path).json
            body=req(source_sha256=current['source_sha256'],confirmation=True,**values)
            return self.call('POST',path+'/'+action,body).json,body
        profile,profile_body=command('profile',revision=0,serial_number='SYN-PG-1',manufacturer='Synthetic',model='Evidence tool',location='Actual shelf',condition='serviceable',notes='Synthetic factual identity',reason='Actual stock confirmed')
        requirement,_=command('requirements',revision=0,title='Synthetic operator inspection',due_on=self.today,required_for_use=True,active=True,notes='Actual requirement',reason='Operator requires original proof')
        appointment=req(project_id=project,title='Synthetic resource use',start_at=(self.now+timedelta(days=1)).isoformat(),end_at=(self.now+timedelta(days=1,hours=1)).isoformat(),timezone='Europe/Berlin',employee_ids=[employee['id']],resource_ids=[resource_id])
        self.call('POST','/business/appointments',dict(appointment,override_conflicts=True,override_reason='Must not bypass usage evidence'),status=409)
        raw=b'%PDF-1.7\n'+b'x'*(MAX_FILE-9)
        upload_body=req(filename='actual-inspection.pdf',media_type='application/pdf',content_base64=base64.b64encode(raw).decode())
        original=self.call('POST',path+'/files',upload_body).json
        self.assertEqual(self.call('POST',path+'/files',upload_body).json,original)
        self.assertEqual(self.call('GET',path+'/files/'+original['id']+'/original').data,raw)
        self.call('POST',path+'/files',req(filename='oversize.pdf',media_type='application/pdf',content_base64=base64.b64encode(b'x'*(MAX_FILE+1)).decode()),status=413)
        inspection,_=command('inspections',requirement_id=requirement['record']['id'],requirement_revision=1,performed_at=(self.now-timedelta(days=1)).isoformat(),inspector='Synthetic actual inspector',result='passed',next_due_on=(self.now+timedelta(days=5)).date().isoformat(),evidence_id=original['id'],note='Actual original checked',supersedes_id=None,correction_reason='')
        current=self.call('GET',path).json
        handoff_body=req(source_sha256=current['source_sha256'],confirmation=True,employee_id=employee['id'],project_id=project,issued_at=(self.now-timedelta(hours=3)).isoformat(),expected_return_at=(self.now-timedelta(hours=2)).isoformat(),condition='serviceable',notes='Actual synthetic handoff',evidence_id=original['id'])
        def issue_once():
            office=PostgresOffice(self.runtime)
            try:return ResourceCustody(office).command(self.owner,resource_id,'handoffs',handoff_body)
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:issued=list(pool.map(lambda _:issue_once(),range(2)))
        self.assertEqual(issued[0],issued[1]);self.assertEqual(self.call('POST',path+'/handoffs',handoff_body).json,issued[0])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_resource_handoffs').fetchone()[0],1)
        self.call('POST','/business/appointments',dict(appointment,request_id=req()['request_id'],employee_ids=[],override_conflicts=True,override_reason='No custody bypass'),status=409)
        booked=self.call('POST','/business/appointments',appointment,status=201).json
        returned,_=command('returns',handoff_id=issued[0]['record']['id'],returned_at=(self.now-timedelta(hours=1)).isoformat(),received_by_employee_id=employee['id'],condition='out_of_service',notes='Recorded damage on actual return',evidence_id=original['id'])
        other=dict(appointment,request_id=req()['request_id'],start_at=(self.now+timedelta(days=2)).isoformat(),end_at=(self.now+timedelta(days=2,hours=1)).isoformat())
        self.call('POST','/business/appointments',other,status=409)
        values={k:returned['record'][k] for k in RETURN_FIELDS};values.update(condition='serviceable',notes='Original proves transcription error')
        corrected,correction_body=command('corrections',target_kind='return',target_id=returned['record']['id'],values=values,reason='Explicit original-backed correction',evidence_id=original['id'])
        self.call('POST','/business/appointments',other,status=201)
        self.assertEqual(self.call('POST',path+'/handoffs',handoff_body).json,issued[0])
        self.assertEqual(self.call('POST',path+'/profile',profile_body).json,profile)
        history=self.call('GET',path+'/history').json
        business_schema.validate_integrity(self.office)
        return dict(path=path,resource_id=resource_id,profile=profile,profile_body=profile_body,raw=raw,original=original,upload_body=upload_body,handoff=issued[0],handoff_body=handoff_body,corrected=corrected,correction_body=correction_body,history=history)

    def test_real_mfa_http_actual_calendar_concurrent_custody_and_current_permissions(self):
        data=self.workflow();path=data['path']
        self.call('GET',path,{'ignored':True},status=400)
        self.call('POST',path+'/handoffs?ignored=1',data['handoff_body'],status=400)
        collision=self.call('POST',path+'/handoffs',dict(data['handoff_body'],notes='Different same nonce'),status=409).json;self.assertNotIn('request_resolution',collision)
        rejected=self.call('POST',path+'/handoffs',dict(data['handoff_body'],request_id=req()['request_id']),status=409).json;self.assertEqual(rejected['request_resolution'],'not_accepted')
        self.call('POST','/users',dict(email='custody-tech-pg@example.test',password='Synthetic-resource-tech-password-123',role='technician'),status=201)
        token=self.login('custody-tech-pg@example.test','Synthetic-resource-tech-password-123')
        self.call('GET',path,token=token,status=403);self.call('POST',path+'/handoffs',data['handoff_body'],token=token,status=403)
        device=self.call('POST','/business/offline/access',{},status=201).json['token'];self.call('GET',path,token=device,status=403)
        for table in protected_tables():
            column=self.office.db.execute('SELECT * FROM '+table+' LIMIT 1').description[0].name
            for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table,'TRUNCATE '+table):
                with self.subTest(table=table,statement=statement),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db:self.office.db.execute(statement)
            with psycopg.connect(fixture.DSN,autocommit=True) as migrator:
                for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table):
                    with self.subTest(table=table,statement=statement),self.assertRaisesRegex(psycopg.Error,'immutable resource custody evidence'):
                        with migrator.transaction():migrator.execute('SET LOCAL ROLE "smartplan-migrator"');migrator.execute(statement)
        self.reopen();self.assertEqual(self.call('POST',path+'/handoffs',data['handoff_body']).json,data['handoff'])
        business_schema.validate_integrity(self.office)

    def test_actual_backup_restore_preserves_originals_complete_custody_history_and_receipts(self):
        data=self.workflow();actor,runtime=self.owner,self.runtime
        before=release.snapshot_fingerprint(fixture.DSN);self.office.db.close()
        migrate(fixture.DSN,owner_role='smartplan-migrator',compatibility_mode='business',require_business_modules=True)
        self.assertEqual(release.snapshot_fingerprint(fixture.DSN),before)
        target=make_conninfo(fixture.DSN,dbname='smartplan_release_check');release.validate_dsns(fixture.DSN,target,test_mode=True)
        with psycopg.connect(fixture.DSN,autocommit=True) as admin:
            if admin.execute("SELECT 1 FROM pg_database WHERE datname='smartplan_release_check'").fetchone():raise RuntimeError('Existing restore target must remain untouched')
            admin.execute('CREATE DATABASE smartplan_release_check OWNER "smartplan-migrator" TEMPLATE template0')
        try:
            with tempfile.TemporaryDirectory(prefix='resource-custody-pg-restore-') as directory:
                saved=backup(fixture.DSN,directory);self.assertTrue(restore(saved,fixture.DSN,target,privileged_operator=True,test_mode=True)['restore_pending'])
            restored_runtime=make_conninfo(runtime,dbname='smartplan_release_check');verifier=PostgresOffice(restored_runtime,allow_restore_pending=True)
            try:self.assertFalse(complete_restore(verifier)['restore_pending'])
            finally:verifier.db.close()
            recovered=PostgresOffice(restored_runtime)
            try:
                api=ResourceCustody(recovered)
                for action in ('profile','handoff','correction'):
                    endpoint={'handoff':'handoffs','correction':'corrections'}.get(action,action);result=data[{'correction':'corrected'}.get(action,action)]
                    self.assertEqual(api.command(actor,data['resource_id'],endpoint,data[action+'_body']),result)
                self.assertEqual(api.upload(actor,data['resource_id'],data['upload_body']),data['original'])
                self.assertEqual(bytes(api.file(data['resource_id'],data['original']['id'])['content']),data['raw'])
                self.assertEqual(api.history(actor,data['resource_id']),data['history']);business_schema.validate_integrity(recovered)
                after=release.snapshot_fingerprint(target)
                for table in protected_tables():self.assertEqual(after[table],before[table],table)
                self.assertEqual(release.snapshot_fingerprint(fixture.DSN),before)
            finally:recovered.db.close()
        finally:
            with psycopg.connect(fixture.DSN,autocommit=True) as admin:admin.execute('DROP DATABASE smartplan_release_check')


if __name__=='__main__':unittest.main()
