"""Optional personal OneDrive connector for the shared PostgreSQL service.

Microsoft credentials stay on the server. External requests never hold Office's
transaction lock; a separate PostgreSQL session lock serializes this connector
across Gunicorn workers without blocking unrelated application requests.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import base64

from cryptography.fernet import Fernet, InvalidToken
import psycopg

from core import Problem, canonical, digest


GRAPH = 'https://graph.microsoft.com/v1.0'
LOGIN = 'https://login.microsoftonline.com/consumers/oauth2/v2.0'
SCOPES = 'offline_access Files.ReadWrite.AppFolder'
TOKEN_NAME = 'onedrive'
STATE_PREFIX = 'onedrive.oauth.'
FOLDER_PREFIX = 'onedrive.folder.'
OPERATION_LOCK_ID = 741290519  # Deliberately distinct from online.store.LOCK_ID.
RECONNECT = 'Microsoft-Anmeldung abgelaufen oder widerrufen. OneDrive bitte erneut verbinden.'
NETWORK_TIMEOUT = 'Microsoft antwortet nicht rechtzeitig. Bitte später erneut versuchen.'
_operation_deadline = ContextVar('smartplan_onedrive_deadline', default=None)


class _ReconnectRequired(Exception):
    pass


class _NotFound(Exception):
    pass


class _Conflict(Exception):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        # Never forward a bearer token or confidential form to another endpoint.
        return None


class OnlineOneDrive:
    def __init__(self, office, key, host, *, client_id=None, client_secret=None):
        self.office = office
        self.vault = Fernet(key)
        if not re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)+', host):
            raise RuntimeError('Gültiger öffentlicher Hostname erforderlich.')
        self.redirect = f'https://{host}/api/v1/storage/callback'
        self.client_id = (os.environ.get('MS_CLIENT_ID', '') if client_id is None else client_id).strip()
        if client_secret is None:
            secret_file = os.environ.get('SMARTPLAN_MS_CLIENT_SECRET_FILE', '')
            if secret_file:
                try:
                    with Path(secret_file).open('r', encoding='utf-8') as stream:
                        client_secret = stream.read(8193).strip()
                    if len(client_secret) > 8192:
                        raise ValueError('oversized secret')
                except (OSError, UnicodeError, ValueError):
                    raise RuntimeError('Geschützte Microsoft-Konfiguration kann nicht gelesen werden.') from None
            else:
                client_secret = ''
        self.secret = client_secret.strip()

    def configured(self):
        return bool(self.client_id and self.secret)

    def _configured(self):
        if not self.configured():
            raise Problem(409, 'Microsoft-App für OneDrive noch nicht eingerichtet.')

    def _authorize(self, token, roles=('owner',)):
        actor = self.office.user(token)
        self.office.require(actor, roles)
        return actor

    def _encrypt(self, value):
        return self.vault.encrypt(canonical(value).encode()).decode()

    def _decrypt(self, value):
        try:
            result = json.loads(self.vault.decrypt(value.encode()))
            if not isinstance(result, dict):
                raise ValueError('object required')
            return result
        except (InvalidToken, ValueError, TypeError, AttributeError, UnicodeError):
            raise Problem(409, 'Gespeicherte Microsoft-Anmeldung bitte erneut einrichten.') from None

    def _row(self, name):
        return self.office.db.execute('SELECT value FROM secrets WHERE name=?', (name,)).fetchone()

    def _save(self, name, value):
        self.office.db.execute(
            'INSERT INTO secrets VALUES(?,?) ON CONFLICT(name) DO UPDATE SET value=excluded.value',
            (name, self._encrypt(value)),
        )

    def status(self, token):
        with self.office.lock, self.office.db:
            self._authorize(token)
            row = self._row(TOKEN_NAME)
            connected = False
            if row and self.configured():
                try:
                    value = self._decrypt(row[0])
                    connected = bool(value.get('refresh_token') and value.get('access_token') and
                                     value.get('client_id', self.client_id) == self.client_id)
                except Problem:
                    pass
        return {'configured': self.configured(), 'connected': connected,
                'account_type': 'personal', 'scope': SCOPES}

    @contextmanager
    def _operation(self):
        deadline_token = _operation_deadline.set(time.monotonic() + 18)
        connection = None
        acquired = False
        try:
            try:
                self._remaining()
                connection = psycopg.connect(self.office.db.dsn, autocommit=True, connect_timeout=5,
                                             options='-c statement_timeout=5000')
                self._remaining()
                acquired = connection.execute('SELECT pg_try_advisory_lock(%s)', (OPERATION_LOCK_ID,)).fetchone()[0]
            except psycopg.Error:
                self._remaining()
                raise Problem(503, 'OneDrive-Verbindung derzeit nicht verfügbar.') from None
            if not acquired:
                raise Problem(409, 'Eine OneDrive-Aktion läuft bereits. Bitte kurz warten und erneut versuchen.')
            self._remaining()
            yield
        finally:
            if (acquired and connection is not None and not connection.closed and
                    time.monotonic() < _operation_deadline.get()):
                try:
                    connection.execute('SELECT pg_advisory_unlock(%s)', (OPERATION_LOCK_ID,))
                except psycopg.Error:
                    pass
            if connection is not None:
                connection.close()  # Closing also releases an expired session lock.
            _operation_deadline.reset(deadline_token)

    @staticmethod
    def _remaining(deadline=None):
        deadline = _operation_deadline.get() if deadline is None else deadline
        remaining = deadline - time.monotonic() if deadline is not None else 18
        if remaining <= 0:
            raise Problem(504, NETWORK_TIMEOUT)
        return remaining

    def begin(self, token):
        self._configured()
        state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        with self.office.lock, self.office.db:
            actor = self._authorize(token)
            rows = self.office.db.execute('SELECT name,value FROM secrets WHERE name LIKE ?',
                                          (STATE_PREFIX + '%',)).fetchall()
            live = 0
            for row in rows:
                try:
                    expired = self._decrypt(row['value']).get('expires_at', 0) <= time.time()
                except (Problem, TypeError):
                    expired = True
                if expired:
                    self.office.db.execute('DELETE FROM secrets WHERE name=?', (row['name'],))
                else:
                    live += 1
            if live >= 20:
                raise Problem(429, 'Zu viele offene Microsoft-Anmeldungen. Bitte später erneut versuchen.')
            self._save(STATE_PREFIX + digest(state), {
                'owner_id': actor['id'], 'session': digest(token), 'verifier': verifier,
                'expires_at': time.time() + 600, 'client_id': self.client_id, 'redirect': self.redirect,
            })
        return LOGIN + '/authorize?' + urllib.parse.urlencode({
            'client_id': self.client_id, 'response_type': 'code', 'redirect_uri': self.redirect,
            'response_mode': 'form_post', 'scope': SCOPES, 'state': state,
            'code_challenge': challenge, 'code_challenge_method': 'S256', 'prompt': 'select_account',
        })

    def _callback_actor(self, pending):
        actor = self.office.db.execute(
            'SELECT u.id,u.email,u.role FROM users u JOIN sessions s ON u.id=s.user_id '
            'WHERE s.token=? AND s.expiry>? AND u.active=1',
            (pending.get('session'), time.time()),
        ).fetchone()
        if not actor or actor['id'] != pending.get('owner_id') or actor['role'] != 'owner':
            raise Problem(403, 'Berechtigung zur Microsoft-Verbindung nicht mehr gültig.')
        return actor

    def callback(self, state, code, error=None):
        self._configured()
        if not isinstance(state, str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,200}', state):
            raise Problem(400, 'Microsoft-Anmeldung ungültig oder abgelaufen.')
        with self._operation():
            with self.office.lock, self.office.db:
                name = STATE_PREFIX + digest(state)
                row = self._row(name)
                if not row:
                    raise Problem(400, 'Microsoft-Anmeldung abgelaufen oder bereits verwendet.')
                self.office.db.execute('DELETE FROM secrets WHERE name=?', (name,))
                # Consume first, in its own committed transaction, including
                # cancellation and expired credentials. No replay after failure.
                encrypted_pending = row[0]
            pending = self._decrypt(encrypted_pending)
            expiry = pending.get('expires_at')
            if (type(expiry) not in (int, float) or not math.isfinite(expiry) or expiry <= time.time() or
                    pending.get('client_id') != self.client_id or pending.get('redirect') != self.redirect or
                    not isinstance(pending.get('verifier'), str)):
                raise Problem(400, 'Microsoft-Anmeldung ungültig oder abgelaufen.')
            with self.office.lock, self.office.db:
                self._callback_actor(pending)
            if error:
                raise Problem(400, 'Microsoft-Anmeldung wurde nicht abgeschlossen. Bitte erneut verbinden.')
            if not isinstance(code, str) or not code or len(code) > 8192:
                raise Problem(400, 'Microsoft-Anmeldung unvollständig. Bitte erneut verbinden.')
            try:
                value = self._token_request({'grant_type': 'authorization_code', 'code': code,
                                             'code_verifier': pending['verifier'], 'redirect_uri': self.redirect})
                tokens = self._tokens(value)
            except _ReconnectRequired:
                raise Problem(409, RECONNECT) from None
            with self.office.lock, self.office.db:
                actor = self._callback_actor(pending)
                self._save(TOKEN_NAME, tokens)
                self.office.audit(actor, 'onedrive.connected', 'personal')

    def request(self, url, method='GET', data=None, headers=None):
        request = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
        deadline = _operation_deadline.get()
        if deadline is None:
            deadline = time.monotonic() + 18
        try:
            opener = urllib.request.build_opener(_NoRedirect())
            with opener.open(request, timeout=min(8, self._remaining(deadline))) as response:
                body = self._read_response(response, 1_000_000, deadline)
            value = json.loads(body)
            self._remaining(deadline)
            if not isinstance(value, dict):
                raise ValueError('object required')
            return value
        except urllib.error.HTTPError as error:
            try:
                value = json.loads(self._read_response(error, 8192, deadline))
            except TimeoutError:
                raise Problem(504, NETWORK_TIMEOUT) from None
            except (ValueError, OSError):
                value = {}
            finally:
                error.close()
            if error.code == 401 or (isinstance(value, dict) and value.get('error') == 'invalid_grant'):
                raise _ReconnectRequired() from None
            if url.startswith(GRAPH + '/'):
                if error.code == 404:
                    raise _NotFound() from None
                if error.code == 409:
                    raise _Conflict() from None
            raise Problem(502, 'Microsoft-Anfrage fehlgeschlagen. Bitte später erneut versuchen.') from None
        except TimeoutError:
            raise Problem(504, NETWORK_TIMEOUT) from None
        except urllib.error.URLError as error:
            self._remaining(deadline)
            if isinstance(error.reason, TimeoutError):
                raise Problem(504, NETWORK_TIMEOUT) from None
            raise Problem(502, 'Microsoft-Verbindung fehlgeschlagen. Bitte später erneut versuchen.') from None
        except (OSError, ValueError):
            self._remaining(deadline)
            raise Problem(502, 'Microsoft-Verbindung fehlgeschlagen. Bitte später erneut versuchen.') from None

    def _read_response(self, response, limit, deadline):
        chunks, count = [], 0
        read = getattr(response, 'read1', response.read)
        while True:
            remaining = self._remaining(deadline)
            # Real urllib HTTPResponse supports read1, which returns available
            # bytes without waiting to fill a large buffer. Shrink the underlying
            # socket timeout as the shared operation budget runs down so a slow
            # response cannot reset an eight-second timeout on every packet.
            stream = response
            for _ in range(6):
                socket = getattr(stream, '_sock', None)
                if socket is not None:
                    socket.settimeout(min(8, remaining))
                    break
                stream = getattr(stream, 'fp', None) or getattr(stream, 'raw', None)
                if stream is None:
                    break
            chunk = read(min(65536, limit + 1 - count))
            self._remaining(deadline)
            if not chunk:
                break
            chunks.append(chunk)
            count += len(chunk)
            if count > limit:
                raise ValueError('response too large')
        return b''.join(chunks)

    def _token_request(self, values):
        form = dict(values, client_id=self.client_id, client_secret=self.secret, scope=SCOPES)
        return self.request(LOGIN + '/token', 'POST', urllib.parse.urlencode(form).encode(),
                            {'Content-Type': 'application/x-www-form-urlencoded'})

    def _tokens(self, value, previous=None):
        if isinstance(value, dict) and value.get('error') == 'invalid_grant':
            raise _ReconnectRequired()
        if not isinstance(value, dict) or value.get('error'):
            raise Problem(502, 'Microsoft lieferte keine gültige Anmeldung.')
        access = value.get('access_token')
        refresh = value.get('refresh_token') or (previous or {}).get('refresh_token')
        expires = value.get('expires_in')
        if (not isinstance(access, str) or not 1 <= len(access) <= 20000 or
                not isinstance(refresh, str) or not 1 <= len(refresh) <= 20000 or
                any(ord(character) <= 32 or ord(character) > 126 for character in access + refresh) or
                str(value.get('token_type', 'Bearer')).lower() != 'bearer' or
                type(expires) is not int or not 1 <= expires <= 86400):
            raise Problem(502, 'Microsoft lieferte keine gültige Anmeldung.')
        return {'access_token': access, 'refresh_token': refresh, 'expires_at': time.time() + expires,
                'client_id': self.client_id}

    def _forget_tokens(self):
        with self.office.lock, self.office.db:
            self.office.db.execute('DELETE FROM secrets WHERE name=?', (TOKEN_NAME,))

    def _access_token(self, token):
        with self.office.lock, self.office.db:
            self._authorize(token, ('owner', 'manager'))
            row = self._row(TOKEN_NAME)
            if not row:
                raise Problem(409, 'OneDrive noch nicht verbunden.')
            tokens = self._decrypt(row[0])
        expiry = tokens.get('expires_at')
        if (tokens.get('client_id', self.client_id) != self.client_id or
                not isinstance(tokens.get('access_token'), str) or not tokens['access_token'] or
                not isinstance(tokens.get('refresh_token'), str) or not tokens['refresh_token'] or
                type(expiry) not in (int, float) or not math.isfinite(expiry)):
            raise Problem(409, RECONNECT)
        if expiry < time.time() + 60:
            value = self._token_request({'grant_type': 'refresh_token', 'refresh_token': tokens['refresh_token']})
            tokens = self._tokens(value, tokens)
            with self.office.lock, self.office.db:
                self._authorize(token, ('owner', 'manager'))
                self._save(TOKEN_NAME, tokens)
        return tokens['access_token']

    def _report(self, token, report_id):
        actor = self._authorize(token, ('owner', 'manager'))
        report = self.office.report(actor, report_id)
        if report['status'] != 'signed':
            raise Problem(409, 'Zunächst Dokument unterzeichnen.')
        return actor, report, self.office.pdf(actor, report_id)

    @staticmethod
    def _item_id(value):
        item_id = value.get('id') if isinstance(value, dict) else None
        if not isinstance(item_id, str) or not 1 <= len(item_id) <= 1024:
            raise Problem(502, 'Microsoft lieferte keine gültige Dateibestätigung.')
        return item_id

    @staticmethod
    def _folder_name(project):
        # The complete ID makes names unique even for identically named projects.
        # The prefix avoids reserved device names; strip OneDrive's forbidden
        # filename characters and keep a comfortable margin below its name limit.
        label = ''.join(' ' if ord(character) < 32 or character in '\\/:*?"<>|' else character
                        for character in project['name'])
        label = ' '.join(label.split()).strip(' .')[:80].rstrip(' .')
        return ('Projekt - ' + label + ' - ' if label else 'Projekt - ') + project['id']

    def _project_folder(self, token, report_id, root_id, headers):
        with self.office.lock, self.office.db:
            actor = self._authorize(token, ('owner', 'manager'))
            report = self.office.report(actor, report_id)
            project = self.office.project(actor, report['content']['project_id'])
            mapping_key = FOLDER_PREFIX + digest(canonical([root_id, project['id']]))
            row = self._row(mapping_key)
            if row:
                mapping = self._decrypt(row[0])
                name = mapping.get('name')
                if (mapping.get('root_id') != root_id or mapping.get('project_id') != project['id'] or
                        not isinstance(name, str) or not 1 <= len(name) <= 160 or
                        name in ('.', '..') or any(ord(c) < 32 or c in '\\/:*?"<>|' for c in name)):
                    raise Problem(409, 'Gespeicherter OneDrive-Projektordner muss geprüft werden.')
            else:
                name = self._folder_name(project)
        # Resolve by a path directly beneath the app folder, never an arbitrary
        # saved drive item ID. A folder moved outside the app area is not reused.
        root = GRAPH + '/me/drive/items/' + urllib.parse.quote(root_id, safe='')
        location = root + ':/' + urllib.parse.quote(name, safe='')
        try:
            folder = self.request(location, headers=headers)
        except _NotFound:
            body = canonical({'name': name, 'folder': {}, '@microsoft.graph.conflictBehavior': 'fail'}).encode()
            # An existing folder must be reused, never silently renamed to a
            # second project folder by Graph's default conflict behaviour.
            try:
                folder = self.request(root + '/children', 'POST', body,
                                      {**headers, 'Content-Type': 'application/json'})
            except _Conflict:
                folder = self.request(location, headers=headers)
        folder_id = self._item_id(folder)
        if not isinstance(folder.get('folder'), dict):
            raise Problem(409, 'Das OneDrive-Ziel ist kein Projektordner. Bitte die Ablage prüfen.')
        with self.office.lock, self.office.db:
            actor = self._authorize(token, ('owner', 'manager'))
            self.office.report(actor, report_id)
            # Persist before the PDF PUT: retrying a failed upload after an
            # Office project rename still uses the original project folder.
            self._save(mapping_key, {'root_id': root_id, 'project_id': project['id'], 'name': name})
        return folder_id

    def upload_report(self, token, report_id):
        with self.office.lock, self.office.db:
            self._report(token, report_id)
        self._configured()
        with self._operation():
            try:
                access = self._access_token(token)
                headers = {'Authorization': 'Bearer ' + access}
                folder = self.request(GRAPH + '/me/drive/special/approot', headers=headers)
                root_id = self._item_id(folder)
                folder_id = self._project_folder(token, report_id, root_id, headers)
                with self.office.lock, self.office.db:
                    _, report, data = self._report(token, report_id)
                name = report['content']['project_id'] + '_' + report_id + '.pdf'
                url = (GRAPH + '/me/drive/items/' + urllib.parse.quote(folder_id, safe='') + ':/' +
                       urllib.parse.quote(name, safe='') + ':/content')
                result = self.request(url, 'PUT', data, {**headers, 'Content-Type': 'application/pdf'})
                item_id = self._item_id(result)
                with self.office.lock, self.office.db:
                    actor, _, current_pdf = self._report(token, report_id)
                    if data != current_pdf:
                        raise Problem(409, 'Dokumentinhalt hat sich geändert. Bitte erneut prüfen.')
                    self.office.db.execute('UPDATE reports SET onedrive_id=? WHERE id=?', (item_id, report_id))
                    self.office.audit(actor, 'onedrive.uploaded', report_id)
                return {'uploaded': True, 'item_id': item_id}
            except _ReconnectRequired:
                self._forget_tokens()
                raise Problem(409, RECONNECT) from None
            except (_NotFound, _Conflict):
                raise Problem(502, 'OneDrive-Projektordner derzeit nicht verfügbar. Bitte erneut versuchen.') from None

    def disconnect(self, token):
        with self.office.lock, self.office.db:
            self._authorize(token)
        with self._operation():
            with self.office.lock, self.office.db:
                actor = self._authorize(token)
                self.office.db.execute('DELETE FROM secrets WHERE name=? OR name LIKE ?',
                                       (TOKEN_NAME, STATE_PREFIX + '%'))
                self.office.audit(actor, 'onedrive.disconnected', 'personal')
        return {'ok': True, 'connected': False}
