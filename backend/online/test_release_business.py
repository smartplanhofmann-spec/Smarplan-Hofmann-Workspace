"""Real schema-7 candidate/down/archive and least-privilege PostgreSQL acceptance.

Only the guarded loopback smartplan_check/smartplan_release_check fixture is used.
No production endpoints, provider accounts or customer documents are contacted.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from cryptography.fernet import Fernet

import business_schema
from business_documents import Documents, render_prepared
from business_finance import Finance
from business_tests.test_documents import DocumentsFixture
from core import Problem
from online import release
from online import test_release as base
from online.restore import restore, complete_restore
from online.store import PostgresOffice, Row, migrate


class BusinessOperatorGuards(unittest.TestCase):
    def test_ready_reports_actual_legacy_storage_instead_of_build_schema_constant(self):
        class Database:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def execute(self, query, parameters=()):
                return SimpleNamespace(fetchone=lambda: (1,), fetchall=lambda: [])
        office = SimpleNamespace(db=Database(), lock=threading.RLock())
        from online.web import create_app
        app = create_app(office=office, key=Fernet.generate_key(), host='office.example.test',
                         storage=SimpleNamespace(onedrive=None), integrations=SimpleNamespace())
        reply = app.test_client().get('/ready', base_url='https://office.example.test')
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json['schema_version'], 6)
        self.assertNotIn('business_suite', reply.json['capabilities'])

    def test_new_production_prepare_cannot_use_old_runtime_writer_path(self):
        source = 'host=/var/run/postgresql dbname=smartplan_online user=smartplan-online'
        with patch('online.release.psycopg.connect') as connect:
            with self.assertRaisesRegex(ValueError, 'Operatorpfad'):
                release.prepare(source, make_conninfo(source, dbname='smartplan_candidate'), '/not-created')
        connect.assert_not_called()

    def test_explicit_operator_flag_does_not_bypass_euid_or_local_peer_guard(self):
        source = 'host=/var/run/postgresql dbname=smartplan_online user=smartplan-online'
        target = make_conninfo(source, dbname='smartplan_candidate')
        with patch('online.release.os.geteuid', return_value=2001), \
                patch('online.release.pwd.getpwnam', return_value=SimpleNamespace(pw_uid=2002)), \
                patch('online.release.psycopg.connect') as connect:
            with self.assertRaises(ValueError):
                release.operator_dsns(source, target)
            with self.assertRaises(ValueError):
                release.operator_dsns(make_conninfo(source, host='127.0.0.1'), make_conninfo(target, host='127.0.0.1'))
        connect.assert_not_called()

    def test_compatibility_start_on_schema6_reads_only_and_never_runs_ddl(self):
        queries = []
        class Database:
            def __init__(self, dsn):
                self.closed = False
            def execute(self, query, args=()):
                queries.append(query)
                if query == 'SELECT version FROM smartplan_schema':
                    return SimpleNamespace(fetchall=lambda: [Row(version=6)])
                if 'FROM pg_tables' in query:
                    return SimpleNamespace(fetchall=lambda: [])
                raise AssertionError('Unexpected startup SQL')
            def close(self):
                self.closed = True
        with patch('online.store.Database', Database):
            office = PostgresOffice('synthetic-unused-no-connect')
        self.assertTrue(queries)
        self.assertTrue(all(query.startswith('SELECT ') for query in queries))
        self.assertFalse(office.db.closed)

    def test_unknown_or_ambiguous_storage_marker_is_rejected_and_connection_closed(self):
        for values in ([Row(version=8)], [Row(version=6), Row(version=7)], []):
            db = SimpleNamespace(execute=lambda *args: SimpleNamespace(fetchall=lambda: values), close=lambda: None)
            with patch('online.store.Database', return_value=db), patch.object(db, 'close') as close:
                with self.assertRaises(RuntimeError):
                    PostgresOffice('synthetic-unused-no-connect')
                close.assert_called_once()

    def test_down_cannot_remove_old_schema_receipts_events_or_existing_flags(self):
        before = {'business_schema_migrations': [dict(module='synthetic', version=1, checksum='a')],
                  'business_schema_events': [dict(generation=1, compatibility_mode='business', at='synthetic')],
                  'business_feature_flags': [dict(name='mail_send', enabled=1, revision=1, updated_at='before')]}
        with self.assertRaises(RuntimeError):
            release._verify_control_preserved(before, {}, 'legacy')
        after = {**before, 'business_feature_flags': [dict(name='mail_send', enabled=0, revision=2, updated_at='after')]}
        release._verify_control_preserved(before, after, 'legacy')
        with self.assertRaises(RuntimeError):
            release._verify_control_preserved(before, after, 'business')


class PrivacySetupGuards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.environment = self.root / 'service.env'
        self.original = b"SMARTPLAN_DATABASE_DSN='host=/var/run/postgresql dbname=smartplan_online user=smartplan-online'\nUNRELATED=value\n"
        self.environment.write_bytes(self.original)
        self.environment.chmod(0o600)
        self.directory = self.root / 'private'

    def configure(self):
        with patch('online.release.psycopg.connect', side_effect=AssertionError('No setup DB access')):
            return release.configure_privacy_environment(self.environment, directory=self.directory, test_mode=True)

    def test_setup_is_private_atomic_and_repeated_or_envrollback_retry_never_rekeys(self):
        result = self.configure()
        key = (self.directory / 'key').read_bytes()
        identity = (self.directory / 'installation-id').read_bytes()
        configured = self.environment.read_bytes()
        self.assertEqual(len(key), 32)
        self.assertEqual(self.directory.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.directory / 'key').stat().st_mode & 0o777, 0o600)
        self.assertEqual(result['installation_id'], identity.decode().strip())
        self.assertNotIn(key, configured)
        self.assertTrue(configured.startswith(self.original))
        self.assertFalse((self.directory / 'journal.json').exists())
        self.assertEqual(self.configure(), result)
        self.assertEqual(self.environment.read_bytes(), configured)
        self.environment.write_bytes(self.original)
        self.assertEqual(self.configure(), result)
        self.assertEqual((self.directory / 'key').read_bytes(), key)
        self.assertEqual((self.directory / 'installation-id').read_bytes(), identity)

    def test_partial_or_duplicate_noncanonical_binding_is_never_replaced(self):
        for suffix in (b'SMARTPLAN_PRIVACY_CHECKPOINT_FILE=/missing\n',
                       b'export SMARTPLAN_PRIVACY_CHECKPOINT_FILE=/missing\n',
                       b'SMARTPLAN_PRIVACY_INSTALLATION_ID=x\nSMARTPLAN_PRIVACY_INSTALLATION_ID=y\n'):
            with self.subTest(binding=suffix.split(b'=')[0]):
                self.environment.write_bytes(self.original + suffix)
                before = self.environment.read_bytes()
                with self.assertRaises(ValueError):
                    self.configure()
                self.assertEqual(self.environment.read_bytes(), before)
                self.assertFalse(self.directory.exists())

    def test_partial_directory_or_symlink_key_is_preserved_and_fails_closed(self):
        self.directory.mkdir(mode=0o700)
        key = self.directory / 'key'
        key.write_bytes(b'original synthetic key is short')
        key.chmod(0o600)
        with self.assertRaises((ValueError, FileNotFoundError)):
            self.configure()
        self.assertEqual(key.read_bytes(), b'original synthetic key is short')
        self.assertEqual(self.environment.read_bytes(), self.original)
        key.unlink()
        key.symlink_to(self.environment)
        with self.assertRaises(ValueError):
            self.configure()
        self.assertTrue(key.is_symlink())
        self.assertEqual(self.environment.read_bytes(), self.original)

    def test_failed_environment_publication_retains_private_key_for_safe_retry(self):
        with patch('online.release.atomic_write', side_effect=OSError('Synthetic publication failure')):
            with self.assertRaises(OSError):
                self.configure()
        key = (self.directory / 'key').read_bytes()
        self.assertEqual(self.environment.read_bytes(), self.original)
        self.configure()
        self.assertEqual((self.directory / 'key').read_bytes(), key)

    def test_existing_private_binding_is_kept_and_public_directory_is_refused(self):
        self.configure()
        before = self.environment.read_bytes()
        self.directory.chmod(0o755)
        with self.assertRaises(ValueError):
            self.configure()
        self.assertEqual(self.environment.read_bytes(), before)
        self.assertEqual(self.directory.stat().st_mode & 0o777, 0o755)


@unittest.skipUnless(base.DSN, 'Explicit disposable PostgreSQL DSN required')
class BusinessCandidateRelease(DocumentsFixture, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base.CandidateRelease.setUpClass()

    @classmethod
    def tearDownClass(cls):
        base.CandidateRelease.tearDownClass()

    def setUp(self):
        self.fixture = base.CandidateRelease('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        with psycopg.connect(base.DSN) as connection:
            if not connection.execute("SELECT 1 FROM pg_roles WHERE rolname='smartplan-online'").fetchone():
                connection.execute('CREATE ROLE "smartplan-online" LOGIN')
            connection.execute(sql.SQL('ALTER ROLE "smartplan-online" PASSWORD {}').format(sql.Literal('synthetic-business-runtime-only')))
        release.secure_database(base.DSN, test_mode=True)
        with psycopg.connect(base.DSN, autocommit=True) as connection:
            connection.execute('ALTER DATABASE smartplan_release_check OWNER TO "smartplan-migrator"')
        with psycopg.connect(base.CANDIDATE) as connection:
            connection.execute('ALTER SCHEMA public OWNER TO "smartplan-migrator"')
        self.runtime = make_conninfo(base.DSN, user='smartplan-online', password='synthetic-business-runtime-only')
        self.candidate_runtime = make_conninfo(self.runtime, dbname='smartplan_release_check')
        self.office = PostgresOffice(self.runtime)
        self.addCleanup(self.office.db.close)
        self.owner, self.project = self.fixture.user, self.fixture.project
        self.api = Documents(self.office, clock=lambda: datetime(2030, 1, 10, 12, tzinfo=timezone.utc))

    def prepare(self, mode=None):
        self.office.db.close()
        return release.prepare(base.DSN, base.CANDIDATE, self.fixture.temp.name,
                               test_mode=True, privileged_operator=True, compatibility_mode=mode)

    def seeded_invoice(self):
        self.settings()
        invoice = self.issue(self.draft(kind='invoice'))
        Finance(self.office).record_payment(self.owner, dict(
            request_id=uuid.uuid4().hex, source_id='synthetic-bank-17', kind='receipt', amount='10.00',
            currency='EUR', booking_date='2030-01-10', reference='Synthetic receipt',
            allocations=[dict(document_id=invoice['id'], amount='10.00')]))
        return invoice

    def test_runtime_cannot_own_create_drop_disable_guards_reset_numbers_or_mutate_final_archive(self):
        invoice = self.seeded_invoice()
        self.assertTrue(business_schema.require_runtime_security(self.office))
        before = release.snapshot_fingerprint(base.DSN)
        destructive = (
            'CREATE TABLE public.business_unauthorized(id TEXT)',
            'CREATE TEMP TABLE business_unauthorized_temp(id TEXT)',
            'ALTER TABLE business_document_archives DISABLE TRIGGER USER',
            'DROP TABLE business_document_archives',
            'SET ROLE "smartplan-migrator"',
            "SET LOCAL session_replication_role='replica'",
            'TRUNCATE business_document_numbers',
            'UPDATE business_document_counters SET next_value=1',
            "UPDATE business_documents SET payload_json='{}' WHERE status='final'",
            "UPDATE business_document_archives SET pdf='broken'::bytea",
            'DELETE FROM business_document_numbers',
            'DELETE FROM audit',
            'DELETE FROM business_stock_movements',
            'DELETE FROM business_budget_versions',
            'DELETE FROM business_operation_versions',
            'DELETE FROM business_maintenance_versions',
        )
        for statement in destructive:
            with self.subTest(operation=statement.split()[0]), self.assertRaises(psycopg.Error):
                with self.office.db:
                    self.office.db.execute(statement)
        self.assertEqual(release.snapshot_fingerprint(base.DSN), before)
        self.assertTrue(self.call('archive', invoice['id'], 'pdf').startswith(b'%PDF-'))

    def test_postgres_admin_session_cannot_fake_runtime_proof_by_set_role(self):
        office = PostgresOffice(base.DSN)
        self.addCleanup(office.db.close)
        office.db.execute('SET ROLE "smartplan-online"')
        with self.assertRaises(Problem) as failure:
            business_schema.require_runtime_security(office)
        self.assertEqual(failure.exception.status, 409)

    def test_public_create_or_runtime_membership_is_not_a_valid_issuance_role_proof(self):
        with psycopg.connect(base.DSN) as connection:
            connection.execute('GRANT CREATE ON SCHEMA public TO PUBLIC')
        try:
            with self.assertRaises(Problem):
                business_schema.require_runtime_security(self.office)
        finally:
            with psycopg.connect(base.DSN) as connection:
                connection.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
        with psycopg.connect(base.DSN) as connection:
            connection.execute('GRANT "smartplan-migrator" TO "smartplan-online"')
        try:
            with self.assertRaises(Problem):
                business_schema.require_runtime_security(self.office)
        finally:
            with psycopg.connect(base.DSN) as connection:
                connection.execute('REVOKE "smartplan-migrator" FROM "smartplan-online"')
        self.assertTrue(business_schema.require_runtime_security(self.office))

    def test_extra_table_or_column_grants_are_not_a_valid_runtime_security_proof(self):
        before = release.snapshot_fingerprint(base.DSN)
        for grant in ('GRANT DELETE ON business_stock_movements TO "smartplan-online"',
                      'GRANT UPDATE(payload_json) ON business_budget_versions TO "smartplan-online"',
                      'GRANT UPDATE(financial_reconciliation_required) ON business_restore_state TO "smartplan-online"'):
            with self.subTest(grant=grant.split(' ON ')[0]):
                with psycopg.connect(base.DSN) as connection:
                    connection.execute(grant)
                try:
                    with self.assertRaises(Problem) as failure:
                        business_schema.require_runtime_security(self.office)
                    self.assertEqual(failure.exception.status, 409)
                finally:
                    operator = PostgresOffice(base.DSN)
                    try:
                        with operator.lock, operator.db:
                            business_schema.apply_runtime_privileges(operator)
                    finally:
                        operator.db.close()
                self.assertTrue(business_schema.require_runtime_security(self.office))
        self.assertEqual(release.snapshot_fingerprint(base.DSN), before)

    def test_real_schema6_compatibility_start_and_candidate_up_preserve_every_old_table(self):
        self.office.db.close()
        self.fixture.source_version(6)
        before = release.snapshot_fingerprint(base.DSN)
        legacy = PostgresOffice(self.runtime)
        try:
            self.assertEqual(business_schema.state(legacy)['storage_version'], 6)
            self.assertEqual(business_schema.state(legacy)['capabilities'], [])
        finally:
            legacy.db.close()
        self.assertEqual(release.snapshot_fingerprint(base.DSN), before)
        result = self.prepare()
        self.assertEqual((result['source_schema'], result['target_schema']), (6, 7))
        candidate = release.snapshot_fingerprint(base.CANDIDATE)
        for table, digest in before.items():
            if table != 'smartplan_schema':
                self.assertEqual(candidate[table], digest, table)
        self.assertEqual(release.snapshot_fingerprint(base.DSN), before)

    def test_filled_schema7_down_retains_archive_payment_numbers_and_readable_export(self):
        invoice = self.seeded_invoice()
        self.office.db.close()
        before = release.snapshot_fingerprint(base.DSN)
        result = self.prepare('legacy')
        self.assertEqual(result['business']['storage_version'], 7)
        self.assertEqual(result['business']['capabilities'], [])
        self.assertIn('business_documents', result['business']['read_capabilities'])
        after = release.snapshot_fingerprint(base.CANDIDATE)
        for table, digest in before.items():
            if table not in ('business_schema_state', 'business_schema_events'):
                self.assertEqual(after[table], digest, table)
        office = PostgresOffice(self.candidate_runtime)
        try:
            import business_api
            payload, status, media = business_api.dispatch(office, self.owner,
                '/business/documents/' + invoice['id'] + '/pdf', 'GET', {})
            self.assertEqual((status, media), (200, 'application/pdf'))
            self.assertTrue(payload.startswith(b'%PDF-'))
            with self.assertRaises(Problem):
                business_api.dispatch(office, self.owner, '/business/documents', 'POST', {})
        finally:
            office.db.close()
        self.assertEqual(release.snapshot_fingerprint(base.CANDIDATE), after)
        self.assertEqual(release.snapshot_fingerprint(base.DSN), before)

    def test_explicit_restore_keeps_final_business_and_resets_only_old_access_credentials(self):
        invoice = self.seeded_invoice()
        self.office.db.close()
        before = release.snapshot_fingerprint(base.DSN)
        saved = release.backup(base.DSN, self.fixture.temp.name)
        report = restore(saved, base.DSN, base.CANDIDATE, privileged_operator=True, test_mode=True)
        self.assertTrue(report['restore_pending'])
        with self.assertRaises(RuntimeError):
            PostgresOffice(self.candidate_runtime)
        verifier = PostgresOffice(self.candidate_runtime, allow_restore_pending=True)
        try:
            self.assertFalse(complete_restore(verifier)['restore_pending'])
        finally:
            verifier.db.close()
        after = release.snapshot_fingerprint(base.CANDIDATE)
        for table, digest in before.items():
            if table.startswith('business_') and table != 'business_restore_state':
                self.assertEqual(after[table], digest, table)
        office = PostgresOffice(self.candidate_runtime)
        try:
            self.assertEqual(office.db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0], 0)
            self.assertEqual(office.db.execute('SELECT COUNT(*) FROM plan_sessions').fetchone()[0], 0)
            self.assertTrue(Documents(office).archive(self.owner, invoice['id']).startswith(b'%PDF-'))
            self.assertTrue(business_schema.require_runtime_security(office))
            self.assertTrue(business_schema.state(office)['financial_reconciliation_required'])
            with self.assertRaises(Problem) as blocked:
                business_schema.require_financial_release(office)
            self.assertEqual(blocked.exception.status, 409)
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with office.db:
                    office.db.execute('UPDATE business_restore_state SET financial_reconciliation_required=0')
        finally:
            office.db.close()
        self.assertEqual(release.snapshot_fingerprint(base.DSN), before)

    def test_financial_restore_reconciliation_binds_exact_restore_horizons_and_never_mutates_archives(self):
        self.seeded_invoice()
        self.office.db.close()
        saved = release.backup(base.DSN, self.fixture.temp.name)
        report = restore(saved, base.DSN, base.CANDIDATE, privileged_operator=True, test_mode=True)
        verifier = PostgresOffice(self.candidate_runtime, allow_restore_pending=True)
        try:
            complete_restore(verifier)
        finally:
            verifier.db.close()
        office = PostgresOffice(base.CANDIDATE)
        try:
            evidence = dict(schema=1, restore_id=report['restore_id'], reviewed_by='Synthetic operator',
                            reviewed_at=datetime.now(timezone.utc).isoformat(), outbound_reconciled=True,
                            number_horizons=[dict(company_id=row['company_id'], series=row['series'],
                                                  year=row['year'], last_value=row['next_value'] - 1)
                                             for row in office.db.execute('SELECT * FROM business_document_counters')])
            before = release.snapshot_fingerprint(base.CANDIDATE)
            wrong = {**evidence, 'number_horizons': [{**row, 'last_value': row['last_value'] + 1}
                                                    for row in evidence['number_horizons']]}
            with self.assertRaises(Problem):
                business_schema.reconcile_financial_restore(office, wrong, 'b' * 64)
            self.assertEqual(release.snapshot_fingerprint(base.CANDIDATE), before)
            digest = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()
            result = business_schema.reconcile_financial_restore(office, evidence, digest)
            self.assertEqual(result, business_schema.reconcile_financial_restore(office, evidence, digest))
            after = release.snapshot_fingerprint(base.CANDIDATE)
            for table, fingerprint in before.items():
                if table not in ('business_restore_state', 'business_financial_reconciliations'):
                    self.assertEqual(after[table], fingerprint, table)
            with self.assertRaises(Problem):
                business_schema.reconcile_financial_restore(office, evidence, 'c' * 64)
        finally:
            office.db.close()
        runtime = PostgresOffice(self.candidate_runtime)
        try:
            self.assertTrue(business_schema.require_financial_release(runtime))
            with self.assertRaises(Problem):
                business_schema.reconcile_financial_restore(runtime, evidence, digest)
        finally:
            runtime.db.close()

    def test_privileged_restore_never_reads_runtime_key_and_runtime_replays_newer_privacy_decision(self):
        directory = tempfile.TemporaryDirectory(prefix='smartplan-pg-privacy-')
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        key = root / 'key'
        key.write_bytes(b's' * 32)
        key.chmod(0o600)
        with patch.dict(os.environ, {
                'SMARTPLAN_PRIVACY_CHECKPOINT_FILE': str(root / 'journal.json'),
                'SMARTPLAN_PRIVACY_CHECKPOINT_KEY_FILE': str(key),
                'SMARTPLAN_PRIVACY_INSTALLATION_ID': 'f' * 32,
        }):
            contact = self.office.create_customer(self.owner, {'name': 'Synthetic isolated person', 'email': 'isolated@example.test'})
            with self.office.lock, self.office.db:
                business_schema.initialize_privacy_checkpoint(self.office)
            saved = release.backup(base.DSN, self.fixture.temp.name)
            with self.office.lock, self.office.db:
                business_schema.checkpoint_before_erasure(self.office, contact['id'], 'e' * 32)
            self.office.db.close()
            before = release.snapshot_fingerprint(base.DSN)
            with patch('business_schema._privacy_config', side_effect=AssertionError('Operator must not read runtime key')):
                report = restore(saved, base.DSN, base.CANDIDATE, privileged_operator=True, test_mode=True)
            self.assertTrue(report['restore_pending'])
            with self.assertRaises(RuntimeError):
                PostgresOffice(self.candidate_runtime)
            verifier = PostgresOffice(self.candidate_runtime, allow_restore_pending=True)
            try:
                self.assertEqual(verifier.db.execute('SELECT name FROM customers WHERE id=?', (contact['id'],)).fetchone()[0], 'Synthetic isolated person')
                complete_restore(verifier)
                after = release.snapshot_fingerprint(base.CANDIDATE)
                complete_restore(verifier)
                self.assertEqual(release.snapshot_fingerprint(base.CANDIDATE), after)
                self.assertNotEqual(verifier.db.execute('SELECT name FROM customers WHERE id=?', (contact['id'],)).fetchone()[0], 'Synthetic isolated person')
            finally:
                verifier.db.close()
            normal = PostgresOffice(self.candidate_runtime)
            normal.db.close()
            self.assertEqual(release.snapshot_fingerprint(base.DSN), before)

    def test_real_pg_up_up_down_down_up_preserves_all_canonical_rows_and_never_reuses_numbers(self):
        invoice = self.seeded_invoice()
        self.office.db.close()
        before = release.snapshot_fingerprint(base.DSN)
        migrate(base.DSN, owner_role='smartplan-migrator', compatibility_mode='business')
        migrate(base.DSN, owner_role='smartplan-migrator', compatibility_mode='business')
        self.assertEqual(release.snapshot_fingerprint(base.DSN), before)
        migrate(base.DSN, owner_role='smartplan-migrator', compatibility_mode='legacy')
        down = release.snapshot_fingerprint(base.DSN)
        migrate(base.DSN, owner_role='smartplan-migrator', compatibility_mode='legacy')
        self.assertEqual(release.snapshot_fingerprint(base.DSN), down)
        migrate(base.DSN, owner_role='smartplan-migrator', compatibility_mode='business')
        after = release.snapshot_fingerprint(base.DSN)
        for table, digest in before.items():
            if table not in ('business_schema_state', 'business_schema_events'):
                self.assertEqual(after[table], digest, table)
        office = PostgresOffice(self.runtime)
        try:
            self.assertEqual(business_schema.state(office)['storage_version'], 7)
            self.assertTrue(Documents(office).archive(self.owner, invoice['id']).startswith(b'%PDF-'))
            self.assertEqual(office.db.execute('SELECT next_value FROM business_document_counters').fetchone()[0], 2)
        finally:
            office.db.close()


if __name__ == '__main__':
    unittest.main()
