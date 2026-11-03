"""Versioned documentary capacity after explicitly bound C1 refunds.

The immutable C1 and R1 journals retain their original meaning. This module
owns a whole invoice after its first atomic handoff and records exact segment
cents; it does not change Finance, cash, open items, or tax results.
"""
import json
import re
import sqlite3
import uuid

from accounting_component_segments import CentAmounts, ComponentSegment
from core import Problem, canonical
from business_operations import Domain, identifier, iso_date, transaction
from business_accounting_components import DocumentComponents, _cents, _money, _sha, _stored
from business_accounting_refunds import RefundOrigins

FEATURES = ('accounting_document_component_reuse',)
_TABLES = tuple('business_accounting_capacity_' + suffix for suffix in
                ('handoffs', 'segments', 'releases', 'entries', 'lines', 'requests'))
_ID = r'[a-f0-9]{32}'
_HASH = r'[a-f0-9]{64}'
_FLAGS = dict(scope='authorized_sources', tax_status='unconfigured', tax_result_available=False)
_MONEY = ('amount', 'net', 'tax', 'gross_before', 'gross_after', 'net_before', 'net_after',
          'tax_before', 'tax_after', 'remaining_gross', 'remaining_net', 'remaining_tax')


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BLOB', 'BYTEA'):
        raise ValueError('Unsupported binary type')
    return [
        '''CREATE TABLE IF NOT EXISTS business_accounting_capacity_entries(
        id TEXT PRIMARY KEY, sequence INTEGER NOT NULL UNIQUE CHECK(sequence>0),
        event_id TEXT NOT NULL REFERENCES business_accounting_cash_events(id), revision INTEGER NOT NULL CHECK(revision>0),
        document_id TEXT NOT NULL REFERENCES business_documents(id), portion_id TEXT NOT NULL UNIQUE CHECK(length(portion_id)=64),
        source_hash TEXT NOT NULL CHECK(length(source_hash)=64), previous_state_hash TEXT NOT NULL CHECK(length(previous_state_hash)=64),
        entry_json TEXT NOT NULL, entry_sha256 TEXT NOT NULL CHECK(length(entry_sha256)=64), proof_json TEXT NOT NULL,
        access_segments_json TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL, UNIQUE(event_id,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_accounting_capacity_handoffs(
        document_id TEXT PRIMARY KEY REFERENCES business_documents(id), entry_id TEXT NOT NULL UNIQUE REFERENCES business_accounting_capacity_entries(id),
        handoff_json TEXT NOT NULL, handoff_sha256 TEXT NOT NULL CHECK(length(handoff_sha256)=64))''',
        '''CREATE TABLE IF NOT EXISTS business_accounting_capacity_segments(
        id TEXT PRIMARY KEY CHECK(length(id)=64), document_id TEXT NOT NULL REFERENCES business_documents(id),
        group_id TEXT NOT NULL CHECK(length(group_id)=64), revision INTEGER NOT NULL CHECK(revision>0),
        previous_id TEXT UNIQUE REFERENCES business_accounting_capacity_segments(id),
        entry_id TEXT NOT NULL REFERENCES business_accounting_capacity_entries(id),
        segment_json TEXT NOT NULL, segment_sha256 TEXT NOT NULL CHECK(length(segment_sha256)=64),
        UNIQUE(document_id,group_id,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_accounting_capacity_releases(
        refund_entry_id TEXT NOT NULL, origin_entry_id TEXT NOT NULL, group_id TEXT NOT NULL,
        segment_id TEXT NOT NULL REFERENCES business_accounting_capacity_segments(id),
        reference_json TEXT NOT NULL, reference_sha256 TEXT NOT NULL CHECK(length(reference_sha256)=64),
        PRIMARY KEY(refund_entry_id,origin_entry_id,group_id),
        FOREIGN KEY(refund_entry_id,origin_entry_id,group_id) REFERENCES business_accounting_refund_lines(entry_id,origin_entry_id,group_id))''',
        '''CREATE TABLE IF NOT EXISTS business_accounting_capacity_lines(
        entry_id TEXT NOT NULL REFERENCES business_accounting_capacity_entries(id), group_id TEXT NOT NULL CHECK(length(group_id)=64),
        segment_id TEXT NOT NULL REFERENCES business_accounting_capacity_segments(id),
        amount TEXT NOT NULL, net TEXT NOT NULL, tax TEXT NOT NULL,
        gross_before TEXT NOT NULL, gross_after TEXT NOT NULL, net_before TEXT NOT NULL, net_after TEXT NOT NULL,
        tax_before TEXT NOT NULL, tax_after TEXT NOT NULL, remaining_gross TEXT NOT NULL, remaining_net TEXT NOT NULL, remaining_tax TEXT NOT NULL,
        PRIMARY KEY(entry_id,group_id))''',
        '''CREATE TABLE IF NOT EXISTS business_accounting_capacity_requests(
        user_id TEXT NOT NULL REFERENCES users(id), request_id TEXT NOT NULL,
        event_id TEXT NOT NULL REFERENCES business_accounting_cash_events(id), request_json TEXT NOT NULL,
        request_hash TEXT NOT NULL CHECK(length(request_hash)=64),
        entry_id TEXT NOT NULL UNIQUE REFERENCES business_accounting_capacity_entries(id), PRIMARY KEY(user_id,request_id))''',
        'CREATE INDEX IF NOT EXISTS business_accounting_capacity_groups ON business_accounting_capacity_lines(segment_id,entry_id)',
    ]


def protected_tables():
    return _TABLES


def runtime_privileges():
    return {table: ('SELECT', 'INSERT') for table in _TABLES}


def guard_statements(dialect):
    if dialect == 'sqlite':
        guards = [f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} ON {table} "
                  "BEGIN SELECT RAISE(ABORT,'immutable documentary capacity'); END"
                  for table in _TABLES for action in ('UPDATE', 'DELETE')]
        conflicts = ('document_id=NEW.document_id OR entry_id=NEW.entry_id',
                     'id=NEW.id OR previous_id=NEW.previous_id OR (document_id=NEW.document_id AND group_id=NEW.group_id AND revision=NEW.revision)',
                     'refund_entry_id=NEW.refund_entry_id AND origin_entry_id=NEW.origin_entry_id AND group_id=NEW.group_id',
                     'id=NEW.id OR sequence=NEW.sequence OR portion_id=NEW.portion_id OR (event_id=NEW.event_id AND revision=NEW.revision)',
                     'entry_id=NEW.entry_id AND group_id=NEW.group_id',
                     '(user_id=NEW.user_id AND request_id=NEW.request_id) OR entry_id=NEW.entry_id')
        for table, conflict in zip(_TABLES, conflicts):
            guards.append(f'CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} '
                          f'WHEN EXISTS(SELECT 1 FROM {table} WHERE {conflict}) '
                          "BEGIN SELECT RAISE(ABORT,'immutable documentary capacity'); END")
        return guards
    if dialect != 'postgresql':
        raise ValueError('Unsupported guard dialect')
    guards = ["""CREATE OR REPLACE FUNCTION business_accounting_capacity_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'immutable documentary capacity'; END; $$"""]
    for table in _TABLES:
        for action in ('UPDATE', 'DELETE'):
            name = table + '_' + action.lower() + '_guard'
            guards.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) "
                          f"THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION "
                          "business_accounting_capacity_immutable_guard(); END IF; END $$")
    return guards


def installed(office):
    from business_schema import _tables
    from business_accounting_refunds import installed as refunds_installed
    tables = _tables(office); present = set(_TABLES) & tables
    marker = ('business_schema_migrations' in tables and office.db.execute(
        "SELECT 1 FROM business_schema_migrations WHERE module='business_accounting_capacity'").fetchone())
    if not present and not marker:
        return False
    if present != set(_TABLES) or not marker or not refunds_installed(office):
        raise Problem(409, 'Wiederverwendbare Belegkapazität oder ihre Abhängigkeiten sind unvollständig installiert')
    return True


def require_legacy_writer(office, document_id):
    """A permanent ownership boundary, independent of feature enablement."""
    if document_id and installed(office) and office.db.execute(
            'SELECT 1 FROM business_accounting_capacity_handoffs WHERE document_id=?', (document_id,)).fetchone():
        raise Problem(409, 'Beleg wurde in die aktuelle Kapazitätsverwaltung übernommen; erneut prüfen')


def _amounts(value, gross='gross'):
    return CentAmounts(_cents(value['net']), _cents(value['tax']), _cents(value[gross]))


def _dto(value):
    return dict(net=_money(value.net), tax=_money(value.tax), gross=_money(value.gross))


def _sum(values):
    values = list(values)
    return CentAmounts(*(sum(getattr(value, key) for value in values) for key in ('net', 'tax', 'gross')))


def _difference(left, right):
    return CentAmounts(left.net-right.net, left.tax-right.tax, left.gross-right.gross)


def _release_key(value):
    return value.get('refund_version', 'r1'), value['refund_entry_id'], value.get('origin_version', 'c1'), value['origin_entry_id'], value['group_id']


def _header(row):
    return {key: row[key] for key in ('id', 'sequence', 'revision', 'entry_sha256')}


def _hash_input(value):
    if not isinstance(value, str) or not re.fullmatch(_HASH, value):
        raise Problem(400, 'SHA-256-Prüfsumme erwartet')
    return value


class ReusableDocumentComponents(Domain):
    """Whole positive source portions using one globally ordered capacity ledger."""

    def _gate(self):
        from business_accounting import Accounting
        Accounting(self.office)._write_gate()

    def _authorize_segments(self, actor, segment_ids, write=False):
        from business_accounting_refunds_v2 import installed as versioned_installed
        if versioned_installed(self.office):
            from accounting_joint_access import authorize_sources
            authorize_sources(self.office, actor, write=write, segments=segment_ids)
            return
        pending = set(segment_ids); seen = set(); events = set()
        while pending:
            segment_id = pending.pop()
            if segment_id in seen:
                continue
            seen.add(segment_id)
            row = self.office.db.execute('SELECT previous_id FROM business_accounting_capacity_segments WHERE id=?', (segment_id,)).fetchone()
            if not row:
                raise Problem(409, 'Gespeicherter Kapazitätsabschnitt fehlt')
            if row['previous_id']:
                pending.add(row['previous_id'])
            rows = self.office.db.execute('SELECT DISTINCT e.event_id FROM business_accounting_capacity_releases r '
                'JOIN business_accounting_refund_entries e ON e.id=r.refund_entry_id WHERE r.segment_id=?', (segment_id,)).fetchall()
            events.update(row['event_id'] for row in rows)
        refunds = RefundOrigins(self.office)
        for event_id in sorted(events):
            refunds._access(actor, event_id, write)

    def _access(self, actor, event_id, write=False):
        fresh = DocumentComponents(self.office)._access(actor, event_id, write)
        if not installed(self.office):
            raise Problem(409, 'Wiederverwendbare Belegkapazität ist nicht installiert')
        from business_accounting_refunds_v2 import installed as versioned_installed
        if versioned_installed(self.office):
            from accounting_joint_access import authorize_sources
            return authorize_sources(self.office, fresh, event_id, write=write)
        rows = self.office.db.execute('SELECT access_segments_json FROM business_accounting_capacity_entries WHERE event_id=?', (event_id,)).fetchall()
        segments = set()
        for row in rows:
            segments.update(self._access_ids(row['access_segments_json']))
        self._authorize_segments(fresh, segments, write)
        return fresh

    @staticmethod
    @_stored
    def _access_ids(encoded):
        values = json.loads(encoded)
        if (not isinstance(values, list) or values != sorted(set(values)) or canonical(values) != encoded
                or any(not isinstance(value, str) or not re.fullmatch(_HASH, value) for value in values)):
            raise ValueError('Invalid historical capacity authorization binding')
        return values

    @staticmethod
    def _access_segments(proof):
        return sorted({value['segment_id'] for value in proof['prior_segments']} | {value['id'] for value in proof['new_segments']})

    def _writes_allowed(self, actor, event_id):
        try:
            self._access(actor, event_id, True); self._gate()
            return True
        except Problem as error:
            if error.status not in (403, 404, 409, 423):
                raise
            return False

    @_stored
    def _sources(self, cache):
        if 'capacity_sources' in cache:
            return cache['capacity_sources']
        components = DocumentComponents(self.office); refunds = RefundOrigins(self.office)
        r1 = refunds._ledger(cache)
        legacy = {}; contexts = {}; entries = {}; legacy_portions = set(); legacy_rows = []
        for row in self.office.db.execute('SELECT * FROM business_accounting_component_entries ORDER BY sequence,id').fetchall():
            legacy_rows.append(dict(row))
            event_id = row['event_id']
            if event_id not in contexts:
                context = components._source(None, event_id)
                values, unused = components._history(context)
                contexts[event_id] = context
                entries.update((value['id'], value) for value in values)
            value = entries[row['id']]; legacy_portions.add(row['portion_id'])
            if contexts[event_id]['kind'] != 'customer_receipt':
                continue
            document_id = value['portion']['document_id']
            for line in self.office.db.execute('SELECT * FROM business_accounting_component_lines WHERE entry_id=? ORDER BY group_id', (row['id'],)).fetchall():
                reference = dict(entry_id=row['id'], group_id=line['group_id'], sequence=row['sequence'],
                    entry_sha256=row['entry_sha256'], proof_sha256=_sha(row['proof_json']), line_sha256=_sha(canonical(dict(line))),
                    net=line['net'], tax=line['tax'], amount=line['amount'])
                legacy.setdefault(document_id, []).append(reference)
        if ([row['sequence'] for row in legacy_rows] != list(range(1, len(legacy_rows)+1))
                or len(legacy_rows) != self.office.db.execute('SELECT COUNT(*) FROM business_accounting_component_requests').fetchone()[0]
                or sum(len(value['lines']) for value in entries.values()) != self.office.db.execute('SELECT COUNT(*) FROM business_accounting_component_lines').fetchone()[0]
                or any(sum(_cents(value['amount']) for value in entries.values() if value['event_id'] == event_id) > _cents(context['event']['amount'])
                       for event_id, context in contexts.items())):
            raise ValueError('Invalid complete legacy component history')
        returned = {}; refund_entries = {}
        for row in self.office.db.execute('SELECT * FROM business_accounting_refund_entries ORDER BY sequence,id').fetchall():
            value = next(value for value in r1['by_event'][row['event_id']] if value['id'] == row['id'])
            refund_entries[row['id']] = dict(row)
            for actual in self.office.db.execute('SELECT * FROM business_accounting_refund_lines WHERE entry_id=? ORDER BY origin_entry_id,group_id', (row['id'],)).fetchall():
                lot = refunds._lot(actual['origin_entry_id'], actual['group_id'], cache)
                reference = dict(refund_entry_id=row['id'], origin_entry_id=actual['origin_entry_id'], group_id=actual['group_id'],
                    refund_event_id=row['event_id'], origin_event_id=lot['value']['origin_event_id'], sequence=row['sequence'],
                    entry_sha256=row['entry_sha256'], proof_sha256=_sha(row['proof_json']), line_sha256=_sha(canonical(dict(actual))),
                    cash_date=value['cash_date'], net=actual['net'], tax=actual['tax'], amount=actual['amount'])
                returned.setdefault(lot['value']['document_id'], []).append(reference)
        result = dict(legacy=legacy, legacy_portions=legacy_portions, returns=returned, refund_entries=refund_entries,
                      r1_sequence=len(refund_entries), legacy_entries=entries, legacy_rows=legacy_rows,
                      c1_sequence=max((row['sequence'] for row in legacy_rows), default=0))
        cache['capacity_sources'] = result
        return result

    def _finance_gate(self, document_id, sources):
        from business_accounting import Accounting
        rows = self.office.db.execute('SELECT a.* FROM business_payment_allocations a JOIN business_payments p ON p.id=a.payment_id '
            "WHERE a.document_id=? AND p.kind='refund' ORDER BY a.id", (document_id,)).fetchall()
        observations = []
        for row in rows:
            source, unused = Accounting(self.office)._payment_source(None, row['payment_id'])
            link = self.office.db.execute("SELECT event_id FROM business_accounting_source_links WHERE kind='payment' AND source_id=?", (row['payment_id'],)).fetchone()
            matches = [('r1', value) for value in sources['refund_entries'].values() if value['refund_allocation_id'] == row['id']]
            matches += [('r2', value) for value in sources.get('refunds_v2_entries', {}).values() if value['refund_allocation_id'] == row['id']]
            if len(matches) > 1:
                raise ValueError('Refund allocation was bound in two versions')
            version, entry = matches[0] if matches else (None, None)
            if link:
                Accounting(self.office)._event(None, link['event_id'])
            observed = dict(allocation=dict(row), source_hash=source['source_hash'],
                event_id=link['event_id'] if link else None, refund_entry_id=entry['id'] if entry else None,
                refund_entry_sha256=entry['entry_sha256'] if entry else None)
            if 'r2_sequence' in sources:
                observed['refund_version'] = version
            observations.append(observed)
        return dict(refunds=observations, complete=all(value['event_id'] and value['refund_entry_id'] for value in observations))

    @_stored
    def _validate_gate_snapshot(self, document_id, gate, sources, *, r1_sequence=None):
        """Validate each observed immutable fact; do not infer eternal absence."""
        from business_accounting import Accounting
        if (not isinstance(gate, dict) or set(gate) != {'refunds', 'complete'} or type(gate['complete']) is not bool
                or not isinstance(gate['refunds'], list)):
            raise ValueError('Invalid refund gate observation')
        identities = []
        for value in gate['refunds']:
            if set(value) != {'allocation', 'source_hash', 'event_id', 'refund_entry_id', 'refund_entry_sha256'} | ({'refund_version'} if 'r2_sequence' in sources else set()):
                raise ValueError('Invalid refund gate member')
            allocation = value['allocation']; identities.append(allocation['id'])
            actual = self.office.db.execute('SELECT * FROM business_payment_allocations WHERE id=?', (allocation['id'],)).fetchone()
            if not actual or dict(actual) != allocation or allocation['document_id'] != document_id:
                raise ValueError('Changed observed refund allocation')
            source, unused = Accounting(self.office)._payment_source(None, allocation['payment_id'])
            if source['kind'] != 'refund' or source['source_hash'] != value['source_hash']:
                raise ValueError('Changed observed refund payment')
            if value['event_id']:
                event = Accounting(self.office)._event(None, value['event_id'])
                if event['source']['id'] != allocation['payment_id'] or event['source']['source_hash'] != value['source_hash']:
                    raise ValueError('Changed observed refund import')
            if value['refund_entry_id']:
                version = value.get('refund_version', 'r1')
                if version not in ('r1', 'r2'):
                    raise ValueError('Unknown observed refund version')
                entry = sources['refund_entries' if version == 'r1' else 'refunds_v2_entries'][value['refund_entry_id']]
                observed_head = (sources['r1_sequence'] if r1_sequence is None else r1_sequence) if version == 'r1' else sources['r2_sequence']
                if entry['sequence'] > observed_head:
                    raise ValueError('Observed refund binding lies beyond the recorded prefix')
                if (not value['event_id'] or entry['event_id'] != value['event_id'] or entry['refund_allocation_id'] != allocation['id']
                        or entry['entry_sha256'] != value['refund_entry_sha256']):
                    raise ValueError('Changed observed refund binding')
            elif value['refund_entry_sha256'] is not None or value.get('refund_version') is not None:
                raise ValueError('Unexpected refund binding checksum')
        if identities != sorted(set(identities)) or gate['complete'] != all(value['event_id'] and value['refund_entry_id'] for value in gate['refunds']):
            raise ValueError('Invalid observed gate completeness')

    @staticmethod
    def _empty_ledger():
        return dict(by_event={}, headers={}, handoffs={}, active={}, segments={}, consumed={}, claims=set(), portions=set(), lines={}, entries_by_id={}, rows={})

    @staticmethod
    def _segment(document_id, basis, carry, returns, previous=None, *, version=1):
        state = ComponentSegment(carry)
        for returned in returns:
            state = state.reopen_with_return(canonical(_release_key(returned)), _amounts(returned, 'amount'))
        dates = ([previous['not_before_date']] if previous and carry.gross and previous['not_before_date'] else []) + [value['cash_date'] for value in returns]
        value = dict(document_id=document_id, group_id=basis['group_id'], revision=previous['revision']+1 if previous else 1,
            previous_id=previous['id'] if previous else None, basis=_dto(state.basis), carry=_dto(carry),
            returns=returns, not_before_date=max(dates) if dates else None)
        if version == 2:
            value['schema_version'] = 2
        return dict(value, id=_sha(canonical(value)))

    @staticmethod
    def _segment_state(segment, ledger):
        return ComponentSegment(_amounts(segment['basis']), ledger['consumed'].get(segment['id'], 0))

    @staticmethod
    def _line(segment, before, amount):
        state = ComponentSegment(_amounts(segment['basis']), before)
        allocation, following = state.consume(amount)
        old, new, remaining = state.consumed_amounts, following.consumed_amounts, following.remaining_amounts
        return dict(group_id=segment['group_id'], segment_id=segment['id'], amount=_money(amount), net=_money(allocation.net), tax=_money(allocation.tax),
            gross_before=_money(old.gross), gross_after=_money(new.gross), net_before=_money(old.net), net_after=_money(new.net),
            tax_before=_money(old.tax), tax_after=_money(new.tax), remaining_gross=_money(remaining.gross),
            remaining_net=_money(remaining.net), remaining_tax=_money(remaining.tax))

    @staticmethod
    def _state_hash(context, ledger, sources, c1_sequence=None, portions=None):
        c1_sequence = sources['c1_sequence'] if c1_sequence is None else c1_sequence
        portions = context['portions'] if portions is None else portions
        documents = sorted({value['document_id'] for value in portions if value['document_id']})
        heads = []
        for document_id in documents:
            handoff = ledger['handoffs'].get(document_id)
            heads.append(dict(document_id=document_id, handoff_sha256=_sha(canonical(handoff)) if handoff else None,
                segments=[dict(group_id=key[1], id=value['id'], consumed=ledger['consumed'].get(value['id'], 0))
                          for key, value in sorted(ledger['active'].items()) if key[0] == document_id]))
        return _sha(canonical(dict(schema_version=1, event_id=context['event']['id'], source_hash=context['event']['source']['source_hash'],
            portions=portions, legacy=[_header(row) for row in sources['legacy_rows'] if row['event_id'] == context['event']['id'] and row['sequence'] <= c1_sequence],
            entries=ledger['headers'].get(context['event']['id'], []), documents=heads)))

    def _plan(self, actor, context, raw, ledger, sources, *, historical=None, write=True):
        """Build a complete invoice proposal; historical mode fixes observations."""
        components = DocumentComponents(self.office)
        metadata, bases, archive = components._basis(context, raw)
        document_id = raw['document_id']
        document = self.office.db.execute('SELECT customer_id FROM business_documents WHERE id=?', (document_id,)).fetchone()
        if not document:
            raise Problem(409, 'Rechnungsquelle fehlt')
        handoff = ledger['handoffs'].get(document_id)
        legacy = sources['legacy'].get(document_id, [])
        version = historical['schema_version'] if historical is not None else 2 if 'r2_sequence' in sources else 1
        if type(version) is not int or version not in (1, 2) or (version == 2) != ('r2_sequence' in sources):
            raise ValueError('Invalid capacity proof version or source space')
        r2_sequence = sources.get('r2_sequence', 0)
        if historical is None:
            reason, eligibility = components._eligibility(context, raw)
            r1_sequence = sources['r1_sequence']; c1_sequence = sources['c1_sequence']
            gate = self._finance_gate(document_id, sources)
            authorized = set()
            # Only relational identifiers precede fresh full source authorization.
            events = set()
            for table in ('business_accounting_refund_entries',)+(('business_accounting_refunds_v2_entries',) if version == 2 else ()):
                events.update(row['event_id'] for row in self.office.db.execute('SELECT e.event_id FROM '+table+' e '
                    'JOIN business_payment_allocations a ON a.id=e.refund_allocation_id WHERE a.document_id=?', (document_id,)).fetchall())
            for event_id in sorted(events):
                try:
                    RefundOrigins(self.office)._access(actor, event_id, write)
                except Problem as error:
                    if error.status not in (403, 404):
                        raise
                else:
                    authorized.add(event_id)
            active = [value['id'] for key, value in ledger['active'].items() if key[0] == document_id]
            self._authorize_segments(actor, active, write)
        else:
            r1_sequence, c1_sequence = historical['r1_sequence'], historical['c1_sequence']
            gate, eligibility = historical['gate'], historical['eligibility']
            if (type(r1_sequence) is not int or not 0 <= r1_sequence <= sources['r1_sequence']
                    or type(c1_sequence) is not int or not 0 <= c1_sequence <= sources['c1_sequence']
                    or version == 2 and (type(historical.get('r2_sequence')) is not int or historical['r2_sequence'] != r2_sequence)
                    or eligibility != {'relations': []}):
                raise ValueError('Invalid historical capacity observation')
            self._validate_gate_snapshot(document_id, gate, sources, r1_sequence=r1_sequence)
            authorized = set(historical['authorized_returns'])
            if (not isinstance(historical['authorized_returns'], list)
                    or historical['authorized_returns'] != sorted(authorized)):
                raise ValueError('Invalid historical return authorization decision')
            reason = context['reason']
        # A handoff freezes this invoice's complete C1 line population forever.
        if handoff and legacy != handoff['legacy']:
            raise ValueError('A handed-off invoice has new or changed legacy components')
        legacy_before = [value for value in legacy if value['sequence'] <= c1_sequence]
        if not handoff and historical is not None and legacy_before != legacy:
            raise ValueError('Legacy invoice changed after its handoff')
        pending = [value for value in sources['returns'].get(document_id, [])
                   if value['sequence'] <= (r2_sequence if value.get('refund_version') == 'r2' else r1_sequence) and _release_key(value) not in ledger['claims']]
        if any(value['refund_event_id'] not in {item['event_id'] for item in gate['refunds'] if item['refund_entry_id']}
               for value in pending if gate['complete']):
            raise ValueError('Observed complete gate omits a contributing return')
        date = context['event']['cash_date']; iso_date(date)
        pending_reason = None
        if not gate['complete']:
            pending_reason = 'refund_origin_unresolved'
        elif any(value['refund_event_id'] not in authorized for value in pending):
            pending_reason = 'source_access_required'
        elif not handoff and pending and max(value['cash_date'] for value in pending) > date:
            pending_reason = 'receipt_before_capacity'
        takeover = not handoff and bool(pending) and pending_reason is None and reason is None
        groups = []; segments = []; active_refs = []
        for basis in bases:
            group_id = basis['group_id']; old = ledger['active'].get((document_id, group_id))
            old_state = self._segment_state(old, ledger) if old else None
            carry = old_state.remaining_amounts if old else _difference(_amounts(basis), _sum(
                _amounts(value, 'amount') for value in legacy_before if value['group_id'] == group_id))
            returns = [value for value in pending if value['group_id'] == group_id]
            returned = _sum(_amounts(value, 'amount') for value in returns)
            current = dict(segment_id=old['id'] if old else None, **_dto(carry), not_before_date=old['not_before_date'] if old else None)
            pending_date = max((value['cash_date'] for value in returns), default=None)
            transition = 'none'; segment = old
            release_allowed = gate['complete'] and all(value['refund_event_id'] in authorized for value in returns)
            if takeover:
                transition = 'takeover'; segment = self._segment(document_id, basis, carry, returns, version=version)
            elif handoff and returns and release_allowed:
                candidate = self._segment(document_id, basis, carry, returns, old, version=version)
                if not candidate['not_before_date'] or candidate['not_before_date'] <= date:
                    transition = 'successor'; segment = candidate
                elif pending_reason is None:
                    pending_reason = 'receipt_before_capacity'
            if transition != 'none':
                segments.append(segment)
            offered = (dict(segment_id=segment['id'], **segment['basis'], not_before_date=segment['not_before_date'])
                       if transition != 'none' else current)
            if old:
                active_refs.append(dict(group_id=group_id, segment_id=old['id'], segment_sha256=_sha(canonical(old)),
                                        consumed_gross=ledger['consumed'].get(old['id'], 0)))
            detail = dict(group_id=group_id, rate=basis['rate'], category=basis['category'], reason=basis['reason'],
                archive=_dto(_amounts(basis)), current_capacity=current,
                pending_returns=dict(**_dto(returned), not_before_date=pending_date), offered_capacity=offered, transition=transition)
            detail['group_state_hash'] = _sha(canonical(dict(group=detail, legacy=[value for value in legacy_before if value['group_id'] == group_id],
                returns=returns, active=active_refs[-1] if old else None)))
            if _cents(basis['gross']) or carry.gross or returned.gross:
                groups.append(detail)
        available = sum(_cents(group['offered_capacity']['gross']) for group in groups
                        if not group['offered_capacity']['not_before_date'] or group['offered_capacity']['not_before_date'] <= date)
        action = 'takeover_and_document' if takeover else 'document_current' if handoff else 'document_legacy'
        writer = 'c2' if handoff or takeover else 'c1'
        blocked = reason
        if blocked is None and _cents(raw['amount']) > available:
            too_early = any(group['offered_capacity']['not_before_date'] and group['offered_capacity']['not_before_date'] > date for group in groups)
            blocked = pending_reason or ('receipt_before_capacity' if too_early else 'group_capacity_exceeded')
        if blocked:
            action = None
        proof = dict(schema_version=version, source=dict(event_sha256=_sha(canonical(context['event'])), portion=raw),
            portions_before=context['portions'] if historical is None else historical['portions_before'],
            basis=bases, archive=archive, eligibility=eligibility, c1_sequence=c1_sequence, r1_sequence=r1_sequence,
            legacy=legacy_before, prior_segments=active_refs, gate=gate,
            authorized_returns=sorted(authorized), new_segments=segments)
        if version == 2:
            proof['r2_sequence'] = r2_sequence
        portion = dict(portion_id=raw['portion_id'], kind=raw['kind'], event_id=context['event']['id'],
            document_id=document_id, customer_id=document['customer_id'], project_id=metadata['project_id'], number=metadata['number'],
            party_name=metadata['party_name'], amount=raw['amount'], currency='EUR', payload_sha256=metadata['payload_sha256'], pdf_sha256=metadata['pdf_sha256'],
            ownership_id=document_id if handoff else None, writer=writer, action=action,
            refund_status=None if reason else 'clear' if gate['complete'] else 'unresolved', pending_blocked_reason=pending_reason,
            eligible=blocked is None, blocked_reason=blocked, groups=groups)
        portion['portion_state_hash'] = _sha(canonical(dict(proof=proof, portion=portion)))
        return portion, proof

    @staticmethod
    def _inputs(data, confirm=False):
        if not isinstance(data, dict) or data.get('action') not in ('takeover_and_document', 'document_current'):
            raise Problem(400, 'Ausdrückliche aktuelle Kapazitätsaktion erwartet')
        DocumentComponents._inputs({key: value for key, value in data.items() if key != 'action'}, confirm)

    @staticmethod
    def _request_hash(event_id, data):
        return _sha(canonical(['capacity.confirm', event_id, data]))

    @staticmethod
    def _preview_from_entry(value):
        preview = {key: item for key, item in value.items() if key not in ('id', 'sequence', 'revision', 'previous_state_hash', 'created_by', 'created_at', 'preview_hash')}
        return dict(preview, expected_revision=value['revision']-1, state_hash=value['previous_state_hash'])

    @staticmethod
    def _changes(proof):
        return [dict(group_id=value['group_id'], previous_segment_id=value['previous_id'], segment_id=value['id'],
            carry=value['carry'], returned=_dto(_sum(_amounts(item, 'amount') for item in value['returns'])),
            basis=value['basis'], not_before_date=value['not_before_date']) for value in proof['new_segments']]

    @_stored
    def _basic(self, row):
        value = json.loads(row['entry_json']); proof = json.loads(row['proof_json'])
        expected = {'id', 'sequence', 'revision', 'previous_state_hash', 'created_by', 'created_at', 'event_id', 'source_hash',
                    'action', 'portion', 'amount', 'net', 'tax', 'lines', 'capacity_changes', 'reason', 'preview_hash'} | set(_FLAGS)
        if (set(value) != expected or any(value[key] != wanted for key, wanted in _FLAGS.items())
                or value['tax_result_available'] is not False or canonical(value) != row['entry_json'] or canonical(proof) != row['proof_json']
                or _sha(row['entry_json']) != row['entry_sha256']
                or any(value[key] != row[key] for key in ('id', 'sequence', 'revision', 'event_id', 'source_hash', 'previous_state_hash', 'created_by', 'created_at'))
                or type(row['sequence']) is not int or row['sequence'] < 1 or type(row['revision']) is not int or row['revision'] < 1
                or type(value['sequence']) is not int or type(value['revision']) is not int
                or value['portion']['portion_id'] != row['portion_id'] or value['portion']['document_id'] != row['document_id']
                or not isinstance(value['lines'], list) or not 1 <= len(value['lines']) <= 500
                or [line['group_id'] for line in value['lines']] != sorted({line['group_id'] for line in value['lines']})):
            raise ValueError('Invalid capacity entry')
        if self._access_ids(row['access_segments_json']) != self._access_segments(proof):
            raise ValueError('Changed historical capacity authorization binding')
        for key in ('id', 'event_id', 'document_id', 'created_by'):
            identifier(row[key])
        if (sum(_cents(line['amount'], positive=True) for line in value['lines']) != _cents(value['amount'], positive=True, input_value=True)
                or sum(_cents(line['net']) for line in value['lines']) != _cents(value['net'])
                or sum(_cents(line['tax']) for line in value['lines']) != _cents(value['tax'])
                or _cents(value['net'])+_cents(value['tax']) != _cents(value['amount'])):
            raise ValueError('Invalid capacity totals')
        actual = self.office.db.execute('SELECT * FROM business_accounting_capacity_lines WHERE entry_id=? ORDER BY group_id', (row['id'],)).fetchall()
        if len(actual) != len(value['lines']) or any(line != {key: item for key, item in dict(stored).items() if key != 'entry_id'}
                                                  for line, stored in zip(value['lines'], actual)):
            raise ValueError('Changed capacity lines')
        request = self.office.db.execute('SELECT * FROM business_accounting_capacity_requests WHERE entry_id=?', (row['id'],)).fetchone()
        if not request:
            raise ValueError('Missing capacity request')
        body = json.loads(request['request_json']); self._inputs(body, True)
        if (request['event_id'] != row['event_id'] or request['user_id'] != row['created_by'] or request['request_id'] != body['request_id']
                or canonical(body) != request['request_json'] or request['request_hash'] != self._request_hash(row['event_id'], body)
                or body['expected_revision'] != row['revision']-1 or body['state_hash'] != row['previous_state_hash']
                or any(body[key] != value[key] for key in ('source_hash', 'preview_hash', 'reason', 'action'))
                or body['portion_id'] != row['portion_id'] or body['portion_state_hash'] != value['portion']['portion_state_hash']
                or sorted(body['groups'], key=lambda group: group['group_id']) != [{key: line[key] for key in ('group_id', 'amount')} for line in value['lines']]
                or _sha(canonical(self._preview_from_entry(value))) != value['preview_hash']):
            raise ValueError('Changed capacity request or preview')
        return value, proof

    @_stored
    def _historical_source(self, row, proof):
        context = DocumentComponents(self.office)._source(None, row['event_id'])
        if context['kind'] != 'customer_receipt':
            raise ValueError('Capacity entry requires a customer receipt')
        raw = next((value for value in context['portions'] if value['portion_id'] == row['portion_id']), None)
        if (not raw or raw['document_id'] != row['document_id'] or proof['source'] != dict(event_sha256=_sha(canonical(context['event'])), portion=raw)
                or context['event']['source']['source_hash'] != row['source_hash']):
            raise ValueError('Changed capacity source')
        previous = proof['portions_before']; available = {value['portion_id']: value for value in context['portions']}
        if (not isinstance(previous, list) or [value['portion_id'] for value in previous] != sorted({value['portion_id'] for value in previous})
                or any(available.get(value['portion_id']) != value for value in previous) or raw not in previous):
            raise ValueError('Changed historical source membership')
        fixed = [value for value in context['portions'] if value['kind'] != 'additional_allocation']
        revisions = sorted(value['reference']['revision'] for value in previous if value['kind'] == 'additional_allocation')
        if any(value not in previous for value in fixed) or revisions != list(range(1, len(revisions)+1)):
            raise ValueError('Incomplete historical source membership')
        return context, raw

    @staticmethod
    def _handoff(value, proof):
        return dict(document_id=value['portion']['document_id'], entry_id=value['id'], archive=proof['archive'], legacy=proof['legacy'],
                    c1_sequence=proof['c1_sequence'], created_by=value['created_by'], created_at=value['created_at'])

    def _entry_lines(self, context, portion, proof, selections, ledger):
        offered = {group['group_id']: group for group in portion['groups']}
        new = {value['group_id']: value for value in proof['new_segments']}; lines = []
        if sum(_cents(value['amount']) for value in selections) != _cents(portion['amount']):
            raise Problem(400, 'Gruppenbeträge müssen den ganzen unveränderlichen Quellenanteil ergeben')
        for selection in sorted(selections, key=lambda value: value['group_id']):
            group_id = selection['group_id']; group = offered.get(group_id)
            if not group:
                raise Problem(409, 'Gruppe gehört nicht zu den verteilbaren Beleggruppen')
            capacity = group['offered_capacity']; amount = _cents(selection['amount'], positive=True)
            if (amount > _cents(capacity['gross']) or capacity['not_before_date'] and capacity['not_before_date'] > context['event']['cash_date']):
                raise Problem(409, 'Gruppenrest oder Erstattungsdatum erlaubt diesen Betrag nicht')
            segment = new.get(group_id) or ledger['active'].get((portion['document_id'], group_id))
            if not segment:
                raise Problem(409, 'Aktueller Kapazitätsschreiber erforderlich')
            lines.append(self._line(segment, ledger['consumed'].get(segment['id'], 0), amount))
        return lines

    def _apply(self, row, value, proof, ledger, *, validate_rows):
        document_id = value['portion']['document_id']
        if value['action'] == 'takeover_and_document':
            if document_id in ledger['handoffs'] or not any(segment['returns'] for segment in proof['new_segments']):
                raise ValueError('Invalid first invoice handoff')
            handoff = self._handoff(value, proof)
            if validate_rows:
                actual = self.office.db.execute('SELECT * FROM business_accounting_capacity_handoffs WHERE document_id=?', (document_id,)).fetchone()
                if (not actual or actual['entry_id'] != value['id'] or actual['handoff_json'] != canonical(handoff)
                        or actual['handoff_sha256'] != _sha(canonical(handoff))):
                    raise ValueError('Changed invoice handoff')
            ledger['handoffs'][document_id] = handoff
        elif document_id not in ledger['handoffs']:
            raise ValueError('Missing invoice handoff')
        if validate_rows:
            actual_segments = self.office.db.execute('SELECT * FROM business_accounting_capacity_segments WHERE entry_id=? ORDER BY group_id', (value['id'],)).fetchall()
            if len(actual_segments) != len(proof['new_segments']):
                raise ValueError('Orphan or missing capacity segment')
        for index, segment in enumerate(proof['new_segments']):
            group_id = segment['group_id']; key = (document_id, group_id); old = ledger['active'].get(key)
            if segment['id'] in ledger['segments'] or segment['previous_id'] != (old['id'] if old else None):
                raise ValueError('Capacity segment branched or repeated')
            if validate_rows:
                actual = actual_segments[index]
                if (any(actual[field] != segment[field] for field in ('id', 'document_id', 'group_id', 'revision', 'previous_id'))
                        or actual['segment_json'] != canonical(segment) or actual['segment_sha256'] != _sha(canonical(segment))):
                    raise ValueError('Changed capacity segment')
                releases = [dict(actual) for actual in self.office.db.execute('SELECT * FROM business_accounting_capacity_releases WHERE segment_id=?', (segment['id'],)).fetchall()]
                if proof['schema_version'] == 2:
                    releases += [dict(actual, refund_version='r2') for actual in self.office.db.execute(
                        'SELECT * FROM business_accounting_refunds_v2_releases WHERE segment_id=?', (segment['id'],)).fetchall()]
                by_key = {_release_key(actual): actual for actual in releases}
                if len(by_key) != len(segment['returns']):
                    raise ValueError('Missing or orphan capacity release')
            for reference in segment['returns']:
                release_key = _release_key(reference)
                if release_key in ledger['claims']:
                    raise ValueError('Refund line released twice')
                if validate_rows:
                    actual = by_key[release_key]
                    if actual['reference_json'] != canonical(reference) or actual['reference_sha256'] != _sha(canonical(reference)):
                        raise ValueError('Changed capacity release')
                ledger['claims'].add(release_key)
            ledger['segments'][segment['id']] = segment; ledger['active'][key] = segment
        for line in value['lines']:
            segment = ledger['active'].get((document_id, line['group_id']))
            if not segment or segment['id'] != line['segment_id']:
                raise ValueError('Capacity line uses an inactive or foreign segment')
            ledger['consumed'][segment['id']] = ledger['consumed'].get(segment['id'], 0)+_cents(line['amount'])
            ledger['lines'].setdefault(segment['id'], []).append(dict(entry_id=value['id'], entry_sha256=row['entry_sha256'], line=line))
        ledger['portions'].add(value['portion']['portion_id'])
        ledger['by_event'].setdefault(value['event_id'], []).append(value)
        ledger['headers'].setdefault(value['event_id'], []).append(_header(row))
        ledger['entries_by_id'][value['id']] = value
        ledger['rows'][value['id']] = dict(row)

    def _ledger(self, cache):
        from business_accounting_refunds_v2 import installed as versioned_installed
        if versioned_installed(self.office):
            from accounting_joint_ledger import read_joint_ledger
            return read_joint_ledger(self.office, cache)['capacity']
        return self._legacy_ledger(cache)

    @_stored
    def _legacy_ledger(self, cache):
        if 'capacity_ledger' in cache:
            return cache['capacity_ledger']
        sources = self._sources(cache); ledger = self._empty_ledger(); line_count = 0
        for sequence, row in enumerate(self.office.db.execute('SELECT * FROM business_accounting_capacity_entries ORDER BY sequence,id').fetchall(), 1):
            value, proof = self._basic(row)
            if (type(proof.get('schema_version')) is not int or proof['schema_version'] != 1 or row['sequence'] != sequence
                    or row['revision'] != len(ledger['by_event'].get(row['event_id'], []))+1
                    or row['portion_id'] in ledger['portions'] or row['portion_id'] in sources['legacy_portions']):
                raise ValueError('Invalid capacity order or duplicated whole portion')
            context, raw = self._historical_source(row, proof)
            portion, expected_proof = self._plan(None, context, raw, ledger, sources, historical=proof)
            if (proof != expected_proof or portion != value['portion'] or not portion['eligible'] or portion['action'] != value['action']
                    or value['amount'] != raw['amount'] or value['action'] not in ('takeover_and_document', 'document_current')
                    or row['previous_state_hash'] != self._state_hash(context, ledger, sources, proof['c1_sequence'], proof['portions_before'])
                    or self._entry_lines(context, portion, proof, value['lines'], ledger) != value['lines']
                    or self._changes(proof) != value['capacity_changes']):
                raise ValueError('Changed historical capacity source, state or cumulative cents')
            self._apply(row, value, proof, ledger, validate_rows=True); line_count += len(value['lines'])
        counts = dict(handoffs=len(ledger['handoffs']), segments=len(ledger['segments']), releases=len(ledger['claims']),
                      entries=sum(map(len, ledger['by_event'].values())), lines=line_count,
                      requests=sum(map(len, ledger['by_event'].values())))
        for suffix, count in counts.items():
            if self.office.db.execute('SELECT COUNT(*) FROM business_accounting_capacity_'+suffix).fetchone()[0] != count:
                raise ValueError('Orphan capacity ledger row')
        cache['capacity_ledger'] = ledger
        return ledger

    def _blocked_portion(self, context, raw, ledger):
        metadata, unused, unused_archive = DocumentComponents(self.office)._basis(context, raw)
        document = self.office.db.execute('SELECT customer_id FROM business_documents WHERE id=?', (raw['document_id'],)).fetchone()
        owned = raw['document_id'] in ledger['handoffs']
        value = dict(portion_id=raw['portion_id'], kind=raw['kind'], event_id=context['event']['id'], document_id=raw['document_id'],
            customer_id=document['customer_id'], project_id=metadata['project_id'], number=metadata['number'], party_name=metadata['party_name'],
            amount=raw['amount'], currency='EUR', payload_sha256=metadata['payload_sha256'], pdf_sha256=metadata['pdf_sha256'],
            ownership_id=raw['document_id'] if owned else None, writer='c2' if owned else 'c1', action=None,
            refund_status=None, pending_blocked_reason='source_access_required', eligible=False, blocked_reason='source_access_required', groups=[])
        value['portion_state_hash'] = _sha(canonical(value))
        return value

    def _view(self, actor, event_id, cache, *, write=False):
        context = DocumentComponents(self.office)._source(None, event_id)
        ledger = self._ledger(cache); sources = cache.get('capacity_joint_sources') or self._sources(cache)
        own = ledger['by_event'].get(event_id, [])
        legacy = [value for value in sources['legacy_entries'].values() if value['event_id'] == event_id]
        documented = sum(_cents(value['amount']) for value in own+legacy)
        if documented > _cents(context['event']['amount']):
            raise Problem(409, 'Dokumentierte Anteile überschreiten den Geldfluss')
        portions = []
        if context['kind'] == 'customer_receipt':
            for raw in context['portions']:
                if raw['portion_id'] in ledger['portions'] or raw['portion_id'] in sources['legacy_portions']:
                    continue
                try:
                    portion, unused = self._plan(actor, context, raw, ledger, sources, write=write)
                except Problem as error:
                    if error.status not in (403, 404):
                        raise
                    portion = self._blocked_portion(context, raw, ledger)
                portions.append(portion)
        eligible = any(value['eligible'] for value in portions)
        reason = (None if eligible else 'not_customer_receipt' if context['kind'] != 'customer_receipt' else context['reason'] or
                  (portions[0]['blocked_reason'] if portions else 'unallocated' if _cents(context['unallocated']) else 'fully_documented'))
        state = dict(event_id=event_id, source_hash=context['event']['source']['source_hash'], revision=len(own),
            state_hash=self._state_hash(context, ledger, sources), source_kind=context['kind'], amount=context['event']['amount'], currency='EUR',
            cash_date=context['event']['cash_date'], documented_amount=_money(documented),
            undocumented_amount=_money(_cents(context['event']['amount'])-documented), unallocated_amount=context['unallocated'],
            eligible=eligible, blocked_reason=reason, writes_allowed=self._writes_allowed(actor, event_id), **_FLAGS)
        return state, context, ledger, sources, portions

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
            return _paged(self._view(fresh, event_id, {}, write=True)[4], limit, offset)

    def history(self, actor, event_id, limit=50, offset=0):
        from business_accounting import _page, _paged
        identifier(event_id); _page(limit, offset)
        with transaction(self.office):
            self._access(actor, event_id)
            return _paged(list(reversed(self._ledger({})['by_event'].get(event_id, []))), limit, offset)

    def _prepare(self, actor, state, context, ledger, sources, data):
        if any(data[key] != state[target] for key, target in (('source_hash', 'source_hash'), ('expected_revision', 'revision'), ('state_hash', 'state_hash'))):
            raise Problem(409, 'Quellen- oder Kapazitätsstand geändert; neu laden')
        if context['kind'] != 'customer_receipt':
            raise Problem(409, 'Gültiger Kundeneingang erforderlich')
        raw = next((value for value in context['portions'] if value['portion_id'] == data['portion_id']), None)
        if not raw or raw['portion_id'] in ledger['portions'] or raw['portion_id'] in sources['legacy_portions']:
            raise Problem(409, 'Noch undokumentierter ganzer Quellenanteil erforderlich')
        portion, proof = self._plan(actor, context, raw, ledger, sources)
        if not portion['eligible'] or portion['writer'] != 'c2' or portion['action'] != data['action']:
            raise Problem(409, 'Kapazitätsaktion gesperrt: '+str(portion['blocked_reason'] or 'legacy_writer_required'))
        if portion['portion_state_hash'] != data['portion_state_hash']:
            raise Problem(409, 'Rechnungs-, Rücknahme- oder Abschnittsstand geändert; neu prüfen')
        lines = self._entry_lines(context, portion, proof, data['groups'], ledger)
        preview = dict(event_id=state['event_id'], source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
            action=data['action'], portion=portion, amount=portion['amount'], net=_money(sum(_cents(line['net']) for line in lines)),
            tax=_money(sum(_cents(line['tax']) for line in lines)), lines=lines, capacity_changes=self._changes(proof), reason=data['reason'], **_FLAGS)
        return dict(preview, preview_hash=_sha(canonical(preview))), proof

    def preview(self, actor, event_id, data):
        identifier(event_id); self._inputs(data)
        with transaction(self.office):
            fresh = self._access(actor, event_id, True); self._gate(); cache = {}
            state, context, ledger, sources, unused = self._view(fresh, event_id, cache, write=True)
            return self._prepare(fresh, state, context, ledger, sources, data)[0]

    def _insert(self, suffix, value):
        self.office.db.execute('INSERT INTO business_accounting_capacity_'+suffix+'('+','.join(value)+') VALUES('
                               +','.join('?' for unused in value)+')', tuple(value.values()))

    def confirm(self, actor, event_id, data):
        identifier(event_id); self._inputs(data, True)
        with transaction(self.office):
            fresh = self._access(actor, event_id, True); self._gate(); cache = {}
            ledger = self._ledger(cache); digest = self._request_hash(event_id, data)
            request = self.office.db.execute('SELECT * FROM business_accounting_capacity_requests WHERE user_id=? AND request_id=?',
                                             (fresh['id'], data['request_id'])).fetchone()
            if request:
                if request['event_id'] != event_id or request['request_hash'] != digest:
                    raise Problem(409, 'Vorgangs-ID wurde mit anderem Inhalt verwendet')
                return next(value for value in ledger['by_event'].get(event_id, []) if value['id'] == request['entry_id'])
            try:
                state, context, ledger, sources, unused = self._view(fresh, event_id, cache, write=True)
                preview, proof = self._prepare(fresh, state, context, ledger, sources, data)
                if preview['preview_hash'] != data['preview_hash']:
                    raise Problem(409, 'Passende aktuelle Vorschau erforderlich')
            except Problem as error:
                if error.status != 409:
                    raise
                raise Problem(409, error.message, request_resolution='not_accepted') from None
            sequence = sum(map(len, ledger['by_event'].values()))+1
            value = {key: item for key, item in preview.items() if key not in ('expected_revision', 'state_hash')}
            value.update(id=uuid.uuid4().hex, sequence=sequence, revision=state['revision']+1, previous_state_hash=state['state_hash'],
                         created_by=fresh['id'], created_at=self.now())
            self._insert('entries', dict(id=value['id'], sequence=sequence, event_id=event_id, revision=value['revision'],
                document_id=value['portion']['document_id'], portion_id=value['portion']['portion_id'], source_hash=value['source_hash'],
                previous_state_hash=value['previous_state_hash'], entry_json=canonical(value), entry_sha256=_sha(canonical(value)),
                proof_json=canonical(proof), access_segments_json=canonical(self._access_segments(proof)),
                created_by=fresh['id'], created_at=value['created_at']))
            if value['action'] == 'takeover_and_document':
                handoff = self._handoff(value, proof)
                self._insert('handoffs', dict(document_id=handoff['document_id'], entry_id=value['id'],
                    handoff_json=canonical(handoff), handoff_sha256=_sha(canonical(handoff))))
            for segment in proof['new_segments']:
                self._insert('segments', {**{key: segment[key] for key in ('id', 'document_id', 'group_id', 'revision', 'previous_id')},
                    'entry_id': value['id'], 'segment_json': canonical(segment), 'segment_sha256': _sha(canonical(segment))})
                for reference in segment['returns']:
                    released = dict(refund_entry_id=reference['refund_entry_id'], origin_entry_id=reference['origin_entry_id'],
                        group_id=reference['group_id'], segment_id=segment['id'], reference_json=canonical(reference), reference_sha256=_sha(canonical(reference)))
                    if reference.get('refund_version') == 'r2':
                        from business_accounting_refunds_v2 import VersionedRefundOrigins
                        VersionedRefundOrigins(self.office)._insert('releases', dict(released, origin_version=reference['origin_version']))
                    else:
                        self._insert('releases', released)
            for line in value['lines']:
                self._insert('lines', dict(entry_id=value['id'], **line))
            self._insert('requests', dict(user_id=fresh['id'], request_id=data['request_id'], event_id=event_id,
                request_json=canonical(data), request_hash=digest, entry_id=value['id']))
            self.office.audit(fresh, 'business.accounting.capacity_confirmed', value['id'])
            return value


def validate_integrity(office, *, cache=None):
    try:
        if not installed(office):
            return True
        ReusableDocumentComponents(office)._ledger({} if cache is None else cache)
        if isinstance(office.db, sqlite3.Connection):
            normalize = lambda value: re.sub(r'\s+', ' ', value.replace('IF NOT EXISTS ', '')).strip().lower()
            for sql in guard_statements('sqlite'):
                name = re.search(r'CREATE TRIGGER IF NOT EXISTS (\w+)', sql)[1]
                row = office.db.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?", (name,)).fetchone()
                if not row or normalize(row[0]) != normalize(sql):
                    raise ValueError('Missing or changed capacity guard')
        else:
            from business_documents import _validate_pg_guards
            _validate_pg_guards(office.db, guard_statements('postgresql'))
    except (Problem, KeyError, TypeError, ArithmeticError) as error:
        raise ValueError('Invalid documentary capacity history') from error
    return True


def restore_horizon(office, *, cache=None):
    with office.lock:
        if not installed(office):
            return None
        validate_integrity(office, cache=cache)
        tables = {table: sorted((dict(row) for row in office.db.execute('SELECT * FROM '+table).fetchall()), key=canonical) for table in _TABLES}
        return dict(schema_version=1, table_counts={table: len(rows) for table, rows in tables.items()},
                    sha256=_sha(canonical(dict(schema_version=1, tables=tables))))


def methods(path):
    match = re.fullmatch(r'/accounting/components/v2/events/'+_ID+r'(/(?:portions|history|preview|confirm))?', path)
    return ('POST' if match[1] in ('/preview', '/confirm') else 'GET') if match else None


def dispatch(office, actor, path, method, data):
    allowed = methods(path)
    if allowed is None:
        return None
    if method != allowed:
        raise Problem(405, 'Methode nicht unterstützt')
    if not isinstance(data, dict) or not isinstance(data.get('_query', {}), dict):
        raise Problem(400, 'Eindeutige Kapazitätsparameter erwartet')
    parts = path.split('/'); event_id = parts[5]; action = parts[6] if len(parts) > 6 else 'state'; api = ReusableDocumentComponents(office)
    if method == 'GET':
        if set(data)-{'_query'}:
            raise Problem(400, 'GET erwartet keinen Anfragekörper')
        query = data.get('_query', {})
        if action == 'state':
            if query:
                raise Problem(400, 'Keine zusätzlichen Filter erlaubt')
            result = api.state(actor, event_id)
        else:
            if (set(query)-{'limit', 'offset'} or any(not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,6}', value) for value in query.values())):
                raise Problem(400, 'Nur eindeutige bekannte Listenfilter erwartet')
            result = getattr(api, action)(actor, event_id, int(query.get('limit', '50')), int(query.get('offset', '0')))
        return result, 200, 'application/json'
    if '_query' in data:
        raise Problem(400, 'Keine zusätzlichen Filter erlaubt')
    return getattr(api, action)(actor, event_id, data), (201 if action == 'confirm' else 200), 'application/json'
