"""Real PostgreSQL contracts, MFA/revocation, and concurrent signing."""
import base64
from concurrent.futures import ThreadPoolExecutor
import os
import tempfile
import time
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet
import psycopg

from core import Problem
from online.auth import Authentication, totp
from online.store import migrate, PostgresOffice
from online.web import create_app
from online.backup import backup
from online.restore import restore
from psycopg.conninfo import make_conninfo, conninfo_to_dict
import test_office

DSN = os.environ.get('SMARTPLAN_TEST_DSN')
if DSN and conninfo_to_dict(DSN).get('dbname') != 'smartplan_check':
    raise RuntimeError('Tests dürfen ausschließlich die entbehrliche Datenbank smartplan_check verwenden.')


def reset():
    # This database is explicitly disposable (guard above). Recreate the entire
    # fixture, including ledgers without a user FK; partial CASCADE resets leave
    # counters/receipts that correctly fail the next startup integrity check.
    with psycopg.connect(DSN) as connection:
        connection.execute('DROP SCHEMA public CASCADE')
        connection.execute('CREATE SCHEMA public')
    migrate(DSN)


@unittest.skipUnless(DSN, 'SMARTPLAN_TEST_DSN points to a disposable PostgreSQL database')
class PostgresContracts(test_office.OfficeTests):
    def setUp(self):
        reset()
        with patch.object(test_office, 'Office', side_effect=lambda path: PostgresOffice(DSN)):
            super().setUp()


class TotpStandardTest(unittest.TestCase):
    def test_rfc6238_sha1_vectors(self):
        secret = base64.b32encode(b'12345678901234567890').decode()
        for timestamp, expected in ((59, '94287082'), (1111111109, '07081804'),
                                    (1111111111, '14050471'), (1234567890, '89005924'),
                                    (2000000000, '69279037'), (20000000000, '65353130')):
            self.assertEqual(totp(secret, timestamp // 30, digits=8), expected)


@unittest.skipUnless(DSN, 'SMARTPLAN_TEST_DSN points to a disposable PostgreSQL database')
class OnlineApiTests(unittest.TestCase):
    def setUp(self):
        reset()
        self.office = PostgresOffice(DSN)
        self.owner_id = self.office.add_user('owner@example.test', 'Owner-password-123', 'owner')
        self.key = Fernet.generate_key()
        self.auth = Authentication(self.office, self.key)
        self.app = create_app(office=self.office, key=self.key, host='office.example.test')
        self.client = self.app.test_client()
        self.secrets = {}

    def tearDown(self):
        self.office.db.close()

    def request(self, path, body=None, token=None, status=200, method=None):
        response = self.client.open('/api/v1' + path, method=method or ('POST' if body is not None else 'GET'),
                                    base_url='https://office.example.test', json=body,
                                    headers={'Authorization': 'Bearer ' + token} if token else {})
        self.assertEqual(response.status_code, status, repr(response.data[:500]))
        return response

    def login(self, email='owner@example.test', password='Owner-password-123'):
        pending = self.request('/login', {'email': email, 'password': password}).json
        if 'enrollment' in pending:
            self.secrets[email] = pending['enrollment']['secret']
        self.assertNotIn('token', pending)
        return self.request('/login/verify', {'challenge': pending['challenge'],
                            'code': totp(self.secrets[email], int(time.time() // 30))}).json

    def test_enrollment_replay_recovery_logout_and_encrypted_storage(self):
        result = self.login()
        token, codes = result['token'], result['recovery_codes']
        self.assertEqual(len(codes), 10)
        row = self.office.db.execute('SELECT * FROM mfa').fetchone()
        self.assertNotIn(self.secrets['owner@example.test'], row['secret'])
        self.assertNotIn(codes[0], row['recovery'])
        self.assertEqual(self.request('/me', token=token).json['role'], 'owner')
        pending = self.request('/login', {'email': 'owner@example.test', 'password': 'Owner-password-123'}).json
        self.assertNotIn('enrollment', pending)
        self.request('/login/verify', {'challenge': pending['challenge'],
                                     'code': totp(self.secrets['owner@example.test'], int(time.time() // 30))}, status=401)
        recovered = self.request('/login/verify', {'challenge': pending['challenge'], 'code': codes[0]}).json
        self.request('/login/verify', {'challenge': pending['challenge'], 'code': codes[1]}, status=401)
        pending = self.request('/login', {'email': 'owner@example.test', 'password': 'Owner-password-123'}).json
        self.request('/login/verify', {'challenge': pending['challenge'], 'code': codes[0]}, status=401)
        self.request('/logout', {}, token=recovered['token'])
        self.request('/me', token=recovered['token'], status=401)

    def test_wrong_password_limit_survives_new_process_state(self):
        for _ in range(5):
            self.request('/login', {'email': 'owner@example.test', 'password': 'wrong'}, status=401)
        second = PostgresOffice(DSN)
        try:
            with self.assertRaises(Problem) as error:
                Authentication(second, self.key).begin('owner@example.test', 'Owner-password-123', 'different-ip')
            self.assertEqual(error.exception.status, 429)
        finally:
            second.db.close()

    def test_password_change_invalidates_pending_challenge(self):
        pending = self.auth.begin('owner@example.test', 'Owner-password-123', 'test')
        with self.office.db:
            self.office.db.execute('UPDATE users SET password=? WHERE id=?', ('changed', self.owner_id))
        self.request('/login/verify', {'challenge': pending['challenge'],
                                     'code': totp(pending['enrollment']['secret'], int(time.time() // 30))}, status=401)

    def test_expired_and_repeated_wrong_codes_do_not_grant_sessions(self):
        pending = self.auth.begin('owner@example.test', 'Owner-password-123', 'test')
        with self.office.db:
            self.office.db.execute('UPDATE auth_challenges SET expiry=0')
        self.request('/login/verify', {'challenge': pending['challenge'],
                                     'code': totp(pending['enrollment']['secret'], int(time.time() // 30))}, status=401)
        pending = self.auth.begin('owner@example.test', 'Owner-password-123', 'test')
        for _ in range(5):
            self.request('/login/verify', {'challenge': pending['challenge'], 'code': 'bad-code'}, status=401)
        self.request('/login/verify', {'challenge': pending['challenge'],
                                     'code': totp(pending['enrollment']['secret'], int(time.time() // 30))}, status=401)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0], 0)

    def test_full_two_device_workflow_access_revocation_and_restart(self):
        owner = self.login()['token']
        tech_id = self.request('/users', {'email': 'tech@example.test', 'password': 'Technician-password-123',
                                        'role': 'technician'}, owner, status=201).json['id']
        tech = self.login('tech@example.test', 'Technician-password-123')['token']
        customer = self.request('/customers', {'name': 'Musterkunde', 'notes': 'Nur Geschäftsführung'}, owner, status=201).json
        project = self.request('/projects', {'name': 'Online-Test', 'customer_id': customer['id']}, owner, status=201).json['id']
        self.request('/assignments', {'project_id': project, 'user_id': tech_id}, owner)
        self.request('/customers', token=tech, status=403)
        report = self.request('/projects/' + project + '/reports',
                              {'kind': 'Servicebericht', 'description': 'Fiktiver Test'}, tech, status=201).json
        self.request('/reports/' + report['id'] + '/sign', {'content_hash': report['content_hash'],
                     'signer': 'Testkunde', 'strokes': [[[0.1, 0.2], [0.7, 0.8]]]}, tech)
        pdf = self.request('/reports/' + report['id'] + '/pdf', token=owner).data
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.office.db.close()
        self.office = PostgresOffice(DSN)
        self.client = create_app(office=self.office, key=self.key, host='office.example.test').test_client()
        self.assertEqual(pdf, self.request('/reports/' + report['id'] + '/pdf', token=owner).data)
        self.request('/assignments', {'project_id': project, 'user_id': tech_id, 'remove': True}, owner)
        self.request('/reports/' + report['id'] + '/pdf', token=tech, status=404)
        self.request('/users/' + tech_id, {'active': False}, owner)
        self.request('/me', token=tech, status=401)

    def test_request_limits_methods_https_and_host(self):
        self.request('/projects', status=401)
        self.request('/projects', status=405, method='DELETE')
        self.request('/unknown', status=404)
        for url in ('http://office.example.test', 'https://foreign.example.test'):
            self.assertEqual(self.client.get('/health', base_url=url).status_code, 400)
        self.assertEqual(self.client.post('/api/v1/login', base_url='https://office.example.test',
                                        data='[', content_type='application/json').status_code, 400)
        self.assertEqual(self.client.post('/api/v1/login', base_url='https://office.example.test',
                                        data='x' * 1_000_001, content_type='application/json').status_code, 413)
        self.assertEqual(self.client.get('/health', base_url='https://office.example.test').json['database'], 'ok')

    def test_connection_loss_recovers_on_next_request(self):
        with psycopg.connect(DSN) as admin:
            admin.execute('SELECT pg_terminate_backend(%s)', (self.office.db.connection.info.backend_pid,))
        self.assertEqual(self.client.get('/ready', base_url='https://office.example.test').status_code, 503)
        self.assertEqual(self.client.get('/ready', base_url='https://office.example.test').status_code, 200)

    def test_parallel_signing_commits_only_one_signature(self):
        owner = self.office.user(self.office.login('owner@example.test', 'Owner-password-123'))
        project = self.office.add_project(owner, 'Parallel', 'Testkunde')
        report = self.office.draft(owner, project, 'Servicebericht', 'Test')
        def sign(name):
            other = PostgresOffice(DSN)
            try:
                other.sign(owner, report['id'], report['content_hash'], name, [[[0.1, 0.2], [0.7, 0.8]]])
                return 200
            except Problem as error:
                return error.status
            finally:
                other.db.close()
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertEqual(sorted(executor.map(sign, ['Test A', 'Test B'])), [200, 409])

    def test_dump_restore_preserves_pdf_and_revokes_sessions(self):
        token = self.login()['token']
        device = self.request('/offline/access', {}, token, 201).json['token']
        owner = self.office.user(token)
        project = self.office.add_project(owner, 'Restore', 'Testkunde')
        report = self.office.draft(owner, project, 'Servicebericht', 'Test')
        self.office.sign(owner, report['id'], report['content_hash'], 'Testkunde', [[[0.1, 0.2], [0.7, 0.8]]])
        pdf = self.office.pdf(owner, report['id'])
        target_name = 'smartplan_restore_check'
        with psycopg.connect(DSN, autocommit=True) as admin:
            admin.execute('CREATE DATABASE ' + target_name)
        target_dsn = make_conninfo(DSN, dbname=target_name)
        try:
            with tempfile.TemporaryDirectory() as directory:
                saved = backup(DSN, directory)
                self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
                with self.assertRaisesRegex(ValueError, 'aktive Datenbank'):
                    restore(saved, DSN, DSN)
                restore(saved, DSN, target_dsn)
                target = PostgresOffice(target_dsn)
                try:
                    self.assertEqual(target.pdf(owner, report['id']), pdf)
                    self.assertEqual(target.db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0], 0)
                    self.assertEqual(target.db.execute('SELECT COUNT(*) FROM mfa').fetchone()[0], 1)
                    self.assertEqual(target.db.execute('SELECT COUNT(*) FROM plan_sessions').fetchone()[0], 0)
                    import plan_access
                    with self.assertRaises(Problem):
                        plan_access.user(target, device)
                    with self.assertRaises(Problem):
                        target.user(token)
                finally:
                    target.db.close()
                with self.assertRaisesRegex(ValueError, 'leer'):
                    restore(saved, DSN, target_dsn)
                saved.write_bytes(saved.read_bytes() + b'bad')
                with self.assertRaisesRegex(ValueError, 'Prüfsumme'):
                    restore(saved, DSN, target_dsn)
        finally:
            with psycopg.connect(DSN, autocommit=True) as admin:
                admin.execute('DROP DATABASE ' + target_name)
