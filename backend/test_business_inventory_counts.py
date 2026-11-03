"""Physical inventory against the actual stock/valuation ledger, using synthetic data."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json
from pathlib import Path
import threading
import unittest

from core import Office, Problem
import test_business_inventory as fixture
from business_inventory import BusinessInventory, validate_integrity as validate_stock
from business_inventory_counts import InventoryCounts, schema_statements, guard_statements, validate_integrity


class InventoryCountTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.InventoryTests('test_fractional_weighted_cost_rounding_does_not_leave_value_without_stock')
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        for key in ('office','owner','tech','project','location','article','api','req','receive','inventory_grant','error'):
            setattr(self,key,getattr(self.fixture,key))
        for statement in schema_statements('BLOB')+guard_statements('sqlite'):
            self.office.db.execute(statement)
        self.office.db.commit()
        self.counts=InventoryCounts(self.office)

    def opened(self,**changes):
        body=dict(location_id=self.location['id'],article_ids=[self.article['id']],title='Jahreszählung',
            counted_on='2026-11-03',correction_of=None,reason='Physischer Bestand geprüft')
        return self.counts.command(self.owner,'open',self.req(**{**body,**changes}))

    def counted(self,quantity,opened=None):
        opened=opened or self.opened()
        return self.counts.command(self.owner,'count',self.req(revision=opened['revision'],
            lines=[dict(article_id=self.article['id'],quantity=quantity,reason='Tatsächlich gezählt')]),opened['id'])

    def approve(self,counted,prices=None,actor=None):
        return self.counts.command(actor or self.owner,'approve',self.req(revision=counted['revision'],
            confirmed=True,zero_stock_unit_costs=prices or {}),counted['id'])

    def balance(self):
        return self.api.balance(self.owner,self.location['id'],self.article['id'])

    def test_shrinkage_is_count_adjustment_not_project_cost_and_later_issue_uses_weighted_cost(self):
        self.receive('10','1'); self.receive('10','3')
        counted=self.counted('15')
        preview=self.counts.preview(self.owner,counted['id'],dict(revision=2,zero_stock_unit_costs={}))
        self.assertEqual(preview['items'][0]['value_delta_net'],'-10.0000')
        result=self.approve(counted)
        self.assertEqual(result['status'],'approved')
        self.assertEqual((self.balance()['on_hand'],self.balance()['stock_value_net']),('15.0000','30.00'))
        self.assertEqual(self.api.cost_report(self.owner,self.project)['material_actual_net'],'0.00')
        issue=self.api.move(self.owner,self.req(kind='issue',article_id=self.article['id'],
            from_location_id=self.location['id'],project_id=self.project,quantity='5'))
        self.assertEqual(issue['cost_net'],'10.0000')
        self.assertTrue(validate_stock(self.office)); self.assertTrue(validate_integrity(self.office))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_stock_movements').fetchone()[0],3)

    def test_positive_new_stock_needs_explicit_cost_and_can_be_issued_after_restart(self):
        counted=self.counted('3')
        self.error(400,self.approve,counted)
        result=self.approve(counted,{self.article['id']:'2.3333'})
        second=Office(Path(self.fixture.temp.name)/'office.db'); self.addCleanup(second.db.close)
        api=BusinessInventory(second)
        self.assertEqual(InventoryCounts(second).get(self.owner,result['id'])['status'],'approved')
        move=api.move(self.owner,self.req(kind='issue',article_id=self.article['id'],from_location_id=self.location['id'],project_id=self.project,quantity='3'))
        self.assertEqual(move['cost_net'],'6.9999')
        self.assertEqual(api._stock(self.location['id'],self.article['id'])[:2],(Decimal(0),Decimal(0)))
        self.assertTrue(validate_stock(second)); self.assertTrue(validate_integrity(second))

    def test_zero_count_consumes_exact_remaining_value_and_correction_is_new_history(self):
        self.receive('3','0.3333')
        first=self.approve(self.counted('0'))
        self.assertEqual(first['items'][0]['adjustment_value_net'],'-0.9999')
        self.assertEqual(self.balance()['stock_value_net'],'0.00')
        correction=self.opened(correction_of=first['id'],reason='Weitere Einheit bei Nachzählung gefunden')
        second=self.approve(self.counted('1',correction),{self.article['id']:'0.3333'})
        self.assertEqual(second['correction_of'],first['id'])
        self.assertEqual(self.counts.get(self.owner,first['id'])['items'][0]['counted_quantity'],'0.0000')
        self.assertTrue(validate_stock(self.office)); self.assertTrue(validate_integrity(self.office))

    def test_intervening_movement_even_with_same_net_balance_invalidates_snapshot(self):
        self.receive('10','1')
        counted=self.counted('9')
        issue=self.api.move(self.owner,self.req(kind='issue',article_id=self.article['id'],from_location_id=self.location['id'],project_id=self.project,quantity='1'))
        self.api.move(self.owner,self.req(kind='return',article_id=self.article['id'],to_location_id=self.location['id'],project_id=self.project,quantity='1',reversal_of=issue['id']))
        self.assertFalse(self.counts.get(self.owner,counted['id'])['basis_current'])
        self.error(409,self.approve,counted)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_inventory_adjustments').fetchone()[0],0)

    def test_reservation_change_and_count_below_existing_reservation_block_approval(self):
        self.receive('10','1')
        counted=self.counted('9')
        self.api.reserve(self.owner,self.project,self.req(article_id=self.article['id'],location_id=self.location['id'],quantity='8'))
        self.error(409,self.approve,counted)
        newer=self.counted('7')
        self.error(409,self.approve,newer)
        self.assertEqual(self.balance()['on_hand'],'10.0000')

    def test_price_revisions_after_open_require_recount_but_never_revalue_old_stock(self):
        self.receive('10','1')
        counted=self.counted('9')
        from business_documents import Documents
        Documents(self.office).save_article(self.owner,self.req(revision=self.article['revision'],cost_price_net='999'),self.article['id'])
        self.error(409,self.approve,counted)
        self.assertEqual(self.approve(self.counted('9'))['items'][0]['adjustment_value_net'],'-1.0000')

    def test_replay_exactly_once_is_historical_and_fresh_finance_permission_required(self):
        self.receive('10','1'); counted=self.counted('9')
        for permission in ('inventory.write','finance.read','finance.write','finance.approve'):
            self.inventory_grant(permission)
        body=self.req(revision=2,confirmed=True,zero_stock_unit_costs={})
        first=self.counts.command(self.tech,'approve',body,counted['id'])
        self.assertEqual(self.counts.command(self.tech,'approve',body,counted['id']),first)
        self.inventory_grant('finance.approve',effect='deny',revision=1)
        self.error(403,self.counts.command,self.tech,'approve',body,counted['id'])
        self.inventory_grant('finance.read',effect='deny',revision=1)
        read=self.counts.get(self.tech,counted['id'])
        self.assertFalse(read['financial_values_visible'])
        self.assertNotIn('value_net',read['items'][0]); self.assertNotIn('adjustment_value_net',read['items'][0])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_inventory_adjustments').fetchone()[0],1)

    def test_count_revision_history_is_immutable_and_cancel_has_no_stock_effect(self):
        self.receive('10','1'); counted=self.counted('9')
        newer=self.counted('8',counted)
        old=self.counts.get(self.owner,newer['id'],2)
        self.assertEqual(old['items'][0]['counted_quantity'],'9.0000')
        self.counts.command(self.owner,'cancel',self.req(revision=3,reason='Zähltag neu ansetzen'),newer['id'])
        self.assertEqual(self.balance()['on_hand'],'10.0000')
        self.error(409,self.approve,newer)
        with self.assertRaises(Exception):
            self.office.db.execute('DELETE FROM business_inventory_count_events')
        self.office.db.rollback()
        self.assertTrue(validate_integrity(self.office))

    def test_partial_or_duplicate_counts_and_unexpected_prices_are_rejected(self):
        self.receive('10','1'); opened=self.opened()
        for lines in ([],[dict(article_id=self.article['id'],quantity='9',reason='')],
                      [dict(article_id=self.article['id'],quantity='-1',reason='X')]):
            self.error(400,self.counts.command,self.owner,'count',self.req(revision=1,lines=lines),opened['id'])
        counted=self.counted('10',opened)
        self.error(400,self.approve,counted,{self.article['id']:'8'})
        self.assertEqual(self.approve(counted)['items'][0]['adjustment_value_net'],'0.0000')
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_inventory_adjustments').fetchone()[0],0)

    def test_competing_counts_cannot_apply_same_original_stock_twice(self):
        self.receive('10','1')
        first=self.counted('9'); second_count=self.counted('8')
        second_office=Office(Path(self.fixture.temp.name)/'office.db'); self.addCleanup(second_office.db.close)
        barrier=threading.Barrier(2)
        def approve_pair(pair):
            service,count=pair; barrier.wait()
            try:
                return service.command(self.owner,'approve',self.req(revision=2,confirmed=True,zero_stock_unit_costs={}),count['id'])['status']
            except Problem as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(approve_pair,[(self.counts,first),(InventoryCounts(second_office),second_count)]))
        self.assertCountEqual(outcomes,['approved',409])
        self.assertTrue(validate_stock(self.office)); self.assertTrue(validate_integrity(self.office))

    def test_adjustment_tampering_is_detected_even_without_runtime_guards(self):
        self.receive('10','1'); self.approve(self.counted('9'))
        self.office.db.execute('DROP TRIGGER business_inventory_adjustments_update_guard')
        self.office.db.execute("UPDATE business_inventory_adjustments SET value_delta_net='-99.0000'")
        with self.assertRaises(ValueError): validate_integrity(self.office)


if __name__=='__main__': unittest.main()
