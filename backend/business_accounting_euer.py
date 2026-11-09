"""Explicit German cash-basis bookkeeping, separate EÜR and VAT recognition.

Sources remain in the existing accounting/documentary journals. This additive
ledger records reviewed decisions, exact counter-postings, period attestations
and frozen adviser packages. It never transmits money or tax declarations.
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from contextlib import contextmanager
import csv
import io
import json
import re
import uuid

from core import Problem, canonical
from business_operations import Domain, identifier, iso_date, instant, transaction
from business_accounting import Accounting, _hash, _page, _paged, _sha, _evidence
from business_accounting_components import DocumentComponents, _cents as _unsigned_cents, _money as _unsigned_money, _stored
from business_accounting_profile import AccountingPreparationProfile

FEATURES = ('accounting_euer', 'accounting_year_evidence_v1', 'accounting_year_evidence_v2')
RULE_VERSION = 'de_euer_regular_cash_2026_v1'
_TABLES = ('business_euer_entries', 'business_euer_requests')
_INPUT = {'operation', 'expected_revision', 'state_hash', 'payload', 'reason', 'evidence_reference'}
_ECONOMIC = {'cash', 'input_vat', 'external_cash', 'asset', 'depreciation', 'payroll_cash', 'travel_cash', 'opening_depreciation', 'opening_item_cash', 'opening_year_values'}
_OPERATIONS = _ECONOMIC | {'reverse', 'correct', 'period', 'export'}
_EXPENSE = ('materials', 'external_services', 'rent', 'insurance', 'software', 'travel', 'other_expense', 'asset_acquisition')
_EXTERNAL = {'vat_payment':'out', 'vat_refund':'in', 'owner_contribution':'in', 'owner_withdrawal':'out',
             'loan_received':'in', 'loan_repayment':'out'}
_MONEY = ('business_net', 'deductible_net', 'business_tax', 'deductible_input_tax', 'deductible_tax_cost')
_LIMITATIONS = ['Domestic regular taxation with explicitly recorded cash VAT profile',
    'Invoice chains require verified incremental documentary components; historical invoice proofs remain unchanged',
    'No automatic reverse charge, cross-border VAT, VAT-free sales, private deemed supplies or partial advance input VAT',
    'Linear depreciation for evidenced new assets and separately reviewed unchanged historical movable assets; no disposal, special/degressive depreciation or GWG automation',
    'No automatic loan-interest limitation, home-office allowance or payroll tax determination; travel cash requires separately reviewed travel claims',
    'Own adviser review format; no official tax return, ELSTER transmission or DATEV certification']


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA', 'BLOB'):
        raise ValueError('Unsupported binary type')
    return [
        '''CREATE TABLE IF NOT EXISTS business_euer_entries(
        id TEXT PRIMARY KEY, sequence INTEGER NOT NULL UNIQUE CHECK(sequence>0),
        operation TEXT NOT NULL, target TEXT, previous_hash TEXT NOT NULL CHECK(length(previous_hash)=64),
        entry_json TEXT NOT NULL, entry_sha256 TEXT NOT NULL CHECK(length(entry_sha256)=64),
        created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_euer_requests(
        user_id TEXT NOT NULL REFERENCES users(id), request_id TEXT NOT NULL,
        request_json TEXT NOT NULL, request_hash TEXT NOT NULL CHECK(length(request_hash)=64),
        entry_id TEXT NOT NULL UNIQUE REFERENCES business_euer_entries(id), PRIMARY KEY(user_id,request_id))''',
        'CREATE INDEX IF NOT EXISTS business_euer_target ON business_euer_entries(target,sequence)',
    ]


def protected_tables():
    return _TABLES


def runtime_privileges():
    return {table: ('SELECT', 'INSERT') for table in _TABLES}


def guard_statements(dialect):
    if dialect == 'sqlite':
        values = [f'CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} ON {table} '
                  "BEGIN SELECT RAISE(ABORT,'immutable EÜR journal'); END" for table in _TABLES for action in ('UPDATE', 'DELETE')]
        for table, conflict in zip(_TABLES, ('id=NEW.id OR sequence=NEW.sequence',
                '(user_id=NEW.user_id AND request_id=NEW.request_id) OR entry_id=NEW.entry_id')):
            values.append(f'CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} '
                          f'WHEN EXISTS(SELECT 1 FROM {table} WHERE {conflict}) '
                          "BEGIN SELECT RAISE(ABORT,'immutable EÜR journal'); END")
        return values
    if dialect != 'postgresql':
        raise ValueError('Unsupported guard dialect')
    values = ["CREATE OR REPLACE FUNCTION business_euer_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$ "
              "BEGIN RAISE EXCEPTION 'immutable EÜR journal'; END; $$"]
    for table in _TABLES:
        for action in ('UPDATE', 'DELETE'):
            name = table+'_'+action.lower()+'_guard'
            values.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) "
                          f'THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW '
                          'EXECUTE FUNCTION business_euer_immutable_guard(); END IF; END $$')
    return values


def _shape(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys.split() if isinstance(keys, str) else keys):
        raise Problem(400, 'Vollständige bekannte Buchführungsfelder erwartet')


def _line(value, name='Begründung', maximum=1000):
    if (not isinstance(value, str) or not 1 <= len(value) <= maximum or not value.strip()
            or any(ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in value)):
        raise Problem(400, 'Begrenzter einzeiliger Text erwartet: '+name)
    return value


def _account(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{4}', value):
        raise Problem(400, 'Ausdrücklich geprüfte vierstellige SKR04-Kontenzuordnung erwartet')
    return value


def _amount(value, positive=False):
    if not isinstance(value, str) or not re.fullmatch(r'(?:0|[1-9][0-9]{0,12})\.[0-9]{2}', value):
        raise Problem(400, 'Kanonischer begrenzter EUR-Centbetrag erwartet')
    return _unsigned_cents(value, positive=positive)


def _cents(value):
    if isinstance(value, str) and value.startswith('-'):
        return -_unsigned_cents(value[1:], positive=True)
    return _unsigned_cents(value)


def _money(value):
    return ('-' if value < 0 else '') + _unsigned_money(abs(value))


def _year(value):
    if type(value) is not int or not 1900 <= value <= 2200:
        raise Problem(400, 'Gültiges Kalenderjahr erwartet')
    return value


def _period(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{4}-(?:0[1-9]|1[0-2])', value):
        raise Problem(400, 'Monatsperiode YYYY-MM erwartet')
    iso_date(value+'-01')
    return value


def _euer_date(cash_date, wanted, rule):
    iso_date(wanted)
    if rule == {'kind':'cash'}:
        if wanted != cash_date:
            raise Problem(400, 'Ohne Jahreswechselregel gilt das tatsächliche Zahlungsdatum')
        return wanted
    _shape(rule, 'kind economic_year due_date recurring')
    if rule['kind'] != 'ten_day' or rule['recurring'] is not True:
        raise Problem(400, 'Regelmäßig wiederkehrenden Jahreswechselfall ausdrücklich prüfen')
    year = _year(rule['economic_year']); iso_date(rule['due_date'])
    cash = date.fromisoformat(cash_date); due = date.fromisoformat(rule['due_date'])
    if cash.year == year+1 and cash.month == 1 and cash.day <= 10:
        expected = f'{year}-12-31'; boundary = date(year, 12, 31)
    elif cash.year == year-1 and cash.month == 12 and cash.day >= 22:
        expected = f'{year}-01-01'; boundary = date(year-1, 12, 31)
    else:
        raise Problem(400, 'Zahlung liegt nicht im Zehntagesfenster des anderen Wirtschaftsjahres')
    if not -9 <= (due-boundary).days <= 10 or wanted != expected:
        raise Problem(400, 'Fälligkeit und wirtschaftliche Jahreszuordnung erfüllen die Zehntagesregel nicht')
    return wanted


def _posting(ledger, category, amount, day, account, source):
    return dict(ledger=ledger, category=category, amount=_money(amount), date=day, account=account, source_key=source)


def _negate(postings):
    return [dict(value, amount=_money(-_cents(value['amount']))) for value in postings]


def _state_hash(entries):
    return _sha(canonical(dict(schema_version=1, revision=len(entries), head=entries[-1]['entry_hash'] if entries else None)))


class EuerAccounting(Domain):
    @contextmanager
    def _source_read(self):
        """Share one validated joint journal only inside this serialized call.

        Every cash event used to reconstruct all C2/R2 histories again. A
        company report therefore repeated the whole reconstruction for every
        source and journal entry. Never retain this cache between calls: new
        bookings, changed originals and revoked source rights must stay visible.
        """
        previous = getattr(self, '_joint_source_cache', None)
        self._joint_source_cache = {}
        try:
            yield
        finally:
            if previous is None:
                del self._joint_source_cache
            else:
                self._joint_source_cache = previous

    def _access(self, actor, write=False):
        fresh = Accounting(self.office)._access(actor, 'accounting.admin' if write else None)
        if write:
            self.access(fresh, 'accounting.prepare'); self.access(fresh, 'finance.write')
        return fresh

    def _gate(self):
        from business_schema import require_capability
        require_capability(self.office, 'business_accounting_euer')
        Accounting(self.office)._write_gate()

    def _profile(self):
        entries = AccountingPreparationProfile(self.office)._ledger()['entries']
        return entries[-1] if entries else None

    @staticmethod
    def _configured(profile):
        if not profile:
            return False
        facts = profile['profile']
        return (facts['legal_form'] == 'sole_proprietorship' and facts['accounting_method'] == 'euer'
                and facts['vat_regime'] == 'regular' and facts['vat_timing'] == 'cash'
                and facts['vat_effective_from'] is not None and facts['bookkeeping_start'] is not None)

    def _source_access(self, actor, source, write=False):
        if actor is None:
            return
        from accounting_joint_access import authorize_sources
        from business_finance import Finance
        if source['kind'] == 'opening_year_values':
            from business_accounting_year_openings import financial_access
            financial_access(self.office,actor,write)
        elif source['kind'] == 'opening_item_cash':
            from business_accounting_open_items import financial_access
            financial_access(self.office,actor,write)
        elif source['kind'] == 'opening_asset':
            from business_accounting_asset_openings import financial_access
            financial_access(self.office,actor,write)
        elif source['kind'] == 'travel_cash':
            from travel_allowance_cash import financial_access
            financial_access(self.office,actor,write)
        elif source['kind'] == 'payroll_cash':
            from business_payroll_cash import financial_access
            financial_access(self.office,actor,write)
        elif source['kind'] == 'cash':
            authorize_sources(self.office, actor, source['event']['id'], write=write)
        else:
            Finance(self.office)._incoming(actor, source['receipt']['receipt_id'], 'finance.write' if write else 'finance.read')
        if source.get('payment_event'):
            authorize_sources(self.office, actor, source['payment_event']['id'], write=write)

    def _cash_source(self, actor, event_id):
        from accounting_joint_ledger import read_joint_ledger
        from accounting_joint_access import authorize_sources
        if actor is not None:
            authorize_sources(self.office, actor, event_id)
        event = Accounting(self.office)._event(actor, event_id)
        api = DocumentComponents(self.office)
        c1 = api._history(api._source(actor, event_id))[0]
        joint = read_joint_ledger(self.office, getattr(self, '_joint_source_cache', None))
        groups = [('c1', c1), ('c2', joint['capacity']['by_event'].get(event_id, [])),
                  ('r1', joint['refunds']['by_event'].get(event_id, [])), ('r2', joint['refunds_v2']['by_event'].get(event_id, []))]
        units = []
        for version, entries in groups:
            for entry in entries:
                for index, part in enumerate(entry['lines']):
                    unit = dict(version=version, entry_id=entry['id'], group_id=part['group_id'], index=index,
                                net=part['net'], tax=part['tax'], gross=part['amount'])
                    if version == 'c1':
                        row = self.office.db.execute('SELECT basis_json FROM business_accounting_component_lines WHERE entry_id=? AND group_id=?',
                                                     (entry['id'], part['group_id'])).fetchone()
                        basis = json.loads(row['basis_json']); unit['rate'] = basis['rate']; unit['tax_category'] = basis['category']
                    elif version == 'c2':
                        row = self.office.db.execute('SELECT proof_json FROM business_accounting_capacity_entries WHERE id=?', (entry['id'],)).fetchone()
                        basis = next(value for value in json.loads(row['proof_json'])['basis'] if value['group_id'] == part['group_id'])
                        unit['rate'] = basis.get('rate'); unit['tax_category'] = basis.get('category')
                    else:
                        unit['rate'] = part['rate']; unit['tax_category'] = part['category']
                    unit['unit_id'] = _sha(canonical(dict(version=version, entry_id=entry['id'], index=index)))
                    units.append(unit)
        units.sort(key=lambda value: value['unit_id'])
        documented = sum(_cents(value['gross']) for value in units)
        if documented > _cents(event['amount']):
            raise Problem(409, 'Dokumentarische Geldanteile überschreiten die Quelle')
        value = dict(kind='cash', event=event, units=units, undocumented_amount=_money(_cents(event['amount'])-documented),
                     source_path='/accounting/events/'+event_id)
        return dict(value, source_hash=_sha(canonical(value)))

    def _receipt_source(self, actor, receipt_id, historical=None):
        revision = historical['receipt']['review_revision'] if historical else None
        value, unused_proof = Accounting(self.office)._receipt_source(actor, receipt_id, revision)
        if value is None:
            raise Problem(409, 'Geprüftes positives EUR-Original erforderlich')
        source = dict(kind='receipt', receipt=value, source_path='/finance/receipts/'+receipt_id)
        return dict(source, source_hash=_sha(canonical(source)))

    def _validate_source(self, source):
        if source['kind'] == 'opening_year_values':
            from business_accounting_year_openings import public_source
            current=public_source(self.office,source['id'],source['revision'])
        elif source['kind'] == 'opening_item_cash':
            from business_accounting_open_items import public_source
            current=public_source(self.office,source['id'],source['revision'])
        elif source['kind'] == 'opening_asset':
            from business_accounting_asset_openings import public_source
            current=public_source(self.office,source['id'])
        elif source['kind'] == 'travel_cash':
            from travel_allowance_cash import public_source
            current=public_source(self.office,source['id'],source['revision'])
        elif source['kind'] == 'payroll_cash':
            from business_payroll_cash import public_source
            current=public_source(self.office,source['id'],source['revision'])
        elif source['kind'] == 'cash':
            current = self._cash_source(None, source['event']['id'])
        else:
            current = self._receipt_source(None, source['receipt']['receipt_id'], source)
        if current != {key:value for key,value in source.items() if key != 'payment_event'}:
            raise ValueError('Changed frozen bookkeeping source')
        if source.get('payment_event') and Accounting(self.office)._event(None, source['payment_event']['id']) != source['payment_event']:
            raise ValueError('Changed advance payment proof')

    @staticmethod
    def _inputs(data, confirm=False):
        _shape(data, _INPUT | ({'request_id', 'preview_hash', 'confirmation'} if confirm else set()))
        if not isinstance(data['operation'],str) or data['operation'] not in _OPERATIONS or type(data['expected_revision']) is not int or data['expected_revision'] < 0:
            raise Problem(400, 'Bekannter Vorgang und nichtnegative Journalrevision erwartet')
        _hash(data['state_hash']); _line(data['reason']); _line(data['evidence_reference'], 'Prüfnachweis', 200)
        if not isinstance(data['payload'], dict):
            raise Problem(400, 'Buchführungsvorgang als Objekt erwartet')
        if confirm:
            identifier(data['request_id']); _hash(data['preview_hash'])
            if data['confirmation'] is not True:
                raise Problem(400, 'Sachverhalt, Steuerbehandlung und Kontenzuordnung ausdrücklich bestätigen')

    @staticmethod
    def _empty():
        return dict(entries=[], active={}, by_id={}, periods={})

    @staticmethod
    def _apply(ledger, entry):
        if entry['reverses']:
            old = ledger['by_id'].get(entry['reverses'])
            if not old or ledger['active'].get(old['target'], {}).get('id') != old['id']:
                raise ValueError('Counter-posting must reference the active entry')
            del ledger['active'][old['target']]
        if entry['effect']:
            if entry['target'] in ledger['active']:
                raise ValueError('Duplicate active economic source')
            ledger['active'][entry['target']] = entry
        if entry['operation'] == 'period':
            payload = entry['payload']; old = ledger['periods'].get(payload['period'])
            if payload['expected_period_revision'] != (old['revision'] if old else 0):
                raise ValueError('Invalid period event order')
            ledger['periods'][payload['period']] = dict(period=payload['period'], revision=payload['expected_period_revision']+1,
                                                      status='closed' if payload['action'] == 'close' else 'open', entry_id=entry['id'])
        ledger['entries'].append(entry); ledger['by_id'][entry['id']] = entry

    def _validate_report(self, report, ledger, profile):
        """A frozen package must reproduce its actual journal prefix exactly.

        Unbooked sources may arrive later; their historical completeness review
        is retained, never re-created from the current inbox during integrity.
        """
        prefix=report['period'] or str(_year(report['year']))
        if report['period'] is not None:_period(report['period'])
        postings=[dict(value,entry_id=entry['id'],sequence=entry['sequence']) for entry in ledger['entries']
                  for value in entry['postings'] if value['date'].startswith(prefix)]
        if (report['revision']!=len(ledger['entries']) or report['state_hash']!=_state_hash(ledger['entries'])
                or report['postings']!=postings or report['profile']!=profile or report['rule_version']!=RULE_VERSION
                or report['official_tax_return'] is not False or report['scope']!='recorded_sources'):
            raise ValueError('Frozen report changed its recorded journal horizon')
        grouped={}
        for value in postings:
            key=(value['ledger'],value['category']);grouped[key]=grouped.get(key,0)+_cents(value['amount'])
        categories=[dict(ledger=key[0],category=key[1],amount=_money(amount)) for key,amount in sorted(grouped.items())]
        income=sum(amount for (kind,category),amount in grouped.items() if kind=='euer' and category in ('sales','vat_collected','vat_refund'))
        expense=-sum(amount for (kind,category),amount in grouped.items() if kind=='euer' and category not in ('sales','vat_collected','vat_refund'))
        output=sum(amount for (kind,category),amount in grouped.items() if kind=='vat' and category=='output_vat')
        iv=-sum(amount for (kind,category),amount in grouped.items() if kind=='vat' and category=='input_vat')
        complete=not report['issues']
        totals=dict(confirmed_income=_money(income),confirmed_expenses=_money(expense),confirmed_surplus=_money(income-expense),
                    euer_surplus=_money(income-expense) if complete else None,confirmed_output_vat=_money(output),
                    confirmed_input_vat=_money(iv),vat_balance=_money(output-iv) if complete else None)
        if report['categories']!=categories or report['totals']!=totals or report['complete_for_recorded_sources'] is not complete:
            raise ValueError('Frozen report changed its monetary projection')
        if 'historical_assets' in report:
            from accounting_asset_opening_sources import validate_report_assets
            validate_report_assets(self,report,ledger)
        elif any(entry['effect'] and entry['effect']['operation']=='opening_depreciation' for entry in ledger['entries']):
            raise ValueError('Historical asset journal cannot have a legacy report without its asset projection')

        if 'historical_year_values' in report or 'opening_year_values:'+str(report['year']) in ledger['active']:
            from accounting_year_opening_sources import validate_report
            validate_report(self,report,ledger,profile)

    @_stored
    def _ledger(self):
        rows = self.office.db.execute('SELECT * FROM business_euer_entries ORDER BY sequence').fetchall()
        receipts = {row['entry_id']:row for row in self.office.db.execute('SELECT * FROM business_euer_requests').fetchall()}
        if len(rows) != len(receipts):
            raise ValueError('Missing bookkeeping receipt')
        profiles = {value['id']:value for value in AccountingPreparationProfile(self.office)._ledger()['entries']}
        ledger = self._empty()
        for sequence, row in enumerate(rows, 1):
            entry = json.loads(row['entry_json'])
            _shape(entry,(_INPUT-{'expected_revision','state_hash'})|{'id','sequence','previous_hash','created_by','created_at','profile','rule_version',
                                                                  'target','effect','reverses','postings','artifact','control','preview_hash'})
            if (canonical(entry) != row['entry_json'] or _sha(row['entry_json']) != row['entry_sha256']
                    or row['sequence'] != sequence or entry['sequence'] != sequence
                    or any(entry[key] != row[key] for key in ('id','operation','target','previous_hash','created_by','created_at'))
                    or entry['previous_hash'] != _state_hash(ledger['entries']) or instant(entry['created_at']) != entry['created_at']
                    or entry['rule_version'] != RULE_VERSION):
                raise ValueError('Changed bookkeeping journal chain')
            receipt = receipts[row['id']]; command = json.loads(receipt['request_json']); self._inputs(command, True)
            if (receipt['request_json'] != canonical(command) or receipt['request_hash'] != _sha(canonical(command))
                    or command['request_id'] != receipt['request_id'] or receipt['user_id'] != row['created_by']
                    or command['expected_revision'] != sequence-1 or command['state_hash'] != row['previous_hash']
                    or any(command[key] != entry[key] for key in ('operation','payload','reason','evidence_reference','preview_hash'))):
                raise ValueError('Changed bookkeeping request')
            profile = entry['profile']
            if profile and profiles.get(profile['id']) != profile:
                raise ValueError('Changed historical preparation profile')
            preview = {key:value for key,value in entry.items() if key not in ('id','sequence','previous_hash','created_by','created_at','preview_hash')}
            preview.update(expected_revision=sequence-1, state_hash=row['previous_hash'])
            if _sha(canonical(preview)) != entry['preview_hash']:
                raise ValueError('Changed confirmed bookkeeping preview')
            if entry['effect']:
                effect = entry['effect']; self._validate_source(effect['source'])
                if (effect['operation']!=(entry['payload']['operation'] if entry['operation']=='correct' else entry['operation'])
                        or effect['payload']!=(entry['payload']['payload'] if entry['operation']=='correct' else entry['payload'])
                        or effect['target']!=entry['target']):
                    raise ValueError('Changed economic operation or source target')
                calculated = self._economic(None, effect['operation'], effect['payload'], ledger, profile, historical=effect['source'])
                if calculated != effect:
                    raise ValueError('Changed reviewed bookkeeping computation')
            old = ledger['by_id'].get(entry['reverses']) if entry['reverses'] else None
            if entry['operation'] in ('reverse','correct'):
                if old is None or entry['payload']['entry_id']!=old['id'] or entry['target']!=old['target']:
                    raise ValueError('Changed correction origin')
                self._counter_target(ledger,old['id'])
            elif old is not None:
                raise ValueError('Only correction operations may reverse a source')
            postings = (_negate(old['effect']['postings']) if old else []) + (entry['effect']['postings'] if entry['effect'] else [])
            if postings != entry['postings']:
                raise ValueError('Changed exact counter-posting')
            self._unlocked(ledger, postings)
            for effect in (entry['effect'],old['effect'] if old else None):
                if effect:
                    self._unlocked(ledger,[dict(date=day) for day in self._effect_dates(effect)])
            if entry['artifact']:
                artifact = entry['artifact']
                if (entry['operation']!='export' or artifact['format']!='smartplan_euer_review_v1' or artifact['datev_certified'] is not False
                        or artifact['official_tax_return'] is not False or entry['payload']!={'year':artifact['report']['year']}
                        or _sha(canonical(artifact['report'])) != artifact['report_sha256'] or _sha(artifact['csv']) != artifact['csv_sha256']
                        or self._csv(artifact['report'])!=artifact['csv']):
                    raise ValueError('Changed frozen adviser package')
                self._validate_report(artifact['report'],ledger,profile)
            elif entry['operation']=='export':
                raise ValueError('Missing frozen adviser package')
            if entry['operation']=='period':
                payload=entry['payload']; _shape(payload,'period action expected_period_revision attestation'); _period(payload['period'])
                _shape(payload['attestation'],'bank_reconciled originals_complete special_cases_reviewed')
                previous=ledger['periods'].get(payload['period'])
                if (type(payload['expected_period_revision']) is not int or any(type(value) is not bool for value in payload['attestation'].values())
                        or payload['action'] not in ('close','reopen') or entry['target']!='period:'+payload['period']):
                    raise ValueError('Invalid historical period command')
                if payload['action']=='close':
                    control=entry['control']
                    if (not all(payload['attestation'].values()) or previous and previous['status']=='closed' or not control
                            or control['report']['period']!=payload['period'] or control['report']['issues']
                            or _sha(canonical(control['report']))!=control['report_sha256']):
                        raise ValueError('Changed explicit period completion proof')
                    self._validate_report(control['report'],ledger,profile)
                    if 'bank_reconciliation' in control:
                        from business_bank_reconciliation import validate_period_closure_proof
                        validate_period_closure_proof(self.office,control['bank_reconciliation'],payload['period'])
                elif not previous or previous['status']!='closed' or entry['control'] is not None:
                    raise ValueError('Invalid historical reopening')
            elif entry['control'] is not None:
                raise ValueError('Unexpected period proof')
            entry['entry_hash'] = row['entry_sha256']; self._apply(ledger, entry)
        return ledger

    @staticmethod
    def _unlocked(ledger, postings):
        for value in postings:
            if ledger['periods'].get(value['date'][:7], {}).get('status') == 'closed':
                raise Problem(409, 'Buchungsperiode ist gesperrt: '+value['date'][:7])

    @staticmethod
    def _profile_dates(profile, days):
        if not EuerAccounting._configured(profile):
            raise Problem(409, 'Vollständiges ausdrücklich datiertes EÜR-/Ist-Profil erforderlich')
        facts = profile['profile']
        if any(day < facts['bookkeeping_start'] or day < facts['vat_effective_from'] for day in days):
            raise Problem(409, 'Sachverhalt liegt vor dem bestätigten Buchführungs-/Umsatzsteuerbeginn')

    def _economic(self, actor, operation, payload, ledger, profile, historical=None):
        method = getattr(self, '_prepare_'+operation)
        source, target, postings, details = method(actor, payload, ledger, historical)
        if operation=='opening_year_values':
            # Only this original-bound historical copy may precede software start.
            self._profile_dates(profile,[source['date']])
            from business_accounting_openings import profile_reference
            if source['profile_ref']!=profile_reference(profile):
                raise Problem(409,'Historische Jahresquelle gehört zu einem anderen Buchführungsprofil.')
        else:
            self._profile_dates(profile, [value['date'] for value in postings] or [details['date']])
        return dict(operation=operation, payload=payload, source=source, target=target, postings=postings, details=details)

    def _prepare_cash(self, actor, payload, ledger, historical):
        _shape(payload, 'event_id source_hash euer_date year_rule lines'); identifier(payload['event_id']); _hash(payload['source_hash'])
        source = historical or self._cash_source(actor, payload['event_id'])
        if source['source_hash'] != payload['source_hash']:
            raise Problem(409, 'Geldfluss oder dokumentarische Einordnung wurde geändert')
        if _cents(source['undocumented_amount']):
            raise Problem(409, 'Der ganze Geldfluss benötigt zuerst nachgewiesene C1/C2/R1/R2-Centanteile')
        event = source['event']; day = _euer_date(event['cash_date'], payload['euer_date'], payload['year_rule'])
        units = {value['unit_id']:value for value in source['units']}
        if not isinstance(payload['lines'], list) or len(payload['lines']) != len(units) or not units:
            raise Problem(400, 'Jeden dokumentierten Geldanteil genau einmal ausdrücklich einordnen')
        seen = set(); postings = []; source_key = 'cash:'+event['id']
        payment = event['source']['kind'] == 'payment'; refund = payment and event['direction'] == 'out'
        input_decision = None
        if not payment:
            original = event['source']['snapshot']['original_sha256']
            input_decision = ledger['active'].get('input_vat:'+original)
            if not input_decision:
                raise Problem(409, 'Vorsteuerrecht des Originalbelegs zuerst ausdrücklich prüfen, auch bei 0,00 Abzug')
            decision = input_decision['effect']
            if (any(decision['source']['receipt'][key] != event['source']['snapshot'][key] for key in
                    ('receipt_id','original_sha256','net','tax','gross','currency')) or decision['payload']['entitlement_date'] > event['cash_date']):
                raise Problem(409, 'Belegprüfung/Vorsteuerzeitpunkt passt nicht zu diesem unterstützten Zahlungsfall')
            if 'external_cash:'+original in ledger['active']:
                raise Problem(409, 'Dasselbe Original ist bereits als gesonderte Geldbewegung gebucht')
        for row in payload['lines']:
            _shape(row, set(_MONEY) | {'unit_id','category','account','vat_account'}); _hash(row['unit_id'])
            _account(row['account']); _account(row['vat_account'])
            if row['unit_id'] not in units or row['unit_id'] in seen:
                raise Problem(400, 'Unbekannter oder doppelter dokumentierter Geldanteil')
            seen.add(row['unit_id']); unit = units[row['unit_id']]
            values = {key:_amount(row[key]) for key in _MONEY}; net = _cents(unit['net']); tax = _cents(unit['tax'])
            bn, dn, bt, iv, tc = (values[key] for key in _MONEY)
            if dn > bn or bn > net or iv+tc > bt or bt > tax:
                raise Problem(400, 'Betriebliche, private und abziehbare Cents überschreiten ihren Beleganteil')
            if payment:
                if (row['category'] != 'sales' or bn != net or bt != tax or dn or iv or tc
                        or unit['tax_category'] != 'S' or unit['rate'] not in ('19', '19.00', '7', '7.00')):
                    raise Problem(409, 'Unterstützt sind ausdrücklich geprüfte inländische voll betriebliche 19-/7-Prozent-Erlöse')
                sign = -1 if refund else 1
                postings += [_posting('euer','sales',sign*net,day,row['account'],source_key),
                             _posting('euer','vat_collected',sign*tax,day,row['vat_account'],source_key),
                             _posting('vat','output_vat',sign*tax,event['cash_date'],row['vat_account'],source_key)]
            else:
                if row['category'] not in _EXPENSE:
                    raise Problem(400, 'Unterstützte laufende Ausgabe oder Anlageanschaffung auswählen')
                if row['category'] == 'asset_acquisition' and (dn or tc):
                    raise Problem(400, 'Anlagebasis wird nicht sofort als laufender Aufwand abgezogen')
                postings += [_posting('euer',row['category'],-dn-tc,day,row['account'],source_key),
                             _posting('euer','paid_input_vat',-iv,day,row['vat_account'],source_key),
                             _posting('asset' if row['category']=='asset_acquisition' else 'nondeductible',row['category'],
                                      -(bn-dn+bt-iv-tc),day,row['account'],source_key),
                             _posting('neutral','private_portion',-(net-bn+tax-bt),day,row['account'],source_key)]
        if input_decision:
            original = event['source']['snapshot']['original_sha256']
            used = sum(_amount(line['deductible_input_tax']) for value in ledger['active'].values()
                       if value['effect']['operation'] == 'cash' and value['target'] != source_key
                       and value['effect']['source']['event']['source']['kind'] == 'receipt'
                       and value['effect']['source']['event']['source']['snapshot']['original_sha256'] == original
                       for line in value['effect']['payload']['lines'])
            if used+sum(_amount(row['deductible_input_tax']) for row in payload['lines']) > _amount(input_decision['effect']['payload']['deductible_tax']):
                raise Problem(400, 'Bezahlte abziehbare Vorsteuer überschreitet die geprüfte Berechtigung des Originals')
            related=[value['effect'] for value in ledger['active'].values() if value['effect']['operation']=='cash' and value['target']!=source_key
                     and value['effect']['source']['event']['source']['kind']=='receipt'
                     and value['effect']['source']['event']['source']['snapshot']['original_sha256']==original]
            paid=sum(_amount(value['source']['event']['amount']) for value in related)+_amount(event['amount'])
            if paid==_amount(event['source']['snapshot']['gross']) and used+sum(_amount(row['deductible_input_tax']) for row in payload['lines'])!=_amount(input_decision['effect']['payload']['deductible_tax']):
                raise Problem(400,'Bei vollständiger Zahlung muss die bezahlte abziehbare Vorsteuer die geprüfte Originalberechtigung genau erreichen')
            asset=ledger['active'].get('asset:'+original)
            all_lines=[line for value in related for line in value['payload']['lines']]+payload['lines']
            if asset:
                if any(line['category']!='asset_acquisition' and _amount(line['business_net']) for line in all_lines):
                    raise Problem(409,'Registrierte Anlage darf nicht gleichzeitig laufender Nettoaufwand sein')
                expected_basis=sum(_amount(line['business_net'])+_amount(line['business_tax'])-_amount(line['deductible_input_tax']) for line in all_lines)
                if paid==_amount(event['source']['snapshot']['gross']) and expected_basis!=_amount(asset['effect']['payload']['business_basis']):
                    raise Problem(400,'Vollständig bezahlte betriebliche Anlagebasis muss mit dem Anlagenverzeichnis übereinstimmen')
        return source, source_key, [value for value in postings if _cents(value['amount'])], dict(date=day,cash_date=event['cash_date'],gross=event['amount'])

    def _prepare_input_vat(self, actor, payload, ledger, historical):
        _shape(payload, 'receipt_id source_hash invoice_received_date service_date prepayment payment_event_id entitlement_date deductible_tax account conditions_confirmed')
        identifier(payload['receipt_id']); _hash(payload['source_hash']); _account(payload['account'])
        if payload['conditions_confirmed'] is not True or type(payload['prepayment']) is not bool:
            raise Problem(400, 'Inländische ordnungsgemäße Rechnung, betriebliche Leistung und Vorsteuerrecht ausdrücklich prüfen')
        source = historical or self._receipt_source(actor, payload['receipt_id'])
        if source['source_hash'] != payload['source_hash']:
            raise Problem(409, 'Geprüftes Original wurde geändert')
        receipt = source['receipt']; amount = _amount(payload['deductible_tax'])
        if any(value['effect'] and value['effect']['operation']=='external_cash' and value['target']=='external_cash:'+receipt['original_sha256']
               for value in ledger['entries']):
            raise Problem(409,'Zahlungsnachweis einer Kapital-/Finanzamtsbewegung ist keine Vorsteuerrechnung')
        if amount > _amount(receipt['tax']):
            raise Problem(400, 'Abziehbare Vorsteuer überschreitet die belegte Steuer')
        iso_date(payload['invoice_received_date']); iso_date(payload['entitlement_date'])
        if payload['invoice_received_date'] < receipt['issue_date']:
            raise Problem(400, 'Rechnungseingang darf nicht vor Rechnungsdatum liegen')
        if payload['prepayment']:
            identifier(payload['payment_event_id'])
            if payload['service_date'] is not None:
                raise Problem(400, 'Vorauszahlung und bereits ausgeführte Leistung getrennt prüfen')
            event = Accounting(self.office)._event(actor, payload['payment_event_id'])
            if (event['source']['kind'] != 'receipt' or event['source']['snapshot']['receipt_id'] != receipt['receipt_id']
                    or event['source']['snapshot']['review_sha256'] != receipt['review_sha256'] or event['amount'] != receipt['gross']):
                raise Problem(409, 'Unterstützte Vorauszahlung benötigt genau die vollständige belegte Rechnungsauszahlung')
            source = dict(source, payment_event=event)
            earliest = max(payload['invoice_received_date'], event['cash_date'])
        else:
            iso_date(payload['service_date'])
            if payload['payment_event_id'] is not None:
                raise Problem(400, 'Reguläre Vorsteuer wird aus Rechnung und Leistung bestimmt')
            earliest = max(payload['invoice_received_date'], payload['service_date'])
        if payload['entitlement_date'] != earliest:
            raise Problem(400, 'Vorsteuerdatum muss dem bestätigten Eintritt aller Voraussetzungen entsprechen')
        target = 'input_vat:'+receipt['original_sha256']
        used = sum(_amount(line['deductible_input_tax']) for value in ledger['active'].values()
                   if value['effect']['operation'] == 'cash' and value['effect']['source']['event']['source']['kind'] == 'receipt'
                   and value['effect']['source']['event']['source']['snapshot']['original_sha256'] == receipt['original_sha256']
                   for line in value['effect']['payload']['lines'])
        if amount < used:
            raise Problem(409, 'Bereits gebuchte Vorsteuerzahlungen zuerst berichtigen')
        postings = [_posting('vat','input_vat',-amount,earliest,payload['account'],target)] if amount else []
        return source, target, postings, dict(date=earliest, reviewed_tax=receipt['tax'],deductible_tax=payload['deductible_tax'])

    def _prepare_external_cash(self, actor, payload, ledger, historical):
        _shape(payload, 'receipt_id source_hash account_id account_revision evidence_key cash_date amount direction category euer_date year_rule account')
        identifier(payload['receipt_id']); identifier(payload['account_id']); _hash(payload['source_hash']); _account(payload['account'])
        _line(payload['evidence_key'],'Eindeutige Zahlungsnachweis-ID',200); iso_date(payload['cash_date'])
        if type(payload['account_revision']) is not int or payload['account_revision'] < 1:
            raise Problem(400, 'Geldkontoversion erwartet')
        source = historical or self._receipt_source(actor,payload['receipt_id'])
        if source['source_hash'] != payload['source_hash']:
            raise Problem(409, 'Originalstand wurde geändert')
        receipt = source['receipt']; amount = _amount(payload['amount'],True)
        if any(prefix+receipt['original_sha256'] in ledger['active'] for prefix in ('input_vat:','asset:')):
            raise Problem(409,'Original ist bereits als Lieferanten-/Anlagenbeleg eingeordnet; Zweck zuerst ausdrücklich berichtigen')
        if not isinstance(payload['category'],str) or payload['category'] not in _EXTERNAL or payload['direction'] != _EXTERNAL[payload['category']]:
            raise Problem(400, 'Passende ausdrücklich belegte Steuer- oder Kapitalgeldbewegung auswählen')
        if amount != _amount(receipt['gross']) or _amount(receipt['tax']):
            raise Problem(400, 'Einmaliger vollständiger Zahlungsnachweis ohne ausgewiesene Umsatzsteuer erforderlich')
        account = Accounting(self.office)._account(payload['account_id'], payload['account_revision'])
        if not historical and (not account['active'] or Accounting(self.office)._account(payload['account_id'])['revision'] != payload['account_revision']):
            raise Problem(409, 'Aktuelles aktives Geldkonto erforderlich')
        if self.office.db.execute('SELECT 1 FROM business_accounting_receipt_bindings WHERE original_sha256=?', (receipt['original_sha256'],)).fetchone():
            raise Problem(409, 'Original ist bereits an das bestehende Geldflussjournal gebunden')
        target = 'external_cash:'+receipt['original_sha256']
        normalized = _evidence(payload['evidence_key'])[1]
        if not historical:
            from business_payroll_cash import ensure_cash_available
            ensure_cash_available(self.office,payload['account_id'],normalized,receipt['original_sha256'])
            from travel_allowance_cash import ensure_cash_available as travel_available
            travel_available(self.office,payload['account_id'],normalized,receipt['original_sha256'])
        if self.office.db.execute('SELECT 1 FROM business_accounting_cash_events WHERE account_id=? AND evidence_key=?',
                                  (payload['account_id'],normalized)).fetchone():
            raise Problem(409, 'Zahlungsnachweis ist bereits im bestehenden Geldflussjournal vorhanden')
        for value in ledger['active'].values():
            effect = value['effect']
            if effect['operation']=='external_cash' and value['target'] != target and effect['payload']['account_id']==payload['account_id'] and _evidence(effect['payload']['evidence_key'])[1]==normalized:
                raise Problem(409, 'Zahlungsnachweis ist bereits gebucht')
        day = _euer_date(payload['cash_date'],payload['euer_date'],payload['year_rule'])
        taxable = payload['category'] in ('vat_payment','vat_refund')
        if not taxable and payload['year_rule'] != {'kind':'cash'}:
            raise Problem(400, 'Neutrale Kapitalbewegungen werden nicht über die Zehntagesregel verschoben')
        signed = amount if payload['direction']=='in' else -amount
        return source,target,[_posting('euer' if taxable else 'neutral',payload['category'],signed,day,payload['account'],target)],dict(
            date=day,cash_date=payload['cash_date'],gross=payload['amount'],cash_account=account,evidence_key=normalized)

    def _prepare_payroll_cash(self,actor,payload,ledger,historical):
        from business_payroll_cash import public_source,financial_access,_instance
        _shape(payload,'batch_id revision source_hash accounts');identifier(payload['batch_id']);_hash(payload['source_hash'])
        if type(payload['revision']) is not int or payload['revision']<1 or not isinstance(payload['accounts'],dict):
            raise Problem(400,'Positive Lohnzahlungsrevision und ausdrücklich geprüfte Kontenzuordnung erforderlich.')
        financial_access(self.office,actor)
        source=historical or public_source(self.office,payload['batch_id'],payload['revision'])
        if (source['id']!=payload['batch_id'] or source['revision']!=payload['revision'] or source['source_hash']!=payload['source_hash']
                or not historical and (public_source(self.office,payload['batch_id'])['revision']!=payload['revision'] or source['instance_id']!=_instance(self.office))):
            raise Problem(409,'Genau aktuelle öffentliche Lohnzahlungsquelle erforderlich.')
        categories={key for item in source['cash_movements'] for key in item['categories']}
        if set(payload['accounts'])!=categories:raise Problem(400,'Jede tatsächliche Personalausgabenart genau einmal einem geprüften SKR04-Konto zuordnen.')
        for account in payload['accounts'].values():_account(account)
        target='payroll_cash:'+source['id'];postings=[]
        for movement in source['cash_movements']:
            sign=-1 if movement['direction']=='out' else 1
            for category,amount in movement['categories'].items():
                postings.append(_posting('euer',category,sign*_amount(amount,True),movement['date'],payload['accounts'][category],target))
        return source,target,postings,dict(date=source['date'],cash_dates=sorted({item['date'] for item in source['cash_movements']}),status=source['status'])

    def _prepare_travel_cash(self, actor, payload, ledger, historical):
        from travel_allowance_cash import installed
        from accounting_travel_sources import prepare
        if not installed(self.office):
            raise Problem(409, 'Reisekosten-Geldquellen sind noch nicht vollständig installiert.')
        return prepare(self,actor,payload,ledger,historical)

    def _prepare_asset(self, actor, payload, ledger, historical):
        _shape(payload,'receipt_id source_hash description business_basis use_start life_months account')
        identifier(payload['receipt_id']); _hash(payload['source_hash']); _line(payload['description'],'Anlagenbeschreibung',300); _account(payload['account'])
        iso_date(payload['use_start']); basis = _amount(payload['business_basis'],True)
        if type(payload['life_months']) is not int or not 12 <= payload['life_months'] <= 1200 or payload['life_months'] % 12:
            raise Problem(400, 'Ausdrücklich geprüfte lineare Nutzungsdauer in ganzen Jahren (12 bis 1200 Monate) erwartet')
        source = historical or self._receipt_source(actor,payload['receipt_id']); receipt=source['receipt']
        if not historical:
            from business_accounting_asset_openings import HistoricalAssets,installed as historical_assets_installed
            if historical_assets_installed(self.office) and any(entry['status']=='active' and entry['source_proof']['original']['sha256']==receipt['original_sha256']
                    for entry in HistoricalAssets(self.office)._ledger()['current'].values()):
                raise Problem(409,'Dieses Original ist bereits als historische Anlage übernommen; keine neue Anschaffung daraus anlegen.')
        if source['source_hash'] != payload['source_hash']:
            raise Problem(409,'Anlagenoriginal wurde geändert')
        vat = ledger['active'].get('input_vat:'+receipt['original_sha256'])
        if not vat:
            raise Problem(409,'Vorsteuerrecht des Anlagenoriginals zuerst prüfen')
        if basis > _amount(receipt['gross'])-_amount(vat['effect']['payload']['deductible_tax']):
            raise Problem(400,'Anlagebasis überschreitet Anschaffungskosten ohne abziehbare Vorsteuer')
        if payload['use_start'] < receipt['issue_date']:
            raise Problem(409,'Vorgezogene Nutzung/Eröffnungsbestand benötigt einen gesonderten belegten Übernahmefall')
        cash=[value['effect'] for value in ledger['active'].values() if value['effect']['operation']=='cash'
              and value['effect']['source']['event']['source']['kind']=='receipt'
              and value['effect']['source']['event']['source']['snapshot']['original_sha256']==receipt['original_sha256']]
        lines=[line for value in cash for line in value['payload']['lines']]
        if any(line['category']!='asset_acquisition' and _amount(line['business_net']) for line in lines):
            raise Problem(409,'Laufenden Nettoaufwand vor Anlageaufnahme ausdrücklich berichtigen')
        if sum(_amount(value['source']['event']['amount']) for value in cash)==_amount(receipt['gross']) and sum(
                _amount(line['business_net'])+_amount(line['business_tax'])-_amount(line['deductible_input_tax']) for line in lines)!=basis:
            raise Problem(400,'Anlagebasis muss den vollständig bezahlten betrieblichen Anschaffungsanteilen entsprechen')
        target='asset:'+receipt['original_sha256']
        return source,target,[],dict(date=payload['use_start'],method='linear',basis=payload['business_basis'],life_months=payload['life_months'],description=payload['description'])

    def _prepare_depreciation(self, actor, payload, ledger, historical):
        _shape(payload,'asset_entry_id year account'); identifier(payload['asset_entry_id']); year=_year(payload['year']); _account(payload['account'])
        asset=ledger['by_id'].get(payload['asset_entry_id'])
        if not asset or asset['effect']['operation']!='asset' or ledger['active'].get(asset['target'],{}).get('id') != asset['id']:
            raise Problem(409,'Aktives belegtes Anlagegut erforderlich')
        source=asset['effect']['source']; self._source_access(actor,source)
        setup=asset['effect']['payload']; start=date.fromisoformat(setup['use_start']); life=setup['life_months']; basis=_amount(setup['business_basis'])
        first=max(0,(year-start.year)*12+1-start.month); last=max(0,(year-start.year)*12+12-start.month+1)
        before=min(life,first); after=min(life,last)
        if after<=before:
            raise Problem(400,'Jahr liegt außerhalb der linearen Nutzungsdauer')
        def accrued(months):
            return int((Decimal(basis)*months/life).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        amount=accrued(after)-accrued(before); target='depreciation:'+asset['id']+':'+str(year)
        day=str(year)+'-12-31'
        return source,target,[_posting('euer','depreciation',-amount,day,payload['account'],target)],dict(
            date=day,asset_entry_id=asset['id'],basis=setup['business_basis'],months=after-before,amount=_money(amount),
            opening_book_value=_money(basis-accrued(before)),closing_book_value=_money(basis-accrued(after)))

    def _prepare_opening_year_values(self,actor,payload,ledger,historical):
        from accounting_year_opening_sources import prepare
        return prepare(self,actor,payload,ledger,historical)

    def _prepare_opening_item_cash(self,actor,payload,ledger,historical):
        from accounting_open_item_sources import prepare
        return prepare(self,actor,payload,ledger,historical)

    def _prepare_opening_depreciation(self,actor,payload,ledger,historical):
        from accounting_asset_opening_sources import prepare
        return prepare(self,actor,payload,ledger,historical)

    def _authorized_ledger(self, actor, ledger, write=False):
        seen=set()
        for entry in ledger['entries']:
            if entry['effect']:
                source=entry['effect']['source']; identity=source['source_hash']
                if identity not in seen:
                    self._source_access(actor,source,write); seen.add(identity)

    @staticmethod
    def _effect_dates(effect):
        days={value['date'] for value in effect['postings']}
        days.add(effect['details']['date'])
        if 'cash_date' in effect['details']:
            days.add(effect['details']['cash_date'])
        days.update(effect['details'].get('cash_dates',[]))
        if effect['operation']=='opening_year_values':
            from datetime import timedelta
            coverage=effect['details']['coverage'];current=date.fromisoformat(coverage['from'])
            while current.isoformat()<=coverage['through']:
                days.add(current.isoformat());current+=timedelta(days=1)
        return days

    def _counter_target(self, ledger, entry_id):
        identifier(entry_id); old=ledger['by_id'].get(entry_id)
        if not old or not old['effect'] or ledger['active'].get(old['target'],{}).get('id')!=entry_id:
            raise Problem(409,'Nur die aktive wirtschaftliche Einordnung kann berichtigt werden')
        operation=old['effect']['operation']
        if operation=='opening_depreciation' and any(value['effect']['operation']=='opening_depreciation'
                and value['effect']['source']['id']==old['effect']['source']['id']
                and value['effect']['payload']['year']>old['effect']['payload']['year'] for value in ledger['active'].values()):
            raise Problem(409,'Spätere Folgeabschreibungen dieser Anlagenfassung zuerst ausdrücklich gegenbuchen.')
        if operation=='asset' and any(value['effect']['operation']=='depreciation' and
                value['effect']['payload']['asset_entry_id']==entry_id for value in ledger['active'].values()):
            raise Problem(409,'Zugehörige Abschreibungen zuerst nachvollziehbar berichtigen')
        if operation=='input_vat':
            original=old['effect']['source']['receipt']['original_sha256']
            if any(value['effect']['operation'] in ('cash','asset') and (
                    value['effect']['source'].get('receipt',{}).get('original_sha256')==original or
                    value['effect']['source'].get('event',{}).get('source',{}).get('snapshot',{}).get('original_sha256')==original)
                   for value in ledger['active'].values()):
                raise Problem(409,'Abhängige Ausgaben-/Anlagenbuchungen zuerst berichtigen')
        return old

    def _catalog(self, actor, ledger):
        from business_finance import Finance
        from business_accounting_allocations import require_effective_payment_access
        items=[]; issues=[]; movements=[]; receipt_sources={}
        for row in self.office.db.execute('SELECT id FROM business_accounting_cash_events ORDER BY sequence').fetchall():
            source=self._cash_source(actor,row['id']); event=source['event']; target='cash:'+event['id']; current=ledger['active'].get(target)
            reasons=[]
            if _cents(source['undocumented_amount']): reasons.append('documentary_components_missing')
            if not current: reasons.append('cash_classification_missing')
            items.append(dict(kind='cash',id=event['id'],date=event['cash_date'],source=source,current=current,reasons=reasons))
            movements.append(dict(source_kind='cash_event',source_id=event['id'],account=event['account'],date=event['cash_date'],
                                  direction=event['direction'],amount=event['amount'],source_path=source['source_path']))
            for code in reasons: issues.append(dict(code=code,source_id=event['id'],date=event['cash_date'],source_path=source['source_path']))
        linked={row[0] for row in self.office.db.execute("SELECT source_id FROM business_accounting_source_links WHERE kind='payment'").fetchall()}
        for row in self.office.db.execute('SELECT id,booking_date,amount FROM business_payments ORDER BY booking_date,id').fetchall():
            if row['id'] not in linked:
                require_effective_payment_access(self.office,actor,row['id'],'finance.read')
                item=dict(kind='payment_import',id=row['id'],date=row['booking_date'],amount=row['amount'],source_path='/accounting/sources/payments',reasons=['cash_import_missing'],current=None)
                items.append(item); issues.append(dict(code='cash_import_missing',source_id=row['id'],date=row['booking_date'],source_path=item['source_path']))
        for row in self.office.db.execute('SELECT id FROM business_incoming_receipts ORDER BY created_at,id').fetchall():
            receipt=Finance(self.office).receipt(actor,row['id'])
            # Finance DTO fields are intentionally read from its immutable review
            # row rather than inferring any zero amount from a missing review.
            stored=self.office.db.execute('SELECT payload_json FROM business_receipt_reviews WHERE receipt_id=? ORDER BY revision DESC LIMIT 1',(row['id'],)).fetchone()
            reviewed=json.loads(stored['payload_json']) if stored else None
            if not reviewed or reviewed['status']!='reviewed' or _amount(reviewed['gross'])==0:
                existing=[value for value in ledger['active'].values() if value['effect']['source'].get('receipt',{}).get('original_sha256')==receipt['sha256']]
                if reviewed and reviewed['status']=='rejected' and not existing:
                    continue
                if reviewed and _amount(reviewed['gross'])==0 and not existing:
                    continue
                day=receipt['created_at'][:10]
                code='original_review_changed' if existing else 'original_review_missing'
                if existing:day=existing[0]['effect']['details']['date']
                items.append(dict(kind='receipt_review',id=row['id'],date=day,source_path='/finance/receipts/'+row['id'],current=None,reasons=[code]))
                issues.append(dict(code=code,source_id=row['id'],date=day,source_path='/finance/receipts/'+row['id']))
                continue
            source=self._receipt_source(actor,row['id']); original=source['receipt']['original_sha256']; receipt_sources[original]=source
            vat=ledger['active'].get('input_vat:'+original); external=ledger['active'].get('external_cash:'+original); asset=ledger['active'].get('asset:'+original)
            reserved=next((value for value in ledger['entries'] if value['effect'] and value['effect']['operation']=='external_cash'
                           and value['target']=='external_cash:'+original),None)
            reasons=[]
            if reserved and not external:reasons.append('external_cash_classification_missing')
            elif not vat and not external:reasons.append('input_vat_decision_missing')
            for existing in (vat,external,asset):
                if existing and existing['effect']['source']['source_hash']!=source['source_hash']:
                    reasons.append('original_review_changed'); break
            if any(value and value['effect']['source']['receipt']['receipt_id']!=row['id'] for value in (vat,external,asset)):
                reasons.append('duplicate_original')
            items.append(dict(kind='receipt',id=row['id'],date=reviewed['issue_date'],source=source,current=vat,external_cash=external,asset=asset,reasons=reasons,
                              source_role='payment_evidence' if reserved else 'trade_receipt'))
            for code in reasons: issues.append(dict(code=code,source_id=row['id'],date=reviewed['issue_date'],source_path=source['source_path']))
        for entry in ledger['active'].values():
            effect=entry['effect']
            if effect['operation']=='external_cash':
                payload=effect['payload']; details=effect['details']
                movements.append(dict(source_kind='reviewed_external_cash',source_id=entry['id'],account=details['cash_account'],date=payload['cash_date'],
                                      direction=payload['direction'],amount=payload['amount'],source_path=effect['source']['source_path']))
            if effect['operation']=='cash' and effect['source']['event']['source']['kind']=='receipt':
                original=effect['source']['event']['source']['snapshot']['original_sha256']
                if any(line['category']=='asset_acquisition' for line in effect['payload']['lines']) and 'asset:'+original not in ledger['active']:
                    issues.append(dict(code='asset_register_missing',source_id=entry['id'],date=effect['details']['date'],source_path=effect['source']['source_path']))
        from business_payroll_cash import installed as payroll_cash_installed,public_source as payroll_cash_source
        payroll_present=False
        if payroll_cash_installed(self.office):
            for row in self.office.db.execute('SELECT DISTINCT id FROM business_payroll_cash_batches ORDER BY id'):
                payroll_present=True;source=payroll_cash_source(self.office,row['id']);target='payroll_cash:'+source['id'];current=ledger['active'].get(target);reasons=[]
                if not current and source['status']!='void':reasons.append('payroll_cash_classification_missing')
                if current and current['effect']['source']['source_hash']!=source['source_hash']:reasons.append('payroll_cash_source_changed')
                items.append(dict(kind='payroll_cash',id=source['id'],date=source['date'],source=source,current=current,reasons=reasons))
                for movement in source['cash_movements']:
                    movements.append(dict(source_kind='payroll_cash',source_id=movement['id'],account=movement['account'],date=movement['date'],
                        direction=movement['direction'],amount=movement['amount'],source_path=source['source_path']))
                for code in reasons:
                    dates={item['date'] for item in source['cash_movements']} or {source['date']}
                    if current:dates.update(self._effect_dates(current['effect']))
                    issues.extend(dict(code=code,source_id=source['id'],date=day,source_path=source['source_path']) for day in sorted(dates))
        from accounting_travel_sources import catalog as travel_catalog
        travel_items,travel_issues,travel_movements=travel_catalog(self,actor,ledger)
        items.extend(travel_items);issues.extend(travel_issues);movements.extend(travel_movements)
        from accounting_asset_opening_sources import catalog as historical_asset_catalog
        asset_items,asset_issues=historical_asset_catalog(self,actor)
        items.extend(asset_items);issues.extend(asset_issues)
        from accounting_open_item_sources import catalog as opening_item_catalog
        opening_items,opening_issues,opening_movements=opening_item_catalog(self,actor,ledger)
        items.extend(opening_items);issues.extend(opening_issues);movements.extend(opening_movements)
        from accounting_year_opening_sources import catalog as year_catalog
        year_items,year_issues=year_catalog(self,actor,ledger)
        items.extend(year_items);issues.extend(year_issues)
        totals={}
        for value in movements:
            key=value['account']['id']; total=totals.setdefault(key,dict(account=value['account'],inflows=0,outflows=0))
            total['inflows' if value['direction']=='in' else 'outflows']+=_amount(value['amount'])
        accounts=[dict(account=value['account'],inflows=_money(value['inflows']),outflows=_money(value['outflows']),
                       movement_net=_money(value['inflows']-value['outflows']),opening_balance=None,balance=None) for value in totals.values()]
        movements.sort(key=lambda value:(value['date'],value['source_kind'],value['source_id']))
        return dict(items=items,issues=issues,cash_movements=movements,account_movements=accounts,
                    cash_scope='existing_cash_events_reviewed_external_payroll_travel_and_opening_item_cash' if opening_items else 'existing_cash_events_reviewed_external_payroll_and_travel_cash' if travel_items else 'existing_cash_events_reviewed_external_and_payroll_cash' if payroll_present else 'existing_cash_events_and_reviewed_external_cash',opening_balances_available=False)

    def _report(self, actor, year, ledger, *, month=None):
        _year(year); catalog=self._catalog(actor,ledger)
        prefix=month or str(year)
        postings=[dict(value,entry_id=entry['id'],sequence=entry['sequence']) for entry in ledger['entries']
                  for value in entry['postings'] if value['date'].startswith(prefix)]
        issues=[value for value in catalog['issues'] if value['date'].startswith(prefix)]
        profile=self._profile()
        if not self._configured(profile): issues.append(dict(code='profile_incomplete',source_id=None,date=prefix+'-01' if month else prefix+'-01-01',source_path='/accounting/profile'))
        elif max(profile['profile']['bookkeeping_start'],profile['profile']['vat_effective_from']) > (prefix+'-01' if month else prefix+'-01-01'):
            issues.append(dict(code='partial_period_profile_coverage',source_id=profile['id'],date=prefix,source_path='/accounting/profile'))
        assets=[]
        for entry in ledger['active'].values():
            effect=entry['effect']
            if effect['operation']!='asset': continue
            details=effect['details']; start=date.fromisoformat(details['date'])
            if start.year>year: continue
            key='depreciation:'+entry['id']+':'+str(year)
            still_used=(year-start.year)*12+1-start.month < details['life_months']
            if still_used and key not in ledger['active'] and (month is None or month.endswith('-12')):
                issues.append(dict(code='depreciation_missing',source_id=entry['id'],date=str(year)+'-12-31',source_path=effect['source']['source_path']))
            assets.append(dict(entry_id=entry['id'],description=details['description'],basis=details['basis'],use_start=details['date'],
                               life_months=details['life_months'],depreciation=ledger['active'].get(key)))
        try:
            from business_schema import require_financial_release
            require_financial_release(self.office)
        except Problem:
            issues.append(dict(code='restore_reconciliation_pending',source_id=None,date=prefix,source_path=None))
        from accounting_asset_opening_sources import report_assets
        historical_assets,historical_issues=report_assets(self,actor,year,ledger,month=month)
        issues.extend(historical_issues)
        grouped={}
        for value in postings:
            key=(value['ledger'],value['category']); grouped[key]=grouped.get(key,0)+_cents(value['amount'])
        categories=[dict(ledger=key[0],category=key[1],amount=_money(amount)) for key,amount in sorted(grouped.items())]
        income=sum(amount for (kind,category),amount in grouped.items() if kind=='euer' and category in ('sales','vat_collected','vat_refund'))
        expenses=-sum(amount for (kind,category),amount in grouped.items() if kind=='euer' and category not in ('sales','vat_collected','vat_refund'))
        output=sum(amount for (kind,category),amount in grouped.items() if kind=='vat' and category=='output_vat')
        iv=-sum(amount for (kind,category),amount in grouped.items() if kind=='vat' and category=='input_vat')
        source_manifest=[]
        for entry in ledger['entries']:
            if entry['effect'] and (any(value['date'].startswith(prefix) for value in entry['postings']) or entry['effect']['details']['date'].startswith(prefix)):
                source=entry['effect']['source']
                source_manifest.append(dict(entry_id=entry['id'],entry_hash=entry['entry_hash'],source_hash=source['source_hash'],source_path=source['source_path'],kind=source['kind']))
        movements=[value for value in catalog['cash_movements'] if value['date'].startswith(prefix)]
        periods=[value for key,value in sorted(ledger['periods'].items()) if key.startswith(prefix)]
        from accounting_year_opening_sources import report_projection
        year_values,covered=report_projection(ledger,profile,year,month)
        if covered:issues=[row for row in issues if row['code']!='partial_period_profile_coverage']
        complete=not issues
        return dict(**({'historical_year_values':year_values} if year_values else {}),year=year,period=month,currency='EUR',rule_version=RULE_VERSION,account_frame='SKR04',scope='recorded_sources',
                    profile=profile,revision=len(ledger['entries']),state_hash=_state_hash(ledger['entries']),
                    coverage_start=profile['profile']['bookkeeping_start'] if profile else None,
                    complete_for_recorded_sources=complete,official_tax_return=False,limitations=list(_LIMITATIONS),
                    totals=dict(confirmed_income=_money(income),confirmed_expenses=_money(expenses),confirmed_surplus=_money(income-expenses),
                                euer_surplus=_money(income-expenses) if complete else None,confirmed_output_vat=_money(output),
                                confirmed_input_vat=_money(iv),vat_balance=_money(output-iv) if complete else None),
                    categories=categories,postings=postings,issues=issues,assets=assets,historical_assets=historical_assets,periods=periods,sources=source_manifest,
                    cash_movements=movements,cash_scope=catalog['cash_scope'],opening_balances_available=False)

    @staticmethod
    def _csv(report):
        stream=io.StringIO(newline=''); writer=csv.writer(stream,delimiter=';',lineterminator='\r\n')
        writer.writerow(['entry_id','sequence','date','ledger','category','amount_eur','account_skr04','source_key'])
        for value in report['postings']:
            cells=[str(value[key]) for key in ('entry_id','sequence','date','ledger','category','amount','account','source_key')]
            # All textual cells are controlled identifiers; only numeric amount
            # is signed. Protect future caller-defined additions regardless.
            writer.writerow([("'"+cell if index!=5 and cell[:1] in ('=','+','-','@','\t','\r') else cell) for index,cell in enumerate(cells)])
        return stream.getvalue()

    def _prepare(self, actor, ledger, data):
        if data['expected_revision']!=len(ledger['entries']) or data['state_hash']!=_state_hash(ledger['entries']):
            raise Problem(409,'Journal wurde geändert; aktuelle Vorschau erneut prüfen')
        operation=data['operation']; payload=data['payload']; profile=self._profile()
        effect=None; old=None; artifact=None; target=None; control=None
        if operation in _ECONOMIC:
            effect=self._economic(actor,operation,payload,ledger,profile)
        elif operation in ('reverse','correct'):
            _shape(payload,'entry_id' if operation=='reverse' else 'entry_id operation payload')
            old=self._counter_target(ledger,payload['entry_id']); target=old['target']
            if operation=='correct':
                if payload['operation']!=old['effect']['operation']:
                    raise Problem(400,'Berichtigung muss denselben wirtschaftlichen Quellenfall ersetzen')
                effect=self._economic(actor,payload['operation'],payload['payload'],ledger,profile)
                if effect['target']!=target:
                    raise Problem(400,'Berichtigung darf keine andere wirtschaftliche Quelle ersetzen')
        elif operation=='period':
            _shape(payload,'period action expected_period_revision attestation'); period=_period(payload['period'])
            _shape(payload['attestation'],'bank_reconciled originals_complete special_cases_reviewed')
            if any(type(value) is not bool for value in payload['attestation'].values()) or payload['action'] not in ('close','reopen'):
                raise Problem(400,'Ausdrücklichen Periodenvorgang und Prüfaussagen erwartet')
            previous=ledger['periods'].get(period)
            if type(payload['expected_period_revision']) is not int or payload['expected_period_revision']!=(previous['revision'] if previous else 0):
                raise Problem(409,'Periodenstand wurde geändert')
            if payload['action']=='close':
                if previous and previous['status']=='closed': raise Problem(409,'Periode ist bereits gesperrt')
                if not all(payload['attestation'].values()): raise Problem(400,'Kontoabgleich, Originalvollständigkeit und Sonderfälle ausdrücklich prüfen')
                report=self._report(actor,int(period[:4]),ledger,month=period)
                if report['issues']: raise Problem(409,'Offene Quellen oder Steuerfälle verhindern den Periodenabschluss')
                control=dict(report_sha256=_sha(canonical(report)),report=report)
                from business_bank_reconciliation import period_closure_proof
                bank_proof=period_closure_proof(self.office,actor,period)
                if bank_proof is not None:
                    control['bank_reconciliation']=bank_proof
            elif not previous or previous['status']!='closed':
                raise Problem(409,'Nur gesperrte Periode kann begründet wieder geöffnet werden')
            target='period:'+period
        else:
            _shape(payload,'year'); report=self._report(actor,_year(payload['year']),ledger); csv_value=self._csv(report)
            artifact=dict(format='smartplan_euer_review_v1',report=report,report_sha256=_sha(canonical(report)),csv=csv_value,csv_sha256=_sha(csv_value),
                          official_tax_return=False,datev_certified=False,generated_at=None)
            target='export:'+str(payload['year'])
        if effect:
            self._source_access(actor,effect['source'],True); target=effect['target']
            if target in ledger['active'] and not old:
                raise Problem(409,'Quelle ist bereits gebucht; vorhandenen Eintrag ausdrücklich berichtigen')
        postings=(_negate(old['effect']['postings']) if old else [])+(effect['postings'] if effect else [])
        self._unlocked(ledger,postings)
        for value in (effect,old['effect'] if old else None):
            if value:
                self._unlocked(ledger,[dict(date=day) for day in self._effect_dates(value)])
        preview=dict({key:data[key] for key in _INPUT},profile=profile,rule_version=RULE_VERSION,target=target,
                     effect=effect,reverses=old['id'] if old else None,postings=postings,artifact=artifact,control=control)
        return dict(preview,preview_hash=_sha(canonical(preview)))

    def state(self,actor):
        with transaction(self.office), self._source_read():
            fresh=self._access(actor); ledger=self._ledger(); self._authorized_ledger(fresh,ledger)
            try:
                self._access(fresh,True); self._gate(); writes=True
            except Problem as error:
                if error.status not in (403,409,423): raise
                writes=False
            profile=self._profile()
            from business_accounting_openings import entrypoint as opening_entrypoint
            from business_accounting_asset_openings import entrypoint as historical_asset_entrypoint
            return dict(revision=len(ledger['entries']),state_hash=_state_hash(ledger['entries']),profile=profile,
                        profile_ready=self._configured(profile),writes_allowed=writes,rule_version=RULE_VERSION,account_frame='SKR04',
                        categories=dict(income=['sales'],expense=list(_EXPENSE),external_cash=dict(_EXTERNAL),
                            payroll_cash=['payroll_net','payroll_employee_tax','payroll_employee_social','payroll_employer_social','payroll_employer_levies','payroll_employer_flat_tax'],
                            travel_cash=['travel_allowance']),
                        periods=list(ledger['periods'].values()),limitations=list(_LIMITATIONS),official_tax_return=False,
                        opening_balances_path=opening_entrypoint(self.office,fresh),historical_assets_path=historical_asset_entrypoint(self.office,fresh))

    def sources(self,actor):
        with transaction(self.office), self._source_read():
            fresh=self._access(actor); ledger=self._ledger(); self._authorized_ledger(fresh,ledger)
            from business_accounting_openings import entrypoint as opening_entrypoint
            from business_accounting_asset_openings import entrypoint as historical_asset_entrypoint
            return dict(self._catalog(fresh,ledger),opening_balances_path=opening_entrypoint(self.office,fresh),historical_assets_path=historical_asset_entrypoint(self.office,fresh))

    def journal(self,actor,limit=50,offset=0):
        _page(limit,offset)
        with transaction(self.office), self._source_read():
            fresh=self._access(actor); ledger=self._ledger(); self._authorized_ledger(fresh,ledger)
            return _paged(list(reversed(ledger['entries'])),limit,offset)

    def report(self,actor,year):
        with transaction(self.office), self._source_read():
            fresh=self._access(actor); ledger=self._ledger(); self._authorized_ledger(fresh,ledger)
            return self._report(fresh,_year(year),ledger)

    def exported(self,actor,entry_id):
        identifier(entry_id)
        with transaction(self.office), self._source_read():
            fresh=self._access(actor); ledger=self._ledger(); self._authorized_ledger(fresh,ledger)
            entry=ledger['by_id'].get(entry_id)
            if not entry or entry['operation']!='export': raise Problem(404,'Prüfpaket nicht verfügbar')
            return dict(entry_id=entry['id'],entry_hash=entry['entry_hash'],created_at=entry['created_at'],**entry['artifact'])

    def year_evidence(self,actor,entry_id,*,archive=False):
        """Read-only supplement; old report and source acceptance remain intact."""
        from accounting_year_package_v1 import sha,BASE
        from accounting_year_package_v2 import build_selected as build
        from workspace_api import BinaryAttachment
        try:
            raw,manifest=build(self.office,actor,entry_id)
        except (ValueError,KeyError,TypeError,IndexError,ArithmeticError):
            raise Problem(409,'Der ursprüngliche Jahresnachweis ist unvollständig oder seine Bindung wurde verändert.') from None
        filename='smartplan-jahresnachweis-'+str(manifest['year'])+'-'+entry_id+'.zip'
        if archive:return BinaryAttachment(raw,filename)
        return dict(format=manifest['format'],schema_version=1,instance_id=manifest['instance_id'],year=manifest['year'],
            export_id=entry_id,export_hash=manifest['export_hash'],sha256=sha(raw),size=len(raw),filename=filename,
            archive_path=BASE+entry_id+'/evidence/archive',original_count=len(manifest['originals']),
            original_year_complete=manifest['original_year_complete'],private_source_boundaries=manifest['private_source_boundaries'],
            official_tax_return=False,datev_certified=False,private_personnel_originals_included=False)

    def preview(self,actor,data):
        self._inputs(data)
        with transaction(self.office), self._source_read():
            from business_accounting_asset_openings import HistoricalAssets,installed as historical_assets_installed
            if historical_assets_installed(self.office):HistoricalAssets(self.office)._lock()
            fresh=self._access(actor,True); self._gate(); ledger=self._ledger(); self._authorized_ledger(fresh,ledger,True)
            return self._prepare(fresh,ledger,data)

    def confirm(self,actor,data):
        self._inputs(data,True)
        with transaction(self.office), self._source_read():
            from business_accounting_asset_openings import HistoricalAssets,installed as historical_assets_installed
            if historical_assets_installed(self.office):HistoricalAssets(self.office)._lock()
            fresh=self._access(actor,True); self._gate(); ledger=self._ledger(); self._authorized_ledger(fresh,ledger,True)
            digest=_sha(canonical(data))
            receipt=self.office.db.execute('SELECT * FROM business_euer_requests WHERE user_id=? AND request_id=?',(fresh['id'],data['request_id'])).fetchone()
            if receipt:
                if receipt['request_hash']!=digest: raise Problem(409,'Vorgangs-ID wurde mit anderem Inhalt verwendet')
                return ledger['by_id'][receipt['entry_id']]
            try:
                preview=self._prepare(fresh,ledger,data)
                if preview['preview_hash']!=data['preview_hash']: raise Problem(409,'Genau passende aktuelle Vorschau erforderlich')
            except Problem as error:
                if error.status!=409: raise
                raise Problem(409,error.message,request_resolution='not_accepted') from None
            entry={key:value for key,value in preview.items() if key not in ('expected_revision','state_hash')}
            entry.update(id=uuid.uuid4().hex,sequence=len(ledger['entries'])+1,previous_hash=data['state_hash'],created_by=fresh['id'],created_at=self.now())
            encoded=canonical(entry); entry_hash=_sha(encoded)
            self.office.db.execute('INSERT INTO business_euer_entries(id,sequence,operation,target,previous_hash,entry_json,entry_sha256,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                (entry['id'],entry['sequence'],entry['operation'],entry['target'],entry['previous_hash'],encoded,entry_hash,fresh['id'],entry['created_at']))
            self.office.db.execute('INSERT INTO business_euer_requests(user_id,request_id,request_json,request_hash,entry_id) VALUES(?,?,?,?,?)',
                                   (fresh['id'],data['request_id'],canonical(data),digest,entry['id']))
            self.office.audit(fresh,'business.accounting.euer_'+entry['operation'],entry['id'])
            return dict(entry,entry_hash=entry_hash)


def installed(office):
    from business_schema import _tables
    tables=_tables(office); present=set(_TABLES)&tables
    if not present:return False
    if present!=set(_TABLES):raise Problem(409,'EÜR-Journal unvollständig installiert')
    return True


def ensure_cash_identity_available(office,account_id,evidence_key,original_sha256=None,*,payroll_batch_id=None,travel_payment_id=None,opening_payment_id=None):
    """Existing cash writer calls this under its own serialized transaction.

    These immutable original identities remain reserved after a counter-posting;
    corrections must use this same EÜR source, never become a second cash event.
    """
    from business_payroll_cash import ensure_cash_available
    ensure_cash_available(office,account_id,evidence_key,original_sha256 if payroll_batch_id is None else None,own_batch=payroll_batch_id)
    from travel_allowance_cash import ensure_cash_available as travel_available
    travel_available(office,account_id,evidence_key,original_sha256,own_payment=travel_payment_id)
    from business_accounting_open_items import ensure_cash_available as opening_available
    opening_available(office,account_id,evidence_key,original_sha256,own_payment=opening_payment_id)
    if not installed(office):return
    for row in office.db.execute("SELECT entry_json,entry_sha256 FROM business_euer_entries WHERE operation IN ('external_cash','correct')").fetchall():
        if _sha(row['entry_json'])!=row['entry_sha256']:raise Problem(409,'EÜR-Zahlungsnachweis beschädigt')
        entry=json.loads(row['entry_json']); effect=entry['effect']
        if not effect or effect['operation']!='external_cash':continue
        payload=effect['payload']
        if ((payload['account_id']==account_id and _evidence(payload['evidence_key'])[1]==_evidence(evidence_key)[1])
                or original_sha256 and effect['source']['receipt']['original_sha256']==original_sha256):
            raise Problem(409,'Zahlungsnachweis ist bereits im gemeinsamen EÜR-Geldflussjournal erfasst')


def external_receipt_binding(office,actor,original_sha256):
    """A permanently bound payment original is no supplier liability.

    Read callers must not disclose an earlier private binding merely because a
    duplicate of the same file was uploaded into a currently visible project.
    """
    if not installed(office):return None
    candidates=[]
    for row in office.db.execute("SELECT entry_json,entry_sha256 FROM business_euer_entries WHERE operation IN ('external_cash','correct') ORDER BY sequence").fetchall():
        if _sha(row['entry_json'])!=row['entry_sha256']:raise Problem(409,'EÜR-Zahlungsnachweis beschädigt')
        entry=json.loads(row['entry_json']); effect=entry['effect']
        if effect and effect['operation']=='external_cash' and effect['source']['receipt']['original_sha256']==original_sha256:
            candidates.append(entry['id'])
    if not candidates:return None
    api=EuerAccounting(office); ledger=api._ledger()
    for entry_id in candidates:api._source_access(actor,ledger['by_id'][entry_id]['effect']['source'])
    active=ledger['active'].get('external_cash:'+original_sha256)
    return dict(source_role='payment_evidence',reserved_entry_id=candidates[0],active_entry_id=active['id'] if active else None,
                source_path='/accounting/euer/journal')


def validate_integrity(office):
    if not installed(office):return True
    EuerAccounting(office)._ledger()
    return True


def restore_horizon(office):
    if not installed(office):return None
    validate_integrity(office)
    tables={table:sorted((dict(row) for row in office.db.execute('SELECT * FROM '+table).fetchall()),key=canonical) for table in _TABLES}
    return dict(schema_version=1,table_counts={table:len(rows) for table,rows in tables.items()},sha256=_sha(canonical(dict(schema_version=1,tables=tables))))


def methods(path):
    match=re.fullmatch(r'/accounting/euer(?:/(sources|journal|report|preview|confirm|exports/[a-f0-9]{32}(?:/evidence(?:/archive)?)?))?',path)
    return ('POST' if match[1] in ('preview','confirm') else 'GET') if match else None


def dispatch(office,actor,path,method,data):
    allowed=methods(path)
    if allowed is None:return None
    if method!=allowed:raise Problem(405,'Methode nicht unterstützt')
    if not isinstance(data,dict) or not isinstance(data.get('_query',{}),dict):raise Problem(400,'Eindeutige Buchführungsparameter erwartet')
    action=path.removeprefix('/accounting/euer').lstrip('/') or 'state'; api=EuerAccounting(office)
    if method=='POST':
        if '_query' in data:raise Problem(400,'Keine zusätzlichen Filter erlaubt')
        return getattr(api,action)(actor,data),(201 if action=='confirm' else 200),'application/json'
    if set(data)-{'_query'}:raise Problem(400,'GET erwartet keinen Anfragekörper')
    query=data.get('_query',{})
    if action=='journal':
        if set(query)-{'limit','offset'} or any(not isinstance(value,str) or not re.fullmatch(r'[0-9]{1,6}',value) for value in query.values()):raise Problem(400,'Gültige Listenfilter erwartet')
        value=api.journal(actor,int(query.get('limit','50')),int(query.get('offset','0')))
    elif action=='report':
        if set(query)!={'year'} or not isinstance(query['year'],str) or not re.fullmatch(r'[0-9]{4}',query['year']):raise Problem(400,'Eindeutiges Kalenderjahr erwartet')
        value=api.report(actor,int(query['year']))
    else:
        if query:raise Problem(400,'Keine zusätzlichen Filter erlaubt')
        if action.startswith('exports/') and action.endswith(('/evidence','/evidence/archive')):
            archive=action.endswith('/archive')
            return api.year_evidence(actor,action.split('/')[1],archive=archive),200,'application/zip' if archive else 'application/json'
        value=api.exported(actor,action.split('/')[1]) if action.startswith('exports/') else getattr(api,action)(actor)
    return value,200,'application/json'
