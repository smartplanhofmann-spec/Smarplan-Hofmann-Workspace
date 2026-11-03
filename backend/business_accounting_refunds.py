"""Whole existing refund portions bound to immutable documentary income lots.

This journal records exact returned cents only. It never changes Finance,
cash events, component lines or reusable documentary group capacity.
"""
import json
import re
import sqlite3
import uuid

from core import Problem, canonical
from business_operations import Domain, identifier, iso_date, transaction
from business_accounting_components import DocumentComponents, _cents, _money, _sha, _stored

FEATURES = ('accounting_refund_origins',)
_TABLES = tuple('business_accounting_refund_' + name for name in ('entries', 'lines', 'requests'))
_ID = r'[a-f0-9]{32}'
_HASH = r'[a-f0-9]{64}'
_INPUT = {'source_hash', 'expected_revision', 'state_hash', 'portion_id', 'portion_state_hash', 'origins', 'reason'}
_MONEY_FIELDS = ('amount', 'net', 'tax', 'gross_before', 'gross_after', 'net_before', 'net_after', 'tax_before', 'tax_after',
                 'remaining_gross', 'remaining_net', 'remaining_tax')
_LINE_FIELDS = {'entry_id', 'group_id', 'origin_event_id', 'component_sequence', 'rate', 'category', 'tax_reason',
                'origin_cash_date', 'origin_evidence_reference', 'origin_reference', 'lot_state_hash'} | set(_MONEY_FIELDS)
_FLAGS = dict(capacity_released=False, scope='authorized_sources', tax_status='unconfigured', tax_result_available=False)


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BLOB', 'BYTEA'):
        raise ValueError('Unsupported binary type')
    return [
        '''CREATE TABLE IF NOT EXISTS business_accounting_refund_entries(
        id TEXT PRIMARY KEY, sequence INTEGER NOT NULL UNIQUE CHECK(sequence>0),
        event_id TEXT NOT NULL REFERENCES business_accounting_cash_events(id), revision INTEGER NOT NULL CHECK(revision>0),
        refund_allocation_id TEXT NOT NULL UNIQUE REFERENCES business_payment_allocations(id),
        portion_id TEXT NOT NULL UNIQUE CHECK(length(portion_id)=64), source_hash TEXT NOT NULL CHECK(length(source_hash)=64),
        previous_state_hash TEXT NOT NULL CHECK(length(previous_state_hash)=64),
        entry_json TEXT NOT NULL, entry_sha256 TEXT NOT NULL CHECK(length(entry_sha256)=64), proof_json TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL, UNIQUE(event_id,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_accounting_refund_lines(
        entry_id TEXT NOT NULL REFERENCES business_accounting_refund_entries(id), origin_entry_id TEXT NOT NULL,
        group_id TEXT NOT NULL CHECK(length(group_id)=64), amount TEXT NOT NULL, net TEXT NOT NULL, tax TEXT NOT NULL,
        gross_before TEXT NOT NULL, gross_after TEXT NOT NULL, net_before TEXT NOT NULL, net_after TEXT NOT NULL,
        tax_before TEXT NOT NULL, tax_after TEXT NOT NULL,
        remaining_gross TEXT NOT NULL, remaining_net TEXT NOT NULL, remaining_tax TEXT NOT NULL,
        origin_line_sha256 TEXT NOT NULL CHECK(length(origin_line_sha256)=64),
        PRIMARY KEY(entry_id,origin_entry_id,group_id),
        FOREIGN KEY(origin_entry_id,group_id) REFERENCES business_accounting_component_lines(entry_id,group_id))''',
        '''CREATE TABLE IF NOT EXISTS business_accounting_refund_requests(
        user_id TEXT NOT NULL REFERENCES users(id), request_id TEXT NOT NULL,
        event_id TEXT NOT NULL REFERENCES business_accounting_cash_events(id), request_json TEXT NOT NULL,
        request_hash TEXT NOT NULL CHECK(length(request_hash)=64),
        entry_id TEXT NOT NULL UNIQUE REFERENCES business_accounting_refund_entries(id), PRIMARY KEY(user_id,request_id))''',
        'CREATE INDEX IF NOT EXISTS business_accounting_refund_origins ON business_accounting_refund_lines(origin_entry_id,group_id,entry_id)',
    ]


def protected_tables():
    return _TABLES


def runtime_privileges():
    return {table: ('SELECT', 'INSERT') for table in _TABLES}


def guard_statements(dialect):
    if dialect == 'sqlite':
        guards = [f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} ON {table} "
                  "BEGIN SELECT RAISE(ABORT,'immutable refund origin history'); END"
                  for table in _TABLES for action in ('UPDATE', 'DELETE')]
        conflicts = ('id=NEW.id OR sequence=NEW.sequence OR refund_allocation_id=NEW.refund_allocation_id OR portion_id=NEW.portion_id OR (event_id=NEW.event_id AND revision=NEW.revision)',
                     'entry_id=NEW.entry_id AND origin_entry_id=NEW.origin_entry_id AND group_id=NEW.group_id',
                     '(user_id=NEW.user_id AND request_id=NEW.request_id) OR entry_id=NEW.entry_id')
        for table, conflict in zip(_TABLES, conflicts):
            guards.append(f'CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} '
                          f'WHEN EXISTS(SELECT 1 FROM {table} WHERE {conflict}) '
                          "BEGIN SELECT RAISE(ABORT,'immutable refund origin history'); END")
        return guards
    if dialect != 'postgresql':
        raise ValueError('Unsupported guard dialect')
    guards = ["""CREATE OR REPLACE FUNCTION business_accounting_refund_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'immutable refund origin history'; END; $$"""]
    for table in _TABLES:
        for action in ('UPDATE', 'DELETE'):
            name = table + '_' + action.lower() + '_guard'
            guards.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) "
                          f"THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION "
                          "business_accounting_refund_immutable_guard(); END IF; END $$")
    return guards


def installed(office):
    from business_schema import _tables
    from business_accounting_components import installed as components_installed
    tables = _tables(office); present = set(_TABLES) & tables
    marker = ('business_schema_migrations' in tables and office.db.execute(
        "SELECT 1 FROM business_schema_migrations WHERE module='business_accounting_refunds'").fetchone())
    if not present and not marker:
        return False
    if present != set(_TABLES) or not marker or not components_installed(office):
        raise Problem(409, 'Erstattungsursprünge oder ihre Abhängigkeiten sind unvollständig installiert')
    return True


def _hash_input(value):
    if not isinstance(value, str) or not re.fullmatch(_HASH, value):
        raise Problem(400, 'SHA-256-Prüfsumme erwartet')
    return value


def _portion_id(allocation_id):
    return _sha(canonical(dict(kind='original_refund_allocation', id=allocation_id)))


def _header(row):
    return {key: row[key] for key in ('id', 'sequence', 'revision', 'entry_sha256')}


def _state_hash(context, headers):
    return _sha(canonical(dict(schema_version=1, event_id=context['event']['id'],
        source_hash=context['event']['source']['source_hash'], portions=context['portions'], entries=headers)))


def _tax(returned, tax, gross):
    return (2*returned*tax+gross)//(2*gross)


def _origin(lot, returned, references):
    value = lot['value']; gross, net, tax = (_cents(value[key]) for key in ('amount', 'net', 'tax'))
    if returned > gross:
        raise Problem(409, 'Ursprungslot wurde über seine festen Cents hinaus zurückgenommen')
    returned_tax = _tax(returned, tax, gross)
    return dict(value, returned_amount=_money(returned), returned_net=_money(returned-returned_tax), returned_tax=_money(returned_tax),
        remaining_amount=_money(gross-returned), remaining_net=_money(net-returned+returned_tax), remaining_tax=_money(tax-returned_tax),
        lot_state_hash=_sha(canonical(dict(schema_version=1, origin=lot['reference'], claims=references))))


def _line(origin, amount):
    gross, net, tax = (_cents(origin[key]) for key in ('amount', 'net', 'tax'))
    before = _cents(origin['returned_amount']); after = before+amount
    if amount <= 0 or after > gross:
        raise Problem(409, 'Rücknahme überschreitet den noch verfügbaren Ursprungslot')
    old_tax, new_tax = _tax(before, tax, gross), _tax(after, tax, gross)
    return dict(**{key: origin[key] for key in ('entry_id', 'group_id', 'origin_event_id', 'component_sequence', 'rate', 'category', 'tax_reason', 'lot_state_hash')},
        origin_cash_date=origin['cash_date'], origin_evidence_reference=origin['evidence_reference'], origin_reference=origin['reference'],
        amount=_money(amount), net=_money(amount-new_tax+old_tax), tax=_money(new_tax-old_tax),
        gross_before=_money(before), gross_after=_money(after), net_before=_money(before-old_tax), net_after=_money(after-new_tax),
        tax_before=_money(old_tax), tax_after=_money(new_tax), remaining_gross=_money(gross-after),
        remaining_net=_money(net-after+new_tax), remaining_tax=_money(tax-new_tax))


class RefundOrigins(Domain):
    def _access(self, actor, event_id, write=False, selected=()):
        """Only relational IDs are read until every required source is authorized."""
        components = DocumentComponents(self.office)
        fresh = components._access(actor, event_id, write)
        if not installed(self.office):
            raise Problem(409, 'Erstattungsursprünge sind nicht installiert')
        linked = {row[0] for row in self.office.db.execute('SELECT DISTINCT l.origin_entry_id FROM business_accounting_refund_lines l '
            'JOIN business_accounting_refund_entries e ON e.id=l.entry_id WHERE e.event_id=?', (event_id,)).fetchall()}
        new = {value['entry_id'] for value in selected}
        for entry_id in sorted(linked | new):
            row = self.office.db.execute('SELECT event_id FROM business_accounting_component_entries WHERE id=?', (entry_id,)).fetchone()
            if not row:
                raise Problem(409 if entry_id in linked else 404, 'Dokumentierter Ursprung nicht verfügbar')
            components._access(fresh, row['event_id'], write)
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
    def _source(self, event_id, cache):
        key = ('refund_source', event_id)
        if key in cache:
            return cache[key]
        from business_accounting import Accounting
        base = DocumentComponents(self.office)._source(None, event_id)
        event = base['event']; iso_date(event['cash_date']); portions = []; reason = None
        if base['kind'] != 'customer_refund':
            reason = 'not_customer_refund'
        else:
            for allocation in self.office.db.execute('SELECT * FROM business_payment_allocations WHERE payment_id=? ORDER BY id', (event['source']['id'],)).fetchall():
                document = self.office.db.execute('SELECT * FROM business_documents WHERE id=?', (allocation['document_id'],)).fetchone()
                proof = Accounting(self.office)._document_proof(document); payload = json.loads(document['payload_json'])
                supported = (document['kind'] == 'invoice' and payload.get('currency') == 'EUR' and _cents(payload['totals']['gross']) > 0
                             and not payload.get('previous_document_ids') and not payload.get('previous_documents'))
                portions.append(dict(portion_id=_portion_id(allocation['id']), allocation=dict(allocation), document=proof,
                                     party_name=payload['buyer']['name'], supported=bool(supported)))
            customers = {value['document']['customer_id'] for value in portions}
            if portions and (len(customers) != 1 or not next(iter(customers))):
                reason = 'source_customer_unresolved'
        portions.sort(key=lambda value: value['portion_id'])
        context = dict(event=event, kind=base['kind'], reason=reason, portions=portions,
                       unallocated=event['source']['snapshot']['unallocated'] if event['source']['kind'] == 'payment' else '0.00')
        cache[key] = context
        return context

    def _portion(self, context, raw, *, bound=False):
        document, allocation = raw['document'], raw['allocation']
        reason = context['reason'] or ('unsupported_document' if not raw['supported'] else 'fully_documented' if bound else None)
        binding = dict(schema_version=1, source_hash=context['event']['source']['source_hash'], portion=raw, bound=bound)
        return dict(portion_id=raw['portion_id'], kind='original_refund_allocation', event_id=context['event']['id'],
            **{key: document[key] for key in ('document_id', 'customer_id', 'project_id', 'number', 'payload_sha256', 'pdf_sha256')},
            party_name=raw['party_name'], amount=allocation['amount'], currency='EUR', portion_state_hash=_sha(canonical(binding)),
            eligible=reason is None, blocked_reason=reason)

    @_stored
    def _component_history(self, event_id, cache):
        key = ('component_history', event_id)
        if key not in cache:
            components = DocumentComponents(self.office)
            context = components._source(None, event_id)
            entries, unused = components._history(context)
            cache[key] = (context, {value['id']: value for value in entries})
        return cache[key]

    @_stored
    def _lot(self, entry_id, group_id, cache):
        key = ('origin_lot', entry_id, group_id)
        if key in cache:
            return cache[key]
        row = self.office.db.execute('SELECT * FROM business_accounting_component_entries WHERE id=?', (entry_id,)).fetchone()
        line = self.office.db.execute('SELECT * FROM business_accounting_component_lines WHERE entry_id=? AND group_id=?', (entry_id, group_id)).fetchone()
        if not row or not line:
            raise Problem(404, 'Dokumentierter Ursprungslot nicht verfügbar')
        context, entries = self._component_history(row['event_id'], cache)
        if context['kind'] != 'customer_receipt':
            raise Problem(409, 'Ursprung muss ein dokumentierter Kundeneingang sein')
        entry = entries[entry_id]; proof = json.loads(row['proof_json']); basis = json.loads(line['basis_json'])
        document = proof['archive']['archive']['document']
        if (document['kind'] != 'invoice' or not document['customer_id'] or entry['portion']['document_id'] != document['id']
                or _cents(line['net'])+_cents(line['tax']) != _cents(line['amount'], positive=True, input_value=True)
                or type(row['sequence']) is not int or row['sequence'] < 1):
            raise ValueError('Invalid documentary income lot')
        event = context['event']; iso_date(event['cash_date'])
        value = dict(entry_id=entry_id, group_id=group_id, origin_event_id=event['id'], component_sequence=row['sequence'],
            rate=basis['rate'], category=basis['category'], tax_reason=basis['reason'], document_id=document['id'], customer_id=document['customer_id'],
            project_id=document['project_id'], number=document['number'], party_name=entry['portion']['party_name'],
            cash_date=event['cash_date'], evidence_reference=event['evidence_reference'], reference=event['reference'], currency='EUR',
            **{field: line[field] for field in ('amount', 'net', 'tax')})
        reference = dict(entry_id=entry_id, group_id=group_id, origin_event_id=event['id'], entry_sha256=row['entry_sha256'],
            proof_sha256=_sha(row['proof_json']), line_sha256=_sha(canonical(dict(line))), source_hash=event['source']['source_hash'])
        lot = dict(value=value, reference=reference)
        cache[key] = lot
        return lot

    @staticmethod
    def _inputs(data, confirm=False):
        if not isinstance(data, dict) or set(data) != _INPUT | ({'request_id', 'preview_hash', 'confirmation'} if confirm else set()):
            raise Problem(400, 'Vollständige bekannte Erstattungsfelder erwartet')
        for key in ('source_hash', 'state_hash', 'portion_id', 'portion_state_hash') + (('preview_hash',) if confirm else ()):
            _hash_input(data[key])
        if type(data['expected_revision']) is not int or data['expected_revision'] < 0:
            raise Problem(400, 'Nichtnegative Ursprungsrevision erwartet')
        if confirm:
            identifier(data['request_id'], 'request_id')
            if data['confirmation'] is not True:
                raise Problem(400, 'Erstattungsursprung ausdrücklich bestätigen')
        reason = data['reason']
        if (not isinstance(reason, str) or not 1 <= len(reason) <= 1000 or not reason.strip()
                or any(ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF for char in reason)):
            raise Problem(400, 'Einzeilige Begründung mit 1 bis 1000 Zeichen erwartet')
        if not isinstance(data['origins'], list) or not 1 <= len(data['origins']) <= 500:
            raise Problem(400, '1 bis 500 ausdrückliche Ursprungslotbeträge erwartet')
        seen = set()
        for origin in data['origins']:
            if not isinstance(origin, dict) or set(origin) != {'entry_id', 'group_id', 'lot_state_hash', 'amount'}:
                raise Problem(400, 'Bekannte Ursprungslotfelder erwartet')
            identifier(origin['entry_id']); _hash_input(origin['group_id']); _hash_input(origin['lot_state_hash'])
            key = (origin['entry_id'], origin['group_id'])
            if key in seen:
                raise Problem(400, 'Ursprungslot doppelt angegeben')
            seen.add(key); _cents(origin['amount'], positive=True, input_value=True)

    @staticmethod
    def _request_hash(event_id, data):
        return _sha(canonical(['refund.confirm', event_id, data]))

    @staticmethod
    def _preview_from_entry(value):
        preview = {key: item for key, item in value.items() if key not in ('id', 'sequence', 'revision', 'previous_state_hash', 'created_by', 'created_at', 'preview_hash')}
        return dict(preview, expected_revision=value['revision']-1, state_hash=value['previous_state_hash'])

    @_stored
    def _basic(self, row):
        value = json.loads(row['entry_json']); proof = json.loads(row['proof_json'])
        expected = {'id', 'sequence', 'revision', 'previous_state_hash', 'created_by', 'created_at', 'event_id', 'source_hash',
                    'cash_date', 'evidence_reference', 'reference', 'portion', 'amount', 'net', 'tax', 'lines', 'reason', 'preview_hash'} | set(_FLAGS)
        if (set(value) != expected or any(value[key] != expected_value for key, expected_value in _FLAGS.items())
                or value['capacity_released'] is not False or value['tax_result_available'] is not False
                or type(value['sequence']) is not int or type(value['revision']) is not int
                or canonical(value) != row['entry_json'] or canonical(proof) != row['proof_json'] or _sha(row['entry_json']) != row['entry_sha256']
                or any(value[key] != row[key] for key in ('id', 'sequence', 'revision', 'event_id', 'source_hash', 'previous_state_hash', 'created_by', 'created_at'))
                or value['portion']['portion_id'] != row['portion_id'] or type(row['sequence']) is not int or row['sequence'] < 1
                or type(row['revision']) is not int or row['revision'] < 1):
            raise ValueError('Invalid refund origin entry')
        identifier(row['id']); identifier(row['event_id']); identifier(row['created_by']); identifier(row['refund_allocation_id'])
        if (not isinstance(value['lines'], list) or not 1 <= len(value['lines']) <= 500
                or [(line['entry_id'], line['group_id']) for line in value['lines']] != sorted({(line['entry_id'], line['group_id']) for line in value['lines']})):
            raise ValueError('Invalid refund origin lines')
        if (sum(_cents(line['amount'], positive=True) for line in value['lines']) != _cents(value['amount'], positive=True, input_value=True)
                or sum(_cents(line['net']) for line in value['lines']) != _cents(value['net'])
                or sum(_cents(line['tax']) for line in value['lines']) != _cents(value['tax'])
                or _cents(value['net'])+_cents(value['tax']) != _cents(value['amount'])):
            raise ValueError('Invalid refund origin totals')
        stored = self.office.db.execute('SELECT * FROM business_accounting_refund_lines WHERE entry_id=? ORDER BY origin_entry_id,group_id', (row['id'],)).fetchall()
        if len(stored) != len(value['lines']):
            raise ValueError('Missing refund line')
        for line, actual in zip(value['lines'], stored):
            if (set(line) != _LINE_FIELDS or line['entry_id'] != actual['origin_entry_id'] or line['group_id'] != actual['group_id']
                    or any(line[key] != actual[key] for key in _MONEY_FIELDS)):
                raise ValueError('Changed refund origin line')
        request = self.office.db.execute('SELECT * FROM business_accounting_refund_requests WHERE entry_id=?', (row['id'],)).fetchone()
        if not request:
            raise ValueError('Missing refund request receipt')
        body = json.loads(request['request_json']); self._inputs(body, True)
        wanted = [{key: line[key] for key in ('entry_id', 'group_id', 'lot_state_hash', 'amount')} for line in value['lines']]
        if (request['event_id'] != row['event_id'] or request['user_id'] != row['created_by'] or request['request_id'] != body['request_id']
                or canonical(body) != request['request_json'] or request['request_hash'] != self._request_hash(row['event_id'], body)
                or body['expected_revision'] != row['revision']-1 or body['state_hash'] != row['previous_state_hash']
                or any(body[key] != value[key] for key in ('source_hash', 'preview_hash', 'reason'))
                or body['portion_id'] != row['portion_id'] or body['portion_state_hash'] != value['portion']['portion_state_hash']
                or sorted(body['origins'], key=lambda item: (item['entry_id'], item['group_id'])) != wanted
                or _sha(canonical(self._preview_from_entry(value))) != value['preview_hash']):
            raise ValueError('Changed refund request or preview')
        return value, proof, stored

    @staticmethod
    def _match(context, portion, lot):
        origin = lot['value']
        if (context['kind'] != 'customer_refund' or not portion['eligible'] or origin['document_id'] != portion['document_id']
                or origin['customer_id'] != portion['customer_id'] or origin['currency'] != portion['currency']
                or origin['cash_date'] > context['event']['cash_date']):
            raise Problem(409, 'Ursprung muss zum selben Beleg und Kunden gehören und spätestens am Erstattungsdatum liegen')

    @_stored
    def _ledger(self, cache):
        """Single chronological pass, without recursive R1 proofs or ACL filters.

        Only aggregates/authorized entries leave this internal proof reader.
        Local memoization lives for one serialized API transaction, never longer.
        """
        if 'refund_ledger' in cache:
            return cache['refund_ledger']
        by_event = {}; headers = {}; returned = {}; references = {}; bound = set(); count_lines = 0
        rows = self.office.db.execute('SELECT * FROM business_accounting_refund_entries ORDER BY sequence,id').fetchall()
        for sequence, row in enumerate(rows, 1):
            value, proof, stored = self._basic(row)
            if row['sequence'] != sequence:
                raise ValueError('Invalid global refund sequence')
            try:
                context = self._source(row['event_id'], cache)
            except Problem as error:
                if error.status != 404:
                    raise
                raise Problem(409, 'Gespeicherte Erstattungsquelle fehlt') from None
            raw = next((part for part in context['portions'] if part['portion_id'] == row['portion_id']), None)
            if raw is None or raw['allocation']['id'] != row['refund_allocation_id'] or raw['portion_id'] in bound:
                raise ValueError('Missing or duplicated refund portion')
            portion = self._portion(context, raw)
            own = by_event.setdefault(row['event_id'], []); own_headers = headers.setdefault(row['event_id'], [])
            expected_source = dict(event_sha256=_sha(canonical(context['event'])), portion=raw)
            if (set(proof) != {'schema_version', 'source', 'origins', 'claims_before'}
                    or type(proof['schema_version']) is not int or proof['schema_version'] != 1
                    or proof['source'] != expected_source or value['portion'] != portion or not portion['eligible']
                    or value['amount'] != portion['amount'] or row['source_hash'] != context['event']['source']['source_hash']
                    or any(value[key] != context['event'][key] for key in ('cash_date', 'evidence_reference', 'reference'))
                    or row['revision'] != len(own)+1 or row['previous_state_hash'] != _state_hash(context, own_headers)):
                raise ValueError('Changed refund source, whole portion or event history')
            origins = []; claims = []; updates = []
            for line, actual in zip(value['lines'], stored):
                key = (line['entry_id'], line['group_id'])
                try:
                    lot = self._lot(*key, cache)
                except Problem as error:
                    if error.status != 404:
                        raise
                    raise Problem(409, 'Gespeicherter Ursprungslot fehlt') from None
                self._match(context, portion, lot)
                previous = references.get(key, [])
                origin = _origin(lot, returned.get(key, 0), previous)
                if actual['origin_line_sha256'] != lot['reference']['line_sha256'] or _line(origin, _cents(line['amount'], positive=True)) != line:
                    raise ValueError('Invalid historical cumulative lot return')
                origins.append(lot['reference'])
                claims.append(dict(entry_id=key[0], group_id=key[1], references=previous))
                updates.append((key, _cents(line['amount']), dict(entry_id=row['id'], sequence=row['sequence'], entry_sha256=row['entry_sha256'],
                    proof_sha256=_sha(row['proof_json']), line_sha256=_sha(canonical(dict(actual))))))
            if proof['origins'] != origins or proof['claims_before'] != claims:
                raise ValueError('Changed historical origin references')
            for key, amount, reference in updates:
                returned[key] = returned.get(key, 0)+amount
                references[key] = references.get(key, [])+[reference]
            own.append(value); own_headers.append(_header(row)); bound.add(raw['portion_id']); count_lines += len(stored)
            if sum(_cents(entry['amount']) for entry in own) > _cents(context['event']['amount']):
                raise ValueError('Origin bindings exceed the refund cash source')
        if len(rows) != self.office.db.execute('SELECT COUNT(*) FROM business_accounting_refund_requests').fetchone()[0]:
            raise ValueError('Orphan refund request')
        if count_lines != self.office.db.execute('SELECT COUNT(*) FROM business_accounting_refund_lines').fetchone()[0]:
            raise ValueError('Orphan refund line')
        ledger = dict(by_event=by_event, headers=headers, returned=returned, references=references, bound=bound)
        cache['refund_ledger'] = ledger
        return ledger

    def _view(self, fresh, event_id, cache):
        context = self._source(event_id, cache); ledger = self._ledger(cache)
        entries = ledger['by_event'].get(event_id, [])
        portions = [self._portion(context, raw) for raw in context['portions'] if raw['portion_id'] not in ledger['bound']]
        documented = sum(_cents(entry['amount']) for entry in entries)
        eligible = any(portion['eligible'] for portion in portions)
        reason = (None if eligible else context['reason'] or (portions[0]['blocked_reason'] if portions else
                  'unallocated' if _cents(context['unallocated']) else 'fully_documented'))
        state = dict(event_id=event_id, source_hash=context['event']['source']['source_hash'], revision=len(entries),
            state_hash=_state_hash(context, ledger['headers'].get(event_id, [])), source_kind=context['kind'], amount=context['event']['amount'], currency='EUR',
            **{key: context['event'][key] for key in ('cash_date', 'evidence_reference', 'reference')},
            origin_documented_amount=_money(documented), origin_unresolved_amount=_money(_cents(context['event']['amount'])-documented),
            unallocated_amount=context['unallocated'], eligible=eligible, blocked_reason=reason,
            writes_allowed=self._writes_allowed(fresh, event_id), **_FLAGS)
        return state, context, ledger, portions

    def state(self, actor, event_id):
        identifier(event_id)
        with transaction(self.office):
            fresh = self._access(actor, event_id)
            return self._view(fresh, event_id, {})[0]

    def portions(self, actor, event_id, limit=50, offset=0):
        from business_accounting import _page, _paged
        identifier(event_id); _page(limit, offset)
        with transaction(self.office):
            fresh = self._access(actor, event_id, True)
            return _paged(self._view(fresh, event_id, {})[3], limit, offset)

    def history(self, actor, event_id, limit=50, offset=0):
        from business_accounting import _page, _paged
        identifier(event_id); _page(limit, offset)
        with transaction(self.office):
            self._access(actor, event_id)
            cache = {}; self._source(event_id, cache)
            return _paged(list(reversed(self._ledger(cache)['by_event'].get(event_id, []))), limit, offset)

    def origins(self, actor, event_id, portion_id, limit=50, offset=0):
        from business_accounting import _page, _paged
        identifier(event_id); _hash_input(portion_id); _page(limit, offset)
        with transaction(self.office):
            fresh = self._access(actor, event_id, True); cache = {}
            unused, context, ledger, portions = self._view(fresh, event_id, cache)
            portion = next((value for value in portions if value['portion_id'] == portion_id), None)
            if not portion:
                raise Problem(409, 'Noch ungebundene Refundportion erforderlich')
            if not portion['eligible']:
                return _paged([], limit, offset)
            items = []; components = DocumentComponents(self.office)
            # Authorize an entire origin cash source before decoding its C1 DTO.
            for row in self.office.db.execute('SELECT id,event_id FROM business_accounting_component_entries ORDER BY id').fetchall():
                try:
                    components._access(fresh, row['event_id'], True)
                except Problem as error:
                    if error.status in (403, 404):
                        continue
                    raise
                component_source, entries = self._component_history(row['event_id'], cache)
                if component_source['kind'] != 'customer_receipt' or entries[row['id']]['portion']['document_id'] != portion['document_id']:
                    continue
                for line in entries[row['id']]['lines']:
                    key = (row['id'], line['group_id']); lot = self._lot(*key, cache)
                    value = lot['value']
                    if value['customer_id'] != portion['customer_id'] or value['cash_date'] > context['event']['cash_date']:
                        continue
                    origin = _origin(lot, ledger['returned'].get(key, 0), ledger['references'].get(key, []))
                    if _cents(origin['remaining_amount']) > 0:
                        items.append(origin)
            items.sort(key=lambda value: tuple(value[key] for key in ('cash_date', 'origin_event_id', 'entry_id', 'group_id')))
            return _paged(items, limit, offset)

    def _prepare(self, state, context, ledger, data, cache):
        if any(data[key] != state[target] for key, target in (('source_hash', 'source_hash'), ('expected_revision', 'revision'), ('state_hash', 'state_hash'))):
            raise Problem(409, 'Quellen- oder Bindungsstand geändert; neu laden')
        raw = next((value for value in context['portions'] if value['portion_id'] == data['portion_id']), None)
        if raw is None or raw['portion_id'] in ledger['bound']:
            raise Problem(409, 'Noch ungebundene ganze Refundportion erforderlich')
        portion = self._portion(context, raw)
        if not portion['eligible'] or portion['portion_state_hash'] != data['portion_state_hash']:
            raise Problem(409, 'Refundportion passt nicht zum aktuellen zulässigen Quellenstand')
        if sum(_cents(value['amount']) for value in data['origins']) != _cents(portion['amount']):
            raise Problem(400, 'Ursprungsbeträge müssen die ganze unveränderliche Refundportion ergeben')
        lines = []; origin_refs = []; claims = []
        for selected in sorted(data['origins'], key=lambda value: (value['entry_id'], value['group_id'])):
            key = (selected['entry_id'], selected['group_id']); lot = self._lot(*key, cache)
            self._match(context, portion, lot)
            previous = ledger['references'].get(key, [])
            origin = _origin(lot, ledger['returned'].get(key, 0), previous)
            if origin['lot_state_hash'] != selected['lot_state_hash']:
                raise Problem(409, 'Ursprungslot wurde zwischenzeitlich beansprucht; neu prüfen')
            lines.append(_line(origin, _cents(selected['amount'], positive=True)))
            origin_refs.append(lot['reference']); claims.append(dict(entry_id=key[0], group_id=key[1], references=previous))
        preview = dict(event_id=state['event_id'], source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
            **{key: context['event'][key] for key in ('cash_date', 'evidence_reference', 'reference')},
            portion=portion, amount=portion['amount'], net=_money(sum(_cents(line['net']) for line in lines)),
            tax=_money(sum(_cents(line['tax']) for line in lines)), lines=lines, reason=data['reason'], **_FLAGS)
        proof = dict(schema_version=1, source=dict(event_sha256=_sha(canonical(context['event'])), portion=raw), origins=origin_refs, claims_before=claims)
        return dict(preview, preview_hash=_sha(canonical(preview))), proof

    def preview(self, actor, event_id, data):
        identifier(event_id); self._inputs(data)
        with transaction(self.office):
            fresh = self._access(actor, event_id, True, data['origins']); self._gate(); cache = {}
            state, context, ledger, unused = self._view(fresh, event_id, cache)
            return self._prepare(state, context, ledger, data, cache)[0]

    def confirm(self, actor, event_id, data):
        identifier(event_id); self._inputs(data, True)
        with transaction(self.office):
            fresh = self._access(actor, event_id, True, data['origins']); self._gate(); cache = {}
            state, context, ledger, unused = self._view(fresh, event_id, cache)
            digest = self._request_hash(event_id, data)
            request = self.office.db.execute('SELECT * FROM business_accounting_refund_requests WHERE user_id=? AND request_id=?',
                                             (fresh['id'], data['request_id'])).fetchone()
            if request:
                if request['event_id'] != event_id or request['request_hash'] != digest:
                    raise Problem(409, 'Vorgangs-ID wurde mit anderem Inhalt verwendet')
                return next(value for value in ledger['by_event'].get(event_id, []) if value['id'] == request['entry_id'])
            preview, proof = self._prepare(state, context, ledger, data, cache)
            if preview['preview_hash'] != data['preview_hash']:
                raise Problem(409, 'Passende aktuelle Vorschau erforderlich')
            sequence = self.office.db.execute('SELECT COALESCE(MAX(sequence),0)+1 FROM business_accounting_refund_entries').fetchone()[0]
            entry = {key: value for key, value in preview.items() if key not in ('expected_revision', 'state_hash')}
            entry.update(id=uuid.uuid4().hex, sequence=sequence, revision=state['revision']+1, previous_state_hash=state['state_hash'],
                         created_by=fresh['id'], created_at=self.now())
            encoded = canonical(entry)
            self.office.db.execute('INSERT INTO business_accounting_refund_entries(id,sequence,event_id,revision,refund_allocation_id,portion_id,source_hash,'
                'previous_state_hash,entry_json,entry_sha256,proof_json,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (entry['id'], sequence, event_id, entry['revision'], proof['source']['portion']['allocation']['id'], data['portion_id'], entry['source_hash'],
                 entry['previous_state_hash'], encoded, _sha(encoded), canonical(proof), fresh['id'], entry['created_at']))
            for line in entry['lines']:
                lot = self._lot(line['entry_id'], line['group_id'], cache)
                self.office.db.execute('INSERT INTO business_accounting_refund_lines(entry_id,origin_entry_id,group_id,' + ','.join(_MONEY_FIELDS) + ',origin_line_sha256) '
                    'VALUES(' + ','.join('?' for unused in range(len(_MONEY_FIELDS)+4)) + ')',
                    (entry['id'], line['entry_id'], line['group_id']) + tuple(line[key] for key in _MONEY_FIELDS) + (lot['reference']['line_sha256'],))
            self.office.db.execute('INSERT INTO business_accounting_refund_requests(user_id,request_id,event_id,request_json,request_hash,entry_id) VALUES(?,?,?,?,?,?)',
                                   (fresh['id'], data['request_id'], event_id, canonical(data), digest, entry['id']))
            self.office.audit(fresh, 'business.accounting.refund_origin_confirmed', entry['id'])
            return entry


def validate_integrity(office):
    try:
        if not installed(office):
            return True
        RefundOrigins(office)._ledger({})
        if isinstance(office.db, sqlite3.Connection):
            normalize = lambda value: re.sub(r'\s+', ' ', value.replace('IF NOT EXISTS ', '')).strip().lower()
            for sql in guard_statements('sqlite'):
                name = re.search(r'CREATE TRIGGER IF NOT EXISTS (\w+)', sql)[1]
                row = office.db.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?", (name,)).fetchone()
                if not row or normalize(row[0]) != normalize(sql):
                    raise ValueError('Missing or changed refund guard')
        else:
            from business_documents import _validate_pg_guards
            _validate_pg_guards(office.db, guard_statements('postgresql'))
    except (Problem, KeyError, TypeError, ArithmeticError) as error:
        raise ValueError('Invalid refund origin history') from error
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
    match = re.fullmatch(r'/accounting/refunds/events/' + _ID + r'(/(?:portions|origins|history|preview|confirm))?', path)
    return ('POST' if match[1] in ('/preview', '/confirm') else 'GET') if match else None


def dispatch(office, actor, path, method, data):
    allowed = methods(path)
    if allowed is None:
        return None
    if method != allowed:
        raise Problem(405, 'Methode nicht unterstützt')
    if not isinstance(data, dict) or not isinstance(data.get('_query', {}), dict):
        raise Problem(400, 'Eindeutige Erstattungsparameter erwartet')
    parts = path.split('/'); event_id = parts[4]; action = parts[5] if len(parts) > 5 else 'state'; api = RefundOrigins(office)
    if method == 'GET':
        if set(data)-{'_query'}:
            raise Problem(400, 'GET erwartet keinen Anfragekörper')
        query = data.get('_query', {})
        if action == 'state':
            if query:
                raise Problem(400, 'Keine zusätzlichen Filter erlaubt')
            result = api.state(actor, event_id)
        else:
            allowed_query = {'limit', 'offset'} | ({'portion_id'} if action == 'origins' else set())
            if (set(query)-allowed_query or any(not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,6}', value)
                                               for key, value in query.items() if key in ('limit', 'offset'))):
                raise Problem(400, 'Nur eindeutige bekannte Listenfilter erwartet')
            limit, offset = int(query.get('limit', '50')), int(query.get('offset', '0'))
            if action == 'origins':
                portion_id = _hash_input(query.get('portion_id'))
                result = api.origins(actor, event_id, portion_id, limit, offset)
            else:
                result = getattr(api, action)(actor, event_id, limit, offset)
        return result, 200, 'application/json'
    if '_query' in data:
        raise Problem(400, 'Keine zusätzlichen Filter erlaubt')
    return getattr(api, action)(actor, event_id, data), (201 if action == 'confirm' else 200), 'application/json'
