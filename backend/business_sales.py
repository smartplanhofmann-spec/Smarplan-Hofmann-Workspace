"""Versioned CRM opportunities with canonical customers, inquiries and projects.

Forecast amounts are not revenue. Adoption and its immutable link commit in the
same transaction. This module sends no messages and accepts no payments/orders.
"""
from datetime import date, datetime, timezone
import hashlib
import json
import re
import sqlite3
import uuid

from core import Problem, canonical
from business_foundation import BusinessFoundation, _fresh, require_permission
from business_operations import identifier, iso_date, text, transaction
from inquiries import Inquiries

FEATURES = ('sales_pipeline',)
STAGES = ('new','qualified','proposal','negotiation','won','lost')
FIELDS = ('title','person_id','stage','expected_net_minor','probability_percent','responsible_id',
          'follow_up_on','expected_close_on','description','closure_reason')
TABLES = tuple('business_sales_'+name for name in ('opportunities','versions','activities','adoptions','requests'))
ID = r'[a-f0-9]{32}'


def schema_statements(binary_type='BYTEA'):
    return [
        '''CREATE TABLE IF NOT EXISTS business_sales_opportunities(
        id TEXT PRIMARY KEY,customer_id TEXT NOT NULL REFERENCES customers(id),
        inquiry_id TEXT UNIQUE REFERENCES inquiries(id),created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_sales_versions(
        opportunity_id TEXT NOT NULL REFERENCES business_sales_opportunities(id),revision INTEGER NOT NULL CHECK(revision>0),
        payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
        PRIMARY KEY(opportunity_id,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_sales_activities(
        id TEXT PRIMARY KEY,opportunity_id TEXT NOT NULL REFERENCES business_sales_opportunities(id),
        supersedes_id TEXT UNIQUE REFERENCES business_sales_activities(id),payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_sales_adoptions(
        opportunity_id TEXT NOT NULL REFERENCES business_sales_opportunities(id),kind TEXT NOT NULL CHECK(kind IN ('project','offer')),
        project_id TEXT NOT NULL REFERENCES projects(id),document_id TEXT REFERENCES business_documents(id),
        payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
        PRIMARY KEY(opportunity_id,kind))''',
        '''CREATE TABLE IF NOT EXISTS business_sales_requests(
        user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,operation TEXT NOT NULL,
        request_json TEXT NOT NULL,request_hash TEXT NOT NULL,result_json TEXT NOT NULL,
        PRIMARY KEY(user_id,request_id))''',
        'CREATE INDEX IF NOT EXISTS business_sales_customer ON business_sales_opportunities(customer_id,created_at,id)',
    ]


def protected_tables(): return TABLES
def runtime_privileges(): return {table:('SELECT','INSERT') for table in TABLES}


def guard_statements(dialect):
    result=[]
    if dialect=='postgresql':
        result.append("CREATE OR REPLACE FUNCTION business_sales_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable sales history'; END; $$")
    for table in TABLES:
        for action in ('UPDATE','DELETE'):
            name=table+'_'+action.lower()+'_guard'
            if dialect=='sqlite': result.append(f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable sales history'); END")
            elif dialect=='postgresql': result.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION business_sales_immutable_guard(); END IF; END $$")
            else: raise ValueError('Unsupported sales storage dialect')
        if dialect=='sqlite':
            kind=table.removeprefix('business_sales_')
            condition={'opportunities':'id=NEW.id OR (inquiry_id IS NOT NULL AND inquiry_id=NEW.inquiry_id)',
                'versions':'opportunity_id=NEW.opportunity_id AND revision=NEW.revision',
                'activities':'id=NEW.id OR (supersedes_id IS NOT NULL AND supersedes_id=NEW.supersedes_id)',
                'adoptions':'opportunity_id=NEW.opportunity_id AND kind=NEW.kind',
                'requests':'user_id=NEW.user_id AND request_id=NEW.request_id'}[kind]
            result.append(f"CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition}) BEGIN SELECT RAISE(ABORT,'immutable sales history'); END")
    return result


def sha(value): return hashlib.sha256(canonical(value).encode()).hexdigest()
def shape(value, required, optional=()):
    if not isinstance(value,dict) or not set(required)<=set(value)<=set(required)|set(optional):
        raise Problem(400,'Vollständige eindeutige Verkaufschancendaten erwartet.')
def integer(value, low, high):
    if type(value) is not int or not low<=value<=high: raise Problem(400,'Gültige ganze Zahl erwartet.')
    return value
def day(value): return None if value is None else iso_date(value)


class Sales:
    def __init__(self,office,clock=None):
        self.office,self.db=office,office.db
        self.clock=clock or (lambda:datetime.now(timezone.utc))
        self.foundation=BusinessFoundation(office)
    def now(self): return self.clock().astimezone(timezone.utc).isoformat(timespec='seconds')
    def gate(self):
        from business_schema import require_capability,state
        require_capability(self.office,'business_sales')
        if state(self.office)['readonly']: raise Problem(423,'Verkaufschancen sind aktuell nur lesbar.')
    def value(self,row):
        value=json.loads(row['payload_json'])
        if sha(value)!=row['sha256']: raise Problem(500,'Verkaufsnachweis ist beschädigt.')
        return value
    def header(self,object_id):
        row=self.db.execute('SELECT * FROM business_sales_opportunities WHERE id=?',(identifier(object_id),)).fetchone()
        if row is None: raise Problem(404,'Verkaufschance nicht verfügbar.')
        return row
    def access(self,actor,header,write=False):
        actor=require_permission(self.office,actor,'contacts.write' if write else 'contacts.read')
        self.foundation._contact_scope(actor,header['customer_id'],'contacts.write' if write else 'contacts.read')
        customer=self.foundation.contact(actor,header['customer_id'])
        if customer['erased_at']: raise Problem(404,'Kontakt nicht verfügbar.')
        inquiry=Inquiries(self.office).get(actor,header['inquiry_id']) if header['inquiry_id'] else None
        for link in self.db.execute('SELECT project_id FROM business_sales_adoptions WHERE opportunity_id=?',(header['id'],)):
            self.office.project(actor,link['project_id'])
        return actor,customer,inquiry
    def receipt(self,actor,operation,data):
        identifier(data['request_id'])
        digest=sha([operation,data])
        row=self.db.execute('SELECT * FROM business_sales_requests WHERE user_id=? AND request_id=?',(actor['id'],data['request_id'])).fetchone()
        if row and (row['operation']!=operation or row['request_hash']!=digest): raise Problem(409,'Vorgangs-ID wurde bereits anders verwendet.')
        return digest,json.loads(row['result_json']) if row else None
    def remember(self,actor,operation,data,digest,result):
        self.db.execute('INSERT INTO business_sales_requests(user_id,request_id,operation,request_json,request_hash,result_json) VALUES(?,?,?,?,?,?)',
            (actor['id'],data['request_id'],operation,canonical(data),digest,canonical(result)))
        return result
    def current(self,object_id):
        row=self.db.execute('SELECT * FROM business_sales_versions WHERE opportunity_id=? ORDER BY revision DESC LIMIT 1',(object_id,)).fetchone()
        if row is None: raise Problem(500,'Verkaufschancenstand fehlt.')
        return self.value(row)
    def sources(self,header,customer,inquiry):
        return dict(customer_id=customer['id'],customer_revision=customer['revision'],customer_updated_at=customer['updated_at'],
            inquiry={key:inquiry[key] for key in ('id','revision','status','project_id','customer_id')} if inquiry else None)
    def view(self,actor,object_id):
        with transaction(self.office):
            header=self.header(object_id); actor,customer,inquiry=self.access(actor,header)
            result=self.current(object_id)
            responsible=self.db.execute('SELECT email FROM users WHERE id=?',(result['responsible_id'],)).fetchone()
            links=[self.value(row) for row in self.db.execute('SELECT * FROM business_sales_adoptions WHERE opportunity_id=? ORDER BY kind',(object_id,))]
            source=self.sources(header,customer,inquiry)
            return dict(result,customer_name=customer['name'],responsible_name=responsible['email'] if responsible else 'Nicht mehr verfügbar',source=source,source_sha256=sha(source),links=links,
                inquiry_subject=inquiry['subject'] if inquiry else None,
                overdue=result['follow_up_on'] is not None and result['follow_up_on']<self.now()[:10] and result['stage'] not in ('won','lost'))
    def listing(self,actor,query='',stage=None,customer_id=None):
        with transaction(self.office):
            actor=require_permission(self.office,actor,'contacts.read'); query=text(query,'Suche',200).casefold()
            if stage is not None and stage not in STAGES: raise Problem(400,'Unbekannte Vertriebsphase.')
            if customer_id is not None: identifier(customer_id)
            items=[]
            for row in self.db.execute('SELECT id,customer_id FROM business_sales_opportunities ORDER BY created_at DESC,id'):
                if customer_id is not None and row['customer_id']!=customer_id: continue
                try: item=self.view(actor,row['id'])
                except Problem as error:
                    if error.status in (403,404): continue
                    raise
                if stage and item['stage']!=stage or query and query not in (item['title']+' '+item['customer_name']).casefold(): continue
                items.append(item)
            open_items=[item for item in items if item['stage'] not in ('won','lost')]
            return dict(items=items,stages=list(STAGES),summary=dict(open_count=len(open_items),overdue_count=sum(item['overdue'] for item in items),
                expected_net_minor=sum(item['expected_net_minor'] for item in open_items),
                weighted_net_minor=sum((item['expected_net_minor']*item['probability_percent']+50)//100 for item in open_items),
                currency='EUR',basis='visible_filtered_open_opportunities',forecast_only=True,as_of=self.now()))
    def options(self,actor,customer_id=None):
        with transaction(self.office):
            actor=require_permission(self.office,actor,'contacts.read')
            contacts=self.foundation.contacts(actor)['items']
            customers=[dict(id=item['id'],name=item['name'],persons=item['persons']) for item in contacts if item['active'] and not item['erased_at']]
            if customer_id is not None:
                identifier(customer_id)
                if customer_id not in {item['id'] for item in customers}: raise Problem(404,'Kontakt nicht verfügbar.')
            people=[]
            for row in self.db.execute('SELECT id,email FROM users WHERE active=1 ORDER BY email,id'):
                if customer_id is None and row['id']!=actor['id']: continue
                try:
                    require_permission(self.office,dict(id=row['id']),'contacts.read')
                    if customer_id:self.foundation._contact_scope(dict(id=row['id']),customer_id)
                except Problem as error:
                    if error.status in (401,403,404): continue
                    raise
                people.append(dict(row))
            return dict(customer_id=customer_id,customers=customers,responsibles=people,stages=list(STAGES))
    def save(self,actor,data):
        shape(data,('request_id','revision','customer_id','inquiry_id',*FIELDS),('id',))
        object_id=identifier(data['id']) if 'id' in data else uuid.uuid4().hex
        customer_id=identifier(data['customer_id']); inquiry_id=identifier(data['inquiry_id']) if data['inquiry_id'] is not None else None
        with transaction(self.office):
            old=self.header(object_id) if 'id' in data else dict(id=object_id,customer_id=customer_id,inquiry_id=inquiry_id)
            if old['customer_id']!=customer_id or old['inquiry_id']!=inquiry_id: raise Problem(409,'Kunden- und Anfragebindung bleiben unverändert.')
            actor,customer,inquiry=self.access(actor,old,True)
            operation='save:'+str(data.get('id')); digest,replay=self.receipt(actor,operation,data)
            if replay:
                self.access(actor,self.header(replay['id']))
                return replay
            self.gate()
            if not customer['active']: raise Problem(409,'Kontakt zuerst reaktivieren.')
            if inquiry and inquiry['customer_id'] and inquiry['customer_id']!=customer_id: raise Problem(409,'Anfrage gehört zu einem anderen Kunden.')
            previous=self.current(object_id) if 'id' in data else None
            if integer(data['revision'],0,10**9)!=(previous['revision'] if previous else 0): raise Problem(409,'Verkaufschance wurde inzwischen geändert.')
            if previous is None and inquiry_id and self.db.execute('SELECT 1 FROM business_sales_opportunities WHERE inquiry_id=?',(inquiry_id,)).fetchone():
                raise Problem(409,'Für diese Anfrage besteht bereits eine Verkaufschance.')
            value={key:data[key] for key in FIELDS}
            for key,maximum in (('title',300),('description',10000),('closure_reason',2000)):
                value[key]=text(value[key],key,maximum,required=key=='title')
            if value['stage'] not in STAGES: raise Problem(400,'Gültige Vertriebsphase auswählen.')
            integer(value['expected_net_minor'],0,10**12); integer(value['probability_percent'],0,100)
            if value['stage']=='won' and value['probability_percent']!=100 or value['stage']=='lost' and value['probability_percent']!=0:
                raise Problem(400,'Gewonnen benötigt 100 %, verloren 0 %.')
            if value['stage'] in ('won','lost') and not value['closure_reason']: raise Problem(400,'Abschlussentscheidung begründen.')
            value['follow_up_on']=day(value['follow_up_on']); value['expected_close_on']=day(value['expected_close_on'])
            responsible=identifier(value['responsible_id']); require_permission(self.office,dict(id=responsible),'contacts.read')
            self.foundation._contact_scope(dict(id=responsible),customer_id)
            person=None
            if value['person_id'] is not None:
                identifier(value['person_id']); person=next((item for item in customer['persons'] if item['id']==value['person_id']),None)
                if person is None: raise Problem(409,'Ansprechpartner gehört nicht zum aktuellen Kontakt.')
            stamp=self.now(); value.update(id=object_id,revision=data['revision']+1,customer_id=customer_id,inquiry_id=inquiry_id,
                customer_snapshot=dict(id=customer_id,name=customer['name'],revision=customer['revision']),person_snapshot=person,
                created_by=actor['id'],created_at=stamp,currency='EUR')
            if previous is None:self.db.execute('INSERT INTO business_sales_opportunities(id,customer_id,inquiry_id,created_by,created_at) VALUES(?,?,?,?,?)',
                (object_id,customer_id,inquiry_id,actor['id'],stamp))
            self.db.execute('INSERT INTO business_sales_versions(opportunity_id,revision,payload_json,sha256,created_by,created_at) VALUES(?,?,?,?,?,?)',
                (object_id,value['revision'],canonical(value),sha(value),actor['id'],stamp))
            self.office.audit(actor,'sales.opportunity.saved',object_id)
            return self.remember(actor,operation,data,digest,value)
    def history(self,actor,object_id):
        with transaction(self.office):
            self.access(actor,self.header(object_id))
            return dict(items=[self.value(row) for row in self.db.execute('SELECT * FROM business_sales_versions WHERE opportunity_id=? ORDER BY revision',(object_id,))])
    def activities(self,actor,object_id):
        with transaction(self.office):
            self.access(actor,self.header(object_id))
            return dict(items=[self.value(row) for row in self.db.execute('SELECT * FROM business_sales_activities WHERE opportunity_id=? ORDER BY created_at,id',(object_id,))])
    def activity(self,actor,object_id,data):
        shape(data,('request_id','kind','text','occurred_on','supersedes_id','correction_reason'))
        with transaction(self.office):
            actor,_,_=self.access(actor,self.header(object_id),True); operation='activity:'+object_id
            digest,replay=self.receipt(actor,operation,data)
            if replay:return replay
            self.gate()
            if data['kind'] not in ('note','call','email','meeting'): raise Problem(400,'Gültige Aktivitätsart angeben.')
            value=dict(kind=data['kind'],text=text(data['text'],'Aktivität',10000,required=True),occurred_on=iso_date(data['occurred_on']),
                supersedes_id=data['supersedes_id'],correction_reason=text(data['correction_reason'],'Korrekturgrund',2000))
            if value['occurred_on']>self.now()[:10]: raise Problem(400,'Erfolgte Aktivität darf nicht in der Zukunft liegen; dafür Wiedervorlage nutzen.')
            if value['supersedes_id'] is not None:
                old=self.db.execute('SELECT * FROM business_sales_activities WHERE id=?',(identifier(value['supersedes_id']),)).fetchone()
                if not old or old['opportunity_id']!=object_id: raise Problem(404,'Zu korrigierende Aktivität gehört nicht zur Chance.')
                if not value['correction_reason']: raise Problem(400,'Korrekturgrund angeben.')
                if self.db.execute('SELECT 1 FROM business_sales_activities WHERE supersedes_id=?',(old['id'],)).fetchone(): raise Problem(409,'Aktivität wurde bereits korrigiert.')
            stamp=self.now(); value.update(id=uuid.uuid4().hex,opportunity_id=object_id,created_by=actor['id'],created_at=stamp)
            self.db.execute('INSERT INTO business_sales_activities(id,opportunity_id,supersedes_id,payload_json,sha256,created_by,created_at) VALUES(?,?,?,?,?,?,?)',
                (value['id'],object_id,value['supersedes_id'],canonical(value),sha(value),actor['id'],stamp))
            return self.remember(actor,operation,data,digest,value)
    def adoption(self,actor,object_id,kind,data):
        if kind not in ('project','offer'): raise Problem(400,'Unbekannte Übernahmeart.')
        required=('request_id','revision','source_sha256','confirmation')
        shape(data,required+(('project_id','project_name') if kind=='project' else ('title','issue_date','due_date','positions')))
        with transaction(self.office):
            header=self.header(object_id); actor,customer,inquiry=self.access(actor,header,True)
            current=self.current(object_id); operation=kind+':'+object_id
            digest,replay=self.receipt(actor,operation,data)
            existing=self.db.execute('SELECT * FROM business_sales_adoptions WHERE opportunity_id=? AND kind=?',(object_id,kind)).fetchone()
            if replay:
                self._adoption_rights(actor,kind,replay['project_id']);return replay
            if existing: raise Problem(409,'Diese Chance wurde bereits übernommen; bestehende Verknüpfung verwenden.')
            self.gate()
            if data['confirmation'] is not True: raise Problem(400,'Konkrete Übernahme ausdrücklich bestätigen.')
            if integer(data['revision'],1,10**9)!=current['revision'] or data['source_sha256']!=sha(self.sources(header,customer,inquiry)):
                raise Problem(409,'Chance oder Kunden-/Anfragequelle wurde geändert; neu prüfen.')
            if not customer['active'] or current['stage']=='lost': raise Problem(409,'Archivierten Kontakt oder verlorene Chance zuerst reaktivieren.')
            stamp=self.now(); document_id=None
            if kind=='project':
                require_permission(self.office,actor,'projects.manage');self.office.require(actor,('owner',))
                name=text(data['project_name'],'Projektname',300,required=True)
                selected=identifier(data['project_id']) if data['project_id'] is not None else None
                if inquiry and inquiry['status']=='converted':
                    if selected is not None and selected!=inquiry['project_id']: raise Problem(409,'Anfrage wurde bereits in ein anderes Projekt übernommen.')
                    project_id=inquiry['project_id']
                elif inquiry:
                    if selected is not None: raise Problem(409,'Nicht übernommene Anfrage über ihren bestehenden Konvertierungsweg übernehmen.')
                    converted=Inquiries(self.office).convert(actor,inquiry['id'],dict(request_id=uuid.uuid5(uuid.NAMESPACE_URL,'sales-project:'+object_id).hex,
                        revision=inquiry['revision'],project_name=name,customer_id=customer['id']))
                    project_id=converted['project']['id']
                elif selected is not None: project_id=selected
                else:
                    # Canonical project table, same owner/customer policy as
                    # Office.add_project, without its premature SQLite commit.
                    project_id=uuid.uuid4().hex
                    self.db.execute('INSERT INTO projects(id,name,customer,customer_id) VALUES(?,?,?,?)',(project_id,name,customer['name'],customer['id']))
                    self.office.audit(actor,'project.created',project_id)
                project=self.office.project(actor,project_id)
                if project['customer_id']!=customer['id']: raise Problem(409,'Projekt gehört nicht zum Kunden dieser Chance.')
            else:
                link=self.db.execute("SELECT project_id FROM business_sales_adoptions WHERE opportunity_id=? AND kind='project'",(object_id,)).fetchone()
                if not link: raise Problem(409,'Zuerst das Projekt übernehmen oder verknüpfen.')
                project_id=link['project_id'];self._adoption_rights(actor,kind,project_id)
                if self.office.project(actor,project_id)['customer_id']!=customer['id']:
                    raise Problem(409,'Projektkunde wurde seit der Übernahme geändert.')
                from business_documents import Documents
                documents=Documents(self.office)
                if not isinstance(data['positions'],list) or not 1<=len(data['positions'])<=50: raise Problem(400,'Ein bis 50 bestätigte Katalogpositionen auswählen.')
                positions=[]
                for selected in data['positions']:
                    shape(selected,('article_id','article_revision','quantity'))
                    article=documents.catalog_item(actor,'business_articles',identifier(selected['article_id']))
                    if not article['active'] or integer(selected['article_revision'],1,10**9)!=article['revision']: raise Problem(409,'Katalogposition wurde geändert oder deaktiviert.')
                    positions.append(dict(description=article['name'],quantity=selected['quantity'],unit=article['unit'],unit_price_net=article['unit_price_net'],tax_rate=article['tax_rate'],kind=article['kind']))
                document=documents.create(actor,dict(request_id=uuid.uuid5(uuid.NAMESPACE_URL,'sales-offer:'+object_id).hex,project_id=project_id,kind='offer',
                    title=data['title'],issue_date=data['issue_date'],due_date=data['due_date'],positions=positions))
                document_id=document['id']
            result=dict(opportunity_id=object_id,kind=kind,project_id=project_id,document_id=document_id,
                opportunity_revision=current['revision'],source_snapshot=self.sources(header,customer,inquiry),
                source_sha256=data['source_sha256'],created_by=actor['id'],created_at=stamp)
            self.db.execute('INSERT INTO business_sales_adoptions(opportunity_id,kind,project_id,document_id,payload_json,sha256,created_by,created_at) VALUES(?,?,?,?,?,?,?,?)',
                (object_id,kind,project_id,document_id,canonical(result),sha(result),actor['id'],stamp))
            self.office.audit(actor,'sales.'+kind+'.adopted',object_id)
            return self.remember(actor,operation,data,digest,result)
    def _adoption_rights(self,actor,kind,project_id):
        require_permission(self.office,actor,'projects.manage',project_id)
        if kind=='offer':
            from business_organization import module_enabled
            require_permission(self.office,actor,'finance.read',project_id);require_permission(self.office,actor,'finance.write',project_id)
            if not module_enabled(self.office,'documents'): raise Problem(423,'Kaufmännische Belege sind deaktiviert.')


def validate_integrity(office):
    api,db=Sales(office),office.db
    try:
        headers={row['id']:row for row in db.execute('SELECT * FROM business_sales_opportunities')}
        versions={}
        for row in db.execute('SELECT * FROM business_sales_versions ORDER BY opportunity_id,revision'):
            value=api.value(row); header=headers[row['opportunity_id']]
            count=versions.get(row['opportunity_id'],0)+1
            if (row['revision']!=count or value['revision']!=count or value['id']!=header['id'] or value['customer_id']!=header['customer_id'] or
                value['inquiry_id']!=header['inquiry_id'] or value['created_by']!=row['created_by'] or value['created_at']!=row['created_at'] or value['stage'] not in STAGES):
                raise ValueError('Invalid opportunity revision')
            integer(value['expected_net_minor'],0,10**12);integer(value['probability_percent'],0,100)
            if value['stage']=='won' and value['probability_percent']!=100 or value['stage']=='lost' and value['probability_percent']!=0: raise ValueError('Invalid closure probability')
            versions[row['opportunity_id']]=count
        if set(headers)!=set(versions): raise ValueError('Incomplete opportunity history')
        activities={}
        for row in db.execute('SELECT * FROM business_sales_activities'):
            value=api.value(row)
            if (any(value[key]!=row[key] for key in ('id','opportunity_id','supersedes_id','created_by','created_at')) or
                    value['kind'] not in ('note','call','email','meeting') or not value['text']): raise ValueError('Invalid activity binding')
            iso_date(value['occurred_on'])
            activities[row['id']]=value
        for value in activities.values():
            if value['supersedes_id']:
                prior=activities[value['supersedes_id']]
                if prior['opportunity_id']!=value['opportunity_id'] or not value['correction_reason']: raise ValueError('Invalid activity correction')
                seen={value['id']}
                while prior:
                    if prior['id'] in seen:raise ValueError('Cyclic activity correction')
                    seen.add(prior['id']);prior=activities[prior['supersedes_id']] if prior['supersedes_id'] else None
        for row in db.execute('SELECT * FROM business_sales_adoptions'):
            value=api.value(row); header=headers[row['opportunity_id']]
            if any(value[key]!=row[key] for key in ('opportunity_id','kind','project_id','document_id','created_by','created_at')): raise ValueError('Invalid adoption binding')
            if sha(value['source_snapshot'])!=value['source_sha256'] or value['source_snapshot']['customer_id']!=header['customer_id']:
                raise ValueError('Invalid adoption source proof')
            project=db.execute('SELECT customer_id FROM projects WHERE id=?',(row['project_id'],)).fetchone()
            if project['customer_id']!=header['customer_id'] or not 1<=value['opportunity_revision']<=versions[header['id']]: raise ValueError('Foreign adoption source')
            if row['kind']=='offer':
                doc=db.execute('SELECT project_id,customer_id,kind FROM business_documents WHERE id=?',(row['document_id'],)).fetchone()
                if doc is None or doc['project_id']!=row['project_id'] or doc['customer_id']!=header['customer_id'] or doc['kind']!='offer': raise ValueError('Invalid adopted offer')
            elif row['document_id'] is not None: raise ValueError('Unexpected adopted document')
        for row in db.execute('SELECT * FROM business_sales_requests'):
            request=json.loads(row['request_json']);result=json.loads(row['result_json'])
            if row['request_id']!=request['request_id'] or sha([row['operation'],request])!=row['request_hash']: raise ValueError('Invalid sales receipt')
            if result['created_by']!=row['user_id']: raise ValueError('Foreign sales receipt')
            operation,target=row['operation'].split(':',1)
            if operation=='save':
                proof=db.execute('SELECT * FROM business_sales_versions WHERE opportunity_id=? AND revision=?',(result['id'],result['revision'])).fetchone()
                if (target!=str(request.get('id')) or result['revision']!=request['revision']+1 or
                        result['customer_id']!=request['customer_id'] or result['inquiry_id']!=request['inquiry_id'] or
                        request.get('id',result['id'])!=result['id']): raise ValueError('Sales save receipt differs from original')
            elif operation=='activity':
                proof=db.execute('SELECT * FROM business_sales_activities WHERE id=?',(result['id'],)).fetchone()
                if result['opportunity_id']!=target: raise ValueError('Foreign activity receipt')
            elif operation in ('project','offer'):
                proof=db.execute('SELECT * FROM business_sales_adoptions WHERE opportunity_id=? AND kind=?',(target,operation)).fetchone()
                if (result['opportunity_id']!=target or result['kind']!=operation or
                        result['opportunity_revision']!=request['revision'] or result['source_sha256']!=request['source_sha256']):
                    raise ValueError('Foreign adoption receipt')
            else: raise ValueError('Unknown sales receipt')
            if proof is None or api.value(proof)!=result: raise ValueError('Sales receipt differs from immutable result')
    except (KeyError,TypeError,ValueError,Problem) as error: raise ValueError('Invalid sales history') from error
    return True


def methods(path):
    if path=='/sales/options':return 'GET'
    if path=='/sales/opportunities':return 'GET, POST'
    if re.fullmatch(r'/sales/opportunities/'+ID,path):return 'GET'
    if re.fullmatch(r'/sales/opportunities/'+ID+r'/history',path):return 'GET'
    if re.fullmatch(r'/sales/opportunities/'+ID+r'/activities',path):return 'GET, POST'
    if re.fullmatch(r'/sales/opportunities/'+ID+r'/(?:project|offer)',path):return 'POST'
    return None


def dispatch(office,actor,path,method,data):
    allowed=methods(path)
    if allowed is None:return None
    if method not in allowed.split(', '):raise Problem(405,'Methode nicht erlaubt.')
    if not isinstance(data,dict):raise Problem(400,'JSON-Objekt erwartet.')
    api=Sales(office);query=data.get('_query',{});body={key:value for key,value in data.items() if key!='_query'}
    if method=='GET':
        if body:raise Problem(400,'Keine Abrufinhalte erlaubt.')
        if path=='/sales/opportunities':
            shape(query,(),('q','stage','customer_id'));result=api.listing(actor,query.get('q',''),query.get('stage'),query.get('customer_id'))
        elif path=='/sales/options':
            shape(query,(),('customer_id',));result=api.options(actor,query.get('customer_id'))
        else:
            shape(query,());parts=path.split('/');object_id=parts[3]
            result=api.history(actor,object_id) if path.endswith('/history') else api.activities(actor,object_id) if path.endswith('/activities') else api.view(actor,object_id)
    else:
        if query:raise Problem(400,'Keine zusätzlichen Schreibfilter erlaubt.')
        try:
            if path=='/sales/opportunities':result=api.save(actor,body)
            else:
                object_id,action=path.split('/')[3:]
                result=api.activity(actor,object_id,body) if action=='activities' else api.adoption(actor,object_id,action,body)
        except Problem as error:
            if error.status==409 and isinstance(body.get('request_id'),str) and re.fullmatch(ID,body['request_id']):
                with transaction(office):
                    fresh=_fresh(office,actor)
                    if not office.db.execute('SELECT 1 FROM business_sales_requests WHERE user_id=? AND request_id=?',(fresh['id'],body['request_id'])).fetchone():
                        raise Problem(409,error.message,request_resolution='not_accepted') from None
            raise
    return result,200,'application/json'
