"""Authenticated integration workflows with synthetic provider IO only.

SQLite exercises the real Flask/session/domain path. The optional PostgreSQL
cases use only the explicitly disposable loopback smartplan_check database.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit
import uuid

from cryptography.fernet import Fernet
from psycopg.conninfo import conninfo_to_dict

from core import Office, Problem, digest
from external_integrations import validate_integrity
from online.integration_http import IntegrationAuthenticationRequired
from online.integrations_service import OnlineIntegrations
from online.store import PostgresOffice
from online.web import create_app
import test_online as pg_fixture
from test_workspace_api import WorkspaceHttpFlow


if pg_fixture.DSN and conninfo_to_dict(pg_fixture.DSN).get('host') not in ('127.0.0.1', 'localhost'):
    raise RuntimeError('Integration tests require a disposable loopback PostgreSQL database.')


def request_id():
    return uuid.uuid4().hex


def financial_payload():
    return {'contact': {'id': 'contact-17', 'name': 'Synthetic contact'},
            'offers': [{'id': 'offer-17', 'kind': 'offer', 'number': 'SYN-17',
                        'title': 'Synthetic offer', 'status': '100', 'status_label': 'Entwurf',
                        'date': '2030-12-12', 'total_gross': '1234.50', 'currency': 'EUR', 'url': None}],
            'invoices': [{'id': 'invoice-17', 'kind': 'invoice', 'number': 'SYN-18',
                          'title': 'Synthetic invoice', 'status': '100', 'status_label': 'Entwurf',
                          'date': '2030-12-13', 'total_gross': '7.00', 'currency': 'EUR', 'url': None}]}


def calendar_payload():
    return {'calendar': {'id': 'calendar@example.test', 'name': 'Synthetic calendar',
                         'time_zone': 'Europe/Berlin'},
            'events': [{'id': 'event-17', 'title': 'Synthetic all-day survey', 'description': '',
                        'start': '2030-12-12', 'end': '2030-12-13', 'all_day': True,
                        'time_zone': 'Europe/Berlin', 'location': 'Synthetic site', 'status': 'confirmed',
                        'url': 'https://calendar.google.com/calendar/event?eid=synthetic'},
                       {'id': 'private-event-18', 'title': 'UNSELECTED PRIVATE CALENDAR EVENT',
                        'description': '', 'start': '2030-12-14', 'end': '2030-12-15', 'all_day': True,
                        'time_zone': 'Europe/Berlin', 'location': '', 'status': 'confirmed', 'url': None}]}


def onedrive_payload():
    folder = {'id': 'synthetic-folder', 'drive_id': 'synthetic-drive', 'name': 'Synthetic project documents',
              'path': '/Synthetic project documents',
              'url': 'https://synthetic.sharepoint.com/sites/site/Shared%20Documents/Project'}
    return {'complete': True, 'folder': folder,
            'files': [{'id': 'synthetic-plan', 'drive_id': folder['drive_id'], 'parent_id': folder['id'],
                       'name': 'Synthetic plan.pdf', 'path': folder['path'] + '/Synthetic plan.pdf',
                       'rev': '"synthetic-etag,1"', 'size': 123, 'media_type': 'application/pdf',
                       'url': folder['url'] + '/Synthetic%20plan.pdf'}]}


class SyntheticSevdesk:
    """Provider boundary, deliberately independent from auth and persistence."""

    def __init__(self):
        self.calls = []
        self.hook = None
        self.error = None
        self.extra_document = False

    def record(self, operation, *args):
        self.calls.append((operation, deepcopy(args)))
        if self.hook:
            self.hook(operation)
        if self.error:
            raise self.error

    def validate(self, token):
        self.record('validate', token)
        if token == 'synthetic-invalid-provider-token':
            raise IntegrationAuthenticationRequired()
        return {'id': 'synthetic-sevdesk-account', 'label': 'Synthetic company'}

    def contacts(self, token, query=''):
        self.record('contacts', token, query)
        return [financial_payload()['contact']]

    def contact_documents(self, token, contact):
        self.record('contact_documents', token, contact)
        return financial_payload()

    def snapshot(self, token, selection):
        self.record('snapshot', token, selection)
        result = financial_payload()
        for key, ids in (('offers', selection['offer_ids']), ('invoices', selection['invoice_ids'])):
            result[key] = [row for row in result[key] if row['id'] in ids]
        if self.extra_document:
            result['offers'].append({**financial_payload()['offers'][0], 'id': 'foreign-offer'})
        return result


class SyntheticGoogle:
    def __init__(self):
        self.calls = []
        self.hook = None
        self.bad_snapshot = False

    def record(self, operation, *args):
        self.calls.append((operation, deepcopy(args)))
        if self.hook:
            self.hook(operation)

    def authorization_url(self, config, state, challenge, redirect):
        self.record('authorization_url', state, challenge, redirect)
        return 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode(
            {'state': state, 'code_challenge': challenge, 'redirect_uri': redirect})

    def exchange(self, config, code, verifier, redirect):
        self.record('exchange', code, verifier, redirect)
        return {'access_token': 'synthetic-google-access', 'refresh_token': 'synthetic-google-refresh',
                'expires_in': 3600}

    def identity(self, access):
        self.record('identity', access)
        return {'id': 'synthetic-google-account', 'label': 'Synthetic Google account'}

    def refresh(self, config, refresh):
        self.record('refresh', refresh)
        return {'access_token': 'synthetic-refreshed-google-access',
                'refresh_token': 'synthetic-google-refresh', 'expires_in': 3600}

    def calendars(self, access):
        self.record('calendars', access)
        return [calendar_payload()['calendar']]

    def events(self, access, calendar):
        self.record('events', access, calendar)
        return calendar_payload()['events']

    def snapshot(self, access, selection):
        self.record('snapshot', access, selection)
        result = calendar_payload()
        if not self.bad_snapshot:
            result['events'] = [e for e in result['events'] if e['id'] in selection['event_ids']]
        return result


class IntegrationHttpFixture(WorkspaceHttpFlow):
    """Helpers only, so PostgreSQL does not inherit and duplicate SQLite tests."""

    def prepare(self):
        self.secrets = {}
        self.sevdesk, self.google = SyntheticSevdesk(), SyntheticGoogle()
        self.now = [time.time()]
        self.service = OnlineIntegrations(self.office, self.key, 'office.example.test',
            providers={'sevdesk': self.sevdesk, 'google_calendar': self.google}, clock=lambda: self.now[0])
        self.app = create_app(office=self.office, key=self.key, host='office.example.test', integrations=self.service)
        self.client = self.app.test_client()
        self.token = self.mfa_login()
        self.owner = self.office.user(self.token)
        self.project = self.call('POST', '/projects', {
            'name': 'Synthetic integration project', 'customer': 'Synthetic customer'}, status=201).json['id']
        self.project_base = '/projects/' + self.project + '/integrations'

    def connect_sevdesk(self, **changes):
        return self.call('POST', '/integrations/sevdesk/connect', {
            'request_id': request_id(), 'api_token': 'synthetic-valid-provider-token', **changes}).json

    def link_sevdesk(self, *, generation=None, **changes):
        if generation is None:
            generation = self.connect_sevdesk()['generation']
        return self.call('POST', self.project_base + '/sevdesk/link', {
            'generation': generation, 'revision': 0, 'request_id': request_id(),
            'contact_id': 'contact-17', 'offer_ids': ['offer-17'], 'invoice_ids': [], **changes}).json

    def provider_status(self, provider, *, project=False, token='owner'):
        value = self.call('GET', self.project_base if project else '/integrations', token=token).json
        return next(row for row in value['providers'] if row['id'] == provider)

    def configure_google(self):
        return self.call('POST', '/integrations/google_calendar/configure', {
            'request_id': request_id(), 'client_id': 'synthetic-client.apps.googleusercontent.com',
            'client_secret': 'synthetic-oauth-client-secret'}).json

    def begin_google(self):
        url = self.call('POST', '/integrations/google_calendar/connect', {}).json['url']
        return parse_qs(urlsplit(url).query)['state'][0]

    def callback(self, state, *, status=200, **changes):
        response = self.client.get('/api/v1/integrations/google_calendar/callback',
            base_url='https://office.example.test', query_string={
                'state': state, 'code': 'synthetic-oauth-authorization-code', **changes})
        self.assertEqual(response.status_code, status, response.data[:500])
        self.assertNotIn(b'synthetic-oauth-authorization-code', response.data)
        self.assertNotIn(b'synthetic-oauth-client-secret', response.data)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        return response

    def connect_google(self):
        self.configure_google()
        self.callback(self.begin_google())
        return self.provider_status('google_calendar')

    def bot_connect(self):
        return self.call('POST', '/integrations/bot/connect', {'request_id': request_id()}).json

    def bot_jobs(self, token):
        return self.call('GET', '/intake/integrations/jobs', token=token).json['jobs']

    def deliver(self, token, job, payload, *, source_id=None, status=201):
        body = {'source_id': source_id or 'synthetic-source-' + job['id'], 'complete': True, 'payload': payload}
        return self.call('POST', '/intake/integrations/jobs/' + job['id'] + '/result',
                         body, token=token, status=status).json

    def google_bot_catalog(self):
        return {'complete': True, 'identity': {'id': 'synthetic-google-account', 'label': 'Synthetic Google account'},
                'calendars': [calendar_payload()['calendar']]}

    def confirm_google_bot_catalog(self, token):
        job = next(j for j in self.bot_jobs(token) if j['provider'] == 'google_calendar' and j['kind'] == 'catalog')
        receipt = self.deliver(token, job, self.google_bot_catalog())
        return job, receipt, self.provider_status('google_calendar')['generation']

    def google_bot_resource(self, token, generation):
        body = {'generation': generation, 'calendar_id': 'calendar@example.test'}
        pending = self.call('POST', self.project_base + '/google_calendar/preview', body).json
        self.assertTrue(pending['pending'])
        self.assertNotIn('events', pending)
        self.assertEqual(self.call('POST', self.project_base + '/google_calendar/preview', body).json, pending)
        job = next(j for j in self.bot_jobs(token) if j['id'] == pending['job_id'])
        self.deliver(token, job, dict(calendar_payload(), complete=True))
        return self.call('POST', self.project_base + '/google_calendar/preview', body).json

    def link_google_bot(self, token):
        _, _, generation = self.confirm_google_bot_catalog(token)
        self.google_bot_resource(token, generation)
        selected = self.call('POST', self.project_base + '/google_calendar/link', {
            'generation': generation, 'revision': 0, 'request_id': request_id(),
            'calendar_id': 'calendar@example.test', 'event_ids': ['event-17']}).json
        return selected


class IntegrationsApiTests(IntegrationHttpFixture, unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='smartplan-integration-api-')
        self.addCleanup(self.temporary.cleanup)
        self.database = Path(self.temporary.name) / 'office.db'
        self.office = Office(self.database)
        self.addCleanup(self.office.db.close)
        self.key = Fernet.generate_key()
        self.owner_id = self.office.add_user('owner@example.test', 'Owner-password-123', 'owner')
        self.office.db.executescript('''
            CREATE TABLE mfa(user_id TEXT PRIMARY KEY REFERENCES users(id),secret TEXT NOT NULL,
                last_step BIGINT NOT NULL DEFAULT -1,recovery TEXT NOT NULL);
            CREATE TABLE auth_challenges(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),
                credential TEXT NOT NULL,secret TEXT NOT NULL,expiry DOUBLE PRECISION NOT NULL,
                failures INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE login_limits(key TEXT PRIMARY KEY,failures INTEGER NOT NULL,
                reset_at DOUBLE PRECISION NOT NULL);
        ''')
        self.prepare()

    def test_real_session_scopes_finance_visibility_and_no_fabricated_records(self):
        initial = self.call('GET', self.project_base).json
        self.assertTrue(initial['financial_visible'])
        self.assertTrue(all(p['data'] is None and p['binding'] is None for p in initial['providers']))
        self.assertEqual(self.sevdesk.calls, [])
        self.connect_sevdesk()
        self.link_sevdesk(generation=1)
        for role in ('technician', 'manager', 'accountant'):
            with self.subTest(role=role):
                _, actor = self.add_actor(role)
                status = self.call('GET', self.project_base, token=actor).json
                self.assertEqual(status['financial_visible'], role == 'accountant')
                self.assertEqual('sevdesk' in [p['id'] for p in status['providers']], role == 'accountant')
                self.call('GET', '/integrations', token=actor, status=403)
                self.call('POST', self.project_base + '/sevdesk/link', {
                    'generation': 1, 'revision': 1, 'request_id': request_id(),
                    'contact_id': 'contact-17', 'offer_ids': [], 'invoice_ids': []}, token=actor, status=403)
        _, outsider = self.add_actor('technician', assign=False)
        self.call('GET', self.project_base, token=outsider, status=404)
        self.call('GET', self.project_base, token=None, status=401)
        offline = self.call('POST', '/offline/access', {}, status=201).json['token']
        inbound = self.issue_gmail()['token']
        for token, expected in ((offline, 403), (inbound, 401)):
            self.call('GET', '/integrations', token=token, status=expected)
            self.call('GET', self.project_base, token=token, status=expected)

    def test_sevdesk_connect_retry_is_encrypted_and_bad_replacement_preserves_account(self):
        body = {'request_id': request_id(), 'api_token': 'synthetic-valid-provider-token'}
        connected = self.call('POST', '/integrations/sevdesk/connect', body).json
        self.assertEqual(connected, self.call('POST', '/integrations/sevdesk/connect', body).json)
        self.assertEqual(connected['generation'], 1)
        self.assertTrue(connected['connected'])
        self.call('POST', '/integrations/sevdesk/connect', {
            'request_id': request_id(), 'api_token': 'synthetic-invalid-provider-token'}, status=409)
        self.assertEqual(self.provider_status('sevdesk'), connected)
        raw = str(dict(self.office.db.execute('SELECT * FROM external_connections WHERE provider=?', ('sevdesk',)).fetchone()))
        self.assertNotIn(body['api_token'], raw)
        self.assertNotIn(body['api_token'], json.dumps(self.call('GET', '/integrations').json))
        self.call('POST', '/integrations/sevdesk/connect', {**body, 'api_token': 'other-synthetic-token'}, status=409)
        self.assertEqual(self.provider_status('sevdesk')['generation'], 1)

    def test_explicit_financial_selection_retries_and_stale_account_do_not_rebind(self):
        generation = self.connect_sevdesk()['generation']
        self.call('POST', '/integrations/sevdesk/catalog', {'query': 'Synthetic'})
        preview = self.call('POST', self.project_base + '/sevdesk/preview', {
            'generation': generation, 'contact_id': 'contact-17'}).json
        self.assertEqual(preview['invoices'][0]['id'], 'invoice-17')
        body = {'generation': generation, 'revision': 0, 'request_id': request_id(),
                'contact_id': 'contact-17', 'offer_ids': ['offer-17'], 'invoice_ids': []}
        linked = self.call('POST', self.project_base + '/sevdesk/link', body).json
        self.assertEqual(linked, self.call('POST', self.project_base + '/sevdesk/link', body).json)
        self.assertEqual(linked['binding'], {k: body[k] for k in ('contact_id', 'offer_ids', 'invoice_ids')})
        self.assertEqual(linked['data']['invoices'], [])
        self.assertEqual(linked['data']['offers'][0]['total_gross'], '1234.50')
        self.call('POST', '/integrations/sevdesk/disconnect', {'request_id': request_id()})
        current = self.connect_sevdesk()
        before = len(self.sevdesk.calls)
        self.call('POST', self.project_base + '/sevdesk/link', {**body, 'request_id': request_id()}, status=409)
        self.call('POST', self.project_base + '/sevdesk/preview', {
            'generation': generation, 'contact_id': 'contact-17'}, status=409)
        self.assertEqual(len(self.sevdesk.calls), before)
        state = self.provider_status('sevdesk', project=True)
        self.assertEqual(state['generation'], current['generation'])
        self.assertIsNone(state['data'])
        self.assertIsNone(state['binding'])

    def test_unselected_provider_document_is_rejected_without_committing_link(self):
        generation = self.connect_sevdesk()['generation']
        self.sevdesk.extra_document = True
        self.call('POST', self.project_base + '/sevdesk/link', {
            'generation': generation, 'revision': 0, 'request_id': request_id(),
            'contact_id': 'contact-17', 'offer_ids': ['offer-17'], 'invoice_ids': []}, status=409)
        self.assertIsNone(self.provider_status('sevdesk', project=True)['binding'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM external_snapshots').fetchone()[0], 0)

    def test_successful_sevdesk_link_retry_survives_lost_ack_and_provider_outage_without_io(self):
        generation = self.connect_sevdesk()['generation']
        body = {'generation': generation, 'revision': 0, 'request_id': request_id(),
                'contact_id': 'contact-17', 'offer_ids': ['offer-17'], 'invoice_ids': []}
        confirmed = self.call('POST', self.project_base + '/sevdesk/link', body).json
        calls = deepcopy(self.sevdesk.calls)
        self.sevdesk.error = Problem(503, 'Der Anbieter ist vorübergehend nicht erreichbar.')
        retried = self.call('POST', self.project_base + '/sevdesk/link', body).json
        self.assertEqual(retried, confirmed)
        self.assertEqual(self.sevdesk.calls, calls, 'A confirmed link receipt must be retried without provider IO')
        self.call('POST', self.project_base + '/sevdesk/link', {**body, 'invoice_ids': ['invoice-17']}, status=409)
        self.call('POST', self.project_base + '/sevdesk/link', {**body, 'generation': generation - 1}, status=409)
        self.call('POST', self.project_base + '/sevdesk/link', {**body, 'request_id': request_id()}, status=409)
        self.assertEqual(self.sevdesk.calls, calls)
        self.assertEqual(self.provider_status('sevdesk', project=True), confirmed)

    def test_provider_io_releases_office_lock_and_late_logout_drops_result(self):
        generation = self.connect_sevdesk()['generation']
        acquired = []
        def during_io(operation):
            if operation != 'snapshot':
                return
            def independent_request():
                self.assertTrue(self.office.lock.acquire(timeout=2), 'Provider IO retained the Office lock')
                try:
                    with self.office.db:
                        acquired.append(self.office.user(self.token)['id'])
                        self.office.db.execute('DELETE FROM sessions WHERE token=?', (digest(self.token),))
                finally:
                    self.office.lock.release()
            with ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(independent_request).result(timeout=3)
        self.sevdesk.hook = during_io
        self.call('POST', self.project_base + '/sevdesk/link', {
            'generation': generation, 'revision': 0, 'request_id': request_id(),
            'contact_id': 'contact-17', 'offer_ids': ['offer-17'], 'invoice_ids': []}, status=401)
        self.assertEqual(acquired, [self.owner_id])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM external_project_links').fetchone()[0], 0)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM external_snapshots').fetchone()[0], 0)

    def test_owner_role_changed_during_provider_io_drops_result(self):
        generation = self.connect_sevdesk()['generation']
        def during_io(operation):
            if operation == 'snapshot':
                with self.office.lock, self.office.db:
                    self.office.db.execute('UPDATE users SET role=? WHERE id=?', ('technician', self.owner_id))
        self.sevdesk.hook = during_io
        self.call('POST', self.project_base + '/sevdesk/link', {
            'generation': generation, 'revision': 0, 'request_id': request_id(),
            'contact_id': 'contact-17', 'offer_ids': [], 'invoice_ids': []}, status=403)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM external_snapshots').fetchone()[0], 0)

    def test_google_oauth_is_single_use_private_and_commits_only_after_fresh_session(self):
        self.configure_google()
        state = self.begin_google()
        self.callback(state)
        self.assertTrue(self.provider_status('google_calendar')['connected'])
        self.callback(state, status=400)
        self.assertEqual(len([c for c in self.google.calls if c[0] == 'exchange']), 1)
        state = self.begin_google()
        self.callback(state, error='provider-error-contains-secret', status=400)
        self.callback(state, status=400)
        stored = str([dict(row) for row in self.office.db.execute('SELECT * FROM external_connections')])
        for secret in ('synthetic-google-access', 'synthetic-google-refresh', 'synthetic-oauth-client-secret'):
            self.assertNotIn(secret, stored)
            self.assertNotIn(secret, json.dumps(self.call('GET', '/integrations').json))
        state = self.begin_google()
        previous_generation = self.provider_status('google_calendar')['generation']
        def logout(operation):
            if operation == 'exchange':
                with self.office.lock, self.office.db:
                    self.office.db.execute('DELETE FROM sessions WHERE token=?', (digest(self.token),))
        self.google.hook = logout
        self.callback(state, status=403)
        self.assertEqual(self.office.db.execute("SELECT generation FROM external_connections WHERE provider='google_calendar'").fetchone()[0], previous_generation)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM external_oauth_states').fetchone()[0], 0)

    def test_google_project_displays_only_selected_events_and_retains_exclusive_all_day_end(self):
        generation = self.connect_google()['generation']
        body = {'generation': generation, 'revision': 0, 'request_id': request_id(),
                'calendar_id': 'calendar@example.test', 'event_ids': ['event-17']}
        selected = self.call('POST', self.project_base + '/google_calendar/link', body).json
        self.assertEqual([e['id'] for e in selected['data']['events']], ['event-17'])
        self.assertEqual(selected['data']['events'][0]['end'], '2030-12-13')
        self.assertNotIn('UNSELECTED PRIVATE', json.dumps(self.call('GET', self.project_base).json))
        self.google.bad_snapshot = True
        self.call('POST', self.project_base + '/google_calendar/sync', {
            'generation': generation, 'revision': selected['revision']}, status=409)
        current = self.provider_status('google_calendar', project=True)
        self.assertEqual([e['id'] for e in current['data']['events']], ['event-17'])

    def test_stale_google_generation_is_rejected_before_even_token_refresh_io(self):
        generation = self.connect_google()['generation']
        selection = {'generation': generation, 'revision': 0, 'request_id': request_id(),
                     'calendar_id': 'calendar@example.test', 'event_ids': ['event-17']}
        linked = self.call('POST', self.project_base + '/google_calendar/link', selection).json
        self.now[0] += 3601
        before = len(self.google.calls)
        actions = {
            'preview': {'generation': generation - 1, 'calendar_id': 'calendar@example.test'},
            'link': {**selection, 'generation': generation - 1, 'revision': linked['revision'], 'request_id': request_id()},
            'sync': {'generation': generation - 1, 'revision': linked['revision']},
        }
        for action, body in actions.items():
            with self.subTest(action=action):
                self.call('POST', self.project_base + '/google_calendar/' + action, body, status=409)
                self.assertEqual(len(self.google.calls), before,
                                 'A stale project screen must not refresh credentials for a different account epoch')

    def test_provider_auth_revocation_invalidates_only_current_account_and_safe_metadata(self):
        linked = self.link_sevdesk()
        self.sevdesk.error = IntegrationAuthenticationRequired()
        response = self.call('POST', self.project_base + '/sevdesk/sync', {
            'generation': linked['generation'], 'revision': linked['revision']}, status=409)
        self.assertNotIn(b'synthetic-valid-provider-token', response.data)
        state = self.provider_status('sevdesk', project=True)
        self.assertFalse(state['connected'])
        self.assertIsNone(state['data'])
        self.assertIsNone(state['binding'])
        self.assertGreater(state['generation'], linked['generation'])
        self.assertTrue(validate_integrity(self.office))

    def test_transient_provider_failure_retains_confirmed_data_and_original_sync_timestamp(self):
        linked = self.link_sevdesk()
        self.now[0] += 180
        self.sevdesk.error = Problem(504, 'Der Anbieter hat nicht rechtzeitig geantwortet.')
        failed = self.call('POST', self.project_base + '/sevdesk/sync', {
            'generation': linked['generation'], 'revision': linked['revision']}, status=504)
        self.assertNotIn(b'synthetic-valid-provider-token', failed.data)
        saved = self.provider_status('sevdesk', project=True)
        self.assertEqual(saved['data'], linked['data'])
        self.assertEqual(saved['synced_at'], linked['synced_at'])
        self.assertTrue(saved['connected'])
        self.assertIsNotNone(saved['error'])

    def test_project_assignment_revoked_during_google_io_cannot_publish_late_snapshot(self):
        generation = self.connect_google()['generation']
        body = {'generation': generation, 'revision': 0, 'request_id': request_id(),
                'calendar_id': 'calendar@example.test', 'event_ids': ['event-17']}
        linked = self.call('POST', self.project_base + '/google_calendar/link', body).json
        technician_id, technician = self.add_actor('technician')
        def unassign(operation):
            if operation == 'snapshot':
                with self.office.lock, self.office.db:
                    self.office.assign(self.owner, self.project, technician_id, True)
        self.google.hook = unassign
        self.call('POST', self.project_base + '/google_calendar/sync', {
            'generation': generation, 'revision': linked['revision']}, token=technician, status=404)
        self.assertEqual(self.provider_status('google_calendar', project=True)['data'], linked['data'])
        self.call('GET', self.project_base, token=technician, status=404)

    def test_bot_key_is_private_idempotent_expiring_and_does_not_replace_gmail(self):
        mail_key = self.issue_gmail()['token']
        body = {'request_id': request_id()}
        created = self.call('POST', '/integrations/bot/connect', body).json
        repeated = self.call('POST', '/integrations/bot/connect', body).json
        self.assertEqual(created, repeated)
        self.assertTrue(created['token'].startswith('SPIX_'))
        self.assertEqual(set(created['providers']), {'google_calendar', 'onedrive'})
        self.assertNotIn(created['token'], created['instructions'])
        statuses = self.call('GET', '/integrations').json
        self.assertNotIn(created['token'], json.dumps(statuses))
        for provider in statuses['providers']:
            if provider['id'] != 'sevdesk':
                self.assertEqual((provider['method'], provider['state'], provider['connected']),
                                 ('bot', 'awaiting_bot', False))
                self.assertIsNone(provider['identity'])
        raw = str([dict(row) for row in self.office.db.execute('SELECT * FROM external_connections')])
        self.assertNotIn(created['token'], raw)
        self.call('POST', '/intake/gmail', self.gmail_message(), token=mail_key, status=201)
        self.assertEqual(len(self.call('GET', '/inquiries').json), 1)
        self.now[0] += 301
        self.call('POST', '/integrations/bot/connect', body, status=409)
        generations = {p: self.provider_status(p)['generation'] for p in created['providers']}
        replacement = self.bot_connect()
        self.assertNotEqual(created['token'], replacement['token'])
        self.call('GET', '/intake/integrations/jobs', token=created['token'], status=401)
        self.assertEqual({p: self.provider_status(p)['generation'] for p in created['providers']}, generations)
        self.assertEqual(len(self.bot_jobs(replacement['token'])), 2)
        self.now[0] += 90 * 86400 + 1
        self.call('GET', '/intake/integrations/jobs', token=replacement['token'], status=401)
        self.assertEqual(self.provider_status('onedrive')['state'], 'key_expired')

    def test_bot_pending_catalog_is_explicit_and_status_get_does_not_queue_or_claim_success(self):
        created = self.bot_connect()
        original_jobs = self.bot_jobs(created['token'])
        self.assertEqual({j['kind'] for j in original_jobs}, {'catalog'})
        self.assertEqual({j['provider'] for j in original_jobs}, {'google_calendar', 'onedrive'})
        self.assertTrue(all(j['project_id'] is None for j in original_jobs))
        for provider in created['providers']:
            first = self.call('POST', '/integrations/' + provider + '/catalog', {}).json
            second = self.call('POST', '/integrations/' + provider + '/catalog', {}).json
            self.assertEqual(first, second)
            self.assertTrue(first['pending'])
            self.assertEqual(first['items'], [])
            self.assertIsNone(first['synced_at'])
            self.assertFalse(self.provider_status(provider)['connected'])
            self.assertIsNone(self.provider_status(provider, project=True)['data'])
        self.call('GET', '/integrations')
        self.call('GET', self.project_base)
        self.assertEqual(self.bot_jobs(created['token']), original_jobs)
        self.assertEqual(self.sevdesk.calls, [])
        self.assertEqual(self.google.calls, [])

    def test_delayed_old_bot_key_issue_retry_never_rotates_or_revokes_the_newer_key(self):
        first_request, newer_request = {'request_id': request_id()}, {'request_id': request_id()}
        first = self.call('POST', '/integrations/bot/connect', first_request).json
        newer = self.call('POST', '/integrations/bot/connect', newer_request).json
        self.assertNotEqual(first['token'], newer['token'])
        before = [dict(row) for row in self.office.db.execute('SELECT * FROM external_connections ORDER BY provider')]
        count = self.office.db.execute('SELECT COUNT(*) FROM external_bridge_jobs').fetchone()[0]
        self.call('POST', '/integrations/bot/connect', first_request, status=409)
        self.assertEqual([dict(row) for row in self.office.db.execute('SELECT * FROM external_connections ORDER BY provider')], before)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM external_bridge_jobs').fetchone()[0], count)
        self.assertEqual({job['provider'] for job in self.bot_jobs(newer['token'])}, {'google_calendar', 'onedrive'})
        self.call('GET', '/intake/integrations/jobs', token=first['token'], status=401)
        repeated = self.call('POST', '/integrations/bot/connect', newer_request).json
        self.assertEqual(repeated, newer)
        self.assertNotIn(newer['token'], json.dumps(self.call('GET', '/integrations').json))

    def test_bot_credentials_are_narrow_and_fresh_owner_role_is_required(self):
        token = self.bot_connect()['token']
        offline = self.call('POST', '/offline/access', {}, status=201).json['token']
        gmail = self.issue_gmail()['token']
        _, technician = self.add_actor('technician')
        for credential in (self.token, offline, gmail, technician):
            self.call('GET', '/intake/integrations/jobs', token=credential, status=401)
        for path in ('/projects', '/customers', '/inquiries', '/integrations', self.project_base):
            self.call('GET', path, token=token, status=401)
        self.call('POST', '/intake/gmail', self.gmail_message(), token=token, status=401)
        self.call('POST', '/integrations/bot/connect', {'request_id': request_id()}, token=technician, status=403)
        with self.office.lock, self.office.db:
            self.office.db.execute('UPDATE users SET role=? WHERE id=?', ('manager', self.owner_id))
        self.call('GET', '/intake/integrations/jobs', token=token, status=401)
        self.call('POST', '/intake/integrations/jobs/' + 'a' * 32 + '/result', {
            'source_id': 'synthetic-revision', 'error_code': 'unsupported'}, token=token, status=401)

    def test_authenticated_unknown_jobs_and_malformed_json_consume_durable_rate_limit(self):
        token = self.bot_connect()['token']
        path = '/intake/integrations/jobs/' + 'a' * 32 + '/result'
        body = {'source_id': 'synthetic-revision', 'error_code': 'unsupported'}
        self.call('POST', path, body, token=token, status=404)
        self.call('POST', path, b'{', token=token, mime='application/json', status=400)
        self.call('POST', path, b'synthetic binary body', token=token,
                  mime='application/octet-stream', status=415)
        rows = self.office.db.execute('SELECT request_count FROM external_bridge_limits').fetchall()
        self.assertEqual([r['request_count'] for r in rows], [3, 3])
        self.call('POST', path, body, token='SPIX_synthetic-invalid-key', status=401)
        self.assertEqual([r[0] for r in self.office.db.execute('SELECT request_count FROM external_bridge_limits')], [3, 3])
        with self.office.lock, self.office.db:
            self.office.db.execute('UPDATE external_bridge_limits SET request_count=299')
        self.call('POST', path, body, token=token, status=404)
        blocked = self.call('GET', '/intake/integrations/jobs', token=token, status=429)
        self.assertIn('Retry-After', blocked.headers)
        self.assertEqual([r[0] for r in self.office.db.execute('SELECT request_count FROM external_bridge_limits')], [300, 300])

    def test_bot_result_enforces_json_size_and_fixed_error_codes_without_fake_connection(self):
        token = self.bot_connect()['token']
        job = self.bot_jobs(token)[0]
        path = '/intake/integrations/jobs/' + job['id'] + '/result'
        for body in ({'source_id': 'synthetic', 'complete': False, 'payload': {}},
                     {'source_id': 'synthetic', 'error_code': 'raw-provider-secret-failure'},
                     {'source_id': 'synthetic', 'error_code': 'unsupported', 'credential': 'synthetic-secret'}):
            self.call('POST', path, body, token=token, status=400)
        self.call('POST', path, b'{' + b'x' * (2 * 1024 * 1024 + 8192), token=token,
                  mime='application/json', status=413)
        receipt = self.call('POST', path, {'source_id': 'synthetic-failure', 'error_code': 'unsupported'},
                            token=token, status=201).json
        self.assertEqual(receipt, {'status': 'received', 'job_id': job['id'], 'idempotent': False})
        self.assertFalse(self.provider_status(job['provider'])['connected'])
        self.assertIsNone(self.provider_status(job['provider'])['last_sync'])

    def test_failed_initial_bot_catalog_exposes_safe_error_until_a_new_request_or_real_success(self):
        token = self.bot_connect()['token']
        job = next(j for j in self.bot_jobs(token) if j['provider'] == 'google_calendar')
        source = 'synthetic-private-upstream-source-revision'
        receipt = self.call('POST', '/intake/integrations/jobs/' + job['id'] + '/result', {
            'source_id': source, 'error_code': 'permission_denied'}, token=token, status=201).json
        self.assertEqual(receipt, {'status': 'received', 'job_id': job['id'], 'idempotent': False})
        failed = self.provider_status('google_calendar')
        self.assertEqual(failed['state'], 'error')
        self.assertFalse(failed['connected'])
        self.assertIsNone(failed['identity'])
        self.assertIsNone(failed['last_sync'])
        self.assertIsInstance(failed['error'], str)
        self.assertGreater(len(failed['error']), 20)
        self.assertNotEqual(failed['error'], 'permission_denied')
        self.assertNotIn(source, json.dumps(failed))
        self.assertNotIn(token, json.dumps(failed))
        self.now[0] += 1
        queued = self.call('POST', '/integrations/bot/sync', {}).json
        waiting = next(p for p in queued['providers'] if p['id'] == 'google_calendar')
        self.assertEqual(waiting['state'], 'awaiting_bot')
        self.assertFalse(waiting['connected'])
        self.assertIsNone(waiting['error'])
        newer = next(j for j in self.bot_jobs(token) if j['provider'] == 'google_calendar')
        self.assertNotEqual(newer['id'], job['id'])
        self.deliver(token, newer, self.google_bot_catalog())
        recovered = self.provider_status('google_calendar')
        self.assertTrue(recovered['connected'])
        self.assertIsNone(recovered['error'])
        self.assertIsNotNone(recovered['last_sync'])

    def test_failed_bot_resource_preview_explains_failure_and_deduplicates_retry_until_real_data(self):
        token = self.bot_connect()['token']
        _, _, generation = self.confirm_google_bot_catalog(token)
        body = {'generation': generation, 'calendar_id': 'calendar@example.test'}
        initial = self.call('POST', self.project_base + '/google_calendar/preview', body).json
        self.assertTrue(initial['pending'])
        self.call('POST', '/intake/integrations/jobs/' + initial['job_id'] + '/result', {
            'source_id': 'synthetic-unsupported-read-revision', 'error_code': 'unsupported'}, token=token, status=201)
        self.now[0] += 1
        retried = self.call('POST', self.project_base + '/google_calendar/preview', body).json
        self.assertTrue(retried['pending'])
        self.assertNotEqual(retried['job_id'], initial['job_id'])
        self.assertNotEqual(retried['message'], initial['message'])
        self.assertRegex(retried['message'], r'(?i)nicht|fehlt|fehlgeschlagen|fehler|kein|kann|unterstütz|berechtig|zugriff')
        self.assertRegex(retried['message'], r'(?i)erneut|neu|nächsten|wieder|abgleich')
        self.assertNotIn('events', retried)
        repeated = self.call('POST', self.project_base + '/google_calendar/preview', body).json
        self.assertEqual(repeated, retried)
        resources = [j for j in self.bot_jobs(token) if j['kind'] == 'resource']
        self.assertEqual([j['id'] for j in resources], [retried['job_id']])
        self.assertIsNone(self.provider_status('google_calendar', project=True)['data'])
        self.deliver(token, resources[0], dict(calendar_payload(), complete=True))
        recovered = self.call('POST', self.project_base + '/google_calendar/preview', body).json
        self.assertFalse(recovered['pending'])
        self.assertEqual([e['id'] for e in recovered['events']], ['event-17', 'private-event-18'])
        self.assertEqual(recovered['events'][0]['end'], '2030-12-13')
        self.assertNotIn('error', recovered)

    def test_google_bot_catalog_promotes_once_then_explicit_selection_and_snapshot_are_separate(self):
        token = self.bot_connect()['token']
        job, receipt, generation = self.confirm_google_bot_catalog(token)
        self.assertEqual(generation, job['generation'] + 1)
        self.assertEqual(receipt, {'status': 'received', 'job_id': job['id'], 'idempotent': False})
        self.assertTrue(self.deliver(token, job, self.google_bot_catalog())['idempotent'])
        self.assertEqual(self.provider_status('google_calendar')['generation'], generation)
        changed = self.google_bot_catalog()
        changed['identity']['label'] = 'Different synthetic label'
        self.deliver(token, job, changed, status=409)
        catalog = self.call('POST', '/integrations/google_calendar/catalog', {}).json
        self.assertFalse(catalog['pending'])
        self.assertEqual(catalog['items'], [calendar_payload()['calendar']])
        self.assertTrue(self.provider_status('google_calendar')['connected'])
        self.assertFalse(self.provider_status('onedrive')['connected'])
        self.assertIsNone(self.provider_status('google_calendar', project=True)['binding'])
        preview = self.google_bot_resource(token, generation)
        self.assertEqual(len(preview['events']), 2)
        body = {'generation': generation, 'revision': 0, 'request_id': request_id(),
                'calendar_id': 'calendar@example.test', 'event_ids': ['event-17']}
        linked = self.call('POST', self.project_base + '/google_calendar/link', body).json
        self.assertEqual(linked, self.call('POST', self.project_base + '/google_calendar/link', body).json)
        self.assertEqual(linked['state'], 'sync_pending')
        self.assertEqual([e['id'] for e in linked['data']['events']], ['event-17'])
        self.assertNotIn('UNSELECTED PRIVATE', json.dumps(self.call('GET', self.project_base).json))
        jobs = self.bot_jobs(token)
        snapshots = [j for j in jobs if j['kind'] == 'snapshot']
        self.assertEqual(len(snapshots), 1)
        snapshot = snapshots[0]
        self.assertEqual(snapshot['selection'], {'calendar_id': 'calendar@example.test', 'event_ids': ['event-17']})
        self.assertEqual((snapshot['project_id'], snapshot['revision']), (self.project, linked['revision']))
        payload = dict(calendar_payload(), complete=True)
        payload['events'] = payload['events'][:1]
        self.deliver(token, snapshot, payload)
        synced = self.provider_status('google_calendar', project=True)
        self.assertEqual(synced['state'], 'synced')
        self.assertEqual(synced['data']['events'][0]['end'], '2030-12-13')
        self.assertFalse(self.google.calls, 'Bot metadata must not invoke native OAuth provider IO')

    def test_bot_link_revision_blocks_late_snapshot_and_unrelated_calendar_events(self):
        token = self.bot_connect()['token']
        linked = self.link_google_bot(token)
        pending = next(j for j in self.bot_jobs(token) if j['kind'] == 'snapshot')
        self.deliver(token, pending, dict(calendar_payload(), complete=True), status=400)
        self.assertEqual(self.provider_status('google_calendar', project=True)['state'], 'sync_pending')
        _, technician = self.add_actor('technician')
        previous = self.call('POST', self.project_base + '/google_calendar/sync', {
            'generation': linked['generation'], 'revision': linked['revision']}, token=technician).json
        self.assertEqual(previous['state'], 'sync_pending')
        self.assertEqual(len([j for j in self.bot_jobs(token) if j['kind'] == 'snapshot']), 1)
        unlinked = self.call('POST', self.project_base + '/google_calendar/unlink', {
            'generation': linked['generation'], 'revision': linked['revision'], 'request_id': request_id()}).json
        self.assertIsNone(unlinked['binding'])
        self.assertIsNone(unlinked['data'])
        payload = dict(calendar_payload(), complete=True)
        payload['events'] = payload['events'][:1]
        self.deliver(token, pending, payload, status=409)
        self.assertIsNone(self.provider_status('google_calendar', project=True)['data'])

    def test_successful_bot_link_retry_preserves_newer_snapshot_after_resource_cache_expires(self):
        token = self.bot_connect()['token']
        _, _, generation = self.confirm_google_bot_catalog(token)
        self.google_bot_resource(token, generation)
        body = {'generation': generation, 'revision': 0, 'request_id': request_id(),
                'calendar_id': 'calendar@example.test', 'event_ids': ['event-17']}
        initial = self.call('POST', self.project_base + '/google_calendar/link', body).json
        snapshot = next(j for j in self.bot_jobs(token) if j['kind'] == 'snapshot')
        self.now[0] += 60
        newer = dict(calendar_payload(), complete=True)
        newer['events'] = [dict(newer['events'][0], title='Newer confirmed site appointment')]
        self.deliver(token, snapshot, newer, source_id='synthetic-newer-snapshot-revision')
        confirmed = self.provider_status('google_calendar', project=True)
        self.assertEqual(confirmed['state'], 'synced')
        self.assertEqual(confirmed['data']['events'][0]['title'], 'Newer confirmed site appointment')
        self.assertGreater(confirmed['synced_at'], initial['synced_at'])
        stored = dict(self.office.db.execute('SELECT * FROM external_snapshots WHERE project_id=? AND provider=?',
                      (self.project, 'google_calendar')).fetchone())
        count = self.office.db.execute('SELECT COUNT(*) FROM external_bridge_jobs').fetchone()[0]
        for seconds in (0, 301):
            with self.subTest(additional_seconds=seconds):
                self.now[0] += seconds
                replay = self.call('POST', self.project_base + '/google_calendar/link', body).json
                self.assertEqual(replay, confirmed)
                self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM external_bridge_jobs').fetchone()[0], count)
                current = dict(self.office.db.execute('SELECT * FROM external_snapshots WHERE project_id=? AND provider=?',
                               (self.project, 'google_calendar')).fetchone())
                self.assertEqual(current, stored, 'A replay must preserve the newer snapshot and timestamp byte-for-byte')
        self.call('POST', self.project_base + '/google_calendar/link', {
            **body, 'event_ids': ['private-event-18']}, status=409)
        self.call('POST', self.project_base + '/google_calendar/link', {
            **body, 'generation': generation - 1}, status=409)
        self.call('POST', self.project_base + '/google_calendar/link', {
            **body, 'request_id': request_id()}, status=409)
        self.assertEqual(self.provider_status('google_calendar', project=True), confirmed)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM external_bridge_jobs').fetchone()[0], count)

    def test_concurrent_bot_link_retry_rechecks_receipt_before_republishing_old_resource(self):
        token = self.bot_connect()['token']
        _, _, generation = self.confirm_google_bot_catalog(token)
        self.google_bot_resource(token, generation)
        body = {'generation': generation, 'revision': 0, 'request_id': request_id(),
                'calendar_id': 'calendar@example.test', 'event_ids': ['event-17']}
        preflight_done, release = threading.Event(), threading.Event()
        real_replay = self.service.replay_link
        def delayed_preflight(*args, **kwargs):
            # Synchronize only after the genuine DB/auth preflight has returned.
            result = real_replay(*args, **kwargs)
            if result is None and threading.current_thread().name.startswith('late-link-retry'):
                preflight_done.set()
                if not release.wait(5):
                    raise AssertionError('The independent confirmed link never completed')
            return result
        def late_request():
            with self.app.test_client() as client:
                return client.post('/api/v1' + self.project_base + '/google_calendar/link',
                    base_url='https://office.example.test', headers={'Authorization': 'Bearer ' + self.token}, json=body)
        with patch.object(self.service, 'replay_link', delayed_preflight):
            with ThreadPoolExecutor(max_workers=1, thread_name_prefix='late-link-retry') as executor:
                pending = executor.submit(late_request)
                try:
                    self.assertTrue(preflight_done.wait(3), 'Late request never finished its real preflight')
                    self.call('POST', self.project_base + '/google_calendar/link', body)
                    snapshot = next(j for j in self.bot_jobs(token) if j['kind'] == 'snapshot')
                    self.now[0] += 60
                    newer = dict(calendar_payload(), complete=True)
                    newer['events'] = [dict(newer['events'][0], title='Newer snapshot delivered during concurrent retry')]
                    self.deliver(token, snapshot, newer, source_id='synthetic-concurrent-newer-revision')
                    confirmed = self.provider_status('google_calendar', project=True)
                    self.assertEqual(confirmed['state'], 'synced')
                    stored = dict(self.office.db.execute('SELECT * FROM external_snapshots WHERE project_id=? AND provider=?',
                                  (self.project, 'google_calendar')).fetchone())
                    count = self.office.db.execute('SELECT COUNT(*) FROM external_bridge_jobs').fetchone()[0]
                finally:
                    release.set()
                response = pending.result(timeout=5)
        self.assertEqual(response.status_code, 200, response.data[:500])
        self.assertEqual(response.json, confirmed)
        self.assertEqual(response.json['data']['events'][0]['title'], 'Newer snapshot delivered during concurrent retry')
        self.assertEqual(self.provider_status('google_calendar', project=True), confirmed)
        current = dict(self.office.db.execute('SELECT * FROM external_snapshots WHERE project_id=? AND provider=?',
                       (self.project, 'google_calendar')).fetchone())
        self.assertEqual(current, stored)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM external_bridge_jobs').fetchone()[0], count)

    def test_bot_key_rotation_preserves_account_binding_and_rejects_unannounced_account_switch(self):
        original = self.bot_connect()['token']
        linked = self.link_google_bot(original)
        replacement = self.bot_connect()['token']
        self.call('GET', '/intake/integrations/jobs', token=original, status=401)
        after = self.provider_status('google_calendar', project=True)
        self.assertEqual((after['generation'], after['revision'], after['binding'], after['data']),
                         (linked['generation'], linked['revision'], linked['binding'], linked['data']))
        catalog = next(j for j in self.bot_jobs(replacement)
                       if j['provider'] == 'google_calendar' and j['kind'] == 'catalog')
        switched = self.google_bot_catalog()
        switched['identity']['id'] = 'unannounced-other-google-account'
        self.deliver(replacement, catalog, switched, status=409)
        self.assertEqual(self.provider_status('google_calendar')['generation'], linked['generation'])
        self.assertEqual(self.provider_status('google_calendar', project=True)['data'], linked['data'])
        self.call('POST', '/integrations/google_calendar/disconnect', {'request_id': request_id()})
        self.assertEqual({j['provider'] for j in self.bot_jobs(replacement)}, {'onedrive'})
        pending = next(j for j in self.bot_jobs(replacement) if j['provider'] == 'onedrive')
        # Same private key keeps only its still-authorized OneDrive scope.
        self.call('POST', '/intake/integrations/jobs/' + catalog['id'] + '/result', {
            'source_id': 'synthetic-revision', 'error_code': 'unsupported'}, token=replacement, status=404)
        self.assertEqual(pending['provider'], 'onedrive')

    def test_onedrive_bot_confirms_real_folder_then_explicit_drive_binding_and_original_url(self):
        token = self.bot_connect()['token']
        catalog_job = next(j for j in self.bot_jobs(token) if j['provider'] == 'onedrive')
        source = onedrive_payload()
        folders = [{**source['folder'], 'parent_id': 'synthetic-parent'},
                   {**source['folder'], 'drive_id': 'different-synthetic-drive',
                    'parent_id': 'different-synthetic-parent'}]
        catalog = {'complete': True, 'identity': {'id': 'synthetic-ms-account', 'label': 'Synthetic OneDrive account'},
                   'folders': folders}
        self.deliver(token, catalog_job, {**catalog, 'complete': False}, status=400)
        self.assertFalse(self.provider_status('onedrive')['connected'])
        self.deliver(token, catalog_job, catalog)
        generation = self.provider_status('onedrive')['generation']
        self.assertEqual(generation, catalog_job['generation'] + 1)
        known = self.call('POST', '/integrations/onedrive/catalog', {'query': 'project documents'}).json
        self.assertEqual({item['drive_id'] for item in known['items']},
                         {'synthetic-drive', 'different-synthetic-drive'})
        selection = {'generation': generation, 'folder_id': 'synthetic-folder', 'drive_id': 'synthetic-drive'}
        self.call('POST', self.project_base + '/onedrive/preview', {**selection, 'drive_id': 'unknown-drive'}, status=409)
        self.call('POST', self.project_base + '/onedrive/preview', {
            'folder_id': 'synthetic-folder', 'drive_id': 'synthetic-drive'}, status=400)
        pending = self.call('POST', self.project_base + '/onedrive/preview', selection).json
        resource_job = next(j for j in self.bot_jobs(token) if j['id'] == pending['job_id'])
        self.assertEqual(resource_job['selection'], {k: selection[k] for k in ('folder_id', 'drive_id')})
        outside = deepcopy(source)
        outside['files'][0]['parent_id'] = 'different-folder'
        self.deliver(token, resource_job, outside, status=409)
        unsafe = deepcopy(source)
        unsafe['files'][0]['url'] = 'https://unexpected.example.test/provider-secret'
        self.deliver(token, resource_job, unsafe, status=400)
        self.deliver(token, resource_job, source)
        preview = self.call('POST', self.project_base + '/onedrive/preview', selection).json
        self.assertFalse(preview['pending'])
        self.assertEqual(preview['files'][0]['url'], source['files'][0]['url'])
        body = {**selection, 'revision': 0, 'request_id': request_id()}
        linked = self.call('POST', self.project_base + '/onedrive/link', body).json
        self.assertEqual(linked['binding'], {k: selection[k] for k in ('drive_id', 'folder_id')})
        self.assertEqual(linked['state'], 'sync_pending')
        self.assertEqual(linked['data']['files'][0]['rev'], source['files'][0]['rev'])
        _, technician = self.add_actor('technician')
        visible = self.provider_status('onedrive', project=True, token=technician)
        self.assertEqual(visible['data'], linked['data'])
        job = next(j for j in self.bot_jobs(token) if j['provider'] == 'onedrive' and j['kind'] == 'snapshot')
        self.deliver(token, job, source)
        self.assertEqual(self.provider_status('onedrive', project=True)['state'], 'synced')
        self.call('POST', '/integrations/onedrive/disconnect', {'request_id': request_id()})
        self.bot_connect()
        before = self.office.db.execute('SELECT COUNT(*) FROM external_bridge_jobs').fetchone()[0]
        self.call('POST', self.project_base + '/onedrive/preview', selection, status=409)
        self.call('POST', self.project_base + '/onedrive/link', {**body, 'request_id': request_id()}, status=409)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM external_bridge_jobs').fetchone()[0], before)
        self.assertIsNone(self.provider_status('onedrive', project=True)['data'])


@unittest.skipUnless(pg_fixture.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class PostgresIntegrationsApiTests(IntegrationHttpFixture, unittest.TestCase):
    def setUp(self):
        pg_fixture.reset()
        self.office = PostgresOffice(pg_fixture.DSN)
        self.addCleanup(self.office.db.close)
        self.key = Fernet.generate_key()
        self.owner_id = self.office.add_user('owner@example.test', 'Owner-password-123', 'owner')
        self.prepare()

    def other_process(self):
        other = PostgresOffice(pg_fixture.DSN)
        self.addCleanup(other.db.close)
        service = OnlineIntegrations(other, self.key, 'office.example.test',
            providers={'sevdesk': SyntheticSevdesk(), 'google_calendar': SyntheticGoogle()})
        app = create_app(office=other, key=self.key, host='office.example.test', integrations=service)
        return other, service, app.test_client()

    def test_provider_advisory_lock_does_not_block_normal_requests_in_another_process(self):
        generation = self.connect_sevdesk()['generation']
        _, _, other_client = self.other_process()
        entered, release = threading.Event(), threading.Event()
        def provider_io(operation):
            if operation == 'snapshot':
                entered.set()
                if not release.wait(5):
                    raise AssertionError('Independent normal request was blocked by provider IO')
        self.sevdesk.hook = provider_io
        body = {'generation': generation, 'revision': 0, 'request_id': request_id(),
                'contact_id': 'contact-17', 'offer_ids': ['offer-17'], 'invoice_ids': []}
        with ThreadPoolExecutor(max_workers=2) as executor:
            pending = executor.submit(self.call, 'POST', self.project_base + '/sevdesk/link', body)
            try:
                self.assertTrue(entered.wait(3), 'Synthetic provider never entered')
                def independent():
                    headers = {'Authorization': 'Bearer ' + self.token}
                    response = other_client.get('/api/v1/projects',
                        base_url='https://office.example.test', headers=headers)
                    self.assertEqual(response.status_code, 200, response.data[:500])
                    collision = other_client.post('/api/v1/integrations/sevdesk/catalog',
                        base_url='https://office.example.test', headers=headers, json={})
                    self.assertEqual(collision.status_code, 409, collision.data[:500])
                    return response.json
                projects = executor.submit(independent).result(timeout=3)
                self.assertIn(self.project, [p['id'] for p in projects])
            finally:
                release.set()
            self.assertEqual(pending.result(timeout=5).json['state'], 'synced')

    def test_account_generation_changed_in_another_process_drops_late_provider_result(self):
        generation = self.connect_sevdesk()['generation']
        other, service, _ = self.other_process()
        def account_changed(operation):
            if operation == 'snapshot':
                with other.lock, other.db:
                    actor = other.user(self.token)
                    service.domain.disconnect(actor, 'sevdesk', request_id(), expected_generation=generation)
        self.sevdesk.hook = account_changed
        self.call('POST', self.project_base + '/sevdesk/link', {
            'generation': generation, 'revision': 0, 'request_id': request_id(),
            'contact_id': 'contact-17', 'offer_ids': [], 'invoice_ids': []}, status=409)
        self.assertIsNone(self.provider_status('sevdesk', project=True)['data'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM external_snapshots').fetchone()[0], 0)

    def test_owner_deactivated_in_another_process_cannot_publish_or_delegate_credentials(self):
        linked = self.link_sevdesk()
        technician_id, technician = self.add_actor('technician')
        del technician_id
        other, other_service, _ = self.other_process()
        def revoked(operation):
            if operation == 'snapshot':
                with other.lock, other.db:
                    other.db.execute('UPDATE users SET active=0 WHERE id=?', (self.owner_id,))
        self.sevdesk.hook = revoked
        self.call('POST', self.project_base + '/sevdesk/sync', {
            'generation': linked['generation'], 'revision': linked['revision']}, status=401)
        state = self.call('GET', self.project_base, token=technician).json
        self.assertFalse(state['financial_visible'])
        self.assertNotIn('Synthetic offer', json.dumps(state))
        # An assigned accountant also loses the revoked owner's delegation.
        accountant_id = other.add_user('accountant@example.test', 'Synthetic-accountant-password-123', 'accountant')
        with other.lock, other.db:
            actor = {'id': accountant_id, 'role': 'accountant', 'email': 'accountant@example.test'}
            other.db.execute('INSERT INTO assignments(project_id,user_id) VALUES(?,?)', (self.project, accountant_id))
            current = other_service.domain.project_connection(actor, self.project, 'sevdesk')
            self.assertIsNone(current['credential'])
            self.assertIsNone(other_service.domain.snapshot(actor, self.project, 'sevdesk')['data'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
