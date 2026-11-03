"""Explicit versioned preparation facts; no tax rules or cash classification."""
from functools import wraps
import json
import re
import sqlite3
import uuid

from core import Problem, canonical
from business_accounting import Accounting, _hash, _page, _paged, _sha
from business_operations import Domain, identifier, instant, iso_date, transaction


FEATURES = ('accounting_preparation_profile',)
_TABLES = ('business_accounting_profile_versions', 'business_accounting_profile_requests')
_PROFILE = {'legal_form', 'accounting_method', 'vat_regime', 'vat_timing', 'vat_effective_from', 'bookkeeping_start'}
_INPUT = {'expected_revision', 'state_hash', 'profile', 'reason', 'evidence_reference'}
_FLAGS = dict(scope='organization_profile', tax_status='unconfigured', tax_result_available=False)
_ENTRY = (_INPUT-{'expected_revision', 'state_hash'}) | set(_FLAGS) | {
    'preview_hash', 'id', 'revision', 'previous_state_hash', 'created_by', 'created_at'}


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BLOB', 'BYTEA'):
        raise ValueError('Unsupported binary type')
    return [
        '''CREATE TABLE IF NOT EXISTS business_accounting_profile_versions(
        id TEXT PRIMARY KEY, revision INTEGER NOT NULL UNIQUE CHECK(revision>0),
        previous_state_hash TEXT NOT NULL CHECK(length(previous_state_hash)=64),
        entry_json TEXT NOT NULL, entry_sha256 TEXT NOT NULL CHECK(length(entry_sha256)=64),
        created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_accounting_profile_requests(
        user_id TEXT NOT NULL REFERENCES users(id), request_id TEXT NOT NULL,
        request_json TEXT NOT NULL, request_hash TEXT NOT NULL CHECK(length(request_hash)=64),
        entry_id TEXT NOT NULL UNIQUE REFERENCES business_accounting_profile_versions(id),
        PRIMARY KEY(user_id,request_id))''',
    ]


def protected_tables():
    return _TABLES


def runtime_privileges():
    return {table: ('SELECT', 'INSERT') for table in _TABLES}


def guard_statements(dialect):
    if dialect == 'sqlite':
        guards = [f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} ON {table} "
                  "BEGIN SELECT RAISE(ABORT,'immutable accounting preparation profile'); END"
                  for table in _TABLES for action in ('UPDATE', 'DELETE')]
        for table, condition in zip(_TABLES, ('id=NEW.id OR revision=NEW.revision',
                '(user_id=NEW.user_id AND request_id=NEW.request_id) OR entry_id=NEW.entry_id')):
            guards.append(f'CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} '
                          f'WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition}) '
                          "BEGIN SELECT RAISE(ABORT,'immutable accounting preparation profile'); END")
        return guards
    if dialect != 'postgresql':
        raise ValueError('Unsupported guard dialect')
    guards = ["""CREATE OR REPLACE FUNCTION business_accounting_profile_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'immutable accounting preparation profile'; END; $$"""]
    for table in _TABLES:
        for action in ('UPDATE', 'DELETE'):
            name = table+'_'+action.lower()+'_guard'
            guards.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) "
                          f"THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION "
                          "business_accounting_profile_immutable_guard(); END IF; END $$")
    return guards


def _stored(method):
    @wraps(method)
    def checked(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except Problem as error:
            if error.status != 400:
                raise
            raise Problem(409, 'Gespeichertes Vorbereitungsprofil besteht die Integritätsprüfung nicht') from None
        except (ValueError, KeyError, TypeError, ArithmeticError):
            raise Problem(409, 'Gespeichertes Vorbereitungsprofil besteht die Integritätsprüfung nicht') from None
    return checked


@_stored
def installed(office):
    from business_schema import _tables
    from business_accounting_refunds_v2 import installed as refunds_installed
    tables = _tables(office); present = set(_TABLES) & tables
    marker = ('business_schema_migrations' in tables and office.db.execute(
        "SELECT 1 FROM business_schema_migrations WHERE module='business_accounting_profile'").fetchone())
    if not present and not marker:
        return False
    if present != set(_TABLES) or not marker or not refunds_installed(office):
        raise Problem(409, 'Vorbereitungsprofil oder seine Abhängigkeiten sind unvollständig installiert')
    return True


def _state_hash(revision, head=None):
    return _sha(canonical(dict(schema_version=1, revision=revision, head=head)))


class AccountingPreparationProfile(Domain):
    def _access(self, actor, write=False):
        fresh = Accounting(self.office)._access(actor, 'accounting.admin' if write else None)
        if not installed(self.office):
            raise Problem(409, 'Vorbereitungsprofil ist nicht installiert')
        return fresh

    def _gate(self):
        Accounting(self.office)._write_gate()

    def _writes_allowed(self, actor):
        try:
            self._access(actor, True); self._gate()
            return True
        except Problem as error:
            if error.status not in (403, 409, 423):
                raise
            return False

    @staticmethod
    def _inputs(data, confirm=False):
        expected = _INPUT | ({'request_id', 'preview_hash', 'confirmation'} if confirm else set())
        if not isinstance(data, dict) or set(data) != expected:
            raise Problem(400, 'Vollständige bekannte Profilfelder erwartet')
        if type(data['expected_revision']) is not int or data['expected_revision'] < 0:
            raise Problem(400, 'Nichtnegative Profilrevision erwartet')
        _hash(data['state_hash'])
        if confirm:
            identifier(data['request_id'], 'request_id'); _hash(data['preview_hash'])
            if data['confirmation'] is not True:
                raise Problem(400, 'Vorbereitungsprofil ausdrücklich bestätigen')
        profile = data['profile']
        if not isinstance(profile, dict) or set(profile) != _PROFILE:
            raise Problem(400, 'Vollständige bekannte Vorbereitungsangaben erwartet')
        if profile['legal_form'] != 'sole_proprietorship' or profile['accounting_method'] != 'euer':
            raise Problem(400, 'Unterstützt wird Einzelunternehmen mit EÜR')
        if (profile['vat_regime'] not in (None, 'small_business', 'regular')
                or profile['vat_timing'] not in (None, 'accrual', 'cash')
                or profile['vat_regime'] != 'regular' and profile['vat_timing'] is not None
                or profile['vat_regime'] is None and profile['vat_effective_from'] is not None):
            raise Problem(400, 'Zueinander passende ausdrückliche Umsatzsteuerangaben erwartet')
        for name in ('vat_effective_from', 'bookkeeping_start'):
            if profile[name] is not None:
                iso_date(profile[name], name)
        for name, maximum in (('reason', 1000), ('evidence_reference', 200)):
            value = data[name]
            if (not isinstance(value, str) or not 1 <= len(value) <= maximum or not value.strip()
                    or any(ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF for char in value)):
                raise Problem(400, 'Begrenzter einzeiliger Text erwartet: '+name)

    @staticmethod
    def _request_hash(data):
        return _sha(canonical(['profile.confirm', None, data]))

    @staticmethod
    def _preview(data):
        value = dict({key: data[key] for key in _INPUT}, **_FLAGS)
        value['profile'] = dict(data['profile'])
        return dict(value, preview_hash=_sha(canonical(value)))

    @_stored
    def _ledger(self):
        rows = self.office.db.execute('SELECT * FROM business_accounting_profile_versions ORDER BY revision,id').fetchall()
        receipts = self.office.db.execute('SELECT * FROM business_accounting_profile_requests').fetchall()
        if len(rows) != len(receipts):
            raise ValueError('Every profile version requires exactly one receipt')
        requests = {row['entry_id']: row for row in receipts}
        if len(requests) != len(receipts):
            raise ValueError('Duplicate profile version receipt')
        entries = []; state_hash = _state_hash(0)
        for revision, row in enumerate(rows, 1):
            value = json.loads(row['entry_json'])
            if (not isinstance(value, dict) or set(value) != _ENTRY or canonical(value) != row['entry_json']
                    or _sha(row['entry_json']) != row['entry_sha256'] or type(row['revision']) is not int
                    or row['revision'] != revision or type(value['revision']) is not int or value['revision'] != revision
                    or any(value[key] != row[key] for key in ('id', 'previous_state_hash', 'created_by', 'created_at'))
                    or row['previous_state_hash'] != state_hash or any(value[key] != expected for key, expected in _FLAGS.items())
                    or value['tax_result_available'] is not False or instant(row['created_at']) != row['created_at']):
                raise ValueError('Changed preparation profile or previous prefix')
            identifier(row['id']); identifier(row['created_by']); _hash(row['entry_sha256'])
            data = dict(expected_revision=revision-1, state_hash=state_hash,
                        **{key: value[key] for key in ('profile', 'reason', 'evidence_reference')})
            self._inputs(data)
            preview = self._preview(data)
            if value['preview_hash'] != preview['preview_hash']:
                raise ValueError('Changed profile preview')
            receipt = requests.get(row['id'])
            if not receipt:
                raise ValueError('Missing original profile receipt')
            command = json.loads(receipt['request_json'])
            self._inputs(command, True)
            expected = dict(data, request_id=receipt['request_id'], preview_hash=preview['preview_hash'], confirmation=True)
            if (canonical(command) != receipt['request_json'] or command != expected
                    or receipt['user_id'] != row['created_by'] or self._request_hash(command) != receipt['request_hash']):
                raise ValueError('Changed original profile request')
            entries.append(value)
            state_hash = _state_hash(revision, dict(id=row['id'], entry_sha256=row['entry_sha256']))
        return dict(entries=entries, revision=len(entries), state_hash=state_hash)

    def state(self, actor):
        with transaction(self.office):
            fresh = self._access(actor); ledger = self._ledger()
            return dict(revision=ledger['revision'], state_hash=ledger['state_hash'],
                        preparation_status='recorded' if ledger['entries'] else 'unrecorded',
                        current=ledger['entries'][-1] if ledger['entries'] else None,
                        writes_allowed=self._writes_allowed(fresh), **_FLAGS)

    def history(self, actor, limit=50, offset=0):
        _page(limit, offset)
        with transaction(self.office):
            self._access(actor)
            return dict(_paged(list(reversed(self._ledger()['entries'])), limit, offset), scope='organization_profile')

    def _prepare(self, ledger, data):
        if data['expected_revision'] != ledger['revision'] or data['state_hash'] != ledger['state_hash']:
            raise Problem(409, 'Vorbereitungsprofil wurde geändert; erneut prüfen')
        return self._preview(data)

    def preview(self, actor, data):
        self._inputs(data)
        with transaction(self.office):
            self._access(actor, True); self._gate()
            return self._prepare(self._ledger(), data)

    def confirm(self, actor, data):
        self._inputs(data, True)
        with transaction(self.office):
            fresh = self._access(actor, True); self._gate(); ledger = self._ledger()
            digest = self._request_hash(data)
            receipt = self.office.db.execute('SELECT * FROM business_accounting_profile_requests WHERE user_id=? AND request_id=?',
                                            (fresh['id'], data['request_id'])).fetchone()
            if receipt:
                if receipt['request_hash'] != digest:
                    raise Problem(409, 'Vorgangs-ID wurde mit anderem Inhalt verwendet')
                return next(value for value in ledger['entries'] if value['id'] == receipt['entry_id'])
            try:
                preview = self._prepare(ledger, data)
                if preview['preview_hash'] != data['preview_hash']:
                    raise Problem(409, 'Passende aktuelle Profilvorschau erforderlich')
            except Problem as error:
                if error.status != 409:
                    raise
                raise Problem(409, error.message, request_resolution='not_accepted') from None
            value = {key: item for key, item in preview.items() if key not in ('expected_revision', 'state_hash')}
            value.update(id=uuid.uuid4().hex, revision=ledger['revision']+1, previous_state_hash=ledger['state_hash'],
                         created_by=fresh['id'], created_at=self.now())
            encoded = canonical(value)
            self.office.db.execute('INSERT INTO business_accounting_profile_versions '
                '(id,revision,previous_state_hash,entry_json,entry_sha256,created_by,created_at) VALUES(?,?,?,?,?,?,?)',
                (value['id'], value['revision'], value['previous_state_hash'], encoded, _sha(encoded), value['created_by'], value['created_at']))
            self.office.db.execute('INSERT INTO business_accounting_profile_requests '
                '(user_id,request_id,request_json,request_hash,entry_id) VALUES(?,?,?,?,?)',
                (fresh['id'], data['request_id'], canonical(data), digest, value['id']))
            self.office.audit(fresh, 'business.accounting.preparation_profile_confirmed', value['id'])
            return value


def validate_integrity(office):
    try:
        if not installed(office):
            return True
        AccountingPreparationProfile(office)._ledger()
        if isinstance(office.db, sqlite3.Connection):
            normalize = lambda value: re.sub(r'\s+', ' ', value.replace('IF NOT EXISTS ', '')).strip().lower()
            for statement in guard_statements('sqlite'):
                name = re.search(r'CREATE TRIGGER IF NOT EXISTS (\w+)', statement)[1]
                row = office.db.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?", (name,)).fetchone()
                if not row or normalize(row[0]) != normalize(statement):
                    raise ValueError('Missing or changed preparation profile guard')
        else:
            from business_documents import _validate_pg_guards
            _validate_pg_guards(office.db, guard_statements('postgresql'))
    except (Problem, KeyError, TypeError, ArithmeticError) as error:
        raise ValueError('Invalid accounting preparation profile history') from error
    return True


def restore_horizon(office):
    with office.lock:
        if not installed(office):
            return None
        validate_integrity(office)
        tables = {table: sorted((dict(row) for row in office.db.execute('SELECT * FROM '+table).fetchall()), key=canonical) for table in _TABLES}
        return dict(schema_version=1, table_counts={table: len(rows) for table, rows in tables.items()},
                    sha256=_sha(canonical(dict(schema_version=1, tables=tables))))


def methods(path):
    match = re.fullmatch(r'/accounting/profile(/(?:history|preview|confirm))?', path)
    return ('POST' if match[1] in ('/preview', '/confirm') else 'GET') if match else None


def dispatch(office, actor, path, method, data):
    allowed = methods(path)
    if allowed is None:
        return None
    if method != allowed:
        raise Problem(405, 'Methode nicht unterstützt')
    if not isinstance(data, dict) or not isinstance(data.get('_query', {}), dict):
        raise Problem(400, 'Eindeutige Profilparameter erwartet')
    action = path.removeprefix('/accounting/profile').lstrip('/') or 'state'
    api = AccountingPreparationProfile(office)
    if method == 'GET':
        if set(data)-{'_query'}:
            raise Problem(400, 'GET erwartet keinen Anfragekörper')
        query = data.get('_query', {})
        if action == 'state':
            if query:
                raise Problem(400, 'Keine zusätzlichen Filter erlaubt')
            result = api.state(actor)
        else:
            if (set(query)-{'limit', 'offset'} or any(not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,6}', value)
                                                       for value in query.values())):
                raise Problem(400, 'Nur eindeutige bekannte Listenfilter erwartet')
            result = api.history(actor, int(query.get('limit', '50')), int(query.get('offset', '0')))
        return result, 200, 'application/json'
    if '_query' in data:
        raise Problem(400, 'Keine zusätzlichen Filter erlaubt')
    return getattr(api, action)(actor, data), (201 if action == 'confirm' else 200), 'application/json'
