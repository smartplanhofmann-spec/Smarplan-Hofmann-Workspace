"""Private HR evidence, expense lifecycle and frozen monthly source contracts."""
import base64
import json
import sqlite3
import unittest

from business_personnel_workflow import PersonnelWorkflow, validate_integrity, dispatch, _sha
from business_time import TimeTracking
from core import Problem
from test_business_planning import BusinessFixture, rid


class PersonnelWorkflowTests(BusinessFixture, unittest.TestCase):
    def setUp(self):
        self.prepare()
        self.now = self.now.replace(hour=20)
        self.hr = PersonnelWorkflow(self.office, clock=lambda: self.now)
        self.time = TimeTracking(self.office, clock=lambda: self.now)

    def upload(self, *, purpose='personnel', actor=None, visible=False, **extra):
        content = b'%PDF-1.4\nSynthetic personnel evidence ' + extra.pop('marker', b'one') + b'\n%%EOF'
        return self.hr.upload(actor or self.owner, dict(request_id=rid(), employee_id=self.employee['id'],
            purpose=purpose, owner_visible=visible, filename='nachweis.pdf', media_type='application/pdf',
            content_base64=base64.b64encode(content).decode(), **extra))

    def agreement(self, **changes):
        file = self.upload()
        return self.hr.save_agreement(self.owner, dict(request_id=rid(), employee_id=self.employee['id'], revision=0,
            effective_from='2026-01-01', employment_kind='regular', pay_basis='monthly', amount_minor=350000,
            currency='EUR', reference_file_id=file['id'], notes='Belegte Vereinbarung', **changes))

    def expense_body(self, file=None, **changes):
        file = file or self.upload(purpose='expense_receipt', actor=self.technician, visible=True, marker=b'expense')
        return {**dict(request_id=rid(), employee_id=self.employee['id'], revision=0, purpose='Kundenbesuch',
            start_date='2026-10-23', end_date='2026-10-24', items=[dict(date='2026-10-23',
            description='Belegte Bahnfahrt', amount_minor=4987, currency='EUR', receipt_file_id=file['id'], project_id=self.project)]), **changes}

    def approved_expense(self):
        expense = self.hr.save_expense(self.technician, self.expense_body())
        expense = self.hr.expense_action(self.technician, expense['id'], 'submit', dict(request_id=rid(), revision=expense['revision']))
        return self.hr.expense_action(self.owner, expense['id'], 'approve', dict(request_id=rid(), revision=expense['revision'], reason='Original und Reisezweck geprüft'))

    def approved_day(self):
        entry = rid()
        common = dict(entry_id=entry, device_id='synthetic-personnel-device', project_id=self.project)
        self.time.event(self.technician, dict(common, request_id=rid(), action='start', sequence=1, revision=0, occurred_at='2026-10-26T08:00:00+01:00'))
        self.time.event(self.technician, dict(common, request_id=rid(), action='stop', sequence=2, revision=1, occurred_at='2026-10-26T16:00:00+01:00'))
        summary = self.time.summary(self.owner, dict(employee_id=self.employee['id'], **{'from':'2026-10-26','to':'2026-10-26'}))
        self.time.approve_day(self.owner, '2026-10-26', dict(request_id=rid(), employee_id=self.employee['id'], revision=summary['days'][0]['revision']))

    def close_body(self, **changes):
        preview = self.hr.preview(self.owner, dict(employee_id=self.employee['id'], month='2026-10'))
        return {**dict(request_id=rid(), employee_id=self.employee['id'], month='2026-10', revision=0,
                    source_hash=preview['source_hash'], completeness_confirmed=True), **changes}

    def test_real_receipts_to_approved_expenses_to_frozen_month_with_exports(self):
        agreement = self.agreement()
        expense = self.approved_expense()
        expense = self.hr.expense_action(self.owner, expense['id'], 'reimburse', dict(request_id=rid(),
            revision=expense['revision'], confirmed=True, amount_minor=4987, paid_on='2026-10-25', payment_reference='Bankauszug 25/17'))
        self.approved_day()
        absence = self.planning.save_absence(self.technician, dict(request_id=rid(), employee_id=self.employee['id'],
            start_date='2026-10-27', end_date='2026-10-27', kind='sick', details='Private medical reason'))
        self.planning.approve_absence(self.owner, absence['id'], dict(request_id=rid(), revision=absence['revision'], status='approved'))
        body = self.close_body()
        closed = self.hr.close_preparation(self.owner, body)
        self.assertEqual(self.hr.close_preparation(self.owner, body), closed)
        self.assertEqual(closed['snapshot']['agreements'][0]['amount_minor'], 350000)
        self.assertEqual(closed['snapshot']['recorded_expenses_minor'], 4987)
        self.assertEqual(closed['snapshot']['expenses'][0]['payments'][0]['reference'], 'Bankauszug 25/17')
        self.assertEqual(closed['snapshot']['approved_days'][0]['status'], 'approved')
        self.assertNotIn('Private medical', json.dumps(closed))
        self.assertNotIn('hourly_cost_minor', json.dumps(closed))
        self.assertFalse(closed['payroll_calculated'])
        self.assertEqual(closed['transmission_status'], 'not_transmitted')
        pdf, mime = self.hr.export(self.owner, closed['id'], 'pdf')
        self.assertTrue(pdf.startswith(b'%PDF-'))
        self.assertEqual(_sha(pdf), closed['pdf_sha256'])
        self.assertEqual(mime, 'application/pdf')
        export, _ = self.hr.export(self.owner, closed['id'], 'json')
        self.assertEqual(json.loads(export), closed)
        export, _ = self.hr.export(self.owner, closed['id'], 'csv')
        self.assertIn(b'4987', export)
        self.assertIn(closed['source_hash'].encode(), export)
        self.assertTrue(validate_integrity(self.office))

    def test_private_originals_and_personnel_data_are_not_finance_or_project_permissions(self):
        file = self.upload()
        self.assertEqual(self.hr.files(self.technician, {})['items'], [])
        self.problem(403, lambda: self.hr.file_content(self.technician, file['id']))
        user_id = self.office.add_user('accounts@example.test','Synthetic-accounts-password-123','accountant')
        accountant = dict(id=user_id, role='owner')  # Stale/forged role is never authoritative.
        self.problem(403, lambda: self.hr.files(accountant, dict(employee_id=self.employee['id'])))
        self.problem(403, lambda: self.hr.list_records(accountant, 'agreement', dict(employee_id=self.employee['id'])))
        self.problem(403, lambda: self.hr.upload(self.technician, dict(request_id=rid(), employee_id=self.employee['id'], purpose='personnel', owner_visible=True,
            filename='private.pdf', media_type='application/pdf', content_base64=base64.b64encode(b'%PDF-1.4\n%%EOF').decode())))
        own = self.upload(purpose='expense_receipt', actor=self.technician, visible=True)
        self.assertEqual(self.hr.file_content(self.technician, own['id'])[0], b'%PDF-1.4\nSynthetic personnel evidence one\n%%EOF')

    def test_replay_returns_original_receipt_after_sources_change_but_checks_fresh_authority(self):
        agreement = self.agreement()
        body = self.close_body()
        closed = self.hr.close_preparation(self.owner, body)
        changed = self.hr.save_agreement(self.owner, dict(request_id=rid(), employee_id=self.employee['id'], id=agreement['id'],
            revision=agreement['revision'], effective_from=agreement['effective_from'], employment_kind='regular', pay_basis='monthly',
            amount_minor=360000, currency='EUR', reference_file_id=agreement['reference_file_id'], correction_reason='Schreibfehler korrigiert'))
        self.assertEqual(self.hr.close_preparation(self.owner, body), closed)
        self.assertEqual(self.hr.get(self.owner, 'preparation', closed['id'])['snapshot']['agreements'][0]['amount_minor'], 350000)
        revised_body = self.close_body(id=closed['id'], revision=closed['revision'], correction_reason='Geänderte Entgeltvereinbarung übernommen')
        revised = self.hr.close_preparation(self.owner, revised_body)
        self.assertEqual(revised['revision'], 2)
        self.assertEqual(revised['snapshot']['agreements'][0]['amount_minor'], 360000)
        self.assertEqual(len(self.hr.get(self.owner, 'preparation', closed['id'], True)['items']), 2)
        historical, _ = self.hr.export(self.owner, closed['id'], 'json', '1')
        self.assertEqual(json.loads(historical), closed)
        self.problem(409, lambda: self.hr.close_preparation(self.owner, {**body, 'source_hash':'a'*64}))
        self.office.db.execute('UPDATE users SET active=0 WHERE id=?', (self.owner_id,))
        self.problem(401, lambda: self.hr.close_preparation(self.owner, body))

    def test_expense_corrections_keep_reviews_and_confirmed_repayment_history(self):
        expense = self.approved_expense()
        payment = dict(request_id=rid(), revision=expense['revision'], amount_minor=4987, confirmed=True,
                       paid_on='2026-10-25', payment_reference='Payment-001')
        reimbursed = self.hr.expense_action(self.owner, expense['id'], 'reimburse', payment)
        self.assertEqual(self.hr.expense_action(self.owner, expense['id'], 'reimburse', payment), reimbursed)
        changes = self.expense_body(id=expense['id'], revision=reimbursed['revision'], correction_reason='Korrektur')
        self.problem(409, lambda: self.hr.save_expense(self.technician, changes))
        self.problem(400, lambda: self.hr.expense_action(self.owner, expense['id'], 'reverse-reimbursement', dict(
            request_id=rid(), revision=reimbursed['revision'], amount_minor=1, confirmed=True, paid_on='2026-10-26', payment_reference='Refund-001')))
        reversed_ = self.hr.expense_action(self.owner, expense['id'], 'reverse-reimbursement', dict(request_id=rid(),
            revision=reimbursed['revision'], amount_minor=4987, confirmed=True, paid_on='2026-10-26', payment_reference='Refund-001'))
        corrected = self.hr.save_expense(self.technician, {**changes, 'revision':reversed_['revision']})
        self.assertEqual(corrected['status'], 'draft')
        self.assertEqual([item['kind'] for item in corrected['payments']], ['reimbursement','repayment'])
        history = self.hr.get(self.owner, 'expense', expense['id'], True)['items']
        self.assertEqual(history[2]['status'], 'approved')
        self.assertEqual(len(history), 6)
        self.assertTrue(validate_integrity(self.office))

    def test_no_inferred_wages_unapproved_sources_or_mismatched_preview(self):
        self.problem(409, lambda: self.hr.preview(self.owner, dict(employee_id=self.employee['id'], month='2026-10')))
        self.agreement()
        stale = self.close_body()
        draft = self.hr.save_expense(self.technician, self.expense_body())
        self.problem(409, lambda: self.hr.close_preparation(self.owner, stale))
        submitted = self.hr.expense_action(self.technician, draft['id'], 'submit', dict(request_id=rid(), revision=1))
        self.hr.expense_action(self.owner, draft['id'], 'reject', dict(request_id=rid(), revision=2, reason='Belegangaben fehlen'))
        self.problem(409, lambda: self.hr.close_preparation(self.owner, {**stale, 'source_hash':'b'*64}))
        self.assertFalse(self.hr.preview(self.owner, dict(employee_id=self.employee['id'], month='2026-10'))['snapshot']['payroll_calculated'])

    def test_self_approval_duplicate_receipt_and_wrong_employee_are_rejected(self):
        body = self.expense_body()
        expense = self.hr.save_expense(self.technician, body)
        self.hr.expense_action(self.technician, expense['id'], 'submit', dict(request_id=rid(), revision=1))
        self.problem(403, lambda: self.hr.expense_action(self.technician, expense['id'], 'approve', dict(request_id=rid(), revision=2, reason='Selbst geprüft')))
        second = self.hr.save_expense(self.technician, {**body, 'request_id':rid()})
        self.problem(409, lambda: self.hr.expense_action(self.technician, second['id'], 'submit', dict(request_id=rid(), revision=1)))
        private = self.upload()
        invalid = self.expense_body()
        invalid['items'][0]['receipt_file_id'] = private['id']
        self.problem(400, lambda: self.hr.save_expense(self.technician, invalid))

    def test_archive_guards_and_failed_receipt_rollback_protect_originals(self):
        file = self.upload()
        with self.assertRaises(sqlite3.IntegrityError):
            self.office.db.execute('UPDATE business_personnel_files SET filename=? WHERE id=?', ('changed.pdf',file['id']))
        with self.assertRaises(sqlite3.IntegrityError):
            self.office.db.execute('DELETE FROM business_personnel_files WHERE id=?', (file['id'],))
        count = self.office.db.execute('SELECT COUNT(*) FROM business_personnel_files').fetchone()[0]
        self.office.db.execute("CREATE TRIGGER synthetic_personnel_failure BEFORE INSERT ON business_personnel_requests BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.upload()
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_personnel_files').fetchone()[0], count)

    def test_sqlite_replace_cannot_remove_a_period_root_through_its_unique_identity(self):
        agreement = self.agreement()
        archived = dict(self.office.db.execute('SELECT * FROM business_personnel_events WHERE id=?', (agreement['id'],)).fetchone())
        replaced = {**archived, 'id':rid()}
        columns = tuple(replaced)
        with self.assertRaises(sqlite3.IntegrityError):
            self.office.db.execute('INSERT OR REPLACE INTO business_personnel_events(' + ','.join(columns) + ') VALUES(' + ','.join('?' for _ in columns) + ')', tuple(replaced.values()))
        self.assertEqual(self.hr.get(self.owner, 'agreement', agreement['id']), agreement)
        self.assertTrue(validate_integrity(self.office))

    def test_restore_rejects_a_rehashed_snapshot_containing_another_employees_valid_source(self):
        self.agreement()
        closed = self.hr.close_preparation(self.owner, self.close_body())
        original_employee = self.employee
        self.employee = self.planning.save_employee(self.owner, dict(request_id=rid(), user_id=self.owner_id, name='Other employee'))
        foreign = self.agreement()
        self.employee = original_employee
        row = dict(self.office.db.execute('SELECT * FROM business_personnel_events WHERE id=?', (closed['id'],)).fetchone())
        payload = json.loads(row['payload_json'])
        payload['snapshot']['agreements'] = [foreign]
        payload['source_hash'] = _sha(payload['snapshot'])
        envelope = {key:row[key] for key in ('id','kind','employee_id','revision','previous_hash','created_by','created_at','pdf_sha256','identity_key')}
        envelope['payload'] = payload
        self.office.db.execute('DROP TRIGGER business_personnel_events_update_guard')
        self.office.db.execute('UPDATE business_personnel_events SET payload_json=?,content_hash=? WHERE id=?',
                               (json.dumps(payload),_sha(envelope),closed['id']))
        with self.assertRaisesRegex(ValueError, 'Missing monthly source'):
            validate_integrity(self.office)

    def test_changed_archive_pdf_and_duplicate_uploaded_original_fail_closed(self):
        self.agreement()
        first = self.hr.save_expense(self.technician, self.expense_body())
        self.hr.expense_action(self.technician, first['id'], 'submit', dict(request_id=rid(),revision=1))
        # A new upload ID does not create a new expense original.
        duplicate = self.hr.save_expense(self.technician, self.expense_body())
        self.problem(409, lambda: self.hr.expense_action(self.technician, duplicate['id'], 'submit', dict(request_id=rid(),revision=1)))
        self.problem(400, lambda: self.hr.expense_action(self.technician, duplicate['id'], 'submit', dict(request_id=rid(),revision=1,payment_reference='ignored')))
        self.hr.expense_action(self.owner, first['id'], 'reject', dict(request_id=rid(),revision=2,reason='Beleg klären'))
        # Reject the other draft via its normal submission/review path.
        self.hr.expense_action(self.technician, duplicate['id'], 'submit', dict(request_id=rid(),revision=1))
        self.hr.expense_action(self.owner, duplicate['id'], 'reject', dict(request_id=rid(),revision=2,reason='Doppelt erfasst'))
        closed = self.hr.close_preparation(self.owner, self.close_body())
        self.office.db.execute('DROP TRIGGER business_personnel_events_update_guard')
        self.office.db.execute('UPDATE business_personnel_events SET pdf=? WHERE id=?', (b'%PDF-changed',closed['id']))
        self.problem(500, lambda: self.hr.export(self.owner, closed['id'], 'pdf'))
        with self.assertRaisesRegex(ValueError, 'Changed preparation PDF'):
            validate_integrity(self.office)

    def test_running_or_unapproved_recorded_time_blocks_closing(self):
        self.agreement()
        entry = rid()
        common = dict(entry_id=entry,device_id='synthetic-hr',project_id=self.project)
        self.time.event(self.technician, dict(common,request_id=rid(),action='start',sequence=1,revision=0,occurred_at='2026-10-26T08:00:00+01:00'))
        self.problem(409, lambda: self.close_body())
        self.time.event(self.technician, dict(common,request_id=rid(),action='stop',sequence=2,revision=1,occurred_at='2026-10-26T16:00:00+01:00'))
        self.problem(409, lambda: self.close_body())

    def test_explicit_conflict_proof_and_disabled_module_preserve_archived_reads(self):
        from business_organization import Organization, _stored
        self.agreement()
        body = self.close_body()
        closed = self.hr.close_preparation(self.owner, body)
        with self.assertRaises(Problem) as prior_identity:
            self.hr.close_preparation(self.owner, {**body, 'source_hash':'f'*64})
        self.assertIsNone(prior_identity.exception.request_resolution)
        with self.assertRaises(Problem) as fresh_identity:
            self.hr.close_preparation(self.owner, {**body, 'request_id':rid(), 'source_hash':'f'*64})
        self.assertEqual(fresh_identity.exception.request_resolution, 'not_accepted')
        settings = _stored(self.office)
        settings['modules']['personnel']['enabled'] = False
        Organization(self.office).save(self.owner, dict(request_id=rid(), revision=settings['revision'],
            needs=settings['needs'], modules=settings['modules']))
        self.problem(423, lambda: self.hr.close_preparation(self.owner, body))
        self.assertEqual(self.hr.get(self.owner, 'preparation', closed['id']), closed)
        self.assertTrue(self.hr.export(self.owner, closed['id'], 'pdf')[0].startswith(b'%PDF-'))

    def test_ticket_purchased_before_travel_remains_an_actual_receipted_expense(self):
        body = self.expense_body()
        body['items'][0]['date'] = '2026-10-01'
        saved = self.hr.save_expense(self.technician, body)
        self.assertEqual(saved['items'][0]['date'], '2026-10-01')
        self.assertEqual(saved['total_minor'], 4987)
        self.assertTrue(validate_integrity(self.office))

    def test_dispatch_rejects_ignored_channels_and_export_requires_narrow_permission(self):
        self.agreement()
        result = self.hr.close_preparation(self.owner, self.close_body())
        self.problem(403, lambda: self.hr.export(self.technician, result['id'], 'pdf'))
        self.problem(400, lambda: dispatch(self.office, self.owner, '/personnel/agreements','GET', {'unexpected':True}))
        self.problem(400, lambda: dispatch(self.office, self.owner, '/personnel/agreements','GET', {'_query':{'unknown':'yes'}}))
        pdf, status, mime = dispatch(self.office, self.owner, '/personnel/payroll-preparations/'+result['id']+'/pdf','GET',{})
        self.assertEqual(status, 200)
        self.assertEqual(mime, 'application/pdf')
        self.assertTrue(pdf.filename.endswith('.pdf'))


if __name__ == '__main__':
    unittest.main()
