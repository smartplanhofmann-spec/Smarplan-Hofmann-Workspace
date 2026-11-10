"""Actual mixed adjustments, zero cash, MFA, EÜR, annual original and full restore."""
from copy import deepcopy
from decimal import Decimal
import unittest

import business_schema
from business_payroll import Payroll
from business_payroll_accounts import PayrollAccounts
from business_payroll_annual_basis import PayrollAnnualBasis
from business_payroll_cash import PayrollCash
from business_accounting_euer import EuerAccounting
from business_payroll_facts import reference
from online.store import PostgresOffice
from online import test_business_payroll_payment_dates_pg as dates
from online.test_postgres_accounting_components_integration import disposable_restore, evidence_for, approve


@unittest.skipUnless(dates.prior.fixture.DSN, 'Guarded disposable loopback PostgreSQL required')
class ActualAdjustmentPostgres(unittest.TestCase):
    setUpClass = classmethod(dates.ActualPaymentDatesPostgres.setUpClass.__func__)
    windows_calculate = dates.ActualPaymentDatesPostgres.windows_calculate
    setUp = dates.ActualPaymentDatesPostgres.setUp
    reopen = dates.ActualPaymentDatesPostgres.reopen
    call = dates.ActualPaymentDatesPostgres.call
    login = dates.ActualPaymentDatesPostgres.login
    sources = dates.ActualPaymentDatesPostgres.sources
    profile = dates.ActualPaymentDatesPostgres.profile
    post = dates.ActualPaymentDatesPostgres.post
    cash_body = dates.ActualPaymentDatesPostgres.cash_body
    cash_payload = dates.ActualPaymentDatesPostgres.cash_payload
    private_file = dates.ActualPaymentDatesPostgres.private_file
    forecast = dates.ActualPaymentDatesPostgres.forecast
    save_case = dates.ActualPaymentDatesPostgres.save_case
    prepare_run = dates.ActualPaymentDatesPostgres.prepare_run
    review = dates.ActualPaymentDatesPostgres.review
    pay = dates.ActualPaymentDatesPostgres.pay
    workflow = dates.ActualPaymentDatesPostgres.workflow
    correction = dates.ActualPaymentDatesPostgres.correction
    import_net = dates.ActualPaymentDatesPostgres.import_net

    def adjustment(self, data, prior, paid, amount, version):
        self.forecast(data, amount)
        current = self.call('GET', '/business/payroll/multiple-one-off-cases/'+data['case']['id']).json
        case = self.save_case(data, current)
        review = self.review(data)
        review.update(schema_version=2 if version == 4 else 3,
            contract='source5_actual_net_repayment_review_v1' if version == 4 else 'source5_actual_net_adjustment_review_v1')
        inputs = dict(employee_id=data['employee']['id'], source_schema_version=5,
            multiple_one_off_case_ref=reference(case), settlement_review=review)
        preview = self.call('POST', '/business/payroll/preview', inputs).json
        command = dates.prior.req(**inputs, id=prior['id'], revision=prior['revision'], confirmed=True,
            preview_hash=preview['preview_hash'], accepted_scope=preview['calculation']['scope'],
            correction_reason='Actual corrected private source; immutable original signed payment prefix')
        run = self.call('POST', '/business/payroll/runs', command).json
        details = deepcopy(paid['details']); index = len(details['payments'])
        details.update(run_id=run['id'], run_revision=run['revision'], payment_source_schema_version=version,
            prior_payment_ref=reference(paid))
        delta = run['settlement_transition']['net_delta_minor']
        if delta:
            details['payments'].append(dict(paid_on='2026-11-03', amount_minor=delta,
                payment_reference='SYN-PG-ACTUAL-NET-ADJUSTMENT-'+str(run['revision'])))
            details['settlement_allocations'].append(dict(payment_index=index, running_minor=0,
                one_off_allocations=[dict(event_key=run['settlement_transition']['event_key'], net_minor=delta)]))
        payment_command = dates.prior.req(employee_id=data['employee']['id'], kind='payment', revision=0,
            source_file_id=data['file']['id'], confirmed=True, details=details)
        accepted = self.call('POST', '/business/payroll/account-records', payment_command).json
        self.assertEqual(accepted['details']['payments'][:index], paid['details']['payments'])
        self.assertEqual(accepted['details']['settlement_allocations'][:index], paid['details']['settlement_allocations'])
        self.assertEqual(self.call('POST', '/business/payroll/runs', command).json, run)
        self.assertEqual(self.call('POST', '/business/payroll/account-records', payment_command).json, accepted)
        print('Actual PostgreSQL net adjustment', run['revision'], version, delta, flush=True)
        return run, accepted, command, payment_command

    def test_actual_positive_negative_zero_adjustments_private_mfa_euer_annual_and_restore(self):
        data = self.workflow(money=True, windows_original=True)
        original, original_payment = data['run'], data['payment']
        original_pdf = self.call('GET', '/business/payroll/runs/'+original['id']+'/pdf').data
        _, _, positive_command = self.correction(data)
        run = self.call('POST', '/business/payroll/runs', positive_command).json
        paid, _ = self.pay(data, run, original_payment, day='2026-11-01')
        batch, _ = self.import_net(paid, [2]); self.post('payroll_cash', self.cash_payload(batch))
        histories = [deepcopy(paid)]
        cash_commands = []
        for amount, version, expected in ((2000000, 4, -1), (1500000, 5, 1),
                (2000000, 5, -1), (2000000, 5, 0)):
            run, paid, command, payment_command = self.adjustment(data, run, paid, amount, version)
            plan = paid['sources']['single_payment_plan']
            delta = plan['net_delta_minor']
            self.assertEqual((delta > 0)-(delta < 0), expected)
            self.assertEqual(delta, plan['total_net_minor']-plan['prior_total_net_minor'])
            self.assertEqual(plan['schema_version'], version)
            if expected:
                indexes = plan['new_payment_indexes']; self.assertEqual(len(indexes), 1)
                batch, cash_command = self.import_net(paid, indexes)
                movement = batch['public_source']['cash_movements'][0]
                self.assertEqual(movement['direction'], 'in' if delta < 0 else 'out')
                self.assertEqual(Decimal(movement['amount']), Decimal(abs(delta))/100)
                self.post('payroll_cash', self.cash_payload(batch)); cash_commands.append((cash_command, batch))
            else:
                self.assertEqual(plan['new_payment_indexes'], [])
                self.assertEqual(paid['details']['payments'], histories[-1]['details']['payments'])
                empty = self.cash_body(paid); empty['sources'][0]['payment_indexes'] = []
                self.call('POST', '/business/payroll/cash/preview', empty, status=400)
            histories.append(deepcopy(paid))
        report = self.call('GET', '/business/accounting/euer/report?year=2026').json
        self.assertEqual(Decimal(report['totals']['confirmed_expenses']),
            Decimal(run['calculation']['net_minor']-run['calculation']['net_deductions_minor'])/100)
        annual_details = deepcopy(data['annual_basis']['details'])
        annual_details.update(as_of_date='2026-11-03', current_calculation_case_ref=None,
            payroll_run_refs=[reference(run)], payroll_payment_refs=[reference(paid)])
        proposal = dict(employee_id=data['employee']['id'], employee_revision=data['employee']['revision'],
            kind='annual_basis', details=annual_details, source_file_ids=[data['file']['id']])
        preview = self.call('POST', '/business/payroll/annual-facts/preview', proposal).json
        annual_command = dates.prior.req(**proposal, revision=0, status='active', confirmed=True, preview_hash=preview['preview_hash'])
        annual = self.call('POST', '/business/payroll/annual-facts', annual_command).json
        self.assertEqual(annual['plan']['earlier_other_taxable_minor'], 50000)
        self.assertEqual(len(annual['plan']['projection']['prior_one_offs']), 1)
        self.call('GET', '/business/payroll/account-records/'+paid['id'], token=data['tech'], status=403)
        self.call('POST', '/business/payroll/account-records', payment_command, token=data['tech'], status=403)
        own = self.call('GET', '/business/payroll/employee-statements/'+run['id'], token=data['tech']).json
        self.assertNotIn('settlement_review', str(own))
        self.token = self.login('order-owner@example.test', 'Synthetic-owner-password-123')
        self.assertEqual(self.call('POST', '/business/payroll/account-records', payment_command).json, paid)
        self.assertTrue(business_schema.validate_integrity(self.office)); self.office.db.close()
        with disposable_restore(self.runtime) as (target, runtime, restore_report):
            operator = PostgresOffice(target)
            try: approve(operator, evidence_for(operator, restore_report))
            finally: operator.db.close()
            restored = PostgresOffice(runtime)
            try:
                self.assertEqual(Payroll(restored).finalize(self.owner, command), run)
                self.assertEqual(PayrollAccounts(restored).save(self.owner, payment_command), paid)
                for cash_command, batch in cash_commands:
                    self.assertEqual(PayrollCash(restored).confirm(self.owner, cash_command), batch)
                self.assertEqual(PayrollAnnualBasis(restored).save(self.owner, annual_command), annual)
                self.assertEqual(EuerAccounting(restored).report(self.owner, 2026)['totals'], report['totals'])
                self.assertEqual(Payroll(restored).export(self.owner, original['id'], 'pdf', revision='1')[0], original_pdf)
                self.assertTrue(business_schema.validate_integrity(restored))
            finally: restored.db.close()


if __name__ == '__main__': unittest.main()
