"""Guarded loopback PostgreSQL, actual HTTP, claims, ACLs and populated restore."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import os
import threading
import tempfile
import unittest
from unittest.mock import patch
import uuid

import psycopg

import business_schema
from business_company_events import CompanyEvents,TABLES,validate_integrity
from core import Problem
from online import test_customer_execution_journey_pg as journey
from online import test_assistant_pg as assistant_fixture
from online import release
from online.store import PostgresOffice
from online.storage import Storage
from online.instance import bind
from online.web import create_app
from online.test_postgres_accounting_components_integration import disposable_restore,evidence_for,approve
from test_business_assistant import SyntheticDeliveryForTests

fixture=journey.fixture
request=fixture.request
BASE='/business/company-events'


@unittest.skipUnless(fixture.DSN,'Guarded disposable loopback PostgreSQL fixture required')
class CompanyEventsPostgres(unittest.TestCase):
    login=journey.CustomerExecutionJourneyPostgres.login
    call=journey.CustomerExecutionJourneyPostgres.call
    dunning=assistant_fixture.AssistantPostgres.dunning

    def setUp(self):
        journey.CustomerExecutionJourneyPostgres.setUp(self)
        self.actor=self.office.user(self.token)
        self.instance=uuid.uuid4().hex
        directory=tempfile.TemporaryDirectory(prefix='synthetic-company-events-pg-')
        self.addCleanup(directory.cleanup);self.storage_config={'server':{'path':directory.name+'/company'}}
        # Actual explicit operator binding includes the key and private storage
        # marker; a genuine HTTP restart must verify the same installation.
        operator=PostgresOffice(fixture.DSN)
        try:bind(operator,self.instance,'office.example.test',self.key,Storage(operator,self.key,'office.example.test',config=self.storage_config))
        finally:operator.db.close()
        self.reopen()
        self.project=self.call('POST','/projects',dict(name='Synthetic company events',customer='Synthetic customer'),status=201).json['id']

    def reopen(self):
        if not hasattr(self,'instance'):
            return journey.CustomerExecutionJourneyPostgres.reopen(self)
        if hasattr(self,'office'):self.office.db.close()
        self.office=PostgresOffice(self.runtime);self.addCleanup(self.office.db.close)
        self.app=create_app(office=self.office,key=self.key,host='office.example.test',instance_id=self.instance,storage_config=self.storage_config)
        self.client=self.app.test_client()

    def task(self):
        return self.call('POST','/projects/'+self.project+'/tasks',request(title='Synthetic overdue source',details='Original fixture task',
            due_date=(self.now-timedelta(days=3)).date().isoformat(),priority='normal',status='todo',assignee_id=self.actor['id']),status=201).json

    def rule(self, mode='auto', **changes):
        body=request(id=uuid.uuid4().hex,revision=0,title='Explicit synthetic PG event rule',enabled=True,project_ids=[self.project],
            trigger='task.overdue',action='task.create',mode=mode,conditions=[],template=dict(title='Actual PG follow-up',details='Fixed template',priority='normal',due_days=None),
            responsible_id=self.actor['id'],confirmation=True)
        body.update(changes)
        return self.call('POST',BASE+'/rules',body).json

    def scan(self): return self.call('POST',BASE+'/scan',request(limit=100,after=None)).json

    def test_two_connections_claim_one_actual_task_and_restart_preserves_exact_acceptance(self):
        self.task();self.rule();barrier=threading.Barrier(2)
        def work(_):
            office=PostgresOffice(self.runtime)
            try:
                api=CompanyEvents(office);barrier.wait(timeout=10)
                return api.scan(self.actor,request(limit=100,after=None))
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            runs=list(pool.map(work,range(2)))
        ids=[run['items'][0]['plan_ids'][0] for run in runs]
        self.assertEqual(ids[0],ids[1])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM workspace_items').fetchone()[0],2)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_company_event_executions').fetchone()[0],1)
        row=self.office.db.execute('SELECT * FROM business_company_event_requests WHERE operation=?',('execute:'+ids[0],)).fetchone()
        body=json.loads(row['request_json'])
        accepted=self.call('POST',BASE+'/plans/'+ids[0]+'/execute',body).json
        self.reopen()
        self.assertEqual(self.call('POST',BASE+'/plans/'+ids[0]+'/execute',body).json,accepted)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM workspace_items').fetchone()[0],2)
        for table in TABLES:
            column=self.office.db.execute('SELECT * FROM '+table+' LIMIT 1').description[0].name
            for query in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table,'TRUNCATE '+table):
                with self.subTest(table=table,query=query),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db:self.office.db.execute(query)
        validate_integrity(self.office);business_schema.validate_integrity(self.office)

    def test_actual_invoice_and_dunning_sources_use_native_gates_and_one_synthetic_transport(self):
        sink=SyntheticDeliveryForTests()
        with patch.dict(os.environ,{'SMARTPLAN_SMTP_FROM':'seller@example.test'}),patch('business_delivery.configuration',return_value=object()),patch('business_delivery.configured_transport',return_value=sink):
            invoice,mail=self.dunning(self.project)
            self.rule(mode='approval',trigger='dunning.ready',action='dunning.email',template={})
            self.rule(mode='auto',trigger='payment.overdue',conditions=[dict(field='open_minor',operator='gte',value='10000')])
            run=self.scan();plans=[self.call('GET',BASE+'/plans/'+key).json for item in run['items'] for key in item['plan_ids']]
            reminder=next(p for p in plans if p['action']=='dunning.email')
            followup=next(p for p in plans if p['action']=='task.create')
            self.assertEqual(followup['status'],'succeeded')
            self.assertEqual(followup['context']['sources'][0]['data']['open_minor'],'11900')
            self.call('POST',BASE+'/plans/'+reminder['id']+'/approve',request(plan_sha256=reminder['sha256'],reason='Exact original PDF and recipient reviewed',confirmation=True))
            body=request(plan_sha256=reminder['sha256'],confirmation=True)
            done=self.call('POST',BASE+'/plans/'+reminder['id']+'/execute',body).json
            self.assertEqual(done['status'],'succeeded');self.assertEqual(len(sink.jobs),1)
            self.assertEqual(sink.jobs[0]['recipient'],'buyer@example.test')
            self.assertEqual(self.call('POST',BASE+'/plans/'+reminder['id']+'/execute',body).json,done)
            self.scan();self.assertEqual(len(sink.jobs),1)
        business_schema.validate_integrity(self.office)

    def test_populated_restore_preserves_claims_and_exact_receipts_and_suspends_pending(self):
        self.task();self.task();self.rule(mode='approval')
        run=self.scan();ids=[key for item in run['items'] for key in item['plan_ids']]
        first,pending=[self.call('GET',BASE+'/plans/'+key).json for key in ids]
        for plan in (first,pending):
            self.call('POST',BASE+'/plans/'+plan['id']+'/approve',request(plan_sha256=plan['sha256'],reason='Original source reviewed',confirmation=True))
        body=request(plan_sha256=first['sha256'],confirmation=True)
        accepted=self.call('POST',BASE+'/plans/'+first['id']+'/execute',body).json
        before=release.snapshot_fingerprint(fixture.DSN)
        self.office.db.close()
        with disposable_restore(self.runtime) as (target,runtime,report):
            recovered=PostgresOffice(runtime)
            try:
                api=CompanyEvents(recovered)
                self.assertEqual(api.execute(self.actor,first['id'],body)['outcome'],accepted['outcome'])
                self.assertEqual(api.plan(self.actor,pending['id'])['status'],'suspended_after_restore')
                with self.assertRaises(Problem) as blocked:api.scan(self.actor,request(limit=100,after=None))
                self.assertEqual(blocked.exception.status,409)
                evidence=evidence_for(recovered,report)
            finally:recovered.db.close()
            # Operator-owned reconciliation cannot be manufactured by runtime.
            operator=PostgresOffice(target,allow_restore_pending=True)
            try:approve(operator,evidence)
            finally:operator.db.close()
            recovered=PostgresOffice(runtime)
            try:
                api=CompanyEvents(recovered);again=api.scan(self.actor,request(limit=100,after=None))
                plans=[api.plan(self.actor,key) for item in again['items'] for key in item['plan_ids']]
                renewed=next(p for p in plans if p['action_key']==pending['action_key'])
                self.assertNotEqual(renewed['id'],pending['id']);self.assertEqual(renewed['status'],'awaiting_approval')
                self.assertIsNone(renewed['decision'])
                self.assertEqual(recovered.db.execute('SELECT COUNT(*) FROM workspace_items').fetchone()[0],3)
                business_schema.validate_integrity(recovered)
            finally:recovered.db.close()
        self.assertEqual(release.snapshot_fingerprint(fixture.DSN),before)
