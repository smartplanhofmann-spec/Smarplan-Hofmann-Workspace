"""Bounded operational article references never grant access to price catalogs."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid

import business_api
from business_documents import Documents
from business_foundation import BusinessFoundation
from business_inventory import BusinessInventory, methods
from core import Office, Problem, canonical


def request(**values):
    return {'request_id': uuid.uuid4().hex, **values}


class InventoryArticleFixture:
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='synthetic-inventory-refs-')
        self.addCleanup(temporary.cleanup)
        self.office = Office(Path(temporary.name) / 'office.db')
        self.addCleanup(self.office.db.close)
        self.owner = self.actor('owner')
        self.tech = self.actor('technician')
        self.scoped = self.actor('accountant')
        self.project = self.office.add_project(self.owner, 'Synthetic assigned stock', 'Synthetic customer')
        self.other = self.office.add_project(self.owner, 'Other synthetic stock', 'Other customer')
        for actor in (self.tech, self.scoped):
            self.office.assign(self.owner, self.project, actor['id'])
        self.foundation = BusinessFoundation(self.office)
        self.api = BusinessInventory(self.office)
        self.grant(self.scoped, 'finance.read', '*', 'deny')
        self.grant(self.scoped, 'inventory.read', self.project)
        self.material = self.article('material', 'SYN-MATERIAL')
        self.machine = self.article('machine', 'SYN-MACHINE')
        self.service = self.article('service', 'SYN-SERVICE')
        self.inactive = self.article('material', 'SYN-INACTIVE', active=False)

    def actor(self, role):
        email = role + '-' + uuid.uuid4().hex[:8] + '@example.test'
        return {'id': self.office.add_user(email, 'Synthetic-password-123', role), 'email': email, 'role': role}

    def grant(self, actor, permission, scope, effect='allow', revision=0):
        return self.foundation.save_grant(self.owner, request(user_id=actor['id'], permission=permission,
            scope=scope, effect=effect, revision=revision))

    def article(self, kind, code, active=True):
        return Documents(self.office).save_article(self.owner, request(code=code, name='Synthetic ' + code,
            kind=kind, unit='C62', active=active, currency='EUR', unit_price_net='123.45', cost_price_net='67.89', tax_rate='19'))

    def problem(self, status, action):
        with self.assertRaises(Problem) as failure:
            action()
        self.assertEqual(failure.exception.status, status)


class InventoryArticleTests(InventoryArticleFixture, unittest.TestCase):
    def test_operational_projection_is_exact_read_only_and_excludes_nested_finance_and_supplier_data(self):
        payload = json.loads(self.office.db.execute('SELECT payload_json FROM business_articles WHERE id=?', (self.material['id'],)).fetchone()[0])
        # Extra import/future payload fields must not reach an operational DTO.
        payload.update(supplier={'name': 'SECRET SUPPLIER', 'email': 'private-supplier@example.test'},
            components=[{'name': 'SECRET BOM', 'cost_price_net': '987.65'}], private_notes='SECRET NOTE')
        with self.office.db:
            self.office.db.execute('UPDATE business_articles SET payload_json=? WHERE id=?', (canonical(payload), self.material['id']))
        before = self.office.db.total_changes
        result = self.api.article_references(self.tech)
        self.assertEqual(set(result), {'items', 'has_more', 'next_after'})
        self.assertEqual({item['id'] for item in result['items']}, {self.material['id'], self.machine['id']})
        for item in result['items']:
            self.assertEqual(set(item), {'id', 'revision', 'code', 'name', 'unit', 'active'})
            self.assertIs(item['active'], True)
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertNotIn('price', json.dumps(result))
        self.assertEqual(self.office.db.total_changes, before)
        self.assertEqual(json.loads(self.office.db.execute('SELECT payload_json FROM business_articles WHERE id=?', (self.material['id'],)).fetchone()[0]), payload)
        self.problem(403, lambda: Documents(self.office).articles(self.tech))

    def test_project_only_inventory_allow_is_not_a_global_grant_or_an_assignment_bypass(self):
        self.assertEqual(len(self.api.article_references(self.scoped, project_id=self.project)['items']), 2)
        self.problem(403, lambda: self.api.article_references(self.scoped))
        self.problem(404, lambda: self.api.article_references(self.scoped, project_id=self.other))
        self.office.assign(self.owner, self.project, self.scoped['id'], remove=True)
        self.problem(404, lambda: self.api.article_references(self.scoped, project_id=self.project))

    def test_explicit_project_and_global_denies_win_without_global_fallback(self):
        self.grant(self.tech, 'inventory.read', self.project, 'deny')
        self.problem(403, lambda: self.api.article_references(self.tech, project_id=self.project))
        self.api.article_references(self.tech)
        self.grant(self.scoped, 'inventory.read', '*', 'deny')
        self.problem(403, lambda: self.api.article_references(self.scoped, project_id=self.project))

    def test_current_role_and_activation_are_rechecked_instead_of_trusting_actor_snapshot(self):
        self.api.article_references(self.tech)
        with self.office.db:
            self.office.db.execute("UPDATE users SET role='accountant' WHERE id=?", (self.tech['id'],))
        self.problem(403, lambda: self.api.article_references(self.tech))
        with self.office.db:
            self.office.db.execute('UPDATE users SET active=0 WHERE id=?', (self.scoped['id'],))
        self.problem(401, lambda: self.api.article_references(self.scoped, project_id=self.project))

    def test_cursor_is_bounded_and_filters_inactive_and_nonphysical_rows_before_pagination(self):
        # These IDs sort before normal UUIDs: a raw-row LIMIT followed by Python
        # filtering would produce an empty first page and conceal valid choices.
        with self.office.db:
            for index in range(12):
                value = {**self.service, 'active': index % 2 == 0, 'kind': 'service' if index % 2 == 0 else 'material'}
                self.office.db.execute('INSERT INTO business_articles(id,revision,payload_json,created_by,updated_by,created_at,updated_at) VALUES(?,1,?,?,?,?,?)',
                    (format(index + 1, '032x'), canonical(value), self.owner['id'], self.owner['id'], '2030-01-01', '2030-01-01'))
        first = self.api.article_references(self.tech, limit=1)
        self.assertEqual(len(first['items']), 1)
        self.assertTrue(first['has_more'])
        self.assertEqual(first['next_after'], first['items'][-1]['id'])
        second = self.api.article_references(self.tech, after=first['next_after'], limit='1')
        self.assertEqual(len(second['items']), 1)
        self.assertFalse(second['has_more'])
        self.assertIsNone(second['next_after'])
        self.assertEqual({first['items'][0]['id'], second['items'][0]['id']}, {self.material['id'], self.machine['id']})

    def test_invalid_bounds_cursor_and_project_never_silently_become_a_global_list(self):
        for limit in (0, -1, 201, True, 'all', '1.5', '10000'):
            self.problem(400, lambda: self.api.article_references(self.tech, limit=limit))
        self.problem(400, lambda: self.api.article_references(self.tech, after='broken'))
        self.problem(400, lambda: self.api.article_references(self.tech, project_id=''))

    def test_feature_is_additive_metadata_and_never_a_finance_or_offline_grant(self):
        metadata = business_api.capabilities(self.office, self.tech)
        self.assertIn('inventory_article_refs', metadata['features'])
        self.assertNotIn('finance.read', metadata['permissions'])
        self.assertEqual(methods('/inventory/articles'), 'GET')
        self.problem(403, lambda: business_api.dispatch(self.office, self.tech,
            '/business/inventory/articles', 'GET', {}, offline=True, offline_capabilities=['field_media']))


# The real online adapter imports POSIX fcntl storage protection. Its HTTP
# contracts run in Linux/online CI; all seven domain tests remain cross-platform.
ONLINE_AVAILABLE = bool(os.name == 'posix' and importlib.util.find_spec('flask') and importlib.util.find_spec('psycopg'))


@unittest.skipUnless(ONLINE_AVAILABLE, 'Real online Flask adapter requires POSIX and the separately locked online dependencies')
class InventoryArticleHttpTests(InventoryArticleFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        from cryptography.fernet import Fernet
        from online.web import create_app
        self.client = create_app(office=self.office, key=Fernet.generate_key(), host='office.example.test').test_client()
        self.token = self.office.login(self.tech['email'], 'Synthetic-password-123')
        self.scoped_token = self.office.login(self.scoped['email'], 'Synthetic-password-123')

    def call(self, path, *, status=200, token=None, method='GET'):
        result = self.client.open('/api/v1/business' + path, method=method, base_url='https://office.example.test',
            headers={'Authorization': 'Bearer ' + (token or self.token)})
        self.assertEqual(result.status_code, status, result.get_data(as_text=True))
        return result

    def test_real_http_operational_list_succeeds_without_weakening_financial_articles(self):
        metadata = self.call('/capabilities').json
        self.assertIn('inventory_article_refs', metadata['features'])
        self.assertNotIn('finance.read', metadata['permissions'])
        result = self.call('/inventory/articles?limit=1')
        self.assertEqual(result.headers['Cache-Control'], 'no-store')
        self.assertEqual(len(result.json['items']), 1)
        self.call('/articles', status=403)
        self.call('/inventory/articles', method='POST', status=405)
        self.call('/inventory/articles?include_prices=true', status=400)

    def test_real_http_scoped_access_and_fresh_revocation(self):
        metadata = self.call('/capabilities?project_id=' + self.project, token=self.scoped_token).json
        self.assertIn('inventory_article_refs', metadata['features'])
        self.assertIn('inventory.read', metadata['permissions'])
        self.assertNotIn('finance.read', metadata['permissions'])
        self.call('/inventory/articles?project_id=' + self.project, token=self.scoped_token)
        self.call('/inventory/articles', token=self.scoped_token, status=403)
        self.office.assign(self.owner, self.project, self.scoped['id'], remove=True)
        self.call('/inventory/articles?project_id=' + self.project, token=self.scoped_token, status=404)
        with self.office.db:
            self.office.db.execute('UPDATE users SET active=0 WHERE id=?', (self.tech['id'],))
        self.call('/inventory/articles', status=401)


if __name__ == '__main__':
    unittest.main()
