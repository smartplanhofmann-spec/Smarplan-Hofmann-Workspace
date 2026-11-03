"""EÜR monetary/legal reference cases on isolated real SQLite domain stores.

Only invoice issuance uses the existing explicit SyntheticDocuments adapter.
Separate PostgreSQL/HTTP tests exercise actual runtime roles and MFA transport.
"""
import json
import sqlite3
import unittest
import uuid
from unittest.mock import patch

import test_business_accounting_components as fixture
from business_accounting_euer import EuerAccounting, _euer_date, dispatch, protected_tables, restore_horizon, validate_integrity
from business_accounting_profile import AccountingPreparationProfile
from business_operations import transaction
from core import Problem, canonical


class EuerWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.ComponentTests('runTest'); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.office=self.fixture.office; self.owner=self.fixture.owner; self.api=EuerAccounting(self.office,clock=self.fixture.clock)
        self.profile=AccountingPreparationProfile(self.office,clock=self.fixture.clock)
        self.configure()

    def configure(self,**changes):
        state=self.profile.state(self.owner)
        body=dict(expected_revision=state['revision'],state_hash=state['state_hash'],reason='Explicit synthetic accounting facts',evidence_reference='Synthetic owner statement',
                  profile=dict(legal_form='sole_proprietorship',accounting_method='euer',vat_regime='regular',vat_timing='cash',
                               vat_effective_from='2026-01-01',bookkeeping_start='2026-01-01')|changes)
        preview=self.profile.preview(self.owner,body)
        return self.profile.confirm(self.owner,dict(body,request_id=uuid.uuid4().hex,confirmation=True,preview_hash=preview['preview_hash']))

    def body(self,operation,payload):
        state=self.api.state(self.owner)
        return dict(operation=operation,payload=payload,expected_revision=state['revision'],state_hash=state['state_hash'],
                    reason='Explicit synthetic subject/tax/account review',evidence_reference='Synthetic evidence and SKR04 mapping')

    def command(self,operation,payload):
        body=self.body(operation,payload); preview=self.api.preview(self.owner,body)
        return dict(body,request_id=uuid.uuid4().hex,confirmation=True,preview_hash=preview['preview_hash'])

    def post(self,operation,payload):
        return self.api.confirm(self.owner,self.command(operation,payload))

    def failure(self,status,method,*args,resolution=None):
        with self.assertRaises(Problem) as caught:method(*args)
        self.assertEqual(caught.exception.status,status,caught.exception.message)
        if resolution is not None:self.assertEqual(caught.exception.request_resolution,resolution)
        return caught.exception

    def incoming(self,net='50.00',tax='9.50',gross='59.50',day='2026-11-01'):
        receipt=self.fixture.receipt()
        self.fixture.finance.review_receipt(self.owner,receipt['id'],self.fixture.review_body(revision=1,net=net,tax=tax,gross=gross,issue_date=day))
        return receipt

    def vat_payload(self,receipt,amount='9.50',day='2026-11-01'):
        source=self.api._receipt_source(self.owner,receipt['id'])
        return dict(receipt_id=receipt['id'],source_hash=source['source_hash'],invoice_received_date=day,service_date=day,
                    prepayment=False,payment_event_id=None,entitlement_date=day,deductible_tax=amount,account='1406',conditions_confirmed=True)

    def documented(self,event):
        self.fixture.components.confirm(self.owner,event['id'],self.fixture.confirm_body(event))
        return event

    def sale(self,net='100.00',amount='119.00'):
        invoice=self.fixture.invoice(net=net)
        return self.documented(self.fixture.customer_event(invoice,amount))

    def payout(self,receipt,amount='59.50',day='2026-11-02'):
        return self.documented(self.fixture.api.payout(self.owner,self.fixture.payout_body(receipt,amount=amount,cash_date=day)))

    def cash_payload(self,event,category='sales',**changes):
        source=self.api._cash_source(self.owner,event['id']); income=category=='sales'
        lines=[dict(unit_id=unit['unit_id'],category=category,business_net=unit['net'],deductible_net='0.00' if income or category=='asset_acquisition' else unit['net'],
                    business_tax=unit['tax'],deductible_input_tax='0.00' if income else unit['tax'],deductible_tax_cost='0.00',
                    account='4400' if income else '5400',vat_account='3806' if income else '1406') for unit in source['units']]
        return dict(event_id=event['id'],source_hash=source['source_hash'],euer_date=event['cash_date'],year_rule={'kind':'cash'},lines=lines)|changes

    def external_payload(self,receipt,amount='9.50',category='vat_payment',day='2026-11-03'):
        source=self.api._receipt_source(self.owner,receipt['id'])
        return dict(receipt_id=receipt['id'],source_hash=source['source_hash'],account_id=self.fixture.account['id'],account_revision=1,
                    evidence_key='synthetic-tax-'+uuid.uuid4().hex,cash_date=day,amount=amount,direction='in' if category in ('vat_refund','owner_contribution','loan_received') else 'out',
                    category=category,euer_date=day,year_rule={'kind':'cash'},account='3820')

    def test_official_cash_vat_reference_closed_journey_and_exact_frozen_export(self):
        income=self.sale(); sale=self.post('cash',self.cash_payload(income))
        receipt=self.incoming(); self.post('input_vat',self.vat_payload(receipt)); expense=self.payout(receipt)
        self.post('cash',self.cash_payload(expense,'materials'))
        interim=self.api.report(self.owner,2026)
        self.assertEqual(interim['totals']['confirmed_surplus'],'59.50')
        self.assertEqual(interim['totals']['confirmed_output_vat'],'19.00')
        self.assertEqual(interim['totals']['confirmed_input_vat'],'9.50')
        tax=self.incoming('9.50','0.00','9.50'); self.post('external_cash',self.external_payload(tax))
        report=self.api.report(self.owner,2026)
        self.assertTrue(report['complete_for_recorded_sources'],report['issues'])
        self.assertEqual(report['totals']['euer_surplus'],'50.00')
        self.assertEqual(report['totals']['vat_balance'],'9.50')
        self.assertEqual(len(report['cash_movements']),3)
        self.assertEqual(self.api.sources(self.owner)['account_movements'][0]['movement_net'],'50.00')
        command=self.command('export',{'year':2026}); exported=self.api.confirm(self.owner,command)
        artifact=self.api.exported(self.owner,exported['id'])
        self.assertIn('vat_collected',artifact['csv']); self.assertIn('paid_input_vat',artifact['csv'])
        self.assertEqual(self.api.confirm(self.owner,command),exported)
        self.post('correct',dict(entry_id=sale['id'],operation='cash',payload=self.cash_payload(income)))
        self.assertEqual(self.api.exported(self.owner,exported['id']),artifact)
        self.assertTrue(validate_integrity(self.office))

    def test_unpaid_invoice_input_vat_is_separate_from_later_cash_year(self):
        receipt=self.incoming(day='2026-12-15')
        self.post('input_vat',self.vat_payload(receipt,day='2026-12-15'))
        report=self.api.report(self.owner,2026)
        self.assertEqual(report['totals']['confirmed_input_vat'],'9.50')
        self.assertEqual(report['totals']['confirmed_expenses'],'0.00')
        payout=self.payout(receipt,day='2027-01-20'); self.post('cash',self.cash_payload(payout,'materials'))
        self.assertEqual(self.api.report(self.owner,2026)['totals']['confirmed_expenses'],'0.00')
        future=self.api.report(self.owner,2027)
        self.assertEqual(future['totals']['confirmed_expenses'],'59.50')
        self.assertEqual(future['totals']['confirmed_input_vat'],'0.00')

    def test_missing_review_decision_profile_or_components_never_becomes_zero(self):
        receipt=self.incoming(); event=self.payout(receipt)
        report=self.api.report(self.owner,2026)
        self.assertIsNone(report['totals']['euer_surplus'])
        self.failure(409,self.api.preview,self.owner,self.body('cash',self.cash_payload(event,'materials')))
        self.configure(bookkeeping_start=None)
        self.failure(409,self.api.preview,self.owner,self.body('input_vat',self.vat_payload(receipt)))
        self.assertFalse(self.api.state(self.owner)['profile_ready'])

    def test_ten_day_exception_requires_real_due_date_and_separate_vat_period(self):
        self.assertEqual(_euer_date('2027-01-08','2026-12-31',dict(kind='ten_day',economic_year=2026,due_date='2027-01-10',recurring=True)),'2026-12-31')
        for due,day,recurring in [('2026-09-10','2027-01-08',True),('2027-01-10','2027-01-11',True),('2027-01-10','2027-01-08',False)]:
            self.failure(400,_euer_date,day,'2026-12-31',dict(kind='ten_day',economic_year=2026,due_date=due,recurring=recurring))
        receipt=self.incoming('9.50','0.00','9.50',day='2026-12-31')
        body=self.external_payload(receipt,day='2027-01-08'); body.update(euer_date='2026-12-31',year_rule=dict(kind='ten_day',economic_year=2026,due_date='2027-01-10',recurring=True))
        self.post('external_cash',body)
        self.assertEqual(self.api.report(self.owner,2026)['totals']['confirmed_expenses'],'9.50')
        self.assertEqual(self.api.report(self.owner,2027)['totals']['confirmed_expenses'],'0.00')

    def test_reviewed_private_nondeductible_and_tax_components_balance_exactly(self):
        receipt=self.incoming(); self.post('input_vat',self.vat_payload(receipt,amount='4.75')); event=self.payout(receipt)
        payload=self.cash_payload(event,'other_expense')
        payload['lines'][0].update(business_net='25.00',deductible_net='20.00',business_tax='4.75',deductible_input_tax='4.75')
        entry=self.post('cash',payload)
        amounts={row['category']:row['amount'] for row in entry['postings']}
        self.assertEqual(amounts['private_portion'],'-29.75')
        self.assertEqual(sum(int(row['amount'].replace('.','')) for row in entry['postings']),-5950)
        self.assertEqual(self.api.report(self.owner,2026)['totals']['confirmed_expenses'],'24.75')

    def test_counterposting_correction_lock_and_reopening_preserve_full_history(self):
        event=self.sale(); initial=self.post('cash',self.cash_payload(event))
        close=dict(period='2026-11',action='close',expected_period_revision=0,
                   attestation=dict(bank_reconciled=True,originals_complete=True,special_cases_reviewed=True))
        closed=self.post('period',close)
        self.failure(409,self.api.preview,self.owner,self.body('reverse',{'entry_id':initial['id']}))
        self.post('period',dict(close,action='reopen',expected_period_revision=1))
        correction=self.post('correct',dict(entry_id=initial['id'],operation='cash',payload=self.cash_payload(event)))
        self.assertEqual(correction['reverses'],initial['id'])
        self.assertEqual(len(correction['postings']),6)
        self.assertEqual(self.api.report(self.owner,2026)['totals']['confirmed_income'],'119.00')
        self.post('reverse',dict(entry_id=correction['id']))
        report=self.api.report(self.owner,2026)
        self.assertEqual(report['totals']['confirmed_income'],'0.00')
        self.assertIsNone(report['totals']['euer_surplus'])
        self.assertEqual(len(self.api.journal(self.owner)['items']),5)
        self.assertTrue(validate_integrity(self.office))

    def test_new_asset_linear_monthly_basis_and_no_double_cash_expense(self):
        receipt=self.incoming('100.00','19.00','119.00'); self.post('input_vat',self.vat_payload(receipt,amount='19.00'))
        source=self.api._receipt_source(self.owner,receipt['id'])
        asset=self.post('asset',dict(receipt_id=receipt['id'],source_hash=source['source_hash'],description='Explicit two year asset',business_basis='100.00',
                                     use_start='2026-11-01',life_months=24,account='0670'))
        event=self.payout(receipt,'119.00'); self.post('cash',self.cash_payload(event,'asset_acquisition'))
        self.assertIn('depreciation_missing',[item['code'] for item in self.api.report(self.owner,2026)['issues']])
        first=self.post('depreciation',dict(asset_entry_id=asset['id'],year=2026,account='6220'))
        second=self.post('depreciation',dict(asset_entry_id=asset['id'],year=2027,account='6220'))
        third=self.post('depreciation',dict(asset_entry_id=asset['id'],year=2028,account='6220'))
        self.assertEqual([entry['effect']['details']['amount'] for entry in (first,second,third)],['8.33','50.00','41.67'])
        self.assertEqual(third['effect']['details']['closing_book_value'],'0.00')
        self.assertEqual(self.api.report(self.owner,2026)['totals']['confirmed_expenses'],'27.33')
        self.failure(409,self.api.preview,self.owner,self.body('reverse',dict(entry_id=asset['id'])))
        self.failure(409,self.api.preview,self.owner,self.body('depreciation',dict(asset_entry_id=asset['id'],year=2027,account='6220')))

    def test_replay_rights_conflict_markers_atomic_rollback_and_immutable_guards(self):
        event=self.sale(); command=self.command('cash',self.cash_payload(event)); entry=self.api.confirm(self.owner,command)
        self.assertEqual(self.api.confirm(self.owner,command),entry)
        conflict=dict(command,request_id=uuid.uuid4().hex)
        self.failure(409,self.api.confirm,self.owner,conflict,resolution='not_accepted')
        self.failure(403,self.api.confirm,self.fixture.tech,command)
        before=restore_horizon(self.office)
        command2=self.command('reverse',dict(entry_id=entry['id']))
        with patch.object(self.office,'audit',side_effect=RuntimeError('synthetic interrupted final write')):
            with self.assertRaises(RuntimeError):self.api.confirm(self.owner,command2)
        self.assertEqual(restore_horizon(self.office),before)
        for table in protected_tables():
            with self.assertRaises(sqlite3.IntegrityError):self.office.db.execute('DELETE FROM '+table)
            columns=[row['name'] for row in self.office.db.execute('PRAGMA table_info('+table+')')]
            row=self.office.db.execute('SELECT * FROM '+table+' LIMIT 1').fetchone()
            with self.assertRaises(sqlite3.IntegrityError):self.office.db.execute('INSERT OR REPLACE INTO '+table+' VALUES('+','.join('?' for col in columns)+')',tuple(row))

    def test_duplicate_original_and_movement_identity_are_rejected_cross_module(self):
        receipt=self.incoming('9.50','0.00','9.50'); command=self.external_payload(receipt)
        self.post('external_cash',command)
        self.failure(409,self.fixture.api.payout,self.owner,self.fixture.payout_body(receipt,amount='9.50'))
        original=self.office.db.execute('SELECT original FROM business_incoming_receipts WHERE id=?',(receipt['id'],)).fetchone()[0]
        duplicate=self.fixture.receipt(original=bytes(original))
        self.fixture.finance.review_receipt(self.owner,duplicate['id'],self.fixture.review_body(revision=1,net='9.50',tax='0.00',gross='9.50'))
        self.failure(409,self.api.preview,self.owner,self.body('external_cash',self.external_payload(duplicate)))
        self.assertIn('duplicate_original',[item['code'] for item in self.api.report(self.owner,2026)['issues']])

    def test_transport_shapes_preserve_known_uncertainty_contract(self):
        for path in ('/accounting/euer','/accounting/euer/sources','/accounting/euer/journal'):
            self.failure(400,dispatch,self.office,self.owner,path,'GET',dict(_query={'unknown':'x'}))
            self.failure(400,dispatch,self.office,self.owner,path,'GET',dict(body=True))
        self.failure(400,dispatch,self.office,self.owner,'/accounting/euer/report','GET',dict(_query={'year':['2026','2027']}))
        self.failure(405,dispatch,self.office,self.owner,'/accounting/euer/confirm','GET',{})
        self.failure(400,dispatch,self.office,self.owner,'/accounting/euer/preview','POST',dict(_query={}))

    def test_rejected_later_review_and_partial_vat_claim_never_hide_incomplete_tax(self):
        receipt=self.incoming(); self.post('input_vat',self.vat_payload(receipt)); event=self.payout(receipt)
        payload=self.cash_payload(event,'materials'); payload['lines'][0]['deductible_input_tax']='4.75'
        self.failure(400,self.api.preview,self.owner,self.body('cash',payload))
        payload['lines'][0]['deductible_input_tax']='9.50'; self.post('cash',payload)
        self.fixture.finance.review_receipt(self.owner,receipt['id'],self.fixture.review_body(revision=2,status='rejected'))
        report=self.api.report(self.owner,2026)
        self.assertIn('original_review_changed',[item['code'] for item in report['issues']])
        self.assertIsNone(report['totals']['euer_surplus'])
        self.assertEqual(report['totals']['confirmed_input_vat'],'9.50')
        self.assertTrue(validate_integrity(self.office))

    def test_registered_asset_and_already_expensed_acquisition_cannot_double_deduct(self):
        receipt=self.incoming(); self.post('input_vat',self.vat_payload(receipt)); event=self.payout(receipt)
        self.post('cash',self.cash_payload(event,'materials'))
        source=self.api._receipt_source(self.owner,receipt['id'])
        payload=dict(receipt_id=receipt['id'],source_hash=source['source_hash'],description='Explicit asset',business_basis='50.00',use_start='2026-11-01',life_months=24,account='0670')
        self.failure(409,self.api.preview,self.owner,self.body('asset',payload))

    def test_original_reused_and_mixed_refund_cents_flow_unchanged_into_tax_journal(self):
        import test_business_accounting_refunds_v2 as refunds_fixture
        source=refunds_fixture.VersionedRefundDomainTests('runTest'); source.setUp(); self.addCleanup(source.doCleanups)
        self.fixture=source; self.office=source.office; self.owner=source.owner; self.api=EuerAccounting(self.office,clock=source.clock)
        self.profile=AccountingPreparationProfile(self.office,clock=source.clock); self.configure()
        invoice,middle,old_refund,old_return,reused_event,reused,unused=source.mixed_seed()
        unused,refund=source.cash_event(invoice,'26.44',kind='refund')
        group=middle['lines'][0]['group_id']
        source.r2.confirm(self.owner,refund['id'],source.versioned_command(refund,[('c1',middle['id'],group,'13.22'),('c2',reused['id'],group,'13.22')]))
        old_tables=('business_accounting_component_entries','business_accounting_capacity_entries','business_accounting_refund_entries','business_accounting_refunds_v2_entries')
        before=source.snapshot(old_tables)
        for row in self.office.db.execute('SELECT id FROM business_accounting_cash_events ORDER BY sequence').fetchall():
            event=source.api.event(self.owner,row['id']); self.post('cash',self.cash_payload(event))
        report=self.api.report(self.owner,2026)
        self.assertEqual(report['totals']['confirmed_income'],'92.56')
        self.assertEqual(report['totals']['confirmed_output_vat'],'14.77')
        self.assertTrue(report['complete_for_recorded_sources'],report['issues'])
        self.assertEqual(source.snapshot(old_tables),before)
        self.assertTrue(validate_integrity(self.office))

    def test_nfkc_whitespace_cash_identity_blocks_different_original_across_writers(self):
        original=self.incoming('9.50','0.00','9.50'); payload=self.external_payload(original)
        payload['evidence_key']='ＡＢ  42'; self.post('external_cash',payload)
        other=self.incoming('9.50','0.00','9.50')
        self.assertNotEqual(self.api._receipt_source(self.owner,original['id'])['receipt']['original_sha256'],
                            self.api._receipt_source(self.owner,other['id'])['receipt']['original_sha256'])
        self.failure(409,self.fixture.api.payout,self.owner,self.fixture.payout_body(other,amount='9.50',evidence_reference='ab 42'))
        other_payload=self.external_payload(other); other_payload['evidence_key']='ab 42'
        self.failure(409,self.api.preview,self.owner,self.body('external_cash',other_payload))

    def test_external_payment_original_stays_distinct_from_supplier_payables_after_counterposting(self):
        receipt=self.incoming('9.50','0.00','9.50'); entry=self.post('external_cash',self.external_payload(receipt))
        state=self.fixture.receipt_source(receipt)
        self.assertEqual(state['source_role'],'payment_evidence'); self.assertFalse(state['payable'])
        self.assertIsNone(state['remaining_amount']); self.assertIsNone(state['paid_amount'])
        self.assertEqual(state['external_cash_binding']['active_entry_id'],entry['id'])
        self.post('reverse',dict(entry_id=entry['id']))
        state=self.fixture.receipt_source(receipt)
        self.assertEqual(state['blocked_reason'],'external_cash_evidence'); self.assertIsNone(state['external_cash_binding']['active_entry_id'])
        self.assertEqual(state['external_cash_binding']['reserved_entry_id'],entry['id'])

    def test_duplicate_payment_original_does_not_reveal_private_historical_binding(self):
        private=self.fixture.receipt(project=False)
        self.fixture.finance.review_receipt(self.owner,private['id'],self.fixture.review_body(revision=1,net='9.50',tax='0.00',gross='9.50',issue_date='2026-11-01'))
        self.post('external_cash',self.external_payload(private))
        original=self.office.db.execute('SELECT original FROM business_incoming_receipts WHERE id=?',(private['id'],)).fetchone()[0]
        public=self.fixture.receipt(original=bytes(original))
        self.fixture.finance.review_receipt(self.owner,public['id'],self.fixture.review_body(revision=1,net='9.50',tax='0.00',gross='9.50',issue_date='2026-11-01'))
        for permission in ('accounting.read','finance.read'):self.fixture.grant(self.fixture.tech,permission)
        result=self.fixture.api.receipt_sources(self.fixture.tech)
        self.assertNotIn(public['id'],[row['receipt_id'] for row in result['items']])
        self.assertNotIn(private['id'],[row['receipt_id'] for row in result['items']])

    def test_new_review_of_identical_amounts_can_be_explicitly_corrected_without_rewriting_cash(self):
        receipt=self.incoming(); vat=self.post('input_vat',self.vat_payload(receipt)); event=self.payout(receipt)
        expense=self.post('cash',self.cash_payload(event,'materials'))
        before=self.fixture.snapshot(('business_accounting_cash_events','business_accounting_component_entries'))
        self.fixture.finance.review_receipt(self.owner,receipt['id'],self.fixture.review_body(revision=2,issue_date='2026-11-01',note='New explicit source review'))
        self.post('reverse',dict(entry_id=expense['id'])); self.post('reverse',dict(entry_id=vat['id']))
        self.post('input_vat',self.vat_payload(receipt)); self.post('cash',self.cash_payload(event,'materials'))
        self.assertEqual(self.fixture.snapshot(tuple(before)),before)
        report=self.api.report(self.owner,2026)
        self.assertTrue(report['complete_for_recorded_sources'],report['issues'])
        self.assertEqual(report['totals']['confirmed_expenses'],'59.50')

    def test_fresh_rights_after_lost_ack_and_incomplete_year_coverage(self):
        actor=self.fixture.tech
        for permission in ('accounting.read','accounting.prepare','accounting.admin','finance.read','finance.write'):
            self.fixture.grant(actor,permission)
        receipt=self.incoming(); command=self.command('input_vat',self.vat_payload(receipt))
        result=self.api.confirm(actor,command)
        self.fixture.grant(actor,'finance.read',effect='deny',revision=1)
        self.failure(403,self.api.confirm,actor,command)
        self.assertEqual(self.api.journal(self.owner)['items'][0],result)
        self.configure(bookkeeping_start='2026-10-01')
        report=self.api.report(self.owner,2026)
        self.assertIn('partial_period_profile_coverage',[issue['code'] for issue in report['issues']])
        self.assertIsNone(report['totals']['euer_surplus'])


if __name__=='__main__':unittest.main()
