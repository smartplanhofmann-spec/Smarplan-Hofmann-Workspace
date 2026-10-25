"""Canonical project-date timeline: scoped data, no fabricated appointment bars."""
import importlib.util
import json
import os
import unittest

from core import Problem
from project_workspace import ProjectWorkspace
from test_business_planning import BusinessFixture, rid


class ProjectTimelineTests(BusinessFixture, unittest.TestCase):
    def setUp(self):
        self.prepare()

    def profile(self, project, **changes):
        workspace = ProjectWorkspace(self.office)
        with self.office.lock, self.office.db:
            current = workspace.profile(self.owner, project)
            return workspace.save_profile(self.owner, project, dict(
                request_id=rid(), revision=current['revision'], **changes))

    def grant(self, actor, permission, effect, project=None):
        from business_foundation import BusinessFoundation
        return BusinessFoundation(self.office).save_grant(self.owner, dict(
            request_id=rid(), user_id=actor['id'], permission=permission,
            scope=project or '*', effect=effect, revision=0))

    def timeline(self, actor=None, **query):
        return self.planning.timeline(actor or self.owner, query)

    def test_unplanned_projects_have_no_invented_dates_bars_customers_or_private_fields(self):
        self.profile(self.project, description='SYNTHETIC PRIVATE DESCRIPTION',
                     site_address='SYNTHETIC PRIVATE ADDRESS', deposit_status='received')
        result = self.timeline()
        self.assertEqual((result['from'], result['to']), ('2026-01-01', '2026-12-31'))
        self.assertEqual(result['items'], [])
        self.assertEqual({item['id'] for item in result['unplanned']}, {self.project, self.other})
        fields = {'id', 'name', 'start_date', 'end_date', 'revision', 'phase', 'status',
                  'can_edit', 'planning_state'}
        for item in result['unplanned']:
            self.assertEqual(set(item), fields)
            self.assertIsNone(item['start_date'])
            self.assertIsNone(item['end_date'])
            self.assertEqual(item['planning_state'], 'unscheduled')
        self.assertNotIn('SYNTHETIC PRIVATE', json.dumps(result))
        self.assertNotIn('customer', json.dumps(result))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_appointments').fetchone()[0], 0)

    def test_real_date_ranges_include_year_boundaries_and_do_not_shift_with_dst(self):
        self.profile(self.project, start_date='2026-12-31', end_date='2027-01-02')
        self.profile(self.other, start_date='2026-03-28', end_date='2026-03-30')
        january = self.timeline(**{'from': '2027-01-01', 'to': '2027-01-01'})
        self.assertEqual([item['id'] for item in january['items']], [self.project])
        self.assertEqual((january['items'][0]['start_date'], january['items'][0]['end_date']),
                         ('2026-12-31', '2027-01-02'))
        march = self.timeline(**{'from': '2026-03-29', 'to': '2026-03-29'})
        self.assertEqual([item['id'] for item in march['items']], [self.other])
        self.assertEqual((march['items'][0]['start_date'], march['items'][0]['end_date']),
                         ('2026-03-28', '2026-03-30'))
        self.assertEqual(march['unplanned'], [])

    def test_partial_dates_remain_unplanned_and_true_status_is_not_a_fake_appointment(self):
        from business_foundation import BusinessFoundation
        foundation = BusinessFoundation(self.office)
        status = foundation.save_status(self.owner, dict(request_id=rid(), name='Synthetic clarification',
            color='#123456', position=1, terminal=False, active=True))
        foundation.save_project(self.owner, self.project, dict(request_id=rid(), revision=0, status_id=status['id']))
        current = self.profile(self.project, end_date='2028-02-29', phase='on_hold')
        result = self.timeline(**{'from': '2027-01-01', 'to': '2029-12-31'})
        item = next(item for item in result['unplanned'] if item['id'] == self.project)
        self.assertEqual(item['planning_state'], 'partial')
        self.assertEqual((item['start_date'], item['end_date']), (None, '2028-02-29'))
        self.assertEqual(item['phase'], 'on_hold')
        self.assertEqual(item['revision'], current['revision'])
        self.assertEqual(item['status'], {key: status[key] for key in ('id', 'name', 'color', 'terminal')})
        self.assertEqual(result['items'], [])

    def test_scope_denial_assignment_and_fresh_role_apply_to_bulk_and_specific_reads(self):
        visible = self.timeline(self.technician)
        self.assertEqual([item['id'] for item in visible['unplanned']], [self.project])
        self.assertFalse(visible['unplanned'][0]['can_edit'])
        self.problem(404, lambda: self.timeline(self.technician, project_id=self.other))
        self.grant(self.technician, 'planning.read', 'deny', self.project)
        self.assertEqual(self.timeline(self.technician)['unplanned'], [])
        self.problem(403, lambda: self.timeline(self.technician, project_id=self.project))
        with self.office.db:
            self.office.db.execute('UPDATE users SET active=0 WHERE id=?', (self.technician['id'],))
        self.problem(401, lambda: self.timeline(self.technician))

    def test_date_edit_uses_same_profile_revision_retries_once_and_never_changes_phases_or_money(self):
        original = self.profile(self.project, description='Retained description', phase='execution',
                                deposit_status='requested', materials_status='not_planned')
        body = dict(request_id=rid(), revision=original['revision'],
                    start_date='2026-11-01', end_date='2027-04-30')
        first = self.planning.save_project_dates(self.owner, self.project, body)
        self.assertEqual(self.planning.save_project_dates(self.owner, self.project, body), first)
        self.assertEqual(first['revision'], original['revision'] + 1)
        workspace = ProjectWorkspace(self.office)
        canonical = workspace.profile(self.owner, self.project)
        self.assertEqual((canonical['start_date'], canonical['end_date']), ('2026-11-01', '2027-04-30'))
        for field in ('description', 'phase', 'deposit_status', 'materials_status'):
            self.assertEqual(canonical[field], original[field])
        newer = self.planning.save_project_dates(self.owner, self.project, dict(
            request_id=rid(), revision=first['revision'], start_date=None, end_date=None))
        self.assertEqual(self.planning.save_project_dates(self.owner, self.project, body), newer)
        self.problem(409, lambda: self.planning.save_project_dates(self.owner, self.project, dict(body, request_id=rid())))
        self.assertEqual(self.office.db.execute("SELECT COUNT(*) FROM audit WHERE action='workspace.profile.saved'").fetchone()[0], 3)

    def test_explicit_project_manage_grant_can_edit_and_revocation_blocks_old_receipt(self):
        self.grant(self.technician, 'projects.manage', 'allow', self.project)
        item = self.timeline(self.technician)['unplanned'][0]
        self.assertTrue(item['can_edit'])
        body = dict(request_id=rid(), revision=item['revision'], start_date='2026-11-03', end_date='2026-11-04')
        self.planning.save_project_dates(self.technician, self.project, body)
        self.office.assign(self.owner, self.project, self.technician['id'], remove=True)
        self.problem(404, lambda: self.planning.save_project_dates(self.technician, self.project, body))
        self.assertEqual(ProjectWorkspace(self.office).profile(self.owner, self.project)['revision'], 1)

    def test_query_and_edits_are_bounded_and_strict_without_partial_date_writes(self):
        for query in ({'from': '2026-03-29T00:00:00Z', 'to': '2026-03-30'},
                      {'from': '2026-02-29'}, {'from': '2027-01-02', 'to': '2027-01-01'},
                      {'from': '2026-01-01', 'to': '2029-01-01'}, {'year': '2026'},
                      {'project_id': True}):
            with self.subTest(query=query):
                self.problem(400, lambda: self.timeline(**query))
        body = dict(request_id=rid(), revision=0, start_date='2026-12-31', end_date='2026-01-01')
        self.problem(400, lambda: self.planning.save_project_dates(self.owner, self.project, body))
        self.problem(400, lambda: self.planning.save_project_dates(self.owner, self.project, dict(body, end_date=None, phase='completed')))
        self.assertEqual(ProjectWorkspace(self.office).profile(self.owner, self.project)['revision'], 0)
        self.timeline(**{'from': '2026-01-01', 'to': '2028-12-31'})

    def test_bulk_limit_cannot_be_used_to_read_other_assigned_or_financial_data(self):
        customer = self.office.project(self.owner, self.project)['customer_id']
        with self.office.db:
            self.office.db.executemany('INSERT INTO projects(id,name,customer,customer_id) VALUES(?,?,?,?)',
                [(rid(), 'Synthetic extra ' + str(index), 'PRIVATE CUSTOMER', customer) for index in range(499)])
        self.problem(413, lambda: self.timeline())
        result = self.timeline(self.technician)
        self.assertEqual(len(result['unplanned']), 1)
        self.assertNotIn('PRIVATE CUSTOMER', json.dumps(result))
        self.assertEqual(len(self.timeline(project_id=self.project)['unplanned']), 1)

    @unittest.skipUnless(os.name == 'posix' and importlib.util.find_spec('flask') and importlib.util.find_spec('psycopg'),
                         'Real online Flask adapter requires POSIX and optional online dependencies')
    def test_real_http_date_edit_stale_revision_and_readonly_mode_share_canonical_dates(self):
        from cryptography.fernet import Fernet
        from online.web import create_app
        from business_schema import set_mode
        token = self.office.login('owner@example.test', 'Synthetic-owner-password-123')
        client = create_app(office=self.office, key=Fernet.generate_key(), host='office.example.test').test_client()
        headers = {'Authorization': 'Bearer ' + token}
        base = '/api/v1/business/planning'
        def request(method, path, data=None):
            return client.open(base + path, method=method, json=data, headers=headers,
                               base_url='https://office.example.test')
        result = request('GET', '/timeline?project_id=' + self.project)
        self.assertEqual(result.status_code, 200, result.data)
        item = result.json['unplanned'][0]
        body = dict(request_id=rid(), revision=item['revision'], start_date='2026-12-31', end_date='2027-01-02')
        saved = request('POST', '/projects/' + self.project + '/dates', body)
        self.assertEqual(saved.status_code, 200, saved.data)
        current = request('GET', '/timeline?from=2027-01-01&to=2027-12-31&project_id=' + self.project)
        self.assertEqual(current.json['items'][0], saved.json)
        stale = request('POST', '/projects/' + self.project + '/dates', dict(body, request_id=rid()))
        self.assertEqual(stale.status_code, 409, stale.data)
        set_mode(self.office, 'legacy')
        blocked = request('POST', '/projects/' + self.project + '/dates', dict(body, revision=1, request_id=rid()))
        self.assertEqual(blocked.status_code, 409, blocked.data)
        self.assertEqual(request('GET', '/timeline?from=2027-01-01&to=2027-12-31&project_id=' + self.project).json['items'][0], saved.json)


if __name__ == '__main__':
    unittest.main()
