"""Real password/MFA/Flask checks for the operational article reference route."""
from pathlib import Path
import tempfile
import time
import unittest
import uuid

from cryptography.fernet import Fernet

from core import Office
from business_documents import Documents
from online.auth import totp
from online.web import create_app


def request(**values):
    return dict(request_id=uuid.uuid4().hex, **values)


class InventoryArticleReferenceApiTests(unittest.TestCase):
    host = 'inventory-reference.example.test'
    password = 'Synthetic-reference-password-123'

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='inventory-reference-http-')
        self.addCleanup(temporary.cleanup)
        self.office = Office(Path(temporary.name) / 'synthetic.sqlite3')
        self.addCleanup(self.office.db.close)
        self.office.db.executescript('''
            CREATE TABLE mfa(user_id TEXT PRIMARY KEY REFERENCES users(id),secret TEXT NOT NULL,
                last_step BIGINT NOT NULL DEFAULT -1,recovery TEXT NOT NULL);
            CREATE TABLE auth_challenges(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),
                credential TEXT NOT NULL,secret TEXT NOT NULL,expiry DOUBLE PRECISION NOT NULL,
                failures INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE login_limits(key TEXT PRIMARY KEY,failures INTEGER NOT NULL,reset_at DOUBLE PRECISION NOT NULL);
        ''')
        self.owner = self.actor('owner')
        self.warehouse = self.actor('technician')
        self.project = self.office.add_project(self.owner, 'Synthetic warehouse project', 'Synthetic customer')
        self.private_project = self.office.add_project(self.owner, 'Unassigned synthetic project', 'Other synthetic customer')
        self.office.assign(self.owner, self.project, self.warehouse['id'])
        documents = Documents(self.office)
        self.articles = []
        for index, (kind, active) in enumerate((('material', True), ('machine', True),
                                                ('service', True), ('labor', True), ('material', False))):
            self.articles.append(documents.save_article(self.owner, request(
                code='SYN-' + str(index), name='Synthetic article ' + str(index), kind=kind,
                unit='Stk', unit_price_net='123.45', cost_price_net='67.89',
                tax_rate='19', tax_category='S', currency='EUR', active=active)))
        self.key = Fernet.generate_key()
        self.client = create_app(office=self.office, key=self.key, host=self.host, storage_config={}).test_client()
        self.owner_token = self.login(self.owner['email'])
        self.warehouse_token = self.login(self.warehouse['email'])

    def actor(self, role):
        email = role + '@inventory-reference.example.test'
        return dict(id=self.office.add_user(email, self.password, role), email=email, role=role)

    def call(self, path, *, token=None, method='GET', body=None, status=200):
        result = self.client.open('/api/v1' + path, base_url='https://' + self.host,
                                  method=method, json=body,
                                  headers={'Authorization': 'Bearer ' + token} if token else {})
        self.assertEqual(result.status_code, status, (path, result.data[:350]))
        return result

    def login(self, email):
        pending = self.call('/login', method='POST', body=dict(email=email, password=self.password)).json
        self.assertTrue(pending['mfa_required'])
        result = self.call('/login/verify', method='POST', body=dict(
            challenge=pending['challenge'],
            code=totp(pending['enrollment']['secret'], int(time.time() // 30)))).json
        return result['token']

    def path(self, query=''):
        return '/business/inventory/articles' + ('?' + query if query else '')

    def expected(self):
        return sorted([{key: article[key] for key in ('id', 'revision', 'code', 'name', 'unit', 'active')}
                       for article in self.articles[:2]], key=lambda row: row['id'])

    def test_authenticated_reference_feature_and_price_free_owner_and_warehouse_reads(self):
        for token in (self.owner_token, self.warehouse_token):
            capabilities = self.call('/business/capabilities?project_id=' + self.project, token=token).json
            self.assertIn('inventory_article_refs', capabilities['features'])
            result = self.call(self.path('project_id=' + self.project), token=token)
            self.assertEqual(result.json, dict(items=self.expected(), has_more=False, next_after=None))
            self.assertEqual(result.mimetype, 'application/json')
        self.call('/business/articles', token=self.warehouse_token, status=403)
        self.call('/business/finance/payments', token=self.warehouse_token, status=403)

    def test_mfa_sessions_are_required_and_other_http_methods_are_not_allowed(self):
        self.call(self.path(), status=401)
        self.call(self.path(), token='not-an-authenticated-session', status=401)
        denied = self.call(self.path(), token=self.owner_token, method='POST', body={}, status=405)
        self.assertEqual(denied.headers['Allow'], 'GET')

    def test_real_query_parser_rejects_unknown_duplicates_blank_and_noncanonical_page_values(self):
        for query in ('unexpected=1', 'limit=1&limit=2', 'after=a&after=b',
                      'project_id=' + self.project + '&project_id=' + self.project,
                      'limit=', 'limit=0', 'limit=201', 'limit=01', 'limit=-1',
                      'limit=1.0', 'limit=true', 'limit=%201', 'limit=%2B1',
                      'after=', 'after=' + 'A' * 32, 'project_id=none'):
            with self.subTest(query=query):
                self.call(self.path(query), token=self.owner_token, status=400)

    def test_cursor_cannot_reuse_withdrawn_project_or_global_inventory_permission(self):
        first = self.call(self.path('project_id=' + self.project + '&limit=1'),
                          token=self.warehouse_token).json
        self.assertEqual(first['items'], self.expected()[:1])
        self.assertTrue(first['has_more'])
        next_path = self.path('project_id=' + self.project + '&after=' + first['next_after'] + '&limit=1')
        second = self.call(next_path, token=self.warehouse_token).json
        self.assertEqual(second, dict(items=self.expected()[1:], has_more=False, next_after=None))
        self.call('/business/settings/permissions', token=self.owner_token, method='POST',
                  body=request(user_id=self.warehouse['id'], permission='inventory.read',
                               scope=self.project, effect='deny', revision=0))
        self.call(next_path, token=self.warehouse_token, status=403)
        self.call(self.path('project_id=' + self.private_project), token=self.warehouse_token, status=404)
        self.call('/business/settings/permissions', token=self.owner_token, method='POST',
                  body=request(user_id=self.warehouse['id'], permission='inventory.read',
                               scope='*', effect='deny', revision=0))
        self.call(self.path(), token=self.warehouse_token, status=403)

    def test_revoked_assignment_and_disabled_login_do_not_keep_catalogue_access(self):
        self.call(self.path('project_id=' + self.project), token=self.warehouse_token)
        with self.office.db:
            self.office.db.execute('DELETE FROM assignments WHERE user_id=? AND project_id=?',
                                   (self.warehouse['id'], self.project))
        self.call(self.path('project_id=' + self.project), token=self.warehouse_token, status=404)
        with self.office.db:
            self.office.db.execute('UPDATE users SET active=0 WHERE id=?', (self.warehouse['id'],))
        self.call(self.path(), token=self.warehouse_token, status=401)

    def test_company_session_isolation_rejects_a_foreign_real_login(self):
        temporary = tempfile.TemporaryDirectory(prefix='inventory-reference-foreign-http-')
        self.addCleanup(temporary.cleanup)
        other = Office(Path(temporary.name) / 'foreign.sqlite3')
        self.addCleanup(other.db.close)
        other_client = create_app(office=other, key=Fernet.generate_key(), host=self.host,
                                  storage_config={}).test_client()
        result = other_client.get('/api/v1' + self.path(), base_url='https://' + self.host,
                                  headers={'Authorization': 'Bearer ' + self.owner_token})
        self.assertEqual(result.status_code, 401)


if __name__ == '__main__':
    unittest.main()
