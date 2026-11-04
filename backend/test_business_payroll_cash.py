"""Actual evidenced payroll payments to EÜR, without leaking private wages."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch
import uuid

from cryptography.fernet import Fernet
from core import Problem,canonical
from business_accounting import Accounting
from business_accounting_euer import EuerAccounting,ensure_cash_identity_available,validate_integrity as validate_euer
from business_accounting_profile import AccountingPreparationProfile
from business_payroll_cash import PayrollCash,validate_integrity,public_source,restore_horizon
from payroll_cash_sources import calculated
from online.instance import bind
from online.storage import Storage
import test_business_payroll_accounts as fixture


def rid():return uuid.uuid4().hex


class PayrollCashTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.PayrollAccountTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.office,self.owner=self.f.office,self.f.owner;self.clock=lambda:self.f.now
        self.instance=rid();self.key=Fernet.generate_key()
        self.storage=Storage(self.office,self.key,'payroll.example.test',config={'server':{'path':str(Path(self.f.temporary.name)/'company')}})
        bind(self.office,self.instance,'payroll.example.test',self.key,self.storage)
        self.api=PayrollCash(self.office,clock=self.clock);self.euer=EuerAccounting(self.office,clock=self.clock)
        self.account=Accounting(self.office,clock=self.clock).create_account(self.owner,dict(request_id=rid(),confirmation=True,code='1200',name='Synthetic company bank',kind='bank'))
        profile=AccountingPreparationProfile(self.office,clock=self.clock);state=profile.state(self.owner)
        body=dict(expected_revision=state['revision'],state_hash=state['state_hash'],reason='Synthetic confirmed EÜR facts',evidence_reference='Synthetic owner evidence',
            profile=dict(legal_form='sole_proprietorship',accounting_method='euer',vat_regime='regular',vat_timing='cash',vat_effective_from='2026-01-01',bookkeeping_start='2026-01-01'))
        preview=profile.preview(self.owner,body);profile.confirm(self.owner,dict(body,request_id=rid(),confirmation=True,preview_hash=preview['preview_hash']))

    def case(self,regular=False,payments=None):
        data=self.f.case('regular',500000,health_additional_percent='2.90',tax_allowance_monthly_minor=0,tax_addition_monthly_minor=0) if regular else self.f.case()
        run=self.f.payroll.finalize(self.owner,self.f.command(data));identity,_=self.f.save_account(data,'identity',self.f.identity_details(data))
        details=self.f.payment_details(run,identity,**({'payments':payments} if payments is not None else {}))
        paid,_=self.f.save_account(data,'payment',details)
        return data,run,identity,paid

    def body(self,paid,**changes):
        return dict(batch_id=rid(),expected_revision=0,instance_id=self.instance,action='adopt',kind='net',account_id=self.account['id'],account_revision=1,
            sources=[dict(account_record_id=paid['id'],revision=paid['revision'],content_hash=paid['content_hash'],payment_indexes=[0])],
            settlement=None,correction_file_id=None,reason='Explicit synthetic actual payment evidence')|changes

    def command(self,body):
        preview=self.api.preview(self.owner,body)
        return dict(body,request_id=rid(),preview_hash=preview['preview_hash'],confirmation=True)

    def import_cash(self,body):
        return self.api.confirm(self.owner,self.command(body))

    def euer_body(self,operation,payload,actor=None):
        state=self.euer.state(actor or self.owner)
        return dict(operation=operation,payload=payload,expected_revision=state['revision'],state_hash=state['state_hash'],reason='Explicit reviewed payroll expense',evidence_reference='Protected batch checked')

    def post(self,operation,payload,actor=None):
        actor=actor or self.owner;body=self.euer_body(operation,payload,actor);preview=self.euer.preview(actor,body)
        return self.euer.confirm(actor,dict(body,request_id=rid(),preview_hash=preview['preview_hash'],confirmation=True))

    def payload(self,batch):
        source=batch['public_source']
        return dict(batch_id=batch['id'],revision=batch['revision'],source_hash=source['source_hash'],
            accounts={key:'6020' if key=='payroll_net' else '6110' for move in source['cash_movements'] for key in move['categories']})

    def failure(self,status,fn,*args):
        with self.assertRaises(Problem) as error:fn(*args)
        self.assertEqual(error.exception.status,status,error.exception.message)
        return error.exception

    def remittance(self,data,run,paid,**changes):
        amounts=calculated(run['calculation'])
        return self.body(paid,kind='remittance',sources=[dict(source_kind='run',id=run['id'],revision=run['revision'],content_hash=run['content_hash'],amounts=amounts)],
            settlement=dict(paid_on='2026-11-02',payment_reference='SYN-PAID-TAX-SV-001',amount_minor=sum(amounts.values()),source_file_id=data['file']['id'],employee_id=self.f.employee['id'],sha256=data['file']['sha256']))|changes

    def test_minijob_actual_net_and_separately_evidenced_remittance_reach_euer_once(self):
        data,run,identity,paid=self.case();body=self.body(paid);command=self.command(body);net=self.api.confirm(self.owner,command)
        self.assertEqual(self.api.confirm(self.owner,command),net)
        self.assertEqual(net['public_source']['cash_movements'][0]['amount'],'581.29')
        self.assertEqual(self.euer.report(self.owner,2026)['totals']['confirmed_expenses'],'0.00')
        self.post('payroll_cash',self.payload(net));self.assertEqual(self.euer.report(self.owner,2026)['totals']['confirmed_expenses'],'581.29')
        remittance=self.import_cash(self.remittance(data,run,paid));self.post('payroll_cash',self.payload(remittance))
        report=self.euer.report(self.owner,2026)
        self.assertEqual(report['totals']['euer_surplus'],'-790.95');self.assertEqual(report['totals']['confirmed_input_vat'],'0.00')
        self.assertEqual(report['totals']['confirmed_output_vat'],'0.00');self.assertEqual(len(report['cash_movements']),2)
        self.assertTrue(validate_integrity(self.office));self.assertTrue(validate_euer(self.office))
        self.assertEqual(restore_horizon(self.office)['table_counts']['business_payroll_cash_batches'],2)

    def test_finance_only_can_classify_and_read_aggregate_without_personal_sources(self):
        data,run,identity,paid=self.case(True);batch=self.import_cash(self.body(paid))
        uid=self.office.add_user('synthetic-cash-finance@example.test','Synthetic-accountant-password-123','accountant');actor=dict(id=uid,role='owner')
        from business_foundation import BusinessFoundation
        foundation=BusinessFoundation(self.office)
        for permission in ('accounting.read','accounting.prepare','accounting.admin','finance.read','finance.write'):
            foundation.save_grant(self.owner,dict(request_id=rid(),user_id=uid,permission=permission,effect='allow',scope='*',revision=0))
        self.failure(403,self.api.state,actor);self.failure(403,self.api.sources,actor,self.f.employee['id'])
        entry=self.post('payroll_cash',self.payload(batch),actor)
        report=self.euer.report(actor,2026);self.assertEqual(report['totals']['confirmed_expenses'],'3130.09')
        self.post('correct',dict(entry_id=entry['id'],operation='payroll_cash',payload=self.payload(batch)),actor)
        exported=self.post('export',dict(year=2026),actor)
        output=canonical([self.euer.sources(actor),self.euer.journal(actor),self.euer.report(actor,2026),self.euer.exported(actor,exported['id'])])
        for denied in (self.f.employee['id'],paid['id'],identity['id'],data['file']['id'],'12345678903','Synthetic technician','SYN-WAGE-001','verified-payroll-profile.pdf'):
            self.assertNotIn(denied,output)
        self.assertTrue(validate_euer(self.office))

    def test_negative_actual_employee_part_reduces_expense_without_an_invented_gross_payment(self):
        parts=[dict(paid_on='2026-10-30',amount_minor=60000,payment_reference='SYN-PAID-600'),dict(paid_on='2026-11-01',amount_minor=-1871,payment_reference='SYN-RETURN-1871')]
        data,run,identity,paid=self.case(payments=parts)
        first=self.import_cash(self.body(paid));self.post('payroll_cash',self.payload(first))
        second=self.import_cash(self.body(paid,sources=[dict(account_record_id=paid['id'],revision=1,content_hash=paid['content_hash'],payment_indexes=[1])]))
        self.assertEqual(second['public_source']['cash_movements'][0]['direction'],'in');self.post('payroll_cash',self.payload(second))
        self.assertEqual(self.euer.report(self.owner,2026)['totals']['confirmed_expenses'],'581.29')
        self.assertTrue(validate_integrity(self.office))

    def test_duplicate_part_reference_and_remittance_capacity_are_not_reused(self):
        data,run,identity,paid=self.case();self.import_cash(self.body(paid))
        self.failure(409,self.api.preview,self.owner,self.body(paid))
        self.failure(409,ensure_cash_identity_available,self.office,self.account['id'],'ＳＹＮ-WAGE-001')
        remittance=self.remittance(data,run,paid);self.import_cash(remittance)
        changed=json.loads(canonical(remittance));changed['batch_id']=rid();changed['settlement']['payment_reference']='Another reference'
        self.failure(409,self.api.preview,self.owner,changed)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_payroll_cash_batches').fetchone()[0],2)

    def test_evidenced_date_correction_and_void_preserve_old_euer_export_and_reservations(self):
        data,run,identity,paid=self.case();body=self.body(paid);batch=self.import_cash(body);posted=self.post('payroll_cash',self.payload(batch))
        export=self.post('export',dict(year=2026));frozen=self.euer.exported(self.owner,export['id'])
        revised,_=self.f.save_account(data,'payment',{**paid['details'],'payments':[dict(paid_on='2026-11-01',amount_minor=58129,payment_reference='SYN-WAGE-001')]},
            id=paid['id'],revision=1,correction_reason='Actual bank date corrected from original evidence')
        change=self.body(revised,batch_id=batch['id'],expected_revision=1,action='replace',correction_file_id=data['file']['id'])
        updated=self.import_cash(change)
        self.assertIn('payroll_cash_source_changed',[v['code'] for v in self.euer.report(self.owner,2026)['issues']])
        corrected=self.post('correct',dict(entry_id=posted['id'],operation='payroll_cash',payload=self.payload(updated)))
        self.assertEqual(self.euer.report(self.owner,2026)['totals']['confirmed_expenses'],'581.29')
        self.assertEqual(self.euer.exported(self.owner,export['id']),frozen)
        void=self.import_cash(dict(change,expected_revision=2,action='void',sources=[]))
        self.post('correct',dict(entry_id=corrected['id'],operation='payroll_cash',payload=self.payload(void)))
        self.assertEqual(self.euer.report(self.owner,2026)['totals']['confirmed_expenses'],'0.00')
        self.failure(409,self.api.preview,self.owner,self.body(revised))
        self.assertTrue(validate_integrity(self.office));self.assertTrue(validate_euer(self.office))

    def test_atomic_failure_parallel_retry_and_fresh_permission_after_lost_ack(self):
        data,run,identity,paid=self.case();command=self.command(self.body(paid))
        with patch.object(self.office,'audit',side_effect=RuntimeError('Synthetic interrupted audit')):
            with self.assertRaises(RuntimeError):self.api.confirm(self.owner,command)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_payroll_cash_batches').fetchone()[0],0)
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.api.confirm(self.owner,command),range(2)))
        self.assertEqual(results[0],results[1]);self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_payroll_cash_batches').fetchone()[0],1)
        with self.assertRaises(sqlite3.IntegrityError):self.office.db.execute('DELETE FROM business_payroll_cash_batches')
        with self.office.db:self.office.db.execute("UPDATE users SET role='accountant' WHERE id=?",(self.owner['id'],))
        self.failure(403,self.api.confirm,self.owner,command)

    def test_calculation_correction_is_not_cash_and_only_evidenced_additional_part_is_imported(self):
        data,run,identity,paid=self.case();original=self.import_cash(self.body(paid));self.post('payroll_cash',self.payload(original))
        revised=self.f.payroll.save_profile(self.owner,dict(request_id=rid(),employee_id=self.f.employee['id'],id=data['profile']['id'],revision=1,
            profile={**data['profile']['profile'],'minijob_rv_exempt':True},source_file_id=data['file']['id'],confirmed=True,correction_reason='Actual exemption evidence'))
        data['inputs']['profile_revision']=2;changed=self.f.payroll.finalize(self.owner,self.f.command(data,id=run['id'],revision=1,correction_reason='Documented exemption correction'))
        self.assertEqual(changed['delta']['net_minor'],2171)
        self.assertEqual(self.euer.report(self.owner,2026)['totals']['confirmed_expenses'],'581.29')
        fresh_identity,_=self.f.save_account(data,'identity',self.f.identity_details({**data,'profile':revised}))
        current,_=self.f.save_account(data,'payment',self.f.payment_details(changed,fresh_identity,payments=[paid['details']['payments'][0],
            dict(paid_on='2026-11-02',amount_minor=2171,payment_reference='SYN-ACTUAL-ADDITIONAL-2171')]))
        additional=self.import_cash(self.body(current,sources=[dict(account_record_id=current['id'],revision=1,content_hash=current['content_hash'],payment_indexes=[1])]))
        self.post('payroll_cash',self.payload(additional));self.assertEqual(self.euer.report(self.owner,2026)['totals']['confirmed_expenses'],'603.00')
        self.assertEqual(public_source(self.office,original['id'],1),original['public_source'])
        self.assertTrue(validate_integrity(self.office));self.assertTrue(validate_euer(self.office))

    def test_period_lock_source_guards_and_explicit_not_accepted_resolution(self):
        data,run,identity,paid=self.case();body=self.body(paid);command=self.command(body)
        self.post('period',dict(period='2026-10',action='close',expected_period_revision=0,
            attestation=dict(bank_reconciled=True,originals_complete=True,special_cases_reviewed=True)))
        rejected=self.failure(409,self.api.confirm,self.owner,command);self.assertEqual(rejected.request_resolution,'not_accepted')
        self.post('period',dict(period='2026-10',action='reopen',expected_period_revision=1,
            attestation=dict(bank_reconciled=True,originals_complete=True,special_cases_reviewed=True)))
        self.assertEqual(self.api.confirm(self.owner,command)['revision'],1)
        sources=self.api.sources(self.owner,self.f.employee['id'])
        self.assertTrue(sources['net_sources'][0]['payments'][0]['already_imported'])
        self.assertTrue(sources['evidence_files'][0]['source_path'].endswith('/content'))
        foreign=dict(command,instance_id=rid());rejected=self.failure(409,self.api.confirm,self.owner,foreign)
        self.assertIsNone(rejected.request_resolution)
        remit=self.remittance(data,run,paid);remit['settlement']['paid_on']='2027-01-03'
        self.failure(400,self.api.preview,self.owner,remit)

    def test_new_restore_horizon_rejects_inconsistent_private_scope_and_keeps_schema9_readable(self):
        from business_schema import financial_accounting_horizon,_validate_financial_accounting_horizon
        data,run,identity,paid=self.case();self.import_cash(self.body(paid))
        complete=financial_accounting_horizon(self.office);self.assertEqual(complete['schema_version'],13)
        _validate_financial_accounting_horizon(complete,14)
        horizon={key:value for key,value in complete.items() if key not in ('bank_reconciliation','travel_cash','opening_balances','historical_assets')};horizon['schema_version']=9
        _validate_financial_accounting_horizon(horizon,10)
        old={k:v for k,v in horizon.items() if k!='payroll_cash'};old['schema_version']=8
        encoded=canonical(old);_validate_financial_accounting_horizon(old,9);self.assertEqual(canonical(old),encoded)
        for change in ('missing','bool','negative','hash'):
            malformed=json.loads(canonical(horizon));value=malformed['payroll_cash']
            if change=='missing':value['table_counts'].pop('business_payroll_cash_parts')
            elif change=='bool':value['table_counts']['business_payroll_cash_parts']=True
            elif change=='negative':value['table_counts']['business_payroll_cash_parts']=-1
            else:value['sha256']='not-a-hash'
            with self.subTest(change=change),self.assertRaises(ValueError):_validate_financial_accounting_horizon(malformed,10)
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_payroll_cash_parts_delete_guard')
            self.office.db.execute('DELETE FROM business_payroll_cash_parts')
        with self.assertRaises(ValueError):validate_integrity(self.office)


if __name__=='__main__':unittest.main()
