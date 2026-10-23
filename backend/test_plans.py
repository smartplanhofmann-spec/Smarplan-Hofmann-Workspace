"""Real HTTP plan persistence, conflict protection and access checks."""
import unittest
import test_admin_api as fixtures


class PlanApiTests(unittest.TestCase):
    setUp = fixtures.AdminApiTests.setUp
    tearDown = fixtures.AdminApiTests.tearDown
    request = fixtures.AdminApiTests.request
    login = fixtures.AdminApiTests.login
    create_user = fixtures.AdminApiTests.create_user
    project = fixtures.AdminApiTests.project
    def test_plan_roundtrip_conflict_and_reopen(self):
        project = self.project()
        path = f'/api/projects/{project}/plans'
        first = self.request(path, self.owner, {'title': 'Erdgeschoss', 'walls': []}, status=201)
        detail = path + '/' + first['id']
        wall = {'id': 'wall_1', 'points': [[10, 20], [200, 20]]}
        updated = self.request(detail, self.owner, {'title': 'EG', 'walls': [wall], 'revision': 1})
        self.assertEqual(updated['revision'], 2)
        self.request(detail, self.owner, {'title': 'Veraltet', 'walls': [], 'revision': 1}, status=409)
        self.assertEqual(self.request(detail, self.owner), updated)
        self.assertEqual(self.request(path, self.owner), [updated])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM plan_versions WHERE id=?', (first['id'],)).fetchone()[0], 2)
        # A second connection models reopening after a process restart.
        from core import Office
        reopened = Office(self.office.db.execute('PRAGMA database_list').fetchone()[2])
        try:
            user = reopened.user(self.owner)
            self.assertEqual(reopened.plan(user, project, first['id']), updated)
        finally:
            reopened.db.close()

    def test_project_scope_accountant_and_revocation(self):
        project = self.project()
        path = f'/api/projects/{project}/plans'
        plan = self.request(path, self.owner, {'title': 'OG', 'walls': []}, status=201)
        detail = path + '/' + plan['id']
        uid = self.create_user()
        token = self.login('tech@example.test', 'Technician-password-123')
        self.request(path, token, status=404)
        self.request(detail, token, status=404)
        self.request('/api/assignments', self.owner, {'project_id': project, 'user_id': uid})
        self.assertEqual(self.request(detail, token)['id'], plan['id'])
        accountant = self.create_user('accounts@example.test', 'accountant')
        read = self.login('accounts@example.test', 'Technician-password-123')
        self.request('/api/assignments', self.owner, {'project_id': project, 'user_id': accountant})
        self.request(detail, read)
        self.request(detail, read, {'title': 'No', 'walls': [], 'revision': 1}, status=403)
        self.request('/api/assignments', self.owner, {'project_id': project, 'user_id': uid, 'remove': True})
        self.request(detail, token, status=404)
        self.request(path, status=401)
        self.request(path, self.owner, method='DELETE', status=405)

    def test_invalid_geometry_is_not_persisted(self):
        project = self.project()
        path = f'/api/projects/{project}/plans'
        for walls in ([{'id': 'w', 'points': [[0, 0], [0, 0]]}],
                      [{'id': 'w', 'points': [[False, 0], [1, 2]]}],
                      [{'id': 'w', 'points': [[0, 0], [10001, 0]]}],
                      [{'id': 'w', 'points': [[0, 0], [1, 2]]}] * 2):
            self.request(path, self.owner, {'title': 'Test', 'walls': walls}, status=400)
        self.assertEqual(self.request(path, self.owner), [])


    def test_repeated_sync_after_lost_ack_creates_no_duplicates(self):
        project = self.project()
        path = f'/api/projects/{project}/plans'
        request = {'title': 'Offline EG', 'walls': [], 'request_id': 'a' * 32}
        created = self.request(path, self.owner, request, status=201)
        self.assertEqual(self.request(path, self.owner, request, status=201), created)
        self.request(path, self.owner, {**request, 'title': 'Anderer Inhalt'}, status=409)
        detail = path + '/' + created['id']
        update = {'title': 'Bearbeitet', 'walls': [], 'revision': 1, 'request_id': 'b' * 32}
        saved = self.request(detail, self.owner, update)
        self.assertEqual(self.request(detail, self.owner, update), saved)
        self.assertEqual(len(self.request(path, self.owner)), 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM plan_versions').fetchone()[0], 2)
