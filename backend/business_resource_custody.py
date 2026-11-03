"""Evidence-backed custody and usage holds for canonical planning resources.

An operator records an inspection; this software does not perform or certify it.
The native calendar calls usage_blockers for every new resource assignment.
"""
import base64
from datetime import datetime,timezone,timedelta
import hashlib
import json
import re
import sqlite3
import uuid
from zoneinfo import ZoneInfo

from core import Problem,canonical
from business_foundation import _fresh,require_permission
from business_operations import identifier,iso_date,instant,text,transaction
from business_planning import Planning

FEATURES=('resource_custody',)
ID=r'[a-f0-9]{32}'
MAX_FILE=2*1024*1024
CONDITIONS=('unknown','serviceable','restricted','out_of_service')
TABLES=tuple('business_resource_'+name for name in ('profiles','requirements','inspections','handoffs','returns','corrections','evidence','requests'))
HANDOFF_FIELDS=('employee_id','project_id','issued_at','expected_return_at','condition','notes','evidence_id')
RETURN_FIELDS=('handoff_id','returned_at','received_by_employee_id','condition','notes','evidence_id')


def sha(value):return hashlib.sha256(value if isinstance(value,bytes) else canonical(value).encode()).hexdigest()
def shape(data,required,optional=()):
    if not isinstance(data,dict) or set(data)-set(required)-set(optional) or set(required)-set(data):raise Problem(400,'Unvollständige oder unbekannte Betriebsmittelfelder.')
def moment(value):return datetime.fromisoformat(value.replace('Z','+00:00'))


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA','BLOB'):raise ValueError('Unsupported storage type')
    return [
        '''CREATE TABLE IF NOT EXISTS business_resource_profiles(
        resource_id TEXT NOT NULL REFERENCES business_resources(id),revision INTEGER NOT NULL CHECK(revision>0),
        payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
        PRIMARY KEY(resource_id,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_resource_requirements(
        id TEXT NOT NULL,resource_id TEXT NOT NULL REFERENCES business_resources(id),revision INTEGER NOT NULL CHECK(revision>0),
        payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
        PRIMARY KEY(id,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_resource_inspections(
        id TEXT PRIMARY KEY,resource_id TEXT NOT NULL REFERENCES business_resources(id),requirement_id TEXT NOT NULL,requirement_revision INTEGER NOT NULL,
        supersedes_id TEXT UNIQUE REFERENCES business_resource_inspections(id),payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
        FOREIGN KEY(requirement_id,requirement_revision) REFERENCES business_resource_requirements(id,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_resource_handoffs(
        id TEXT PRIMARY KEY,resource_id TEXT NOT NULL REFERENCES business_resources(id),employee_id TEXT REFERENCES business_employees(id),project_id TEXT REFERENCES projects(id),
        payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_resource_returns(
        id TEXT PRIMARY KEY,resource_id TEXT NOT NULL REFERENCES business_resources(id),handoff_id TEXT NOT NULL UNIQUE REFERENCES business_resource_handoffs(id),
        payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_resource_corrections(
        id TEXT PRIMARY KEY,resource_id TEXT NOT NULL REFERENCES business_resources(id),target_kind TEXT NOT NULL,target_id TEXT NOT NULL,
        payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        f'''CREATE TABLE IF NOT EXISTS business_resource_evidence(
        id TEXT PRIMARY KEY,resource_id TEXT NOT NULL REFERENCES business_resources(id),filename TEXT NOT NULL,media_type TEXT NOT NULL,
        content {binary_type} NOT NULL,sha256 TEXT NOT NULL,sequence INTEGER NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,UNIQUE(resource_id,filename))''',
        '''CREATE TABLE IF NOT EXISTS business_resource_requests(
        user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,operation TEXT NOT NULL,
        request_json TEXT NOT NULL,request_hash TEXT NOT NULL,result_json TEXT NOT NULL,PRIMARY KEY(user_id,request_id))''',
    ]


def protected_tables():return TABLES
def runtime_privileges():return {table:('SELECT','INSERT') for table in TABLES}
def guard_statements(dialect):
    output=[]
    if dialect=='postgresql':output.append("CREATE OR REPLACE FUNCTION business_resource_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable resource custody evidence'; END; $$")
    keys={'profiles':'resource_id=NEW.resource_id AND revision=NEW.revision','requirements':'id=NEW.id AND revision=NEW.revision',
        'inspections':'id=NEW.id OR (supersedes_id IS NOT NULL AND supersedes_id=NEW.supersedes_id)',
        'handoffs':'id=NEW.id','returns':'id=NEW.id OR handoff_id=NEW.handoff_id','corrections':'id=NEW.id',
        'evidence':'id=NEW.id OR (resource_id=NEW.resource_id AND filename=NEW.filename)','requests':'user_id=NEW.user_id AND request_id=NEW.request_id'}
    for table in TABLES:
        for action in ('UPDATE','DELETE'):
            name=table+'_'+action.lower()+'_guard'
            if dialect=='sqlite':output.append(f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable resource custody evidence'); END")
            elif dialect=='postgresql':output.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION business_resource_immutable_guard(); END IF; END $$")
            else:raise ValueError('Unsupported storage dialect')
        if dialect=='sqlite':output.append(f"CREATE TRIGGER IF NOT EXISTS {table}_replace_guard BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {keys[table.removeprefix('business_resource_')]}) BEGIN SELECT RAISE(ABORT,'immutable resource custody evidence'); END")
    return output


class ResourceCustody:
    def __init__(self,office,clock=None):
        self.office,self.db=office,office.db;self.planning=Planning(office)
        self.clock=clock or (lambda:datetime.now(timezone.utc))
    def now(self):return self.clock().astimezone(timezone.utc).isoformat(timespec='seconds')
    def access(self,actor):
        actor=require_permission(self.office,actor,'planning.read')
        return require_permission(self.office,actor,'planning.write')
    def gate(self):
        from business_schema import require_capability,state
        require_capability(self.office,'business_resource_custody')
        if state(self.office)['readonly']:raise Problem(423,'Betriebsmittel sind derzeit nur lesbar.')
    def active(self,actor):
        from business_organization import require_active
        require_active(self.office,actor,'/planning/resources','business_planning')
    def value(self,row):
        value=json.loads(row['payload_json'])
        if sha(value)!=row['sha256']:raise Problem(500,'Betriebsmittelnachweis ist beschädigt.')
        return value
    def resource(self,resource_id):
        row=self.db.execute('SELECT * FROM business_resources WHERE id=?',(identifier(resource_id),)).fetchone()
        if row is None:raise Problem(404,'Planungsressource nicht verfügbar.')
        return dict(row,active=bool(row['active']))
    def rows(self,kind,resource_id):
        values=[self.value(row) for row in self.db.execute('SELECT * FROM business_resource_'+kind+' WHERE resource_id=?',(resource_id,))]
        return sorted(values,key=lambda item:item['sequence'])
    def profile(self,resource_id):
        rows=self.rows('profiles',resource_id)
        return rows[-1] if rows else dict(id=resource_id,resource_id=resource_id,revision=0,sequence=0,serial_number='',manufacturer='',model='',location='',condition='unknown',notes='')
    def requirements(self,resource_id):
        result={}
        for value in self.rows('requirements',resource_id):result[value['id']]=value
        return list(result.values())
    def file(self,resource_id,file_id):
        row=self.db.execute('SELECT * FROM business_resource_evidence WHERE id=? AND resource_id=?',(identifier(file_id),resource_id)).fetchone()
        if row is None:raise Problem(404,'Originalnachweis nicht verfügbar.')
        if sha(bytes(row['content']))!=row['sha256']:raise Problem(409,'Originalnachweis ist beschädigt.')
        return row
    def files(self,resource_id):
        return [dict(id=r['id'],resource_id=r['resource_id'],filename=r['filename'],media_type=r['media_type'],size=len(r['content']),sha256=r['sha256'],sequence=r['sequence']) for r in self.db.execute('SELECT * FROM business_resource_evidence WHERE resource_id=? ORDER BY sequence',(resource_id,))]
    def sequence(self,resource_id):
        return 1+sum(self.db.execute('SELECT COUNT(*) FROM '+table+' WHERE resource_id=?',(resource_id,)).fetchone()[0] for table in TABLES if not table.endswith('_requests'))
    def identity(self,resource_id):
        resource=self.resource(resource_id);profile=self.profile(resource_id)
        return {**{key:resource[key] for key in ('id','kind','code')},**{key:profile[key] for key in ('serial_number','manufacturer','model')}}
    def effective(self,resource_id,kind,value):
        result=dict(value)
        corrections=[c for c in self.rows('corrections',resource_id) if c['target_kind']==kind and c['target_id']==value['id']]
        if corrections:
            latest=corrections[-1];result.update(latest['values'],sequence=latest['sequence'],correction_id=latest['id'])
        return result
    def handoffs(self,resource_id):
        returns={r['handoff_id']:r for r in self.rows('returns',resource_id)}
        result=[]
        for row in self.rows('handoffs',resource_id):
            returned=returns.get(row['id'])
            result.append(dict(row,effective=self.effective(resource_id,'handoff',row),
                **{'return':dict(returned,effective=self.effective(resource_id,'return',returned)) if returned else None}))
        return result
    def snapshot(self,resource_id):
        return dict(resource=self.resource(resource_id),profiles=self.rows('profiles',resource_id),requirements=self.rows('requirements',resource_id),
            inspections=self.rows('inspections',resource_id),handoffs=self.rows('handoffs',resource_id),returns=self.rows('returns',resource_id),
            corrections=self.rows('corrections',resource_id),files=self.files(resource_id))
    def source(self,resource_id):
        snapshot=self.snapshot(resource_id)
        snapshot['appointments']=[dict(r) for r in self.db.execute('SELECT a.id,a.project_id,a.revision,a.status,a.start_at,a.end_at FROM business_appointments a JOIN business_appointment_resources r ON r.appointment_id=a.id WHERE r.resource_id=? ORDER BY a.id',(resource_id,))]
        return sha(snapshot)
    def condition(self,resource_id):
        profile=self.profile(resource_id)
        candidates=[profile]
        handoffs=self.handoffs(resource_id)
        if handoffs:
            latest=max(handoffs,key=lambda h:(moment(h['effective']['issued_at']),h['sequence']))
            candidates.append(latest['return']['effective'] if latest['return'] else latest['effective'])
        return max(candidates,key=lambda item:item['sequence'])['condition']
    def safety(self,resource_id,start_at,end_at,timezone_name):
        resource=self.resource(resource_id);profile=self.profile(resource_id);blockers=[]
        if not resource['active']:blockers.append(dict(code='inactive',message='Planungsressource ist deaktiviert.'))
        condition=self.condition(resource_id)
        if condition in ('restricted','out_of_service'):blockers.append(dict(code='condition',message='Der dokumentierte Zustand sperrt die Nutzung.'))
        try:zone=ZoneInfo(timezone_name)
        except (ValueError,KeyError):raise Problem(400,'Gültige Zeitzone erforderlich.') from None
        last_day=(moment(end_at)-timedelta(microseconds=1)).astimezone(zone).date().isoformat()
        inspections=self.rows('inspections',resource_id);identity=sha(self.identity(resource_id))
        for requirement in self.requirements(resource_id):
            if not requirement['active'] or not requirement['required_for_use']:continue
            matching=[i for i in inspections if i['requirement_id']==requirement['id'] and i['requirement_revision']==requirement['revision']]
            current=matching[-1] if matching else None
            if current is None or current['result']!='passed' or current['identity_sha256']!=identity:
                blockers.append(dict(code='inspection_required',message='Ein aktueller bestandener Nachweis zur Nutzungsanforderung fehlt.',requirement_id=requirement['id']));continue
            self.file(resource_id,current['evidence_id'])
            if moment(current['performed_at'])>moment(start_at):blockers.append(dict(code='inspection_after_start',message='Der Prüfnachweis liegt nach dem gewählten Nutzungsbeginn.',requirement_id=requirement['id']))
            if current['next_due_on'] and last_day>current['next_due_on']:blockers.append(dict(code='inspection_due',message='Der ausdrücklich festgelegte nächste Prüftermin liegt vor Ende der Nutzung.',requirement_id=requirement['id']))
        return blockers
    def usage(self,resource_id,start_at,end_at,timezone_name,employee_ids=(),project_id=None):
        blockers=self.safety(resource_id,start_at,end_at,timezone_name)
        for handoff in self.handoffs(resource_id):
            value=handoff['effective'];returned=handoff['return']['effective'] if handoff['return'] else None
            if moment(value['issued_at'])>=moment(end_at) or returned and moment(returned['returned_at'])<=moment(start_at):continue
            if value['employee_id'] and value['employee_id'] not in employee_ids or value['project_id'] and value['project_id']!=project_id:
                blockers.append(dict(code='custody',message='Im gewählten Zeitraum besteht eine Ausgabe an einen anderen Mitarbeiter oder ein anderes Projekt.'))
        return blockers
    def view(self,actor,resource_id):
        with transaction(self.office):
            self.access(actor);resource=self.resource(resource_id);profile=self.profile(resource_id);handoffs=self.handoffs(resource_id)
            now=self.now();end=(moment(now)+timedelta(minutes=1)).isoformat();blockers=self.usage(resource_id,now,end,'UTC')
            blockers.extend(self.reservations(resource_id,now,end))
            opened=next((h for h in handoffs if h['return'] is None),None)
            return dict(id=resource_id,resource=resource,profile=profile,requirements=self.requirements(resource_id),inspections=self.rows('inspections',resource_id),handoffs=handoffs,files=self.files(resource_id),
                source_sha256=self.source(resource_id),state=dict(configured=bool(profile['revision'] or self.requirements(resource_id)),checked_at=now,condition=self.condition(resource_id),
                    open_handoff=opened,blockers=blockers,available=not blockers,inspection_knowledge='declared' if self.requirements(resource_id) else 'unconfigured'))
    def listing(self,actor):
        with transaction(self.office):
            self.access(actor)
            return dict(items=[self.view(actor,r['id']) for r in self.db.execute('SELECT id FROM business_resources ORDER BY name,id')])
    def options(self,actor):
        with transaction(self.office):
            self.access(actor)
            employees=[{k:r[k] for k in ('id','user_id','name','active')} for r in self.planning.employees(actor)['items'] if r['active']]
            return dict(resources=self.planning.resources(actor)['items'],employees=employees,projects=[dict(p) for p in self.office.projects(actor)],conditions=list(CONDITIONS))
    def history(self,actor,resource_id):
        with transaction(self.office):
            self.access(actor);self.resource(resource_id)
            return {key:self.rows(key,resource_id) for key in ('profiles','requirements','inspections','handoffs','returns','corrections')}
    def availability(self,actor,resource_id,query):
        shape(query,('start_at','end_at','timezone'),('employee_id','project_id'))
        with transaction(self.office):
            self.access(actor);self.resource(resource_id)
            start,end=instant(query['start_at']),instant(query['end_at'])
            if start>=end:raise Problem(400,'Geordneter Nutzungszeitraum erforderlich.')
            employee_ids=[identifier(query['employee_id'])] if query.get('employee_id') else []
            project_id=identifier(query['project_id']) if query.get('project_id') else None
            self.targets(actor,employee_ids[0] if employee_ids else None,project_id,required=False)
            blockers=self.usage(resource_id,start,end,query['timezone'],employee_ids,project_id)
            blockers.extend(self.reservations(resource_id,start,end))
            return dict(resource_id=resource_id,source_sha256=self.source(resource_id),start_at=start,end_at=end,available=not blockers,blockers=blockers,
                inspection_knowledge='declared' if self.requirements(resource_id) else 'unconfigured')

    def reservations(self,resource_id,start,end):
        return [dict(code='reservation',message='Eine bestehende Kalenderbuchung überschneidet sich.',appointment_id=row['id']) for row in self.db.execute("SELECT a.id FROM business_appointments a JOIN business_appointment_resources r ON r.appointment_id=a.id WHERE r.resource_id=? AND a.status='scheduled' AND a.start_at<? AND a.end_at>?",(resource_id,end,start))]

    def targets(self,actor,employee_id,project_id,required=True):
        if required and not employee_id and not project_id:raise Problem(400,'Tatsächlichen Mitarbeiter oder kanonisches Projekt wählen.')
        employee=project=None
        if employee_id:
            row=self.planning.employee(identifier(employee_id))
            if not row['active'] or not row['user_active']:raise Problem(409,'Aktiver tatsächlicher Mitarbeiter erforderlich.')
            employee={k:row[k] for k in ('id','user_id','name','active','user_active')}
        if project_id:
            project=dict(self.office.project(actor,identifier(project_id)))
            if employee:
                try:self.office.project(_fresh(self.office,dict(id=employee['user_id'])),project_id)
                except Problem:raise Problem(409,'Mitarbeiter muss zum gewählten Projekt gehören.') from None
        return employee,project
    def actual(self,value,name):
        value=instant(value,name)
        if moment(value)>moment(self.now()):raise Problem(400,'Ein tatsächlicher Vorgang darf nicht in der Zukunft liegen: '+name)
        return value
    def evidence(self,resource_id,file_id,required=False):
        if file_id is None:
            if required:raise Problem(400,'Ein unveränderter Originalnachweis ist erforderlich.')
            return None
        row=self.file(resource_id,file_id)
        return dict(id=row['id'],sha256=row['sha256'],filename=row['filename'])
    def condition_value(self,value):
        if value not in CONDITIONS:raise Problem(400,'Dokumentierten Zustand auswählen.')
        return value
    def movement_values(self,actor,resource_id,kind,data):
        fields=HANDOFF_FIELDS if kind=='handoff' else RETURN_FIELDS;shape(data,fields)
        value={key:data[key] for key in fields};value['condition']=self.condition_value(value['condition'])
        value['notes']=text(value['notes'],'Übergabevermerk',5000,required=True)
        value['evidence_snapshot']=self.evidence(resource_id,value['evidence_id'])
        if kind=='handoff':
            employee,project=self.targets(actor,value['employee_id'],value['project_id'])
            value['employee_snapshot'],value['project_snapshot']=employee,project
            value['issued_at']=self.actual(value['issued_at'],'Ausgabezeitpunkt')
            value['expected_return_at']=instant(value['expected_return_at'],'Rückgabe erwartet') if value['expected_return_at'] is not None else None
            if value['expected_return_at'] and value['expected_return_at']<value['issued_at']:raise Problem(400,'Erwartete Rückgabe darf nicht vor Ausgabe liegen.')
        else:
            identifier(value['handoff_id']);value['returned_at']=self.actual(value['returned_at'],'Rückgabezeitpunkt')
            receiver,_=self.targets(actor,value['received_by_employee_id'],None,required=False);value['receiver_snapshot']=receiver
        return value
    def interval_check(self,resource_id):
        previous_end=None;first=True
        values=sorted(self.handoffs(resource_id),key=lambda r:moment(r['effective']['issued_at']))
        for row in values:
            start=moment(row['effective']['issued_at']);end=moment(row['return']['effective']['returned_at']) if row['return'] else None
            if end is not None and end<start:raise Problem(409,'Rückgabe darf nicht vor der tatsächlichen Ausgabe liegen.')
            if not first and (previous_end is None or start<previous_end):raise Problem(409,'Ausgabezeiträume dürfen sich nicht überschneiden.')
            previous_end=end;first=False
    def receipt(self,actor,operation,data):
        identifier(data['request_id']);safe=dict(data)
        if 'content_base64' in safe:safe['content_base64_sha256']=sha(safe.pop('content_base64'))
        fingerprint=sha([operation,safe]);row=self.db.execute('SELECT * FROM business_resource_requests WHERE user_id=? AND request_id=?',(actor['id'],data['request_id'])).fetchone()
        if row and (row['operation']!=operation or row['request_hash']!=fingerprint):raise Problem(409,'Vorgangs-ID wurde bereits anders verwendet.')
        return safe,fingerprint,json.loads(row['result_json']) if row else None
    def remember(self,actor,operation,safe,fingerprint,result):
        self.db.execute('INSERT INTO business_resource_requests VALUES(?,?,?,?,?,?)',(actor['id'],safe['request_id'],operation,canonical(safe),fingerprint,canonical(result)))
        return result
    def stamp(self,actor,resource_id,values,record_id=None,revision=1):
        return dict(values,id=record_id or uuid.uuid4().hex,resource_id=resource_id,revision=revision,sequence=self.sequence(resource_id),created_by=actor['id'],created_at=self.now())
    def upload(self,actor,resource_id,data):
        shape(data,('request_id','filename','media_type','content_base64'))
        with transaction(self.office):
            actor=self.access(actor);self.gate();self.resource(resource_id);operation='files:'+resource_id
            safe,fingerprint,previous=self.receipt(actor,operation,data)
            if previous:return previous
            self.active(actor)
            filename=text(data['filename'],'Dateiname',200,required=True)
            if filename in ('.','..') or any(c in filename for c in '/\\') or any(ord(c)<32 or ord(c)==127 for c in filename):raise Problem(400,'Dateiname ohne Pfad oder Steuerzeichen erforderlich.')
            if data['media_type'] not in ('application/pdf','image/jpeg','image/png','application/xml','text/xml'):raise Problem(400,'PDF, PNG, JPEG oder XML-Original wählen.')
            if not isinstance(data['content_base64'],str) or len(data['content_base64'])>4*((MAX_FILE+2)//3):raise Problem(413,'Original darf höchstens 2 MiB umfassen.')
            try:raw=base64.b64decode(data['content_base64'],validate=True)
            except (ValueError,TypeError):raise Problem(400,'Ungültige Originaldatei.') from None
            if not raw or len(raw)>MAX_FILE:raise Problem(413,'Original benötigt 1 Byte bis 2 MiB.')
            if data['media_type']=='application/pdf' and not raw.startswith(b'%PDF-'):raise Problem(400,'PDF-Dateikopf fehlt.')
            if any(f['filename']==filename for f in self.files(resource_id)):raise Problem(409,'Originalname bereits vorhanden; Nachweis wird nicht ersetzt.')
            if len(self.files(resource_id))>=200:raise Problem(413,'Höchstens 200 Originale je Ressource.')
            record=dict(id=uuid.uuid4().hex,resource_id=resource_id,filename=filename,media_type=data['media_type'],size=len(raw),sha256=sha(raw),sequence=self.sequence(resource_id))
            self.db.execute('INSERT INTO business_resource_evidence VALUES(?,?,?,?,?,?,?,?,?)',(record['id'],resource_id,filename,data['media_type'],raw,record['sha256'],record['sequence'],actor['id'],self.now()))
            return self.remember(actor,operation,safe,fingerprint,record)
    def command(self,actor,resource_id,action,data):
        common=('request_id','source_sha256','confirmation')
        fields={'profile':('revision','serial_number','manufacturer','model','location','condition','notes','reason'),
            'requirements':('revision','title','due_on','required_for_use','active','notes','reason'),
            'inspections':('requirement_id','requirement_revision','performed_at','inspector','result','next_due_on','evidence_id','note','supersedes_id','correction_reason'),
            'handoffs':HANDOFF_FIELDS,'returns':RETURN_FIELDS,
            'corrections':('target_kind','target_id','values','reason','evidence_id')}
        shape(data,(*common,*fields[action]),('id',) if action=='requirements' else ())
        with transaction(self.office):
            actor=self.access(actor);self.gate();resource=self.resource(resource_id);operation=action+':'+resource_id
            safe,fingerprint,previous=self.receipt(actor,operation,data)
            if previous:return previous
            self.active(actor)
            if data['confirmation'] is not True:raise Problem(400,'Konkrete Aussage oder Übergabe ausdrücklich bestätigen.')
            if data['source_sha256']!=self.source(resource_id):raise Problem(409,'Ressource, Nachweise oder Kalenderbindung haben sich geändert; neu prüfen.')
            if action=='profile':
                current=self.profile(resource_id)
                if type(data['revision']) is not int or data['revision']!=current['revision']:raise Problem(409,'Profil wurde inzwischen geändert.')
                values={k:text(data[k],k,5000 if k=='notes' else 1000 if k=='reason' else 200,required=k=='reason') for k in ('serial_number','manufacturer','model','location','notes','reason')}
                values['condition']=self.condition_value(data['condition'])
                if any(h['return'] is None for h in self.handoffs(resource_id)) and any(values[k]!=current[k] for k in ('serial_number','manufacturer','model')):raise Problem(409,'Ausgegebenes Betriebsmittel darf nicht still umidentifiziert werden; zuerst tatsächliche Rücknahme.')
                record=self.stamp(actor,resource_id,dict(values,native_resource_snapshot=resource),resource_id,current['revision']+1)
                self.db.execute('INSERT INTO business_resource_profiles VALUES(?,?,?,?,?,?)',(resource_id,record['revision'],canonical(record),sha(record),actor['id'],record['created_at']))
            elif action=='requirements':
                requirement_id=identifier(data['id']) if data.get('id') else uuid.uuid4().hex
                all_rows=self.db.execute('SELECT * FROM business_resource_requirements WHERE id=? ORDER BY revision DESC',(requirement_id,)).fetchall();current=self.value(all_rows[0]) if all_rows else None
                if current and current['resource_id']!=resource_id:raise Problem(404,'Anforderung gehört nicht zur Ressource.')
                if type(data['revision']) is not int or data['revision']!=(current['revision'] if current else 0):raise Problem(409,'Anforderung wurde inzwischen geändert.')
                if type(data['active']) is not bool or type(data['required_for_use']) is not bool:raise Problem(400,'Aktivierung und Nutzungsanforderung ausdrücklich auswählen.')
                values=dict(title=text(data['title'],'Anforderung',300,required=True),due_on=iso_date(data['due_on'],'Fälligkeit',optional=True),required_for_use=data['required_for_use'],active=data['active'],
                    notes=text(data['notes'],'Notizen',5000),reason=text(data['reason'],'Änderungsgrund',1000,required=True))
                record=self.stamp(actor,resource_id,values,requirement_id,(current['revision'] if current else 0)+1)
                self.db.execute('INSERT INTO business_resource_requirements VALUES(?,?,?,?,?,?,?)',(record['id'],resource_id,record['revision'],canonical(record),sha(record),actor['id'],record['created_at']))
            elif action=='inspections':
                requirement=next((r for r in self.requirements(resource_id) if r['id']==data['requirement_id']),None)
                if requirement is None or not requirement['active'] or data['requirement_revision']!=requirement['revision'] or type(data['requirement_revision']) is not int:raise Problem(409,'Aktuelle aktive Anforderung auswählen.')
                if data['result'] not in ('passed','failed','review_required'):raise Problem(400,'Tatsächlich dokumentiertes Prüfergebnis auswählen.')
                performed=self.actual(data['performed_at'],'Prüfzeitpunkt');due=iso_date(data['next_due_on'],'Nächster Prüftermin',optional=True)
                if due and due<performed[:10]:raise Problem(400,'Nächster Prüftermin darf nicht vor der Prüfung liegen.')
                evidence=self.evidence(resource_id,data['evidence_id'],True);inspector=text(data['inspector'],'Prüfende Person',300,required=True)
                note=text(data['note'],'Prüfvermerk',5000,required=True);reason=text(data['correction_reason'],'Korrekturgrund',1000)
                previous_inspections=[i for i in self.rows('inspections',resource_id) if i['requirement_id']==requirement['id']]
                if data['supersedes_id']:
                    if not previous_inspections or previous_inspections[-1]['id']!=identifier(data['supersedes_id']) or not reason:raise Problem(409,'Nur den jüngsten Nachweis dieser Anforderung begründet korrigieren.')
                elif reason:raise Problem(400,'Korrekturgrund benötigt den ursprünglichen Nachweis.')
                elif previous_inspections and performed<previous_inspections[-1]['performed_at']:raise Problem(409,'Rückdatierte Prüfung benötigt eine ausdrückliche Korrektur.')
                record=self.stamp(actor,resource_id,dict(requirement_id=requirement['id'],requirement_revision=requirement['revision'],performed_at=performed,inspector=inspector,result=data['result'],next_due_on=due,evidence_id=data['evidence_id'],evidence_snapshot=evidence,note=note,supersedes_id=data['supersedes_id'],correction_reason=reason,identity_snapshot=self.identity(resource_id),identity_sha256=sha(self.identity(resource_id))))
                self.db.execute('INSERT INTO business_resource_inspections VALUES(?,?,?,?,?,?,?,?,?)',(record['id'],resource_id,requirement['id'],requirement['revision'],data['supersedes_id'],canonical(record),sha(record),actor['id'],record['created_at']))
            elif action=='handoffs':
                if any(h['return'] is None for h in self.handoffs(resource_id)):raise Problem(409,'Ressource ist bereits ausgegeben; tatsächliche Rückgabe zuerst dokumentieren.')
                if not resource['active']:raise Problem(409,'Inaktive Ressource kann nicht neu ausgegeben werden.')
                values=self.movement_values(actor,resource_id,'handoff',{k:data[k] for k in HANDOFF_FIELDS})
                record=self.stamp(actor,resource_id,dict(values,identity_snapshot=self.identity(resource_id),identity_sha256=sha(self.identity(resource_id))))
                self.db.execute('INSERT INTO business_resource_handoffs VALUES(?,?,?,?,?,?,?,?)',(record['id'],resource_id,record['employee_id'],record['project_id'],canonical(record),sha(record),actor['id'],record['created_at']))
                self.interval_check(resource_id)
            elif action=='returns':
                original=next((h for h in self.handoffs(resource_id) if h['id']==data['handoff_id']),None)
                if original is None or original['return'] is not None:raise Problem(409,'Offene Ausgabe dieser Ressource auswählen.')
                values=self.movement_values(actor,resource_id,'return',{k:data[k] for k in RETURN_FIELDS})
                record=self.stamp(actor,resource_id,values)
                self.db.execute('INSERT INTO business_resource_returns VALUES(?,?,?,?,?,?,?)',(record['id'],resource_id,record['handoff_id'],canonical(record),sha(record),actor['id'],record['created_at']))
                self.interval_check(resource_id)
            else:
                if data['target_kind'] not in ('handoff','return'):raise Problem(400,'Ausgabe oder Rückgabe als Korrekturziel wählen.')
                table='handoffs' if data['target_kind']=='handoff' else 'returns'
                original=next((r for r in self.rows(table,resource_id) if r['id']==data['target_id']),None)
                if original is None:raise Problem(404,'Ursprünglicher Übergabenachweis nicht verfügbar.')
                evidence=self.evidence(resource_id,data['evidence_id'],True)
                values=self.movement_values(actor,resource_id,data['target_kind'],data['values'])
                if data['target_kind']=='return' and values['handoff_id']!=original['handoff_id']:raise Problem(409,'Eine Rückgabe darf nicht einer anderen Ausgabe zugeordnet werden.')
                record=self.stamp(actor,resource_id,dict(target_kind=data['target_kind'],target_id=original['id'],values=values,reason=text(data['reason'],'Korrekturgrund',2000,required=True),evidence_id=data['evidence_id'],evidence_snapshot=evidence,original_sha256=sha(original)))
                self.db.execute('INSERT INTO business_resource_corrections VALUES(?,?,?,?,?,?,?,?)',(record['id'],resource_id,data['target_kind'],original['id'],canonical(record),sha(record),actor['id'],record['created_at']))
                self.interval_check(resource_id)
            result=dict(resource=self.view(actor,resource_id),record=record)
            self.office.audit(actor,'business.resource.'+action,resource_id)
            return self.remember(actor,operation,safe,fingerprint,result)
    def original(self,actor,resource_id,file_id):
        with transaction(self.office):
            self.access(actor);self.resource(resource_id);row=self.file(resource_id,file_id)
            from business_documents import Download
            return Download(bytes(row['content']),row['filename']),200,'application/octet-stream'


def installed(office):
    return office.db.execute("SELECT 1 FROM business_schema_migrations WHERE module='business_resource_custody'").fetchone() is not None


def usage_blockers(office,values):
    """No personal details escape this native planning gate; no override bypass."""
    if values.get('status')=='cancelled' or not values.get('resource_ids') or not installed(office):return []
    api=ResourceCustody(office);result=[]
    for resource_id in values['resource_ids']:
        result.extend(dict(kind='resource_usage',resource_id=resource_id,**blocker) for blocker in
            api.usage(resource_id,values['start_at'],values['end_at'],values['timezone'],values.get('employee_ids',()),values.get('project_id')))
    return result


def guard_resource_change(office,previous,current):
    if previous is None or not installed(office):return
    previous=dict(previous)
    if any(previous.get(key)!=current.get(key) for key in ('kind','code')) and any(h['return'] is None for h in ResourceCustody(office).handoffs(previous['id'])):
        raise Problem(409,'Ausgegebenes Betriebsmittel darf nicht über den Ressourcenstamm umidentifiziert werden; tatsächliche Rückgabe zuerst dokumentieren.')


def validate_integrity(office):
    api=ResourceCustody(office);db=office.db
    try:
        for resource in db.execute('SELECT id FROM business_resources'):
            resource_id=resource['id'];sequences=[]
            for table in TABLES:
                if table.endswith('_requests'):continue
                for row in db.execute('SELECT * FROM '+table+' WHERE resource_id=?',(resource_id,)):
                    if table.endswith('_evidence'):
                        if not 0<len(row['content'])<=MAX_FILE or sha(bytes(row['content']))!=row['sha256']:raise ValueError('Invalid resource original')
                        sequences.append(row['sequence']);continue
                    value=api.value(row);sequences.append(value['sequence'])
                    if value['resource_id']!=resource_id or value['created_by']!=row['created_by'] or value['created_at']!=row['created_at']:raise ValueError('Invalid resource identity')
                    if table.endswith('_profiles') and (value['id']!=resource_id or value['revision']!=row['revision']):raise ValueError('Invalid resource profile')
                    if table.endswith('_requirements') and (value['id']!=row['id'] or value['revision']!=row['revision']):raise ValueError('Invalid requirement version')
                    if table.endswith('_inspections'):
                        if value['id']!=row['id'] or value['requirement_id']!=row['requirement_id'] or value['requirement_revision']!=row['requirement_revision'] or value['supersedes_id']!=row['supersedes_id']:raise ValueError('Invalid inspection binding')
                        if value['identity_sha256']!=sha(value['identity_snapshot']) or api.file(resource_id,value['evidence_id'])['sha256']!=value['evidence_snapshot']['sha256']:raise ValueError('Invalid inspection proof')
                        requirement=db.execute('SELECT resource_id FROM business_resource_requirements WHERE id=? AND revision=?',(value['requirement_id'],value['requirement_revision'])).fetchone()
                        if requirement is None or requirement['resource_id']!=resource_id:raise ValueError('Foreign inspection requirement')
                    if table.endswith('_handoffs'):
                        if value['id']!=row['id'] or value['employee_id']!=row['employee_id'] or value['project_id']!=row['project_id'] or value['identity_sha256']!=sha(value['identity_snapshot']):raise ValueError('Invalid handoff')
                    if table.endswith('_returns'):
                        handoff=db.execute('SELECT resource_id FROM business_resource_handoffs WHERE id=?',(value['handoff_id'],)).fetchone()
                        if value['id']!=row['id'] or value['handoff_id']!=row['handoff_id'] or handoff is None or handoff['resource_id']!=resource_id:raise ValueError('Foreign return')
                    if table.endswith('_corrections'):
                        if value['target_kind'] not in ('handoff','return') or value['id']!=row['id'] or value['target_kind']!=row['target_kind'] or value['target_id']!=row['target_id']:raise ValueError('Invalid custody correction')
                        kind='handoffs' if value['target_kind']=='handoff' else 'returns'
                        original=next((r for r in api.rows(kind,resource_id) if r['id']==value['target_id']),None)
                        if original is None or sha(original)!=value['original_sha256'] or original['sequence']>=value['sequence']:raise ValueError('Missing correction original')
                        if value['target_kind']=='return' and value['values']['handoff_id']!=original['handoff_id']:raise ValueError('Changed correction target')
                        if api.file(resource_id,value['evidence_id'])['sha256']!=value['evidence_snapshot']['sha256']:raise ValueError('Missing correction evidence')
                    if value.get('evidence_id') and value.get('evidence_snapshot'):
                        if api.file(resource_id,value['evidence_id'])['sha256']!=value['evidence_snapshot']['sha256']:raise ValueError('Changed original evidence')
            if sorted(sequences)!=list(range(1,len(sequences)+1)):raise ValueError('Resource history sequence gap')
            profiles=api.rows('profiles',resource_id)
            if [p['revision'] for p in profiles]!=list(range(1,len(profiles)+1)):raise ValueError('Resource profile gap')
            groups={}
            for row in api.rows('requirements',resource_id):groups.setdefault(row['id'],[]).append(row['revision'])
            if any(versions!=list(range(1,len(versions)+1)) for versions in groups.values()):raise ValueError('Resource requirement gap')
            api.interval_check(resource_id)
        for row in db.execute('SELECT * FROM business_resource_requests'):
            request=json.loads(row['request_json']);result=json.loads(row['result_json']);action,resource_id=row['operation'].split(':')
            if sha([row['operation'],request])!=row['request_hash'] or request['request_id']!=row['request_id']:raise ValueError('Invalid resource receipt')
            if action=='files':
                original=api.file(resource_id,result['id'])
                expected=next(r for r in api.files(resource_id) if r['id']==original['id'])
            else:
                record=result['record'];kind='profiles' if action=='profile' else action
                candidates=api.rows(kind,resource_id);expected=next((r for r in candidates if r['id']==record['id'] and r['revision']==record['revision']),None)
                if result['resource']['id']!=resource_id:raise ValueError('Foreign resource receipt')
                result=record
            if expected is None or result!=expected:raise ValueError('Receipt differs from immutable record')
    except (KeyError,TypeError,ValueError,Problem) as error:raise ValueError('Invalid resource custody evidence') from error
    return True


def methods(path):
    if path in ('/resource-custody','/resource-custody/options'):return 'GET'
    if re.fullmatch(r'/resource-custody/'+ID+r'(?:/(?:history|availability))?',path):return 'GET'
    if re.fullmatch(r'/resource-custody/'+ID+r'/(?:profile|requirements|inspections|handoffs|returns|corrections|files)',path):return 'POST'
    if re.fullmatch(r'/resource-custody/'+ID+r'/files/'+ID+r'/original',path):return 'GET'
    return None


def dispatch(office,actor,path,method,data):
    allowed=methods(path)
    if allowed is None:return None
    if method not in allowed.split(', '):raise Problem(405,'Methode nicht erlaubt.')
    if not isinstance(data,dict):raise Problem(400,'JSON-Objekt erwartet.')
    api=ResourceCustody(office);query=data.get('_query',{});body={k:v for k,v in data.items() if k!='_query'}
    if method=='GET':
        if body:raise Problem(400,'Keine zusätzlichen Abrufinhalte erlaubt.')
        if not path.endswith('/availability'):shape(query,())
        if path=='/resource-custody':result=api.listing(actor)
        elif path=='/resource-custody/options':result=api.options(actor)
        else:
            parts=path.split('/');resource_id=parts[2]
            if path.endswith('/original'):return api.original(actor,resource_id,parts[4])
            if path.endswith('/history'):result=api.history(actor,resource_id)
            elif path.endswith('/availability'):result=api.availability(actor,resource_id,query)
            else:result=api.view(actor,resource_id)
    else:
        if query:raise Problem(400,'Keine zusätzlichen Schreibfilter erlaubt.')
        _,_,resource_id,action=path.split('/')
        try:result=api.upload(actor,resource_id,body) if action=='files' else api.command(actor,resource_id,action,body)
        except Problem as error:
            if error.status==409 and isinstance(body.get('request_id'),str) and re.fullmatch(ID,body['request_id']):
                with transaction(office):
                    fresh=_fresh(office,actor)
                    if not office.db.execute('SELECT 1 FROM business_resource_requests WHERE user_id=? AND request_id=?',(fresh['id'],body['request_id'])).fetchone():raise Problem(409,error.message,request_resolution='not_accepted') from None
            raise
    return result,200,'application/json'
