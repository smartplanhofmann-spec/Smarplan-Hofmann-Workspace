"""Real dated source -> approved order -> receipt, without supplier contacts."""
import json
import unittest

from business_documents import Documents
from business_inventory import BusinessInventory
from business_purchasing import Purchasing, validate_integrity
from test_business_catalog_prices import request, raw, row
import test_business_catalog_prices as fixture_module
import business_catalog_prices as prices


class DatedCatalogPurchasingTests(unittest.TestCase):
    def setUp(self):
        fixture = self.fixture = fixture_module.CatalogPricesTests()
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        self.office,self.owner,self.project = fixture.office,fixture.owner,fixture.project
        self.inventory,self.purchasing = BusinessInventory(self.office),Purchasing(self.office)
        self.location = self.inventory.save_location(self.owner,request(name='Synthetic dated receiving'))
        self.accepted,_=fixture.accept(fixture.stage(raw(row(role='purchase_net',amount='1',basis='3'))))
        self.article_id=self.accepted['bindings'][0]['article_id']
        self.selection=fixture.selection(self.accepted)

    def order(self, **line):
        return self.inventory.save_order(self.owner,request(project_id=self.project,supplier_name='Synthetic supplier',status='approved',
            items=[dict(article_id=self.article_id,quantity='3',**line)]))

    def confirmation(self,order,day='2026-11-04'):
        return request(source_revision=order['revision'],expected_receipt_revision=0,order_reference='SYN-DATED-1',ordered_on=day,confirmation=True)

    def test_order_rejects_technical_zero_and_wrong_role_then_freezes_exact_ratio(self):
        self.fixture.problem(409,self.order)
        order=self.order(catalog_price_selection=self.selection)
        snapshot=order['items'][0]['catalog_price_snapshot']
        self.assertEqual((snapshot['price']['price_net'],snapshot['price']['price_base_quantity']),('1','3'))
        self.assertEqual(order['items'][0]['article_snapshot']['unit_price_net'],'0')
        self.fixture.problem(409,self.purchasing.confirm,self.owner,order['id'],self.confirmation(order,'2026-12-01'))
        confirmed=self.purchasing.confirm(self.owner,order['id'],self.confirmation(order))
        self.assertEqual(confirmed['status'],'ordered')
        self.assertEqual(self.purchasing.get(self.owner,order['id'])['status'],'ordered')
        prices.validate_integrity(self.office)
        validate_integrity(self.office)

    def test_corrected_current_price_blocks_unconfirmed_order_but_preserves_confirmed_original(self):
        order=self.order(catalog_price_selection=self.selection)
        pending=self.order(catalog_price_selection=self.selection)
        body=self.confirmation(order)
        self.purchasing.confirm(self.owner,order['id'],body)
        frozen=self.office.db.execute('SELECT source_json FROM business_purchase_confirmations WHERE order_id=?',(order['id'],)).fetchone()[0]
        staged=self.fixture.stage(raw(row(role='purchase_net',amount='2',basis='3')))
        self.fixture.accept(staged,self.fixture.choices(staged,{'nov':dict(revision=1,sha256=self.selection['price_sha256'])}))
        self.fixture.problem(409,self.purchasing.confirm,self.owner,pending['id'],self.confirmation(pending))
        self.assertEqual(self.purchasing.confirm(self.owner,order['id'],body)['status'],'ordered')
        self.assertEqual(self.office.db.execute('SELECT source_json FROM business_purchase_confirmations WHERE order_id=?',(order['id'],)).fetchone()[0],frozen)
        self.assertEqual(self.purchasing.get(self.owner,order['id'])['status'],'ordered')
        validate_integrity(self.office)

    def test_receiving_requires_actual_cost_even_when_legacy_current_article_has_nonzero_cost(self):
        Documents(self.office).save_article(self.owner,request(revision=1,cost_price_net='99'),self.article_id)
        args=dict(kind='receive',article_id=self.article_id,to_location_id=self.location['id'],quantity='3')
        self.fixture.problem(409,self.inventory.move,self.owner,request(**args))
        moved=self.inventory.move(self.owner,request(**args,unit_cost_net='0'))
        self.assertEqual(moved['cost_net'],'0.0000')
        order=self.order(catalog_price_selection=self.selection)
        self.purchasing.confirm(self.owner,order['id'],self.confirmation(order))
        received=self.purchasing.receive(self.owner,order['id'],request(source_revision=order['revision'],expected_receipt_revision=0,
            receipt_reference='SYN-RECEIPT',received_on='2026-11-04',location_id=self.location['id'],
            lines=[dict(line_index=0,quantity='3',unit_cost_net='0.40')]))
        self.assertEqual(received['lines'][0]['cost_net'],'1.2000')
        self.assertEqual(received['lines'][0]['unit_cost_net'],'0.4000')
        validate_integrity(self.office)

    def test_unconfirmed_dated_order_requires_its_actual_original_article_version_on_read_and_restore(self):
        from copy import deepcopy
        from core import canonical,Problem
        order=self.order(catalog_price_selection=self.selection)
        original=order['items']
        for field,value in [('revision',999),('name','Rewritten original name'),('cost_price_net','99')]:
            with self.subTest(field=field):
                items=deepcopy(original);items[0]['article_snapshot'][field]=value
                self.office.db.execute('UPDATE business_purchase_orders SET payload_json=? WHERE id=?',(canonical(items),order['id']))
                with self.assertRaises(Problem):self.purchasing.get(self.owner,order['id'])
                with self.assertRaises(ValueError):validate_integrity(self.office)
                self.office.db.execute('UPDATE business_purchase_orders SET payload_json=? WHERE id=?',(canonical(original),order['id']))
        validate_integrity(self.office)

    def test_original_order_article_survives_later_name_and_cost_changes_without_head_requirement(self):
        order=self.order(catalog_price_selection=self.selection)
        original=order['items'][0]['article_snapshot']
        Documents(self.office).save_article(self.owner,request(revision=1,name='Changed current name',cost_price_net='99'),self.article_id)
        read=self.purchasing.get(self.owner,order['id'])
        self.assertEqual(read['items'][0]['article_name'],original['name'])
        self.assertEqual(read['items'][0]['catalog_price_snapshot'],order['items'][0]['catalog_price_snapshot'])
        validate_integrity(self.office)


if __name__=='__main__':
    unittest.main()
