"""Two synthetic companies through real HTTP/auth/domain code, without services.

SQLite fixtures prove API scoping; they do not claim PostgreSQL process/role,
backup, connector or production deployment acceptance.
"""
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid

from cryptography.fernet import Fernet

from core import Office, Problem
from online.auth import totp
from online.instance import bind, identity, verify_worker, MARKER, InstanceConfigurationError
from online.storage import Storage
from online.web import create_app


MFA_SCHEMA = '''
CREATE TABLE mfa(user_id TEXT PRIMARY KEY REFERENCES users(id),secret TEXT NOT NULL,
 last_step BIGINT NOT NULL DEFAULT -1,recovery TEXT NOT NULL);
CREATE TABLE auth_challenges(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),
 credential TEXT NOT NULL,secret TEXT NOT NULL,expiry DOUBLE PRECISION NOT NULL,
 failures INTEGER NOT NULL DEFAULT 0);
CREATE TABLE login_limits(key TEXT PRIMARY KEY,failures INTEGER NOT NULL,reset_at DOUBLE PRECISION NOT NULL);
'''


@unittest.skipUnless(os.name == 'posix', 'Private POSIX server storage required')
class InstanceIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic-company-isolation-')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.company = [self.fixture('alpha'), self.fixture('beta')]

    def fixture(self, name):
        office = Office(self.directory / (name + '.sqlite3'))
        self.addCleanup(office.db.close)
        office.db.executescript(MFA_SCHEMA)
        value = dict(office=office, instance_id=uuid.uuid4().hex, host=name + '.example.test',
                     key=Fernet.generate_key(), root=self.directory / name)
        value['storage'] = Storage(office, value['key'], value['host'],
                                   config={'server': {'path': str(value['root'])}})
        office.add_user('owner@example.test', 'Synthetic-owner-password-123', 'owner')
        return value

    def bind(self, value):
        return bind(value['office'], value['instance_id'], value['host'], value['key'], value['storage'])

    def app(self, value, **changes):
        args = dict(office=value['office'], instance_id=value['instance_id'], host=value['host'],
                    key=value['key'], storage=value['storage'])
        args.update(changes)
        return create_app(**args)

    def request(self, value, path, body=None, *, token=None, status=200, method=None, **kwargs):
        response = value['client'].open('/api/v1' + path,
            method=method or ('POST' if body is not None else 'GET'), base_url='https://' + value['host'],
            json=body, headers={'Authorization': 'Bearer ' + token} if token else {}, **kwargs)
        self.assertEqual(response.status_code, status, repr(response.data[:250]))
        return response

    def login(self, value, email='owner@example.test', password='Synthetic-owner-password-123'):
        challenge = self.request(value, '/login', {'email': email, 'password': password}).json
        self.assertNotIn('token', challenge)
        return self.request(value, '/login/verify', {'challenge': challenge['challenge'],
            'code': totp(challenge['enrollment']['secret'], int(time.time() // 30))}).json['token']

    def start(self, value):
        self.bind(value)
        value['client'] = self.app(value).test_client()
        value['token'] = self.login(value)
        value['project'] = self.request(value, '/projects', {'name': value['host'] + ' project',
            'customer': value['host'] + ' customer'}, token=value['token'], status=201).json['id']
        value['report'] = self.request(value, '/projects/' + value['project'] + '/reports',
            {'kind': 'Servicebericht', 'description': 'Synthetischer Firmenbericht'},
            token=value['token'], status=201).json
        return value

    def test_two_companies_enforce_sessions_objects_lists_files_and_offline_scope(self):
        first, second = [self.start(value) for value in self.company]
        for current, foreign in ((first, second), (second, first)):
            self.request(current, '/projects', token=foreign['token'], status=401)
            projects = self.request(current, '/projects', token=current['token']).json
            self.assertEqual([row['id'] for row in projects], [current['project']])
            contacts = self.request(current, '/customers', token=current['token']).json
            self.assertEqual([row['name'] for row in contacts], [current['host'] + ' customer'])
            self.request(current, '/projects/' + foreign['project'] + '/reports', token=current['token'], status=404)
            self.request(current, '/reports/' + foreign['report']['id'] + '/pdf', token=current['token'], status=404)
            offline = self.request(foreign, '/offline/access', {}, token=foreign['token'], status=201).json['token']
            self.request(current, '/projects', token=offline, status=401)
            self.request(current, '/business/contacts', token=foreign['token'], status=401)
            report = current['report']
            self.request(current, '/reports/' + report['id'] + '/sign', {
                'content_hash': report['content_hash'], 'signer': 'Synthetischer Kunde',
                'strokes': [[[0.1, 0.2], [0.7, 0.8]]]}, token=current['token'])
            pdf = self.request(current, '/reports/' + report['id'] + '/pdf', token=current['token']).data
            self.assertTrue(pdf.startswith(b'%PDF'))
            # Equal object IDs in independent DBs must still have separate file destinations.
            current['storage'].backends['server'].put('a' * 32, 'b' * 32, pdf)
            self.assertEqual((current['root'] / ('a' * 32) / ('b' * 32 + '.pdf')).read_bytes(), pdf)
        self.assertNotEqual((first['root'] / ('a' * 32) / ('b' * 32 + '.pdf')).read_bytes(),
                            (second['root'] / ('a' * 32) / ('b' * 32 + '.pdf')).read_bytes())

    def test_same_email_mfa_challenges_and_restricted_role_stay_in_their_instance(self):
        first, second = [self.start(value) for value in self.company]
        for current in (first, second):
            self.request(current, '/users', {'email': 'pending@example.test',
                'password': 'Synthetic-pending-password-123', 'role': 'technician'},
                token=current['token'], status=201)
        challenge = self.request(first, '/login', {'email': 'pending@example.test',
            'password': 'Synthetic-pending-password-123'}).json
        verification = {'challenge': challenge['challenge'],
                        'code': totp(challenge['enrollment']['secret'], int(time.time() // 30))}
        # The same code/challenge succeeds at A, proving B's refusal is company
        # scoping rather than an intentionally invalid MFA-code fixture.
        self.request(second, '/login/verify', verification, status=401)
        pending_token = self.request(first, '/login/verify', verification).json['token']
        self.request(second, '/me', token=pending_token, status=401)
        technician = self.request(first, '/users', {'email': 'technician@example.test',
            'password': 'Synthetic-technician-password-123', 'role': 'technician'}, token=first['token'], status=201).json['id']
        self.request(first, '/assignments', {'project_id': first['project'], 'user_id': technician}, token=first['token'])
        token = self.login(first, 'technician@example.test', 'Synthetic-technician-password-123')
        self.request(first, '/projects/' + first['project'] + '/reports', token=token)
        self.request(first, '/customers', token=token, status=403)
        self.request(first, '/business/settings/permissions', token=token, status=403)
        self.request(second, '/projects', token=token, status=401)

    def test_bound_startup_rejects_wrong_host_database_key_root_and_missing_id(self):
        first, second = self.company
        self.bind(first)
        for changes in ({'host': second['host']}, {'instance_id': second['instance_id']},
                        {'key': second['key']}, {'office': second['office']},
                        {'storage': second['storage']}):
            with self.subTest(changes=list(changes)), self.assertRaises(InstanceConfigurationError):
                self.app(first, **changes)
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(InstanceConfigurationError):
            self.app(first, instance_id=None)
        with self.assertRaises(InstanceConfigurationError):
            bind(first['office'], second['instance_id'], second['host'], second['key'], first['storage'])
        response = self.app(first).test_client().get('/ready', base_url='https://' + second['host'])
        self.assertEqual(response.status_code, 400)

    def test_shared_storage_and_replaced_marker_fail_closed_including_after_startup(self):
        first, second = self.company
        self.bind(first)
        shared = Storage(second['office'], second['key'], second['host'],
                         config={'server': {'path': str(first['root'])}})
        with self.assertRaises(InstanceConfigurationError):
            bind(second['office'], second['instance_id'], second['host'], second['key'], shared)
        self.assertIsNone(identity(second['office']))
        self.bind(second)
        (first['root'] / MARKER).write_bytes((second['root'] / MARKER).read_bytes())
        with self.assertRaises(InstanceConfigurationError):
            self.app(first)
        with self.assertRaises(InstanceConfigurationError):
            first['storage'].backends['server'].put('a' * 32, 'b' * 32, b'%PDF-1.7\nsynthetic\n')

    def test_marker_symlink_and_insecure_permissions_are_rejected(self):
        first = self.company[0]
        self.bind(first)
        marker = first['root'] / MARKER
        original = marker.read_bytes()
        marker.chmod(0o644)
        with self.assertRaises(InstanceConfigurationError):
            self.app(first)
        marker.unlink()
        target = self.directory / 'copied-marker'
        target.write_bytes(original)
        target.chmod(0o600)
        marker.symlink_to(target)
        with self.assertRaises(InstanceConfigurationError):
            self.app(first)

    def test_explicit_binding_is_idempotent_and_cannot_change_existing_business_data(self):
        first = self.company[0]
        actor = first['office'].user(first['office'].login('owner@example.test', 'Synthetic-owner-password-123'))
        project = first['office'].add_project(actor, 'Bestandsprojekt', 'Bestandskunde')
        before = [tuple(row) for row in first['office'].db.execute('SELECT * FROM projects')]
        result = self.bind(first)
        saved = dict(identity(first['office']))
        marker = (first['root'] / MARKER).stat().st_mtime_ns
        self.assertEqual(self.bind(first), result)
        self.assertEqual(identity(first['office']), saved)
        self.assertEqual((first['root'] / MARKER).stat().st_mtime_ns, marker)
        self.assertEqual([tuple(row) for row in first['office'].db.execute('SELECT * FROM projects')], before)
        self.assertEqual(first['office'].project(actor, project)['name'], 'Bestandsprojekt')
        for statement in ('DELETE FROM business_instance_identity',
                          "UPDATE business_instance_identity SET public_host='other.example.test'",
                          '''INSERT OR REPLACE INTO business_instance_identity
                             SELECT singleton,instance_id,'other.example.test',storage_root,vault_fingerprint,created_at
                             FROM business_instance_identity'''):
            with self.assertRaises(sqlite3.IntegrityError), first['office'].db:
                first['office'].db.execute(statement)

    def test_unbound_legacy_app_does_not_bind_or_create_storage_and_configured_unbound_fails(self):
        first = self.company[0]
        with patch.dict(os.environ, {}, clear=True):
            app = self.app(first, instance_id=None)
        self.assertIsNone(app.extensions['smartplan_instance'])
        self.assertIsNone(identity(first['office']))
        self.assertFalse(first['root'].exists())
        with self.assertRaises(InstanceConfigurationError):
            self.app(first)
        self.assertFalse(first['root'].exists())

    def test_bound_external_storage_choice_is_rejected_before_provider_activity(self):
        first = self.start(self.company[0])
        self.request(first, '/storage/provider', {'provider': 'webdav'}, token=first['token'], status=409)
        self.request(first, '/storage/connect', {}, token=first['token'], status=409)
        self.request(first, '/reports/' + first['report']['id'] + '/onedrive', {}, token=first['token'], status=409)
        response = first['client'].post('/api/v1/storage/callback', base_url='https://' + first['host'],
            data={'state': 'synthetic-state', 'code': 'synthetic-code'}, content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(first['storage']._selected(), 'none')

    def test_unbound_legacy_instance_cannot_use_a_reserved_company_root(self):
        first, second = self.company
        self.bind(first)
        shared = Storage(second['office'], second['key'], second['host'],
                         config={'server': {'path': str(first['root'])}})
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(InstanceConfigurationError):
            self.app(second, instance_id=None, storage=shared)
        with self.assertRaises(InstanceConfigurationError):
            shared.backends['server'].put('a' * 32, 'b' * 32, b'%PDF-1.7\nsynthetic\n')
        self.assertFalse((first['root'] / ('a' * 32)).exists())

    def test_database_worker_rejects_missing_or_foreign_company_configuration(self):
        first, second = self.company
        self.bind(first)
        with patch.dict(os.environ, {}, clear=True):
            verify_worker(second['office'])  # Historical unbound worker remains compatible.
            with self.assertRaises(InstanceConfigurationError):
                verify_worker(first['office'])
        with patch.dict(os.environ, {'SMARTPLAN_INSTANCE_ID': first['instance_id'],
                                    'SMARTPLAN_PUBLIC_HOST': first['host']}, clear=True):
            verify_worker(first['office'])
            with self.assertRaises(InstanceConfigurationError):
                verify_worker(second['office'])
        with patch.dict(os.environ, {'SMARTPLAN_INSTANCE_ID': first['instance_id'],
                                    'SMARTPLAN_PUBLIC_HOST': second['host']}, clear=True):
            with self.assertRaises(InstanceConfigurationError):
                verify_worker(first['office'])


if __name__ == '__main__':
    unittest.main()
