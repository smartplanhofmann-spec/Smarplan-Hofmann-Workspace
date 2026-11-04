"""Real travel journals through EÜR, bank reconciliation and restore scope."""
import copy
import unittest

from core import Problem, canonical
from business_accounting import Accounting
from business_accounting_euer import EuerAccounting, validate_integrity as validate_euer
from business_bank_reconciliation import BankReconciliation, validate_integrity as validate_bank
from business_foundation import BusinessFoundation
from business_schema import financial_accounting_horizon, _validate_financial_accounting_horizon
from business_travel_allowances import TABLES, validate_integrity as validate_travel
from travel_allowance_cash import public_source, record_payment
import test_business_accounting as accounting_fixture
import test_business_bank_reconciliation as bank_fixture
import test_business_travel_allowances as travel_fixture
from test_business_planning import rid


class TravelFinanceTests(unittest.TestCase):
    def setUp(self):
        self.f = travel_fixture.TravelWorkflowTests('runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.office, self.owner = self.f.office, self.f.owner
        self.euer = EuerAccounting(self.office, clock=lambda: self.f.now)
        self.b = bank_fixture.BankTests('runTest')
        self.b.office, self.b.owner, self.b.account = self.office, self.owner, self.f.account
        self.b.bank = BankReconciliation(self.office, clock=lambda: self.f.now)
        self.b.configure()
        self.settlement = self.f.api.approve(self.owner, self.f.approval(self.f.submitted()))['result']

    def failure(self, status, call, *args):
        with self.assertRaises(Problem) as caught:
            call(*args)
        self.assertEqual(caught.exception.status, status, caught.exception.message)
        return caught.exception

    def post(self, operation, payload, actor=None):
        actor = actor or self.owner
        state = self.euer.state(actor)
        body = dict(operation=operation, payload=payload, expected_revision=state['revision'],
                    state_hash=state['state_hash'], reason='Reviewed actual travel reimbursement',
                    evidence_reference='Original payment checked')
        preview = self.euer.preview(actor, body)
        return self.euer.confirm(actor, dict(body, request_id=rid(),
                                preview_hash=preview['preview_hash'], confirmation=True))

    def paid(self, amount=1400):
        body = self.f.payment(self.settlement, amount)
        return record_payment(self.f.api, self.owner, body)['result'], body

    def payload(self, payment):
        source = public_source(self.office, payment['id'], payment['revision'])
        return dict(payment_id=payment['id'], revision=payment['revision'],
                    source_hash=source['source_hash'],
                    accounts={'travel_allowance': '6664'} if source['cash_movements'] else {})

    def period(self, action, revision):
        return self.post('period', dict(period='2026-10', action=action,
            expected_period_revision=revision, attestation=dict(bank_reconciled=True,
                originals_complete=True, special_cases_reviewed=True)))

    def bank_match(self, *payments):
        self.b.binding = self.b.bank.save_account(self.owner, self.b.account_body())
        amounts = ['-' + public_source(self.office, payment['id'])['cash_movements'][0]['amount']
                   for payment in payments]
        statement, _ = self.b.save_statement(self.b.rows(*amounts, day='2026-10-27'),
            period_from='2026-10-01', period_to='2026-10-31')
        for line, payment in zip(statement['lines'], payments):
            source = public_source(self.office, payment['id'])['cash_movements'][0]
            self.b.match(line['transaction_id'], [self.b.link(line['transaction_id'],
                         source['id'], source['amount'])])
        report, command = self.b.report([statement], period='2026-10')
        return statement, report, command

    def test_two_actual_partial_payments_have_exact_expense_and_bank_evidence(self):
        self.assertEqual(self.euer.report(self.owner, 2026)['totals']['confirmed_expenses'], '0.00')
        first, original_command = self.paid(1000)
        second, _ = self.paid(400)
        for payment in (first, second):
            self.post('travel_cash', self.payload(payment))
        report = self.euer.report(self.owner, 2026)
        self.assertEqual(report['totals']['confirmed_expenses'], '14.00')
        self.assertEqual(report['totals']['confirmed_input_vat'], '0.00')
        self.assertEqual(report['totals']['confirmed_output_vat'], '0.00')
        self.assertEqual(report['totals']['euer_surplus'], '-14.00')
        self.assertEqual(len(report['cash_movements']), 2)
        _, bank, _ = self.bank_match(first, second)
        self.assertTrue(bank['record']['payload']['complete'])
        self.assertEqual(record_payment(self.f.api, self.owner, original_command)['result'], first)
        for validator in (validate_travel, validate_euer, validate_bank):
            self.assertTrue(validator(self.office))

    def test_finance_permissions_allow_aggregate_but_never_private_travel(self):
        payment, command = self.paid()
        user = self.office.add_user('travel-finance@example.test', 'Synthetic-password-123', 'accountant')
        actor = dict(id=user, role='owner')  # A caller cannot upgrade its stored role.
        for permission in ('accounting.read', 'accounting.prepare', 'accounting.admin',
                           'finance.read', 'finance.write', 'bank.read'):
            BusinessFoundation(self.office).save_grant(self.owner, dict(request_id=rid(),
                user_id=user, permission=permission, effect='allow', scope='*', revision=0))
        self.failure(403, self.f.api.sources, actor, self.f.employee['id'])
        self.post('travel_cash', self.payload(payment), actor)
        statement, _, _ = self.bank_match(payment)
        visible = canonical([self.euer.sources(actor), self.euer.journal(actor),
            self.euer.report(actor, 2026),
            self.b.bank.candidates(actor, statement['lines'][0]['transaction_id'])])
        for secret in (self.f.employee['id'], self.f.employee['name'], self.settlement['id'],
                       command['reference_file_id'], self.f.place['id'], 'Actual customer visit'):
            self.assertNotIn(secret, visible)
        self.assertEqual(self.euer.report(actor, 2026)['totals']['confirmed_expenses'], '14.00')

    def test_void_preserves_originals_and_demands_explicit_financial_correction(self):
        payment, body = self.paid()
        posted = self.post('travel_cash', self.payload(payment))
        _, bank, bank_command = self.bank_match(payment)
        bank_id = bank['record']['id']
        original_bank = self.b.bank.export(self.owner, bank_id, 'pdf')[0]
        export = self.post('export', dict(year=2026))
        original_euer = self.euer.exported(self.owner, export['id'])
        original_source = public_source(self.office, payment['id'], 1)
        void = record_payment(self.f.api, self.owner, dict(body, request_id=rid(), revision=1,
            action='void', correction_reason='Original proves duplicate transcription',
            source_hash=self.f.api._basis(self.f.employee['id'])))['result']
        self.assertEqual(public_source(self.office, payment['id'])['cash_movements'], [])
        self.assertEqual(public_source(self.office, payment['id'], 1), original_source)
        self.assertIn('travel_cash_source_changed',
                      [issue['code'] for issue in self.euer.report(self.owner, 2026)['issues']])
        self.assertFalse(self.b.bank.reconciliation(self.owner, bank_id)['current'])
        self.post('correct', dict(entry_id=posted['id'], operation='travel_cash', payload=self.payload(void)))
        self.assertEqual(self.euer.report(self.owner, 2026)['totals']['confirmed_expenses'], '0.00')
        self.assertEqual(self.euer.exported(self.owner, export['id']), original_euer)
        self.assertEqual(self.b.bank.export(self.owner, bank_id, 'pdf')[0], original_bank)
        self.assertEqual(self.b.bank.save_reconciliation(self.owner, bank_command), bank)
        for validator in (validate_travel, validate_euer, validate_bank):
            self.assertTrue(validator(self.office))

    def test_closed_period_blocks_new_cash_old_date_correction_and_void_but_not_replay(self):
        payment, body = self.paid(1000)
        self.post('travel_cash', self.payload(payment))
        self.period('close', 0)
        self.assertEqual(record_payment(self.f.api, self.owner, body)['result'], payment)
        self.failure(409, record_payment, self.f.api, self.owner, self.f.payment(self.settlement, 400))
        correction = dict(body, request_id=rid(), revision=1, action='correct', paid_on='2026-11-02',
                          correction_reason='Actual payment date corrected',
                          source_hash=self.f.api._basis(self.f.employee['id']))
        self.failure(409, record_payment, self.f.api, self.owner, correction)
        self.failure(409, record_payment, self.f.api, self.owner,
                     dict(correction, request_id=rid(), action='void', paid_on=body['paid_on']))
        self.period('reopen', 1)
        self.assertEqual(record_payment(self.f.api, self.owner, correction)['result']['revision'], 2)

    def test_reference_is_reserved_against_legacy_cash_in_both_directions(self):
        helper = accounting_fixture.AccountingTests('runTest')
        helper.office, helper.owner, helper.account = self.office, self.owner, self.f.account
        helper.api = Accounting(self.office, clock=lambda: self.f.now)
        from business_finance import Finance
        helper.finance = Finance(self.office, clock=lambda: self.f.now)
        payment, travel_command = self.paid(1000)
        cash = helper.payment(amount='10.00')
        self.failure(409, helper.api.import_payment, self.owner,
                     helper.import_body(cash, evidence_reference=travel_command['reference']))
        other = helper.payment(amount='4.00')
        reference = 'PREVIOUS-ACTUAL-BANK-TRANSFER'
        helper.api.import_payment(self.owner, helper.import_body(other, evidence_reference=reference))
        self.failure(409, record_payment, self.f.api, self.owner,
                     self.f.payment(self.settlement, 400, reference=reference))

    def test_restore_adds_exact_travel_scope_and_preserves_old_bank_evidence(self):
        self.paid()
        current = financial_accounting_horizon(self.office)
        self.assertEqual(current['schema_version'], 13)
        _validate_financial_accounting_horizon(current, 14)
        current = {key: value for key, value in current.items() if key not in ('opening_balances','historical_assets')}
        current['schema_version'] = 11
        self.assertEqual(set(current['travel_cash']['table_counts']), set(TABLES))
        _validate_financial_accounting_horizon(current, 12)
        old = {key: value for key, value in current.items() if key != 'travel_cash'}
        old['schema_version'] = 10
        original = canonical(old)
        _validate_financial_accounting_horizon(old, 11)
        self.assertEqual(canonical(old), original)
        for case in ('missing', 'bool', 'negative', 'hash', 'extra'):
            bad = copy.deepcopy(current)
            travel = bad['travel_cash']
            if case == 'missing': travel['table_counts'].pop(TABLES[0])
            elif case == 'bool': travel['table_counts'][TABLES[0]] = True
            elif case == 'negative': travel['table_counts'][TABLES[0]] = -1
            elif case == 'hash': travel['sha256'] = 'invalid'
            else: travel['table_counts']['business_fake'] = 0
            with self.subTest(case=case), self.assertRaises(ValueError):
                _validate_financial_accounting_horizon(bad, 12)


if __name__ == '__main__':
    unittest.main()
