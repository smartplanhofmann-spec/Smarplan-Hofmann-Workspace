"""Actual PostgreSQL/MFA/ACL/backup/restore for the sales adoption chain."""
from concurrent.futures import ThreadPoolExecutor
import tempfile
import unittest

import psycopg
from psycopg.conninfo import make_conninfo
import business_schema
from business_sales import Sales,protected_tables
from online import release,test_customer_execution_journey_pg as journey
from online.backup import backup
from online.restore import complete_restore,restore
from online.store import PostgresOffice,migrate
import test_business_sales as domain

fixture=journey.fixture
req=domain.req


@unittest.skipUnless(fixture.DSN,'Guarded disposable PostgreSQL fixture required')
class SalesPostgres(unittest.TestCase):
    setUp=journey.CustomerExecutionJourneyPostgres.setUp
    reopen=journey.CustomerExecutionJourneyPostgres.reopen
    login=journey.CustomerExecutionJourneyPostgres.login
    call=journey.CustomerExecutionJourneyPostgres.call
    command=domain.SalesTests.command
    adopt_body=domain.SalesTests.adopt_body

    def workflow(self):
        self.owner=self.office.user(self.token);self.api=Sales(self.office)
        self.contact=self.call('POST','/business/contacts',req(name='Synthetic PG sales customer',email='sales-pg@example.test',
            persons=[dict(name='Synthetic contact',role_label='billing',email='buyer-pg@example.test',phone='')],
            addresses=[dict(purpose='billing',label='Main',street='Synthetic street 10',postal_code='10115',city='Berlin',country='DE')]),status=201).json
        inquiry=self.call('POST','/inquiries',req(subject='Synthetic PG inquiry',message='Please prepare an offer.',sender_email='sales-pg@example.test'),status=201).json
        body=self.command(inquiry_id=inquiry['id']);item=self.call('POST','/business/sales/opportunities',body).json
        self.assertEqual(self.call('POST','/business/sales/opportunities',body).json,item)
        current=self.call('GET','/business/sales/opportunities/'+item['id']).json
        self.assertEqual(self.call('GET','/business/sales/options?customer_id='+self.contact['id']).json['customer_id'],self.contact['id'])
        self.assertEqual(self.call('GET','/business/sales/opportunities?customer_id='+self.contact['id']).json['summary']['weighted_net_minor'],61728)
        activity=self.call('POST','/business/sales/opportunities/'+item['id']+'/activities',req(kind='call',text='Synthetic documented call',occurred_on=self.today,supersedes_id=None,correction_reason='')).json
        project_command=self.adopt_body(item);project=self.call('POST','/business/sales/opportunities/'+item['id']+'/project',project_command).json
        self.assertEqual(self.call('POST','/business/sales/opportunities/'+item['id']+'/project',project_command).json,project)
        self.assertEqual(self.call('GET','/inquiries/'+inquiry['id']).json['project_id'],project['project_id'])
        offer_command=self.adopt_body(item,'offer');offer=self.call('POST','/business/sales/opportunities/'+item['id']+'/offer',offer_command).json
        document=self.call('GET','/business/documents/'+offer['document_id']).json
        self.assertEqual((document['status'],document['totals']['net']),('draft','159.90'))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM projects').fetchone()[0],1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_documents').fetchone()[0],1)
        return dict(item=item,body=body,project=project,project_command=project_command,offer=offer,offer_command=offer_command)

    def test_http_canonical_chain_concurrent_receipts_fresh_rights_and_immutable_runtime(self):
        data=self.workflow()
        def replay():
            office=PostgresOffice(self.runtime)
            try:return Sales(office).save(self.owner,data['body'])
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as workers:
            results=list(workers.map(lambda _:replay(),range(2)))
        self.assertEqual(results,[data['item'],data['item']])
        tech=self.call('POST','/users',dict(email='sales-tech-pg@example.test',password='Synthetic-sales-tech-password-123',role='technician'),status=201).json
        token=self.login('sales-tech-pg@example.test','Synthetic-sales-tech-password-123')
        for suffix in ('','/'+data['item']['id'],'/'+data['item']['id']+'/history','/'+data['item']['id']+'/activities'):
            self.call('GET','/business/sales/opportunities'+suffix,token=token,status=403)
        self.call('POST','/business/sales/opportunities',data['body'],token=token,status=403)
        device=self.call('POST','/business/offline/access',{},status=201).json['token']
        self.call('GET','/business/sales/opportunities',token=device,status=403)
        self.call('GET','/business/sales/opportunities',{'ignored':True},status=400)
        self.call('POST','/business/sales/opportunities?ignored=1',data['body'],status=400)
        self.call('POST','/business/sales/opportunities',{**data['body'],'title':'Changed original request'},status=409)
        self.reopen()
        self.assertEqual(self.call('POST','/business/sales/opportunities/'+data['item']['id']+'/offer',data['offer_command']).json,data['offer'])
        for table in protected_tables():
            self.assertGreater(self.office.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],0)
            column=self.office.db.execute('SELECT * FROM '+table+' LIMIT 1').description[0].name
            for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table,'TRUNCATE '+table):
                with self.subTest(table=table,statement=statement),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db:self.office.db.execute(statement)
            with psycopg.connect(fixture.DSN,autocommit=True) as migrator:
                for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table):
                    with self.subTest(table=table,guard=statement),self.assertRaisesRegex(psycopg.Error,'immutable sales history'):
                        with migrator.transaction():
                            migrator.execute('SET LOCAL ROLE "smartplan-migrator"');migrator.execute(statement)
        business_schema.validate_integrity(self.office)

    def test_real_backup_restore_preserves_forecasts_history_projects_and_offer_receipts(self):
        data=self.workflow();actor,runtime=self.owner,self.runtime
        before=release.snapshot_fingerprint(fixture.DSN);self.office.db.close()
        migrate(fixture.DSN,owner_role='smartplan-migrator',compatibility_mode='business',require_business_modules=True)
        self.assertEqual(release.snapshot_fingerprint(fixture.DSN),before)
        target=make_conninfo(fixture.DSN,dbname='smartplan_release_check');release.validate_dsns(fixture.DSN,target,test_mode=True)
        with psycopg.connect(fixture.DSN,autocommit=True) as admin:
            if admin.execute("SELECT 1 FROM pg_database WHERE datname='smartplan_release_check'").fetchone():raise RuntimeError('Existing restore target must remain untouched')
            admin.execute('CREATE DATABASE smartplan_release_check OWNER "smartplan-migrator" TEMPLATE template0')
        try:
            with tempfile.TemporaryDirectory(prefix='sales-pg-restore-') as directory:
                saved=backup(fixture.DSN,directory);self.assertTrue(restore(saved,fixture.DSN,target,privileged_operator=True,test_mode=True)['restore_pending'])
            restored_runtime=make_conninfo(runtime,dbname='smartplan_release_check');verifier=PostgresOffice(restored_runtime,allow_restore_pending=True)
            try:self.assertFalse(complete_restore(verifier)['restore_pending'])
            finally:verifier.db.close()
            recovered=PostgresOffice(restored_runtime)
            try:
                api=Sales(recovered)
                self.assertEqual(api.save(actor,data['body']),data['item'])
                self.assertEqual(api.adoption(actor,data['item']['id'],'offer',data['offer_command']),data['offer'])
                self.assertEqual(api.history(actor,data['item']['id'])['items'],[data['item']])
                self.assertEqual(len(api.activities(actor,data['item']['id'])['items']),1)
                business_schema.validate_integrity(recovered)
                after=release.snapshot_fingerprint(target)
                for table in protected_tables():self.assertEqual(after[table],before[table],table)
                self.assertEqual(release.snapshot_fingerprint(fixture.DSN),before)
            finally:recovered.db.close()
        finally:
            with psycopg.connect(fixture.DSN,autocommit=True) as admin:admin.execute('DROP DATABASE smartplan_release_check')


if __name__=='__main__':unittest.main()
