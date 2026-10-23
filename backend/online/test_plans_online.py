"""Plan routes against a real disposable PostgreSQL database and MFA session."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
import test_online as fixtures
from online.store import migrate, PostgresOffice, SCHEMA_VERSION
from core import Problem


@unittest.skipUnless(fixtures.DSN, 'Disposable SMARTPLAN_TEST_DSN required')
class OnlinePlanTests(unittest.TestCase):
    setUp = fixtures.OnlineApiTests.setUp
    tearDown = fixtures.OnlineApiTests.tearDown
    request = fixtures.OnlineApiTests.request
    login = fixtures.OnlineApiTests.login

    def test_online_roundtrip_and_concurrent_conflict(self):
        token = self.login()['token']
        project = self.request('/projects', {'name': 'Planprojekt', 'customer': 'Fiktiv'}, token, 201).json['id']
        path = f'/projects/{project}/plans'
        create = {'title': 'EG', 'walls': [], 'request_id': '0' * 32}
        plan = self.request(path, create, token, 201).json
        self.assertEqual(self.request(path, create, token, 201).json, plan)
        detail = path + '/' + plan['id']
        self.assertEqual(self.request(detail, token=token).json, plan)
        self.request(detail, {'title': 'Wrong', 'walls': [], 'revision': 0}, token, 409)
        def save(title):
            office = PostgresOffice(fixtures.DSN)
            try:
                with office.lock, office.db:
                    user = office.user(token)
                    try:
                        return office.save_plan(user, project, {'title': title, 'walls': [], 'revision': 1, 'request_id': ('a' if title == 'A' else 'b') * 32}, plan['id'])['revision']
                    except Problem as error:
                        return error.status
            finally:
                office.db.close()
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertEqual(sorted(executor.map(save, ['A', 'B'])), [2, 409])
        self.assertEqual(self.request(path, token=token).json[0]['revision'], 2)
        migrate(fixtures.DSN)
        self.assertEqual(self.request(detail, token=token).json['revision'], 2)

    def test_migration_from_v1_preserves_existing_data(self):
        with self.office.db:
            self.office.db.execute('DROP TABLE plan_versions')
            self.office.db.execute('UPDATE smartplan_schema SET version=1')
        migrate(fixtures.DSN)
        migrate(fixtures.DSN)
        self.assertEqual(self.office.db.execute('SELECT version FROM smartplan_schema').fetchone()[0], SCHEMA_VERSION)
        self.assertEqual(self.office.db.execute('SELECT id FROM users WHERE id=?', (self.owner_id,)).fetchone()[0], self.owner_id)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM plan_versions').fetchone()[0], 0)


    def test_mfa_device_access_is_limited_to_plans_and_can_be_revoked(self):
        owner = self.login()['token']
        grant = self.request('/offline/access', {}, owner, 201).json
        token = grant['token']
        project = self.request('/projects', {'name': 'Offline', 'customer': 'Test'}, owner, 201).json['id']
        self.request('/projects', token=token)
        path = f'/projects/{project}/plans'
        self.request(path, {'title': 'iPad', 'walls': [], 'request_id': 'e' * 32}, token, 201)
        self.request('/users', token=token, status=403)
        self.request('/offline/access', {}, token, 403)
        self.request('/projects', {'name': 'No'}, token, 403)
        self.request('/offline/logout', {}, token)
        self.request(path, token=token, status=401)
