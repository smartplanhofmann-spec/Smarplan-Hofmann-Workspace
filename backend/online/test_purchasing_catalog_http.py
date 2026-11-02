"""Independent price-free purchasing catalogue through Flask HTTP and MFA.

All identities and data are synthetic. No supplier or external service is
contacted. These cases exercise the real authentication, dispatch and domain
handlers; no catalogue responses or permission checks are mocked.
"""
import unittest
from urllib.parse import urlencode

from online import test_purchasing_journey as fixture


class PurchasingCatalogHTTPTests(unittest.TestCase):
    # Reuse the authenticated SQLite fixture without inheriting its journey tests.
    setUp = fixture.PurchasingJourneyTests.setUp
    open_app = fixture.PurchasingJourneyTests.open_app
    call = fixture.PurchasingJourneyTests.call
    login = fixture.PurchasingJourneyTests.login
    article_record = fixture.PurchasingJourneyTests.article_record

    def reader(self, label='receiver', *, role='technician'):
        email, password = label + '@example.test', 'Synthetic-catalog-password-123'
        user = self.call('/users', {'email': email, 'password': password, 'role': role},
                         status=201).json['id']
        self.call('/assignments', {'project_id': self.project, 'user_id': user})
        return user, self.login(email, password)

    def permission(self, user, name, *, scope='*', effect='allow', revision=0):
        return self.call('/business/settings/permissions', fixture.request(
            user_id=user, permission=name, scope=scope, effect=effect,
            revision=revision)).json

    def catalog_article(self, code, *, name=None, kind='material', active=True):
        return self.call('/business/articles', fixture.request(
            code=code, name=name or code, kind=kind, active=active, unit='Stk',
            unit_price_net='987.6543', cost_price_net='456.7890',
            tax_rate='19', tax_category='S', currency='EUR')).json

    def catalog(self, *, token='owner', status=200, **filters):
        suffix = '?' + urlencode(filters) if filters else ''
        return self.call('/business/purchasing/articles' + suffix,
                         token=token, status=status)

    def calculated_article(self, code, *, kind='material', components=None):
        preview = self.call('/business/commercial/pricing/preview', fixture.request(
            base_cost_net='12.34', labor_hours='2', hourly_cost_net='20',
            overhead_percent='10', markup_percent='25', quantity='1', kind=kind, unit='Stk',
            source_article_id=self.article['id'], source_article_revision=self.article['revision'],
            components=components or [])).json
        return self.call('/business/articles', fixture.request(code=code,
            name='Synthetic calculated ' + kind, pricing=preview['inputs'],
            pricing_hash=preview['preview_hash'], price_confirmation=True)).json

    def test_calculated_article_financial_snapshots_never_escape_via_draft_replay_or_scan(self):
        article = self.calculated_article('CAT-CALCULATED')
        service = self.calculated_article('CAT-COMPONENTS', kind='service', components=[{
            'article_id': self.article['id'], 'article_revision': self.article['revision'], 'quantity': '2'}])
        snapshot = article['pricing_snapshot']
        self.assertTrue(snapshot['source_articles'])
        for key in ('profit_net', 'margin_percent', 'net', 'gross'):
            self.assertIn(key, snapshot['totals'])
        self.assertTrue(service['components'])
        self.assertTrue(service['pricing_snapshot']['components'])
        user, token = self.reader()
        self.permission(user, 'inventory.write')
        body = fixture.request(project_id=self.project,
            supplier_name='Synthetic calculated-material supplier', status='draft',
            items=[{'article_id': article['id'], 'quantity': '2.0000'}])
        draft = self.call('/business/inventory/orders', body, token=token, status=201).json
        allowed = {'id', 'revision', 'code', 'name', 'kind', 'unit', 'active'}
        self.assertEqual(set(draft['items'][0]['article_snapshot']), allowed)
        public_order = self.call('/business/purchasing/orders/' + draft['id'], token=token).json
        self.assertEqual(public_order['items'][0]['article_id'], article['id'])
        self.assertNotIn('pricing_snapshot', str(public_order))
        self.assertNotIn('profit_net', str(public_order))
        self.call('/business/inventory/orders/' + draft['id'], token=token, status=403)

        # A full earlier replay must be reprojected when its reader loses finance rights.
        self.permission(user, 'finance.read')
        privileged = self.call('/business/inventory/orders', body, token=token, status=201).json
        self.assertEqual(privileged['items'][0]['article_snapshot']['pricing_snapshot'], snapshot)
        self.permission(user, 'finance.read', effect='deny', revision=1)
        replay = self.call('/business/inventory/orders', body, token=token, status=201).json
        self.assertEqual(replay, draft)
        for code, original in (('CAT-CALCULATED', article), ('CAT-COMPONENTS', service)):
            operational = self.call('/business/inventory/scan?' + urlencode({'code': code}), token=token).json
            self.assertEqual(set(operational), allowed)
            self.assertEqual(operational['id'], original['id'])
            owner_scan = self.call('/business/inventory/scan?' + urlencode({'code': code})).json
            self.assertEqual(owner_scan['pricing_snapshot'], original['pricing_snapshot'])
            self.assertEqual(owner_scan['components'], original['components'])
        # The source and financial archive stay complete; this is response projection only.
        stored = self.call('/business/inventory/orders/' + draft['id']).json
        self.assertEqual(stored['items'][0]['article_snapshot']['pricing_snapshot'], snapshot)
        self.assertEqual(self.call('/business/articles/' + article['id']).json['pricing_snapshot'], snapshot)

    def test_inventory_reader_can_find_and_propose_unstocked_article_without_finance(self):
        user, token = self.reader()
        self.permission(user, 'inventory.write')
        article = self.catalog_article('FRESH-NO-STOCK', name='Synthetisches neues Lagerteil')
        self.assertEqual(self.call('/business/inventory/stock', token=token).json['items'], [])
        capabilities = self.call('/business/capabilities', token=token).json
        self.assertIn('purchasing_catalog', capabilities['features'])
        self.assertIn('inventory.read', capabilities['permissions'])
        self.assertFalse(any(value.startswith('finance.') for value in capabilities['permissions']))
        self.call('/business/articles', token=token, status=403)
        self.catalog(token=None, status=401)

        before = self.office.db.total_changes
        result = self.catalog(token=token, query='fresh-no-stock').json
        self.assertEqual(self.office.db.total_changes, before)
        self.assertEqual(result['total'], 1)
        self.assertIsNone(result['next_offset'])
        self.assertEqual(result['items'], [{key: article[key] for key in
            ('id', 'revision', 'code', 'name', 'kind', 'unit', 'active')}])
        self.assertEqual(set(result['items'][0]),
                         {'id', 'revision', 'code', 'name', 'kind', 'unit', 'active'})
        self.assertNotIn('456.7890', str(result))
        self.assertNotIn('987.6543', str(result))
        # Owners receive the same deliberately narrow catalogue projection.
        self.assertEqual(self.catalog(query='FRESH-NO-STOCK').json, result)

        order = self.call('/business/inventory/orders', fixture.request(
            project_id=self.project, supplier_name='Synthetic catalogue supplier', status='draft',
            items=[{'article_id': result['items'][0]['id'], 'quantity': '2.1250'}]),
            token=token, status=201).json
        self.assertEqual(order['items'][0]['article_id'], article['id'])
        self.assertEqual(order['items'][0]['quantity'], '2.1250')
        self.assertNotIn('cost_price_net', order['items'][0]['article_snapshot'])
        self.assertEqual(self.call('/business/inventory/stock', token=token).json['items'], [])

    def test_project_permission_and_membership_are_checked_again_on_every_read(self):
        user, token = self.reader()
        self.permission(user, 'inventory.read', scope=self.project, effect='deny')
        before = self.office.db.total_changes
        self.catalog(token=token, project_id=self.project, status=403)
        self.catalog(token=token)
        self.assertEqual(self.office.db.total_changes, before)
        self.permission(user, 'inventory.read', scope=self.project, revision=1)
        self.catalog(token=token, project_id=self.project)

        private = self.call('/projects', {'name': 'Synthetic private project',
                           'customer': 'Synthetic private customer'}, status=201).json['id']
        self.catalog(token=token, project_id=private, status=404)
        self.call('/assignments', {'project_id': self.project, 'user_id': user, 'remove': True})
        self.catalog(token=token, project_id=self.project, status=404)

        scoped_user, scoped_token = self.reader('scoped-reader', role='accountant')
        for name in ('finance.read', 'finance.write'):
            self.permission(scoped_user, name, effect='deny')
        self.permission(scoped_user, 'inventory.read', scope=self.project)
        self.catalog(token=scoped_token, status=403)
        result = self.catalog(token=scoped_token, project_id=self.project).json
        self.assertGreater(result['total'], 0)
        self.permission(scoped_user, 'inventory.read', scope=self.project,
                        effect='deny', revision=1)
        self.catalog(token=scoped_token, project_id=self.project, status=403)

    def test_search_pagination_and_rejected_filters_do_not_write_to_database(self):
        _, token = self.reader()
        expected = []
        for index in (4, 1, 3, 0, 5, 2):
            expected.append(self.catalog_article('CAT-PAGE-' + str(index),
                name='Synthetic catalogue page ' + str(index),
                kind='machine' if index % 2 else 'material')['id'])
        self.catalog_article('CAT-PAGE-INACTIVE', active=False)
        self.catalog_article('CAT-PAGE-SERVICE', kind='service')
        self.catalog_article('CAT-PAGE-LABOR', kind='labor')
        before = self.office.db.total_changes
        full = self.catalog(token=token, query='cat-page', limit=100).json
        self.assertEqual(full['total'], len(expected))
        self.assertCountEqual([item['id'] for item in full['items']], expected)
        self.assertIsNone(full['next_offset'])
        self.assertEqual(self.catalog(token=token, query='synthetic catalogue page').json['total'], 6)
        self.assertEqual(self.catalog(token=token, query="%_' OR 1=1 --").json['total'], 0)

        paged, offset = [], 0
        for index in range(3):
            page = self.catalog(token=token, query='CAT-PAGE', limit=2, offset=offset).json
            self.assertEqual(page['total'], 6)
            self.assertEqual(len(page['items']), 2)
            paged.extend(page['items'])
            self.assertEqual(page['next_offset'], None if index == 2 else offset + 2)
            offset += 2
        self.assertEqual(paged, full['items'])
        self.assertEqual(len({item['id'] for item in paged}), 6)
        beyond = self.catalog(token=token, query='CAT-PAGE', limit=1, offset=100000).json
        self.assertEqual((beyond['items'], beyond['total'], beyond['next_offset']), ([], 6, None))

        for filters in ({'limit': 0}, {'limit': 101}, {'limit': '1.5'},
                        {'offset': -1}, {'offset': 100001}, {'include_prices': 'true'}):
            with self.subTest(filters=filters):
                self.catalog(token=token, status=400, **filters)
        for query in ('query=CAT&query=PAGE', 'limit=1&limit=2',
                      'project_id=' + self.project + '&project_id=' + self.project):
            with self.subTest(query=query):
                self.call('/business/purchasing/articles?' + query, token=token, status=400)
        self.assertEqual(self.office.db.total_changes, before)


if __name__ == '__main__':
    unittest.main()
