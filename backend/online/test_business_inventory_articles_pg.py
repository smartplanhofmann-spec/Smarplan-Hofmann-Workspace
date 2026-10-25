"""Real PostgreSQL JSONB/HTTP inventory references under the restricted runtime.

Reuse only the guarded synthetic journey setup, never its tests or a relaxed
financial policy. No provider, SMTP, production account or live data is used.
"""
import json
import unittest

import business_schema
from online import test_business_journey_pg as journey


@unittest.skipUnless(journey.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN not configured')
class InventoryArticlePostgresTests(unittest.TestCase):
    setUp = journey.BusinessJourneyPostgres.setUp
    call = journey.BusinessJourneyPostgres.call
    login = journey.BusinessJourneyPostgres.login

    def project(self, name='Synthetic inventory reference project'):
        return self.call('POST', '/projects', {'name': name, 'customer': 'Synthetic stock customer'}, status=201).json['id']

    def user(self, role, project):
        email = 'inventory-' + role + '@example.test'
        identifier = self.call('POST', '/users', {'email': email, 'password': 'Synthetic-inventory-password-123', 'role': role}, status=201).json['id']
        token = self.login(email, 'Synthetic-inventory-password-123')
        self.call('POST', '/assignments', {'project_id': project, 'user_id': identifier})
        return identifier, token

    def article(self, kind, code, **changes):
        body = journey.request(kind=kind, code=code,
            name='Synthetic ' + code, unit='C62', unit_price_net='123.45', cost_price_net='67.89',
            tax_rate='19', tax_exemption_reason='PRIVATE FINANCIAL ARTICLE NOTE', active=True)
        body.update(changes)
        return self.call('POST', '/business/articles', body).json

    def permission(self, user, scope, effect='allow', *, name='inventory.read', revision=0):
        return self.call('POST', '/business/settings/permissions', journey.request(user_id=user,
            permission=name, scope=scope, effect=effect, revision=revision)).json

    def test_jsonb_projection_and_pagination_are_operational_without_financial_catalog_access(self):
        self.assertEqual(self.office.db.execute('SELECT current_user').fetchone()[0], 'smartplan-online')
        self.assertTrue(business_schema.require_runtime_security(self.office))
        project = self.project()
        _, technician = self.user('technician', project)
        material = self.article('material', 'SYN-PG-MATERIAL')
        machine = self.article('machine', 'SYN-PG-MACHINE')
        self.article('material', 'SYN-PG-INACTIVE', active=False)
        self.article('service', 'SYN-PG-BOM-SERVICE', components=[{
            'article_id': material['id'], 'article_revision': material['revision'], 'quantity': '1'}])
        before = [dict(row) for row in self.office.db.execute('SELECT id,revision,payload_json FROM business_articles ORDER BY id').fetchall()]
        path = '/business/inventory/articles?project_id=' + project + '&limit=1'
        first = self.call('GET', path, token=technician).json
        self.assertEqual(len(first['items']), 1)
        self.assertTrue(first['has_more'])
        self.assertEqual(first['next_after'], first['items'][0]['id'])
        second = self.call('GET', path + '&after=' + first['next_after'], token=technician).json
        self.assertEqual(len(second['items']), 1)
        self.assertFalse(second['has_more'])
        self.assertIsNone(second['next_after'])
        items = first['items'] + second['items']
        self.assertEqual({item['id'] for item in items}, {material['id'], machine['id']})
        for item in items:
            self.assertEqual(set(item), {'id', 'revision', 'code', 'name', 'unit', 'active'})
            self.assertIs(item['active'], True)
        self.assertNotIn('PRIVATE', json.dumps(items))
        self.assertNotIn('price', json.dumps(items))
        after = [dict(row) for row in self.office.db.execute('SELECT id,revision,payload_json FROM business_articles ORDER BY id').fetchall()]
        self.assertEqual(after, before)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_stock_movements').fetchone()[0], 0)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_inventory_requests').fetchone()[0], 0)
        metadata = self.call('GET', '/business/capabilities?project_id=' + project, token=technician).json
        self.assertIn('inventory_article_refs', metadata['features'])
        self.assertIn('inventory.read', metadata['permissions'])
        self.assertNotIn('finance.read', metadata['permissions'])
        self.call('GET', '/business/articles', token=technician, status=403)
        self.call('GET', '/business/articles/' + material['id'], token=technician, status=403)

    def test_project_only_permission_remains_fresh_and_never_bypasses_membership_or_denies(self):
        project = self.project()
        other = self.project('Other synthetic inventory reference project')
        identifier, token = self.user('accountant', project)
        self.permission(identifier, '*', 'deny', name='finance.read')
        scoped = self.permission(identifier, project)
        self.article('material', 'SYN-PG-SCOPED')
        path = '/business/inventory/articles?project_id=' + project
        self.assertEqual(len(self.call('GET', path, token=token).json['items']), 1)
        self.call('GET', '/business/inventory/articles', token=token, status=403)
        self.call('GET', '/business/inventory/articles?project_id=' + other, token=token, status=404)
        denied = self.permission(identifier, project, 'deny', revision=scoped['revision'])
        self.call('GET', path, token=token, status=403)
        self.permission(identifier, project, revision=denied['revision'])
        self.call('GET', path, token=token)
        self.call('POST', '/assignments', {'project_id': project, 'user_id': identifier, 'remove': True})
        self.call('GET', path, token=token, status=404)
        self.call('POST', '/assignments', {'project_id': project, 'user_id': identifier})
        self.permission(identifier, '*', 'deny')
        self.call('GET', path, token=token, status=403)
        self.call('GET', '/business/articles', token=token, status=403)


if __name__ == '__main__':
    unittest.main()
