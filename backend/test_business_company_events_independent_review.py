"""Independent event authorization/binding journeys against real SQLite domains."""
from datetime import datetime, timedelta
import os
import unittest
from unittest.mock import patch
import uuid

from business_assistant import Assistant
from business_company_events import CompanyEvents, validate_integrity
from business_foundation import BusinessFoundation
from business_operations import transaction
from project_workspace import ProjectWorkspace
import test_business_assistant as fixture

request = fixture.request


class CompanyEventIndependentReview(unittest.TestCase):
    problem = fixture.AssistantTests.problem
    final_offer = fixture.AssistantTests.final_offer

    def setUp(self):
        fixture.AssistantTests.setUp(self)
        with self.office.db:
            self.office.db.execute('INSERT INTO business_instance_identity VALUES(1,?,?,?,?,?)',
                (uuid.uuid4().hex, 'review.example.test', str(self.path.parent), 'c'*64, self.clock().isoformat()))
        clock = patch('business_company_events.datetime', wraps=datetime)
        observed = clock.start()
        self.addCleanup(clock.stop)
        observed.now.side_effect = lambda zone: self.clock().astimezone(zone)
        self.api = CompanyEvents(self.office, clock=self.clock)

    def save_task(self, project, command, identifier=None):
        with transaction(self.office):
            return ProjectWorkspace(self.office).save_item(self.owner, project, 'tasks', command, identifier)

    def source(self, project=None):
        return self.save_task(project or self.project,
            request(title='Independent original', details='Private original description', due_date='2026-11-01',
                    priority='normal', status='todo', assignee_id=self.owner['id']))

    def rule(self, **values):
        command = request(id=uuid.uuid4().hex, revision=0, title='Independent event delegation', enabled=True,
            project_ids=[self.project], trigger='task.overdue', action='task.create', mode='approval', conditions=[],
            template=dict(title='Independent accepted task', details='Explicit fixed text', priority='high', due_days=None),
            responsible_id=self.owner['id'], confirmation=True)
        command.update(values)
        return self.api.save_rule(self.owner, command), command

    def scan(self, **values):
        command = request(limit=100, after=None)
        command.update(values)
        run = self.api.scan(self.owner, command)
        return run, [self.api.plan(self.owner, key) for item in run['items'] for key in item['plan_ids']], command

    def decision(self, plan, actor=None, approved=True):
        command = request(plan_sha256=plan['sha256'], reason='Reviewed exact independent source', confirmation=True)
        return self.api.decide(actor or self.owner, plan['id'], approved, command), command

    def grant(self, permission, effect='allow'):
        old = self.office.db.execute('SELECT revision FROM business_permission_grants WHERE user_id=? AND permission=? AND scope=?',
            (self.other['id'], permission, '*')).fetchone()
        return BusinessFoundation(self.office).save_grant(self.owner, request(user_id=self.other['id'],
            permission=permission, effect=effect, scope='*', revision=old['revision'] if old else 0))

    def count_tasks(self):
        return self.office.db.execute("SELECT COUNT(*) FROM workspace_items WHERE kind='tasks'").fetchone()[0]

    def project_rule(self, mode='approval', **changes):
        command = request(id=uuid.uuid4().hex, revision=0, project_id=self.project,
            title='Existing exact event project rule', enabled=True, trigger='task.overdue',
            action='task.create', mode=mode, conditions=[], responsible_id=self.owner['id'], confirmation=True)
        command.update(changes)
        return Assistant(self.office, clock=self.clock).save_rule(self.owner, command), command

    def test_exact_project_scope_and_plan_list_never_reveal_other_project(self):
        self.source(); self.source(self.private)
        self.rule()
        run, plans, _ = self.scan()
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]['project_id'], self.project)
        self.office.assign(self.owner, self.private, self.other['id'])
        self.assertEqual(self.api.plans(self.other)['items'], [])
        self.problem(404, self.api.plan, self.other, plans[0]['id'])
        self.problem(404, self.api.event, self.other, plans[0]['event_id'])
        self.problem(403, self.api.run, self.other, run['id'])
        self.assertEqual(self.count_tasks(), 2)

    def test_responsibility_cannot_substitute_approval_or_domain_rights(self):
        self.office.assign(self.owner, self.project, self.other['id'])
        self.grant('projects.manage')
        self.source(); self.rule(responsible_id=self.other['id'])
        _, plans, _ = self.scan(); plan = plans[0]
        command = request(plan_sha256=plan['sha256'], reason='Not yet authorized', confirmation=True)
        self.problem(403, self.api.decide, self.other, plan['id'], True, command)
        self.grant('assistant.approve')
        self.decision(plan, self.other)
        self.grant('projects.manage', 'deny')
        self.problem(403, self.api.execute, self.other, plan['id'],
            request(plan_sha256=plan['sha256'], confirmation=True))
        self.assertEqual(self.count_tasks(), 1)

    def test_approved_plan_rechecks_responsible_project_membership(self):
        self.office.assign(self.owner, self.project, self.other['id'])
        self.grant('projects.manage'); self.grant('assistant.approve')
        self.source(); self.rule(responsible_id=self.other['id'])
        _, plans, _ = self.scan(); plan = plans[0]
        self.decision(plan, self.other)
        self.office.assign(self.owner, self.project, self.other['id'], remove=True)
        self.problem(404, self.api.execute, self.other, plan['id'],
            request(plan_sha256=plan['sha256'], confirmation=True))
        self.assertEqual(self.count_tasks(), 1)

    def test_crossed_plan_hash_cannot_approve_or_execute_other_occurrence(self):
        self.source(); self.source(); self.rule()
        _, plans, _ = self.scan(); first, second = plans
        wrong = request(plan_sha256=first['sha256'], reason='Crossed exact plan', confirmation=True)
        self.problem(409, self.api.decide, self.owner, second['id'], True, wrong)
        self.decision(first)
        self.problem(409, self.api.execute, self.owner, second['id'],
            request(plan_sha256=first['sha256'], confirmation=True))
        self.assertEqual(self.count_tasks(), 2)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_company_event_executions').fetchone()[0], 0)

    def test_rule_revision_after_approval_invalidates_old_command(self):
        self.source(); _, rule_command = self.rule()
        _, plans, _ = self.scan(); old = plans[0]
        self.decision(old)
        self.api.save_rule(self.owner, {**rule_command, 'revision': 1, 'request_id': uuid.uuid4().hex,
            'template': dict(title='Changed explicit task', details='', priority='normal', due_days=None)})
        self.problem(409, self.api.execute, self.owner, old['id'], request(plan_sha256=old['sha256'], confirmation=True))
        _, fresh, _ = self.scan()
        self.assertNotEqual(fresh[0]['id'], old['id'])
        self.assertEqual(fresh[0]['action_key'], old['action_key'])
        self.assertIsNone(fresh[0]['decision'])
        self.assertEqual(fresh[0]['status'], 'awaiting_approval')
        self.assertEqual(self.count_tasks(), 1)

    def test_source_revision_after_approval_cannot_reuse_decision(self):
        source = self.source(); self.rule()
        _, plans, _ = self.scan(); old = plans[0]
        self.decision(old)
        values = {key: source[key] for key in ('title', 'details', 'status', 'priority', 'due_date', 'assignee_id')}
        self.save_task(self.project,
            request(**{**values, 'details': 'Actually changed original'}, revision=source['revision']), source['id'])
        self.problem(409, self.api.execute, self.owner, old['id'], request(plan_sha256=old['sha256'], confirmation=True))
        _, fresh, _ = self.scan()
        self.assertNotEqual(fresh[0]['id'], old['id'])
        self.assertIsNone(fresh[0]['decision'])
        self.assertEqual(fresh[0]['status'], 'awaiting_approval')
        self.assertEqual(self.count_tasks(), 1)

    def test_matching_conflicting_responsibility_is_denied(self):
        self.office.assign(self.owner, self.project, self.other['id']); self.grant('projects.manage')
        self.source(); self.rule(mode='auto'); self.rule(mode='auto', responsible_id=self.other['id'])
        _, plans, _ = self.scan()
        self.assertEqual(plans[0]['status'], 'denied')
        self.assertEqual(plans[0]['policy']['reason'], 'ambiguous_rules')
        self.assertIsNone(plans[0]['policy']['responsible_id'])
        self.assertEqual(self.count_tasks(), 1)

    def test_legacy_project_deny_blocks_new_company_auto_action(self):
        self.source(); self.rule(mode='auto')
        Assistant(self.office, clock=self.clock).save_rule(self.owner, request(id=uuid.uuid4().hex,
            revision=0, project_id=self.project, title='Existing explicit project prohibition', enabled=True,
            trigger='manual', action='task.create', mode='deny', conditions=[], responsible_id=self.owner['id'], confirmation=True))
        run, plans, _ = self.scan()
        self.assertEqual(run['processing']['items'][0]['status'], 'denied')
        self.assertEqual(plans[0]['status'], 'denied')
        self.assertFalse(plans[0]['can_execute'])
        self.assertEqual(plans[0]['blocked']['status_code'], 403)
        self.assertEqual(self.count_tasks(), 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_company_event_executions').fetchone()[0], 0)

    def test_legacy_same_event_trigger_deny_blocks_new_company_auto_action(self):
        self.source(); self.rule(mode='auto')
        Assistant(self.office, clock=self.clock).save_rule(self.owner, request(id=uuid.uuid4().hex,
            revision=0, project_id=self.project, title='Existing overdue-event prohibition', enabled=True,
            trigger='task.overdue', action='task.create', mode='deny', conditions=[], responsible_id=self.owner['id'], confirmation=True))
        run, plans, _ = self.scan()
        self.assertEqual(run['processing']['items'][0]['status'], 'denied')
        self.assertEqual(plans[0]['status'], 'denied')
        self.assertFalse(plans[0]['can_execute'])
        self.assertEqual(plans[0]['blocked']['status_code'], 403)
        self.assertEqual(self.count_tasks(), 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_company_event_executions').fetchone()[0], 0)

    def test_project_approval_strengthens_company_auto_and_approves_same_bound_plan(self):
        self.source(); self.rule(mode='auto'); project_rule, _ = self.project_rule()
        _, plans, _ = self.scan(); plan = plans[0]
        self.assertEqual(plan['status'], 'awaiting_approval')
        self.assertEqual(plan['policy']['mode'], 'approval')
        self.assertEqual(plan['policy']['company_mode'], 'auto')
        proof = next(item for item in plan['policy']['project_policies'] if item['trigger'] == 'task.overdue')
        self.assertEqual(proof['policy']['matched_rules'], [dict(id=project_rule['id'], revision=1)])
        self.assertEqual(self.count_tasks(), 1)
        self.decision(plan)
        accepted = self.api.execute(self.owner, plan['id'], request(plan_sha256=plan['sha256'], confirmation=True))
        self.assertEqual(accepted['status'], 'succeeded')
        self.assertEqual(self.count_tasks(), 2)
        validate_integrity(self.office)

    def test_project_rule_change_invalidates_previously_approved_company_plan(self):
        self.source(); self.rule(mode='auto'); _, original = self.project_rule()
        _, plans, _ = self.scan(); plan = plans[0]
        self.decision(plan)
        Assistant(self.office, clock=self.clock).save_rule(self.owner,
            {**original, 'request_id': uuid.uuid4().hex, 'revision': 1, 'mode': 'deny'})
        self.problem(409, self.api.execute, self.owner, plan['id'], request(plan_sha256=plan['sha256'], confirmation=True))
        self.assertEqual(self.count_tasks(), 1)
        self.assertEqual(self.api.plan(self.owner, plan['id'])['status'], 'stale')

    def test_exact_accepted_replay_survives_next_day_and_changed_rule_without_second_task(self):
        self.source(); _, rule_command = self.rule()
        _, plans, scan_command = self.scan(); plan = plans[0]
        self.decision(plan)
        command = request(plan_sha256=plan['sha256'], confirmation=True)
        accepted = self.api.execute(self.owner, plan['id'], command)
        task = accepted['outcome']['result']
        self.assertEqual(task['assignee_id'], self.owner['id'])
        self.today += timedelta(days=1)
        self.api.save_rule(self.owner, {**rule_command, 'revision': 1, 'enabled': False, 'request_id': uuid.uuid4().hex})
        replay = self.api.execute(self.owner, plan['id'], command)
        self.assertEqual(replay['outcome'], accepted['outcome'])
        self.assertEqual(replay['execution'], accepted['execution'])
        self.api.scan(self.owner, scan_command)
        self.scan()
        self.assertEqual(self.count_tasks(), 2)
        self.problem(409, self.api.execute, self.owner, plan['id'], {**command, 'plan_sha256': 'f'*64})
        validate_integrity(self.office)

    def test_unknown_external_delivery_is_claimed_once_even_after_new_rule_and_day(self):
        self.final_offer()
        self.rule(trigger='document.finalized', action='document.email', template={})
        sink = fixture.SyntheticDeliveryForTests('unknown')
        self.api.delivery_transport = sink
        with patch.dict(os.environ, {'SMARTPLAN_SMTP_FROM': 'review@example.test'}), patch('business_delivery.configuration', return_value=object()):
            _, plans, _ = self.scan(); plan = plans[0]
            self.decision(plan)
            command = request(plan_sha256=plan['sha256'], confirmation=True)
            result = self.api.execute(self.owner, plan['id'], command)
            self.assertEqual(result['status'], 'unknown')
            self.api.execute(self.owner, plan['id'], command)
            self.today += timedelta(days=1)
            self.scan()
            self.assertEqual(len(sink.jobs), 1)
            self.assertFalse(self.api.plan(self.owner, plan['id'])['can_execute'])
        validate_integrity(self.office)

    def test_money_condition_preserves_exact_large_cent_string_and_rejects_numeric_rounding(self):
        exact = '9007199254740993'
        saved, command = self.rule(trigger='payment.overdue',
            conditions=[dict(field='open_minor', operator='gte', value=exact)])
        self.assertEqual(saved['conditions'][0]['value'], exact)
        self.assertEqual(self.api.save_rule(self.owner, command), saved)
        self.assertEqual(self.api.rule_history(self.owner, saved['id'])['items'][0]['conditions'][0]['value'], exact)
        for invalid in [int(exact), '09007199254740993', '9007199254740993.00', True]:
            body = {**command, 'request_id': uuid.uuid4().hex, 'id': uuid.uuid4().hex,
                'conditions': [dict(field='open_minor', operator='gte', value=invalid)]}
            self.problem(400, self.api.save_rule, self.owner, body)
        validate_integrity(self.office)

    def test_scanner_without_finance_right_cannot_receive_hidden_document_identifier_in_issue(self):
        document = self.final_offer()
        self.rule(trigger='document.finalized', action='task.create', mode='auto')
        self.office.assign(self.owner, self.project, self.other['id'])
        self.grant('settings.manage')
        run = self.api.scan(self.other, request(limit=100, after=None))
        self.assertEqual(run['items'], [])
        self.assertTrue(run['complete'])
        self.assertEqual(run['issues'], [])
        self.assertIsNone(run['next_after'])
        self.assertNotIn(document['id'], str(run))
        self.assertEqual(self.count_tasks(), 0)

    def test_existing_assistant_event_auto_cannot_bypass_company_prohibition(self):
        task = self.source(); self.rule(mode='deny'); self.project_rule(mode='auto')
        legacy = Assistant(self.office, clock=self.clock)
        context = legacy.create_context(self.owner, request(project_id=self.project,
            sources=[dict(kind='task', id=task['id'])]))
        plan = legacy.create_plan(self.owner, request(context_id=context['id'], trigger='task.overdue',
            action='task.create', parameters=dict(title='Forbidden legacy duplicate', details='Explicit source',
                due_date=None, priority='normal'), reason='Existing event entry must preserve company restriction'))
        self.assertNotEqual(plan['status'], 'succeeded')
        self.assertFalse(plan['can_execute'])
        self.assertEqual(self.count_tasks(), 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_assistant_executions').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
