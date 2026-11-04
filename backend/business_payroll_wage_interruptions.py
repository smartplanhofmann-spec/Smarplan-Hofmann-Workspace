"""Private annual U assessments bound to actual payroll, P4 and daily originals."""
import calendar
import json
import re
import uuid

from core import Problem,canonical
from business_operations import identifier,text,transaction
from business_personnel_workflow import _integer,_sha,_shape
from business_payroll_facts import PayrollFacts,ref,references,reference,file_ids,employee_view,EMPLOYEE_FIELDS
from payroll_de_2026 import day
from payroll_wage_interruptions_2026 import RULE_VERSION,EXCLUDED_PAYMENTS,calculate_wage_interruptions,_dates

FEATURES=('payroll_wage_interruptions',)
TABLES=('business_payroll_wage_interruption_events','business_payroll_wage_interruption_requests')
KIND='wage_interruption_assessment'
ID=r'[a-f0-9]{32}'


def schema_statements(binary_type='BYTEA'):
    from business_payroll_facts import schema_statements as original
    return [value.replace('business_payroll_fact','business_payroll_wage_interruption')
        .replace("'employment_terms','work_schedule','period_case'","'wage_interruption_assessment'") for value in original(binary_type)]


def guard_statements(dialect):
    from business_payroll_facts import guard_statements as original
    return [value.replace('business_payroll_fact','business_payroll_wage_interruption')
        .replace('immutable payroll fact','immutable payroll wage interruption') for value in original(dialect)]


def protected_tables():return TABLES
def runtime_privileges():return {table:('SELECT','INSERT') for table in TABLES}


def normalize_details(value):
    fields=('year','assessment_through','employment_terms_refs','run_refs','work_schedule_refs','entitlement_case_refs',
        'excluded_payments_reviewed','exception_review_file_refs','excluded_payments','verification_note')
    _shape(value,fields,fields)
    if type(value['year']) is not int or value['year']!=2026 or day(value['assessment_through']).year!=2026:
        raise Problem(400,'Prüfjahr und tatsächlichen Prüfungstag 2026 angeben.')
    if value['excluded_payments_reviewed'] is not True:raise Problem(400,'Sämtliche gesetzlichen §41Abs1Satz4-Leistungen ausdrücklich anhand der Originale prüfen.')
    payments=value['excluded_payments']
    if not isinstance(payments,list) or len(payments)>200:raise Problem(400,'Begrenzte tatsächliche Leistungszeiträume angeben.')
    normalized=[]
    for payment in payments:
        _shape(payment,('from','to','kind','evidence_refs'),('from','to','kind','evidence_refs'))
        if payment['kind'] not in EXCLUDED_PAYMENTS or not day('2026-01-01')<=day(payment['from'])<=day(payment['to'])<=day(value['assessment_through']):
            raise Problem(400,'Gesetzliche Leistungsart mit tatsächlichem Zeitraum innerhalb der Prüfung angeben.')
        normalized.append(dict(payment,evidence_refs=references(payment['evidence_refs'])))
    normalized.sort(key=lambda item:(item['from'],item['to'],item['kind']))
    for left,right in zip(normalized,normalized[1:]):
        if left['to']>=right['from']:raise Problem(400,'Gesetzliche Leistungszeiträume dürfen sich nicht unaufgelöst überlappen.')
    return dict(year=2026,assessment_through=value['assessment_through'],employment_terms_refs=references(value['employment_terms_refs']),
        run_refs=references(value['run_refs'],minimum=0,maximum=12),work_schedule_refs=references(value['work_schedule_refs'],minimum=0,maximum=12),
        entitlement_case_refs=references(value['entitlement_case_refs'],minimum=0,maximum=200),excluded_payments_reviewed=True,
        exception_review_file_refs=references(value['exception_review_file_refs']),excluded_payments=normalized,
        verification_note=text(value['verification_note'],'Beurteilung der gesetzlichen Unterbrechungsaufzeichnung',3000,required=True))


def build_plan(snapshot):
    details=snapshot['details'];through=details['assessment_through'];year='2026';blockers=[]
    def block(code,message):
        if not any(value['code']==code for value in blockers):blockers.append(dict(code=code,message=message))
    terms=sorted(snapshot['employment_terms'],key=lambda item:item['details']['employment_from'])
    intervals=[dict(**{'from':item['details']['employment_from'],'to':item['details']['employment_to']},evidence_refs=[reference(item)]) for item in terms]
    runs={value['source']['month']:value for value in snapshot['runs']};schedules={value['details']['month']:value for value in snapshot['work_schedules']}
    if len(runs)!=len(snapshot['runs']) or len(schedules)!=len(snapshot['work_schedules']):raise Problem(400,'Jeder Monat benötigt genau eine tatsächliche Lauf-/Arbeitsplanfassung.')
    mini=False;rows=[];unpaid=set()
    for value in snapshot['runs']:
        if value['source'].get('source_schema_version')!=3:
            block('source3_run_required','Dieser U-Prüfzweig benötigt die tatsächliche vollständige Source3-Anspruchsaufteilung.');continue
        calculation=value['calculation'];unpaid.update(calculation['period_details']['unpaid_dates'])
        mini|=any(p['profile']['employment_kind']=='minijob' for p in value['source']['calculation_case']['sources']['profiles'])
        if calculation['period_details']['unpaid_dates'] and calculation['period_details']['travel']['benefit_in_kind_non_cash_minor']:
            block('noncash_wage_claim_requires_assessment','Sachbezug und unbezahlter Zeitraum benötigen eine konkrete tägliche Anspruchsbeurteilung.')
    for term in terms:
        details_term=term['details']
        start=max(day(year+'-01-01'),day(details_term['employment_from']))
        end=min(day(through),day(details_term['employment_to']) if details_term['employment_to'] else day(through))
        for current in _dates(start,end):
            run=runs.get(current[:7]);schedule=schedules.get(current[:7]);scheduled=None
            if schedule is not None:scheduled=next((v for v in schedule['details']['days'] if v['date']==current),None)
            if scheduled is None:block('work_schedule_missing','Die geprüfte Beschäftigung benötigt für jeden Monat den vollständigen kanonischen Tagesarbeitsplan.')
            covered=(run is not None and run['source'].get('source_schema_version')==3 and any(v['start']<=current<=v['end'] for v in run['calculation']['period_details']['employment_intervals']))
            if not covered:block('payroll_period_missing','Die geprüfte Beschäftigung ist nicht vollständig durch tatsächliche Source3-Laufrevisionen abgedeckt.')
            exception=next((value for value in details['excluded_payments'] if value['from']<=current<=value['to']),None)
            rows.append(dict(date=current,contractual_workday=bool(scheduled and scheduled['scheduled_seconds']),
                wage_claim=('none' if current in unpaid else 'preserved') if covered else 'partial_unknown',
                section41_1_4_payment_kind=exception['kind'] if exception else 'none',
                claim_evidence_refs=[reference(run)] if run else [reference(term)],
                schedule_evidence_refs=[reference(schedule)] if schedule else [reference(term)],
                exception_evidence_refs=exception['evidence_refs'] if exception else details['exception_review_file_refs']))
    # A January-only SV continuation proof cannot erase an earlier loss of
    # wage entitlement in its bound sickness history. Inspect the original
    # entitlement result at the year boundary, within the same employment.
    prior_day='2025-12-31';first_day=year+'-01-01'
    continuing_terms=[reference(value) for value in terms if value['details']['employment_from']<=prior_day
        and (value['details']['employment_to'] is None or value['details']['employment_to']>=first_day)]
    def prior_loss(value):
        if value['details']['employment_terms_ref'] not in continuing_terms:return False
        plan=value['plan']
        if value['kind']=='unpaid_continuation':
            return any(part['from']<=prior_day<=part['to'] for part in plan['intervals'])
        if value['kind']!='sickness_history':return False
        if 'phases' in plan:
            return any(part['from_date']<=prior_day<=part['to_date'] and not part['entitled']
                and not part['first_day_remaining_regular_wage'] for part in plan['phases'])
        return any(part['from_date']<=prior_day<=part['to_date']
            and not (part['entitlement_from'] is not None and part['entitlement_from']<=prior_day<=part['entitlement_to'])
            and part['first_day_remaining_regular_wage']!=prior_day for part in plan['episodes'])
    carry=first_day in unpaid and any(prior_loss(value) for value in snapshot['entitlements'])
    source=dict(year=2026,assessment_through=through,employment_intervals=intervals,days=rows,carry_in_loss=carry,
        tax_scope='flat_minijob' if mini else 'individual')
    result=calculate_wage_interruptions(source)
    all_blockers=sorted(result['blockers']+blockers,key=lambda value:value['code'])
    result={key:value for key,value in result.items() if key!='plan_hash'}
    result.update(source_snapshot_hash=_sha(snapshot),input=source,blockers=all_blockers,can_determine=not all_blockers,
        number_u=None if all_blockers else result['number_u'])
    return dict(result,plan_hash=_sha(result))


class PayrollWageInterruptions(PayrollFacts):
    def _gate(self,actor,*,new=True):
        from business_schema import require_capability
        from business_organization import require_active
        require_capability(self.office,'business_payroll_wage_interruptions')
        if new:require_active(self.office,actor,'/payroll','business_payroll')

    def _row(self,object_id,revision=None):
        identifier(object_id)
        if revision is None:row=self.db.execute('SELECT * FROM '+TABLES[0]+' WHERE id=? ORDER BY revision DESC LIMIT 1',(object_id,)).fetchone()
        else:
            _integer(revision,1);row=self.db.execute('SELECT * FROM '+TABLES[0]+' WHERE id=? AND revision=?',(object_id,revision)).fetchone()
        if row is None:raise Problem(404,'U-Merkmalsnachweis nicht verfügbar.')
        return row

    def _event(self,row):
        result=super()._event(row);result.pop('accepted_command');return result

    def _all(self,employee_id,kind=None):
        return [self._event(row) for row in self.db.execute('SELECT e.* FROM '+TABLES[0]+' e WHERE e.employee_id=? AND NOT EXISTS '
            '(SELECT 1 FROM '+TABLES[0]+' n WHERE n.id=e.id AND n.revision>e.revision) ORDER BY e.created_at,e.id',(employee_id,))]

    def _snapshot(self,employee,details,ids,*,fresh=True):
        from business_payroll import Payroll
        from business_payroll_entitlements import PayrollEntitlements,validate_entitlement_sources
        api=PayrollFacts(self.office,clock=self.hr.clock);payroll=Payroll(self.office,clock=self.hr.clock);claims_api=PayrollEntitlements(self.office,clock=self.hr.clock)
        employee_id=employee['id'];through=details['assessment_through']
        if fresh and through>self.hr.now()[:10]:raise Problem(400,'U-Aufzeichnung darf keine zukünftige tatsächliche Prüfung behaupten.')
        terms=[api._fact_ref(employee_id,value,'employment_terms',fresh=fresh) for value in details['employment_terms_refs']]
        schedules=[api._fact_ref(employee_id,value,'work_schedule',fresh=fresh) for value in details['work_schedule_refs']]
        runs=[]
        for value in details['run_refs']:
            run=payroll._event(payroll._row(value['id'],'run',value['revision']))
            if run['employee_id']!=employee_id or reference(run)!=value or not '2026-01'<=run['source']['month']<=through[:7]:raise Problem(409,'Tatsächlicher Lohnlauf gehört nicht zur geprüften Person und zum Zeitraum.')
            if fresh and reference(payroll._event(payroll._row(value['id'],'run')))!=value:raise Problem(409,'Aktuelle tatsächliche Laufrevision für den neuen U-Nachweis binden.')
            if run['source'].get('source_schema_version')==3:payroll._verify_calculation_record(run)
            else:
                from business_payroll import _calculate_source
                if _calculate_source(run['source'],rule_version=run['calculation']['rule_version'])!=run['calculation']:raise Problem(500,'Lohnquelle lässt sich nicht historisch reproduzieren.')
            runs.append(run)
        claims=[claims_api._ref(employee_id,value,fresh=fresh) for value in details['entitlement_case_refs']]
        for value in claims:validate_entitlement_sources(self.office,value)
        if fresh:
            expected_terms=[reference(v) for v in api._all(employee_id,'employment_terms') if v['status']=='active' and v['effective_from']<=through and (v['effective_to'] is None or v['effective_to']>='2026-01-01')]
            expected_runs=[reference(v) for v in payroll._all('run',employee_id) if '2026-01'<=v['source']['month']<=through[:7]]
            expected_claims=[reference(v) for v in claims_api._all(employee_id) if v['status']=='active' and v['effective_from']<=through and v['effective_to']>='2026-01-01']
            for expected,key in ((expected_terms,'employment_terms_refs'),(expected_runs,'run_refs'),(expected_claims,'entitlement_case_refs')):
                if sorted(expected,key=lambda v:v['id'])!=details[key]:raise Problem(409,'Alle tatsächlichen aktuellen Beschäftigungs-, Lauf- und Anspruchsquellen des Prüfzeitraums müssen vollständig gebunden sein.')
            for claim in claims:
                for run in runs:
                    month=run['source']['month'];last=calendar.monthrange(2026,int(month[-2:]))[1]
                    if claim['effective_from']<=min(through,month+'-'+str(last)) and claim['effective_to']>=month+'-01':
                        bound=run['source'].get('calculation_case',{}).get('details',{}).get('entitlement_case_refs',[])
                        if reference(claim) not in bound:raise Problem(409,'Ein aktueller einschlägiger Anspruch ist noch nicht in der tatsächlichen Lohnrevision berücksichtigt.')
        refs=details['exception_review_file_refs']+[value for payment in details['excluded_payments'] for value in payment['evidence_refs']]
        files=self._files(employee_id,ids,fresh=fresh);by_id={value['id']:value for value in files}
        for value in refs:
            if value['id'] not in by_id or value['revision']!=1 or by_id[value['id']]['content_hash']!=value['content_hash']:
                raise Problem(409,'Jede Leistungsprüfung benötigt das unveränderte tatsächlich gebundene Personaloriginal.')
        return dict(schema_version=1,rule_version=RULE_VERSION,employee=employee_view(employee),details=details,
            employment_terms=terms,runs=runs,work_schedules=schedules,entitlements=claims,source_files=files)

    def sources(self,actor,query):
        _shape(query,('employee_id','year'),('employee_id','year'))
        if query['year']!='2026':raise Problem(400,'Prüfjahr2026 erforderlich.')
        with transaction(self.office):
            fresh,employee=self._access(actor,query['employee_id'])
            from business_payroll import Payroll
            from business_payroll_entitlements import PayrollEntitlements
            source=PayrollFacts(self.office).sources(fresh,dict(employee_id=employee['id']))
            source.update(year=2026,runs=Payroll(self.office).records(fresh,'run',dict(employee_id=employee['id']))['items'],
                entitlements=PayrollEntitlements(self.office)._all(employee['id']),assessments=self._all(employee['id']))
            for value in source['assessments']:validate_sources(self.office,value)
            source['file_references']=[dict(id=value['id'],revision=1,content_hash=value['content_hash']) for value in source['files']]
            return source

    def records(self,actor,query):
        _shape(query,('employee_id','year'),('employee_id',))
        if query.get('year','2026')!='2026':raise Problem(400,'Prüfjahr2026 erforderlich.')
        with transaction(self.office):
            fresh,employee=self._access(actor,query['employee_id'])
            items=self._all(employee['id'])
            for value in items:validate_sources(self.office,value)
            return dict(employee_id=employee['id'],items=items,**self._capabilities(fresh))

    def get(self,actor,object_id,history=False):
        with transaction(self.office):
            row=self._row(object_id);self._access(actor,row['employee_id'])
            items=[self._event(value) for value in self.db.execute('SELECT * FROM '+TABLES[0]+' WHERE id=? ORDER BY revision',(object_id,))] if history else [self._event(row)]
            for value in items:validate_sources(self.office,value)
            return dict(items=items) if history else items[0]

    @staticmethod
    def _versions(data):
        if data['kind']!=KIND or data['rule_version']!=RULE_VERSION or type(data['source_contract_version']) is not int or data['source_contract_version']!=1:
            raise Problem(400,'U-Nachweisart und explizite Regel-/Quellenversion angeben.')
        _integer(data['employee_revision'],1)

    def preview(self,actor,data):
        fields=('employee_id','employee_revision','kind','rule_version','source_contract_version','details','source_file_ids')
        _shape(data,fields,fields);self._versions(data);details=normalize_details(data['details']);ids=file_ids(data['source_file_ids'])
        with transaction(self.office):
            fresh,employee=self._access(actor,data['employee_id'])
            if employee['revision']!=data['employee_revision']:raise Problem(409,'Aktuelle tatsächliche Mitarbeiterrevision angeben.')
            sources=self._snapshot(employee,details,ids);plan=build_plan(sources)
            return dict(employee_id=employee['id'],kind=KIND,source_snapshot=sources,source_hash=_sha(sources),plan=plan,
                preview_hash=_sha(dict(source_snapshot=sources,plan=plan)),can_confirm=True,can_determine=plan['can_determine'],**self._capabilities(fresh))

    def save(self,actor,data):
        required=('request_id','employee_id','employee_revision','kind','rule_version','source_contract_version','revision','status','details','source_file_ids','confirmed','preview_hash')
        _shape(data,required+('id','correction_reason'),required);identifier(data['request_id']);self._versions(data);_integer(data['revision'])
        if data.get('id') is not None:identifier(data['id'])
        if data['confirmed'] is not True or data['status'] not in ('active','void') or not re.fullmatch('[a-f0-9]{64}',str(data['preview_hash'])):
            raise Problem(400,'U-Vorschau und ausdrückliche Bestätigung erforderlich.')
        details=normalize_details(data['details']);ids=file_ids(data['source_file_ids']);reason=text(data.get('correction_reason',''),'Korrekturgrund',2000,required=bool(data.get('id')))
        operation='wage_interruption.saved';fingerprint=_sha([operation,data])
        with transaction(self.office):
            fresh,employee=self._access(actor,data['employee_id'],'personnel.approve');self._gate(fresh,new=False)
            receipt=self.db.execute('SELECT * FROM '+TABLES[1]+' WHERE user_id=? AND request_id=?',(fresh['id'],data['request_id'])).fetchone()
            if receipt is not None:
                if receipt['operation']!=operation or receipt['request_hash']!=fingerprint:raise Problem(409,'Vorgangs-ID gehört zu anderem ursprünglichen Auftrag.')
                row=self._row(receipt['fact_id'],receipt['fact_revision']);value=self._event(row)
                if json.loads(row['payload_json'])['accepted_command']!=data or value['content_hash']!=receipt['fact_content_hash']:raise Problem(500,'Annahmequittung widerspricht dem Originalauftrag.')
                validate_sources(self.office,value);return value
            try:
                self._gate(fresh)
                if employee['revision']!=data['employee_revision']:raise Problem(409,'Mitarbeiter wurde seit der Vorschau geändert.')
                previous=self._get(data['id']) if data.get('id') else None
                if previous and previous['employee_id']!=employee['id']:raise Problem(404,'U-Korrektur gehört zu anderer Person.')
                if data['revision']!=(previous['revision'] if previous else 0):raise Problem(409,'U-Nachweis wurde inzwischen geändert.')
                existing=self.db.execute('SELECT id FROM '+TABLES[0]+' WHERE employee_id=? AND identity_key=?',(employee['id'],'year:2026')).fetchone()
                if existing and (previous is None or existing['id']!=previous['id']):raise Problem(409,'Für dieses Jahr besteht bereits ein U-Nachweis; Korrektur verwenden.')
                if data['status']=='void':
                    if previous is None or previous['status']!='active' or details!=previous['details'] or ids!=previous['source_file_ids'] or data['preview_hash']!=previous['preview_hash']:
                        raise Problem(400,'Aufheben benötigt die unveränderte aktive Fassung.')
                    validate_sources(self.office,previous);snapshot,plan=previous['sources'],previous['plan']
                else:
                    snapshot=self._snapshot(employee,details,ids);plan=build_plan(snapshot)
                    if _sha(dict(source_snapshot=snapshot,plan=plan))!=data['preview_hash']:raise Problem(409,'U-Quellen wurden seit Vorschau geändert.')
                payload=dict(rule_version=RULE_VERSION,source_contract_version=1,details=details,source_file_ids=ids,plan=plan,
                    preview_hash=data['preview_hash'],correction_reason=reason,accepted_command=json.loads(canonical(data)))
                envelope=dict(id=previous['id'] if previous else uuid.uuid4().hex,revision=previous['revision']+1 if previous else 1,
                    employee_id=employee['id'],kind=KIND,effective_from='2026-01-01',effective_to=details['assessment_through'],status=data['status'],
                    source_hash=_sha(snapshot),previous_hash=previous['content_hash'] if previous else None,created_by=fresh['id'],created_at=self.hr.now(),
                    identity_key=None if previous else 'year:2026',command_hash=fingerprint,payload=payload,sources=snapshot)
                columns=tuple(key for key in envelope if key not in ('payload','sources'))
                self.db.execute('INSERT INTO '+TABLES[0]+'('+','.join(columns)+',payload_json,sources_json,content_hash) VALUES('+','.join('?' for _ in range(len(columns)+3))+')',
                    tuple(envelope[key] for key in columns)+(canonical(payload),canonical(snapshot),_sha(envelope)))
                value=self._get(envelope['id'])
                self.db.execute('INSERT INTO '+TABLES[1]+'(user_id,request_id,operation,request_hash,fact_id,fact_revision,fact_content_hash,created_at) VALUES(?,?,?,?,?,?,?,?)',
                    (fresh['id'],data['request_id'],operation,fingerprint,value['id'],value['revision'],value['content_hash'],envelope['created_at']))
                validate_sources(self.office,value);self.office.audit(fresh,'payroll.wage_interruption',value['id']);return value
            except Problem as error:
                if error.status==409:raise Problem(409,error.message,request_resolution='not_accepted') from None
                raise


def validate_sources(office,value):
    api=PayrollWageInterruptions(office)
    try:
        row=api._row(value['id'],value['revision']);payload=json.loads(row['payload_json']);command=payload['accepted_command'];api._versions(command)
        details=normalize_details(value['details']);fingerprint=_sha(['wage_interruption.saved',command])
        receipt=office.db.execute('SELECT * FROM '+TABLES[1]+' WHERE user_id=? AND request_id=?',(value['created_by'],command['request_id'])).fetchone()
        if (api._event(row)!=value or value['rule_version']!=RULE_VERSION or type(value['source_contract_version']) is not int or value['source_contract_version']!=1
                or value['kind']!=KIND or value['effective_from']!='2026-01-01' or value['effective_to']!=details['assessment_through']
                or row['identity_key']!=('year:2026' if value['revision']==1 else None)
                or row['command_hash']!=fingerprint or receipt is None or receipt['operation']!='wage_interruption.saved'
                or receipt['request_hash']!=fingerprint or receipt['fact_id']!=value['id'] or receipt['fact_revision']!=value['revision']
                or receipt['fact_content_hash']!=value['content_hash'] or receipt['created_at']!=value['created_at']
                or normalize_details(command['details'])!=details or command['employee_id']!=value['employee_id']
                or command['revision']+1!=value['revision'] or command.get('id',value['id'])!=value['id'] or command['status']!=value['status']
                or command['preview_hash']!=value['preview_hash'] or command['confirmed'] is not True
                or file_ids(command['source_file_ids'])!=value['source_file_ids'] or details!=value['details']
                or text(command.get('correction_reason',''),'Korrekturgrund',2000)!=value['correction_reason']):raise ValueError('Changed U acceptance original')
        employee=value['sources']['employee'];_shape(employee,EMPLOYEE_FIELDS,EMPLOYEE_FIELDS)
        if employee['id']!=value['employee_id'] or value['status']=='active' and employee['revision']!=command['employee_revision']:raise ValueError('Changed U employee original')
        current=office.db.execute('SELECT user_id FROM business_employees WHERE id=?',(employee['id'],)).fetchone()
        if current is None or current['user_id']!=employee['user_id']:raise ValueError('Changed immutable U employee binding')
        if not office.db.execute('SELECT 1 FROM business_employee_terms WHERE employee_id=? AND revision=?',(employee['id'],employee['revision'])).fetchone():
            raise ValueError('Missing original U employee revision')
        accepted=[]
        for item in office.db.execute("SELECT result_json FROM business_planning_requests WHERE operation='employee' AND result_json LIKE ?",('%"id":"'+employee['id']+'"%',)):
            original=json.loads(item['result_json'])
            if original.get('id')==employee['id'] and original.get('revision')==employee['revision']:accepted.append(original)
        if len(accepted)!=1 or any(accepted[0].get(key)!=employee[key] for key in EMPLOYEE_FIELDS if key in accepted[0]):raise ValueError('Changed accepted employee revision')
        expected=api._snapshot(employee,details,value['source_file_ids'],fresh=False);plan=build_plan(expected)
        if expected!=value['sources'] or plan!=value['plan'] or value['preview_hash']!=_sha(dict(source_snapshot=expected,plan=plan)):
            raise ValueError('Changed U historical sources or arithmetic')
        return True
    except (Problem,KeyError,TypeError,ValueError,RecursionError) as error:raise ValueError('Invalid wage interruption archive') from error


def validate_integrity(office):
    from business_schema import _tables
    present=set(TABLES)&_tables(office)
    if not present:return True
    if present!=set(TABLES):raise ValueError('Incomplete wage interruption schema')
    api=PayrollWageInterruptions(office);prior={};accepted=set()
    for row in office.db.execute('SELECT * FROM '+TABLES[0]+' ORDER BY id,revision'):
        value=api._event(row);previous=prior.get(value['id'])
        if (value['revision']!=(previous['revision']+1 if previous else 1) or value['previous_hash']!=(previous['content_hash'] if previous else None)
                or row['identity_key']!=(None if previous else 'year:2026') or value['effective_from']!='2026-01-01'
                or value['effective_to']!=value['details']['assessment_through'] or previous and value['employee_id']!=previous['employee_id']
                or previous and not value['correction_reason'] or not previous and value['status']!='active'):raise ValueError('Broken wage interruption history')
        if value['status']=='void' and (previous is None or previous['status']!='active' or any(value[key]!=previous[key] for key in ('details','source_file_ids','sources','plan','preview_hash'))):
            raise ValueError('Changed void wage interruption')
        validate_sources(office,value);prior[value['id']]=value;accepted.add((value['id'],value['revision']))
    receipts=[(row['fact_id'],row['fact_revision']) for row in office.db.execute('SELECT * FROM '+TABLES[1])]
    if len(receipts)!=len(accepted) or set(receipts)!=accepted:raise ValueError('Missing or duplicated wage interruption acceptance')
    return True


def current_projection(office,employee_id,year,records):
    """Fresh yearly field completeness; preserve invalidated original evidence."""
    from business_schema import _tables
    empty=dict(status='missing',reference=None,assessment_through=None,number_u=None,periods=[],covered_dates=[],blockers=[],additional_statutory_fields_required=False)
    if not set(TABLES).issubset(_tables(office)):return empty
    api=PayrollWageInterruptions(office)
    selected=[value for value in api._all(employee_id) if str(value['details']['year'])==year and value['status']=='active']
    if not selected:return empty
    if len(selected)!=1:raise Problem(500,'Mehrere aktuelle U-Jahresnachweise vorhanden.')
    value=selected[0]
    try:validate_sources(office,value)
    except ValueError as error:raise Problem(500,'Integrität des ursprünglichen U-Merkmalsnachweises verletzt.') from error
    plan=value['plan'];status='current' if plan['can_determine'] else 'incomplete';blockers=list(plan['blockers'])
    try:
        employee=api.db.execute('SELECT * FROM business_employees WHERE id=?',(employee_id,)).fetchone()
        expected=api._snapshot(dict(employee),value['details'],value['source_file_ids'])
        if expected!=value['sources']:raise Problem(409,'Aktuelle U-Quellen weichen von der angenommenen Fassung ab.')
        bound=value['details']['run_refs'];covered=set(plan['covered_dates'])
        for run in records:
            if run.get('source',{}).get('source_schema_version')!=3:continue
            unpaid=run['calculation']['period_details']['unpaid_dates']
            if unpaid and (reference(run) not in bound or not set(unpaid).issubset(covered)):
                raise Problem(409,'Ein tatsächlich unbezahlter Zeitraum ist vom U-Nachweis noch nicht abgedeckt.')
    except Problem as error:
        if error.status not in (400,404,409):raise
        status='outdated';blockers.append(dict(code='wage_interruption_sources_outdated',message=error.message))
    return dict(status=status,reference=reference(value),assessment_through=plan['assessment_through'],
        number_u=plan['number_u'] if status=='current' else None,periods=plan['periods'],covered_dates=plan['covered_dates'],blockers=blockers,
        additional_statutory_fields_required=bool(value['details']['excluded_payments']))


def methods(path):
    if path=='/payroll/wage-interruptions':return 'GET, POST'
    if path=='/payroll/wage-interruptions/preview':return 'POST'
    if path=='/payroll/wage-interruptions/sources' or re.fullmatch('/payroll/wage-interruptions/'+ID+'(?:/history)?',path):return 'GET'
    return None


def dispatch(office,actor,path,method,data):
    allowed=methods(path)
    if allowed is None:return None
    if method not in allowed.split(', '):raise Problem(405,'Methode für diesen U-Nachweis nicht erlaubt.')
    api=PayrollWageInterruptions(office)
    if method=='POST':result=api.preview(actor,data) if path.endswith('/preview') else api.save(actor,data)
    else:
        _shape(data,('_query',));query=data.get('_query',{})
        if path.endswith('/sources'):result=api.sources(actor,query)
        elif path=='/payroll/wage-interruptions':result=api.records(actor,query)
        else:_shape(query,());result=api.get(actor,path.split('/')[3],path.endswith('/history'))
    return result,200,'application/json'
