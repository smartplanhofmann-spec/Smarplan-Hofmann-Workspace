"""Explicit local file migration; originals never become issued invoices or money.

Smartplan mapping v1 is our interchange contract, not a claimed HERO/sevdesk
export schema. No provider access, rendering, sending, payment or journal entry.
"""
import base64
import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import io
import json
import re
import sqlite3
import uuid

from core import Problem, canonical, customer_key
from business_foundation import BusinessFoundation, _fresh, require_permission
from business_operations import identifier, iso_date, text, transaction

FEATURES = ('file_migrations',)
ID = r'[a-f0-9]{32}'
MAX_FILE = 2 * 1024 * 1024
MAX_FILES, MAX_ROWS = 20, 1000
KINDS = ('contact', 'project', 'document')
FIELDS = {
    'contact': ('source_id','name','contact','email','phone','address','notes','person_name','person_email','person_phone'),
    'project': ('source_id','customer_source_id','name'),
    'document': ('source_id','customer_source_id','project_source_id','kind','number','issue_date','net','tax','gross','currency','original_filename'),
}
REQUIRED = {'contact': ('source_id','name'), 'project': ('source_id','customer_source_id','name'),
    'document': ('source_id','customer_source_id','kind','number','issue_date','original_filename')}
TABLES = tuple('business_migration_' + item for item in
    ('packages','files','mappings','bindings','documents','applications','reconciliations','requests'))


def sha(value):
    return hashlib.sha256(value if isinstance(value,bytes) else canonical(value).encode()).hexdigest()


def shape(value,required,optional=()):
    if not isinstance(value,dict) or set(value)-set(required)-set(optional) or set(required)-set(value):
        raise Problem(400,'Unvollständige oder unbekannte Importfelder.')


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA','BLOB'): raise ValueError('Unsupported binary type')
    return [
        '''CREATE TABLE IF NOT EXISTS business_migration_packages(
        id TEXT PRIMARY KEY,payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        f'''CREATE TABLE IF NOT EXISTS business_migration_files(
        id TEXT PRIMARY KEY,package_id TEXT NOT NULL REFERENCES business_migration_packages(id),
        filename TEXT NOT NULL,media_type TEXT NOT NULL,content {binary_type} NOT NULL,sha256 TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,UNIQUE(package_id,filename))''',
        '''CREATE TABLE IF NOT EXISTS business_migration_mappings(
        package_id TEXT NOT NULL REFERENCES business_migration_packages(id),revision INTEGER NOT NULL CHECK(revision>0),
        payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
        PRIMARY KEY(package_id,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_migration_bindings(
        source_system TEXT NOT NULL,source_account TEXT NOT NULL,kind TEXT NOT NULL,source_id TEXT NOT NULL,
        package_id TEXT NOT NULL REFERENCES business_migration_packages(id),target_id TEXT NOT NULL,
        customer_id TEXT REFERENCES customers(id),project_id TEXT REFERENCES projects(id),
        source_sha256 TEXT NOT NULL,payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,
        PRIMARY KEY(source_system,source_account,kind,source_id))''',
        '''CREATE TABLE IF NOT EXISTS business_migration_documents(
        id TEXT PRIMARY KEY,package_id TEXT NOT NULL REFERENCES business_migration_packages(id),
        file_id TEXT NOT NULL REFERENCES business_migration_files(id),customer_id TEXT NOT NULL REFERENCES customers(id),
        project_id TEXT REFERENCES projects(id),payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_migration_applications(
        package_id TEXT PRIMARY KEY REFERENCES business_migration_packages(id),
        payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_migration_reconciliations(
        package_id TEXT PRIMARY KEY REFERENCES business_migration_packages(id),
        payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_migration_requests(
        user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,operation TEXT NOT NULL,
        request_json TEXT NOT NULL,request_hash TEXT NOT NULL,result_json TEXT NOT NULL,
        PRIMARY KEY(user_id,request_id))''',
    ]


def protected_tables(): return TABLES
def runtime_privileges(): return {table:('SELECT','INSERT') for table in TABLES}


def guard_statements(dialect):
    output=[]
    if dialect=='postgresql': output.append("CREATE OR REPLACE FUNCTION business_migration_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable migration evidence'; END; $$")
    unique={'packages':'id=NEW.id','files':'id=NEW.id OR (package_id=NEW.package_id AND filename=NEW.filename)',
        'mappings':'package_id=NEW.package_id AND revision=NEW.revision',
        'bindings':'source_system=NEW.source_system AND source_account=NEW.source_account AND kind=NEW.kind AND source_id=NEW.source_id',
        'documents':'id=NEW.id','applications':'package_id=NEW.package_id','reconciliations':'package_id=NEW.package_id',
        'requests':'user_id=NEW.user_id AND request_id=NEW.request_id'}
    for table in TABLES:
        for action in ('UPDATE','DELETE'):
            name=table+'_'+action.lower()+'_guard'
            if dialect=='sqlite': output.append(f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable migration evidence'); END")
            elif dialect=='postgresql': output.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION business_migration_immutable_guard(); END IF; END $$")
            else: raise ValueError('Unsupported storage dialect')
        if dialect=='sqlite': output.append(f"CREATE TRIGGER IF NOT EXISTS {table}_replace_guard BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {unique[table.removeprefix('business_migration_')]}) BEGIN SELECT RAISE(ABORT,'immutable migration evidence'); END")
    return output


def _pairs(items):
    result={}
    for key,value in items:
        if key in result: raise ValueError('Duplicate JSON field')
        result[key]=value
    return result


def parse_rows(raw,format_,encoding,delimiter):
    if format_ not in ('csv','json') or encoding not in ('utf-8-sig','cp1252') or delimiter not in (';',',','\t'):
        raise Problem(400,'CSV/JSON, UTF-8/Windows-1252 und ein bekanntes Trennzeichen wählen.')
    try:
        value=raw.decode(encoding)
        if '\x00' in value: raise ValueError('Binary text')
        if format_=='json':
            rows=json.loads(value,object_pairs_hook=_pairs)
            if not isinstance(rows,list): raise ValueError('JSON row array expected')
            columns=list(rows[0]) if rows and isinstance(rows[0],dict) else []
        else:
            reader=csv.DictReader(io.StringIO(value),delimiter=delimiter,strict=True)
            columns=reader.fieldnames or []
            rows=[]
            for item in reader:
                rows.append(item)
                if len(rows)>MAX_ROWS: raise Problem(413,'Höchstens 1000 Datenzeilen je Paket.')
        if (not columns or len(columns)>50 or len(set(columns))!=len(columns) or
                any(not isinstance(key,str) or not key or len(key)>150 or any(ord(c)<32 for c in key) for key in columns)):
            raise ValueError('Invalid columns')
        if not rows or len(rows)>MAX_ROWS: raise Problem(413,'Zwischen 1 und 1000 Datenzeilen erforderlich.')
        if any(not isinstance(row,dict) or set(row)!=set(columns) or (format_=='csv' and any(v is None for v in row.values())) or
                any(value is not None and (not isinstance(value,str) or len(value)>5000) for value in row.values()) for row in rows):
            raise ValueError('Inconsistent text rows')
        return columns,rows
    except (UnicodeError,ValueError,csv.Error,RecursionError):
        raise Problem(400,'Datei passt nicht zum ausdrücklich gewählten Tabellenformat; JSON-Werte müssen Text oder null sein.') from None


class Migrations:
    def __init__(self,office,clock=None):
        self.office,self.db=office,office.db
        self.foundation=BusinessFoundation(office)
        self.clock=clock or (lambda:datetime.now(timezone.utc))
    def now(self):return self.clock().astimezone(timezone.utc).isoformat(timespec='seconds')
    def access(self,actor,write=False):
        actor=require_permission(self.office,actor,'settings.manage')
        if actor['role']!='owner':raise Problem(403,'Originalpakete können unternehmensweite Daten enthalten und sind der Geschäftsführung vorbehalten.')
        for right in ('contacts.read','finance.read','documents.read'):
            require_permission(self.office,actor,right)
        if write:
            from business_schema import require_capability,state
            require_capability(self.office,'business_migrations')
            if state(self.office)['readonly']:raise Problem(423,'Datenübernahme ist aktuell nur lesbar.')
        return actor
    def value(self,row):
        value=json.loads(row['payload_json'])
        if sha(value)!=row['sha256']:raise Problem(500,'Importnachweis ist beschädigt.')
        return value
    def header(self,package_id):
        row=self.db.execute('SELECT * FROM business_migration_packages WHERE id=?',(identifier(package_id),)).fetchone()
        if row is None:raise Problem(404,'Importpaket nicht verfügbar.')
        return self.value(row)
    def receipt(self,actor,operation,data):
        identifier(data['request_id']);safe=dict(data)
        if 'content_base64' in safe:safe['content_base64_sha256']=sha(safe.pop('content_base64'))
        fingerprint=sha([operation,safe])
        row=self.db.execute('SELECT * FROM business_migration_requests WHERE user_id=? AND request_id=?',(actor['id'],data['request_id'])).fetchone()
        if row and (row['operation']!=operation or row['request_hash']!=fingerprint):raise Problem(409,'Vorgangs-ID wurde bereits anders verwendet.')
        return safe,fingerprint,json.loads(row['result_json']) if row else None
    def remember(self,actor,operation,safe,fingerprint,result):
        self.db.execute('INSERT INTO business_migration_requests(user_id,request_id,operation,request_json,request_hash,result_json) VALUES(?,?,?,?,?,?)',
            (actor['id'],safe['request_id'],operation,canonical(safe),fingerprint,canonical(result)))
        return result
    def immutable(self,table,package_id):
        row=self.db.execute('SELECT * FROM '+table+' WHERE package_id=?',(package_id,)).fetchone()
        return self.value(row) if row else None
    def open_package(self,package_id):
        if self.immutable('business_migration_applications',package_id):raise Problem(409,'Übernommenes Paket bleibt unverändert; Ergänzungen benötigen ein neues Paket.')
    def mapping(self,package_id):
        row=self.db.execute('SELECT * FROM business_migration_mappings WHERE package_id=? ORDER BY revision DESC LIMIT 1',(package_id,)).fetchone()
        return self.value(row) if row else dict(revision=0,tables=[],decisions=[])
    def file(self,package_id,file_id):
        row=self.db.execute('SELECT * FROM business_migration_files WHERE id=? AND package_id=?',(identifier(file_id),package_id)).fetchone()
        if row is None:raise Problem(404,'Originaldatei nicht verfügbar.')
        if sha(bytes(row['content']))!=row['sha256']:raise Problem(500,'Originaldatei ist beschädigt.')
        return row
    def view(self,actor,package_id):
        with transaction(self.office):
            self.access(actor);header=self.header(package_id)
            files=[dict(id=r['id'],filename=r['filename'],media_type=r['media_type'],size=len(r['content']),sha256=r['sha256']) for r in self.db.execute('SELECT * FROM business_migration_files WHERE package_id=? ORDER BY filename',(package_id,))]
            application=self.immutable('business_migration_applications',package_id)
            reconciliation=self.immutable('business_migration_reconciliations',package_id)
            return dict(header,files=files,mapping=self.mapping(package_id),status='reconciled' if reconciliation else 'applied' if application else 'staged',
                report=application,reconciliation=reconciliation,provider_profile_verified=False,format='smartplan_file_mapping_v1')
    def listing(self,actor):
        with transaction(self.office):
            self.access(actor)
            return dict(items=[self.view(actor,r['id']) for r in self.db.execute('SELECT id FROM business_migration_packages ORDER BY created_at DESC,id')],
                supported_format='smartplan_file_mapping_v1',provider_profiles={'hero':False,'sevdesk':False})
    def options(self,actor):
        with transaction(self.office):
            self.access(actor)
            return dict(fields=FIELDS,required_fields=REQUIRED,contacts=[{key:r[key] for key in ('id','name','revision','email','address')} for r in self.foundation.contacts(actor)['items']],
                projects=self.office.projects(actor),max_file_bytes=MAX_FILE,max_files=MAX_FILES,max_rows=MAX_ROWS,
                document_kinds=['invoice','credit_note','offer','order','delivery_note','other'])
    def create(self,actor,data):
        shape(data,('request_id','source_system','source_account','label','period_from','period_to','scope'))
        with transaction(self.office):
            actor=self.access(actor,True);safe,fingerprint,previous=self.receipt(actor,'create',data)
            if previous:return previous
            if data['source_system'] not in ('hero','sevdesk','other'):raise Problem(400,'Quellsystem wählen.')
            value={field:text(data[field],field,500 if field=='scope' else 200,required=True) for field in ('source_account','label','scope')}
            value.update(source_system=data['source_system'],period_from=iso_date(data['period_from'],'Zeitraum ab',optional=True),period_to=iso_date(data['period_to'],'Zeitraum bis',optional=True))
            if (value['period_from'] is None)!=(value['period_to'] is None) or value['period_from'] and value['period_from']>value['period_to']:raise Problem(400,'Vollständiger geordneter Exportzeitraum erwartet.')
            value.update(id=uuid.uuid4().hex,created_by=actor['id'],created_at=self.now())
            self.db.execute('INSERT INTO business_migration_packages VALUES(?,?,?,?,?)',(value['id'],canonical(value),sha(value),actor['id'],value['created_at']))
            self.office.audit(actor,'business.migration.created',value['id'])
            return self.remember(actor,'create',safe,fingerprint,value)
    def upload(self,actor,package_id,data):
        shape(data,('request_id','filename','media_type','content_base64'))
        with transaction(self.office):
            actor=self.access(actor,True);self.header(package_id);operation='file:'+package_id
            safe,fingerprint,previous=self.receipt(actor,operation,data)
            if previous:return previous
            self.open_package(package_id)
            filename=text(data['filename'],'Dateiname',200,required=True)
            if filename in ('.','..') or any(c in filename for c in '/\\') or any(ord(c)<32 or ord(c)==127 for c in filename):raise Problem(400,'Einfacher Dateiname ohne Pfad erwartet.')
            media=data['media_type']
            if media not in ('text/csv','application/json','application/pdf','application/xml','text/xml','application/zip','application/octet-stream','image/jpeg','image/png'):
                raise Problem(400,'Nicht unterstützte Originaldateiart.')
            if not isinstance(data['content_base64'],str) or len(data['content_base64'])>4*((MAX_FILE+2)//3):raise Problem(413,'Originaldatei darf höchstens 2 MiB umfassen.')
            try:raw=base64.b64decode(data['content_base64'],validate=True)
            except (ValueError,TypeError):raise Problem(400,'Ungültige Originaldatei.') from None
            if not raw or len(raw)>MAX_FILE:raise Problem(413,'Originaldatei muss 1 Byte bis 2 MiB umfassen.')
            files=self.db.execute('SELECT filename,content FROM business_migration_files WHERE package_id=?',(package_id,)).fetchall()
            if any(r['filename']==filename for r in files):raise Problem(409,'Dateiname bereits vorhanden; Originale werden nicht ersetzt.')
            if len(files)>=MAX_FILES or sum(len(r['content']) for r in files)+len(raw)>10*MAX_FILE:raise Problem(413,'Paketgrenze: 20 Dateien und 20 MiB.')
            result=dict(id=uuid.uuid4().hex,package_id=package_id,filename=filename,media_type=media,size=len(raw),sha256=sha(raw))
            self.db.execute('INSERT INTO business_migration_files VALUES(?,?,?,?,?,?,?,?)',(result['id'],package_id,filename,media,raw,result['sha256'],actor['id'],self.now()))
            return self.remember(actor,operation,safe,fingerprint,result)
    def inspect(self,actor,package_id,file_id,options):
        shape(options,(),('format','encoding','delimiter'))
        with transaction(self.office):
            self.access(actor);self.header(package_id);row=self.file(package_id,file_id)
            columns,rows=parse_rows(bytes(row['content']),options.get('format','csv'),options.get('encoding','utf-8-sig'),options.get('delimiter',';'))
            return dict(file_id=file_id,sha256=row['sha256'],columns=columns,samples=rows[:5],row_count=len(rows))
    def save_mapping(self,actor,package_id,data):
        shape(data,('request_id','revision','tables','decisions'))
        with transaction(self.office):
            actor=self.access(actor,True);self.header(package_id);operation='mapping:'+package_id
            safe,fingerprint,previous=self.receipt(actor,operation,data)
            if previous:return previous
            self.open_package(package_id);current=self.mapping(package_id)
            if type(data['revision']) is not int or data['revision']!=current['revision']:raise Problem(409,'Zuordnung wurde inzwischen geändert.')
            if not isinstance(data['tables'],list) or not 1<=len(data['tables'])<=MAX_FILES:raise Problem(400,'Mindestens eine Quelltabelle wählen.')
            seen=set();count=0
            for table in data['tables']:
                shape(table,('file_id','kind','format','encoding','delimiter','decimal_separator','columns'))
                if table['kind'] not in KINDS or table['decimal_separator'] not in ('.',','):raise Problem(400,'Unbekannter Tabellen- oder Zahlenvertrag.')
                if table['file_id'] in seen:raise Problem(400,'Jede Datei höchstens einer Tabelle zuordnen.')
                seen.add(table['file_id']);row=self.file(package_id,table['file_id'])
                columns,rows=parse_rows(bytes(row['content']),table['format'],table['encoding'],table['delimiter']);count+=len(rows)
                mapping=table['columns']
                if (not isinstance(mapping,dict) or set(mapping)-set(FIELDS[table['kind']]) or set(REQUIRED[table['kind']])-set(mapping) or
                        any(not isinstance(v,str) or v not in columns for v in mapping.values())):raise Problem(400,'Pflichtfelder ausdrücklich vorhandenen Quellspalten zuordnen.')
            if count>MAX_ROWS:raise Problem(413,'Höchstens 1000 Zeilen über alle Tabellen des Pakets.')
            if not isinstance(data['decisions'],list) or len(data['decisions'])>MAX_ROWS:raise Problem(400,'Ungültige Dublettenentscheidungen.')
            seen=set()
            for item in data['decisions']:
                shape(item,('kind','source_id','action','target_id','reason'))
                if item['kind'] not in KINDS or item['action'] not in ('create','link','skip') or item['action']=='link' and item['kind']=='document':raise Problem(400,'Ungültige Übernahmeentscheidung.')
                text(item['source_id'],'Quellkennung',200,required=True);text(item['reason'],'Begründung',500,required=True)
                if item['action']=='link':identifier(item['target_id'])
                elif item['target_id'] is not None:raise Problem(400,'Nur Verknüpfungen besitzen eine Zielkennung.')
                key=(item['kind'],item['source_id'])
                if key in seen:raise Problem(400,'Doppelte Übernahmeentscheidung.')
                seen.add(key)
            value=dict(package_id=package_id,revision=current['revision']+1,tables=data['tables'],decisions=data['decisions'])
            self.db.execute('INSERT INTO business_migration_mappings VALUES(?,?,?,?,?,?)',(package_id,value['revision'],canonical(value),sha(value),actor['id'],self.now()))
            return self.remember(actor,operation,safe,fingerprint,value)

    def normalize(self,kind,values,decimal_separator):
        result={key:text(values.get(key) or '',key,5000 if key=='notes' else 1000 if key=='address' else 200,
            required=key in REQUIRED[kind]) for key in FIELDS[kind]}
        if kind=='contact':
            persons=[dict(name=result['person_name'],email=result['person_email'],phone=result['person_phone'],role_label='')] if result['person_name'] else []
            if not result['person_name'] and (result['person_email'] or result['person_phone']):raise Problem(400,'Ansprechpartner benötigt einen Namen.')
            self.foundation._contact_values({**{k:result[k] for k in ('name','contact','email','phone','address','notes')},'persons':persons})
        if kind=='document':
            if result['kind'] not in ('invoice','credit_note','offer','order','delivery_note','other'):raise Problem(400,'Historische Dokumentart ausdrücklich zuordnen.')
            iso_date(result['issue_date'],'Dokumentdatum')
            for field in ('net','tax','gross'):
                value=result[field]
                if not value:result[field]=None;continue
                if decimal_separator==',':value=value.replace(',','.')
                if not re.fullmatch(r'-?(?:0|[1-9][0-9]{0,12})(?:\.[0-9]{1,2})?',value):raise Problem(400,'Beträge benötigen das gewählte Dezimalzeichen, höchstens zwei Nachkommastellen und keine Tausendertrennzeichen.')
                result[field]=format(Decimal(value),'.2f')
            if result['currency'] and not re.fullmatch(r'[A-Z]{3}',result['currency']):raise Problem(400,'Währung benötigt einen dreistelligen Code.')
            if any(result[k] is not None for k in ('net','tax','gross')) and not result['currency']:raise Problem(400,'Deklarierte Beträge benötigen eine Währung; keine Standardwährung wird ergänzt.')
            if all(result[k] is not None for k in ('net','tax','gross')) and Decimal(result['net'])+Decimal(result['tax'])!=Decimal(result['gross']):raise Problem(400,'Deklarierte Nettosumme und Steuer ergeben nicht den Bruttobetrag.')
        return result

    def binding(self,header,kind,source_id):
        row=self.db.execute('SELECT * FROM business_migration_bindings WHERE source_system=? AND source_account=? AND kind=? AND source_id=?',
            (header['source_system'],header['source_account'],kind,source_id)).fetchone()
        if row is not None:self.value(row)
        return row

    def target(self,actor,kind,target_id,*,historical=False):
        if kind=='contact':
            value=self.foundation.contact(actor,target_id)
            if value['erased_at'] or not historical and not value['active']:raise Problem(409,'Zielkontakt ist archiviert oder gelöscht.')
            return value
        if kind=='project':return dict(self.office.project(actor,target_id))
        row=self.db.execute('SELECT * FROM business_migration_documents WHERE id=?',(identifier(target_id),)).fetchone()
        if row is None:raise Problem(409,'Historisches Ziel fehlt.')
        value=self.value(row);self.foundation.contact(actor,row['customer_id'])
        if row['project_id']:self.office.project(actor,row['project_id'])
        self.file(row['package_id'],row['file_id'])
        return value

    def preview(self,actor,package_id):
        with transaction(self.office):
            actor=self.access(actor);header=self.header(package_id);mapping=self.mapping(package_id)
            files=[dict(id=r['id'],filename=r['filename'],sha256=r['sha256']) for r in self.db.execute('SELECT * FROM business_migration_files WHERE package_id=? ORDER BY id',(package_id,))]
            by_filename={r['filename']:r for r in files};rows=[];errors=[]
            if not mapping['revision']:errors.append(dict(code='mapping_required',message='Zuerst die Quellspalten ausdrücklich zuordnen.'))
            decisions={(d['kind'],d['source_id']):d for d in mapping['decisions']}
            keys={}
            for table in mapping['tables']:
                original=self.file(package_id,table['file_id'])
                _,raw_rows=parse_rows(bytes(original['content']),table['format'],table['encoding'],table['delimiter'])
                for index,raw in enumerate(raw_rows,1):
                    value={k:raw[v] for k,v in table['columns'].items()}
                    row=dict(kind=table['kind'],source_id=value.get('source_id') or '',file_id=table['file_id'],row=index,
                        values=value,source_sha256=None,action='create',target_id=None,candidates=[],errors=[],reason='',target_snapshot=None)
                    try:
                        value=self.normalize(table['kind'],value,table['decimal_separator']);row.update(values=value,source_id=value['source_id'])
                        extra=None
                        if table['kind']=='document':
                            original_file=by_filename.get(value['original_filename'])
                            if original_file is None:raise Problem(400,'Genanntes Dokumentoriginal ist nicht im Paket vorhanden.')
                            file_row=self.file(package_id,original_file['id'])
                            raw_original=bytes(file_row['content'])
                            if file_row['media_type'] not in ('application/pdf','application/xml','text/xml','image/jpeg','image/png'):raise Problem(400,'Dokumentoriginal muss PDF, XML, PNG oder JPEG sein; ZIP/Tabellen bleiben Paketoriginale.')
                            if file_row['media_type']=='application/pdf' and not raw_original.startswith(b'%PDF-'):raise Problem(400,'PDF-Original besitzt keinen PDF-Dateikopf.')
                            extra=original_file['sha256'];row['original_file_id']=original_file['id'];row['original_sha256']=extra
                        row['source_sha256']=sha([table['kind'],value,extra])
                    except Problem as error:row['errors'].append(dict(code='invalid_row',message=error.message))
                    key=(row['kind'],row['source_id']);keys.setdefault(key,[]).append(row);rows.append(row)
            for key,duplicates in keys.items():
                if len(duplicates)>1:
                    for row in duplicates:row['errors'].append(dict(code='duplicate_source',message='Quellkennung steht mehrfach im Paket.'))
            for key in decisions:
                if key not in keys:errors.append(dict(code='unused_decision',message='Eine Entscheidung verweist auf keine aktuelle Quellzeile.'))
            contacts=self.foundation.contacts(actor)['items']
            for row in sorted(rows,key=lambda item:KINDS.index(item['kind'])):
                kind,values=row['kind'],row['values'];decision=decisions.get((kind,row['source_id']))
                if decision:row.update(action=decision['action'],target_id=decision['target_id'],reason=decision['reason'])
                if row['action']=='skip' or row['errors']:continue
                try:
                    bound=self.binding(header,kind,row['source_id'])
                    if bound:
                        if bound['source_sha256']!=row['source_sha256']:raise Problem(409,'Diese Quellkennung wurde bereits mit anderem Inhalt übernommen; kein stilles Überschreiben.')
                        if decision and (decision['action']!='link' or decision['target_id']!=bound['target_id']):raise Problem(409,'Bestehende Herkunftsverknüpfung darf nicht umgelenkt werden.')
                        row.update(action='reuse',target_id=bound['target_id'],target_snapshot=self.target(actor,kind,bound['target_id']))
                    elif kind=='contact':
                        row['candidates']=[dict(id=c['id'],name=c['name']) for c in contacts if c['active'] and not c['erased_at'] and
                            (c['name'].casefold()==values['name'].casefold() or values['email'] and c['email'].casefold()==values['email'].casefold())]
                    if row['action']=='link':row['target_snapshot']=self.target(actor,kind,row['target_id'])
                    if kind in ('project','document'):
                        def resolve(ref_kind,source):
                            matches=keys.get((ref_kind,source),[])
                            if matches:
                                if len(matches)!=1 or matches[0]['errors'] or matches[0]['action'] in ('skip','review'):raise Problem(409,'Quellbeziehung ist fehlerhaft, ungeklärt oder ausgeschlossen: '+ref_kind)
                                return matches[0]['target_id']
                            previous=self.binding(header,ref_kind,source)
                            if previous is None:raise Problem(409,'Quellbeziehung fehlt: '+ref_kind+' '+source)
                            row.setdefault('external_references',[]).append(dict(kind=ref_kind,source_id=source,target_id=previous['target_id'],snapshot=self.target(actor,ref_kind,previous['target_id'])))
                            return previous['target_id']
                        customer=resolve('contact',values['customer_source_id']);row['customer_target_id']=customer
                        if kind=='project':
                            if row['action'] in ('link','reuse') and row['target_snapshot']['customer_id']!=customer:raise Problem(409,'Projekt gehört nicht zum ausdrücklich zugeordneten Kunden.')
                            if not bound:row['candidates']=[dict(id=p['id'],name=p['name']) for p in self.office.projects(actor) if customer and p['customer_id']==customer and p['name'].casefold()==values['name'].casefold()]
                        elif values['project_source_id']:
                            project=resolve('project',values['project_source_id']);row['project_target_id']=project
                            project_rows=keys.get(('project',values['project_source_id']),[])
                            project_customer=project_rows[0]['values']['customer_source_id'] if project_rows else None
                            if project_customer is not None and project_customer!=values['customer_source_id']:raise Problem(409,'Dokument und Projekt beziehen sich auf verschiedene Kunden.')
                            if project and self.target(actor,'project',project)['customer_id']!=customer:raise Problem(409,'Dokument und Zielprojekt gehören zu verschiedenen Kunden.')
                        if kind=='document' and not bound and customer:
                            candidates=[]
                            for candidate in self.db.execute('SELECT * FROM business_migration_documents WHERE customer_id=?',(customer,)):
                                previous=self.value(candidate)
                                if previous['values']['kind']==values['kind'] and previous['values']['number']==values['number']:
                                    candidates.append(dict(id=candidate['id'],name='Importiertes Dokument '+values['number']))
                            for candidate in self.db.execute('SELECT d.id,d.kind,d.number FROM business_documents d JOIN projects p ON p.id=d.project_id WHERE p.customer_id=? AND d.number=?',(customer,values['number'])):
                                candidates.append(dict(id=candidate['id'],name='Smartplan-Dokument '+candidate['number']))
                            row['candidates']=candidates
                    if row['candidates'] and decision is None and not bound:row['action']='review'
                    if kind=='contact' and row['action']=='create' and any(customer_key(c['name'],c['address'])==customer_key(values['name'],values['address']) for c in contacts):
                        raise Problem(409,'Kontakt mit gleichem Namen und gleicher Adresse existiert; ausdrücklich verknüpfen oder ausschließen.')
                except Problem as error:row['errors'].append(dict(code='conflict',message=error.message))
            planned_contacts={}
            for row in rows:
                if row['kind']=='contact' and row['action']=='create' and not row['errors']:
                    key=customer_key(row['values']['name'],row['values']['address'])
                    planned_contacts.setdefault(key,[]).append(row)
            for duplicates in planned_contacts.values():
                if len(duplicates)>1:
                    for row in duplicates:row['errors'].append(dict(code='duplicate_target',message='Mehrere neue Quellkontakte besitzen denselben Namen und dieselbe Adresse. Zuordnung vor Übernahme bereinigen.'))
            planned_documents={}
            for row in rows:
                if row['kind']=='document' and row['action']=='create' and not row['errors']:
                    value=row['values'];key=(value['customer_source_id'],value['kind'],value['number'])
                    planned_documents.setdefault(key,[]).append(row)
            for duplicates in planned_documents.values():
                if len(duplicates)>1:
                    for row in duplicates:row['errors'].append(dict(code='duplicate_document',message='Dokumentart, Nummer und Quellkunde stehen mehrfach im Paket; Herkunft zuerst prüfen.'))
            # Later rows may refer to a source which has only just become invalid.
            for row in rows:
                if row['action']=='skip':continue
                for ref_kind,field in (('contact','customer_source_id'),('project','project_source_id')):
                    source=row['values'].get(field)
                    referenced=keys.get((ref_kind,source),[]) if source else []
                    if referenced and any(r['errors'] or r['action'] in ('skip','review') for r in referenced):
                        row['errors'].append(dict(code='unresolved_reference',message='Zugeordnete Quellbeziehung ist noch nicht übernahmefähig.'))
            counts=dict(source=len(rows),create=0,link=0,reuse=0,skip=0,errors=0,review=0)
            for row in rows:
                counts[row['action']]+=1
                if row['errors'] and row['action']!='skip':counts['errors']+=1
            result=dict(package_id=package_id,revision=mapping['revision'],files=files,rows=rows,errors=errors,counts=counts,
                totals=self.totals(rows),ready=bool(rows) and not errors and not counts['errors'] and not counts['review'])
            result['preview_sha256']=sha(result)
            return result

    @staticmethod
    def totals(rows):
        groups={}
        for row in rows:
            if row['kind']!='document':continue
            values=row['values'];key=(values.get('kind') or 'unknown',values.get('currency') or 'unknown')
            group=groups.setdefault(key,dict(kind=key[0],currency=key[1],source={k:0 for k in ('net','tax','gross','missing')},selected={k:0 for k in ('net','tax','gross','missing')}))
            for section in ('source','selected'):
                if section=='selected' and (row['action'] in ('skip','review') or row['errors']):continue
                missing=False
                for field in ('net','tax','gross'):
                    value=values.get(field)
                    if isinstance(value,str) and re.fullmatch(r'-?[0-9]{1,13}\.[0-9]{2}',value):group[section][field]+=int(Decimal(value)*100)
                    else:missing=True
                group[section]['missing']+=int(missing)
        for group in groups.values():
            for section in ('source','selected'):
                for field in ('net','tax','gross'):
                    group[section][field+'_exact']=format(Decimal(group[section][field])/100,'.2f')
        return [groups[key] for key in sorted(groups)]

    def apply(self,actor,package_id,data):
        shape(data,('request_id','revision','preview_sha256','confirmation'))
        with transaction(self.office):
            actor=self.access(actor,True);header=self.header(package_id)
            for right in ('contacts.write','projects.manage'):require_permission(self.office,actor,right)
            if actor['role']!='owner':raise Problem(403,'Neue Stammdaten übernimmt die Geschäftsführung.')
            operation='apply:'+package_id;safe,fingerprint,previous=self.receipt(actor,operation,data)
            if previous:
                for row in previous['rows']:
                    if row['action']!='skip':self.target(actor,row['kind'],row['target_id'],historical=True)
                return previous
            self.open_package(package_id)
            if data['confirmation'] is not True:raise Problem(400,'Geprüfte Übernahme ausdrücklich bestätigen.')
            preview=self.preview(actor,package_id)
            if type(data['revision']) is not int or preview['revision']!=data['revision'] or preview['preview_sha256']!=data['preview_sha256']:raise Problem(409,'Quellen, Zuordnung oder Zielbestand haben sich seit der Vorschau geändert.')
            if not preview['ready']:raise Problem(409,'Vorschau enthält ungeklärte Fehler oder Dubletten.')
            if any(r['kind']=='document' and r['action']!='skip' for r in preview['rows']):
                from business_organization import require_active
                require_active(self.office,actor,'/documents','business_documents')
            targets={};results=[]
            for row in sorted(preview['rows'],key=lambda item:KINDS.index(item['kind'])):
                row=dict(row);kind,values=row['kind'],row['values'];target_id=row['target_id'];customer=None;project=None
                if row['action']=='skip':results.append(row);continue
                def resolve(ref_kind,source):
                    if (ref_kind,source) in targets:return targets[(ref_kind,source)]
                    binding=self.binding(header,ref_kind,source)
                    if binding is None:raise Problem(409,'Quellbeziehung fehlt während der Übernahme.')
                    self.target(actor,ref_kind,binding['target_id'])
                    return binding['target_id']
                if kind=='contact':
                    if row['action']=='create':
                        contact_values={k:values[k] for k in ('name','contact','email','phone','address','notes')}
                        if values['person_name']:contact_values['persons']=[dict(name=values['person_name'],email=values['person_email'],phone=values['person_phone'],role_label='')]
                        target_id=self.foundation.save_contact(actor,dict(contact_values,request_id=sha([package_id,kind,row['source_id']])[:32]))['id']
                    customer=target_id
                else:
                    customer=resolve('contact',values['customer_source_id'])
                    if kind=='project':
                        if row['action']=='create':
                            customer_data=self.target(actor,'contact',customer);target_id=uuid.uuid4().hex
                            self.db.execute('INSERT INTO projects(id,name,customer,customer_id) VALUES(?,?,?,?)',(target_id,values['name'],customer_data['name'],customer))
                            self.office.audit(actor,'project.created',target_id)
                        project=target_id
                    else:
                        project=resolve('project',values['project_source_id']) if values['project_source_id'] else None
                        if row['action']=='create':
                            target_id=uuid.uuid4().hex
                            document=dict(id=target_id,package_id=package_id,source_system=header['source_system'],source_account=header['source_account'],
                                source_id=row['source_id'],customer_id=customer,project_id=project,file_id=row['original_file_id'],original_sha256=row['original_sha256'],
                                values=values,source_sha256=row['source_sha256'],historical_source=True,issued_by_smartplan=False,financial_effects=False)
                            self.db.execute('INSERT INTO business_migration_documents VALUES(?,?,?,?,?,?,?,?,?)',(target_id,package_id,row['original_file_id'],customer,project,canonical(document),sha(document),actor['id'],self.now()))
                targets[(kind,row['source_id'])]=target_id
                row.update(target_id=target_id,customer_id=customer,project_id=project)
                if row['action']!='reuse':
                    proof=dict(source_system=header['source_system'],source_account=header['source_account'],kind=kind,source_id=row['source_id'],package_id=package_id,
                        target_id=target_id,customer_id=customer,project_id=project,source_sha256=row['source_sha256'],source_values=values,
                        file_id=row['file_id'],row=row['row'],action=row['action'],reason=row['reason'])
                    self.db.execute('INSERT INTO business_migration_bindings VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                        (header['source_system'],header['source_account'],kind,row['source_id'],package_id,target_id,customer,project,row['source_sha256'],canonical(proof),sha(proof)))
                results.append(row)
            report=dict(package_id=package_id,revision=preview['revision'],preview_sha256=preview['preview_sha256'],rows=results,
                counts=preview['counts'],totals=preview['totals'],files=preview['files'],created_at=self.now(),created_by=actor['id'],financial_effects=False,
                scope=header['scope'],source_system=header['source_system'],source_account=header['source_account'])
            report['report_sha256']=sha(report)
            self.db.execute('INSERT INTO business_migration_applications VALUES(?,?,?,?,?)',(package_id,canonical(report),sha(report),actor['id'],report['created_at']))
            self.office.audit(actor,'business.migration.applied',package_id)
            return self.remember(actor,operation,safe,fingerprint,report)

    def report(self,actor,package_id):
        with transaction(self.office):
            self.access(actor);self.header(package_id)
            value=self.immutable('business_migration_applications',package_id)
            if value is None:raise Problem(404,'Paket wurde noch nicht übernommen.')
            for row in value['rows']:
                if row['action']!='skip':self.target(actor,row['kind'],row['target_id'],historical=True)
            return value
    def reconcile(self,actor,package_id,data):
        shape(data,('request_id','report_sha256','confirmation','note'))
        with transaction(self.office):
            actor=self.access(actor,True);report=self.report(actor,package_id);operation='reconcile:'+package_id
            safe,fingerprint,previous=self.receipt(actor,operation,data)
            if previous:return previous
            if self.immutable('business_migration_reconciliations',package_id):raise Problem(409,'Abgleich wurde bereits bestätigt.')
            if data['confirmation'] is not True or data['report_sha256']!=report['report_sha256']:raise Problem(409,'Exakten Ergebnisbericht ausdrücklich bestätigen.')
            value=dict(package_id=package_id,report_sha256=report['report_sha256'],note=text(data['note'],'Abgleichnotiz',2000,required=True),
                created_by=actor['id'],created_at=self.now(),scope_only=True,financial_effects=False)
            self.db.execute('INSERT INTO business_migration_reconciliations VALUES(?,?,?,?,?)',(package_id,canonical(value),sha(value),actor['id'],value['created_at']))
            self.office.audit(actor,'business.migration.reconciled',package_id)
            return self.remember(actor,operation,safe,fingerprint,value)

    def original(self,actor,package_id,file_id):
        with transaction(self.office):
            self.access(actor);self.header(package_id);row=self.file(package_id,file_id)
            from business_documents import Download
            return Download(bytes(row['content']),row['filename']),200,'application/octet-stream'


def validate_integrity(office):
    api=Migrations(office);db=office.db
    try:
        for table in TABLES:
            for row in db.execute('SELECT * FROM '+table).fetchall():
                if table.endswith('_files'):
                    if not 0<len(row['content'])<=MAX_FILE or sha(bytes(row['content']))!=row['sha256']:raise ValueError('Invalid original')
                    continue
                if table.endswith('_requests'):
                    request=json.loads(row['request_json']);identifier(row['request_id'])
                    if sha([row['operation'],request])!=row['request_hash'] or request['request_id']!=row['request_id']:raise ValueError('Invalid request')
                    result=json.loads(row['result_json']);operation=row['operation'].split(':')
                    if operation==['create']:expected=api.header(result['id'])
                    elif len(operation)!=2:raise ValueError('Unknown migration operation')
                    elif operation[0]=='file':
                        original=api.file(operation[1],result['id'])
                        expected=dict(id=original['id'],package_id=original['package_id'],filename=original['filename'],media_type=original['media_type'],size=len(original['content']),sha256=original['sha256'])
                    elif operation[0]=='mapping':
                        proof=db.execute('SELECT * FROM business_migration_mappings WHERE package_id=? AND revision=?',(operation[1],result['revision'])).fetchone()
                        if proof is None:raise ValueError('Missing mapping receipt proof')
                        expected=api.value(proof)
                    elif operation[0] in ('apply','reconcile'):expected=api.immutable('business_migration_applications' if operation[0]=='apply' else 'business_migration_reconciliations',operation[1])
                    else:raise ValueError('Unknown migration operation')
                    if result!=expected:raise ValueError('Migration receipt differs from original result')
                    continue
                value=api.value(row)
                if table.endswith('_packages'):
                    if value['id']!=row['id']:raise ValueError('Invalid package')
                elif table.endswith('_mappings'):
                    if value['package_id']!=row['package_id'] or value['revision']!=row['revision']:raise ValueError('Invalid mapping')
                elif table.endswith('_bindings'):
                    if any(value[k]!=row[k] for k in ('source_system','source_account','kind','source_id','package_id','target_id','customer_id','project_id','source_sha256')):raise ValueError('Invalid binding')
                    table_name={'contact':'customers','project':'projects','document':'business_migration_documents'}[row['kind']]
                    if not db.execute('SELECT 1 FROM '+table_name+' WHERE id=?',(row['target_id'],)).fetchone():raise ValueError('Missing migration target')
                    api.file(row['package_id'],value['file_id'])
                    if value['kind']=='contact' and (value['target_id']!=value['customer_id'] or value['project_id'] is not None):raise ValueError('Foreign contact binding')
                    if value['kind']=='project' and value['target_id']!=value['project_id']:raise ValueError('Foreign project binding')
                    if value['project_id']:
                        project=db.execute('SELECT customer_id FROM projects WHERE id=?',(value['project_id'],)).fetchone()
                        if project is None or project['customer_id']!=value['customer_id']:raise ValueError('Foreign migration relationship')
                elif table.endswith('_documents'):
                    if any(value[k]!=row[k] for k in ('id','package_id','file_id','customer_id','project_id')) or value['financial_effects'] is not False or value['issued_by_smartplan'] is not False:raise ValueError('Invalid historical document')
                    if api.file(row['package_id'],row['file_id'])['sha256']!=value['original_sha256']:raise ValueError('Changed document original')
                    if value['source_sha256']!=sha(['document',value['values'],value['original_sha256']]):raise ValueError('Invalid document source proof')
                elif table.endswith('_applications'):
                    if value['package_id']!=row['package_id'] or value['financial_effects'] is not False or value['report_sha256']!=sha({k:v for k,v in value.items() if k!='report_sha256'}):raise ValueError('Invalid migration report')
                    for source in value['files']:
                        if api.file(row['package_id'],source['id'])['sha256']!=source['sha256']:raise ValueError('Changed source')
                    if value['totals']!=api.totals(value['rows']):raise ValueError('Invalid source reconciliation totals')
                    counts=dict(source=len(value['rows']),create=0,link=0,reuse=0,skip=0,errors=0,review=0)
                    header=api.header(row['package_id'])
                    for source in value['rows']:
                        counts[source['action']]+=1
                        if source['action']=='skip':continue
                        if source['errors'] or source['action']=='review':raise ValueError('Unresolved applied row')
                        proof=api.binding(header,source['kind'],source['source_id'])
                        if proof is None or proof['target_id']!=source['target_id'] or proof['source_sha256']!=source['source_sha256']:raise ValueError('Missing applied source proof')
                    if counts!=value['counts']:raise ValueError('Invalid migration reconciliation counts')
                elif table.endswith('_reconciliations'):
                    report=api.immutable('business_migration_applications',row['package_id'])
                    if report is None or value['report_sha256']!=report['report_sha256']:raise ValueError('Invalid reconciliation')
        for package in db.execute('SELECT id FROM business_migration_packages'):
            revisions=[r[0] for r in db.execute('SELECT revision FROM business_migration_mappings WHERE package_id=? ORDER BY revision',(package['id'],))]
            if revisions!=list(range(1,len(revisions)+1)):raise ValueError('Mapping gap')
    except (KeyError,TypeError,ValueError,Problem) as error:raise ValueError('Invalid migration evidence') from error
    return True


def methods(path):
    if path=='/migrations':return 'GET, POST'
    if path=='/migrations/options':return 'GET'
    if re.fullmatch(r'/migrations/'+ID,path):return 'GET'
    if re.fullmatch(r'/migrations/'+ID+r'/(?:preview|report)',path):return 'GET'
    if re.fullmatch(r'/migrations/'+ID+r'/(?:files|mapping|apply|reconcile)',path):return 'POST'
    if re.fullmatch(r'/migrations/'+ID+r'/files/'+ID+r'/(?:original|inspect)',path):return 'GET'
    return None


def dispatch(office,actor,path,method,data):
    allowed=methods(path)
    if allowed is None:return None
    if method not in allowed.split(', '):raise Problem(405,'Methode nicht erlaubt.')
    if not isinstance(data,dict):raise Problem(400,'JSON-Objekt erwartet.')
    api=Migrations(office);query=data.get('_query',{});body={k:v for k,v in data.items() if k!='_query'}
    if method=='GET':
        if body:raise Problem(400,'Keine zusätzlichen Abrufinhalte erlaubt.')
        if not path.endswith('/inspect'):shape(query,())
        if path=='/migrations':result=api.listing(actor)
        elif path=='/migrations/options':result=api.options(actor)
        else:
            parts=path.split('/');package_id=parts[2]
            if path.endswith('/original'):return api.original(actor,package_id,parts[4])
            if path.endswith('/inspect'):result=api.inspect(actor,package_id,parts[4],query)
            elif path.endswith('/preview'):result=api.preview(actor,package_id)
            elif path.endswith('/report'):result=api.report(actor,package_id)
            else:result=api.view(actor,package_id)
    else:
        if query:raise Problem(400,'Keine zusätzlichen Schreibfilter erlaubt.')
        try:
            if path=='/migrations':result=api.create(actor,body)
            else:
                _,_,package_id,action=path.split('/')
                result=getattr(api,{'files':'upload','mapping':'save_mapping','apply':'apply','reconcile':'reconcile'}[action])(actor,package_id,body)
        except Problem as error:
            if error.status==409 and isinstance(body.get('request_id'),str) and re.fullmatch(ID,body['request_id']):
                with transaction(office):
                    fresh=_fresh(office,actor)
                    if not office.db.execute('SELECT 1 FROM business_migration_requests WHERE user_id=? AND request_id=?',(fresh['id'],body['request_id'])).fetchone():
                        raise Problem(409,error.message,request_resolution='not_accepted') from None
            raise
    return result,200,'application/json'
