"""Actual MFA, independent runtime connections and complete archive restore."""
import base64
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

import psycopg
from psycopg.conninfo import make_conninfo

import business_schema
from business_personnel_workflow import PersonnelWorkflow, protected_tables
from core import Problem
from online import release, test_customer_execution_journey_pg as journey
from online.backup import backup
from online.restore import complete_restore, restore
from online.store import PostgresOffice

fixture, request = journey.fixture, journey.request


@unittest.skipUnless(fixture.DSN, 'Guarded disposable PostgreSQL fixture required')
class ExpenseOriginalPostgres(unittest.TestCase):
    setUp = journey.CustomerExecutionJourneyPostgres.setUp
    reopen = journey.CustomerExecutionJourneyPostgres.reopen
    login = journey.CustomerExecutionJourneyPostgres.login
    call = journey.CustomerExecutionJourneyPostgres.call

    def test_cross_employee_race_withdrawal_payment_receipts_and_originals_survive_complete_restore(self):
        drafts, tokens, actors = [], [], []
        original = b'%PDF-1.4\nSynthetic same entire ticket for two employees\n%%EOF'
        for index in range(2):
            email = f'expense-{index}@example.test'
            uid = self.call('POST', '/users', dict(email=email, password='Synthetic-expense-password-123', role='technician'), status=201).json['id']
            token = self.login(email, 'Synthetic-expense-password-123')
            employee = self.call('POST', '/business/employees', request(user_id=uid, name=f'Synthetic employee {index}',
                weekly_minutes=2400, hourly_cost_minor=3500), status=201).json
            file = self.call('POST', '/business/personnel/files', request(employee_id=employee['id'], purpose='expense_receipt',
                owner_visible=True, filename=f'ticket-{index}.pdf', media_type='application/pdf',
                content_base64=base64.b64encode(original).decode()), token=token).json
            draft = self.call('POST', '/business/personnel/expenses', request(employee_id=employee['id'], revision=0,
                purpose='Synthetic actual ticket', start_date=self.today, end_date=self.today,
                items=[dict(date=self.today, description='Entire ticket', amount_minor=4987, currency='EUR', receipt_file_id=file['id'])]), token=token).json
            drafts.append(draft); tokens.append(token); actors.append(dict(id=uid, role='technician'))
        barrier = threading.Barrier(2)
        commands = [request(revision=item['revision']) for item in drafts]
        def submit(index):
            runtime = PostgresOffice(self.runtime)
            try:
                barrier.wait(timeout=10)
                try:
                    return PersonnelWorkflow(runtime).expense_action(actors[index], drafts[index]['id'], 'submit', commands[index])
                except Problem as error:
                    self.assertEqual((error.status, error.request_resolution), (409, 'not_accepted'))
                    return None
            finally:
                runtime.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            accepted = list(pool.map(submit, range(2)))
        self.assertEqual(sum(item is not None for item in accepted), 1)
        winner = next(index for index, item in enumerate(accepted) if item)
        loser = 1-winner
        def path(index, action): return '/business/personnel/expenses/'+drafts[index]['id']+'/'+action
        first = self.call('POST', path(winner, 'submit'), commands[winner], token=tokens[winner]).json
        self.assertEqual(first, accepted[winner])
        denied = self.call('POST', path(loser, 'submit'), commands[loser], token=tokens[loser], status=409).json
        for private in (drafts[winner]['id'], drafts[winner]['employee_id'], drafts[winner]['items'][0]['receipt_file_id']):
            self.assertNotIn(private, str(denied))
        first = self.call('POST', path(winner, 'approve'), request(revision=first['revision'], reason='Independent check')).json
        withdraw = request(revision=first['revision'], reason='Duplicate whole ticket: independent approval withdrawn before payment')
        withdrawn = self.call('POST', path(winner, 'withdraw-approval'), withdraw).json
        self.assertEqual(withdrawn['status'], 'rejected')
        self.assertEqual(withdrawn['payments'], [])
        second = self.call('POST', path(loser, 'submit'), commands[loser], token=tokens[loser]).json
        second = self.call('POST', path(loser, 'approve'), request(revision=second['revision'], reason='Remaining whole ticket checked')).json
        payment = request(revision=second['revision'], amount_minor=4987, confirmed=True, paid_on=self.today,
            payment_reference='SYNTHETIC-ACTUAL-TRANSFER-ONE')
        paid = self.call('POST', path(loser, 'reimburse'), payment).json
        self.assertEqual(self.call('POST', path(winner, 'withdraw-approval'), withdraw).json, withdrawn)
        self.assertEqual(len(paid['payments']), 1)
        self.call('GET', '/business/personnel/expenses/'+drafts[winner]['id'], token=tokens[loser], status=403)
        for index in range(2):
            self.assertEqual(self.call('GET', '/business/personnel/files/'+drafts[index]['items'][0]['receipt_file_id']+'/content', token=tokens[index]).data, original)
        self.reopen()
        self.assertEqual(self.call('POST', path(winner, 'withdraw-approval'), withdraw).json, withdrawn)
        self.assertEqual(self.call('POST', path(loser, 'reimburse'), payment).json, paid)
        business_schema.validate_integrity(self.office)
        before = release.snapshot_fingerprint(fixture.DSN)
        actor = self.office.user(self.token)
        self.office.db.close()
        target = make_conninfo(fixture.DSN, dbname='smartplan_release_check')
        release.validate_dsns(fixture.DSN, target, test_mode=True)
        with psycopg.connect(fixture.DSN, autocommit=True) as admin:
            self.assertIsNone(admin.execute("SELECT 1 FROM pg_database WHERE datname='smartplan_release_check'").fetchone())
            admin.execute('CREATE DATABASE smartplan_release_check OWNER "smartplan-migrator" TEMPLATE template0')
        try:
            with tempfile.TemporaryDirectory(prefix='expense-original-restore-') as directory:
                saved = backup(fixture.DSN, directory)
                self.assertTrue(restore(saved, fixture.DSN, target, privileged_operator=True, test_mode=True)['restore_pending'])
            runtime = make_conninfo(self.runtime, dbname='smartplan_release_check')
            verifier = PostgresOffice(runtime, allow_restore_pending=True)
            try: self.assertFalse(complete_restore(verifier)['restore_pending'])
            finally: verifier.db.close()
            restored = PostgresOffice(runtime)
            try:
                hr = PersonnelWorkflow(restored)
                self.assertEqual(hr.expense_action(actor, drafts[winner]['id'], 'withdraw-approval', withdraw), withdrawn)
                self.assertEqual(hr.expense_action(actor, drafts[loser]['id'], 'reimburse', payment), paid)
                for item in drafts:
                    self.assertEqual(hr.file_content(actor, item['items'][0]['receipt_file_id'])[0], original)
                business_schema.validate_integrity(restored)
                after = release.snapshot_fingerprint(target)
                for table in protected_tables(): self.assertEqual(after[table], before[table], table)
                self.assertEqual(release.snapshot_fingerprint(fixture.DSN), before)
            finally: restored.db.close()
        finally:
            with psycopg.connect(fixture.DSN, autocommit=True) as admin:
                admin.execute('DROP DATABASE smartplan_release_check')


if __name__ == '__main__':
    unittest.main()
