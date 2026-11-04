#!/usr/bin/env python3
"""Reproduce API acceptance fixtures solely with temporary synthetic Offices."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from business_company_events import dispatch
from business_assistant import Assistant
from test_business_company_events import CompanyEventTests,request
from test_business_assistant import SyntheticDeliveryForTests


class SyntheticProcessExit(BaseException):
    """Only the temporary fixture exits after the actual domain claim."""


class SyntheticInterruptedDelivery:
    def __init__(self):self.jobs=[]
    def send(self,job):
        self.jobs.append(dict(job))
        raise SyntheticProcessExit()


def scenario(mode, *, project_approval=False, external=False, interrupted=False):
    case=CompanyEventTests();case.setUp()
    try:
        with ExitStack() as stack:
            if external:
                sink=SyntheticInterruptedDelivery() if interrupted else SyntheticDeliveryForTests('unknown')
                stack.enter_context(patch.dict(os.environ,{'SMARTPLAN_SMTP_FROM':'seller@example.test'}))
                stack.enter_context(patch('business_delivery.configuration',return_value=object()))
                stack.enter_context(patch('business_delivery.configured_transport',return_value=sink))
                source=case.final_offer()
            else: source=case.task()
            def call(path,body=None):
                return dispatch(case.office,case.owner,'/company-events'+path,'GET' if body is None else 'POST',{} if body is None else body)[0]
            values=dict(schema_version=1,actor=case.owner,project_id=case.project,source=source,status=call('/status'),rules_before=call('/rules'))
            if project_approval:
                values['project_rule']=Assistant(case.office,clock=case.clock).save_rule(case.owner,request(id=uuid.uuid4().hex,
                    revision=0,project_id=case.project,title='Existing project requires approval',enabled=True,
                    trigger='task.overdue',action='task.create',mode='approval',conditions=[],responsible_id=case.owner['id'],confirmation=True))
            command=request(id=uuid.uuid4().hex,revision=0,title='Explicit synthetic company event rule',enabled=True,
                project_ids=[case.project],trigger='document.finalized' if external else 'task.overdue',
                action='document.email' if external else 'task.create',mode=mode,conditions=[],
                template={} if external else dict(title='Actual source-bound follow-up',details='Fixed reviewed company template',priority='high',due_days=None),
                responsible_id=case.owner['id'],confirmation=True)
            values['rule_command']=command;values['rule']=call('/rules',command)
            values['rules_after']=call('/rules');values['rule_history']=call('/rules/'+command['id']+'/history')
            scan=request(limit=100,after=None);values['scan_command']=scan;values['scan']=call('/scan',scan)
            values['events']=call('/events');values['runs']=call('/runs');values['plans']=call('/plans')
            plan=values['plans']['items'][0];plan_id=plan['id']
            if plan['status']=='awaiting_approval':
                decision=request(plan_sha256=plan['sha256'],reason='Reviewed exact source, policy and action',confirmation=True)
                values['approve_command']=decision;values['approved']=call('/plans/'+plan_id+'/approve',decision)
                execute=request(plan_sha256=plan['sha256'],confirmation=True)
                values['execute_command']=execute
                if interrupted:
                    try:call('/plans/'+plan_id+'/execute',execute)
                    except SyntheticProcessExit:pass
                    else:raise AssertionError('Actual test transport must be interrupted after committed claim')
                values['executed']=call('/plans/'+plan_id+'/execute',execute)
                values['execute_replay']=call('/plans/'+plan_id+'/execute',execute)
            values['plan_after']=call('/plans/'+plan_id)
            values['scan_replay']=call('/scan',scan)
            values['plans_after']=call('/plans');values['events_after']=call('/events');values['runs_after']=call('/runs')
            if external: values['synthetic_transport_calls']=len(sink.jobs)
            return values
    finally: case.doCleanups()


result=dict(schema_version=1,fixture='temporary_synthetic_actual_company_event_dispatch',
    auto=scenario('auto'),approval=scenario('approval'),deny=scenario('deny'),
    project_approval=scenario('auto',project_approval=True),external_unknown=scenario('approval',external=True),
    external_unconfirmed=scenario('approval',external=True,interrupted=True))
encoded=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode()
for name in ('docs/fixtures/company_events_2026.json','app/test/fixtures/company_events_2026.json'):
    path=ROOT/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(encoded)
import hashlib
print(json.dumps(dict(bytes=len(encoded),sha256=hashlib.sha256(encoded).hexdigest())))
