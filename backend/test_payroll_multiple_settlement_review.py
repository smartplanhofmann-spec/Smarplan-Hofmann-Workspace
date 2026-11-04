"""Independent review: accepted actual transfers survive unpaid run revisions."""
import test_business_payroll_multiple as multiple_fixture
from test_business_payroll_periods import command
import test_business_payroll_accounts as account_fixture
from business_payroll_facts import reference
from core import Problem
import business_schema
import unittest


class EarlierActualSettlement(unittest.TestCase):
    def setUp(self):
        self.case = multiple_fixture.MultipleWorkflow('runTest')
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.f = self.case.f

    def revised_run(self, *, intermediate_source3=False):
        c, f = self.case, self.f
        inputs = dict(source_schema_version=3, employee_id=f.employee['id'],
                      calculation_case_ref=reference(c.source['running_calculation_case']))
        original_command = command(f.payroll, f.owner, inputs)
        old = f.payroll.finalize(f.owner, original_command)
        self.running = old['calculation']['payout_minor']
        self.old_parts = [dict(paid_on='2026-10-30', amount_minor=self.running,
                               payment_reference='ACTUAL-REVIEW-RUNNING-ORIGINAL')]
        paid, paid_command = f.save_account(f.data, 'payment',
            account_fixture.PayrollAccountTests.payment_details(f, old, f.identity, payments=self.old_parts))
        fact, _ = c.case()
        if intermediate_source3:
            f.payroll.finalize(f.owner, command(f.payroll, f.owner, inputs) |
                dict(id=old['id'], revision=1, correction_reason='Review before bonus source'))
        else:
            f.payroll.finalize(f.owner, c.run_command(fact, id=old['id'], revision=1,
                correction_reason='One bonus after the actual running transfer'))
            fact, _ = c.case(dict(c.details(), verification_note='Rechecked unchanged full claim'),
                id=fact['id'], revision=1, correction_reason='Recheck before bonus payment')
        run = f.payroll.finalize(f.owner, c.run_command(fact, id=old['id'], revision=2,
            correction_reason='Latest unpaid bonus revision'))
        self.assertEqual(f.payroll.finalize(f.owner, original_command), old)
        self.original_payment_command = paid_command
        return run, paid

    def payment(self, run, prior, *, relabel=False):
        c, f = self.case, self.f
        bonus = run['calculation']['payout_minor'] - self.running
        parts = [dict(self.old_parts[0]), dict(paid_on='2026-10-31', amount_minor=bonus,
            payment_reference='ACTUAL-REVIEW-BONUS')]
        if relabel:
            parts[0]['payment_reference'] = 'REPLACED-OLD-ACTUAL-REFERENCE'
        details = account_fixture.PayrollAccountTests.payment_details(f, run, f.identity, payments=parts)
        details.update(payment_source_schema_version=1, prior_payment_ref=prior,
            settlement_allocations=[dict(payment_index=0, running_minor=self.running,
                one_off_allocations=[]), dict(payment_index=1, running_minor=0,
                one_off_allocations=[dict(event_key=c.source['components'][0]['planned_receipts'][0]['event_key'],
                    net_minor=bonus)])])
        return f.save_account(f.data, 'payment', details)[0]

    def test_unpaid_intermediate_source5_cannot_erase_actual_paid_running(self):
        run, _ = self.revised_run()
        before = self.f.office.db.execute(
            "SELECT COUNT(*) FROM business_payroll_account_events WHERE kind='payment'").fetchone()[0]
        with self.assertRaises(Problem) as raised:
            self.payment(run, None, relabel=True)
        self.assertEqual(raised.exception.status, 409)
        self.assertEqual(self.f.office.db.execute(
            "SELECT COUNT(*) FROM business_payroll_account_events WHERE kind='payment'").fetchone()[0], before)

    def test_actual_original_payment_is_bound_across_unpaid_source5_revision(self):
        run, paid = self.revised_run()
        receipt = self.payment(run, reference(paid))
        self.assertEqual(receipt['details']['payments'][0], self.old_parts[0])
        self.assertEqual(receipt['sources']['single_payment_plan']['preserved_prior_payment_indexes'], [0])
        self.assertEqual(receipt['sources']['single_payment_plan']['new_payment_indexes'], [1])
        self.assertTrue(business_schema.validate_integrity(self.f.office))

    def test_actual_original_payment_is_bound_across_unpaid_source3_revision(self):
        run, paid = self.revised_run(intermediate_source3=True)
        receipt = self.payment(run, reference(paid))
        self.assertEqual(receipt['details']['payments'][0], self.old_parts[0])
        self.assertEqual(receipt['sources']['single_payment_plan']['preserved_prior_payment_indexes'], [0])
        self.assertTrue(business_schema.validate_integrity(self.f.office))


if __name__ == '__main__':
    unittest.main()
