"""Server vault and project-scoped orchestration for read-only integrations.

Every provider call runs outside Office's transaction. A separate provider lock
serializes refresh/configuration across workers; generation and link revision
are rechecked before publishing results. No upstream financial/calendar writes.
"""
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import secrets
import sqlite3
import threading
import time

from cryptography.fernet import Fernet, InvalidToken
import psycopg

from core import Problem, canonical, digest
from external_integrations import ExternalIntegrations, PROVIDERS, OAUTH_PROVIDERS
from online.integration_http import (
    IntegrationAuthenticationRequired, IntegrationPermissionDenied,
    IntegrationHttp, integration_deadline,
)


NAMES = {'sevdesk': 'sevdesk', 'google_calendar': 'Google Kalender', 'onedrive': 'OneDrive'}
LOCKS = {'sevdesk': 741290540, 'google_calendar': 741290541, 'onedrive': 741290542}
MAX_FILE_BYTES = 20 * 1024 * 1024
_ID = r'[a-f0-9]{32}'
_PROVIDER = r'(?:sevdesk|google_calendar|onedrive)'
_PROJECT = r'/projects/(' + _ID + r')/integrations'
_ACTIONS = ('preview', 'link', 'sync', 'unlink')
_ERROR_MESSAGES = {
    'provider_unavailable': 'Der Anbieter ist derzeit nicht erreichbar. Der angezeigte Stand kann veraltet sein.',
    'reconnect_required': 'Die Verbindung oder Freigabe beim Anbieter muss geprüft werden.',
    'rate_limited': 'Der Anbieter begrenzt die Abrufe. Bitte später erneut aktualisieren.',
    'timeout': 'Der Anbieter hat nicht rechtzeitig geantwortet. Der letzte Stand bleibt erhalten.',
    'invalid_response': 'Der Anbieter hat keine gültigen Daten geliefert. Bitte später erneut aktualisieren.',
}


def methods(path):
    if path == '/integrations' or re.fullmatch(_PROJECT, path):
        return 'GET'
    if re.fullmatch(r'/integrations/sevdesk/(?:connect|disconnect|catalog)', path):
        return 'POST'
    if re.fullmatch(r'/integrations/(?:google_calendar)/(?:configure|connect|disconnect|catalog)', path):
        return 'POST'
    if path in ('/integrations/bot/connect', '/integrations/bot/sync'):
        return 'POST'
    if path in ('/integrations/onedrive/catalog', '/integrations/onedrive/disconnect'):
        return 'POST'
    if re.fullmatch(_PROJECT + '/' + _PROVIDER + '/(?:preview|link|sync|unlink)', path):
        return 'POST'
    return None


def _object(data, allowed, required=()):
    if not isinstance(data, dict) or set(data) - set(allowed) or set(required) - set(data):
        raise Problem(400, 'Vollständige Integrationsauswahl erwartet.')


def _text(value, maximum, label, *, empty=False):
    if (not isinstance(value, str) or len(value) > maximum or
            (not empty and not value.strip()) or
            any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise Problem(400, 'Ungültiges Feld: ' + label)
    return value.strip()


def _request_id(data):
    value = data.get('request_id')
    if not isinstance(value, str) or not re.fullmatch(_ID, value):
        raise Problem(400, 'Eindeutige Vorgangs-ID erwartet.')
    return value


def _revision(data):
    value = data.get('revision')
    if type(value) is not int or value < 0:
        raise Problem(400, 'Aktueller Stand der Projektzuordnung erwartet.')
    return value


def _generation(data):
    value = data.get('generation')
    if type(value) is not int or value < 0:
        raise Problem(400, 'Aktueller Stand der Kontoverbindung erwartet.')
    return value


def _ids(value, maximum):
    if (not isinstance(value, list) or len(value) > maximum or
            any(not isinstance(item, str) or not item or len(item) > 2048 or
                not item.isprintable() for item in value) or len(set(value)) != len(value)):
        raise Problem(400, 'Eindeutige, begrenzte Auswahl erwartet.')
    return list(value)


def _selection(provider, data):
    if provider == 'sevdesk':
        _object(data, ('generation', 'revision', 'request_id', 'contact_id', 'offer_ids', 'invoice_ids'),
                ('generation', 'revision', 'request_id', 'contact_id', 'offer_ids', 'invoice_ids'))
        remote = _text(data['contact_id'], 2048, 'sevdesk-Kontakt')
        return remote, dict(contact_id=remote, offer_ids=_ids(data['offer_ids'], 50),
                            invoice_ids=_ids(data['invoice_ids'], 50))
    if provider == 'google_calendar':
        _object(data, ('generation', 'revision', 'request_id', 'calendar_id', 'event_ids'),
                ('generation', 'revision', 'request_id', 'calendar_id', 'event_ids'))
        remote = _text(data['calendar_id'], 1024, 'Google-Kalender')
        return remote, dict(calendar_id=remote, event_ids=_ids(data['event_ids'], 50))
    _object(data, ('generation', 'revision', 'request_id', 'folder_id', 'drive_id'),
            ('generation', 'revision', 'request_id', 'folder_id', 'drive_id'))
    remote = _text(data['folder_id'], 2048, 'OneDrive-Ordner')
    return remote, {'folder_id': remote, 'drive_id': _text(data['drive_id'], 2048, 'OneDrive-Laufwerk')}


def _error_code(error):
    if isinstance(error, (IntegrationAuthenticationRequired, IntegrationPermissionDenied)):
        return 'reconnect_required'
    return {429: 'rate_limited', 504: 'timeout', 400: 'invalid_response'}.get(error.status, 'provider_unavailable')


class OnlineIntegrations:
    def __init__(self, office, key, host, *, providers=None, clock=None):
        if not re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)+', host):
            raise RuntimeError('Gültiger öffentlicher Hostname erforderlich.')
        self.office, self.vault, self.host = office, Fernet(key), host
        self.clock = clock or time.time
        self.domain = ExternalIntegrations(office, clock=self.clock)
        self._bot_worker = None
        self.providers = dict(providers or {})
        self.local_locks = {provider: threading.Lock() for provider in PROVIDERS}

    @property
    def bot(self):
        if self._bot_worker is None:
            from online.integration_bot_service import BotIntegrations
            self._bot_worker = BotIntegrations(self)
        return self._bot_worker

    def _provider(self, provider):
        if provider not in PROVIDERS:
            raise Problem(404, 'Integration nicht gefunden.')
        if provider not in self.providers:
            if provider == 'sevdesk':
                from online.integration_sevdesk import SevdeskProvider
                worker = SevdeskProvider(IntegrationHttp(provider))
            elif provider == 'google_calendar':
                from online.integration_google import GoogleCalendarProvider
                worker = GoogleCalendarProvider(IntegrationHttp(provider))
            else:
                raise Problem(409, 'OneDrive-Projektunterlagen werden über den vorhandenen Bot bereitgestellt.')
            self.providers[provider] = worker
        return self.providers[provider]

    def _redirect(self, provider):
        return 'https://' + self.host + '/api/v1/integrations/' + provider + '/callback'

    def _encrypt(self, value):
        return self.vault.encrypt(canonical(value).encode('utf-8')).decode('ascii')

    def _decrypt(self, value):
        try:
            result = json.loads(self.vault.decrypt(value.encode('ascii')))
            if not isinstance(result, dict):
                raise ValueError()
            return result
        except (InvalidToken, AttributeError, TypeError, ValueError, UnicodeError):
            raise Problem(409, 'Gespeicherte Verbindung bitte erneut einrichten.') from None

    def _actor(self, token, *, owner=False):
        actor = self.office.user(token)
        if owner:
            self.office.require(actor, ('owner',))
        return actor

    @contextmanager
    def _operation(self, provider):
        if provider not in PROVIDERS:
            raise Problem(404, 'Integration nicht gefunden.')
        connection = None
        acquired = False
        with integration_deadline():
            try:
                if isinstance(self.office.db, sqlite3.Connection):
                    acquired = self.local_locks[provider].acquire(blocking=False)
                else:
                    try:
                        connection = psycopg.connect(
                            self.office.db.dsn, autocommit=True, connect_timeout=5,
                            options='-c statement_timeout=5000',
                        )
                        acquired = connection.execute(
                            'SELECT pg_try_advisory_lock(%s)', (LOCKS[provider],),
                        ).fetchone()[0]
                    except psycopg.Error:
                        raise Problem(503, 'Die Integration ist derzeit nicht verfügbar.') from None
                if not acquired:
                    raise Problem(409, 'Für diesen Anbieter läuft bereits ein Abgleich. Bitte kurz warten.')
                yield
            finally:
                if connection is not None:
                    connection.close()
                elif acquired:
                    self.local_locks[provider].release()

    def _connection(self, actor, provider, project=None):
        return (self.domain.connection(actor, provider) if project is None else
                self.domain.project_connection(actor, project, provider))

    def _public_connection(self, row):
        provider = row['provider']
        result = {
            'id': provider, 'name': NAMES[provider], 'generation': row['generation'],
            'configured': bool(row.get('config')) if provider != 'sevdesk' else True,
            'connected': row['state'] == 'connected' and bool(row.get('credential')),
            'state': row['state'], 'identity': row.get('identity'),
            'last_sync': None, 'error': None,
        }
        if provider == 'google_calendar':
            from online.integration_google import SCOPES
            result.update(redirect_uri=self._redirect(provider), scopes=list(SCOPES))
        elif provider == 'onedrive':
            result['scopes'] = ['Gewählte OneDrive-Projektunterlagen über den vorhandenen Bot']
        else:
            result['scopes'] = ['Kunden, Angebote und Rechnungen lesend']
        if row.get('state') == 'reauth_required':
            result['error'] = 'Verbindung bitte erneut autorisieren.'
        result['method'] = 'api' if provider == 'sevdesk' else 'oauth'
        if self.bot.mode(row):
            result.update(self.bot.public_status(row))
        return result

    def status(self, token):
        with self.office.lock, self.office.db:
            actor = self._actor(token, owner=True)
            return {'providers': [self._public_connection(self.domain.connection(actor, p)) for p in PROVIDERS],
                    'capabilities': ['business_integrations'], 'instructions': self.bot.instructions()}

    def _project_status(self, actor, project, provider):
        row = self.domain.project_connection(actor, project, provider)
        saved = self.domain.snapshot(actor, project, provider)
        binding = saved.get('binding')
        result = {
            'id': provider, 'name': NAMES[provider], 'generation': row['generation'],
            'configured': bool(row.get('config')) if provider != 'sevdesk' else True,
            'connected': row['state'] == 'connected' and bool(row.get('credential')),
            'revision': binding['revision'] if binding else 0,
            'state': saved['state'], 'binding': binding.get('data') if binding else None,
            'data': saved.get('data'), 'synced_at': saved.get('synced_at'),
            'error': _ERROR_MESSAGES.get(saved.get('error')),
        }
        if not result['connected']:
            result.update(state='reauth_required' if row['state'] == 'reauth_required' else
                          'not_connected', binding=None, data=None, synced_at=None)
        result['method'] = 'api' if provider == 'sevdesk' else 'oauth'
        if self.bot.mode(row):
            result.update(self.bot.project_public_status(actor, project, row, binding))
        return result

    def project_status(self, token, project):
        with self.office.lock, self.office.db:
            actor = self._actor(token)
            self.domain.project(actor, project)
            financial = actor['role'] in ('owner', 'accountant')
            return {'financial_visible': financial,
                    'providers': [self._project_status(actor, project, p)
                                  for p in PROVIDERS if financial or p != 'sevdesk']}

    def configure(self, token, provider, data):
        if provider not in OAUTH_PROVIDERS:
            raise Problem(404, 'Einrichtung nicht gefunden.')
        _object(data, ('client_id', 'client_secret', 'request_id'),
                ('client_id', 'client_secret', 'request_id'))
        request = _request_id(data)
        config = {'client_id': _text(data['client_id'], 512, 'Client-ID'),
                  'client_secret': _text(data['client_secret'], 4096, 'Client-Secret')}
        with self._operation(provider):
            with self.office.lock, self.office.db:
                actor = self._actor(token, owner=True)
                self.domain.put_connection(
                    actor, provider, config=self._encrypt(config), credential=None, identity=None,
                    request_id=request, request_hash=digest(canonical(config)),
                )
                return self._public_connection(self.domain.connection(actor, provider))

    def connect_sevdesk(self, token, data):
        _object(data, ('api_token', 'request_id'), ('api_token', 'request_id'))
        request = _request_id(data)
        api_token = _text(data['api_token'], 512, 'sevdesk-API-Zugang')
        with self._operation('sevdesk'):
            with self.office.lock, self.office.db:
                actor = self._actor(token, owner=True)
                before = self.domain.connection(actor, 'sevdesk')
            # A mistyped replacement must leave the previous working connection.
            identity = self._provider('sevdesk').validate(api_token)
            with self.office.lock, self.office.db:
                actor = self._actor(token, owner=True)
                self.domain.put_connection(
                    actor, 'sevdesk', credential=self._encrypt({'api_token': api_token}),
                    identity=identity, expected_generation=before['generation'],
                    request_id=request, request_hash=digest(canonical({'api_token': api_token})),
                )
                return self._public_connection(self.domain.connection(actor, 'sevdesk'))

    def begin(self, token, provider, data):
        if provider not in OAUTH_PROVIDERS:
            raise Problem(404, 'Verbindung nicht gefunden.')
        _object(data, ())
        state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        with self._operation(provider):
            with self.office.lock, self.office.db:
                actor = self._actor(token, owner=True)
                row = self.domain.connection(actor, provider)
                if not row.get('config'):
                    raise Problem(409, 'Zuerst die einmalige Anbietereinrichtung abschließen.')
                config = self._decrypt(row['config'])
                if config.get('mode') == 'bot':
                    raise Problem(409, 'Diese Verbindung verwendet den bereits verbundenen Projektbot.')
                self.domain.put_oauth(
                    actor, provider, state_hash=digest(state), session_hash=digest(token),
                    config_hash=row['config_hash'], generation=row['generation'],
                    payload=self._encrypt({'verifier': verifier, 'redirect': self._redirect(provider)}),
                    expires_at=self.clock() + 600,
                )
            return {'url': self._provider(provider).authorization_url(
                config, state, challenge, self._redirect(provider))}

    def _callback_actor(self, pending):
        actor = self.office.db.execute(
            'SELECT u.id,u.email,u.role FROM users u JOIN sessions s ON u.id=s.user_id '
            'WHERE s.token=? AND s.expiry>? AND u.active=1',
            (pending['session_hash'], self.clock()),
        ).fetchone()
        if not actor or actor['id'] != pending['actor']['id'] or actor['role'] != 'owner':
            raise Problem(403, 'Die Berechtigung zur Verbindung ist nicht mehr gültig.')
        return dict(actor)

    def _tokens(self, value):
        if not isinstance(value, dict):
            raise Problem(503, 'Der Anbieter hat keine gültige Anmeldung geliefert.')
        access, refresh, seconds = value.get('access_token'), value.get('refresh_token'), value.get('expires_in')
        if (not isinstance(access, str) or not 1 <= len(access) <= 16384 or
                not isinstance(refresh, str) or not 1 <= len(refresh) <= 16384 or
                type(seconds) is not int or not 1 <= seconds <= 366 * 86400 or
                any(ord(c) < 33 or ord(c) > 126 for c in access + refresh)):
            raise Problem(503, 'Der Anbieter hat keine gültige Anmeldung geliefert.')
        return dict(value, expires_at=self.clock() + seconds)

    def callback(self, provider, state, code, error=None):
        if provider not in OAUTH_PROVIDERS or not isinstance(state, str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,200}', state):
            raise Problem(400, 'Anbieteranmeldung ist ungültig oder abgelaufen.')
        with self._operation(provider):
            with self.office.lock, self.office.db:
                pending = self.domain.consume_oauth(digest(state))
            # Consumption commits even on cancellation, expiry, invalid role or IO.
            if not pending or not pending.get('valid') or pending.get('provider') != provider:
                raise Problem(400, 'Anbieteranmeldung ist ungültig oder bereits verwendet.')
            if error:
                raise Problem(400, 'Anbieteranmeldung wurde nicht abgeschlossen.')
            code = _text(code, 8192, 'Anmeldebestätigung')
            secret = self._decrypt(pending['payload'])
            with self.office.lock, self.office.db:
                actor = self._callback_actor(pending)
                row = self.domain.connection(actor, provider)
                if row['generation'] != pending['generation'] or row['config_hash'] != pending['config_hash']:
                    raise Problem(409, 'Die Einrichtung wurde inzwischen geändert. Bitte erneut verbinden.')
                config = self._decrypt(row['config'])
            tokens = self._tokens(self._provider(provider).exchange(
                config, code, secret['verifier'], self._redirect(provider)))
            identity = self._provider(provider).identity(tokens['access_token'])
            with self.office.lock, self.office.db:
                actor = self._callback_actor(pending)
                self.domain.put_connection(
                    actor, provider, credential=self._encrypt(tokens), identity=identity,
                    expected_generation=pending['generation'],
                )
            return {'connected': True}

    def disconnect(self, token, provider, data):
        _object(data, ('request_id',), ('request_id',))
        request = _request_id(data)
        with self._operation(provider):
            with self.office.lock, self.office.db:
                actor = self._actor(token, owner=True)
                self.domain.disconnect(actor, provider, request)
                return self._public_connection(self.domain.connection(actor, provider))

    def _access(self, token, provider, *, project=None, revision=None, expected_generation=None):
        with self.office.lock, self.office.db:
            actor = self._actor(token, owner=project is None)
            row = self._connection(actor, provider, project)
            if expected_generation is not None and row['generation'] != expected_generation:
                raise Problem(409, 'Die Kontoverbindung wurde inzwischen geändert. Bitte neu laden.')
            if row['state'] != 'connected' or not row.get('credential'):
                raise Problem(409, 'Den Anbieter zuerst verbinden oder die Verbindung erneuern.')
            if project is not None and revision is not None:
                binding = self.domain.binding(actor, project, provider)
                if (not binding or not binding['data'] or binding['revision'] != revision or
                        binding['generation'] != row['generation']):
                    raise Problem(409, 'Die Projektzuordnung wurde inzwischen geändert. Bitte neu laden.')
            value = self._decrypt(row['credential'])
            config = self._decrypt(row['config']) if provider in OAUTH_PROVIDERS else None
        if provider == 'sevdesk':
            if not isinstance(value.get('api_token'), str):
                raise Problem(409, 'sevdesk bitte erneut verbinden.')
            return row, value['api_token']
        expiry = value.get('expires_at')
        if not isinstance(expiry, (int, float)) or not math.isfinite(expiry):
            raise Problem(409, 'Die Anmeldung bitte erneut autorisieren.')
        if expiry <= self.clock() + 60:
            try:
                value = self._tokens(self._provider(provider).refresh(config, value['refresh_token']))
            except Problem as error:
                self._failure(token, provider, error, row, project=project, revision=revision)
                raise
            with self.office.lock, self.office.db:
                actor = self._actor(token, owner=project is None)
                self.domain.refresh_credential(
                    actor, provider, self._encrypt(value), generation=row['generation'],
                    project_id=project, revision=revision,
                )
        return row, value['access_token']

    def _postcheck(self, token, provider, row, *, project=None, revision=None):
        actor = self._actor(token, owner=project is None)
        current = self._connection(actor, provider, project)
        if current['generation'] != row['generation'] or current['state'] != 'connected':
            raise Problem(409, 'Die Verbindung wurde inzwischen geändert. Bitte neu laden.')
        if project is not None and revision is not None:
            binding = self.domain.binding(actor, project, provider)
            if (not binding or binding['revision'] != revision or
                    binding['generation'] != row['generation'] or not binding['data']):
                raise Problem(409, 'Die Projektzuordnung wurde inzwischen geändert. Bitte neu laden.')
        return actor

    def _failure(self, token, provider, error, row=None, *, project=None, revision=None):
        if row is None:
            return
        try:
            with self.office.lock, self.office.db:
                actor = self._postcheck(token, provider, row, project=project, revision=revision)
                if isinstance(error, IntegrationAuthenticationRequired):
                    self.domain.invalidate_connection(
                        actor, provider, generation=row['generation'],
                        project_id=project, revision=revision,
                    )
                elif project is not None and revision is not None:
                    self.domain.record_error(
                        actor, project, provider, _error_code(error),
                        generation=row['generation'], revision=revision,
                    )
        except Problem:
            pass  # Never alter a newer account, assignment or link after stale IO.

    def catalog(self, token, provider, data):
        if self.bot.active(token, provider):
            return self.bot.catalog(token, provider, data)
        _object(data, ('query',))
        query = _text(data.get('query', ''), 2048, 'Suche', empty=True)
        row = None
        with self._operation(provider):
            try:
                row, access = self._access(token, provider)
                worker = self._provider(provider)
                if provider == 'sevdesk':
                    items = worker.contacts(access, query)
                elif provider == 'google_calendar':
                    if query:
                        raise Problem(400, 'Google-Kalender bitte aus der Liste auswählen.')
                    items = worker.calendars(access)
                else:
                    raise Problem(409, 'OneDrive-Projektunterlagen verwenden den vorhandenen Bot.')
                with self.office.lock, self.office.db:
                    self._postcheck(token, provider, row)
                return {'items': items}
            except Problem as error:
                self._failure(token, provider, error, row)
                raise

    def preview(self, token, project, provider, data):
        if self.bot.active(token, provider, project):
            return self.bot.preview(token, project, provider, data)
        field = {'sevdesk': 'contact_id', 'google_calendar': 'calendar_id', 'onedrive': 'folder_id'}[provider]
        _object(data, (field, 'generation'), (field, 'generation'))
        generation = _generation(data)
        remote = _text(data[field], 2048, 'Anbieterauswahl')
        row = None
        with self._operation(provider):
            try:
                with self.office.lock, self.office.db:
                    actor = self._actor(token, owner=True)
                    self.domain.project(actor, project, provider, write=True)
                row, access = self._access(token, provider, expected_generation=generation)
                if row['generation'] != generation:
                    raise Problem(409, 'Die Kontoverbindung wurde inzwischen geändert. Bitte neu laden.')
                worker = self._provider(provider)
                if provider == 'sevdesk':
                    result = worker.contact_documents(access, remote)
                elif provider == 'google_calendar':
                    result = {'calendar': {'id': remote}, 'events': worker.events(access, remote)}
                else:
                    raise Problem(409, 'OneDrive-Projektunterlagen verwenden den vorhandenen Bot.')
                with self.office.lock, self.office.db:
                    actor = self._postcheck(token, provider, row)
                    self.domain.project(actor, project, provider, write=True)
                return dict(result, generation=generation)
            except Problem as error:
                self._failure(token, provider, error, row)
                raise

    def _snapshot(self, provider, access, row, selection):
        worker = self._provider(provider)
        return worker.snapshot(access, selection)

    def _replay_link_locked(self, actor, project, provider, remote, selection, generation, revision, request):
        """Call inside the final transaction as well as before external IO."""
        self.domain.project(actor, project, provider, write=True)
        row = self.domain.project_connection(actor, project, provider)
        if row['generation'] != generation:
            raise Problem(409, 'Die Kontoverbindung wurde inzwischen geändert. Bitte neu laden.')
        receipt = self.office.db.execute(
            'SELECT 1 FROM external_requests WHERE user_id=? AND request_id=?',
            (actor['id'], request),
        ).fetchone()
        if receipt is None:
            current = self.domain.binding(actor, project, provider)
            if revision != (current['revision'] if current else 0):
                raise Problem(409, 'Die Projektzuordnung wurde inzwischen geändert. Bitte neu laden.')
            return None
        self.domain.bind(actor, project, provider, remote, selection,
                         generation=generation, revision=revision, request_id=request)
        return self._project_status(actor, project, provider)

    def replay_link(self, token, project, provider, remote, selection, generation, revision, request):
        """A confirmed retry reads today's state and never republishes old data."""
        with self.office.lock, self.office.db:
            return self._replay_link_locked(
                self._actor(token, owner=True), project, provider, remote, selection,
                generation, revision, request,
            )

    def link(self, token, project, provider, data):
        if self.bot.active(token, provider, project):
            return self.bot.link(token, project, provider, data)
        remote, selection = _selection(provider, data)
        request, revision, generation = _request_id(data), _revision(data), _generation(data)
        replay = self.replay_link(token, project, provider, remote, selection, generation, revision, request)
        if replay is not None:
            return replay
        row = None
        with self._operation(provider):
            replay = self.replay_link(token, project, provider, remote, selection, generation, revision, request)
            if replay is not None:
                return replay
            try:
                with self.office.lock, self.office.db:
                    actor = self._actor(token, owner=True)
                    self.domain.project(actor, project, provider, write=True)
                row, access = self._access(token, provider, expected_generation=generation)
                if row['generation'] != generation:
                    raise Problem(409, 'Die Kontoverbindung wurde inzwischen geändert. Bitte neu laden.')
                payload = self._snapshot(provider, access, row, selection)
                with self.office.lock, self.office.db:
                    actor = self._postcheck(token, provider, row)
                    replay = self._replay_link_locked(
                        actor, project, provider, remote, selection, generation, revision, request,
                    )
                    if replay is not None:
                        return replay
                    self.domain.project(actor, project, provider, write=True)
                    binding = self.domain.bind(
                        actor, project, provider, remote, selection, generation=row['generation'],
                        revision=revision, request_id=request,
                    )
                    self.domain.save_snapshot(
                        actor, project, provider, payload, generation=row['generation'],
                        revision=binding['revision'], synced_at=self._now(),
                    )
                    return self._project_status(actor, project, provider)
            except Problem as error:
                self._failure(token, provider, error, row)
                raise

    def _now(self):
        return datetime.fromtimestamp(self.clock(), timezone.utc).isoformat(timespec='seconds')

    def sync(self, token, project, provider, data):
        if self.bot.active(token, provider, project):
            return self.bot.sync(token, project, provider, data)
        _object(data, ('revision', 'generation'), ('revision', 'generation'))
        revision, generation, row = _revision(data), _generation(data), None
        with self._operation(provider):
            try:
                row, access = self._access(token, provider, project=project, revision=revision,
                                           expected_generation=generation)
                if row['generation'] != generation:
                    raise Problem(409, 'Die Kontoverbindung wurde inzwischen geändert. Bitte neu laden.')
                with self.office.lock, self.office.db:
                    actor = self._actor(token)
                    binding = self.domain.binding(actor, project, provider)
                payload = self._snapshot(provider, access, row, binding['data'])
                with self.office.lock, self.office.db:
                    actor = self._postcheck(token, provider, row, project=project, revision=revision)
                    self.domain.save_snapshot(
                        actor, project, provider, payload, generation=row['generation'],
                        revision=revision, synced_at=self._now(),
                    )
                    return self._project_status(actor, project, provider)
            except Problem as error:
                self._failure(token, provider, error, row, project=project, revision=revision)
                raise

    def unlink(self, token, project, provider, data):
        _object(data, ('revision', 'request_id', 'generation'), ('revision', 'request_id', 'generation'))
        revision, request, generation = _revision(data), _request_id(data), _generation(data)
        with self._operation(provider):
            with self.office.lock, self.office.db:
                actor = self._actor(token, owner=True)
                row = self.domain.project_connection(actor, project, provider)
                if row['generation'] != generation:
                    raise Problem(409, 'Die Kontoverbindung wurde inzwischen geändert. Bitte neu laden.')
                self.domain.unlink(actor, project, provider, generation=row['generation'],
                                   revision=revision, request_id=request)
                return self._project_status(actor, project, provider)

    def dispatch(self, token, path, method, data):
        if methods(path) is None:
            raise Problem(404, 'Integration nicht gefunden.')
        if path == '/integrations':
            return self.status(token), 200, 'application/json'
        if path == '/integrations/bot/connect':
            return self.bot.connect(token, data), 200, 'application/json'
        if path == '/integrations/bot/sync':
            return self.bot.request_catalogs(token, data), 200, 'application/json'
        match = re.fullmatch(r'/integrations/(' + _PROVIDER + r')/([a-z]+)', path)
        if match:
            provider, action = match.groups()
            if action == 'configure':
                result = self.configure(token, provider, data)
            elif action == 'connect':
                result = self.connect_sevdesk(token, data) if provider == 'sevdesk' else self.begin(token, provider, data)
            elif action == 'disconnect':
                result = self.disconnect(token, provider, data)
            else:
                result = self.catalog(token, provider, data)
            return result, 200, 'application/json'
        match = re.fullmatch(_PROJECT, path)
        if match:
            return self.project_status(token, match[1]), 200, 'application/json'
        match = re.fullmatch(_PROJECT + '/(' + _PROVIDER + ')/([a-z]+)', path)
        if match:
            project, provider, action = match.groups()
            result = getattr(self, action)(token, project, provider, data)
            return result, 200, 'application/json'
        raise Problem(404, 'Integration nicht gefunden.')
