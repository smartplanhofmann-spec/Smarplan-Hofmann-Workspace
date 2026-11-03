"""Customer service cases joining existing CRM, dispatch and signed evidence.

States are internal workflow decisions: no customer acceptance, legal warranty,
mail, invoice or financial action is inferred. Existing native guards still apply.
"""
from datetime import datetime, timezone
import hashlib
import json
import re
import sqlite3
import uuid

from core import Problem, canonical
from business_foundation import BusinessFoundation, _fresh, require_permission
from business_operations import BusinessOperations, identifier, iso_date, text, transaction
from business_maintenance import BusinessMaintenance
from business_planning import Planning as BusinessPlanning
from inquiries import Inquiries

FEATURES=('service_cases',)
ID=r'[a-f0-9]{32}'
PRIORITIES=('low','normal','high','urgent')
TRANSITIONS={'open':('triaged','cancelled'),'triaged':('planned','in_progress','waiting_customer','waiting_supplier','resolved','cancelled'),
    'planned':('in_progress','waiting_customer','waiting_supplier','resolved','cancelled'),
    'in_progress':('planned','waiting_customer','waiting_supplier','resolved','cancelled'),
    'waiting_customer':('triaged','planned','in_progress','resolved','cancelled'),
    'waiting_supplier':('triaged','planned','in_progress','resolved','cancelled'),
    'resolved':('closed','triaged'),'closed':('triaged',),'cancelled':('triaged',)}
REFS=('customer_id','project_id','asset_id','contract_id','visit_id','inquiry_id','defect_id')
FIELDS=('person_id','title','kind','priority','responsible_id','follow_up_on','description')
TABLES=tuple('business_service_'+name for name in ('cases','versions','events','links','requests'))


def sha(value):return hashlib.sha256(value if isinstance(value,bytes) else canonical(value).encode()).hexdigest()
def shape(data,required,optional=()):
    if not isinstance(data,dict) or set(data)-set(required)-set(optional) or set(required)-set(data):raise Problem(400,'Unvollständige oder unbekannte Servicefelder.')


def schema_statements(binary_type='BYTEA'):
    return [
        '''CREATE TABLE IF NOT EXISTS business_service_cases(
        id TEXT PRIMARY KEY,customer_id TEXT NOT NULL REFERENCES customers(id),origin_kind TEXT NOT NULL,origin_id TEXT,
        created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,UNIQUE(origin_kind,origin_id))''',
        '''CREATE TABLE IF NOT EXISTS business_service_versions(
        case_id TEXT NOT NULL REFERENCES business_service_cases(id),revision INTEGER NOT NULL CHECK(revision>0),
        payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
        PRIMARY KEY(case_id,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_service_events(
        id TEXT PRIMARY KEY,case_id TEXT NOT NULL REFERENCES business_service_cases(id),supersedes_id TEXT UNIQUE REFERENCES business_service_events(id),
        payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_service_links(
        id TEXT PRIMARY KEY,case_id TEXT NOT NULL REFERENCES business_service_cases(id),kind TEXT NOT NULL,target_id TEXT NOT NULL,
        payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
        UNIQUE(case_id,kind,target_id))''',
        '''CREATE TABLE IF NOT EXISTS business_service_requests(
        user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,operation TEXT NOT NULL,
        request_json TEXT NOT NULL,request_hash TEXT NOT NULL,result_json TEXT NOT NULL,PRIMARY KEY(user_id,request_id))''',
        "CREATE UNIQUE INDEX IF NOT EXISTS business_service_evidence_unique ON business_service_links(kind,target_id) WHERE kind IN ('report','appointment')",
        'CREATE INDEX IF NOT EXISTS business_service_customer ON business_service_cases(customer_id,created_at,id)',
    ]


def protected_tables():return TABLES
def runtime_privileges():return {table:('SELECT','INSERT') for table in TABLES}
def guard_statements(dialect):
    output=[]
    if dialect=='postgresql':output.append("CREATE OR REPLACE FUNCTION business_service_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable service history'; END; $$")
    keys={'cases':'id=NEW.id OR (origin_kind=NEW.origin_kind AND origin_id=NEW.origin_id)',
        'versions':'case_id=NEW.case_id AND revision=NEW.revision',
        'events':'id=NEW.id OR (supersedes_id IS NOT NULL AND supersedes_id=NEW.supersedes_id)',
        'links':"id=NEW.id OR (kind=NEW.kind AND target_id=NEW.target_id AND (case_id=NEW.case_id OR kind IN ('report','appointment')))",
        'requests':'user_id=NEW.user_id AND request_id=NEW.request_id'}
    for table in TABLES:
        for action in ('UPDATE','DELETE'):
            name=table+'_'+action.lower()+'_guard'
            if dialect=='sqlite':output.append(f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable service history'); END")
            elif dialect=='postgresql':output.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION business_service_immutable_guard(); END IF; END $$")
            else:raise ValueError('Unsupported storage dialect')
        if dialect=='sqlite':output.append(f"CREATE TRIGGER IF NOT EXISTS {table}_replace_guard BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {keys[table.removeprefix('business_service_')]}) BEGIN SELECT RAISE(ABORT,'immutable service history'); END")
    return output


class Service:
    def __init__(self,office,clock=None):
        self.office,self.db=office,office.db;self.foundation=BusinessFoundation(office)
        self.ops=BusinessOperations(office);self.maintenance=BusinessMaintenance(office);self.planning=BusinessPlanning(office)
        self.clock=clock or (lambda:datetime.now(timezone.utc))
    def now(self):return self.clock().astimezone(timezone.utc).isoformat(timespec='seconds')
    def value(self,row):
        value=json.loads(row['payload_json'])
        if sha(value)!=row['sha256']:raise Problem(500,'Servicenachweis ist beschädigt.')
        return value
    def gate(self):
        from business_schema import require_capability,state
        require_capability(self.office,'business_service')
        if state(self.office)['readonly']:raise Problem(423,'Kundenservice ist derzeit nur lesbar.')
    def current(self,case_id):
        row=self.db.execute('SELECT * FROM business_service_versions WHERE case_id=? ORDER BY revision DESC LIMIT 1',(identifier(case_id),)).fetchone()
        if row is None:raise Problem(404,'Servicefall nicht verfügbar.')
        return self.value(row)
    def access(self,actor,item,write=False):
        actor=_fresh(self.office,actor);project=item.get('project_id')
        require_permission(self.office,actor,'contacts.read',project)
        self.foundation._contact_scope(actor,item['customer_id'])
        if project:
            require_permission(self.office,actor,'documents.write' if write else 'documents.read',project)
            if self.office.project(actor,project)['customer_id']!=item['customer_id']:raise Problem(409,'Serviceprojekt gehört nicht zum Kunden.')
        elif actor['role']!='owner':raise Problem(403,'Servicefälle ohne Projekt bearbeitet die Geschäftsführung.')
        elif write:require_permission(self.office,actor,'contacts.write')
        return actor
    def sources(self,actor,item):
        actor=_fresh(self.office,actor)
        customer=self.foundation.contact(actor,item['customer_id'])
        if customer['erased_at']:raise Problem(404,'Kontakt nicht verfügbar.')
        result={'customer':customer,'project':dict(self.office.project(actor,item['project_id'])) if item.get('project_id') else None}
        for key,table,reader in (('asset_id','business_assets',self.maintenance._asset),('contract_id','business_maintenance_contracts',self.maintenance._contract),('visit_id','business_maintenance_visits',self.maintenance._visit)):
            if not item.get(key):continue
            if not item.get('project_id'):raise Problem(400,'Gerät und Wartung benötigen ihr kanonisches Projekt.')
            require_permission(self.office,actor,'documents.read',item['project_id'])
            row=self.maintenance.row(table,item['project_id'],identifier(item[key]));result[key]=reader(row)
        if item.get('contract_id') and (not item.get('asset_id') or result['contract_id']['asset_id']!=item['asset_id']):raise Problem(409,'Wartungsvertrag gehört nicht zum Gerät.')
        if item.get('visit_id') and (result['visit_id']['asset_id']!=item.get('asset_id') or result['visit_id']['contract_id']!=item.get('contract_id')):raise Problem(409,'Wartungsbesuch passt nicht zu Gerät und Vertrag.')
        if item.get('inquiry_id'):
            inquiry=Inquiries(self.office).get(actor,item['inquiry_id'])
            if inquiry.get('customer_id') and inquiry['customer_id']!=item['customer_id'] or inquiry.get('project_id') and item.get('project_id') and inquiry['project_id']!=item['project_id']:raise Problem(409,'Anfrage gehört zu einem anderen Kunden oder Projekt.')
            result['inquiry']=inquiry
        if item.get('defect_id'):
            if not item.get('project_id'):raise Problem(400,'Mangel benötigt sein Projekt.')
            defect=self.ops.get_entry(actor,item['project_id'],item['defect_id'])
            if defect['kind']!='defect':raise Problem(400,'Ausgewählte Quelle ist kein Mangel.')
            result['defect']=defect
        result['linked']=[]
        if item.get('id'):
            for row in self.db.execute('SELECT * FROM business_service_links WHERE case_id=? ORDER BY id',(item['id'],)):
                link=self.value(row)
                if link['kind']=='appointment':
                    require_permission(self.office,actor,'planning.read',item['project_id'])
                    native=self.db.execute('SELECT * FROM business_appointments WHERE id=? AND project_id=?',(link['target_id'],item['project_id'])).fetchone()
                    if native is None:raise Problem(409,'Verknüpfter Einsatz fehlt.')
                    result['linked'].append(self.planning._appointment(native))
                elif link['kind']=='report':
                    result['linked'].append(self.report_source(actor,item['project_id'],link['target_id']))
        return result
    def report_source(self,actor,project_id,report_id):
        if not project_id:raise Problem(400,'Servicebericht benötigt ein Projekt.')
        report=self.ops.get_entry(actor,project_id,identifier(report_id))
        if report['kind']!='service' or report['status']!='signed':raise Problem(409,'Unverändert unterzeichneter Servicebericht erforderlich.')
        pdf=self.ops.entry_pdf(actor,project_id,report_id)
        if sha(pdf)!=report['pdf_sha256']:raise Problem(409,'Berichtsoriginal wurde verändert.')
        return report
    def view(self,actor,case_id):
        with transaction(self.office):
            item=self.current(case_id);self.access(actor,item);source=self.sources(actor,item)
            links=[self.value(r) for r in self.db.execute('SELECT * FROM business_service_links WHERE case_id=? ORDER BY created_at,id',(case_id,))]
            person=self.db.execute('SELECT email FROM users WHERE id=?',(item['responsible_id'],)).fetchone()
            return dict(item,customer_name=source['customer']['name'],responsible_name=person['email'] if person else 'Nicht mehr verfügbar',
                source_sha256=sha(source),links=links,overdue=bool(item['follow_up_on'] and item['follow_up_on']<self.now()[:10] and item['status'] not in ('resolved','closed','cancelled')),
                allowed_transitions=list(TRANSITIONS[item['status']]))
    def receipt(self,actor,operation,data):
        identifier(data['request_id']);fingerprint=sha([operation,data])
        row=self.db.execute('SELECT * FROM business_service_requests WHERE user_id=? AND request_id=?',(actor['id'],data['request_id'])).fetchone()
        if row and (row['operation']!=operation or row['request_hash']!=fingerprint):raise Problem(409,'Vorgangs-ID wurde bereits anders verwendet.')
        return fingerprint,json.loads(row['result_json']) if row else None
    def remember(self,actor,operation,data,fingerprint,result):
        self.db.execute('INSERT INTO business_service_requests VALUES(?,?,?,?,?,?)',(actor['id'],data['request_id'],operation,canonical(data),fingerprint,canonical(result)))
        return result
    def version(self,actor,item):
        item=dict(item,revision=item['revision']+1,updated_by=actor['id'],updated_at=self.now())
        self.db.execute('INSERT INTO business_service_versions VALUES(?,?,?,?,?,?)',(item['id'],item['revision'],canonical(item),sha(item),actor['id'],item['updated_at']))
        return item
    def event(self,actor,item,kind,values,supersedes=None):
        ordinal=self.db.execute('SELECT COUNT(*) FROM business_service_events WHERE case_id=?',(item['id'],)).fetchone()[0]+1
        result=dict(id=uuid.uuid4().hex,case_id=item['id'],case_revision=item['revision'],ordinal=ordinal,kind=kind,values=values,supersedes_id=supersedes,created_by=actor['id'],created_at=self.now())
        self.db.execute('INSERT INTO business_service_events VALUES(?,?,?,?,?,?,?)',(result['id'],item['id'],supersedes,canonical(result),sha(result),actor['id'],result['created_at']))
        return result
    def link(self,actor,item,kind,target):
        result=dict(id=uuid.uuid4().hex,case_id=item['id'],kind=kind,target_id=target['id'],source_snapshot=target,source_sha256=sha(target),created_by=actor['id'],created_at=self.now())
        self.db.execute('INSERT INTO business_service_links VALUES(?,?,?,?,?,?,?,?)',(result['id'],item['id'],kind,target['id'],canonical(result),sha(result),actor['id'],result['created_at']))
        return result
    def listing(self,actor,query):
        shape(query,(),('q','customer_id','project_id','status','priority','responsible_id','due'))
        with transaction(self.office):
            actor=_fresh(self.office,actor)
            q=text(query.get('q',''),'Suche',200).casefold()
            for key in ('customer_id','project_id','responsible_id'):
                if query.get(key):identifier(query[key])
            if query.get('status') and query['status'] not in TRANSITIONS or query.get('priority') and query['priority'] not in PRIORITIES or query.get('due') not in (None,'overdue'):raise Problem(400,'Unbekannter Servicefilter.')
            items=[]
            for row in self.db.execute('SELECT id FROM business_service_cases ORDER BY created_at DESC,id'):
                try:item=self.view(actor,row['id'])
                except Problem as error:
                    if error.status in (403,404):continue
                    raise
                if any(query.get(k) and item[k]!=query[k] for k in ('customer_id','project_id','responsible_id','status','priority')):continue
                if query.get('due') and not item['overdue']:continue
                if q and q not in (item['title']+' '+item['description']+' '+item['customer_name']).casefold():continue
                items.append(item)
            return dict(items=items,summary=dict(open_count=sum(i['status'] not in ('resolved','closed','cancelled') for i in items),overdue_count=sum(i['overdue'] for i in items),as_of=self.now()))
    def options(self,actor,customer_id=None,project_id=None):
        with transaction(self.office):
            customer_id=identifier(customer_id) if customer_id else None;project_id=identifier(project_id) if project_id else None
            actor=require_permission(self.office,actor,'contacts.read',project_id)
            if customer_id:self.foundation.contact(actor,customer_id)
            if project_id:
                project=self.office.project(actor,project_id)
                if customer_id and project['customer_id']!=customer_id:raise Problem(409,'Projekt gehört zu einem anderen Kunden.')
                customer_id=project['customer_id']
            customers=[dict(id=c['id'],name=c['name'],persons=c['persons']) for c in self.foundation.contacts(actor)['items'] if c['active'] and not c['erased_at']]
            projects=[dict(p) for p in self.office.projects(actor) if not customer_id or p['customer_id']==customer_id]
            people=[]
            for person in self.db.execute('SELECT id,email FROM users WHERE active=1 ORDER BY email'):
                try:
                    candidate=_fresh(self.office,dict(person))
                    if project_id:self.access(candidate,dict(customer_id=customer_id,project_id=project_id),True)
                    elif candidate['role']!='owner':continue
                except Problem:continue
                people.append(dict(person))
            assets=contracts=visits=defects=reports=employees=resources=[]
            if project_id:
                assets=self.maintenance.list_assets(actor,project_id);contracts=self.maintenance.list_contracts(actor,project_id);visits=self.maintenance.history(actor,project_id)
                defects=self.ops.list_entries(actor,project_id,'defect');reports=[r for r in self.ops.list_entries(actor,project_id,'service') if r['status']=='signed']
                try:
                    require_permission(self.office,actor,'planning.read',project_id)
                    employees=self.planning.employees(actor,{'project_id':project_id})['items'];resources=self.planning.resources(actor)['items']
                except Problem as error:
                    if error.status!=403:raise
            inquiries=[]
            for row in self.db.execute('SELECT id FROM inquiries ORDER BY created_at DESC,id'):
                try:value=Inquiries(self.office).get(actor,row['id'])
                except Problem as error:
                    if error.status in (403,404):continue
                    raise
                if (not customer_id or value.get('customer_id') in (None,customer_id)) and (not project_id or value.get('project_id') in (None,project_id)):
                    inquiries.append({k:value.get(k) for k in ('id','subject','customer_id','project_id')})
            return dict(customer_id=customer_id,project_id=project_id,customers=customers,projects=projects,responsibles=people,assets=assets,contracts=contracts,visits=visits,defects=defects,reports=reports,
                employees=employees,resources=resources,inquiries=inquiries,stages=list(TRANSITIONS),priorities=list(PRIORITIES))

    def save(self,actor,data):
        shape(data,('request_id','revision',*REFS,*FIELDS),('id',))
        with transaction(self.office):
            self.gate();actor=_fresh(self.office,actor);old=self.current(data['id']) if data.get('id') else None
            operation='save:'+str(data.get('id'));fingerprint,previous=self.receipt(actor,operation,data)
            if previous:
                current=self.current(previous['id']);self.access(actor,current,True);self.sources(actor,current)
                return previous
            item={key:data[key] for key in (*REFS,*FIELDS)}
            for key in (*REFS,'person_id','responsible_id'):
                if item[key] is not None:identifier(item[key])
            if item['customer_id'] is None:raise Problem(400,'Kunde ist erforderlich.')
            origins=[(key,item[key]) for key in ('inquiry_id','defect_id','visit_id') if item[key]]
            if len(origins)>1:raise Problem(400,'Genau eine Eingangshistorie wählen; andere Nachweise später verknüpfen.')
            if item['visit_id']:
                native=self.db.execute('SELECT * FROM business_maintenance_visits WHERE id=?',(item['visit_id'],)).fetchone()
                if native is None:raise Problem(404,'Wartungsbesuch nicht verfügbar.')
                self.office.project(actor,native['project_id'])
                for key in ('project_id','asset_id','contract_id'):
                    if item[key] is not None and item[key]!=native[key]:raise Problem(409,'Wartungsbesuch besitzt einen anderen Quellenbezug.')
                    item[key]=native[key]
            elif item['defect_id']:
                native=self.db.execute("SELECT project_id FROM business_operation_entries WHERE id=? AND kind='defect'",(item['defect_id'],)).fetchone()
                if native is None:raise Problem(404,'Mangel nicht verfügbar.')
                self.office.project(actor,native['project_id'])
                if item['project_id'] is not None and item['project_id']!=native['project_id']:raise Problem(409,'Mangel gehört zu einem anderen Projekt.')
                item['project_id']=native['project_id']
            actor=self.access(actor,item,True);source=self.sources(actor,item)
            if type(data['revision']) is not int or data['revision']!=(old['revision'] if old else 0):raise Problem(409,'Servicefall wurde inzwischen geändert.')
            if old and any(item[key]!=old[key] for key in REFS):raise Problem(409,'Kunde und Quellen bleiben fest; Projekt nur ausdrücklich übernehmen.')
            if item['kind'] not in ('request','complaint','maintenance') or item['priority'] not in PRIORITIES:raise Problem(400,'Gültige Serviceart und Priorität wählen.')
            if item['visit_id'] and item['kind']!='maintenance':raise Problem(400,'Wartungsbesuch benötigt die Serviceart Wartung.')
            item['title']=text(item['title'],'Betreff',300,required=True);item['description']=text(item['description'],'Beschreibung',10000,required=True)
            item['follow_up_on']=iso_date(item['follow_up_on'],'Wiedervorlage',optional=True)
            customer=source['customer']
            if not old and not customer['active']:raise Problem(409,'Archivierten Kunden zuerst reaktivieren.')
            person=next((p for p in customer['persons'] if p['id']==item['person_id']),None)
            if item['person_id'] and person is None:raise Problem(409,'Ansprechpartner gehört nicht zum Kunden.')
            responsible=_fresh(self.office,dict(id=identifier(item['responsible_id'])))
            self.access(responsible,item,True)
            self.sources(responsible,item)
            if not old:
                origin_kind,origin_id=origins[0] if origins else ('manual',None)
                if origin_id and self.db.execute('SELECT 1 FROM business_service_cases WHERE origin_kind=? AND origin_id=?',(origin_kind,origin_id)).fetchone():raise Problem(409,'Diese Eingangshistorie besitzt bereits einen Servicefall.')
                item.update(id=uuid.uuid4().hex,revision=0,status='open',resolution='',last_transition_reason='',created_by=actor['id'],created_at=self.now(),origin_kind=origin_kind,origin_id=origin_id)
                self.db.execute('INSERT INTO business_service_cases VALUES(?,?,?,?,?,?)',(item['id'],item['customer_id'],origin_kind,origin_id,actor['id'],item['created_at']))
            else:
                if old['status'] in ('closed','cancelled'):raise Problem(409,'Abgeschlossenen Servicefall zuerst begründet wieder öffnen.')
                item={**old,**item}
            item.update(customer_snapshot={'id':customer['id'],'name':customer['name']},person_snapshot=person)
            item=self.version(actor,item)
            self.event(actor,item,'created' if old is None else 'edited',dict(source_sha256=sha(source)))
            self.office.audit(actor,'business.service.saved',item['id'])
            return self.remember(actor,operation,data,fingerprint,self.view(actor,item['id']))

    def history(self,actor,case_id):
        with transaction(self.office):
            self.view(actor,case_id)
            return dict(versions=[self.value(r) for r in self.db.execute('SELECT * FROM business_service_versions WHERE case_id=? ORDER BY revision',(case_id,))],
                events=sorted([self.value(r) for r in self.db.execute('SELECT * FROM business_service_events WHERE case_id=?',(case_id,))],key=lambda e:e['ordinal']))

    def command(self,actor,case_id,action,data):
        base=('request_id','revision','source_sha256')
        fields={'events':('kind','text','occurred_on','supersedes_id','correction_reason'),
            'project':('confirmation','project_id','project_name'),
            'dispatch':('confirmation','title','start_at','end_at','timezone','employee_ids','resource_ids','details'),
            'evidence':('confirmation','report_id'),'transition':('status','reason','resolution')}
        shape(data,(*base,*fields[action]))
        with transaction(self.office):
            self.gate();item=self.current(case_id);actor=self.access(actor,item,True);source=self.sources(actor,item)
            if action=='project':require_permission(self.office,actor,'projects.manage',item['project_id'])
            if action=='dispatch':require_permission(self.office,actor,'planning.write',item['project_id'])
            operation=action+':'+case_id;fingerprint,previous=self.receipt(actor,operation,data)
            if previous:return previous
            if type(data['revision']) is not int or data['revision']!=item['revision'] or data['source_sha256']!=sha(source):raise Problem(409,'Servicefall oder zugehörige Quellen wurden inzwischen geändert; neu prüfen.')
            if action not in ('events','transition') and item['status'] in ('resolved','closed','cancelled'):raise Problem(409,'Servicefall zuerst begründet wieder öffnen.')
            if action in ('project','dispatch','evidence') and data['confirmation'] is not True:raise Problem(400,'Konkrete Übernahme ausdrücklich bestätigen.')
            event=link=None
            if action=='events':
                if data['kind'] not in ('note','call','email','meeting'):raise Problem(400,'Unbekannte Aktivität.')
                occurred=iso_date(data['occurred_on'],'Aktivitätsdatum')
                if occurred>self.now()[:10]:raise Problem(400,'Dokumentierte Aktivität darf nicht in der Zukunft liegen.')
                reason=text(data['correction_reason'],'Korrekturgrund',1000)
                if data['supersedes_id']:
                    prior=self.db.execute('SELECT * FROM business_service_events WHERE id=? AND case_id=?',(identifier(data['supersedes_id']),case_id)).fetchone()
                    if prior is None or self.value(prior)['kind'] not in ('note','call','email','meeting') or not reason:raise Problem(409,'Nur eine bestehende Aktivität dieses Falls kann begründet korrigiert werden.')
                    if self.db.execute('SELECT 1 FROM business_service_events WHERE supersedes_id=?',(prior['id'],)).fetchone():raise Problem(409,'Aktivität wurde bereits korrigiert.')
                elif reason:raise Problem(400,'Korrekturgrund benötigt eine ursprüngliche Aktivität.')
                event=self.event(actor,item,data['kind'],dict(text=text(data['text'],'Aktivität',10000,required=True),occurred_on=occurred,correction_reason=reason,source_sha256=data['source_sha256']),data['supersedes_id'])
            elif action=='project':
                if item['project_id']:raise Problem(409,'Servicefall ist bereits mit seinem kanonischen Projekt verbunden.')
                if item['inquiry_id']:
                    inquiry=source['inquiry']
                    if inquiry.get('project_id'):
                        if data['project_id'] not in (None,inquiry['project_id']):raise Problem(409,'Anfrage besitzt bereits ihr kanonisches Projekt.')
                        project=dict(self.office.project(actor,inquiry['project_id']))
                    else:
                        if data['project_id'] is not None:raise Problem(409,'Anfrage zuerst über ihren bestehenden Konvertierungsweg übernehmen.')
                        converted=Inquiries(self.office).convert(actor,inquiry['id'],dict(request_id=sha(['service-project',case_id])[:32],revision=inquiry['revision'],project_name=data['project_name'],customer_id=item['customer_id']))
                        project=dict(converted['project'])
                elif data['project_id']:
                    project=dict(self.office.project(actor,identifier(data['project_id'])))
                    if project['customer_id']!=item['customer_id']:raise Problem(409,'Gewähltes Projekt gehört zu einem anderen Kunden.')
                else:
                    if actor['role']!='owner':raise Problem(403,'Neue Projekte legt die Geschäftsführung an.')
                    customer=self.foundation.contact(actor,item['customer_id'])
                    if not customer['active']:raise Problem(409,'Kunde ist archiviert.')
                    project=dict(id=uuid.uuid4().hex,name=text(data['project_name'],'Projektname',200,required=True),customer=customer['name'],customer_id=customer['id'])
                    self.db.execute('INSERT INTO projects(id,name,customer,customer_id) VALUES(?,?,?,?)',tuple(project[k] for k in ('id','name','customer','customer_id')))
                    self.office.audit(actor,'project.created',project['id'])
                item=dict(item,project_id=project['id']);self.access(dict(id=item['responsible_id']),item,True)
                self.sources(dict(id=item['responsible_id']),item)
                link=self.link(actor,item,'project',project);item=self.version(actor,item)
                event=self.event(actor,item,'project_linked',dict(link_id=link['id'],source_sha256=data['source_sha256']))
            elif action=='dispatch':
                if not item['project_id']:raise Problem(409,'Einsatz benötigt zuerst das kanonische Serviceprojekt.')
                from business_organization import require_active
                require_active(self.office,actor,'/planning/appointments','business_planning')
                command={k:data[k] for k in ('title','start_at','end_at','timezone','employee_ids','resource_ids','details')}
                command.update(request_id=sha(['service-dispatch',case_id,data['request_id']])[:32],project_id=item['project_id'])
                appointment=self.planning.save_appointment(actor,item['project_id'],command)
                link=self.link(actor,item,'appointment',appointment)
                item=self.version(actor,dict(item,status='planned'))
                event=self.event(actor,item,'dispatched',dict(link_id=link['id'],source_sha256=data['source_sha256']))
            elif action=='evidence':
                from business_organization import require_active
                require_active(self.office,actor,'/service-reports/offline','business_operations')
                report=self.report_source(actor,item['project_id'],data['report_id'])
                if self.db.execute("SELECT 1 FROM business_service_links WHERE kind='report' AND target_id=?",(report['id'],)).fetchone():raise Problem(409,'Servicebericht ist bereits einem Fall zugeordnet.')
                if item['visit_id']:
                    visit=source['visit_id']
                    if visit['status']=='completed':
                        if visit['report_id']!=report['id'] or visit['report_pdf_sha256']!=report['pdf_sha256']:raise Problem(409,'Wartungsabschluss besitzt einen anderen Bericht.')
                    else:self.maintenance.complete_visit(actor,item['project_id'],item['visit_id'],dict(request_id=sha(['service-maintenance',case_id,data['request_id']])[:32],revision=visit['revision'],report_id=report['id']))
                link=self.link(actor,item,'report',report);item=self.version(actor,item)
                event=self.event(actor,item,'evidence_linked',dict(link_id=link['id'],source_sha256=data['source_sha256']))
            else:
                target=data['status'];reason=text(data['reason'],'Entscheidungsgrund',2000,required=True)
                resolution=text(data['resolution'],'Lösung',10000)
                if target not in TRANSITIONS[item['status']]:raise Problem(409,'Dieser Statusübergang ist nicht zulässig.')
                if target in ('resolved','closed'):
                    if not resolution:raise Problem(400,'Abschluss benötigt die dokumentierte Lösung.')
                    if item['visit_id'] and source['visit_id']['status']!='completed':raise Problem(409,'Wartungsfall benötigt zuerst seinen belegten Wartungsabschluss.')
                if target=='planned' and not any(r.get('kind')=='appointment' and r.get('status')=='scheduled' for r in source['linked']):raise Problem(409,'Geplant benötigt einen vorhandenen, nicht abgesagten Einsatz.')
                before=item['status'];item=self.version(actor,dict(item,status=target,resolution=resolution,last_transition_reason=reason))
                event=self.event(actor,item,'transition',dict(from_status=before,to_status=target,reason=reason,resolution=resolution,source_sha256=data['source_sha256']))
            result=dict(case=self.view(actor,case_id))
            if event:result['event']=event
            if link:result['link']=link
            self.office.audit(actor,'business.service.'+action,case_id)
            return self.remember(actor,operation,data,fingerprint,result)


def validate_integrity(office):
    api=Service(office);db=office.db
    try:
        cases={r['id']:r for r in db.execute('SELECT * FROM business_service_cases')}
        for case_id,header in cases.items():
            versions=db.execute('SELECT * FROM business_service_versions WHERE case_id=? ORDER BY revision',(case_id,)).fetchall()
            if not versions:raise ValueError('Missing service history')
            for index,row in enumerate(versions,1):
                value=api.value(row)
                if value['id']!=case_id or value['revision']!=index or row['revision']!=index or value['customer_id']!=header['customer_id'] or value['origin_kind']!=header['origin_kind'] or value['origin_id']!=header['origin_id']:raise ValueError('Invalid service identity')
                if value['status'] not in TRANSITIONS or value['priority'] not in PRIORITIES:raise ValueError('Invalid service state')
                if value['updated_by']!=row['created_by'] or value['updated_at']!=row['created_at']:raise ValueError('Invalid service version author')
                if index>1:
                    prior=api.value(versions[index-2])
                    if any(value[k]!=prior[k] for k in REFS if k!='project_id') or prior['project_id'] is not None and value['project_id']!=prior['project_id']:raise ValueError('Changed canonical service references')
                if value['project_id']:
                    project=db.execute('SELECT customer_id FROM projects WHERE id=?',(value['project_id'],)).fetchone()
                    if project is None or project['customer_id']!=header['customer_id']:raise ValueError('Foreign service project')
            events=[api.value(r) for r in db.execute('SELECT * FROM business_service_events WHERE case_id=?',(case_id,))]
            if sorted(e['ordinal'] for e in events)!=list(range(1,len(events)+1)):raise ValueError('Service event sequence gap')
        for table in ('business_service_events','business_service_links'):
            for row in db.execute('SELECT * FROM '+table):
                value=api.value(row)
                if value['id']!=row['id'] or value['case_id']!=row['case_id'] or value['created_by']!=row['created_by'] or value['created_at']!=row['created_at']:raise ValueError('Invalid service evidence')
                if table.endswith('links'):
                    if value['kind']!=row['kind'] or value['target_id']!=row['target_id'] or value['source_sha256']!=sha(value['source_snapshot']) or value['source_snapshot']['id']!=row['target_id']:raise ValueError('Invalid source link')
                    kind_table={'project':'projects','appointment':'business_appointments','report':'business_operation_entries'}[row['kind']]
                    native=db.execute('SELECT * FROM '+kind_table+' WHERE id=?',(row['target_id'],)).fetchone()
                    if native is None:raise ValueError('Missing linked native object')
                    current=api.current(row['case_id'])
                    if (native['id'] if row['kind']=='project' else native['project_id'])!=current['project_id']:raise ValueError('Foreign linked native object')
                    if row['kind']=='report' and api.ops._entry(native)!=value['source_snapshot']:raise ValueError('Changed signed service evidence')
                else:
                    if value['supersedes_id']!=row['supersedes_id']:raise ValueError('Invalid correction reference')
                    if not db.execute('SELECT 1 FROM business_service_versions WHERE case_id=? AND revision=?',(row['case_id'],value['case_revision'])).fetchone():raise ValueError('Missing event version')
                    if row['supersedes_id']:
                        prior=db.execute('SELECT * FROM business_service_events WHERE id=? AND case_id=?',(row['supersedes_id'],row['case_id'])).fetchone()
                        if prior is None or api.value(prior)['ordinal']>=value['ordinal']:raise ValueError('Invalid correction order')
        for row in db.execute('SELECT * FROM business_service_requests'):
            request=json.loads(row['request_json']);result=json.loads(row['result_json'])
            if sha([row['operation'],request])!=row['request_hash'] or request['request_id']!=row['request_id']:raise ValueError('Invalid service receipt')
            value=result.get('case',result);proof=db.execute('SELECT * FROM business_service_versions WHERE case_id=? AND revision=?',(value['id'],value['revision'])).fetchone()
            if proof is None:raise ValueError('Missing receipt original')
            original=api.value(proof)
            if any(value.get(k)!=v for k,v in original.items()):raise ValueError('Receipt differs from original version')
            for key,table in (('event','business_service_events'),('link','business_service_links')):
                if key in result:
                    entry=db.execute('SELECT * FROM '+table+' WHERE id=?',(result[key]['id'],)).fetchone()
                    if entry is None or api.value(entry)!=result[key]:raise ValueError('Receipt differs from original evidence')
    except (KeyError,TypeError,ValueError,Problem) as error:raise ValueError('Invalid customer service history') from error
    return True


def methods(path):
    if path=='/service/options':return 'GET'
    if path=='/service/cases':return 'GET, POST'
    if re.fullmatch(r'/service/cases/'+ID+r'(?:/history)?',path):return 'GET'
    if re.fullmatch(r'/service/cases/'+ID+r'/(?:events|project|dispatch|evidence|transition)',path):return 'POST'
    return None


def dispatch(office,actor,path,method,data):
    allowed=methods(path)
    if allowed is None:return None
    if method not in allowed.split(', '):raise Problem(405,'Methode nicht erlaubt.')
    if not isinstance(data,dict):raise Problem(400,'JSON-Objekt erwartet.')
    api=Service(office);query=data.get('_query',{});body={k:v for k,v in data.items() if k!='_query'}
    if method=='GET':
        if body:raise Problem(400,'Keine zusätzlichen Abrufinhalte erlaubt.')
        if path=='/service/options':
            shape(query,(),('customer_id','project_id'));result=api.options(actor,query.get('customer_id'),query.get('project_id'))
        elif path=='/service/cases':result=api.listing(actor,query)
        else:
            shape(query,());case_id=path.split('/')[3]
            result=api.history(actor,case_id) if path.endswith('/history') else api.view(actor,case_id)
    else:
        if query:raise Problem(400,'Keine zusätzlichen Schreibfilter erlaubt.')
        try:
            result=api.save(actor,body) if path=='/service/cases' else api.command(actor,path.split('/')[3],path.split('/')[4],body)
        except Problem as error:
            if error.status==409 and isinstance(body.get('request_id'),str) and re.fullmatch(ID,body['request_id']):
                with transaction(office):
                    fresh=_fresh(office,actor)
                    if not office.db.execute('SELECT 1 FROM business_service_requests WHERE user_id=? AND request_id=?',(fresh['id'],body['request_id'])).fetchone():raise Problem(409,error.message,request_resolution='not_accepted') from None
            raise
    return result,200,'application/json'
