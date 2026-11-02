"""EUR cash provenance before tax classification; no bank or tax side effects.

Proof schema 1 binds complete immutable payment/allocation rows and final
document archive digests, or original receipt metadata and an exact review row.
Original bytes are verified but never copied into a cash snapshot. Account and
cash histories are append-only; existing finance sources are never changed.
"""
from decimal import Decimal
from functools import wraps
import hashlib
import json
import re
import sqlite3
import unicodedata
import uuid

from core import Problem, canonical
from business_documents import Documents, INVOICES, MAX_PDF
from business_finance import Finance
from business_operations import Domain, identifier, iso_date, text, transaction


FEATURES = ('accounting_prejournal',)
_TABLES = tuple('business_accounting_' + name for name in
                ('accounts', 'account_versions', 'cash_events', 'source_links', 'receipt_bindings', 'requests'))
_ID = r'[a-f0-9]{32}'
_HASH = r'[a-f0-9]{64}'
_MAX_AMOUNT = Decimal('999999999.99')
_ACCOUNT = ('id', 'code', 'name', 'kind', 'currency', 'active', 'revision', 'created_by', 'created_at')
_RECEIPT_SNAPSHOT = ('receipt_id', 'project_id', 'filename', 'media_type', 'original_sha256', 'review_revision',
                     'review_sha256', 'vendor', 'invoice_number', 'issue_date', 'net', 'tax', 'gross', 'currency')


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BLOB', 'BYTEA'):
        raise ValueError('Unsupported binary type')
    return [
        '''CREATE TABLE IF NOT EXISTS business_accounting_accounts(
        id TEXT PRIMARY KEY, code TEXT NOT NULL, code_key TEXT NOT NULL UNIQUE,
        kind TEXT NOT NULL CHECK(kind IN ('bank','cash','payment_service')), currency TEXT NOT NULL CHECK(currency='EUR'),
        created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_accounting_account_versions(
        account_id TEXT NOT NULL REFERENCES business_accounting_accounts(id), revision INTEGER NOT NULL CHECK(revision>0),
        payload_json TEXT NOT NULL, payload_sha256 TEXT NOT NULL CHECK(length(payload_sha256)=64),
        updated_by TEXT NOT NULL REFERENCES users(id), updated_at TEXT NOT NULL, PRIMARY KEY(account_id,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_accounting_cash_events(
        id TEXT PRIMARY KEY, sequence INTEGER NOT NULL UNIQUE CHECK(sequence>0),
        account_id TEXT NOT NULL, account_revision INTEGER NOT NULL, account_json TEXT NOT NULL,
        direction TEXT NOT NULL CHECK(direction IN ('in','out')), amount TEXT NOT NULL, currency TEXT NOT NULL CHECK(currency='EUR'),
        cash_date TEXT NOT NULL, evidence_reference TEXT NOT NULL, evidence_key TEXT NOT NULL, reference TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL,
        UNIQUE(account_id,evidence_key), FOREIGN KEY(account_id,account_revision) REFERENCES business_accounting_account_versions(account_id,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_accounting_source_links(
        event_id TEXT PRIMARY KEY REFERENCES business_accounting_cash_events(id), kind TEXT NOT NULL CHECK(kind IN ('payment','receipt')),
        source_id TEXT NOT NULL, source_hash TEXT NOT NULL CHECK(length(source_hash)=64), proof_json TEXT NOT NULL, snapshot_json TEXT NOT NULL,
        payment_id TEXT UNIQUE REFERENCES business_payments(id), receipt_id TEXT REFERENCES business_incoming_receipts(id),
        review_revision INTEGER, cash_revision INTEGER CHECK(cash_revision>0), original_sha256 TEXT,
        UNIQUE(receipt_id,cash_revision), FOREIGN KEY(receipt_id,review_revision) REFERENCES business_receipt_reviews(receipt_id,revision),
        CHECK((kind='payment' AND payment_id=source_id AND payment_id IS NOT NULL AND receipt_id IS NULL
        AND review_revision IS NULL AND cash_revision IS NULL AND original_sha256 IS NULL)
        OR (kind='receipt' AND receipt_id=source_id AND receipt_id IS NOT NULL AND payment_id IS NULL
        AND review_revision IS NOT NULL AND review_revision>0 AND cash_revision IS NOT NULL
        AND original_sha256 IS NOT NULL AND length(original_sha256)=64)))''',
        '''CREATE TABLE IF NOT EXISTS business_accounting_receipt_bindings(
        original_sha256 TEXT PRIMARY KEY CHECK(length(original_sha256)=64), receipt_id TEXT NOT NULL UNIQUE REFERENCES business_incoming_receipts(id),
        first_event_id TEXT NOT NULL UNIQUE REFERENCES business_accounting_cash_events(id))''',
        '''CREATE TABLE IF NOT EXISTS business_accounting_requests(
        user_id TEXT NOT NULL REFERENCES users(id), request_id TEXT NOT NULL, operation TEXT NOT NULL,
        request_hash TEXT NOT NULL CHECK(length(request_hash)=64), result_json TEXT NOT NULL,
        PRIMARY KEY(user_id,request_id))''',
        'CREATE INDEX IF NOT EXISTS business_accounting_sources_receipt ON business_accounting_source_links(receipt_id,cash_revision)',
    ]


def protected_tables():
    return _TABLES


def runtime_privileges():
    return {table: ('SELECT', 'INSERT') for table in _TABLES}


def guard_statements(dialect):
    if dialect == 'sqlite':
        result = [f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} ON {table} "
                  "BEGIN SELECT RAISE(ABORT,'immutable accounting history'); END"
                  for table in _TABLES for action in ('UPDATE', 'DELETE')]
        conflicts = {
            'business_accounting_accounts': 'id=NEW.id OR code_key=NEW.code_key',
            'business_accounting_account_versions': 'account_id=NEW.account_id AND revision=NEW.revision',
            'business_accounting_cash_events': 'id=NEW.id OR sequence=NEW.sequence OR (account_id=NEW.account_id AND evidence_key=NEW.evidence_key)',
            'business_accounting_source_links': 'event_id=NEW.event_id OR payment_id=NEW.payment_id OR (receipt_id=NEW.receipt_id AND cash_revision=NEW.cash_revision)',
            'business_accounting_receipt_bindings': 'original_sha256=NEW.original_sha256 OR receipt_id=NEW.receipt_id OR first_event_id=NEW.first_event_id',
            'business_accounting_requests': 'user_id=NEW.user_id AND request_id=NEW.request_id',
            # Additive protection of legacy finance rows. Their original module
            # DDL and migration checksum remain byte-for-byte unchanged.
            'business_payments': 'id=NEW.id OR source_id=NEW.source_id',
            'business_payment_allocations': 'id=NEW.id OR (payment_id=NEW.payment_id AND document_id=NEW.document_id)',
            'business_incoming_receipts': 'id=NEW.id',
            'business_receipt_reviews': 'receipt_id=NEW.receipt_id AND revision=NEW.revision',
        }
        for table, condition in conflicts.items():
            name = table + '_insert_guard' if table in _TABLES else 'business_accounting_' + table.removeprefix('business_') + '_insert_guard'
            result.append(f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE INSERT ON {table} "
                          f"WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition}) "
                          "BEGIN SELECT RAISE(ABORT,'immutable accounting source'); END")
        return result
    if dialect != 'postgresql':
        raise ValueError('Unsupported guard dialect')
    result = ["""CREATE OR REPLACE FUNCTION business_accounting_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'immutable accounting history'; END; $$"""]
    for table in _TABLES:
        for action in ('UPDATE', 'DELETE'):
            name = table + '_' + action.lower() + '_guard'
            result.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) "
                          f"THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION "
                          "business_accounting_immutable_guard(); END IF; END $$")
    return result


def _sha(value):
    return hashlib.sha256(value.encode('utf-8') if isinstance(value, str) else value).hexdigest()


def _money(value, *, positive=True):
    if not isinstance(value, str) or not re.fullmatch(r'(?:0|[1-9][0-9]{0,8})\.[0-9]{2}', value):
        raise Problem(400, 'Kanonischer EUR-Centbetrag mit zwei Nachkommastellen erwartet')
    amount = Decimal(value)
    if amount > _MAX_AMOUNT or (positive and amount <= 0):
        raise Problem(400, 'Positiver begrenzter EUR-Centbetrag erwartet')
    return amount


def _amount(value):
    return format(value, '.2f')


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch(_HASH, value):
        raise Problem(400, 'SHA-256-Prüfsumme erwartet')
    return value


def _line(value, name, maximum, *, required=True):
    value = text(value, name, maximum, required=required)
    if any(ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise Problem(400, 'Einzeiliger Text erwartet: ' + name)
    return value


def _evidence(value):
    value = _line(value, 'Zahlungsnachweis-Referenz', 200)
    return value, ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def _body(data, fields):
    if not isinstance(data, dict) or set(data) != set(fields) | {'request_id', 'confirmation'}:
        raise Problem(400, 'Vollständige bekannte Vorjournalfelder erwartet')
    identifier(data['request_id'], 'request_id')
    if data['confirmation'] is not True:
        raise Problem(400, 'Vorgang ausdrücklich bestätigen')


def _page(limit, offset):
    if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or not 0 <= offset <= 100000:
        raise Problem(400, 'Limit 1 bis 100 und Offset 0 bis 100000 erwartet')


def _paged(items, limit, offset):
    total = len(items)
    following = offset + len(items[offset:offset + limit])
    return dict(items=items[offset:offset + limit], total=total,
                next_offset=following if following < total and following <= 100000 else None, scope='authorized_sources')


def _checked_source(method):
    """Invalid stored source data is a conflict, never a malformed HTTP input."""
    @wraps(method)
    def checked(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except Problem as error:
            if error.status != 400:
                raise
            raise Problem(409, 'Gespeicherte Quelle besteht die Integritätsprüfung nicht') from None
        except (ValueError, KeyError, TypeError):
            raise Problem(409, 'Gespeicherte Quelle besteht die Integritätsprüfung nicht') from None
    return checked


class Accounting(Domain):
    def _access(self, actor, extra=None):
        fresh = self.access(actor, 'accounting.read')
        self.access(fresh, 'finance.read')
        if extra:
            self.access(fresh, extra)
        return fresh

    def _write_gate(self):
        from business_schema import state, require_financial_release, require_runtime_security
        from business_organization import module_enabled
        if state(self.office)['compatibility_mode'] != 'business':
            raise Problem(409, 'Vorjournal ist im Rückkehrmodus schreibgeschützt')
        if not module_enabled(self.office, 'finance'):
            raise Problem(423, 'Finanzen sind fachlich deaktiviert')
        require_financial_release(self.office)
        require_runtime_security(self.office)

    def status(self, actor):
        with transaction(self.office):
            self._access(actor)
            allowed = True
            try:
                self._write_gate()
            except Problem as error:
                if error.status not in (409, 423):
                    raise
                allowed = False
            return dict(profile_status='unconfigured', tax_status='unconfigured', tax_result_available=False,
                        scope='authorized_sources', writes_allowed=allowed)

    def _account(self, account_id, revision=None):
        identifier(account_id, 'Geldkonto-ID')
        row = self.office.db.execute('SELECT * FROM business_accounting_account_versions WHERE account_id=? '
            + ('AND revision=?' if revision is not None else 'ORDER BY revision DESC LIMIT 1'),
            (account_id, revision) if revision is not None else (account_id,)).fetchone()
        if not row:
            raise Problem(404, 'Geldkonto nicht verfügbar')
        value = json.loads(row['payload_json'])
        identity = self.office.db.execute('SELECT * FROM business_accounting_accounts WHERE id=?', (account_id,)).fetchone()
        if (not identity or _sha(row['payload_json']) != row['payload_sha256'] or set(value) != set(_ACCOUNT)
                or value['revision'] != row['revision'] or any(value[key] != identity[key] for key in
                    ('id', 'code', 'kind', 'currency', 'created_by', 'created_at')) or type(value['active']) is not bool):
            raise Problem(409, 'Geldkontohistorie besteht die Integritätsprüfung nicht')
        return value

    def accounts(self, actor):
        with transaction(self.office):
            self._access(actor)
            return {'items': [self._account(row['id']) for row in self.office.db.execute(
                'SELECT id FROM business_accounting_accounts ORDER BY code_key,id').fetchall()]}

    def _request(self, actor, operation, target, data):
        digest = _sha(canonical([operation, target, data]))
        row = self.office.db.execute('SELECT * FROM business_accounting_requests WHERE user_id=? AND request_id=?',
                                     (actor['id'], data['request_id'])).fetchone()
        if row and (row['operation'] != operation or row['request_hash'] != digest):
            raise Problem(409, 'Vorgangs-ID wurde mit anderem Inhalt verwendet')
        return digest, json.loads(row['result_json']) if row else None

    def _remember(self, actor, data, operation, digest, result):
        self.office.db.execute('INSERT INTO business_accounting_requests(user_id,request_id,operation,request_hash,result_json) VALUES(?,?,?,?,?)',
                               (actor['id'], data['request_id'], operation, digest, canonical(result)))

    def _save_account_version(self, actor, value):
        payload = canonical(value)
        self.office.db.execute('INSERT INTO business_accounting_account_versions(account_id,revision,payload_json,payload_sha256,updated_by,updated_at) '
            'VALUES(?,?,?,?,?,?)', (value['id'], value['revision'], payload, _sha(payload), actor['id'], self.now()))

    def create_account(self, actor, data):
        _body(data, ('code', 'name', 'kind'))
        if not isinstance(data['code'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', data['code']):
            raise Problem(400, 'Geldkontocode aus 1 bis 40 Buchstaben, Ziffern, Unterstrich oder Bindestrich erwartet')
        if data['kind'] not in ('bank', 'cash', 'payment_service'):
            raise Problem(400, 'Bank, Kasse oder Zahlungsdienst erwartet')
        name = _line(data['name'], 'Kontoname', 200)
        with transaction(self.office):
            fresh = self._access(actor, 'accounting.admin'); self._write_gate()
            digest, replay = self._request(fresh, 'account.create', None, data)
            if replay:
                return self._account(replay['account_id'], replay['revision'])
            if self.office.db.execute('SELECT 1 FROM business_accounting_accounts WHERE code_key=?', (data['code'].casefold(),)).fetchone():
                raise Problem(409, 'Geldkontocode ist bereits vergeben')
            account_id, stamp = uuid.uuid4().hex, self.now()
            self.office.db.execute('INSERT INTO business_accounting_accounts(id,code,code_key,kind,currency,created_by,created_at) VALUES(?,?,?,?,?,?,?)',
                                   (account_id, data['code'], data['code'].casefold(), data['kind'], 'EUR', fresh['id'], stamp))
            value = dict(id=account_id, code=data['code'], name=name, kind=data['kind'], currency='EUR', active=True,
                         revision=1, created_by=fresh['id'], created_at=stamp)
            self._save_account_version(fresh, value)
            self._remember(fresh, data, 'account.create', digest, dict(account_id=account_id, revision=1))
            self.office.audit(fresh, 'business.accounting.account_created', account_id)
            return value

    def update_account(self, actor, account_id, data):
        _body(data, ('revision', 'name', 'active'))
        name = _line(data['name'], 'Kontoname', 200)
        if type(data['active']) is not bool or type(data['revision']) is not int or data['revision'] < 1:
            raise Problem(400, 'Aktivstatus und positive Kontorevision erwartet')
        with transaction(self.office):
            fresh = self._access(actor, 'accounting.admin'); self._write_gate()
            digest, replay = self._request(fresh, 'account.update', account_id, data)
            if replay:
                return self._account(replay['account_id'], replay['revision'])
            old = self._account(account_id)
            if old['revision'] != data['revision']:
                raise Problem(409, 'Geldkonto wurde geändert; neu laden')
            value = dict(old, name=name, active=data['active'], revision=old['revision'] + 1)
            self._save_account_version(fresh, value)
            self._remember(fresh, data, 'account.update', digest, dict(account_id=account_id, revision=value['revision']))
            self.office.audit(fresh, 'business.accounting.account_updated', account_id)
            return value

    def _document_proof(self, row):
        archive = self.office.db.execute('SELECT * FROM business_document_archives WHERE document_id=?', (row['id'],)).fetchone()
        if row['status'] != 'final' or row['kind'] not in INVOICES or row['kind'] == 'credit_note' or not archive:
            raise Problem(409, 'Zahlungsquelle benötigt unveränderte finale Ausgangsrechnungen')
        pdf = bytes(archive['pdf'])
        if (row['payload_json'] != archive['payload_json'] or row['payload_sha256'] != archive['payload_sha256']
                or _sha(row['payload_json']) != row['payload_sha256'] or not pdf.startswith(b'%PDF-')
                or len(pdf) > MAX_PDF or _sha(pdf) != archive['pdf_sha256']
                or (archive['xml'] is None) != (archive['xml_sha256'] is None)
                or archive['xml'] is not None and _sha(bytes(archive['xml'])) != archive['xml_sha256']):
            raise Problem(409, 'Rechnungsarchiv besteht die Integritätsprüfung nicht')
        payload = json.loads(row['payload_json'])
        if (payload.get('id') != row['id'] or payload.get('number') != row['number'] or payload.get('project_id') != row['project_id']
                or payload.get('kind') != row['kind'] or payload.get('document_revision') != row['revision'] - 1):
            raise Problem(409, 'Rechnungsfassung ist nicht konsistent')
        return dict(document_id=row['id'], number=row['number'], project_id=row['project_id'], customer_id=row['customer_id'],
                    revision=row['revision'], kind=row['kind'], payload_sha256=row['payload_sha256'],
                    pdf_sha256=archive['pdf_sha256'], xml_sha256=archive['xml_sha256'])

    @_checked_source
    def _payment_source(self, actor, payment_id):
        identifier(payment_id, 'Zahlungs-ID')
        row = self.office.db.execute('SELECT * FROM business_payments WHERE id=?', (payment_id,)).fetchone()
        if not row:
            raise Problem(404, 'Zahlungsquelle nicht verfügbar')
        allocations = self.office.db.execute('SELECT * FROM business_payment_allocations WHERE payment_id=? ORDER BY document_id,id', (payment_id,)).fetchall()
        if actor is not None:
            fresh = self.access(actor, 'finance.read')
            if not allocations and fresh['role'] != 'owner' and fresh['id'] != row['created_by']:
                raise Problem(403, 'Diese unzugeordnete Zahlungsquelle ist nicht freigegeben')
            # Additional assignments extend current authorization only. Never
            # add them to this immutable E1a proof or its historical DTO.
            from business_accounting_allocations import require_effective_payment_access
            require_effective_payment_access(self.office, fresh, payment_id)
        # Resolve every project right before verifying or revealing any member
        # of a multi-document payment, including malformed hidden sources.
        documents = []
        for allocation in allocations:
            document = (Documents(self.office)._row(actor, allocation['document_id']) if actor is not None else
                        self.office.db.execute('SELECT * FROM business_documents WHERE id=?', (allocation['document_id'],)).fetchone())
            if not document:
                raise Problem(409, 'Rechnungsquelle fehlt')
            documents.append(document)
        public_allocations, document_proofs = [], []
        amount, allocated = _money(row['amount']), Decimal(0)
        if row['currency'] != 'EUR' or row['kind'] not in ('receipt', 'refund'):
            raise Problem(409, 'Ungültige Zahlungsquelle')
        iso_date(row['booking_date'])
        for allocation, document in zip(allocations, documents):
            proof = self._document_proof(document)
            document_proofs.append(proof)
            allocated += _money(allocation['amount'])
            public_allocations.append({**{key: proof[key] for key in ('document_id', 'number', 'project_id', 'payload_sha256', 'pdf_sha256')},
                                       'amount': allocation['amount']})
        if allocated > amount:
            raise Problem(409, 'Zahlungszuordnungen überschreiten die Zahlungsquelle')
        proof = dict(schema_version=1, payment=dict(row), allocations=[dict(value) for value in allocations], documents=document_proofs)
        public = dict(payment_id=payment_id, kind=row['kind'], direction='in' if row['kind'] == 'receipt' else 'out', amount=row['amount'],
            currency='EUR', booking_date=row['booking_date'], reference=row['reference'], source_id=row['source_id'],
            source_hash=_sha(canonical(proof)), allocations=public_allocations, unallocated=_amount(amount - allocated))
        return public, proof

    @_checked_source
    def _receipt_source(self, actor, receipt_id, revision=None):
        identifier(receipt_id, 'Eingangsbeleg-ID')
        row = (Finance(self.office)._incoming(actor, receipt_id) if actor is not None else
               self.office.db.execute('SELECT * FROM business_incoming_receipts WHERE id=?', (receipt_id,)).fetchone())
        if not row:
            raise Problem(404, 'Eingangsbelegquelle nicht verfügbar')
        original = bytes(row['original'])
        if not 1 <= len(original) <= 20 * 1024 * 1024 or _sha(original) != row['sha256']:
            raise Problem(409, 'Eingangsoriginal besteht die Integritätsprüfung nicht')
        capture = json.loads(row['payload_json'])
        if capture.get('sha256') != row['sha256'] or capture.get('status') != 'needs_review':
            raise Problem(409, 'Eingangsoriginalnachweis ist nicht konsistent')
        review = self.office.db.execute('SELECT * FROM business_receipt_reviews WHERE receipt_id=? '
            + ('AND revision=?' if revision is not None else 'ORDER BY revision DESC LIMIT 1'),
            (receipt_id, revision) if revision is not None else (receipt_id,)).fetchone()
        if not review:
            return None, None
        if _sha(review['payload_json']) != review['payload_sha256']:
            raise Problem(409, 'Belegprüfung besteht die Integritätsprüfung nicht')
        value = json.loads(review['payload_json'])
        if value.get('status') != 'reviewed' or value.get('currency') != 'EUR':
            return None, None
        gross = _money(value['gross'], positive=False)
        if _money(value['net'], positive=False) + _money(value['tax'], positive=False) != gross:
            raise Problem(409, 'Geprüfte Belegbeträge sind nicht konsistent')
        if gross <= 0:
            return None, None
        iso_date(value['issue_date'])
        proof = dict(schema_version=1, receipt={key: row[key] for key in row.keys() if key != 'original'}, review=dict(review))
        public = dict(receipt_id=receipt_id, project_id=row['project_id'], filename=row['filename'], media_type=row['media_type'],
            original_sha256=row['sha256'], review_revision=review['revision'], review_sha256=review['payload_sha256'],
            source_hash=_sha(canonical(proof)), **{key: value[key] for key in ('vendor', 'invoice_number', 'issue_date', 'net', 'tax', 'gross', 'currency')})
        return public, proof

    def _receipt_state(self, source):
        rows = self.office.db.execute("SELECT s.review_revision,s.cash_revision,e.amount FROM business_accounting_source_links s "
            'JOIN business_accounting_cash_events e ON e.id=s.event_id WHERE s.receipt_id=? ORDER BY s.cash_revision', (source['receipt_id'],)).fetchall()
        paid = sum((_money(row['amount']) for row in rows), Decimal(0))
        remaining = max(Decimal(0), _money(source['gross']) - paid)
        binding = self.office.db.execute('SELECT receipt_id FROM business_accounting_receipt_bindings WHERE original_sha256=?',
                                         (source['original_sha256'],)).fetchone()
        reason = ('duplicate_original' if binding and binding['receipt_id'] != source['receipt_id'] else
                  'review_changed' if rows and any(row['review_revision'] != source['review_revision'] for row in rows) else
                  'paid' if remaining == 0 else None)
        return dict(source, cash_revision=len(rows), paid_amount=_amount(paid), remaining_amount=_amount(remaining),
                    payable=reason is None, blocked_reason=reason)

    def payment_sources(self, actor, limit=50, offset=0):
        _page(limit, offset)
        with transaction(self.office):
            fresh = self._access(actor); items = []
            for row in self.office.db.execute('SELECT id FROM business_payments ORDER BY created_at DESC,id').fetchall():
                try:
                    public, _ = self._payment_source(fresh, row['id'])
                except Problem as error:
                    if error.status in (403, 404):
                        continue
                    raise
                link = self.office.db.execute('SELECT event_id FROM business_accounting_source_links WHERE payment_id=?', (row['id'],)).fetchone()
                if link:
                    self._event(fresh, link['event_id'])
                items.append(dict(public, linked_event_id=link['event_id'] if link else None))
            return _paged(items, limit, offset)

    def receipt_sources(self, actor, limit=50, offset=0):
        _page(limit, offset)
        with transaction(self.office):
            fresh = self._access(actor); items = []
            for row in self.office.db.execute('SELECT id FROM business_incoming_receipts ORDER BY created_at DESC,id').fetchall():
                try:
                    public, _ = self._receipt_source(fresh, row['id'])
                except Problem as error:
                    if error.status in (403, 404):
                        continue
                    raise
                if public:
                    for link in self.office.db.execute('SELECT event_id FROM business_accounting_source_links WHERE receipt_id=?', (row['id'],)).fetchall():
                        self._event(fresh, link['event_id'])
                    items.append(self._receipt_state(public))
            return _paged(items, limit, offset)

    def _event(self, actor, event_id):
        identifier(event_id, 'Geldfluss-ID')
        row = self.office.db.execute('SELECT * FROM business_accounting_cash_events WHERE id=?', (event_id,)).fetchone()
        link = self.office.db.execute('SELECT * FROM business_accounting_source_links WHERE event_id=?', (event_id,)).fetchone()
        if not row:
            raise Problem(404, 'Geldfluss nicht verfügbar')
        if not link:
            raise Problem(409, 'Geldflussquelle fehlt')
        if link['kind'] == 'payment':
            source, proof = self._payment_source(actor, link['source_id'])
            snapshot = {key: value for key, value in source.items() if key != 'source_hash'}
        else:
            source, proof = self._receipt_source(actor, link['source_id'], link['review_revision'])
            snapshot = {key: source[key] for key in _RECEIPT_SNAPSHOT} if source else None
        account = self._account(row['account_id'], row['account_revision'])
        if (not source or source['source_hash'] != link['source_hash'] or canonical(proof) != link['proof_json']
                or canonical(snapshot) != link['snapshot_json'] or canonical(account) != row['account_json']):
            raise Problem(409, 'Historischer Geldfluss besteht die Quellenprüfung nicht')
        reasons = ['tax_profile_unconfigured']
        if link['kind'] == 'payment' and snapshot['kind'] == 'refund':
            reasons.append('refund_origin_unresolved')
        return dict(id=row['id'], sequence=row['sequence'], account=account, direction=row['direction'], amount=row['amount'], currency=row['currency'],
            cash_date=row['cash_date'], evidence_reference=row['evidence_reference'], reference=row['reference'],
            source=dict(kind=link['kind'], id=link['source_id'], source_hash=link['source_hash'], snapshot=snapshot),
            classification_status='unclassified', unresolved_reasons=reasons, created_by=row['created_by'], created_at=row['created_at'])

    def event(self, actor, event_id):
        with transaction(self.office):
            return self._event(self._access(actor), event_id)

    def events(self, actor, limit=50, offset=0):
        _page(limit, offset)
        with transaction(self.office):
            fresh = self._access(actor); items = []
            for row in self.office.db.execute('SELECT id FROM business_accounting_cash_events ORDER BY sequence DESC,id').fetchall():
                try:
                    items.append(self._event(fresh, row['id']))
                except Problem as error:
                    if error.status in (403, 404):
                        continue
                    raise
            return dict(_paged(items, limit, offset), tax_result_available=False)

    def _cash_inputs(self, data):
        identifier(data['account_id'], 'Geldkonto-ID'); _hash(data['source_hash'])
        if type(data['account_revision']) is not int or data['account_revision'] < 1:
            raise Problem(400, 'Positive Kontorevision erwartet')
        iso_date(data['cash_date'], 'Zahlungsdatum')
        return _evidence(data['evidence_reference'])

    def _active_account(self, data):
        value = self._account(data['account_id'])
        if not value['active'] or value['revision'] != data['account_revision']:
            raise Problem(409, 'Geldkonto deaktiviert oder geändert; neu laden')
        return value

    def _post_cash(self, actor, data, account, source, proof, kind, amount, direction, reference, cash_revision=None):
        evidence, key = _evidence(data['evidence_reference'])
        if self.office.db.execute('SELECT 1 FROM business_accounting_cash_events WHERE account_id=? AND evidence_key=?', (account['id'], key)).fetchone():
            raise Problem(409, 'Dieser Zahlungsnachweis ist auf dem Geldkonto bereits erfasst')
        event_id, stamp = uuid.uuid4().hex, self.now()
        sequence = self.office.db.execute('SELECT COALESCE(MAX(sequence),0)+1 FROM business_accounting_cash_events').fetchone()[0]
        self.office.db.execute('INSERT INTO business_accounting_cash_events(id,sequence,account_id,account_revision,account_json,direction,amount,currency,'
            'cash_date,evidence_reference,evidence_key,reference,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (event_id, sequence, account['id'], account['revision'], canonical(account), direction, amount, 'EUR', data['cash_date'], evidence, key,
             reference, actor['id'], stamp))
        snapshot = ({key: value for key, value in source.items() if key != 'source_hash'} if kind == 'payment' else
                    {key: source[key] for key in _RECEIPT_SNAPSHOT})
        source_id = source['payment_id'] if kind == 'payment' else source['receipt_id']
        self.office.db.execute('INSERT INTO business_accounting_source_links(event_id,kind,source_id,source_hash,proof_json,snapshot_json,'
            'payment_id,receipt_id,review_revision,cash_revision,original_sha256) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
            (event_id, kind, source_id, source['source_hash'], canonical(proof), canonical(snapshot), source_id if kind == 'payment' else None,
             source_id if kind == 'receipt' else None, source.get('review_revision'), cash_revision, source.get('original_sha256')))
        if kind == 'receipt' and cash_revision == 1:
            self.office.db.execute('INSERT INTO business_accounting_receipt_bindings(original_sha256,receipt_id,first_event_id) VALUES(?,?,?)',
                                   (source['original_sha256'], source_id, event_id))
        return event_id

    def import_payment(self, actor, data):
        _body(data, ('payment_id', 'source_hash', 'account_id', 'account_revision', 'cash_date', 'evidence_reference'))
        identifier(data['payment_id'], 'Zahlungs-ID'); self._cash_inputs(data)
        with transaction(self.office):
            fresh = self._access(actor, 'accounting.prepare'); self._write_gate()
            digest, replay = self._request(fresh, 'cash.import_payment', None, data)
            if replay:
                return self._event(fresh, replay['event_id'])
            source, proof = self._payment_source(fresh, data['payment_id'])
            if source['source_hash'] != data['source_hash']:
                raise Problem(409, 'Zahlungsquelle wurde geändert; neu laden')
            if self.office.db.execute('SELECT 1 FROM business_accounting_source_links WHERE payment_id=?', (data['payment_id'],)).fetchone():
                raise Problem(409, 'Zahlungsquelle bereits übernommen; vorhandenen Stand prüfen')
            account = self._active_account(data)
            event_id = self._post_cash(fresh, data, account, source, proof, 'payment', source['amount'], source['direction'], source['reference'])
            self._remember(fresh, data, 'cash.import_payment', digest, dict(event_id=event_id))
            self.office.audit(fresh, 'business.accounting.payment_imported', event_id)
            return self._event(fresh, event_id)

    def payout(self, actor, data):
        _body(data, ('receipt_id', 'source_hash', 'review_revision', 'review_sha256', 'original_sha256', 'account_id', 'account_revision',
                     'expected_cash_revision', 'amount', 'cash_date', 'evidence_reference', 'reference'))
        identifier(data['receipt_id'], 'Eingangsbeleg-ID'); self._cash_inputs(data)
        _hash(data['review_sha256']); _hash(data['original_sha256']); amount = _money(data['amount'])
        reference = _line(data['reference'], 'Verwendungszweck', 1000, required=False)
        if (type(data['review_revision']) is not int or data['review_revision'] < 1
                or type(data['expected_cash_revision']) is not int or data['expected_cash_revision'] < 0):
            raise Problem(400, 'Prüfversion und erwartete Auszahlungsrevision erforderlich')
        with transaction(self.office):
            fresh = self._access(actor, 'accounting.prepare'); self._write_gate()
            digest, replay = self._request(fresh, 'cash.payout', None, data)
            if replay:
                return self._event(fresh, replay['event_id'])
            source, proof = self._receipt_source(fresh, data['receipt_id'])
            if not source or any(source[key] != data[key] for key in ('source_hash', 'review_revision', 'review_sha256', 'original_sha256')):
                raise Problem(409, 'Aktuell geprüfte unveränderte Eingangsbelegquelle erforderlich')
            state = self._receipt_state(source)
            if not state['payable']:
                raise Problem(409, 'Auszahlung gesperrt; Belegstand und Zahlungsnachweise klären: ' + state['blocked_reason'])
            if state['cash_revision'] != data['expected_cash_revision'] or amount > _money(state['remaining_amount'], positive=False):
                raise Problem(409, 'Auszahlungsstand geändert oder geprüfter Restbetrag überschritten')
            account = self._active_account(data)
            event_id = self._post_cash(fresh, data, account, source, proof, 'receipt', data['amount'], 'out', reference, state['cash_revision'] + 1)
            self._remember(fresh, data, 'cash.payout', digest, dict(event_id=event_id))
            self.office.audit(fresh, 'business.accounting.payout_recorded', event_id)
            return self._event(fresh, event_id)


def _verify_guards(office):
    if isinstance(office.db, sqlite3.Connection):
        normalize = lambda value: re.sub(r'\s+', ' ', value.replace('IF NOT EXISTS ', '')).strip().lower()
        for sql in guard_statements('sqlite'):
            name = re.search(r'CREATE TRIGGER IF NOT EXISTS (\w+)', sql)[1]
            row = office.db.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?", (name,)).fetchone()
            if not row or normalize(row[0]) != normalize(sql):
                raise ValueError('Missing or modified accounting guard')
    else:
        from business_documents import _validate_pg_guards
        _validate_pg_guards(office.db, guard_statements('postgresql'))


def validate_integrity(office):
    api = Accounting(office)
    try:
        accounts = {}
        versions = {}
        for row in office.db.execute('SELECT * FROM business_accounting_accounts').fetchall():
            identifier(row['id'])
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', row['code']) or row['code'].casefold() != row['code_key']:
                raise ValueError('Invalid accounting account identity')
            history = office.db.execute('SELECT revision FROM business_accounting_account_versions WHERE account_id=? ORDER BY revision', (row['id'],)).fetchall()
            if not history or [value[0] for value in history] != list(range(1, len(history) + 1)):
                raise ValueError('Incomplete accounting account history')
            for revision in history:
                value = api._account(row['id'], revision[0]); _line(value['name'], 'Kontoname', 200)
                versions[(row['id'], revision[0])] = value
            accounts[row['id']] = row
        events = {}; receipt_totals = {}; payment_ids = set(); sources = {}
        for expected, row in enumerate(office.db.execute('SELECT * FROM business_accounting_cash_events ORDER BY sequence').fetchall(), 1):
            identifier(row['id']); amount = _money(row['amount']); iso_date(row['cash_date'])
            evidence, key = _evidence(row['evidence_reference'])
            if row['sequence'] != expected or key != row['evidence_key'] or evidence != row['evidence_reference']:
                raise ValueError('Invalid accounting event sequence or evidence')
            public = api._event(None, row['id'])
            source = office.db.execute('SELECT * FROM business_accounting_source_links WHERE event_id=?', (row['id'],)).fetchone()
            if source['kind'] == 'payment':
                snapshot = public['source']['snapshot']
                if (source['payment_id'] != source['source_id'] or source['payment_id'] in payment_ids
                        or (row['direction'], row['amount'], row['reference']) != (snapshot['direction'], snapshot['amount'], snapshot['reference'])):
                    raise ValueError('Invalid imported payment event')
                payment_ids.add(source['payment_id'])
            else:
                snapshot = public['source']['snapshot']
                prior, paid, revision = receipt_totals.get(source['source_id'], (0, Decimal(0), source['review_revision']))
                if (source['receipt_id'] != source['source_id'] or source['cash_revision'] != prior + 1 or source['review_revision'] != revision
                        or row['direction'] != 'out' or paid + amount > _money(snapshot['gross'])
                        or source['original_sha256'] != snapshot['original_sha256']):
                    raise ValueError('Invalid cumulative receipt payout')
                binding = office.db.execute('SELECT * FROM business_accounting_receipt_bindings WHERE original_sha256=?', (snapshot['original_sha256'],)).fetchone()
                if not binding or binding['receipt_id'] != source['source_id'] or (prior == 0 and binding['first_event_id'] != row['id']):
                    raise ValueError('Invalid original receipt binding')
                receipt_totals[source['source_id']] = (prior + 1, paid + amount, revision)
            events[row['id']] = row
            sources[row['id']] = source
        if len(events) != office.db.execute('SELECT COUNT(*) FROM business_accounting_source_links').fetchone()[0]:
            raise ValueError('Orphan accounting source')
        if len(receipt_totals) != office.db.execute('SELECT COUNT(*) FROM business_accounting_receipt_bindings').fetchone()[0]:
            raise ValueError('Orphan accounting original binding')
        observed_versions, observed_events = set(), set()
        for row in office.db.execute('SELECT * FROM business_accounting_requests').fetchall():
            identifier(row['request_id']); _hash(row['request_hash']); result = json.loads(row['result_json'])
            if row['operation'] in ('account.create', 'account.update') and set(result) == {'account_id', 'revision'}:
                key = (result['account_id'], result['revision'])
                version = office.db.execute('SELECT updated_by FROM business_accounting_account_versions WHERE account_id=? AND revision=?', key).fetchone()
                if not version or version[0] != row['user_id'] or key in observed_versions:
                    raise ValueError('Invalid accounting account receipt')
                observed_versions.add(key)
            elif row['operation'] in ('cash.import_payment', 'cash.payout') and set(result) == {'event_id'}:
                event = events.get(result['event_id']); source = sources.get(result['event_id'])
                if (not event or event['created_by'] != row['user_id'] or result['event_id'] in observed_events
                        or (source['kind'] == 'payment') != (row['operation'] == 'cash.import_payment')):
                    raise ValueError('Invalid accounting cash receipt')
                observed_events.add(result['event_id'])
            else:
                raise ValueError('Invalid accounting request operation')
        if observed_events != set(events) or observed_versions != set(versions):
            raise ValueError('Missing accounting transaction receipt')
        _verify_guards(office)
    except (Problem, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid accounting history') from error
    return True


def restore_horizon(office):
    """Sensitive operator-only evidence; no DDL, commit, source import or tax claim."""
    from business_schema import _tables
    with office.lock:
        actual = _tables(office)
        installed = ('business_schema_migrations' in actual and office.db.execute(
            "SELECT 1 FROM business_schema_migrations WHERE module='business_accounting'").fetchone() is not None)
        present = set(_TABLES) & actual
        if not present and not installed:
            return None
        if present != set(_TABLES):
            raise ValueError('Incomplete accounting installation')
        validate_integrity(office)
        snapshot = {table: sorted((dict(row) for row in office.db.execute('SELECT * FROM ' + table).fetchall()), key=canonical) for table in _TABLES}
        return dict(schema_version=1, accounts_count=len(snapshot[_TABLES[0]]), account_versions_count=len(snapshot[_TABLES[1]]),
            cash_events_count=len(snapshot[_TABLES[2]]), source_links_count=len(snapshot[_TABLES[3]]),
            max_sequence=max((row['sequence'] for row in snapshot[_TABLES[2]]), default=0),
            sha256=_sha(canonical(dict(schema_version=1, tables=snapshot))))


def methods(path):
    if path in ('/accounting/status', '/accounting/sources/payments', '/accounting/sources/receipts', '/accounting/events'):
        return 'GET'
    if path == '/accounting/accounts':
        return 'GET, POST'
    if re.fullmatch(r'/accounting/accounts/' + _ID, path) or path in ('/accounting/events/import-payment', '/accounting/events/payout'):
        return 'POST'
    if re.fullmatch(r'/accounting/events/' + _ID, path):
        return 'GET'
    return None


def dispatch(office, actor, path, method, data):
    allowed = methods(path)
    if allowed is None:
        return None
    if method not in allowed.split(', '):
        raise Problem(405, 'Methode nicht unterstützt')
    if not isinstance(data, dict) or not isinstance(data.get('_query', {}), dict):
        raise Problem(400, 'Eindeutige Vorjournalparameter erwartet')
    query = data.get('_query', {}); body = {key: value for key, value in data.items() if key != '_query'}
    api = Accounting(office)
    if method == 'GET':
        if body:
            raise Problem(400, 'GET erwartet keinen Anfragekörper')
        lists = {'/accounting/sources/payments': api.payment_sources, '/accounting/sources/receipts': api.receipt_sources, '/accounting/events': api.events}
        if path in lists:
            if set(query) - {'limit', 'offset'} or any(not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,6}', value) for value in query.values()):
                raise Problem(400, 'Nur ganzzahlige Limit-/Offsetfilter erwartet')
            result = lists[path](actor, int(query.get('limit', '50')), int(query.get('offset', '0')))
        else:
            if query:
                raise Problem(400, 'Keine zusätzlichen Filter erlaubt')
            result = api.status(actor) if path.endswith('/status') else api.accounts(actor) if path.endswith('/accounts') else api.event(actor, path.split('/')[-1])
        return result, 200, 'application/json'
    if query:
        raise Problem(400, 'Keine zusätzlichen Filter erlaubt')
    if path == '/accounting/accounts':
        return api.create_account(actor, body), 201, 'application/json'
    if path.startswith('/accounting/accounts/'):
        return api.update_account(actor, path.split('/')[-1], body), 200, 'application/json'
    result = api.import_payment(actor, body) if path.endswith('/import-payment') else api.payout(actor, body)
    return result, 201, 'application/json'
