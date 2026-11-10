"""Private immutable original evidence for one minijob RV revocation episode.

No profile change, statutory notification or payment is produced by this API.
"""
import json
from copy import deepcopy
import re
import uuid
from core import Problem, canonical
from business_operations import identifier, text, transaction
from business_personnel_workflow import _integer, _sha, _shape
from business_payroll_facts import PayrollFacts, ref, reference, file_ids, employee_view, EMPLOYEE_FIELDS
from payroll_minijob_rv_lifecycle_2026 import RULE_VERSION, normalize, assess, InvalidEvidence

FEATURES=('payroll_rv_lifecycle',)
TABLES=('business_payroll_rv_lifecycle_events','business_payroll_rv_lifecycle_requests')
KIND='rv_lifecycle_assessment'
ID=r'[a-f0-9]{32}'

def schema_statements(binary_type='BYTEA'):
    from business_payroll_facts import schema_statements as original
    return [value.replace('business_payroll_fact','business_payroll_rv_lifecycle')
        .replace("'employment_terms','work_schedule','period_case'","'rv_lifecycle_assessment'") for value in original(binary_type)]


def guard_statements(dialect):
    from business_payroll_facts import guard_statements as original
    return [value.replace('business_payroll_fact','business_payroll_rv_lifecycle')
        .replace('immutable payroll fact','immutable payroll RV lifecycle') for value in original(dialect)]


def protected_tables():return TABLES
def runtime_privileges():return {table:('SELECT','INSERT') for table in TABLES}


def normalize_details(value):
    _shape(value,('assessment','prior_assessment_refs'),('assessment','prior_assessment_refs'))
    try:
        assessment=normalize(value['assessment'])
    except InvalidEvidence as error:
        raise Problem(400,'Vollständige belegte RV-Antragsgeschichte, Datumsfolge und Fristprüfung erforderlich.') from error
    prior=value['prior_assessment_refs']
    if not isinstance(prior,list) or len(prior)>100:raise Problem(400,'Begrenzten vollständigen bisherigen RV-Verlauf angeben.')
    prior=[ref(item) for item in prior]
    if len({(item['id'],item['revision']) for item in prior})!=len(prior):raise Problem(400,'Jede ursprüngliche RV-Fassung genau einmal binden.')
    return dict(assessment=assessment,prior_assessment_refs=sorted(prior,key=lambda r:(r['id'],r['revision'])))


def build_plan(snapshot):
    try:
        result=assess(snapshot['details']['assessment'],original_profile=snapshot['original_profile'],
            source_files=snapshot['source_files'],prior_assessments=[p['assessment'] for p in snapshot['prior_assessments']])
    except InvalidEvidence as error:
        raise Problem(409,'Die gebundenen RV-Originale oder der vollständige bisherige Antragsverlauf widersprechen sich.') from error
    return dict(result,can_determine=result['can_bind_payroll'],source_snapshot_hash=_sha(snapshot))


class PayrollRvLifecycle(PayrollFacts):
    def _gate(self,actor,*,new=True):
        from business_schema import require_capability
        from business_organization import require_active
        require_capability(self.office,'business_payroll_rv_lifecycle')
        if new:require_active(self.office,actor,'/payroll','business_payroll')

    def _row(self,object_id,revision=None):
        identifier(object_id)
        if revision is None:row=self.db.execute('SELECT * FROM '+TABLES[0]+' WHERE id=? ORDER BY revision DESC LIMIT 1',(object_id,)).fetchone()
        else:
            _integer(revision,1);row=self.db.execute('SELECT * FROM '+TABLES[0]+' WHERE id=? AND revision=?',(object_id,revision)).fetchone()
        if row is None:raise Problem(404,'RV-Lebenslauf nicht verfügbar.')
        return row

    def _event(self,row):
        result=super()._event(row);result.pop('accepted_command');return result

    def _all(self,employee_id,kind=None):
        return [self._event(row) for row in self.db.execute('SELECT e.* FROM '+TABLES[0]+' e WHERE e.employee_id=? AND NOT EXISTS '
            '(SELECT 1 FROM '+TABLES[0]+' n WHERE n.id=e.id AND n.revision>e.revision) ORDER BY e.created_at,e.id',(employee_id,))]

    def _snapshot(self,employee,details,ids,*,fresh=True,exclude_reference=None):
        assessment=details['assessment'];employee_id=employee['id']
        if (assessment['employee_id']!=employee_id or assessment['episode_id']!=employee_id
                or assessment['employment_from']!=employee['employment_from']
                or assessment['employment_to']!=(employee['employment_to'] or None)):
            raise Problem(409,'Den unveränderten tatsächlichen Beschäftigungsverlauf dieser Person binden.')
        if fresh and assessment['reviewed_as_of']>self.hr.now()[:10]:
            raise Problem(400,'Keine zukünftige tatsächliche RV-Prüfung bestätigen.')
        helper=PayrollFacts(self.office,clock=self.hr.clock)
        original=helper._payroll_ref(employee_id,assessment['established_exemption']['profile_ref'],fresh=fresh)
        files=[dict(value,revision=1) for value in self._files(employee_id,ids,fresh=fresh)]
        prior=[]
        for ref in details['prior_assessment_refs']:
            value=self._event(self._row(ref['id'],ref['revision']))
            if value['employee_id']!=employee_id or reference(value)!=ref:
                raise Problem(409,'Bisheriger RV-Nachweis gehört nicht unverändert zu dieser Person.')
            prior.append(dict(reference=ref,assessment=value['details']['assessment']))
        if fresh:
            expected=[reference(self._event(row)) for row in self.db.execute('SELECT * FROM '+TABLES[0]+' WHERE employee_id=? ORDER BY id,revision',(employee_id,))]
            if exclude_reference is not None:expected=[r for r in expected if r!=exclude_reference]
            if sorted(expected,key=lambda r:(r['id'],r['revision']))!=details['prior_assessment_refs']:
                raise Problem(409,'Alle bisherigen RV-Originalfassungen vollständig binden; aktuellen Verlauf neu laden.')
        snapshot=dict(schema_version=1,rule_version=RULE_VERSION,employee=employee_view(employee),details=details,
            original_profile=original,source_files=files,prior_assessments=prior)
        build_plan(snapshot)
        return snapshot

    def sources(self,actor,query):
        _shape(query,('employee_id',),('employee_id',))
        with transaction(self.office):
            fresh,employee=self._access(actor,query['employee_id'])
            self._gate(fresh,new=False)
            from business_payroll import Payroll
            items=[self._event(row) for row in self.db.execute('SELECT * FROM '+TABLES[0]+' WHERE employee_id=? ORDER BY id,revision',(employee['id'],))]
            for item in items:validate_sources(self.office,item)
            files=[v for v in self.hr.files(fresh,dict(employee_id=employee['id']))['items'] if v['purpose']=='personnel']
            return dict(employee=employee_view(employee),employee_id=employee['id'],episode_id=employee['id'],
                profiles=Payroll(self.office)._all('profile',employee['id']),history=items,
                prior_assessment_refs=sorted([reference(v) for v in items],key=lambda r:(r['id'],r['revision'])),
                files=files,file_references=[dict(id=v['id'],revision=1,content_hash=v['content_hash']) for v in files],
                **self._capabilities(fresh))

    def records(self,actor,query):
        _shape(query,('employee_id',),('employee_id',))
        with transaction(self.office):
            fresh,employee=self._access(actor,query['employee_id']);self._gate(fresh,new=False)
            items=self._all(employee['id'])
            for item in items:validate_sources(self.office,item)
            return dict(employee_id=employee['id'],items=items,**self._capabilities(fresh))

    def get(self,actor,object_id,history=False):
        with transaction(self.office):
            row=self._row(object_id);fresh,_=self._access(actor,row['employee_id']);self._gate(fresh,new=False)
            items=[self._event(r) for r in self.db.execute('SELECT * FROM '+TABLES[0]+' WHERE id=? ORDER BY revision',(object_id,))] if history else [self._event(row)]
            for item in items:validate_sources(self.office,item)
            return dict(items=items) if history else items[0]

    @staticmethod
    def _versions(data):
        if data['kind']!=KIND or data['rule_version']!=RULE_VERSION or type(data['source_contract_version']) is not int or data['source_contract_version']!=1:
            raise Problem(400,'RV-Lebenslaufart und ausdrückliche Regel-/Quellenversion angeben.')
        _integer(data['employee_revision'],1)

    def preview(self,actor,data):
        fields=('employee_id','employee_revision','kind','rule_version','source_contract_version','details','source_file_ids')
        _shape(data,fields,fields);self._versions(data);details=normalize_details(data['details']);ids=file_ids(data['source_file_ids'])
        with transaction(self.office):
            fresh,employee=self._access(actor,data['employee_id']);self._gate(fresh,new=False)
            if employee['revision']!=data['employee_revision']:raise Problem(409,'Aktuelle tatsächliche Mitarbeiterrevision angeben.')
            sources=self._snapshot(employee,details,ids);plan=build_plan(sources)
            return dict(employee_id=employee['id'],kind=KIND,source_snapshot=sources,source_hash=_sha(sources),plan=plan,
                preview_hash=_sha(dict(source_snapshot=sources,plan=plan)),can_confirm=True,can_determine=plan['can_determine'],**self._capabilities(fresh))

    def save(self,actor,data):
        required=('request_id','employee_id','employee_revision','kind','rule_version','source_contract_version','revision','status','details','source_file_ids','confirmed','preview_hash')
        _shape(data,required+('id','correction_reason'),required);identifier(data['request_id']);self._versions(data);_integer(data['revision'])
        if data.get('id') is not None:identifier(data['id'])
        if data['confirmed'] is not True or data['status']!='active' or not re.fullmatch('[a-f0-9]{64}',str(data['preview_hash'])):
            raise Problem(400,'Aktiven RV-Lebenslauf, geprüfte Vorschau und ausdrückliche Bestätigung angeben.')
        details=normalize_details(data['details']);ids=file_ids(data['source_file_ids']);reason=text(data.get('correction_reason',''),'Korrekturgrund',2000,required=bool(data.get('id')))
        operation='rv_lifecycle.saved';fingerprint=_sha([operation,data])
        with transaction(self.office):
            fresh,employee=self._access(actor,data['employee_id'],'personnel.approve');self._gate(fresh,new=False)
            receipt=self.db.execute('SELECT * FROM '+TABLES[1]+' WHERE user_id=? AND request_id=?',(fresh['id'],data['request_id'])).fetchone()
            if receipt is not None:
                if receipt['operation']!=operation or receipt['request_hash']!=fingerprint:raise Problem(409,'Vorgangs-ID gehört zu anderem ursprünglichen RV-Auftrag.')
                row=self._row(receipt['fact_id'],receipt['fact_revision']);value=self._event(row)
                if json.loads(row['payload_json'])['accepted_command']!=data or value['content_hash']!=receipt['fact_content_hash']:raise Problem(500,'RV-Annahmequittung widerspricht dem Originalauftrag.')
                validate_sources(self.office,value);return value
            try:
                self._gate(fresh)
                if employee['revision']!=data['employee_revision']:raise Problem(409,'Mitarbeiter wurde seit der RV-Vorschau geändert.')
                previous=self._get(data['id']) if data.get('id') else None
                if previous and previous['employee_id']!=employee['id']:raise Problem(404,'RV-Korrektur gehört zu anderer Person.')
                if data['revision']!=(previous['revision'] if previous else 0):raise Problem(409,'RV-Lebenslauf wurde inzwischen geändert.')
                identity='episode:'+employee['id']
                existing=self.db.execute('SELECT id FROM '+TABLES[0]+' WHERE employee_id=? AND identity_key=?',(employee['id'],identity)).fetchone()
                if existing and (previous is None or existing['id']!=previous['id']):raise Problem(409,'Bestehenden vollständigen RV-Lebenslauf fortschreiben; keinen zweiten Verlauf beginnen.')
                snapshot=self._snapshot(employee,details,ids);plan=build_plan(snapshot)
                if _sha(dict(source_snapshot=snapshot,plan=plan))!=data['preview_hash']:raise Problem(409,'RV-Quellen wurden seit Vorschau geändert.')
                payload=dict(rule_version=RULE_VERSION,source_contract_version=1,details=details,source_file_ids=ids,plan=plan,
                    preview_hash=data['preview_hash'],correction_reason=reason,accepted_command=json.loads(canonical(data)))
                envelope=dict(id=previous['id'] if previous else uuid.uuid4().hex,revision=previous['revision']+1 if previous else 1,
                    employee_id=employee['id'],kind=KIND,effective_from=employee['employment_from'],effective_to=employee['employment_to'] or None,
                    status='active',source_hash=_sha(snapshot),previous_hash=previous['content_hash'] if previous else None,
                    created_by=fresh['id'],created_at=self.hr.now(),identity_key=None if previous else identity,
                    command_hash=fingerprint,payload=payload,sources=snapshot)
                columns=tuple(key for key in envelope if key not in ('payload','sources'))
                self.db.execute('INSERT INTO '+TABLES[0]+'('+','.join(columns)+',payload_json,sources_json,content_hash) VALUES('+','.join('?' for _ in range(len(columns)+3))+')',
                    tuple(envelope[key] for key in columns)+(canonical(payload),canonical(snapshot),_sha(envelope)))
                value=self._get(envelope['id'])
                self.db.execute('INSERT INTO '+TABLES[1]+'(user_id,request_id,operation,request_hash,fact_id,fact_revision,fact_content_hash,created_at) VALUES(?,?,?,?,?,?,?,?)',
                    (fresh['id'],data['request_id'],operation,fingerprint,value['id'],value['revision'],value['content_hash'],envelope['created_at']))
                validate_sources(self.office,value);self.office.audit(fresh,'payroll.rv_lifecycle',value['id']);return value
            except Problem as error:
                if error.status==409:raise Problem(409,error.message,request_resolution='not_accepted') from None
                raise


def validate_sources(office,value):
    api=PayrollRvLifecycle(office)
    try:
        row=api._row(value['id'],value['revision']);payload=json.loads(row['payload_json']);command=payload['accepted_command'];api._versions(command)
        details=normalize_details(value['details']);fingerprint=_sha(['rv_lifecycle.saved',command])
        receipt=office.db.execute('SELECT * FROM '+TABLES[1]+' WHERE user_id=? AND request_id=?',(value['created_by'],command['request_id'])).fetchone()
        if (api._event(row)!=value or value['rule_version']!=RULE_VERSION or type(value['source_contract_version']) is not int or value['source_contract_version']!=1
                or value['kind']!=KIND or value['status']!='active'
                or row['identity_key']!=('episode:'+value['employee_id'] if value['revision']==1 else None)
                or row['command_hash']!=fingerprint or receipt is None or receipt['operation']!='rv_lifecycle.saved'
                or receipt['request_hash']!=fingerprint or receipt['fact_id']!=value['id'] or receipt['fact_revision']!=value['revision']
                or receipt['fact_content_hash']!=value['content_hash'] or receipt['created_at']!=value['created_at']
                or normalize_details(command['details'])!=details or command['employee_id']!=value['employee_id']
                or command['revision']+1!=value['revision'] or command.get('id',value['id'])!=value['id'] or command['status']!=value['status']
                or command['preview_hash']!=value['preview_hash'] or command['confirmed'] is not True
                or file_ids(command['source_file_ids'])!=value['source_file_ids'] or details!=value['details']
                or text(command.get('correction_reason',''),'Korrekturgrund',2000)!=value['correction_reason']):raise ValueError('Changed RV acceptance original')
        expected_prior=[reference(api._event(item)) for item in office.db.execute('SELECT * FROM '+TABLES[0]+' WHERE id=? AND revision<? ORDER BY revision',(value['id'],value['revision']))]
        if details['prior_assessment_refs']!=expected_prior:raise ValueError('Incomplete original RV prefix')
        employee=value['sources']['employee'];_shape(employee,EMPLOYEE_FIELDS,EMPLOYEE_FIELDS)
        if (employee['id']!=value['employee_id'] or employee['revision']!=command['employee_revision']
                or value['effective_from']!=employee['employment_from'] or value['effective_to']!=(employee['employment_to'] or None)):
            raise ValueError('Changed RV employee original')
        current=office.db.execute('SELECT user_id FROM business_employees WHERE id=?',(employee['id'],)).fetchone()
        if current is None or current['user_id']!=employee['user_id']:raise ValueError('Changed immutable RV employee binding')
        if not office.db.execute('SELECT 1 FROM business_employee_terms WHERE employee_id=? AND revision=?',(employee['id'],employee['revision'])).fetchone():
            raise ValueError('Missing original RV employee revision')
        accepted=[]
        for item in office.db.execute("SELECT result_json FROM business_planning_requests WHERE operation='employee' AND result_json LIKE ?",('%"id":"'+employee['id']+'"%',)):
            original=json.loads(item['result_json'])
            if original.get('id')==employee['id'] and original.get('revision')==employee['revision']:accepted.append(original)
        if len(accepted)!=1 or any(accepted[0].get(key)!=employee[key] for key in EMPLOYEE_FIELDS if key in accepted[0]):raise ValueError('Changed accepted RV employee revision')
        expected=api._snapshot(employee,details,value['source_file_ids'],fresh=False);plan=build_plan(expected)
        if (expected!=value['sources'] or plan!=value['plan'] or value['preview_hash']!=_sha(dict(source_snapshot=expected,plan=plan))
                or value['source_hash']!=_sha(expected) or details['assessment']['reviewed_as_of']>value['created_at'][:10]):
            raise ValueError('Changed RV historical sources or future review')
        return True
    except (Problem,KeyError,TypeError,ValueError,RecursionError) as error:raise ValueError('Invalid RV lifecycle archive') from error


def validate_integrity(office):
    from business_schema import _tables
    present=set(TABLES)&_tables(office)
    if not present:return True
    if present!=set(TABLES):raise ValueError('Incomplete RV lifecycle schema')
    api=PayrollRvLifecycle(office);prior={};accepted=set()
    for row in office.db.execute('SELECT * FROM '+TABLES[0]+' ORDER BY id,revision'):
        value=api._event(row);previous=prior.get(value['id'])
        if (value['revision']!=(previous['revision']+1 if previous else 1) or value['previous_hash']!=(previous['content_hash'] if previous else None)
                or row['identity_key']!=(None if previous else 'episode:'+value['employee_id'])
                or previous and (value['employee_id']!=previous['employee_id'] or value['effective_from']!=previous['effective_from'] or not value['correction_reason'])
                or value['status']!='active'):raise ValueError('Broken RV lifecycle history')
        validate_sources(office,value);prior[value['id']]=value;accepted.add((value['id'],value['revision']))
    receipts=[(row['fact_id'],row['fact_revision']) for row in office.db.execute('SELECT * FROM '+TABLES[1])]
    if len(receipts)!=len(accepted) or set(receipts)!=accepted:raise ValueError('Missing or duplicated RV lifecycle acceptance')
    return True


def methods(path):
    if path=='/payroll/rv-lifecycle':return 'GET, POST'
    if path=='/payroll/rv-lifecycle/preview':return 'POST'
    if path=='/payroll/rv-lifecycle/sources' or re.fullmatch('/payroll/rv-lifecycle/'+ID+'(?:/history)?',path):return 'GET'
    return None


def dispatch(office,actor,path,method,data):
    allowed=methods(path)
    if allowed is None:return None
    if method not in allowed.split(', '):raise Problem(405,'Methode für diesen RV-Nachweis nicht erlaubt.')
    api=PayrollRvLifecycle(office)
    if method=='POST':result=api.preview(actor,data) if path.endswith('/preview') else api.save(actor,data)
    else:
        _shape(data,('_query',));query=data.get('_query',{})
        if path.endswith('/sources'):result=api.sources(actor,query)
        elif path=='/payroll/rv-lifecycle':result=api.records(actor,query)
        else:_shape(query,());result=api.get(actor,path.split('/')[3],path.endswith('/history'))
    return result,200,'application/json'


PROFILE_SOURCE_VERSION=1
PROFILE_BINDING_FIELDS=('rv_lifecycle_source_contract_version','rv_lifecycle_ref')


def available(office):
    from business_schema import _tables
    present=set(TABLES)&_tables(office)
    if present and present!=set(TABLES):raise Problem(503,'Der RV-Lebenslauf ist nicht vollständig verfügbar.')
    return present==set(TABLES)


def profile_binding_input(data):
    present=[name in data for name in PROFILE_BINDING_FIELDS]
    if present[0]!=present[1]:raise Problem(400,'RV-Quellenversion und konkrete Originalfassung gemeinsam angeben.')
    if not present[0]:return None
    if type(data[PROFILE_BINDING_FIELDS[0]]) is not int or data[PROFILE_BINDING_FIELDS[0]]!=PROFILE_SOURCE_VERSION:
        raise Problem(400,'Die ausdrücklich unterstützte RV-Profilquellenversion1 angeben.')
    return ref(data['rv_lifecycle_ref'])


def original_reference(office,employee_id,value):
    bound=ref(value);api=PayrollRvLifecycle(office);result=api._event(api._row(bound['id'],bound['revision']))
    if result['employee_id']!=employee_id or reference(result)!=bound or result['status']!='active':
        raise Problem(409,'RV-Originalfassung gehört nicht unverändert zu dieser Person.')
    try:validate_sources(office,result)
    except ValueError as error:raise Problem(500,'Der ursprüngliche RV-Nachweis ist nicht unverändert reproduzierbar.') from error
    return result


def resolve_current(office,actor,employee_id,value,*,clock=None):
    api=PayrollRvLifecycle(office,clock=clock)
    with transaction(office):
        fresh,employee=api._access(actor,employee_id);api._gate(fresh,new=False)
        result=original_reference(office,employee_id,value)
        bound=reference(result)
        if reference(api._get(bound['id']))!=bound:raise Problem(409,'RV-Lebenslauf wurde geändert; aktuelle Originalfassung neu auswählen.')
        current=api._snapshot(employee,result['details'],result['source_file_ids'],fresh=True,exclude_reference=bound)
        if current!=result['sources']:raise Problem(409,'RV-Nachweise oder Personalstamm sind seit der Prüfung geändert.')
        return result


def status_for_month(record,month):
    snapshot=deepcopy(record['sources']);snapshot['details']['assessment']['target_month']=month
    return build_plan(snapshot)


def bind_profile(office,actor,employee,profile,value,*,previous=None,clock=None):
    if profile['employment_kind']!='minijob':
        if value is not None:raise Problem(400,'Dieser RV-Lebenslauf gehört zum gewerblichen Minijob.')
        return None
    if not available(office):
        if value is not None:raise Problem(409,'RV-Profilbindung ist auf diesem Server nicht verfügbar.')
        return None
    api=PayrollRvLifecycle(office,clock=clock);items=api._all(employee['id'])
    if not items:
        if value is not None:raise Problem(409,'Zuerst den tatsächlichen RV-Lebenslauf dieser Person festhalten.')
        return None
    if len(items)!=1:raise Problem(500,'Der ursprüngliche RV-Lebenslauf ist nicht eindeutig.')
    if value is None:raise Problem(409,'Für diesen aufgenommenen RV-Lebenslauf den aktuellen Nachweis ausdrücklich am Profil binden.')
    original=resolve_current(office,actor,employee['id'],value,clock=clock)
    if previous is not None and previous['id']==original['details']['assessment']['established_exemption']['profile_ref']['id']:
        raise Problem(409,'Das ursprüngliche RV-Befreiungsprofil ist gebunden; seine fachliche Berichtigung benötigt einen eigenen geprüften Korrekturweg.')
    status=status_for_month(original,profile['effective_from'][:7])
    if not status['can_bind_payroll'] or status['minijob_rv_exempt']!=profile['minijob_rv_exempt']:
        raise Problem(409,'Der neue Profilstatus ist für seinen Wirksamkeitsmonat nicht durch den aktuellen RV-Verlauf belegt.')
    return reference(original)


def validate_archived_profile(office,profile):
    value=profile_binding_input(profile)
    if value is None:return True
    original=original_reference(office,profile['employee_id'],value)
    if original['created_at']>profile['created_at'] or profile['profile']['employment_kind']!='minijob':
        raise Problem(500,'Die gebundene RV-Quelle bestand nicht beim ursprünglichen Minijobprofil.')
    status=status_for_month(original,profile['profile']['effective_from'][:7])
    if not status['can_bind_payroll'] or status['minijob_rv_exempt']!=profile['profile']['minijob_rv_exempt']:
        raise Problem(500,'Der ursprüngliche Profilstatus widerspricht seinem damaligen RV-Nachweis.')
    return True


def used_profiles(source,calculation):
    pool=[source['profile']]
    for container in (source.get('period_case'),source.get('calculation_case')):
        if isinstance(container,dict):pool.extend(container.get('sources',{}).get('profiles',[]))
    detail=calculation.get('period_details') or {};refs=[]
    for name in ('tax_periods','social_periods'):
        for period in detail.get(name,[]):
            if period.get('profile_ref') is not None:refs.append(period['profile_ref'])
    unique={(p['id'],p['revision'],p['content_hash']):p for p in pool}
    if not refs:return [source['profile']]
    keys={(r['id'],r['revision'],r['content_hash']) for r in refs}
    if not keys.issubset(unique):raise Problem(500,'Der verwendete RV-Profilbestandteil fehlt im ursprünglichen Lohnquellsnapshot.')
    return [unique[key] for key in sorted(keys)]


def guard_prepared_payroll(office,actor,result,*,clock=None):
    profiles=used_profiles(result['source'],result['calculation'])
    minis=[p for p in profiles if p['profile']['employment_kind']=='minijob']
    if not minis or not available(office):return result
    employee_id=result['source']['employee_id'];api=PayrollRvLifecycle(office,clock=clock)
    # Current global private access precedes inspecting the presence of history.
    api._access(actor,employee_id)
    records=api._all(employee_id)
    if not records:return result
    if len(records)!=1 or len(minis)!=len(profiles):
        raise Problem(409,'Dieser RV-Vertrag benötigt den belegten Minijob ohne Wechsel in eine andere Beschäftigungsart.')
    latest=reference(records[0]);current=resolve_current(office,actor,employee_id,latest,clock=clock)
    status=status_for_month(current,result['source']['month'])
    if not status['can_bind_payroll']:
        raise Problem(409,'Die RV-Wirkung für diesen Abrechnungsmonat ist noch nicht abschließend belegt.')
    for profile in minis:
        if profile_binding_input(profile)!=latest or profile['profile']['minijob_rv_exempt']!=status['minijob_rv_exempt']:
            raise Problem(409,'Alle tatsächlich verwendeten Minijobprofile an den aktuellen RV-Nachweis dieses Monats binden.')
    return result


def validate_archived_payroll(office,run):
    profiles=used_profiles(run['source'],run['calculation'])
    for profile in profiles:
        bound=profile_binding_input(profile)
        if bound is None:continue
        original=original_reference(office,run['employee_id'],bound)
        status=status_for_month(original,run['source']['month'])
        if (original['created_at']>run['created_at'] or not status['can_bind_payroll']
                or status['minijob_rv_exempt']!=profile['profile']['minijob_rv_exempt']):
            raise Problem(500,'Die ursprüngliche RV-Profilquelle stimmt nicht mit dem damaligen Lohnmonat überein.')
    return True
