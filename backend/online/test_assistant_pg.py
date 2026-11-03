"""Real PostgreSQL/MFA source, policy, mail gates and disaster recovery.

All identities, messages and transports are synthetic. The only database allowed
is the existing guarded disposable loopback fixture; no provider is contacted.
"""
from datetime import timedelta
import os
import tempfile
import unittest
from unittest.mock import patch
import uuid

import psycopg
from psycopg.conninfo import make_conninfo

import business_assistant
import business_schema
from business_assistant import Assistant, protected_tables
from business_finance import Finance, default_rules
from core import Problem
from online import release, test_customer_execution_journey_pg as journey
from online.backup import backup
from online.restore import complete_restore, restore
from online.store import PostgresOffice, migrate
from test_business_assistant import SyntheticDeliveryForTests

fixture = journey.fixture
request = fixture.request


@unittest.skipUnless(fixture.DSN, 'Guarded disposable PostgreSQL fixture required')
class AssistantPostgres(unittest.TestCase):
    setUp = journey.CustomerExecutionJourneyPostgres.setUp
    reopen = journey.CustomerExecutionJourneyPostgres.reopen
    login = journey.CustomerExecutionJourneyPostgres.login
    call = journey.CustomerExecutionJourneyPostgres.call

    def rule(self, project, action='task.create', mode='approval'):
        return self.call('POST', '/business/assistant/rules', request(id=uuid.uuid4().hex,
            revision=0, project_id=project, title='Explicit synthetic policy', enabled=True,
            trigger='manual', action=action, mode=mode, conditions=[],
            responsible_id=self.office.user(self.token)['id'], confirmation=True)).json

    def change_rule(self, rule, mode):
        values = {key:rule[key] for key in ('id','revision','project_id','title','enabled',
            'trigger','action','mode','conditions','responsible_id')}
        return self.call('POST', '/business/assistant/rules', request(**{**values,'mode':mode},confirmation=True)).json

    def plan(self, project, *, sources=None, action='task.create', parameters=None):
        context = self.call('POST', '/business/assistant/contexts', request(project_id=project,
            sources=sources or [dict(kind='project',id=project)])).json
        plan = self.call('POST', '/business/assistant/plans', request(context_id=context['id'],
            trigger='manual', action=action, parameters=parameters or dict(title='Source-bound synthetic task',
                details='Created from an approved plan', due_date=None, priority='normal'),
            reason='Explicit synthetic request')).json
        return context, plan

    def approve(self, plan):
        return self.call('POST', '/business/assistant/plans/'+plan['id']+'/approve',
            request(plan_sha256=plan['sha256'],reason='Reviewed exact source, action and rule',confirmation=True)).json

    def workflow(self):
        project = self.call('POST', '/projects', dict(name='Synthetic assistant project',customer='Synthetic customer'),status=201).json['id']
        rule = self.rule(project)
        context, plan = self.plan(project)
        command = request(plan_sha256=plan['sha256'],confirmation=True)
        self.call('POST','/business/assistant/plans/'+plan['id']+'/execute',command,status=409)
        self.approve(plan)
        executed = self.call('POST','/business/assistant/plans/'+plan['id']+'/execute',command).json
        self.assertEqual(executed['status'],'succeeded')
        self.assertEqual(self.call('POST','/business/assistant/plans/'+plan['id']+'/execute',command).json,executed)
        return dict(project=project,rule=rule,context=context,plan=executed,command=command)

    def dunning(self, project):
        past = (self.now-timedelta(days=14)).date().isoformat()
        due = (self.now-timedelta(days=7)).date().isoformat()
        self.call('POST','/business/settings/branding',request(revision=0,company_name='Synthetic seller',
            address_line='Teststreet 1',postal_code='10115',city='Berlin',country='DE',vat_id='DE123456789',
            email='seller@example.test',issuer_mode='own',issuing_enabled=True,cutover_ack=True,
            cutover_date=past,einvoice_format='none'))
        draft = self.call('POST','/business/documents',request(project_id=project,kind='invoice',title='Synthetic overdue invoice',
            issue_date=past,due_date=due,buyer=dict(name='Synthetic buyer',address_line='Teststreet 2',postal_code='10117',
            city='Berlin',country='DE',email='buyer@example.test'),positions=[dict(description='Synthetic service',quantity='1',
            unit='HUR',unit_price_net='100',tax_rate='19',kind='labor')])).json
        invoice = self.call('POST','/business/documents/'+draft['id']+'/finalize',request(revision=draft['revision'])).json
        self.call('POST','/business/finance/dunning/settings',request(revision=0,**{**default_rules(),'enabled':True}))
        proposals = self.call('POST','/business/finance/dunning/preview',request(project_id=project)).json['items']
        self.assertEqual(len(proposals),1)
        approved = self.call('POST','/business/finance/dunning/proposals/'+proposals[0]['id']+'/approve',request(confirmation=True)).json
        return invoice, approved

    def test_actual_http_fresh_rights_restart_and_append_only_runtime_acl(self):
        data = self.workflow()
        technician = self.call('POST','/users',dict(email='assistant-tech@example.test',password='Synthetic-technician-password-123',role='technician'),status=201).json
        token = self.login('assistant-tech@example.test','Synthetic-technician-password-123')
        self.call('GET','/business/assistant/contexts/'+data['context']['id'],token=token,status=404)
        self.call('GET','/business/assistant/plans/'+data['plan']['id'],token=token,status=404)
        self.call('POST','/business/assistant/plans/'+data['plan']['id']+'/execute',data['command'],token=token,status=404)
        self.call('GET','/business/assistant/status',token='SPCT_'+'a'*43,status=401)
        device = self.call('POST','/business/offline/access',{},status=201).json['token']
        self.call('GET','/business/assistant/status',token=device,status=403)
        self.call('GET','/business/assistant/status',{'ignored':True},status=400)
        self.call('POST','/business/assistant/plans/'+data['plan']['id']+'/execute?ignored=1',data['command'],status=400)
        self.reopen()
        self.assertEqual(self.call('POST','/business/assistant/plans/'+data['plan']['id']+'/execute',data['command']).json,data['plan'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM workspace_items').fetchone()[0],1)
        for table in protected_tables():
            column = self.office.db.execute('SELECT * FROM '+table+' LIMIT 1').description[0].name
            for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table,'TRUNCATE '+table):
                with self.subTest(table=table,statement=statement),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db: self.office.db.execute(statement)
            if self.office.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]:
                with psycopg.connect(fixture.DSN,autocommit=True) as migrator:
                    for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table):
                        with self.subTest(table=table,guard=statement),self.assertRaisesRegex(psycopg.Error,'immutable assistant history'):
                            with migrator.transaction():
                                migrator.execute('SET LOCAL ROLE "smartplan-migrator"')
                                migrator.execute(statement)
        business_schema.validate_integrity(self.office)

    def test_dunning_policy_passes_both_native_gates_one_transport_and_exact_retry(self):
        data = self.workflow()
        sink = SyntheticDeliveryForTests()
        with patch.dict(os.environ,{'SMARTPLAN_SMTP_FROM':'seller@example.test'}), \
                patch('business_delivery.configuration',return_value=object()), \
                patch('business_delivery.configured_transport',return_value=sink):
            invoice, mail = self.dunning(data['project'])
            rule = self.rule(data['project'],action='dunning.email',mode='deny')
            row = Finance(self.office)._mail(mail['outbox_id'])
            native = request(confirmation=True,payload_sha256=row['payload_sha256'])
            path = '/business/finance/outbox/'+mail['outbox_id']+'/deliver'
            self.call('POST',path,native,status=403)
            rule = self.change_rule(rule,'approval')
            self.call('POST',path,native,status=409)
            _, plan = self.plan(data['project'],sources=[dict(kind='dunning',id=mail['outbox_id'])],
                action='dunning.email',parameters=dict(outbox_id=mail['outbox_id']))
            self.approve(plan)
            execute = request(plan_sha256=plan['sha256'],confirmation=True)
            actual = business_assistant.require_send_policy
            with patch.object(business_assistant,'require_send_policy',wraps=actual) as gates:
                completed = self.call('POST','/business/assistant/plans/'+plan['id']+'/execute',execute).json
            self.assertEqual(completed['status'],'succeeded')
            self.assertEqual(gates.call_count,2)
            self.assertEqual(len(sink.jobs),1)
            self.assertEqual(sink.jobs[0]['recipient'],'buyer@example.test')
            self.assertEqual(sink.jobs[0]['attachments'][0]['bytes'][:5],b'%PDF-')
            self.assertEqual(self.call('POST','/business/assistant/plans/'+plan['id']+'/execute',execute).json,completed)
            self.change_rule(rule,'deny')
            domain = self.office.db.execute('SELECT domain_request_id FROM business_assistant_executions WHERE plan_id=?',(plan['id'],)).fetchone()[0]
            known = self.call('POST',path,{**native,'request_id':domain}).json
            self.assertEqual(known['status'],'sent')
            self.assertEqual(len(sink.jobs),1)
        business_schema.validate_integrity(self.office)

    def test_dunning_rule_change_after_claim_blocks_transport_and_preserves_receipt(self):
        data = self.workflow()
        sink = SyntheticDeliveryForTests()
        with patch.dict(os.environ,{'SMARTPLAN_SMTP_FROM':'seller@example.test'}), \
                patch('business_delivery.configuration',return_value=object()), \
                patch('business_delivery.configured_transport',return_value=sink):
            _, mail = self.dunning(data['project'])
            rule = self.rule(data['project'],action='dunning.email')
            _, plan = self.plan(data['project'],sources=[dict(kind='dunning',id=mail['outbox_id'])],
                action='dunning.email',parameters=dict(outbox_id=mail['outbox_id']))
            self.approve(plan)
            actual, calls = business_assistant.require_send_policy, []
            def change_after_first_gate(*args):
                actual(*args)
                calls.append(True)
                if len(calls)==1:
                    values = {key:rule[key] for key in ('id','revision','project_id','title','enabled','trigger','action','mode','conditions','responsible_id')}
                    Assistant(self.office).save_rule(self.office.user(self.token),request(**{**values,'mode':'deny'},confirmation=True))
            with patch.object(business_assistant,'require_send_policy',side_effect=change_after_first_gate):
                result = self.call('POST','/business/assistant/plans/'+plan['id']+'/execute',request(plan_sha256=plan['sha256'],confirmation=True)).json
            self.assertEqual(result['status'],'blocked')
            self.assertEqual(sink.jobs,[])
            native = self.office.db.execute('SELECT outcome,provider_receipt FROM business_outbox_receipts WHERE outbox_id=? ORDER BY ordinal',(mail['outbox_id'],)).fetchall()
            self.assertEqual([r['outcome'] for r in native],['sending','failed'])
            self.assertEqual(native[-1]['provider_receipt'],'authorization_changed_before_io')
        business_schema.validate_integrity(self.office)

    def test_actual_backup_restore_preserves_completed_actions_and_suspends_pending_plan(self):
        data = self.workflow()
        _, pending = self.plan(data['project'])
        self.approve(pending)
        actor, runtime = self.office.user(self.token), self.runtime
        before = release.snapshot_fingerprint(fixture.DSN)
        self.office.db.close()
        migrate(fixture.DSN,owner_role='smartplan-migrator',compatibility_mode='business',require_business_modules=True)
        self.assertEqual(release.snapshot_fingerprint(fixture.DSN),before)
        target = make_conninfo(fixture.DSN,dbname='smartplan_release_check')
        release.validate_dsns(fixture.DSN,target,test_mode=True)
        with psycopg.connect(fixture.DSN,autocommit=True) as admin:
            if admin.execute("SELECT 1 FROM pg_database WHERE datname='smartplan_release_check'").fetchone():
                raise RuntimeError('Existing restore target must remain untouched')
            admin.execute('CREATE DATABASE smartplan_release_check OWNER "smartplan-migrator" TEMPLATE template0')
        try:
            with tempfile.TemporaryDirectory(prefix='assistant-pg-restore-') as directory:
                saved = backup(fixture.DSN,directory)
                self.assertTrue(restore(saved,fixture.DSN,target,privileged_operator=True,test_mode=True)['restore_pending'])
            restored_runtime = make_conninfo(runtime,dbname='smartplan_release_check')
            verifier = PostgresOffice(restored_runtime,allow_restore_pending=True)
            try: self.assertFalse(complete_restore(verifier)['restore_pending'])
            finally: verifier.db.close()
            recovered = PostgresOffice(restored_runtime)
            try:
                api = Assistant(recovered)
                self.assertEqual(api.plan(actor,data['plan']['id']),data['plan'])
                self.assertEqual(api.plan(actor,pending['id'])['status'],'suspended_after_restore')
                with self.assertRaises(Problem) as blocked:
                    api.execute(actor,pending['id'],request(plan_sha256=pending['sha256'],confirmation=True))
                self.assertEqual(blocked.exception.status,409)
                self.assertEqual(api.execute(actor,data['plan']['id'],data['command']),data['plan'])
                self.assertEqual(recovered.db.execute('SELECT COUNT(*) FROM workspace_items').fetchone()[0],1)
                business_schema.validate_integrity(recovered)
                after = release.snapshot_fingerprint(target)
                for table in protected_tables():
                    if table!='business_assistant_suspensions': self.assertEqual(after[table],before[table],table)
                self.assertEqual(release.snapshot_fingerprint(fixture.DSN),before)
            finally: recovered.db.close()
        finally:
            with psycopg.connect(fixture.DSN,autocommit=True) as admin:
                admin.execute('DROP DATABASE smartplan_release_check')


if __name__=='__main__': unittest.main()
