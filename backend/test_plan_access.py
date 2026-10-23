"""Device grant scope, expiry, revocation and restoration over real HTTP."""
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import test_admin_api as fixtures
from core import Office, Problem, digest
from restore import restore


class PlanAccessTests(unittest.TestCase):
    setUp = fixtures.AdminApiTests.setUp
    tearDown = fixtures.AdminApiTests.tearDown
    request = fixtures.AdminApiTests.request
    login = fixtures.AdminApiTests.login
    create_user = fixtures.AdminApiTests.create_user
    project = fixtures.AdminApiTests.project

    def test_device_grant_is_scoped_seven_days_and_revocable(self):
        project = self.project()
        grant = self.request('/api/offline/access', self.owner, {}, status=201)
        token = grant['token']
        row = self.office.db.execute('SELECT * FROM plan_sessions').fetchone()
        self.assertEqual(row['token'], digest(token))
        self.assertAlmostEqual(row['expiry'], time.time() + 7 * 86400, delta=5)
        self.request('/api/projects', token)
        path = f'/api/projects/{project}/plans'
        self.request(path, token, {'title': 'Offline EG', 'walls': [], 'request_id': '1' * 32}, status=201)
        for path in ('/api/users', '/api/customers', '/api/me', f'/api/projects/{project}/reports'):
            self.request(path, token, status=403)
        self.request('/api/projects', token, {'name': 'Not allowed'}, status=403)
        self.request('/api/offline/access', token, {}, status=403)
        self.request('/api/offline/logout', token, {})
        self.request('/api/projects', token, status=401)
        grant = self.request('/api/offline/access', self.owner, {}, status=201)
        with patch('plan_access.time.time', return_value=time.time() + 7 * 86400 + 1):
            self.request('/api/projects', grant['token'], status=401)

    def test_revocation_and_reactivation_never_restore_old_device_grant(self):
        project = self.project()
        uid = self.create_user()
        full = self.login('tech@example.test', 'Technician-password-123')
        self.request('/api/assignments', self.owner, {'project_id': project, 'user_id': uid})
        token = self.request('/api/offline/access', full, {}, status=201)['token']
        path = f'/api/projects/{project}/plans'
        self.request(path, token)
        self.request('/api/assignments', self.owner, {'project_id': project, 'user_id': uid, 'remove': True})
        self.request(path, token, status=404)
        self.request('/api/users/' + uid, self.owner, {'active': False})
        self.request('/api/users/' + uid, self.owner, {'active': True})
        self.request('/api/projects', token, status=401)

    def test_restore_retains_plans_but_revokes_device_tokens(self):
        project = self.project()
        token = self.request('/api/offline/access', self.owner, {}, status=201)['token']
        saved = self.request(f'/api/projects/{project}/plans', token, {'title': 'Saved', 'walls': []}, status=201)
        restored = restore(Path(self.temp.name) / 'office.sqlite3', Path(self.temp.name) / 'restored.sqlite3')
        office = Office(restored)
        try:
            import plan_access
            with self.assertRaises(Problem):
                plan_access.user(office, token)
            self.assertEqual(office.db.execute('SELECT COUNT(*) FROM plan_versions WHERE id=?', (saved['id'],)).fetchone()[0], 1)
        finally:
            office.db.close()
