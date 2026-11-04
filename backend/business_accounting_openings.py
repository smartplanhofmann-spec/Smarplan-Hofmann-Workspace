"""Evidenced opening balances: retained originals, no money or tax posting.

An opening balance is a state at the beginning of the explicitly configured
bookkeeping date. It never substitutes for a bank transaction or an EÜR entry.
"""
import base64
import binascii
from datetime import date, datetime, timedelta, timezone
from functools import wraps
import hashlib
import json
import re
import sqlite3
import uuid
from zoneinfo import ZoneInfo

from core import Problem, canonical
from business_accounting import Accounting
from business_accounting_profile import AccountingPreparationProfile
from business_foundation import require_permission
from business_operations import identifier, instant, iso_date, transaction, _image_check


FEATURES = ('accounting_opening_balances',)
RULE_VERSION = 'account_opening_balances_v1'
TABLES = tuple('business_accounting_opening_' + name for name in ('originals', 'events', 'requests'))
MAX_FILE = 5 * 1024 * 1024
ID = r'[a-f0-9]{32}'
BASE = '/accounting/opening-balances'
INPUT = {'expected_revision', 'state_hash', 'account_id', 'account_revision', 'profile_ref',
         'status', 'opening_date', 'amount', 'source', 'reason'}
FLAGS = dict(schema_version=1, rule_version=RULE_VERSION, cash_flow_created=False, tax_postings_created=False,
             balance_timing='start_of_day', timezone='Europe/Berlin')


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA', 'BLOB'):
        raise ValueError('Unsupported opening balance binary type')
    return [
        f'''CREATE TABLE IF NOT EXISTS business_accounting_opening_originals(
        id TEXT PRIMARY KEY,account_id TEXT NOT NULL REFERENCES business_accounting_accounts(id),
        filename TEXT NOT NULL,media_type TEXT NOT NULL,size INTEGER NOT NULL CHECK(size>0),sha256 TEXT NOT NULL,
        original {binary_type} NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
        UNIQUE(account_id,sha256))''',
        '''CREATE TABLE IF NOT EXISTS business_accounting_opening_events(
        id TEXT PRIMARY KEY,sequence INTEGER NOT NULL UNIQUE CHECK(sequence>0),
        account_id TEXT NOT NULL REFERENCES business_accounting_accounts(id),revision INTEGER NOT NULL CHECK(revision>0),
        previous_hash TEXT,payload_json TEXT NOT NULL,content_hash TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,UNIQUE(account_id,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_accounting_opening_requests(
        user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,operation TEXT NOT NULL,
        request_json TEXT NOT NULL,request_hash TEXT NOT NULL,result_json TEXT NOT NULL,
        PRIMARY KEY(user_id,request_id))''',
    ]


def protected_tables():
    return TABLES


def runtime_privileges():
    return {table: ('SELECT', 'INSERT') for table in TABLES}


def guard_statements(dialect):
    if dialect == 'sqlite':
        guards = [f"CREATE TRIGGER IF NOT EXISTS {table}_{op.lower()}_guard BEFORE {op} ON {table} "
                  "BEGIN SELECT RAISE(ABORT,'immutable opening balance evidence'); END"
                  for table in TABLES for op in ('UPDATE', 'DELETE')]
        conditions = ('id=NEW.id OR (account_id=NEW.account_id AND sha256=NEW.sha256)',
                      'id=NEW.id OR sequence=NEW.sequence OR (account_id=NEW.account_id AND revision=NEW.revision)',
                      'user_id=NEW.user_id AND request_id=NEW.request_id')
        return guards + [f'CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} '
                         f'WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition}) '
                         "BEGIN SELECT RAISE(ABORT,'immutable opening balance evidence'); END"
                         for table, condition in zip(TABLES, conditions)]
    if dialect != 'postgresql':
        raise ValueError('Unsupported opening balance dialect')
    guards = ["CREATE OR REPLACE FUNCTION business_accounting_opening_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable opening balance evidence'; END; $$"]
    for table in TABLES:
        for op in ('UPDATE', 'DELETE'):
            name = table + '_' + op.lower() + '_guard'
            guards.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} BEFORE {op} ON {table} FOR EACH ROW EXECUTE FUNCTION business_accounting_opening_immutable_guard(); END IF; END $$")
    return guards


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value).encode()).hexdigest()


def shape(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise Problem(400, 'Vollständige bekannte Anfangsbestandsfelder erforderlich.')


def hash_value(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{64}', value):
        raise Problem(400, 'Gültige Prüfsumme erforderlich.')
    return value


def integer(value, minimum=0):
    if type(value) is not int or not minimum <= value <= 2147483646:
        raise Problem(400, 'Gültige ganze Fassung erforderlich.')
    return value


def cents(value):
    if not isinstance(value, str) or not re.fullmatch(r'-?(?:0|[1-9][0-9]{0,10})\.[0-9]{2}', value) or value == '-0.00':
        raise Problem(400, 'Exakten EUR-Centbetrag ohne Tausendertrennzeichen angeben.')
    negative = value.startswith('-')
    whole, fraction = value.lstrip('-').split('.')
    return (-1 if negative else 1) * (int(whole) * 100 + int(fraction))


def money(value):
    return ('-' if value < 0 else '') + str(abs(value) // 100) + '.' + str(abs(value) % 100).zfill(2)


def line(value, label, maximum=1000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or any(ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise Problem(400, 'Begrenzter einzeiliger Text erforderlich: ' + label)
    return value


def profile_reference(value):
    return dict(id=value['id'], revision=value['revision'], entry_sha256=sha(value))


def event_reference(value):
    return dict(id=value['id'], revision=value['revision'], content_hash=value['content_hash'])


def state_hash(entries):
    return sha(dict(schema_version=1, revision=len(entries), head=entries[-1]['content_hash'] if entries else None))


def stored(method):
    @wraps(method)
    def checked(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except Problem as error:
            if error.status != 400:
                raise
            raise Problem(409, 'Gespeicherter Anfangsbestandsnachweis ist ungültig.') from None
        except (ValueError, KeyError, TypeError, ArithmeticError):
            raise Problem(409, 'Gespeicherter Anfangsbestandsnachweis ist ungültig.') from None
    return checked


def installed(office):
    from business_schema import _tables
    tables = _tables(office)
    present = set(TABLES) & tables
    marker = 'business_schema_migrations' in tables and office.db.execute(
        "SELECT 1 FROM business_schema_migrations WHERE module='business_accounting_openings'").fetchone()
    if not present and not marker:
        return False
    if present != set(TABLES) or not marker:
        raise Problem(409, 'Anfangsbestandsmodul ist unvollständig installiert.')
    for dependency in ('business_accounting_euer', 'business_bank_reconciliation', 'business_travel_allowances'):
        if not office.db.execute('SELECT 1 FROM business_schema_migrations WHERE module=?', (dependency,)).fetchone():
            raise Problem(409, 'Abhängigkeiten der Anfangsbestände sind unvollständig installiert.')
    return True


class OpeningBalances:
    def __init__(self, office, *, clock=None):
        self.office = office
        self.db = office.db
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def now(self):
        return self.clock().astimezone(timezone.utc).isoformat(timespec='seconds')

    def _lock(self):
        if not isinstance(self.db, sqlite3.Connection):
            # Same global accounting transaction lock used by bank operations.
            self.db.execute('SELECT pg_advisory_xact_lock(129842776,18494302)')

    def _access(self, actor, write=False):
        fresh = Accounting(self.office)._access(actor, 'accounting.admin' if write else None)
        require_permission(self.office, fresh, 'bank.read')
        if write:
            require_permission(self.office, fresh, 'accounting.prepare')
            require_permission(self.office, fresh, 'finance.write')
        if not installed(self.office):
            raise Problem(409, 'Anfangsbestandsmodul ist nicht installiert.')
        return fresh

    def _gate(self):
        from business_schema import require_capability
        require_capability(self.office, 'business_accounting_openings')
        Accounting(self.office)._write_gate()

    def _profile(self, reference=None, *, optional=False):
        entries = AccountingPreparationProfile(self.office)._ledger()['entries']
        value = next((entry for entry in entries if reference is not None and profile_reference(entry) == reference), None) if reference else (entries[-1] if entries else None)
        if not value or value['profile']['legal_form'] != 'sole_proprietorship' or value['profile']['accounting_method'] != 'euer' or value['profile']['bookkeeping_start'] is None:
            if optional:
                return None
            raise Problem(409, 'Ausdrücklich datiertes Buchführungsprofil erforderlich.')
        return value

    @stored
    def _original(self, original_id, *, require_receipt=True):
        identifier(original_id)
        row = self.db.execute('SELECT * FROM business_accounting_opening_originals WHERE id=?', (original_id,)).fetchone()
        if not row:
            raise Problem(404, 'Anfangsbestandsoriginal nicht verfügbar.')
        raw = bytes(row['original'])
        if len(raw) != row['size'] or sha(raw) != row['sha256'] or not 1 <= len(raw) <= MAX_FILE:
            raise Problem(409, 'Anfangsbestandsoriginal besteht die Integritätsprüfung nicht.')
        if row['media_type'] not in ('application/pdf', 'image/png', 'image/jpeg'):
            raise Problem(409, 'Unbekanntes Originalformat.')
        _image_check(raw, row['media_type'])
        value = {key: row[key] for key in ('id', 'account_id', 'filename', 'media_type', 'size', 'sha256', 'created_by', 'created_at')}
        identifier(value['account_id']); identifier(value['created_by']); instant(value['created_at'])
        line(value['filename'], 'Dateiname', 200)
        if '/' in value['filename'] or '\\' in value['filename']:
            raise Problem(409, 'Ungültiger Originaldateiname.')
        if require_receipt:
            accepted = False
            for receipt in self.db.execute("SELECT * FROM business_accounting_opening_requests WHERE operation='original'"):
                result = json.loads(receipt['result_json']); shape(result, ('original_id',))
                if result['original_id'] != original_id:
                    continue
                command = json.loads(receipt['request_json'])
                shape(command, ('request_id', 'account_id', 'filename', 'media_type', 'size', 'sha256'))
                if (canonical(command) != receipt['request_json'] or command['request_id'] != receipt['request_id']
                        or sha(['original', command]) != receipt['request_hash']
                        or any(command[key] != value[key] for key in ('account_id', 'filename', 'media_type', 'size', 'sha256'))):
                    raise Problem(409, 'Originalannahmequittung ist nicht reproduzierbar.')
                accepted |= receipt['user_id'] == value['created_by']
            if not accepted:
                raise Problem(409, 'Ursprüngliche Originalannahmequittung fehlt.')
        return dict(value, path=BASE + '/originals/' + value['id']), raw

    def _request(self, actor, operation, data):
        identifier(data['request_id'])
        digest = sha([operation, data])
        row = self.db.execute('SELECT * FROM business_accounting_opening_requests WHERE user_id=? AND request_id=?', (actor['id'], data['request_id'])).fetchone()
        if row and (row['operation'] != operation or row['request_hash'] != digest or json.loads(row['request_json']) != data):
            raise Problem(409, 'Vorgangs-ID wurde mit anderem Inhalt verwendet.')
        return digest, json.loads(row['result_json']) if row else None

    def _remember(self, actor, operation, data, digest, result):
        self.db.execute('INSERT INTO business_accounting_opening_requests(user_id,request_id,operation,request_json,request_hash,result_json) VALUES(?,?,?,?,?,?)',
                        (actor['id'], data['request_id'], operation, canonical(data), digest, canonical(result)))

    def upload_original(self, actor, data):
        shape(data, ('request_id', 'account_id', 'filename', 'media_type', 'content_base64'))
        identifier(data['request_id']); identifier(data['account_id']); line(data['filename'], 'Dateiname', 200)
        if '/' in data['filename'] or '\\' in data['filename'] or data['media_type'] not in ('application/pdf', 'image/png', 'image/jpeg'):
            raise Problem(400, 'Einfacher Dateiname und PDF, PNG oder JPEG erforderlich.')
        if not isinstance(data['content_base64'], str) or len(data['content_base64']) > ((MAX_FILE + 2) // 3) * 4:
            raise Problem(413, 'Originaldatei darf höchstens 5 MiB haben.')
        try:
            raw = base64.b64decode(data['content_base64'], validate=True)
        except (ValueError, binascii.Error):
            raise Problem(400, 'Gültige Base64-Originaldatei erforderlich.') from None
        if not 1 <= len(raw) <= MAX_FILE:
            raise Problem(413, 'Originaldatei benötigt 1 Byte bis 5 MiB.')
        _image_check(raw, data['media_type'])
        safe = {key: value for key, value in data.items() if key != 'content_base64'}
        safe.update(size=len(raw), sha256=sha(raw))
        with transaction(self.office):
            self._lock(); fresh = self._access(actor, True); self._gate()
            digest, replay = self._request(fresh, 'original', safe)
            if replay:
                return self._original(replay['original_id'])[0]
            account = Accounting(self.office)._account(data['account_id'])
            if not account['active']:
                raise Problem(409, 'Aktives Geldkonto erforderlich.', request_resolution='not_accepted')
            old = self.db.execute('SELECT id FROM business_accounting_opening_originals WHERE account_id=? AND sha256=?', (account['id'], safe['sha256'])).fetchone()
            if old:
                value = self._original(old['id'])[0]
                if any(value[key] != safe[key] for key in ('filename', 'media_type', 'size')):
                    raise Problem(409, 'Dasselbe Original ist bereits mit anderen Metadaten gespeichert.', request_resolution='not_accepted')
            else:
                original_id = uuid.uuid4().hex
                self.db.execute('INSERT INTO business_accounting_opening_originals(id,account_id,filename,media_type,size,sha256,original,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                                (original_id, account['id'], safe['filename'], safe['media_type'], safe['size'], safe['sha256'], raw, fresh['id'], self.now()))
                value = self._original(original_id, require_receipt=False)[0]
            self._remember(fresh, 'original', safe, digest, dict(original_id=value['id']))
            self.office.audit(fresh, 'business.accounting.opening_original', value['id'])
            return value

    def original(self, actor, original_id):
        from workspace_api import BinaryAttachment
        with transaction(self.office):
            self._access(actor)
            value, raw = self._original(original_id)
            self._access(actor)
            return BinaryAttachment(raw, value['filename']), value['media_type']

    @stored
    def _bank_statement(self, statement_id):
        from business_bank_reconciliation import BankReconciliation
        identifier(statement_id)
        row = self.db.execute('SELECT * FROM business_bank_statements WHERE id=?', (statement_id,)).fetchone()
        event = BankReconciliation(self.office)._event(row, 'statement')
        if sha(bytes(row['original'])) != event['file_sha256']:
            raise Problem(409, 'Bankoriginal besteht die Integritätsprüfung nicht.')
        return event

    def _source(self, account, opening_date, amount, source):
        if not isinstance(source, dict):
            raise Problem(400, 'Beleggebundene Anfangsbestandsquelle erforderlich.')
        if source.get('kind') == 'bank_statement':
            shape(source, ('kind', 'statement_id', 'content_hash', 'balance_side'))
            if account['kind'] != 'bank' or source['balance_side'] not in ('opening', 'closing'):
                raise Problem(400, 'Passenden Anfangs- oder Endsaldo eines Bankauszugs wählen.')
            hash_value(source['content_hash'])
            event = self._bank_statement(source['statement_id'])
            if event['account_id'] != account['id'] or event['content_hash'] != source['content_hash']:
                raise Problem(409, 'Bankauszug gehört nicht zum gewählten Geldkonto oder Quellenstand.')
            metadata = event['payload']
            day = metadata['period_from'] if source['balance_side'] == 'opening' else (date.fromisoformat(metadata['period_to']) + timedelta(days=1)).isoformat()
            derived = metadata[source['balance_side'] + '_balance']
            if day != opening_date or derived != amount:
                raise Problem(409, 'Stichtag und Anfangsbetrag müssen dem unveränderten Bankauszug entsprechen.')
            return dict(kind='bank_statement', statement_id=event['id'], content_hash=event['content_hash'],
                        file_sha256=event['file_sha256'], account_id=account['id'], balance_side=source['balance_side'],
                        period_from=metadata['period_from'], period_to=metadata['period_to'], amount=derived,
                        statement_reference=metadata['statement_reference'], source_path='/bank/statements/' + event['id'] + '/original')
        if source.get('kind') != 'original':
            raise Problem(400, 'Bankauszug oder gespeichertes Anfangsbestandsoriginal erforderlich.')
        shape(source, ('kind', 'original_id', 'sha256', 'evidence_type', 'at_start_of_day'))
        hash_value(source['sha256'])
        if source['at_start_of_day'] is not True or source['evidence_type'] != ('cash_count' if account['kind'] == 'cash' else 'account_statement'):
            raise Problem(400, 'Passenden Beleg und Bestand vor der ersten Bewegung des Stichtags ausdrücklich bestätigen.')
        original = self._original(source['original_id'])[0]
        if original['account_id'] != account['id'] or original['sha256'] != source['sha256']:
            raise Problem(409, 'Original gehört nicht zum bestätigten Konto oder Quellenstand.')
        return dict(kind='original', original=original, evidence_type=source['evidence_type'],
                    opening_date=opening_date, amount=amount, at_start_of_day=True, source_path=original['path'])

    @staticmethod
    def _inputs(data, confirm=False):
        shape(data, INPUT | ({'request_id', 'preview_hash', 'confirmation'} if confirm else set()))
        integer(data['expected_revision']); hash_value(data['state_hash'])
        identifier(data['account_id']); integer(data['account_revision'], 1)
        shape(data['profile_ref'], ('id', 'revision', 'entry_sha256'))
        identifier(data['profile_ref']['id']); integer(data['profile_ref']['revision'], 1); hash_value(data['profile_ref']['entry_sha256'])
        if data['status'] not in ('active', 'void'):
            raise Problem(400, 'Bestätigung oder ausdrückliche Aufhebung auswählen.')
        iso_date(data['opening_date']); cents(data['amount']); line(data['reason'], 'Prüf-/Korrekturgrund')
        if confirm:
            identifier(data['request_id']); hash_value(data['preview_hash'])
            if data['confirmation'] is not True:
                raise Problem(400, 'Geprüften Anfangsbestand ausdrücklich bestätigen.')

    def _connections(self, account_id, opening_date, amount):
        expected = cents(amount)
        for row in self.db.execute('SELECT id FROM business_bank_statements WHERE account_id=?', (account_id,)):
            event = self._bank_statement(row['id']); metadata = event['payload']
            if metadata['period_from'] == opening_date and cents(metadata['opening_balance']) != expected:
                raise Problem(409, 'Anfangsbestand widerspricht einem vorhandenen Bankauszugsanfang.')
            if (date.fromisoformat(metadata['period_to']) + timedelta(days=1)).isoformat() == opening_date and cents(metadata['closing_balance']) != expected:
                raise Problem(409, 'Anfangsbestand widerspricht dem vorhandenen Vorperioden-Endsaldo.')

    def _open(self, days):
        from business_accounting_euer import EuerAccounting
        earliest = min(days)[:7]
        if any(period >= earliest and value['status'] == 'closed' for period, value in EuerAccounting(self.office)._ledger()['periods'].items()):
            raise Problem(409, 'Betroffene EÜR-Perioden vor Änderung des Anfangsbestands begründet wieder öffnen.')

    def _prepare(self, ledger, data, *, historical=False):
        self._inputs(data)
        if data['expected_revision'] != len(ledger['entries']) or data['state_hash'] != state_hash(ledger['entries']):
            raise Problem(409, 'Anfangsbestandsjournal wurde geändert; Vorschau erneut prüfen.')
        old = ledger['current'].get(data['account_id'])
        account = Accounting(self.office)._account(data['account_id'], data['account_revision'])
        profile = self._profile(data['profile_ref'])
        if data['opening_date'] != profile['profile']['bookkeeping_start']:
            raise Problem(409, 'Anfangsbestand muss genau am bestätigten Buchführungsbeginn liegen.')
        if account['kind'] == 'cash' and cents(data['amount']) < 0:
            raise Problem(400, 'Ein gezählter Kassenbestand darf nicht negativ sein.')
        if data['status'] == 'void':
            if not old or old['status'] != 'active':
                raise Problem(409, 'Nur einen bestätigten Anfangsbestand ausdrücklich aufheben.')
            if any(data[key] != old[key] for key in ('account_revision', 'profile_ref', 'opening_date', 'amount', 'source')):
                raise Problem(409, 'Eine Aufhebung muss den unveränderten früheren Quellenstand binden.')
        elif not historical:
            if account != Accounting(self.office)._account(data['account_id']) or not account['active']:
                raise Problem(409, 'Aktuelle aktive Geldkontofassung erforderlich.')
            if data['profile_ref'] != profile_reference(self._profile()):
                raise Problem(409, 'Buchführungsprofil wurde geändert; Quellen erneut prüfen.')
            if data['opening_date'] > self.clock().astimezone(ZoneInfo('Europe/Berlin')).date().isoformat():
                raise Problem(409, 'Ein tatsächlicher Anfangsbestand darf nicht in der Zukunft liegen.')
            self._connections(account['id'], data['opening_date'], data['amount'])
        proof = self._source(account, data['opening_date'], data['amount'], data['source'])
        if not historical:
            self._open([data['opening_date']] + ([old['opening_date']] if old else []))
        value = dict({key: data[key] for key in INPUT}, **FLAGS, account=account, profile=profile,
                     source_proof=proof, previous_ref=event_reference(old) if old else None)
        return dict(value, preview_hash=sha(value))

    @stored
    def _ledger(self):
        ledger = dict(entries=[], current={}, by_id={})
        receipts = self.db.execute("SELECT * FROM business_accounting_opening_requests WHERE operation='confirm'").fetchall()
        receipt_map = {}
        for row in receipts:
            result = json.loads(row['result_json']); shape(result, ('entry_id',))
            if result['entry_id'] in receipt_map:
                raise Problem(409, 'Doppelte Anfangsbestandsquittung.')
            receipt_map[result['entry_id']] = row
        for row in self.db.execute('SELECT * FROM business_accounting_opening_events ORDER BY sequence'):
            value = json.loads(row['payload_json']); previous = ledger['entries'][-1]['content_hash'] if ledger['entries'] else None
            if (canonical(value) != row['payload_json'] or sha(value) != row['content_hash']
                    or any(value.get(key) != row[key] for key in ('id', 'sequence', 'account_id', 'revision', 'previous_hash', 'created_by', 'created_at'))
                    or row['sequence'] != len(ledger['entries']) + 1 or row['previous_hash'] != previous):
                raise Problem(409, 'Anfangsbestandsjournal besteht die Integritätsprüfung nicht.')
            old = ledger['current'].get(row['account_id'])
            if row['revision'] != (old['revision'] + 1 if old else 1):
                raise Problem(409, 'Anfangsbestandsfassungen sind nicht lückenlos.')
            identifier(row['id']); identifier(row['created_by']); instant(row['created_at'])
            receipt = receipt_map.get(row['id'])
            if not receipt:
                raise Problem(409, 'Ursprüngliche Anfangsbestandsquittung fehlt.')
            command = json.loads(receipt['request_json']); self._inputs(command, True)
            if (canonical(command) != receipt['request_json'] or command['request_id'] != receipt['request_id']
                    or receipt['user_id'] != row['created_by'] or sha(['confirm', command]) != receipt['request_hash']):
                raise Problem(409, 'Ursprünglicher Anfangsbestandsauftrag wurde verändert.')
            preview = self._prepare(ledger, {key: command[key] for key in INPUT}, historical=True)
            expected = dict(preview, id=row['id'], sequence=row['sequence'], revision=row['revision'], previous_hash=previous,
                            created_by=row['created_by'], created_at=row['created_at'])
            if value != expected or command['preview_hash'] != preview['preview_hash']:
                raise Problem(409, 'Anfangsbestand ist nicht aus seinen Originalen reproduzierbar.')
            value = dict(value, content_hash=row['content_hash'])
            ledger['entries'].append(value); ledger['current'][row['account_id']] = value; ledger['by_id'][row['id']] = value
        if len(receipt_map) != len(ledger['entries']):
            raise Problem(409, 'Verwaiste Anfangsbestandsquittung.')
        return ledger

    def state(self, actor):
        with transaction(self.office):
            fresh = self._access(actor); ledger = self._ledger()
            profile = self._profile(optional=True)
            writable = True
            try:
                self._access(fresh, True); self._gate()
            except Problem:
                writable = False
            return dict(schema_version=1, rule_version=RULE_VERSION, revision=len(ledger['entries']), state_hash=state_hash(ledger['entries']),
                        profile=profile, profile_ref=profile_reference(profile) if profile else None,
                        accounts=Accounting(self.office).accounts(fresh)['items'], items=list(ledger['current'].values()),
                        can_prepare=writable and profile is not None, max_original_bytes=MAX_FILE,
                        liquidity_path=BASE + '/liquidity', cash_flow_created=False, tax_postings_created=False)

    def sources(self, actor, account_id):
        with transaction(self.office):
            self._access(actor); account = Accounting(self.office)._account(account_id); profile = self._profile()
            opening_date = profile['profile']['bookkeeping_start']; candidates = []
            if account['kind'] == 'bank':
                for row in self.db.execute('SELECT id FROM business_bank_statements WHERE account_id=? ORDER BY created_at,id', (account_id,)):
                    value = self._bank_statement(row['id']); metadata = value['payload']
                    for side, day in (('opening', metadata['period_from']), ('closing', (date.fromisoformat(metadata['period_to']) + timedelta(days=1)).isoformat())):
                        if day == opening_date:
                            source = dict(kind='bank_statement', statement_id=value['id'], content_hash=value['content_hash'], balance_side=side)
                            candidates.append(dict(source=source, amount=metadata[side + '_balance'], statement_reference=metadata['statement_reference'],
                                                   period_from=metadata['period_from'], period_to=metadata['period_to']))
            originals = [self._original(row['id'])[0] for row in self.db.execute('SELECT id FROM business_accounting_opening_originals WHERE account_id=? ORDER BY created_at,id', (account_id,))]
            return dict(schema_version=1, account=account, profile_ref=profile_reference(profile), opening_date=opening_date,
                        bank_statements=candidates, originals=originals, original_evidence_type='cash_count' if account['kind'] == 'cash' else 'account_statement')

    def history(self, actor, account_id):
        with transaction(self.office):
            self._access(actor); Accounting(self.office)._account(account_id)
            return dict(schema_version=1, account_id=account_id, items=[entry for entry in self._ledger()['entries'] if entry['account_id'] == account_id])

    def preview(self, actor, data):
        self._inputs(data)
        with transaction(self.office):
            self._lock(); self._access(actor, True); self._gate()
            return self._prepare(self._ledger(), data)

    def confirm(self, actor, data):
        self._inputs(data, True)
        with transaction(self.office):
            self._lock(); fresh = self._access(actor, True); self._gate(); ledger = self._ledger()
            digest, replay = self._request(fresh, 'confirm', data)
            if replay:
                return ledger['by_id'][replay['entry_id']]
            try:
                preview = self._prepare(ledger, {key: data[key] for key in INPUT})
                if preview['preview_hash'] != data['preview_hash']:
                    raise Problem(409, 'Passende aktuelle Anfangsbestandsvorschau erforderlich.')
            except Problem as error:
                if error.status == 409:
                    raise Problem(409, error.message, request_resolution='not_accepted') from None
                raise
            old = ledger['current'].get(data['account_id'])
            value = dict(preview, id=uuid.uuid4().hex, sequence=len(ledger['entries']) + 1, revision=old['revision'] + 1 if old else 1,
                         previous_hash=ledger['entries'][-1]['content_hash'] if ledger['entries'] else None, created_by=fresh['id'], created_at=self.now())
            self._access(fresh, True)
            self.db.execute('INSERT INTO business_accounting_opening_events(id,sequence,account_id,revision,previous_hash,payload_json,content_hash,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                            (value['id'], value['sequence'], value['account_id'], value['revision'], value['previous_hash'], canonical(value), sha(value), fresh['id'], value['created_at']))
            self._remember(fresh, 'confirm', data, digest, dict(entry_id=value['id']))
            self.office.audit(fresh, 'business.accounting.opening_confirmed', value['id'])
            return dict(value, content_hash=sha(value))

    def liquidity(self, actor, as_of):
        iso_date(as_of)
        if as_of > self.clock().astimezone(ZoneInfo('Europe/Berlin')).date().isoformat():
            raise Problem(400, 'Bestandsstichtag darf nicht in der Zukunft liegen.')
        from business_accounting_euer import EuerAccounting
        with transaction(self.office):
            self._access(actor); ledger = self._ledger()
            profile = self._profile(optional=True)
            euer = EuerAccounting(self.office); catalog = euer._catalog(actor, euer._ledger()); movements = catalog['cash_movements']
            start_date = profile['profile']['bookkeeping_start'] if profile else None
            unresolved = [issue for issue in catalog['issues'] if issue['code'] == 'cash_import_missing'
                          and issue['date'] <= as_of and (start_date is None or issue['date'] >= start_date)]
            global_issues = []
            from business_schema import require_financial_release
            try:
                require_financial_release(self.office)
            except Problem:
                global_issues.append(dict(code='restore_reconciliation_pending'))
            accounts = Accounting(self.office).accounts(actor)['items']; result = []; known = 0
            for account in accounts:
                entry = ledger['current'].get(account['id']); all_movements = [m for m in movements if m['account']['id'] == account['id'] and m['date'] <= as_of]
                if not account['active'] and not entry and not all_movements:
                    continue
                issues = []
                if not entry or entry['status'] != 'active':
                    issues.append(dict(code='opening_balance_missing'))
                elif not profile or entry['profile_ref'] != profile_reference(profile):
                    issues.append(dict(code='opening_profile_changed'))
                elif entry['opening_date'] > as_of:
                    issues.append(dict(code='as_of_before_opening'))
                start = entry['opening_date'] if entry and entry['status'] == 'active' else None
                selected = [m for m in all_movements if start is not None and m['date'] >= start]
                inflows = sum(cents(m['amount']) for m in selected if m['direction'] == 'in')
                outflows = sum(cents(m['amount']) for m in selected if m['direction'] == 'out')
                calculated = cents(entry['amount']) + inflows - outflows if start is not None and start <= as_of else None
                if account['kind'] == 'cash' and calculated is not None and calculated < 0:
                    issues.append(dict(code='cash_balance_negative'))
                checks = []
                if account['kind'] == 'bank' and calculated is not None:
                    for row in self.db.execute('SELECT id FROM business_bank_statements WHERE account_id=?', (account['id'],)):
                        statement = self._bank_statement(row['id']); metadata = statement['payload']
                        for side, boundary, exclusive in (('opening', metadata['period_from'], True), ('closing', metadata['period_to'], False)):
                            previous_closing = side == 'closing' and (date.fromisoformat(boundary) + timedelta(days=1)).isoformat() == start
                            if start <= boundary <= as_of or previous_closing and start <= as_of:
                                delta = sum(cents(m['amount']) * (1 if m['direction'] == 'in' else -1) for m in selected if m['date'] < boundary or not exclusive and m['date'] == boundary)
                                expected = cents(entry['amount']) + delta; observed = cents(metadata[side + '_balance'])
                                checks.append(dict(statement_id=statement['id'], content_hash=statement['content_hash'], balance_side=side, date=boundary,
                                                   recorded_balance=money(expected), statement_balance=money(observed), matches=expected == observed))
                                if expected != observed:
                                    issues.append(dict(code='bank_statement_connection_mismatch', statement_id=statement['id'], balance_side=side, date=boundary))
                if calculated is not None and not issues:
                    known += calculated
                result.append(dict(account=account, opening_ref=event_reference(entry) if entry else None, opening_date=start,
                                   opening_balance=entry['amount'] if start is not None else None, inflows=money(inflows), outflows=money(outflows),
                                   calculated_balance=money(calculated) if calculated is not None else None,
                                   balance=money(calculated) if calculated is not None and not issues else None,
                                   movements=selected, bank_connections=checks, issues=issues))
            complete = bool(result) and not unresolved and not global_issues and all(not item['issues'] and item['balance'] is not None for item in result)
            known_count = sum(item['balance'] is not None for item in result)
            return dict(schema_version=1, rule_version=RULE_VERSION, as_of=as_of, currency='EUR', scope='recorded_movements',
                        revision=len(ledger['entries']), state_hash=state_hash(ledger['entries']), accounts=result, unresolved_cash_sources=unresolved, issues=global_issues,
                        complete_for_recorded_accounts=complete, known_balance_sum=money(known) if known_count else None,
                        known_account_count=known_count, account_count=len(result), balance_total=money(known) if complete else None,
                        euer_result_unchanged=True, cash_flow_created=False, tax_postings_created=False,
                        balance_timing='start_of_day', timezone='Europe/Berlin')


def validate_integrity(office):
    if not installed(office):
        return True
    api = OpeningBalances(office)
    try:
        ledger = api._ledger(); original_ids = set()
        for row in office.db.execute('SELECT id FROM business_accounting_opening_originals'):
            original_ids.add(row['id']); api._original(row['id'])
        covered = set()
        for row in office.db.execute('SELECT * FROM business_accounting_opening_requests'):
            command = json.loads(row['request_json']); result = json.loads(row['result_json'])
            identifier(row['user_id']); identifier(row['request_id'])
            if canonical(command) != row['request_json'] or command['request_id'] != row['request_id'] or sha([row['operation'], command]) != row['request_hash']:
                raise ValueError('Changed opening receipt')
            if row['operation'] == 'original':
                shape(command, ('request_id', 'account_id', 'filename', 'media_type', 'size', 'sha256')); shape(result, ('original_id',))
                original = api._original(result['original_id'])[0]
                if any(command[key] != original[key] for key in ('account_id', 'filename', 'media_type', 'size', 'sha256')):
                    raise ValueError('Wrong original receipt')
                covered.add(original['id'])
            elif row['operation'] != 'confirm' or result['entry_id'] not in ledger['by_id']:
                raise ValueError('Unknown opening receipt')
        if original_ids != covered:
            raise ValueError('Missing original receipt')
        if isinstance(office.db, sqlite3.Connection):
            normalize = lambda value: re.sub(r'\s+', ' ', value.replace('IF NOT EXISTS ', '')).strip().lower()
            for statement in guard_statements('sqlite'):
                name = re.search(r'CREATE TRIGGER IF NOT EXISTS (\w+)', statement)[1]
                row = office.db.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?", (name,)).fetchone()
                if not row or normalize(row[0]) != normalize(statement):
                    raise ValueError('Missing opening guard')
        else:
            from business_documents import _validate_pg_guards
            _validate_pg_guards(office.db, guard_statements('postgresql'))
    except (Problem, KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ValueError('Invalid opening balance evidence') from error
    return True


def entrypoint(office, actor):
    """Additive live navigation only; never rewrites an archived EÜR report."""
    if not installed(office):
        return None
    try:
        OpeningBalances(office)._access(actor)
    except Problem as error:
        if error.status in (403, 404):
            return None
        raise
    return BASE


def restore_horizon(office):
    with office.lock:
        if not installed(office):
            return None
        validate_integrity(office); tables = {}
        for table in TABLES:
            rows = []
            for row in office.db.execute('SELECT * FROM ' + table):
                value = dict(row)
                if 'original' in value:
                    value['original'] = dict(sha256=sha(bytes(value['original'])), size=len(value['original']))
                rows.append(value)
            tables[table] = sorted(rows, key=canonical)
        return dict(schema_version=1, table_counts={table: len(rows) for table, rows in tables.items()}, sha256=sha(dict(schema_version=1, tables=tables)))


def methods(path):
    if path in (BASE, BASE + '/sources', BASE + '/liquidity') or re.fullmatch(BASE + '/(?:accounts/' + ID + '/history|originals/' + ID + ')', path):
        return 'GET'
    if path in (BASE + '/preview', BASE + '/confirm', BASE + '/originals'):
        return 'POST'
    return None


def dispatch(office, actor, path, method, data):
    allowed = methods(path)
    if allowed is None:
        return None
    if method != allowed:
        raise Problem(405, 'HTTP-Methode nicht erlaubt.')
    api = OpeningBalances(office)
    if method == 'POST':
        if not isinstance(data, dict) or '_query' in data:
            raise Problem(400, 'JSON-Befehl ohne zusätzliche Filter erforderlich.')
        action = path.rsplit('/', 1)[-1]
        result = getattr(api, 'upload_original' if action == 'originals' else action)(actor, data)
        return result, 200 if action == 'preview' else 201, 'application/json'
    if not isinstance(data, dict) or set(data) - {'_query'}:
        raise Problem(400, 'GET erwartet keinen Anfragekörper.')
    query = data.get('_query', {})
    if path == BASE + '/sources':
        shape(query, ('account_id',)); result = api.sources(actor, query['account_id'])
    elif path == BASE + '/liquidity':
        shape(query, ('as_of',)); result = api.liquidity(actor, query['as_of'])
    else:
        shape(query, ())
        if '/originals/' in path:
            raw, media_type = api.original(actor, path.rsplit('/', 1)[-1])
            return raw, 200, media_type
        result = api.history(actor, path.split('/')[-2]) if path.endswith('/history') else api.state(actor)
    return result, 200, 'application/json'
