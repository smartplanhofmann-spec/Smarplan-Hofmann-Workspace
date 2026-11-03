"""Additional real MFA/HTTP boundaries and explicit local restore-operator path.

Uses the shared synthetic journey fixture, not its test cases. No invoice-policy
override, bank connection, provider or tax-result claim is involved.
"""
from datetime import datetime, timezone
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest
from unittest.mock import patch
import uuid

from backup import backup
import business_schema
from business_accounting import restore_horizon
from core import Office, Problem
from restore import restore
from online import test_accounting_journey as journey


class AccountingHTTPTests(unittest.TestCase):
    setUp = journey.AccountingJourneyTests.setUp
    new_company = journey.AccountingJourneyTests.new_company
    open_app = journey.AccountingJourneyTests.open_app
    call = journey.AccountingJourneyTests.call
    login = journey.AccountingJourneyTests.login
    user = journey.AccountingJourneyTests.user
    permission = journey.AccountingJourneyTests.permission
    payment = journey.AccountingJourneyTests.payment
    incoming = journey.AccountingJourneyTests.incoming
    account_record = journey.AccountingJourneyTests.account_record
    source = journey.AccountingJourneyTests.source
    payout_body = journey.AccountingJourneyTests.payout_body
    import_body = journey.AccountingJourneyTests.import_body
    legacy_sources = journey.AccountingJourneyTests.legacy_sources

    def report(self, office):
        horizon = business_schema.financial_accounting_horizon(office)
        return dict(schema=horizon['schema_version'] + 1, restore_id=business_schema.state(office)['restore_id'],
            reviewed_by='Synthetic independent reviewer', reviewed_at=datetime.now(timezone.utc).isoformat(),
            number_horizons=[dict(company_id=row['company_id'], series=row['series'], year=row['year'],
                last_value=row['next_value'] - 1) for row in office.db.execute('SELECT * FROM business_document_counters')],
            outbound_reconciled=True, accounting_horizon=horizon, accounting_reconciled=True,
            accounting_external_review=dict(reviewed_since_backup=True,
                evidence_sha256=hashlib.sha256(b'Synthetic independently reviewed bank/source records').hexdigest(),
                note='Synthetic independent source/payment review since backup; no live records.'))

    def require_reconciliation(self, office):
        with office.db:
            office.db.execute('UPDATE business_restore_state SET financial_reconciliation_required=1,restore_id=?',
                              (uuid.uuid4().hex,))

    @staticmethod
    def report_hash(report):
        return hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()

    def test_scope_methods_unknown_fields_and_customer_offline_tokens_never_open_accounting(self):
        company = self.company
        user, token = self.user(company)
        for permission in ('accounting.read', 'accounting.prepare', 'accounting.admin'):
            self.call(company, '/business/settings/permissions', journey.request(user_id=user,
                permission=permission, scope=company['project'], effect='allow', revision=0), status=400)
        self.call(company, '/business/accounting/status', token=token, status=403)
        self.permission(company, user, 'accounting.read')
        self.call(company, '/business/accounting/status', token=token)
        self.call(company, '/business/accounting/accounts', journey.request(
            code='NO_GLOBAL_ADMIN', name='Not allowed', kind='bank', confirmation=True), token=token, status=403)
        self.permission(company, user, 'finance.read', effect='deny')
        self.call(company, '/business/accounting/status', token=token, status=403)
        offline = self.call(company, '/offline/access', {}, status=201).json['token']
        for credential in (None, offline, 'SPPT_' + 's' * 43, 'SPPI_' + 'i' * 43):
            self.call(company, '/business/accounting/status', token=credential, status=(401, 403))
        for suffix in ('/status?project_id=' + company['project'], '/accounts?company_id=other',
                       '/events?limit=1&limit=2', '/events?offset=-1', '/events?limit=101',
                       '/sources/payments?limit=0', '/sources/receipts?offset=100001'):
            self.call(company, '/business/accounting' + suffix, status=400)
        self.call(company, '/business/accounting/status', {}, status=405)
        self.call(company, '/business/accounting/accounts', method='DELETE', status=405)
        self.call(company, '/business/accounting/accounts', journey.request(
            code='BAD', name='No account injection', kind='bank', confirmation=True, company_id='other'), status=400)
        self.call(company, '/business/accounting/events/' + 'f' * 32 + '?source_id=other', status=400)
        self.call(company, '/business/accounting/reconcile', {}, status=404)
        response = self.call(company, '/business/accounting/events')
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(response.headers['Referrer-Policy'], 'no-referrer')
        self.assertNotIn('Set-Cookie', response.headers)

    def test_malformed_money_and_source_fields_never_round_or_create_cash_events(self):
        company = self.company
        receipt, _ = self.incoming(company)
        source = self.source(company, 'receipts', receipt['id'])
        before = self.legacy_sources(company)
        for amount in ('59.5', '59.500', '59,50', '1e2', 'NaN', '-1.00', '0.00', '1000000000.00', 59.50, True):
            with self.subTest(amount=amount):
                self.call(company, '/business/accounting/events/payout', self.payout_body(source, amount=amount), status=400)
        for changes in ({'confirmation': 1}, {'account_revision': True}, {'review_revision': True},
                        {'expected_cash_revision': False}, {'cash_date': '2026-02-30'}, {'cash_date': '2026-1-01'},
                        {'source_hash': 'x' * 64}, {'original_sha256': '0' * 63}, {'tax_category': 'invented'}):
            self.call(company, '/business/accounting/events/payout', {**self.payout_body(source), **changes}, status=(400, 409))
        self.assertEqual(self.call(company, '/business/accounting/events').json['total'], 0)
        self.assertEqual(self.legacy_sources(company), before)

    def test_current_report_requires_exact_cash_horizon_and_independent_external_review_atomically(self):
        office = self.company['office']
        self.require_reconciliation(office)
        report = self.report(office)
        before = '\n'.join(office.db.iterdump())
        def changed_cash_horizon(**changes):
            horizon = report['accounting_horizon']
            return ({**horizon, 'prejournal': {**horizon['prejournal'], **changes}}
                    if horizon['schema_version'] >= 2 else {**horizon, **changes})
        invalid = [{key: value for key, value in report.items() if not key.startswith('accounting_')},
            {**report, 'accounting_reconciled': False},
            {**report, 'accounting_external_review': {**report['accounting_external_review'], 'reviewed_since_backup': False}},
            {**report, 'accounting_external_review': {**report['accounting_external_review'], 'note': ''}},
            {**report, 'accounting_horizon': changed_cash_horizon(cash_events_count=1)},
            {**report, 'accounting_horizon': changed_cash_horizon(sha256='0' * 64)},
            {**report, 'accounting_horizon': {**report['accounting_horizon'], 'schema_version': True}},
            {**report, 'restore_id': uuid.uuid4().hex}, {**report, 'reviewed_at': '2026-11-02T12:00:00'}]
        invalid[0]['schema'] = 1
        for candidate in invalid:
            with self.assertRaises((Problem, ValueError)):
                business_schema.reconcile_local_financial_restore(office, candidate, self.report_hash(candidate), application_stopped=True)
            self.assertEqual('\n'.join(office.db.iterdump()), before)
        with self.assertRaises(Problem):
            business_schema.reconcile_financial_restore(office, report, self.report_hash(report))
        with self.assertRaises(Problem):
            business_schema.reconcile_local_financial_restore(office, report, self.report_hash(report))
        self.assertEqual('\n'.join(office.db.iterdump()), before)

    def test_local_operator_refuses_enclosing_transaction_and_competing_writer(self):
        office = self.company['office']
        self.require_reconciliation(office)
        report = self.report(office)
        office.db.execute('BEGIN')
        try:
            with self.assertRaises(Problem):
                business_schema.reconcile_local_financial_restore(office, report, self.report_hash(report), application_stopped=True)
            self.assertTrue(office.db.in_transaction)
        finally:
            office.db.rollback()
        other = sqlite3.connect(self.directory / 'alpha.sqlite3', timeout=0.01)
        try:
            other.execute('BEGIN IMMEDIATE')
            office.db.execute('PRAGMA busy_timeout=10')
            with self.assertRaises(sqlite3.OperationalError):
                business_schema.reconcile_local_financial_restore(office, report, self.report_hash(report), application_stopped=True)
        finally:
            other.rollback()
            other.close()
        self.assertTrue(business_schema.state(office)['financial_reconciliation_required'])
        self.assertEqual(office.db.execute('SELECT COUNT(*) FROM business_financial_reconciliations').fetchone()[0], 0)

    def test_actual_restore_cli_reviews_bytes_then_unblocks_without_mutating_sources_or_reimporting(self):
        company = self.company
        payment = self.payment(company)
        source = self.source(company, 'payments', payment['id'])
        command = self.import_body(source)
        event = self.call(company, '/business/accounting/events/import-payment', command, status=201).json
        original_sources = self.legacy_sources(company)
        original_horizon = restore_horizon(company['office'])
        saved = backup(self.directory / 'alpha.sqlite3', self.directory / 'saved.sqlite3')
        target = restore(saved, self.directory / 'restored.sqlite3')
        restored = Office(target)
        self.addCleanup(restored.db.close)
        self.assertEqual(restore_horizon(restored), original_horizon)
        self.assertEqual(self.legacy_sources({'office': restored}), original_sources)
        restored_company = {**company, 'office': restored}
        self.open_app(restored_company)
        self.call(restored_company, '/business/accounting/status', status=401)
        restored_company['token'] = self.login(restored_company, 'owner@example.test',
            'Synthetic-accounting-owner-password-123', advance=True)
        self.assertFalse(self.call(restored_company, '/business/accounting/status').json['writes_allowed'])
        self.call(restored_company, '/business/accounting/events/import-payment', command, status=409)
        self.assertEqual(self.call(restored_company, '/business/accounting/events/' + event['id']).json, event)
        report = self.report(restored)
        report_path = self.directory / 'independent-review.json'
        raw = (json.dumps(report, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
        report_path.write_bytes(raw)
        report_path.chmod(0o600)
        company['office'].db.close()
        restored.db.close()
        script = Path(__file__).resolve().parents[2] / 'scripts' / 'reconcile-accounting-restore.py'
        args = [sys.executable, str(script), '--database', str(target), '--evidence', str(report_path)]
        rejected = subprocess.run(args, capture_output=True, text=True, timeout=15)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn('application-stopped', rejected.stderr)
        first = subprocess.run(args + ['--application-stopped'], capture_output=True, text=True, timeout=15)
        self.assertEqual(first.returncode, 0, first.stderr)
        receipt = json.loads(first.stdout)
        self.assertEqual(receipt['evidence_sha256'], hashlib.sha256(raw).hexdigest())
        second = subprocess.run(args + ['--application-stopped'], capture_output=True, text=True, timeout=15)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads(second.stdout), receipt)
        reopened = Office(target)
        self.addCleanup(reopened.db.close)
        restored_company['office'] = reopened
        self.open_app(restored_company)
        self.assertTrue(self.call(restored_company, '/business/accounting/status').json['writes_allowed'])
        self.assertEqual(self.call(restored_company, '/business/accounting/events/import-payment', command, status=201).json, event)
        self.call(restored_company, '/business/accounting/events/import-payment',
            {**command, 'request_id': uuid.uuid4().hex}, status=409)
        self.assertEqual(self.legacy_sources(restored_company), original_sources)
        self.assertEqual(restore_horizon(reopened), original_horizon)
        stored = reopened.db.execute('SELECT * FROM business_financial_reconciliations').fetchall()
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]['evidence_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertTrue(stored[0]['operator_name'].startswith('sqlite-local-'))

    def test_schema1_compatibility_and_legacy_restore_without_adding_accounting_tables(self):
        previous = tuple(spec for spec in business_schema.registry()
                         if spec.name not in ('business_accounting', 'business_accounting_allocations', 'business_accounting_components',
                                              'business_accounting_refunds', 'business_accounting_capacity'))
        with patch.object(business_schema, 'registry', return_value=previous):
            office = Office(self.directory / 'pre-accounting.sqlite3')
            self.addCleanup(office.db.close)
            self.require_reconciliation(office)
            evidence = dict(schema=1, restore_id=business_schema.state(office)['restore_id'],
                reviewed_by='Synthetic legacy reviewer', reviewed_at=datetime.now(timezone.utc).isoformat(),
                number_horizons=[], outbound_reconciled=True)
            before = office.db.execute('SELECT type,name,sql FROM sqlite_master ORDER BY type,name').fetchall()
            result = business_schema.reconcile_local_financial_restore(office, evidence,
                self.report_hash(evidence), application_stopped=True)
            self.assertTrue(result['reconciled'])
            self.assertEqual([tuple(row) for row in office.db.execute('SELECT type,name,sql FROM sqlite_master ORDER BY type,name')],
                             [tuple(row) for row in before])
            self.assertIsNone(restore_horizon(office))
        with patch('business_schema.ensure_sqlite_schema'):
            legacy = Office(self.directory / 'pure-legacy.sqlite3')
        self.addCleanup(legacy.db.close)
        legacy.db.close()
        path = restore(self.directory / 'pure-legacy.sqlite3', self.directory / 'pure-legacy-restored.sqlite3')
        with closing(sqlite3.connect(path)) as restored:
            self.assertIsNone(restored.execute("SELECT name FROM sqlite_master WHERE name='business_restore_state'").fetchone())
            self.assertIsNone(restored.execute("SELECT name FROM sqlite_master WHERE name='business_accounting_accounts'").fetchone())

    def test_cli_rejects_ambiguous_or_public_reports_symlinks_and_missing_databases_without_writes(self):
        office = self.company['office']
        self.require_reconciliation(office)
        report = self.report(office)
        before = '\n'.join(office.db.iterdump())
        office.db.close()
        database = self.directory / 'alpha.sqlite3'
        report_path = self.directory / 'operator-review.json'
        script = Path(__file__).resolve().parents[2] / 'scripts' / 'reconcile-accounting-restore.py'

        def rejected(db=database, evidence=report_path):
            reply = subprocess.run([sys.executable, str(script), '--database', str(db), '--evidence', str(evidence),
                '--application-stopped'], capture_output=True, text=True, timeout=15)
            self.assertNotEqual(reply.returncode, 0)
            with closing(sqlite3.connect(database)) as check:
                self.assertEqual('\n'.join(check.iterdump()), before)

        for raw in (b'{"schema":2,"schema":2}', b'{"schema":NaN}', b'\xff', b'', b' ' * (4 * 1024 * 1024 + 1)):
            report_path.write_bytes(raw)
            report_path.chmod(0o600)
            rejected()
        report_path.write_text(json.dumps(report), encoding='utf-8')
        report_path.chmod(0o600)
        missing = self.directory / 'never-created.sqlite3'
        rejected(db=missing)
        self.assertFalse(missing.exists())
        linked_report = self.directory / 'linked-report.json'
        linked_database = self.directory / 'linked-database.sqlite3'
        linked_report.symlink_to(report_path)
        linked_database.symlink_to(database)
        rejected(evidence=linked_report)
        rejected(db=linked_database)
        if os.name == 'posix':
            report_path.chmod(0o644)
            rejected()

    def test_cli_inspection_is_read_only_even_while_restore_is_pending_and_is_not_an_approval_report(self):
        office = self.company['office']
        self.require_reconciliation(office)
        expected_horizon = business_schema.financial_accounting_horizon(office)
        with office.db:
            office.db.execute('UPDATE business_restore_state SET pending=1')
        expected_restore = office.db.execute('SELECT restore_id FROM business_restore_state').fetchone()[0]
        before_rows = '\n'.join(office.db.iterdump())
        office.db.close()
        database = self.directory / 'alpha.sqlite3'
        before_bytes = hashlib.sha256(database.read_bytes()).hexdigest()
        script = Path(__file__).resolve().parents[2] / 'scripts' / 'reconcile-accounting-restore.py'
        args = [sys.executable, str(script), '--database', str(database), '--inspect']
        response = subprocess.run(args, capture_output=True, text=True, timeout=15)
        self.assertEqual(response.returncode, 0, response.stderr)
        snapshot = json.loads(response.stdout)
        self.assertTrue(snapshot['inspection_only'])
        self.assertTrue(snapshot['external_review_required'])
        self.assertEqual(snapshot['evidence_schema'], expected_horizon['schema_version'] + 1)
        self.assertEqual(snapshot['restore_id'], expected_restore)
        self.assertTrue(snapshot['restore_pending'])
        self.assertTrue(snapshot['financial_reconciliation_required'])
        self.assertEqual(snapshot['accounting_horizon'], expected_horizon)
        for field in ('schema', 'reviewed_by', 'reviewed_at', 'outbound_reconciled',
                      'accounting_reconciled', 'accounting_external_review'):
            self.assertNotIn(field, snapshot)
        self.assertNotEqual(subprocess.run(args + ['--application-stopped'], capture_output=True, timeout=15).returncode, 0)
        self.assertNotEqual(subprocess.run(args + ['--evidence', 'unused.json'], capture_output=True, timeout=15).returncode, 0)
        missing = self.directory / 'inspection-must-not-create.sqlite3'
        self.assertNotEqual(subprocess.run([sys.executable, str(script), '--database', str(missing), '--inspect'],
            capture_output=True, timeout=15).returncode, 0)
        self.assertFalse(missing.exists())
        self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), before_bytes)
        with closing(sqlite3.connect(database)) as check:
            self.assertEqual('\n'.join(check.iterdump()), before_rows)


if __name__ == '__main__':
    unittest.main()
