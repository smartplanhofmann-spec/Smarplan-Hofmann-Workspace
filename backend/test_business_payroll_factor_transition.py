"""Actual original-bound factor/Midijob API, revisions and historical receipts."""
from copy import deepcopy
import unittest

from core import Problem
from business_payroll_facts import reference
from business_payroll_calculation_cases import PayrollCalculationCases
from test_business_payroll_factor_entitlements import FactorEntitlementFixture
from test_payroll_transition_2026 import assessment
import test_business_payroll_periods as periods
from test_business_planning import rid

RULE='de_2026_factor_transition_month_v14'
SCOPE='regular_transition_factor_month'


class FactorTransitionFixture(FactorEntitlementFixture):
    monthly_amount=200000

    def proposal(self):
        f=self.f
        review=dict(schema_version=1,employee_id=f.employee['id'],valid_from='2026-10-01',
            valid_to='2026-10-31',declaration_date='2026-10-01',
            transition_assessment=assessment(self.monthly_amount),forecast_evidence_ref=self.original,
            sole_employment_confirmed=True,full_fixed_monthly_pay_confirmed=True,
            verification_note='Synthetic original factor profile and separate complete twelve-month prognosis')
        return dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],kind='calculation_case',
            rule_version=RULE,source_contract_version=6,source_file_ids=[self.original['id']],
            details=dict(month='2026-10',period_case_ref=reference(self.base),
                employment_terms_refs=[reference(self.terms)],profile_refs=[reference(f.data['profile'])],
                identity_refs=[reference(f.identity)],segment_events=[],thirty_day_rule=None,
                entitlement_case_refs=[],travel_settlement_refs=[],flat_tax_decision=None,
                factor_transition_assessment=review,
                verification_note='Explicit full-month factor and independent status election'))

    def accepted(self):
        self.case_input=self.proposal();self.case_preview=self.api.preview(self.f.owner,self.case_input)
        self.case_command=dict(self.case_input,request_id=rid(),revision=0,status='active',confirmed=True,
            preview_hash=self.case_preview['preview_hash'])
        self.case=self.api.save(self.f.owner,self.case_command)
        self.run_input=dict(employee_id=self.f.employee['id'],source_schema_version=3,
            calculation_case_ref=reference(self.case))
        self.run_preview=self.f.payroll.preview(self.f.owner,self.run_input)
        self.run_command=periods.command(self.f.payroll,self.f.owner,self.run_input)
        self.run=self.f.payroll.finalize(self.f.owner,self.run_command)
        return self.run


class FactorTransitionWorkflow(FactorTransitionFixture):
    def test_evidenced_note_correction_keeps_original_case_run_pdf_and_receipts(self):
        original=self.accepted();old_case=deepcopy(self.case)
        pdf=self.f.payroll.export(self.f.owner,original['id'],'pdf',revision='1')[0]
        proposal=self.proposal()
        proposal['details']['verification_note']='Separately corrected factual review; original factor and forecast unchanged'
        preview=self.api.preview(self.f.owner,proposal)
        corrected_command=dict(proposal,request_id=rid(),id=old_case['id'],revision=1,
            status='active',confirmed=True,preview_hash=preview['preview_hash'],
            correction_reason='Actual review text correction without rewriting the original')
        corrected=self.api.save(self.f.owner,corrected_command)
        self.assertEqual(corrected['previous_hash'],old_case['content_hash'])
        inputs=dict(employee_id=self.f.employee['id'],source_schema_version=3,
            calculation_case_ref=reference(corrected))
        command=periods.command(self.f.payroll,self.f.owner,inputs)
        command.update(id=original['id'],revision=1,correction_reason='Bind the separately verified corrected case')
        current=self.f.payroll.finalize(self.f.owner,command)
        self.assertEqual((current['revision'],current['previous_hash']),(2,original['content_hash']))
        self.assertEqual(current['calculation']['net_minor'],original['calculation']['net_minor'])
        self.assertEqual(self.api.save(self.f.owner,self.case_command),old_case)
        self.assertEqual(self.f.payroll.finalize(self.f.owner,self.run_command),original)
        self.assertEqual(self.f.payroll.finalize(self.f.owner,command),current)
        self.assertEqual(self.f.payroll.export(self.f.owner,original['id'],'pdf',revision='1')[0],pdf)

    def test_actual_new_scope_keeps_original_profile_and_both_exact_receipts(self):
        original=deepcopy(self.f.data['profile']);before=[dict(x)for x in self.f.office.db.execute('SELECT * FROM business_time_days')]
        run=self.accepted()
        self.assertTrue(self.case_preview['can_calculate'])
        self.assertEqual(run['accepted_scope'],SCOPE)
        self.assertEqual(run['calculation']['rule_version'],RULE)
        self.assertNotIn('transition_assessment',run['source']['profile']['profile'])
        self.assertEqual(run['source']['profile'],original)
        self.assertEqual(self.api.save(self.f.owner,self.case_command),self.case)
        self.assertEqual(self.f.payroll.finalize(self.f.owner,self.run_command),run)
        self.assertEqual(before,[dict(x)for x in self.f.office.db.execute('SELECT * FROM business_time_days')])
        self.assertEqual(self.f.payroll.export(self.f.owner,run['id'],'pdf')[0][:4],b'%PDF')
        from business_schema import validate_integrity
        self.assertTrue(validate_integrity(self.f.office))

    def test_missing_or_foreign_prognosis_original_is_rejected(self):
        proposal=self.proposal()
        review=proposal['details']['factor_transition_assessment']
        replacements=[dict(source_file_ids=[])]
        for changed in (dict(employee_id=rid()),
                        dict(forecast_evidence_ref=self.original|dict(content_hash='f'*64))):
            replacements.append(dict(details=proposal['details']|dict(factor_transition_assessment=review|changed)))
        for replacement in replacements:
            with self.subTest(replacement=replacement),self.assertRaises(Problem):
                self.api.preview(self.f.owner,proposal|replacement)

    def test_extra_active_claim_cannot_disappear_from_a_simple_month(self):
        self.unpaid();proposal=self.proposal()
        with self.assertRaises(Problem)as error:self.api.preview(self.f.owner,proposal)
        self.assertEqual(error.exception.status,409)

    def test_partial_month_and_changed_fixed_gross_remain_unsupported(self):
        other=FactorTransitionFixture('runTest');other.employment_start='2026-10-15';other.setUp()
        try:
            preview=other.api.preview(other.f.owner,other.proposal())
            self.assertFalse(preview['can_calculate'])
            self.assertIn('factor_transition_full_month_required',[x['code']for x in preview['plan']['blockers']])
        finally:other.doCleanups()

    def test_actual_reduced_contributions_cash_private_statement_and_annual_basis(self):
        import test_business_payroll_accounts as accounts
        import test_business_payroll_calculations as calculation_fixture
        from business_payroll_statements import PayrollStatements
        from business_payroll_annual_basis import PayrollAnnualBasis
        from business_schema import validate_integrity
        other=FactorTransitionFixture('runTest');other.monthly_amount=100000;other.setUp()
        try:
            f=other.f;run=other.accepted()
            self.assertEqual(run['calculation']['net_minor'],87467)
            social=run['calculation']['period_details']['social_assessments'][0]
            self.assertEqual(social['branch_bases']['health_general'],dict(total_minor=85406,employee_minor=56836))
            details=accounts.PayrollAccountTests.payment_details(f,run,f.identity,
                payments=[dict(paid_on='2026-10-31',amount_minor=87467,payment_reference='SYN-FACTOR-MIDI-NET')])
            paid,command=f.save_account(f.data,'payment',details)
            self.assertEqual(f.account_api().save(f.owner,command),paid)
            finance=calculation_fixture.CalculationPayrollWorkflow.finance(other)
            cash=finance.import_cash(finance.body(paid));finance.post('payroll_cash',finance.payload(cash))
            self.assertEqual(finance.euer.report(f.owner,2026)['totals']['confirmed_expenses'],'874.67')
            own=PayrollStatements(f.office).get(f.technician,run['id'])['statement']
            self.assertEqual(own['calculation']['net_minor'],87467)
            self.assertNotIn(other.original['id'],str(own))
            self.assertNotIn(other.case['id'],str(own))
            self.assertNotIn('factor_transition_assessment',str(own))
            annual=PayrollAnnualBasis(f.office,clock=lambda:f.now)
            details=dict(employer_identity_ref=reference(f.identity),verification_note='Actual factor/Midijob original and net evidence',
                year=2026,coverage_to='2026-10-31',as_of_date='2026-10-31',payroll_run_refs=[reference(run)],
                payroll_payment_refs=[reference(paid)],imported_period_refs=[],imported_one_off_refs=[],current_calculation_case_ref=None,
                gaps=[dict(start='2026-01-01',end='2026-09-30',reason='not_employed',evidence_ref=other.original)],
                completeness_confirmed=True)
            body=dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],kind='annual_basis',
                details=details,source_file_ids=[other.original['id']])
            preview=annual.preview(f.owner,body)
            record=annual.save(f.owner,dict(body,request_id=rid(),revision=0,status='active',confirmed=True,
                preview_hash=preview['preview_hash']))
            self.assertEqual(record['plan']['running_taxable_minor'],100000)
            self.assertEqual(record['plan']['section_rooms']['regular']['health']['sv_days'],30)
            self.assertEqual(f.payroll.finalize(f.owner,other.run_command),run)
            self.assertEqual(finance.euer.report(f.owner,2026)['totals']['confirmed_expenses'],'874.67')
            self.assertTrue(validate_integrity(f.office))
        finally:other.doCleanups()


if __name__=='__main__':unittest.main()
