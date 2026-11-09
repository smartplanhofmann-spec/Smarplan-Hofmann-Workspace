"""Private additive Source5 cases with immutable original monthly acceptance."""
import json
import re
import uuid

from core import Problem,canonical
from business_operations import identifier,text,transaction
from business_personnel_workflow import _integer,_sha,_shape
from business_payroll_facts import PayrollFacts,ref,reference,file_ids,employee_view,EMPLOYEE_FIELDS
from business_payroll_annual_basis import PayrollAnnualBasis
from business_payroll_calculation_cases import PayrollCalculationCases
from payroll_de_2026 import day,month_range
from payroll_multiple_oneoff_2026 import MULTIPLE_RULE_VERSION as RULE_VERSION,SOURCE_CONTRACT_VERSION,calculate_multiple_source

FEATURES=('payroll_multiple_cases',)
TABLES=('business_payroll_multiple_case_events','business_payroll_multiple_case_requests','business_payroll_multiple_consumptions')
KIND='multiple_one_off_case'
ID=r'[a-f0-9]{32}'


def schema_statements(binary_type='BYTEA'):
    from business_payroll_facts import schema_statements as original
    return [value.replace('business_payroll_fact','business_payroll_multiple_case')
        .replace("'employment_terms','work_schedule','period_case'","'multiple_one_off_case'") for value in original(binary_type)]+[
        """CREATE TABLE IF NOT EXISTS business_payroll_multiple_consumptions(
        run_id TEXT NOT NULL,run_revision INTEGER NOT NULL CHECK(run_revision>0),
        employee_id TEXT NOT NULL REFERENCES business_employees(id),case_id TEXT NOT NULL,case_revision INTEGER NOT NULL,
        component_key TEXT NOT NULL,event_key TEXT NOT NULL,claim_identity_key TEXT,event_identity_key TEXT,
        payload_json TEXT NOT NULL,content_hash TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
        PRIMARY KEY(run_id,run_revision,component_key,event_key),UNIQUE(employee_id,claim_identity_key),UNIQUE(employee_id,event_identity_key),
        FOREIGN KEY(run_id,run_revision) REFERENCES business_payroll_events(id,revision),
        FOREIGN KEY(case_id,case_revision) REFERENCES business_payroll_multiple_case_events(id,revision))"""]


def guard_statements(dialect):
    from business_payroll_facts import guard_statements as original
    statements=[value.replace('business_payroll_fact','business_payroll_multiple_case')
        .replace('immutable payroll fact','immutable payroll multiple case') for value in original(dialect)]
    statements += [value.replace(TABLES[0],TABLES[2]) for value in statements if TABLES[0] in value and 'insert_guard' not in value]
    if dialect=='sqlite':
        statements.append("CREATE TRIGGER IF NOT EXISTS business_payroll_multiple_consumptions_insert_guard BEFORE INSERT ON "
            "business_payroll_multiple_consumptions WHEN EXISTS(SELECT 1 FROM business_payroll_multiple_consumptions WHERE "
            "(run_id=NEW.run_id AND run_revision=NEW.run_revision AND component_key=NEW.component_key AND event_key=NEW.event_key) OR "
            "(NEW.claim_identity_key IS NOT NULL AND employee_id=NEW.employee_id AND claim_identity_key=NEW.claim_identity_key) OR "
            "(NEW.event_identity_key IS NOT NULL AND employee_id=NEW.employee_id AND event_identity_key=NEW.event_identity_key)) "
            "BEGIN SELECT RAISE(ABORT,'immutable payroll multiple consumption'); END")
    return statements


def protected_tables():return TABLES

def runtime_privileges():return {table:('SELECT','INSERT') for table in TABLES}


def normalize_details(value):
    fields=('month','running_calculation_case_ref','components','current_annual_basis_ref','previous_annual_basis_ref',
        'annual_tax_forecasts','completeness','verification_note')
    _shape(value,fields,fields);first,last=month_range(value['month'])
    if first.year!=2026:raise Problem(400,'Mehrfachbezugsmonat 2026 erforderlich.')
    result=dict(value)
    for key in ('running_calculation_case_ref','current_annual_basis_ref','previous_annual_basis_ref'):
        result[key]=None if key=='previous_annual_basis_ref' and value[key] is None else ref(value[key])
    parts=value['components'];components=[];seen=set();event_ids=set()
    if not isinstance(parts,list) or not 1<=len(parts)<=20:raise Problem(400,'Ein bis zwanzig ursprüngliche Anspruchskomponenten erforderlich.')
    for part in parts:
        _shape(part,('component_key','earning_ref','planned_receipts'),('component_key','earning_ref','planned_receipts'))
        identifier(part['component_key']);earning=ref(part['earning_ref'])
        if part['component_key']!=earning['id'] or part['component_key'] in seen:raise Problem(409,'Jeder Anspruch benötigt genau seine ursprüngliche stabile Komponente.')
        seen.add(part['component_key']);receipts=part['planned_receipts'];normalized=[]
        if not isinstance(receipts,list) or not 1<=len(receipts)<=20:raise Problem(400,'Begrenzte konkrete geplante Zuflüsse erforderlich.')
        for receipt in receipts:
            _shape(receipt,('event_key','receipt_date','gross_minor','document_refs'),('event_key','receipt_date','gross_minor','document_refs'))
            identifier(receipt['event_key']);day(receipt['receipt_date']);_integer(receipt['gross_minor'],1,10**12)
            if receipt['event_key'] in event_ids or receipt['receipt_date'][:7]!=value['month']:raise Problem(409,'Ereignisse sind eindeutig und gehören zum selben Monat.')
            event_ids.add(receipt['event_key']);documents=receipt['document_refs']
            if not isinstance(documents,list) or not 1<=len(documents)<=20:raise Problem(400,'Konkrete Originalreferenzen erforderlich.')
            documents=[ref(item) for item in documents]
            if len({canonical(item) for item in documents})!=len(documents):raise Problem(400,'Doppelte Originalreferenzen.')
            normalized.append(dict(receipt,document_refs=sorted(documents,key=canonical)))
        components.append(dict(component_key=part['component_key'],earning_ref=earning,planned_receipts=sorted(normalized,key=lambda item:(item['receipt_date'],item['event_key']))))
    if len(event_ids)>100:raise Problem(400,'Höchstens hundert Ereignisse je Monatsfall.')
    result['components']=sorted(components,key=lambda item:item['component_key'])
    forecasts=value['annual_tax_forecasts'];seen_forecasts=set();normalized=[]
    if not isinstance(forecasts,list) or len(forecasts)>100:raise Problem(400,'Explizite begrenzte Steuerquellenliste erforderlich.')
    for item in forecasts:
        _shape(item,('event_key','annual_tax_forecast_ref'),('event_key','annual_tax_forecast_ref'));identifier(item['event_key'])
        if item['event_key'] not in event_ids or item['event_key'] in seen_forecasts:raise Problem(409,'Jede Steuerprognose gehört genau zu ihrem Ereignis.')
        seen_forecasts.add(item['event_key']);normalized.append(dict(event_key=item['event_key'],annual_tax_forecast_ref=ref(item['annual_tax_forecast_ref'])))
    result['annual_tax_forecasts']=sorted(normalized,key=lambda item:item['event_key'])
    _shape(value['completeness'],('month_events_complete','evidence_ref'),('month_events_complete','evidence_ref'))
    if value['completeness']['month_events_complete'] is not True:raise Problem(409,'Vollständige Monatsgruppe ausdrücklich bestätigen.')
    result['completeness']=dict(month_events_complete=True,evidence_ref=ref(value['completeness']['evidence_ref']))
    result['verification_note']=text(value['verification_note'],'Beurteilung der vollständigen Monatsgruppe',3000,required=True)
    return result


def identity_key(details):return 'month:'+details['month']


def components_identity(parts):
    return [(part['component_key'],[(event['event_key'],event['receipt_date'],event['gross_minor']) for event in part['planned_receipts']]) for part in parts]


class PayrollMultipleCases(PayrollFacts):
    def _gate(self, actor, *, new=True):
        from business_schema import require_capability
        from business_organization import require_active
        require_capability(self.office, 'business_payroll_multiple_cases')
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
        employee_id=employee['id'];files=self._files(employee_id,ids,fresh=fresh)
        cases=PayrollCalculationCases(self.office,clock=self.hr.clock)
        annual=PayrollAnnualBasis(self.office,clock=self.hr.clock)
        value=details['running_calculation_case_ref'];running=cases._get(value['id'],value['revision'])
        from business_payroll_calculation_cases import validate_case_sources as validate_running
        if (running['employee_id']!=employee_id or running['kind']!='calculation_case'
                or running['status']!='active' or reference(running)!=value):
            raise Problem(409,'Laufender Originalfall gehört nicht zur Person oder ist nicht aktiv.')
        if running['rule_version']!='de_2026_segments_entitlements_v5' or running['source_contract_version']!=1:
            raise Problem(409,'Einmalbezüge auf einem Faktor-Reisefall benötigen ihren eigenen Regelzweig.')
        validate_running(self.office,running)
        flat=running['sources']['flat_travel_tax'];planned_on=flat['recording_context']['planned_recording_on'] if flat else None
        if fresh and (reference(cases._get(value['id']))!=value or cases._snapshot(employee,'calculation_case',
                running['details'],running['source_file_ids'],planned_on=planned_on)!=running['sources']):
            raise Problem(409,'Der ursprüngliche laufende Gesamtfall wurde geändert.')
        components=[]
        for part in details['components']:
            earning=annual._reference(employee_id,part['earning_ref'],'one_off_earning',fresh=fresh)
            components.append(dict(component_key=part['component_key'],earning=earning,planned_receipts=part['planned_receipts']))
        current=annual._reference(employee_id,details['current_annual_basis_ref'],'annual_basis',fresh=fresh)
        previous=(annual._reference(employee_id,details['previous_annual_basis_ref'],'annual_basis',fresh=fresh,
            current_one_off_id=components[0]['earning']['id'] if len(components)==1 else None) if details['previous_annual_basis_ref'] else None)
        forecasts=[dict(event_key=item['event_key'],annual_tax_forecast=annual._reference(employee_id,
            item['annual_tax_forecast_ref'],'annual_tax_forecast',fresh=fresh)) for item in details['annual_tax_forecasts']]
        if employee_view(running['sources']['period_case']['sources']['preparation']['snapshot']['employee'])!=employee_view(employee):
            raise Problem(409,'Laufende Vorbereitung muss die bestätigte Mitarbeiterfassung enthalten.')
        if fresh:
            from business_payroll import Payroll
            for run in Payroll(self.office)._all('run',employee_id):
                if run['source']['month']!=details['month']:continue
                if run['source'].get('source_schema_version')==4:
                    raise Problem(409,'Ein bereits verbrauchter Source4-Anspruch benötigt seinen gesondert geprüften Versionsübergang; neue Ereignis-IDs dürfen ihn nicht nochmals verwenden.')
                if run['source'].get('source_schema_version')==5:
                    validate_run_consumption(self.office,run)
                    old=run['source']['multiple_one_off_case']['details']['components']
                    if components_identity(details['components'])!=components_identity(old):
                        raise Problem(409,'Ein bereits verbrauchtes Source5-Ereignis darf nicht durch einen anderen Anspruch, Betrag oder Zuflusstag ersetzt werden.')
        pure=dict(schema_version=1,source_contract_version=SOURCE_CONTRACT_VERSION,rule_version=RULE_VERSION,
            employee_id=employee_id,month=details['month'],running_calculation_case=running,components=components,
            current_annual_basis=current,previous_annual_basis=previous,annual_tax_forecasts=forecasts,completeness=details['completeness'])
        return dict(schema_version=1,employee=employee_view(employee),details=details,source_files=files,calculation_source=pure)

    @staticmethod
    def _plan(snapshot):
        return calculate_multiple_source(snapshot['calculation_source'], rule_version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION)

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
            source.update(month=query['month'], multiple_one_off_cases=self._all(employee['id']))
            for value in source['multiple_one_off_cases']: validate_case_sources(self.office, value)
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
        operation = 'multiple_one_off_case.saved'; fingerprint = _sha([operation, data])
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
                validate_case_sources(self.office, saved); self.office.audit(fresh, 'payroll.multiple_one_off_case', saved['id']); return saved
            except Problem as error:
                if error.status == 409: raise Problem(409, error.message, request_resolution='not_accepted') from None
                raise

    def resolve_multiple_case(self, actor, employee_id, value, *, fresh=True):
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
    api = PayrollMultipleCases(office)
    try:
        row = api._row(value['id'], value['revision']); payload = json.loads(row['payload_json']); command = payload['accepted_command']; api._versions(command)
        details = normalize_details(value['details']); first, last = month_range(details['month']); fingerprint = _sha(['multiple_one_off_case.saved', command])
        receipt = office.db.execute('SELECT * FROM ' + TABLES[1] + ' WHERE user_id=? AND request_id=?', (value['created_by'], command['request_id'])).fetchone()
        if (api._event(row) != value or value['rule_version'] != RULE_VERSION or type(value['source_contract_version']) is not int or value['source_contract_version'] != SOURCE_CONTRACT_VERSION
                or value['kind'] != KIND or value['effective_from'] != first.isoformat() or value['effective_to'] != last.isoformat()
                or row['identity_key'] != (identity_key(details) if value['revision'] == 1 else None)
                or row['command_hash'] != fingerprint or receipt is None or receipt['operation'] != 'multiple_one_off_case.saved'
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


def _consumption_payload(run, previous=None):
    case=run['source']['multiple_one_off_case'];pure=case['sources']['calculation_source']
    extra=run['calculation']['multiple_one_off_details']
    if (len(pure['components'])!=1 or len(pure['components'][0]['planned_receipts'])!=1
            or not run['calculation']['payroll_calculation_complete'] or 'single_original_calculation' not in extra):
        raise Problem(409,'Nur der vollständig geprüfte einzelne Anspruch darf verbraucht werden.')
    part=pure['components'][0];event=part['planned_receipts'][0];original=extra['single_original_calculation']['one_off_details']
    return dict(schema_version=1,run_ref=reference(run),case_ref=reference(case),
        component_key=part['component_key'],event_key=event['event_key'],earning_ref=reference(part['earning']),
        current_annual_basis_ref=reference(pure['current_annual_basis']),
        previous_annual_basis_ref=reference(pure['previous_annual_basis']) if pure['previous_annual_basis'] else None,
        annual_tax_forecast_ref=reference(pure['annual_tax_forecasts'][0]['annual_tax_forecast']),
        receipt_date=event['receipt_date'],gross_minor=event['gross_minor'],assignment=original['assignment'],
        assigned_part_key=original['assigned_part_key'],
        additional_contributed_bases_minor={key:value['total_minor'] for key,value in original['social']['branch_bases'].items()},
        previous_run_ref=reference(previous) if previous else None)


def _consumption_row(office, run):
    rows=office.db.execute('SELECT * FROM '+TABLES[2]+' WHERE run_id=? AND run_revision=?',(run['id'],run['revision'])).fetchall()
    if len(rows)!=1:raise Problem(500,'Genau ein atomarer Source5-Anspruchsverbrauch muss vorhanden sein.')
    result=dict(rows[0]);payload=json.loads(result.pop('payload_json'));content_hash=result.pop('content_hash');result['payload']=payload
    if _sha(result)!=content_hash:raise Problem(500,'Unveränderte Source5-Verbrauchsquittung erforderlich.')
    return dict(result,content_hash=content_hash)


def _owners(office, employee, claim, event):
    from business_schema import _tables
    claim_owner=office.db.execute('SELECT run_id,run_revision FROM '+TABLES[2]+' WHERE employee_id=? AND claim_identity_key=?',(employee,claim)).fetchone()
    event_owner=office.db.execute('SELECT run_id,run_revision FROM '+TABLES[2]+' WHERE employee_id=? AND event_identity_key=?',(employee,event)).fetchone()
    legacy=None
    if 'business_payroll_oneoff_consumptions' in _tables(office):
        legacy=office.db.execute('SELECT run_id FROM business_payroll_oneoff_consumptions WHERE employee_id=? AND claim_identity_key=?',(employee,claim)).fetchone()
    return claim_owner,event_owner,legacy


def record_run_consumption(office, actor, run, previous=None):
    if run['source'].get('source_schema_version')!=5:raise Problem(400,'Explizite Source5-Lohnrevision erforderlich.')
    case=run['source']['multiple_one_off_case'];validate_case_sources(office,case)
    if actor['id']!=run['created_by'] or case['employee_id']!=run['employee_id'] or case['plan']!=run['calculation']:
        raise Problem(409,'Tatsächlicher Abschluss, Person und ursprünglicher Mehrfachfall widersprechen sich.')
    from business_payroll import Payroll
    payroll=Payroll(office)
    if payroll._event(payroll._row(run['id'],'run',run['revision']))!=run:raise Problem(500,'Angenommene Lohnrevision fehlt vor dem Verbrauch.')
    expected=payroll._event(payroll._row(run['id'],'run',run['revision']-1)) if run['revision']>1 else None
    if expected!=previous:raise Problem(409,'Verbrauch benötigt die tatsächliche vorherige Lohnrevision.')
    payload=_consumption_payload(run,previous);claim=payload['component_key'];event=payload['event_key']
    claim_owner,event_owner,legacy=_owners(office,run['employee_id'],claim,event)
    if legacy or any(owner is not None and owner['run_id']!=run['id'] for owner in (claim_owner,event_owner)):
        raise Problem(409,'Anspruch oder Zuflussereignis ist bereits einem anderen tatsächlichen Lohnlauf bzw. Source4-Verbrauch zugeordnet.')
    if previous:
        version=previous['source'].get('source_schema_version')
        if version==5:
            validate_run_consumption(office,previous)
            if components_identity(previous['source']['multiple_one_off_case']['details']['components'])!=components_identity(case['details']['components']):
                raise Problem(409,'Verbrauchte Ereignisse dürfen nicht neu bezeichnet oder umdatiert werden.')
        elif version!=3 or previous['source']['calculation_case']!=run['source']['calculation_case']:
            raise Problem(409,'Der erste Versionsübergang benötigt genau den unveränderten laufenden v5-Originalfall.')
    envelope=dict(run_id=run['id'],run_revision=run['revision'],employee_id=run['employee_id'],case_id=case['id'],case_revision=case['revision'],
        component_key=claim,event_key=event,claim_identity_key=claim if claim_owner is None else None,
        event_identity_key=event if event_owner is None else None,payload=payload,created_by=actor['id'],created_at=run['created_at'])
    columns=tuple(key for key in envelope if key!='payload')
    office.db.execute('INSERT INTO '+TABLES[2]+'('+','.join(columns)+',payload_json,content_hash) VALUES('+','.join('?' for _ in range(len(columns)+2))+')',
        tuple(envelope[key] for key in columns)+(canonical(payload),_sha(envelope)))
    validate_run_consumption(office,run);return _consumption_row(office,run)


def validate_run_consumption(office, run):
    if run['source'].get('source_schema_version')!=5:return True
    from business_payroll import Payroll
    payroll=Payroll(office);row=_consumption_row(office,run)
    previous=payroll._event(payroll._row(run['id'],'run',run['revision']-1)) if run['revision']>1 else None
    payload=_consumption_payload(run,previous);case=run['source']['multiple_one_off_case'];claim=payload['component_key'];event=payload['event_key']
    claim_owner,event_owner,legacy=_owners(office,run['employee_id'],claim,event)
    if (legacy or row['payload']!=payload or row['employee_id']!=run['employee_id'] or row['case_id']!=case['id']
            or row['case_revision']!=case['revision'] or row['component_key']!=claim or row['event_key']!=event
            or row['created_by']!=run['created_by'] or row['created_at']!=run['created_at']):
        raise Problem(500,'Source5-Verbrauch widerspricht tatsächlichen Originalen oder wurde doppelt zugeordnet.')
    for owner,key,value in ((claim_owner,'claim_identity_key',claim),(event_owner,'event_identity_key',event)):
        if (owner is None or owner['run_id']!=run['id'] or owner['run_revision']>run['revision']
                or row[key]!=(value if owner['run_revision']==run['revision'] else None)):
            raise Problem(500,'Ursprünglicher Anspruchs- und Ereignisinhaber fehlt oder wurde ersetzt.')
    if previous:
        version=previous['source'].get('source_schema_version')
        if version==5:
            if components_identity(previous['source']['multiple_one_off_case']['details']['components'])!=components_identity(case['details']['components']):
                raise Problem(500,'Verbrauchte Source5-Ereignisse wurden historisch umgewidmet.')
        elif version!=3 or previous['source']['calculation_case']!=run['source']['calculation_case']:
            raise Problem(500,'Nicht belegter historischer Source5-Versionsübergang.')
    return True


def validate_integrity(office):
    from business_schema import _tables
    present = set(TABLES) & _tables(office)
    if not present: return True
    if present != set(TABLES): raise ValueError('Incomplete multiple one-off case schema')
    api = PayrollMultipleCases(office); prior = {}; accepted = set()
    for row in office.db.execute('SELECT * FROM ' + TABLES[0] + ' ORDER BY id,revision'):
        value = api._event(row); previous = prior.get(value['id'])
        if (value['revision'] != (previous['revision'] + 1 if previous else 1)
                or value['previous_hash'] != (previous['content_hash'] if previous else None)
                or row['identity_key'] != (None if previous else identity_key(value['details']))
                or previous and (value['employee_id'] != previous['employee_id'] or value['effective_from'] != previous['effective_from']
                    or value['effective_to'] != previous['effective_to'] or identity_key(value['details']) != identity_key(previous['details']))
                or previous and not value['correction_reason'] or not previous and value['status'] != 'active'):
            raise ValueError('Broken multiple one-off case history')
        if value['status'] == 'void' and (previous is None or previous['status'] != 'active'
                or any(value[key] != previous[key] for key in ('details', 'source_file_ids', 'sources', 'plan', 'preview_hash'))):
            raise ValueError('Changed multiple one-off withdrawal original')
        validate_case_sources(office, value); prior[value['id']] = value; accepted.add((value['id'], value['revision']))
    receipts = [(row['fact_id'], row['fact_revision']) for row in office.db.execute('SELECT * FROM ' + TABLES[1])]
    if len(receipts) != len(accepted) or set(receipts) != accepted: raise ValueError('Missing or duplicate multiple one-off acceptance')
    from business_payroll import Payroll
    payroll=Payroll(office);expected=set()
    for row in office.db.execute("SELECT * FROM business_payroll_events WHERE kind='run' ORDER BY id,revision"):
        run=payroll._event(row)
        if run['source'].get('source_schema_version')==5:
            try:validate_run_consumption(office,run)
            except Problem as error:raise ValueError('Invalid Source5 consumption original') from error
            payload=_consumption_payload(run)
            expected.add((run['id'],run['revision'],payload['component_key'],payload['event_key']))
    found={(row['run_id'],row['run_revision'],row['component_key'],row['event_key']) for row in office.db.execute('SELECT * FROM '+TABLES[2])}
    if expected!=found:raise ValueError('Missing or orphaned Source5 consumption')
    return True

def methods(path):
    if path == '/payroll/multiple-one-off-cases': return 'GET, POST'
    if path == '/payroll/multiple-one-off-cases/preview': return 'POST'
    if path == '/payroll/multiple-one-off-cases/sources' or re.fullmatch('/payroll/multiple-one-off-cases/' + ID + '(?:/history)?', path): return 'GET'
    return None


def dispatch(office, actor, path, method, data):
    allowed = methods(path)
    if allowed is None: return None
    if method not in allowed.split(', '): raise Problem(405, 'Methode für diesen Einmalbezugsfall nicht erlaubt.')
    api = PayrollMultipleCases(office)
    if method == 'POST': result = api.preview(actor, data) if path.endswith('/preview') else api.save(actor, data)
    else:
        _shape(data, ('_query',)); query = data.get('_query', {})
        if path.endswith('/sources'): result = api.sources(actor, query)
        elif path == '/payroll/multiple-one-off-cases': result = api.records(actor, query)
        else: _shape(query, ()); result = api.get(actor, path.split('/')[3], path.endswith('/history'))
    return result, 200, 'application/json'
