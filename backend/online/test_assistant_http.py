"""Real MFA and strict HTTP for source-bound rules, approvals and actions."""
import json
import unittest
import uuid

import business_schema
from online import test_portal_http as portal_fixture


class AssistantHTTPTests(unittest.TestCase):
    setUp = portal_fixture.PortalHTTPTests.setUp
    call = portal_fixture.PortalHTTPTests.call
    staff_call = portal_fixture.PortalHTTPTests.staff_call
    req = staticmethod(portal_fixture.PortalHTTPTests.req)

    def setup_context(self):
        project = self.staff_call('/projects',dict(name='Synthetic assistant HTTP project',customer='Synthetic customer'),status=201).json['id']
        context = self.staff_call('/business/assistant/contexts',self.req(project_id=project,sources=[dict(kind='project',id=project)])).json
        actor = self.office.user(self.staff)
        rule = self.req(id=uuid.uuid4().hex,revision=0,project_id=project,title='Synthetic HTTP rule',enabled=True,
            trigger='manual',action='task.create',mode='approval',conditions=[],responsible_id=actor['id'],confirmation=True)
        return project, context, rule

    def plan_request(self, context):
        return self.req(context_id=context['id'],trigger='manual',action='task.create',
            parameters=dict(title='Real HTTP follow-up',details='Selected project source',due_date=None,priority='normal'),reason='Explicit reviewed HTTP request')

    def test_whole_source_rule_approval_real_action_and_receipt_history(self):
        project, context, rule = self.setup_context()
        self.staff_call('/business/assistant/rules',rule)
        plan = self.staff_call('/business/assistant/plans',self.plan_request(context)).json
        self.assertEqual(plan['status'],'awaiting_approval')
        body = self.req(plan_sha256=plan['sha256'],confirmation=True)
        denied = self.staff_call('/business/assistant/plans/'+plan['id']+'/execute',body,status=409)
        self.assertEqual(denied.json['request_resolution'],'not_accepted')
        self.staff_call('/business/assistant/plans/'+plan['id']+'/approve',self.req(plan_sha256=plan['sha256'],reason='Reviewed source and exact action',confirmation=True))
        completed = self.staff_call('/business/assistant/plans/'+plan['id']+'/execute',body).json
        self.assertEqual(completed['status'],'succeeded')
        self.assertEqual(self.staff_call('/business/assistant/plans/'+plan['id']+'/execute',body).json,completed)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM workspace_items').fetchone()[0],1)
        self.assertEqual(self.staff_call('/business/assistant/rules/'+rule['id']+'/history').json['items'][0]['revision'],1)
        self.assertEqual(self.staff_call('/business/assistant/plans?project_id='+project).json['items'][0]['id'],plan['id'])
        self.assertEqual(self.staff_call('/business/assistant/chat?project_id='+project).json,dict(items=[]))
        business_schema.validate_integrity(self.office)

    def test_request_collision_remains_unknown_while_proven_unaccepted_rule_revision_is_marked(self):
        _, _, rule = self.setup_context()
        self.staff_call('/business/assistant/rules',rule)
        replay = self.staff_call('/business/assistant/rules',{**rule,'title':'Changed same request'},status=409)
        self.assertNotIn('request_resolution',replay.json)
        rejected = self.staff_call('/business/assistant/rules',{**rule,'request_id':uuid.uuid4().hex},status=409)
        self.assertEqual(rejected.json['request_resolution'],'not_accepted')
        self.assertEqual(len(self.staff_call('/business/assistant/rules/'+rule['id']+'/history').json['items']),1)

    def test_exact_fields_duplicate_json_public_tokens_and_foreign_sources_are_closed(self):
        _, context, rule = self.setup_context()
        self.staff_call('/business/assistant/rules',{**rule,'provider_api_key':'must-not-enter'},status=400)
        self.staff_call('/business/assistant/rules',raw=json.dumps(rule)[:-1]+',"mode":"auto"}',status=400)
        self.staff_call('/business/assistant/status?unexpected='+context['project_id'],status=400)
        self.staff_call('/business/assistant/plans',self.plan_request(context),method='PUT',status=405)
        self.call('/business/assistant/status',token='SPCT_'+'a'*43,status=401)
        self.call('/business/assistant/status',token='SPPT_'+'a'*43,status=401)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_assistant_rules').fetchone()[0],0)

    def test_source_query_is_strict_bounded_and_paginated(self):
        project, _, _ = self.setup_context()
        value = self.staff_call('/business/assistant/sources?project_id='+project+'&q=Projekt&offset=0').json
        self.assertEqual(value['offset'],0)
        self.assertIsNone(value['next_offset'])
        self.assertIn(project,[item['id'] for item in value['items']])
        for suffix in ('&offset=-1','&offset=01','&offset=100001','&q='+'x'*201,'&unknown=1'):
            self.staff_call('/business/assistant/sources?project_id='+project+suffix,status=400)


if __name__ == '__main__': unittest.main()
