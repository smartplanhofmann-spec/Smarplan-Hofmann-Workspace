"""Independent consumer review: real CSV imports and domain actions, no DTO stubs."""
from copy import deepcopy
import unittest
import json
import uuid

from core import Problem, canonical
from business_documents import Documents, validate_integrity as documents_integrity
from business_inventory import BusinessInventory
from business_purchasing import Purchasing, validate_integrity as purchasing_integrity
import business_catalog_prices as prices
import test_business_catalog_price_consumers as consumers
import test_business_catalog_prices as fixtures


class CatalogIndependentReview(unittest.TestCase):
    def setUp(self):
        self.f = consumers.CatalogPriceConsumerTests('runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.office, self.actor, self.service = self.f.office, self.f.owner, self.f.service

    def rejected(self, function, *args, statuses=(400, 409), **kwargs):
        with self.assertRaises(Problem) as caught:
            function(*args, **kwargs)
        self.assertIn(caught.exception.status, statuses, caught.exception.message)

    def corrected(self, accepted, **changes):
        staged = self.f.stage(fixtures.raw(fixtures.row(**changes)))
        before = accepted['prices'][0]
        return self.f.accept(staged, self.f.choices(staged, {'nov': {'revision': before['revision'], 'sha256': before['sha256']}}))[0]

    def withdraw(self, accepted, index=0):
        p = accepted['prices'][index]
        return self.service.withdraw(self.actor, p['price_id'], fixtures.request(revision=p['revision'], sha256=p['sha256'], reason='Independent synthetic withdrawal', confirmation=True))

    def test_withdrawal_preserves_frozen_document_bytes_and_rejects_new_price_or_forged_position_identity(self):
        self.f.settings()
        accepted, _ = self.f.accept(self.f.stage())
        saved = self.f.draft(positions=[self.f.position(accepted)])
        issued = self.f.issue(saved)
        original = self.f.api.archive(self.actor, issued['id'], 'pdf')
        snapshot = issued['positions'][0]['catalog_price_snapshot']
        self.withdraw(accepted)
        self.assertEqual(prices.validate_snapshot(self.office, snapshot), snapshot)
        self.assertEqual(self.f.api.archive(self.actor, issued['id'], 'pdf'), original)
        self.assertEqual(self.f.api.get(self.actor, issued['id'])['positions'], issued['positions'])
        self.rejected(self.f.draft, positions=[self.f.position(accepted)])
        forged = dict(issued['positions'][0], id=uuid.uuid4().hex)
        self.rejected(self.f.draft, positions=[forged])
        prices.validate_integrity(self.office)
        documents_integrity(self.office)

    def test_rebinding_source_code_retires_old_selection_but_never_invalidates_original_snapshots(self):
        accepted, _ = self.f.accept(self.f.stage())
        saved = self.f.draft(positions=[self.f.position(accepted)])
        old_article = accepted['bindings'][0]['article_id']
        staged = self.f.stage(fixtures.raw(fixtures.row(price_id='dec', amount='12', start='2026-12-01', end='')))
        choices = self.f.choices(staged)
        choices['bindings']['SYN-PRICE'].update(action='create', article_id=None, article_revision=None, confirm_name_difference=False)
        replacement, _ = self.f.accept(staged, choices)
        self.assertNotEqual(old_article, replacement['bindings'][0]['article_id'])
        candidates = self.service.candidates(self.actor, dict(article_id=old_article, price_role='sales_net', effective_on='2026-11-10'))
        self.assertEqual([v['status'] for v in candidates['items']], ['retired_binding'])
        self.rejected(self.f.draft, positions=[self.f.position(accepted)])
        unchanged = self.f.api.update(self.actor, saved['id'], fixtures.request(revision=1, title='Independent original retained after rebind'))
        self.assertEqual(unchanged['positions'], saved['positions'])
        documents_integrity(self.office)

    def test_same_position_id_cannot_switch_to_foreign_article_or_erase_bound_identity(self):
        accepted, _ = self.f.accept(self.f.stage())
        document = self.f.draft(positions=[self.f.position(accepted)])
        original = document['positions'][0]
        foreign = self.f.api.save_article(self.actor, fixtures.request(name='Independent undated article', unit='ST', kind='material', unit_price_net='0', tax_rate='19'))
        for mode in ('foreign_article', 'no_article', 'no_proof', 'forged_id'):
            with self.subTest(mode=mode):
                altered = deepcopy(original)
                if mode == 'foreign_article':
                    altered.update(article_id=foreign['id'], article_revision=foreign['revision']);altered.pop('catalog_price_snapshot')
                elif mode == 'no_article':
                    for k in ('article_id', 'article_revision', 'catalog_price_snapshot'):altered.pop(k)
                elif mode == 'no_proof':altered.pop('catalog_price_snapshot')
                else:altered['id'] = uuid.uuid4().hex
                altered['unit_price_net'] = '0'
                self.rejected(self.f.api.update, self.actor, document['id'], fixtures.request(revision=1, positions=[altered]))
                self.assertEqual(self.f.api.get(self.actor, document['id'])['positions'], document['positions'])

    def test_rehashed_snapshot_date_is_bound_to_existing_position_not_just_valid_price_window(self):
        accepted, _ = self.f.accept(self.f.stage())
        document = self.f.draft(positions=[self.f.position(accepted)])
        changed = deepcopy(document['positions'][0])
        proof = changed['catalog_price_snapshot']
        proof['effective_on'] = '2026-11-11'
        proof['snapshot_sha256'] = prices.sha({k:v for k,v in proof.items() if k != 'snapshot_sha256'})
        # It is a valid historical fact at that different day, but not the
        # originally accepted position choice. New explicit selection is needed.
        prices.validate_snapshot(self.office, proof)
        self.rejected(self.f.api.update, self.actor, document['id'], fixtures.request(revision=1, positions=[changed]))
        changed['catalog_price_selection'] = self.f.selection(accepted, day='2026-11-11')
        current = self.f.api.update(self.actor, document['id'], fixtures.request(revision=1, positions=[changed]))
        self.assertEqual(current['positions'][0]['catalog_price_snapshot']['effective_on'], '2026-11-11')
        self.assertNotEqual(current['positions'][0]['catalog_price_snapshot']['snapshot_sha256'], document['positions'][0]['catalog_price_snapshot']['snapshot_sha256'])

    def test_each_source_role_has_exact_calendar_boundaries_without_cross_role_fallback(self):
        accepted, _ = self.f.accept(self.f.stage(fixtures.raw(
            fixtures.row(price_id='sales-feb', amount='1', start='2024-02-29', end='2024-02-29'),
            fixtures.row(price_id='purchase-feb', role='purchase_net', amount='2', start='2024-02-28', end='2024-03-01'))))
        article = accepted['bindings'][0]['article_id']
        for day, status in [('2024-02-28','not_yet_valid'),('2024-02-29','eligible'),('2024-03-01','expired')]:
            candidates = self.service.candidates(self.actor, dict(article_id=article, price_role='sales_net', effective_on=day))
            self.assertEqual([i['status'] for i in candidates['items']], [status])
        purchase = next(p for p in accepted['prices'] if self.service.price_history(self.actor,p['price_id'])['items'][0]['price']['price_role']=='purchase_net')
        selection = dict(price_id=purchase['price_id'],price_revision=purchase['revision'],price_sha256=purchase['sha256'],effective_on='2024-02-29')
        self.rejected(prices.resolve_selection,self.office,self.actor,article,selection,'sales_net')
        self.assertEqual(prices.resolve_selection(self.office,self.actor,article,selection,'purchase_net')['price']['price_net'],'2')

    def test_confirmed_purchase_and_actual_receiving_cost_survive_source_withdrawal_without_repricing_stock(self):
        accepted, _ = self.f.accept(self.f.stage(fixtures.raw(fixtures.row(role='purchase_net',amount='1',basis='3'))))
        article = accepted['bindings'][0]['article_id']; inventory = BusinessInventory(self.office); purchasing = Purchasing(self.office)
        location = inventory.save_location(self.actor, fixtures.request(name='Independent original stock'))
        order = inventory.save_order(self.actor, fixtures.request(project_id=self.f.project, supplier_name='Independent synthetic supplier',status='approved',items=[dict(article_id=article,quantity='3',catalog_price_selection=self.f.selection(accepted))]))
        confirmation = fixtures.request(source_revision=1,expected_receipt_revision=0,order_reference='INDEPENDENT-ORDER',ordered_on='2026-11-10',confirmation=True)
        purchasing.confirm(self.actor,order['id'],confirmation)
        before=self.office.db.execute('SELECT source_json,source_sha256 FROM business_purchase_confirmations WHERE order_id=?',(order['id'],)).fetchone()
        self.withdraw(accepted)
        actual=purchasing.receive(self.actor,order['id'],fixtures.request(source_revision=1,expected_receipt_revision=0,receipt_reference='INDEPENDENT-RECEIPT',received_on='2026-11-11',location_id=location['id'],lines=[dict(line_index=0,quantity='3',unit_cost_net='0.4000')]))
        self.assertEqual(actual['lines'][0]['cost_net'],'1.2000')
        self.assertEqual(inventory.balance(self.actor,location['id'],article)['stock_value_net'],'1.20')
        self.assertEqual(tuple(self.office.db.execute('SELECT source_json,source_sha256 FROM business_purchase_confirmations WHERE order_id=?',(order['id'],)).fetchone()),tuple(before))
        self.assertEqual(purchasing.confirm(self.actor,order['id'],confirmation)['status'],'ordered')
        self.assertEqual(purchasing.get(self.actor,order['id'])['status'],'received')
        purchasing_integrity(self.office)
        prices.validate_integrity(self.office)

    def test_stale_calculation_or_foreign_role_cannot_create_service_but_old_service_keeps_its_source(self):
        accepted,_=self.f.accept(self.f.stage(fixtures.raw(fixtures.row(role='purchase_net',amount='1',basis='3'))))
        article=self.f.article(accepted)
        source=dict(article_id=article['id'],article_revision=1,quantity='3',price_selection=self.f.selection(accepted))
        preview=self.f.api.pricing_preview(self.actor,dict(components=[source]))
        service=self.f.api.save_article(self.actor,fixtures.request(name='Independent priced service',pricing=preview['inputs'],pricing_hash=preview['preview_hash'],price_confirmation=True))
        self.withdraw(accepted)
        self.rejected(self.f.api.save_article,self.actor,fixtures.request(name='Stale newly minted service',pricing=preview['inputs'],pricing_hash=preview['preview_hash'],price_confirmation=True))
        kept=self.f.api.save_article(self.actor,fixtures.request(revision=1,name='Historical service remains'),service['id'])
        self.assertEqual(kept['components'],service['components']);self.assertEqual(kept['pricing_snapshot'],service['pricing_snapshot'])
        documents_integrity(self.office)

    def test_copying_old_component_twice_cannot_mint_an_additional_withdrawn_price_use(self):
        accepted,_=self.f.accept(self.f.stage(fixtures.raw(fixtures.row(role='purchase_net',amount='1',basis='3'))))
        article=self.f.article(accepted)
        preview=self.f.api.pricing_preview(self.actor,dict(components=[dict(article_id=article['id'],article_revision=1,quantity='3',price_selection=self.f.selection(accepted))]))
        service=self.f.api.save_article(self.actor,fixtures.request(name='Independent single original component',pricing=preview['inputs'],pricing_hash=preview['preview_hash'],price_confirmation=True))
        self.withdraw(accepted)
        # One old accepted occurrence is retainable. A second occurrence is a
        # new position and cannot silently mint a withdrawn purchase source.
        kept=self.f.api.save_article(self.actor,fixtures.request(revision=1,name='Unchanged historical component'),service['id'])
        self.assertEqual(kept['components'],service['components'])
        self.rejected(self.f.api.save_article,self.actor,fixtures.request(revision=2,components=service['components']+deepcopy(service['components'])),service['id'])
        self.assertEqual(self.f.api.catalog_item(self.actor,'business_articles',service['id'])['components'],service['components'])

    def test_two_explicitly_accepted_original_occurrences_both_survive_withdrawal(self):
        accepted,_=self.f.accept(self.f.stage(fixtures.raw(fixtures.row(role='purchase_net',amount='1',basis='3'))))
        article=self.f.article(accepted)
        chosen=dict(article_id=article['id'],article_revision=1,quantity='3',price_selection=self.f.selection(accepted))
        preview=self.f.api.pricing_preview(self.actor,dict(components=[chosen,deepcopy(chosen)]))
        self.assertEqual(preview['breakdown']['component_cost_net'],'2.00')
        service=self.f.api.save_article(self.actor,fixtures.request(name='Two explicitly accepted original occurrences',pricing=preview['inputs'],pricing_hash=preview['preview_hash'],price_confirmation=True))
        self.withdraw(accepted)
        kept=self.f.api.save_article(self.actor,fixtures.request(revision=1,name='Both original occurrences retained'),service['id'])
        self.assertEqual(len(kept['components']),2)
        self.assertEqual(kept['components'],service['components'])
        documents_integrity(self.office)

    def test_restore_rejects_nonexistent_article_revision_in_old_component_even_with_new_hash_and_restored_guards(self):
        accepted,_=self.f.accept(self.f.stage(fixtures.raw(fixtures.row(role='purchase_net',amount='1',basis='3'))))
        article=self.f.article(accepted)
        checked=self.f.api.pricing_preview(self.actor,dict(components=[dict(article_id=article['id'],article_revision=1,quantity='3',price_selection=self.f.selection(accepted))]))
        service=self.f.api.save_article(self.actor,fixtures.request(name='Original source revision',pricing=checked['inputs'],pricing_hash=checked['preview_hash'],price_confirmation=True))
        self.f.api.save_article(self.actor,fixtures.request(revision=1,name='Current unchanged source revision'),service['id'])
        documents_integrity(self.office)
        old=self.office.db.execute('SELECT payload_json FROM business_article_versions WHERE article_id=? AND revision=1',(service['id'],)).fetchone()[0]
        value=json.loads(old);value['components'][0]['article_revision']=999
        # Restore SQL guards before validation so a missing trigger cannot make
        # a semantic regression test pass for the wrong reason.
        triggers=list(self.office.db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name='business_article_versions'"))
        for trigger in triggers:self.office.db.execute('DROP TRIGGER '+trigger['name'])
        from business_documents import _hash
        changed=canonical(value)
        self.office.db.execute('UPDATE business_article_versions SET payload_json=?,payload_sha256=? WHERE article_id=? AND revision=1',(changed,_hash(changed),service['id']))
        for trigger in triggers:self.office.db.execute(trigger['sql'])
        with self.assertRaises(ValueError):documents_integrity(self.office)

    def test_restore_rejects_nonexistent_article_revision_in_historical_document_position_with_restored_guards(self):
        accepted,_=self.f.accept(self.f.stage())
        document=self.f.draft(positions=[self.f.position(accepted)])
        self.f.api.update(self.actor,document['id'],fixtures.request(revision=1,title='Current accepted document'))
        old=self.office.db.execute('SELECT payload_json FROM business_document_versions WHERE document_id=? AND revision=1',(document['id'],)).fetchone()[0]
        value=json.loads(old);value['positions'][0]['article_revision']=999
        triggers=list(self.office.db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name='business_document_versions'"))
        for trigger in triggers:self.office.db.execute('DROP TRIGGER '+trigger['name'])
        from business_documents import _hash
        changed=canonical(value)
        self.office.db.execute('UPDATE business_document_versions SET payload_json=?,payload_sha256=? WHERE document_id=? AND revision=1',(changed,_hash(changed),document['id']))
        for trigger in triggers:self.office.db.execute(trigger['sql'])
        with self.assertRaises(ValueError):documents_integrity(self.office)

    def test_multi_position_crm_adoption_is_atomic_if_second_selected_source_was_withdrawn(self):
        f=consumers.CatalogPriceSalesConsumerTests('runTest');f.setUp();self.addCleanup(f.doCleanups)
        accepted,_=f.accept(f.stage(fixtures.raw(fixtures.row(price_id='first',code='FIRST'),fixtures.row(price_id='second',code='SECOND'))))
        opportunity=f.save();f.api.adoption(f.owner,opportunity['id'],'project',f.adopt_body(opportunity))
        selected=[]
        for fact in accepted['prices']:
            history=f.service.price_history(f.owner,fact['price_id']);article=history['items'][0]['price']['article_id']
            selected.append(dict(article_id=article,article_revision=1,quantity='1',catalog_price_selection=dict(price_id=fact['price_id'],price_revision=fact['revision'],price_sha256=fact['sha256'],effective_on='2026-11-10')))
        fact=accepted['prices'][1];f.service.withdraw(f.owner,fact['price_id'],fixtures.request(revision=fact['revision'],sha256=fact['sha256'],reason='Independent second-source withdrawal',confirmation=True))
        self.rejected(f.api.adoption,f.owner,opportunity['id'],'offer',f.adopt_body(opportunity,'offer',positions=selected))
        self.assertEqual(f.office.db.execute('SELECT COUNT(*) FROM business_documents').fetchone()[0],0)
        self.assertEqual(f.office.db.execute("SELECT COUNT(*) FROM business_sales_adoptions WHERE kind='offer'").fetchone()[0],0)

if __name__=='__main__':unittest.main()
