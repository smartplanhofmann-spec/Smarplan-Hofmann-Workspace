"""Offer-scoped customer access, immutable declarations and explicit staff adoption.

Portal principals never become Office users. Secrets are returned once and only
their hashes are persisted. This module neither sends messages nor issues invoices.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
import uuid
from urllib.parse import urlsplit

from core import Problem, canonical
from business_operations import Domain, identifier, text, transaction


FEATURES = ('offer_portal',)  # Runtime availability still requires a trusted online origin.
STATEMENTS = {
    'version': 'offer-decision-v1',
    'accepted': 'Ich nehme das angezeigte Angebot mit dieser Angebotsnummer, Fassung und Gesamtsumme ausdrücklich an.',
    'declined': 'Ich lehne das angezeigte Angebot mit dieser Angebotsnummer und Fassung ausdrücklich ab.',
}
_HISTORY = ('business_portal_grants', 'business_portal_revocations', 'business_portal_decisions',
            'business_portal_adoptions', 'business_portal_staff_requests', 'business_portal_decision_requests')
_ID = r'[a-f0-9]{32}'
_HASH = r'[a-f0-9]{64}'
_BUYER = ('name', 'contact_name', 'address_line', 'postal_code', 'city', 'country', 'email', 'vat_id')
_ISSUER = ('company_name', 'address_line', 'postal_code', 'city', 'country', 'email', 'phone', 'website',
           'vat_id', 'tax_number', 'iban', 'bic', 'payment_terms', 'footer')
_POSITION = ('index', 'description', 'quantity', 'unit', 'unit_price_net', 'price_base_quantity',
             'discount_percent', 'tax_rate', 'tax_category', 'tax_exemption_reason', 'net')
_TOTALS = ('net', 'tax', 'gross', 'payable', 'labor_net', 'labor_tax', 'labor_gross',
           'material_net', 'material_tax', 'material_gross')
_SOURCE = ('offer_id', 'number', 'project_id', 'customer_id', 'source_revision', 'content_hash', 'pdf_hash')
_DECISION = ('id', 'offer_id', 'grant_id', 'principal_id', 'decision', 'declared_name',
             'statement_version', 'statement_text', 'content_hash', 'pdf_hash', 'created_at')
_ADOPTION = ('id', 'offer_id', 'decision_id', 'document_id', 'project_id', 'created_by', 'created_at')


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA', 'BLOB'):
        raise ValueError('Unsupported binary storage type')
    return [
        '''CREATE TABLE IF NOT EXISTS business_portal_principals(
        id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id), name TEXT NOT NULL, email TEXT NOT NULL,
        active INTEGER NOT NULL CHECK(active IN (0,1)), revision INTEGER NOT NULL CHECK(revision>0),
        created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_portal_grants(
        id TEXT PRIMARY KEY, principal_id TEXT NOT NULL REFERENCES business_portal_principals(id),
        offer_id TEXT NOT NULL REFERENCES business_documents(id), number TEXT NOT NULL,
        project_id TEXT NOT NULL REFERENCES projects(id), customer_id TEXT NOT NULL REFERENCES customers(id),
        source_revision INTEGER NOT NULL CHECK(source_revision>0), content_hash TEXT NOT NULL CHECK(length(content_hash)=64),
        pdf_hash TEXT NOT NULL CHECK(length(pdf_hash)=64), public_json TEXT NOT NULL,
        secret_hash TEXT NOT NULL UNIQUE CHECK(length(secret_hash)=64), expires_at TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_portal_revocations(
        grant_id TEXT PRIMARY KEY REFERENCES business_portal_grants(id), reason TEXT NOT NULL,
        kind TEXT NOT NULL CHECK(kind IN ('staff','restore')), revoked_by TEXT REFERENCES users(id), created_at TEXT NOT NULL,
        CHECK((kind='staff' AND revoked_by IS NOT NULL) OR (kind='restore' AND revoked_by IS NULL)))''',
        '''CREATE TABLE IF NOT EXISTS business_portal_sessions(
        token_hash TEXT PRIMARY KEY CHECK(length(token_hash)=64),
        grant_id TEXT NOT NULL REFERENCES business_portal_grants(id),
        principal_id TEXT NOT NULL REFERENCES business_portal_principals(id), created_at TEXT NOT NULL, expires_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_portal_decisions(
        id TEXT PRIMARY KEY, offer_id TEXT NOT NULL UNIQUE REFERENCES business_documents(id),
        grant_id TEXT NOT NULL REFERENCES business_portal_grants(id), principal_id TEXT NOT NULL REFERENCES business_portal_principals(id),
        source_revision INTEGER NOT NULL CHECK(source_revision>0), content_hash TEXT NOT NULL CHECK(length(content_hash)=64),
        pdf_hash TEXT NOT NULL CHECK(length(pdf_hash)=64), decision TEXT NOT NULL CHECK(decision IN ('accepted','declined')),
        declared_name TEXT NOT NULL, statement_version TEXT NOT NULL, statement_text TEXT NOT NULL, created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_portal_adoptions(
        id TEXT PRIMARY KEY, offer_id TEXT NOT NULL UNIQUE REFERENCES business_documents(id),
        decision_id TEXT NOT NULL UNIQUE REFERENCES business_portal_decisions(id),
        document_id TEXT NOT NULL UNIQUE REFERENCES business_documents(id), project_id TEXT NOT NULL REFERENCES projects(id),
        created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_portal_staff_requests(
        user_id TEXT NOT NULL REFERENCES users(id), request_id TEXT NOT NULL, request_hash TEXT NOT NULL CHECK(length(request_hash)=64),
        operation TEXT NOT NULL CHECK(operation IN ('grant','revoke','adopt')), target_id TEXT NOT NULL,
        PRIMARY KEY(user_id,request_id))''',
        '''CREATE TABLE IF NOT EXISTS business_portal_decision_requests(
        grant_id TEXT NOT NULL REFERENCES business_portal_grants(id), principal_id TEXT NOT NULL REFERENCES business_portal_principals(id),
        request_id TEXT NOT NULL, request_hash TEXT NOT NULL CHECK(length(request_hash)=64),
        decision_id TEXT NOT NULL REFERENCES business_portal_decisions(id), PRIMARY KEY(grant_id,principal_id,request_id))''',
        '''CREATE TABLE IF NOT EXISTS business_portal_rate_counters(
        key_hash TEXT PRIMARY KEY CHECK(length(key_hash)=64), window_start INTEGER NOT NULL,
        window_seconds INTEGER NOT NULL CHECK(window_seconds>0), attempts INTEGER NOT NULL CHECK(attempts>0), expires_at DOUBLE PRECISION NOT NULL)''',
        'CREATE INDEX IF NOT EXISTS business_portal_grants_offer ON business_portal_grants(offer_id,created_at,id)',
        'CREATE INDEX IF NOT EXISTS business_portal_sessions_grant ON business_portal_sessions(grant_id,expires_at)',
    ]


def protected_tables():
    return _HISTORY


def runtime_privileges():
    return {**{table: ('SELECT', 'INSERT') for table in _HISTORY},
            'business_portal_principals': ('SELECT', 'INSERT', 'UPDATE'),
            'business_portal_sessions': ('SELECT', 'INSERT', 'DELETE'),
            'business_portal_rate_counters': ('SELECT', 'INSERT', 'UPDATE', 'DELETE')}


def guard_statements(dialect):
    if dialect == 'sqlite':
        result = [f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} ON {table} "
                  "BEGIN SELECT RAISE(ABORT,'immutable portal history'); END"
                  for table in _HISTORY for action in ('UPDATE', 'DELETE')]
        conflicts = {
            'business_portal_grants': 'id=NEW.id OR secret_hash=NEW.secret_hash',
            'business_portal_revocations': 'grant_id=NEW.grant_id',
            'business_portal_decisions': 'id=NEW.id OR offer_id=NEW.offer_id',
            'business_portal_adoptions': 'id=NEW.id OR offer_id=NEW.offer_id OR decision_id=NEW.decision_id OR document_id=NEW.document_id',
            'business_portal_staff_requests': 'user_id=NEW.user_id AND request_id=NEW.request_id',
            'business_portal_decision_requests': 'grant_id=NEW.grant_id AND principal_id=NEW.principal_id AND request_id=NEW.request_id',
            'business_portal_principals': 'id=NEW.id',
        }
        for table, condition in conflicts.items():
            result.append(f"CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} "
                          f"WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition}) "
                          "BEGIN SELECT RAISE(ABORT,'immutable portal history'); END")
        result += ["""CREATE TRIGGER IF NOT EXISTS business_portal_principals_update_guard BEFORE UPDATE ON business_portal_principals
            WHEN NEW.id<>OLD.id OR NEW.customer_id<>OLD.customer_id OR NEW.name<>OLD.name OR NEW.email<>OLD.email
            OR NEW.created_by<>OLD.created_by OR NEW.created_at<>OLD.created_at
            OR OLD.active<>1 OR NEW.active<>0 OR NEW.revision<>OLD.revision+1
            BEGIN SELECT RAISE(ABORT,'immutable portal identity'); END""",
            "CREATE TRIGGER IF NOT EXISTS business_portal_principals_delete_guard BEFORE DELETE ON business_portal_principals "
            "BEGIN SELECT RAISE(ABORT,'immutable portal identity'); END"]
        return result
    if dialect == 'postgresql':
        result = ["""CREATE OR REPLACE FUNCTION business_portal_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'immutable portal history'; END; $$""",
            """CREATE OR REPLACE FUNCTION business_portal_principal_guard() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF NEW.id<>OLD.id OR NEW.customer_id<>OLD.customer_id OR NEW.name<>OLD.name OR NEW.email<>OLD.email
            OR NEW.created_by<>OLD.created_by OR NEW.created_at<>OLD.created_at OR OLD.active<>1 OR NEW.active<>0
            OR NEW.revision<>OLD.revision+1 THEN RAISE EXCEPTION 'immutable portal identity'; END IF; RETURN NEW; END; $$"""]
        for table, actions in [(table, ('UPDATE', 'DELETE')) for table in _HISTORY] + [('business_portal_principals', ('UPDATE', 'DELETE'))]:
            for action in actions:
                name = table + '_' + action.lower() + '_guard'
                function = 'business_portal_principal_guard' if table == 'business_portal_principals' and action == 'UPDATE' else 'business_portal_immutable_guard'
                result.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) "
                              f"THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION {function}(); END IF; END $$")
        return result
    raise ValueError('Unsupported guard dialect')


def _sha(value):
    return hashlib.sha256(value.encode('utf-8') if isinstance(value, str) else value).hexdigest()


def _origin(office):
    value = getattr(office, 'portal_origin', None)
    try:
        parsed = urlsplit(value) if isinstance(value, str) else None
        if (not parsed or parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.path or parsed.query or parsed.fragment or value != 'https://' + parsed.netloc
                or any(char.isspace() or ord(char) < 32 for char in value)):
            return None
        parsed.port  # Reject malformed ports as well.
        return value
    except ValueError:
        return None


def runtime_features(office):
    return ('offer_portal',) if _origin(office) else ()


def _fields(value, fields):
    return {key: value[key] for key in fields if key in value.keys()}


def _public_offer(row, payload, pdf_hash):
    # Never add arbitrary source fields: rich commercial snapshots contain
    # internal costs, employees, BOMs and operational provenance.
    value = _fields(payload, ('title', 'issue_date', 'due_date', 'currency', 'intro', 'notes'))
    value.update(id=row['id'], number=row['number'], revision=row['revision'],
                 content_hash=row['payload_sha256'], pdf_hash=pdf_hash,
                 buyer=_fields(payload['buyer'], _BUYER), issuer=_fields(payload['issuer'], _ISSUER),
                 positions=[_fields(position, _POSITION) for position in payload['positions']],
                 totals=_fields(payload['totals'], _TOTALS))
    value['totals']['tax_breakdown'] = [_fields(bucket, ('rate', 'category', 'reason', 'net', 'tax'))
                                      for bucket in payload['totals']['tax_breakdown']]
    return value


def _at(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError('Missing timestamp timezone')
    return parsed.astimezone(timezone.utc)


def _token(value, prefix):
    return isinstance(value, str) and re.fullmatch(prefix + r'[A-Za-z0-9_-]{43}', value) is not None


def _body(data, fields):
    if not isinstance(data, dict) or set(data) != set(fields) | {'request_id', 'confirmation'}:
        raise Problem(400, 'Vollständige bekannte Portalfelder erwartet')
    identifier(data['request_id'], 'request_id')
    if data['confirmation'] is not True:
        raise Problem(400, 'Portalaktion ausdrücklich bestätigen')
    return data


def _line(value, name, maximum):
    value = text(value, name, maximum, required=True)
    if any(ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise Problem(400, 'Einzeiliger Text erwartet: ' + name)
    return value


class Portal(Domain):
    def _online(self):
        origin = _origin(self.office)
        if origin is None:
            raise Problem(409, 'Kundenportal ist nur am eingerichteten Online-Dienst verfügbar')
        return origin

    def _write_gate(self):
        from business_schema import state, require_financial_release
        from business_organization import module_enabled
        self._online()
        if state(self.office)['compatibility_mode'] != 'business':
            raise Problem(409, 'Portalaktionen sind im Rückkehrmodus gesperrt')
        if not module_enabled(self.office, 'documents'):
            raise Problem(423, 'Kaufmännische Belege sind fachlich deaktiviert')
        require_financial_release(self.office)

    def _source(self, offer_id, *, current=True):
        identifier(offer_id, 'Angebots-ID')
        row = self.office.db.execute('SELECT * FROM business_documents WHERE id=?', (offer_id,)).fetchone()
        if row is None:
            raise Problem(404, 'Angebot nicht verfügbar')
        archive = self.office.db.execute('SELECT * FROM business_document_archives WHERE document_id=?', (offer_id,)).fetchone()
        if row['kind'] != 'offer' or row['status'] != 'final' or not row['customer_id'] or not archive:
            raise Problem(409, 'Finales archiviertes Angebot mit Kundenbindung erforderlich')
        from business_documents import MAX_PDF
        pdf = bytes(archive['pdf'])
        if (row['payload_json'] != archive['payload_json'] or row['payload_sha256'] != archive['payload_sha256']
                or _sha(archive['payload_json']) != row['payload_sha256'] or _sha(pdf) != archive['pdf_sha256']
                or not pdf.startswith(b'%PDF-') or len(pdf) > MAX_PDF):
            raise Problem(409, 'Angebotsarchiv besteht die Integritätsprüfung nicht')
        payload = json.loads(archive['payload_json'])
        if (payload.get('id') != row['id'] or payload.get('project_id') != row['project_id']
                or payload.get('number') != row['number'] or payload.get('kind') != 'offer'
                or payload.get('document_revision') != row['revision'] - 1):
            raise Problem(409, 'Angebotsfassung ist nicht konsistent')
        if current:
            project = self.office.db.execute('SELECT customer_id FROM projects WHERE id=?', (row['project_id'],)).fetchone()
            customer = self.office.db.execute('SELECT active FROM customers WHERE id=?', (row['customer_id'],)).fetchone()
            erased = self.office.db.execute('SELECT erased_at FROM business_contact_extras WHERE customer_id=?', (row['customer_id'],)).fetchone()
            if not project or project['customer_id'] != row['customer_id'] or not customer or not customer['active'] or (erased and erased['erased_at']):
                raise Problem(409, 'Aktive unveränderte Kundenbindung erforderlich')
        source = dict(offer_id=row['id'], number=row['number'], project_id=row['project_id'], customer_id=row['customer_id'],
                      source_revision=row['revision'], content_hash=row['payload_sha256'], pdf_hash=archive['pdf_sha256'])
        return source, _public_offer(row, payload, archive['pdf_sha256']), pdf

    def _staff(self, actor, offer_id, *, adopt=False):
        identifier(offer_id, 'Angebots-ID')
        row = self.office.db.execute('SELECT project_id FROM business_documents WHERE id=?', (offer_id,)).fetchone()
        if row is None:
            self.access(actor, 'portal.manage')
            raise Problem(404, 'Angebot nicht verfügbar')
        fresh = self.access(actor, 'portal.manage', row['project_id'])
        self.access(fresh, 'finance.read', row['project_id'])
        if adopt:
            self.access(fresh, 'finance.write', row['project_id'])
            self.access(fresh, 'projects.manage', row['project_id'])
        return fresh

    def _expected(self, source, data):
        if (type(data.get('source_revision')) is not int or data['source_revision'] != source['source_revision']
                or data.get('content_hash') != source['content_hash'] or data.get('pdf_hash') != source['pdf_hash']):
            raise Problem(409, 'Angebotsfassung wurde geändert; neu laden')

    def _receipt(self, actor, operation, target, data):
        fingerprint = _sha(canonical([operation, target, data]))
        row = self.office.db.execute('SELECT * FROM business_portal_staff_requests WHERE user_id=? AND request_id=?',
                                     (actor['id'], data['request_id'])).fetchone()
        if row and (row['operation'] != operation or row['request_hash'] != fingerprint):
            raise Problem(409, 'Vorgangs-ID wurde mit anderem Inhalt verwendet')
        return fingerprint, row['target_id'] if row else None

    def _remember(self, actor, data, fingerprint, operation, target):
        self.office.db.execute('INSERT INTO business_portal_staff_requests(user_id,request_id,request_hash,operation,target_id) VALUES(?,?,?,?,?)',
                               (actor['id'], data['request_id'], fingerprint, operation, target))

    def _grant_row(self, grant_id):
        identifier(grant_id, 'Freigabe-ID')
        row = self.office.db.execute('SELECT * FROM business_portal_grants WHERE id=?', (grant_id,)).fetchone()
        if not row:
            raise Problem(404, 'Portalfreigabe nicht verfügbar')
        return row

    def _grant(self, row):
        principal = self.office.db.execute('SELECT * FROM business_portal_principals WHERE id=?', (row['principal_id'],)).fetchone()
        revoked = self.office.db.execute('SELECT * FROM business_portal_revocations WHERE grant_id=?', (row['id'],)).fetchone()
        value = _fields(row, ('id',) + _SOURCE + ('created_by', 'created_at', 'expires_at'))
        value.update(principal=dict(id=principal['id'], name=principal['name'], email=principal['email'], active=bool(principal['active'])),
                     status='revoked' if revoked else 'expired' if _at(row['expires_at']) <= _at(self.now()) else 'active')
        if revoked:
            value['revocation'] = dict(revoked)
        return value

    def _decision(self, offer_id):
        row = self.office.db.execute('SELECT * FROM business_portal_decisions WHERE offer_id=?', (offer_id,)).fetchone()
        return _fields(row, _DECISION) if row else None

    def _adoption(self, offer_id):
        row = self.office.db.execute('SELECT * FROM business_portal_adoptions WHERE offer_id=?', (offer_id,)).fetchone()
        return _fields(row, _ADOPTION) if row else None

    def list_grants(self, actor, offer_id):
        with transaction(self.office):
            self._staff(actor, offer_id)
            source, _, _ = self._source(offer_id, current=False)
            return dict(source=source, items=[self._grant(row) for row in self.office.db.execute(
                'SELECT * FROM business_portal_grants WHERE offer_id=? ORDER BY created_at,id', (offer_id,)).fetchall()],
                decision=self._decision(offer_id), adoption=self._adoption(offer_id))

    def create_grant(self, actor, data):
        _body(data, ('offer_id', 'source_revision', 'content_hash', 'pdf_hash', 'recipient_name', 'recipient_email', 'expires_in_days'))
        name = _line(data['recipient_name'], 'Empfängername', 200)
        email = _line(data['recipient_email'], 'Empfänger-E-Mail', 254)
        if not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+', email):
            raise Problem(400, 'Gültige Empfänger-E-Mail erwartet')
        if type(data['expires_in_days']) is not int or not 1 <= data['expires_in_days'] <= 30:
            raise Problem(400, 'Freigabedauer zwischen 1 und 30 Tagen erwartet')
        with transaction(self.office):
            fresh = self._staff(actor, data['offer_id'])
            self._write_gate()
            source, public, _ = self._source(data['offer_id'])
            self._expected(source, data)
            fingerprint, replay = self._receipt(fresh, 'grant', data['offer_id'], data)
            if replay:
                return dict(grant=self._grant(self._grant_row(replay)), link_available=False)
            stamp = self.now()
            active = self.office.db.execute('SELECT g.id FROM business_portal_grants g WHERE g.offer_id=? AND g.expires_at>? '
                'AND NOT EXISTS(SELECT 1 FROM business_portal_revocations r WHERE r.grant_id=g.id)', (data['offer_id'], stamp)).fetchone()
            if active:
                raise Problem(409, 'Vorhandene Freigabe zuerst ausdrücklich widerrufen')
            principal_id, grant_id = uuid.uuid4().hex, uuid.uuid4().hex
            key = 'SPPI_' + secrets.token_urlsafe(32)
            expires = (_at(stamp) + timedelta(days=data['expires_in_days'])).isoformat(timespec='seconds')
            self.office.db.execute('INSERT INTO business_portal_principals(id,customer_id,name,email,active,revision,created_by,created_at) '
                'VALUES(?,?,?,?,1,1,?,?)', (principal_id, source['customer_id'], name, email, fresh['id'], stamp))
            self.office.db.execute('INSERT INTO business_portal_grants(id,principal_id,offer_id,number,project_id,customer_id,source_revision,'
                'content_hash,pdf_hash,public_json,secret_hash,expires_at,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (grant_id, principal_id, source['offer_id'], source['number'], source['project_id'], source['customer_id'],
                 source['source_revision'], source['content_hash'], source['pdf_hash'], canonical(public), _sha(key), expires, fresh['id'], stamp))
            self._remember(fresh, data, fingerprint, 'grant', grant_id)
            self.office.audit(fresh, 'business.portal.granted', grant_id)
            return dict(grant=self._grant(self._grant_row(grant_id)), link_available=True,
                        portal_url=self._online() + '/office/portal.html#grant=' + grant_id + '&key=' + key)

    def revoke_grant(self, actor, grant_id, data):
        _body(data, ('reason',))
        reason = _line(data['reason'], 'Widerrufsgrund', 500)
        with transaction(self.office):
            row = self._grant_row(grant_id)
            fresh = self._staff(actor, row['offer_id'])
            fingerprint, replay = self._receipt(fresh, 'revoke', grant_id, data)
            if replay:
                return self._grant(row)
            if not self.office.db.execute('SELECT 1 FROM business_portal_revocations WHERE grant_id=?', (grant_id,)).fetchone():
                self.office.db.execute("INSERT INTO business_portal_revocations(grant_id,reason,kind,revoked_by,created_at) VALUES(?,?,'staff',?,?)",
                                       (grant_id, reason, fresh['id'], self.now()))
                self.office.audit(fresh, 'business.portal.revoked', grant_id)
            self._remember(fresh, data, fingerprint, 'revoke', grant_id)
            self.office.db.execute('DELETE FROM business_portal_sessions WHERE grant_id=?', (grant_id,))
            return self._grant(row)

    def _bound(self, grant):
        principal = self.office.db.execute('SELECT * FROM business_portal_principals WHERE id=?', (grant['principal_id'],)).fetchone()
        if (not principal or not principal['active'] or principal['customer_id'] != grant['customer_id']
                or _at(grant['expires_at']) <= _at(self.now())
                or self.office.db.execute('SELECT 1 FROM business_portal_revocations WHERE grant_id=?', (grant['id'],)).fetchone()):
            raise Problem(401, 'Portalzugang nicht verfügbar')
        try:
            source, public, pdf = self._source(grant['offer_id'])
            if any(source[key] != grant[key] for key in _SOURCE) or canonical(public) != grant['public_json']:
                raise Problem(401, 'Portalzugang nicht verfügbar')
        except (Problem, ValueError, TypeError, KeyError):
            raise Problem(401, 'Portalzugang nicht verfügbar') from None
        return source, public, pdf

    def open_session(self, grant_id, key):
        self._online()
        if not isinstance(grant_id, str) or not re.fullmatch(_ID, grant_id) or not _token(key, 'SPPI_'):
            raise Problem(401, 'Portalzugang nicht verfügbar')
        with transaction(self.office):
            grant = self.office.db.execute('SELECT * FROM business_portal_grants WHERE id=?', (grant_id,)).fetchone()
            if not grant or not hmac.compare_digest(grant['secret_hash'], _sha(key)):
                raise Problem(401, 'Portalzugang nicht verfügbar')
            self._bound(grant)
            stamp = self.now()
            self.office.db.execute('DELETE FROM business_portal_sessions WHERE expires_at<=?', (stamp,))
            count = self.office.db.execute('SELECT COUNT(*) FROM business_portal_sessions WHERE grant_id=?', (grant_id,)).fetchone()[0]
            if count >= 5:
                raise Problem(429, 'Zu viele aktive Portalsitzungen')
            token = 'SPPT_' + secrets.token_urlsafe(32)
            expiry = min(_at(grant['expires_at']), _at(stamp) + timedelta(minutes=30)).isoformat(timespec='seconds')
            self.office.db.execute('INSERT INTO business_portal_sessions(token_hash,grant_id,principal_id,created_at,expires_at) VALUES(?,?,?,?,?)',
                                   (_sha(token), grant_id, grant['principal_id'], stamp, expiry))
            return dict(token=token, expires_at=expiry)

    def _session(self, token):
        self._online()
        if not _token(token, 'SPPT_'):
            raise Problem(401, 'Portalzugang nicht verfügbar')
        session = self.office.db.execute('SELECT * FROM business_portal_sessions WHERE token_hash=?', (_sha(token),)).fetchone()
        if not session or _at(session['expires_at']) <= _at(self.now()):
            raise Problem(401, 'Portalzugang nicht verfügbar')
        grant = self._grant_row(session['grant_id'])
        if session['principal_id'] != grant['principal_id'] or _at(session['expires_at']) > _at(grant['expires_at']):
            raise Problem(401, 'Portalzugang nicht verfügbar')
        source, public, pdf = self._bound(grant)
        return session, grant, source, public, pdf

    def logout(self, token):
        if not _token(token, 'SPPT_'):
            raise Problem(401, 'Portalzugang nicht verfügbar')
        with transaction(self.office):
            self.office.db.execute('DELETE FROM business_portal_sessions WHERE token_hash=?', (_sha(token),))
        return {'logged_out': True}

    def view(self, token):
        with transaction(self.office):
            session, grant, _, public, _ = self._session(token)
            decision = self._decision(grant['offer_id'])
            allowed = decision is None
            try:
                self._write_gate()
            except Problem as error:
                if error.status not in (409, 423):
                    raise
                allowed = False
            return dict(offer=public, expires_at=session['expires_at'], decision=decision,
                        actions_allowed=allowed, statements=dict(STATEMENTS))

    def pdf(self, token):
        with transaction(self.office):
            _, _, source, _, pdf = self._session(token)
            filename = 'Angebot-' + re.sub(r'[^A-Za-z0-9_-]', '_', source['number'])[:100] + '.pdf'
            return pdf, filename

    def decide(self, token, data):
        _body(data, ('content_hash', 'pdf_hash', 'decision', 'declared_name', 'statement_version'))
        if data['decision'] not in ('accepted', 'declined') or data['statement_version'] != STATEMENTS['version']:
            raise Problem(400, 'Aktuelle ausdrückliche Angebotserklärung erwartet')
        name = _line(data['declared_name'], 'Erklärter Name', 200)
        fingerprint = _sha(canonical(data))
        with transaction(self.office):
            _, grant, source, _, _ = self._session(token)
            self._write_gate()
            if data['content_hash'] != source['content_hash'] or data['pdf_hash'] != source['pdf_hash']:
                raise Problem(409, 'Angebotsfassung stimmt nicht überein; neu laden')
            previous = self.office.db.execute('SELECT * FROM business_portal_decision_requests WHERE grant_id=? AND principal_id=? AND request_id=?',
                (grant['id'], grant['principal_id'], data['request_id'])).fetchone()
            if previous:
                if previous['request_hash'] != fingerprint:
                    raise Problem(409, 'Vorgangs-ID wurde mit anderem Inhalt verwendet')
                return self._decision(source['offer_id'])
            if self._decision(source['offer_id']):
                raise Problem(409, 'Für dieses Angebot liegt bereits eine abschließende Erklärung vor')
            decision_id = uuid.uuid4().hex
            self.office.db.execute('INSERT INTO business_portal_decisions(id,offer_id,grant_id,principal_id,source_revision,content_hash,pdf_hash,'
                'decision,declared_name,statement_version,statement_text,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                (decision_id, source['offer_id'], grant['id'], grant['principal_id'], source['source_revision'], source['content_hash'], source['pdf_hash'],
                 data['decision'], name, STATEMENTS['version'], STATEMENTS[data['decision']], self.now()))
            self.office.db.execute('INSERT INTO business_portal_decision_requests(grant_id,principal_id,request_id,request_hash,decision_id) VALUES(?,?,?,?,?)',
                (grant['id'], grant['principal_id'], data['request_id'], fingerprint, decision_id))
            return self._decision(source['offer_id'])

    def adopt(self, actor, offer_id, data):
        _body(data, ('decision_id', 'source_revision', 'content_hash', 'pdf_hash'))
        identifier(data['decision_id'], 'Entscheidungs-ID')
        with transaction(self.office):
            fresh = self._staff(actor, offer_id, adopt=True)
            self._write_gate()
            source, _, _ = self._source(offer_id)
            self._expected(source, data)
            decision = self._decision(offer_id)
            if (not decision or decision['id'] != data['decision_id'] or decision['decision'] != 'accepted'
                    or decision['content_hash'] != source['content_hash'] or decision['pdf_hash'] != source['pdf_hash']):
                raise Problem(409, 'Passende unveränderte Angebotsannahme erforderlich')
            fingerprint, replay = self._receipt(fresh, 'adopt', offer_id, data)
            existing = self._adoption(offer_id)
            if replay:
                return existing
            if existing:
                raise Problem(409, 'Angenommenes Angebot wurde bereits übernommen')
            manual = self.office.db.execute("SELECT d.id FROM business_document_relations r JOIN business_documents d ON d.id=r.target_id "
                "WHERE r.source_id=? AND r.kind='converted_from' AND d.kind='order_confirmation'", (offer_id,)).fetchone()
            if manual:
                raise Problem(409, 'Auftragsbestätigung aus dieser Quelle besteht bereits; intern prüfen')
            from business_documents import Documents
            result = Documents(self.office, clock=self.clock).convert(fresh, offer_id,
                dict(request_id=uuid.uuid4().hex, revision=source['source_revision'], target_kind='order_confirmation'))
            adoption_id = uuid.uuid4().hex
            self.office.db.execute('INSERT INTO business_portal_adoptions(id,offer_id,decision_id,document_id,project_id,created_by,created_at) '
                'VALUES(?,?,?,?,?,?,?)', (adoption_id, offer_id, decision['id'], result['id'], source['project_id'], fresh['id'], self.now()))
            self._remember(fresh, data, fingerprint, 'adopt', adoption_id)
            self.office.audit(fresh, 'business.portal.adopted', adoption_id)
            return self._adoption(offer_id)


def count_attempt(office, key, limit, window_seconds):
    """Commit a bounded hashed counter before a later auth/body failure can roll back."""
    if (not isinstance(key, str) or not re.fullmatch(_HASH, key) or type(limit) is not int or not 1 <= limit <= 10000
            or type(window_seconds) is not int or not 1 <= window_seconds <= 86400):
        raise ValueError('Bounded portal rate counter expected')
    now = time.time()
    start = int(now) // window_seconds * window_seconds
    rejected = False
    with transaction(office):
        office.db.execute('DELETE FROM business_portal_rate_counters WHERE expires_at<=?', (now,))
        row = office.db.execute('SELECT * FROM business_portal_rate_counters WHERE key_hash=?', (key,)).fetchone()
        if not row and office.db.execute('SELECT COUNT(*) FROM business_portal_rate_counters').fetchone()[0] >= 10000:
            rejected = True
        else:
            attempts = min(row['attempts'] + 1, limit + 1) if row and row['window_start'] == start and row['window_seconds'] == window_seconds else 1
            office.db.execute('INSERT INTO business_portal_rate_counters(key_hash,window_start,window_seconds,attempts,expires_at) VALUES(?,?,?,?,?) '
                'ON CONFLICT(key_hash) DO UPDATE SET window_start=excluded.window_start,window_seconds=excluded.window_seconds,'
                'attempts=excluded.attempts,expires_at=excluded.expires_at', (key, start, window_seconds, attempts, start + 2 * window_seconds))
            rejected = attempts > limit
    if rejected:
        raise Problem(429, 'Zu viele Portalversuche; später erneut versuchen')


def sanitize_after_restore(db):
    """Participate in the caller's restore transaction; never commit or impersonate."""
    if isinstance(db, sqlite3.Connection):
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='business_portal_grants'").fetchone()
    else:
        exists = db.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='business_portal_grants'").fetchone()
    if not exists:
        return
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    db.execute("INSERT INTO business_portal_revocations(grant_id,reason,kind,revoked_by,created_at) "
        "SELECT g.id,?,'restore',NULL,? FROM business_portal_grants g "
        'WHERE NOT EXISTS(SELECT 1 FROM business_portal_revocations r WHERE r.grant_id=g.id)',
        ('Zugang nach Wiederherstellung gesperrt; neue Freigabe erforderlich.', stamp))
    db.execute('UPDATE business_portal_principals SET active=0,revision=revision+1 WHERE active=1')
    db.execute('DELETE FROM business_portal_sessions')
    db.execute('DELETE FROM business_portal_rate_counters')


def validate_integrity(office):
    """Validate historical identities/archives without requiring today's customer binding."""
    api = Portal(office)
    try:
        grants = {}
        for row in office.db.execute('SELECT * FROM business_portal_grants').fetchall():
            identifier(row['id']); identifier(row['principal_id'])
            source, public, _ = api._source(row['offer_id'], current=False)
            principal = office.db.execute('SELECT * FROM business_portal_principals WHERE id=?', (row['principal_id'],)).fetchone()
            if (not principal or principal['customer_id'] != row['customer_id'] or not re.fullmatch(_HASH, row['secret_hash'])
                    or any(source[key] != row[key] for key in _SOURCE) or canonical(public) != row['public_json']
                    or not timedelta(0) < _at(row['expires_at']) - _at(row['created_at']) <= timedelta(days=30)):
                raise ValueError('Invalid portal grant source')
            grants[row['id']] = row
        for row in office.db.execute('SELECT * FROM business_portal_principals').fetchall():
            identifier(row['id']); _line(row['name'], 'Name', 200); _line(row['email'], 'E-Mail', 254)
            if row['revision'] != (1 if row['active'] else 2):
                raise ValueError('Invalid portal identity history')
        for row in office.db.execute('SELECT * FROM business_portal_revocations').fetchall():
            grant = grants[row['grant_id']]
            if row['kind'] not in ('staff', 'restore') or (row['revoked_by'] is None) != (row['kind'] == 'restore'):
                raise ValueError('Invalid portal revocation actor')
            _at(row['created_at']); _line(row['reason'], 'Widerruf', 500)
        for row in office.db.execute('SELECT * FROM business_portal_sessions').fetchall():
            grant = grants[row['grant_id']]
            if (not re.fullmatch(_HASH, row['token_hash']) or row['principal_id'] != grant['principal_id']
                    or not timedelta(0) < _at(row['expires_at']) - _at(row['created_at']) <= timedelta(minutes=30)
                    or _at(row['expires_at']) > _at(grant['expires_at'])):
                raise ValueError('Invalid portal session')
        decisions = {}
        for row in office.db.execute('SELECT * FROM business_portal_decisions').fetchall():
            grant = grants[row['grant_id']]
            if (any(row[key] != grant[key] for key in ('offer_id', 'principal_id', 'source_revision', 'content_hash', 'pdf_hash'))
                    or row['statement_version'] != STATEMENTS['version'] or row['decision'] not in ('accepted', 'declined')
                    or row['statement_text'] != STATEMENTS[row['decision']]
                    or not _at(grant['created_at']) <= _at(row['created_at']) < _at(grant['expires_at'])):
                raise ValueError('Invalid portal decision binding')
            identifier(row['id']); _line(row['declared_name'], 'Name', 200)
            decisions[row['id']] = row
        adoptions = {}
        for row in office.db.execute('SELECT * FROM business_portal_adoptions').fetchall():
            decision = decisions[row['decision_id']]
            grant = grants[decision['grant_id']]
            target = office.db.execute('SELECT * FROM business_documents WHERE id=?', (row['document_id'],)).fetchone()
            relation = office.db.execute("SELECT * FROM business_document_relations WHERE target_id=? AND source_id=? AND kind='converted_from'",
                                         (row['document_id'], row['offer_id'])).fetchone()
            if (decision['decision'] != 'accepted' or row['offer_id'] != decision['offer_id'] or row['project_id'] != grant['project_id']
                    or not target or target['kind'] != 'order_confirmation' or target['project_id'] != grant['project_id']
                    or target['customer_id'] != grant['customer_id'] or not relation or relation['source_sha256'] != grant['content_hash']
                    or json.loads(target['payload_json']).get('converted_from') != row['offer_id']):
                raise ValueError('Invalid portal adoption target')
            identifier(row['id']); _at(row['created_at'])
            adoptions[row['id']] = row
        for row in office.db.execute('SELECT * FROM business_portal_staff_requests').fetchall():
            identifier(row['request_id'])
            if not re.fullmatch(_HASH, row['request_hash']):
                raise ValueError('Invalid portal staff receipt')
            target = adoptions.get(row['target_id']) if row['operation'] == 'adopt' else grants.get(row['target_id'])
            if not target or row['operation'] not in ('grant', 'revoke', 'adopt'):
                raise ValueError('Missing portal staff receipt target')
            if row['operation'] != 'revoke' and target['created_by'] != row['user_id']:
                raise ValueError('Wrong portal staff receipt actor')
            if row['operation'] == 'revoke' and not office.db.execute('SELECT 1 FROM business_portal_revocations WHERE grant_id=?', (row['target_id'],)).fetchone():
                raise ValueError('Missing portal revocation')
        for row in office.db.execute('SELECT * FROM business_portal_decision_requests').fetchall():
            decision = decisions[row['decision_id']]
            identifier(row['request_id'])
            if (not re.fullmatch(_HASH, row['request_hash']) or row['grant_id'] != decision['grant_id']
                    or row['principal_id'] != decision['principal_id']):
                raise ValueError('Invalid portal decision receipt')
    except (Problem, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid portal history') from error
    return True


def methods(path):
    if path == '/portal/grants':
        return 'GET, POST'
    if re.fullmatch(r'/portal/grants/' + _ID + r'/revoke', path) or re.fullmatch(r'/portal/offers/' + _ID + r'/adopt', path):
        return 'POST'
    return None


def dispatch(office, actor, path, method, data):
    allowed = methods(path)
    if allowed is None:
        return None
    if method not in allowed.split(', '):
        raise Problem(405, 'Methode nicht unterstützt')
    if not isinstance(data, dict):
        raise Problem(400, 'JSON-Objekt erwartet')
    query = data.get('_query', {})
    body = {key: value for key, value in data.items() if key != '_query'}
    if not isinstance(query, dict):
        raise Problem(400, 'Eindeutige Portalfilter erwartet')
    api = Portal(office)
    if path == '/portal/grants' and method == 'GET':
        if body or not isinstance(query, dict) or set(query) != {'offer_id'}:
            raise Problem(400, 'Genau eine Angebots-ID als Filter erwartet')
        return api.list_grants(actor, query['offer_id']), 200, 'application/json'
    if query:
        raise Problem(400, 'Keine zusätzlichen Portalfilter erlaubt')
    if path == '/portal/grants':
        return api.create_grant(actor, body), 201, 'application/json'
    identifier_ = path.split('/')[3]
    if path.endswith('/revoke'):
        return api.revoke_grant(actor, identifier_, body), 200, 'application/json'
    return api.adopt(actor, identifier_, body), 201, 'application/json'
