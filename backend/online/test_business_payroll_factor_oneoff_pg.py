"""Real V15 MFA, concurrent original/run ownership, money, annual and restore."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from decimal import Decimal
import time
import unittest
from cryptography.fernet import Fernet

import business_schema
from business_payroll import Payroll
from business_payroll_accounts import PayrollAccounts
from business_payroll_annual_basis import PayrollAnnualBasis
from business_payroll_cash import PayrollCash
from business_accounting_euer import EuerAccounting
from business_payroll_factor_oneoff_cases import FactorOneoffCases
from business_payroll_facts import reference
from business_payroll_oneoff_cases import _consumption_row,TABLES
from business_payroll_statements import PayrollStatements
from online import test_business_payroll_factor_annual_pg as annual
from online.store import PostgresOffice
from online.web import create_app
from online.auth import totp
from online.test_postgres_accounting_components_integration import disposable_restore,evidence_for,approve
import test_business_payroll_accounts as account_fixture
import test_business_payroll_cash as cash_fixture

fixture=annual.fixture
req=annual.req
ROOT='/business/payroll/one-off-cases/factor-v15'


@unittest.skipUnless(fixture.DSN,'Guarded disposable loopback PostgreSQL required')
class FactorOneoffPostgres(unittest.TestCase):
    setUp=annual.FactorAnnualPostgres.setUp
    reopen=annual.FactorAnnualPostgres.reopen
    call=annual.FactorAnnualPostgres.call
    login=annual.FactorAnnualPostgres.login
    sources=annual.FactorAnnualPostgres.sources
    create_factor_case=annual.FactorAnnualPostgres.create_factor_case
    profile=annual.original.FactorClaimsPostgres.profile
    post=annual.original.FactorClaimsPostgres.post
    cash_body=cash_fixture.PayrollCashTests.body
    cash_payload=cash_fixture.PayrollCashTests.payload

    def workflow(self):
        data=self.create_factor_case();identity=data['identity'];case=data['case'];original=data['original']
        def save_annual(kind,details,*,v2=False):
            path='/business/payroll/annual-facts'+('/factor-v2' if v2 else '')
            proposal=dict(data['common'],kind=kind,details=dict(employer_identity_ref=reference(identity),verification_note='Actual PG factor bonus annual original reviewed',**details))
            preview=self.call('POST',path+'/preview',proposal).json
            command=req(**proposal,revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
            return self.call('POST',path,command).json,command
        basis,_=save_annual('annual_basis',dict(year=2026,coverage_to='2026-10-31',as_of_date='2026-10-31',
            payroll_run_refs=[],payroll_payment_refs=[],imported_period_refs=[],imported_one_off_refs=[],current_calculation_case_ref=reference(case),
            gaps=[dict(start='2026-01-01',end='2026-09-30',reason='not_employed',evidence_ref=original)],completeness_confirmed=True),v2=True)
        earning,_=save_annual('one_off_earning',dict(claim_key=original,claim_reference='Actual PG factor contractual bonus position1',
            planned_receipt_date='2026-10-31',amount_minor=50000,tax_classification='other_payment',social_classification='one_off_remuneration',section_key='regular',
            employment_terms_refs=[reference(data['terms'])],claim_periods=[dict(start='2026-10-15',end='2026-10-31',evidence_ref=original)],document_refs=[original]))
        forecast,_=save_annual('annual_tax_forecast',dict(annual_basis_ref=reference(basis),receipt_date='2026-10-31',identity_ref=reference(identity),current_one_off_ref=reference(earning),
            previous_employers=[dict(employer_name='Actual PG synthetic earlier employer',employer_tax_number='111/222/33333',start='2026-01-01',end='2026-09-30',running_taxable_minor=12000000,other_paid_minor=0,evidence_ref=original)],
            no_previous_employer_ref=None,other_tax_receipt_refs=[],remaining_periods=[dict(month=month,employment_terms_ref=reference(data['terms']),agreement_refs=[reference(data['agreement'])],work_schedule_ref=None) for month in ('2026-11','2026-12')]),v2=True)
        proposal=dict(data['common'],kind='one_off_case',rule_version='de_2026_factor_claims_oneoff_v15',source_contract_version=2,
            details=dict(month='2026-10',running_calculation_case_ref=reference(case),one_off_earning_ref=reference(earning),current_annual_basis_ref=reference(basis),previous_annual_basis_ref=None,annual_tax_forecast_ref=reference(forecast),verification_note='Actual V15 factor, P4 and full annual original reviewed'))
        self.call('POST','/business/payroll/one-off-cases/preview',proposal,status=400)
        preview=self.call('POST',ROOT+'/preview',proposal).json;self.assertTrue(preview['can_calculate'])
        data.update(proposal=proposal,case_command=req(**proposal,revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash']),basis=basis,earning=earning)
        return data

    def concurrent(self,callback):
        def writer(_):
            office=PostgresOffice(self.runtime)
            try:return callback(office)
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:a,b=list(pool.map(writer,range(2)))
        self.assertEqual(a,b);return a

    def test_actual_mfa_concurrent_case_run_money_annual_statement_and_full_restore(self):
        data=self.workflow();owner=self.office.user(self.token)
        case=self.concurrent(lambda office:FactorOneoffCases(office).save(owner,data['case_command']))
        self.assertEqual(self.call('POST',ROOT,data['case_command']).json,case)
        inputs=dict(employee_id=data['employee']['id'],source_schema_version=4,one_off_case_ref=reference(case))
        preview=self.call('POST','/business/payroll/preview',inputs).json
        command=req(**inputs,revision=0,confirmed=True,preview_hash=preview['preview_hash'],accepted_scope=preview['calculation']['scope'])
        run=self.concurrent(lambda office:Payroll(office).finalize(owner,command))
        self.assertEqual(self.call('POST','/business/payroll/runs',command).json,run)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM '+TABLES[2]).fetchone()[0],1)
        consumption=_consumption_row(self.office,run['id'],run['revision'])
        self.assertGreater(run['calculation']['one_off_details']['tax']['STS'],0);self.assertGreater(run['calculation']['one_off_details']['tax']['SOLZS'],0)
        self.assertEqual(run['source']['calculation_case'],data['case'])
        pdf=self.call('GET','/business/payroll/runs/'+run['id']+'/pdf').data
        amount=run['calculation']['payout_minor']
        details=account_fixture.PayrollAccountTests.payment_details(self,run,data['identity'],payments=[dict(paid_on='2026-10-31',amount_minor=amount,payment_reference='SYN-PG-FACTOR-BONUS-ACTUAL')])
        payment_command=req(employee_id=data['employee']['id'],kind='payment',revision=0,source_file_id=data['file']['id'],confirmed=True,details=details)
        payment=self.call('POST','/business/payroll/account-records',payment_command).json
        self.account=self.call('POST','/business/accounting/accounts',req(confirmation=True,code='PAYROLL',name='Synthetic actual factor bonus bank',kind='bank'),status=201).json
        self.profile();body=self.cash_body(payment);preview=self.call('POST','/business/payroll/cash/preview',body).json
        cash_command=req(**body,preview_hash=preview['preview_hash'],confirmation=True)
        batch=self.call('POST','/business/payroll/cash/batches',cash_command,status=201).json
        self.post('payroll_cash',self.cash_payload(batch));report=self.call('GET','/business/accounting/euer/report?year=2026').json
        self.assertEqual(Decimal(report['totals']['confirmed_expenses']),Decimal(amount)/100)
        details=deepcopy(data['basis']['details']);details.update(as_of_date='2026-11-01',current_calculation_case_ref=None,payroll_run_refs=[reference(run)],payroll_payment_refs=[reference(payment)])
        proposal=dict(data['common'],kind='annual_basis',details=details);preview=self.call('POST','/business/payroll/annual-facts/preview',proposal).json
        annual_command=req(**proposal,revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
        completed=self.call('POST','/business/payroll/annual-facts',annual_command).json
        self.assertEqual(completed['plan']['earlier_other_taxable_minor'],50000)
        self.assertEqual(len(completed['plan']['projection']['prior_one_offs']),1)
        own=self.call('GET','/business/payroll/employee-statements/'+run['id'],token=data['tech']).json['statement']
        self.assertEqual(own['schema_version'],5)
        for private in (case['id'],data['earning']['id'],data['basis']['id'],data['file']['id']):self.assertNotIn(private,str(own))
        self.call('GET',ROOT+'/'+case['id'],token=data['tech'],status=403)
        self.call('POST',ROOT+'/preview?ignored=1',data['proposal'],status=400)
        secret=Fernet(self.key).decrypt(self.office.db.execute('SELECT secret FROM mfa WHERE user_id=?',(owner['id'],)).fetchone()['secret'].encode()).decode()
        self.assertTrue(business_schema.validate_integrity(self.office));self.office.db.close()
        with disposable_restore(self.runtime) as (target,runtime,restore_report):
            operator=PostgresOffice(target)
            try:approve(operator,evidence_for(operator,restore_report))
            finally:operator.db.close()
            restored=PostgresOffice(runtime)
            try:
                self.assertEqual(FactorOneoffCases(restored).save(owner,data['case_command']),case)
                self.assertEqual(Payroll(restored).finalize(owner,command),run)
                self.assertEqual(PayrollAccounts(restored).save(owner,payment_command),payment)
                self.assertEqual(PayrollCash(restored).confirm(owner,cash_command),batch)
                self.assertEqual(PayrollAnnualBasis(restored).save(owner,annual_command),completed)
                self.assertEqual(_consumption_row(restored,run['id'],run['revision']),consumption)
                self.assertEqual(Payroll(restored).export(owner,run['id'],'pdf')[0],pdf)
                self.assertEqual(EuerAccounting(restored).report(owner,2026)['totals'],report['totals'])
                app=create_app(office=restored,key=self.key,host='office.example.test',instance_id=self.instance,storage_config=self.storage_config);client=app.test_client();base='https://office.example.test'
                path='/api/v1'+ROOT+'/'+case['id']
                self.assertEqual(client.get(path,headers={'Authorization':'Bearer '+self.token},base_url=base).status_code,401)
                pending=client.post('/api/v1/login',json=dict(email=owner['email'],password='Synthetic-owner-password-123'),base_url=base).json
                authenticated=client.post('/api/v1/login/verify',json=dict(challenge=pending['challenge'],code=totp(secret,int(time.time()//30)+1)),base_url=base)
                self.assertEqual(authenticated.status_code,200)
                self.assertEqual(client.get(path,headers={'Authorization':'Bearer '+authenticated.json['token']},base_url=base).json,case)
                self.assertTrue(business_schema.validate_integrity(restored))
            finally:restored.db.close()


if __name__=='__main__':unittest.main()
