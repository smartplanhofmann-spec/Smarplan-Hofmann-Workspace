"""Workspace document destinations, independent of the API/database host."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import time

from cryptography.fernet import Fernet, InvalidToken
import psycopg

from core import Problem, canonical
from online.onedrive_connector import OnlineOneDrive
from online.storage_backends import ServerStorage, WebDavStorage


OPERATION_LOCK = 741290528
SETTINGS = 'storage.settings'
PROVIDERS = {'none', 'server', 'onedrive', 'webdav'}


def load_config():
    """Only an administrator-controlled file can define network/disk targets."""
    filename = os.environ.get('SMARTPLAN_STORAGE_CONFIG_FILE')
    if not filename:
        return {}
    try:
        with Path(filename).open(encoding='utf-8') as source:
            raw = source.read(65537)
        if len(raw) > 65536:
            raise ValueError('oversized config')
        value = json.loads(raw)
        if not isinstance(value, dict) or set(value) - {'server', 'onedrive', 'webdav'}:
            raise ValueError('unknown storage configuration')
        allowed = {'server': {'path'}, 'onedrive': {'client_id', 'client_secret'},
                   'webdav': {'url', 'username', 'password'}}
        for provider, fields in value.items():
            if (not isinstance(fields, dict) or set(fields) - allowed[provider] or
                    any(not isinstance(item, str) or len(item) > 8192 for item in fields.values())):
                raise ValueError('invalid provider configuration')
        return value
    except (OSError, UnicodeError, ValueError):
        raise RuntimeError('Geschützte Speicherkonfiguration ist nicht gültig.') from None


class Storage:
    def __init__(self, office, key, host, *, config=None, onedrive=None):
        self.office = office
        self.vault = Fernet(key)
        config = load_config() if config is None else config
        self.onedrive = onedrive or OnlineOneDrive(
            office, key, host,
            client_id=config.get('onedrive', {}).get('client_id', ''),
            client_secret=config.get('onedrive', {}).get('client_secret', ''),
        )
        self.backends = {
            'server': ServerStorage(config.get('server', {}).get('path', '')),
            'webdav': WebDavStorage(**{name: config.get('webdav', {}).get(name, '')
                                      for name in ('url', 'username', 'password')}),
        }

    def _authorize(self, token, roles=('owner',)):
        user = self.office.user(token)
        self.office.require(user, roles)
        return user

    def _load(self, name):
        row = self.office.db.execute('SELECT value FROM secrets WHERE name=?', (name,)).fetchone()
        if not row:
            return None
        try:
            value = json.loads(self.vault.decrypt(row[0].encode()))
            if not isinstance(value, dict):
                raise ValueError('object required')
            return value
        except (InvalidToken, ValueError, UnicodeError, AttributeError):
            raise Problem(409, 'Gespeicherte Ablageeinstellung kann nicht gelesen werden.') from None

    def _save(self, name, value):
        encrypted = self.vault.encrypt(canonical(value).encode()).decode()
        self.office.db.execute(
            'INSERT INTO secrets VALUES(?,?) ON CONFLICT(name) DO UPDATE SET value=excluded.value',
            (name, encrypted),
        )

    def _selected(self):
        value = self._load(SETTINGS)
        provider = value.get('provider') if value else 'none'
        if provider not in PROVIDERS:
            raise Problem(409, 'Gespeicherte Ablage bitte erneut auswählen.')
        return provider

    @contextmanager
    def _operation(self):
        # This lock only serializes storage changes/transfers. No Office
        # transaction is held during filesystem/network operations.
        try:
            connection = psycopg.connect(self.office.db.dsn, autocommit=True, connect_timeout=5,
                                         options='-c statement_timeout=5000')
        except psycopg.Error:
            raise Problem(503, 'Dokumentablage derzeit nicht verfügbar.') from None
        try:
            acquired = connection.execute('SELECT pg_try_advisory_lock(%s)', (OPERATION_LOCK,)).fetchone()[0]
            if not acquired:
                raise Problem(409, 'Eine Ablageaktion läuft bereits. Bitte kurz warten.')
            yield
        finally:
            # Closing the dedicated session releases its advisory lock even
            # when the remote destination failed or the request was cancelled.
            connection.close()

    def status(self, token):
        with self.office.lock, self.office.db:
            self._authorize(token)
            selected = self._selected()
        drive = self.onedrive.status(token)
        providers = [
            dict(self.backends['server'].status(), id='server', label='Smartplan-Server',
                 connected=False, requires_connection=False),
            dict(drive, id='onedrive', label='OneDrive', requires_connection=True),
            dict(self.backends['webdav'].status(), id='webdav', label='Cloud / NAS (WebDAV)',
                 connected=False, requires_connection=False),
        ]
        active = next((provider for provider in providers if provider['id'] == selected), {})
        return {'selected_provider': selected, 'providers': providers,
                'configured': bool(active.get('configured')),
                'connected': bool(active.get('connected')),
                'requires_connection': bool(active.get('requires_connection')),
                'account_type': active.get('account_type', 'none')}

    def select(self, token, provider):
        if not isinstance(provider, str) or provider not in PROVIDERS:
            raise Problem(400, 'Gültige Dokumentablage auswählen.')
        with self._operation(), self.office.lock, self.office.db:
            actor = self._authorize(token)
            self._save(SETTINGS, {'provider': provider})
            self.office.audit(actor, 'storage.selected', provider)
        # Selecting a destination neither connects an account nor moves files.
        return self.status(token)

    def _require_drive(self, token):
        with self.office.lock, self.office.db:
            self._authorize(token)
            if self._selected() != 'onedrive':
                raise Problem(409, 'Für die Microsoft-Anmeldung zunächst OneDrive als Ablage auswählen.')

    def begin(self, token):
        with self._operation():
            self._require_drive(token)
            return self.onedrive.begin(token)

    def callback(self, state, code, error=None):
        with self._operation():
            with self.office.lock, self.office.db:
                if self._selected() != 'onedrive':
                    raise Problem(409, 'Die Dokumentablage wurde geändert. Anmeldung erneut in Smartplan beginnen.')
            self.onedrive.callback(state, code, error=error)

    def disconnect(self, token):
        with self._operation():
            self._require_drive(token)
            return self.onedrive.disconnect(token)

    def upload(self, token, report_id, *, expected_provider=None):
        with self._operation():
            with self.office.lock, self.office.db:
                actor = self._authorize(token, ('owner', 'manager'))
                selected = self._selected()
                if selected == 'none':
                    raise Problem(409, 'Die Geschäftsführung muss zuerst eine Dokumentablage auswählen.')
                if expected_provider is not None and selected != expected_provider:
                    raise Problem(409, 'Für diese Aktion muss OneDrive als Dokumentablage ausgewählt sein.')
                report = self.office.report(actor, report_id)
                if report['status'] != 'signed':
                    raise Problem(409, 'Zunächst Dokument unterzeichnen.')
                pdf = self.office.pdf(actor, report_id)
                project_id = report['content']['project_id']
            if selected == 'onedrive':
                result = self.onedrive.upload_report(token, report_id)
            else:
                result = self.backends[selected].put(project_id, report_id, pdf)
            if (not isinstance(result, dict) or result.get('uploaded') is not True or
                    not isinstance(result.get('item_id'), str) or not 1 <= len(result['item_id']) <= 2000):
                raise Problem(502, 'Die Ablage hat das Speichern nicht bestätigt.')
            with self.office.lock, self.office.db:
                actor = self._authorize(token, ('owner', 'manager'))
                self.office.report(actor, report_id)
                self._save(f'storage.receipt.{report_id}.{selected}', {
                    'provider': selected, 'item_id': result['item_id'],
                    'pdf_hash': hashlib.sha256(pdf).hexdigest(), 'at': time.time(),
                })
                self.office.audit(actor, 'storage.uploaded', report_id)
            return {'uploaded': True, 'provider': selected}
