"""Real original-backed old receivables/payables and their actual cash/EÜR continuation."""
import base64
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
import uuid

from core import Problem
import business_schema
from business_accounting_open_items import OpeningItems,INPUT,TABLES,public_source,validate_integrity,restore_horizon
import test_business_accounting_openings as fixture


class OpeningItemWorkflow(unittest.TestCase):
    def setUp(self):
        self.f=fixture.OpeningWorkflow('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.office=self.f.office;self.owner=self.f.owner;self.euer=self.f.fixture
        self.euer.configure(vat_effective_from='2025-01-01')
        self.api=OpeningItems(self.office,clock=lambda:self.f.now)

    def original(self,key,marker):
        raw=('%PDF-1.4\nSynthetic opening-item '+marker+'\n%%EOF').encode()
        command=dict(request_id=uuid.uuid4().hex,entity_key=key,filename='synthetic.pdf',media_type='application/pdf',content_base64=base64.b64encode(raw).decode())
        value=self.api.upload_original(self.owner,command)
        return dict(original_id=value['id'],sha256=value['sha256'])

    def item(self,key='legacy-a',direction='receivable',prior=False):
        invoice=self.original(key,'invoice '+key);cutover=self.original(key,'cutover '+key)
        payments=[dict(date='2025-12-20',reference='Original old part',gross='39.67',net='33.34',tax='6.33',proof=cutover)] if prior else []
        return dict(status='active',external_system='Legacy system',external_id=key,direction=direction,counterparty_key='customer-'+key,counterparty_name='Synthetic counterparty',invoice_number='OLD-'+key,
                    invoice_date='2025-11-10',service_date='2025-11-10',invoice_received_date='2025-11-11',currency='EUR',rate='19',category='sales' if direction=='receivable' else 'materials',
                    net='100.00',tax='19.00',gross='119.00',prior_payments=payments,invoice_proof=invoice,cutover_proof=cutover,history_through='2025-12-31',
                    prior_input_vat=None if direction=='receivable' else dict(amount='19.00',entitlement_date='2025-11-11',declared_period='2025-11',deducted_on='2025-12-10',proof=self.original(key,'old full VAT deduction '+key)),scope_confirmed=True)

    def body(self,operation,key,payload):
        state=self.api.state(self.owner)
        return dict(expected_revision=state['revision'],state_hash=state['state_hash'],entity_key=key,profile_ref=state['profile_ref'],operation=operation,payload=payload,reason='Synthetic original and complete payment history reviewed')

    def save(self,operation,key,payload):
        body=self.body(operation,key,payload);preview=self.api.preview(self.owner,body)
        command=dict(body,request_id=uuid.uuid4().hex,confirmation=True,preview_hash=preview['preview_hash'])
        return self.api.confirm(self.owner,command),command

    def payment(self,item,amount='119.00',day='2026-02-15',key=None,proof=None,reference=None):
        key=key or uuid.uuid4().hex
        payload=dict(status='active',item_key=item['entity_key'],item_id=item['id'],item_hash=item['content_hash'],date=day,amount=amount,
                     account_id=self.f.account['id'],account_revision=1,evidence_reference=reference or 'Actual bank transfer '+key,
                     proof=proof or self.original(item['entity_key'],'actual transfer '+key))
        return self.save('payment',key,payload)

    def classify(self,payment):
        source=public_source(self.office,payment['entity_key'])
        return self.euer.post('opening_item_cash',dict(payment_id=source['id'],revision=source['revision'],source_hash=source['source_hash'],net_account='4400' if source['direction']=='in' else '5400',tax_account='3806' if source['direction']=='in' else '1406'))

    def reject(self,status,call,*args,**kwargs):
        with self.assertRaises(Problem) as caught:call(*args,**kwargs)
        self.assertEqual(caught.exception.status,status,caught.exception.message)
        return caught.exception

    def test_receivable_real_remainder_only_no_reissue_double_tax_or_changed_export(self):
        export=self.euer.post('export',dict(year=2026));artifact=self.euer.api.exported(self.owner,export['id'])
        counts={t:self.office.db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('business_documents','business_incoming_receipts','business_payments','business_accounting_cash_events')}
        item,command=self.save('item','legacy-a',self.item(prior=True))
        self.assertEqual(self.api.state(self.owner)['items'][0]['remaining'],'79.33')
        self.assertEqual(self.euer.api.report(self.owner,2026)['totals']['confirmed_income'],'0.00')
        first,_=self.payment(item,'39.67');self.classify(first)
        final,_=self.payment(item,'39.66',day='2026-03-15');self.classify(final)
        self.assertEqual((first['details']['net'],first['details']['tax'],final['details']['net'],final['details']['tax']),('33.33','6.34','33.33','6.33'))
        report=self.euer.api.report(self.owner,2026)
        self.assertEqual((report['totals']['confirmed_income'],report['totals']['confirmed_output_vat']),('79.33','12.67'))
        self.assertEqual(self.api.state(self.owner)['items'][0]['remaining'],'0.00')
        self.assertEqual(counts,{t:self.office.db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in counts})
        self.assertEqual(self.euer.api.exported(self.owner,export['id']),artifact)
        self.assertEqual(self.api.confirm(self.owner,command),item)
        self.assertTrue(validate_integrity(self.office));self.assertTrue(business_schema.validate_integrity(self.office))

    def test_payable_full_old_vat_deduction_and_actual_new_cash_expense(self):
        item,_=self.save('item','supplier-a',self.item('supplier-a','payable'))
        self.assertEqual(self.euer.api.report(self.owner,2026)['totals']['confirmed_expenses'],'0.00')
        payment,_=self.payment(item);entry=self.classify(payment);report=self.euer.api.report(self.owner,2026)
        self.assertEqual((report['totals']['confirmed_expenses'],report['totals']['confirmed_input_vat']),('119.00','0.00'))
        self.assertEqual([(p['ledger'],p['category'],p['amount']) for p in entry['postings']],[('euer','materials','-100.00'),('euer','paid_input_vat','-19.00')])
        self.assertEqual(sum(1 for e in self.euer.api._ledger()['entries'] if e['operation']=='input_vat'),0)

    def test_payment_void_requires_euer_counterposting_then_corrected_exact_source(self):
        item,_=self.save('item','legacy-a',self.item());payment,oldcommand=self.payment(item,'59.50');posted=self.classify(payment)
        void=dict(payment['payload'],status='void')
        self.reject(409,self.api.preview,self.owner,self.body('payment',payment['entity_key'],void))
        self.euer.post('reverse',dict(entry_id=posted['id']))
        voided,_=self.save('payment',payment['entity_key'],void)
        self.assertEqual(self.euer.api.report(self.owner,2026)['cash_movements'],[])
        corrected,_=self.save('payment',payment['entity_key'],dict(payment['payload'],amount='119.00'))
        self.classify(corrected)
        self.assertEqual(self.euer.api.report(self.owner,2026)['totals']['confirmed_income'],'119.00')
        self.assertEqual(self.api.confirm(self.owner,oldcommand),payment)
        self.assertEqual(public_source(self.office,payment['entity_key'],1)['gross'],'59.50')
        self.assertEqual(len(self.api.history(self.owner,payment['entity_key'])['items']),3)

    def test_prior_cents_open_vat_unsupported_period_and_overpayment_are_blocked(self):
        bad=self.item(prior=True);bad['prior_payments'][0].update(net='33.33',tax='6.34')
        self.reject(409,self.api.preview,self.owner,self.body('item','legacy-a',bad))
        payable=self.item('supplier-a','payable');payable['prior_input_vat']['amount']='0.00'
        self.reject(409,self.api.preview,self.owner,self.body('item','supplier-a',payable))
        item,_=self.save('item','legacy-a',self.item(prior=True))
        self.reject(409,self.payment,item,'79.34')
        self.reject(409,self.payment,item,'1.00','2025-12-31')

    def test_original_identity_and_payment_proof_cannot_be_renamed_or_reused(self):
        item,_=self.save('item','legacy-a',self.item());other=self.item('legacy-b')
        other.update(external_system=item['payload']['external_system'],external_id=item['payload']['external_id'])
        self.reject(409,self.api.preview,self.owner,self.body('item','legacy-b',other))
        first,_=self.payment(item,'59.50')
        self.reject(409,self.payment,item,'59.50',proof=first['payload']['proof'])
        self.reject(409,self.payment,item,'59.50',proof=item['payload']['invoice_proof'])
        original=self.api._original(item['payload']['invoice_proof']['original_id'])[1]
        self.reject(409,self.euer.fixture.finance.capture_receipt,self.owner,dict(request_id=uuid.uuid4().hex,filename='duplicate.pdf',media_type='application/pdf',original_base64=base64.b64encode(original).decode(),project_id=None,note='Duplicate old trade original'))

    def test_stale_profile_and_rights_block_new_work_but_keep_original_acceptance(self):
        item,command=self.save('item','legacy-a',self.item());self.euer.configure(vat_effective_from='2024-01-01')
        self.assertEqual(self.api.confirm(self.owner,command),item)
        self.reject(409,self.payment,item)
        self.reject(403,self.api.state,self.euer.fixture.tech)

    def test_late_failure_is_atomic_and_financial_restore_gate_precedes_replay(self):
        body=self.body('item','legacy-a',self.item());preview=self.api.preview(self.owner,body);command=dict(body,request_id=uuid.uuid4().hex,preview_hash=preview['preview_hash'],confirmation=True)
        with patch.object(self.office,'audit',side_effect=RuntimeError('Synthetic interrupted acceptance')):
            with self.assertRaises(RuntimeError):self.api.confirm(self.owner,command)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM '+TABLES[1]).fetchone()[0],0)
        entry=self.api.confirm(self.owner,command)
        with patch('business_accounting.Accounting._write_gate',side_effect=Problem(409,'Synthetic restore pending')):self.reject(409,self.api.confirm,self.owner,command)
        self.assertEqual(restore_horizon(self.office)['table_counts'][TABLES[1]],1)

    def test_real_bank_matching_and_liquidity_share_exact_single_money_source(self):
        from business_bank_reconciliation import BankReconciliation,HEADERS,validate_integrity as bank_integrity
        self.f.save(amount='1000.00');self.f.bank_statement()
        item,_=self.save('item','legacy-a',self.item());payment,_=self.payment(item);self.classify(payment)
        self.assertEqual(self.f.api.liquidity(self.owner,'2026-02-28')['balance_total'],'1119.00')
        bank=BankReconciliation(self.office,clock=lambda:self.f.now)
        row=['SYN-OLD-1','2026-02-15','2026-02-15','119.00','EUR','Synthetic payer','Actual old remainder']
        raw=(';'.join(HEADERS)+'\n'+';'.join(row)+'\n').encode()
        body=dict(account_id=self.f.account['id'],account_revision=1,bank_revision=1,statement_reference='Synthetic February',period_from='2026-02-01',period_to='2026-02-28',opening_balance='1000.00',closing_balance='1119.00',filename='synthetic.csv',delimiter=';',content_base64=base64.b64encode(raw).decode(),complete_statement_confirmed=True)
        preview=bank.preview_import(self.owner,body);self.assertTrue(preview['can_import'])
        saved=bank.import_statement(self.owner,dict(body,request_id=uuid.uuid4().hex,confirmation=True,preview_hash=preview['preview_hash']))
        transaction=bank.statement(self.owner,saved['statement']['id'])['lines'][0]['transaction_id'];candidate=bank.candidates(self.owner,transaction)['items'][0]['source']
        self.assertEqual((candidate['source_kind'],candidate['source_id'],candidate['amount']),('opening_item_cash',payment['entity_key'],'119.00'))
        match=dict(revision=0,links=[dict(source_kind=candidate['source_kind'],source_id=candidate['source_id'],source_hash=candidate['source_hash'],amount='119.00',date_difference_reason='')],reason='Synthetic original amount and bank movement checked')
        preview=bank.preview_match(self.owner,transaction,match);accepted=bank.save_match(self.owner,transaction,dict(match,request_id=uuid.uuid4().hex,confirmation=True,preview_hash=preview['preview_hash']))
        self.assertTrue(accepted['payload']['complete']);self.assertTrue(bank_integrity(self.office))
        posted=self.euer.api._ledger()['active']['opening_item_cash:'+payment['entity_key']];self.euer.post('reverse',dict(entry_id=posted['id']))
        self.reject(409,self.api.preview,self.owner,self.body('payment',payment['entity_key'],dict(payment['payload'],status='void')))

    def test_closed_period_and_under_year_profile_never_become_complete_old_year(self):
        item,_=self.save('item','legacy-a',self.item());payment,_=self.payment(item);self.classify(payment)
        close=dict(period='2026-02',action='close',expected_period_revision=0,attestation=dict(bank_reconciled=True,originals_complete=True,special_cases_reviewed=True))
        self.euer.post('period',close)
        self.reject(409,self.api.preview,self.owner,self.body('payment',payment['entity_key'],dict(payment['payload'],status='void')))
        self.reject(409,self.api.preview,self.owner,self.body('item','legacy-a',item['payload']))
        self.euer.configure(vat_effective_from='2025-01-01',bookkeeping_start='2026-11-01')
        report=self.euer.api.report(self.owner,2026)
        self.assertIn('partial_period_profile_coverage',[issue['code'] for issue in report['issues']])

    def test_independent_7_percent_and_prior_supplier_split_references(self):
        from pathlib import Path
        expected=json.loads((Path(__file__).resolve().parents[1]/'docs/evidence/altposten-quellen-2026-11-04/expected-cases.json').read_text())
        refs={case['id']:case for case in expected['numerical_cases']}
        item=self.item('seven',prior=True);item.update(rate='7',tax='7.00',gross='107.00');item['prior_payments'][0].update(net='50.00',tax='3.50',gross='53.50')
        accepted,_=self.save('item','seven',item);payment,_=self.payment(accepted,'53.50');self.classify(payment)
        source=public_source(self.office,payment['entity_key']);reference=refs['F02']['payments'][0]
        self.assertEqual([int(source[key].replace('.','')) for key in ('net','tax','gross')],[reference['euer_net'],reference['euer_vat'],reference['cash']])
        item=self.item('supplier-split','payable',prior=True);item.update(net='1000.00',tax='190.00',gross='1190.00');item['prior_input_vat']['amount']='190.00';item['prior_payments'][0].update(net='200.00',tax='38.00',gross='238.00')
        accepted,_=self.save('item','supplier-split',item)
        for amount,day,reference in zip(('357.00','595.00'),('2026-02-15','2026-03-15'),refs['F04']['payments']):
            payment,_=self.payment(accepted,amount,day);entry=self.classify(payment)
            self.assertEqual([int(p['amount'].replace('.','')) for p in entry['postings']],[reference['euer_net'],reference['euer_vat']])
        self.assertEqual(self.euer.api.report(self.owner,2026)['totals']['confirmed_input_vat'],'0.00')


if __name__=='__main__':unittest.main()
