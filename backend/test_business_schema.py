"""Migration contract first: disposable synthetic SQLite, no provider or PG I/O.

These tests specify the new schema foundation before its production wiring. A
module failure must never commit an enclosing request or erase a newer archive.
"""
import hashlib
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import business_schema


class BusinessSchemaContract(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / 'synthetic.sqlite3'
        database = sqlite3.connect(self.path)
        database.row_factory = sqlite3.Row
        database.execute('PRAGMA foreign_keys=ON')
        self.office = SimpleNamespace(db=database, lock=threading.RLock())
        self.addCleanup(self.office.db.close)
        self.loaded = []
        self.validated = []
        self.module = self.document_module()
        self.registry = (business_schema.ModuleSpec('synthetic_documents', 1, self.load_documents),)
        with self.office.db:
            self.office.db.execute('CREATE TABLE legacy_originals(id TEXT PRIMARY KEY, data BLOB NOT NULL)')
            self.office.db.execute('INSERT INTO legacy_originals VALUES(?,?)',
                                   ('legacy-unchanged', b'\x00synthetic original\xff'))

    def document_module(self):
        def statements(binary_type='BYTEA'):
            if binary_type not in ('BLOB', 'BYTEA'):
                raise ValueError('Unexpected binary storage type')
            return [
                'CREATE TABLE IF NOT EXISTS synthetic_documents('
                'id TEXT PRIMARY KEY,number INTEGER UNIQUE NOT NULL,'
                'status TEXT NOT NULL,pdf ' + binary_type + ' NOT NULL,sha256 TEXT NOT NULL)',
                'CREATE TABLE IF NOT EXISTS synthetic_financial_audit('
                'id TEXT PRIMARY KEY,document_id TEXT NOT NULL REFERENCES synthetic_documents(id),'
                'action TEXT NOT NULL)',
                'CREATE TABLE IF NOT EXISTS synthetic_send_receipts('
                'request_id TEXT PRIMARY KEY,document_id TEXT NOT NULL REFERENCES synthetic_documents(id),'
                'state TEXT NOT NULL,provider_id TEXT)',
            ]

        def validate(office):
            self.validated.append('documents')
            for row in office.db.execute('SELECT pdf,sha256 FROM synthetic_documents').fetchall():
                if hashlib.sha256(bytes(row['pdf'])).hexdigest() != row['sha256']:
                    raise ValueError('Synthetic archive corruption')

        return SimpleNamespace(schema_statements=statements, validate_integrity=validate)

    def load_documents(self):
        self.loaded.append('documents')
        return self.module

    def snapshot(self, *, canonical_only=False):
        names = [row[0] for row in self.office.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        if canonical_only:
            names = [name for name in names if name.startswith(('legacy_', 'synthetic_'))]
        return {name: sorted((tuple(row) for row in self.office.db.execute('SELECT * FROM "' + name + '"')),
                             key=repr) for name in names}

    def up(self, registry=None):
        return business_schema.ensure_schema(self.office, registry=self.registry if registry is None else registry)

    def mode(self, value, registry=None):
        return business_schema.set_mode(self.office, value, registry=self.registry if registry is None else registry)

    def current(self):
        return business_schema.state(self.office, registry=self.registry)

    def seed_archive(self):
        original = b'%PDF-1.4\nSynthetic frozen invoice, never a customer document\n%%EOF'
        with self.office.db:
            self.office.db.execute('INSERT INTO synthetic_documents VALUES(?,?,?,?,?)',
                                   ('a' * 32, 17, 'finalized', original, hashlib.sha256(original).hexdigest()))
            self.office.db.execute('INSERT INTO synthetic_financial_audit VALUES(?,?,?)',
                                   ('b' * 32, 'a' * 32, 'invoice.finalized'))
            self.office.db.execute('INSERT INTO synthetic_send_receipts VALUES(?,?,?,?)',
                                   ('c' * 32, 'a' * 32, 'unknown', 'synthetic-provider-message-17'))

    def test_legacy_read_is_lazy_and_never_creates_or_migrates_any_table(self):
        before = self.snapshot()
        value = self.current()
        self.assertEqual(value['storage_version'], 6)
        self.assertEqual(value['compatibility_mode'], 'legacy')
        self.assertEqual(value['capabilities'], [])
        self.assertEqual(self.loaded, [])
        self.assertEqual(self.snapshot(), before)

    def test_explicit_up_is_additive_and_preserves_legacy_ids_and_binary_originals(self):
        before = self.snapshot()
        self.up()
        value = self.current()
        self.assertEqual(value['storage_version'], 7)
        self.assertEqual(value['compatibility_mode'], 'business')
        after = self.snapshot()
        for name, rows in before.items():
            self.assertEqual(after[name], rows, name)
        self.assertIn('synthetic_documents', after)
        self.assertIn('documents', self.validated)

    def test_repeated_up_does_not_change_generation_timestamps_receipts_or_rows(self):
        self.up()
        self.seed_archive()
        before, state = self.snapshot(), self.current()
        self.up()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.current(), state)

    def test_up_up_down_down_up_keeps_finalized_archive_audit_numbers_and_unknown_send(self):
        self.up()
        self.seed_archive()
        canonical = self.snapshot(canonical_only=True)
        self.up()
        self.mode('legacy')
        down, first_down = self.current(), self.snapshot()
        self.assertEqual(down['storage_version'], 7)
        self.assertEqual(down['compatibility_mode'], 'legacy')
        self.assertEqual(down['capabilities'], [])
        self.assertEqual(self.snapshot(canonical_only=True), canonical)
        self.mode('legacy')
        self.assertEqual(self.snapshot(), first_down)
        self.assertEqual(self.current(), down)
        self.up()
        self.assertEqual(self.current()['storage_version'], 7)
        self.assertEqual(self.current()['compatibility_mode'], 'business')
        self.assertEqual(self.snapshot(canonical_only=True), canonical)
        self.assertEqual(self.office.db.execute('SELECT number FROM synthetic_documents').fetchone()[0], 17)
        self.assertEqual(self.office.db.execute('SELECT state FROM synthetic_send_receipts').fetchone()[0], 'unknown')

    def test_archive_is_still_readable_after_down_and_reopening_the_real_file(self):
        self.up()
        self.seed_archive()
        self.mode('legacy')
        expected = self.snapshot(canonical_only=True)
        reopened = sqlite3.connect(self.path)
        reopened.row_factory = sqlite3.Row
        self.addCleanup(reopened.close)
        office = SimpleNamespace(db=reopened, lock=self.office.lock)
        value = business_schema.state(office, registry=self.registry)
        self.assertEqual((value['storage_version'], value['compatibility_mode']), (7, 'legacy'))
        for name, rows in expected.items():
            saved = sorted((tuple(row) for row in reopened.execute('SELECT * FROM "' + name + '"')), key=repr)
            self.assertEqual(saved, rows, name)

    def test_sqlite_startup_migration_never_reenables_a_deliberate_legacy_mode(self):
        self.up()
        self.seed_archive()
        self.mode('legacy')
        before = self.snapshot()
        business_schema.ensure_sqlite_schema(self.office, registry=self.registry)
        self.assertEqual(self.current()['compatibility_mode'], 'legacy')
        self.assertEqual(self.snapshot(), before)

    def test_partial_second_module_ddl_failure_rolls_back_the_whole_first_up(self):
        bad = SimpleNamespace(schema_statements=lambda binary_type='BYTEA': [
            'CREATE TABLE synthetic_partial(id TEXT PRIMARY KEY)',
            'CREATE TABLE syntactically broken synthetic statement'], validate_integrity=lambda office: None)
        registry = self.registry + (business_schema.ModuleSpec('synthetic_failure', 1, lambda: bad),)
        before = self.snapshot()
        with self.assertRaises((sqlite3.DatabaseError, RuntimeError, ValueError)):
            self.up(registry)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.current()['storage_version'], 6)

    def test_failed_module_validator_does_not_publish_any_new_schema_state(self):
        def fail(office):
            raise ValueError('Synthetic validation failure')
        self.module = SimpleNamespace(schema_statements=self.module.schema_statements, validate_integrity=fail)
        before = self.snapshot()
        with self.assertRaises((RuntimeError, ValueError)):
            self.up()
        self.assertEqual(self.snapshot(), before)

    def test_schema_up_never_commits_an_enclosing_sqlite_request(self):
        self.office.db.execute('BEGIN IMMEDIATE')
        self.office.db.execute('INSERT INTO legacy_originals VALUES(?,?)', ('uncommitted-request', b'pending'))
        self.up()
        self.assertTrue(self.office.db.in_transaction)
        self.office.db.rollback()
        self.assertIsNone(self.office.db.execute('SELECT 1 FROM legacy_originals WHERE id=?',
                                               ('uncommitted-request',)).fetchone())
        self.assertEqual(self.current()['storage_version'], 6)

    def test_changed_registered_ddl_checksum_fails_without_modifying_any_record(self):
        self.up()
        self.seed_archive()
        before = self.snapshot()
        original = self.module.schema_statements
        self.module = SimpleNamespace(schema_statements=lambda binary_type='BYTEA': original(binary_type) + [
            'CREATE TABLE IF NOT EXISTS synthetic_unversioned_change(id TEXT PRIMARY KEY)'],
            validate_integrity=self.module.validate_integrity)
        with self.assertRaises((RuntimeError, ValueError)):
            self.up()
        self.assertEqual(self.snapshot(), before)

    def test_missing_previously_registered_module_cannot_silently_down_or_skip_validation(self):
        self.up()
        self.seed_archive()
        before = self.snapshot()
        with self.assertRaises((RuntimeError, ValueError)):
            self.mode('legacy', ())
        self.assertEqual(self.snapshot(), before)

    def test_unavailable_registered_code_fails_closed_without_partial_migration(self):
        def unavailable():
            raise ImportError('Synthetic missing registered module')
        registry = self.registry + (business_schema.ModuleSpec('synthetic_missing', 1, unavailable),)
        before = self.snapshot()
        with self.assertRaises((ImportError, RuntimeError, ValueError)):
            self.up(registry)
        self.assertEqual(self.snapshot(), before)

    def test_down_checks_archive_integrity_before_changing_active_capabilities(self):
        self.up()
        self.seed_archive()
        with self.office.db:
            self.office.db.execute('UPDATE synthetic_documents SET pdf=?', (b'corrupt synthetic bytes',))
        before = self.snapshot()
        with self.assertRaises((RuntimeError, ValueError)):
            self.mode('legacy')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.current()['compatibility_mode'], 'business')

    def test_unknown_mode_fails_before_any_write_or_module_load(self):
        before = self.snapshot()
        with self.assertRaises((RuntimeError, ValueError)):
            self.mode('schema-6-reset')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.loaded, [])

    def device(self, capabilities='["time_events","field_media"]'):
        issued = datetime(2030, 1, 1, tzinfo=timezone.utc)
        with self.office.db:
            self.office.db.execute('CREATE TABLE users(id TEXT PRIMARY KEY)')
            self.office.db.execute('CREATE TABLE plan_sessions(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),expiry DOUBLE PRECISION)')
            self.office.db.execute('INSERT INTO users VALUES(?)', ('a' * 32,))
            self.office.db.execute('INSERT INTO plan_sessions VALUES(?,?,?)', ('b' * 64, 'a' * 32, issued.timestamp() + 86400))
        self.up()
        with self.office.db:
            self.office.db.execute('INSERT INTO business_device_grants(token_hash,user_id,capabilities_json,issued_at,expiry) VALUES(?,?,?,?,?)',
                                   ('b' * 64, 'a' * 32, capabilities, issued.isoformat(), issued.timestamp() + 86400))

    def test_explicit_new_device_scope_survives_down_and_cascades_on_session_revocation(self):
        self.device()
        business_schema.validate_integrity(self.office, registry=self.registry)
        with self.office.db:
            grant = tuple(self.office.db.execute('SELECT * FROM business_device_grants').fetchone())
        self.mode('legacy')
        self.assertEqual(tuple(self.office.db.execute('SELECT * FROM business_device_grants').fetchone()), grant)
        with self.office.db:
            self.office.db.execute('DELETE FROM plan_sessions WHERE token=?', ('b' * 64,))
        self.assertIsNone(self.office.db.execute('SELECT * FROM business_device_grants').fetchone())

    def test_device_scope_never_accepts_financial_unknown_or_duplicate_capabilities(self):
        self.device('["finance.issue"]')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            business_schema.validate_integrity(self.office, registry=self.registry)
        self.assertEqual(self.snapshot(), before)
        for capabilities in ('["time_events","time_events"]', '["legacy_plan_access"]', '[]'):
            with self.office.db:
                self.office.db.execute('UPDATE business_device_grants SET capabilities_json=?', (capabilities,))
            with self.assertRaises(ValueError):
                business_schema.validate_integrity(self.office, registry=self.registry)


if __name__ == '__main__':
    unittest.main()
