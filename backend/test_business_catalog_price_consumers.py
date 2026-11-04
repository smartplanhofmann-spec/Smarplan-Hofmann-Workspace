"""Dated price consumers use real originals and immutable historical snapshots."""
from copy import deepcopy
from datetime import datetime, timezone
import unittest
import json
import uuid
from unittest.mock import patch
from core import Problem
from business_documents import Documents, validate_integrity
from business_tests.test_documents import DocumentsFixture
import business_catalog_prices as prices
import test_business_catalog_prices as domain
import test_business_sales as legacy_sales


class CatalogPriceConsumerTests(DocumentsFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        for sql in prices.schema_statements('BLOB')+prices.guard_statements('sqlite'):self.office.db.execute(sql)
        self.service=prices.CatalogPrices(self.office,clock=lambda:datetime(2026,11,4,tzinfo=timezone.utc))
        self.source=self.service.create_source(self.owner,domain.request(name='Synthetic consumer source',reference='SYN-CONSUMER-V2'));self.sequence=0

    stage = domain.CatalogPricesTests.stage
    choices = domain.CatalogPricesTests.choices
    accept = domain.CatalogPricesTests.accept

    def problem(self, status, fn, *args, **kwargs):
        with self.assertRaises(Problem) as caught:
            fn(*args, **kwargs)
        self.assertEqual(caught.exception.status, status, caught.exception.message)

    def selection(self, accepted, index=0, day='2026-11-10'):
        fact = accepted['prices'][index]
        return dict(price_id=fact['price_id'], price_revision=fact['revision'], price_sha256=fact['sha256'], effective_on=day)

    def article(self, accepted):
        return self.api.catalog_item(self.owner, 'business_articles', accepted['bindings'][0]['article_id'])

    def position(self, accepted, index=0, day='2026-11-10', **changes):
        article = self.article(accepted)
        return dict(article_id=article['id'], article_revision=article['revision'], quantity='3',
                    catalog_price_selection=self.selection(accepted, index, day), **changes)

    def test_managed_price_requires_selection_even_with_forged_position_id_or_manual_placeholder(self):
        accepted, _ = self.accept(self.stage()); article = self.article(accepted)
        for extra in ({}, {'id':uuid.uuid4().hex}, {'unit_price_net':'99','description':'Copied fallback'}):
            self.problem(409, self.draft, positions=[dict(article_id=article['id'], article_revision=1, quantity='3', **extra)])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_documents').fetchone()[0], 0)

    def test_explicit_november_december_and_historical_offer_survive_price_correction(self):
        november, _ = self.accept(self.stage()); old = self.draft(positions=[self.position(november)])
        december, _ = self.accept(self.stage(domain.raw(domain.row(price_id='dec',amount='12.00',start='2026-12-01',end=''))))
        fresh = self.draft(positions=[self.position(december,day='2026-12-01')])
        self.assertEqual((old['totals']['net'],fresh['totals']['net']), ('30.00','36.00'))
        self.problem(409,self.draft,positions=[self.position(december,day='2026-11-30')])
        self.problem(409,self.draft,positions=[self.position(november,day='2026-12-01')])
        staged=self.stage(domain.raw(domain.row(amount='11.00'))); prior=november['prices'][0]
        corrected,_=self.accept(staged,self.choices(staged,{'nov':{'revision':prior['revision'],'sha256':prior['sha256']}}))
        self.problem(409,self.draft,positions=[self.position(november)])
        self.assertEqual(self.draft(positions=[self.position(corrected)])['totals']['net'],'33.00')
        changed=self.api.update(self.owner,old['id'],domain.request(revision=1,title='Historical title only'))
        converted=self.api.convert(self.owner,old['id'],domain.request(revision=changed['revision'],target_kind='order_confirmation'))
        self.assertEqual(converted['positions'],old['positions']); self.assertEqual(converted['totals'],old['totals'])
        validate_integrity(self.office)

    def test_final_offer_archive_keeps_original_price_and_bytes_after_correction(self):
        self.settings()
        first,_=self.accept(self.stage())
        draft=self.draft(positions=[self.position(first)])
        issued=self.issue(draft)
        original_pdf=self.api.archive(self.owner,issued['id'],'pdf')
        original_digest=issued['payload_sha256']
        staged=self.stage(domain.raw(domain.row(amount='11')));prior=first['prices'][0]
        self.accept(staged,self.choices(staged,{'nov':{'revision':prior['revision'],'sha256':prior['sha256']}}))
        retained=self.api.get(self.owner,issued['id'])
        self.assertEqual(retained['payload_sha256'],original_digest)
        self.assertEqual(retained['positions'],issued['positions'])
        self.assertEqual(self.api.archive(self.owner,issued['id'],'pdf'),original_pdf)
        validate_integrity(self.office)

    def test_one_euro_per_three_units_and_explicit_tax_decision(self):
        accepted,_=self.accept(self.stage(domain.raw(domain.row(amount='1.00',basis='3'))))
        offer=self.draft(positions=[self.position(accepted,tax_rate='0',tax_category='AE',tax_exemption_reason='Synthetic explicit reverse-charge decision')])
        position=offer['positions'][0]
        self.assertEqual((position['unit_price_net'],position['price_base_quantity'],position['net']),('1.00','3','1.00'))
        self.assertEqual(position['catalog_price_snapshot']['price']['tax_rate'],'19')
        self.assertEqual((position['tax_rate'],position['tax_category'],offer['totals']['gross']),('0','AE','1.00'))
        self.assertNotIn('cost_price_net',position)
        self.assertFalse(self.api.document_calculation(self.owner,{'revision':1},offer['id'])['cost_summary']['complete'])
        validate_integrity(self.office)

    def test_bound_amount_basis_unit_and_snapshot_cannot_be_forged_or_removed(self):
        accepted,_=self.accept(self.stage())
        for change in ({'unit_price_net':'0'},{'price_base_quantity':'3'},{'unit':'PACK'}):
            self.problem(409,self.draft,positions=[self.position(accepted,**change)])
        offer=self.draft(positions=[self.position(accepted)]); old=offer['positions'][0]
        forged=dict(old,id=uuid.uuid4().hex); self.problem(409,self.draft,positions=[forged])
        for field,value in [('unit_price_net','99'),('price_base_quantity','3'),('unit','PACK')]:
            self.problem(409,self.api.update,self.owner,offer['id'],domain.request(revision=1,positions=[dict(old,**{field:value})]))
        without=dict(old);without.pop('catalog_price_snapshot')
        self.problem(409,self.api.update,self.owner,offer['id'],domain.request(revision=1,positions=[without]))
        self.assertEqual(self.api.get(self.owner,offer['id']),offer)

    def test_manual_article_cost_never_becomes_automatic_managed_position_cost(self):
        accepted,_=self.accept(self.stage()); article=self.article(accepted)
        self.api.save_article(self.owner,domain.request(revision=1,unit_price_net='99',cost_price_net='77'),article['id'])
        offer=self.draft(positions=[self.position(accepted)])
        self.assertEqual(offer['positions'][0]['unit_price_net'],'10.00');self.assertNotIn('cost_price_net',offer['positions'][0])
        explicit=self.draft(positions=[self.position(accepted,cost_price_net='2.50')])
        self.assertEqual(explicit['positions'][0]['cost_price_net'],'2.50')

    def test_readonly_preview_and_write_use_distinct_lock_policy(self):
        accepted,_=self.accept(self.stage());selected=self.position(accepted)
        with patch.object(prices,'resolve_selection',wraps=prices.resolve_selection) as resolve:
            self.api.document_calculation(self.owner,dict(project_id=self.project,positions=[selected]))
            self.assertIs(resolve.call_args.kwargs['lock'],False)
            self.draft(positions=[selected]);self.assertIs(resolve.call_args.kwargs['lock'],True)

    def test_bom_keeps_raw_price_basis_until_existing_cent_rounding_and_persists_proof(self):
        accepted,_=self.accept(self.stage(domain.raw(domain.row(role='purchase_net',amount='1.00',basis='3'))));article=self.article(accepted)
        component=dict(article_id=article['id'],article_revision=1,quantity='3')
        self.problem(409,self.api.pricing_preview,self.owner,dict(components=[component]))
        value=self.api.pricing_preview(self.owner,dict(components=[dict(component,price_selection=self.selection(accepted))]))
        self.assertEqual((value['components'][0]['cost_price_net'],value['components'][0]['cost_price_base_quantity']),('1.00','3'))
        self.assertEqual((value['breakdown']['component_cost_net'],value['unit_cost_net']),('1.00','1.00'))
        position=dict(description='Bound synthetic calculation',quantity='1',pricing=value['inputs'],pricing_hash=value['preview_hash'],price_confirmation=True)
        with patch.object(prices,'resolve_selection',wraps=prices.resolve_selection) as resolve:
            offer=self.draft(positions=[position]);self.assertIs(resolve.call_args.kwargs['lock'],True)
        self.assertEqual(offer['positions'][0]['pricing_snapshot'],value);validate_integrity(self.office)

    def test_source_selection_sets_base_cost_and_conflicts_without_changing_v1(self):
        accepted,_=self.accept(self.stage(domain.raw(domain.row(role='purchase_net',amount='1.00',basis='3'))));article=self.article(accepted)
        source=dict(source_article_id=article['id'],source_article_revision=1)
        self.problem(409,self.api.pricing_preview,self.owner,source)
        data=dict(source,source_price_selection=self.selection(accepted));value=self.api.pricing_preview(self.owner,data)
        self.assertEqual((value['inputs']['base_cost_net'],value['unit_cost_net']),('0.33','0.33'))
        self.assertEqual(self.api.pricing_preview(self.owner,value['inputs']),value)
        self.problem(409,self.api.pricing_preview,self.owner,dict(data,base_cost_net='0'))
        self.problem(400,self.api.pricing_preview,self.owner,dict(source_price_selection=self.selection(accepted)))
        legacy=self.api.save_article(self.owner,domain.request(name='Undated V1',kind='material',unit='ST',unit_price_net='7',cost_price_net='4',tax_rate='19'))
        result=self.api.pricing_preview(self.owner,dict(source_article_id=legacy['id'],source_article_revision=1,base_cost_net='9'))
        self.assertEqual(result['unit_cost_net'],'9.00')

    def test_calculated_service_components_require_and_preserve_full_cost_source(self):
        accepted,_=self.accept(self.stage(domain.raw(domain.row(role='purchase_net',amount='1.00',basis='3'))));article=self.article(accepted)
        component=dict(article_id=article['id'],article_revision=1,quantity='3')
        self.problem(409,self.api.save_article,self.owner,domain.request(name='Unbound service',kind='service',unit='ST',unit_price_net='2',components=[component]))
        checked=self.api.pricing_preview(self.owner,dict(components=[dict(component,price_selection=self.selection(accepted))]))
        service=self.api.save_article(self.owner,domain.request(name='Bound service',pricing=checked['inputs'],pricing_hash=checked['preview_hash'],price_confirmation=True))
        self.assertEqual((service['components'][0]['cost_price_net'],service['components'][0]['cost_price_base_quantity'],service['components'][0]['cost_net']),('1.00','3','1.00'))
        self.assertEqual(service['components'][0]['catalog_price_snapshot'],checked['components'][0]['catalog_price_snapshot'])
        changed=self.api.save_article(self.owner,domain.request(revision=1,name='Renamed service'),service['id'])
        self.assertEqual(changed['components'],service['components'])

    def test_dated_calculation_provenance_rejects_rehashed_forged_inputs_or_article_facts(self):
        accepted,_=self.accept(self.stage(domain.raw(domain.row(role='purchase_net',amount='1',basis='3'))));article=self.article(accepted)
        checked=self.api.pricing_preview(self.owner,dict(components=[dict(article_id=article['id'],article_revision=1,quantity='3',price_selection=self.selection(accepted))]))
        from business_documents import _hash
        from core import canonical
        from business_pricing import validate_catalog_sources
        for field in ('article','date','quantity','missing'):
            proof=deepcopy(checked)
            if field=='article':proof['source_articles'][0]['revision']=999
            if field=='date':proof['inputs']['components'][0]['price_selection']['effective_on']='2026-11-11'
            if field=='quantity':proof['components'][0]['quantity']='9'
            if field=='missing':proof['source_articles'][0].pop('catalog_price_snapshot')
            proof['preview_hash']=_hash(canonical({key:value for key,value in proof.items() if key!='preview_hash'}))
            self.problem(409,validate_catalog_sources,self.office,proof)

    def test_templates_cannot_reuse_managed_prices_as_undated_releases(self):
        accepted,_=self.accept(self.stage());offer=self.draft(positions=[self.position(accepted)])
        self.problem(409,self.api.save_template,self.owner,domain.request(name='Unsafe dated template',kind='offer',title='Synthetic',positions=offer['positions']))


    def test_explicit_zero_is_valid_but_wrong_roles_and_null_selections_are_rejected(self):
        accepted,_=self.accept(self.stage(domain.raw(domain.row(price_id='sale',amount='0'),domain.row(price_id='buy',role='purchase_net',amount='0'))))
        self.assertEqual(self.draft(positions=[self.position(accepted)])['totals']['net'],'0.00')
        self.problem(409,self.draft,positions=[self.position(accepted,index=1)])
        article=self.article(accepted)
        source=dict(source_article_id=article['id'],source_article_revision=1)
        self.problem(409,self.api.pricing_preview,self.owner,dict(source,source_price_selection=self.selection(accepted)))
        value=self.api.pricing_preview(self.owner,dict(source,source_price_selection=self.selection(accepted,index=1)))
        self.assertEqual(value['unit_cost_net'],'0.00')
        for malformed in (None,[],{},''):
            expected=400
            self.problem(expected,self.api.pricing_preview,self.owner,dict(source,source_price_selection=malformed))
            self.problem(expected,self.draft,positions=[dict(article_id=article['id'],article_revision=1,quantity='1',catalog_price_selection=malformed)])

    def test_saved_component_fact_survives_live_article_revision_and_price_correction(self):
        accepted,_=self.accept(self.stage(domain.raw(domain.row(role='purchase_net',amount='1.00',basis='3'))));article=self.article(accepted)
        component=dict(article_id=article['id'],article_revision=1,quantity='3',price_selection=self.selection(accepted))
        checked=self.api.pricing_preview(self.owner,dict(components=[component]))
        service=self.api.save_article(self.owner,domain.request(name='Bound service',pricing=checked['inputs'],pricing_hash=checked['preview_hash'],price_confirmation=True))
        self.api.save_article(self.owner,domain.request(revision=1,name='Changed source article'),article['id'])
        staged=self.stage(domain.raw(domain.row(role='purchase_net',amount='2.00',basis='3')));prior=accepted['prices'][0]
        decisions=self.choices(staged,{'nov':{'revision':prior['revision'],'sha256':prior['sha256']}})
        decisions['bindings']['SYN-PRICE']['confirm_name_difference']=True
        self.accept(staged,decisions)
        changed=self.api.save_article(self.owner,domain.request(revision=1,name='Rename only'),service['id'])
        self.assertEqual(changed['components'],service['components'])
        self.assertEqual(changed['pricing_snapshot'],service['pricing_snapshot'])
        validate_integrity(self.office)

    def test_old_undated_offer_survives_later_article_management_but_cannot_mint_new_price(self):
        article=self.api.save_article(self.owner,domain.request(code='SYN-PRICE',name='Synthetic dated item',kind='material',unit='ST',unit_price_net='7',cost_price_net='4',tax_rate='19'))
        old=self.draft(positions=[dict(article_id=article['id'],article_revision=1,quantity='2')])
        staged=self.stage();decisions=self.choices(staged)
        decisions['bindings']['SYN-PRICE'].update(action='bind',article_id=article['id'],article_revision=1)
        self.accept(staged,decisions)
        changed=self.api.update(self.owner,old['id'],domain.request(revision=1,title='Preserved undated offer'))
        self.assertEqual(changed['positions'],old['positions'])
        self.problem(409,self.draft,positions=[dict(article_id=article['id'],article_revision=1,quantity='2')])
        altered=dict(old['positions'][0],unit_price_net='8')
        self.problem(409,self.api.update,self.owner,old['id'],domain.request(revision=2,positions=[altered]))
        validate_integrity(self.office)

    def test_stale_cost_selection_cannot_confirm_a_previously_checked_calculation(self):
        accepted,_=self.accept(self.stage(domain.raw(domain.row(role='purchase_net',amount='1'))));article=self.article(accepted)
        data=dict(source_article_id=article['id'],source_article_revision=1,source_price_selection=self.selection(accepted))
        checked=self.api.pricing_preview(self.owner,data)
        staged=self.stage(domain.raw(domain.row(role='purchase_net',amount='2')));prior=accepted['prices'][0]
        self.accept(staged,self.choices(staged,{'nov':{'revision':prior['revision'],'sha256':prior['sha256']}}))
        self.problem(409,self.draft,positions=[dict(description='Stale cost',quantity='1',pricing=checked['inputs'],pricing_hash=checked['preview_hash'],price_confirmation=True)])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_documents').fetchone()[0],0)

    def test_multiple_sources_are_prelocked_in_stable_order_before_any_write_resolution(self):
        first,_=self.accept(self.stage(domain.raw(domain.row(price_id='sale'),domain.row(price_id='buy',role='purchase_net',amount='1'))))
        original_source=self.source
        self.source=self.service.create_source(self.owner,domain.request(name='Second source',reference='SYN-SECOND'))
        second,_=self.accept(self.stage(domain.raw(domain.row(code='SECOND',price_id='other'))))
        ordered=sorted([original_source['id'],self.source['id']])
        second_article=self.api.catalog_item(self.owner,'business_articles',second['bindings'][0]['article_id'])
        selected=[self.position(first),dict(article_id=second_article['id'],article_revision=1,quantity='1',catalog_price_selection=self.selection(second))]
        if selected[0]['catalog_price_selection']['price_id']==second['prices'][0]['price_id']:selected.reverse()
        source=self.article(first)
        calculation=self.api.pricing_preview(self.owner,dict(components=[dict(article_id=source['id'],article_revision=1,quantity='1',price_selection=self.selection(first,index=1))]))
        selected.append(dict(description='Calculated third position',quantity='1',pricing=calculation['inputs'],pricing_hash=calculation['preview_hash'],price_confirmation=True))
        events=[]
        original_lock=prices.CatalogPrices.lock_source
        original_resolve=prices.resolve_selection
        def lock(service,source_id):
            events.append(('lock',source_id));return original_lock(service,source_id)
        def resolve(*args,**kwargs):
            events.append(('resolve',args[3]['price_id']));return original_resolve(*args,**kwargs)
        with patch.object(prices.CatalogPrices,'lock_source',lock),patch.object(prices,'resolve_selection',resolve):
            self.draft(positions=list(reversed(selected)))
        self.assertEqual(events[:2],[('lock',key) for key in ordered])
        self.assertGreaterEqual(next(i for i,event in enumerate(events) if event[0]=='resolve'),2)

    def test_restore_integrity_checks_dated_proofs_in_old_document_versions(self):
        accepted,_=self.accept(self.stage());old=self.draft(positions=[self.position(accepted)])
        manual=dict(description='Independent later position',quantity='1',unit='ST',unit_price_net='2',tax_rate='19')
        self.api.update(self.owner,old['id'],domain.request(revision=1,positions=[manual]))
        validate_integrity(self.office)
        historical=self.office.db.execute('SELECT payload_json FROM business_document_versions WHERE document_id=? AND revision=1',(old['id'],)).fetchone()[0]
        value=json.loads(historical);proof=value['positions'][0]['catalog_price_snapshot'];proof['effective_on']='2026-12-01'
        proof['snapshot_sha256']=prices.sha({key:item for key,item in proof.items() if key!='snapshot_sha256'})
        from core import canonical
        from business_documents import _hash
        with self.office.db:
            for trigger in self.office.db.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='business_document_versions'").fetchall():
                self.office.db.execute('DROP TRIGGER '+trigger['name'])
            text=canonical(value)
            self.office.db.execute('UPDATE business_document_versions SET payload_json=?,payload_sha256=? WHERE document_id=? AND revision=1',(text,_hash(text),old['id']))
        with self.assertRaises(ValueError):validate_integrity(self.office)


class CatalogPriceSalesConsumerTests(unittest.TestCase):
    command=legacy_sales.SalesTests.command
    save=legacy_sales.SalesTests.save
    adopt_body=legacy_sales.SalesTests.adopt_body
    problem=legacy_sales.SalesTests.problem
    stage=domain.CatalogPricesTests.stage
    choices=domain.CatalogPricesTests.choices
    accept=domain.CatalogPricesTests.accept

    def setUp(self):
        legacy_sales.SalesTests.setUp(self)
        for sql in prices.schema_statements('BLOB')+prices.guard_statements('sqlite'):self.office.db.execute(sql)
        self.service=prices.CatalogPrices(self.office,clock=lambda:datetime(2026,11,4,tzinfo=timezone.utc))
        self.source=self.service.create_source(self.owner,domain.request(name='Synthetic sales source',reference='SYN-SALES-V2'));self.sequence=0

    def test_sales_adoption_retains_article_reference_and_explicit_selection(self):
        accepted,_=self.accept(self.stage(domain.raw(domain.row(amount='1.00',basis='3'))));article_id=accepted['bindings'][0]['article_id']
        item=self.save();self.api.adoption(self.owner,item['id'],'project',self.adopt_body(item))
        selected=dict(article_id=article_id,article_revision=1,quantity='3');body=self.adopt_body(item,'offer',positions=[selected])
        self.problem(409,self.api.adoption,self.owner,item['id'],'offer',body)
        fact=accepted['prices'][0]
        selected['catalog_price_selection']=dict(price_id=fact['price_id'],price_revision=fact['revision'],price_sha256=fact['sha256'],effective_on='2026-11-03')
        result=self.api.adoption(self.owner,item['id'],'offer',body)
        self.assertEqual(self.api.adoption(self.owner,item['id'],'offer',body),result)
        offer=Documents(self.office).get(self.owner,result['document_id'])
        self.assertEqual((offer['positions'][0]['article_id'],offer['positions'][0]['article_revision']),(article_id,1))
        self.assertEqual((offer['positions'][0]['price_base_quantity'],offer['totals']['net']),('3','1.00'))
        self.assertEqual(offer['positions'][0]['catalog_price_snapshot']['price_id'],fact['price_id'])
