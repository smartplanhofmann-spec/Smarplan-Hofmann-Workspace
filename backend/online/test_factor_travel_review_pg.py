"""Independent V10 review on an isolated PostgreSQL/MFA/restore fixture."""
import base64
from copy import deepcopy
from datetime import date, timedelta
import unittest
import uuid

import business_schema
from business_foundation import BusinessFoundation
from business_payroll import Payroll
from business_payroll_calculation_cases import PayrollCalculationCases, validate_case_sources
from business_payroll_facts import reference
from business_payroll_statements import PayrollStatements
from core import Problem, canonical
from online import release
from online import test_business_payroll_periods_pg as periods
from online import test_business_travel_pg as travel
from online.store import PostgresOffice
from online.test_postgres_accounting_components_integration import disposable_restore, evidence_for, approve
from payroll_factor_taxfree_travel_2026 import RULE_VERSION, SOURCE_CONTRACT_VERSION, SCOPE, AMOUNTS
from test_payroll_de_2026 import profile as tax_profile
from travel_allowance_cash import public_source

fixture = periods.fixture
req = fixture.request


@unittest.skipUnless(fixture.DSN, 'Own guarded disposable PostgreSQL fixture required')
class FactorTravelPostgresReview(unittest.TestCase):
    setUp = periods.PeriodPayrollPostgres.setUp
    reopen = periods.PeriodPayrollPostgres.reopen
    login = periods.PeriodPayrollPostgres.login
    sources = periods.PeriodPayrollPostgres.sources

    def call(self, method, path, body=None, *, token='owner', status=200, mime=None):
        bearer = self.token if token == 'owner' else token
        headers = {'Authorization': 'Bearer ' + bearer} if bearer else {}
        arguments = {'json': body} if isinstance(body, dict) else {'data': body}
        response = self.client.open('/api/v1' + path, method=method,
            base_url='https://office.example.test', headers=headers, content_type=mime, **arguments)
        error = response.get_json(silent=True) or {}
        self.assertEqual(response.status_code, status,
                         (method, path, response.status_code, error.get('error') if isinstance(error, dict) else None))
        return response

    def factor_period(self):
        data = self.sources()
        original = b'%PDF-1.4\nIndependent full-month October contract: EUR 5000, class IV factor 0.753\n%%EOF'
        data['file'] = self.call('POST', '/business/personnel/files', req(
            employee_id=data['employee']['id'], purpose='personnel', owner_visible=False,
            filename='independent-full-month.pdf', media_type='application/pdf',
            content_base64=base64.b64encode(original).decode())).json
        data['original'] = original
        employee = self.call('POST', '/business/employees', req(
            id=data['employee']['id'], revision=data['employee']['revision'],
            employment_from='2026-10-01', employment_to=None), status=201).json
        data['employee'] = employee
        data['agreement'] = self.call('POST', '/business/personnel/agreements', req(
            employee_id=employee['id'], id=data['agreement']['id'], revision=1,
            effective_from='2026-01-01', employment_kind='regular', pay_basis='monthly',
            amount_minor=500000, currency='EUR', reference_file_id=data['file']['id'],
            correction_reason='Independent full-month factor agreement')).json
        data['profile'] = self.call('POST', '/business/payroll/profiles', req(
            employee_id=employee['id'], id=data['profile']['id'], revision=1,
            profile=tax_profile('regular', regular_annual_gross_minor=6000000,
                health_additional_percent='2.90', tax_allowance_monthly_minor=0,
                tax_addition_monthly_minor=0, tax_class=4, special_cases=['tax_factor'],
                tax_factor='0.753'), source_file_id=data['file']['id'], confirmed=True,
            correction_reason='Independent verified factor evidence')).json
        preparation = self.call('GET', '/business/personnel/payroll-preparations/preview?employee_id='
                                + employee['id'] + '&month=2026-10').json
        data['preparation'] = self.call('POST', '/business/personnel/payroll-preparations', req(
            employee_id=employee['id'], month='2026-10', id=data['preparation']['id'], revision=1,
            source_hash=preparation['source_hash'], completeness_confirmed=True,
            correction_reason='Independent full-month source review')).json
        data['identity'] = self.identity(data, previous=data['identity'])
        terms = self.call('POST', '/business/payroll/facts', req(employee_id=employee['id'],
            employee_revision=employee['revision'], kind='employment_terms', revision=0,
            status='active', source_file_ids=[data['file']['id']], confirmed=True,
            details=dict(employment_from='2026-10-01', employment_to=None,
                agreement_refs=[reference(data['agreement'])], proration_method='calendar_days_actual',
                reason='Actual complete October employment'))).json
        details = dict(month='2026-10', preparation_ref=reference(data['preparation']),
            employment_terms_ref=reference(terms), work_schedule_ref=None,
            profile_refs=[reference(data['profile'])], identity_refs=[reference(data['identity'])],
            tax_treatment='domestic_running_wages', entitlement_decisions=[],
            verification_note='Independent original full-month factor case')
        data['period_details'] = details
        data['period'] = self.period(data, details)
        self.assertEqual(data['period']['plan']['rule_version'], 'de_2026_standard_factor_period_v9')
        data['v9_input'] = dict(source_schema_version=2, employee_id=employee['id'],
                                period_case_ref=reference(data['period']))
        data['v9_command'] = self.run_command(data['v9_input'])
        data['v9'] = self.call('POST', '/business/payroll/runs', data['v9_command']).json
        self.assertEqual(data['v9']['calculation']['net_minor'], 332342)
        return data

    def identity(self, data, previous):
        details = periods.accounts.PayrollAccountTests.identity_details(self, data,
            employment_from='2026-10-01', employment_to=None)
        return self.call('POST', '/business/payroll/account-records', req(
            employee_id=data['employee']['id'], kind='identity', revision=0,
            source_file_id=data['file']['id'], confirmed=True, details=details)).json

    def period(self, data, details, previous=None):
        proposal = dict(employee_id=data['employee']['id'], employee_revision=data['employee']['revision'],
            details=details, source_file_ids=[data['file']['id']])
        preview = self.call('POST', '/business/payroll/periods/preview', proposal).json
        self.assertTrue(preview['can_calculate'], preview['plan']['blockers'])
        command = req(**proposal, kind='period_case', revision=previous['revision'] if previous else 0,
            status='active', confirmed=True, preview_hash=preview['preview_hash'])
        if previous:
            command.update(id=previous['id'], correction_reason='Independent corrected factor original')
        return self.call('POST', '/business/payroll/facts', command).json

    def trip(self, data, *, day='2026-10-26', meal=False, pay=True):
        original = b'%PDF-1.4\nIndependent private trip original ' + day.encode() + b'\n%%EOF'
        file = self.call('POST', '/business/personnel/files', req(employee_id=data['employee']['id'],
            purpose='expense_receipt', owner_visible=True, filename='private-trip.pdf',
            media_type='application/pdf', content_base64=base64.b64encode(original).decode()),
            token=data['tech']).json
        local = dict(data, file=file)
        # Existing real travel HTTP helper supplies sites, trip and approval.
        if day == '2026-10-26' and not meal:
            local = travel.TravelPostgres.workflow(self, local)
        else:
            sites = []
            for kind in ('home', 'external_fixed'):
                sites.append(self.call('POST', '/business/personnel/travel/sites', req(
                    employee_id=data['employee']['id'], id=uuid.uuid4().hex, revision=0, status='active',
                    correction_reason='', details=dict(name='Independent ' + kind, kind=kind,
                        address='Private trip address', rate_id='de_2026', timezone='Europe/Berlin',
                        effective_from='2026-01-01', effective_to=None, assignment_basis='Original site evidence',
                        regular_days_per_week=2, history_complete_from='2025-09-01', prior_visit_dates=[],
                        source_file_ids=[file['id']])), token=data['tech']).json['result'])
            start, end = day + 'T08:00:00+01:00', day + 'T18:00:00+01:00'
            meals = [dict(id=uuid.uuid4().hex, date=day, kind='breakfast', provider='employer_arranged',
                offered=True, is_meal=True, price_minor=1500, employee_paid_minor=0,
                replacement_for=None, source_file_ids=[file['id']])] if meal else []
            amount = 840 if meal else 1400
            body = req(employee_id=data['employee']['id'], id=uuid.uuid4().hex, revision=0,
                correction_reason='', details=dict(purpose='Independent private journey', project_id=None,
                    departed_at=start, returned_at=end, timezone='Europe/Berlin', source_file_ids=[file['id']],
                    home_site_ref=reference(sites[0]), first_workplace_ref=None,
                    segments=[dict(id=uuid.uuid4().hex, **{'from':start,'to':end}, site_ref=reference(sites[1]),
                        activity='work', transport='ground', necessary_stopover=False)], overnights=[],
                    meals=meals, expense_refs=[], requested_meal_minor=amount, requested_lodging_minor=0,
                    tax_choice='tax_free_only', private_intervals=[]))
            draft = self.call('POST', '/business/personnel/travel/trips', body, token=data['tech']).json['result']
            current = self.call('GET', '/business/personnel/travel/trips/' + draft['id'], token=data['tech']).json
            approved_trip = self.call('POST', '/business/personnel/travel/trips/' + draft['id'] + '/submit',
                req(employee_id=data['employee']['id'], revision=draft['revision'],
                    source_hash=current['source_hash'], confirmed=True), token=data['tech']).json['result']
            proposal = dict(employee_id=data['employee']['id'], trip_refs=[reference(approved_trip)],
                period_from=day, period_to=day, settlement_unit='trip', tax_choice='tax_free_only',
                requested_meal_minor=amount, requested_lodging_minor=0, correction_of=None,
                review_note='Independent original trip review')
            preview = self.call('POST', '/business/personnel/travel/settlements/preview', proposal).json
            local['command'] = req(**proposal, id=uuid.uuid4().hex, revision=0,
                source_hash=preview['source_hash'], preview_hash=preview['preview_hash'], confirmed=True)
        settlement = self.call('POST', '/business/personnel/travel/settlements', local['command']).json['result']
        local['settlement'] = settlement
        local['account'] = data['account']
        command = travel.TravelPostgres.payment(self, local, settlement)
        command['amount_minor'] = settlement['calculation']['totals']['tax_free_minor']
        command['paid_on'] = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
        local['payment_command'] = command
        if pay:
            local['payment'] = self.call('POST', '/business/personnel/travel/payments', command).json['result']
        return local

    def proposal(self, data, *, local=None, payments=None):
        local = local or data['travel']
        details = dict(month='2026-10', period_case_ref=reference(data['period']),
            employment_terms_refs=[reference(data['period']['sources']['employment_terms'])],
            profile_refs=[reference(data['profile'])], identity_refs=[reference(data['identity'])],
            segment_events=[], thirty_day_rule=None, entitlement_case_refs=[],
            travel_settlement_refs=[reference(local['settlement'])],
            travel_payment_refs=[reference(value) for value in (payments or [local['payment']])],
            flat_tax_decision=None, verification_note='Independent paid original; no additional wage payout')
        return dict(employee_id=data['employee']['id'], employee_revision=data['employee']['revision'],
            kind='calculation_case', rule_version=RULE_VERSION,
            source_contract_version=SOURCE_CONTRACT_VERSION, details=details,
            source_file_ids=[data['file']['id']])

    def save_case(self, proposal, previous=None):
        preview = self.call('POST', '/business/payroll/calculation-cases/preview', proposal).json
        self.assertTrue(preview['can_calculate'], preview['plan']['blockers'])
        command = req(**proposal, revision=previous['revision'] if previous else 0,
            status='active', confirmed=True, preview_hash=preview['preview_hash'])
        if previous:
            command.update(id=previous['id'], correction_reason='Independent changed factor with same original travel')
        return self.call('POST', '/business/payroll/calculation-cases', command).json, command

    def run_command(self, inputs, previous=None):
        preview = self.call('POST', '/business/payroll/preview', inputs).json
        self.assertTrue(preview['can_finalize'])
        command = req(**inputs, revision=previous['revision'] if previous else 0, confirmed=True,
            preview_hash=preview['preview_hash'], accepted_scope=preview['calculation']['scope'])
        if previous:
            command.update(id=previous['id'], correction_reason='Independent additive source/factor correction')
        return command

    def workflow(self):
        data = self.factor_period()
        data['account'] = self.call('POST', '/business/accounting/accounts', req(confirmation=True,
            code='FTRV', name='Independent synthetic reimbursement bank', kind='bank'), status=201).json
        data['travel'] = self.trip(data)
        data['case'], data['case_command'] = self.save_case(self.proposal(data))
        inputs = dict(source_schema_version=3, employee_id=data['employee']['id'],
            calculation_case_ref=reference(data['case']))
        data['run_command'] = self.run_command(inputs, data['v9'])
        data['run'] = self.call('POST', '/business/payroll/runs', data['run_command']).json
        return data

    def test_v9_v10_corrected_factor_originals_and_actual_dump_restore(self):
        data = self.workflow()
        run = data['run']
        self.assertEqual(run['calculation']['scope'], SCOPE)
        for key in AMOUNTS:
            self.assertEqual(run['calculation'][key], data['v9']['calculation'][key], key)
        self.assertFalse(run['calculation']['travel_expenses_included_in_net'])
        self.assertEqual(run['calculation']['period_details']['travel_paid_minor'], 1400)
        original_v9_pdf = self.call('GET', '/business/payroll/runs/' + run['id'] + '/pdf?revision=1').data
        original_v10_pdf = self.call('GET', '/business/payroll/runs/' + run['id'] + '/pdf?revision=2').data
        cash = public_source(self.office, data['travel']['payment']['id'], 1)
        self.assertEqual(cash['cash_movements'][0]['amount'], '14.00')
        self.assertNotIn('account_id', canonical(data['case']['sources']['travel_sources']))
        statement = PayrollStatements(self.office).get(self.owner, run['id'])['statement']
        self.assertEqual(statement['travel_summary']['tax_free_external_minor'], 1400)
        self.assertNotIn('cash_source_hash', canonical(statement))
        old_profile = data['profile']
        data['profile'] = self.call('POST', '/business/payroll/profiles', req(
            employee_id=data['employee']['id'], id=old_profile['id'], revision=old_profile['revision'],
            profile=dict(old_profile['profile'], tax_factor='0.900'), source_file_id=data['file']['id'],
            confirmed=True, correction_reason='Independent original ELStAM factor correction')).json
        data['identity'] = self.identity(data, data['identity'])
        details = dict(data['period_details'], profile_refs=[reference(data['profile'])],
                       identity_refs=[reference(data['identity'])])
        data['period'] = self.period(data, details, data['period'])
        corrected_case, correction_case_command = self.save_case(self.proposal(data), data['case'])
        corrected_input = dict(source_schema_version=3, employee_id=data['employee']['id'],
                               calculation_case_ref=reference(corrected_case))
        correction_command = self.run_command(corrected_input, run)
        corrected = self.call('POST', '/business/payroll/runs', correction_command).json
        self.assertEqual(corrected['calculation']['net_minor'], 320834)
        self.assertEqual(corrected['delta']['net_minor'], -11508)
        self.assertEqual(corrected['calculation']['period_details']['travel_paid_minor'], 1400)
        for command, expected in [(data['v9_command'], data['v9']), (data['run_command'], run),
                                  (correction_command, corrected)]:
            self.assertEqual(self.call('POST', '/business/payroll/runs', command).json, expected)
        self.assertEqual(self.call('POST', '/business/payroll/calculation-cases', data['case_command']).json, data['case'])
        self.assertEqual(public_source(self.office, data['travel']['payment']['id'], 1), cash)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_travel_payments').fetchone()[0], 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_travel_cash_events').fetchone()[0], 1)
        payment = self.call('POST', '/business/payroll/account-records', req(
            employee_id=data['employee']['id'], kind='payment', revision=0,
            source_file_id=data['file']['id'], confirmed=True,
            details=periods.accounts.PayrollAccountTests.payment_details(self, corrected, data['identity']))).json
        self.assertEqual(payment['details']['tax_free_payments_minor'], 0)
        original_ref = dict(id=data['file']['id'], revision=1, content_hash=data['file']['content_hash'])
        annual_details = dict(employer_identity_ref=reference(data['identity']),
            verification_note='Independent full-year coverage of corrected factor run and its actual payment',
            year=2026, coverage_to='2026-10-31', as_of_date='2026-11-01',
            payroll_run_refs=[reference(corrected)], payroll_payment_refs=[reference(payment)],
            imported_period_refs=[], imported_one_off_refs=[], current_calculation_case_ref=None,
            gaps=[dict(start='2026-01-01', end='2026-09-30', reason='not_employed', evidence_ref=original_ref)],
            completeness_confirmed=True)
        annual_input = dict(employee_id=data['employee']['id'], employee_revision=data['employee']['revision'],
            kind='annual_basis', details=annual_details, source_file_ids=[data['file']['id']])
        annual_preview = self.call('POST', '/business/payroll/annual-facts/preview', annual_input).json
        annual_command = req(**annual_input, revision=0, status='active', confirmed=True,
                             preview_hash=annual_preview['preview_hash'])
        annual = self.call('POST', '/business/payroll/annual-facts', annual_command).json
        self.assertEqual(annual['plan']['running_taxable_minor'], 500000)
        self.assertEqual(annual['plan']['section_rooms']['regular']['pension']['contributed_minor'], 500000)
        self.assertTrue(business_schema.validate_integrity(self.office))
        self.office.db.close()
        with disposable_restore(self.runtime) as (target, runtime, report):
            operator = PostgresOffice(target)
            try:
                approve(operator, evidence_for(operator, report))
            finally:
                operator.db.close()
            restored = PostgresOffice(runtime)
            try:
                payroll = Payroll(restored)
                self.assertEqual(payroll.finalize(self.owner, data['v9_command']), data['v9'])
                self.assertEqual(payroll.finalize(self.owner, data['run_command']), run)
                self.assertEqual(payroll.finalize(self.owner, correction_command), corrected)
                self.assertEqual(payroll.export(self.owner, run['id'], 'pdf', '1')[0], original_v9_pdf)
                self.assertEqual(payroll.export(self.owner, run['id'], 'pdf', '2')[0], original_v10_pdf)
                self.assertEqual(PayrollCalculationCases(restored).save(self.owner, data['case_command']), data['case'])
                self.assertEqual(public_source(restored, data['travel']['payment']['id'], 1), cash)
                from business_payroll_annual_basis import PayrollAnnualBasis
                self.assertEqual(PayrollAnnualBasis(restored).save(self.owner, annual_command), annual)
                self.assertTrue(business_schema.validate_integrity(restored))
            finally:
                restored.db.close()

    def test_actual_http_private_rights_bad_shapes_hashes_and_m_are_rejected(self):
        data = self.workflow()
        path = '/business/payroll/calculation-cases'
        self.call('GET', path + '/sources?employee_id=' + data['employee']['id'] + '&month=2026-10',
                  token=data['tech'], status=403)
        self.call('GET', path + '/' + data['case']['id'], token=data['tech'], status=403)
        self.call('POST', path + '/preview', self.proposal(data), token=data['tech'], status=403)
        for malformed in (None, 1, True, [], 'invalid'):
            self.call('POST', path + '/preview', dict(self.proposal(data), details=malformed), status=400)
            self.call('POST', path, req(**dict(self.proposal(data), details=malformed),
                revision=0, status='active', confirmed=True, preview_hash='a' * 64), status=400)
        for field in ('employee_id',):
            self.call('POST', path + '/preview', dict(self.proposal(data), **{field: uuid.uuid4().hex}), status=404)
        other_user = self.call('POST', '/users', dict(email='other-factor-person@example.test',
            password='Synthetic-other-factor-password-123', role='technician'), status=201).json['id']
        other = self.call('POST', '/business/employees', req(user_id=other_user,
            name='Independent other person', weekly_minutes=2400, hourly_cost_minor=1000,
            employment_from='2026-10-01', employment_to=None), status=201).json
        self.call('POST', path + '/preview', dict(self.proposal(data),
            employee_id=other['id'], employee_revision=other['revision']), status=404)
        for field in ('period_case_ref',):
            proposal = deepcopy(self.proposal(data)); proposal['details'][field]['content_hash'] = '0' * 64
            self.call('POST', path + '/preview', proposal, status=409)
        proposal = deepcopy(self.proposal(data)); proposal['details']['travel_payment_refs'] = []
        self.call('POST', path + '/preview', proposal, status=400)
        proposal = deepcopy(self.proposal(data)); proposal['details']['month'] = '2026-11'
        self.call('POST', path + '/preview', proposal, status=400)
        forged = deepcopy(data['case'])
        forged['sources']['travel_sources'][0]['payment_proof']['payments'][0]['cash_source_hash'] = '0' * 64
        with self.assertRaises(ValueError):
            validate_case_sources(self.office, forged)
        m_trip = self.trip(data, day='2026-10-28', meal=True, pay=False)
        self.assertTrue(any(day['letter_m'] for day in m_trip['settlement']['calculation']['days']))
        # The existing cash guard itself refuses an unprocessed M source.
        self.call('POST', '/business/personnel/travel/payments', m_trip['payment_command'], status=409)
        rejected = self.call('POST', path + '/preview',
            self.proposal(data, local=m_trip, payments=[data['travel']['payment']]), status=409)
        self.assertIn('ohne weiteren Lohnbestandteil', rejected.json['error'])
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_paid_prefix_repayment_freshness_and_immutable_original_replay(self):
        data = self.workflow(); local = data['travel']
        saved = deepcopy(data['case'])
        original = public_source(self.office, local['payment']['id'], 1)
        command = travel.TravelPostgres.payment(self, local, local['settlement'])
        command.update(kind='repayment', amount_minor=100, reference='Independent actual partial repayment')
        repaid = self.call('POST', '/business/personnel/travel/payments', command).json['result']
        self.assertEqual(self.call('POST', '/business/payroll/calculation-cases', data['case_command']).json, saved)
        self.assertEqual(self.call('POST', '/business/payroll/runs', data['run_command']).json, data['run'])
        self.call('POST', '/business/payroll/calculation-cases/preview', self.proposal(data), status=409)
        self.call('POST', '/business/payroll/calculation-cases/preview',
                  self.proposal(data, payments=[local['payment'], repaid]), status=409)
        self.assertEqual(public_source(self.office, local['payment']['id'], 1), original)
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_financial_and_personnel_revocation_are_fresh_for_sources_and_replays(self):
        data = self.workflow()
        uid = self.call('POST', '/users', dict(email='factor-financial-review@example.test',
            password='Synthetic-factor-review-password-123', role='accountant'), status=201).json['id']
        token = self.login('factor-financial-review@example.test', 'Synthetic-factor-review-password-123')
        permissions = BusinessFoundation(self.office)
        for permission in ('personnel.read', 'personnel.approve', 'accounting.read', 'finance.read'):
            permissions.save_grant(self.owner, req(user_id=uid, permission=permission,
                scope='*', effect='allow', revision=0))
        self.call('POST', '/business/payroll/calculation-cases/preview', self.proposal(data), token=token)
        permissions.save_grant(self.owner, req(user_id=uid, permission='finance.read',
            scope='*', effect='deny', revision=1))
        self.call('POST', '/business/payroll/calculation-cases/preview', self.proposal(data), token=token, status=403)
        choices = self.call('GET', '/business/payroll/calculation-cases/sources?employee_id='
            + data['employee']['id'] + '&month=2026-10', token=token).json
        self.assertEqual(choices['travel_payment_proofs'], [])
        permissions.save_grant(self.owner, req(user_id=uid, permission='personnel.read',
            scope='*', effect='deny', revision=1))
        self.call('POST', '/business/payroll/calculation-cases', data['case_command'], token=token, status=403)
        self.call('POST', '/business/payroll/runs', data['run_command'], token=token, status=403)
        self.assertTrue(business_schema.validate_integrity(self.office))


if __name__ == '__main__':
    unittest.main()
