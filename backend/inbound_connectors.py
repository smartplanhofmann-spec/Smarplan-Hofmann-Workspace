"""Single-purpose Gmail intake credentials; no mailbox, read or finance access.

The HTTP adapter authenticates owner management with normal MFA sessions. Intake
uses only these hash-stored SPIN credentials and delegates to Inquiries.create;
it must never feed an import token into normal Office dispatch.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import re
import secrets
import sqlite3
import time
import uuid

from core import Problem
from inquiries import Inquiries

PREFIX = 'SPIN_'
MAX_ENVELOPE_BYTES = 200_000
MAX_ACTIVE_TOKENS = 20
MAX_PER_MINUTE = 60


def schema_statements():
    return ['''CREATE TABLE IF NOT EXISTS inbound_import_tokens(
      id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id),
      name TEXT NOT NULL, source_account TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
      created_at DOUBLE PRECISION NOT NULL, expires_at DOUBLE PRECISION NOT NULL,
      revoked_at DOUBLE PRECISION, last_used_at DOUBLE PRECISION,
      window_started_at DOUBLE PRECISION NOT NULL, window_count INTEGER NOT NULL DEFAULT 0)''',
      'CREATE INDEX IF NOT EXISTS inbound_import_tokens_owner ON inbound_import_tokens(owner_id,created_at)']


def ensure_sqlite_schema(office):
    if isinstance(office.db, sqlite3.Connection):
        with office.lock, office.db:
            for statement in schema_statements():
                office.db.execute(statement)


@contextmanager
def _transaction(office):
    with office.lock:
        if not isinstance(office.db, sqlite3.Connection):
            with office.db:
                yield
            return
        name = 'inbound_' + uuid.uuid4().hex
        office.db.execute('SAVEPOINT ' + name)
        try:
            yield
        except BaseException:
            office.db.execute('ROLLBACK TO SAVEPOINT ' + name)
            office.db.execute('RELEASE SAVEPOINT ' + name)
            raise
        else:
            office.db.execute('RELEASE SAVEPOINT ' + name)


def _line(value, field, maximum):
    if (not isinstance(value, str) or not value.strip() or len(value) > maximum
            or any(ord(char) < 32 for char in value)):
        raise Problem(400, 'Ungültiges Feld: ' + field)
    return value.strip()


def _account(value):
    value = _line(value, 'Gmail-Postfach', 254).lower()
    if not re.fullmatch(r'[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+', value):
        raise Problem(400, 'Gültiges Gmail-Postfach erwartet')
    return value


def _instant(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec='seconds') if value is not None else None


class InboundConnectors:
    def __init__(self, office, *, clock=time.time):
        self.office, self.db, self.clock = office, office.db, clock

    def _owner(self, actor):
        if not isinstance(actor, dict) or not isinstance(actor.get('id'), str):
            raise Problem(401, 'Bitte anmelden')
        current = self.db.execute('SELECT id,email,role,active FROM users WHERE id=?', (actor['id'],)).fetchone()
        if not current or not current['active']:
            raise Problem(401, 'Bitte anmelden')
        if current['role'] != 'owner':
            raise Problem(403, 'Nur die Geschäftsführung darf Eingänge verbinden')
        return {key: current[key] for key in ('id', 'email', 'role')}

    def _metadata(self, row):
        return {'id': row['id'], 'name': row['name'], 'source_account': row['source_account'],
                'created_at': _instant(row['created_at']), 'expires_at': _instant(row['expires_at']),
                'revoked_at': _instant(row['revoked_at']), 'last_used_at': _instant(row['last_used_at'])}

    def issue(self, actor, data):
        if not isinstance(data, dict) or set(data) - {'name', 'source_account', 'expires_days'}:
            raise Problem(400, 'Name, Postfach und gegebenenfalls Laufzeit erwartet')
        name = _line(data.get('name'), 'Verbindungsname', 100)
        account = _account(data.get('source_account'))
        days = data.get('expires_days', 90)
        if type(days) is not int or not 1 <= days <= 365:
            raise Problem(400, 'Laufzeit muss zwischen 1 und 365 Tagen liegen')
        with _transaction(self.office):
            owner = self._owner(actor)
            now = self.clock()
            active = self.db.execute('SELECT COUNT(*) FROM inbound_import_tokens WHERE owner_id=? '
                                     'AND revoked_at IS NULL AND expires_at>?', (owner['id'], now)).fetchone()[0]
            if active >= MAX_ACTIVE_TOKENS:
                raise Problem(409, 'Zuerst eine nicht mehr benötigte Eingangsverbindung widerrufen')
            identifier = uuid.uuid4().hex
            token = PREFIX + secrets.token_urlsafe(32)
            self.db.execute('INSERT INTO inbound_import_tokens(id,owner_id,name,source_account,token_hash,created_at,'
                            'expires_at,window_started_at) VALUES(?,?,?,?,?,?,?,?)',
                            (identifier, owner['id'], name, account, hashlib.sha256(token.encode()).hexdigest(),
                             now, now + days * 86400, now))
            self.office.audit(owner, 'inbound.gmail_token.issued', identifier)
            row = self.db.execute('SELECT * FROM inbound_import_tokens WHERE id=?', (identifier,)).fetchone()
            return {**self._metadata(row), 'token': token}

    def list(self, actor):
        with _transaction(self.office):
            owner = self._owner(actor)
            return [self._metadata(row) for row in self.db.execute('SELECT * FROM inbound_import_tokens '
                    'WHERE owner_id=? ORDER BY created_at,id', (owner['id'],)).fetchall()]

    def revoke(self, actor, identifier):
        with _transaction(self.office):
            owner = self._owner(actor)
            if not isinstance(identifier, str) or not re.fullmatch(r'[a-f0-9]{32}', identifier):
                raise Problem(400, 'Ungültige Eingangsverbindung')
            row = self.db.execute('SELECT * FROM inbound_import_tokens WHERE id=? AND owner_id=?',
                                  (identifier, owner['id'])).fetchone()
            if not row:
                raise Problem(404, 'Eingangsverbindung nicht verfügbar')
            if row['revoked_at'] is None:
                self.db.execute('UPDATE inbound_import_tokens SET revoked_at=? WHERE id=?', (self.clock(), identifier))
                self.office.audit(owner, 'inbound.gmail_token.revoked', identifier)
            return self._metadata(self.db.execute('SELECT * FROM inbound_import_tokens WHERE id=?', (identifier,)).fetchone())

    def _credential(self, token, now):
        if not isinstance(token, str) or not re.fullmatch(r'SPIN_[A-Za-z0-9_-]{43}', token):
            raise Problem(401, 'Gmail-Importzugang ungültig oder abgelaufen')
        row = self.db.execute('SELECT t.*,u.email,u.role,u.active FROM inbound_import_tokens t '
                              'JOIN users u ON u.id=t.owner_id WHERE t.token_hash=?',
                              (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if (not row or row['revoked_at'] is not None or row['expires_at'] <= now
                or not row['active'] or row['role'] != 'owner'):
            raise Problem(401, 'Gmail-Importzugang ungültig oder abgelaufen')
        return row

    def receive_gmail(self, token, envelope):
        allowed = {'source_account', 'source_id', 'subject', 'message', 'sender_name', 'sender_email', 'received_at'}
        if (not isinstance(envelope, dict) or set(envelope) - allowed
                or not {'source_account', 'source_id', 'subject', 'message'} <= set(envelope)):
            raise Problem(400, 'Begrenzte Gmail-Nachricht ohne Anhänge erwartet')
        try:
            if len(json.dumps(envelope, ensure_ascii=False, allow_nan=False).encode('utf-8')) > MAX_ENVELOPE_BYTES:
                raise Problem(413, 'Gmail-Nachricht ist zu groß')
        except (TypeError, ValueError, UnicodeError) as error:
            raise Problem(400, 'Ungültige Gmail-Nachricht') from error
        account = _account(envelope['source_account'])
        source_id = envelope['source_id']
        if not isinstance(source_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', source_id):
            raise Problem(400, 'Stabile Gmail-Nachrichten-ID erwartet')
        with _transaction(self.office):
            now = self.clock()
            credential = self._credential(token, now)
            if account != credential['source_account']:
                raise Problem(403, 'Importzugang gehört zu einem anderen Gmail-Postfach')
            count = credential['window_count'] if now < credential['window_started_at'] + 60 else 0
            if count >= MAX_PER_MINUTE:
                raise Problem(429, 'Gmail-Übernahme bitte später wiederholen')
            request_id = hashlib.sha256(('gmail\n' + account + '\n' + source_id).encode()).hexdigest()[:32]
            normalized = {key: value for key, value in envelope.items() if key != 'source_account'}
            normalized.update(request_id=request_id, source='gmail', source_account=account)
            actor = {'id': credential['owner_id'], 'email': credential['email'], 'role': 'owner'}
            inquiry = Inquiries(self.office).create(actor, normalized)
            self.db.execute('UPDATE inbound_import_tokens SET last_used_at=?,window_started_at=?,window_count=? WHERE id=?',
                            (now, credential['window_started_at'] if count else now, count + 1, credential['id']))
            return {'id': inquiry['id'], 'status': 'received', 'ingested_at': _instant(now)}
