"""A changed unit must never reinterpret existing stock or an approved order."""
from pathlib import Path
import tempfile
import unittest
import uuid

from core import Office, Problem
from business_documents import Documents
from business_inventory import BusinessInventory


class StockArticleIdentityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='synthetic-stock-identity-')
        self.addCleanup(temporary.cleanup)
        self.office = Office(Path(temporary.name) / 'office.db')
        self.addCleanup(self.office.db.close)
        self.owner = dict(id=self.office.add_user('owner@example.test', 'Synthetic-password-123', 'owner'), role='owner')
        self.documents, self.inventory = Documents(self.office), BusinessInventory(self.office)
        self.project = self.office.add_project(self.owner, 'Synthetic project', 'Synthetic customer')
        self.location = self.inventory.save_location(self.owner, self.request(name='Synthetic store'))
        self.article = self.documents.save_article(self.owner, self.request(code='SYN-M', name='Synthetic cable',
            kind='material', unit='m', unit_price_net='4.00', cost_price_net='2.00', tax_rate='19', active=True))

    def request(self, **values):
        return dict(request_id=uuid.uuid4().hex, **values)

    def reject_change(self, **values):
        version_count = self.office.db.execute('SELECT COUNT(*) FROM business_article_versions').fetchone()[0]
        with self.assertRaises(Problem) as caught:
            self.documents.save_article(self.owner, self.request(revision=self.article['revision'], **values), self.article['id'])
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_article_versions').fetchone()[0], version_count)

    def test_stock_unit_and_kind_stay_bound_even_after_stock_was_consumed(self):
        self.inventory.move(self.owner, self.request(kind='receive', article_id=self.article['id'],
            to_location_id=self.location['id'], quantity='5', unit_cost_net='2.00'))
        self.reject_change(unit='C62')
        self.reject_change(kind='service')
        issue = self.inventory.move(self.owner, self.request(kind='issue', article_id=self.article['id'],
            from_location_id=self.location['id'], project_id=self.project, quantity='5'))
        self.assertEqual(issue['cost_net'], '10.0000')
        self.reject_change(unit='C62')
        self.assertEqual(self.inventory.balance(self.owner, self.location['id'], self.article['id'])['unit'], 'm')

    def test_prices_names_and_deactivation_do_not_revalue_stock(self):
        self.inventory.move(self.owner, self.request(kind='receive', article_id=self.article['id'],
            to_location_id=self.location['id'], quantity='5', unit_cost_net='2.00'))
        updated = self.documents.save_article(self.owner, self.request(revision=self.article['revision'],
            name='Synthetic new label', cost_price_net='9.00', unit_price_net='12.00', active=False), self.article['id'])
        self.assertEqual(updated['name'], 'Synthetic new label')
        balance = self.inventory.balance(self.owner, self.location['id'], self.article['id'])
        self.assertEqual((balance['on_hand'], balance['stock_value_net'], balance['unit']), ('5.0000', '10.00', 'm'))

    def test_approved_order_binds_unit_before_first_receipt(self):
        self.inventory.save_order(self.owner, self.request(project_id=self.project, supplier_name='Synthetic supplier',
            status='approved', items=[dict(article_id=self.article['id'], quantity='10')]))
        self.reject_change(unit='C62')
        self.reject_change(kind='machine')

    def test_unbound_article_and_draft_order_allow_correction_before_approval(self):
        self.inventory.save_order(self.owner, self.request(project_id=self.project, supplier_name='Synthetic supplier',
            status='draft', items=[dict(article_id=self.article['id'], quantity='10')]))
        changed = self.documents.save_article(self.owner, self.request(revision=self.article['revision'],
            unit='C62'), self.article['id'])
        self.assertEqual(changed['unit'], 'C62')
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_stock_movements').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
