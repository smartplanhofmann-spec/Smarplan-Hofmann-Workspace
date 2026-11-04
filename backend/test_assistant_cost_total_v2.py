"""Standalone correction of actual cost totals, preserving accepted old bytes."""
import base64
from pathlib import Path
import types
import unittest
from unittest.mock import patch
import uuid

import business_schema
from business_assistant import Assistant,validate_integrity
from business_assistant_sources import resolve,cost_total_minor
from business_finance import Finance
from business_project_economics import ProjectEconomics
import test_business_assistant as fixture

request=fixture.request


class AssistantCostTotalV2Tests(unittest.TestCase):
    problem=fixture.AssistantTests.problem

    def setUp(self):
        fixture.AssistantTests.setUp(self)
        finance=Finance(self.office)
        original=finance.capture_receipt(self.owner,request(project_id=self.project,filename='synthetic-cost.pdf',
            media_type='application/pdf',original_base64=base64.b64encode(b'%PDF-1.4\nSynthetic actual100 EUR').decode()))
        current=finance.receipt(self.owner,original['id'])
        reviewed=finance.review_receipt(self.owner,original['id'],request(revision=current['revision'],vendor='Synthetic supplier',
            invoice_number='SYN-COST',issue_date='2026-11-01',net='100.00',tax='19.00',gross='119.00',currency='EUR',status='reviewed',note='Original checked'))
        economics=ProjectEconomics(self.office)
        body=dict(project_id=self.project,receipt_id=reviewed['id'],source_revision=reviewed['revision'],expected_revision=0,
            allocations=[dict(category='external_service',amount_net='100.00')],reason='Actual accepted original cost')
        preview=economics.preview(self.owner,body);economics.confirm(self.owner,request(**body,preview_hash=preview['preview_hash']))
        self.assertEqual(economics.summary(self.owner,self.project)['costs']['total_net'],'100.00')
        path=Path(__file__).resolve().parents[1]/'docs/evidence/assistant-cost-total-v2-2026-11-04/legacy-assistant-sources-4c2f008.txt'
        self.legacy=types.ModuleType('verified_legacy_cost_source')
        exec(compile(path.read_text(),str(path),'exec'),self.legacy.__dict__)

    def rule(self):
        return self.api.save_rule(self.owner,request(id=uuid.uuid4().hex,revision=0,project_id=self.project,title='Explicit cost threshold',
            enabled=True,trigger='cost.threshold',action='task.create',mode='approval',
            conditions=[dict(field='total_cost_minor',operator='gte',value=15000)],responsible_id=self.owner['id'],confirmation=True))

    def context_command(self): return request(project_id=self.project,sources=[dict(kind='costs',id=self.project)])

    def plan_command(self, context):
        return request(context_id=context['id'],trigger='cost.threshold',action='task.create',
            parameters=dict(title='Reviewed cost follow-up',details='',due_date=None,priority='normal'),reason='Exact original cost source')

    def test_actual_current_cost_and_rule_threshold_use100_once(self):
        self.rule();context=self.api.create_context(self.owner,self.context_command())
        self.assertEqual(context['facts']['total_cost_minor'],10000)
        self.assertEqual(context['sources'][0]['data']['cost_total_basis'],'project_economics_total_net_v2')
        plan=self.api.create_plan(self.owner,self.plan_command(context))
        self.assertEqual(plan['status'],'denied');self.assertFalse(plan['policy']['matched_rules'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM workspace_items').fetchone()[0],0)
        business_schema.validate_integrity(self.office)

    def test_real_legacy_context_and_accepted_pending_plan_keep_original_bytes(self):
        self.rule();command=self.context_command()
        with patch('business_assistant.resolve',self.legacy.resolve),patch('business_assistant.facts',self.legacy.facts):
            old=self.api.create_context(self.owner,command);plan_command=self.plan_command(old)
            plan=self.api.create_plan(self.owner,plan_command)
        self.assertEqual(old['facts']['total_cost_minor'],20000)
        self.assertEqual(plan['status'],'awaiting_approval')
        before={table:[tuple(row) for row in self.office.db.execute('SELECT * FROM '+table+' ORDER BY '+('user_id,request_id' if table.endswith('requests') else 'id')).fetchall()]
                for table in ('business_assistant_contexts','business_assistant_plans','business_assistant_requests')}
        replay=self.api.create_context(self.owner,command);oldplan=self.api.create_plan(self.owner,plan_command)
        self.assertEqual((replay['sha256'],replay['sources'],replay['facts']),(old['sha256'],old['sources'],old['facts']))
        self.assertFalse(replay['current']);self.assertEqual(oldplan['status'],'stale')
        for table,rows in before.items():
            self.assertEqual([tuple(row) for row in self.office.db.execute('SELECT * FROM '+table+' ORDER BY '+('user_id,request_id' if table.endswith('requests') else 'id')).fetchall()],rows)
        validate_integrity(self.office)

    def test_unknown_cost_origin_marker_is_rejected(self):
        source=resolve(self.office,self.owner,self.project,dict(kind='costs',id=self.project),'2026-11-03')['data']
        self.problem(409,cost_total_minor,{**source,'cost_total_basis':'unrecognized_total'})
        legacy={key:value for key,value in source.items() if key!='cost_total_basis'}
        self.assertEqual(cost_total_minor(legacy),20000)


if __name__=='__main__':unittest.main()
