"""Company-defined typed additions to contacts, projects and assets.

Definitions and values retain explicit historical revisions. These values never
participate in core authorization, accounting, payroll or metric calculations.
"""
from datetime import datetime,timezone
import json
import re
import sqlite3
import unicodedata
import uuid

from core import Problem,canonical
from business_foundation import BusinessFoundation,require_permission
from business_operations import identifier,iso_date,text,transaction
from business_personnel_workflow import _sha,_integer

FEATURES=('custom_fields',)
TABLES=('business_custom_field_definitions','business_custom_field_values','business_custom_field_requests')
ENTITY_TYPES=('contact','project','asset')
FIELD_TYPES=('text','number','date','choice','boolean')
ID=r'[a-f0-9]{32}'
DEFINITION_FIELDS=('entity_type','label','help_text','field_type','required','active','options')


def _shape(data,allowed,required=()):
    if not isinstance(data,dict) or set(data)-set(allowed) or not set(required)<=set(data):
        raise Problem(400,'Unvollständige oder unbekannte Felder im Zusatzfeld-Vorgang.')


def schema_statements(binary_type='BYTEA'):
    return ["""CREATE TABLE IF NOT EXISTS business_custom_field_definitions(
        id TEXT NOT NULL,revision INTEGER NOT NULL CHECK(revision>0),
        entity_type TEXT NOT NULL CHECK(entity_type IN ('contact','project','asset')),
        payload_json TEXT NOT NULL,content_hash TEXT NOT NULL,previous_hash TEXT,
        created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,PRIMARY KEY(id,revision))""",
        """CREATE TABLE IF NOT EXISTS business_custom_field_values(
        entity_type TEXT NOT NULL CHECK(entity_type IN ('contact','project','asset')),entity_id TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK(revision>0),payload_json TEXT NOT NULL,content_hash TEXT NOT NULL,
        previous_hash TEXT,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
        PRIMARY KEY(entity_type,entity_id,revision))""",
        """CREATE TABLE IF NOT EXISTS business_custom_field_requests(
        user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,request_hash TEXT NOT NULL,
        result_json TEXT NOT NULL,PRIMARY KEY(user_id,request_id))""",
        'CREATE INDEX IF NOT EXISTS business_custom_field_type ON business_custom_field_definitions(entity_type,id,revision)']


def protected_tables():
    return TABLES


def runtime_privileges():
    return {table:('SELECT','INSERT') for table in TABLES}


def guard_statements(dialect):
    if dialect=='sqlite':
        result=[f"CREATE TRIGGER IF NOT EXISTS {table}_{op.lower()}_guard BEFORE {op} ON {table} BEGIN SELECT RAISE(ABORT,'immutable custom field history'); END"
            for table in TABLES for op in ('UPDATE','DELETE')]
        conditions=('id=NEW.id AND revision=NEW.revision',
            'entity_type=NEW.entity_type AND entity_id=NEW.entity_id AND revision=NEW.revision',
            'user_id=NEW.user_id AND request_id=NEW.request_id')
        for table,condition in zip(TABLES,conditions):
            result.append(f"CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition}) BEGIN SELECT RAISE(ABORT,'immutable custom field history'); END")
        return result
    if dialect=='postgresql':
        result=["CREATE OR REPLACE FUNCTION business_custom_field_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable custom field history'; END; $$"]
        for table in TABLES:
            for op in ('UPDATE','DELETE'):
                name=table+'_'+op.lower()+'_guard'
                result.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} BEFORE {op} ON {table} FOR EACH ROW EXECUTE FUNCTION business_custom_field_immutable_guard(); END IF; END $$")
        return result
    raise ValueError('Unknown custom field dialect')


def _definition(data):
    _shape(data,DEFINITION_FIELDS,DEFINITION_FIELDS)
    if data['entity_type'] not in ENTITY_TYPES or data['field_type'] not in FIELD_TYPES:
        raise Problem(400,'Unbekannte Zusatzfeld-Zuordnung oder Feldart.')
    result=dict(data,label=text(data['label'],'Feldname',120,required=True),help_text=text(data['help_text'],'Ausfüllhilfe',1000))
    for key in ('required','active'):
        if type(data[key]) is not bool:
            raise Problem(400,'Pflichtfeld und Aktivierung ausdrücklich angeben.')
    if not isinstance(data['options'],list) or len(data['options'])>100:
        raise Problem(400,'Höchstens hundert Auswahlmöglichkeiten angeben.')
    options=[];seen=set();labels=set()
    for option in data['options']:
        _shape(option,('id','label','active'),('id','label','active'))
        identifier(option['id'],'Auswahl-ID')
        label=text(option['label'],'Auswahlbezeichnung',120,required=True)
        normalized=unicodedata.normalize('NFKC',label).casefold()
        if option['id'] in seen or type(option['active']) is not bool or normalized in labels:
            raise Problem(400,'Auswahlmöglichkeiten müssen eindeutig bezeichnet und ausdrücklich aktiviert sein.')
        seen.add(option['id']);labels.add(normalized)
        options.append(dict(id=option['id'],label=label,active=option['active']))
    if data['field_type']=='choice':
        if not options or data['active'] and not any(option['active'] for option in options):
            raise Problem(400,'Ein aktives Auswahlfeld braucht mindestens eine aktive Auswahl.')
    elif options:
        raise Problem(400,'Nur Auswahlfelder besitzen Auswahlmöglichkeiten.')
    result['options']=options
    return result


def _value(definition,value,previous=None):
    if value is None:
        if definition['required']:
            raise Problem(400,'Pflichtfeld „'+definition['label']+'“ ausfüllen.')
        return None
    kind=definition['field_type']
    if kind=='text':
        if not isinstance(value,str) or len(value)>4000 or any(ord(char)<32 and char not in '\n\t' for char in value):
            raise Problem(400,'Textfeld benötigt höchstens 4.000 gültige Zeichen.')
        if definition['required'] and not value.strip():
            raise Problem(400,'Pflichtfeld „'+definition['label']+'“ ausfüllen.')
    elif kind=='number':
        if not isinstance(value,str) or not re.fullmatch(r'-?(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,6})?',value):
            raise Problem(400,'Zahl als exakten Dezimaltext mit höchstens zwölf Vor- und sechs Nachkommastellen angeben.')
    elif kind=='date':
        iso_date(value,'Zusatzfeld-Datum')
    elif kind=='boolean':
        if type(value) is not bool:
            raise Problem(400,'Ja oder Nein ausdrücklich auswählen.')
    else:
        selected=next((item for item in definition['options'] if item['id']==value),None)
        if selected is None or not selected['active'] and previous!=value:
            raise Problem(400,'Eine aktive Auswahl verwenden; archivierte Bestandsauswahl bleibt unverändert lesbar.')
    return value


class CustomFields:
    def __init__(self,office,*,clock=None):
        self.office,self.db=office,office.db
        self.foundation=BusinessFoundation(office)
        self.clock=clock or (lambda:datetime.now(timezone.utc))

    def now(self):
        return self.clock().astimezone(timezone.utc).isoformat(timespec='seconds')

    def _serialize(self):
        # Serialize definition changes with values across PostgreSQL connections.
        # SQLite's BEGIN IMMEDIATE already provides the same write ordering.
        if not isinstance(self.db,sqlite3.Connection):
            self.db.execute('SELECT pg_advisory_xact_lock(129842776,18494301)')

    def _event(self,row,definition=False):
        keys=('id','revision','entity_type','previous_hash','created_by','created_at') if definition else (
            'entity_type','entity_id','revision','previous_hash','created_by','created_at')
        envelope={key:row[key] for key in keys};envelope['payload']=json.loads(row['payload_json'])
        if _sha(envelope)!=row['content_hash']:
            raise Problem(500,'Integritätsprüfung der Zusatzfeldhistorie fehlgeschlagen.')
        payload=envelope.pop('payload')
        return dict(envelope,**payload,content_hash=row['content_hash'])

    def _definitions(self,entity_type=None):
        rows=self.db.execute('SELECT d.* FROM business_custom_field_definitions d WHERE NOT EXISTS '
            '(SELECT 1 FROM business_custom_field_definitions n WHERE n.id=d.id AND n.revision>d.revision) ORDER BY d.created_at,d.id').fetchall()
        return [self._event(row,True) for row in rows if entity_type is None or row['entity_type']==entity_type]

    def _definition_row(self,definition_id,revision=None):
        identifier(definition_id)
        if revision is None:
            row=self.db.execute('SELECT * FROM business_custom_field_definitions WHERE id=? ORDER BY revision DESC LIMIT 1',(definition_id,)).fetchone()
        else:
            row=self.db.execute('SELECT * FROM business_custom_field_definitions WHERE id=? AND revision=?',(definition_id,revision)).fetchone()
        if row is None:
            raise Problem(404,'Zusatzfelddefinition nicht verfügbar.')
        return self._event(row,True)

    def _values(self,entity_type,entity_id):
        row=self.db.execute('SELECT * FROM business_custom_field_values WHERE entity_type=? AND entity_id=? ORDER BY revision DESC LIMIT 1',(entity_type,entity_id)).fetchone()
        return self._event(row) if row else dict(entity_type=entity_type,entity_id=entity_id,revision=0,
            previous_hash=None,content_hash=None,created_by=None,created_at=None,definitions_hash=None,values={})

    def _entity(self,actor,entity_type,entity_id,write=False):
        identifier(entity_id)
        if entity_type not in ENTITY_TYPES:
            raise Problem(400,'Unbekannte Zusatzfeld-Zuordnung.')
        if entity_type=='contact':
            fresh=self.foundation._contact_scope(actor,entity_id,'contacts.write' if write else 'contacts.read')
            row=self.db.execute('SELECT id,name,active FROM customers WHERE id=?',(entity_id,)).fetchone()
            if row is None:
                raise Problem(404,'Kontakt nicht verfügbar.')
            if write and row['active']!=1:
                raise Problem(409,'Archivierte Kontakte bleiben lesbar; Zusatzfelder können nicht geändert werden.')
            return fresh,dict(id=entity_id,entity_type=entity_type,label=row['name'],project_id=None)
        if entity_type=='project':
            fresh=require_permission(self.office,actor,'projects.manage' if write else 'documents.read',entity_id)
            row=self.db.execute('SELECT id,name FROM projects WHERE id=?',(entity_id,)).fetchone()
            return fresh,dict(id=entity_id,entity_type=entity_type,label=row['name'],project_id=entity_id)
        row=self.db.execute('SELECT id,project_id,payload_json FROM business_assets WHERE id=?',(entity_id,)).fetchone()
        if row is None:
            raise Problem(404,'Gerät nicht verfügbar.')
        fresh=require_permission(self.office,actor,'documents.write' if write else 'documents.read',row['project_id'])
        payload=json.loads(row['payload_json'])
        if write and payload.get('active',True) is not True:
            raise Problem(409,'Archivierte Geräte bleiben lesbar; Zusatzfelder können nicht geändert werden.')
        return fresh,dict(id=entity_id,entity_type=entity_type,label=payload['name'],project_id=row['project_id'])

    def definitions(self,actor,query=None):
        _shape(query or {},('entity_type',))
        with transaction(self.office):
            require_permission(self.office,actor,'settings.manage')
            kind=(query or {}).get('entity_type')
            if kind is not None and kind not in ENTITY_TYPES:
                raise Problem(400,'Unbekannte Zusatzfeld-Zuordnung.')
            return dict(items=self._definitions(kind))

    def entity(self,actor,entity_type,entity_id):
        with transaction(self.office):
            fresh,entity=self._entity(actor,entity_type,entity_id)
            definitions=self._definitions(entity_type);current=self._values(entity_type,entity_id)
            missing=[definition['id'] for definition in definitions if definition['active'] and definition['required']
                and (definition['id'] not in current['values'] or current['values'][definition['id']]['value'] is None
                    or definition['field_type']=='text' and not current['values'][definition['id']]['value'].strip())]
            try:
                self._entity(fresh,entity_type,entity_id,True)
                from business_schema import require_capability
                require_capability(self.office,'business_custom_fields')
                writable=True
            except Problem as error:
                if error.status not in (403,409):raise
                writable=False
            self._entity(fresh,entity_type,entity_id)
            return dict(entity=entity,definitions=definitions,definitions_hash=_sha(definitions),current=current,
                missing_required=missing,complete=not missing,can_write=writable)

    def _request(self,actor,data,operation):
        identifier(data['request_id']);fingerprint=_sha([operation,data])
        row=self.db.execute('SELECT * FROM business_custom_field_requests WHERE user_id=? AND request_id=?',(actor['id'],data['request_id'])).fetchone()
        if row and row['request_hash']!=fingerprint:
            raise Problem(409,'Vorgangs-ID wurde mit anderem Inhalt verwendet.')
        return fingerprint,json.loads(row['result_json']) if row else None

    def _remember(self,actor,data,fingerprint,result):
        self.db.execute('INSERT INTO business_custom_field_requests(user_id,request_id,request_hash,result_json) VALUES(?,?,?,?)',
            (actor['id'],data['request_id'],fingerprint,canonical(result)))

    def save_definition(self,actor,data):
        _shape(data,('request_id','id','revision','definition','reason'),('request_id','revision','definition','reason'))
        if 'id' in data:identifier(data['id'])
        definition=_definition(data['definition'])
        with transaction(self.office):
            self._serialize();fresh=require_permission(self.office,actor,'settings.manage')
            from business_schema import require_capability
            require_capability(self.office,'business_custom_fields')
            fingerprint,prior=self._request(fresh,data,'definition')
            if prior is not None:return prior
            try:
                previous=self._definition_row(data['id']) if data.get('id') else None
                if _integer(data['revision'])!=(previous['revision'] if previous else 0):
                    raise Problem(409,'Die Felddefinition wurde geändert. Neu laden.')
                reason=text(data['reason'],'Änderungsgrund',1000,required=bool(previous))
                if previous and previous['entity_type']!=definition['entity_type']:
                    raise Problem(400,'Zuordnung einer bestehenden Felddefinition darf nicht gewechselt werden.')
                used=[]
                if previous:
                    for row in self.db.execute('SELECT payload_json FROM business_custom_field_values WHERE entity_type=?',(previous['entity_type'],)).fetchall():
                        values=json.loads(row['payload_json'])['values']
                        if previous['id'] in values and values[previous['id']]['value'] is not None:
                            used.append(values[previous['id']]['value'])
                    if used and previous['field_type']!=definition['field_type']:
                        raise Problem(409,'Dieses Feld hat gespeicherte Werte. Für eine neue Feldart das bisherige Feld archivieren und ein neues anlegen.')
                    if definition['field_type']=='choice' and any(value not in {item['id'] for item in definition['options']} for value in used):
                        raise Problem(409,'Verwendete Auswahlen müssen erhalten bleiben; sie können archiviert werden.')
                existing=self._definitions(definition['entity_type'])
                if not previous and len(existing)>=100:
                    raise Problem(409,'Höchstens hundert Definitionen je Zuordnung sind unterstützt.')
                name=unicodedata.normalize('NFKC',definition['label']).casefold()
                if definition['active'] and any(item['active'] and item['id']!=(previous['id'] if previous else None)
                        and unicodedata.normalize('NFKC',item['label']).casefold()==name for item in existing):
                    raise Problem(409,'Eine aktive Felddefinition mit dieser Bezeichnung besteht bereits.')
                object_id=previous['id'] if previous else uuid.uuid4().hex
                payload={key:definition[key] for key in DEFINITION_FIELDS if key!='entity_type'};payload['reason']=reason
                envelope=dict(id=object_id,revision=previous['revision']+1 if previous else 1,entity_type=definition['entity_type'],
                    previous_hash=previous['content_hash'] if previous else None,created_by=fresh['id'],created_at=self.now(),payload=payload)
                require_permission(self.office,fresh,'settings.manage')
                self.db.execute('INSERT INTO business_custom_field_definitions(id,revision,entity_type,payload_json,content_hash,previous_hash,created_by,created_at) VALUES(?,?,?,?,?,?,?,?)',
                    (object_id,envelope['revision'],definition['entity_type'],canonical(payload),_sha(envelope),envelope['previous_hash'],fresh['id'],envelope['created_at']))
                result=self._definition_row(object_id);self._remember(fresh,data,fingerprint,result)
                self.office.audit(fresh,'custom_field.definition.saved',object_id)
                return result
            except Problem as error:
                if error.status==409:raise Problem(409,error.message,request_resolution='not_accepted') from None
                raise

    def save_values(self,actor,entity_type,entity_id,data):
        _shape(data,('request_id','revision','definitions_hash','values','reason'),('request_id','revision','definitions_hash','values','reason'))
        if not isinstance(data['values'],dict) or len(data['values'])>100 or not isinstance(data['definitions_hash'],str) or not re.fullmatch(r'[a-f0-9]{64}',data['definitions_hash']):
            raise Problem(400,'Geprüfte Definitionen und gültige Zusatzfelder angeben.')
        with transaction(self.office):
            self._serialize();fresh,_=self._entity(actor,entity_type,entity_id,True);self._entity(fresh,entity_type,entity_id)
            from business_schema import require_capability
            require_capability(self.office,'business_custom_fields')
            fingerprint,prior=self._request(fresh,data,'values:'+entity_type+':'+entity_id)
            if prior is not None:return prior
            try:
                current=self._values(entity_type,entity_id);definitions=self._definitions(entity_type)
                if _integer(data['revision'])!=current['revision'] or data['definitions_hash']!=_sha(definitions):
                    raise Problem(409,'Zusatzwerte oder Felddefinitionen wurden geändert. Neu laden.')
                active={item['id']:item for item in definitions if item['active']}
                if set(data['values'])!=set(active):
                    raise Problem(400,'Alle aktiven Zusatzfelder ausdrücklich ausfüllen oder als leer angeben; archivierte Felder bleiben unverändert.')
                values=dict(current['values'])
                for field_id,definition in active.items():
                    value=_value(definition,data['values'][field_id],values.get(field_id,{}).get('value'))
                    values[field_id]=dict(definition=definition,value=value)
                reason=text(data['reason'],'Änderungsgrund',1000,required=current['revision']>0)
                payload=dict(definitions_hash=data['definitions_hash'],definitions=definitions,values=values,reason=reason)
                envelope=dict(entity_type=entity_type,entity_id=entity_id,revision=current['revision']+1,
                    previous_hash=current['content_hash'],created_by=fresh['id'],created_at=self.now(),payload=payload)
                self._entity(fresh,entity_type,entity_id,True);self._entity(fresh,entity_type,entity_id)
                self.db.execute('INSERT INTO business_custom_field_values(entity_type,entity_id,revision,payload_json,content_hash,previous_hash,created_by,created_at) VALUES(?,?,?,?,?,?,?,?)',
                    (entity_type,entity_id,envelope['revision'],canonical(payload),_sha(envelope),envelope['previous_hash'],fresh['id'],envelope['created_at']))
                result=self._values(entity_type,entity_id);self._remember(fresh,data,fingerprint,result)
                self.office.audit(fresh,'custom_field.values.saved',entity_type+':'+entity_id)
                return result
            except Problem as error:
                if error.status==409:raise Problem(409,error.message,request_resolution='not_accepted') from None
                raise

    def history(self,actor,query,*,definition_id=None,entity_type=None,entity_id=None):
        _shape(query,('before_revision','limit'))
        if any(not isinstance(value,str) or not re.fullmatch(r'[0-9]{1,10}',value) for value in query.values()):
            raise Problem(400,'Gültige Historienseite angeben.')
        try:
            before=int(query.get('before_revision','2147483647'));limit=int(query.get('limit','50'))
        except (ValueError,TypeError):raise Problem(400,'Gültige Historienseite angeben.') from None
        if not 1<=before<=2147483647 or not 1<=limit<=100:
            raise Problem(400,'Gültige Historienseite mit höchstens hundert Einträgen angeben.')
        with transaction(self.office):
            if definition_id:
                require_permission(self.office,actor,'settings.manage');self._definition_row(definition_id)
                rows=self.db.execute('SELECT * FROM business_custom_field_definitions WHERE id=? AND revision<? ORDER BY revision DESC LIMIT ?',
                    (definition_id,before,limit+1)).fetchall()
            else:
                self._entity(actor,entity_type,entity_id)
                rows=self.db.execute('SELECT * FROM business_custom_field_values WHERE entity_type=? AND entity_id=? AND revision<? ORDER BY revision DESC LIMIT ?',
                    (entity_type,entity_id,before,limit+1)).fetchall()
            selected=rows[:limit]
            return dict(items=[self._event(row,bool(definition_id)) for row in selected],
                next_before_revision=selected[-1]['revision'] if len(rows)>limit else None)


def validate_integrity(office):
    from business_schema import _tables
    present=set(TABLES).intersection(_tables(office))
    if not present:return True
    if present!=set(TABLES):raise ValueError('Incomplete custom field schema')
    api=CustomFields(office);definitions={};versions={};values={}
    try:
        for row in office.db.execute('SELECT * FROM business_custom_field_definitions ORDER BY id,revision').fetchall():
            event=api._event(row,True);previous=definitions.get(event['id'])
            normalized=_definition({key:event[key] for key in DEFINITION_FIELDS})
            if (any(normalized[key]!=event[key] for key in DEFINITION_FIELDS)
                    or event['revision']!=(previous['revision']+1 if previous else 1)
                    or event['previous_hash']!=(previous['content_hash'] if previous else None)
                    or previous and (event['entity_type']!=previous['entity_type'] or not event['reason'])):
                raise ValueError('Invalid custom field definition chain')
            definitions[event['id']]=event
            versions.setdefault(event['id'],[]).append(event)
        for row in office.db.execute('SELECT * FROM business_custom_field_values ORDER BY entity_type,entity_id,revision').fetchall():
            event=api._event(row);key=(event['entity_type'],event['entity_id']);previous=values.get(key)
            table='customers' if event['entity_type']=='contact' else 'projects' if event['entity_type']=='project' else 'business_assets'
            if office.db.execute('SELECT id FROM '+table+' WHERE id=?',(event['entity_id'],)).fetchone() is None:
                raise ValueError('Missing custom field entity')
            if (event['revision']!=(previous['revision']+1 if previous else 1)
                    or event['previous_hash']!=(previous['content_hash'] if previous else None)
                    or event['definitions_hash']!=_sha(event['definitions']) or previous and not event['reason']):
                raise ValueError('Invalid custom field value chain')
            captured={item['id']:item for item in event['definitions']}
            if len(captured)!=len(event['definitions']) or any(item['entity_type']!=event['entity_type'] or api._definition_row(item['id'],item['revision'])!=item for item in captured.values()):
                raise ValueError('Invalid captured custom field definitions')
            active={field_id:item for field_id,item in captured.items() if item['active']}
            if set(event['values'])!=set(active).union(previous['values'] if previous else {}):
                raise ValueError('Lost custom field values')
            for field_id,item in event['values'].items():
                definition=item['definition']
                if field_id not in active:
                    if not previous or previous['values'].get(field_id)!=item:
                        raise ValueError('Archived custom field changed')
                elif definition!=active[field_id]:
                    raise ValueError('Active custom field snapshot changed')
                if (definition['id']!=field_id or definition['entity_type']!=event['entity_type']
                        or api._definition_row(field_id,definition['revision'])!=definition):
                    raise ValueError('Changed custom field definition reference')
                old=previous['values'].get(field_id) if previous else None
                if _value(definition,item['value'],old['value'] if old else None)!=item['value']:
                    raise ValueError('Changed typed custom field value')
                if item['value'] is not None and any(version['revision']>=definition['revision'] and version['field_type']!=definition['field_type'] for version in versions[field_id]):
                    raise ValueError('Used custom field type was reinterpreted')
            values[key]=event
        for row in office.db.execute('SELECT * FROM business_custom_field_requests').fetchall():
            identifier(row['request_id']);result=json.loads(row['result_json'])
            if not re.fullmatch(r'[a-f0-9]{64}',row['request_hash']):raise ValueError('Invalid custom field request hash')
            if 'id' in result:
                expected=api._definition_row(result['id'],result['revision'])
            else:
                record=office.db.execute('SELECT * FROM business_custom_field_values WHERE entity_type=? AND entity_id=? AND revision=?',
                    (result['entity_type'],result['entity_id'],result['revision'])).fetchone()
                expected=api._event(record) if record else None
            if result!=expected:raise ValueError('Changed custom field receipt')
    except (Problem,KeyError,TypeError,json.JSONDecodeError) as error:
        raise ValueError('Invalid custom field archive') from error
    return True


def methods(path):
    if path=='/custom-fields/definitions':return 'GET, POST'
    if re.fullmatch(r'/custom-fields/definitions/'+ID+r'/history',path):return 'GET'
    if re.fullmatch(r'/custom-fields/entities/(?:contact|project|asset)/'+ID,path):return 'GET, POST'
    if re.fullmatch(r'/custom-fields/entities/(?:contact|project|asset)/'+ID+r'/history',path):return 'GET'
    return None


def dispatch(office,actor,path,method,data):
    allowed=methods(path)
    if allowed is None:return None
    if method not in allowed.split(', '):raise Problem(405,'HTTP-Methode nicht erlaubt.')
    api=CustomFields(office)
    if path=='/custom-fields/definitions':
        if method=='POST':result=api.save_definition(actor,data)
        else:
            _shape(data,('_query',));result=api.definitions(actor,data.get('_query',{}))
    elif path.startswith('/custom-fields/definitions/'):
        _shape(data,('_query',));result=api.history(actor,data.get('_query',{}),definition_id=path.split('/')[3])
    else:
        parts=path.split('/');entity_type,entity_id=parts[3:5]
        if method=='POST':result=api.save_values(actor,entity_type,entity_id,data)
        else:
            _shape(data,('_query',));query=data.get('_query',{})
            if path.endswith('/history'):result=api.history(actor,query,entity_type=entity_type,entity_id=entity_id)
            else:
                _shape(query,());result=api.entity(actor,entity_type,entity_id)
    return result,200,'application/json'
