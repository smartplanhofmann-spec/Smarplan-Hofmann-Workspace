"""Private Source4 case originals and atomic actual-run claim ownership."""
import json
import re
import uuid

from core import Problem, canonical
from business_operations import identifier, text, transaction
from business_personnel_workflow import _integer, _sha, _shape
from business_payroll_facts import PayrollFacts, ref, reference, file_ids, employee_view, EMPLOYEE_FIELDS
from business_payroll_annual_basis import PayrollAnnualBasis
from business_payroll_calculation_cases import PayrollCalculationCases
from payroll_de_2026 import month_range
from payroll_oneoff_composition_2026 import ONEOFF_RULE_VERSION as RULE_VERSION, SOURCE_CONTRACT_VERSION, calculate_oneoff_source

FEATURES = ('payroll_oneoff_cases',)
TABLES = ('business_payroll_oneoff_case_events', 'business_payroll_oneoff_case_requests', 'business_payroll_oneoff_consumptions')
KIND = 'one_off_case'
ID = r'[a-f0-9]{32}'


def schema_statements(binary_type='BYTEA'):
    from business_payroll_facts import schema_statements as original
    return [value.replace('business_payroll_fact', 'business_payroll_oneoff_case')
        .replace("'employment_terms','work_schedule','period_case'", "'one_off_case'") for value in original(binary_type)] + [
        '''CREATE TABLE IF NOT EXISTS business_payroll_oneoff_consumptions(
        run_id TEXT NOT NULL,run_revision INTEGER NOT NULL CHECK(run_revision>0),
        employee_id TEXT NOT NULL REFERENCES business_employees(id),case_id TEXT NOT NULL,case_revision INTEGER NOT NULL,
        claim_identity_key TEXT,payload_json TEXT NOT NULL,content_hash TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
        PRIMARY KEY(run_id,run_revision),UNIQUE(employee_id,claim_identity_key),
        FOREIGN KEY(run_id,run_revision) REFERENCES business_payroll_events(id,revision),
        FOREIGN KEY(case_id,case_revision) REFERENCES business_payroll_oneoff_case_events(id,revision))''']


def guard_statements(dialect):
    from business_payroll_facts import guard_statements as original
    statements = [value.replace('business_payroll_fact', 'business_payroll_oneoff_case')
        .replace('immutable payroll fact', 'immutable payroll oneoff case') for value in original(dialect)]
    # Reuse the already defined immutable function/trigger form for allocation
    # rows, without inventing any update privilege or correction deletion.
    statements += [value.replace('business_payroll_oneoff_case_events', TABLES[2]) for value in statements
        if 'business_payroll_oneoff_case_events' in value and 'insert_guard' not in value]
    if dialect == 'sqlite':
        statements.append('CREATE TRIGGER IF NOT EXISTS business_payroll_oneoff_consumptions_insert_guard BEFORE INSERT ON '
            'business_payroll_oneoff_consumptions WHEN EXISTS(SELECT 1 FROM business_payroll_oneoff_consumptions WHERE '
            '(run_id=NEW.run_id AND run_revision=NEW.run_revision) OR (NEW.claim_identity_key IS NOT NULL AND '
            "employee_id=NEW.employee_id AND claim_identity_key=NEW.claim_identity_key)) BEGIN SELECT RAISE(ABORT,'immutable payroll oneoff consumption'); END")
    return statements


def protected_tables(): return TABLES
def runtime_privileges(): return {table: ('SELECT', 'INSERT') for table in TABLES}


def normalize_details(value):
    fields = ('month', 'running_calculation_case_ref', 'one_off_earning_ref', 'current_annual_basis_ref',
        'previous_annual_basis_ref', 'annual_tax_forecast_ref', 'verification_note')
    _shape(value, fields, fields)
    first, _ = month_range(value['month'])
    if first.year != 2026: raise Problem(400, 'Einmalbezugsmonat 2026 erforderlich.')
    result = dict(value)
    for key in fields[1:-1]:
        result[key] = None if key == 'previous_annual_basis_ref' and value[key] is None else ref(value[key])
    result['verification_note'] = text(value['verification_note'], 'Beurteilung des konkreten Einmalbezugs', 3000, required=True)
    return result


def identity_key(details): return 'earning:' + details['one_off_earning_ref']['id']


class PayrollOneoffCases(PayrollFacts):
    def _gate(self, actor, *, new=True):
        from business_schema import require_capability
        from business_organization import require_active
        require_capability(self.office, 'business_payroll_oneoff_cases')
        if new: require_active(self.office, actor, '/payroll', 'business_payroll')

    def _row(self, object_id, revision=None):
        identifier(object_id)
        if revision is None:
            row = self.db.execute('SELECT * FROM ' + TABLES[0] + ' WHERE id=? ORDER BY revision DESC LIMIT 1', (object_id,)).fetchone()
        else:
            _integer(revision, 1)
            row = self.db.execute('SELECT * FROM ' + TABLES[0] + ' WHERE id=? AND revision=?', (object_id, revision)).fetchone()
        if row is None: raise Problem(404, 'Einmalbezugsfall nicht verfügbar.')
        return row

    def _event(self, row):
        result = super()._event(row); result.pop('accepted_command'); return result

    def _all(self, employee_id, kind=None):
        return [self._event(row) for row in self.db.execute('SELECT e.* FROM ' + TABLES[0] + ' e WHERE e.employee_id=? AND NOT EXISTS '
            '(SELECT 1 FROM ' + TABLES[0] + ' n WHERE n.id=e.id AND n.revision>e.revision) ORDER BY e.created_at,e.id', (employee_id,))]

    def _snapshot(self, employee, details, ids, *, fresh=True):
        employee_id = employee['id']; files = self._files(employee_id, ids, fresh=fresh)
        cases = PayrollCalculationCases(self.office, clock=self.hr.clock)
        annual = PayrollAnnualBasis(self.office, clock=self.hr.clock)
        value = details['running_calculation_case_ref']; running = cases._get(value['id'], value['revision'])
        from business_payroll_calculation_cases import validate_case_sources as validate_running_case
        if (running['employee_id'] != employee_id or running['kind'] != 'calculation_case'
                or running['status'] != 'active' or reference(running) != value):
            raise Problem(409, 'Laufender Originalfall gehört nicht zur Person oder ist nicht wirksam.')
        if running['rule_version']!='de_2026_segments_entitlements_v5' or running['source_contract_version']!=1:
            raise Problem(409,'Einmalbezüge auf einem Faktor-Reisefall benötigen ihren eigenen Regelzweig.')
        validate_running_case(self.office, running)
        planned = running['sources']['flat_travel_tax']
        planned_on = planned['recording_context']['planned_recording_on'] if planned else None
        if fresh and (reference(cases._get(value['id'])) != value
                or cases._snapshot(employee, 'calculation_case', running['details'], running['source_file_ids'],
                    planned_on=planned_on) != running['sources']):
            raise Problem(409, 'Der tatsächliche laufende Quellenfall wurde geändert.')
        earning = annual._reference(employee_id, details['one_off_earning_ref'], 'one_off_earning', fresh=fresh)
        if fresh:
            from business_payroll import Payroll
            for run in Payroll(self.office)._all('run', employee_id):
                if (run['source']['month'] == details['month'] and run['source'].get('source_schema_version') == 4
                        and run['source']['one_off_case']['details']['one_off_earning_ref']['id'] != earning['id']):
                    raise Problem(409, 'Ein weiterer Anspruch im selben bereits abgerechneten Monat benötigt eine eigene Mehrfachbezugsrechnung; die aktuelle Monatsquelle darf den ersten Einmalbezug nicht auslassen.')
        current = annual._reference(employee_id, details['current_annual_basis_ref'], 'annual_basis', fresh=fresh)
        previous = (annual._reference(employee_id, details['previous_annual_basis_ref'], 'annual_basis', fresh=fresh,
            current_one_off_id=earning['id'])
            if details['previous_annual_basis_ref'] else None)
        forecast = annual._reference(employee_id, details['annual_tax_forecast_ref'], 'annual_tax_forecast', fresh=fresh)
        pure = dict(schema_version=1, source_contract_version=SOURCE_CONTRACT_VERSION, rule_version=RULE_VERSION,
            employee_id=employee_id, month=details['month'], running_calculation_case=running,
            one_off_earning=earning, current_annual_basis=current, previous_annual_basis=previous, annual_tax_forecast=forecast)
        original_employee = running['sources']['period_case']['sources']['preparation']['snapshot']['employee']
        if employee_view(original_employee) != employee_view(employee):
            raise Problem(409, 'Laufende Monatsvorbereitung muss die tatsächlich bestätigte Mitarbeiterfassung enthalten.')
        return dict(schema_version=1, employee=employee_view(employee), details=details,
            source_files=files, calculation_source=pure)

    @staticmethod
    def _plan(snapshot):
        return calculate_oneoff_source(snapshot['calculation_source'], rule_version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION)

    @staticmethod
    def _versions(data):
        if (data['kind'] != KIND or data['rule_version'] != RULE_VERSION
                or type(data['source_contract_version']) is not int or data['source_contract_version'] != SOURCE_CONTRACT_VERSION):
            raise Problem(400, 'Einmalbezugsfall und explizite Regel-/Quellenversion erforderlich.')
        _integer(data['employee_revision'], 1)

    def sources(self, actor, query):
        _shape(query, ('employee_id', 'month'), ('employee_id', 'month')); month_range(query['month'])
        with transaction(self.office):
            fresh, employee = self._access(actor, query['employee_id'])
            source = PayrollAnnualBasis(self.office, clock=self.hr.clock).sources(fresh, dict(employee_id=employee['id']))
            # New factor/travel cases do not silently become one-off wage bases.
            source['calculation_cases']=[value for value in source['calculation_cases']
                if value['rule_version']=='de_2026_segments_entitlements_v5' and value['source_contract_version']==1]
            source.update(month=query['month'], one_off_cases=self._all(employee['id']))
            for value in source['one_off_cases']: validate_case_sources(self.office, value)
            return source

    def records(self, actor, query):
        _shape(query, ('employee_id', 'month'), ('employee_id',))
        if query.get('month') is not None: month_range(query['month'])
        with transaction(self.office):
            fresh, employee = self._access(actor, query['employee_id']); values = self._all(employee['id'])
            if query.get('month') is not None: values = [item for item in values if item['details']['month'] == query['month']]
            for value in values: validate_case_sources(self.office, value)
            return dict(employee_id=employee['id'], items=values, **self._capabilities(fresh))

    def get(self, actor, object_id, history=False):
        with transaction(self.office):
            row = self._row(object_id); self._access(actor, row['employee_id'])
            values = [self._event(value) for value in self.db.execute('SELECT * FROM ' + TABLES[0] + ' WHERE id=? ORDER BY revision', (object_id,))] if history else [self._event(row)]
            for value in values: validate_case_sources(self.office, value)
            return dict(items=values) if history else values[0]

    def preview(self, actor, data):
        fields = ('employee_id', 'employee_revision', 'kind', 'rule_version', 'source_contract_version', 'details', 'source_file_ids')
        _shape(data, fields, fields); self._versions(data); details = normalize_details(data['details']); ids = file_ids(data['source_file_ids'])
        with transaction(self.office):
            fresh, employee = self._access(actor, data['employee_id'])
            if employee['revision'] != data['employee_revision']: raise Problem(409, 'Aktuelle tatsächliche Mitarbeiterrevision erforderlich.')
            snapshot = self._snapshot(employee, details, ids); plan = self._plan(snapshot)
            return dict(employee_id=employee['id'], kind=KIND, source_snapshot=snapshot, source_hash=_sha(snapshot), plan=plan,
                preview_hash=_sha(dict(source_snapshot=snapshot, plan=plan)), can_confirm=True,
                can_calculate=plan['payroll_calculation_complete'], **self._capabilities(fresh))

    def save(self, actor, data):
        required = ('request_id', 'employee_id', 'employee_revision', 'kind', 'rule_version', 'source_contract_version',
            'revision', 'status', 'details', 'source_file_ids', 'confirmed', 'preview_hash')
        _shape(data, required + ('id', 'correction_reason'), required); identifier(data['request_id']); self._versions(data); _integer(data['revision'])
        if data.get('id') is not None: identifier(data['id'])
        if data['confirmed'] is not True or data['status'] not in ('active', 'void') or not re.fullmatch('[a-f0-9]{64}', str(data['preview_hash'])):
            raise Problem(400, 'Geprüfte Vorschau und ausdrückliche Einmalbezugsbestätigung erforderlich.')
        details = normalize_details(data['details']); ids = file_ids(data['source_file_ids'])
        reason = text(data.get('correction_reason', ''), 'Korrekturgrund', 2000, required=bool(data.get('id')))
        operation = 'one_off_case.saved'; fingerprint = _sha([operation, data])
        with transaction(self.office):
            fresh, employee = self._access(actor, data['employee_id'], 'personnel.approve'); self._gate(fresh, new=False)
            receipt = self.db.execute('SELECT * FROM ' + TABLES[1] + ' WHERE user_id=? AND request_id=?', (fresh['id'], data['request_id'])).fetchone()
            if receipt is not None:
                if receipt['operation'] != operation or receipt['request_hash'] != fingerprint: raise Problem(409, 'Vorgangs-ID gehört zu einem anderen ursprünglichen Auftrag.')
                row = self._row(receipt['fact_id'], receipt['fact_revision']); saved = self._event(row)
                if json.loads(row['payload_json'])['accepted_command'] != data or saved['content_hash'] != receipt['fact_content_hash']:
                    raise Problem(500, 'Einmalbezugsquittung widerspricht ihrem angenommenen Originalauftrag.')
                validate_case_sources(self.office, saved); return saved
            try:
                self._gate(fresh)
                if employee['revision'] != data['employee_revision']: raise Problem(409, 'Mitarbeiter seit Vorschau geändert.')
                previous = self._get(data['id']) if data.get('id') else None
                if previous and previous['employee_id'] != employee['id']: raise Problem(404, 'Einmalbezug gehört zu einer anderen Person.')
                if data['revision'] != (previous['revision'] if previous else 0): raise Problem(409, 'Einmalbezugsfall wurde inzwischen geändert.')
                key = identity_key(details)
                existing = self.db.execute('SELECT id FROM ' + TABLES[0] + ' WHERE employee_id=? AND identity_key=?', (employee['id'], key)).fetchone()
                if existing and (previous is None or existing['id'] != previous['id']):
                    raise Problem(409, 'Dieser konkrete Einmalanspruch besitzt bereits seinen eindeutigen Fall; Korrektur verwenden.')
                if previous and (identity_key(previous['details']) != key or previous['details']['month'] != details['month']):
                    raise Problem(400, 'Ursprünglichen Anspruch und Zuflussmonat nicht ohne gesonderten Zuordnungswechsel verändern.')
                if data['status'] == 'void':
                    if (previous is None or previous['status'] != 'active' or details != previous['details']
                            or ids != previous['source_file_ids'] or data['preview_hash'] != previous['preview_hash']):
                        raise Problem(400, 'Aufheben benötigt die unveränderte aktive Fassung.')
                    validate_case_sources(self.office, previous); snapshot, plan = previous['sources'], previous['plan']
                else:
                    snapshot = self._snapshot(employee, details, ids); plan = self._plan(snapshot)
                    if _sha(dict(source_snapshot=snapshot, plan=plan)) != data['preview_hash']: raise Problem(409, 'Einmalbezugsquellen wurden seit der Vorschau geändert.')
                payload = dict(rule_version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION,
                    details=details, source_file_ids=ids, plan=plan, preview_hash=data['preview_hash'],
                    correction_reason=reason, accepted_command=json.loads(canonical(data)))
                first, last = month_range(details['month'])
                envelope = dict(id=previous['id'] if previous else uuid.uuid4().hex,
                    revision=previous['revision'] + 1 if previous else 1, employee_id=employee['id'], kind=KIND,
                    effective_from=first.isoformat(), effective_to=last.isoformat(), status=data['status'], source_hash=_sha(snapshot),
                    previous_hash=previous['content_hash'] if previous else None, created_by=fresh['id'], created_at=self.hr.now(),
                    identity_key=None if previous else key, command_hash=fingerprint, payload=payload, sources=snapshot)
                columns = tuple(key for key in envelope if key not in ('payload', 'sources'))
                self.db.execute('INSERT INTO ' + TABLES[0] + '(' + ','.join(columns) + ',payload_json,sources_json,content_hash) VALUES('
                    + ','.join('?' for _ in range(len(columns) + 3)) + ')', tuple(envelope[key] for key in columns)
                    + (canonical(payload), canonical(snapshot), _sha(envelope)))
                saved = self._get(envelope['id'])
                self.db.execute('INSERT INTO ' + TABLES[1] + '(user_id,request_id,operation,request_hash,fact_id,fact_revision,fact_content_hash,created_at) VALUES(?,?,?,?,?,?,?,?)',
                    (fresh['id'], data['request_id'], operation, fingerprint, saved['id'], saved['revision'], saved['content_hash'], saved['created_at']))
                validate_case_sources(self.office, saved); self.office.audit(fresh, 'payroll.one_off_case', saved['id']); return saved
            except Problem as error:
                if error.status == 409: raise Problem(409, error.message, request_resolution='not_accepted') from None
                raise

    def resolve_one_off_case(self, actor, employee_id, value, *, fresh=True):
        value = ref(value)
        with transaction(self.office):
            _, employee = self._access(actor, employee_id); record = self._get(value['id'], value['revision'])
            if record['employee_id'] != employee_id: raise Problem(404, 'Einmalbezugsfall gehört nicht zu dieser Person.')
            if record['status'] != 'active' or reference(record) != value or fresh and reference(self._get(value['id'])) != value:
                raise Problem(409, 'Einmalbezugsfall wurde geändert oder aufgehoben.')
            validate_case_sources(self.office, record)
            if fresh and self._snapshot(employee, record['details'], record['source_file_ids']) != record['sources']:
                raise Problem(409, 'Einmalbezugsfall entspricht nicht mehr seinen tatsächlichen Originalen.')
            return record


def validate_case_sources(office, value):
    api = PayrollOneoffCases(office)
    try:
        row = api._row(value['id'], value['revision']); payload = json.loads(row['payload_json']); command = payload['accepted_command']; api._versions(command)
        details = normalize_details(value['details']); first, last = month_range(details['month']); fingerprint = _sha(['one_off_case.saved', command])
        receipt = office.db.execute('SELECT * FROM ' + TABLES[1] + ' WHERE user_id=? AND request_id=?', (value['created_by'], command['request_id'])).fetchone()
        if (api._event(row) != value or value['rule_version'] != RULE_VERSION or type(value['source_contract_version']) is not int or value['source_contract_version'] != SOURCE_CONTRACT_VERSION
                or value['kind'] != KIND or value['effective_from'] != first.isoformat() or value['effective_to'] != last.isoformat()
                or row['identity_key'] != (identity_key(details) if value['revision'] == 1 else None)
                or row['command_hash'] != fingerprint or receipt is None or receipt['operation'] != 'one_off_case.saved'
                or receipt['request_hash'] != fingerprint or receipt['fact_id'] != value['id'] or receipt['fact_revision'] != value['revision']
                or receipt['fact_content_hash'] != value['content_hash'] or receipt['created_at'] != value['created_at']
                or normalize_details(command['details']) != details or command['employee_id'] != value['employee_id']
                or command['revision'] + 1 != value['revision'] or command.get('id', value['id']) != value['id']
                or command['status'] != value['status'] or command['preview_hash'] != value['preview_hash'] or command['confirmed'] is not True
                or file_ids(command['source_file_ids']) != value['source_file_ids'] or details != value['details']
                or text(command.get('correction_reason', ''), 'Korrekturgrund', 2000) != value['correction_reason']):
            raise ValueError('Changed one-off acceptance original')
        employee = value['sources']['employee']; _shape(employee, EMPLOYEE_FIELDS, EMPLOYEE_FIELDS)
        if employee['id'] != value['employee_id'] or value['status'] == 'active' and employee['revision'] != command['employee_revision']:
            raise ValueError('Changed originally accepted employee revision')
        expected = api._snapshot(employee, details, value['source_file_ids'], fresh=False); plan = api._plan(expected)
        from oneoff_provenance_compat import calculation_matches
        if calculation_matches(expected['calculation_source'],plan,value['plan']):plan=value['plan']
        if expected != value['sources'] or plan != value['plan'] or value['preview_hash'] != _sha(dict(source_snapshot=expected, plan=plan)):
            raise ValueError('Changed one-off historical originals or arithmetic')
        return True
    except (Problem, KeyError, TypeError, ValueError, RecursionError) as error:
        raise ValueError('Invalid one-off case archive') from error


def _consumption_row(office, run_id, revision):
    row = office.db.execute('SELECT * FROM ' + TABLES[2] + ' WHERE run_id=? AND run_revision=?', (run_id, revision)).fetchone()
    if row is None: raise Problem(500, 'Atomarer Einmalbezugsverbrauch fehlt für die ursprüngliche Lohnrevision.')
    result = dict(row); payload = json.loads(result.pop('payload_json')); content_hash = result.pop('content_hash')
    result['payload'] = payload
    if _sha(result) != content_hash: raise Problem(500, 'Integrität des ursprünglichen Einmalbezugsverbrauchs verletzt.')
    return dict(result, content_hash=content_hash)


def _consumption_payload(run, previous=None):
    source = run['source']; case = source['one_off_case']; pure = case['sources']['calculation_source']
    extra = run['calculation']['one_off_details']
    return dict(schema_version=1, run_ref=reference(run), case_ref=reference(case),
        earning_ref=reference(pure['one_off_earning']), current_annual_basis_ref=reference(pure['current_annual_basis']),
        previous_annual_basis_ref=reference(pure['previous_annual_basis']) if pure['previous_annual_basis'] else None,
        annual_tax_forecast_ref=reference(pure['annual_tax_forecast']), receipt_date=extra['receipt_date'],
        amount_minor=extra['amount_minor'], assignment=extra['assignment'], assigned_part_key=extra['assigned_part_key'],
        additional_contributed_bases_minor={key:value['total_minor'] for key,value in extra['social']['branch_bases'].items()},
        previous_run_ref=reference(previous) if previous else None)


def record_run_consumption(office, actor, run, previous=None):
    """Append within the owning payroll Finalize transaction, after its run row.

    The common Office transaction takes the same PostgreSQL advisory lock for
    both source revalidation and this unique allocation. A single immutable
    claim owner survives all corrections and can never become a second run.
    """
    if run['source'].get('source_schema_version') != 4: raise Problem(400, 'Einmalbezugsverbrauch benötigt einen Source4-Lauf.')
    case = run['source']['one_off_case']; validate_case_sources(office, case)
    if (case['employee_id'] != run['employee_id'] or case['plan'] != run['calculation']
            or not run['calculation']['payroll_calculation_complete']):
        raise Problem(409, 'Abrechnung und angenommener Einmalbezugsfall widersprechen sich.')
    from business_payroll import Payroll
    payroll = Payroll(office)
    if payroll._event(payroll._row(run['id'], 'run', run['revision'])) != run:
        raise Problem(500, 'Tatsächliche angenommene Lohnrevision fehlt vor dem Einmalbezugsverbrauch.')
    expected_previous = payroll._event(payroll._row(run['id'], 'run', run['revision']-1)) if run['revision'] > 1 else None
    if expected_previous != previous: raise Problem(409, 'Einmalbezug muss an die tatsächliche vorherige Lohnrevision anschließen.')
    claim_id = case['details']['one_off_earning_ref']['id']
    from business_schema import _tables
    if 'business_payroll_multiple_consumptions' in _tables(office) and office.db.execute(
            'SELECT run_id FROM business_payroll_multiple_consumptions WHERE employee_id=? AND claim_identity_key=?',
            (run['employee_id'],claim_id)).fetchone() is not None:
        raise Problem(409,'Der ursprüngliche Anspruch ist bereits einem Source5-Lauf zugeordnet.')
    owner = office.db.execute('SELECT run_id FROM ' + TABLES[2] + ' WHERE employee_id=? AND claim_identity_key=?',
        (run['employee_id'], claim_id)).fetchone()
    if owner is not None and owner['run_id'] != run['id']:
        raise Problem(409, 'Dieser ursprüngliche Einmalanspruch ist bereits einem anderen tatsächlichen Lohnlauf zugeordnet.')
    if previous and previous['source'].get('source_schema_version') == 4:
        validate_run_consumption(office, previous)
        if previous['source']['one_off_case']['details']['one_off_earning_ref']['id'] != claim_id:
            raise Problem(409, 'Die Korrektur darf den bereits verbrauchten Einmalanspruch nicht gegen einen anderen austauschen.')
    existing = office.db.execute('SELECT run_id FROM ' + TABLES[2] + ' WHERE run_id=? AND run_revision=?', (run['id'],run['revision'])).fetchone()
    if existing is not None:
        validate_run_consumption(office, run); return _consumption_row(office, run['id'], run['revision'])
    payload = _consumption_payload(run, previous)
    envelope = dict(run_id=run['id'], run_revision=run['revision'], employee_id=run['employee_id'],
        case_id=case['id'], case_revision=case['revision'], claim_identity_key=claim_id if owner is None else None,
        created_by=actor['id'], created_at=run['created_at'], payload=payload)
    columns = tuple(key for key in envelope if key != 'payload')
    office.db.execute('INSERT INTO ' + TABLES[2] + '(' + ','.join(columns) + ',payload_json,content_hash) VALUES('
        + ','.join('?' for _ in range(len(columns)+2)) + ')', tuple(envelope[key] for key in columns) + (canonical(payload), _sha(envelope)))
    validate_run_consumption(office, run)
    return _consumption_row(office, run['id'], run['revision'])


def validate_run_consumption(office, run):
    """Historical source binding only; never recursively verifies this run."""
    if run['source'].get('source_schema_version') != 4: return True
    from business_payroll import Payroll
    payroll = Payroll(office); row = _consumption_row(office, run['id'], run['revision'])
    previous = payroll._event(payroll._row(run['id'], 'run', run['revision']-1)) if run['revision'] > 1 else None
    payload = _consumption_payload(run, previous); case = run['source']['one_off_case']; claim = case['details']['one_off_earning_ref']['id']
    owner = office.db.execute('SELECT run_id,run_revision FROM ' + TABLES[2] + ' WHERE employee_id=? AND claim_identity_key=?',
        (run['employee_id'], claim)).fetchone()
    first = owner is not None and owner['run_id'] == run['id'] and owner['run_revision'] == run['revision']
    if (row['payload'] != payload or row['employee_id'] != run['employee_id'] or row['case_id'] != case['id']
            or row['case_revision'] != case['revision'] or row['created_by'] != run['created_by'] or row['created_at'] != run['created_at']
            or owner is None or owner['run_id'] != run['id'] or owner['run_revision'] > run['revision']
            or row['claim_identity_key'] != (claim if first else None)):
        raise Problem(500, 'Einmalbezugsverbrauch widerspricht dem ursprünglichen Lauf, Anspruch oder Jahresstand.')
    if previous and previous['source'].get('source_schema_version') == 4 and previous['source']['one_off_case']['details']['one_off_earning_ref']['id'] != claim:
        raise Problem(500, 'Historische Einmalbezugszuordnung hat ihren ursprünglichen Anspruch gewechselt.')
    return True


def validate_integrity(office):
    from business_schema import _tables
    present = set(TABLES) & _tables(office)
    if not present: return True
    if present != set(TABLES): raise ValueError('Incomplete one-off case schema')
    api = PayrollOneoffCases(office); prior = {}; accepted = set()
    for row in office.db.execute('SELECT * FROM ' + TABLES[0] + ' ORDER BY id,revision'):
        value = api._event(row); previous = prior.get(value['id'])
        if (value['revision'] != (previous['revision'] + 1 if previous else 1)
                or value['previous_hash'] != (previous['content_hash'] if previous else None)
                or row['identity_key'] != (None if previous else identity_key(value['details']))
                or previous and (value['employee_id'] != previous['employee_id'] or value['effective_from'] != previous['effective_from']
                    or value['effective_to'] != previous['effective_to'] or identity_key(value['details']) != identity_key(previous['details']))
                or previous and not value['correction_reason'] or not previous and value['status'] != 'active'):
            raise ValueError('Broken one-off case history')
        if value['status'] == 'void' and (previous is None or previous['status'] != 'active'
                or any(value[key] != previous[key] for key in ('details', 'source_file_ids', 'sources', 'plan', 'preview_hash'))):
            raise ValueError('Changed one-off withdrawal original')
        validate_case_sources(office, value); prior[value['id']] = value; accepted.add((value['id'], value['revision']))
    receipts = [(row['fact_id'], row['fact_revision']) for row in office.db.execute('SELECT * FROM ' + TABLES[1])]
    if len(receipts) != len(accepted) or set(receipts) != accepted: raise ValueError('Missing or duplicate one-off acceptance')
    from business_payroll import Payroll
    payroll = Payroll(office); expected = set()
    for row in office.db.execute("SELECT * FROM business_payroll_events WHERE kind='run' ORDER BY id,revision"):
        run = payroll._event(row)
        if run['source'].get('source_schema_version') == 4:
            try: validate_run_consumption(office, run)
            except Problem as error: raise ValueError('Invalid original one-off consumption') from error
            expected.add((run['id'],run['revision']))
    found = {(row['run_id'],row['run_revision']) for row in office.db.execute('SELECT run_id,run_revision FROM ' + TABLES[2])}
    if found != expected: raise ValueError('Missing or orphaned one-off consumption')
    return True


def methods(path):
    if path == '/payroll/one-off-cases': return 'GET, POST'
    if path == '/payroll/one-off-cases/preview': return 'POST'
    if path == '/payroll/one-off-cases/sources' or re.fullmatch('/payroll/one-off-cases/' + ID + '(?:/history)?', path): return 'GET'
    return None


def dispatch(office, actor, path, method, data):
    allowed = methods(path)
    if allowed is None: return None
    if method not in allowed.split(', '): raise Problem(405, 'Methode für diesen Einmalbezugsfall nicht erlaubt.')
    api = PayrollOneoffCases(office)
    if method == 'POST': result = api.preview(actor, data) if path.endswith('/preview') else api.save(actor, data)
    else:
        _shape(data, ('_query',)); query = data.get('_query', {})
        if path.endswith('/sources'): result = api.sources(actor, query)
        elif path == '/payroll/one-off-cases': result = api.records(actor, query)
        else: _shape(query, ()); result = api.get(actor, path.split('/')[3], path.endswith('/history'))
    return result, 200, 'application/json'
