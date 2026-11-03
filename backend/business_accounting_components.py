"""Documentary cent components of immutable cash portions, without tax posting.

One whole source portion is consumed once. Global group pools are independent
of payment IDs and reader visibility. All historical references are flat.
"""
from functools import wraps
import hashlib
import json
import re
import sqlite3
import uuid

from core import Problem, canonical
from business_operations import Domain, identifier, transaction

FEATURES = ('accounting_document_components',)
_TABLES = tuple('business_accounting_component_' + name for name in ('entries', 'lines', 'requests'))
_ID = r'[a-f0-9]{32}'
_HASH = r'[a-f0-9]{64}'
_INPUT = {'source_hash', 'expected_revision', 'state_hash', 'portion_id', 'portion_state_hash', 'groups', 'reason'}
_LINE = ('group_id', 'amount', 'net', 'tax', 'gross_before', 'gross_after', 'net_before', 'net_after', 'tax_before', 'tax_after', 'remaining_gross')
_FLAGS = dict(scope='authorized_sources', tax_status='unconfigured', tax_result_available=False)


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BLOB', 'BYTEA'):
        raise ValueError('Unsupported binary type')
    return [
        '''CREATE TABLE IF NOT EXISTS business_accounting_component_entries(
        id TEXT PRIMARY KEY, sequence INTEGER NOT NULL UNIQUE CHECK(sequence>0),
        event_id TEXT NOT NULL REFERENCES business_accounting_cash_events(id), revision INTEGER NOT NULL CHECK(revision>0),
        portion_id TEXT NOT NULL UNIQUE CHECK(length(portion_id)=64), source_hash TEXT NOT NULL CHECK(length(source_hash)=64),
        previous_state_hash TEXT NOT NULL CHECK(length(previous_state_hash)=64),
        entry_json TEXT NOT NULL, entry_sha256 TEXT NOT NULL CHECK(length(entry_sha256)=64), proof_json TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL, UNIQUE(event_id,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_accounting_component_lines(
        entry_id TEXT NOT NULL REFERENCES business_accounting_component_entries(id), group_id TEXT NOT NULL CHECK(length(group_id)=64),
        amount TEXT NOT NULL, net TEXT NOT NULL, tax TEXT NOT NULL,
        gross_before TEXT NOT NULL, gross_after TEXT NOT NULL, net_before TEXT NOT NULL, net_after TEXT NOT NULL,
        tax_before TEXT NOT NULL, tax_after TEXT NOT NULL, remaining_gross TEXT NOT NULL,
        basis_json TEXT NOT NULL, basis_sha256 TEXT NOT NULL CHECK(length(basis_sha256)=64), PRIMARY KEY(entry_id,group_id))''',
        '''CREATE TABLE IF NOT EXISTS business_accounting_component_requests(
        user_id TEXT NOT NULL REFERENCES users(id), request_id TEXT NOT NULL,
        event_id TEXT NOT NULL REFERENCES business_accounting_cash_events(id), request_json TEXT NOT NULL,
        request_hash TEXT NOT NULL CHECK(length(request_hash)=64),
        entry_id TEXT NOT NULL UNIQUE REFERENCES business_accounting_component_entries(id), PRIMARY KEY(user_id,request_id))''',
        'CREATE INDEX IF NOT EXISTS business_accounting_component_groups ON business_accounting_component_lines(group_id,entry_id)',
    ]


def protected_tables():
    return _TABLES


def runtime_privileges():
    return {table: ('SELECT', 'INSERT') for table in _TABLES}


def guard_statements(dialect):
    if dialect == 'sqlite':
        guards = [f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} ON {table} "
                  "BEGIN SELECT RAISE(ABORT,'immutable documentary components'); END"
                  for table in _TABLES for action in ('UPDATE', 'DELETE')]
        conflicts = ('id=NEW.id OR sequence=NEW.sequence OR portion_id=NEW.portion_id OR (event_id=NEW.event_id AND revision=NEW.revision)',
                     'entry_id=NEW.entry_id AND group_id=NEW.group_id', '(user_id=NEW.user_id AND request_id=NEW.request_id) OR entry_id=NEW.entry_id')
        for table, conflict in zip(_TABLES, conflicts):
            guards.append(f'CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} '
                          f'WHEN EXISTS(SELECT 1 FROM {table} WHERE {conflict}) '
                          "BEGIN SELECT RAISE(ABORT,'immutable documentary components'); END")
        return guards
    if dialect != 'postgresql':
        raise ValueError('Unsupported guard dialect')
    guards = ["""CREATE OR REPLACE FUNCTION business_accounting_component_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'immutable documentary components'; END; $$"""]
    for table in _TABLES:
        for action in ('UPDATE', 'DELETE'):
            name = table + '_' + action.lower() + '_guard'
            guards.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) "
                          f"THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION "
                          "business_accounting_component_immutable_guard(); END IF; END $$")
    return guards


def _sha(value):
    return hashlib.sha256(value.encode('utf-8') if isinstance(value, str) else value).hexdigest()


def _cents(value, *, positive=False, input_value=False):
    digits = 8 if input_value else 26
    if not isinstance(value, str) or not re.fullmatch(r'(?:0|[1-9][0-9]{0,' + str(digits) + r'})\.[0-9]{2}', value):
        raise Problem(400, 'Kanonischer begrenzter EUR-Centbetrag erwartet')
    result = int(value.replace('.', ''))
    if positive and result <= 0:
        raise Problem(400, 'Positiver EUR-Centbetrag erwartet')
    return result


def _money(cents):
    if type(cents) is not int or cents < 0:
        raise ValueError('Invalid integer cents')
    return str(cents // 100) + '.' + str(cents % 100).zfill(2)


def _stored(method):
    @wraps(method)
    def checked(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except Problem as error:
            if error.status != 400:
                raise
            raise Problem(409, 'Gespeicherter Beleganteil besteht die Integritätsprüfung nicht') from None
        except (ValueError, KeyError, TypeError, OverflowError, ArithmeticError):
            raise Problem(409, 'Gespeicherter Beleganteil besteht die Integritätsprüfung nicht') from None
    return checked


def installed(office):
    from business_schema import _tables
    tables = _tables(office); present = set(_TABLES) & tables
    marker = ('business_schema_migrations' in tables and office.db.execute(
        "SELECT 1 FROM business_schema_migrations WHERE module='business_accounting_components'").fetchone())
    if not present and not marker:
        return False
    if present != set(_TABLES) or not marker:
        raise Problem(409, 'Dokumentarische Aufteilung ist unvollständig installiert')
    from business_accounting import protected_tables as prejournal_tables
    from business_accounting_allocations import installed as allocations_installed
    if not set(prejournal_tables()) <= tables or not office.db.execute(
            "SELECT 1 FROM business_schema_migrations WHERE module='business_accounting'").fetchone() or not allocations_installed(office):
        raise Problem(409, 'Vorjournal und zusätzliche Zahlungszuordnung müssen vollständig installiert sein')
    return True


def _portion_id(kind, source_id):
    return _sha(canonical(dict(kind=kind, id=source_id)))


def _header(row):
    return {key: row[key] for key in ('id', 'sequence', 'revision', 'entry_sha256')}


def _state_hash(event_id, source_hash, portions, headers):
    return _sha(canonical(dict(schema_version=1, event_id=event_id, source_hash=source_hash, portions=portions, entries=headers)))


def _tax(cumulative, tax, gross):
    return (2*cumulative*tax + gross) // (2*gross)


def _line(basis, before, amount):
    gross, tax = _cents(basis['gross'], positive=True), _cents(basis['tax'])
    after = before + amount
    if amount <= 0 or after > gross:
        raise Problem(409, 'Gruppenbetrag überschreitet die verbleibende Belegkapazität')
    old_tax, new_tax = _tax(before, tax, gross), _tax(after, tax, gross)
    return dict(group_id=basis['group_id'], amount=_money(amount), net=_money(amount-new_tax+old_tax), tax=_money(new_tax-old_tax),
        gross_before=_money(before), gross_after=_money(after), net_before=_money(before-old_tax), net_after=_money(after-new_tax),
        tax_before=_money(old_tax), tax_after=_money(new_tax), remaining_gross=_money(gross-after))


class DocumentComponents(Domain):
    def _access(self, actor, event_id, write=False):
        from business_accounting_allocations import require_effective_payment_access
        from business_finance import Finance
        fresh = self.access(actor, 'accounting.read'); self.access(fresh, 'finance.read')
        if write:
            self.access(fresh, 'accounting.prepare'); self.access(fresh, 'finance.write')
        if not installed(self.office):
            raise Problem(409, 'Dokumentarische Aufteilung ist nicht installiert')
        link = self.office.db.execute('SELECT kind,source_id FROM business_accounting_source_links WHERE event_id=?', (event_id,)).fetchone()
        if not link:
            raise Problem(404, 'Geldfluss nicht verfügbar')
        permission = 'finance.write' if write else 'finance.read'
        if link['kind'] == 'payment':
            require_effective_payment_access(self.office, fresh, link['source_id'], permission)
        else:
            Finance(self.office)._incoming(fresh, link['source_id'], permission)
        return fresh

    def _gate(self):
        from business_accounting import Accounting
        Accounting(self.office)._write_gate()

    def _writes_allowed(self, actor, event_id):
        try:
            self._access(actor, event_id, True); self._gate()
            return True
        except Problem as error:
            if error.status not in (403, 404, 409, 423):
                raise
            return False

    @_stored
    def _source(self, actor, event_id):
        from business_accounting import Accounting
        from business_accounting_allocations import PaymentAllocations, _entry_reference
        event = Accounting(self.office)._event(actor, event_id)
        source = event['source']; raw = []; reason = None
        if source['kind'] == 'payment':
            source_state, unused = PaymentAllocations(self.office)._load(actor, source['id'])
            payment = source['snapshot']; kind = 'customer_receipt' if payment['kind'] == 'receipt' else 'customer_refund'
            if kind == 'customer_refund':
                reason = 'refund_origin_unresolved'
            else:
                for row in self.office.db.execute('SELECT * FROM business_payment_allocations WHERE payment_id=? ORDER BY id', (source['id'],)).fetchall():
                    raw.append(dict(kind='original_allocation', id=row['id'], document_id=row['document_id'], amount=row['amount'], reference=dict(row)))
                for row in self.office.db.execute('SELECT * FROM business_accounting_allocation_entries WHERE payment_id=? ORDER BY revision,id', (source['id'],)).fetchall():
                    raw.append(dict(kind='additional_allocation', id=row['id'], document_id=row['document_id'], amount=row['amount'], reference=_entry_reference(row)))
                customers = {self.office.db.execute('SELECT customer_id FROM business_documents WHERE id=?', (value['document_id'],)).fetchone()[0] for value in raw}
                if raw and (len(customers) != 1 or not next(iter(customers))):
                    reason = 'source_customer_unresolved'
            unallocated = source_state['unallocated_amount']
            if (event['direction'] != payment['direction'] or event['amount'] != payment['amount'] or event['currency'] != payment['currency']):
                raise ValueError('Invalid cash/payment binding')
        else:
            kind = 'supplier_payout'; unallocated = '0.00'
            snapshot = source['snapshot']
            if event['direction'] != 'out' or _cents(event['amount'], positive=True) > _cents(snapshot['gross'], positive=True):
                raise ValueError('Invalid supplier payout')
            raw.append(dict(kind='supplier_payout', id=event_id, document_id=None, amount=event['amount'], reference=dict(
                receipt_id=snapshot['receipt_id'], original_sha256=snapshot['original_sha256'], review_revision=snapshot['review_revision'],
                review_sha256=snapshot['review_sha256'])))
        _cents(event['amount'], positive=True, input_value=True)
        for value in raw:
            value['portion_id'] = _portion_id(value['kind'], value['id'])
            _cents(value['amount'], positive=True, input_value=True)
        raw.sort(key=lambda value: value['portion_id'])
        return dict(event=event, kind=kind, reason=reason, portions=raw, unallocated=unallocated)

    @_stored
    def _basis(self, context, raw):
        from business_accounting import Accounting
        from business_accounting_allocations import _archive
        from business_documents import calculate_positions
        if raw['kind'] == 'supplier_payout':
            snapshot = context['event']['source']['snapshot']
            source, proof = Accounting(self.office)._receipt_source(None, snapshot['receipt_id'], snapshot['review_revision'])
            if not source or source['source_hash'] != context['event']['source']['source_hash']:
                raise ValueError('Changed payout source')
            binding = {key: snapshot[key] for key in ('receipt_id', 'original_sha256', 'review_revision', 'review_sha256')}
            net, tax = _cents(source['net']), _cents(source['tax']); gross = _cents(source['gross'], positive=True)
            if net + tax != gross:
                raise ValueError('Invalid reviewed totals')
            group = dict(rate=None, category=None, reason=None, net=source['net'], tax=source['tax'], gross=source['gross'])
            group['group_id'] = _sha(canonical(dict(kind='receipt_review', binding=binding, group=group)))
            metadata = dict(document_id=None, receipt_id=source['receipt_id'], project_id=source['project_id'], number=source['invoice_number'],
                party_name=source['vendor'], payload_sha256=None, pdf_sha256=None, original_sha256=source['original_sha256'],
                review_revision=source['review_revision'], review_sha256=source['review_sha256'])
            return metadata, [group], dict(kind='receipt_review', proof=proof)
        row = self.office.db.execute('SELECT * FROM business_documents WHERE id=?', (raw['document_id'],)).fetchone()
        archive = _archive(self.office, row); value = json.loads(row['payload_json'])
        metadata = dict(document_id=row['id'], receipt_id=None, project_id=row['project_id'], number=row['number'], party_name=value['buyer']['name'],
            payload_sha256=row['payload_sha256'], pdf_sha256=archive['pdf_sha256'], original_sha256=None, review_revision=None, review_sha256=None)
        if row['kind'] != 'invoice':
            return metadata, [], dict(kind='document', archive=archive)
        # Reuse the repository's exact archived-position validator. No current
        # article, tax profile or account setting participates in this proof.
        calculated = calculate_positions(value['positions'])
        if canonical(calculated['positions']) != canonical(value['positions']) or canonical(calculated['totals']) != canonical(value['totals']):
            raise ValueError('Invalid archived monetary groups')
        if value.get('currency') != 'EUR':
            raise ValueError('Invalid invoice currency')
        binding = dict(document_id=row['id'], payload_sha256=row['payload_sha256'], pdf_sha256=archive['pdf_sha256'], xml_sha256=archive['xml_sha256'])
        groups = []; identities = set(); total_net = total_tax = 0
        for part in value['totals']['tax_breakdown']:
            if set(part) != {'rate', 'category', 'reason', 'net', 'tax'}:
                raise ValueError('Invalid archived tax group')
            net, tax = _cents(part['net']), _cents(part['tax'])
            identity = (part['rate'], part['category'], part['reason'])
            if identity in identities:
                raise ValueError('Duplicate archived group')
            identities.add(identity); total_net += net; total_tax += tax
            group = dict(part, gross=_money(net+tax))
            group['group_id'] = _sha(canonical(dict(kind='invoice', binding=binding, group=group)))
            groups.append(group)
        if (not 1 <= len(groups) <= 500 or total_net != _cents(value['totals']['net']) or total_tax != _cents(value['totals']['tax'])
                or total_net+total_tax != _cents(value['totals']['gross'], positive=True)):
            raise ValueError('Invalid archived group sums')
        return metadata, sorted(groups, key=lambda item: item['group_id']), dict(kind='document', archive=archive)

    def _eligibility(self, context, raw):
        if context['reason']:
            return context['reason'], dict(source_reason=context['reason'])
        if raw['kind'] == 'supplier_payout':
            reference = raw['reference']
            latest = self.office.db.execute('SELECT revision,payload_sha256 FROM business_receipt_reviews WHERE receipt_id=? ORDER BY revision DESC LIMIT 1',
                                             (reference['receipt_id'],)).fetchone()
            evidence = dict(latest_review=dict(latest) if latest else None)
            reason = None if latest and (latest['revision'], latest['payload_sha256']) == (reference['review_revision'], reference['review_sha256']) else 'review_changed'
            return reason, evidence
        from business_accounting_allocations import _normal
        row = self.office.db.execute('SELECT * FROM business_documents WHERE id=?', (raw['document_id'],)).fetchone()
        relations = [dict(value) for value in self.office.db.execute("SELECT * FROM business_document_relations WHERE (source_id=? OR target_id=?) "
            "AND kind IN ('deducts','cancels') ORDER BY source_id,target_id,kind", (row['id'], row['id'])).fetchall()]
        return (None if _normal(self.office, row) else 'unsupported_document'), dict(relations=relations)

    @_stored
    def _basic(self, row):
        value = json.loads(row['entry_json']); proof = json.loads(row['proof_json'])
        expected = {'id', 'sequence', 'revision', 'previous_state_hash', 'created_by', 'created_at', 'event_id', 'source_hash',
                    'portion', 'amount', 'net', 'tax', 'lines', 'reason', 'preview_hash'} | set(_FLAGS)
        if (set(value) != expected or any(value[key] != expected_value for key, expected_value in _FLAGS.items())
                or value['tax_result_available'] is not False or type(value['sequence']) is not int or type(value['revision']) is not int
                or canonical(value) != row['entry_json'] or canonical(proof) != row['proof_json'] or _sha(row['entry_json']) != row['entry_sha256']
                or any(value[key] != row[key] for key in ('id', 'sequence', 'revision', 'event_id', 'source_hash', 'previous_state_hash', 'created_by', 'created_at'))
                or value['portion']['portion_id'] != row['portion_id'] or type(row['sequence']) is not int or row['sequence'] < 1
                or type(row['revision']) is not int or row['revision'] < 1):
            raise ValueError('Invalid component entry')
        identifier(row['id']); identifier(row['event_id']); identifier(row['created_by'])
        if not isinstance(value['lines'], list) or not 1 <= len(value['lines']) <= 500 or [line['group_id'] for line in value['lines']] != sorted({line['group_id'] for line in value['lines']}):
            raise ValueError('Invalid component lines')
        if (sum(_cents(line['amount'], positive=True) for line in value['lines']) != _cents(value['amount'], positive=True, input_value=True)
                or sum(_cents(line['net']) for line in value['lines']) != _cents(value['net'])
                or sum(_cents(line['tax']) for line in value['lines']) != _cents(value['tax'])
                or _cents(value['net'])+_cents(value['tax']) != _cents(value['amount'])):
            raise ValueError('Invalid component totals')
        stored_lines = self.office.db.execute('SELECT * FROM business_accounting_component_lines WHERE entry_id=? ORDER BY group_id', (row['id'],)).fetchall()
        if len(stored_lines) != len(value['lines']):
            raise ValueError('Missing component line')
        for line, stored_line in zip(value['lines'], stored_lines):
            if (set(line) != set(_LINE) or line != {key: stored_line[key] for key in _LINE}
                    or _sha(stored_line['basis_json']) != stored_line['basis_sha256']):
                raise ValueError('Changed component line')
        request = self.office.db.execute('SELECT * FROM business_accounting_component_requests WHERE entry_id=?', (row['id'],)).fetchone()
        if not request:
            raise ValueError('Missing component receipt')
        body = json.loads(request['request_json']); self._inputs(body, True)
        if (request['user_id'] != row['created_by'] or request['event_id'] != row['event_id'] or body['request_id'] != request['request_id']
                or canonical(body) != request['request_json'] or request['request_hash'] != self._request_hash(row['event_id'], body)
                or body['expected_revision'] != row['revision']-1 or body['state_hash'] != row['previous_state_hash']
                or any(body[key] != value[key] for key in ('source_hash', 'preview_hash', 'reason'))
                or body['portion_id'] != row['portion_id'] or body['portion_state_hash'] != value['portion']['portion_state_hash']
                or sorted(body['groups'], key=lambda item: item['group_id']) != [{key: line[key] for key in ('group_id', 'amount')} for line in value['lines']]):
            raise ValueError('Changed component receipt')
        preview = self._preview_from_entry(value)
        if _sha(canonical(preview)) != value['preview_hash']:
            raise ValueError('Changed component preview')
        return value, proof

    @staticmethod
    def _preview_from_entry(value):
        preview = {key: item for key, item in value.items() if key not in ('id', 'sequence', 'revision', 'previous_state_hash', 'created_by', 'created_at', 'preview_hash')}
        return dict(preview, expected_revision=value['revision']-1, state_hash=value['previous_state_hash'])

    @_stored
    def _proof_source(self, row, proof):
        if set(proof) != {'schema_version', 'source', 'portions_before', 'basis', 'archive', 'eligibility', 'pools_before'} or proof['schema_version'] != 1:
            raise ValueError('Invalid component proof schema')
        context = self._source(None, row['event_id'])
        raw = next((value for value in context['portions'] if value['portion_id'] == row['portion_id']), None)
        if not raw:
            raise ValueError('Component source portion is missing')
        source = dict(event_sha256=_sha(canonical(context['event'])), portion=raw)
        if source != proof['source'] or context['event']['source']['source_hash'] != row['source_hash']:
            raise ValueError('Changed component source')
        available = {value['portion_id']: value for value in context['portions']}
        previous = proof['portions_before']
        if (not isinstance(previous, list) or [value['portion_id'] for value in previous] != sorted({value['portion_id'] for value in previous})
                or any(available.get(value['portion_id']) != value for value in previous) or raw not in previous):
            raise ValueError('Changed historical source membership')
        fixed = [value for value in context['portions'] if value['kind'] != 'additional_allocation']
        added_revisions = sorted(value['reference']['revision'] for value in previous if value['kind'] == 'additional_allocation')
        if any(value not in previous for value in fixed) or added_revisions != list(range(1, len(added_revisions)+1)):
            raise ValueError('Incomplete historical source membership')
        metadata, bases, archive = self._basis(context, raw)
        if bases != proof['basis'] or archive != proof['archive']:
            raise ValueError('Changed component group basis')
        expected_eligibility = (dict(latest_review=dict(revision=raw['reference']['review_revision'], payload_sha256=raw['reference']['review_sha256']))
                                if raw['kind'] == 'supplier_payout' else dict(relations=[]))
        if context['reason'] or proof['eligibility'] != expected_eligibility:
            raise ValueError('Invalid historical source eligibility')
        value = json.loads(row['entry_json']); portion = value['portion']
        fixed = dict(portion_id=raw['portion_id'], kind=raw['kind'], event_id=row['event_id'], amount=raw['amount'], currency='EUR', **metadata)
        binding = {key: item for key, item in proof.items() if key != 'portions_before'}
        if (value['amount'] != raw['amount'] or any(portion[key] != item for key, item in fixed.items())
                or portion['eligible'] is not True or portion['blocked_reason'] is not None
                or portion['portion_state_hash'] != _sha(canonical(binding))):
            raise ValueError('Component entry differs from its complete immutable source portion')
        return context, raw, metadata, bases

    @_stored
    def _pool(self, basis, before_sequence=None):
        sql = ('SELECT l.*,e.sequence FROM business_accounting_component_lines l JOIN business_accounting_component_entries e ON e.id=l.entry_id '
               'WHERE l.group_id=?')
        parameters = (basis['group_id'],)
        if before_sequence is not None:
            sql += ' AND e.sequence<?'; parameters += (before_sequence,)
        rows = self.office.db.execute(sql + ' ORDER BY e.sequence,e.id', parameters).fetchall()
        cumulative = 0; references = []
        for line in rows:
            row = self.office.db.execute('SELECT * FROM business_accounting_component_entries WHERE id=?', (line['entry_id'],)).fetchone()
            unused, proof = self._basic(row)
            unused_context, unused_raw, unused_metadata, bases = self._proof_source(row, proof)
            if basis not in bases or line['basis_json'] != canonical(basis) or line['basis_sha256'] != _sha(canonical(basis)):
                raise ValueError('Changed shared group basis')
            expected = _line(basis, cumulative, _cents(line['amount'], positive=True))
            if {key: line[key] for key in _LINE} != expected:
                raise ValueError('Invalid cumulative component allocation')
            cumulative += _cents(line['amount'])
            references.append(dict(entry_id=row['id'], group_id=basis['group_id'], sequence=row['sequence'],
                entry_sha256=row['entry_sha256'], proof_sha256=_sha(row['proof_json']), line_sha256=_sha(canonical(dict(line)))))
        gross, tax = _cents(basis['gross']), _cents(basis['tax'])
        if not gross and rows:
            raise ValueError('Zero group was allocated')
        used_tax = _tax(cumulative, tax, gross) if gross else 0
        public = dict(basis, documented_net=_money(cumulative-used_tax), documented_tax=_money(used_tax), documented_gross=_money(cumulative),
            remaining_net=_money(_cents(basis['net'])-cumulative+used_tax), remaining_tax=_money(tax-used_tax), remaining_gross=_money(gross-cumulative))
        return public, references

    def _portion(self, context, raw, *, historical=None, before_sequence=None):
        metadata, bases, archive = self._basis(context, raw)
        reason, eligibility = self._eligibility(context, raw) if historical is None else (None, historical)
        groups = []; pools = {}
        for basis in bases:
            group, references = self._pool(basis, before_sequence)
            pools[basis['group_id']] = references
            if _cents(basis['gross']):
                groups.append(group)
        if reason is None and _cents(raw['amount']) > sum(_cents(group['remaining_gross']) for group in groups):
            reason = 'group_capacity_exceeded'
        binding = dict(schema_version=1, source=dict(event_sha256=_sha(canonical(context['event'])), portion=raw),
            basis=bases, archive=archive, eligibility=eligibility, pools_before=pools)
        portion = dict(portion_id=raw['portion_id'], kind=raw['kind'], event_id=context['event']['id'], **metadata,
            amount=raw['amount'], currency='EUR', portion_state_hash=_sha(canonical(binding)), eligible=reason is None, blocked_reason=reason, groups=groups)
        return portion, binding

    @_stored
    def _history(self, context):
        rows = self.office.db.execute('SELECT * FROM business_accounting_component_entries WHERE event_id=? ORDER BY revision,id', (context['event']['id'],)).fetchall()
        entries = []; headers = []
        for revision, row in enumerate(rows, 1):
            value, proof = self._basic(row)
            current, raw, unused_metadata, unused_bases = self._proof_source(row, proof)
            if (row['revision'] != revision or row['previous_state_hash'] != _state_hash(row['event_id'], row['source_hash'], proof['portions_before'], headers)):
                raise ValueError('Invalid component event history')
            portion, binding = self._portion(current, raw, historical=proof['eligibility'], before_sequence=row['sequence'])
            if (portion != value['portion'] or value['amount'] != portion['amount']
                    or any(binding[key] != proof[key] for key in binding if key != 'schema_version')):
                raise ValueError('Invalid historical group capacity')
            by_group = {group['group_id']: group for group in proof['basis']}
            previous_groups = {group['group_id']: group for group in portion['groups']}
            for line in value['lines']:
                before = _cents(previous_groups[line['group_id']]['documented_gross'])
                if _line(by_group[line['group_id']], before, _cents(line['amount'], positive=True)) != line:
                    raise ValueError('Invalid documentary cent rule')
            entries.append(value); headers.append(_header(row))
        return entries, headers

    def _view(self, fresh, event_id):
        context = self._source(fresh, event_id); entries, headers = self._history(context)
        documented = sum(_cents(entry['amount']) for entry in entries); total = _cents(context['event']['amount'])
        if documented > total:
            raise Problem(409, 'Dokumentierte Anteile überschreiten den Geldfluss')
        done = {entry['portion']['portion_id'] for entry in entries}; portions = []
        for raw in context['portions']:
            if raw['portion_id'] not in done:
                portions.append(self._portion(context, raw)[0])
        eligible = any(value['eligible'] for value in portions)
        reason = (None if eligible else context['reason'] or (portions[0]['blocked_reason'] if portions else
                  'unallocated' if _cents(context['unallocated']) else 'fully_documented'))
        state = dict(event_id=event_id, source_hash=context['event']['source']['source_hash'], revision=len(entries),
            state_hash=_state_hash(event_id, context['event']['source']['source_hash'], context['portions'], headers), source_kind=context['kind'],
            amount=context['event']['amount'], currency='EUR', documented_amount=_money(documented), undocumented_amount=_money(total-documented),
            unallocated_amount=context['unallocated'], eligible=eligible, blocked_reason=reason, writes_allowed=self._writes_allowed(fresh, event_id), **_FLAGS)
        return state, context, entries, portions

    def state(self, actor, event_id):
        identifier(event_id)
        with transaction(self.office):
            fresh = self._access(actor, event_id)
            return self._view(fresh, event_id)[0]

    def portions(self, actor, event_id, limit=50, offset=0):
        from business_accounting import _page, _paged
        identifier(event_id); _page(limit, offset)
        with transaction(self.office):
            fresh = self._access(actor, event_id, True)
            return _paged(self._view(fresh, event_id)[3], limit, offset)

    def history(self, actor, event_id, limit=50, offset=0):
        from business_accounting import _page, _paged
        identifier(event_id); _page(limit, offset)
        with transaction(self.office):
            fresh = self._access(actor, event_id)
            return _paged(list(reversed(self._history(self._source(fresh, event_id))[0])), limit, offset)

    @staticmethod
    def _inputs(data, confirm=False):
        if not isinstance(data, dict) or set(data) != _INPUT | ({'request_id', 'preview_hash', 'confirmation'} if confirm else set()):
            raise Problem(400, 'Vollständige bekannte Felder für Beleganteile erwartet')
        for key in ('source_hash', 'state_hash', 'portion_id', 'portion_state_hash') + (('preview_hash',) if confirm else ()):
            if not isinstance(data[key], str) or not re.fullmatch(_HASH, data[key]):
                raise Problem(400, 'SHA-256-Prüfsumme erwartet')
        if type(data['expected_revision']) is not int or data['expected_revision'] < 0:
            raise Problem(400, 'Nichtnegative Aufteilungsrevision erwartet')
        if confirm:
            identifier(data['request_id'], 'request_id')
            if data['confirmation'] is not True:
                raise Problem(400, 'Aufteilung ausdrücklich bestätigen')
        reason = data['reason']
        if (not isinstance(reason, str) or not 1 <= len(reason) <= 1000 or not reason.strip()
                or any(ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF for char in reason)):
            raise Problem(400, 'Einzeilige Begründung mit 1 bis 1000 Zeichen erwartet')
        if not isinstance(data['groups'], list) or not 1 <= len(data['groups']) <= 500:
            raise Problem(400, '1 bis 500 ausdrückliche positive Gruppenbeträge erwartet')
        seen = set()
        for group in data['groups']:
            if (not isinstance(group, dict) or set(group) != {'group_id', 'amount'} or not isinstance(group['group_id'], str)
                    or not re.fullmatch(_HASH, group['group_id']) or group['group_id'] in seen):
                raise Problem(400, 'Eindeutige bekannte Gruppenfelder erwartet')
            seen.add(group['group_id']); _cents(group['amount'], positive=True, input_value=True)

    @staticmethod
    def _request_hash(event_id, data):
        return _sha(canonical(['components.confirm', event_id, data]))

    def _prepare(self, state, context, data):
        if any(data[key] != state[target] for key, target in (('source_hash', 'source_hash'), ('expected_revision', 'revision'), ('state_hash', 'state_hash'))):
            raise Problem(409, 'Quellen- oder Aufteilungsstand geändert; neu laden')
        raw = next((value for value in context['portions'] if value['portion_id'] == data['portion_id']), None)
        if not raw:
            raise Problem(409, 'Quellenanteil gehört nicht zum Geldfluss')
        from business_accounting_capacity import require_legacy_writer
        require_legacy_writer(self.office, raw['document_id'])
        if self.office.db.execute('SELECT 1 FROM business_accounting_component_entries WHERE portion_id=?', (data['portion_id'],)).fetchone():
            raise Problem(409, 'Quellenanteil wurde bereits dokumentiert')
        portion, proof = self._portion(context, raw)
        if not portion['eligible']:
            raise Problem(409, 'Dokumentarische Aufteilung gesperrt: ' + portion['blocked_reason'])
        if portion['portion_state_hash'] != data['portion_state_hash']:
            raise Problem(409, 'Beleggruppen oder deren dokumentierter Stand wurden geändert')
        if sum(_cents(value['amount']) for value in data['groups']) != _cents(portion['amount']):
            raise Problem(400, 'Gruppenbeträge müssen den ganzen unveränderlichen Quellenanteil ergeben')
        available = {group['group_id']: group for group in portion['groups']}; bases = {group['group_id']: group for group in proof['basis']}; lines = []
        for group in sorted(data['groups'], key=lambda item: item['group_id']):
            if group['group_id'] not in available:
                raise Problem(409, 'Gruppe gehört nicht zu den verteilbaren Beleggruppen')
            before = _cents(available[group['group_id']]['documented_gross'])
            lines.append(_line(bases[group['group_id']], before, _cents(group['amount'], positive=True)))
        preview = dict(event_id=state['event_id'], source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
            portion=portion, amount=portion['amount'], net=_money(sum(_cents(line['net']) for line in lines)), tax=_money(sum(_cents(line['tax']) for line in lines)),
            lines=lines, reason=data['reason'], **_FLAGS)
        proof['portions_before'] = context['portions']
        return dict(preview, preview_hash=_sha(canonical(preview))), proof

    def preview(self, actor, event_id, data):
        identifier(event_id); self._inputs(data)
        with transaction(self.office):
            fresh = self._access(actor, event_id, True); self._gate()
            state, context, unused_entries, unused_portions = self._view(fresh, event_id)
            return self._prepare(state, context, data)[0]

    def confirm(self, actor, event_id, data):
        identifier(event_id); self._inputs(data, True)
        with transaction(self.office):
            fresh = self._access(actor, event_id, True); self._gate()
            context = self._source(fresh, event_id); entries, unused_headers = self._history(context)
            digest = self._request_hash(event_id, data)
            request = self.office.db.execute('SELECT * FROM business_accounting_component_requests WHERE user_id=? AND request_id=?',
                                             (fresh['id'], data['request_id'])).fetchone()
            if request:
                if request['event_id'] != event_id or request['request_hash'] != digest:
                    raise Problem(409, 'Vorgangs-ID wurde mit anderem Inhalt verwendet')
                return next(entry for entry in entries if entry['id'] == request['entry_id'])
            try:
                state, context, unused_entries, unused_portions = self._view(fresh, event_id)
                preview, proof = self._prepare(state, context, data)
                if preview['preview_hash'] != data['preview_hash']:
                    raise Problem(409, 'Passende aktuelle Vorschau erforderlich')
            except Problem as error:
                if error.status != 409:
                    raise
                raise Problem(409, error.message, request_resolution='not_accepted') from None
            sequence = self.office.db.execute('SELECT COALESCE(MAX(sequence),0)+1 FROM business_accounting_component_entries').fetchone()[0]
            entry = {key: value for key, value in preview.items() if key not in ('expected_revision', 'state_hash')}
            entry.update(id=uuid.uuid4().hex, sequence=sequence, revision=state['revision']+1, previous_state_hash=state['state_hash'],
                         created_by=fresh['id'], created_at=self.now())
            encoded = canonical(entry)
            self.office.db.execute('INSERT INTO business_accounting_component_entries(id,sequence,event_id,revision,portion_id,source_hash,previous_state_hash,'
                'entry_json,entry_sha256,proof_json,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                (entry['id'], sequence, event_id, entry['revision'], data['portion_id'], entry['source_hash'], entry['previous_state_hash'], encoded,
                 _sha(encoded), canonical(proof), fresh['id'], entry['created_at']))
            bases = {group['group_id']: group for group in proof['basis']}
            for line in entry['lines']:
                basis = canonical(bases[line['group_id']])
                self.office.db.execute('INSERT INTO business_accounting_component_lines(entry_id,' + ','.join(_LINE) + ',basis_json,basis_sha256) '
                    'VALUES(' + ','.join('?' for unused in range(len(_LINE)+3)) + ')', (entry['id'],) + tuple(line[key] for key in _LINE) + (basis, _sha(basis)))
            self.office.db.execute('INSERT INTO business_accounting_component_requests(user_id,request_id,event_id,request_json,request_hash,entry_id) VALUES(?,?,?,?,?,?)',
                                   (fresh['id'], data['request_id'], event_id, canonical(data), digest, entry['id']))
            self.office.audit(fresh, 'business.accounting.components_confirmed', entry['id'])
            return entry


def validate_integrity(office):
    try:
        if not installed(office):
            return True
        api = DocumentComponents(office)
        rows = office.db.execute('SELECT * FROM business_accounting_component_entries ORDER BY sequence').fetchall()
        if [row['sequence'] for row in rows] != list(range(1, len(rows)+1)):
            raise ValueError('Invalid global component sequence')
        line_count = 0
        for event_id in sorted({row['event_id'] for row in rows}):
            context = api._source(None, event_id)
            entries, unused = api._history(context)
            if sum(_cents(value['amount']) for value in entries) > _cents(context['event']['amount']):
                raise ValueError('Components exceed cash event')
            line_count += sum(len(value['lines']) for value in entries)
        if len(rows) != office.db.execute('SELECT COUNT(*) FROM business_accounting_component_requests').fetchone()[0]:
            raise ValueError('Orphan component receipt')
        if line_count != office.db.execute('SELECT COUNT(*) FROM business_accounting_component_lines').fetchone()[0]:
            raise ValueError('Orphan component line')
        if isinstance(office.db, sqlite3.Connection):
            normalize = lambda value: re.sub(r'\s+', ' ', value.replace('IF NOT EXISTS ', '')).strip().lower()
            for sql in guard_statements('sqlite'):
                name = re.search(r'CREATE TRIGGER IF NOT EXISTS (\w+)', sql)[1]
                row = office.db.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?", (name,)).fetchone()
                if not row or normalize(row[0]) != normalize(sql):
                    raise ValueError('Missing or changed component guard')
        else:
            from business_documents import _validate_pg_guards
            _validate_pg_guards(office.db, guard_statements('postgresql'))
    except (Problem, TypeError, KeyError, ArithmeticError) as error:
        raise ValueError('Invalid documentary component history') from error
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
    match = re.fullmatch(r'/accounting/components/events/' + _ID + r'(/(?:portions|history|preview|confirm))?', path)
    return ('POST' if match[1] in ('/preview', '/confirm') else 'GET') if match else None


def dispatch(office, actor, path, method, data):
    allowed = methods(path)
    if allowed is None:
        return None
    if allowed != method:
        raise Problem(405, 'Methode nicht unterstützt')
    if not isinstance(data, dict) or not isinstance(data.get('_query', {}), dict):
        raise Problem(400, 'Eindeutige Parameter für Beleganteile erwartet')
    parts = path.split('/'); event_id = parts[4]; action = parts[5] if len(parts) > 5 else 'state'; api = DocumentComponents(office)
    if method == 'GET':
        if set(data) - {'_query'}:
            raise Problem(400, 'GET erwartet keinen Anfragekörper')
        query = data.get('_query', {})
        if action == 'state':
            if query:
                raise Problem(400, 'Keine zusätzlichen Filter erlaubt')
            result = api.state(actor, event_id)
        else:
            if set(query) - {'limit', 'offset'} or any(not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,6}', value) for value in query.values()):
                raise Problem(400, 'Nur ganzzahlige Limit-/Offsetfilter erwartet')
            result = getattr(api, action)(actor, event_id, int(query.get('limit', '50')), int(query.get('offset', '0')))
        return result, 200, 'application/json'
    if '_query' in data:
        raise Problem(400, 'Keine zusätzlichen Filter erlaubt')
    return getattr(api, action)(actor, event_id, data), (201 if action == 'confirm' else 200), 'application/json'
