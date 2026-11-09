"""Private immutable payroll facts and canonical, evidence-bound period plans.

No wage, payment, tax or reported absence is inferred from a user-entered total.
The pure period kernel owns arithmetic; this module owns actual source bindings.
"""
import calendar
from datetime import date
import json
import re
import uuid

from core import Problem, canonical
from business_foundation import permissions
from business_operations import identifier, iso_date, text, transaction
from business_personnel_workflow import PersonnelWorkflow, EVENT_COLUMNS, _integer, _sha, _shape

FEATURES = ('payroll_period_facts',)
TABLES = ('business_payroll_fact_events', 'business_payroll_fact_requests')
ID = r'[a-f0-9]{32}'
KINDS = ('employment_terms', 'work_schedule', 'period_case')
METHODS = ('calendar_days_actual', 'contractual_30_days', 'scheduled_workdays', 'scheduled_seconds')
STATES = frozenset('BW BY BE BB HB HH HE MV NI NW RP SL SN ST SH TH'.split())
ENTITLEMENTS = ('ordinary_work', 'public_holiday', 'vacation', 'sickness_continued_pay', 'unpaid_leave', 'sickness_after_entitlement')
EMPLOYEE_FIELDS = ('id', 'user_id', 'name', 'employment_from', 'employment_to', 'revision')


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA', 'BLOB'):
        raise ValueError('Unsupported payroll facts storage type')
    return [
        '''CREATE TABLE IF NOT EXISTS business_payroll_fact_events(
        id TEXT NOT NULL,revision INTEGER NOT NULL CHECK(revision>0),
        employee_id TEXT NOT NULL REFERENCES business_employees(id),kind TEXT NOT NULL CHECK(kind IN ('employment_terms','work_schedule','period_case')),
        effective_from TEXT NOT NULL,effective_to TEXT,status TEXT NOT NULL CHECK(status IN ('active','void')),
        payload_json TEXT NOT NULL,sources_json TEXT NOT NULL,source_hash TEXT NOT NULL,
        previous_hash TEXT,content_hash TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
        identity_key TEXT,command_hash TEXT NOT NULL,PRIMARY KEY(id,revision),UNIQUE(employee_id,identity_key))''',
        '''CREATE TABLE IF NOT EXISTS business_payroll_fact_requests(
        user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,operation TEXT NOT NULL,request_hash TEXT NOT NULL,
        fact_id TEXT NOT NULL,fact_revision INTEGER NOT NULL,fact_content_hash TEXT NOT NULL,created_at TEXT NOT NULL,
        PRIMARY KEY(user_id,request_id),FOREIGN KEY(fact_id,fact_revision) REFERENCES business_payroll_fact_events(id,revision))''',
        'CREATE INDEX IF NOT EXISTS business_payroll_fact_employee ON business_payroll_fact_events(employee_id,kind,id,revision)',
    ]


def protected_tables():
    return TABLES


def runtime_privileges():
    return {name: ('SELECT', 'INSERT') for name in TABLES}


def guard_statements(dialect):
    if dialect == 'sqlite':
        output = [f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable payroll fact'); END"
                  for table in TABLES for action in ('UPDATE', 'DELETE')]
        for table, condition in zip(TABLES, (
                '(id=NEW.id AND revision=NEW.revision) OR (NEW.identity_key IS NOT NULL AND employee_id=NEW.employee_id AND identity_key=NEW.identity_key)',
                'user_id=NEW.user_id AND request_id=NEW.request_id')):
            output.append(f"CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition}) BEGIN SELECT RAISE(ABORT,'immutable payroll fact'); END")
        return output
    if dialect == 'postgresql':
        output = ["CREATE OR REPLACE FUNCTION business_payroll_fact_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable payroll fact'; END; $$"]
        for table in TABLES:
            for action in ('UPDATE', 'DELETE'):
                name = table + '_' + action.lower() + '_guard'
                output.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION business_payroll_fact_immutable_guard(); END IF; END $$")
        return output
    raise ValueError('Unsupported payroll facts guard dialect')


def ref(value):
    _shape(value, ('id', 'revision', 'content_hash'), ('id', 'revision', 'content_hash'))
    identifier(value['id']); _integer(value['revision'], 1)
    if not isinstance(value['content_hash'], str) or not re.fullmatch(r'[a-f0-9]{64}', value['content_hash']):
        raise Problem(400, 'Vollständige gehashte Quellenfassung angeben.')
    return dict(value)


def references(value, *, minimum=1, maximum=100):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise Problem(400, 'Eine begrenzte Liste eindeutiger Quellenfassungen angeben.')
    result = [ref(item) for item in value]
    if len({item['id'] for item in result}) != len(result):
        raise Problem(400, 'Eine Quelle darf nur einmal gebunden werden.')
    return sorted(result, key=lambda item: item['id'])


def reference(value):
    return {key: value[key] for key in ('id', 'revision', 'content_hash')}


def file_ids(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 20:
        raise Problem(400, 'Ein bis zwanzig geschützte Personaloriginale angeben.')
    result = [identifier(item, 'Personaldatei-ID') for item in value]
    if len(set(result)) != len(result):
        raise Problem(400, 'Personaloriginale eindeutig angeben.')
    return sorted(result)


def month_days(value):
    if not isinstance(value, str) or not re.fullmatch(r'2026-(0[1-9]|1[0-2])', value):
        raise Problem(400, 'Ein unterstützter Abrechnungsmonat 2026 ist erforderlich.')
    first = date.fromisoformat(value + '-01')
    return [date(first.year, first.month, number).isoformat() for number in range(1, calendar.monthrange(first.year, first.month)[1] + 1)]


def normalize_details(kind, value):
    if kind == 'employment_terms':
        fields = ('employment_from', 'employment_to', 'agreement_refs', 'proration_method', 'reason')
        _shape(value, fields, fields)
        start = iso_date(value['employment_from']); end = iso_date(value['employment_to']) if value['employment_to'] is not None else None
        if end and end < start or value['proration_method'] not in METHODS:
            raise Problem(400, 'Beschäftigungszeitraum und vereinbarte Teilentgeltmethode prüfen.')
        return dict(employment_from=start, employment_to=end, agreement_refs=references(value['agreement_refs']),
                    proration_method=value['proration_method'], reason=text(value['reason'], 'Vertragsgrund', 2000, required=True))
    if kind == 'work_schedule':
        _shape(value, ('month', 'days', 'reason'), ('month', 'days', 'reason'))
        dates = month_days(value['month']); days = value['days']
        if not isinstance(days, list) or len(days) != len(dates):
            raise Problem(400, 'Jeden Kalendertag des Arbeitsplanmonats ausdrücklich angeben.')
        normalized = []
        for expected, item in zip(dates, days):
            _shape(item, ('date', 'scheduled_seconds', 'workplace', 'federal_state'), ('date', 'scheduled_seconds', 'workplace', 'federal_state'))
            seconds = _integer(item['scheduled_seconds'], 0, 86400)
            if item['date'] != expected or item['federal_state'] not in STATES:
                raise Problem(400, 'Chronologische Kalendertage und tatsächliches Bundesland angeben.')
            normalized.append(dict(date=expected, scheduled_seconds=seconds,
                workplace=text(item['workplace'], 'Arbeitsort', 250, required=seconds > 0), federal_state=item['federal_state']))
        return dict(month=value['month'], days=normalized, reason=text(value['reason'], 'Arbeitsplangrund', 2000, required=True))
    if kind == 'period_case':
        fields = ('month', 'preparation_ref', 'employment_terms_ref', 'work_schedule_ref', 'profile_refs', 'identity_refs', 'tax_treatment', 'entitlement_decisions', 'verification_note')
        _shape(value, fields, fields); dates = month_days(value['month'])
        if value['tax_treatment'] != 'domestic_running_wages' or not isinstance(value['entitlement_decisions'], list) or len(value['entitlement_decisions']) > 100:
            raise Problem(400, 'Belegte inländische laufende Entgelte und begrenzte Anspruchsentscheidungen angeben.')
        decisions = []
        for item in value['entitlement_decisions']:
            fields = ('kind', 'from', 'to', 'source_absence_id', 'source_file_ids', 'reason')
            _shape(item, fields, fields)
            start, end = iso_date(item['from']), iso_date(item['to'])
            if item['kind'] not in ENTITLEMENTS or not dates[0] <= start <= end <= dates[-1]:
                raise Problem(400, 'Anspruchsart und Zeitraum innerhalb des Monats angeben.')
            absence = item['source_absence_id']
            if absence is not None:
                identifier(absence, 'Abwesenheits-ID')
            normalized = dict(kind=item['kind'], source_absence_id=absence, source_file_ids=file_ids(item['source_file_ids']),
                              reason=text(item['reason'], 'Anspruchsgrund', 2000, required=True))
            normalized.update({'from': start, 'to': end}); decisions.append(normalized)
        decisions.sort(key=lambda item: (item['from'], item['to'], item['kind']))
        for left, right in zip(decisions, decisions[1:]):
            if right['from'] <= left['to']:
                raise Problem(400, 'Anspruchsentscheidungen dürfen dieselben Kalendertage nicht mehrfach belegen.')
        return dict(month=value['month'], preparation_ref=ref(value['preparation_ref']), employment_terms_ref=ref(value['employment_terms_ref']),
            work_schedule_ref=None if value['work_schedule_ref'] is None else ref(value['work_schedule_ref']),
            profile_refs=references(value['profile_refs']), identity_refs=references(value['identity_refs']),
            tax_treatment=value['tax_treatment'], entitlement_decisions=decisions,
            verification_note=text(value['verification_note'], 'Prüfvermerk', 3000, required=True))
    raise Problem(400, 'Unbekannte Lohnfaktenart.')


def effective(kind, details):
    if kind == 'employment_terms':
        return details['employment_from'], details['employment_to']
    days = month_days(details['month'])
    return days[0], days[-1]


def key_for(kind, details):
    return kind + ':' + (details['employment_from'] if kind == 'employment_terms' else details['month'])


def employee_view(employee):
    return {key: employee[key] for key in EMPLOYEE_FIELDS}


def build_plan(snapshot, *, rule_version=None):
    from payroll_periods_2026 import build_period_plan, PERIOD_RULE_VERSION
    from payroll_factor_periods_2026 import (build_factor_period_plan,
        selected_profile, FACTOR_PERIOD_RULE_VERSION)
    if rule_version not in (None,PERIOD_RULE_VERSION,FACTOR_PERIOD_RULE_VERSION):
        raise Problem(400,'Unbekannter gespeicherter Periodenregelstand.')
    plan=build_period_plan(snapshot)
    if rule_version==FACTOR_PERIOD_RULE_VERSION or rule_version is None and 'tax_factor' in selected_profile(snapshot,plan)['profile']:
        return build_factor_period_plan(snapshot)
    return plan


class PayrollFacts:
    def __init__(self, office, *, clock=None):
        self.office, self.db = office, office.db
        self.hr = PersonnelWorkflow(office, clock=clock)

    def _access(self, actor, employee_id, permission='personnel.read'):
        fresh, employee = self.hr._employee(actor, employee_id, permission=permission)
        self.hr._employee(fresh, employee['id'], permission='personnel.read')
        return fresh, employee

    def _capabilities(self, actor):
        from business_organization import module_enabled
        allowed = permissions(self.office, actor)
        return dict(can_write='personnel.write' in allowed, can_approve='personnel.approve' in allowed,
                    writes_enabled=module_enabled(self.office, 'personnel'))

    def _gate(self, actor, *, new=True):
        from business_schema import require_capability
        from business_organization import require_active
        require_capability(self.office, 'business_payroll_facts')
        if new:
            require_active(self.office, actor, '/payroll', 'business_payroll')

    def _row(self, object_id, revision=None):
        identifier(object_id)
        if revision is None:
            row = self.db.execute('SELECT * FROM business_payroll_fact_events WHERE id=? ORDER BY revision DESC LIMIT 1', (object_id,)).fetchone()
        else:
            _integer(revision, 1)
            row = self.db.execute('SELECT * FROM business_payroll_fact_events WHERE id=? AND revision=?', (object_id, revision)).fetchone()
        if row is None:
            raise Problem(404, 'Lohnfakt nicht verfügbar.')
        return row

    def _event(self, row):
        payload, sources = json.loads(row['payload_json']), json.loads(row['sources_json'])
        envelope = {key: row[key] for key in row.keys() if key not in ('payload_json', 'sources_json', 'content_hash')}
        envelope.update(payload=payload, sources=sources)
        if _sha(envelope) != row['content_hash'] or _sha(sources) != row['source_hash']:
            raise Problem(500, 'Integrität der Lohnfaktenhistorie verletzt.')
        result = {key: row[key] for key in ('id', 'revision', 'employee_id', 'kind', 'effective_from', 'effective_to', 'status', 'source_hash', 'previous_hash', 'content_hash', 'created_by', 'created_at')}
        return dict(result, **payload, sources=sources)

    def _get(self, object_id, revision=None):
        return self._event(self._row(object_id, revision))

    def _all(self, employee_id, kind=None):
        rows = self.db.execute('SELECT e.* FROM business_payroll_fact_events e WHERE e.employee_id=? AND NOT EXISTS '
            '(SELECT 1 FROM business_payroll_fact_events n WHERE n.id=e.id AND n.revision>e.revision) ORDER BY e.created_at,e.id', (employee_id,)).fetchall()
        return [self._event(row) for row in rows if kind is None or row['kind'] == kind]

    def records(self, actor, query):
        _shape(query, ('employee_id', 'kind'), ('employee_id',))
        if query.get('kind') is not None and query['kind'] not in KINDS:
            raise Problem(400, 'Unbekannte Lohnfaktenart.')
        with transaction(self.office):
            fresh, employee = self._access(actor, query['employee_id'])
            return dict(employee_id=employee['id'], items=self._all(employee['id'], query.get('kind')), **self._capabilities(fresh))

    def get(self, actor, object_id, history=False):
        with transaction(self.office):
            row = self._row(object_id)
            self._access(actor, row['employee_id'])
            if history:
                items = [self._event(item) for item in self.db.execute('SELECT * FROM business_payroll_fact_events WHERE id=? ORDER BY revision', (object_id,))]
                return dict(employee_id=row['employee_id'], items=items)
            return self._event(row)

    def sources(self, actor, query):
        from business_payroll import Payroll
        from business_payroll_accounts import PayrollAccounts
        _shape(query, ('employee_id',), ('employee_id',))
        with transaction(self.office):
            fresh, employee = self._access(actor, query['employee_id'])
            files = [item for item in self.hr.files(fresh, query)['items'] if item['purpose'] == 'personnel' and not self.db.execute('SELECT 1 FROM business_personnel_files WHERE supersedes=?', (item['id'],)).fetchone()]
            absences = [{key: row[key] for key in row.keys() if key != 'details'} for row in self.db.execute(
                "SELECT * FROM business_absences WHERE employee_id=? AND status='approved' ORDER BY start_date,id", (employee['id'],))]
            return dict(employee=employee_view(employee), employee_id=employee['id'], files=files,
                agreements=self.hr._all('agreement', employee['id']), preparations=self.hr._all('preparation', employee['id']),
                profiles=Payroll(self.office)._all('profile', employee['id']),
                identities=[item for item in PayrollAccounts(self.office)._all(employee['id']) if item['kind'] == 'identity'],
                facts=self._all(employee['id']), absences=absences, **self._capabilities(fresh))

    def _files(self, employee_id, ids, *, fresh):
        result = []
        for file_id in ids:
            row = self.hr._file(file_id, employee_id)
            if row['purpose'] != 'personnel':
                raise Problem(400, 'Geschützte Personalakten-Originale sind erforderlich.')
            if fresh and self.db.execute('SELECT 1 FROM business_personnel_files WHERE supersedes=?', (file_id,)).fetchone():
                raise Problem(409, 'Ein gewähltes Personaloriginal wurde ersetzt. Aktuellen Nachweis prüfen.')
            result.append(self.hr._file_view(row))
        return result

    def _hr_ref(self, employee_id, value, kind, *, fresh):
        row = self.db.execute('SELECT ' + EVENT_COLUMNS + ' FROM business_personnel_events WHERE id=? AND revision=?', (value['id'], value['revision'])).fetchone()
        if row is None or row['kind'] != kind or row['employee_id'] != employee_id:
            raise Problem(404, 'Personalquelle gehört nicht zu diesem Mitarbeiter.')
        result = self.hr._event(row)
        if reference(result) != value or fresh and reference(self.hr._latest(value['id'], kind)) != value:
            raise Problem(409, 'Personalquellenfassung wurde geändert.')
        original_ids = [result['reference_file_id']] if kind == 'agreement' else []
        if original_ids:
            self._files(employee_id, original_ids, fresh=fresh)
        return result

    def _payroll_ref(self, employee_id, value, *, fresh):
        from business_payroll import Payroll
        payroll = Payroll(self.office)
        result = payroll._event(payroll._row(value['id'], 'profile', value['revision']))
        if result['employee_id'] != employee_id:
            raise Problem(404, 'Lohnprofil gehört nicht zu diesem Mitarbeiter.')
        if reference(result) != value or fresh and reference(payroll._latest(value['id'], 'profile')) != value:
            raise Problem(409, 'Lohnprofil wurde geändert.')
        self._files(employee_id, [result['source_file']['id']], fresh=fresh)
        return result

    def _identity_ref(self, employee_id, value, *, fresh):
        from business_payroll_accounts import PayrollAccounts
        api = PayrollAccounts(self.office)
        result = api._get(value['id'], value['revision'])
        if result['kind'] != 'identity' or result['employee_id'] != employee_id:
            raise Problem(404, 'Lohnkontonachweis gehört nicht zu diesem Mitarbeiter.')
        if reference(result) != value or fresh and reference(api._get(value['id'])) != value:
            raise Problem(409, 'Lohnkontonachweis wurde geändert.')
        self._files(employee_id, [result['source_file']['id']], fresh=fresh)
        return result

    def _fact_ref(self, employee_id, value, kind, *, fresh):
        result = self._get(value['id'], value['revision'])
        if result['employee_id'] != employee_id or result['kind'] != kind:
            raise Problem(404, 'Lohnfaktenquelle gehört nicht zu diesem Mitarbeiter.')
        if reference(result) != value or result['status'] != 'active' or fresh and reference(self._get(value['id'])) != value:
            raise Problem(409, 'Lohnfaktenquelle wurde geändert oder archiviert.')
        validate_fact_sources(self.office, result)
        if fresh:
            self._files(employee_id, result['source_file_ids'], fresh=True)
        return result

    def _snapshot(self, employee, kind, details, ids, *, fresh=True):
        employee_id = employee['id']; files = self._files(employee_id, ids, fresh=fresh)
        if kind == 'employment_terms':
            if details['employment_from'] != employee['employment_from'] or details['employment_to'] != (employee['employment_to'] or None):
                raise Problem(409, 'Belegte Beschäftigungsdaten widersprechen dem Personalstamm. Stamm zuerst begründet korrigieren.')
            agreements = [self._hr_ref(employee_id, item, 'agreement', fresh=fresh) for item in details['agreement_refs']]
            if min(item['effective_from'] for item in agreements) > details['employment_from']:
                raise Problem(409, 'Entgeltvereinbarung zum belegten Beschäftigungsbeginn fehlt.')
            return dict(schema_version=1, employee=employee_view(employee), agreements=agreements, source_files=files)
        if kind == 'work_schedule':
            return dict(schema_version=1, employee=employee_view(employee), source_files=files)
        preparation = self._hr_ref(employee_id, details['preparation_ref'], 'preparation', fresh=fresh)
        if preparation['month'] != details['month']:
            raise Problem(400, 'Monatsvorbereitung muss zum gewählten Monat gehören.')
        if fresh and _sha(self.hr._snapshot(employee, details['month'])) != preparation['source_hash']:
            raise Problem(409, 'Monatsvorbereitung ist nicht mehr aktuell. Zuerst ihre Korrektur abschließen.')
        terms = self._fact_ref(employee_id, details['employment_terms_ref'], 'employment_terms', fresh=fresh)
        if terms['details']['employment_from'] != employee['employment_from'] or terms['details']['employment_to'] != (employee['employment_to'] or None):
            raise Problem(409, 'Beschäftigungsfakt und Personalstamm sind nicht mehr identisch.')
        schedule = self._fact_ref(employee_id, details['work_schedule_ref'], 'work_schedule', fresh=fresh) if details['work_schedule_ref'] else None
        if schedule and schedule['details']['month'] != details['month']:
            raise Problem(400, 'Arbeitsplan gehört zu einem anderen Monat.')
        profiles = [self._payroll_ref(employee_id, item, fresh=fresh) for item in details['profile_refs']]
        identities = [self._identity_ref(employee_id, item, fresh=fresh) for item in details['identity_refs']]
        if any(item['details']['profile_id'] not in {profile['id'] for profile in profiles} for item in identities):
            raise Problem(400, 'Identitätsnachweis muss auf ein gewähltes Profil verweisen.')
        if any(not any(identity['details']['profile_id'] == profile['id'] and identity['details']['profile_revision'] == profile['revision'] for identity in identities) for profile in profiles):
            raise Problem(409, 'Für jede gewählte Profilfassung fehlt ein gebundener Identitätsnachweis.')
        if fresh:
            from business_payroll import Payroll
            month_start, month_end = month_days(details['month'])[0], month_days(details['month'])[-1]
            start = max(month_start, terms['details']['employment_from'])
            actual_end = min(month_end, terms['details']['employment_to'] or month_end)
            applicable = sorted([item for item in Payroll(self.office)._all('profile', employee_id) if item['profile']['effective_from'] <= actual_end], key=lambda item: item['profile']['effective_from'])
            before = [item for item in applicable if item['profile']['effective_from'] <= start]
            expected = ([before[-1]] if before else []) + [item for item in applicable if item['profile']['effective_from'] > start]
            if sorted([reference(item) for item in expected], key=lambda item: item['id']) != details['profile_refs']:
                raise Problem(409, 'Alle tatsächlich einschlägigen aktuellen Profilfassungen ausdrücklich binden.')
            if any(reference(item) not in terms['details']['agreement_refs'] for item in preparation['snapshot']['agreements']):
                raise Problem(409, 'Beschäftigungsfakt enthält nicht alle Entgeltvereinbarungen der Monatsquelle.')
        absences = {item['id']: item for item in preparation['snapshot']['approved_absences']}
        for decision in details['entitlement_decisions']:
            if not set(decision['source_file_ids']).issubset(ids):
                raise Problem(400, 'Jedes Anspruchsoriginal auch an den gesamten Monatsfall binden.')
            if decision['source_absence_id'] is not None:
                absence = absences.get(decision['source_absence_id'])
                if absence is None or not absence['start_date'] <= decision['from'] <= decision['to'] <= absence['end_date']:
                    raise Problem(400, 'Anspruchsentscheidung muss zur freigegebenen Abwesenheit gehören.')
        return dict(schema_version=1, employee_id=employee_id, month=details['month'], preparation=preparation,
            profiles=profiles, identities=identities, employment_terms=terms, work_schedule=schedule,
            case_details=details, source_files=files)

    def preview(self, actor, data):
        _shape(data, ('employee_id', 'employee_revision', 'details', 'source_file_ids'), ('employee_id', 'employee_revision', 'details', 'source_file_ids'))
        details = normalize_details('period_case', data['details']); ids = file_ids(data['source_file_ids'])
        with transaction(self.office):
            fresh, employee = self._access(actor, data['employee_id'])
            if _integer(data['employee_revision'], 1) != employee['revision']:
                raise Problem(409, 'Mitarbeiterstamm wurde geändert. Neu laden.')
            snapshot = self._snapshot(employee, 'period_case', details, ids)
            plan = build_plan(snapshot)
            return dict(employee_id=employee['id'], month=details['month'], source_snapshot=snapshot,
                source_hash=_sha(snapshot), plan=plan, preview_hash=_sha(dict(source_snapshot=snapshot, plan=plan)),
                can_confirm=True, can_calculate=not bool(plan['blockers']), **self._capabilities(fresh))

    def save(self, actor, data):
        required = ('request_id', 'employee_id', 'employee_revision', 'kind', 'revision', 'status', 'details', 'source_file_ids', 'confirmed')
        _shape(data, required + ('id', 'correction_reason', 'preview_hash'), required)
        identifier(data['request_id']); identifier(data['employee_id'])
        if data.get('id') is not None:
            identifier(data['id'])
        if data['kind'] not in KINDS or data['confirmed'] is not True or data['status'] not in ('active', 'void'):
            raise Problem(400, 'Faktenart, Status und ausdrückliche Bestätigung prüfen.')
        if (data['kind'] == 'period_case') != ('preview_hash' in data) or 'preview_hash' in data and not re.fullmatch(r'[a-f0-9]{64}', str(data['preview_hash'])):
            raise Problem(400, 'Nur Monatsfälle benötigen ihre konkrete geprüfte Vorschau.')
        details = normalize_details(data['kind'], data['details']); ids = file_ids(data['source_file_ids'])
        _integer(data['employee_revision'], 1); _integer(data['revision'])
        reason = text(data.get('correction_reason', ''), 'Korrekturgrund', 2000, required=bool(data.get('id')))
        permission = 'personnel.approve' if data['kind'] == 'period_case' else 'personnel.write'
        operation = 'fact.saved:' + data['kind']; fingerprint = _sha([operation, data])
        with transaction(self.office):
            fresh, employee = self._access(actor, data['employee_id'], permission)
            self._gate(fresh, new=False)
            previous_receipt = self.db.execute('SELECT * FROM business_payroll_fact_requests WHERE user_id=? AND request_id=?', (fresh['id'], data['request_id'])).fetchone()
            if previous_receipt is not None:
                if previous_receipt['operation'] != operation or previous_receipt['request_hash'] != fingerprint:
                    raise Problem(409, 'Diese Vorgangs-ID wurde mit anderem Inhalt verwendet.')
                original_row = self._row(previous_receipt['fact_id'], previous_receipt['fact_revision'])
                result = self._event(original_row)
                if result['employee_id'] != employee['id'] or result['kind'] != data['kind'] or result['content_hash'] != previous_receipt['fact_content_hash'] or original_row['command_hash'] != fingerprint:
                    raise Problem(500, 'Ursprüngliche Lohnfaktenquittung widerspricht dem Facharchiv.')
                _validate_command(data, result)
                validate_fact_sources(self.office, result)
                return result
            try:
                self._gate(fresh)
                if data['employee_revision'] != employee['revision']:
                    raise Problem(409, 'Mitarbeiterstamm wurde geändert. Neu laden.')
                previous = self._get(data['id']) if data.get('id') else None
                if previous and (previous['employee_id'] != employee['id'] or previous['kind'] != data['kind']):
                    raise Problem(404, 'Korrektur gehört nicht zu diesem Mitarbeiter und Faktentyp.')
                if data['revision'] != (previous['revision'] if previous else 0):
                    raise Problem(409, 'Lohnfakt wurde geändert. Aktuelle Fassung laden.')
                identity_key = key_for(data['kind'], details)
                existing = self.db.execute('SELECT id FROM business_payroll_fact_events WHERE employee_id=? AND identity_key=?', (employee['id'], identity_key)).fetchone()
                if existing and (previous is None or previous['id'] != existing['id']):
                    raise Problem(409, 'Für diesen Beginn oder Monat besteht bereits ein Fakt. Seine Korrekturfassung verwenden.')
                if previous and key_for(previous['kind'], previous['details']) != identity_key:
                    raise Problem(400, 'Faktenart und ursprünglichen Beginn oder Monat nicht wechseln.')
                if data['status'] == 'void':
                    if previous is None or previous['status'] != 'active' or details != previous['details'] or ids != previous['source_file_ids'] or data.get('preview_hash') != previous['preview_hash']:
                        raise Problem(400, 'Archivieren verlangt die unveränderte aktive Fassung und einen Korrekturgrund.')
                    validate_fact_sources(self.office, previous)
                    snapshot, plan, preview_hash = previous['sources'], previous['plan'], previous['preview_hash']
                else:
                    snapshot = self._snapshot(employee, data['kind'], details, ids)
                    plan = build_plan(snapshot) if data['kind'] == 'period_case' else None
                    preview_hash = _sha(dict(source_snapshot=snapshot, plan=plan)) if plan is not None else None
                    if data.get('preview_hash') != preview_hash:
                        raise Problem(409, 'Quellen oder Periodenplan haben sich seit der Vorschau geändert.')
                    if data['kind'] == 'employment_terms':
                        for other in self._all(employee['id'], 'employment_terms'):
                            if other['status'] == 'active' and (not previous or other['id'] != previous['id']) and max(other['effective_from'], details['employment_from']) <= min(other['effective_to'] or '9999-12-31', details['employment_to'] or '9999-12-31'):
                                raise Problem(409, 'Aktive Beschäftigungsfakten dürfen sich nicht überlappen.')
                payload = dict(details=details, source_file_ids=ids, plan=plan, preview_hash=preview_hash, correction_reason=reason)
                start, end = effective(data['kind'], details)
                envelope = dict(id=previous['id'] if previous else uuid.uuid4().hex, revision=previous['revision'] + 1 if previous else 1,
                    employee_id=employee['id'], kind=data['kind'], effective_from=start, effective_to=end, status=data['status'],
                    source_hash=_sha(snapshot), previous_hash=previous['content_hash'] if previous else None,
                    created_by=fresh['id'], created_at=self.hr.now(), identity_key=None if previous else identity_key,
                    command_hash=fingerprint, payload=payload, sources=snapshot)
                columns = tuple(key for key in envelope if key not in ('payload', 'sources'))
                self.db.execute('INSERT INTO business_payroll_fact_events(' + ','.join(columns) + ',payload_json,sources_json,content_hash) VALUES(' + ','.join('?' for _ in range(len(columns) + 3)) + ')',
                    tuple(envelope[key] for key in columns) + (canonical(payload), canonical(snapshot), _sha(envelope)))
                result = self._get(envelope['id'])
                _validate_command(data, result)
                validate_fact_sources(self.office, result)
                self.db.execute('INSERT INTO business_payroll_fact_requests(user_id,request_id,operation,request_hash,fact_id,fact_revision,fact_content_hash,created_at) VALUES(?,?,?,?,?,?,?,?)',
                    (fresh['id'], data['request_id'], operation, fingerprint, result['id'], result['revision'], result['content_hash'], envelope['created_at']))
                self.office.audit(fresh, 'payroll.fact.' + data['kind'], result['id'])
                return result
            except Problem as error:
                if error.status == 409:
                    raise Problem(409, error.message, request_resolution='not_accepted') from None
                raise

    def resolve_period_case(self, actor, employee_id, value, fresh=True):
        value = ref(value)
        with transaction(self.office):
            _, employee = self._access(actor, employee_id)
            result = self._fact_ref(employee_id, value, 'period_case', fresh=fresh)
            if fresh:
                snapshot = self._snapshot(employee, 'period_case', result['details'], result['source_file_ids'])
                if snapshot != result['sources']:
                    raise Problem(409, 'Der bestätigte Monatsfall entspricht nicht mehr den aktuellen Quellen.')
            return result


def _validate_command(data, value):
    if value['status'] == 'active':
        employee = value['sources']['preparation']['snapshot']['employee'] if value['kind'] == 'period_case' else value['sources']['employee']
        if data['employee_revision'] != employee['revision']:
            raise Problem(500, 'Angenommene Mitarbeiterrevision widerspricht dem ursprünglichen Lohnfakt.')
    if (data['confirmed'] is not True or data['kind'] != value['kind'] or data['employee_id'] != value['employee_id']
            or data['status'] != value['status'] or normalize_details(data['kind'], data['details']) != value['details']
            or file_ids(data['source_file_ids']) != value['source_file_ids'] or data.get('preview_hash') != value['preview_hash']
            or text(data.get('correction_reason', ''), 'Korrekturgrund', 2000) != value['correction_reason']
            or data['revision'] + 1 != value['revision'] or (data.get('id') if data['revision'] else value['id']) != value['id']):
        raise Problem(500, 'Angenommener Originalauftrag widerspricht der Lohnfaktenfassung.')


def validate_fact_sources(office, value):
    """Historical reconstruction, never a demand for today's employee revision."""
    api = PayrollFacts(office)
    try:
        details = normalize_details(value['kind'], value['details'])
        if details != value['details'] or file_ids(value['source_file_ids']) != value['source_file_ids']:
            raise ValueError('Noncanonical payroll fact')
        if effective(value['kind'], details) != (value['effective_from'], value['effective_to']):
            raise ValueError('Changed payroll fact period')
        sources = value['sources']
        employee = sources['preparation']['snapshot']['employee'] if value['kind'] == 'period_case' else sources['employee']
        _shape(employee, EMPLOYEE_FIELDS, EMPLOYEE_FIELDS)
        if employee['id'] != value['employee_id']:
            raise ValueError('Foreign payroll fact employee')
        _integer(employee['revision'], 1)
        if not office.db.execute('SELECT 1 FROM business_employee_terms WHERE employee_id=? AND revision=?', (value['employee_id'], employee['revision'])).fetchone():
            raise ValueError('Missing original employee revision')
        current_employee = office.db.execute('SELECT user_id FROM business_employees WHERE id=?', (value['employee_id'],)).fetchone()
        if current_employee is None or current_employee['user_id'] != employee['user_id']:
            raise ValueError('Changed immutable employee user binding')
        original_employee = []
        for command in office.db.execute("SELECT result_json FROM business_planning_requests WHERE operation='employee' AND result_json LIKE ?", ('%"id":"' + value['employee_id'] + '"%',)):
            accepted = json.loads(command['result_json'])
            if accepted.get('id') == value['employee_id'] and accepted.get('revision') == employee['revision']:
                original_employee.append(accepted)
        if len(original_employee) != 1 or any(original_employee[0].get(key) != employee[key] for key in EMPLOYEE_FIELDS if key in original_employee[0]):
            raise ValueError('Frozen employee differs from the canonical accepted revision')
        expected = api._snapshot(employee, value['kind'], details, value['source_file_ids'], fresh=False)
        if expected != sources or _sha(sources) != value['source_hash']:
            raise ValueError('Changed payroll fact sources')
        plan = build_plan(sources,rule_version=value['plan']['rule_version']) if value['kind'] == 'period_case' else None
        preview_hash = _sha(dict(source_snapshot=sources, plan=plan)) if plan is not None else None
        if value['plan'] != plan or value['preview_hash'] != preview_hash:
            raise ValueError('Changed payroll period plan')
        return True
    except (Problem, KeyError, TypeError, ValueError, RecursionError) as error:
        raise ValueError('Invalid historical payroll fact sources') from error


def validate_integrity(office):
    from business_schema import _tables
    present = set(TABLES).intersection(_tables(office))
    if not present:
        return True
    if present != set(TABLES):
        raise ValueError('Incomplete payroll facts schema')
    api = PayrollFacts(office)
    try:
        previous = {}; receipts = set()
        for row in office.db.execute('SELECT * FROM business_payroll_fact_events ORDER BY id,revision'):
            value = api._event(row); prior = previous.get(value['id'])
            if value['revision'] != (prior['revision'] + 1 if prior else 1) or value['previous_hash'] != (prior['content_hash'] if prior else None):
                raise ValueError('Broken payroll fact history')
            if prior and any(value[key] != prior[key] for key in ('employee_id', 'kind', 'effective_from')):
                raise ValueError('Changed payroll fact identity')
            if row['identity_key'] != (None if prior else key_for(value['kind'], value['details'])):
                raise ValueError('Changed payroll fact identity key')
            if not re.fullmatch(r'[a-f0-9]{64}', row['command_hash']) or prior and not value['correction_reason'] or not prior and value['status'] != 'active':
                raise ValueError('Invalid payroll fact acceptance')
            if value['status'] == 'void' and (not prior or prior['status'] != 'active' or any(value[key] != prior[key] for key in ('details', 'source_file_ids', 'sources', 'source_hash', 'plan', 'preview_hash'))):
                raise ValueError('Changed void payroll fact')
            validate_fact_sources(office, value)
            previous[value['id']] = value
        for row in office.db.execute('SELECT * FROM business_payroll_fact_requests'):
            identifier(row['request_id']); original = api._row(row['fact_id'], row['fact_revision'])
            if (row['operation'] != 'fact.saved:' + original['kind'] or row['request_hash'] != original['command_hash']
                    or row['fact_content_hash'] != original['content_hash'] or row['user_id'] != original['created_by']
                    or row['created_at'] != original['created_at'] or (row['fact_id'], row['fact_revision']) in receipts):
                raise ValueError('Changed payroll fact command receipt')
            receipts.add((row['fact_id'], row['fact_revision']))
        if len(receipts) != office.db.execute('SELECT COUNT(*) FROM business_payroll_fact_events').fetchone()[0]:
            raise ValueError('Missing accepted payroll fact receipt')
    except (Problem, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError('Invalid payroll fact archive') from error
    return True


def methods(path):
    if path == '/payroll/facts':
        return 'GET, POST'
    if path == '/payroll/facts/sources' or re.fullmatch(r'/payroll/facts/' + ID + r'(?:/history)?', path):
        return 'GET'
    if path == '/payroll/periods/preview':
        return 'POST'
    return None


def dispatch(office, actor, path, method, data):
    allowed = methods(path)
    if allowed is None:
        return None
    if method not in allowed.split(', '):
        raise Problem(405, 'Methode für diese Lohnfaktenroute nicht zulässig.')
    api = PayrollFacts(office)
    if method == 'POST':
        result = api.preview(actor, data) if path == '/payroll/periods/preview' else api.save(actor, data)
    else:
        _shape(data, ('_query',))
        query = data.get('_query', {})
        if path == '/payroll/facts/sources':
            result = api.sources(actor, query)
        elif path == '/payroll/facts':
            result = api.records(actor, query)
        else:
            _shape(query, ())
            result = api.get(actor, path.split('/')[3], path.endswith('/history'))
    return result, 200, 'application/json'
