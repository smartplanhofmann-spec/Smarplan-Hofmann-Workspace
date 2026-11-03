import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from core import Problem
from business_foundation import BusinessFoundation, dispatch
from business_overview import overview_metrics
from business_planning import Planning
from project_workspace import ProjectWorkspace
import test_business_project_economics as fixture


class CompanyOverviewTests(unittest.TestCase):
    setUp = fixture.ProjectEconomicsTests.setUp
    actor = fixture.ProjectEconomicsTests.actor
    request = fixture.ProjectEconomicsTests.request
    receipt = fixture.ProjectEconomicsTests.receipt
    review = fixture.ProjectEconomicsTests.review
    inputs = fixture.ProjectEconomicsTests.inputs
    confirm = fixture.ProjectEconomicsTests.confirm
    grant = fixture.ProjectEconomicsTests.grant
    problem = fixture.ProjectEconomicsTests.problem

    def metrics(self, actor=None, query=None):
        return overview_metrics(self.office, actor or self.owner, query,
            clock=lambda: datetime(2026, 11, 3, 12, tzinfo=timezone.utc))

    def task(self, project=None, **changes):
        with self.office.db:
            return ProjectWorkspace(self.office).save_item(self.owner, project or self.project, 'tasks',
                self.request(**dict(title='Synthetic task', due_date='2026-11-02', **changes)))

    def test_costs_are_source_bound_and_missing_classification_is_not_zero_profit(self):
        original = self.receipt()
        before = self.metrics()
        self.assertEqual('0.00', before['finance']['revenue_net'])
        self.assertIsNone(before['finance']['contribution_net'])
        self.assertEqual('project_costs_incomplete', before['warnings'][0]['code'])
        self.confirm(original)
        after = self.metrics()
        self.assertEqual('100.00', after['finance']['costs_net'])
        self.assertEqual('-100.00', after['finance']['contribution_net'])
        self.assertEqual('0.00', after['finance']['receipts_gross'])
        self.assertEqual('0.00', after['finance']['open_gross'])
        self.assertIsNone(after['accounting']['balance'])
        self.assertFalse(after['accounting']['opening_balances_available'])
        self.assertIsNone(after['accounting']['totals']['euer_surplus'])
        self.assertNotEqual(before['source_hash'], after['source_hash'])
        self.assertEqual(after['source_hash'], self.metrics()['source_hash'])

    def test_no_private_project_task_or_financial_data_leaks(self):
        visible = self.task()
        self.task(self.other)
        self.receipt(project=self.other)
        result = self.metrics(self.tech)
        self.assertEqual(1, result['project_count'])
        self.assertEqual([visible['id']], [item['id'] for item in result['tasks']])
        self.assertEqual(0, result['finance']['project_count'])
        self.assertIsNone(result['finance']['revenue_net'])
        self.assertEqual([], result['warnings'])
        self.assertFalse(result['accounting']['available'])
        self.assertNotIn(self.other, str(result))

    def test_selected_project_never_displays_global_accounting_or_other_project(self):
        self.task(self.other)
        result = self.metrics(query={'project_id': self.project})
        self.assertEqual('selected_project', result['scope'])
        self.assertEqual(1, result['project_count'])
        self.assertEqual(0, result['task_count'])
        self.assertFalse(result['accounting']['available'])
        self.problem(404, self.metrics, self.tech, {'project_id': self.other})

    def test_total_task_count_is_not_truncated_to_preview_and_dates_use_berlin(self):
        for _ in range(23): self.task()
        with self.office.db:
            ProjectWorkspace(self.office).save_item(self.owner, self.project, 'tasks',
                self.request(title='Future item', due_date='2026-11-04'))
            ProjectWorkspace(self.office).save_item(self.owner, self.project, 'tasks',
                self.request(title='Completed', status='done'))
        result = self.metrics()
        self.assertEqual((24, 23, 20), (result['task_count'], result['overdue_task_count'], len(result['tasks'])))
        self.assertTrue(all(item['overdue'] for item in result['tasks']))
        self.assertTrue(all(item['source_path'].endswith(item['id']) for item in result['tasks']))

    def test_calendar_uses_canonical_schedule_and_excludes_cancelled_and_foreign(self):
        planning = Planning(self.office)
        for project, status in ((self.project, 'scheduled'), (self.project, 'cancelled'), (self.other, 'scheduled')):
            planning.save_appointment(self.owner, project, self.request(title='Synthetic visit',
                start_at='2026-11-04T10:00:00+00:00', end_at='2026-11-04T11:00:00+00:00', status=status))
        result = self.metrics(self.tech)
        self.assertEqual(1, result['appointment_count'])
        self.assertEqual(self.project, result['appointments'][0]['project_id'])
        self.assertNotIn('employee_ids', result['appointments'][0])

    def test_fresh_rights_even_for_old_actor_and_final_composition_guard(self):
        self.grant('finance.read')
        original = BusinessFoundation.authorize
        calls = 0
        def revoke(foundation, actor, name, project=None):
            nonlocal calls
            if actor['id'] == self.tech['id'] and name == 'finance.read':
                calls += 1
                if calls > 1:
                    raise Problem(403, 'Synthetic revocation during composition')
            return original(foundation, actor, name, project)
        with patch.object(BusinessFoundation, 'authorize', revoke):
            self.problem(403, self.metrics, self.tech)
        with self.office.db:
            self.office.db.execute('UPDATE users SET active=0 WHERE id=?', (self.tech['id'],))
        self.problem(401, self.metrics, self.tech)

    def test_transport_contract_rejects_unknown_query_and_method(self):
        self.problem(400, dispatch, self.office, self.owner, '/overview/metrics', 'GET', {'_query': {'year': '2026'}})
        self.problem(405, dispatch, self.office, self.owner, '/overview/metrics', 'POST', {})
        value, status, mime = dispatch(self.office, self.owner, '/overview/metrics', 'GET', {})
        self.assertEqual((200, 'application/json', 1), (status, mime, value['schema_version']))


if __name__ == '__main__': unittest.main()
