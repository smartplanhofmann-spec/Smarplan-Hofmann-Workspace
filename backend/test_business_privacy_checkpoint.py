"""Independent journal survives an older SQLite snapshot; synthetic subjects only."""
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import business_schema as schema
from core import Problem


@unittest.skipUnless(os.name == 'posix', 'Independent checkpoint is the private POSIX Hetzner server, not a Windows DACL implementation')
class PrivacyCheckpointContract(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        root.chmod(0o700)
        self.file = root / 'independent-checkpoint.json'
        self.key = root / 'key'
        self.key.write_bytes(b's' * 32)
        self.key.chmod(0o600)
        self.environment = patch.dict(os.environ, {
            'SMARTPLAN_PRIVACY_CHECKPOINT_FILE': str(self.file),
            'SMARTPLAN_PRIVACY_CHECKPOINT_KEY_FILE': str(self.key),
            'SMARTPLAN_PRIVACY_INSTALLATION_ID': 'a' * 32,
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.registry = patch('business_schema.registry', return_value=())
        self.registry.start()
        self.addCleanup(self.registry.stop)
        self.db = sqlite3.connect(root / 'live.sqlite3')
        self.db.row_factory = sqlite3.Row
        self.addCleanup(self.db.close)
        self.office = SimpleNamespace(db=self.db, lock=threading.RLock())
        schema.ensure_schema(self.office)
        with self.db:
            self.db.execute('CREATE TABLE synthetic_subjects(id TEXT PRIMARY KEY, name TEXT NOT NULL)')
            self.db.execute('INSERT INTO synthetic_subjects VALUES(?,?)', ('b' * 32, 'Synthetic private name'))

    def initialize(self):
        return schema.initialize_privacy_checkpoint(self.office)

    def event(self, identifier='b' * 32, request='c' * 32):
        return schema.checkpoint_before_erasure(self.office, identifier, request)

    def anchor(self, office=None):
        return [tuple(row) for row in (office or self.office).db.execute('SELECT * FROM business_privacy_anchors')]

    def replay(self, office, event):
        for row in office.db.execute('SELECT id FROM synthetic_subjects').fetchall():
            if schema.privacy_subject_hash('customer', row['id']) == event['subject_hash']:
                office.db.execute('UPDATE synthetic_subjects SET name=? WHERE id=?', ('Anonymisiert', row['id']))

    def test_no_configuration_blocks_erasure_without_changing_database_or_creating_journal(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(Problem) as failure:
                self.event()
        self.assertEqual(failure.exception.status, 409)
        self.assertEqual(self.anchor(), [])
        self.assertFalse(self.file.exists())
        self.assertEqual(self.db.execute('SELECT name FROM synthetic_subjects').fetchone()[0], 'Synthetic private name')

    def test_missing_anchor_cannot_be_initialized_with_empty_journal_after_actual_purge(self):
        self.db.execute('CREATE TABLE business_time_privacy(employee_id TEXT,work_date TEXT)')
        self.db.execute('INSERT INTO business_time_privacy VALUES(?,?)', ('b' * 32, '2030-01-10'))
        self.db.commit()
        with self.assertRaises(Problem):
            self.initialize()
        self.assertFalse(self.file.exists())
        self.assertEqual(self.anchor(), [])

    def test_initialization_and_record_are_private_signed_idempotent_and_contain_no_personal_payload(self):
        self.initialize()
        first = self.event()
        before, anchor = self.file.read_bytes(), self.anchor()
        self.assertEqual(self.event(), first)
        self.assertEqual(self.file.read_bytes(), before)
        self.assertEqual(self.anchor(), anchor)
        self.assertEqual(first['generation'], 1)
        self.assertNotIn(b'Synthetic private name', before)
        self.assertNotIn(('b' * 32).encode(), before)
        self.assertNotIn(b's' * 32, before)
        self.assertEqual(self.file.stat().st_mode & 0o777, 0o600)

    def test_same_request_cannot_be_rebound_to_another_subject_or_operation(self):
        self.initialize()
        self.event()
        before, anchor = self.file.read_bytes(), self.anchor()
        with self.assertRaises(Problem) as failure:
            self.event('d' * 32)
        self.assertEqual(failure.exception.status, 409)
        self.assertEqual(self.file.read_bytes(), before)
        self.assertEqual(self.anchor(), anchor)

    def test_database_rollback_does_not_rollback_independent_decision_and_retry_uses_same_generation(self):
        self.initialize()
        self.db.execute('BEGIN IMMEDIATE')
        event = self.event()
        self.db.execute('UPDATE synthetic_subjects SET name=?', ('temporary change',))
        self.db.rollback()
        self.assertEqual(self.anchor()[0][1], 0)
        self.assertEqual(json.loads(self.file.read_bytes())['generation'], 1)
        retry = self.event()
        self.assertEqual(retry, event)
        self.assertEqual(self.anchor()[0][1], 1)
        self.assertEqual(self.db.execute('SELECT name FROM synthetic_subjects').fetchone()[0], 'Synthetic private name')

    def test_true_older_database_snapshot_reapplies_newer_independent_erasure_before_use(self):
        self.initialize()
        older = sqlite3.connect(Path(self.temporary.name) / 'older.sqlite3')
        older.row_factory = sqlite3.Row
        self.addCleanup(older.close)
        self.db.backup(older)
        self.event()
        with self.db:
            self.db.execute('UPDATE synthetic_subjects SET name=?', ('Anonymisiert',))
        restored = SimpleNamespace(db=older, lock=threading.RLock())
        self.assertEqual(older.execute('SELECT name FROM synthetic_subjects').fetchone()[0], 'Synthetic private name')
        module = SimpleNamespace(reapply_privacy_checkpoint=self.replay)
        with patch('business_schema.importlib.import_module', return_value=module):
            schema.privacy_restore_guard(restored)
            before = self.anchor(restored)
            schema.privacy_restore_guard(restored)
        self.assertEqual(self.anchor(restored), before)
        self.assertEqual(older.execute('SELECT name FROM synthetic_subjects').fetchone()[0], 'Anonymisiert')
        self.assertEqual(self.anchor(restored)[0][1], 1)

    def test_deleting_or_rolling_back_journal_cannot_turn_existing_decisions_into_empty_history(self):
        self.initialize()
        old = self.file.read_bytes()
        self.event()
        anchor = self.anchor()
        self.file.write_bytes(old)
        with self.assertRaises(Problem):
            schema.privacy_restore_guard(self.office)
        self.assertEqual(self.anchor(), anchor)
        self.file.unlink()
        with self.assertRaises(Problem):
            schema.privacy_restore_guard(self.office)
        self.assertEqual(self.anchor(), anchor)

    def test_modified_signed_bytes_wrong_key_or_installation_are_rejected(self):
        self.initialize()
        self.event()
        original = self.file.read_bytes()
        value = json.loads(original)
        value['events'][0]['subject_hash'] = '0' * 64
        self.file.write_text(json.dumps(value))
        with self.assertRaises(Problem):
            schema.privacy_restore_guard(self.office)
        self.file.write_bytes(original)
        self.key.write_bytes(b't' * 32)
        with self.assertRaises(Problem):
            schema.privacy_restore_guard(self.office)
        self.key.write_bytes(b's' * 32)
        with patch.dict(os.environ, {'SMARTPLAN_PRIVACY_INSTALLATION_ID': 'f' * 32}):
            with self.assertRaises(Problem):
                schema.privacy_restore_guard(self.office)

    def test_missing_replayer_or_unsafe_replay_failure_never_advances_anchor_or_commits_partial_cleanup(self):
        self.initialize()
        self.db.execute('BEGIN IMMEDIATE')
        self.event()
        self.db.rollback()
        before = self.anchor()
        def fail(office, event):
            self.replay(office, event)
            raise ValueError('Synthetic retention constraint')
        for module in (SimpleNamespace(), SimpleNamespace(reapply_privacy_checkpoint=fail)):
            with patch('business_schema.importlib.import_module', return_value=module):
                with self.assertRaises((Problem, ValueError)):
                    schema.privacy_restore_guard(self.office)
            self.assertEqual(self.anchor(), before)
            self.assertEqual(self.db.execute('SELECT name FROM synthetic_subjects').fetchone()[0], 'Synthetic private name')

    def test_journal_fsync_failure_prevents_any_database_anchor_or_personal_data_change(self):
        self.initialize()
        before = self.anchor()
        with patch('business_schema.os.fsync', side_effect=OSError('Synthetic persistence failure')):
            with self.assertRaises(OSError):
                self.event()
        self.assertEqual(self.anchor(), before)
        self.assertEqual(self.db.execute('SELECT name FROM synthetic_subjects').fetchone()[0], 'Synthetic private name')

    def test_location_checkpoint_contains_no_coordinates_and_binds_employee_day(self):
        self.initialize()
        event = schema.checkpoint_before_location_purge(self.office, 'b' * 32, '2026-10-25', 'e' * 32)
        self.assertEqual(event['operation'], 'purge_time_locations')
        self.assertEqual(event['subject_hash'], schema.privacy_subject_hash('time_day', 'b' * 32 + ':2026-10-25'))
        data = self.file.read_bytes()
        self.assertNotIn(b'2026-10-25"', data)
        self.assertNotIn(('b' * 32).encode(), data)
        self.assertNotIn(b'latitude', data)
        self.assertNotIn(b'longitude', data)


class PrivacyPlatformBoundary(unittest.TestCase):
    def test_windows_local_backend_cannot_claim_a_posix_server_checkpoint(self):
        with patch.dict(os.environ, {
                'SMARTPLAN_PRIVACY_CHECKPOINT_FILE': '/synthetic/journal.json',
                'SMARTPLAN_PRIVACY_CHECKPOINT_KEY_FILE': '/synthetic/key',
                'SMARTPLAN_PRIVACY_INSTALLATION_ID': 'a' * 32,
        }), patch('business_schema.os.name', 'nt'):
            with self.assertRaises(Problem) as failure:
                schema.privacy_subject_hash('customer', 'b' * 32)
        self.assertEqual(failure.exception.status, 409)


if __name__ == '__main__':
    unittest.main()
