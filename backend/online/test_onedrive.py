"""OneDrive HTTP contracts against disposable PostgreSQL, never Microsoft.

Authentication/MFA has its own contract suite. These fixtures issue ordinary
Office sessions so each test can focus on the persisted OAuth/storage behavior.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from threading import Event
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, unquote, urlencode, urlsplit

from cryptography.fernet import Fernet
import psycopg
from psycopg.conninfo import conninfo_to_dict

from core import Problem
from online import onedrive_connector as onedrive_module
from online.onedrive_connector import OnlineOneDrive
from online.store import LOCK_ID, PostgresOffice, migrate
from online.web import create_app


DSN = os.environ.get('SMARTPLAN_TEST_DSN')
if DSN and conninfo_to_dict(DSN).get('dbname') != 'smartplan_check':
    raise RuntimeError('Tests dürfen ausschließlich die entbehrliche Datenbank smartplan_check verwenden.')


@unittest.skipUnless(DSN, 'SMARTPLAN_TEST_DSN points to a disposable PostgreSQL database')
class OneDriveOnlineTests(unittest.TestCase):
    HOST = 'office.example.test'
    CLIENT_ID = '11111111-2222-4333-8444-555555555555'
    CLIENT_SECRET = 'synthetic-microsoft-client-secret'
    ACCESS = 'synthetic-microsoft-access-token'
    REFRESH = 'synthetic-microsoft-refresh-token'

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
        self.calls = []
        self.token_reply = self.tokens()
        self.put_error = None
        self.put_hook = None
        self.project_folders = {}
        self.folder_create_conflict = False
        self.drive, self.client = self.worker(self.office)
        self.request('/storage/provider', {'provider': 'onedrive'}, self.token)

    def tokens(self, **changes):
        value = dict(access_token=self.ACCESS, refresh_token=self.REFRESH,
                     expires_in=3600, token_type='Bearer')
        value.update(changes)
        return value

    def worker(self, office):
        drive = OnlineOneDrive(office, self.key, self.HOST,
                               client_id=self.CLIENT_ID, client_secret=self.CLIENT_SECRET)
        mocked = patch.object(drive, 'request', side_effect=self.provider)
        mocked.start()
        self.addCleanup(mocked.stop)
        app = create_app(office=office, key=self.key, host=self.HOST,
                         onedrive=drive, storage_config={})
        return drive, app.test_client()

    def request(self, path, body=None, token=None, status=200, *, client=None):
        response = (client or self.client).open(
            '/api/v1' + path, method='POST' if body is not None else 'GET',
            base_url='https://' + self.HOST, json=body,
            headers={'Authorization': 'Bearer ' + token} if token else {})
        self.assertEqual(response.status_code, status, repr(response.data[:500]))
        return response

    def provider(self, url, method='GET', data=None, headers=None):
        # Slow provider operations must not block unrelated Office transactions.
        with psycopg.connect(DSN) as connection:
            available = connection.execute('SELECT pg_try_advisory_xact_lock(%s)', (LOCK_ID,)).fetchone()[0]
        self.assertTrue(available, 'Microsoft network operation holds the global Office transaction lock')
        call = {'url': url, 'method': method, 'data': data, 'headers': headers or {}}
        self.calls.append(call)
        if url == 'https://login.microsoftonline.com/consumers/oauth2/v2.0/token':
            self.assertEqual(method, 'POST')
            return self.token_reply
        self.assertTrue(url.startswith('https://graph.microsoft.com/v1.0/'), url)
        self.assertEqual(call['headers'].get('Authorization'), 'Bearer ' + self.ACCESS)
        if url.endswith('/me/drive/special/approot'):
            self.assertEqual(method, 'GET')
            return {'id': 'app-folder-id', 'folder': {}}
        path = unquote(urlsplit(url).path)
        project_prefix = '/v1.0/me/drive/items/app-folder-id:/'
        if method == 'GET' and path.startswith(project_prefix):
            name = path[len(project_prefix):]
            if name not in self.project_folders:
                raise onedrive_module._NotFound()
            return self.project_folders[name]
        if method == 'POST' and path == '/v1.0/me/drive/items/app-folder-id/children':
            folder = json.loads(data)
            self.assertEqual(folder['folder'], {})
            self.assertEqual(folder['@microsoft.graph.conflictBehavior'], 'fail')
            self.assertNotIn(folder['name'], self.project_folders)
            metadata = {'id': 'project-folder-' + str(len(self.project_folders) + 1),
                        'name': folder['name'], 'folder': {}}
            self.project_folders[folder['name']] = metadata
            if self.folder_create_conflict:
                self.folder_create_conflict = False
                # A concurrent external creator has won the Graph race.
                raise onedrive_module._Conflict()
            return metadata
        self.assertEqual(method, 'PUT')
        self.assertIn('/me/drive/items/project-folder-', url)
        if self.put_hook:
            self.put_hook()
        if self.put_error:
            raise self.put_error
        return {'id': 'stored-drive-item', 'file': {'mimeType': 'application/pdf'}, 'size': len(data)}

    def begin(self):
        response = self.request('/storage/connect', {}, self.token)
        self.assertIsInstance(response.json.get('url'), str)
        parsed = urlsplit(response.json['url'])
        return parsed, {name: values[0] for name, values in parse_qs(parsed.query).items()}

    def callback(self, state, *, code='synthetic-authorization-code', error=None, status=200, client=None):
        form = {'state': state}
        if code is not None:
            form['code'] = code
        if error is not None:
            form['error'] = error
        response = (client or self.client).post(
            '/api/v1/storage/callback', base_url='https://' + self.HOST,
            data=urlencode(form), content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code, status, repr(response.data[:500]))
        return response

    def connect(self):
        _, pending = self.begin()
        self.callback(pending['state'])
        return pending

    def create_user(self, role):
        email = role + '@example.test'
        user_id = self.office.add_user(email, 'Another-password-123', role)
        return user_id, self.office.login(email, 'Another-password-123')

    def report(self, signed=True, project=None):
        if project is None:
            project = self.office.add_project(self.owner, 'Fiktiver OneDrive-Test', 'Testkunde')
        report = self.office.draft(self.owner, project, 'Servicebericht', 'Nur fiktive Testdaten')
        if signed:
            self.office.sign(self.owner, report['id'], report['content_hash'], 'Testkunde',
                             [[[0.1, 0.2], [0.7, 0.8]]])
        return project, report['id']

    def saved_tokens(self):
        return self.office.db.execute("SELECT value FROM secrets WHERE name='onedrive'").fetchone()

    def upload(self, report_id, *, token=None, status=200, client=None):
        return self.request('/reports/' + report_id + '/onedrive', {},
                            self.token if token is None else token, status, client=client)

    def test_configuration_and_storage_controls_are_owner_only(self):
        initial = self.request('/storage/status', token=self.token).json
        self.assertTrue(initial['configured'])
        self.assertFalse(initial['connected'])
        self.assertEqual(initial['account_type'], 'personal')
        self.request('/storage/status', status=401)
        self.request('/storage/connect', {}, status=401)
        for role in ('technician', 'manager'):
            _, token = self.create_user(role)
            with self.subTest(role=role):
                self.request('/storage/status', token=token, status=403)
                self.request('/storage/connect', {}, token, status=403)
                self.request('/storage/disconnect', {}, token, status=403)
                self.request('/storage/provider', {'provider': 'onedrive'}, token, status=403)
        self.assertEqual(self.calls, [])

    def test_oauth_pkce_survives_another_worker_and_rejects_replay(self):
        parsed, pending = self.begin()
        self.assertEqual(parsed.scheme, 'https')
        self.assertEqual(parsed.netloc, 'login.microsoftonline.com')
        self.assertEqual(parsed.path, '/consumers/oauth2/v2.0/authorize')
        self.assertEqual(pending['redirect_uri'], 'https://' + self.HOST + '/api/v1/storage/callback')
        self.assertEqual(set(pending['scope'].split()), {'offline_access', 'Files.ReadWrite.AppFolder'})
        self.assertEqual(pending['code_challenge_method'], 'S256')
        self.assertEqual(pending['response_mode'], 'form_post')
        self.assertEqual(pending['client_id'], self.CLIENT_ID)
        self.assertNotIn(self.CLIENT_SECRET, parsed.query)
        rows = self.office.db.execute('SELECT name,value FROM secrets WHERE name LIKE ?',
                                      ('onedrive.oauth.%',)).fetchall()
        self.assertEqual(len(rows), 1)
        for value in (rows[0]['name'], rows[0]['value']):
            self.assertNotIn(pending['state'], value)
            self.assertNotIn(self.token, value)

        other = PostgresOffice(DSN)
        self.addCleanup(other.db.close)
        _, client = self.worker(other)
        response = self.callback(pending['state'], client=client)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(response.headers['Referrer-Policy'], 'no-referrer')
        token_call = self.calls[0]
        form = {key: values[0] for key, values in parse_qs(token_call['data'].decode()).items()}
        challenge = base64.urlsafe_b64encode(hashlib.sha256(form['code_verifier'].encode()).digest()).rstrip(b'=').decode()
        self.assertEqual(challenge, pending['code_challenge'])
        self.assertEqual(form['grant_type'], 'authorization_code')
        self.assertEqual(form['client_secret'], self.CLIENT_SECRET)
        self.assertEqual(form['redirect_uri'], pending['redirect_uri'])
        self.assertTrue(self.request('/storage/status', token=self.token).json['connected'])
        ciphertext = self.saved_tokens()['value']
        for private in (self.ACCESS, self.REFRESH, self.CLIENT_SECRET, form['code_verifier']):
            self.assertNotIn(private, ciphertext)
            self.assertNotIn(private, response.get_data(as_text=True))
            self.assertNotIn(private, self.request('/storage/status', token=self.token).get_data(as_text=True))
        before = len(self.calls)
        self.callback(pending['state'], status=400)
        self.assertEqual(len(self.calls), before)

    def test_oauth_callback_requires_a_form_post_and_unambiguous_fields(self):
        _, pending = self.begin()
        callback_path = '/api/v1/storage/callback'
        form = {'state': pending['state'], 'code': 'synthetic-authorization-code'}
        base_url = 'https://' + self.HOST
        get = self.client.get(callback_path + '?' + urlencode(form), base_url=base_url)
        self.assertIn(get.status_code, (400, 404, 405))
        json_post = self.client.post(callback_path, json=form, base_url=base_url)
        self.assertIn(json_post.status_code, (400, 415))
        duplicate = self.client.post(
            callback_path, base_url=base_url,
            data=urlencode([('state', pending['state']), ('state', pending['state']), ('code', form['code'])]),
            content_type='application/x-www-form-urlencoded')
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(self.calls, [])
        self.callback(pending['state'])

    def test_expired_callback_is_consumed_without_contacting_microsoft(self):
        _, pending = self.begin()
        with patch('online.onedrive_connector.time.time', return_value=time.time() + 601):
            self.callback(pending['state'], status=400)
        self.callback(pending['state'], status=400)
        self.assertEqual(self.calls, [])
        self.assertIsNone(self.saved_tokens())

    def test_logout_revokes_an_unfinished_oauth_flow(self):
        _, pending = self.begin()
        self.request('/logout', {}, self.token)
        self.callback(pending['state'], status=403)
        self.callback(pending['state'], status=400)
        self.assertEqual(self.calls, [])
        self.assertIsNone(self.saved_tokens())

    def test_disabling_the_initiator_revokes_an_unfinished_oauth_flow(self):
        _, pending = self.begin()
        with self.office.db:
            self.office.db.execute('UPDATE users SET active=0 WHERE id=?', (self.owner_id,))
        self.callback(pending['state'], status=403)
        self.callback(pending['state'], status=400)
        self.assertEqual(self.calls, [])
        self.assertIsNone(self.saved_tokens())

    def test_tampered_state_cannot_consume_the_original_flow(self):
        _, pending = self.begin()
        state = pending['state']
        altered = ('a' if state[0] != 'a' else 'b') + state[1:]
        self.callback(altered, status=400)
        self.assertEqual(self.calls, [])
        self.callback(state)
        self.assertTrue(self.request('/storage/status', token=self.token).json['connected'])

    def test_provider_denial_consumes_state_without_exchanging_a_code(self):
        _, pending = self.begin()
        self.callback(pending['state'], code=None, error='access_denied', status=400)
        self.callback(pending['state'], status=400)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.request('/storage/status', token=self.token).json['connected'])

    def test_signed_upload_uses_app_folder_and_the_immutable_stored_pdf(self):
        self.connect()
        project, report_id = self.report()
        pdf = self.request('/reports/' + report_id + '/pdf', token=self.token).data
        self.assertTrue(pdf.startswith(b'%PDF'))
        result = self.upload(report_id).json
        self.assertTrue(result['uploaded'])
        self.assertEqual(result['provider'], 'onedrive')
        put = next(call for call in self.calls if call['method'] == 'PUT')
        self.assertEqual(put['data'], pdf)
        self.assertEqual(put['headers']['Content-Type'], 'application/pdf')
        self.assertEqual(unquote(urlsplit(put['url']).path),
                         '/v1.0/me/drive/items/project-folder-1:/' + project + '_' + report_id + '.pdf:/content')
        self.assertEqual(list(self.project_folders), ['Projekt - Fiktiver OneDrive-Test - ' + project])
        creates = [call for call in self.calls if call['method'] == 'POST' and '/children' in call['url']]
        self.assertEqual(len(creates), 1)
        stored = self.office.db.execute('SELECT onedrive_id FROM reports WHERE id=?', (report_id,)).fetchone()
        self.assertEqual(stored['onedrive_id'], 'stored-drive-item')
        self.assertEqual(self.request('/reports/' + report_id + '/pdf', token=self.token).data, pdf)

    def test_upload_requires_a_signature_and_an_authorized_manager_or_owner(self):
        self.connect()
        _, draft_id = self.report(signed=False)
        project, signed_id = self.report()
        manager_id, manager = self.create_user('manager')
        technician_id, technician = self.create_user('technician')
        self.office.assign(self.owner, project, technician_id)
        before = len(self.calls)
        self.upload(draft_id, status=409)
        self.upload(signed_id, token=technician, status=403)
        self.upload(signed_id, token=manager, status=404)
        self.assertEqual(len(self.calls), before)
        self.office.assign(self.owner, project, manager_id)
        self.upload(signed_id, token=manager)

    def test_failed_upload_is_retryable_without_changing_the_pdf_or_filename(self):
        self.connect()
        project, report_id = self.report()
        original = self.office.pdf(self.owner, report_id)
        self.put_error = Problem(502, 'Simulierter Microsoft-Ausfall')
        self.upload(report_id, status=502)
        stored = self.office.db.execute('SELECT onedrive_id FROM reports WHERE id=?', (report_id,)).fetchone()
        self.assertIsNone(stored['onedrive_id'])
        with self.office.db:
            self.office.db.execute('UPDATE projects SET name=? WHERE id=?', ('Nach Ausfall umbenannt', project))
        self.put_error = None
        self.upload(report_id)
        self.upload(report_id)
        puts = [call for call in self.calls if call['method'] == 'PUT']
        self.assertGreaterEqual(len(puts), 2)
        self.assertEqual(len({call['url'] for call in puts}), 1)
        self.assertTrue(all(call['data'] == original for call in puts))
        self.assertEqual(self.office.pdf(self.owner, report_id), original)
        self.assertEqual(list(self.project_folders), ['Projekt - Fiktiver OneDrive-Test - ' + project])
        self.assertEqual(sum(call['method'] == 'POST' and '/children' in call['url'] for call in self.calls), 1)

    def test_all_project_reports_keep_the_original_folder_after_a_project_rename(self):
        self.connect()
        project, first = self.report()
        self.upload(first)
        with self.office.db:
            self.office.db.execute('UPDATE projects SET name=? WHERE id=?', ('Neuer Projektname', project))
        _, second = self.report(project=project)
        self.upload(second)
        self.assertEqual(list(self.project_folders), ['Projekt - Fiktiver OneDrive-Test - ' + project])
        puts = [call for call in self.calls if call['method'] == 'PUT']
        self.assertEqual(len(puts), 2)
        self.assertTrue(all('/me/drive/items/project-folder-1:/' in call['url'] for call in puts))
        self.assertNotEqual(puts[0]['url'], puts[1]['url'])
        self.assertEqual(sum(call['method'] == 'POST' and '/children' in call['url'] for call in self.calls), 1)

    def test_project_folder_creation_conflict_reuses_the_existing_folder(self):
        self.connect()
        _, report_id = self.report()
        self.folder_create_conflict = True
        self.upload(report_id)
        self.assertEqual(len(self.project_folders), 1)
        self.assertEqual(sum(call['method'] == 'POST' and '/children' in call['url'] for call in self.calls), 1)
        puts = [call for call in self.calls if call['method'] == 'PUT']
        self.assertEqual(len(puts), 1)
        self.assertIn('/me/drive/items/project-folder-1:/', puts[0]['url'])

    def test_invalid_grant_during_refresh_requires_reconnection(self):
        self.connect()
        _, report_id = self.report()
        self.token_reply = {'error': 'invalid_grant'}
        before = len(self.calls)
        with patch('online.onedrive_connector.time.time', return_value=time.time() + 3700):
            self.upload(report_id, status=409)
        self.assertIsNone(self.saved_tokens())
        self.assertFalse(self.request('/storage/status', token=self.token).json['connected'])
        self.assertEqual(len(self.calls), before + 1)
        form = parse_qs(self.calls[-1]['data'].decode())
        self.assertEqual(form['grant_type'], ['refresh_token'])
        self.assertEqual(form['refresh_token'], [self.REFRESH])

    def test_malformed_oauth_replies_do_not_store_credentials_or_allow_replay(self):
        for value in ([], {'access_token': 'incomplete'}, self.tokens(expires_in='3600'),
                      self.tokens(token_type='MAC'), self.tokens(expires_in=True)):
            with self.subTest(reply=value):
                self.token_reply = value
                _, pending = self.begin()
                self.callback(pending['state'], status=502)
                before = len(self.calls)
                self.callback(pending['state'], status=400)
                self.assertEqual(len(self.calls), before)
                self.assertIsNone(self.saved_tokens())
        self.assertTrue(all(call['method'] == 'POST' for call in self.calls))

    def test_malformed_refresh_preserves_the_previous_connection_for_retry(self):
        self.connect()
        _, report_id = self.report()
        encrypted = self.saved_tokens()['value']
        self.token_reply = {'access_token': 'incomplete'}
        with patch('online.onedrive_connector.time.time', return_value=time.time() + 3700):
            self.upload(report_id, status=502)
        self.assertEqual(self.saved_tokens()['value'], encrypted)
        self.token_reply = self.tokens()
        with patch('online.onedrive_connector.time.time', return_value=time.time() + 3700):
            self.upload(report_id)
        self.assertTrue(self.request('/storage/status', token=self.token).json['connected'])

    def test_disconnect_clears_saved_credentials_and_unfinished_flows(self):
        self.connect()
        _, pending = self.begin()
        self.request('/storage/disconnect', {}, self.token)
        self.assertFalse(self.request('/storage/status', token=self.token).json['connected'])
        self.assertIsNone(self.saved_tokens())
        before = len(self.calls)
        self.callback(pending['state'], status=400)
        self.assertEqual(len(self.calls), before)
        _, report_id = self.report()
        self.upload(report_id, status=409)
        self.assertEqual(len(self.calls), before)

    def test_external_requests_share_a_bounded_operation_budget_and_can_be_retried(self):
        self.connect()
        _, report_id = self.report()
        clock = [100.0]
        opened = []

        class Response:
            def __init__(self, chunks):
                self.chunks = list(chunks)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def read1(self, limit):
                if not self.chunks:
                    return b''
                chunk, elapsed = self.chunks.pop(0)
                clock[0] += elapsed
                return chunk

            read = read1

        class Opener:
            def open(self, request, timeout):
                opened.append((request.full_url, timeout))
                if len(opened) == 1:
                    # No individual read takes eight seconds, but together they
                    # spend almost all of the operation's total allowance.
                    return Response([(b'{"id":', 6), (b'"app-folder-id"', 6), (b'}', 5)])
                if len(opened) == 2:
                    return Response([(b'{"id":"project-folder-1","folder":{}}', 1.5)])
                raise AssertionError('expired operation made another external request')

        with patch.object(self.drive, 'request',
                          side_effect=lambda *args, **kwargs: OnlineOneDrive.request(self.drive, *args, **kwargs)), \
                patch('online.onedrive_connector.urllib.request.build_opener', return_value=Opener()), \
                patch('online.onedrive_connector.time.monotonic', side_effect=lambda: clock[0]):
            self.upload(report_id, status=504)
        self.assertEqual(len(opened), 2)
        self.assertEqual(opened[0][1], 8)
        self.assertGreater(opened[1][1], 0)
        self.assertLessEqual(opened[1][1], 1)
        stored = self.office.db.execute('SELECT onedrive_id FROM reports WHERE id=?', (report_id,)).fetchone()
        self.assertIsNone(stored['onedrive_id'])
        # A timed-out request must release its worker locks and deadline state.
        self.upload(report_id)

    def test_second_worker_cannot_upload_or_disconnect_during_a_running_upload(self):
        self.connect()
        _, report_id = self.report()
        other = PostgresOffice(DSN)
        self.addCleanup(other.db.close)
        _, client = self.worker(other)
        entered, release = Event(), Event()

        def hold_upload():
            entered.set()
            self.assertTrue(release.wait(10), 'test did not release the simulated upload')

        self.put_hook = hold_upload
        with ThreadPoolExecutor(max_workers=1) as executor:
            uploading = executor.submit(self.upload, report_id)
            try:
                self.assertTrue(entered.wait(10), 'upload never reached the simulated provider')
                self.upload(report_id, status=409, client=client)
                self.request('/storage/disconnect', {}, self.token, status=409, client=client)
                self.assertTrue(self.request('/storage/status', token=self.token, client=client).json['connected'])
            finally:
                release.set()
            self.assertEqual(uploading.result(timeout=10).status_code, 200)
        self.assertEqual(sum(call['method'] == 'PUT' for call in self.calls), 1)


if __name__ == '__main__':
    unittest.main()
