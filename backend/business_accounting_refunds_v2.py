"""Whole refund portions bound to original C1 or C2 documentary income lots."""
import json
import re
import sqlite3
import uuid

from core import Problem, canonical
from business_operations import Domain, identifier, instant, transaction
from business_accounting_components import DocumentComponents, _cents, _money, _sha, _stored
from business_accounting_refunds import RefundOrigins, _hash_input, _FLAGS, _MONEY_FIELDS, _LINE_FIELDS
from accounting_return_lots import LotIdentity, ReturnedLot
from accounting_component_segments import CentAmounts

FEATURES = ('accounting_refund_origins_v2',)
_INPUT = {'source_hash', 'expected_revision', 'state_hash', 'portion_id', 'portion_state_hash', 'origins', 'reason', 'action'}
_ORIGIN_INPUT = {'origin_version', 'entry_id', 'group_id', 'lot_state_hash', 'amount'}
_TABLES = tuple('business_accounting_refunds_v2_'+name for name in ('handoffs', 'entries', 'lines', 'requests', 'releases'))
_ID = r'[a-f0-9]{32}'


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BLOB', 'BYTEA'):
        raise ValueError('Unsupported binary type')
    return [
        '''CREATE TABLE IF NOT EXISTS business_accounting_refunds_v2_entries(
        id TEXT PRIMARY KEY, sequence INTEGER NOT NULL UNIQUE CHECK(sequence>0),
        event_id TEXT NOT NULL REFERENCES business_accounting_cash_events(id), revision INTEGER NOT NULL CHECK(revision>0),
        document_id TEXT NOT NULL REFERENCES business_documents(id),
        refund_allocation_id TEXT NOT NULL UNIQUE REFERENCES business_payment_allocations(id),
        portion_id TEXT NOT NULL UNIQUE CHECK(length(portion_id)=64), source_hash TEXT NOT NULL CHECK(length(source_hash)=64),
        previous_state_hash TEXT NOT NULL CHECK(length(previous_state_hash)=64),
        entry_json TEXT NOT NULL, entry_sha256 TEXT NOT NULL CHECK(length(entry_sha256)=64), proof_json TEXT NOT NULL,
        access_origins_json TEXT NOT NULL, created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL,
        UNIQUE(event_id,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_accounting_refunds_v2_handoffs(
        document_id TEXT PRIMARY KEY REFERENCES business_documents(id), entry_id TEXT NOT NULL UNIQUE REFERENCES business_accounting_refunds_v2_entries(id),
        handoff_json TEXT NOT NULL, handoff_sha256 TEXT NOT NULL CHECK(length(handoff_sha256)=64))''',
        '''CREATE TABLE IF NOT EXISTS business_accounting_refunds_v2_lines(
        entry_id TEXT NOT NULL REFERENCES business_accounting_refunds_v2_entries(id), origin_version TEXT NOT NULL CHECK(origin_version IN ('c1','c2')),
        origin_entry_id TEXT NOT NULL, group_id TEXT NOT NULL CHECK(length(group_id)=64),
        origin_c1_entry_id TEXT, origin_c2_entry_id TEXT,
        amount TEXT NOT NULL, net TEXT NOT NULL, tax TEXT NOT NULL,
        gross_before TEXT NOT NULL, gross_after TEXT NOT NULL, net_before TEXT NOT NULL, net_after TEXT NOT NULL,
        tax_before TEXT NOT NULL, tax_after TEXT NOT NULL, remaining_gross TEXT NOT NULL, remaining_net TEXT NOT NULL, remaining_tax TEXT NOT NULL,
        origin_line_sha256 TEXT NOT NULL CHECK(length(origin_line_sha256)=64),
        PRIMARY KEY(entry_id,origin_version,origin_entry_id,group_id),
        CHECK((origin_version='c1' AND origin_c1_entry_id IS NOT NULL AND origin_c1_entry_id=origin_entry_id AND origin_c2_entry_id IS NULL)
           OR (origin_version='c2' AND origin_c2_entry_id IS NOT NULL AND origin_c2_entry_id=origin_entry_id AND origin_c1_entry_id IS NULL)),
        FOREIGN KEY(origin_c1_entry_id,group_id) REFERENCES business_accounting_component_lines(entry_id,group_id),
        FOREIGN KEY(origin_c2_entry_id,group_id) REFERENCES business_accounting_capacity_lines(entry_id,group_id))''',
        '''CREATE TABLE IF NOT EXISTS business_accounting_refunds_v2_requests(
        user_id TEXT NOT NULL REFERENCES users(id), request_id TEXT NOT NULL, event_id TEXT NOT NULL REFERENCES business_accounting_cash_events(id),
        request_json TEXT NOT NULL, request_hash TEXT NOT NULL CHECK(length(request_hash)=64),
        entry_id TEXT NOT NULL UNIQUE REFERENCES business_accounting_refunds_v2_entries(id), PRIMARY KEY(user_id,request_id))''',
        '''CREATE TABLE IF NOT EXISTS business_accounting_refunds_v2_releases(
        refund_entry_id TEXT NOT NULL, origin_version TEXT NOT NULL, origin_entry_id TEXT NOT NULL, group_id TEXT NOT NULL,
        segment_id TEXT NOT NULL REFERENCES business_accounting_capacity_segments(id),
        reference_json TEXT NOT NULL, reference_sha256 TEXT NOT NULL CHECK(length(reference_sha256)=64),
        PRIMARY KEY(refund_entry_id,origin_version,origin_entry_id,group_id),
        FOREIGN KEY(refund_entry_id,origin_version,origin_entry_id,group_id)
            REFERENCES business_accounting_refunds_v2_lines(entry_id,origin_version,origin_entry_id,group_id))''',
        'CREATE INDEX IF NOT EXISTS business_accounting_refunds_v2_origins ON business_accounting_refunds_v2_lines(origin_version,origin_entry_id,group_id,entry_id)',
    ]


def protected_tables():
    return _TABLES


def runtime_privileges():
    return {table: ('SELECT', 'INSERT') for table in _TABLES}


def guard_statements(dialect):
    if dialect == 'sqlite':
        guards = [f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} ON {table} "
                  "BEGIN SELECT RAISE(ABORT,'immutable versioned refund history'); END"
                  for table in _TABLES for action in ('UPDATE', 'DELETE')]
        conflicts = ('document_id=NEW.document_id OR entry_id=NEW.entry_id',
                     'id=NEW.id OR sequence=NEW.sequence OR refund_allocation_id=NEW.refund_allocation_id OR portion_id=NEW.portion_id OR (event_id=NEW.event_id AND revision=NEW.revision)',
                     'entry_id=NEW.entry_id AND origin_version=NEW.origin_version AND origin_entry_id=NEW.origin_entry_id AND group_id=NEW.group_id',
                     '(user_id=NEW.user_id AND request_id=NEW.request_id) OR entry_id=NEW.entry_id',
                     'refund_entry_id=NEW.refund_entry_id AND origin_version=NEW.origin_version AND origin_entry_id=NEW.origin_entry_id AND group_id=NEW.group_id')
        for table, conflict in zip(_TABLES, conflicts):
            guards.append(f'CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} '
                          f'WHEN EXISTS(SELECT 1 FROM {table} WHERE {conflict}) '
                          "BEGIN SELECT RAISE(ABORT,'immutable versioned refund history'); END")
        return guards
    if dialect != 'postgresql':
        raise ValueError('Unsupported guard dialect')
    guards = ["""CREATE OR REPLACE FUNCTION business_accounting_refunds_v2_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'immutable versioned refund history'; END; $$"""]
    for table in _TABLES:
        for action in ('UPDATE', 'DELETE'):
            name = table+'_'+action.lower()+'_guard'
            guards.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) "
                          f"THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION "
                          "business_accounting_refunds_v2_immutable_guard(); END IF; END $$")
    return guards


@_stored
def installed(office):
    from business_schema import _tables
    from business_accounting_capacity import installed as capacity_installed
    tables = _tables(office); present = set(_TABLES) & tables
    marker = ('business_schema_migrations' in tables and office.db.execute(
        "SELECT 1 FROM business_schema_migrations WHERE module='business_accounting_refunds_v2'").fetchone())
    if not present and not marker:
        # During additive migration, the old C2 validator runs before R2 DDL.
        # Genuine v1 storage remains valid; new references may never fall back.
        if 'business_accounting_capacity_entries' in tables:
            for row in office.db.execute('SELECT proof_json FROM business_accounting_capacity_entries').fetchall():
                proof = json.loads(row['proof_json'])
                if not isinstance(proof, dict) or type(proof.get('schema_version')) is not int or proof['schema_version'] != 1:
                    raise Problem(409, 'Versionierte Kapazitätsbeweise benötigen die vollständige Erstattungserweiterung')
        if 'business_accounting_capacity_segments' in tables:
            for row in office.db.execute('SELECT segment_json FROM business_accounting_capacity_segments').fetchall():
                segment = json.loads(row['segment_json'])
                if not isinstance(segment, dict) or 'schema_version' in segment or any('refund_version' in value or 'origin_version' in value for value in segment['returns']):
                    raise Problem(409, 'Versionierte Abschnittsbeweise benötigen die vollständige Erstattungserweiterung')
        return False
    if present != set(_TABLES) or not marker or not capacity_installed(office):
        raise Problem(409, 'Versionierte Erstattungsursprünge oder ihre Abhängigkeiten sind unvollständig installiert')
    return True


def require_legacy_writer(office, document_id):
    if installed(office) and office.db.execute('SELECT 1 FROM business_accounting_refunds_v2_handoffs WHERE document_id=?', (document_id,)).fetchone():
        raise Problem(409, 'Erstattungsbeleg wurde in die aktuelle Ursprungsverwaltung übernommen; erneut prüfen')


def _origin_key(value):
    return value['origin_version'], value['entry_id'], value['group_id']


def return_key(value):
    return value['refund_version'], value['refund_entry_id'], value['origin_version'], value['origin_entry_id'], value['group_id']


def reference_order(value):
    return value['refund_version'], value['sequence'], value['refund_entry_id'], value['origin_version'], value['origin_entry_id'], value['group_id']


def legacy_reference(value):
    return dict(value, refund_version='r1', origin_version='c1')


def _head(row):
    return {key: row[key] for key in ('id', 'sequence', 'revision', 'entry_sha256')}


def _handoff_reference(value):
    return dict(document_id=value['document_id'], entry_id=value['entry_id'], handoff_sha256=_sha(canonical(value))) if value else None


def _origin(lot, claims):
    value = lot['value']
    prior = CentAmounts(*(sum(_cents(item[key]) for item in claims) for key in ('net', 'tax', 'amount')))
    state = ReturnedLot(CentAmounts(_cents(value['net']), _cents(value['tax']), _cents(value['amount'])), prior)
    remaining = state.remaining_amounts
    return dict(value, returned_amount=_money(prior.gross), returned_net=_money(prior.net), returned_tax=_money(prior.tax),
        remaining_amount=_money(remaining.gross), remaining_net=_money(remaining.net), remaining_tax=_money(remaining.tax),
        lot_state_hash=_sha(canonical(dict(schema_version=1, origin=lot['reference'], claims=claims))))


def _line(origin, amount):
    prior = CentAmounts(_cents(origin['returned_net']), _cents(origin['returned_tax']), _cents(origin['returned_amount']))
    state = ReturnedLot(CentAmounts(_cents(origin['net']), _cents(origin['tax']), _cents(origin['amount'])), prior)
    try:
        delta, following = state.return_cents(amount)
    except ValueError:
        raise Problem(409, 'Ursprungslot wurde über seine festen Cents hinaus zurückgenommen') from None
    after, remaining = following.previously_returned, following.remaining_amounts
    return dict(**{key: origin[key] for key in ('origin_version', 'entry_id', 'group_id', 'origin_event_id', 'component_sequence', 'rate', 'category', 'tax_reason', 'lot_state_hash')},
        origin_cash_date=origin['cash_date'], origin_evidence_reference=origin['evidence_reference'], origin_reference=origin['reference'],
        amount=_money(amount), net=_money(delta.net), tax=_money(delta.tax), gross_before=_money(prior.gross), gross_after=_money(after.gross),
        net_before=_money(prior.net), net_after=_money(after.net), tax_before=_money(prior.tax), tax_after=_money(after.tax),
        remaining_gross=_money(remaining.gross), remaining_net=_money(remaining.net), remaining_tax=_money(remaining.tax))


class VersionedRefundOrigins(Domain):
    def _access(self, actor, event_id, write=False, selected=()):
        from accounting_joint_access import authorize_sources
        fresh = DocumentComponents(self.office)._access(actor, event_id, write)
        if not installed(self.office):
            raise Problem(409, 'Versionierte Erstattungsursprünge sind nicht installiert')
        return authorize_sources(self.office, fresh, event_id, write=write, origins=selected)

    def _gate(self):
        RefundOrigins(self.office)._gate()

    def _writes_allowed(self, actor, event_id):
        try:
            self._access(actor, event_id, True); self._gate()
            return True
        except Problem as error:
            if error.status not in (403, 404, 409, 423):
                raise
            return False

    @staticmethod
    def _empty_ledger():
        return dict(by_event={}, headers={}, rows={}, entries={}, handoffs={}, bound=set(), allocations=set(), references={}, returns={})

    def _ledger(self, cache):
        from accounting_joint_ledger import read_joint_ledger
        return read_joint_ledger(self.office, cache)

    @_stored
    def _lot(self, version, entry_id, group_id, joint, cache, c1_sequence=None):
        if version == 'c1':
            lot = RefundOrigins(self.office)._lot(entry_id, group_id, cache)
            if c1_sequence is not None and lot['value']['component_sequence'] > c1_sequence:
                raise Problem(409, 'Ursprungslot liegt hinter dem beobachteten C1-Kopf')
            return dict(value=dict(lot['value'], origin_version='c1'), reference=dict(lot['reference'], origin_version='c1'))
        if version != 'c2':
            raise ValueError('Unknown positive origin version')
        row = self.office.db.execute('SELECT * FROM business_accounting_capacity_entries WHERE id=?', (entry_id,)).fetchone()
        actual = self.office.db.execute('SELECT * FROM business_accounting_capacity_lines WHERE entry_id=? AND group_id=?', (entry_id, group_id)).fetchone()
        if not row or not actual:
            raise Problem(404, 'Dokumentierter Ursprungslot nicht verfügbar')
        entry = joint['capacity']['entries_by_id'].get(entry_id)
        if not entry:
            raise Problem(409, 'Ursprungslot liegt hinter dem geprüften C2-Präfix')
        line = next((value for value in entry['lines'] if value['group_id'] == group_id), None)
        if line is None:
            raise ValueError('Missing positive capacity line')
        group = next(value for value in entry['portion']['groups'] if value['group_id'] == group_id)
        context = DocumentComponents(self.office)._source(None, row['event_id']); event = context['event']; portion = entry['portion']
        if context['kind'] != 'customer_receipt' or not portion['customer_id']:
            raise ValueError('Invalid positive capacity source')
        value = dict(origin_version='c2', entry_id=entry_id, group_id=group_id, origin_event_id=row['event_id'], component_sequence=row['sequence'],
            rate=group['rate'], category=group['category'], tax_reason=group['reason'],
            **{key: portion[key] for key in ('document_id', 'customer_id', 'project_id', 'number', 'party_name')},
            **{key: event[key] for key in ('cash_date', 'evidence_reference', 'reference')}, currency='EUR',
            **{key: line[key] for key in ('amount', 'net', 'tax')})
        reference = dict(origin_version='c2', entry_id=entry_id, group_id=group_id, origin_event_id=row['event_id'], entry_sha256=row['entry_sha256'],
            proof_sha256=_sha(row['proof_json']), line_sha256=_sha(canonical(dict(actual))), source_hash=event['source']['source_hash'])
        return dict(value=value, reference=reference)

    @staticmethod
    def _claims(lot, joint, r1_sequence):
        value = lot['value']; key = _origin_key(value)
        old = ([legacy_reference(item) for item in joint['sources']['returns'].get(value['document_id'], [])
                if item['sequence'] <= r1_sequence and item['origin_entry_id'] == value['entry_id'] and item['group_id'] == value['group_id']]
               if value['origin_version'] == 'c1' else [])
        return sorted(old+joint['refunds_v2']['references'].get(key, []), key=reference_order)

    @staticmethod
    def _state_hash(context, joint, r1_sequence=None):
        r1_sequence = joint['sources']['r1_sequence'] if r1_sequence is None else r1_sequence
        document_ids = sorted({value['document']['document_id'] for value in context['portions']})
        return _sha(canonical(dict(schema_version=1, event_id=context['event']['id'], source_hash=context['event']['source']['source_hash'],
            portions=context['portions'], legacy=[_head(value) for value in joint['sources']['refund_entries'].values()
                if value['event_id'] == context['event']['id'] and value['sequence'] <= r1_sequence],
            entries=joint['refunds_v2']['headers'].get(context['event']['id'], []), handoffs=[dict(document_id=document_id,
                capacity=_handoff_reference(joint['capacity']['handoffs'].get(document_id)),
                refunds=_handoff_reference(joint['refunds_v2']['handoffs'].get(document_id))) for document_id in document_ids])))

    def _observation(self, context, raw, joint, *, c1_sequence=None, r1_sequence=None, c2_sequence=None):
        sources = joint['sources']; document_id = raw['document']['document_id']
        c1_sequence = sources['c1_sequence'] if c1_sequence is None else c1_sequence
        r1_sequence = sources['r1_sequence'] if r1_sequence is None else r1_sequence
        c2_sequence = len(joint['capacity']['entries_by_id']) if c2_sequence is None else c2_sequence
        if (type(c1_sequence) is not int or not 0 <= c1_sequence <= sources['c1_sequence']
                or type(r1_sequence) is not int or not 0 <= r1_sequence <= sources['r1_sequence']
                or type(c2_sequence) is not int or c2_sequence != len(joint['capacity']['entries_by_id'])):
            raise ValueError('Invalid observed original or positive prefix')
        capacity_handoff = _handoff_reference(joint['capacity']['handoffs'].get(document_id))
        handoff = joint['refunds_v2']['handoffs'].get(document_id)
        claims = sorted((legacy_reference(value) for value in sources['returns'].get(document_id, []) if value['sequence'] <= r1_sequence), key=reference_order)
        if handoff and claims != handoff['legacy_claims']:
            raise ValueError('Legacy refund claims changed after handoff')
        return dict(schema_version=1, source=dict(event_sha256=_sha(canonical(context['event'])), portion=raw),
            c1_sequence=c1_sequence, r1_sequence=r1_sequence, c2_sequence=c2_sequence, capacity_handoff=capacity_handoff,
            refund_handoff_before=_handoff_reference(handoff), legacy_claims=claims)

    def _portion(self, context, raw, joint, observation=None):
        observation = observation or self._observation(context, raw, joint)
        portion = RefundOrigins(self.office)._portion(context, raw)
        portion.pop('portion_state_hash')
        capacity_id = raw['document']['document_id'] if observation['capacity_handoff'] else None
        ownership_id = raw['document']['document_id'] if observation['refund_handoff_before'] else None
        writer = 'r2' if capacity_id or ownership_id else 'r1'
        action = ('bind_current' if ownership_id else 'takeover_and_bind' if capacity_id else 'bind_legacy') if portion['eligible'] else None
        portion.update(capacity_ownership_id=capacity_id, ownership_id=ownership_id, writer=writer, action=action)
        portion['portion_state_hash'] = _sha(canonical(dict(observation=observation, portion=portion)))
        return portion
    @staticmethod
    def _inputs(data, confirm=False):
        expected = _INPUT | ({'request_id', 'preview_hash', 'confirmation'} if confirm else set())
        if not isinstance(data, dict) or set(data) != expected:
            raise Problem(400, 'Vollständige bekannte Felder für versionierte Erstattungsursprünge erwartet')
        for key in ('source_hash', 'state_hash', 'portion_id', 'portion_state_hash') + (('preview_hash',) if confirm else ()):
            _hash_input(data[key])
        if type(data['expected_revision']) is not int or data['expected_revision'] < 0:
            raise Problem(400, 'Nichtnegative Ursprungsrevision erwartet')
        if data['action'] not in ('takeover_and_bind', 'bind_current'):
            raise Problem(400, 'Ausdrückliche aktuelle Ursprungsaktion erwartet')
        if confirm:
            identifier(data['request_id'], 'request_id')
            if data['confirmation'] is not True:
                raise Problem(400, 'Erstattungsursprung ausdrücklich bestätigen')
        reason = data['reason']
        if (not isinstance(reason, str) or not 1 <= len(reason) <= 1000 or not reason.strip()
                or any(ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF for char in reason)):
            raise Problem(400, 'Einzeilige Begründung mit 1 bis 1000 Zeichen erwartet')
        if not isinstance(data['origins'], list) or not 1 <= len(data['origins']) <= 500:
            raise Problem(400, '1 bis 500 ausdrückliche versionierte Ursprungslotbeträge erwartet')
        seen = set()
        for origin in data['origins']:
            if not isinstance(origin, dict) or set(origin) != _ORIGIN_INPUT:
                raise Problem(400, 'Bekannte versionierte Ursprungslotfelder erwartet')
            try:
                identity = LotIdentity(origin['origin_version'], origin['entry_id'], origin['group_id'])
            except ValueError:
                raise Problem(400, 'Gültige eindeutige versionierte Ursprungslotkennung erwartet') from None
            _hash_input(origin['lot_state_hash'])
            if identity in seen:
                raise Problem(400, 'Versionierter Ursprungslot doppelt angegeben')
            seen.add(identity)
            _cents(origin['amount'], positive=True, input_value=True)

    @staticmethod
    def _request_hash(event_id, data):
        return _sha(canonical(['refunds_v2.confirm', event_id, data]))

    @staticmethod
    def _preview_from_entry(value):
        preview = {key: item for key, item in value.items() if key not in ('id', 'sequence', 'revision', 'previous_state_hash', 'created_by', 'created_at', 'preview_hash')}
        return dict(preview, expected_revision=value['revision']-1, state_hash=value['previous_state_hash'])

    @staticmethod
    def _access_origins(lines):
        return [{key: value[key] for key in ('origin_version', 'entry_id', 'group_id')} for value in lines]

    @_stored
    def _basic(self, row):
        from accounting_joint_access import origin_access_ids
        value = json.loads(row['entry_json']); proof = json.loads(row['proof_json'])
        expected = {'id', 'sequence', 'revision', 'previous_state_hash', 'created_by', 'created_at', 'event_id', 'source_hash', 'action',
                    'cash_date', 'evidence_reference', 'reference', 'portion', 'amount', 'net', 'tax', 'lines', 'reason', 'preview_hash'} | set(_FLAGS)
        if (set(value) != expected or any(value[key] != wanted for key, wanted in _FLAGS.items())
                or value['capacity_released'] is not False or value['tax_result_available'] is not False
                or type(value['sequence']) is not int or type(value['revision']) is not int
                or canonical(value) != row['entry_json'] or canonical(proof) != row['proof_json'] or _sha(row['entry_json']) != row['entry_sha256']
                or any(value[key] != row[key] for key in ('id', 'sequence', 'revision', 'event_id', 'source_hash', 'previous_state_hash', 'created_by', 'created_at'))
                or value['portion']['portion_id'] != row['portion_id'] or value['portion']['document_id'] != row['document_id']
                or type(row['sequence']) is not int or row['sequence'] < 1 or type(row['revision']) is not int or row['revision'] < 1
                or not isinstance(value['lines'], list) or not 1 <= len(value['lines']) <= 500
                or [_origin_key(line) for line in value['lines']] != sorted({_origin_key(line) for line in value['lines']})):
            raise ValueError('Invalid versioned refund entry')
        for key in ('id', 'event_id', 'document_id', 'created_by', 'refund_allocation_id'):
            identifier(row[key])
        if instant(row['created_at']) != row['created_at']:
            raise ValueError('Versioned refund timestamp must be canonical UTC')
        if origin_access_ids(row['access_origins_json']) != [_origin_key(line) for line in value['lines']]:
            raise ValueError('Changed versioned origin access binding')
        if (sum(_cents(line['amount'], positive=True) for line in value['lines']) != _cents(value['amount'], positive=True, input_value=True)
                or sum(_cents(line['net']) for line in value['lines']) != _cents(value['net'])
                or sum(_cents(line['tax']) for line in value['lines']) != _cents(value['tax'])
                or _cents(value['net'])+_cents(value['tax']) != _cents(value['amount'])):
            raise ValueError('Invalid versioned refund totals')
        stored = self.office.db.execute('SELECT * FROM business_accounting_refunds_v2_lines WHERE entry_id=? ORDER BY origin_version,origin_entry_id,group_id', (row['id'],)).fetchall()
        if len(stored) != len(value['lines']):
            raise ValueError('Missing versioned refund line')
        for line, actual in zip(value['lines'], stored):
            if (set(line) != _LINE_FIELDS | {'origin_version'} or line['origin_version'] not in ('c1', 'c2')
                    or line['origin_version'] != actual['origin_version'] or line['entry_id'] != actual['origin_entry_id'] or line['group_id'] != actual['group_id']
                    or actual['origin_c1_entry_id'] != (line['entry_id'] if line['origin_version'] == 'c1' else None)
                    or actual['origin_c2_entry_id'] != (line['entry_id'] if line['origin_version'] == 'c2' else None)
                    or any(line[key] != actual[key] for key in _MONEY_FIELDS)):
                raise ValueError('Changed versioned refund line or foreign key')
        request = self.office.db.execute('SELECT * FROM business_accounting_refunds_v2_requests WHERE entry_id=?', (row['id'],)).fetchone()
        if not request:
            raise ValueError('Missing versioned refund request receipt')
        body = json.loads(request['request_json']); self._inputs(body, True)
        if (request['event_id'] != row['event_id'] or request['user_id'] != row['created_by'] or request['request_id'] != body['request_id']
                or canonical(body) != request['request_json'] or request['request_hash'] != self._request_hash(row['event_id'], body)
                or body['expected_revision'] != row['revision']-1 or body['state_hash'] != row['previous_state_hash']
                or any(body[key] != value[key] for key in ('source_hash', 'preview_hash', 'reason', 'action'))
                or body['portion_id'] != row['portion_id'] or body['portion_state_hash'] != value['portion']['portion_state_hash']
                or sorted(body['origins'], key=_origin_key) != [{key: line[key] for key in _ORIGIN_INPUT} for line in value['lines']]
                or _sha(canonical(self._preview_from_entry(value))) != value['preview_hash']):
            raise ValueError('Changed versioned refund request or preview')
        return value, proof, stored

    @staticmethod
    def _handoff(value, proof):
        return dict(document_id=value['portion']['document_id'], entry_id=value['id'], capacity_handoff=proof['capacity_handoff'],
                    r1_sequence=proof['r1_sequence'], legacy_claims=proof['legacy_claims'], created_by=value['created_by'], created_at=value['created_at'])

    @_stored
    def _process(self, row, value, proof, stored, joint, cache):
        ledger = joint['refunds_v2']; sources = joint['sources']
        if (type(proof.get('schema_version')) is not int or proof['schema_version'] != 1
                or row['sequence'] != len(ledger['rows'])+1 or row['revision'] != len(ledger['by_event'].get(row['event_id'], []))+1
                or row['portion_id'] in ledger['bound'] or row['portion_id'] in joint['refunds']['bound']
                or row['refund_allocation_id'] in ledger['allocations']):
            raise ValueError('Invalid versioned refund order or duplicated whole portion')
        context = RefundOrigins(self.office)._source(row['event_id'], cache)
        raw = next((value for value in context['portions'] if value['portion_id'] == row['portion_id']), None)
        if not raw or raw['allocation']['id'] != row['refund_allocation_id'] or raw['document']['document_id'] != row['document_id']:
            raise ValueError('Changed versioned refund source portion')
        expected = self._observation(context, raw, joint, **{key: proof[key] for key in ('c1_sequence', 'r1_sequence', 'c2_sequence')})
        portion = self._portion(context, raw, joint, expected)
        if (not portion['eligible'] or portion['writer'] != 'r2' or portion != value['portion'] or portion['action'] != value['action']
                or value['amount'] != portion['amount'] or row['source_hash'] != context['event']['source']['source_hash']
                or any(value[key] != context['event'][key] for key in ('cash_date', 'evidence_reference', 'reference'))
                or row['previous_state_hash'] != self._state_hash(context, joint, proof['r1_sequence'])):
            raise ValueError('Changed historical refund source, whole portion or state')
        origins = []; claims_before = []; returns = []
        for line, actual in zip(value['lines'], stored):
            try:
                lot = self._lot(*_origin_key(line), joint, cache, proof['c1_sequence'])
            except Problem as error:
                if error.status != 404:
                    raise
                raise Problem(409, 'Gespeicherter versionierter Ursprungslot fehlt') from None
            RefundOrigins._match(context, portion, lot)
            claims = self._claims(lot, joint, proof['r1_sequence'])
            origin = _origin(lot, claims)
            if actual['origin_line_sha256'] != lot['reference']['line_sha256'] or _line(origin, _cents(line['amount'], positive=True)) != line:
                raise ValueError('Invalid historical combined lot return')
            origins.append(lot['reference'])
            claims_before.append(dict(origin_version=line['origin_version'], entry_id=line['entry_id'], group_id=line['group_id'], claims=claims))
            returns.append(dict(refund_version='r2', refund_entry_id=row['id'], origin_version=line['origin_version'], origin_entry_id=line['entry_id'],
                group_id=line['group_id'], refund_event_id=row['event_id'], origin_event_id=line['origin_event_id'], sequence=row['sequence'],
                entry_sha256=row['entry_sha256'], proof_sha256=_sha(row['proof_json']), line_sha256=_sha(canonical(dict(actual))),
                cash_date=value['cash_date'], net=line['net'], tax=line['tax'], amount=line['amount']))
        expected.update(origins=origins, claims_before=claims_before)
        if expected != proof:
            raise ValueError('Changed versioned origin or claim references')
        document_id = portion['document_id']
        if value['action'] == 'takeover_and_bind':
            if document_id in ledger['handoffs']:
                raise ValueError('Repeated refund writer handoff')
            handoff = self._handoff(value, proof)
            actual = self.office.db.execute('SELECT * FROM business_accounting_refunds_v2_handoffs WHERE document_id=?', (document_id,)).fetchone()
            if (not actual or actual['entry_id'] != value['id'] or actual['handoff_json'] != canonical(handoff)
                    or actual['handoff_sha256'] != _sha(canonical(handoff))):
                raise ValueError('Changed versioned refund handoff')
            ledger['handoffs'][document_id] = handoff
        elif value['action'] != 'bind_current' or document_id not in ledger['handoffs']:
            raise ValueError('Missing versioned refund handoff')
        for line, reference in zip(value['lines'], returns):
            ledger['references'].setdefault(_origin_key(line), []).append(reference)
            ledger['returns'].setdefault(document_id, []).append(reference)
        ledger['rows'][row['id']] = dict(row); ledger['entries'][row['id']] = value
        ledger['by_event'].setdefault(row['event_id'], []).append(value)
        ledger['headers'].setdefault(row['event_id'], []).append(_head(row)); ledger['bound'].add(row['portion_id'])
        ledger['allocations'].add(row['refund_allocation_id'])
        if sum(_cents(item['amount']) for item in ledger['by_event'][row['event_id']])+sum(
                _cents(item['amount']) for item in joint['refunds']['by_event'].get(row['event_id'], [])) > _cents(context['event']['amount']):
            raise ValueError('Combined origin bindings exceed refund cash source')

    def _view(self, actor, event_id, cache):
        context = RefundOrigins(self.office)._source(event_id, cache); joint = self._ledger(cache)
        own = joint['refunds_v2']['by_event'].get(event_id, []); old = joint['refunds']['by_event'].get(event_id, [])
        documented = sum(_cents(value['amount']) for value in own+old)
        portions = [self._portion(context, raw, joint) for raw in context['portions']
                    if raw['portion_id'] not in joint['refunds_v2']['bound'] and raw['portion_id'] not in joint['refunds']['bound']]
        eligible = any(portion['eligible'] for portion in portions)
        reason = (None if eligible else context['reason'] or (portions[0]['blocked_reason'] if portions else
                  'unallocated' if _cents(context['unallocated']) else 'fully_documented'))
        return dict(event_id=event_id, source_hash=context['event']['source']['source_hash'], revision=len(own),
            state_hash=self._state_hash(context, joint), source_kind=context['kind'], amount=context['event']['amount'], currency='EUR',
            **{key: context['event'][key] for key in ('cash_date', 'evidence_reference', 'reference')},
            origin_documented_amount=_money(documented), origin_unresolved_amount=_money(_cents(context['event']['amount'])-documented),
            unallocated_amount=context['unallocated'], eligible=eligible, blocked_reason=reason,
            writes_allowed=self._writes_allowed(actor, event_id), **_FLAGS), context, joint, portions

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
            return _paged(list(reversed(self._ledger({})['refunds_v2']['by_event'].get(event_id, []))), limit, offset)

    def origins(self, actor, event_id, portion_id, limit=50, offset=0):
        from accounting_joint_access import authorize_sources
        from business_accounting import _page, _paged
        identifier(event_id); _hash_input(portion_id); _page(limit, offset)
        with transaction(self.office):
            fresh = self._access(actor, event_id, True); cache = {}
            unused, context, joint, portions = self._view(fresh, event_id, cache)
            portion = next((value for value in portions if value['portion_id'] == portion_id), None)
            if not portion:
                raise Problem(409, 'Noch ungebundene Refundportion erforderlich')
            if not portion['eligible']:
                return _paged([], limit, offset)
            if portion['writer'] != 'r2':
                raise Problem(409, 'legacy_writer_required')
            items = []
            for version, prefix in (('c1', 'business_accounting_component'), ('c2', 'business_accounting_capacity')):
                for row in self.office.db.execute('SELECT entry_id,group_id FROM '+prefix+'_lines ORDER BY entry_id,group_id').fetchall():
                    selected = dict(origin_version=version, entry_id=row['entry_id'], group_id=row['group_id'])
                    try:
                        authorize_sources(self.office, fresh, write=True, origins=[selected])
                    except Problem as error:
                        if error.status in (403, 404):
                            continue
                        raise
                    entry = (joint['sources']['legacy_entries'].get(row['entry_id']) if version == 'c1'
                             else joint['capacity']['entries_by_id'].get(row['entry_id']))
                    if not entry or entry['portion']['document_id'] != portion['document_id']:
                        continue
                    lot = self._lot(*_origin_key(selected), joint, cache)
                    value = lot['value']
                    if (value['document_id'] != portion['document_id'] or value['customer_id'] != portion['customer_id']
                            or value['cash_date'] > context['event']['cash_date']):
                        continue
                    origin = _origin(lot, self._claims(lot, joint, joint['sources']['r1_sequence']))
                    if _cents(origin['remaining_amount']):
                        items.append(origin)
            items.sort(key=lambda value: tuple(value[key] for key in ('cash_date', 'origin_event_id', 'origin_version', 'entry_id', 'group_id')))
            return _paged(items, limit, offset)

    def _prepare(self, state, context, joint, data, cache):
        if any(data[key] != state[target] for key, target in (('source_hash', 'source_hash'), ('expected_revision', 'revision'), ('state_hash', 'state_hash'))):
            raise Problem(409, 'Quellen- oder Bindungsstand geändert; neu laden')
        raw = next((value for value in context['portions'] if value['portion_id'] == data['portion_id']), None)
        if not raw or raw['portion_id'] in joint['refunds_v2']['bound'] or raw['portion_id'] in joint['refunds']['bound']:
            raise Problem(409, 'Noch ungebundene ganze Refundportion erforderlich')
        proof = self._observation(context, raw, joint); portion = self._portion(context, raw, joint, proof)
        if portion['writer'] != 'r2':
            raise Problem(409, 'legacy_writer_required')
        if (not portion['eligible'] or portion['action'] != data['action'] or portion['portion_state_hash'] != data['portion_state_hash']):
            raise Problem(409, 'Refundportion passt nicht zum aktuellen Quellen- oder Writerstand')
        if sum(_cents(value['amount']) for value in data['origins']) != _cents(portion['amount']):
            raise Problem(400, 'Ursprungsbeträge müssen die ganze unveränderliche Refundportion ergeben')
        lines = []; references = []; claims_before = []
        for selected in sorted(data['origins'], key=_origin_key):
            lot = self._lot(*_origin_key(selected), joint, cache, proof['c1_sequence'])
            RefundOrigins._match(context, portion, lot)
            claims = self._claims(lot, joint, proof['r1_sequence']); origin = _origin(lot, claims)
            if selected['lot_state_hash'] != origin['lot_state_hash']:
                raise Problem(409, 'Versionierter Ursprungslot wurde zwischenzeitlich beansprucht; neu prüfen')
            lines.append(_line(origin, _cents(selected['amount'], positive=True)))
            references.append(lot['reference'])
            claims_before.append(dict(origin_version=selected['origin_version'], entry_id=selected['entry_id'], group_id=selected['group_id'], claims=claims))
        proof.update(origins=references, claims_before=claims_before)
        preview = dict(event_id=state['event_id'], source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
            action=data['action'], **{key: context['event'][key] for key in ('cash_date', 'evidence_reference', 'reference')},
            portion=portion, amount=portion['amount'], net=_money(sum(_cents(line['net']) for line in lines)), tax=_money(sum(_cents(line['tax']) for line in lines)),
            lines=lines, reason=data['reason'], **_FLAGS)
        return dict(preview, preview_hash=_sha(canonical(preview))), proof

    def preview(self, actor, event_id, data):
        identifier(event_id); self._inputs(data)
        with transaction(self.office):
            fresh = self._access(actor, event_id, True, data['origins']); self._gate(); cache = {}
            state, context, joint, unused = self._view(fresh, event_id, cache)
            return self._prepare(state, context, joint, data, cache)[0]

    def _insert(self, suffix, value):
        self.office.db.execute('INSERT INTO business_accounting_refunds_v2_'+suffix+'('+','.join(value)+') VALUES('
                               +','.join('?' for unused in value)+')', tuple(value.values()))

    def confirm(self, actor, event_id, data):
        identifier(event_id); self._inputs(data, True)
        with transaction(self.office):
            fresh = self._access(actor, event_id, True, data['origins']); self._gate(); cache = {}
            joint = self._ledger(cache); digest = self._request_hash(event_id, data)
            request = self.office.db.execute('SELECT * FROM business_accounting_refunds_v2_requests WHERE user_id=? AND request_id=?', (fresh['id'], data['request_id'])).fetchone()
            if request:
                if request['event_id'] != event_id or request['request_hash'] != digest:
                    raise Problem(409, 'Vorgangs-ID wurde mit anderem Inhalt verwendet')
                return joint['refunds_v2']['entries'][request['entry_id']]
            try:
                state, context, joint, unused = self._view(fresh, event_id, cache)
                preview, proof = self._prepare(state, context, joint, data, cache)
                if preview['preview_hash'] != data['preview_hash']:
                    raise Problem(409, 'Passende aktuelle Vorschau erforderlich')
            except Problem as error:
                if error.status != 409:
                    raise
                raise Problem(409, error.message, request_resolution='not_accepted') from None
            sequence = len(joint['refunds_v2']['rows'])+1
            value = {key: item for key, item in preview.items() if key not in ('expected_revision', 'state_hash')}
            value.update(id=uuid.uuid4().hex, sequence=sequence, revision=state['revision']+1, previous_state_hash=state['state_hash'],
                         created_by=fresh['id'], created_at=self.now())
            self._insert('entries', dict(id=value['id'], sequence=sequence, event_id=event_id, revision=value['revision'],
                document_id=value['portion']['document_id'], refund_allocation_id=proof['source']['portion']['allocation']['id'],
                portion_id=value['portion']['portion_id'], source_hash=value['source_hash'], previous_state_hash=value['previous_state_hash'],
                entry_json=canonical(value), entry_sha256=_sha(canonical(value)), proof_json=canonical(proof),
                access_origins_json=canonical(self._access_origins(value['lines'])), created_by=fresh['id'], created_at=value['created_at']))
            if value['action'] == 'takeover_and_bind':
                handoff = self._handoff(value, proof)
                self._insert('handoffs', dict(document_id=handoff['document_id'], entry_id=value['id'], handoff_json=canonical(handoff), handoff_sha256=_sha(canonical(handoff))))
            for line in value['lines']:
                lot = self._lot(*_origin_key(line), joint, cache, proof['c1_sequence'])
                self._insert('lines', dict(entry_id=value['id'], origin_version=line['origin_version'], origin_entry_id=line['entry_id'], group_id=line['group_id'],
                    origin_c1_entry_id=line['entry_id'] if line['origin_version'] == 'c1' else None,
                    origin_c2_entry_id=line['entry_id'] if line['origin_version'] == 'c2' else None,
                    **{key: line[key] for key in _MONEY_FIELDS}, origin_line_sha256=lot['reference']['line_sha256']))
            self._insert('requests', dict(user_id=fresh['id'], request_id=data['request_id'], event_id=event_id, request_json=canonical(data), request_hash=digest, entry_id=value['id']))
            self.office.audit(fresh, 'business.accounting.versioned_refund_confirmed', value['id'])
            return value


def validate_integrity(office, *, cache=None):
    try:
        if not installed(office):
            return True
        VersionedRefundOrigins(office)._ledger({} if cache is None else cache)
        if isinstance(office.db, sqlite3.Connection):
            normalize = lambda value: re.sub(r'\s+', ' ', value.replace('IF NOT EXISTS ', '')).strip().lower()
            for statement in guard_statements('sqlite'):
                name = re.search(r'CREATE TRIGGER IF NOT EXISTS (\w+)', statement)[1]
                row = office.db.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?", (name,)).fetchone()
                if not row or normalize(row[0]) != normalize(statement):
                    raise ValueError('Missing or changed versioned refund guard')
        else:
            from business_documents import _validate_pg_guards
            _validate_pg_guards(office.db, guard_statements('postgresql'))
    except (Problem, KeyError, TypeError, ArithmeticError) as error:
        raise ValueError('Invalid versioned refund history') from error
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
    match = re.fullmatch(r'/accounting/refunds/v2/events/'+_ID+r'(/(?:portions|origins|history|preview|confirm))?', path)
    return ('POST' if match[1] in ('/preview', '/confirm') else 'GET') if match else None


def dispatch(office, actor, path, method, data):
    allowed = methods(path)
    if allowed is None:
        return None
    if method != allowed:
        raise Problem(405, 'Methode nicht unterstützt')
    if not isinstance(data, dict) or not isinstance(data.get('_query', {}), dict):
        raise Problem(400, 'Eindeutige versionierte Erstattungsparameter erwartet')
    parts = path.split('/'); event_id = parts[5]; action = parts[6] if len(parts) > 6 else 'state'; api = VersionedRefundOrigins(office)
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
                result = api.origins(actor, event_id, _hash_input(query.get('portion_id')), limit, offset)
            else:
                result = getattr(api, action)(actor, event_id, limit, offset)
        return result, 200, 'application/json'
    if '_query' in data:
        raise Problem(400, 'Keine zusätzlichen Filter erlaubt')
    return getattr(api, action)(actor, event_id, data), (201 if action == 'confirm' else 200), 'application/json'
