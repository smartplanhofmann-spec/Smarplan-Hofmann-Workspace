"""Whole original ownership across employees, legacy decisions and races."""
import base64
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from business_personnel_workflow import PersonnelWorkflow, dispatch, validate_integrity, _validate_expense_transition
from core import Office, Problem
from test_business_planning import BusinessFixture, rid


class PreFixPersonnel(PersonnelWorkflow):
    """Build controlled old accepted duplicates; old production used no global gate."""
    def _ensure_expense_originals_available(self, expense):
        pass


class ExpenseOriginalTests(BusinessFixture, unittest.TestCase):
    def setUp(self):
        self.prepare()
        self.hr = PersonnelWorkflow(self.office, clock=lambda: self.now)
        uid = self.office.add_user('other-expense@example.test', 'Synthetic-expense-password-123', 'technician')
        self.other_actor = dict(id=uid, role='technician')
        self.second = self.call(self.planning, 'save_employee', self.owner, dict(request_id=rid(), user_id=uid,
            name='Second synthetic employee', weekly_minutes=2400, hourly_cost_minor=3500))

    def draft(self, actor=None, employee=None, marker=b'same whole original'):
        actor, employee = actor or self.technician, employee or self.employee
        file = self.hr.upload(actor, dict(request_id=rid(), employee_id=employee['id'], purpose='expense_receipt',
            owner_visible=True, filename='ticket.pdf', media_type='application/pdf',
            content_base64=base64.b64encode(b'%PDF-1.4\n'+marker+b'\n%%EOF').decode()))
        return self.hr.save_expense(actor, dict(request_id=rid(), employee_id=employee['id'], revision=0,
            purpose='Synthetic actual ticket', start_date='2026-10-23', end_date='2026-10-24',
            items=[dict(date='2026-10-23', description='Whole ticket', amount_minor=4987, currency='EUR', receipt_file_id=file['id'])]))

    def change(self, record, action, actor=None, api=None, **values):
        return (api or self.hr).expense_action(actor or self.owner, record['id'], action,
            dict(request_id=rid(), revision=record['revision'], **values))

    def paid(self, record, action='reimburse', **changes):
        return self.change(record, action, amount_minor=4987, confirmed=True, paid_on='2026-10-25',
            payment_reference=rid(), **changes)

    def legacy_pair(self):
        old = PreFixPersonnel(self.office, clock=lambda: self.now)
        first, second = self.draft(), self.draft(self.other_actor, self.second)
        first = self.change(first, 'submit', self.technician, old)
        second = self.change(second, 'submit', self.other_actor, old)
        return old, first, second

    def test_whole_original_is_reserved_company_wide_in_all_active_states_without_private_disclosure(self):
        first, second = self.draft(), self.draft(self.other_actor, self.second)
        self.assertNotEqual(first['items'][0]['receipt_file_id'], second['items'][0]['receipt_file_id'])
        first = self.change(first, 'submit', self.technician)
        for status in ('submitted', 'approved', 'reimbursed'):
            with self.subTest(status=status):
                before = self.office.db.execute('SELECT COUNT(*) FROM business_personnel_requests').fetchone()[0]
                with self.assertRaises(Problem) as rejected:
                    self.change(second, 'submit', self.other_actor)
                self.assertEqual((rejected.exception.status, rejected.exception.request_resolution), (409, 'not_accepted'))
                for private in (first['id'], self.employee['id'], first['items'][0]['receipt_file_id'], '4987'):
                    self.assertNotIn(private, rejected.exception.message)
                self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_personnel_requests').fetchone()[0], before)
                self.assertEqual(self.hr.get(self.other_actor, 'expense', second['id']), second)
            if status == 'submitted': first = self.change(first, 'approve', reason='Checked original')
            elif status == 'approved': first = self.paid(first)
        self.problem(403, lambda: self.hr.get(self.other_actor, 'expense', first['id']))
        self.assertTrue(validate_integrity(self.office))

    def test_legacy_submitted_conflict_blocks_approval_then_rejection_releases_original(self):
        _, first, second = self.legacy_pair()
        self.problem(409, lambda: self.change(second, 'approve', reason='Must not approve duplicate'))
        self.change(first, 'reject', reason='Duplicate old submission')
        self.assertEqual(self.change(second, 'approve', reason='Only remaining whole ticket')['status'], 'approved')
        self.assertTrue(validate_integrity(self.office))

    def test_legacy_approved_conflict_blocks_payment_and_withdrawal_is_append_only_replayable(self):
        old, first, second = self.legacy_pair()
        first = self.change(first, 'approve', api=old, reason='Old independent decision A')
        second = self.change(second, 'approve', api=old, reason='Old independent decision B')
        historical = self.hr.get(self.owner, 'expense', first['id'], history=True)
        self.problem(409, lambda: self.paid(second))
        command = dict(request_id=rid(), revision=first['revision'], reason='Old duplicate approval withdrawn; no money paid')
        path = '/personnel/expenses/'+first['id']+'/withdraw-approval'
        result, code, _ = dispatch(self.office, self.owner, path, 'POST', command)
        self.assertEqual((code, result['status'], result['payments']), (200, 'rejected', []))
        self.assertEqual(self.hr.get(self.owner, 'expense', first['id'], history=True)['items'][:-1], historical['items'])
        paid = self.paid(second)
        self.assertEqual(paid['status'], 'reimbursed')
        self.assertEqual(dispatch(self.office, self.owner, path, 'POST', command)[0], result)
        self.assertTrue(validate_integrity(self.office))
        with self.office.db:
            self.office.db.execute("UPDATE users SET role='accountant' WHERE id=?", (self.owner['id'],))
        self.problem(403, lambda: dispatch(self.office, self.owner, path, 'POST', command))

    def test_accepted_legacy_payment_receipt_is_not_rewritten_when_new_duplicates_are_blocked(self):
        old, first, second = self.legacy_pair()
        first = self.change(first, 'approve', api=old, reason='Old decision')
        second = self.change(second, 'approve', api=old, reason='Old decision')
        command = dict(request_id=rid(), revision=first['revision'], amount_minor=4987, confirmed=True,
            paid_on='2026-10-25', payment_reference='SYNTHETIC-OLD-ACCEPTED')
        accepted = old.expense_action(self.owner, first['id'], 'reimburse', command)
        self.assertEqual(self.hr.expense_action(self.owner, first['id'], 'reimburse', command), accepted)
        self.problem(409, lambda: self.paid(second))
        self.problem(409, lambda: self.change(accepted, 'withdraw-approval', reason='Cannot erase actual payment'))
        self.assertEqual(self.hr.get(self.owner, 'expense', first['id']), accepted)

    def test_full_actual_repayment_releases_original_but_never_erases_payment_facts(self):
        first, second = self.draft(), self.draft(self.other_actor, self.second)
        first = self.change(self.change(first, 'submit', self.technician), 'approve', reason='Checked')
        first = self.paid(first)
        self.problem(409, lambda: self.change(second, 'submit', self.other_actor))
        repaid = self.paid(first, 'reverse-reimbursement')
        self.assertEqual([p['kind'] for p in repaid['payments']], ['reimbursement', 'repayment'])
        self.assertEqual(self.change(second, 'submit', self.other_actor)['status'], 'submitted')
        self.assertEqual(self.hr.get(self.owner, 'expense', first['id']), repaid)
        self.assertTrue(validate_integrity(self.office))

    def test_withdrawal_needs_real_other_reviewer_reason_and_current_revision(self):
        first = self.change(self.change(self.draft(), 'submit', self.technician), 'approve', reason='Checked')
        self.problem(400, lambda: self.change(first, 'withdraw-approval', reason=' '))
        self.problem(409, lambda: self.change(dict(first, revision=1), 'withdraw-approval', reason='Stale'))
        with self.office.db:
            self.office.db.execute("UPDATE users SET role='owner' WHERE id=?", (self.technician['id'],))
        self.problem(403, lambda: self.change(first, 'withdraw-approval', self.technician, reason='Own claim'))
        self.assertEqual(self.hr.get(self.owner, 'expense', first['id']), first)

    def test_independent_database_connections_accept_only_one_simultaneous_employee_submission(self):
        drafts = [self.draft(), self.draft(self.other_actor, self.second)]
        barrier = threading.Barrier(2)
        def submit(index):
            connection = Office(self.path)
            try:
                api = PersonnelWorkflow(connection, clock=lambda: self.now)
                barrier.wait(timeout=10)
                try:
                    return self.change(drafts[index], 'submit', [self.technician, self.other_actor][index], api)['status']
                except Problem as error:
                    return error.status
            finally:
                connection.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(submit, range(2)))
        self.assertCountEqual(result, ['submitted', 409])
        self.assertTrue(validate_integrity(self.office))

    def test_different_originals_remain_independent(self):
        first, second = self.draft(), self.draft(self.other_actor, self.second, marker=b'other whole original')
        for record, actor in ((first, self.technician), (second, self.other_actor)):
            self.assertEqual(self.change(record, 'submit', actor)['status'], 'submitted')

    def test_new_withdrawal_does_not_reinterpret_an_old_unmarked_invalid_transition(self):
        first = self.change(self.change(self.draft(), 'submit', self.technician), 'approve', reason='Checked')
        withdrawn = self.change(first, 'withdraw-approval', reason='Duplicate cancelled before payment')
        self.assertEqual(withdrawn['decision']['operation'], 'withdraw-approval')
        _validate_expense_transition(withdrawn, first, self.technician['id'])
        unmarked = dict(withdrawn, decision={k:v for k,v in withdrawn['decision'].items() if k != 'operation'})
        with self.assertRaisesRegex(ValueError, 'Explicit approval withdrawal'):
            _validate_expense_transition(unmarked, first, self.technician['id'])


if __name__ == '__main__':
    unittest.main()
