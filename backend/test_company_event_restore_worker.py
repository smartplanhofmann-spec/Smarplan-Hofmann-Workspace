"""Actual restoration, interrupted claims and deterministic worker pages."""
from pathlib import Path
import sqlite3
import unittest
import uuid
import os
from unittest.mock import patch

import business_schema
from business_company_events import CompanyEvents,validate_integrity
from company_event_worker import process
from core import Office,Problem
from restore import restore
import test_business_company_events as fixture
import test_accounting_openings_registration as reconciliation

request=fixture.request


class CompanyEventRestoreWorkerTests(unittest.TestCase):
    setUp=fixture.CompanyEventTests.setUp
    task=fixture.CompanyEventTests.task
    rule=fixture.CompanyEventTests.rule
    scan=fixture.CompanyEventTests.scan
    plans_for=fixture.CompanyEventTests.plans_for
    problem=fixture.CompanyEventTests.problem
    final_offer=fixture.CompanyEventTests.final_offer

    def test_actual_restore_keeps_completed_claim_and_reprepares_only_unstarted_plan(self):
        self.task();self.task();self.rule(mode='approval')
        run,_=self.scan();finished,pending=self.plans_for(run)
        for plan in (finished,pending):
            self.api.decide(self.owner,plan['id'],True,request(plan_sha256=plan['sha256'],reason='Reviewed original',confirmation=True))
        command=request(plan_sha256=finished['sha256'],confirmation=True)
        accepted=self.api.execute(self.owner,finished['id'],command)
        target=self.path.parent/'restored-company-events.sqlite3';restore(self.path,target)
        recovered=Office(target);self.addCleanup(recovered.db.close)
        api=CompanyEvents(recovered,clock=self.clock)
        self.assertEqual(api.execute(self.owner,finished['id'],command)['outcome'],accepted['outcome'])
        self.assertEqual(api.plan(self.owner,pending['id'])['status'],'suspended_after_restore')
        self.problem(409,api.scan,self.owner,request(limit=100,after=None))
        evidence=reconciliation.report(recovered)
        business_schema.reconcile_local_financial_restore(recovered,evidence,reconciliation.digest(evidence),application_stopped=True)
        again=api.scan(self.owner,request(limit=100,after=None))
        plans=[api.plan(self.owner,p) for item in again['items'] for p in item['plan_ids']]
        fresh=next(p for p in plans if p['action_key']==pending['action_key'])
        self.assertNotEqual(fresh['id'],pending['id']);self.assertEqual(fresh['status'],'awaiting_approval')
        self.assertEqual(fresh['reprepared_after_restore'],business_schema.state(recovered)['restore_id'])
        self.assertIsNone(fresh['decision'])
        self.assertEqual(recovered.db.execute('SELECT COUNT(*) FROM workspace_items').fetchone()[0],3)
        validate_integrity(recovered);business_schema.validate_integrity(recovered)

    def test_worker_pages_resume_original_commands_and_never_duplicate_products(self):
        for _ in range(5):self.task()
        self.rule();root_id=uuid.uuid4().hex
        limited=process(self.office,self.owner,request_id=root_id,page_size=2,max_pages=2,clock=self.clock)
        self.assertFalse(limited['complete']);self.assertIsNotNone(limited['next_after'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM workspace_items').fetchone()[0],9)
        completed=process(self.office,self.owner,request_id=root_id,page_size=2,max_pages=10,clock=self.clock)
        self.assertTrue(completed['complete']);self.assertIsNone(completed['next_after']);self.assertEqual(len(completed['runs']),3)
        self.assertEqual([r['id'] for r in completed['runs'][:2]],[r['id'] for r in limited['runs']])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM workspace_items').fetchone()[0],10)
        self.assertEqual(process(self.office,self.owner,request_id=root_id,page_size=2,max_pages=10,clock=self.clock),completed)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_company_event_executions').fetchone()[0],5)
        validate_integrity(self.office)

    def test_missing_original_execution_receipt_blocks_live_known_replay_and_history(self):
        self.task();self.rule();run,_=self.scan();plan=self.plans_for(run)[0]
        receipt=self.office.db.execute("SELECT * FROM business_company_event_requests WHERE operation=?",('execute:'+plan['id'],)).fetchone()
        import json
        command=json.loads(receipt['request_json'])
        self.office.db.execute('BEGIN')
        try:
            self.office.db.execute('DROP TRIGGER business_company_event_requests_delete_guard')
            self.office.db.execute('DELETE FROM business_company_event_requests WHERE request_id=?',(command['request_id'],))
            self.problem(409,self.api.execute,self.owner,plan['id'],command)
            self.problem(409,self.api.plan,self.owner,plan['id'])
            with self.assertRaises(ValueError):validate_integrity(self.office)
        finally:self.office.db.rollback()
        self.assertEqual(self.api.execute(self.owner,plan['id'],command)['status'],'succeeded')

    def test_immutable_scans_and_claims_cannot_be_replaced(self):
        self.task();self.rule();self.scan()
        for table in ('business_company_event_runs','business_company_event_executions','business_company_event_requests'):
            row=dict(self.office.db.execute('SELECT * FROM '+table+' LIMIT 1').fetchone())
            with self.subTest(table=table),self.assertRaises(sqlite3.DatabaseError),self.office.db:
                self.office.db.execute('INSERT OR REPLACE INTO '+table+'('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',tuple(row.values()))
        validate_integrity(self.office)

    def test_missing_original_approval_receipt_blocks_fresh_execution(self):
        self.task();self.rule(mode='approval');run,_=self.scan();plan=self.plans_for(run)[0]
        command=request(plan_sha256=plan['sha256'],reason='Exact source reviewed',confirmation=True)
        self.api.decide(self.owner,plan['id'],True,command)
        self.office.db.execute('BEGIN')
        try:
            self.office.db.execute('DROP TRIGGER business_company_event_requests_delete_guard')
            self.office.db.execute('DELETE FROM business_company_event_requests WHERE request_id=?',(command['request_id'],))
            self.problem(409,self.api.execute,self.owner,plan['id'],request(plan_sha256=plan['sha256'],confirmation=True))
            self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM workspace_items').fetchone()[0],1)
            with self.assertRaises(ValueError):validate_integrity(self.office)
        finally:self.office.db.rollback()
        self.assertEqual(self.api.plan(self.owner,plan['id'])['status'],'ready')

    def test_process_exit_after_committed_external_claim_never_repeats_transport(self):
        class SyntheticProcessExit(BaseException):pass
        class Sink:
            calls=0
            def send(sink,job):
                sink.calls+=1
                raise SyntheticProcessExit()
        sink=Sink();self.final_offer()
        self.rule(trigger='document.finalized',action='document.email',template={})
        self.api.delivery_transport=sink;command=request(limit=100,after=None)
        with patch.dict(os.environ,{'SMARTPLAN_SMTP_FROM':'seller@example.test'}),patch('business_delivery.configuration',return_value=object()):
            with self.assertRaises(SyntheticProcessExit):self.api.scan(self.owner,command)
            self.assertFalse(self.office.db.in_transaction)
            self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_company_event_executions').fetchone()[0],1)
            self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_company_event_outcomes').fetchone()[0],0)
            resumed=CompanyEvents(self.office,clock=self.clock,delivery_transport=sink).scan(self.owner,command)
            self.assertEqual(resumed['processing']['items'][0]['status'],'unconfirmed')
            self.assertEqual(sink.calls,1)
            target=self.path.parent/'external-claim-restored.sqlite3';restore(self.path,target)
            recovered=Office(target);self.addCleanup(recovered.db.close)
            plan_id=resumed['items'][0]['plan_ids'][0]
            self.assertEqual(CompanyEvents(recovered,clock=self.clock,delivery_transport=sink).plan(self.owner,plan_id)['status'],'unconfirmed')
            self.assertEqual(sink.calls,1)
            business_schema.validate_integrity(recovered)

    def test_real_internal_effect_rolls_back_with_failed_acceptance_and_new_scan_can_retry(self):
        import business_assistant_sources
        self.task();self.rule()
        original=business_assistant_sources.execute_internal
        def fail_after_actual_task(*args,**kwargs):
            original(*args,**kwargs)
            raise Problem(409,'Synthetic failure after actual insertion')
        with patch('business_assistant_sources.execute_internal',side_effect=fail_after_actual_task):
            failed,command=self.scan()
        self.assertEqual(failed['processing']['items'][0]['status'],'blocked')
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM workspace_items').fetchone()[0],1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_company_event_executions').fetchone()[0],0)
        self.assertEqual(self.api.scan(self.owner,command),failed)
        succeeded,_=self.scan();self.assertEqual(succeeded['processing']['items'][0]['status'],'succeeded')
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM workspace_items').fetchone()[0],2)
        validate_integrity(self.office)


if __name__=='__main__':unittest.main()
