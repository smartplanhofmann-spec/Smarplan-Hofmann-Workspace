"""Additive private P4 facts. Historical P2 facts and v4 plans stay unchanged."""
import json
import re
import uuid

from core import Problem, canonical
from business_operations import identifier, text, transaction
from business_personnel_workflow import _integer, _sha, _shape
from business_payroll_facts import (PayrollFacts, EMPLOYEE_FIELDS, employee_view, ref,
    reference, references)
from payroll_entitlements_2026 import ENTITLEMENT_KINDS, ENTITLEMENT_RULE_VERSION
from payroll_entitlement_dispatch import calculate_entitlement_input, build_entitlement_plan, requires_current_sickness_rule
from payroll_holidays_2026 import public_holiday, HOLIDAY_RULES_SHA256

FEATURES = ('payroll_entitlements',)
TABLES = ('business_payroll_entitlement_events','business_payroll_entitlement_requests')
ID = r'[a-f0-9]{32}'
KINDS = ENTITLEMENT_KINDS


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA','BLOB'):
        raise ValueError('Unsupported entitlement storage')
    return [
        '''CREATE TABLE IF NOT EXISTS business_payroll_entitlement_events(
        id TEXT NOT NULL,revision INTEGER NOT NULL CHECK(revision>0),
        employee_id TEXT NOT NULL REFERENCES business_employees(id),kind TEXT NOT NULL CHECK(kind IN ('sickness_history','regular_absence','vacation_reference','unpaid_continuation')),
        effective_from TEXT NOT NULL,effective_to TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('active','void')),
        payload_json TEXT NOT NULL,sources_json TEXT NOT NULL,source_hash TEXT NOT NULL,
        previous_hash TEXT,content_hash TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
        identity_key TEXT,command_hash TEXT NOT NULL,PRIMARY KEY(id,revision),UNIQUE(employee_id,identity_key))''',
        '''CREATE TABLE IF NOT EXISTS business_payroll_entitlement_requests(
        user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,operation TEXT NOT NULL,request_hash TEXT NOT NULL,
        fact_id TEXT NOT NULL,fact_revision INTEGER NOT NULL,fact_content_hash TEXT NOT NULL,created_at TEXT NOT NULL,
        PRIMARY KEY(user_id,request_id),FOREIGN KEY(fact_id,fact_revision) REFERENCES business_payroll_entitlement_events(id,revision))''',
        'CREATE INDEX IF NOT EXISTS business_payroll_entitlement_employee ON business_payroll_entitlement_events(employee_id,kind,id,revision)',
    ]


def protected_tables():return TABLES


def runtime_privileges():return {name:('SELECT','INSERT') for name in TABLES}


def guard_statements(dialect):
    # Same append-only mechanics as P2, distinct tables/triggers and no old DDL changes.
    from business_payroll_facts import guard_statements as fact_guards
    return [statement.replace('business_payroll_fact','business_payroll_entitlement').replace('immutable payroll fact','immutable payroll entitlement') for statement in fact_guards(dialect)]


def _files(value):
    if not isinstance(value,list) or not 1<=len(value)<=100:
        raise Problem(400,'Ein bis hundert geschützte Anspruchsoriginale angeben.')
    ids=[identifier(item,'Personaldatei-ID') for item in value]
    if len(set(ids))!=len(ids):raise Problem(400,'Anspruchsoriginale eindeutig angeben.')
    return sorted(ids)


def _normalize_input(value, key=None):
    if isinstance(value,dict):return {k:_normalize_input(v,k) for k,v in value.items()}
    if isinstance(value,list):
        result=[_normalize_input(v) for v in value]
        if key in ('evidence_refs','history_evidence_refs'):result.sort(key=lambda v:(v['id'],v['revision']))
        if key in ('days','reference_days','vacation_days'):result.sort(key=lambda v:v['date'])
        if key=='episodes':result.sort(key=lambda v:(v['from'],v['id']))
        if key=='exceptions':result.sort(key=lambda v:(v['from'],v['to'],v['kind']))
        return result
    return value


def normalize_details(kind,value,rule_version=None):
    fields=('case_key','employment_terms_ref','work_schedule_refs','preparation_refs','agreement_refs','sickness_history_ref','input','verification_note')
    _shape(value,fields,fields);identifier(value['case_key'])
    calculate_entitlement_input(kind,value['input'],rule_version)
    result=dict(case_key=value['case_key'],employment_terms_ref=ref(value['employment_terms_ref']),
        work_schedule_refs=references(value['work_schedule_refs'],minimum=0),
        preparation_refs=references(value['preparation_refs'],minimum=0),agreement_refs=references(value['agreement_refs']),
        sickness_history_ref=None if value['sickness_history_ref'] is None else ref(value['sickness_history_ref']),
        input=_normalize_input(value['input']),verification_note=text(value['verification_note'],'Anspruchsprüfung',3000,required=True))
    if kind!='regular_absence' and result['sickness_history_ref'] is not None:
        raise Problem(400,'Nur die konkrete Ausfallvergütung darf auf einen Krankheitsverlauf verweisen.')
    return result


def effective(kind,details):
    value=details['input']
    if kind=='sickness_history':return value['complete_from'],value['complete_through']
    if kind=='regular_absence':return min(item['date'] for item in value['days']),max(item['date'] for item in value['days'])
    if kind=='vacation_reference':return value['vacation_from'],value['vacation_to']
    return value['from'],value['to']


def _evidence(value):
    result=[]
    if isinstance(value,dict):
        for key,inner in value.items():
            if key in ('evidence_refs','history_evidence_refs'):result.extend(inner)
            else:result.extend(_evidence(inner))
    elif isinstance(value,list):
        for item in value:result.extend(_evidence(item))
    return result


class PayrollEntitlements:
    def __init__(self,office,*,clock=None):
        self.office,self.db=office,office.db
        self.facts=PayrollFacts(office,clock=clock);self.hr=self.facts.hr

    def _access(self,actor,employee_id,permission='personnel.read'):
        return self.facts._access(actor,employee_id,permission)

    def _gate(self,actor,*,new=True):
        from business_schema import require_capability
        from business_organization import require_active
        require_capability(self.office,'business_payroll_entitlements')
        if new:require_active(self.office,actor,'/payroll','business_payroll')

    def _row(self,object_id,revision=None):
        identifier(object_id)
        if revision is None:
            row=self.db.execute('SELECT * FROM business_payroll_entitlement_events WHERE id=? ORDER BY revision DESC LIMIT 1',(object_id,)).fetchone()
        else:
            _integer(revision,1)
            row=self.db.execute('SELECT * FROM business_payroll_entitlement_events WHERE id=? AND revision=?',(object_id,revision)).fetchone()
        if row is None:raise Problem(404,'Anspruchsfassung nicht verfügbar.')
        return row

    def _event(self,row):
        payload=json.loads(row['payload_json']);sources=json.loads(row['sources_json'])
        envelope={key:row[key] for key in row.keys() if key not in ('payload_json','sources_json','content_hash')}
        envelope.update(payload=payload,sources=sources)
        if _sha(envelope)!=row['content_hash'] or _sha(sources)!=row['source_hash']:
            raise Problem(500,'Integrität der Anspruchshistorie verletzt.')
        value={key:row[key] for key in ('id','revision','employee_id','kind','effective_from','effective_to','status','source_hash','previous_hash','content_hash','created_by','created_at')}
        # The exact accepted body is a private archive anchor, never an API DTO.
        return dict(value,**{key:item for key,item in payload.items() if key!='accepted_command'},sources=sources)

    def _get(self,object_id,revision=None):return self._event(self._row(object_id,revision))

    def _all(self,employee_id,kind=None):
        rows=self.db.execute('SELECT e.* FROM business_payroll_entitlement_events e WHERE e.employee_id=? AND NOT EXISTS '
            '(SELECT 1 FROM business_payroll_entitlement_events n WHERE n.id=e.id AND n.revision>e.revision) ORDER BY e.created_at,e.id',(employee_id,)).fetchall()
        return [self._event(row) for row in rows if kind is None or row['kind']==kind]

    def records(self,actor,query):
        _shape(query,('employee_id','kind'),('employee_id',))
        if query.get('kind') is not None and query['kind'] not in KINDS:raise Problem(400,'Unbekannte Anspruchsart.')
        with transaction(self.office):
            fresh,employee=self._access(actor,query['employee_id'])
            return dict(employee_id=employee['id'],items=self._all(employee['id'],query.get('kind')),**self.facts._capabilities(fresh))

    def get(self,actor,object_id,history=False):
        with transaction(self.office):
            row=self._row(object_id);self._access(actor,row['employee_id'])
            if history:
                return dict(employee_id=row['employee_id'],items=[self._event(item) for item in self.db.execute(
                    'SELECT * FROM business_payroll_entitlement_events WHERE id=? ORDER BY revision',(object_id,))])
            return self._event(row)

    def sources(self,actor,query):
        with transaction(self.office):
            result=self.facts.sources(actor,query)
            result['entitlements']=self._all(result['employee_id'])
            result['file_references']=[dict(id=item['id'],revision=1,content_hash=item['content_hash']) for item in result['files']]
            return result

    def _ref(self,employee_id,value,*,fresh):
        value=ref(value);result=self._get(value['id'],value['revision'])
        if result['employee_id']!=employee_id:raise Problem(404,'Anspruchsquelle gehört nicht zu diesem Mitarbeiter.')
        if reference(result)!=value or result['status']!='active' or fresh and reference(self._get(value['id']))!=value:
            raise Problem(409,'Anspruchsquelle wurde korrigiert oder archiviert.')
        validate_entitlement_sources(self.office,result)
        if fresh and requires_current_sickness_rule(result):
            raise Problem(409,'Dieser historische Stundenlohn-Krankheitsfall benötigt eine neue bestätigte v2-Fassung mit Fristbeginn am Folgetag.')
        if fresh:self.facts._files(employee_id,result['source_file_ids'],fresh=True)
        return result

    def _snapshot(self,employee,kind,details,ids,*,fresh=True):
        employee_id=employee['id'];files=self.facts._files(employee_id,ids,fresh=fresh)
        terms=self.facts._fact_ref(employee_id,details['employment_terms_ref'],'employment_terms',fresh=fresh)
        if (terms['details']['employment_from'],terms['details']['employment_to'])!=(employee['employment_from'],employee['employment_to'] or None):
            raise Problem(409,'Beschäftigungsfakt und Mitarbeiterstamm widersprechen sich.')
        schedules=[self.facts._fact_ref(employee_id,value,'work_schedule',fresh=fresh) for value in details['work_schedule_refs']]
        preparations=[self.facts._hr_ref(employee_id,value,'preparation',fresh=fresh) for value in details['preparation_refs']]
        agreements=[self.facts._hr_ref(employee_id,value,'agreement',fresh=fresh) for value in details['agreement_refs']]
        if any(reference(item) not in terms['details']['agreement_refs'] for item in agreements):
            raise Problem(409,'Anspruchsvereinbarung fehlt im belegten Beschäftigungsfakt.')
        if fresh:
            start,end=effective(kind,details)
            if kind=='vacation_reference':start=min(item['date'] for item in details['input']['reference_days'])
            applicable=sorted([item for item in self.hr._all('agreement',employee_id) if item['effective_from']<=end],key=lambda item:item['effective_from'])
            before=[item for item in applicable if item['effective_from']<=start]
            expected=([before[-1]] if before else [])+[item for item in applicable if item['effective_from']>start]
            if sorted([reference(item) for item in expected],key=lambda item:item['id'])!=details['agreement_refs']:
                raise Problem(409,'Alle tatsächlich einschlägigen Entgeltvereinbarungen ausdrücklich binden.')
        if len({item['details']['month'] for item in schedules})!=len(schedules) or len({item['month'] for item in preparations})!=len(preparations):
            raise Problem(400,'Je Monat genau eine konkrete Plan-/Vorbereitungsfassung binden.')
        if fresh and any(_sha(self.hr._snapshot(employee,item['month']))!=item['source_hash'] for item in preparations):
            raise Problem(409,'Eine Monatsvorbereitung entspricht nicht mehr ihren tatsächlichen Quellen.')
        history=self._ref(employee_id,details['sickness_history_ref'],fresh=fresh) if details['sickness_history_ref'] else None
        if history is not None and history['kind']!='sickness_history':raise Problem(400,'Die Anspruchsquelle ist kein Krankheitsverlauf.')
        if history and history['details']['employment_terms_ref']!=details['employment_terms_ref']:
            raise Problem(409,'Krankheitsverlauf und Vergütung müssen dieselbe Beschäftigungsfassung binden.')
        file_refs={item['id']:dict(id=item['id'],revision=1,content_hash=item['content_hash']) for item in files}
        if any(file_refs.get(item['id'])!=item for item in _evidence(details['input'])):
            raise Problem(409,'Jede Anspruchsentscheidung muss ihre exakte Personaloriginalfassung derselben Person binden.')
        snapshot=dict(schema_version=1,kind=kind,employee=employee_view(employee),details=details,
            employment_terms=terms,agreements=agreements,work_schedules=schedules,preparations=preparations,
            sickness_history=history,source_files=files,
            holiday_calendar_hash=HOLIDAY_RULES_SHA256 if kind=='regular_absence' and details['input']['kind']=='public_holiday' else None)
        _validate_semantics(snapshot)
        return snapshot

    def preview(self,actor,data):
        fields=('employee_id','employee_revision','kind','details','source_file_ids')
        _shape(data,fields,fields);details=normalize_details(data['kind'],data['details']);ids=_files(data['source_file_ids'])
        with transaction(self.office):
            fresh,employee=self._access(actor,data['employee_id'])
            if _integer(data['employee_revision'],1)!=employee['revision']:raise Problem(409,'Mitarbeiterstamm wurde geändert. Neu laden.')
            snapshot=self._snapshot(employee,data['kind'],details,ids);plan=build_entitlement_plan(snapshot)
            return dict(employee_id=employee['id'],kind=data['kind'],source_snapshot=snapshot,source_hash=_sha(snapshot),
                plan=plan,preview_hash=_sha(dict(source_snapshot=snapshot,plan=plan)),can_confirm=True,can_calculate=True,
                **self.facts._capabilities(fresh))

    def save(self,actor,data):
        required=('request_id','employee_id','employee_revision','kind','revision','status','details','source_file_ids','confirmed','preview_hash')
        _shape(data,required+('id','correction_reason'),required)
        identifier(data['request_id']);identifier(data['employee_id'])
        if data.get('id') is not None:identifier(data['id'])
        if data['kind'] not in KINDS or data['confirmed'] is not True or data['status'] not in ('active','void'):
            raise Problem(400,'Anspruchsart, Status und ausdrückliche Bestätigung prüfen.')
        if not isinstance(data['preview_hash'],str) or not re.fullmatch('[a-f0-9]{64}',data['preview_hash']):
            raise Problem(400,'Die konkrete geprüfte Anspruchsvorschau ist erforderlich.')
        _integer(data['employee_revision'],1);_integer(data['revision'])
        reason=text(data.get('correction_reason',''),'Korrekturgrund',2000,required=bool(data.get('id')))
        operation='entitlement.saved:'+data['kind'];fingerprint=_sha([operation,data])
        with transaction(self.office):
            fresh,employee=self._access(actor,data['employee_id'],'personnel.approve');self._gate(fresh,new=False)
            receipt=self.db.execute('SELECT * FROM business_payroll_entitlement_requests WHERE user_id=? AND request_id=?',(fresh['id'],data['request_id'])).fetchone()
            if receipt is not None:
                if receipt['operation']!=operation or receipt['request_hash']!=fingerprint:raise Problem(409,'Vorgangs-ID wurde mit anderem Inhalt verwendet.')
                row=self._row(receipt['fact_id'],receipt['fact_revision']);result=self._event(row)
                if result['employee_id']!=employee['id'] or result['kind']!=data['kind'] or receipt['fact_content_hash']!=result['content_hash'] or row['command_hash']!=fingerprint:
                    raise Problem(500,'Anspruchsquittung widerspricht dem Facharchiv.')
                _validate_command(data,result);validate_entitlement_sources(self.office,result);return result
            try:
                self._gate(fresh)
                if data['employee_revision']!=employee['revision']:raise Problem(409,'Mitarbeiterstamm wurde geändert. Neu laden.')
                previous=self._get(data['id']) if data.get('id') else None
                if previous and (previous['employee_id']!=employee['id'] or previous['kind']!=data['kind']):raise Problem(404,'Korrektur gehört zu einem anderen Anspruch.')
                if data['revision']!=(previous['revision'] if previous else 0):raise Problem(409,'Anspruchsfassung wurde geändert. Neu laden.')
                details=normalize_details(data['kind'],data['details'],previous['plan']['rule_version'] if previous and data['status']=='void' else None)
                ids=_files(data['source_file_ids'])
                identity=data['kind']+':'+details['case_key']
                existing=self.db.execute('SELECT id FROM business_payroll_entitlement_events WHERE employee_id=? AND identity_key=?',(employee['id'],identity)).fetchone()
                if existing and (not previous or previous['id']!=existing['id']):raise Problem(409,'Dieser Anspruchsfall ist bereits vorhanden; seine Korrektur verwenden.')
                if previous and details['case_key']!=previous['details']['case_key']:raise Problem(400,'Die ursprüngliche Anspruchsfallkennung bleibt unverändert.')
                if data['status']=='void':
                    if not previous or previous['status']!='active' or any(value!=previous[key] for key,value in (
                            ('details',details),('source_file_ids',ids),('preview_hash',data['preview_hash']))):
                        raise Problem(400,'Archivieren benötigt die unveränderte aktive Fassung und einen Korrekturgrund.')
                    validate_entitlement_sources(self.office,previous)
                    snapshot,plan,preview_hash=previous['sources'],previous['plan'],previous['preview_hash']
                else:
                    snapshot=self._snapshot(employee,data['kind'],details,ids);plan=build_entitlement_plan(snapshot)
                    preview_hash=_sha(dict(source_snapshot=snapshot,plan=plan))
                    if data['preview_hash']!=preview_hash:raise Problem(409,'Anspruch oder Quellen änderten sich seit der Vorschau.')
                payload=dict(details=details,source_file_ids=ids,plan=plan,preview_hash=preview_hash,correction_reason=reason,
                    accepted_command=json.loads(canonical(data)))
                start,end=effective(data['kind'],details)
                envelope=dict(id=previous['id'] if previous else uuid.uuid4().hex,revision=previous['revision']+1 if previous else 1,
                    employee_id=employee['id'],kind=data['kind'],effective_from=start,effective_to=end,status=data['status'],
                    source_hash=_sha(snapshot),previous_hash=previous['content_hash'] if previous else None,created_by=fresh['id'],
                    created_at=self.hr.now(),identity_key=None if previous else identity,command_hash=fingerprint,payload=payload,sources=snapshot)
                columns=tuple(key for key in envelope if key not in ('payload','sources'))
                self.db.execute('INSERT INTO business_payroll_entitlement_events('+','.join(columns)+',payload_json,sources_json,content_hash) VALUES('+','.join('?' for _ in range(len(columns)+3))+')',
                    tuple(envelope[key] for key in columns)+(canonical(payload),canonical(snapshot),_sha(envelope)))
                result=self._get(envelope['id'])
                self.db.execute('INSERT INTO business_payroll_entitlement_requests(user_id,request_id,operation,request_hash,fact_id,fact_revision,fact_content_hash,created_at) VALUES(?,?,?,?,?,?,?,?)',
                    (fresh['id'],data['request_id'],operation,fingerprint,result['id'],result['revision'],result['content_hash'],envelope['created_at']))
                _validate_command(data,result);validate_entitlement_sources(self.office,result)
                self.office.audit(fresh,'payroll.entitlement.'+data['kind'],result['id']);return result
            except Problem as error:
                if error.status==409:raise Problem(409,error.message,request_resolution='not_accepted') from None
                raise

    def resolve_entitlement_case(self,actor,employee_id,value,fresh=True):
        with transaction(self.office):
            _,employee=self._access(actor,employee_id);result=self._ref(employee_id,value,fresh=fresh)
            if fresh and self._snapshot(employee,result['kind'],result['details'],result['source_file_ids'])!=result['sources']:
                raise Problem(409,'Bestätigter Anspruch entspricht nicht mehr den aktuellen Quellen.')
            return result


def _validate_semantics(snapshot):
    """Bind calculations to actual contracts, plans, hours and prior entitlement."""
    kind=snapshot['kind'];value=snapshot['details']['input'];employee=snapshot['employee'];agreements=snapshot['agreements']
    agreement_by_date=sorted(agreements,key=lambda item:item['effective_from'])
    def agreement(current):
        applicable=[item for item in agreement_by_date if item['effective_from']<=current]
        if not applicable:raise Problem(409,'Entgeltvereinbarung am Anspruchstag fehlt.')
        return applicable[-1]
    if kind=='sickness_history':
        if (value['employment_from'],value['employment_to'])!=(employee['employment_from'],employee['employment_to'] or None):
            raise Problem(409,'Krankheitsvorzeiten widersprechen dem belegten Beschäftigungszeitraum.')
        if any(item['pay_basis']!=value['pay_basis'] for item in agreements):raise Problem(409,'Wechselnde Entgeltbasen benötigen einen eigenen Verhinderungsverlauf.')
    elif kind=='unpaid_continuation':
        if value['from']<employee['employment_from'] or value['employment_to']!=(employee['employment_to'] or None):
            raise Problem(409,'Unterbrechung widerspricht der tatsächlichen Beschäftigung.')
    else:
        schedule={day['date']:day for record in snapshot['work_schedules'] for day in record['details']['days']}
        preparation={record['month']:record for record in snapshot['preparations']}
        dates=value['days'] if kind=='regular_absence' else value['vacation_days']
        for item in dates:
            current=item['date'];expected=schedule.get(current);prepared=preparation.get(current[:7])
            if current<employee['employment_from'] or employee['employment_to'] and current>employee['employment_to']:
                raise Problem(409,'Anspruchstag liegt außerhalb der tatsächlichen Beschäftigung.')
            if expected is None or prepared is None:raise Problem(409,'Konkreter Sollplan und abgeschlossene Monatsvorbereitung am Anspruchstag fehlen.')
            actual_agreements=sorted([item for item in prepared['snapshot']['agreements'] if item['effective_from']<=current],key=lambda item:item['effective_from'])
            if not actual_agreements or agreement(current)!=actual_agreements[-1]:raise Problem(409,'Ausgewählte Entgeltvereinbarung widerspricht der tatsächlichen Monatsquelle.')
            if item['scheduled_regular_seconds']!=expected['scheduled_seconds']:raise Problem(409,'Ausfallzeit widerspricht dem unveränderlichen Sollarbeitsplan.')
            actual=sum(day['net_seconds'] for day in prepared['snapshot']['approved_days'] if day['date']==current)
            absences=[absence for absence in prepared['snapshot']['approved_absences'] if absence['start_date']<=current<=absence['end_date']]
            if kind=='vacation_reference':
                if actual:raise Problem(409,'Urlaubstag enthält tatsächlich geleistete Arbeitszeit; eindeutigen Tagesfall prüfen.')
                if len(absences)!=1 or absences[0]['kind']!='vacation':raise Problem(409,'Der Urlaubstag benötigt genau die freigegebene tatsächliche Urlaubsquelle.')
                if agreement(current)['pay_basis']!='hourly':raise Problem(409,'Die eigene Urlaubsreferenz ergänzt hier Stundenlohn; Monatsentgelt erhält seinen eigenen Gesamtfallzweig.')
            else:
                if actual!=item['worked_regular_seconds']:raise Problem(409,'Bereits geleistete Zeit widerspricht der tatsächlichen freigegebenen Monatsquelle.')
                pay=agreement(current)
                if pay['pay_basis']!='hourly' or pay['amount_minor']!=value['hourly_rate_minor']:raise Problem(409,'Regelmäßiger Stundenlohn widerspricht der gebundenen Entgeltvereinbarung.')
                history=snapshot['sickness_history']
                if value['kind']=='public_holiday':
                    if not public_holiday(current,expected['federal_state']):raise Problem(409,'Der Anspruchstag ist am belegten Arbeitsort kein gesetzlicher Feiertag.')
                    if item['entitled'] is not True:raise Problem(409,'Der gesetzliche Feiertag ist vom konkreten Ausfallgrund und Ausschluss zu unterscheiden.')
                    if history is not None:raise Problem(400,'Eigenständige Feiertagsvergütung darf keinen ungeprüften Krankheitsfall übergehen.')
                    if absences:raise Problem(409,'Feiertag mit zusätzlicher freigegebener Abwesenheit benötigt eine eindeutige kombinierte Anspruchsentscheidung.')
                else:
                    if history is None:raise Problem(409,'Krankheitsvergütung benötigt einen konkret berechneten Vorzeiten-/Anspruchsnachweis.')
                    if len(absences)!=1 or absences[0]['kind']!='sick':raise Problem(409,'Krankheitsvergütung benötigt genau die freigegebene tatsächliche AU-Quelle.')
                    rows=history['plan']['episodes']
                    entitled=any(row['entitlement_from'] is not None and row['entitlement_from']<=current<=row['entitlement_to'] for row in rows)
                    if value['kind']=='first_sickness_day_regular_wage':
                        if actual<=0:raise Problem(409,'Begonnener Arbeitstag benötigt tatsächlich geleistete freigegebene Arbeitszeit.')
                        entitled=any(row['first_day_remaining_regular_wage']==current for row in rows)
                    if item['entitled']!=entitled:raise Problem(409,'Ausfallvergütung widerspricht dem berechneten Krankheitsanspruch.')
        if kind=='vacation_reference':
            for item in value['reference_days']:
                expected=schedule.get(item['date'])
                if expected is None or bool(expected['scheduled_seconds'])!=item['contractual_workday']:
                    raise Problem(409,'Die Urlaubsreferenz benötigt die konkret belegten Arbeitstage aller 13 Wochen.')


def _validate_command(data,value):
    required=('request_id','employee_id','employee_revision','kind','revision','status','details','source_file_ids','confirmed','preview_hash')
    _shape(data,required+('id','correction_reason'),required)
    identifier(data['request_id']);identifier(data['employee_id'])
    if data.get('id') is not None:identifier(data['id'])
    _integer(data['employee_revision'],1);_integer(data['revision'])
    if value['status']=='active' and data['employee_revision']!=value['sources']['employee']['revision']:
        raise Problem(500,'Angenommene Mitarbeiterrevision widerspricht der Anspruchsquelle.')
    if (data['confirmed'] is not True or data['employee_id']!=value['employee_id'] or data['kind']!=value['kind']
            or data['status']!=value['status'] or normalize_details(data['kind'],data['details'],value['plan']['rule_version'])!=value['details']
            or _files(data['source_file_ids'])!=value['source_file_ids'] or data['preview_hash']!=value['preview_hash']
            or text(data.get('correction_reason',''),'Korrekturgrund',2000)!=value['correction_reason']
            or data['revision']+1!=value['revision'] or (data.get('id') if data['revision'] else value['id'])!=value['id']):
        raise Problem(500,'Angenommener Originalauftrag widerspricht der Anspruchsfassung.')


def validate_entitlement_sources(office,value):
    api=PayrollEntitlements(office)
    try:
        row=api._row(value['id'],value['revision'])
        if api._event(row)!=value:raise ValueError('Changed archived entitlement projection')
        command=json.loads(row['payload_json'])['accepted_command']
        _validate_command(command,value)
        operation='entitlement.saved:'+value['kind']
        if _sha([operation,command])!=row['command_hash']:raise ValueError('Changed accepted entitlement command')
        receipt=office.db.execute('SELECT * FROM business_payroll_entitlement_requests WHERE user_id=? AND request_id=?',
            (row['created_by'],command['request_id'])).fetchone()
        if (receipt is None or receipt['operation']!=operation or receipt['request_hash']!=row['command_hash']
                or receipt['fact_id']!=row['id'] or receipt['fact_revision']!=row['revision']
                or receipt['fact_content_hash']!=row['content_hash'] or receipt['created_at']!=row['created_at']):
            raise ValueError('Changed entitlement acceptance receipt')
        details=normalize_details(value['kind'],value['details'],value['plan']['rule_version']);sources=value['sources'];employee=sources['employee']
        if details!=value['details'] or _files(value['source_file_ids'])!=value['source_file_ids'] or effective(value['kind'],details)!=(value['effective_from'],value['effective_to']):
            raise ValueError('Changed canonical entitlement')
        _shape(employee,EMPLOYEE_FIELDS,EMPLOYEE_FIELDS)
        if employee['id']!=value['employee_id']:raise ValueError('Foreign entitlement employee')
        _integer(employee['revision'],1)
        current=office.db.execute('SELECT user_id FROM business_employees WHERE id=?',(employee['id'],)).fetchone()
        if current is None or current['user_id']!=employee['user_id']:raise ValueError('Changed immutable employee binding')
        if not office.db.execute('SELECT 1 FROM business_employee_terms WHERE employee_id=? AND revision=?',(employee['id'],employee['revision'])).fetchone():raise ValueError('Missing employee revision')
        accepted=[]
        for row in office.db.execute("SELECT result_json FROM business_planning_requests WHERE operation='employee' AND result_json LIKE ?",('%"id":"'+employee['id']+'"%',)):
            original=json.loads(row['result_json'])
            if original.get('id')==employee['id'] and original.get('revision')==employee['revision']:accepted.append(original)
        if len(accepted)!=1 or any(accepted[0].get(key)!=employee[key] for key in EMPLOYEE_FIELDS if key in accepted[0]):raise ValueError('Changed accepted employee original')
        expected=api._snapshot(employee,value['kind'],details,value['source_file_ids'],fresh=False)
        if expected!=sources or _sha(sources)!=value['source_hash']:raise ValueError('Changed entitlement sources')
        plan=build_entitlement_plan(sources,value['plan']['rule_version'])
        if value['plan']!=plan or value['preview_hash']!=_sha(dict(source_snapshot=sources,plan=plan)):raise ValueError('Changed entitlement plan')
        return True
    except (Problem,KeyError,TypeError,ValueError,RecursionError) as error:
        raise ValueError('Invalid historical entitlement sources') from error


def validate_integrity(office):
    from business_schema import _tables
    present=set(TABLES).intersection(_tables(office))
    if not present:return True
    if present!=set(TABLES):raise ValueError('Incomplete entitlement schema')
    api=PayrollEntitlements(office);previous={};receipts=set()
    try:
        for row in office.db.execute('SELECT * FROM business_payroll_entitlement_events ORDER BY id,revision'):
            value=api._event(row);prior=previous.get(value['id'])
            if value['revision']!=(prior['revision']+1 if prior else 1) or value['previous_hash']!=(prior['content_hash'] if prior else None):raise ValueError('Broken entitlement history')
            if prior and any(value[key]!=prior[key] for key in ('employee_id','kind')):raise ValueError('Changed entitlement identity')
            if prior and value['details']['case_key']!=prior['details']['case_key']:raise ValueError('Changed case key')
            if row['identity_key']!=(None if prior else value['kind']+':'+value['details']['case_key']):raise ValueError('Changed first case identity')
            if not re.fullmatch('[a-f0-9]{64}',row['command_hash']) or prior and not value['correction_reason'] or not prior and value['status']!='active':raise ValueError('Invalid acceptance')
            if value['status']=='void' and (not prior or prior['status']!='active' or any(value[key]!=prior[key] for key in ('details','source_file_ids','sources','source_hash','plan','preview_hash'))):raise ValueError('Changed void entitlement')
            validate_entitlement_sources(office,value);previous[value['id']]=value
        for receipt in office.db.execute('SELECT * FROM business_payroll_entitlement_requests'):
            identifier(receipt['request_id']);original=api._row(receipt['fact_id'],receipt['fact_revision'])
            if (receipt['operation']!='entitlement.saved:'+original['kind'] or receipt['request_hash']!=original['command_hash']
                    or receipt['fact_content_hash']!=original['content_hash'] or receipt['user_id']!=original['created_by']
                    or receipt['created_at']!=original['created_at'] or (receipt['fact_id'],receipt['fact_revision']) in receipts):raise ValueError('Changed entitlement receipt')
            receipts.add((receipt['fact_id'],receipt['fact_revision']))
        if len(receipts)!=office.db.execute('SELECT COUNT(*) FROM business_payroll_entitlement_events').fetchone()[0]:raise ValueError('Missing entitlement receipt')
    except (Problem,KeyError,TypeError,ValueError,json.JSONDecodeError) as error:
        raise ValueError('Invalid entitlement archive') from error
    return True


def methods(path):
    if path=='/payroll/entitlements':return 'GET, POST'
    if path=='/payroll/entitlements/sources' or re.fullmatch('/payroll/entitlements/'+ID+'(?:/history)?',path):return 'GET'
    if path=='/payroll/entitlements/preview':return 'POST'
    return None


def dispatch(office,actor,path,method,data):
    allowed=methods(path)
    if allowed is None:return None
    if method not in allowed.split(', '):raise Problem(405,'Methode für diese Anspruchsroute nicht zulässig.')
    api=PayrollEntitlements(office)
    if method=='POST':result=api.preview(actor,data) if path.endswith('/preview') else api.save(actor,data)
    else:
        _shape(data,('_query',));query=data.get('_query',{})
        if path.endswith('/sources'):result=api.sources(actor,query)
        elif path=='/payroll/entitlements':result=api.records(actor,query)
        else:
            _shape(query,());result=api.get(actor,path.split('/')[3],path.endswith('/history'))
    return result,200,'application/json'
