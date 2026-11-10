"""Actual v16 originals, immutable confirmations, private money/year consumers."""
from copy import deepcopy
import unittest

from core import Problem
from business_payroll_facts import reference
from test_business_payroll_factor_entitlements import FactorEntitlementFixture
from test_payroll_transition_2026 import assessment
from test_business_planning import rid
import test_business_payroll_periods as periods

RULE = 'de_2026_factor_transition_period_v16'
SCOPE = 'regular_transition_factor_period'


class FactorTransitionPeriodFixture(FactorEntitlementFixture):
    monthly_amount = 100000
    employment_start = '2026-10-15'

    def setUp(self):
        super().setUp()
        f = self.f
        # This is an explicit, preserved contractual correction. No old source
        # row, employee, profile or accepted period is modified in place.
        body = f.body('employment_terms', self.terms['details'] | dict(proration_method='contractual_30_days'),
            id=self.terms['id'], revision=self.terms['revision'],
            correction_reason='Synthetic actual fixed contract explicitly uses the thirty-day quotient')
        self.terms = f.api.save(f.owner, body)
        details = f.period_details(self.terms)
        preview = f.api.preview(f.owner, f.preview_body(details))
        self.base = f.api.save(f.owner, f.body('period_case', details, preview_hash=preview['preview_hash'],
            id=self.base['id'], revision=self.base['revision'],
            correction_reason='Bind the separately evidenced thirty-day contract original'))

    def proposal(self):
        f = self.f
        review = dict(schema_version=1, employee_id=f.employee['id'], valid_from='2026-10-01',
            valid_to='2026-10-31', declaration_date='2026-10-01',
            transition_assessment=assessment(self.monthly_amount), forecast_evidence_ref=self.original,
            sole_employment_confirmed=True, fixed_monthly_contract_confirmed=True,
            contractual_30_days_confirmed=True,
            verification_note='Synthetic original actual fixed contract, sole employment and independent prognosis')
        return dict(employee_id=f.employee['id'], employee_revision=f.employee['revision'], kind='calculation_case',
            rule_version=RULE, source_contract_version=7, source_file_ids=[self.original['id']],
            details=dict(month='2026-10', period_case_ref=reference(self.base),
                employment_terms_refs=[reference(self.terms)], profile_refs=[reference(f.data['profile'])],
                identity_refs=[reference(f.identity)], segment_events=[], thirty_day_rule='actual_days_capped_per_claim',
                entitlement_case_refs=[], travel_settlement_refs=[], flat_tax_decision=None,
                factor_transition_period_assessment=review,
                verification_note='Actual original entry period and separately verified Midijob prognosis'))

    def accepted(self):
        f = self.f
        self.case_input = self.proposal()
        self.case_preview = self.api.preview(f.owner, self.case_input)
        self.case_command = dict(self.case_input, request_id=rid(), revision=0, status='active', confirmed=True,
            preview_hash=self.case_preview['preview_hash'])
        self.case = self.api.save(f.owner, self.case_command)
        self.run_input = dict(employee_id=f.employee['id'], source_schema_version=3,
            calculation_case_ref=reference(self.case))
        self.run_preview = f.payroll.preview(f.owner, self.run_input)
        self.run_command = periods.command(f.payroll, f.owner, self.run_input)
        self.run = f.payroll.finalize(f.owner, self.run_command)
        return self.run


class FactorTransitionPeriodWorkflow(FactorTransitionPeriodFixture):
    def test_actual_partial_case_run_original_profile_receipts_and_private_pdf(self):
        f = self.f
        before = deepcopy(f.data['profile'])
        work = [dict(r) for r in f.office.db.execute('SELECT * FROM business_time_days')]
        run = self.accepted()
        self.assertTrue(self.case_preview['can_calculate'])
        self.assertEqual(run['accepted_scope'], SCOPE)
        self.assertEqual(run['calculation']['gross_minor'], 56667)
        self.assertEqual(run['calculation']['period_details']['social_periods'][0]['days'], 17)
        self.assertEqual(run['calculation']['period_details']['tax_periods'][0]['tax_days'], 17)
        self.assertEqual(run['source']['profile'], before)
        self.assertNotIn('transition_assessment', before['profile'])
        self.assertEqual(self.api.save(f.owner, self.case_command), self.case)
        self.assertEqual(f.payroll.finalize(f.owner, self.run_command), run)
        self.assertEqual(work, [dict(r) for r in f.office.db.execute('SELECT * FROM business_time_days')])
        self.assertEqual(f.payroll.export(f.owner, run['id'], 'pdf')[0][:4], b'%PDF')
        from business_schema import validate_integrity
        self.assertTrue(validate_integrity(f.office))

    def test_explicit_contract_review_and_source_bindings_are_not_implicit_flags(self):
        proposal = self.proposal()
        variants = [proposal | dict(source_contract_version=6), proposal | dict(source_file_ids=[])]
        variants.append(proposal | dict(details=proposal['details'] | dict(thirty_day_rule=None)))
        review = proposal['details']['factor_transition_period_assessment']
        for change in (dict(employee_id=rid()),
                dict(forecast_evidence_ref=self.original | dict(content_hash='f'*64)),
                dict(declaration_date='2026-11-04')):
            variants.append(proposal | dict(details=proposal['details'] | dict(factor_transition_period_assessment=review | change)))
        variants.append(proposal | dict(details=proposal['details'] | dict(factor_transition_assessment=review)))
        for body in variants:
            with self.subTest(body=body), self.assertRaises(Problem):
                self.api.preview(self.f.owner, body)
        unchecked = proposal | dict(details=proposal['details'] | dict(
            factor_transition_period_assessment=review | dict(contractual_30_days_confirmed=False)))
        result = self.api.preview(self.f.owner, unchecked)
        self.assertFalse(result['can_calculate'])
        self.assertIn('factor_transition_period_review_not_complete', [r['code'] for r in result['plan']['blockers']])

    def test_new_actual_claim_cannot_disappear_from_the_simple_partial_period(self):
        self.unpaid()
        with self.assertRaises(Problem) as error:
            self.api.preview(self.f.owner, self.proposal())
        self.assertEqual(error.exception.status, 409)

    def test_fresh_private_rights_are_required_for_the_new_version(self):
        with self.assertRaises(Problem) as error:
            self.api.preview(self.f.technician, self.proposal())
        self.assertEqual(error.exception.status, 403)

    def test_note_correction_preserves_old_case_run_pdf_and_exact_original_acknowledgements(self):
        f = self.f
        original = self.accepted()
        pdf = f.payroll.export(f.owner, original['id'], 'pdf')[0]
        proposal = self.proposal()
        proposal['details']['verification_note'] = 'Separately documented review text correction; same actual original period'
        preview = self.api.preview(f.owner, proposal)
        command = proposal | dict(request_id=rid(), id=self.case['id'], revision=self.case['revision'],
            status='active', confirmed=True, preview_hash=preview['preview_hash'],
            correction_reason='Correct the factual review without rewriting an earlier original')
        corrected = self.api.save(f.owner, command)
        inputs = dict(employee_id=f.employee['id'], source_schema_version=3, calculation_case_ref=reference(corrected))
        run_command = periods.command(f.payroll, f.owner, inputs) | dict(id=original['id'], revision=original['revision'],
            correction_reason='Bind the separately corrected factual review')
        current = f.payroll.finalize(f.owner, run_command)
        self.assertEqual(current['previous_hash'], original['content_hash'])
        self.assertEqual(current['calculation']['net_minor'], original['calculation']['net_minor'])
        self.assertEqual(f.payroll.finalize(f.owner, self.run_command), original)
        self.assertEqual(self.api.save(f.owner, self.case_command), self.case)
        self.assertEqual(f.payroll.export(f.owner, original['id'], 'pdf', revision='1')[0], pdf)

    def test_actual_net_payment_euer_private_statement_and_partial_year_basis(self):
        import test_business_payroll_accounts as accounts
        import test_business_payroll_calculations as calculations
        from business_payroll_statements import PayrollStatements
        from business_payroll_annual_basis import PayrollAnnualBasis
        from business_schema import validate_integrity
        f = self.f
        run = self.accepted()
        net = run['calculation']['net_minor']
        details = accounts.PayrollAccountTests.payment_details(f, run, f.identity,
            payments=[dict(paid_on='2026-10-31', amount_minor=net, payment_reference='SYN-FACTOR-MIDI-ACTUAL-PARTIAL-NET')])
        paid, command = f.save_account(f.data, 'payment', details)
        self.assertEqual(f.account_api().save(f.owner, command), paid)
        finance = calculations.CalculationPayrollWorkflow.finance(self)
        cash = finance.import_cash(finance.body(paid))
        finance.post('payroll_cash', finance.payload(cash))
        self.assertEqual(finance.euer.report(f.owner, 2026)['totals']['confirmed_expenses'], f'{net//100}.{net%100:02}')
        own = PayrollStatements(f.office).get(f.technician, run['id'])['statement']
        self.assertEqual(own['calculation']['net_minor'], net)
        self.assertNotIn('factor_transition_period_assessment', str(own))
        self.assertNotIn(self.original['id'], str(own))
        year = PayrollAnnualBasis(f.office, clock=lambda: f.now)
        details = dict(employer_identity_ref=reference(f.identity), verification_note='Actual original partial factor/Midijob period',
            year=2026, coverage_to='2026-10-31', as_of_date='2026-10-31', payroll_run_refs=[reference(run)],
            payroll_payment_refs=[reference(paid)], imported_period_refs=[], imported_one_off_refs=[], current_calculation_case_ref=None,
            gaps=[dict(start='2026-01-01', end='2026-10-14', reason='not_employed', evidence_ref=self.original)],
            completeness_confirmed=True)
        body = dict(employee_id=f.employee['id'], employee_revision=f.employee['revision'], kind='annual_basis',
            details=details, source_file_ids=[self.original['id']])
        # The unchanged annual contract covers a payroll original's calendar
        # month, while branch eligibility uses its actual employment interval.
        # A separate gap inside that already represented month must be rejected.
        with self.assertRaises(Problem) as overlap:
            year.preview(f.owner, body)
        self.assertEqual(overlap.exception.status, 409)
        body['details']['gaps'][0]['end'] = '2026-09-30'
        preview = year.preview(f.owner, body)
        stored = year.save(f.owner, body | dict(request_id=rid(), revision=0, status='active', confirmed=True,
            preview_hash=preview['preview_hash']))
        self.assertEqual(stored['plan']['running_taxable_minor'], 56667)
        self.assertEqual(stored['plan']['section_rooms']['regular']['health']['sv_days'], 17)
        self.assertTrue(validate_integrity(f.office))


class FactorTransitionExitWorkflow(FactorTransitionPeriodFixture):
    employment_start = '2026-01-01'

    def test_actual_exit_rebinds_employee_identity_preparation_and_period_without_rewriting_prior_full_month(self):
        f = self.f
        original_full = deepcopy(self.base)
        f.employee = f.call(f.planning, 'save_employee', f.owner, dict(request_id=rid(),
            id=f.employee['id'], revision=f.employee['revision'],
            employment_from='2026-01-01', employment_to='2026-10-16'))
        f.identity, _ = f.save_account(f.data, 'identity',
            f.identity_details(f.data, employment_from='2026-01-01', employment_to='2026-10-16'),
            id=f.identity['id'], revision=f.identity['revision'], correction_reason='Actual original exit and prior employment')
        hr = f.hr.preview(f.owner, dict(employee_id=f.employee['id'], month='2026-10'))
        previous = f.data['preparation']
        f.data['preparation'] = f.hr.close_preparation(f.owner, dict(request_id=rid(), employee_id=f.employee['id'],
            id=previous['id'], revision=previous['revision'], month='2026-10', source_hash=hr['source_hash'],
            completeness_confirmed=True, correction_reason='Actual exit bound to unchanged original payroll sources'))
        self.terms = f.api.save(f.owner, f.body('employment_terms', self.terms['details'] | dict(
            employment_from='2026-01-01', employment_to='2026-10-16'),
            id=self.terms['id'], revision=self.terms['revision'], correction_reason='Actual evidenced exit and thirty-day contract'))
        details = f.period_details(self.terms)
        preview = f.api.preview(f.owner, f.preview_body(details))
        self.base = f.api.save(f.owner, f.body('period_case', details, preview_hash=preview['preview_hash'],
            id=self.base['id'], revision=self.base['revision'], correction_reason='Actual exit sources and original identity bound'))
        run = self.accepted()
        self.assertEqual(run['calculation']['gross_minor'], 53333)
        self.assertEqual(run['calculation']['period_details']['social_periods'][0]['days'], 16)
        self.assertEqual(run['calculation']['period_details']['tax_periods'][0]['tax_days'], 16)
        self.assertEqual(self.base['previous_hash'], original_full['content_hash'])
        historical = next(row for row in f.api.get(f.owner, original_full['id'], history=True)['items']
            if row['revision'] == original_full['revision'])
        self.assertEqual(historical, original_full)
        self.assertEqual(f.payroll.finalize(f.owner, self.run_command), run)



if __name__ == '__main__':
    unittest.main()
