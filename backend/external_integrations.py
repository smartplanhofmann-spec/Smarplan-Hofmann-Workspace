"""Persistence and authorization for explicit, read-only business integrations.

The caller owns Office's lock and SQL transaction. This module never decrypts a
credential, performs provider IO or authenticates an application bearer token.
Internal connection views contain ciphertext: services must construct their own
public response. OAuth consumption returns a validity result, rather than
raising after deletion; commit consumption before handling an invalid result.
"""
import base64
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import sqlite3
import time
from urllib.parse import urlsplit
import uuid

from core import Problem, canonical


PROVIDERS = ('sevdesk', 'google_calendar', 'onedrive')
OAUTH_PROVIDERS = ('google_calendar',)
MAX_CIPHER_BYTES = 65536
MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024
MAX_SNAPSHOT_ITEMS = 1000
MAX_OAUTH_STATES = 20
OAUTH_TTL_SECONDS = 600
ERROR_CODES = ('provider_unavailable', 'reconnect_required', 'rate_limited', 'timeout', 'invalid_response')
UNSET = object()
_ID = re.compile(r'[a-f0-9]{32}')
_HASH = re.compile(r'[a-f0-9]{64}')


def schema_statements():
    return [
        '''CREATE TABLE IF NOT EXISTS external_connections(
          provider TEXT PRIMARY KEY CHECK(provider IN ('sevdesk','google_calendar','onedrive')),
          id TEXT NOT NULL UNIQUE CHECK(length(id)=32), owner_id TEXT NOT NULL REFERENCES users(id),
          config_cipher TEXT CHECK(config_cipher IS NULL OR length(config_cipher)<=65536),
          credential_cipher TEXT CHECK(credential_cipher IS NULL OR length(credential_cipher)<=65536),
          identity_json TEXT NOT NULL CHECK(length(identity_json)<=8192),
          generation INTEGER NOT NULL CHECK(generation>0),
          state TEXT NOT NULL CHECK(state IN ('disconnected','configured','connected','reauth_required')),
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS external_project_links(
          project_id TEXT NOT NULL REFERENCES projects(id), provider TEXT NOT NULL REFERENCES external_connections(provider),
          remote TEXT CHECK(remote IS NULL OR length(remote)<=2048), selection_json TEXT NOT NULL CHECK(length(selection_json)<=65536),
          active INTEGER NOT NULL CHECK(active IN (0,1)), revision INTEGER NOT NULL CHECK(revision>0),
          generation INTEGER NOT NULL CHECK(generation>0), updated_by TEXT NOT NULL REFERENCES users(id), updated_at TEXT NOT NULL,
          error_code TEXT CHECK(error_code IS NULL OR error_code IN
            ('provider_unavailable','reconnect_required','rate_limited','timeout','invalid_response')),
          PRIMARY KEY(project_id,provider))''',
        '''CREATE TABLE IF NOT EXISTS external_snapshots(
          project_id TEXT NOT NULL, provider TEXT NOT NULL, generation INTEGER NOT NULL CHECK(generation>0),
          revision INTEGER NOT NULL CHECK(revision>0), payload_json TEXT NOT NULL CHECK(length(payload_json)<=2097152),
          payload_sha256 TEXT NOT NULL CHECK(length(payload_sha256)=64), synced_at TEXT NOT NULL,
          PRIMARY KEY(project_id,provider),
          FOREIGN KEY(project_id,provider) REFERENCES external_project_links(project_id,provider))''',
        '''CREATE TABLE IF NOT EXISTS external_requests(
          user_id TEXT NOT NULL REFERENCES users(id), request_id TEXT NOT NULL CHECK(length(request_id)=32),
          provider TEXT NOT NULL REFERENCES external_connections(provider),
          operation TEXT NOT NULL CHECK(operation IN ('connection','disconnect','bind','unlink')),
          project_id TEXT REFERENCES projects(id), request_hash TEXT NOT NULL CHECK(length(request_hash)=64),
          result_json TEXT NOT NULL CHECK(length(result_json)<=65536), created_at TEXT NOT NULL,
          PRIMARY KEY(user_id,request_id))''',
        '''CREATE TABLE IF NOT EXISTS external_oauth_states(
          state_hash TEXT PRIMARY KEY CHECK(length(state_hash)=64), provider TEXT NOT NULL REFERENCES external_connections(provider),
          owner_id TEXT NOT NULL REFERENCES users(id), session_hash TEXT NOT NULL CHECK(length(session_hash)=64),
          config_hash TEXT NOT NULL CHECK(length(config_hash)=64), generation INTEGER NOT NULL CHECK(generation>0),
          payload_cipher TEXT NOT NULL CHECK(length(payload_cipher)<=65536),
          expires_at DOUBLE PRECISION NOT NULL, created_at DOUBLE PRECISION NOT NULL)''',
        'CREATE INDEX IF NOT EXISTS external_oauth_provider ON external_oauth_states(provider,expires_at)',
        'CREATE INDEX IF NOT EXISTS external_links_provider ON external_project_links(provider,generation)',
    ]


def ensure_sqlite_schema(office):
    if isinstance(office.db, sqlite3.Connection):
        with office.lock, office.db:
            for statement in schema_statements():
                office.db.execute(statement)


def _digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _identifier(value, *, length=32):
    pattern = _ID if length == 32 else _HASH
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise Problem(400, 'Ungültige Vorgangs-ID oder Prüfsumme')
    return value


def _provider(value):
    if value not in PROVIDERS or not isinstance(value, str):
        raise Problem(400, 'Unbekannte Integration')
    return value


def _opaque(value, maximum=2048):
    if not isinstance(value, str) or not 1 <= len(value) <= maximum or not value.strip() or not value.isprintable():
        raise Problem(400, 'Ungültige externe Kennung')
    return value


def _cipher(value):
    if value is None:
        return None
    if not isinstance(value, str) or not 1 <= len(value) <= MAX_CIPHER_BYTES:
        raise Problem(400, 'Verschlüsselte Verbindungskonfiguration erwartet')
    try:
        raw = base64.b64decode(value.encode('ascii'), altchars=b'-_', validate=True)
    except (ValueError, UnicodeError):
        raise Problem(400, 'Verschlüsselte Verbindungskonfiguration erwartet') from None
    if len(raw) < 73 or raw[0] != 128:
        raise Problem(400, 'Verschlüsselte Verbindungskonfiguration erwartet')
    return value


def _json(value, maximum):
    def check(item, depth=0):
        if depth > 20:
            raise Problem(400, 'Integrationsdaten sind zu tief verschachtelt')
        if isinstance(item, dict):
            for key, child in item.items():
                if (not isinstance(key, str) or not key or len(key) > 200
                        or any(ord(char) < 32 for char in key)
                        or key.casefold() in {'access_token', 'refresh_token', 'client_secret', 'api_token', 'authorization', 'credential', 'config'}):
                    raise Problem(400, 'Zugangsdaten gehören nicht in Projektdaten')
                check(child, depth + 1)
        elif isinstance(item, list):
            if len(item) > MAX_SNAPSHOT_ITEMS:
                raise Problem(400, 'Zu viele Integrationsdatensätze')
            for child in item:
                check(child, depth + 1)
        elif item is not None and type(item) not in (str, int, float, bool):
            raise Problem(400, 'Gültige JSON-Integrationsdaten erwartet')
    check(value)
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        size = len(encoded.encode('utf-8'))
    except (TypeError, ValueError, UnicodeError):
        raise Problem(400, 'Gültige Unicode- und JSON-Integrationsdaten erwartet') from None
    if size > maximum:
        raise Problem(413, 'Integrationsdaten sind zu groß')
    return encoded


def _identity(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) - {'id', 'label', 'drive_id'} or not {'id', 'label'} <= set(value):
        raise Problem(400, 'Bestätigte externe Kontoidentität erwartet')
    result = dict(id=_opaque(value['id']), label=_opaque(value['label'], 500))
    if 'drive_id' in value:
        result['drive_id'] = _opaque(value['drive_id'])
    _json(result, 8192)
    return result


def _instant(value):
    if not isinstance(value, str) or len(value) > 64:
        raise Problem(400, 'Synchronisationszeit mit Zeitzone erwartet')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('timezone')
        return parsed.astimezone(timezone.utc).isoformat(timespec='seconds')
    except (ValueError, OverflowError):
        raise Problem(400, 'Synchronisationszeit mit Zeitzone erwartet') from None


def _integer(value, *, minimum=0):
    if type(value) is not int or value < minimum:
        raise Problem(400, 'Gültige Generation oder Ausgangsversion erwartet')
    return value


def _selection(provider, remote, value):
    remote = _opaque(remote)
    keys = {'sevdesk': {'contact_id', 'offer_ids', 'invoice_ids'},
            'google_calendar': {'calendar_id', 'event_ids'}, 'onedrive': {'folder_id', 'drive_id'}}[provider]
    main = {'sevdesk': 'contact_id', 'google_calendar': 'calendar_id', 'onedrive': 'folder_id'}[provider]
    if not isinstance(value, dict) or set(value) != keys or value[main] != remote:
        raise Problem(400, 'Ausdrückliche Zuordnung der ausgewählten externen Datensätze erwartet')
    result = {main: remote}
    for key in keys - {main}:
        if key == 'drive_id':
            result[key] = _opaque(value[key])
            continue
        items = value[key]
        if not isinstance(items, list) or len(items) > 50:
            raise Problem(400, 'Höchstens 50 ausgewählte Datensätze pro Liste erwartet')
        ids = [_opaque(item) for item in items]
        if len(ids) != len(set(ids)):
            raise Problem(400, 'Externe Kennungen müssen eindeutig sein')
        result[key] = sorted(ids)
    _json(result, 65536)
    return result


def _onedrive_url(value):
    if (not isinstance(value, str) or not 1 <= len(value) <= 8192
            or any(char.isspace() or ord(char) < 32 for char in value)):
        raise Problem(400, 'Gültiger ursprünglicher OneDrive-Link erwartet')
    try:
        url = urlsplit(value)
        host = (url.hostname or '').lower()
        valid = (url.scheme == 'https' and url.username is None and url.password is None and url.port in (None, 443)
                 and (host in ('onedrive.live.com', '1drv.ms') or host.endswith('.sharepoint.com')))
    except ValueError:
        valid = False
    if not valid:
        raise Problem(400, 'Nur ursprüngliche HTTPS-Links von OneDrive oder SharePoint sind erlaubt')
    return value


def _snapshot_payload(provider, selection, payload):
    if not isinstance(payload, dict):
        raise Problem(400, 'Bestätigte externe Projektdaten erwartet')
    encoded = _json(payload, MAX_SNAPSHOT_BYTES)
    if provider == 'sevdesk':
        if set(payload) != {'contact', 'offers', 'invoices'} or not isinstance(payload['contact'], dict):
            raise Problem(400, 'Ausgewählter sevdesk-Kontakt und Dokumente erwartet')
        if payload['contact'].get('id') != selection['contact_id']:
            raise Problem(409, 'Externe Daten gehören zu einem anderen Kontakt')
        lists = [('offers', 'offer_ids', 'offer'), ('invoices', 'invoice_ids', 'invoice')]
        for key, selected, kind in lists:
            items = payload[key]
            if not isinstance(items, list) or any(not isinstance(item, dict) or item.get('kind') != kind for item in items):
                raise Problem(409, 'Es dürfen ausschließlich die ausgewählten sevdesk-Dokumente übernommen werden')
            ids = [_opaque(item.get('id')) for item in items]
            if set(ids) != set(selection[selected]) or len(items) != len(selection[selected]):
                raise Problem(409, 'Es dürfen ausschließlich die ausgewählten sevdesk-Dokumente übernommen werden')
            for item in items:
                if item.get('total_gross') is not None and not isinstance(item['total_gross'], str):
                    raise Problem(400, 'Geldbeträge müssen unveränderte Dezimalzeichenfolgen sein')
    elif provider == 'google_calendar':
        if set(payload) != {'calendar', 'events'} or not isinstance(payload['calendar'], dict):
            raise Problem(400, 'Ausgewählter Kalender und Termine erwartet')
        events = payload['events']
        if (payload['calendar'].get('id') != selection['calendar_id'] or not isinstance(events, list)
                or any(not isinstance(item, dict) for item in events)):
            raise Problem(409, 'Es dürfen ausschließlich die ausgewählten Kalendertermine übernommen werden')
        if {_opaque(item.get('id')) for item in events} != set(selection['event_ids']) or len(events) != len(selection['event_ids']):
            raise Problem(409, 'Es dürfen ausschließlich die ausgewählten Kalendertermine übernommen werden')
    else:
        if set(payload) - {'folder', 'files', 'has_more'} or not {'folder', 'files'} <= set(payload):
            raise Problem(400, 'Ausgewählter OneDrive-Ordner und direkte Dateien erwartet')
        folder = payload['folder']
        if (not isinstance(folder, dict) or set(folder) - {'id', 'drive_id', 'name', 'path', 'url'}
                or not {'id', 'drive_id', 'name', 'path'} <= set(folder)
                or folder['id'] != selection['folder_id'] or folder['drive_id'] != selection['drive_id']):
            raise Problem(409, 'Externe Dateien gehören zu einem anderen Ordner')
        _opaque(folder['name'], 500)
        if not isinstance(folder['path'], str) or len(folder['path']) > 4096 or any(ord(c) < 32 for c in folder['path']):
            raise Problem(400, 'Gültige OneDrive-Ordnermetadaten erwartet')
        if folder.get('url') is not None:
            _onedrive_url(folder['url'])
        files = payload['files']
        if not isinstance(files, list) or len(files) > MAX_SNAPSHOT_ITEMS:
            raise Problem(400, 'Begrenzte OneDrive-Dateiliste erwartet')
        remote_ids = set()
        for item in files:
            if not isinstance(item, dict) or set(item) != {'id', 'drive_id', 'parent_id', 'name', 'path', 'rev', 'size', 'media_type', 'url'}:
                raise Problem(400, 'Gültige OneDrive-Dateimetadaten erwartet')
            remote = _opaque(item.get('id'))
            if item['drive_id'] != selection['drive_id'] or item['parent_id'] != selection['folder_id']:
                raise Problem(409, 'OneDrive-Dateien müssen unmittelbar zum ausgewählten Ordner und Laufwerk gehören')
            _opaque(item['name'], 500)
            _opaque(item.get('rev'))
            _integer(item.get('size'))
            if (not isinstance(item['path'], str) or len(item['path']) > 4096
                    or any(ord(c) < 32 for c in item['path']) or not isinstance(item['media_type'], str)
                    or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+/[!#$%&'*+.^_`|~0-9A-Za-z-]+", item['media_type'])
                    or len(item['media_type']) > 100):
                raise Problem(400, 'Gültige OneDrive-Dateimetadaten erwartet')
            _onedrive_url(item['url'])
            if remote in remote_ids:
                raise Problem(400, 'OneDrive-Dateikennungen müssen eindeutig sein')
            remote_ids.add(remote)
        if 'has_more' in payload and type(payload['has_more']) is not bool:
            raise Problem(400, 'Gültiger OneDrive-Listenstatus erwartet')
    return encoded


class ExternalIntegrations:
    def __init__(self, office, *, clock=time.time):
        self.office, self.db, self.clock = office, office.db, clock
        if isinstance(self.db, sqlite3.Connection) and not self.db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='external_connections'").fetchone():
            if self.db.in_transaction:
                raise RuntimeError('Initialize integration schema before the caller transaction.')
            ensure_sqlite_schema(office)

    def _now(self):
        return datetime.fromtimestamp(self.clock(), timezone.utc).isoformat(timespec='seconds')

    def _fresh(self, actor):
        if not isinstance(actor, dict) or not isinstance(actor.get('id'), str):
            raise Problem(401, 'Bitte anmelden')
        row = self.db.execute('SELECT id,email,role,active FROM users WHERE id=?', (actor['id'],)).fetchone()
        if not row or row['active'] != 1:
            raise Problem(401, 'Bitte anmelden')
        return {key: row[key] for key in ('id', 'email', 'role')}

    def _owner(self, actor):
        actor = self._fresh(actor)
        self.office.require(actor, ('owner',))
        return actor

    def project(self, actor, project_id, provider=None, *, write=False):
        actor = self._fresh(actor)
        project = self.office.project(actor, _identifier(project_id))
        if provider is not None and _provider(provider) == 'sevdesk':
            self.office.require(actor, ('owner', 'accountant'))
        if write:
            self.office.require(actor, ('owner',))
        return project

    def _connection(self, provider):
        provider = _provider(provider)
        row = self.db.execute('SELECT * FROM external_connections WHERE provider=?', (provider,)).fetchone()
        if not row:
            return dict(id=None, provider=provider, owner_id=None, generation=0, state='disconnected',
                        config=None, credential=None, identity=None, config_hash=None, configured=False, connected=False,
                        created_at=None, updated_at=None)
        result = {key: row[key] for key in ('id', 'provider', 'owner_id', 'generation', 'state', 'created_at', 'updated_at')}
        result.update(config=row['config_cipher'], credential=row['credential_cipher'], identity=json.loads(row['identity_json']))
        result.update(config_hash=_digest(result['config']) if result['config'] else None,
                      configured=bool(result['config'] or result['credential']),
                      connected=row['state'] == 'connected')
        return result

    def _usable(self, connection):
        if connection['state'] != 'connected':
            return False
        owner = self.db.execute('SELECT role,active FROM users WHERE id=?', (connection['owner_id'],)).fetchone()
        return bool(owner and owner['active'] == 1 and owner['role'] == 'owner')

    def _connection_view(self, connection):
        result = dict(connection)
        if connection['state'] == 'connected' and not self._usable(connection):
            result.update(state='reauth_required', credential=None, identity=None, connected=False)
        return result

    def connection(self, actor, provider):
        self._owner(actor)
        return self._connection_view(self._connection(provider))

    def project_connection(self, actor, project_id, provider):
        self.project(actor, project_id, provider)
        return self._connection_view(self._connection(provider))

    def _generation(self, connection, generation, *, connected=False):
        if _integer(generation) != connection['generation']:
            raise Problem(409, 'Die Verbindung wurde inzwischen geändert; neu laden')
        if connected and not self._usable(connection):
            raise Problem(409, 'Die Integration muss erneut verbunden werden')

    def _link(self, project_id, provider):
        row = self.db.execute('SELECT * FROM external_project_links WHERE project_id=? AND provider=?',
                              (project_id, provider)).fetchone()
        return dict(row) if row else None

    def _epoch(self, project_id, provider, generation, revision):
        connection = self._connection(provider)
        self._generation(connection, generation, connected=True)
        link = self._link(project_id, provider)
        if (not link or link['active'] != 1 or link['generation'] != generation
                or link['revision'] != _integer(revision, minimum=1)):
            raise Problem(409, 'Die Projektzuordnung wurde inzwischen geändert; neu laden')
        return connection, link

    def _fingerprint(self, provider, operation, project_id, value, request_hash=None):
        if request_hash is not None:
            value = {'semantic_hash': _identifier(request_hash, length=64)}
        return _digest(_json(dict(provider=provider, operation=operation, project_id=project_id, value=value), 262144))

    def _replay(self, actor, provider, operation, project_id, request_id, fingerprint):
        if request_id is None:
            return None
        _identifier(request_id)
        receipt = self.db.execute('SELECT * FROM external_requests WHERE user_id=? AND request_id=?',
                                  (actor['id'], request_id)).fetchone()
        if not receipt:
            return None
        if (receipt['provider'] != provider or receipt['operation'] != operation or receipt['project_id'] != project_id
                or receipt['request_hash'] != fingerprint):
            raise Problem(409, 'Diese Vorgangs-ID wurde bereits für eine andere Änderung verwendet')
        result = json.loads(receipt['result_json'])
        connection = self._connection(provider)
        if connection['id'] != result['connection_id'] or connection['generation'] != result['generation']:
            raise Problem(409, 'Dieser bestätigte Vorgang wurde durch eine neuere Verbindung abgelöst')
        if project_id is None:
            return self._connection_view(connection)
        link = self._link(project_id, provider)
        if not link or link['revision'] != result['revision'] or bool(link['active']) != result['active']:
            raise Problem(409, 'Dieser bestätigte Vorgang wurde durch eine neuere Zuordnung abgelöst')
        return self.binding(actor, project_id, provider, internal=True)

    def _remember(self, actor, provider, operation, project_id, request_id, fingerprint, connection, link=None):
        if request_id is None:
            return
        result = dict(connection_id=connection['id'], generation=connection['generation'])
        if link is not None:
            result.update(revision=link['revision'], active=bool(link['active']))
        self.db.execute('INSERT INTO external_requests(user_id,request_id,provider,operation,project_id,request_hash,result_json,created_at) '
                        'VALUES(?,?,?,?,?,?,?,?)', (actor['id'], request_id, provider, operation, project_id,
                                                   fingerprint, canonical(result), self._now()))

    def _invalidate(self, provider):
        self.db.execute('DELETE FROM external_snapshots WHERE provider=?', (provider,))
        self.db.execute('DELETE FROM external_oauth_states WHERE provider=?', (provider,))
        self.db.execute('UPDATE external_project_links SET error_code=NULL WHERE provider=?', (provider,))

    def put_connection(self, actor, provider, *, config=UNSET, credential=UNSET, identity=UNSET,
                       expected_generation=None, request_id=None, request_hash=None):
        actor, provider = self._owner(actor), _provider(provider)
        if config is UNSET and credential is UNSET and identity is UNSET:
            raise Problem(400, 'Verbindungskonfiguration erwartet')
        current = self._connection(provider)
        values = {key: value for key, value in (('config_cipher', config), ('credential_cipher', credential), ('identity_json', identity))
                  if value is not UNSET}
        fingerprint = self._fingerprint(provider, 'connection', None,
                                        dict(values, expected_generation=expected_generation), request_hash)
        previous = self._replay(actor, provider, 'connection', None, request_id, fingerprint)
        if previous is not None:
            return previous
        if expected_generation is not None:
            self._generation(current, expected_generation)
        if config is not UNSET:
            config = _cipher(config)
            if provider == 'sevdesk' and config is not None:
                raise Problem(400, 'sevdesk verwendet einen geschützten API-Zugang')
        if credential is not UNSET:
            credential = _cipher(credential)
            if credential is not None and identity is UNSET:
                raise Problem(400, 'Neue Zugangsdaten benötigen eine bestätigte Kontoidentität')
        config_changed = config is not UNSET and config != current['config']
        next_config = current['config'] if config is UNSET else config
        next_credential = current['credential'] if credential is UNSET else credential
        next_identity = current['identity'] if identity is UNSET else _identity(identity)
        if config_changed and credential is UNSET:
            next_credential, next_identity = None, None
        if not next_credential:
            next_identity = None
        elif not next_identity or (provider in OAUTH_PROVIDERS and not next_config):
            raise Problem(400, 'Bestätigte Konfiguration und externe Kontoidentität erforderlich')
        state = 'connected' if next_credential else 'configured' if next_config else 'disconnected'
        now = self._now()
        generation = current['generation'] + 1
        self.db.execute('INSERT INTO external_connections(provider,id,owner_id,config_cipher,credential_cipher,identity_json,'
                        'generation,state,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?) '
                        'ON CONFLICT(provider) DO UPDATE SET owner_id=excluded.owner_id,config_cipher=excluded.config_cipher,'
                        'credential_cipher=excluded.credential_cipher,identity_json=excluded.identity_json,generation=excluded.generation,'
                        'state=excluded.state,updated_at=excluded.updated_at',
                        (provider, current['id'] or uuid.uuid4().hex, actor['id'], next_config, next_credential,
                         canonical(next_identity), generation, state, current['created_at'] or now, now))
        self._invalidate(provider)
        self.office.audit(actor, 'integration.connection.saved', provider)
        result = self._connection(provider)
        self._remember(actor, provider, 'connection', None, request_id, fingerprint, result)
        return result

    def disconnect(self, actor, provider, request_id, *, expected_generation=None):
        actor, provider = self._owner(actor), _provider(provider)
        _identifier(request_id)
        fingerprint = self._fingerprint(provider, 'disconnect', None, {'expected_generation': expected_generation})
        previous = self._replay(actor, provider, 'disconnect', None, request_id, fingerprint)
        if previous is not None:
            return previous
        current = self._connection(provider)
        if expected_generation is not None:
            self._generation(current, expected_generation)
        now = self._now()
        self.db.execute('INSERT INTO external_connections(provider,id,owner_id,config_cipher,credential_cipher,identity_json,'
                        'generation,state,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?) '
                        "ON CONFLICT(provider) DO UPDATE SET owner_id=excluded.owner_id,credential_cipher=NULL,identity_json='null',"
                        "generation=excluded.generation,state='disconnected',updated_at=excluded.updated_at",
                        (provider, current['id'] or uuid.uuid4().hex, actor['id'], current['config'], None, 'null',
                         current['generation'] + 1, 'disconnected', current['created_at'] or now, now))
        self._invalidate(provider)
        self.office.audit(actor, 'integration.disconnected', provider)
        result = self._connection(provider)
        self._remember(actor, provider, 'disconnect', None, request_id, fingerprint, result)
        return result

    def refresh_credential(self, actor, provider, credential, *, generation, project_id=None, revision=None):
        if project_id is None:
            self._owner(actor)
            connection = self._connection(provider)
            self._generation(connection, generation, connected=True)
        else:
            self.project(actor, project_id, provider)
            connection, _ = self._epoch(project_id, provider, generation, revision)
        credential = _cipher(credential)
        if credential is None:
            raise Problem(400, 'Verschlüsselte erneuerte Zugangsdaten erwartet')
        self.db.execute('UPDATE external_connections SET credential_cipher=?,updated_at=? WHERE provider=?',
                        (credential, self._now(), provider))
        return self._connection(provider)

    def rotate_bridge_config(self, actor, provider, config, *, generation):
        """Private service API after verifying a same-account bot-key rotation.

        Ciphertext is opaque here. The service must prove that only the bot
        key hash/expiry/bootstrap changes, rather than the provider account.
        """
        actor = self._owner(actor)
        if provider not in ('google_calendar', 'onedrive'):
            raise Problem(400, 'Diese Integration verwendet keinen Botzugang')
        current = self._connection(provider)
        self._generation(current, generation)
        if current['config'] is None:
            raise Problem(409, 'Botverbindung muss zuerst eingerichtet werden')
        if current['owner_id'] != actor['id']:
            raise Problem(403, 'Nur der aktuelle Verbindungsinhaber darf den Botzugang erneuern')
        config = _cipher(config)
        if config is None:
            raise Problem(400, 'Verschlüsselte erneuerte Botkonfiguration erwartet')
        if config != current['config']:
            self.db.execute('UPDATE external_connections SET config_cipher=?,updated_at=? WHERE provider=?',
                            (config, self._now(), provider))
            self.db.execute('DELETE FROM external_oauth_states WHERE provider=?', (provider,))
            self.office.audit(actor, 'integration.bridge_key.rotated', provider)
        return self._connection_view(self._connection(provider))

    def remember_bridge_issue(self, actor, provider, request_id, request_hash):
        """Remember an issued bot-key request without retaining any key material.

        This is a terminal historical marker, not a bootstrap response cache.
        The service may repeat its current encrypted bootstrap response, but an
        older issuance must never rotate a newer key merely because it retries.
        """
        actor = self._owner(actor)
        if provider not in ('google_calendar', 'onedrive'):
            raise Problem(400, 'Diese Integration verwendet keinen Botzugang')
        _identifier(request_id)
        _identifier(request_hash, length=64)
        fingerprint = self._fingerprint(provider, 'connection', None, {}, request_hash)
        current = self._connection(provider)
        if current['config'] is None:
            raise Problem(409, 'Botverbindung muss zuerst eingerichtet werden')
        if current['owner_id'] != actor['id']:
            raise Problem(403, 'Nur der aktuelle Verbindungsinhaber darf die Schlüsselausgabe bestätigen')
        if self.db.execute('SELECT 1 FROM external_requests WHERE user_id=? AND request_id=?',
                           (actor['id'], request_id)).fetchone():
            raise Problem(409, 'Diese Schlüsselausgabe wurde bereits bestätigt')
        self._remember(actor, provider, 'connection', None, request_id, fingerprint, current)
        return {'connection_id': current['id'], 'generation': current['generation']}

    def invalidate_connection(self, actor, provider, *, generation, project_id=None, revision=None):
        if project_id is None:
            actor = self._owner(actor)
            connection = self._connection(provider)
            self._generation(connection, generation)
        else:
            actor = self._fresh(actor)
            self.project(actor, project_id, provider)
            connection, _ = self._epoch(project_id, provider, generation, revision)
        if connection['id'] is None:
            raise Problem(409, 'Integration ist nicht verbunden')
        self.db.execute("UPDATE external_connections SET credential_cipher=NULL,identity_json='null',state='reauth_required',"
                        'generation=generation+1,updated_at=? WHERE provider=?', (self._now(), provider))
        self._invalidate(provider)
        self.office.audit(actor, 'integration.reauthorization_required', provider)
        return self._connection(provider)

    def bind(self, actor, project_id, provider, remote, data, *, generation, revision, request_id):
        actor = self._fresh(actor)
        self.project(actor, project_id, provider, write=True)
        provider = _provider(provider)
        _identifier(request_id)
        selection = _selection(provider, remote, data)
        fingerprint = self._fingerprint(provider, 'bind', project_id,
                                        dict(remote=remote, data=selection, generation=generation, revision=revision))
        previous = self._replay(actor, provider, 'bind', project_id, request_id, fingerprint)
        if previous is not None:
            return previous
        connection = self._connection(provider)
        self._generation(connection, generation, connected=True)
        current = self._link(project_id, provider)
        if _integer(revision) != (current['revision'] if current else 0):
            raise Problem(409, 'Die Projektzuordnung wurde inzwischen geändert; neu laden')
        self.db.execute('INSERT INTO external_project_links(project_id,provider,remote,selection_json,active,revision,generation,'
                        'updated_by,updated_at,error_code) VALUES(?,?,?,?,?,?,?,?,?,NULL) '
                        'ON CONFLICT(project_id,provider) DO UPDATE SET remote=excluded.remote,selection_json=excluded.selection_json,'
                        'active=1,revision=excluded.revision,generation=excluded.generation,updated_by=excluded.updated_by,'
                        'updated_at=excluded.updated_at,error_code=NULL',
                        (project_id, provider, remote, canonical(selection), 1, revision + 1, generation, actor['id'], self._now()))
        self.db.execute('DELETE FROM external_snapshots WHERE project_id=? AND provider=?', (project_id, provider))
        self.office.audit(actor, 'integration.project.linked', project_id)
        self._remember(actor, provider, 'bind', project_id, request_id, fingerprint, connection, self._link(project_id, provider))
        return self.binding(actor, project_id, provider, internal=True)

    def unlink(self, actor, project_id, provider, *, generation, revision, request_id):
        actor = self._fresh(actor)
        self.project(actor, project_id, provider, write=True)
        provider = _provider(provider)
        _identifier(request_id)
        fingerprint = self._fingerprint(provider, 'unlink', project_id, dict(generation=generation, revision=revision))
        previous = self._replay(actor, provider, 'unlink', project_id, request_id, fingerprint)
        if previous is not None:
            return previous
        connection = self._connection(provider)
        self._generation(connection, generation)
        current = self._link(project_id, provider)
        if not current or _integer(revision, minimum=1) != current['revision']:
            raise Problem(409, 'Die Projektzuordnung wurde inzwischen geändert; neu laden')
        self.db.execute("UPDATE external_project_links SET remote=NULL,selection_json='{}',active=0,revision=revision+1,"
                        'generation=?,updated_by=?,updated_at=?,error_code=NULL WHERE project_id=? AND provider=?',
                        (generation, actor['id'], self._now(), project_id, provider))
        self.db.execute('DELETE FROM external_snapshots WHERE project_id=? AND provider=?', (project_id, provider))
        self.office.audit(actor, 'integration.project.unlinked', project_id)
        self._remember(actor, provider, 'unlink', project_id, request_id, fingerprint, connection, self._link(project_id, provider))
        return self.binding(actor, project_id, provider, internal=True)

    def binding(self, actor, project_id, provider, *, internal=False):
        self.project(actor, project_id, provider)
        connection = self._connection(provider)
        link = self._link(project_id, provider)
        if link is None:
            return None
        current = bool(link['active'] and link['generation'] == connection['generation'] and self._usable(connection))
        state = ('unlinked' if not link['active'] else 'stale' if link['generation'] != connection['generation']
                 else 'reauth_required' if not self._usable(connection) else 'linked')
        result = dict(project_id=project_id, provider=provider, revision=link['revision'], generation=link['generation'],
                      connection_generation=connection['generation'], active=bool(link['active']), state=state,
                      remote=link['remote'] if current else None,
                      data=json.loads(link['selection_json']) if current else None, error=link['error_code'] if current else None)
        if internal:
            result['connection'] = self._connection_view(connection)
        return result

    def save_snapshot(self, actor, project_id, provider, payload, *, generation, revision, synced_at):
        self.project(actor, project_id, provider)
        _, link = self._epoch(project_id, provider, generation, revision)
        encoded = _snapshot_payload(provider, json.loads(link['selection_json']), payload)
        synced_at = _instant(synced_at)
        self.db.execute('INSERT INTO external_snapshots(project_id,provider,generation,revision,payload_json,payload_sha256,synced_at) '
                        'VALUES(?,?,?,?,?,?,?) ON CONFLICT(project_id,provider) DO UPDATE SET generation=excluded.generation,'
                        'revision=excluded.revision,payload_json=excluded.payload_json,payload_sha256=excluded.payload_sha256,'
                        'synced_at=excluded.synced_at', (project_id, provider, generation, revision, encoded, _digest(encoded), synced_at))
        self.db.execute('UPDATE external_project_links SET error_code=NULL WHERE project_id=? AND provider=?', (project_id, provider))
        return self.snapshot(actor, project_id, provider)

    def record_error(self, actor, project_id, provider, error_code, *, generation, revision):
        self.project(actor, project_id, provider)
        self._epoch(project_id, provider, generation, revision)
        if error_code not in ERROR_CODES:
            raise Problem(400, 'Gültiger sicherer Integrationsfehler erwartet')
        self.db.execute('UPDATE external_project_links SET error_code=? WHERE project_id=? AND provider=?',
                        (error_code, project_id, provider))
        return self.snapshot(actor, project_id, provider)

    def snapshot(self, actor, project_id, provider):
        binding = self.binding(actor, project_id, provider)
        result = dict(binding=binding, data=None, synced_at=None, state=binding['state'] if binding else 'unlinked', error=None)
        if binding is None or binding['state'] != 'linked':
            return result
        row = self.db.execute('SELECT * FROM external_snapshots WHERE project_id=? AND provider=?', (project_id, provider)).fetchone()
        error = binding['error']
        result['error'] = error
        if row and row['generation'] == binding['generation'] and row['revision'] == binding['revision']:
            if _digest(row['payload_json']) != row['payload_sha256']:
                raise ValueError('Stored integration snapshot hash mismatch')
            payload = json.loads(row['payload_json'])
            _snapshot_payload(provider, binding['data'], payload)
            result.update(data=payload, synced_at=row['synced_at'], state='stale' if error else 'synced')
        elif error:
            result['state'] = 'error'
        return result

    def put_oauth(self, actor, provider, *, state_hash, session_hash, config_hash, payload, generation, expires_at):
        actor = self._owner(actor)
        if provider not in OAUTH_PROVIDERS:
            raise Problem(400, 'Diese Integration verwendet keine OAuth-Anmeldung')
        for value in (state_hash, session_hash, config_hash):
            _identifier(value, length=64)
        payload = _cipher(payload)
        if payload is None:
            raise Problem(400, 'Verschlüsselter OAuth-Vorgang erwartet')
        connection = self._connection(provider)
        self._generation(connection, generation)
        if connection['config_hash'] is None or connection['config_hash'] != config_hash:
            raise Problem(409, 'OAuth-Konfiguration wurde inzwischen geändert')
        now = self.clock()
        if type(expires_at) not in (float, int) or not math.isfinite(expires_at) or not now < expires_at <= now + OAUTH_TTL_SECONDS:
            raise Problem(400, 'OAuth-Anmeldung darf höchstens zehn Minuten offen bleiben')
        session = self.db.execute('SELECT user_id,expiry FROM sessions WHERE token=?', (session_hash,)).fetchone()
        if not session or session['user_id'] != actor['id'] or session['expiry'] <= now:
            raise Problem(401, 'OAuth-Anmeldung benötigt eine aktive Sitzung')
        self.db.execute('DELETE FROM external_oauth_states WHERE expires_at<=?', (now,))
        if self.db.execute('SELECT COUNT(*) FROM external_oauth_states WHERE provider=?', (provider,)).fetchone()[0] >= MAX_OAUTH_STATES:
            raise Problem(429, 'Zu viele offene Integrationsanmeldungen')
        if self.db.execute('SELECT 1 FROM external_oauth_states WHERE state_hash=?', (state_hash,)).fetchone():
            raise Problem(409, 'OAuth-Vorgang existiert bereits')
        self.db.execute('INSERT INTO external_oauth_states(state_hash,provider,owner_id,session_hash,config_hash,generation,'
                        'payload_cipher,expires_at,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                        (state_hash, provider, actor['id'], session_hash, config_hash, generation, payload, expires_at, now))
        return dict(state_hash=state_hash, provider=provider, generation=generation, expires_at=expires_at)

    def consume_oauth(self, state_hash):
        _identifier(state_hash, length=64)
        row = self.db.execute('SELECT * FROM external_oauth_states WHERE state_hash=?', (state_hash,)).fetchone()
        if not row:
            raise Problem(400, 'Integrationsanmeldung abgelaufen oder bereits verwendet')
        self.db.execute('DELETE FROM external_oauth_states WHERE state_hash=?', (state_hash,))
        connection = self._connection(row['provider'])
        session = self.db.execute('SELECT u.id,u.email,u.role,u.active,s.expiry FROM users u '
                                  'JOIN sessions s ON s.user_id=u.id WHERE s.token=?', (row['session_hash'],)).fetchone()
        valid = bool(row['expires_at'] > self.clock() and session and session['id'] == row['owner_id']
                     and session['active'] == 1 and session['role'] == 'owner' and session['expiry'] > self.clock()
                     and row['generation'] == connection['generation'] and row['config_hash'] == connection['config_hash'])
        result = {key: row[key] for key in ('state_hash', 'provider', 'owner_id', 'session_hash', 'config_hash', 'generation', 'expires_at', 'created_at')}
        result.update(valid=valid, actor={key: session[key] for key in ('id', 'email', 'role')} if valid else None,
                      connection=connection if valid else None, payload=row['payload_cipher'] if valid else None)
        return result


def sanitize_after_restore(office):
    """Explicit disaster restore only, after validation; never a normal clone."""
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    office.db.execute('DELETE FROM external_oauth_states')
    office.db.execute('DELETE FROM external_snapshots')
    office.db.execute("UPDATE external_connections SET config_cipher=NULL,credential_cipher=NULL,identity_json='null',"
                      "state='disconnected',generation=generation+1,updated_at=?", (now,))
    office.db.execute("UPDATE external_project_links SET remote=NULL,selection_json='{}',active=0,revision=revision+1,"
                      'generation=(SELECT generation FROM external_connections c WHERE c.provider=external_project_links.provider),'
                      'updated_at=?,error_code=NULL', (now,))


def validate_integrity(office):
    """Validate current snapshots and immutable retry references without decrypting."""
    domain = ExternalIntegrations(office)
    try:
        connections = {}
        for row in office.db.execute('SELECT * FROM external_connections').fetchall():
            provider = _provider(row['provider'])
            _identifier(row['id'])
            _integer(row['generation'], minimum=1)
            _cipher(row['config_cipher'])
            _cipher(row['credential_cipher'])
            identity = _identity(json.loads(row['identity_json']))
            if not office.db.execute('SELECT 1 FROM users WHERE id=?', (row['owner_id'],)).fetchone():
                raise ValueError('Missing integration owner')
            if (row['state'] == 'connected' and (not row['credential_cipher'] or not identity
                    or (provider in OAUTH_PROVIDERS and not row['config_cipher']))):
                raise ValueError('Connected integration has no valid delegation')
            if row['state'] != 'connected' and (row['credential_cipher'] is not None or identity is not None):
                raise ValueError('Disconnected integration retains active credentials')
            if row['state'] not in ('connected', 'configured', 'disconnected', 'reauth_required'):
                raise ValueError('Invalid integration state')
            for key in ('created_at', 'updated_at'):
                _instant(row[key])
            connections[provider] = row
        links = {}
        for row in office.db.execute('SELECT * FROM external_project_links').fetchall():
            _identifier(row['project_id'])
            connection = connections.get(row['provider'])
            if not connection or row['generation'] > connection['generation']:
                raise ValueError('Invalid integration link generation')
            _integer(row['generation'], minimum=1)
            _integer(row['revision'], minimum=1)
            _instant(row['updated_at'])
            if (not office.db.execute('SELECT 1 FROM projects WHERE id=?', (row['project_id'],)).fetchone()
                    or not office.db.execute('SELECT 1 FROM users WHERE id=?', (row['updated_by'],)).fetchone()):
                raise ValueError('Integration link has no project or author')
            value = json.loads(row['selection_json'])
            if row['active'] == 1:
                if _selection(row['provider'], row['remote'], value) != value:
                    raise ValueError('Noncanonical integration selection')
            elif row['active'] != 0 or row['remote'] is not None or value != {} or row['error_code'] is not None:
                raise ValueError('Unlinked integration retains a selection')
            if row['error_code'] is not None and row['error_code'] not in ERROR_CODES:
                raise ValueError('Unsafe integration error')
            links[(row['project_id'], row['provider'])] = row
        for row in office.db.execute('SELECT * FROM external_snapshots').fetchall():
            link = links.get((row['project_id'], row['provider']))
            connection = connections.get(row['provider'])
            if (not link or not connection or not link['active'] or connection['state'] != 'connected'
                    or row['generation'] != connection['generation'] or row['generation'] != link['generation']
                    or row['revision'] != link['revision']):
                raise ValueError('Stale integration snapshot survived its link epoch')
            if _digest(row['payload_json']) != row['payload_sha256']:
                raise ValueError('Integration snapshot checksum mismatch')
            _snapshot_payload(row['provider'], json.loads(link['selection_json']), json.loads(row['payload_json']))
            _instant(row['synced_at'])
        for row in office.db.execute('SELECT * FROM external_requests').fetchall():
            _identifier(row['request_id'])
            _identifier(row['request_hash'], length=64)
            _instant(row['created_at'])
            connection = connections.get(row['provider'])
            result = json.loads(row['result_json'])
            expected = {'connection_id', 'generation'} | ({'revision', 'active'} if row['project_id'] is not None else set())
            if (not isinstance(result, dict) or set(result) != expected or not connection
                    or result['connection_id'] != connection['id'] or type(result['generation']) is not int
                    or not 1 <= result['generation'] <= connection['generation']
                    or not office.db.execute('SELECT 1 FROM users WHERE id=?', (row['user_id'],)).fetchone()):
                raise ValueError('Invalid integration request receipt')
            if row['project_id'] is None:
                if row['operation'] not in ('connection', 'disconnect'):
                    raise ValueError('Invalid connection receipt operation')
            else:
                link = links.get((row['project_id'], row['provider']))
                if (row['operation'] not in ('bind', 'unlink') or not link or type(result['active']) is not bool
                        or type(result['revision']) is not int or not 1 <= result['revision'] <= link['revision']):
                    raise ValueError('Invalid project binding receipt')
        for row in office.db.execute('SELECT * FROM external_oauth_states').fetchall():
            for key in ('state_hash', 'session_hash', 'config_hash'):
                _identifier(row[key], length=64)
            _cipher(row['payload_cipher'])
            connection = connections.get(row['provider'])
            if (row['provider'] not in OAUTH_PROVIDERS or not connection or row['generation'] != connection['generation']
                    or not connection['config_cipher'] or row['config_hash'] != _digest(connection['config_cipher'])
                    or not office.db.execute('SELECT 1 FROM users WHERE id=?', (row['owner_id'],)).fetchone()
                    or any(type(row[key]) not in (float, int) or not math.isfinite(row[key]) for key in ('expires_at', 'created_at'))
                    or not 0 < row['expires_at'] - row['created_at'] <= OAUTH_TTL_SECONDS):
                raise ValueError('Invalid pending integration OAuth state')
    except (Problem, TypeError, KeyError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid canonical external integration data') from error
    return True
