"""Independent source identity, historical periods and annual coverage cases."""
import base64
from copy import deepcopy
import unittest
import uuid
from core import Problem,canonical
from business_accounting_year_openings import YearValues,public_source
import test_accounting_year_openings as fixtures
import test_business_accounting_open_items as item_fixtures

class IndependentYearValues(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.YearOpeningWorkflow('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.office,self.owner,self.api=self.f.office,self.f.owner,self.f.api

    def test_full_old_coverage_does_not_clear_real_new_unclassified_cash(self):
        entry,_=self.f.save();self.f.classify(entry)
        payment,_=self.f.f.payment(self.f.old,'59.50',day='2026-11-01')
        report=self.f.f.euer.api.report(self.owner,2026)
        self.assertFalse(report['complete_for_recorded_sources']);self.assertIsNone(report['totals']['euer_surplus'])
        self.assertFalse(any(i['code']=='partial_period_profile_coverage' for i in report['issues']))
        self.assertTrue(any('classification_missing' in i['code'] for i in report['issues']))
        self.assertEqual(report['totals']['confirmed_expenses'],'59.50')
        self.f.f.classify(payment);current=self.f.f.euer.api.report(self.owner,2026)
        self.assertTrue(current['complete_for_recorded_sources']);self.assertEqual(current['totals']['confirmed_expenses'],'119.00')

    def test_prior_vat_year_is_not_recreated_by_current_cash_year(self):
        record=deepcopy(self.f.old['payload']);record.update(invoice_date='2025-06-10',service_date='2025-06-10',invoice_received_date='2025-06-11')
        record['prior_input_vat'].update(entitlement_date='2025-06-11',declared_period='2025-06',deducted_on='2025-07-10')
        # Immutable economic invoice identity cannot be changed behind old item.
        with self.assertRaises(Problem):self.f.f.save('item',self.f.old['entity_key'],record)
        # Use a separate genuinely older invoice with its own original binding.
        other=self.f.f.item('prior-year-original','payable');other.update(invoice_date='2025-06-10',service_date='2025-06-10',invoice_received_date='2025-06-11',history_through='2026-10-31')
        other['prior_input_vat'].update(entitlement_date='2025-06-11',declared_period='2025-06',deducted_on='2025-07-10')
        other['prior_payments']=[dict(date='2026-07-15',reference='Original current-year old payment',gross='59.50',net='50.00',tax='9.50',proof=other['cutover_proof'])]
        item,_=self.f.f.save('item','prior-year-original',other)
        payload=deepcopy(self.f.payload);payload['sources'].append(dict(kind='opening_item',entry_id=item['id'],entry_hash=item['content_hash'],accounts=self.f.rules.source['accounts'],cash_entry_keys=['PRIOR-YEAR-CASH'],vat_entry_key='PRIOR-YEAR-VAT'))
        payload['controls'][0]['amount']='-100.00';payload['controls'][1]['amount']='-19.00'
        entry,_=self.f.save(payload);posted=self.f.classify(entry)
        report=self.f.f.euer.api.report(self.owner,2026)
        self.assertEqual(report['totals']['confirmed_expenses'],'119.00')
        self.assertEqual(report['totals']['confirmed_input_vat'],'19.00')
        self.assertEqual([p['date'] for p in posted['postings'] if p['ledger']=='vat'],['2026-06-11'])
        self.assertEqual(report['cash_movements'],[])

    def test_control_account_and_original_journal_identity_are_exact(self):
        for change in ('account','cent','journal_collision'):
            p=deepcopy(self.f.payload)
            if change=='account':p['sources'][0]['accounts']['net']='5401'
            elif change=='cent':p['controls'][0]['amount']='-50.01'
            else:p['sources'][0]['vat_entry_key']=p['sources'][0]['cash_entry_keys'][0]
            with self.subTest(change=change),self.assertRaises(Problem):self.api.preview(self.owner,self.f.body(p))
        p=deepcopy(self.f.payload);p['sources'][0]['accounts']['net']='5401';p['controls'][0]['account']='5401'
        entry,_=self.f.save(p);posted=self.f.classify(entry)
        self.assertEqual(next(v['account'] for v in posted['postings'] if v['category']=='materials'),'5401')

    def test_known_old_original_cannot_be_rescanned_into_closed_trade_alias(self):
        record=deepcopy(self.f.old['payload']);record['external_id']='different-technical-key'
        record['invoice_proof']=self.f.original('Rescan of same economic invoice')
        record['cutover_proof']=self.f.original('Settled before start')
        record['prior_input_vat']['proof']=self.f.original('Actual already exercised VAT')
        record['prior_payments'][0].update(gross='119.00',net='100.00',tax='19.00',proof=record['cutover_proof'])
        candidate=dict(kind='closed_trade',record=record,accounts=self.f.rules.source['accounts'],cash_entry_keys=['ANOTHER-CASH'],vat_entry_key='ANOTHER-VAT')
        p=deepcopy(self.f.payload);p['sources']=[candidate];p['controls'][0]['amount']='-100.00';p['controls'][1]['amount']='-19.00'
        with self.assertRaises(Problem) as denied:self.api.preview(self.owner,self.f.body(p))
        self.assertEqual(denied.exception.status,409)

    def test_fresh_source_revision_cannot_silently_retarget_old_year_approval(self):
        entry,command=self.f.save();source=public_source(self.office,'2026',1)
        changed=deepcopy(self.f.old['payload']);changed['prior_payments'][0]['reference']='Explicitly re-reviewed original reference'
        revised,_=self.f.f.save('item',self.f.old['entity_key'],changed)
        self.assertEqual(self.api.confirm(self.owner,command),entry)
        with self.assertRaises(Problem):self.f.classify(entry)
        self.assertEqual(public_source(self.office,'2026',1),source)
        reasons=[i['code'] for i in self.f.f.euer.api.report(self.owner,2026)['issues']]
        self.assertIn('opening_year_values_coverage_changed',reasons)

    def test_partial_intervals_do_not_implicitly_union_and_old_export_is_unchanged(self):
        p=deepcopy(self.f.payload);p['coverage']={'from':'2026-08-01','through':'2026-10-31'};p['controls']=p['controls'][:2]
        first,command=self.f.save(p);posted=self.f.classify(first);old=self.f.f.euer.post('export',{'year':2026});frozen=self.f.f.euer.api.exported(self.owner,old['id'])
        self.f.f.euer.post('reverse',{'entry_id':posted['id']});self.f.save(dict(p,status='void'))
        p=deepcopy(self.f.payload);p['coverage']={'from':'2026-01-01','through':'2026-07-31'};p['controls']=p['controls'][2:]
        second,_=self.f.save(p);self.f.classify(second);report=self.f.f.euer.api.report(self.owner,2026)
        self.assertFalse(report['complete_for_recorded_sources']);self.assertIsNone(report['totals']['euer_surplus'])
        self.assertEqual(report['historical_year_values']['coverage'],p['coverage'])
        self.assertEqual(report['totals']['confirmed_expenses'],'0.00')
        self.assertEqual(self.f.f.euer.api.exported(self.owner,old['id']),frozen)
        self.assertEqual(self.api.confirm(self.owner,command),first)

    def test_zero_journal_does_not_hide_known_values_or_ordinary_late_source(self):
        p=deepcopy(self.f.payload);p.update(sources=[],controls=[])
        with self.assertRaises(Problem):self.api.preview(self.owner,self.f.body(p))
        f=item_fixtures.OpeningItemWorkflow('runTest');f.setUp();self.addCleanup(f.doCleanups)
        f.euer.configure(vat_effective_from='2025-01-01',bookkeeping_start='2026-11-01')
        helper=fixtures.YearOpeningWorkflow('runTest');helper.f=f;helper.office=f.office;helper.owner=f.owner;helper.api=YearValues(f.office,clock=lambda:f.f.now)
        helper.payload=dict(status='active',coverage={'from':'2026-01-01','through':'2026-10-31'},sources=[],controls=[],ledger_proof=helper.original('Explicit independently verified zero-period journal'),attestations=dict(continuous_method=True,original_journal_complete=True,no_unsupported_values=True))
        entry,_=helper.save();helper.classify(entry)
        self.assertTrue(f.euer.api.report(f.owner,2026)['complete_for_recorded_sources'])
        f.euer.incoming(day='2026-06-11')
        report=f.euer.api.report(f.owner,2026)
        self.assertFalse(report['complete_for_recorded_sources']);self.assertIsNone(report['totals']['euer_surplus'])
        self.assertTrue(report['issues'])

    def test_separate_year_original_identity_and_current_rights_are_required(self):
        original=self.api.upload_original(self.owner,dict(request_id=uuid.uuid4().hex,entity_key='2025',filename='other-year.pdf',media_type='application/pdf',content_base64=base64.b64encode(b'%PDF-1.4\nOther actual year journal\n%%EOF').decode()))
        p=deepcopy(self.f.payload);p['ledger_proof']={'original_id':original['id'],'sha256':original['sha256']}
        with self.assertRaises(Problem):self.api.preview(self.owner,self.f.body(p))
        entry,command=self.f.save()
        with self.assertRaises(Problem) as denied:self.api.confirm(self.f.f.euer.fixture.tech,command)
        self.assertEqual(denied.exception.status,403)
        with self.assertRaises(Problem):self.api.original(self.f.f.euer.fixture.tech,self.f.payload['ledger_proof']['original_id'])
        self.assertEqual(self.api.confirm(self.owner,command),entry)

if __name__=='__main__':unittest.main()
