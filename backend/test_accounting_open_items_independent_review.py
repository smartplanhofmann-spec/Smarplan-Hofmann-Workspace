"""Independent actual old-item workflows; no copied production arithmetic."""
import base64
from copy import deepcopy
from datetime import datetime,timezone
import json
import unittest
import uuid

from core import Problem,canonical
from business_accounting_open_items import TABLES,public_source,validate_integrity
from business_bank_reconciliation import BankReconciliation,HEADERS
import business_schema
import test_business_accounting_open_items as fixtures


class OpeningItemsIndependentReview(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.OpeningItemWorkflow('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.office=self.f.office;self.api=self.f.api;self.owner=self.f.owner

    def blocked(self,call,*args):
        with self.assertRaises(Problem) as caught:call(*args)
        self.assertEqual(caught.exception.status,409,caught.exception.message)

    def test_original_old_cent_allocation_is_not_rewritten_to_fit_supported_method(self):
        payload=self.f.item(prior=True)
        payload['prior_payments'][0].update(net='33.33',tax='6.34')
        original=deepcopy(payload);before=self.api.state(self.owner)['revision']
        self.blocked(self.api.preview,self.owner,self.f.body('item','legacy-a',payload))
        self.assertEqual(payload,original);self.assertEqual(self.api.state(self.owner)['revision'],before)
        payload['prior_payments'][0].update(net='33.34',tax='6.33')
        item,command=self.f.save('item','legacy-a',payload)
        first,_=self.f.payment(item,'39.67');last,_=self.f.payment(item,'39.66','2026-03-15')
        self.assertEqual((first['details']['net'],first['details']['tax'],last['details']['net'],last['details']['tax']),('33.33','6.34','33.33','6.33'))
        self.assertEqual(self.api.confirm(self.owner,command),item)
        self.assertEqual(item['payload']['prior_payments'][0]['tax'],'6.33')
        current=self.api.state(self.owner)['items'][0]
        self.assertEqual([current[k] for k in ('remaining_net','remaining_tax','remaining')],['0.00']*3)

    def test_partial_supplier_settlements_have_paid_vat_expense_but_no_second_deduction(self):
        payload=self.f.item('supplier','payable',prior=True)
        payload.update(net='1000.00',tax='190.00',gross='1190.00')
        payload['prior_input_vat']['amount']='190.00'
        payload['prior_payments'][0].update(gross='238.00',net='200.00',tax='38.00')
        item,_=self.f.save('item','supplier',payload)
        first,_=self.f.payment(item,'357.00');a=self.f.classify(first)
        second,_=self.f.payment(item,'595.00','2026-03-15');b=self.f.classify(second)
        self.assertEqual([(p['ledger'],p['category'],p['amount']) for p in a['postings']],
                         [('euer','materials','-300.00'),('euer','paid_input_vat','-57.00')])
        self.assertEqual([(p['ledger'],p['category'],p['amount']) for p in b['postings']],
                         [('euer','materials','-500.00'),('euer','paid_input_vat','-95.00')])
        report=self.f.euer.api.report(self.owner,2026)
        self.assertEqual(report['totals']['confirmed_expenses'],'952.00')
        self.assertEqual(report['totals']['confirmed_input_vat'],'0.00')
        self.assertEqual([(m['direction'],m['amount']) for m in report['cash_movements']],[('out','357.00'),('out','595.00')])
        self.assertFalse(any(p['category']=='vat_refund' for p in report['postings']))

    def test_prior_declared_month_does_not_replace_actual_deduction_before_cutover(self):
        payload=self.f.item('supplier','payable')
        for day in ('2026-01-01','2025-11-10'):
            candidate=deepcopy(payload);candidate['prior_input_vat']['deducted_on']=day
            with self.subTest(day=day):self.blocked(self.api.preview,self.owner,self.f.body('item','supplier',candidate))
        candidate=deepcopy(payload);candidate['prior_input_vat']['amount']='9.50'
        self.blocked(self.api.preview,self.owner,self.f.body('item','supplier',candidate))
        self.assertEqual(self.api.state(self.owner)['revision'],0)

    def test_under_year_start_day_is_new_cash_but_open_items_do_not_complete_old_year(self):
        self.f.euer.configure(vat_effective_from='2025-01-01',bookkeeping_start='2026-11-01')
        payload=self.f.item('under-year','payable')
        payload.update(invoice_date='2026-06-10',service_date='2026-06-10',invoice_received_date='2026-06-11',history_through='2026-10-31')
        payload['prior_input_vat'].update(entitlement_date='2026-06-11',declared_period='2026-06',deducted_on='2026-07-10')
        payload['prior_payments']=[dict(date='2026-08-20',reference='Actual old half',gross='59.50',net='50.00',tax='9.50',proof=payload['cutover_proof'])]
        item,_=self.f.save('item','under-year',payload)
        self.blocked(self.f.payment,item,'59.50','2026-10-31')
        payment,_=self.f.payment(item,'59.50','2026-11-01');self.f.classify(payment)
        report=self.f.euer.api.report(self.owner,2026)
        self.assertEqual(report['totals']['confirmed_expenses'],'59.50')
        self.assertEqual(report['totals']['confirmed_input_vat'],'0.00')
        self.assertIn('partial_period_profile_coverage',[v['code'] for v in report['issues']])
        self.assertFalse(report['complete_for_recorded_sources']);self.assertIsNone(report['totals']['euer_surplus'])
        self.assertEqual([(v['date'],v['amount']) for v in report['cash_movements']],[('2026-11-01','59.50')])

    def test_unclassified_actual_cash_is_visible_without_fabricated_tax_or_income(self):
        self.f.f.save(amount='1000.00');self.f.f.bank_statement()
        item,_=self.f.save('item','legacy-a',self.f.item())
        payment,_=self.f.payment(item,'59.50')
        report=self.f.euer.api.report(self.owner,2026)
        self.assertEqual(report['totals']['confirmed_income'],'0.00')
        self.assertEqual(report['totals']['confirmed_output_vat'],'0.00')
        self.assertIn('opening_item_cash_classification_missing',[v['code'] for v in report['issues']])
        self.assertEqual([(v['amount'],v['direction']) for v in report['cash_movements']],[('59.50','in')])
        liquidity=self.f.f.api.liquidity(self.owner,'2026-02-28')
        self.assertEqual(liquidity['accounts'][0]['calculated_balance'],'1059.50')
        self.assertEqual(public_source(self.office,payment['entity_key'])['gross'],'59.50')

    def bank_match(self,payment):
        self.f.f.bank_statement()
        bank=BankReconciliation(self.office,clock=lambda:self.f.f.now)
        raw=(';'.join(HEADERS)+'\n'+';'.join(['REVIEW-1','2026-02-15','2026-02-15','59.50','EUR','Synthetic payer','Actual transfer'])+'\n').encode()
        body=dict(account_id=self.f.f.account['id'],account_revision=1,bank_revision=1,statement_reference='Independent February',period_from='2026-02-01',period_to='2026-02-28',opening_balance='1000.00',closing_balance='1059.50',filename='independent.csv',delimiter=';',content_base64=base64.b64encode(raw).decode(),complete_statement_confirmed=True)
        preview=bank.preview_import(self.owner,body);self.assertTrue(preview['can_import'])
        saved=bank.import_statement(self.owner,dict(body,request_id=uuid.uuid4().hex,confirmation=True,preview_hash=preview['preview_hash']))
        transaction=bank.statement(self.owner,saved['statement']['id'])['lines'][0]['transaction_id']
        source=next(row['source'] for row in bank.candidates(self.owner,transaction)['items'] if row['source']['source_id']==payment['entity_key'])
        match=dict(revision=0,links=[dict(source_kind='opening_item_cash',source_id=payment['entity_key'],source_hash=source['source_hash'],amount='59.50',date_difference_reason='')],reason='Original bank line and actual payment reviewed')
        preview=bank.preview_match(self.owner,transaction,match)
        bank.save_match(self.owner,transaction,dict(match,request_id=uuid.uuid4().hex,confirmation=True,preview_hash=preview['preview_hash']))
        return bank,transaction

    def test_void_requires_actual_bank_unlink_and_euer_reverse_and_keeps_original_history(self):
        item,_=self.f.save('item','legacy-a',self.f.item());payment,command=self.f.payment(item,'59.50')
        posted=self.f.classify(payment);bank,transaction=self.bank_match(payment)
        original=public_source(self.office,payment['entity_key'],1)
        payload=dict(payment['payload'],status='void')
        self.blocked(self.api.preview,self.owner,self.f.body('payment',payment['entity_key'],payload))
        self.f.euer.post('reverse',dict(entry_id=posted['id']))
        self.blocked(self.api.preview,self.owner,self.f.body('payment',payment['entity_key'],payload))
        unlink=dict(revision=1,links=[],reason='Erroneous payment requires explicit unlink before correction')
        preview=bank.preview_match(self.owner,transaction,unlink)
        bank.save_match(self.owner,transaction,dict(unlink,request_id=uuid.uuid4().hex,confirmation=True,preview_hash=preview['preview_hash']))
        voided,_=self.f.save('payment',payment['entity_key'],payload)
        self.assertEqual(voided['payload']['status'],'void')
        self.assertEqual(self.f.euer.api.report(self.owner,2026)['cash_movements'],[])
        self.assertEqual(public_source(self.office,payment['entity_key'],1),original)
        self.assertEqual(self.api.confirm(self.owner,command),payment)
        self.assertEqual(len(self.api.history(self.owner,payment['entity_key'])['items']),2)
        self.assertTrue(validate_integrity(self.office));self.assertTrue(business_schema.validate_integrity(self.office))

    def test_missing_original_or_confirmation_acceptance_blocks_live_replay_and_money(self):
        item,_=self.f.save('item','legacy-a',self.f.item());payment,command=self.f.payment(item,'59.50')
        original_id=item['payload']['invoice_proof']['original_id']
        raw,media=self.api.original(self.owner,original_id);original_bytes=bytes(raw)
        for operation,target in [('original',original_id),('confirm',payment['id'])]:
            self.office.db.execute('BEGIN')
            try:
                self.office.db.execute('DROP TRIGGER '+TABLES[2]+'_delete_guard')
                for row in self.office.db.execute('SELECT * FROM '+TABLES[2]+' WHERE operation=?',(operation,)).fetchall():
                    result=json.loads(row['result_json'])
                    if target in result.values():self.office.db.execute('DELETE FROM '+TABLES[2]+' WHERE user_id=? AND request_id=?',(row['user_id'],row['request_id']))
                with self.subTest(operation=operation):
                    self.blocked(self.api.state,self.owner)
                    self.blocked(self.api.confirm,self.owner,command)
                    self.blocked(public_source,self.office,payment['entity_key'])
                    with self.assertRaises(ValueError):validate_integrity(self.office)
            finally:self.office.db.rollback()
        self.assertEqual(bytes(self.api.original(self.owner,original_id)[0]),original_bytes)
        self.assertEqual(self.api.confirm(self.owner,command),payment)

    def test_frozen_export_after_payment_survives_real_reverse_and_void(self):
        item,_=self.f.save('item','legacy-a',self.f.item());payment,_=self.f.payment(item,'59.50');posted=self.f.classify(payment)
        exported=self.f.euer.post('export',dict(year=2026));before=self.f.euer.api.exported(self.owner,exported['id'])
        self.f.euer.post('reverse',dict(entry_id=posted['id']))
        self.f.save('payment',payment['entity_key'],dict(payment['payload'],status='void'))
        self.assertEqual(self.f.euer.api.exported(self.owner,exported['id']),before)
        self.assertEqual(self.f.euer.api.report(self.owner,2026)['totals']['confirmed_income'],'0.00')
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_actual_receivable_payments_cross_year_without_import_date_or_double_old_vat(self):
        self.api.clock=lambda:datetime(2027,2,10,12,tzinfo=timezone.utc)
        payload=self.f.item('cross-year');payload.update(net='1000.00',tax='190.00',gross='1190.00')
        item,_=self.f.save('item','cross-year',payload)
        first,_=self.f.payment(item,'595.00','2026-11-04');self.f.classify(first)
        old_export=self.f.euer.post('export',dict(year=2026));frozen=self.f.euer.api.exported(self.owner,old_export['id'])
        second,_=self.f.payment(item,'595.00','2027-02-02');self.f.classify(second)
        for year in (2026,2027):
            report=self.f.euer.api.report(self.owner,year)
            self.assertEqual(report['totals']['confirmed_income'],'595.00')
            self.assertEqual(report['totals']['confirmed_output_vat'],'95.00')
            self.assertEqual(report['totals']['confirmed_input_vat'],'0.00')
        self.assertEqual(self.f.euer.api.exported(self.owner,old_export['id']),frozen)
        self.assertEqual(self.api.state(self.owner)['items'][0]['remaining'],'0.00')

    def test_later_cent_payment_must_be_undone_before_earlier_cent_correction(self):
        item,_=self.f.save('item','legacy-a',self.f.item(prior=True))
        first,_=self.f.payment(item,'39.67');last,_=self.f.payment(item,'39.66','2026-03-15')
        self.blocked(self.api.preview,self.owner,self.f.body('payment',first['entity_key'],dict(first['payload'],status='void')))
        self.f.save('payment',last['entity_key'],dict(last['payload'],status='void'))
        self.f.save('payment',first['entity_key'],dict(first['payload'],status='void'))
        corrected,_=self.f.save('payment',first['entity_key'],dict(first['payload'],amount='79.33'))
        self.assertEqual([corrected['details'][key] for key in ('net','tax','gross')],['66.66','12.67','79.33'])
        self.assertEqual(public_source(self.office,last['entity_key'],1)['tax'],'6.33')
        self.assertEqual(public_source(self.office,first['entity_key'],1)['tax'],'6.34')
        self.assertTrue(validate_integrity(self.office))


if __name__=='__main__':unittest.main()
