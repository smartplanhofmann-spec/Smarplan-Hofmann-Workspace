"""Original-backed yearly carryover through the actual EÜR and money journals."""
import base64
from copy import deepcopy
import unittest
import uuid
from core import Problem
from business_accounting_year_openings import YearValues,public_source,validate_integrity,TABLES
import test_accounting_year_opening_rules as rule_fixture

class YearOpeningWorkflow(unittest.TestCase):
    def setUp(self):
        self.rules=rule_fixture.YearOpeningRules('runTest');self.rules.setUp();self.addCleanup(self.rules.doCleanups)
        self.f=self.rules.f;self.office=self.f.office;self.owner=self.f.owner
        self.api=YearValues(self.office,clock=lambda:self.f.f.now)
        self.old=next(e for e in self.f.api._ledger()['current'].values() if e['operation']=='item')
        source=dict(kind='opening_item',entry_id=self.old['id'],entry_hash=self.old['content_hash'],accounts=self.rules.source['accounts'],cash_entry_keys=self.rules.source['cash_entry_keys'],vat_entry_key=self.rules.source['vat_entry_key'])
        self.payload=dict(status='active',coverage=self.rules.coverage,sources=[source],controls=self.rules.controls,
            ledger_proof=self.original('Independent old whole journal with reviewed control totals'),
            attestations=dict(continuous_method=True,original_journal_complete=True,no_unsupported_values=True))

    def original(self,marker):
        raw=('%PDF-1.4\nSynthetic year original '+marker+'\n%%EOF').encode()
        value=self.api.upload_original(self.owner,dict(request_id=uuid.uuid4().hex,entity_key='2026',filename='historical.pdf',media_type='application/pdf',content_base64=base64.b64encode(raw).decode()))
        return dict(original_id=value['id'],sha256=value['sha256'])

    def body(self,payload=None):
        state=self.api.state(self.owner)
        return dict(expected_revision=state['revision'],state_hash=state['state_hash'],entity_key='2026',profile_ref=state['profile_ref'],operation='year_values',payload=payload or self.payload,reason='Original historical journal and actual old payments reviewed')

    def save(self,payload=None):
        body=self.body(payload);preview=self.api.preview(self.owner,body)
        command=dict(body,request_id=uuid.uuid4().hex,preview_hash=preview['preview_hash'],confirmation=True)
        return self.api.confirm(self.owner,command),command

    def classify(self,entry):
        source=public_source(self.office,entry['entity_key'])
        return self.f.euer.post('opening_year_values',dict(year=source['id'],revision=source['revision'],source_hash=source['source_hash']))

    def test_old_half_plus_actual_new_half_yields_annual_119_with_only_59_50_cash(self):
        opening,_=self.f.f.save(amount='1000.00')
        export=self.f.euer.post('export',dict(year=2026));frozen=self.f.euer.api.exported(self.owner,export['id'])
        counts={t:self.office.db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('business_accounting_cash_events','business_accounting_opening_events','business_incoming_receipts','business_documents')}
        entry,command=self.save();posted=self.classify(entry)
        payment,_=self.f.payment(self.old,'59.50',day='2026-11-01');self.f.classify(payment)
        report=self.f.euer.api.report(self.owner,2026)
        self.assertEqual((report['totals']['confirmed_expenses'],report['totals']['confirmed_input_vat']),('119.00','19.00'))
        self.assertEqual(report['totals']['euer_surplus'],'-119.00',report['issues'])
        self.assertEqual([m['amount'] for m in report['cash_movements']],['59.50'])
        liquidity=self.f.f.api.liquidity(self.owner,'2026-11-04')
        self.assertEqual(liquidity['accounts'][0]['outflows'],'59.50')
        self.assertEqual(liquidity['accounts'][0]['calculated_balance'],'940.50')
        self.assertEqual(self.f.f.api._ledger()['current'][self.f.f.account['id']],opening)
        november=self.f.euer.api._report(self.owner,2026,self.f.euer.api._ledger(),month='2026-11')
        self.assertEqual((november['totals']['confirmed_expenses'],november['totals']['confirmed_input_vat']),('59.50','0.00'))
        self.assertEqual(counts,{t:self.office.db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in counts})
        self.assertEqual(self.api.confirm(self.owner,command),entry)
        self.assertEqual(self.f.euer.api.exported(self.owner,export['id']),frozen)
        self.assertEqual([p['date'] for p in posted['postings']],['2026-08-20','2026-08-20','2026-06-11'])
        self.assertTrue(validate_integrity(self.office))
        current_export=self.f.euer.post('export',dict(year=2026));self.f.euer.api.exported(self.owner,current_export['id'])

    def test_original_known_values_and_independent_journal_are_required(self):
        for mutate in (lambda p:p.update(sources=[],controls=[]),lambda p:p.update(ledger_proof=self.old['payload']['invoice_proof']),lambda p:p['controls'][0].update(amount='-50.01')):
            payload=deepcopy(self.payload);mutate(payload)
            with self.subTest(payload=payload),self.assertRaises(Problem):self.api.preview(self.owner,self.body(payload))

    def test_active_year_dependency_requires_exact_counterposting_and_preserves_old_receipts(self):
        entry,command=self.save();posted=self.classify(entry);export=self.f.euer.post('export',dict(year=2026));frozen=self.f.euer.api.exported(self.owner,export['id'])
        void=dict(self.payload,status='void')
        with self.assertRaises(Problem):self.api.preview(self.owner,self.body(void))
        with self.assertRaises(Problem):self.f.save('item',self.old['entity_key'],self.old['payload'])
        self.f.euer.post('reverse',dict(entry_id=posted['id']));voided,_=self.save(void)
        self.assertEqual(voided['payload']['status'],'void')
        self.assertEqual(self.api.confirm(self.owner,command),entry)
        self.assertEqual(self.f.euer.api.exported(self.owner,export['id']),frozen)
        self.assertTrue(any(i['code']=='partial_period_profile_coverage' for i in self.f.euer.api.report(self.owner,2026)['issues']))

    def test_partial_coverage_remains_partial_and_old_vat_stays_in_june(self):
        payload=deepcopy(self.payload);payload['coverage']={'from':'2026-08-01','through':'2026-10-31'};payload['controls']=payload['controls'][:2]
        entry,_=self.save(payload);self.classify(entry);report=self.f.euer.api.report(self.owner,2026)
        self.assertIsNone(report['totals']['euer_surplus']);self.assertEqual(report['totals']['confirmed_input_vat'],'0.00')
        self.assertTrue(any(i['code']=='partial_period_profile_coverage' for i in report['issues']))

    def test_fully_paid_trade_has_no_open_item_no_cash_and_original_identity_cannot_be_aliased(self):
        payload=deepcopy(self.payload);record=deepcopy(self.old['payload'])
        record.update(external_id='closed-original',counterparty_key='other-supplier',invoice_number='CLOSED-1')
        record['invoice_proof']=self.original('closed supplier original');record['cutover_proof']=self.original('closed paid proof')
        record['prior_input_vat']['proof']=self.original('closed already deducted VAT')
        record['prior_payments'][0].update(gross='119.00',net='100.00',tax='19.00',proof=record['cutover_proof'])
        source=dict(kind='closed_trade',record=record,accounts=self.rules.source['accounts'],cash_entry_keys=['CLOSED-CASH-1'],vat_entry_key='CLOSED-VAT-1')
        payload['sources'].append(source)
        for row,amount in zip(payload['controls'],('-150.00','-28.50','-38.00')):row['amount']=amount
        entry,_=self.save(payload);self.classify(entry);report=self.f.euer.api.report(self.owner,2026)
        self.assertEqual((report['totals']['confirmed_expenses'],report['totals']['confirmed_input_vat']),('178.50','38.00'))
        self.assertEqual(report['cash_movements'],[]);self.assertEqual(len(self.f.api.state(self.owner)['items']),1)
        duplicate=deepcopy(source);duplicate['record']['external_id']='new alias';duplicate['record']['invoice_proof']=self.original('rescan of same economic invoice')
        bad=deepcopy(payload);bad['sources'].append(duplicate)
        with self.assertRaises(Problem):self.api.preview(self.owner,self.body(bad))
        # Different scan and external key cannot turn the closed original into a new debt.
        candidate=self.f.item('attempted-open','payable');candidate.update(counterparty_key=record['counterparty_key'],invoice_number=record['invoice_number'],invoice_date=record['invoice_date'],service_date=record['service_date'],invoice_received_date=record['invoice_received_date'],history_through='2026-10-31')
        candidate['prior_input_vat'].update(entitlement_date='2026-06-11',declared_period='2026-06',deducted_on='2026-07-10')
        with self.assertRaises(Problem):self.f.save('item','attempted-open',candidate)
        raw=self.api._original(record['invoice_proof']['original_id'])[1]
        with self.assertRaises(Problem):self.f.euer.fixture.finance.capture_receipt(self.owner,dict(request_id=uuid.uuid4().hex,filename='again.pdf',media_type='application/pdf',original_base64=base64.b64encode(raw).decode(),project_id=None,note='Duplicate imported year original'))

    def test_known_old_payment_cannot_disappear_behind_new_empty_source_revision(self):
        entry,_=self.save();self.classify(entry)
        changed=deepcopy(self.old['payload']);changed['prior_payments']=[]
        with self.assertRaises(Problem):self.f.save('item',self.old['entity_key'],changed)

    def test_missing_original_receipt_and_rights_restore_gate_block_reads_and_replay(self):
        from unittest.mock import patch
        entry,command=self.save()
        with self.assertRaises(Problem) as denied:self.api.state(self.f.euer.fixture.tech)
        self.assertEqual(denied.exception.status,403)
        with patch('business_accounting.Accounting._write_gate',side_effect=Problem(409,'Synthetic restore reconciliation pending')):
            with self.assertRaises(Problem):self.api.confirm(self.owner,command)
        self.office.db.execute('DROP TRIGGER '+TABLES[2]+'_delete_guard')
        original=self.payload['ledger_proof']['original_id']
        self.office.db.execute("DELETE FROM "+TABLES[2]+" WHERE operation='original' AND result_json LIKE ?",('%'+original+'%',))
        for method,args in ((self.api.state,(self.owner,)),(self.api.confirm,(self.owner,command)),(self.api.original,(self.owner,original))):
            with self.subTest(method=method.__name__),self.assertRaises(Problem):method(*args)

    def test_actual_closed_old_period_requires_reopening_even_for_empty_correction(self):
        entry,command=self.save();posted=self.classify(entry)
        self.f.euer.post('period',dict(period='2026-06',action='close',expected_period_revision=0,attestation=dict(bank_reconciled=True,originals_complete=True,special_cases_reviewed=True)))
        with self.assertRaises(Problem):self.f.euer.post('reverse',dict(entry_id=posted['id']))
        self.f.euer.post('period',dict(period='2026-06',action='reopen',expected_period_revision=1,attestation=dict(bank_reconciled=True,originals_complete=True,special_cases_reviewed=True)))
        self.f.euer.post('reverse',dict(entry_id=posted['id']));self.save(dict(self.payload,status='void'))
        self.assertEqual(self.api.confirm(self.owner,command),entry)

    def test_profile_revision_keeps_original_ack_and_requires_fresh_source_review(self):
        entry,command=self.save();self.f.euer.configure(vat_effective_from='2024-01-01',bookkeeping_start='2026-11-01')
        self.assertEqual(self.api.confirm(self.owner,command),entry)
        with self.assertRaises(Problem):self.classify(entry)
        with self.assertRaises(Problem):self.api.preview(self.owner,self.body())
        # Void binds the old profile, while removal still requires fresh rights/gates.
        body=self.body(dict(self.payload,status='void'));body['profile_ref']=entry['profile_ref'];preview=self.api.preview(self.owner,body)
        self.api.confirm(self.owner,dict(body,request_id=uuid.uuid4().hex,preview_hash=preview['preview_hash'],confirmation=True))

    def test_explicit_independent_zero_journal_is_allowed_only_without_known_old_values(self):
        import test_business_accounting_open_items as fixtures
        f=fixtures.OpeningItemWorkflow('runTest');f.setUp();self.addCleanup(f.doCleanups)
        f.euer.configure(vat_effective_from='2025-01-01',bookkeeping_start='2026-11-01')
        helper=YearOpeningWorkflow('runTest');helper.f=f;helper.office=f.office;helper.owner=f.owner;helper.api=YearValues(f.office,clock=lambda:f.f.now)
        helper.payload=dict(status='active',coverage={'from':'2026-01-01','through':'2026-10-31'},sources=[],controls=[],ledger_proof=helper.original('Independent whole old zero journal and explicit zero control statement'),attestations=dict(continuous_method=True,original_journal_complete=True,no_unsupported_values=True))
        entry,_=helper.save();posted=helper.classify(entry);report=f.euer.api.report(f.owner,2026)
        self.assertTrue(report['complete_for_recorded_sources']);self.assertEqual(report['totals']['euer_surplus'],'0.00');self.assertEqual(posted['postings'],[]);self.assertEqual(report['cash_movements'],[])
        record=f.item('late-old-source','payable');record.update(invoice_date='2026-06-10',service_date='2026-06-10',invoice_received_date='2026-06-11',history_through='2026-10-31')
        record['prior_input_vat'].update(entitlement_date='2026-06-11',declared_period='2026-06',deducted_on='2026-07-10')
        with self.assertRaises(Problem):f.save('item','late-old-source',record)

    def test_late_acceptance_failure_is_atomic_then_exact_request_is_recoverable(self):
        from unittest.mock import patch
        body=self.body();preview=self.api.preview(self.owner,body);command=dict(body,request_id=uuid.uuid4().hex,preview_hash=preview['preview_hash'],confirmation=True)
        before={t:self.office.db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in TABLES}
        with patch.object(self.office,'audit',side_effect=RuntimeError('Synthetic interrupted final audit')):
            with self.assertRaises(RuntimeError):self.api.confirm(self.owner,command)
        self.assertEqual(before,{t:self.office.db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in TABLES})
        entry=self.api.confirm(self.owner,command);self.assertEqual(self.api.confirm(self.owner,command),entry)

if __name__=='__main__':unittest.main()
