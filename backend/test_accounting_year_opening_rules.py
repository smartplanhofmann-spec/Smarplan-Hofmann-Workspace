"""Independent ordinary-cash reference amounts against real original item sources."""
from copy import deepcopy
import unittest
from core import Problem
from business_accounting_openings import sha
from accounting_year_opening_rules import calculate
import test_business_accounting_open_items as fixture

class YearOpeningRules(unittest.TestCase):
    def setUp(self):
        self.f=fixture.OpeningItemWorkflow('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.profile=self.f.euer.configure(vat_effective_from='2025-01-01',bookkeeping_start='2026-11-01')
        record=self.f.item('year-history','payable')
        record.update(invoice_date='2026-06-10',service_date='2026-06-10',invoice_received_date='2026-06-11',history_through='2026-10-31')
        record['prior_input_vat'].update(entitlement_date='2026-06-11',declared_period='2026-06',deducted_on='2026-07-10')
        record['prior_payments']=[dict(date='2026-08-20',reference='Original August part',gross='59.50',net='50.00',tax='9.50',proof=record['cutover_proof'])]
        entry,_=self.f.save('item','year-history',record)
        self.source=dict(kind='opening_item',source_ref=entry['content_hash'],record=entry['payload'],accounts=dict(net='5400',tax='1406',input_vat='1406'),cash_entry_keys=['OLD-2026-081'],vat_entry_key='OLD-2026-061')
        self.coverage={'from':'2026-01-01','through':'2026-10-31'}
        self.controls=[dict(ledger='euer',category='materials',account='5400',amount='-50.00'),dict(ledger='euer',category='paid_input_vat',account='1406',amount='-9.50'),dict(ledger='vat',category='input_vat',account='1406',amount='-19.00')]

    def test_known_old_half_and_old_full_vat_retain_distinct_actual_periods(self):
        result=calculate(self.profile,self.coverage,[self.source],self.controls)
        self.assertEqual([(p['ledger'],p['amount'],p['date']) for p in result['historical_postings']],[('euer','-50.00','2026-08-20'),('euer','-9.50','2026-08-20'),('vat','-19.00','2026-06-11')])
        self.assertFalse(result['cash_flow_created']);self.assertFalse(result['new_input_vat_claim_created']);self.assertTrue(result['complete_prior_period'])
        self.assertEqual(result['copied_rows'][1]['deducted_on'],'2026-07-10')

    def test_partial_coverage_is_not_full_and_cannot_move_original_vat_month(self):
        result=calculate(self.profile,{'from':'2026-08-01','through':'2026-10-31'},[self.source],self.controls[:2])
        self.assertFalse(result['complete_prior_period']);self.assertEqual(len(result['historical_postings']),2)
        self.assertTrue(all(p['date']=='2026-08-20' for p in result['historical_postings']))

    def test_fully_paid_external_trade_is_supported_without_fake_open_remainder(self):
        source=deepcopy(self.source);source['kind']='closed_trade';source['record']['prior_payments'][0].update(gross='119.00',net='100.00',tax='19.00');source['source_ref']=sha(source['record'])
        controls=deepcopy(self.controls);controls[0]['amount']='-100.00';controls[1]['amount']='-19.00'
        result=calculate(self.profile,self.coverage,[source],controls)
        self.assertEqual(result['copied_rows'][0]['gross'],'119.00');self.assertFalse(result['cash_flow_created'])
        # The unchanged original open-item API still refuses fully paid imports.
        with self.assertRaises(Problem) as denied:self.f.api.preview(self.f.owner,self.f.body('item','year-history',source['record']))
        self.assertEqual(denied.exception.status,409)

    def test_wrong_year_start_day_duplicate_identity_and_control_cent_fail(self):
        for coverage in ({'from':'2025-01-01','through':'2025-10-31'},{'from':'2026-01-01','through':'2026-11-01'}):
            with self.subTest(coverage=coverage),self.assertRaises(Problem):calculate(self.profile,coverage,[self.source],self.controls)
        duplicate=deepcopy(self.source);duplicate['record']['external_id']='different alias'
        with self.assertRaises(Problem):calculate(self.profile,self.coverage,[self.source,duplicate],self.controls)
        wrong=deepcopy(self.controls);wrong[0]['amount']='-50.01'
        with self.assertRaises(Problem):calculate(self.profile,self.coverage,[self.source],wrong)

    def test_old_vat_from_previous_year_is_never_reclaimed_with_current_year_payment(self):
        source=deepcopy(self.source);record=source['record']
        record.update(invoice_date='2025-06-10',service_date='2025-06-10',invoice_received_date='2025-06-11')
        record['prior_input_vat'].update(entitlement_date='2025-06-11',declared_period='2025-06',deducted_on='2025-07-10')
        result=calculate(self.profile,self.coverage,[source],self.controls[:2])
        self.assertEqual(len(result['historical_postings']),2);self.assertEqual(result['copied_rows'][0]['gross'],'59.50')
        self.assertFalse(any(p['ledger']=='vat' for p in result['historical_postings']))

    def test_different_scan_and_alias_still_preserves_original_economic_invoice_identity(self):
        duplicate=deepcopy(self.source);duplicate['record']['external_id']='new alias';duplicate['record']['invoice_proof']['sha256']='c'*64
        with self.assertRaises(Problem):calculate(self.profile,self.coverage,[self.source,duplicate],self.controls)

if __name__=='__main__':unittest.main()
