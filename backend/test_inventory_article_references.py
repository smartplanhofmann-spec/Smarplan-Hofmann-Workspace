"""Price-free article selections through real disposable catalogue/ACL state."""
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from core import Office, Problem
from business_documents import Documents
from business_foundation import BusinessFoundation
from business_inventory import BusinessInventory, dispatch


def request(**values):
    return dict(request_id=uuid.uuid4().hex, **values)


class InventoryArticleReferenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='inventory-reference-domain-')
        self.addCleanup(temporary.cleanup)
        self.office = Office(Path(temporary.name) / 'synthetic.sqlite3')
        self.addCleanup(self.office.db.close)
        self.owner = self.actor('owner')
        self.warehouse = self.actor('technician')
        self.scoped = self.actor('accountant')
        self.project = self.office.add_project(self.owner, 'Synthetic assigned project', 'Synthetic customer')
        self.private_project = self.office.add_project(self.owner, 'Synthetic private project', 'Other synthetic customer')
        self.office.assign(self.owner, self.project, self.warehouse['id'])
        self.office.assign(self.owner, self.project, self.scoped['id'])
        self.api = BusinessInventory(self.office)
        self.documents = Documents(self.office)
        self.articles = [self.article('material'), self.article('machine'),
                         self.article('service'), self.article('labor'),
                         self.article('material', active=False)]

    def actor(self, role):
        email = uuid.uuid4().hex + '@inventory.example.test'
        return dict(id=self.office.add_user(email, 'Synthetic-reference-password-123', role),
                    email=email, role=role)

    def article(self, kind, *, active=True):
        code = 'SYN-' + uuid.uuid4().hex[:12]
        return self.documents.save_article(self.owner, request(
            code=code, name='Synthetic ' + kind + ' ' + code, kind=kind, unit='Stk',
            unit_price_net='978.65', cost_price_net='432.10', tax_rate='19',
            tax_category='S', currency='EUR', active=active))

    def grant(self, actor, *, scope='*', effect='allow', revision=0):
        return BusinessFoundation(self.office).save_grant(self.owner, request(
            user_id=actor['id'], permission='inventory.read', scope=scope,
            effect=effect, revision=revision))

    def denied(self, status, function, *args, **kwargs):
        with self.assertRaises(Problem) as error:
            function(*args, **kwargs)
        self.assertEqual(error.exception.status, status, error.exception.message)

    def public(self, article):
        return {name: article[name] for name in ('id', 'revision', 'code', 'name', 'unit', 'active')}

    def test_owner_and_warehouse_receive_only_active_physical_identities(self):
        expected = sorted([self.public(article) for article in self.articles[:2]], key=lambda item: item['id'])
        for actor in (self.owner, self.warehouse):
            with self.subTest(role=actor['role']):
                result = self.api.article_references(actor, project_id=self.project)
                self.assertEqual(result, dict(items=expected, has_more=False, next_after=None))
                for item in result['items']:
                    self.assertEqual(set(item), {'id', 'revision', 'code', 'name', 'unit', 'active'})

    def test_future_nested_financial_fields_never_escape_even_for_owner(self):
        article = self.articles[0]
        row = self.office.db.execute('SELECT payload_json FROM business_articles WHERE id=?', (article['id'],)).fetchone()
        payload = json.loads(row['payload_json'])
        payload['future_private_pricing'] = {'supplier': 'DO-NOT-EXPOSE', 'components': [{'margin': '98765'}]}
        payload['pricing_snapshot'] = {'confidential': 'DO-NOT-EXPOSE'}
        with self.office.db:
            self.office.db.execute('UPDATE business_articles SET payload_json=? WHERE id=?',
                                   (json.dumps(payload), article['id']))
        result = self.api.article_references(self.owner)
        item = next(item for item in result['items'] if item['id'] == article['id'])
        self.assertEqual(item, self.public(article))
        self.assertNotIn('DO-NOT-EXPOSE', json.dumps(result))

    def test_keyset_pages_include_every_eligible_item_once_and_skip_hidden_rows(self):
        eligible = self.articles[:2] + [self.article('material') for _ in range(5)]
        hidden = [self.article('service') for _ in range(7)] + [self.article('machine', active=False)]
        expected = sorted([self.public(article) for article in eligible], key=lambda item: item['id'])
        seen, after = [], None
        while True:
            page = self.api.article_references(self.warehouse, project_id=self.project, after=after, limit=2)
            self.assertEqual(page['items'], expected[len(seen):len(seen) + 2])
            seen.extend(page['items'])
            self.assertEqual(page['has_more'], len(seen) < len(expected))
            if not page['has_more']:
                self.assertIsNone(page['next_after'])
                break
            after = page['next_after']
            self.assertEqual(after, page['items'][-1]['id'])
        self.assertEqual(seen, expected)
        for cursor in (hidden[0]['id'], expected[-1]['id'], 'f' * 32):
            page = self.api.article_references(self.warehouse, after=cursor, limit=200)
            self.assertEqual(page['items'], [item for item in expected if item['id'] > cursor])
            self.assertFalse(page['has_more'])

    def test_scoped_grant_does_not_enable_global_catalogue_or_another_project(self):
        self.denied(403, self.api.article_references, self.scoped)
        self.grant(self.scoped, scope=self.project)
        self.assertEqual(len(self.api.article_references(self.scoped, project_id=self.project)['items']), 2)
        self.denied(403, self.api.article_references, self.scoped)
        self.denied(404, self.api.article_references, self.scoped, project_id=self.private_project)

    def test_fresh_global_and_project_denials_block_an_already_issued_cursor(self):
        first = self.api.article_references(self.warehouse, project_id=self.project, limit=1)
        self.grant(self.warehouse, scope=self.project, effect='deny')
        self.denied(403, self.api.article_references, self.warehouse,
                    project_id=self.project, after=first['next_after'])
        self.grant(self.warehouse, scope=self.project, effect='allow', revision=1)
        self.grant(self.warehouse, effect='deny')
        self.denied(403, self.api.article_references, self.warehouse, project_id=self.project)
        self.denied(403, self.api.article_references, self.warehouse)

    def test_assignment_and_user_revocation_are_checked_fresh(self):
        self.api.article_references(self.warehouse, project_id=self.project)
        with self.office.db:
            self.office.db.execute('DELETE FROM assignments WHERE user_id=? AND project_id=?',
                                   (self.warehouse['id'], self.project))
        self.denied(404, self.api.article_references, self.warehouse, project_id=self.project)
        with self.office.db:
            self.office.db.execute('UPDATE users SET active=0 WHERE id=?', (self.warehouse['id'],))
        self.denied(401, self.api.article_references, {**self.warehouse, 'role': 'owner'})

    def test_invalid_cursor_scope_and_limit_are_rejected_without_coercion(self):
        for value in ('', 'X' * 32, 'a' * 31, 'a' * 33, ' ' + 'a' * 32, ['a' * 32], 1, True):
            for name in ('after', 'project_id'):
                with self.subTest(field=name, value=value):
                    self.denied(400, self.api.article_references, self.owner, **{name: value})
        for value in (0, 201, -1, True, 1.0, '', '01', '+1', ' 1', '1 ', '1.0', '201', ['1']):
            with self.subTest(limit=value):
                self.denied(400, self.api.article_references, self.owner, limit=value)
        self.assertEqual(len(self.api.article_references(self.owner, limit='1')['items']), 1)

    def test_dispatch_rejects_unrecognized_or_multivalued_query_channels(self):
        for data in ({'_query': {'search': 'x'}}, {'_query': {'limit': ['1']}},
                     {'_query': {'after': None}}, {'_query': []}, {'extra': 'ignored'}, []):
            with self.subTest(data=data):
                self.denied(400, dispatch, self.office, self.owner, '/inventory/articles', 'GET', data)

    def test_separate_company_catalogues_do_not_share_article_identity_rows(self):
        temporary = tempfile.TemporaryDirectory(prefix='inventory-reference-other-company-')
        self.addCleanup(temporary.cleanup)
        other = Office(Path(temporary.name) / 'other.sqlite3')
        self.addCleanup(other.db.close)
        owner = dict(id=other.add_user('other@example.test', 'Synthetic-other-password-123', 'owner'), role='owner')
        self.assertEqual(BusinessInventory(other).article_references(owner),
                         dict(items=[], has_more=False, next_after=None))
        self.denied(401, BusinessInventory(other).article_references, self.owner)


if __name__ == '__main__':
    unittest.main()
