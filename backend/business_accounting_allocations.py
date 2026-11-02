"""Append-only allocation of already evidenced receipts, without new cash flows.

The SQL projection helpers deliberately never call Finance or Accounting. E1a
continues to prove only its original source rows. Historical assignment proofs
retain the then-current invoice ledger; subsequent legitimate rows are allowed.
"""
from decimal import Decimal, InvalidOperation
from functools import wraps
import hashlib
import json
import re
import sqlite3
import uuid

from core import Problem, canonical
from business_documents import Documents, MAX_PDF, require
from business_operations import Domain, identifier, transaction

FEATURES = ('accounting_payment_allocation',)
_TABLES = ('business_accounting_allocation_entries', 'business_accounting_allocation_requests')
_ID = r'[a-f0-9]{32}'
_HASH = r'[a-f0-9]{64}'
_PREVIEW_FIELDS = {'source_hash', 'expected_revision', 'state_hash', 'customer_id', 'document_id',
                   'document_state_hash', 'amount', 'reason'}


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BLOB', 'BYTEA'):
        raise ValueError('Unsupported binary type')
    return [
        '''CREATE TABLE IF NOT EXISTS business_accounting_allocation_entries(
        id TEXT PRIMARY KEY, payment_id TEXT NOT NULL REFERENCES business_payments(id),
        event_id TEXT NOT NULL REFERENCES business_accounting_cash_events(id),
        revision INTEGER NOT NULL CHECK(revision>0), customer_id TEXT NOT NULL REFERENCES customers(id),
        document_id TEXT NOT NULL REFERENCES business_documents(id), amount TEXT NOT NULL,
        source_hash TEXT NOT NULL CHECK(length(source_hash)=64),
        previous_state_hash TEXT NOT NULL CHECK(length(previous_state_hash)=64),
        entry_json TEXT NOT NULL, entry_sha256 TEXT NOT NULL CHECK(length(entry_sha256)=64),
        document_proof_json TEXT NOT NULL, created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL,
        UNIQUE(payment_id,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_accounting_allocation_requests(
        user_id TEXT NOT NULL REFERENCES users(id), request_id TEXT NOT NULL,
        payment_id TEXT NOT NULL REFERENCES business_payments(id),
        request_json TEXT NOT NULL, request_hash TEXT NOT NULL CHECK(length(request_hash)=64),
        entry_id TEXT NOT NULL UNIQUE REFERENCES business_accounting_allocation_entries(id),
        PRIMARY KEY(user_id,request_id))''',
        'CREATE INDEX IF NOT EXISTS business_accounting_allocation_document ON business_accounting_allocation_entries(document_id,payment_id)',
    ]


def protected_tables():
    return _TABLES


def runtime_privileges():
    return {table: ('SELECT', 'INSERT') for table in _TABLES}


def guard_statements(dialect):
    if dialect == 'sqlite':
        guards = [f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} ON {table} "
                  "BEGIN SELECT RAISE(ABORT,'immutable payment allocation history'); END"
                  for table in _TABLES for action in ('UPDATE', 'DELETE')]
        for table, conflict in zip(_TABLES, (
                'id=NEW.id OR (payment_id=NEW.payment_id AND revision=NEW.revision)',
                '(user_id=NEW.user_id AND request_id=NEW.request_id) OR entry_id=NEW.entry_id')):
            guards.append(f'CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} '
                          f'WHEN EXISTS(SELECT 1 FROM {table} WHERE {conflict}) '
                          "BEGIN SELECT RAISE(ABORT,'immutable payment allocation history'); END")
        return guards
    if dialect != 'postgresql':
        raise ValueError('Unsupported guard dialect')
    guards = ["""CREATE OR REPLACE FUNCTION business_accounting_allocation_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'immutable payment allocation history'; END; $$"""]
    for table in _TABLES:
        for action in ('UPDATE', 'DELETE'):
            name = table + '_' + action.lower() + '_guard'
            guards.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) "
                          f"THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION "
                          "business_accounting_allocation_immutable_guard(); END IF; END $$")
    return guards


def _sha(value):
    return hashlib.sha256(value.encode('utf-8') if isinstance(value, str) else value).hexdigest()


def _amount(value):
    return format(value, '.2f')


def _money(value, positive=True):
    if not isinstance(value, str) or not re.fullmatch(r'(?:0|[1-9][0-9]{0,8})\.[0-9]{2}', value):
        raise Problem(400, 'Kanonischer EUR-Centbetrag erwartet')
    amount = Decimal(value)
    if positive and amount <= 0:
        raise Problem(400, 'Positiver EUR-Centbetrag erwartet')
    return amount


def _ledger_money(value, positive=True):
    """Legacy Finance supports larger amounts than a new E1a cash command."""
    if not isinstance(value, str) or not re.fullmatch(r'(?:0|[1-9][0-9]{0,26})\.[0-9]{2}', value):
        raise ValueError('Invalid stored EUR cents')
    result = Decimal(value)
    if positive and result <= 0:
        raise ValueError('Invalid stored positive EUR cents')
    return result


def _stored(method):
    @wraps(method)
    def checked(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except Problem as error:
            if error.status != 400:
                raise
            raise Problem(409, 'Gespeicherte Zahlungszuordnung besteht die Integritätsprüfung nicht') from None
        except (ValueError, TypeError, KeyError, InvalidOperation, OverflowError):
            raise Problem(409, 'Gespeicherte Zahlungszuordnung besteht die Integritätsprüfung nicht') from None
    return checked


def installed(office):
    """Read-only detection: an incomplete migration is never an empty ledger."""
    from business_schema import _tables
    tables = _tables(office)
    present = set(_TABLES) & tables
    journal = ('business_schema_migrations' in tables and office.db.execute(
        "SELECT 1 FROM business_schema_migrations WHERE module='business_accounting_allocations'").fetchone())
    if not present and not journal:
        return False
    if present != set(_TABLES) or not journal:
        raise Problem(409, 'Zusätzliche Zahlungszuordnung ist unvollständig installiert')
    return True


def _entries(office, payment_id):
    return office.db.execute('SELECT * FROM business_accounting_allocation_entries WHERE payment_id=? ORDER BY revision,id',
                             (payment_id,)).fetchall() if installed(office) else []


def require_effective_payment_access(office, actor, payment_id, permission='finance.read'):
    """Authorize every original/additional project before decoding any amount."""
    fresh = require(office, actor, permission)
    payment = office.db.execute('SELECT created_by FROM business_payments WHERE id=?', (payment_id,)).fetchone()
    if not payment:
        raise Problem(404, 'Zahlung nicht verfügbar')
    original = office.db.execute('SELECT document_id FROM business_payment_allocations WHERE payment_id=?', (payment_id,)).fetchall()
    if not original and fresh['role'] != 'owner' and fresh['id'] != payment['created_by']:
        raise Problem(403, 'Diese ursprünglich unzugeordnete Zahlungsquelle ist nicht freigegeben')
    additional = (office.db.execute('SELECT document_id FROM business_accounting_allocation_entries WHERE payment_id=?',
                                  (payment_id,)).fetchall() if installed(office) else [])
    for document_id in sorted({row['document_id'] for row in list(original) + list(additional)}):
        Documents(office)._row(fresh, document_id, permission)
    return fresh


@_stored
def effective_allocations(office, payment_id):
    amounts = {}
    rows = list(office.db.execute('SELECT document_id,amount FROM business_payment_allocations WHERE payment_id=?', (payment_id,)).fetchall())
    if installed(office):
        rows += [_entry_reference(value) for value in office.db.execute('SELECT * FROM business_accounting_allocation_entries WHERE payment_id=?', (payment_id,)).fetchall()]
    for row in rows:
        amounts[row['document_id']] = amounts.get(row['document_id'], Decimal(0)) + _ledger_money(row['amount'])
    return [dict(document_id=key, amount=_amount(amounts[key])) for key in sorted(amounts)]


@_stored
def effective_paid(office, document_id):
    rows = office.db.execute('SELECT a.amount,p.kind FROM business_payment_allocations a JOIN business_payments p ON p.id=a.payment_id '
                             'WHERE a.document_id=?', (document_id,)).fetchall()
    amount = Decimal(0)
    for row in rows:
        if row['kind'] not in ('receipt', 'refund'):
            raise ValueError('Invalid payment kind')
        amount += _ledger_money(row['amount']) * (1 if row['kind'] == 'receipt' else -1)
    if installed(office):
        for row in office.db.execute('SELECT * FROM business_accounting_allocation_entries WHERE document_id=?', (document_id,)).fetchall():
            amount += _money(_entry_reference(row)['amount'])
    return amount


def _state_hash(source_hash, entries):
    headers = [dict(id=value['id'], revision=value['revision'], sha256=_sha(canonical(value))) for value in entries]
    return _sha(canonical(dict(schema_version=1, source_hash=source_hash, entries=headers)))


@_stored
def _entry_reference(row):
    """Flat reference prevents recursive growth of successive invoice proofs."""
    value = {key: row[key] for key in ('id', 'payment_id', 'event_id', 'revision', 'document_id', 'amount', 'entry_sha256')}
    entry = json.loads(row['entry_json'])
    proof_hash = _sha(row['document_proof_json'])
    if (_sha(row['entry_json']) != row['entry_sha256'] or canonical(entry) != row['entry_json']
            or any(entry[key] != row[key] for key in ('id', 'payment_id', 'event_id', 'revision', 'amount', 'customer_id',
                                                     'source_hash', 'previous_state_hash', 'created_by', 'created_at'))
            or entry['document']['document_id'] != row['document_id'] or type(row['revision']) is not int or row['revision'] < 1
            or entry['document']['document_state_hash'] != proof_hash):
        raise ValueError('Invalid referenced allocation entry')
    _money(row['amount'])
    value['document_proof_sha256'] = proof_hash
    return value


@_stored
def _archive(office, row):
    if not row or row['status'] != 'final' or type(row['revision']) is not int or row['revision'] < 2:
        raise ValueError('Missing final document')
    archive = office.db.execute('SELECT * FROM business_document_archives WHERE document_id=?', (row['id'],)).fetchone()
    if not archive:
        raise ValueError('Missing archive')
    payload = json.loads(row['payload_json']); pdf = bytes(archive['pdf'])
    if (row['payload_json'] != archive['payload_json'] or row['payload_sha256'] != archive['payload_sha256']
            or _sha(row['payload_json']) != row['payload_sha256'] or not pdf.startswith(b'%PDF-')
            or len(pdf) > MAX_PDF or _sha(pdf) != archive['pdf_sha256']
            or (archive['xml'] is None) != (archive['xml_sha256'] is None)
            or archive['xml'] is not None and _sha(bytes(archive['xml'])) != archive['xml_sha256']
            or any(payload.get(key) != row[key] for key in ('id', 'number', 'project_id', 'kind'))
            or payload.get('document_revision') != row['revision'] - 1):
        raise ValueError('Invalid document archive')
    return dict(document=dict(row), pdf_sha256=archive['pdf_sha256'], xml_sha256=archive['xml_sha256'])


@_stored
def _normal(office, row):
    if row['kind'] != 'invoice' or row['status'] != 'final':
        return False
    value = json.loads(row['payload_json'])
    if value.get('currency') != 'EUR' or _ledger_money(value['totals']['gross'], False) <= 0 or value.get('previous_document_ids') or value.get('previous_documents'):
        return False
    return not office.db.execute("SELECT 1 FROM business_document_relations WHERE (source_id=? OR target_id=?) AND kind IN ('deducts','cancels')",
                                 (row['id'], row['id'])).fetchone()


@_stored
def _document_state(office, row):
    """Internal full evidence; public DTO exposes only invoice-local aggregates."""
    archive = _archive(office, row)
    old = [dict(value) for value in office.db.execute('SELECT * FROM business_payment_allocations WHERE document_id=? ORDER BY id', (row['id'],)).fetchall()]
    payments = [dict(office.db.execute('SELECT * FROM business_payments WHERE id=?', (key,)).fetchone()) for key in sorted({item['payment_id'] for item in old})]
    added = ([_entry_reference(value) for value in office.db.execute('SELECT * FROM business_accounting_allocation_entries WHERE document_id=? ORDER BY id', (row['id'],)).fetchall()]
             if installed(office) else [])
    relations = [dict(value) for value in office.db.execute("SELECT r.* FROM business_document_relations r JOIN business_documents d ON d.id=r.target_id "
        "WHERE r.source_id=? AND r.kind='cancels' AND d.status='final' ORDER BY r.target_id", (row['id'],)).fetchall()]
    credits = [_archive(office, office.db.execute('SELECT * FROM business_documents WHERE id=?', (value['target_id'],)).fetchone()) for value in relations]
    proof = dict(schema_version=1, archive=archive, allocations=old, payments=payments, additional=added, relations=relations, credits=credits)
    return _candidate_from_proof(proof), proof


@_stored
def _candidate_from_proof(proof):
    row = proof['archive']['document']; payload = json.loads(row['payload_json'])
    gross = _ledger_money(payload['totals']['gross']); paid = Decimal(0); credited = Decimal(0)
    payments = {value['id']: value for value in proof['payments']}
    for value in proof['allocations']:
        payment = payments[value['payment_id']]
        if payment['kind'] not in ('receipt', 'refund') or payment['currency'] != 'EUR':
            raise ValueError('Invalid invoice payment source')
        _ledger_money(payment['amount'])
        paid += _ledger_money(value['amount']) * (1 if payment['kind'] == 'receipt' else -1)
    for value in proof['additional']:
        paid += _money(value['amount'])
    for value in proof['credits']:
        credit = json.loads(value['document']['payload_json'])
        if value['document']['kind'] != 'credit_note' or credit.get('currency') != 'EUR':
            raise ValueError('Invalid credit source')
        credited += _ledger_money(credit['totals']['gross'], False)
    return dict(document_id=row['id'], number=row['number'], project_id=row['project_id'], customer_id=row['customer_id'],
        buyer_name=payload['buyer']['name'], gross=_amount(gross), paid=_amount(paid), credited=_amount(credited), open=_amount(gross-paid-credited),
        payload_sha256=row['payload_sha256'], pdf_sha256=proof['archive']['pdf_sha256'], document_state_hash=_sha(canonical(proof)))


@_stored
def _verify_document_proof(office, proof):
    """Frozen source members must survive unchanged; later additions are legal."""
    if set(proof) != {'schema_version', 'archive', 'allocations', 'payments', 'additional', 'relations', 'credits'} or proof['schema_version'] != 1:
        raise ValueError('Invalid historical invoice proof')
    for archived in [proof['archive']] + proof['credits']:
        row = office.db.execute('SELECT * FROM business_documents WHERE id=?', (archived['document']['id'],)).fetchone()
        if _archive(office, row) != archived:
            raise ValueError('Changed historical archive')
    for field, table in (('allocations', 'business_payment_allocations'), ('payments', 'business_payments'), ('additional', _TABLES[0])):
        seen = set()
        for value in proof[field]:
            row = office.db.execute('SELECT * FROM ' + table + ' WHERE id=?', (value['id'],)).fetchone()
            original = _entry_reference(row) if row and field == 'additional' else dict(row) if row else None
            if original != value or value['id'] in seen:
                raise ValueError('Changed historical invoice source')
            seen.add(value['id'])
    for relation in proof['relations']:
        row = office.db.execute('SELECT * FROM business_document_relations WHERE source_id=? AND target_id=? AND kind=?',
                                (relation['source_id'], relation['target_id'], relation['kind'])).fetchone()
        if not row or dict(row) != relation:
            raise ValueError('Changed historical credit source')
    return _candidate_from_proof(proof)


class PaymentAllocations(Domain):
    def _access(self, actor, payment_id, write=False):
        fresh = self.access(actor, 'accounting.read'); self.access(fresh, 'finance.read')
        if write:
            self.access(fresh, 'accounting.prepare'); self.access(fresh, 'finance.write')
        return require_effective_payment_access(self.office, fresh, payment_id, 'finance.write' if write else 'finance.read')

    def _gate(self):
        from business_accounting import Accounting
        Accounting(self.office)._write_gate()

    def _writes_allowed(self, actor, payment_id):
        try:
            self._access(actor, payment_id, True); self._gate()
            return True
        except Problem as error:
            if error.status not in (403, 404, 409, 423):
                raise
            return False

    @_stored
    def _load(self, actor, payment_id):
        from business_accounting import Accounting
        link = self.office.db.execute("SELECT * FROM business_accounting_source_links WHERE payment_id=? AND kind='payment'", (payment_id,)).fetchone()
        if not link:
            raise Problem(404, 'Bereits übernommene Zahlungsquelle erforderlich')
        accounting = Accounting(self.office)
        event = accounting._event(actor, link['event_id'])
        source = event['source']['snapshot']
        if (event['amount'] != source['amount'] or event['direction'] != source['direction'] or event['currency'] != 'EUR'
                or event['source']['id'] != payment_id or type(event['sequence']) is not int or event['sequence'] < 1):
            raise ValueError('Invalid payment cash source')
        source_hash = link['source_hash']; entries = []; allocated = sum((_money(value['amount']) for value in source['allocations']), Decimal(0))
        original = json.loads(link['proof_json'])['documents']
        customers = {value['customer_id'] for value in original}
        customer = next(iter(customers)) if len(customers) == 1 else None
        for revision, row in enumerate(_entries(self.office, payment_id), 1):
            value = json.loads(row['entry_json']); proof = json.loads(row['document_proof_json'])
            previous = _state_hash(source_hash, entries)
            expected_fields = {'id', 'payment_id', 'event_id', 'revision', 'customer_id', 'source_hash', 'previous_state_hash', 'document',
                               'amount', 'reason', 'unallocated_before', 'unallocated_after', 'open_before', 'open_after', 'preview_hash',
                               'created_by', 'created_at', 'scope', 'tax_result_available'}
            if (set(value) != expected_fields or value['scope'] != 'authorized_sources' or value['tax_result_available'] is not False
                    or type(row['revision']) is not int or row['revision'] != revision or _sha(row['entry_json']) != row['entry_sha256']
                    or canonical(value) != row['entry_json'] or canonical(proof) != row['document_proof_json']
                    or row['previous_state_hash'] != previous or row['source_hash'] != source_hash or row['event_id'] != event['id']
                    or any(value[key] != row[key] for key in ('id', 'payment_id', 'event_id', 'revision', 'customer_id', 'amount',
                                                            'source_hash', 'previous_state_hash', 'created_by', 'created_at'))
                    or value['document']['document_id'] != row['document_id']
                    or value['document'] != _verify_document_proof(self.office, proof)
                    or source['kind'] != 'receipt' or source['direction'] != 'in'):
                raise ValueError('Invalid assignment history')
            identifier(row['id']); identifier(row['customer_id'])
            if (row['customer_id'] != value['document']['customer_id'] or customers and customers != {row['customer_id']}
                    or value['unallocated_before'] != _amount(_money(source['amount']) - allocated)
                    or _money(value['unallocated_before'], False) - _money(row['amount']) != _money(value['unallocated_after'], False)
                    or _ledger_money(value['open_before']) - _money(row['amount']) != _ledger_money(value['open_after'], False)
                    or value['open_before'] != value['document']['open']):
                raise ValueError('Invalid historical assignment budget or customer')
            customers.add(row['customer_id']); customer = row['customer_id']; allocated += _money(row['amount'])
            preview = self._historical_preview(value)
            if value['preview_hash'] != _sha(canonical(preview)):
                raise ValueError('Invalid historical preview')
            request = self.office.db.execute('SELECT * FROM business_accounting_allocation_requests WHERE entry_id=?', (row['id'],)).fetchone()
            if not request:
                raise ValueError('Missing assignment receipt')
            body = json.loads(request['request_json']); self._inputs(body, True)
            if (request['user_id'] != row['created_by'] or request['request_id'] != body['request_id'] or request['payment_id'] != payment_id
                    or canonical(body) != request['request_json']
                    or request['request_hash'] != self._request_hash(payment_id, body)
                    or any(body[key] != preview[key] for key in ('source_hash', 'expected_revision', 'state_hash', 'customer_id', 'amount', 'reason'))
                    or body['document_id'] != row['document_id'] or body['document_state_hash'] != value['document']['document_state_hash']
                    or body['preview_hash'] != value['preview_hash']):
                raise ValueError('Invalid assignment receipt')
            entries.append(value)
        allocations = effective_allocations(self.office, payment_id)
        remaining = _money(source['amount']) - sum((_money(value['amount']) for value in allocations), Decimal(0))
        reason = None
        if source['kind'] != 'receipt' or source['direction'] != 'in':
            reason = 'unsupported_payment'
        elif any(value['kind'] != 'invoice' or not _normal(self.office, self.office.db.execute(
                'SELECT * FROM business_documents WHERE id=?', (value['document_id'],)).fetchone()) for value in original):
            reason = 'unsupported_source_documents'
        elif len(customers) > 1:
            reason = 'mixed_customers'
        elif None in customers or '' in customers:
            reason = 'missing_customer'
        elif remaining < 0:
            reason = 'overallocated'
        elif remaining == 0:
            reason = 'fully_allocated'
        state = dict(payment_id=payment_id, event_id=event['id'], source_hash=source_hash, revision=len(entries),
            state_hash=_state_hash(source_hash, entries), amount=source['amount'], currency='EUR', customer_id=customer,
            allocated_amount=_amount(_money(source['amount'])-remaining), unallocated_amount=_amount(remaining), allocations=allocations,
            eligible=reason is None, blocked_reason=reason, writes_allowed=self._writes_allowed(actor, payment_id) if actor is not None else False,
            scope='authorized_sources', tax_result_available=False)
        return state, entries

    @staticmethod
    def _historical_preview(entry):
        return dict(payment_id=entry['payment_id'], event_id=entry['event_id'], customer_id=entry['customer_id'],
            source_hash=entry['source_hash'], expected_revision=entry['revision']-1, state_hash=entry['previous_state_hash'],
            document=entry['document'], amount=entry['amount'], reason=entry['reason'], unallocated_before=entry['unallocated_before'],
            unallocated_after=entry['unallocated_after'], open_before=entry['open_before'], open_after=entry['open_after'],
            scope='authorized_sources', tax_result_available=False)

    def state(self, actor, payment_id):
        identifier(payment_id)
        with transaction(self.office):
            fresh = self._access(actor, payment_id)
            return self._load(fresh, payment_id)[0]

    def history(self, actor, payment_id, limit=50, offset=0):
        from business_accounting import _page, _paged
        identifier(payment_id); _page(limit, offset)
        with transaction(self.office):
            fresh = self._access(actor, payment_id)
            return _paged(list(reversed(self._load(fresh, payment_id)[1])), limit, offset)

    def candidates(self, actor, payment_id, limit=50, offset=0):
        from business_accounting import _page, _paged
        identifier(payment_id); _page(limit, offset)
        with transaction(self.office):
            fresh = self._access(actor, payment_id, True)
            state, _ = self._load(fresh, payment_id); items = []
            if not state['eligible']:
                return _paged(items, limit, offset)
            for row in self.office.db.execute("SELECT * FROM business_documents WHERE status='final' AND kind='invoice' ORDER BY number,id").fetchall():
                try:
                    Documents(self.office)._row(fresh, row['id'], 'finance.write')
                except Problem as error:
                    if error.status in (403, 404):
                        continue
                    raise
                if not row['customer_id'] or state['customer_id'] is not None and row['customer_id'] != state['customer_id']:
                    continue
                candidate, _ = _document_state(self.office, row)
                if _normal(self.office, row) and Decimal(candidate['open']) > 0:
                    items.append(candidate)
            return _paged(items, limit, offset)

    @staticmethod
    def _inputs(data, assign=False):
        fields = _PREVIEW_FIELDS | ({'request_id', 'preview_hash', 'confirmation'} if assign else set())
        if not isinstance(data, dict) or set(data) != fields:
            raise Problem(400, 'Vollständige bekannte Zuordnungsfelder erwartet')
        for key in ('source_hash', 'state_hash', 'document_state_hash') + (('preview_hash',) if assign else ()):
            if not isinstance(data[key], str) or not re.fullmatch(_HASH, data[key]):
                raise Problem(400, 'SHA-256-Prüfsumme erwartet')
        for key in ('customer_id', 'document_id') + (('request_id',) if assign else ()):
            identifier(data[key], key)
        if type(data['expected_revision']) is not int or data['expected_revision'] < 0:
            raise Problem(400, 'Nichtnegative Zuordnungsrevision erwartet')
        if assign and data['confirmation'] is not True:
            raise Problem(400, 'Zuordnung ausdrücklich bestätigen')
        reason = data['reason']
        if (not isinstance(reason, str) or not 1 <= len(reason) <= 1000 or not reason.strip()
                or any(ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF for char in reason)):
            raise Problem(400, 'Einzeilige Begründung mit 1 bis 1000 Zeichen erwartet')
        _money(data['amount'])

    def _prepare(self, fresh, payment_id, data, state, row):
        if not state['eligible']:
            raise Problem(409, 'Zahlungszuordnung gesperrt: ' + state['blocked_reason'])
        if any(data[key] != state[target] for key, target in (('source_hash', 'source_hash'), ('expected_revision', 'revision'), ('state_hash', 'state_hash'))):
            raise Problem(409, 'Quellenstand geändert; neu laden')
        candidate, proof = _document_state(self.office, row)
        if (not _normal(self.office, row) or not row['customer_id'] or data['customer_id'] != row['customer_id']
                or state['customer_id'] is not None and state['customer_id'] != row['customer_id']
                or data['document_state_hash'] != candidate['document_state_hash']):
            raise Problem(409, 'Kundenbindung oder Rechnungsstand passt nicht zur aktuellen Vorschau')
        amount = _money(data['amount']); remaining = _money(state['unallocated_amount'], False); opened = Decimal(candidate['open'])
        if amount > remaining or amount > opened:
            raise Problem(409, 'Zuordnung überschreitet Zahlungsrest oder offenen Rechnungsbetrag')
        preview = dict(payment_id=payment_id, event_id=state['event_id'], customer_id=data['customer_id'], source_hash=state['source_hash'],
            expected_revision=state['revision'], state_hash=state['state_hash'], document=candidate, amount=data['amount'], reason=data['reason'],
            unallocated_before=_amount(remaining), unallocated_after=_amount(remaining-amount), open_before=candidate['open'], open_after=_amount(opened-amount),
            scope='authorized_sources', tax_result_available=False)
        return dict(preview, preview_hash=_sha(canonical(preview))), proof

    def preview(self, actor, payment_id, data):
        identifier(payment_id); self._inputs(data)
        with transaction(self.office):
            fresh = self._access(actor, payment_id, True)
            row = Documents(self.office)._row(fresh, data['document_id'], 'finance.write')
            self._gate(); state, _ = self._load(fresh, payment_id)
            return self._prepare(fresh, payment_id, data, state, row)[0]

    @staticmethod
    def _request_hash(payment_id, data):
        return _sha(canonical(['allocation.assign', payment_id, data]))

    def assign(self, actor, payment_id, data):
        identifier(payment_id); self._inputs(data, True)
        with transaction(self.office):
            fresh = self._access(actor, payment_id, True)
            row = Documents(self.office)._row(fresh, data['document_id'], 'finance.write')
            self._gate(); state, entries = self._load(fresh, payment_id)
            digest = self._request_hash(payment_id, data)
            request = self.office.db.execute('SELECT * FROM business_accounting_allocation_requests WHERE user_id=? AND request_id=?',
                                             (fresh['id'], data['request_id'])).fetchone()
            if request:
                if request['request_hash'] != digest or request['payment_id'] != payment_id:
                    raise Problem(409, 'Vorgangs-ID wurde mit anderem Inhalt verwendet')
                return next(value for value in entries if value['id'] == request['entry_id'])
            preview, proof = self._prepare(fresh, payment_id, data, state, row)
            if preview['preview_hash'] != data['preview_hash']:
                raise Problem(409, 'Passende aktuelle Vorschau erforderlich')
            entry = {key: value for key, value in preview.items() if key not in ('expected_revision', 'state_hash')}
            entry.update(id=uuid.uuid4().hex, revision=state['revision']+1, previous_state_hash=state['state_hash'], created_by=fresh['id'], created_at=self.now())
            encoded = canonical(entry)
            self.office.db.execute('INSERT INTO business_accounting_allocation_entries(id,payment_id,event_id,revision,customer_id,document_id,amount,'
                'source_hash,previous_state_hash,entry_json,entry_sha256,document_proof_json,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (entry['id'], payment_id, entry['event_id'], entry['revision'], entry['customer_id'], row['id'], entry['amount'], entry['source_hash'],
                 entry['previous_state_hash'], encoded, _sha(encoded), canonical(proof), fresh['id'], entry['created_at']))
            self.office.db.execute('INSERT INTO business_accounting_allocation_requests(user_id,request_id,payment_id,request_json,request_hash,entry_id) VALUES(?,?,?,?,?,?)',
                                   (fresh['id'], data['request_id'], payment_id, canonical(data), digest, entry['id']))
            self.office.audit(fresh, 'business.accounting.payment_allocated', entry['id'])
            return entry


def validate_integrity(office):
    try:
        if not installed(office):
            return True
        api = PaymentAllocations(office)
        count = 0
        for row in office.db.execute('SELECT DISTINCT payment_id FROM business_accounting_allocation_entries ORDER BY payment_id').fetchall():
            count += len(api._load(None, row['payment_id'])[1])
        if count != office.db.execute('SELECT COUNT(*) FROM business_accounting_allocation_requests').fetchone()[0]:
            raise ValueError('Orphan allocation receipt')
        if isinstance(office.db, sqlite3.Connection):
            normalize = lambda value: re.sub(r'\s+', ' ', value.replace('IF NOT EXISTS ', '')).strip().lower()
            for sql in guard_statements('sqlite'):
                name = re.search(r'CREATE TRIGGER IF NOT EXISTS (\w+)', sql)[1]
                row = office.db.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?", (name,)).fetchone()
                if not row or normalize(row[0]) != normalize(sql):
                    raise ValueError('Missing or changed allocation guard')
        else:
            from business_documents import _validate_pg_guards
            _validate_pg_guards(office.db, guard_statements('postgresql'))
    except (Problem, TypeError, KeyError, InvalidOperation) as error:
        raise ValueError('Invalid accounting allocation history') from error
    return True


def restore_horizon(office):
    with office.lock:
        if not installed(office):
            return None
        validate_integrity(office)
        tables = {table: sorted((dict(row) for row in office.db.execute('SELECT * FROM ' + table).fetchall()), key=canonical) for table in _TABLES}
        return dict(schema_version=1, table_counts={table: len(rows) for table, rows in tables.items()},
                    sha256=_sha(canonical(dict(schema_version=1, tables=tables))))


def methods(path):
    match = re.fullmatch(r'/accounting/allocations/payments/' + _ID + r'(/(?:candidates|history|preview|assign))?', path)
    if match:
        return 'POST' if match[1] in ('/preview', '/assign') else 'GET'
    return None


def dispatch(office, actor, path, method, data):
    expected = methods(path)
    if expected is None:
        return None
    if method != expected:
        raise Problem(405, 'Methode nicht unterstützt')
    if not isinstance(data, dict) or not isinstance(data.get('_query', {}), dict):
        raise Problem(400, 'Eindeutige Zuordnungsparameter erwartet')
    query = data.get('_query', {}); body = {key: value for key, value in data.items() if key != '_query'}
    parts = path.split('/'); payment_id = parts[4]; action = parts[5] if len(parts) > 5 else 'state'; api = PaymentAllocations(office)
    if method == 'GET':
        if body:
            raise Problem(400, 'GET erwartet keinen Anfragekörper')
        if action == 'state':
            if query:
                raise Problem(400, 'Keine zusätzlichen Filter erlaubt')
            result = api.state(actor, payment_id)
        else:
            if set(query) - {'limit', 'offset'} or any(not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,6}', value) for value in query.values()):
                raise Problem(400, 'Nur ganzzahlige Limit-/Offsetfilter erwartet')
            result = getattr(api, action)(actor, payment_id, int(query.get('limit', '50')), int(query.get('offset', '0')))
        return result, 200, 'application/json'
    if '_query' in data:
        raise Problem(400, 'Keine zusätzlichen Filter erlaubt')
    return getattr(api, action)(actor, payment_id, body), (201 if action == 'assign' else 200), 'application/json'
