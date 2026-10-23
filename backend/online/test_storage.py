"""Storage adapters and real disposable-PostgreSQL API contracts.

WebDAV responses are provided by an in-process HTTPS handler; these tests never
contact a cloud/NAS account. Database cases require the disposable test database.
"""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
from urllib.response import addinfourl
from email.message import Message

from cryptography.fernet import Fernet
import psycopg
from psycopg.conninfo import conninfo_to_dict

from core import Problem
from online.storage_backends import ServerStorage, WebDavStorage
from online.store import LOCK_ID, PostgresOffice, migrate
from online.web import create_app


PROJECT = 'a' * 32
REPORT = 'b' * 32
PDF = b'%PDF-1.7\nSynthetic document-storage fixture\n%%EOF\n'
DSN = os.environ.get('SMARTPLAN_TEST_DSN')
if DSN and conninfo_to_dict(DSN).get('dbname') != 'smartplan_check':
    raise RuntimeError('Tests dürfen ausschließlich die entbehrliche Datenbank smartplan_check verwenden.')


class ProblemAssertions:
    def problem(self, status, action):
        with self.assertRaises(Problem) as error:
            action()
        self.assertEqual(error.exception.status, status)
        return error.exception


class ServerStorageTests(ProblemAssertions, unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='smartplan-storage-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'documents'
        self.adapter = ServerStorage(self.root)

    def test_exact_private_atomic_file_and_idempotent_retry(self):
        self.assertTrue(self.adapter.configured())
        self.assertFalse(self.root.exists())
        result = self.adapter.put(PROJECT, REPORT, PDF)
        destination = self.root / PROJECT / (REPORT + '.pdf')
        self.assertEqual(result, {'uploaded': True, 'item_id': PROJECT + '/' + REPORT + '.pdf'})
        self.assertEqual(destination.read_bytes(), PDF)
        before = destination.stat().st_ino
        self.assertEqual(self.adapter.put(PROJECT, REPORT, PDF), result)
        self.assertEqual(destination.stat().st_ino, before)
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(destination.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
        self.assertEqual(list(destination.parent.iterdir()), [destination])

    def test_different_existing_document_is_never_replaced(self):
        self.adapter.put(PROJECT, REPORT, PDF)
        destination = self.root / PROJECT / (REPORT + '.pdf')
        self.problem(409, lambda: self.adapter.put(PROJECT, REPORT, PDF + b'different'))
        self.assertEqual(destination.read_bytes(), PDF)
        self.assertFalse(list(self.root.rglob('.upload-*')))

    def test_invalid_ids_and_non_pdf_never_create_a_destination(self):
        for project, report, data in ((PROJECT + '/..', REPORT, PDF),
                                      (PROJECT.upper(), REPORT, PDF),
                                      (PROJECT, '../document', PDF),
                                      (PROJECT, REPORT, b'not a PDF')):
            with self.subTest(project=project, report=report):
                self.problem(400, lambda: self.adapter.put(project, report, data))
        self.assertFalse(self.root.exists())
        self.assertFalse(ServerStorage('relative/documents').configured())
        self.assertFalse(ServerStorage('/').configured())
        self.assertFalse(ServerStorage('/tmp/../documents').configured())

    def test_root_project_and_destination_symlinks_cannot_escape(self):
        outside = Path(self.temporary.name) / 'outside'
        outside.mkdir(mode=0o700)
        link = Path(self.temporary.name) / 'linked-root'
        link.symlink_to(outside, target_is_directory=True)
        self.problem(502, lambda: ServerStorage(link).put(PROJECT, REPORT, PDF))
        self.assertFalse(list(outside.iterdir()))

        self.root.mkdir(mode=0o700)
        project = self.root / PROJECT
        project.symlink_to(outside, target_is_directory=True)
        self.problem(502, lambda: self.adapter.put(PROJECT, REPORT, PDF))
        self.assertFalse(list(outside.iterdir()))
        project.unlink()
        project.mkdir(mode=0o700)
        protected = outside / 'protected.pdf'
        protected.write_bytes(PDF + b'outside')
        protected.chmod(0o600)
        (project / (REPORT + '.pdf')).symlink_to(protected)
        self.problem(502, lambda: self.adapter.put(PROJECT, REPORT, PDF))
        self.assertEqual(protected.read_bytes(), PDF + b'outside')

    def test_nonprivate_directory_or_existing_file_is_rejected(self):
        self.root.mkdir(mode=0o755)
        self.root.chmod(0o755)
        self.problem(409, lambda: self.adapter.put(PROJECT, REPORT, PDF))
        self.root.chmod(0o700)
        self.adapter.put(PROJECT, REPORT, PDF)
        destination = self.root / PROJECT / (REPORT + '.pdf')
        destination.chmod(0o644)
        self.problem(409, lambda: self.adapter.put(PROJECT, REPORT, PDF))
        self.assertEqual(destination.read_bytes(), PDF)

    def test_interrupted_write_leaves_no_partial_document_or_temporary_file(self):
        with patch('online.storage_backends.os.write', side_effect=OSError('synthetic disk failure')):
            self.problem(502, lambda: self.adapter.put(PROJECT, REPORT, PDF))
        self.assertFalse((self.root / PROJECT / (REPORT + '.pdf')).exists())
        self.assertFalse(list(self.root.rglob('.upload-*')))
        self.assertTrue(self.adapter.put(PROJECT, REPORT, PDF)['uploaded'])


class FakeHttpsResponses(urllib.request.BaseHandler):
    # Intercept before proxy/HTTPS transport. The actual urllib response/error
    # and redirect-processing handlers still execute, but no network call does.
    handler_order = 0

    def __init__(self, statuses, *, location=None, body=b'private provider response', on_call=None):
        self.statuses = iter(statuses)
        self.location = location
        self.body = body
        self.on_call = on_call
        self.calls = []

    def https_open(self, request):
        self.calls.append(request)
        if self.on_call:
            self.on_call(request)
        code = next(self.statuses)
        headers = Message()
        if self.location:
            headers['Location'] = self.location
        response = addinfourl(io.BytesIO(self.body), headers, request.full_url, code)
        response.msg = 'Synthetic provider response'
        return response


class WebDavStorageTests(ProblemAssertions, unittest.TestCase):
    URL = 'https://cloud.example.test/remote.php/dav/files/owner'
    USERNAME = 'synthetic-owner'
    PASSWORD = 'synthetic-private-password'

    def adapter(self, statuses, **response_options):
        adapter = WebDavStorage(self.URL, self.USERNAME, self.PASSWORD)
        transport = FakeHttpsResponses(statuses, **response_options)
        adapter.opener.add_handler(transport)
        return adapter, transport

    def test_existing_collections_and_exact_pdf_use_only_configured_https_origin(self):
        adapter, transport = self.adapter([201, 405, 204])
        result = adapter.put(PROJECT, REPORT, PDF)
        self.assertEqual(result, {'uploaded': True, 'item_id': 'Smartplan/' + PROJECT + '/' + REPORT + '.pdf'})
        self.assertEqual([call.get_method() for call in transport.calls], ['MKCOL', 'MKCOL', 'PUT'])
        self.assertEqual([call.full_url for call in transport.calls], [
            self.URL + '/Smartplan', self.URL + '/Smartplan/' + PROJECT,
            self.URL + '/Smartplan/' + PROJECT + '/' + REPORT + '.pdf'])
        credentials = 'Basic ' + base64.b64encode((self.USERNAME + ':' + self.PASSWORD).encode()).decode()
        for call in transport.calls:
            self.assertEqual(call.get_header('Authorization'), credentials)
            self.assertLessEqual(call.timeout, 8)
        self.assertEqual(transport.calls[-1].data, PDF)
        self.assertEqual(transport.calls[-1].get_header('Content-type'), 'application/pdf')
        status = json.dumps(adapter.status())
        for private in (self.USERNAME, self.PASSWORD, self.URL):
            self.assertNotIn(private, status)

    def test_cross_origin_redirect_is_not_followed_and_credentials_do_not_leak(self):
        adapter, transport = self.adapter([302], location='https://untrusted.example.test/stolen',
                                          body=self.PASSWORD.encode())
        error = self.problem(502, lambda: adapter.put(PROJECT, REPORT, PDF))
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(transport.calls[0].full_url, self.URL + '/Smartplan')
        self.assertNotIn(self.PASSWORD, error.message)
        self.assertNotIn('untrusted.example.test', error.message)

    def test_failed_collection_or_put_does_not_report_success(self):
        for statuses, expected in (([503], 502), ([201, 201, 500], 502), ([401], 409)):
            with self.subTest(statuses=statuses):
                adapter, transport = self.adapter(statuses, body=self.PASSWORD.encode())
                error = self.problem(expected, lambda: adapter.put(PROJECT, REPORT, PDF))
                self.assertNotIn(self.PASSWORD, error.message)
                self.assertLessEqual(len(transport.calls), 3)

    def test_invalid_or_metadata_targets_are_not_configured(self):
        for target in ('http://cloud.example.test/dav', '//cloud.example.test/dav',
                       'https://user:password@cloud.example.test/dav',
                       'https://cloud.example.test/dav?token=secret',
                       'https://cloud.example.test/dav#secret',
                       'https://cloud.example.test/dav/../outside',
                       'https://localhost/dav', 'https://[::1]/dav',
                       'https://169.254.169.254/metadata', 'https://metadata.google.internal/dav'):
            with self.subTest(target=target):
                adapter = WebDavStorage(target, self.USERNAME, self.PASSWORD)
                self.assertFalse(adapter.configured())
                self.problem(409, lambda: adapter.put(PROJECT, REPORT, PDF))
        self.assertTrue(WebDavStorage('https://192.168.50.20:5006/dav', self.USERNAME, self.PASSWORD).configured())

    def test_report_input_cannot_choose_another_url_or_path(self):
        adapter, transport = self.adapter([])
        self.problem(400, lambda: adapter.put('../outside', REPORT, PDF))
        self.problem(400, lambda: adapter.request('https://other.example.test/dav/file', 'PUT', PDF))
        self.assertEqual(transport.calls, [])

    def test_total_operation_deadline_bounds_remaining_requests_and_rejects_late_success(self):
        clock = [0.0]
        durations = iter((7, 7, 5))

        def advance_clock(request):
            clock[0] += next(durations)

        adapter, transport = self.adapter([201, 201, 204], on_call=advance_clock)
        with patch('online.storage_backends.time.monotonic', side_effect=lambda: clock[0]):
            self.problem(504, lambda: adapter.put(PROJECT, REPORT, PDF))
            self.assertEqual([call.timeout for call in transport.calls], [8, 8, 4])
            self.assertEqual(len(transport.calls), 3)
            # A completed/failed upload must not leak its expired budget into
            # another operation running in the same worker context.
            following, following_transport = self.adapter([201])
            self.assertEqual(following.request(self.URL + '/Smartplan', 'MKCOL'), 201)
            self.assertEqual(following_transport.calls[0].timeout, 8)


@unittest.skipUnless(DSN, 'SMARTPLAN_TEST_DSN points to a disposable PostgreSQL database')
class StorageOnlineTests(unittest.TestCase):
    HOST = 'office.example.test'

    def setUp(self):
        migrate(DSN)
        with psycopg.connect(DSN) as connection:
            connection.execute('TRUNCATE users,customers,projects,assignments,reports,audit,secrets,'
                               'sessions,mfa,auth_challenges,login_limits RESTART IDENTITY CASCADE')
        self.office = PostgresOffice(DSN)
        self.addCleanup(self.office.db.close)
        self.owner_id = self.office.add_user('owner@example.test', 'Owner-password-123', 'owner')
        self.token = self.office.login('owner@example.test', 'Owner-password-123')
        self.owner = self.office.user(self.token)
        self.key = Fernet.generate_key()
        temporary = tempfile.TemporaryDirectory(prefix='smartplan-storage-api-')
        self.addCleanup(temporary.cleanup)
        self.destination = Path(temporary.name) / 'documents'
        self.config = {'server': {'path': str(self.destination)},
                       'webdav': {'url': 'https://cloud.example.test/private-dav',
                                  'username': 'private-webdav-user', 'password': 'private-webdav-password'}}
        self.app = create_app(office=self.office, key=self.key, host=self.HOST, storage_config=self.config)
        self.client = self.app.test_client()
        self.storage = self.app.extensions['smartplan_storage']
        self.project = self.office.add_project(self.owner, 'Ablage-Test', 'Fiktiver Kunde')

    def request(self, path, body=None, token=None, status=200, *, client=None):
        response = (client or self.client).open(
            '/api/v1' + path, method='POST' if body is not None else 'GET',
            base_url='https://' + self.HOST, json=body,
            headers={'Authorization': 'Bearer ' + token} if token else {})
        self.assertEqual(response.status_code, status, repr(response.data[:500]))
        return response

    def user(self, role):
        email = role + '@example.test'
        identifier = self.office.add_user(email, 'Synthetic-user-password-123', role)
        return identifier, self.office.login(email, 'Synthetic-user-password-123')

    def report(self, *, signed=True):
        report = self.office.draft(self.owner, self.project, 'Servicebericht', 'Fiktiver Speichertest')
        if signed:
            self.office.sign(self.owner, report['id'], report['content_hash'], 'Testkunde',
                             [[[0.1, 0.2], [0.7, 0.8]]])
        return report

    def receipts(self, report_id):
        return self.office.db.execute('SELECT name,value FROM secrets WHERE name LIKE ?',
                                      ('storage.receipt.' + report_id + '.%',)).fetchall()

    def test_only_owner_selects_provider_and_selection_causes_no_transfer(self):
        self.request('/storage/status', status=401)
        for role in ('manager', 'technician', 'accountant'):
            _, token = self.user(role)
            self.request('/storage/provider', {'provider': 'server'}, token, status=403)
            self.request('/storage/status', token=token, status=403)
        self.assertEqual(self.request('/storage/status', token=self.token).json['selected_provider'], 'none')
        result = self.request('/storage/provider', {'provider': 'server'}, self.token).json
        self.assertEqual(result['selected_provider'], 'server')
        self.assertTrue(result['configured'])
        self.assertEqual({item['id'] for item in result['providers']}, {'server', 'onedrive', 'webdav'})
        self.assertFalse(self.destination.exists())
        self.request('/storage/provider', {'provider': 'unknown'}, self.token, status=400)
        self.request('/storage/provider', {'provider': 'server', 'path': '/outside'}, self.token, status=400)

    def test_status_never_returns_server_paths_or_provider_credentials(self):
        result = self.request('/storage/status', token=self.token)
        for private in (str(self.destination), *self.config['webdav'].values()):
            self.assertNotIn(private.encode(), result.data)

    def test_exact_signed_pdf_and_encrypted_receipt_survive_idempotent_upload(self):
        self.request('/storage/provider', {'provider': 'server'}, self.token)
        report = self.report()
        original = self.office.pdf(self.owner, report['id'])
        route = '/reports/' + report['id'] + '/storage'
        response = self.request(route, {}, self.token).json
        self.assertEqual(response, {'uploaded': True, 'provider': 'server'})
        destination = self.destination / self.project / (report['id'] + '.pdf')
        self.assertEqual(destination.read_bytes(), original)
        inode = destination.stat().st_ino
        receipt, = self.receipts(report['id'])
        saved = json.loads(Fernet(self.key).decrypt(receipt['value'].encode()))
        self.assertEqual(saved['provider'], 'server')
        self.assertEqual(saved['pdf_hash'], hashlib.sha256(original).hexdigest())
        self.assertEqual(saved['item_id'], self.project + '/' + report['id'] + '.pdf')
        self.assertNotIn(saved['pdf_hash'], receipt['value'])
        self.request(route, {}, self.token)
        self.assertEqual(destination.stat().st_ino, inode)
        self.assertEqual(len(self.receipts(report['id'])), 1)
        self.assertEqual(self.office.pdf(self.owner, report['id']), original)

    def test_missing_selection_configuration_and_unsigned_reports_fail_clearly(self):
        report = self.report()
        route = '/reports/' + report['id'] + '/storage'
        self.request(route, {}, self.token, status=409)
        unconfigured = create_app(office=self.office, key=self.key, host=self.HOST,
                                  storage_config={}).test_client()
        self.request('/storage/provider', {'provider': 'server'}, self.token, client=unconfigured)
        self.request(route, {}, self.token, status=409, client=unconfigured)
        draft = self.report(signed=False)
        self.request('/reports/' + draft['id'] + '/storage', {}, self.token, status=409)
        self.request(route, {'url': 'https://other.example.test/dav'}, self.token, status=400)
        self.assertEqual(self.receipts(report['id']), [])
        self.assertFalse(self.destination.exists())

    def test_manager_needs_assignment_and_other_roles_cannot_upload(self):
        self.request('/storage/provider', {'provider': 'server'}, self.token)
        report = self.report()
        route = '/reports/' + report['id'] + '/storage'
        for role in ('technician', 'accountant'):
            identifier, token = self.user(role)
            self.office.assign(self.owner, self.project, identifier)
            self.request(route, {}, token, status=403)
        manager_id, manager = self.user('manager')
        self.request(route, {}, manager, status=404)
        self.office.assign(self.owner, self.project, manager_id)
        self.request(route, {}, manager)
        self.office.assign(self.owner, self.project, manager_id, remove=True)
        self.request(route, {}, manager, status=404)

    def test_failed_provider_does_not_record_success_or_change_original_pdf(self):
        self.request('/storage/provider', {'provider': 'server'}, self.token)
        report = self.report()
        original = self.office.pdf(self.owner, report['id'])
        with patch.object(self.storage.backends['server'], 'put',
                          side_effect=Problem(502, 'Synthetischer Speicherausfall')):
            self.request('/reports/' + report['id'] + '/storage', {}, self.token, status=502)
        self.assertEqual(self.receipts(report['id']), [])
        self.assertEqual(self.office.pdf(self.owner, report['id']), original)
        self.assertFalse(self.destination.exists())
        self.request('/reports/' + report['id'] + '/storage', {}, self.token)

    def test_transfer_blocks_provider_switch_but_not_unrelated_database_requests(self):
        self.request('/storage/provider', {'provider': 'server'}, self.token)
        report = self.report()
        other = PostgresOffice(DSN)
        self.addCleanup(other.db.close)
        other_client = create_app(office=other, key=self.key, host=self.HOST,
                                   storage_config=self.config).test_client()
        actual_put = self.storage.backends['server'].put

        def transfer(project_id, report_id, pdf):
            with psycopg.connect(DSN) as connection:
                available = connection.execute('SELECT pg_try_advisory_xact_lock(%s)', (LOCK_ID,)).fetchone()[0]
            self.assertTrue(available, 'Storage I/O holds the global Office transaction lock')
            self.request('/storage/provider', {'provider': 'none'}, self.token,
                         status=409, client=other_client)
            self.request('/projects', token=self.token, client=other_client)
            return actual_put(project_id, report_id, pdf)

        with patch.object(self.storage.backends['server'], 'put', side_effect=transfer):
            self.request('/reports/' + report['id'] + '/storage', {}, self.token)
        self.assertEqual(self.request('/storage/status', token=self.token).json['selected_provider'], 'server')
        self.request('/storage/provider', {'provider': 'none'}, self.token, client=other_client)
        self.assertEqual(self.request('/storage/status', token=self.token).json['selected_provider'], 'none')
        self.assertTrue((self.destination / self.project / (report['id'] + '.pdf')).exists())
        self.assertEqual(len(self.receipts(report['id'])), 1)


if __name__ == '__main__':
    unittest.main()
