"""Additive V2 grants retain old data and revoke cleanly across restore."""
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid

from cryptography.fernet import Fernet

from core import Office, Problem, canonical, digest
import business_schema
import plan_access
from business_offline_binding import TABLE, context, validate_integrity
from online.instance import bind
from online.storage import Storage


class OfflineBindingStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic-offline-binding-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'office.sqlite3'
        self.office = Office(self.path)
        self.addCleanup(self.office.db.close)
        self.actor = dict(id=self.office.add_user('binding@example.test', 'Synthetic-binding-password-123', 'owner'), role='owner')
        self.instance = uuid.uuid4().hex

    def bind(self, office=None):
        office = office or self.office
        key = Fernet.generate_key()
        storage = Storage(office, key, 'binding.example.test', config={'server': {'path': str(Path(self.temp.name) / 'private-store')}})
        bind(office, self.instance, 'binding.example.test', key, storage)

    def grant(self, **extra):
        with self.office.lock, self.office.db:
            return plan_access.issue(self.office, self.actor, workspace=True, protocol_version=2, **extra)

    def test_v2_requires_real_binding_and_preserves_legacy_credential_algorithm(self):
        row = self.office.db.execute('SELECT * FROM users WHERE id=?', (self.actor['id'],)).fetchone()
        expected = digest(canonical([row['id'], row['salt'], row['password'], row['role'], row['active']]))
        self.assertEqual(plan_access.credential(row), expected)
        with self.assertRaises(Problem) as refused:
            self.grant()
        self.assertEqual(refused.exception.status, 409)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM plan_sessions').fetchone()[0], 0)
        self.bind()
        issued = self.grant()
        stored = self.office.db.execute('SELECT * FROM plan_sessions').fetchone()
        self.assertNotEqual(stored['credential'], expected)
        self.assertEqual(stored['credential'], plan_access.credential(row, instance_id=self.instance))
        self.assertEqual(issued['binding'], context(self.office, self.actor)['binding'])
        self.assertEqual(plan_access.user(self.office, issued['token'])['id'], self.actor['id'])
        self.assertTrue(validate_integrity(self.office))

    def test_grant_failure_rolls_back_and_binding_is_immutable_but_revocable(self):
        self.bind()
        with patch.object(self.office, 'audit', side_effect=RuntimeError('Synthetic unavailable audit')):
            with self.assertRaises(RuntimeError):
                self.grant()
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM plan_sessions').fetchone()[0], 0)
        issued = self.grant()
        with self.assertRaises(sqlite3.DatabaseError):
            with self.office.db:
                self.office.db.execute(f'UPDATE {TABLE} SET instance_id=?', (uuid.uuid4().hex,))
        with self.office.db:
            plan_access.revoke(self.office, issued['token'])
        self.assertEqual(self.office.db.execute(f'SELECT COUNT(*) FROM {TABLE}').fetchone()[0], 0)
        with self.assertRaises(Problem):
            plan_access.user(self.office, issued['token'])

    def test_expired_grant_cleanup_cascades_without_changing_existing_plans(self):
        self.bind()
        issued = self.grant()
        with patch('plan_access.time.time', return_value=time.time() + 8 * 86400):
            with self.assertRaises(Problem) as expired:
                plan_access.user(self.office, issued['token'])
            self.assertEqual(expired.exception.status, 401)
            next_grant = self.grant()
        rows = self.office.db.execute(f'SELECT token_hash FROM {TABLE}').fetchall()
        self.assertEqual([row['token_hash'] for row in rows], [digest(next_grant['token'])])
        self.assertTrue(validate_integrity(self.office))

    def test_actual_backup_restore_revokes_v2_grants_but_preserves_original_plan(self):
        from backup import backup
        from restore import restore
        self.bind()
        issued = self.grant()
        project = self.office.add_project(self.actor, 'Retained synthetic plan', 'Synthetic customer')
        original = self.office.save_plan(self.actor, project, dict(request_id=uuid.uuid4().hex, title='Original', walls=[]))
        saved = backup(self.path, Path(self.temp.name) / 'backup.sqlite3')
        restored = Office(restore(saved, Path(self.temp.name) / 'restored.sqlite3'))
        self.addCleanup(restored.db.close)
        self.assertEqual(restored.plan(self.actor, project, original['id']), original)
        for table in ('plan_sessions', TABLE):
            self.assertEqual(restored.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0], 0)
        self.assertTrue(validate_integrity(restored))
        with self.assertRaises(Problem):
            plan_access.user(restored, issued['token'])

    def test_recovery_rejects_changed_float_bits_even_when_numeric_equality_holds(self):
        from business_offline_binding import legacy_lookup
        self.bind()
        project = self.office.add_project(self.actor, 'Float original', 'Synthetic customer')
        body = dict(request_id=uuid.uuid4().hex, title='Original',
                    walls=[dict(id='wall_1', points=[[-0.0, 1.0], [0.000001, 2.0]])])
        original = self.office.save_plan(self.actor, project, body)
        lookup = dict(schema_version=1, nonce=uuid.uuid4().hex, kind='plan_write', project_id=project,
                      plan_id=None, command_json=canonical(body))
        self.assertEqual(legacy_lookup(self.office, self.actor, lookup)['original'], original)
        changed = json.loads(canonical(original))
        changed['walls'][0]['points'][0][0] = 0.0
        self.assertEqual(changed, original)  # Python numeric equality alone hides the changed sign.
        with self.office.db:
            self.office.db.execute('UPDATE plan_requests SET result=? WHERE request_id=?',
                                   (canonical(changed), body['request_id']))
            self.office.db.execute('UPDATE plan_versions SET payload=? WHERE id=? AND revision=1',
                                   (canonical(changed), original['id']))
        with self.assertRaises(Problem) as error:
            legacy_lookup(self.office, self.actor, lookup)
        self.assertEqual(error.exception.status, 409)
        self.assertIsNone(error.exception.request_resolution)

    def test_immutable_grant_expiry_cannot_be_extended_by_mutable_session(self):
        self.bind()
        grant = self.grant()
        original_expiry = self.office.db.execute(f'SELECT expiry FROM {TABLE}').fetchone()[0]
        with self.office.db:
            self.office.db.execute('UPDATE plan_sessions SET expiry=expiry+? WHERE token=?',
                                   (30*86400, digest(grant['token'])))
        with patch('time.time', return_value=original_expiry+1), self.assertRaises(Problem) as denied:
            plan_access.user(self.office, grant['token'])
        self.assertEqual(denied.exception.status, 403)
        with self.assertRaises(ValueError):
            validate_integrity(self.office)

    def test_legacy_integer_float_exponents_and_original_updates_remain_readable(self):
        from business_offline_binding import legacy_lookup
        self.bind()
        project = self.office.add_project(self.actor, 'Legacy numeric originals', 'Synthetic customer')
        for points in ([[1, 0], [3, 4]], [[1.0, -0.0], [1e-6, 2.5]]):
            body = dict(request_id=uuid.uuid4().hex, title=' Original Süd ', walls=[dict(id='wall_1', points=points)])
            original = self.office.save_plan(self.actor, project, body)
            updated_body = dict(request_id=uuid.uuid4().hex, title='Updated', walls=body['walls'], revision=1)
            updated = self.office.save_plan(self.actor, project, updated_body, original['id'])
            for plan_id, command, expected in ((None, body, original), (original['id'], updated_body, updated)):
                for text in (canonical(command), json.dumps(command, indent=2).replace('1e-06', '0.000001')):
                    lookup = dict(schema_version=1, nonce=uuid.uuid4().hex, kind='plan_write', project_id=project,
                                  plan_id=plan_id, command_json=text)
                    result = legacy_lookup(self.office, self.actor, lookup)
                    self.assertEqual(canonical(result['original']), canonical(expected))
                    self.assertEqual(result['request_hash'], digest(canonical(dict(project_id=project, plan_id=plan_id, data=command))))
                    self.assertEqual(result['lookup_hash'], digest(canonical(lookup)))

    def test_additive_migration_keeps_v1_sessions_then_binding_blocks_them_without_deletion(self):
        specs = business_schema.registry()
        old = tuple(spec for spec in specs if spec.name != 'business_offline_binding')
        with patch.object(business_schema, 'registry', return_value=old):
            office = Office(Path(self.temp.name) / 'old.sqlite3')
        self.addCleanup(office.db.close)
        actor = dict(id=office.add_user('old-binding@example.test', 'Synthetic-old-password-123', 'owner'), role='owner')
        with office.db:
            legacy = plan_access.issue(office, actor, workspace=True)
        before = [tuple(row) for row in office.db.execute('SELECT * FROM plan_sessions')]
        checksums = [tuple(row) for row in office.db.execute('SELECT module,version,checksum FROM business_schema_migrations ORDER BY module,version')]
        business_schema.ensure_schema(office, registry=specs, activate=True)
        self.assertEqual([tuple(row) for row in office.db.execute('SELECT * FROM plan_sessions')], before)
        self.assertEqual([tuple(row) for row in office.db.execute("SELECT module,version,checksum FROM business_schema_migrations WHERE module!='business_offline_binding' ORDER BY module,version")], checksums)
        self.assertEqual(plan_access.user(office, legacy['token'])['id'], actor['id'])
        self.bind(office)
        with self.assertRaises(Problem) as blocked:
            plan_access.user(office, legacy['token'])
        self.assertEqual(blocked.exception.status, 409)
        self.assertEqual([tuple(row) for row in office.db.execute('SELECT * FROM plan_sessions')], before)


if __name__ == '__main__':
    unittest.main()
