"""Actual synthetic finance sources, exact bank files and explicit reconciliation."""
import base64
import csv
import io
import json
import sqlite3
import unittest
import uuid

import test_business_accounting as accounting
from business_bank_reconciliation import BankReconciliation,HEADERS,TABLES,parse_statement,validate_integrity,restore_horizon,period_closure_proof,validate_period_closure_proof,_sha
from business_accounting_euer import EuerAccounting
from business_accounting_profile import AccountingPreparationProfile
from business_schema import set_mode
from core import Problem,canonical


class BankTests(unittest.TestCase):
    def setUp(self):
        self.fixture=accounting.AccountingTests('runTest');self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.office=self.fixture.office;self.owner=self.fixture.owner;self.bank=BankReconciliation(self.office,clock=self.fixture.clock)
        self.account=self.fixture.account;self.binding=self.bank.save_account(self.owner,self.account_body())

    def req(self,**data):return dict(request_id=uuid.uuid4().hex,**data)
    def error(self,status,call,*args,**kwargs):
        with self.assertRaises(Problem) as caught:call(*args,**kwargs)
        self.assertEqual(caught.exception.status,status,caught.exception.message);return caught.exception
    def account_body(self,**changes):return self.req(**(dict(account_id=self.account['id'],account_revision=1,revision=0,iban='DE89370400440532013000',label='Synthetic bank',active=True,coverage_from='2026-01-01',coverage_to=None,reason='')|changes))
    def rows(self,*amounts,day='2026-11-02',prefix='TX',reference='Synthetic receipt'):
        return [dict(transaction_id=prefix+str(index+1),booking_date=day,value_date=day,amount=amount,currency='EUR',counterparty='Synthetic payer',reference=reference) for index,amount in enumerate(amounts)]
    def file(self,rows):
        stream=io.StringIO(newline='');writer=csv.writer(stream,delimiter=';',lineterminator='\r\n');writer.writerow(HEADERS)
        for row in rows:writer.writerow([row.get(key,'') for key in HEADERS])
        return stream.getvalue().encode('utf-8')
    def import_body(self,rows,**changes):
        total=sum(int(row['amount'].replace('.','')) for row in rows);closing=('' if total>=0 else '-')+str(abs(total)//100)+'.'+str(abs(total)%100).zfill(2)
        return dict(account_id=self.account['id'],account_revision=1,bank_revision=self.binding['revision'],statement_reference='SYN-'+uuid.uuid4().hex,period_from='2026-11-01',period_to='2026-11-30',opening_balance='0.00',closing_balance=closing,filename='synthetic.csv',delimiter=';',content_base64=base64.b64encode(self.file(rows)).decode(),complete_statement_confirmed=True)|changes
    def save_statement(self,rows,**changes):
        body=self.import_body(rows,**changes);preview=self.bank.preview_import(self.owner,body)
        if preview['identity_checks']:
            body['distinct_transaction_confirmations']={item['external_id']:'Synthetic fixture: two genuinely separate bank transactions checked' for item in preview['identity_checks']};preview=self.bank.preview_import(self.owner,body)
        self.assertTrue(preview['can_import'],preview['errors'])
        command=self.req(**body,preview_hash=preview['preview_hash'],confirmation=True);return self.bank.import_statement(self.owner,command),command
    def cash(self,amount='119.00',day='2026-11-02'):
        payment=self.fixture.payment(amount=amount)
        return self.fixture.api.import_payment(self.owner,self.fixture.import_body(payment,cash_date=day))
    def link(self,transaction_id,source_id,amount,reason=''):
        source=next(item['source'] for item in self.bank.candidates(self.owner,transaction_id)['items'] if item['source']['source_id']==source_id)
        return dict(source_kind=source['source_kind'],source_id=source_id,source_hash=source['source_hash'],amount=amount,date_difference_reason=reason)
    def match(self,transaction_id,links,**changes):
        body=dict(revision=self.bank._match(transaction_id)['revision'],links=links,reason='Synthetic explicit reconciliation')|changes
        preview=self.bank.preview_match(self.owner,transaction_id,body);command=self.req(**body,preview_hash=preview['preview_hash'],confirmation=True)
        return self.bank.save_match(self.owner,transaction_id,command),command
    def report(self,statements,period='2026-11'):
        body=dict(account_id=self.account['id'],period=period,statement_ids=[item['statement']['id'] for item in statements],reason='Synthetic complete scope reviewed')
        preview=self.bank.preview_reconciliation(self.owner,body);command=self.req(**body,preview_hash=preview['preview_hash'],confirmation=True)
        return self.bank.save_reconciliation(self.owner,command),command
    def configure(self):
        api=AccountingPreparationProfile(self.office);state=api.state(self.owner)
        body=dict(expected_revision=state['revision'],state_hash=state['state_hash'],reason='Synthetic declared facts',evidence_reference='Synthetic owner review',profile=dict(legal_form='sole_proprietorship',accounting_method='euer',vat_regime='regular',vat_timing='cash',vat_effective_from='2026-01-01',bookkeeping_start='2026-01-01'))
        preview=api.preview(self.owner,body);api.confirm(self.owner,self.req(**body,confirmation=True,preview_hash=preview['preview_hash']))

    def test_header_only_statement_is_zero_activity_but_zero_bytes_and_zero_entries_fail(self):
        rows,errors=parse_statement(self.file([]),';','2026-11-01','2026-11-30');self.assertEqual((rows,errors),([],[]))
        self.error(400,parse_statement,b'',';','2026-11-01','2026-11-30')
        preview=self.bank.preview_import(self.owner,self.import_body(self.rows('0.00')));self.assertFalse(preview['can_import'])
        statement,_=self.save_statement([]);report,_=self.report([statement]);self.assertTrue(report['record']['payload']['complete']);self.assertEqual(report['record']['payload']['bank_rows'],[])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_bank_transactions').fetchone()[0],0)
        self.assertTrue(validate_integrity(self.office))

    def test_identical_header_only_bytes_allow_separate_confirmed_zero_activity_months(self):
        november,_=self.save_statement([])
        december,_=self.save_statement([],period_from='2026-12-01',period_to='2026-12-31')
        self.assertNotEqual(november['statement']['id'],december['statement']['id'])
        self.assertEqual(november['statement']['file_sha256'],december['statement']['file_sha256'])
        report,_=self.report([december],period='2026-12');self.assertTrue(report['record']['payload']['complete'])
        overlapping=self.bank.preview_import(self.owner,self.import_body([],period_from='2026-11-15',period_to='2026-12-15'));self.assertFalse(overlapping['can_import'])
        self.assertTrue(validate_integrity(self.office))

    def test_explicit_opening_and_closing_dates_bound_statement_and_month_coverage(self):
        self.account=self.fixture.api.create_account(self.owner,self.fixture.req(code='SECOND',name='Synthetic new bank',kind='bank'))
        self.binding=self.bank.save_account(self.owner,self.account_body(iban='DE12500105170648489890',coverage_from='2026-11-15',coverage_to='2026-11-30'))
        self.error(400,self.bank.preview_import,self.owner,self.import_body([]))
        statement,_=self.save_statement([],period_from='2026-11-15');report,_=self.report([statement])
        self.assertTrue(report['record']['payload']['complete']);self.assertEqual(report['record']['payload']['coverage_from'],'2026-11-15')
        self.error(400,self.report,[statement],period='2026-12')
        self.error(409,self.bank.save_account,self.owner,self.account_body(revision=1,iban='DE12500105170648489890',coverage_from='2026-11-15',coverage_to='2026-11-20',reason='Cannot exclude an existing original'))
        self.assertTrue(validate_integrity(self.office))

    def test_invalid_rows_dates_currencies_balances_and_controls_never_partially_import(self):
        for changes in ({'closing_balance':'119.01'},{'complete_statement_confirmed':False},{'filename':'../synthetic.csv'}):
            body=self.import_body(self.rows('119.00'),**changes)
            if 'closing_balance' in changes:self.assertFalse(self.bank.preview_import(self.owner,body)['can_import'])
            else:self.error(400,self.bank.preview_import,self.owner,body)
        for change in ({'booking_date':'2026-02-29'},{'currency':'USD'},{'amount':'1e2'},{'reference':'bad\x00'}):
            rows=self.rows('10.00','20.00');rows[1].update(change);body=self.import_body(self.rows('10.00','20.00'));body['content_base64']=base64.b64encode(self.file(rows)).decode();preview=self.bank.preview_import(self.owner,body)
            self.assertFalse(preview['can_import']);self.error(409,self.bank.import_statement,self.owner,self.req(**body,preview_hash=preview['preview_hash'],confirmation=True))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_bank_statements').fetchone()[0],0)

    def test_unchanged_original_nonce_and_cross_statement_ids_do_not_duplicate_transactions(self):
        rows=self.rows('119.00');statement,command=self.save_statement(rows)
        self.assertEqual(self.bank.import_statement(self.owner,command),statement)
        original,mime=self.bank.original(self.owner,statement['statement']['id']);self.assertEqual(original,self.file(rows));self.assertIn('csv',mime)
        other=self.import_body(rows,period_from='2026-11-02',period_to='2026-11-02');other['content_base64']=base64.b64encode(b'\xef\xbb\xbf'+self.file(rows)).decode()
        preview=self.bank.preview_import(self.owner,other);self.assertEqual(len(preview['duplicates']),1)
        second=self.bank.import_statement(self.owner,self.req(**other,preview_hash=preview['preview_hash'],confirmation=True));self.assertNotEqual(second['statement']['id'],statement['statement']['id'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_bank_transactions').fetchone()[0],1)
        changed=self.import_body(self.rows('118.00'));self.assertFalse(self.bank.preview_import(self.owner,changed)['can_import'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_payments').fetchone()[0],0)
        self.assertTrue(validate_integrity(self.office))

    def test_many_to_many_matches_preserve_core_money_and_both_capacities(self):
        first=self.cash('119.00');second=self.cash('81.00');statement,command=self.save_statement(self.rows('100.00','100.00'))
        left,right=[line['transaction_id'] for line in statement['lines']]
        before={table:[dict(row) for row in self.office.db.execute('SELECT * FROM '+table)] for table in ('business_payments','business_accounting_cash_events','business_euer_entries')}
        one,_=self.match(left,[self.link(left,first['id'],'100.00')])
        self.error(409,self.match,right,[self.link(right,first['id'],'20.00')])
        two,replay=self.match(right,[self.link(right,first['id'],'19.00'),self.link(right,second['id'],'81.00')]);self.assertTrue(two['payload']['complete'])
        self.assertEqual(self.bank.save_match(self.owner,right,replay),two)
        report,_=self.report([statement]);self.assertTrue(report['record']['payload']['complete'])
        after={table:[dict(row) for row in self.office.db.execute('SELECT * FROM '+table)] for table in before};self.assertEqual(before,after)
        self.assertEqual(self.bank.import_statement(self.owner,command),statement,'Import ACK must not gain later matches')
        self.match(left,[]);self.assertFalse(self.bank.reconciliation(self.owner,report['record']['id'])['current'])
        self.assertEqual(self.bank.history(self.owner,left,{})['items'][-1],one)
        self.assertTrue(validate_integrity(self.office))

    def test_dates_are_explicit_and_source_direction_or_account_is_not_inferred(self):
        event=self.cash('119.00',day='2026-11-01');statement,_=self.save_statement(self.rows('119.00'));transaction_id=statement['lines'][0]['transaction_id']
        self.error(400,self.match,transaction_id,[self.link(transaction_id,event['id'],'119.00')])
        result,_=self.match(transaction_id,[self.link(transaction_id,event['id'],'119.00','Belegter Zahlungsauftrag am Vortag')]);self.assertEqual(result['payload']['links'][0]['source']['date'],'2026-11-01')
        negative,_=self.save_statement(self.rows('-119.00',prefix='NEG'))
        self.assertEqual(self.bank.candidates(self.owner,negative['lines'][0]['transaction_id'])['items'],[])

    def test_historical_report_exports_and_period_reference_survive_later_correction(self):
        event=self.cash();statement,_=self.save_statement(self.rows('119.00',reference='=SUM(1+1)'));transaction_id=statement['lines'][0]['transaction_id']
        self.match(transaction_id,[self.link(transaction_id,event['id'],'119.00')]);report,command=self.report([statement]);report_id=report['record']['id']
        proof=period_closure_proof(self.office,self.owner,'2026-11');self.assertTrue(validate_period_closure_proof(self.office,proof,'2026-11'))
        exports={kind:self.bank.export(self.owner,report_id,kind)[0] for kind in ('json','csv','pdf')}
        for kind,content in exports.items():self.assertEqual(_sha(content),report['exports'][kind]['sha256'])
        self.assertIn(b"'=SUM",exports['csv'])
        self.match(transaction_id,[])
        self.assertTrue(validate_period_closure_proof(self.office,proof,'2026-11'))
        self.error(409,period_closure_proof,self.office,self.owner,'2026-11')
        self.assertEqual(self.bank.save_reconciliation(self.owner,command),report,'Report ACK remains original after source-match change')
        for kind,content in exports.items():self.assertEqual(self.bank.export(self.owner,report_id,kind)[0],content)
        self.assertTrue(validate_integrity(self.office))

    def test_gaps_overlaps_and_saldo_discontinuity_cannot_be_complete(self):
        left,_=self.save_statement([],period_from='2026-11-01',period_to='2026-11-14')
        right_body=self.import_body([],period_from='2026-11-16',opening_balance='5.00',closing_balance='5.00');right_body['content_base64']=base64.b64encode(b'\xef\xbb\xbf'+self.file([])).decode();preview=self.bank.preview_import(self.owner,right_body)
        right=self.bank.import_statement(self.owner,self.req(**right_body,preview_hash=preview['preview_hash'],confirmation=True));report,_=self.report([left,right])
        self.assertFalse(report['record']['payload']['complete']);codes={issue['code'] for issue in report['record']['payload']['issues']}
        self.assertTrue({'statement_coverage_gap_or_overlap','statement_balance_discontinuity'}<=codes)
        self.assertTrue(validate_integrity(self.office))

    def test_fresh_bank_permissions_required_even_for_original_receipt(self):
        tech=self.fixture.tech
        for permission in ('accounting.read','finance.read','bank.read','bank.prepare','accounting.prepare','finance.write'):self.fixture.grant(tech,permission)
        body=self.import_body(self.rows('10.00'));preview=self.bank.preview_import(tech,body);command=self.req(**body,preview_hash=preview['preview_hash'],confirmation=True)
        saved=self.bank.import_statement(tech,command)
        self.fixture.grant(tech,'bank.prepare',effect='deny',revision=1);self.error(403,self.bank.import_statement,tech,command)
        self.assertEqual(self.bank.original(tech,saved['statement']['id'])[0],self.file(self.rows('10.00')))
        self.fixture.grant(tech,'bank.read',effect='deny',revision=1);self.error(403,self.bank.original,tech,saved['statement']['id'])
        self.error(403,self.bank.accounts,self.fixture.other_actor)

    def test_closed_period_rejects_changed_import_or_matches_and_requires_existing_reopen(self):
        self.configure();statement,_=self.save_statement([]);report,_=self.report([statement]);euer=EuerAccounting(self.office)
        def period(action,revision):
            state=euer.state(self.owner);body=dict(operation='period',expected_revision=state['revision'],state_hash=state['state_hash'],payload=dict(period='2026-11',action=action,expected_period_revision=revision,attestation=dict(bank_reconciled=True,originals_complete=True,special_cases_reviewed=True)),reason='Explicit synthetic period action',evidence_reference='Bank report '+report['record']['id'])
            preview=euer.preview(self.owner,body);return euer.confirm(self.owner,self.req(**body,preview_hash=preview['preview_hash'],confirmation=True))
        closed=period('close',0);self.assertEqual(closed['operation'],'period')
        body=self.import_body(self.rows('10.00'));preview=self.bank.preview_import(self.owner,body)
        self.error(409,self.bank.import_statement,self.owner,self.req(**body,preview_hash=preview['preview_hash'],confirmation=True))
        period('reopen',1)
        self.bank.import_statement(self.owner,self.req(**body,preview_hash=preview['preview_hash'],confirmation=True))
        self.assertTrue(validate_integrity(self.office))

    def test_schema_guards_horizon_readonly_and_semantically_forged_money(self):
        event=self.cash();statement,_=self.save_statement(self.rows('119.00'));transaction_id=statement['lines'][0]['transaction_id'];saved,body=self.match(transaction_id,[self.link(transaction_id,event['id'],'119.00')])
        self.report([statement])
        horizon=restore_horizon(self.office);self.assertEqual(set(horizon['table_counts']),set(TABLES));self.assertEqual(horizon['schema_version'],1)
        for table in TABLES:
            with self.assertRaises(sqlite3.IntegrityError):self.office.db.execute('DELETE FROM '+table)
        set_mode(self.office,'legacy');self.assertEqual(self.bank.original(self.owner,statement['statement']['id'])[0],self.file(self.rows('119.00')));self.error(409,self.bank.save_match,self.owner,transaction_id,body);set_mode(self.office,'business')
        forged=json.loads(json.dumps(saved));forged['payload']['links'][0]['source']['amount']='120.00';source=forged['payload']['links'][0]['source'];source['source_hash']=_sha([{key:value for key,value in source.items() if key not in ('source_hash','origin_hash')},source['origin_hash']]);envelope={key:value for key,value in forged.items() if key!='content_hash'}
        self.office.db.execute('DROP TRIGGER business_bank_match_events_update_guard');self.office.db.execute('UPDATE business_bank_match_events SET payload_json=?,content_hash=?',(canonical(forged['payload']),_sha(envelope)))
        with self.assertRaises(ValueError):validate_integrity(self.office)

    def test_lookalike_with_changed_external_id_requires_documented_distinction(self):
        self.save_statement(self.rows('119.00'))
        body=self.import_body(self.rows('119.00',prefix='OTHER'))
        preview=self.bank.preview_import(self.owner,body);self.assertFalse(preview['can_import']);self.assertEqual(preview['identity_checks'][0]['similar_external_ids'],['TX1'])
        self.error(409,self.bank.import_statement,self.owner,self.req(**body,preview_hash=preview['preview_hash'],confirmation=True))
        body['distinct_transaction_confirmations']={'OTHER1':'Original shows a distinct second actual transfer with this external ID'}
        preview=self.bank.preview_import(self.owner,body);self.assertTrue(preview['can_import'])
        self.bank.import_statement(self.owner,self.req(**body,preview_hash=preview['preview_hash'],confirmation=True))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_bank_transactions').fetchone()[0],2)
        self.assertTrue(validate_integrity(self.office))

    def test_reviewed_external_cash_is_actual_source_and_reversal_invalidates_only_current_report(self):
        import test_business_accounting_euer as external
        fixture=external.EuerWorkflowTests('runTest');fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.office,self.owner,self.account=fixture.office,fixture.owner,fixture.fixture.account
        self.bank=BankReconciliation(self.office,clock=fixture.fixture.clock);self.binding=self.bank.save_account(self.owner,self.account_body())
        receipt=fixture.incoming('9.50','0.00','9.50');entry=fixture.post('external_cash',fixture.external_payload(receipt,day='2026-11-02'))
        statement,_=self.save_statement(self.rows('-9.50'));identifier=statement['lines'][0]['transaction_id']
        link=self.link(identifier,entry['id'],'9.50');self.assertEqual(link['source_kind'],'reviewed_external_cash')
        self.match(identifier,[link]);report,_=self.report([statement]);self.assertTrue(report['record']['payload']['complete'])
        frozen=self.bank.export(self.owner,report['record']['id'],'json')[0]
        fixture.post('reverse',dict(entry_id=entry['id']))
        self.assertFalse(self.bank.reconciliation(self.owner,report['record']['id'])['current'])
        self.assertEqual(self.bank.export(self.owner,report['record']['id'],'json')[0],frozen)
        self.assertTrue(validate_integrity(self.office))

    def test_actual_payroll_aggregate_preserves_private_scope_and_historical_void_proof(self):
        import test_business_payroll_cash as payroll
        fixture=payroll.PayrollCashTests('runTest');fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.office,self.owner,self.account=fixture.office,fixture.owner,fixture.account
        self.bank=BankReconciliation(self.office,clock=fixture.clock);self.binding=self.bank.save_account(self.owner,self.account_body())
        data,run,identity,paid=fixture.case(payments=[dict(paid_on='2026-11-02',amount_minor=58129,payment_reference='SYN-WAGE-001')])
        body=fixture.body(paid);batch=fixture.import_cash(body);movement=batch['public_source']['cash_movements'][0]
        statement,_=self.save_statement(self.rows('-581.29'));identifier=statement['lines'][0]['transaction_id']
        link=self.link(identifier,movement['id'],'581.29');self.assertEqual(link['source_kind'],'payroll_cash')
        self.match(identifier,[link]);report,_=self.report([statement]);self.assertTrue(report['record']['payload']['complete'])
        uid=self.office.add_user('synthetic-bank-finance@example.test','Synthetic-bank-password-123','accountant');actor=dict(id=uid,role='accountant')
        from business_foundation import BusinessFoundation
        for permission in ('bank.read','accounting.read','finance.read'):
            BusinessFoundation(self.office).save_grant(self.owner,self.req(user_id=uid,permission=permission,scope='*',effect='allow',revision=0))
        candidate=self.bank.candidates(actor,identifier);text=canonical(candidate)
        for private in (fixture.f.employee['id'],paid['id'],identity['id'],data['file']['id'],'12345678903','SYN-WAGE-001'):
            self.assertNotIn(private,text)
        self.error(403,fixture.api.state,actor)
        fixture.import_cash(dict(body,expected_revision=1,action='void',sources=[],correction_file_id=data['file']['id']))
        self.assertFalse(self.bank.reconciliation(self.owner,report['record']['id'])['current'])
        self.assertTrue(validate_integrity(self.office))

    def test_rehashed_false_completion_is_rejected_from_actual_historical_sources(self):
        self.cash();statement,_=self.save_statement(self.rows('119.00'));report,_=self.report([statement])
        self.assertFalse(report['record']['payload']['complete'])
        forged=json.loads(canonical(report['record']));forged['payload']['complete']=True;forged['payload']['issues']=[]
        forged['payload']['preview_hash']=_sha({key:value for key,value in forged['payload'].items() if key!='preview_hash'})
        forged['content_hash']=_sha({key:value for key,value in forged.items() if key!='content_hash'})
        self.office.db.execute('DROP TRIGGER business_bank_reconciliations_update_guard')
        self.office.db.execute('UPDATE business_bank_reconciliations SET payload_json=?,content_hash=?',(canonical(forged['payload']),forged['content_hash']))
        with self.assertRaises(ValueError):validate_integrity(self.office)

    def test_changed_original_bytes_fail_before_restore_horizon_is_accepted(self):
        statement,_=self.save_statement([])
        self.office.db.execute('DROP TRIGGER business_bank_statements_update_guard')
        self.office.db.execute('UPDATE business_bank_statements SET original=?',(b'corrupted original',))
        self.error(409,self.bank.original,self.owner,statement['statement']['id'])
        with self.assertRaises(ValueError):restore_horizon(self.office)


if __name__=='__main__':unittest.main()
