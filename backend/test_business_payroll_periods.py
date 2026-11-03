"""Real P2 facts -> v4 run -> identity/payment -> existing cash and EÜR."""
import json
import unittest

import business_schema
from business_payroll import validate_integrity
from business_payroll_facts import PayrollFacts,reference
from business_personnel_workflow import _sha
from core import Problem,canonical
from test_business_payroll import rid,profile
import test_business_payroll_facts as facts_fixture
import test_business_payroll_accounts as account_fixture


def inputs(employee_id,fact):
    return dict(source_schema_version=2,employee_id=employee_id,period_case_ref=reference(fact))


def command(payroll,owner,data,**changes):
    preview=payroll.preview(owner,data)
    return dict(data,request_id=rid(),preview_hash=preview['preview_hash'],accepted_scope=preview['calculation']['scope'],
        confirmed=True,revision=0,**changes)


def reconcile_payroll_batches(office,owner,account,batches,clock):
    """Actual neutral bank originals bind the existing v4 cash movements."""
    from business_bank_reconciliation import BankReconciliation
    import test_business_bank_reconciliation as bank_fixture
    bank=bank_fixture.BankTests('runTest');bank.office=office;bank.owner=owner;bank.account=account
    bank.bank=BankReconciliation(office,clock=clock)
    bank.binding=bank.bank.save_account(owner,bank.account_body(coverage_from='2026-11-01'))
    movements=[value for batch in batches for value in batch['public_source']['cash_movements']]
    rows=bank.rows(*['-'+value['amount'] for value in movements],day=clock().date().isoformat(),reference='Synthetic actual partial payroll bank settlement')
    statement,_=bank.save_statement(rows)
    for transaction,movement in zip(statement['lines'],movements):
        link=bank.link(transaction['transaction_id'],movement['id'],movement['amount'],reason='Actual cash evidence and bank settlement dates independently checked')
        bank.match(transaction['transaction_id'],[link])
    report,_=bank.report([statement]);bank.assertTrue(report['record']['payload']['complete'])
    return report


class PayrollPeriodWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.f=facts_fixture.PayrollFactTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)

    def regular(self,amount=500000,**changes):
        f=self.f;old=f.data
        agreement=f.hr.save_agreement(f.owner,dict(request_id=rid(),employee_id=f.employee['id'],id=old['agreement']['id'],revision=1,
            effective_from='2026-01-01',employment_kind='regular',pay_basis='monthly',amount_minor=amount,currency='EUR',
            reference_file_id=old['file']['id'],correction_reason='Synthetic reviewed regular contract'))
        saved=f.payroll.save_profile(f.owner,dict(request_id=rid(),employee_id=f.employee['id'],id=old['profile']['id'],revision=1,
            profile=profile('regular',regular_annual_gross_minor=amount*12,health_additional_percent='2.90',
                tax_allowance_monthly_minor=0,tax_addition_monthly_minor=0,**changes),source_file_id=old['file']['id'],confirmed=True,
            correction_reason='Synthetic actual regular employment evidence'))
        fresh=f.hr.preview(f.owner,dict(employee_id=f.employee['id'],month='2026-10'))
        preparation=f.hr.close_preparation(f.owner,dict(request_id=rid(),employee_id=f.employee['id'],month='2026-10',
            id=old['preparation']['id'],revision=1,source_hash=fresh['source_hash'],completeness_confirmed=True,
            correction_reason='Synthetic actual contract source corrected'))
        f.data=dict(old,agreement=agreement,profile=saved,preparation=preparation)
        f.identity,_=f.save_account(f.data,'identity',f.identity_details(f.data,employment_from='2026-10-15',employment_to=None))

    def test_partial_minijob_originals_ledger_and_private_sources(self):
        f=self.f;fact,_,_=f.period();data=inputs(f.employee['id'],fact);body=command(f.payroll,f.owner,data)
        run=f.payroll.finalize(f.owner,body)
        self.assertEqual(run['calculation']['gross_minor'],33068)
        self.assertEqual(run['calculation']['net_minor'],31878)
        self.assertEqual(run['source']['period_case'],fact)
        self.assertEqual(f.payroll.finalize(f.owner,body),run)
        f.problem(400,lambda:f.payroll.preview(f.owner,data|dict(gross_minor=1)))
        original=f.payroll.export(f.owner,run['id'],'pdf')[0]
        self.assertEqual(_sha(original),run['pdf_sha256']);self.assertIn(b'Zeitnachweis',original)
        paid,_=f.save_account(f.data,'payment',account_fixture.PayrollAccountTests.payment_details(f,run,f.identity))
        ledger=f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026'))['ledger']
        self.assertEqual(ledger['totals']['individual_wage_tax_minor'],0)
        self.assertEqual(ledger['totals']['net_minor'],31878)
        self.assertTrue(ledger['months'][9]['wage_account']['complete'])
        self.assertEqual(ledger['months'][9]['source_refs']['period_case'],reference(fact))
        for fmt in ('json','csv','pdf'):
            value,_=f.payroll.export_ledger(f.owner,dict(employee_id=f.employee['id'],year='2026',snapshot_hash=ledger['snapshot_hash']),fmt)
            self.assertIn(b'de_2026_periods_pap_v4',value)
        for read in (lambda:f.payroll.get(f.technician,'run',run['id']),lambda:f.payroll.records(f.technician,'run',dict(employee_id=f.employee['id'])),
                lambda:f.payroll.ledger(f.technician,dict(employee_id=f.employee['id'],year='2026')),
                lambda:f.account_api().get(f.technician,paid['id'])):
            f.problem(403,read)
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_regular_partial_identity_covers_actual_days_and_old_run_survives_correction(self):
        f=self.f;self.regular();fact,_,_=f.period();data=inputs(f.employee['id'],fact);body=command(f.payroll,f.owner,data)
        run=f.payroll.finalize(f.owner,body)
        self.assertTrue(run['calculation']['payroll_calculation_complete'])
        self.assertEqual(run['calculation']['scope'],'regular_standard_period')
        self.assertEqual(run['calculation']['gross_minor'],274194)
        original=f.payroll.export(f.owner,run['id'],'json')[0];pdf=f.payroll.export(f.owner,run['id'],'pdf')[0]
        f.save_account(f.data,'payment',account_fixture.PayrollAccountTests.payment_details(f,run,f.identity))
        current=f.data['profile']
        f.data['profile']=f.payroll.save_profile(f.owner,dict(request_id=rid(),employee_id=f.employee['id'],id=current['id'],revision=current['revision'],
            profile=current['profile']|dict(tax_allowance_monthly_minor=10000),source_file_id=f.data['file']['id'],confirmed=True,
            correction_reason='Synthetic verified monthly allowance'))
        f.identity,_=f.save_account(f.data,'identity',f.identity_details(f.data,employment_from='2026-10-15',employment_to=None,
            tax_allowance_yearly_minor=120000))
        details=f.period_details(fact['sources']['employment_terms'])
        preview=f.api.preview(f.owner,f.preview_body(details))
        corrected=f.api.save(f.owner,f.body('period_case',details,id=fact['id'],revision=1,preview_hash=preview['preview_hash'],
            correction_reason='New actual ELStAM and identity evidence'))
        newbody=command(f.payroll,f.owner,inputs(f.employee['id'],corrected))|dict(id=run['id'],revision=1,correction_reason='Explicit supported partial-period correction')
        correction=f.payroll.finalize(f.owner,newbody)
        self.assertGreater(correction['calculation']['net_minor'],run['calculation']['net_minor'])
        self.assertEqual(correction['delta']['net_minor'],-correction['delta']['employee_tax_minor'])
        self.assertEqual(f.payroll.export(f.owner,run['id'],'json','1')[0],original)
        self.assertEqual(f.payroll.export(f.owner,run['id'],'pdf','1')[0],pdf)
        self.assertEqual(f.payroll.finalize(f.owner,body),run)
        ledger=f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026'))['ledger']
        self.assertEqual(ledger['recorded_months'],1)
        self.assertEqual(ledger['totals']['net_minor'],correction['calculation']['net_minor'])
        self.assertFalse(ledger['months'][9]['wage_account']['complete'])
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_module_pause_returns_accepted_original_but_blocks_new_calculation(self):
        f=self.f;fact,_,_=f.period();data=inputs(f.employee['id'],fact);body=command(f.payroll,f.owner,data)
        run=f.payroll.finalize(f.owner,body);f.pause()
        self.assertEqual(f.payroll.finalize(f.owner,body),run)
        f.problem(423,lambda:f.payroll.finalize(f.owner,body|dict(request_id=rid())))
        self.assertTrue(validate_integrity(f.office))

    def test_midijob_partial_rule_and_source_drift(self):
        f=self.f;self.regular(100000,transition_assessment=dict(status='within_transition_area',assessed_on='2026-01-01',
            regular_monthly_gross_minor=100000,forecast_months=12,foreseeable_one_off_payments=False,note='Synthetic evidenced forecast'))
        fact,_,_=f.period();data=inputs(f.employee['id'],fact);preview=f.payroll.preview(f.owner,data)
        self.assertTrue(preview['can_finalize'])
        self.assertEqual(preview['calculation']['scope'],'regular_transition_period')
        run=f.payroll.finalize(f.owner,command(f.payroll,f.owner,data))
        terms=fact['sources']['employment_terms']
        f.api.save(f.owner,f.body('employment_terms',terms['details']|dict(proration_method='contractual_30_days'),
            id=terms['id'],revision=1,correction_reason='Contract source actually corrected'))
        f.problem(409,lambda:f.payroll.preview(f.owner,data))
        self.assertEqual(f.payroll.get(f.owner,'run',run['id']),run)
        self.assertTrue(business_schema.validate_integrity(f.office))


class PeriodCashFlowTests(unittest.TestCase):
    def test_actual_partial_net_and_remittance_reach_existing_euer_once(self):
        from test_business_payroll_cash import PayrollCashTests
        from payroll_cash_sources import calculated
        c=PayrollCashTests('runTest');c.setUp();self.addCleanup(c.doCleanups);f=c.f
        f.employee=f.call(f.planning,'save_employee',f.owner,dict(request_id=rid(),id=f.employee['id'],revision=f.employee['revision'],employment_from='2026-10-15',employment_to=None))
        data=f.case('minijob',60300);identity,_=f.save_account(data,'identity',f.identity_details(data,employment_from='2026-10-15',employment_to=None))
        api=PayrollFacts(f.office,clock=lambda:f.now)
        common=dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],revision=0,status='active',
            source_file_ids=[data['file']['id']],confirmed=True)
        terms=api.save(f.owner,dict(common,request_id=rid(),kind='employment_terms',details=dict(employment_from='2026-10-15',employment_to=None,
            agreement_refs=[reference(data['agreement'])],proration_method='calendar_days_actual',reason='Original synthetic partial contract')))
        details=dict(month='2026-10',preparation_ref=reference(data['preparation']),employment_terms_ref=reference(terms),work_schedule_ref=None,
            profile_refs=[reference(data['profile'])],identity_refs=[reference(identity)],tax_treatment='domestic_running_wages',
            entitlement_decisions=[],verification_note='Actual synthetic source review')
        preview=api.preview(f.owner,dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],details=details,source_file_ids=common['source_file_ids']))
        fact=api.save(f.owner,dict(common,request_id=rid(),kind='period_case',details=details,preview_hash=preview['preview_hash']))
        run=f.payroll.finalize(f.owner,command(f.payroll,f.owner,inputs(f.employee['id'],fact)))
        paid,_=f.save_account(data,'payment',f.payment_details(run,identity))
        net=c.import_cash(c.body(paid));c.post('payroll_cash',c.payload(net))
        remittance=c.import_cash(c.remittance(data,run,paid));c.post('payroll_cash',c.payload(remittance))
        expected=run['calculation']['employer_total_excluding_accident_insurance_minor']
        self.assertEqual(c.euer.report(f.owner,2026)['totals']['confirmed_expenses'],f'{expected//100}.{expected%100:02d}')
        self.assertEqual(c.euer.report(f.owner,2026)['totals']['confirmed_input_vat'],'0.00')
        report=reconcile_payroll_batches(f.office,f.owner,c.account,[net,remittance],lambda:f.now)
        self.assertTrue(report['record']['payload']['complete'])
        public=canonical(net['public_source'])
        self.assertNotIn(fact['id'],public);self.assertNotIn('entitlement_decisions',public)
        self.assertTrue(business_schema.validate_integrity(f.office))


if __name__=='__main__':unittest.main()
