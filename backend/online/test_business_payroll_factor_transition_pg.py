"""Actual factor/Midijob HTTP originals, two concurrent receipts, cash, annual, CRLF and full restore."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import threading
import unittest

import business_schema
from business_payroll import Payroll
from business_payroll_accounts import PayrollAccounts
from business_payroll_annual_basis import PayrollAnnualBasis
from business_payroll_calculation_cases import PayrollCalculationCases
from business_payroll_cash import PayrollCash
from business_accounting_euer import EuerAccounting
from business_payroll_facts import reference
from online.store import PostgresOffice
from online import test_business_payroll_payment_dates_pg as dates
from online import test_business_payroll_entitlements_pg as entitlements
from online import test_business_company_handover_pg as bound
from online.test_postgres_accounting_components_integration import disposable_restore, evidence_for, approve
import test_business_payroll_oneoff_provenance as original_transport
import test_business_payroll_cash as cash_fixture

fixture=entitlements.fixture
req=entitlements.req
GOLDEN=json.loads((Path(__file__).resolve().parents[2]/'app/test/fixtures/payroll_factor_transition.json').read_text())


@unittest.skipUnless(fixture.DSN,'Guarded disposable loopback PostgreSQL required')
class FactorTransitionPostgres(unittest.TestCase):
    setUpClass=classmethod(original_transport.OneoffOriginalTransport.setUpClass.__func__)
    setUp=bound.CompanyHandoverPostgres.setUp
    reopen=bound.CompanyHandoverPostgres.reopen
    call=bound.CompanyHandoverPostgres.call
    login=dates.ActualPaymentDatesPostgres.login
    sources=entitlements.PayrollEntitlementsPostgres.sources
    profile=dates.ActualPaymentDatesPostgres.profile
    post=dates.ActualPaymentDatesPostgres.post
    cash_body=cash_fixture.PayrollCashTests.body
    cash_payload=cash_fixture.PayrollCashTests.payload

    def test_actual_factor_midijob_concurrent_mfa_cash_annual_crlf_and_full_restore(self):
        data=self.sources();employee=data['employee'];proof=data['file']
        employee=self.call('POST','/business/employees',req(id=employee['id'],revision=employee['revision'],
            employment_from='2026-10-01',employment_to=None),status=201).json
        agreement=self.call('POST','/business/personnel/agreements',req(employee_id=employee['id'],
            id=data['agreement']['id'],revision=data['agreement']['revision'],effective_from='2026-01-01',
            employment_kind='regular',pay_basis='monthly',amount_minor=100000,currency='EUR',
            reference_file_id=proof['id'],correction_reason='Actual original regular factor salary')).json
        profile=self.call('POST','/business/payroll/profiles',req(employee_id=employee['id'],id=data['profile']['id'],
            revision=data['profile']['revision'],profile=dict(GOLDEN['case']['sources']['profiles'][0]['profile'],regular_annual_gross_minor=1200000),source_file_id=proof['id'],
            confirmed=True,correction_reason='Actual original class IV factor and insurance')).json
        identity=self.call('POST','/business/payroll/account-records',req(employee_id=employee['id'],kind='identity',
            revision=0,source_file_id=proof['id'],confirmed=True,
            details=dict(GOLDEN['case']['sources']['identities'][0]['details'],profile_id=profile['id'],profile_revision=profile['revision']))).json
        preview=self.call('GET','/business/personnel/payroll-preparations/preview?employee_id='+employee['id']+'&month=2026-10').json
        preparation=self.call('POST','/business/personnel/payroll-preparations',req(employee_id=employee['id'],
            id=data['preparation']['id'],revision=data['preparation']['revision'],month='2026-10',
            source_hash=preview['source_hash'],completeness_confirmed=True,
            correction_reason='Actual original full-month factor employment')).json
        common=dict(employee_id=employee['id'],employee_revision=employee['revision'],source_file_ids=[proof['id']])
        original=dict(id=proof['id'],revision=1,content_hash=proof['content_hash'])
        terms=self.call('POST','/business/payroll/facts',req(**common,kind='employment_terms',revision=0,status='active',
            confirmed=True,details=dict(employment_from='2026-10-01',employment_to=None,
                agreement_refs=[reference(agreement)],proration_method='calendar_days_actual',reason='Actual original full-month contract'))).json
        period_details=dict(month='2026-10',preparation_ref=reference(preparation),employment_terms_ref=reference(terms),
            work_schedule_ref=None,profile_refs=[reference(profile)],identity_refs=[reference(identity)],
            tax_treatment='domestic_running_wages',entitlement_decisions=[],verification_note='Actual original full factor month')
        preview=self.call('POST','/business/payroll/periods/preview',dict(common,details=period_details)).json
        period=self.call('POST','/business/payroll/facts',req(**common,kind='period_case',revision=0,status='active',
            confirmed=True,details=period_details,preview_hash=preview['preview_hash'])).json
        before_times=self.call('GET','/business/time/summary?employee_id='+employee['id']+'&from=2026-10-01&to=2026-10-31').json
        review=deepcopy(GOLDEN['case_input']['details']['factor_transition_assessment'])
        review.update(employee_id=employee['id'],forecast_evidence_ref=original)
        review['transition_assessment']['regular_monthly_gross_minor']=100000
        proposal=dict(common,kind='calculation_case',rule_version='de_2026_factor_transition_month_v14',source_contract_version=6,
            details=dict(month='2026-10',period_case_ref=reference(period),employment_terms_refs=[reference(terms)],
                profile_refs=[reference(profile)],identity_refs=[reference(identity)],segment_events=[],thirty_day_rule=None,
                entitlement_case_refs=[],travel_settlement_refs=[],flat_tax_decision=None,
                factor_transition_assessment=review,verification_note='Actual original factor and separately evidenced full prognosis'))
        preview=self.call('POST','/business/payroll/calculation-cases/preview',proposal).json
        case_command=req(**proposal,revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
        case_barrier=threading.Barrier(2)
        def case_writer(_):
            office=PostgresOffice(self.runtime)
            try:
                case_barrier.wait(timeout=15)
                return PayrollCalculationCases(office).save(self.owner,case_command)
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2)as pool:cases=list(pool.map(case_writer,range(2)))
        case=cases[0];self.assertEqual(case,cases[1])
        self.assertEqual(self.call('POST','/business/payroll/calculation-cases',case_command).json,case)
        inputs=dict(employee_id=employee['id'],source_schema_version=3,calculation_case_ref=reference(case))
        preview=self.call('POST','/business/payroll/preview',inputs).json
        c=preview['calculation'];self.assertEqual((c['gross_minor'],c['individual_wage_tax_minor'],c['net_minor']),
            (100000,0,87467))
        self.assertEqual(c['period_details']['social_assessments'][0]['branch_bases']['health_general'],dict(total_minor=85406,employee_minor=56836))
        self.assertEqual(preview['source']['profile'],profile)
        self.assertNotIn('transition_assessment',profile['profile'])
        self.assertFalse(c['travel_expenses_included_in_net'])
        # Genuine CRLF source import in a separate interpreter: no compatibility DTO rewrite.
        code=('import json,sys;sys.path.insert(0,sys.argv[1]);'
            'from payroll_factor_transition_2026 import calculate_source;'
            'print(json.dumps(calculate_source(json.load(sys.stdin))))')
        result=subprocess.run([sys.executable,'-I','-B','-c',code,str(self.root)],input=json.dumps(case['sources']),
            text=True,capture_output=True,check=True,timeout=60)
        self.assertEqual(json.loads(result.stdout),c)
        command=req(**inputs,revision=0,confirmed=True,preview_hash=preview['preview_hash'],accepted_scope=c['scope'])
        barrier=threading.Barrier(2)
        def writer(_):
            office=PostgresOffice(self.runtime)
            try:barrier.wait(timeout=15);return Payroll(office).finalize(self.owner,command)
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:runs=list(pool.map(writer,range(2)))
        run=runs[0];self.assertEqual(run,runs[1]);self.assertEqual(self.call('POST','/business/payroll/runs',command).json,run)
        pdf=self.call('GET','/business/payroll/runs/'+run['id']+'/pdf').data
        payment_command=req(employee_id=employee['id'],kind='payment',revision=0,source_file_id=proof['id'],confirmed=True,
            details=dict(run_id=run['id'],run_revision=run['revision'],identity_id=identity['id'],identity_revision=identity['revision'],
                payments=[dict(paid_on='2026-10-31',amount_minor=87467,payment_reference='SYN-PG-FACTOR-MIDI-NET')],
                tax_free_payments_minor=0,tax_free_basis='',standard_case_confirmed=True))
        paid=self.call('POST','/business/payroll/account-records',payment_command).json
        self.account=self.call('POST','/business/accounting/accounts',req(confirmation=True,code='PAYROLL',
            name='Synthetic actual factor claim bank',kind='bank'),status=201).json
        self.profile()
        body=self.cash_body(paid);preview=self.call('POST','/business/payroll/cash/preview',body).json
        cash_command=req(**body,preview_hash=preview['preview_hash'],confirmation=True)
        batch=self.call('POST','/business/payroll/cash/batches',cash_command,status=201).json
        self.post('payroll_cash',self.cash_payload(batch))
        report=self.call('GET','/business/accounting/euer/report?year=2026').json
        self.assertEqual(report['totals']['confirmed_expenses'],'874.67')
        self.assertEqual(report['totals']['confirmed_input_vat'],'0.00')
        self.assertEqual(self.call('GET','/business/time/summary?employee_id='+employee['id']+'&from=2026-10-01&to=2026-10-31').json,before_times)
        details=dict(employer_identity_ref=reference(identity),verification_note='Actual factor/Midijob wage and payment',
            year=2026,coverage_to='2026-10-31',as_of_date='2026-10-31',payroll_run_refs=[reference(run)],
            payroll_payment_refs=[reference(paid)],imported_period_refs=[],imported_one_off_refs=[],current_calculation_case_ref=None,
            gaps=[dict(start='2026-01-01',end='2026-09-30',reason='not_employed',evidence_ref=original)],completeness_confirmed=True)
        proposal=dict(common,kind='annual_basis',details=details)
        preview=self.call('POST','/business/payroll/annual-facts/preview',proposal).json
        annual_command=req(**proposal,revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
        annual=self.call('POST','/business/payroll/annual-facts',annual_command).json
        self.assertEqual(annual['plan']['running_taxable_minor'],100000)
        self.call('GET','/business/payroll/calculation-cases/'+case['id'],token=data['tech'],status=403)
        self.call('POST','/business/payroll/account-records',payment_command,token=data['tech'],status=403)
        own=self.call('GET','/business/payroll/employee-statements/'+run['id'],token=data['tech']).json
        self.assertNotIn(case['id'],str(own));self.assertNotIn(proof['id'],str(own))
        self.token=self.login('order-owner@example.test','Synthetic-owner-password-123')
        self.assertEqual(self.call('POST','/business/payroll/account-records',payment_command).json,paid)
        self.assertTrue(business_schema.validate_integrity(self.office));self.office.db.close()
        with disposable_restore(self.runtime) as (target,runtime,restore_report):
            operator=PostgresOffice(target)
            try:approve(operator,evidence_for(operator,restore_report))
            finally:operator.db.close()
            restored=PostgresOffice(runtime)
            try:
                self.assertEqual(PayrollCalculationCases(restored).save(self.owner,case_command),case)
                self.assertEqual(Payroll(restored).finalize(self.owner,command),run)
                self.assertEqual(PayrollAccounts(restored).save(self.owner,payment_command),paid)
                self.assertEqual(PayrollCash(restored).confirm(self.owner,cash_command),batch)
                self.assertEqual(PayrollAnnualBasis(restored).save(self.owner,annual_command),annual)
                self.assertEqual(EuerAccounting(restored).report(self.owner,2026)['totals'],report['totals'])
                self.assertEqual(Payroll(restored).export(self.owner,run['id'],'pdf',revision='1')[0],pdf)
                self.assertTrue(business_schema.validate_integrity(restored))
            finally:restored.db.close()
            self.runtime=runtime;self.reopen()
            self.call('GET','/me',status=401)
            self.token=self.login('order-owner@example.test','Synthetic-owner-password-123')
            self.assertEqual(self.call('POST','/business/payroll/calculation-cases',case_command).json,case)
            self.assertEqual(self.call('POST','/business/payroll/runs',command).json,run)
            self.assertEqual(self.call('POST','/business/payroll/account-records',payment_command).json,paid)
            self.assertEqual(self.call('GET','/business/payroll/runs/'+run['id']+'/pdf').data,pdf)
            self.assertEqual(self.call('GET','/business/accounting/euer/report?year=2026').json['totals'],report['totals'])
            self.office.db.close()


if __name__=='__main__':unittest.main()
