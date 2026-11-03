"""Managed subject requests with bounded private working data and real actions.

Case evidence never overrides source retention or source permissions. Private
working copies have their own explicit purpose/hold/retention and checkpointed
purge; immutable metadata alone is retained after that purge.
"""
from datetime import date,datetime,timezone
import io
import json
import re
import sqlite3
import uuid
import zipfile

from core import Problem,canonical
from business_foundation import BusinessFoundation,_fresh,require_permission
from business_operations import identifier,text,iso_date,transaction
from privacy_case_sources import MANUAL_AREAS,access,inventory,resolve,sha,subject
from workspace_api import BinaryAttachment

FEATURES=('privacy_cases',)
TABLES=('business_privacy_case_events','business_privacy_case_contents','business_privacy_case_exports',
        'business_privacy_case_export_blobs','business_privacy_case_purges','business_privacy_case_requests')
KINDS=('access','export','rectification','erasure')
MAX_CONTENT=500_000
MAX_EXPORT=8_000_000
ID=r'[a-f0-9]{32}'


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BLOB','BYTEA'):raise ValueError('Unsupported binary type')
    return [
        '''CREATE TABLE IF NOT EXISTS business_privacy_case_events(
          id TEXT PRIMARY KEY,case_id TEXT NOT NULL,revision INTEGER NOT NULL CHECK(revision>0),operation TEXT NOT NULL,
          metadata_json TEXT NOT NULL,content_sha256 TEXT NOT NULL,previous_hash TEXT,event_sha256 TEXT NOT NULL,
          created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,UNIQUE(case_id,revision))''',
        f'''CREATE TABLE IF NOT EXISTS business_privacy_case_contents(
          event_id TEXT PRIMARY KEY REFERENCES business_privacy_case_events(id),case_id TEXT NOT NULL,content {binary_type} NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_privacy_case_exports(
          id TEXT PRIMARY KEY,case_id TEXT NOT NULL,case_revision INTEGER NOT NULL CHECK(case_revision>0),
          metadata_json TEXT NOT NULL,sha256 TEXT NOT NULL,size INTEGER NOT NULL CHECK(size>0 AND size<=8000000),
          expires_on TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        f'''CREATE TABLE IF NOT EXISTS business_privacy_case_export_blobs(
          export_id TEXT PRIMARY KEY REFERENCES business_privacy_case_exports(id),content {binary_type} NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_privacy_case_purges(
          kind TEXT NOT NULL CHECK(kind IN ('case','export')),object_id TEXT NOT NULL,checkpoint_digest TEXT NOT NULL,
          created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,PRIMARY KEY(kind,object_id))''',
        '''CREATE TABLE IF NOT EXISTS business_privacy_case_requests(
          user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,case_id TEXT NOT NULL,
          operation TEXT NOT NULL,request_sha256 TEXT NOT NULL,result_ref_json TEXT NOT NULL,PRIMARY KEY(user_id,request_id))''',
        'CREATE INDEX IF NOT EXISTS business_privacy_case_history ON business_privacy_case_events(case_id,revision)',
    ]


def protected_tables():
    # Only immutable evidence belongs to the global no-DELETE contract.
    # Private blobs have their own conditional purge-proof DELETE guards.
    return tuple(table for table in TABLES if table not in (TABLES[1],TABLES[3]))
def runtime_privileges():
    return {table:('SELECT','INSERT','DELETE') if table in (TABLES[1],TABLES[3]) else ('SELECT','INSERT') for table in TABLES}


def guard_statements(dialect):
    deletable={TABLES[1]:"EXISTS(SELECT 1 FROM business_privacy_case_purges WHERE kind='case' AND object_id=OLD.case_id)",
        TABLES[3]:"EXISTS(SELECT 1 FROM business_privacy_case_purges p WHERE (p.kind='export' AND p.object_id=OLD.export_id) OR (p.kind='case' AND p.object_id=(SELECT case_id FROM business_privacy_case_exports WHERE id=OLD.export_id)))"}
    keys={TABLES[0]:'id=NEW.id OR (case_id=NEW.case_id AND revision=NEW.revision)',TABLES[1]:'event_id=NEW.event_id',
        TABLES[2]:'id=NEW.id',TABLES[3]:'export_id=NEW.export_id',TABLES[4]:'kind=NEW.kind AND object_id=NEW.object_id',
        TABLES[5]:'user_id=NEW.user_id AND request_id=NEW.request_id'}
    forbidden_insert={TABLES[1]:deletable[TABLES[1]].replace('OLD.','NEW.')+
        ' OR NOT EXISTS(SELECT 1 FROM business_privacy_case_events e WHERE e.id=NEW.event_id AND e.case_id=NEW.case_id)',
        TABLES[3]:deletable[TABLES[3]].replace('OLD.','NEW.')}
    if dialect=='sqlite':
        result=[]
        for table in TABLES:
            result.extend([f"CREATE TRIGGER IF NOT EXISTS {table}_update_guard BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT,'immutable privacy evidence'); END",
                f"CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {keys[table]})"+
                (' OR '+forbidden_insert[table] if table in forbidden_insert else '')+" BEGIN SELECT RAISE(ABORT,'immutable privacy evidence'); END",
                f"CREATE TRIGGER IF NOT EXISTS {table}_delete_guard BEFORE DELETE ON {table} "+
                ('WHEN NOT '+deletable[table]+' ' if table in deletable else '')+"BEGIN SELECT RAISE(ABORT,'privacy purge proof required'); END"])
        return result
    if dialect!='postgresql':raise ValueError('Unsupported dialect')
    result=["CREATE OR REPLACE FUNCTION business_privacy_case_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable privacy evidence'; END; $$"]
    for table in TABLES:
        function='business_privacy_case_immutable'
        if table in deletable:
            function=table+'_purge'
            result.append(f"CREATE OR REPLACE FUNCTION {function}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF {deletable[table]} THEN RETURN OLD; END IF; RAISE EXCEPTION 'privacy purge proof required'; END; $$")
            insert_function=table+'_insert'
            result.append(f"CREATE OR REPLACE FUNCTION {insert_function}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF {forbidden_insert[table]} THEN RAISE EXCEPTION 'purged privacy content cannot return'; END IF; RETURN NEW; END; $$")
            insert_name=table+'_insert_guard'
            result.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{insert_name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {insert_name} BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION {insert_function}(); END IF; END $$")
        for operation,target in (('UPDATE','business_privacy_case_immutable'),('DELETE',function)):
            name=table+'_'+operation.lower()+'_guard'
            result.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} BEFORE {operation} ON {table} FOR EACH ROW EXECUTE FUNCTION {target}(); END IF; END $$")
    return result


def _shape(data,fields):
    if not isinstance(data,dict) or set(data)!=set(fields):raise Problem(400,'Vollständige unveränderte Datenschutzfelder erwartet.')


def _date(value):
    iso_date(value);return date.fromisoformat(value)


def _reference(value):return text(value,'Prüfnachweis',2000,required=True)


def _decode(raw):
    from business_api import decode_offline_report
    return decode_offline_report(bytes(raw),max_bytes=MAX_CONTENT)


class PrivacyCases:
    def __init__(self,office,*,clock=None):
        self.office,self.db=office,office.db
        self.clock=clock or (lambda:datetime.now(timezone.utc))

    def now(self):return self.clock().astimezone(timezone.utc).isoformat(timespec='seconds')
    def today(self):return self.now()[:10]
    def _gate(self):
        from business_schema import require_capability
        require_capability(self.office,'business_privacy_cases')

    def _purged(self,kind,object_id):
        return self.db.execute('SELECT 1 FROM business_privacy_case_purges WHERE kind=? AND object_id=?',(kind,object_id)).fetchone() is not None

    def _event(self,case_id,revision=None):
        identifier(case_id)
        row=self.db.execute('SELECT * FROM business_privacy_case_events WHERE case_id=?'+(' AND revision=?' if revision is not None else '')+' ORDER BY revision DESC LIMIT 1',
            (case_id,revision) if revision is not None else (case_id,)).fetchone()
        if row is None:raise Problem(404,'Datenschutzfall nicht verfügbar.')
        return row

    def _load(self,actor,case_id,revision=None):
        fresh=require_permission(self.office,actor,'privacy.manage')
        event=self._event(case_id,revision);meta=json.loads(event['metadata_json'])
        if fresh['role']!='owner' and fresh['id'] not in (meta['creator_id'],meta['assigned_to']):
            raise Problem(404,'Privater Datenschutzfall nicht zugeordnet.')
        if self._purged('case',case_id):
            if fresh['role']!='owner':raise Problem(403,'Minimale gelöschte Fallnachweise sind der Geschäftsführung vorbehalten.')
            return fresh,event,None
        raw=self.db.execute('SELECT content FROM business_privacy_case_contents WHERE event_id=?',(event['id'],)).fetchone()
        if raw is None or sha(bytes(raw['content']))!=event['content_sha256']:raise Problem(409,'Privater Fallinhalt fehlt oder ist verändert.')
        state=_decode(raw['content'])
        subject(self.office,fresh,state['subject_kind'],state['subject_id'])
        # Private notes and redactions may refer to every linked source. They
        # cannot become a cache bypass after a source right was revoked.
        for source in (state.get('inventory') or {}).get('sources',[]):
            resolve(self.office,fresh,source,check_hash=False)
        return fresh,event,state

    def _record(self,actor,state,operation,previous=None):
        revision=previous['revision']+1 if previous else 1
        state={**state,'revision':revision}
        encoded=canonical(state).encode()
        if len(encoded)>MAX_CONTENT:raise Problem(413,'Privater Fallinhalt überschreitet die geprüfte Grenze.')
        metadata={key:state[key] for key in ('id','subject_kind','subject_hash','request_kind','creator_id','assigned_to','status',
            'received_date','due_date','retain_until','legal_hold')}
        event=dict(id=uuid.uuid4().hex,case_id=state['id'],revision=revision,operation=operation,
            metadata_json=canonical(metadata),content_sha256=sha(encoded),previous_hash=previous['event_sha256'] if previous else None,
            created_by=actor['id'],created_at=self.now())
        event['event_sha256']=sha(event)
        keys=tuple(event)
        self.db.execute('INSERT INTO business_privacy_case_events('+','.join(keys)+') VALUES('+','.join('?' for _ in keys)+')',tuple(event[key] for key in keys))
        self.db.execute('INSERT INTO business_privacy_case_contents(event_id,case_id,content) VALUES(?,?,?)',(event['id'],state['id'],encoded))
        self.office.audit(actor,'privacy.case.'+operation,state['id'])
        return state

    def view(self,actor,case_id):
        with transaction(self.office):
            fresh,event,state=self._load(actor,case_id)
            meta=json.loads(event['metadata_json'])
            if state is None:return dict(meta,revision=event['revision'],purged=True,status='purged',personal_content_available=False)
            _,person=subject(self.office,fresh,state['subject_kind'],state['subject_id'])
            exports=[]
            for row in self.db.execute('SELECT * FROM business_privacy_case_exports WHERE case_id=? ORDER BY created_at,id',(case_id,)):
                exports.append(dict(id=row['id'],revision=row['case_revision'],sha256=row['sha256'],size=row['size'],expires_on=row['expires_on'],
                    available=not self._purged('export',row['id']) and row['expires_on']>=self.today()))
            return dict(state,subject_label=person['label'],purged=False,overdue=state['due_date']<self.today() and state['status']!='closed',
                exports=exports,automatic_completeness=False,external_messages_sent=False)

    def list(self,actor):
        with transaction(self.office):
            require_permission(self.office,actor,'privacy.manage')
            result=[]
            for row in self.db.execute('SELECT DISTINCT case_id FROM business_privacy_case_events ORDER BY case_id'):
                try:value=self.view(actor,row['case_id'])
                except Problem as error:
                    if error.status in (401,403,404):continue
                    raise
                result.append({key:value.get(key) for key in ('id','revision','subject_kind','subject_label','request_kind','status','due_date','assigned_to','overdue','purged')})
            return dict(items=result)

    def command_status(self,actor,case_id,request_id):
        identifier(request_id)
        with transaction(self.office):
            fresh,_,_=self._load(actor,case_id)
            row=self.db.execute('SELECT operation,result_ref_json FROM business_privacy_case_requests WHERE user_id=? AND request_id=? AND case_id=?',
                (fresh['id'],request_id,case_id)).fetchone()
            if row is None:raise Problem(404,'Dieser persönliche Bearbeitungsauftrag ist noch nicht bestätigt.')
            return dict(case_id=case_id,request_id=request_id,operation=row['operation'],confirmed=True,reference=json.loads(row['result_ref_json']))

    def options(self,actor,query=''):
        with transaction(self.office):
            fresh=require_permission(self.office,actor,'privacy.manage')
            query=text(query,'Suchbegriff',80)
            results=[];limited=False
            for kind,table,label in (('customer','customers','name'),('employee','business_employees','name'),('user','users','email')):
                if kind=='user' and fresh['role']!='owner':continue
                if kind=='employee':
                    try:require_permission(self.office,fresh,'personnel.read')
                    except Problem:continue
                found=self.db.execute('SELECT id FROM '+table+' WHERE LOWER('+label+') LIKE ? ORDER BY '+label+',id LIMIT 501',('%'+query.lower()+'%',)).fetchall()
                limited=limited or len(found)>500
                for row in found[:500]:
                    try:_,value=subject(self.office,fresh,kind,row['id'])
                    except Problem as error:
                        if error.status in (403,404):continue
                        raise
                    results.append(dict(kind=kind,id=value['id'],label=value['label']))
            handlers=[]
            for row in self.db.execute('SELECT id,email FROM users WHERE active=1 ORDER BY email,id'):
                if fresh['role']!='owner' and row['id']!=fresh['id']:continue
                try:require_permission(self.office,dict(id=row['id']),'privacy.manage')
                except Problem:continue
                handlers.append(dict(row))
            return dict(subjects=results,handlers=handlers,limited=limited)

    def _receipt(self,actor,case_id,operation,data):
        identifier(data.get('request_id'))
        fingerprint=sha([case_id,operation,data])
        row=self.db.execute('SELECT * FROM business_privacy_case_requests WHERE user_id=? AND request_id=?',(actor['id'],data['request_id'])).fetchone()
        if row and (row['operation']!=operation or row['request_sha256']!=fingerprint or row['case_id']!=case_id):
            raise Problem(409,'Diese Vorgangskennung wurde bereits anders verwendet.')
        return fingerprint,json.loads(row['result_ref_json']) if row else None

    def _remember(self,actor,case_id,operation,data,fingerprint,reference):
        self.db.execute('INSERT INTO business_privacy_case_requests(user_id,request_id,case_id,operation,request_sha256,result_ref_json) VALUES(?,?,?,?,?,?)',
            (actor['id'],data['request_id'],case_id,operation,fingerprint,canonical(reference)))

    def create(self,actor,data):
        _shape(data,('request_id','id','subject_kind','subject_id','request_kind','received_date','due_date','assigned_to','scope','retain_until','retention_reason'))
        with transaction(self.office):
            fresh,person=subject(self.office,actor,data['subject_kind'],data['subject_id']);self._gate()
            case_id=identifier(data['id']);fingerprint,replay=self._receipt(fresh,case_id,'create',data)
            if replay:return self.view(fresh,case_id)
            if self.db.execute('SELECT 1 FROM business_privacy_case_events WHERE case_id=?',(case_id,)).fetchone():raise Problem(409,'Fallkennung bereits vorhanden.')
            if data['request_kind'] not in KINDS:raise Problem(400,'Anfragetyp auswählen.')
            if _date(data['received_date'])>_date(self.today()) or _date(data['due_date'])<_date(data['received_date']) or _date(data['retain_until'])<_date(self.today()):
                raise Problem(400,'Eingangsdatum, Antwortfrist und begründete Aufbewahrung prüfen.')
            assignee=identifier(data['assigned_to']);subject(self.office,dict(id=assignee),data['subject_kind'],data['subject_id'])
            state={key:data[key] for key in ('subject_kind','subject_id','request_kind','received_date','due_date','assigned_to','retain_until')}
            state.update(id=case_id,creator_id=fresh['id'],subject_hash=sha([case_id,data['subject_kind'],data['subject_id']]),
                scope=_reference(data['scope']),retention_reason=_reference(data['retention_reason']),legal_hold=False,status='open',identity=None,inventory=None,
                reviews={},manual_reviews={},actions=[],response=None)
            self._record(fresh,state,'create');self._remember(fresh,case_id,'create',data,fingerprint,dict(case_id=case_id))
            return self.view(fresh,case_id)

    def _command(self,actor,case_id,operation,data,callback,*,closed=False):
        if not isinstance(data,dict):raise Problem(400,'JSON-Objekt erwartet.')
        with transaction(self.office):
            fresh,event,state=self._load(actor,case_id);self._gate()
            fingerprint,replay=self._receipt(fresh,case_id,operation,data)
            if replay:return dict(case=self.view(fresh,case_id),receipt=replay)
            if state is None:raise Problem(409,'Private Fallinhalte wurden bereits gelöscht.')
            if type(data.get('revision')) is not int or data['revision']!=event['revision']:raise Problem(409,'Fall wurde geändert; aktuellen Stand laden.')
            if state['status']=='closed' and not closed:raise Problem(409,'Abgeschlossenen Fall nicht still verändern; Folgeanfrage getrennt aufnehmen.')
            reference=callback(fresh,state)
            self._record(fresh,state,operation,event)
            reference=reference or dict(case_id=case_id)
            self._remember(fresh,case_id,operation,data,fingerprint,reference)
            return dict(case=self.view(fresh,case_id),receipt=reference)

    def identity(self,actor,case_id,data):
        _shape(data,('request_id','revision','method','evidence','confirmed'))
        def change(fresh,state):
            if data['confirmed'] is not True or data['method'] not in ('existing_contact_channel','in_person','authenticated_account','other'):
                raise Problem(400,'Identitätsprüfung ausdrücklich bestätigen.')
            state['identity']=dict(method=data['method'],evidence=_reference(data['evidence']),verified_by=fresh['id'],verified_at=self.now())
            state['status']='verified'
        return self._command(actor,case_id,'identity',data,change)

    def scan(self,actor,case_id,data):
        _shape(data,('request_id','revision'))
        def change(fresh,state):
            if not state['identity']:raise Problem(409,'Identität vor der Quellensammlung prüfen.')
            value=inventory(self.office,fresh,state['subject_kind'],state['subject_id'])
            state['inventory']={key:value[key] for key in ('sources','blocked_tables','manual_tables','closure_limit_reached','sha256')}
            state['reviews']={key:review for key,review in state['reviews'].items() if any(v['key']==key and v['sha256']==review['source_sha256'] for v in value['sources'])}
            state['manual_reviews']={};state['status']='reviewing'
        return self._command(actor,case_id,'scan',data,change)

    def sources(self,actor,case_id):
        with transaction(self.office):
            fresh,_,state=self._load(actor,case_id)
            if not state or not state['identity']:raise Problem(409,'Identität vor der Quellensammlung prüfen.')
            return inventory(self.office,fresh,state['subject_kind'],state['subject_id'])

    def source(self,actor,case_id,key):
        with transaction(self.office):
            fresh,_,state=self._load(actor,case_id)
            source=next((v for v in (state.get('inventory') or {}).get('sources',[]) if v['key']==key),None) if state else None
            if source is None:raise Problem(404,'Geprüfte Fallquelle nicht vorhanden.')
            value,_=resolve(self.office,fresh,source)
            return dict(source=source,value=value)

    def review(self,actor,case_id,data):
        _shape(data,('request_id','revision','source_key','source_sha256','decision','reason','redacted_value','include_originals'))
        def change(fresh,state):
            source=next((v for v in (state.get('inventory') or {}).get('sources',[]) if v['key']==data['source_key']),None)
            if source is None or source['sha256']!=data['source_sha256']:raise Problem(409,'Aktuelle Fallquelle auswählen.')
            resolve(self.office,fresh,source,export=data['decision'] in ('include','redact'))
            if data['decision'] not in ('include','redact','retain','not_subject','erase_master') or type(data['include_originals']) is not bool:
                raise Problem(400,'Quellenentscheidung auswählen.')
            if data['decision']=='erase_master' and (state['subject_kind']!='customer' or source['table']!='customers'):
                raise Problem(409,'Nur Kontaktstammdaten unterstützen diese Löschaktion; Fachhistorien bleiben gesperrt.')
            if data['decision']=='redact':
                if not isinstance(data['redacted_value'],dict) or not data['redacted_value']:raise Problem(400,'Geprüften redigierten Dateninhalt als JSON-Objekt angeben.')
            elif data['redacted_value'] is not None:raise Problem(400,'Redigierte Inhalte nur bei ausdrücklicher Redaktion angeben.')
            if data['include_originals'] and (data['decision']!='include' or not source['binary_fields']):raise Problem(400,'Originale separat prüfen und nur bei unveränderter Aufnahme bestätigen.')
            state['reviews'][source['key']]=dict(source_sha256=source['sha256'],decision=data['decision'],reason=_reference(data['reason']),
                redacted_value=data['redacted_value'],include_originals=data['include_originals'],reviewed_by=fresh['id'],reviewed_at=self.now())
        return self._command(actor,case_id,'review',data,change)

    def manual(self,actor,case_id,data):
        _shape(data,('request_id','revision','area','decision','evidence'))
        def change(fresh,state):
            if not state['inventory']:raise Problem(409,'Zuerst strukturierte Quellen erfassen.')
            if data['area'] not in MANUAL_AREAS or data['decision'] not in ('checked','not_applicable','pending'):raise Problem(400,'Manuellen Prüfbereich und Ergebnis auswählen.')
            state['manual_reviews'][data['area']]=dict(decision=data['decision'],evidence=_reference(data['evidence']),reviewed_by=fresh['id'],reviewed_at=self.now())
        return self._command(actor,case_id,'manual',data,change)

    def manage(self,actor,case_id,data):
        _shape(data,('request_id','revision','due_date','assigned_to','retain_until','retention_reason','legal_hold','reason','notification_evidence'))
        def change(fresh,state):
            if type(data['legal_hold']) is not bool:raise Problem(400,'Aufbewahrungssperre ausdrücklich angeben.')
            subject(self.office,dict(id=identifier(data['assigned_to'])),state['subject_kind'],state['subject_id'])
            if _date(data['due_date'])<_date(state['received_date']) or _date(data['retain_until'])<_date(self.today()):raise Problem(400,'Frist und Aufbewahrung prüfen.')
            reason=_reference(data['reason'])
            if data['due_date']>state['due_date']:_reference(data['notification_evidence'])
            state.update({key:data[key] for key in ('due_date','assigned_to','retain_until','legal_hold')})
            state['retention_reason']=_reference(data['retention_reason'])
            state['actions'].append(dict(kind='case_management',reason=reason,notification_evidence=data['notification_evidence'],at=self.now()))
        return self._command(actor,case_id,'manage',data,change,closed=True)

    def _ready(self,fresh,state,*,export=False):
        current=state['inventory']
        if not state['identity'] or not current:raise Problem(409,'Identitätsprüfung und Quelleninventur fehlen.')
        if any(area not in state['manual_reviews'] or state['manual_reviews'][area]['decision']=='pending' for area in MANUAL_AREAS):
            raise Problem(409,'Manuelle Quellen-, Empfänger-, Backup- und Aufbewahrungsprüfung abschließen.')
        live=inventory(self.office,fresh,state['subject_kind'],state['subject_id'])
        if live['sha256']!=current['sha256']:raise Problem(409,'Der Quellenbestand wurde erweitert oder geändert; Bestandsaufnahme erneut prüfen.')
        for source in current['sources']:
            review=state['reviews'].get(source['key'])
            if not review or review['source_sha256']!=source['sha256']:raise Problem(409,'Alle erfassten Quellen begründet entscheiden.')
            resolve(self.office,fresh,source,export=export and review['decision'] in ('include','redact'))

    def export(self,actor,case_id,data):
        _shape(data,('request_id','revision','expires_on','confirmed'))
        def change(fresh,state):
            self._ready(fresh,state,export=True)
            if data['confirmed'] is not True or not _date(self.today())<=_date(data['expires_on'])<=_date(state['retain_until']):raise Problem(400,'Exportfreigabe und Ablauf innerhalb der Fallaufbewahrung angeben.')
            if state['subject_kind']=='employee':require_permission(self.office,fresh,'personnel.export')
            stream=io.BytesIO();files=[];total=0;rows=[]
            export_id=uuid.uuid4().hex
            with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as package:
                for source in state['inventory']['sources']:
                    review=state['reviews'][source['key']]
                    if review['decision'] not in ('include','redact'):continue
                    value,originals=resolve(self.office,fresh,source,export=True)
                    if review['decision']=='redact':value=review['redacted_value']
                    entry=dict(source=source,decision=review['decision'],data=value,files=[])
                    if review['include_originals']:
                        for column,raw in originals.items():
                            path='originals/'+source['key']+'/'+column+'.bin';total+=len(raw)
                            if total>MAX_EXPORT:raise Problem(413,'Geprüfter Personenexport überschreitet die Größe; kein Teilarchiv wurde gespeichert.')
                            package.writestr(path,raw);entry['files'].append(dict(path=path,size=len(raw),sha256=sha(raw)))
                    rows.append(entry)
                if not rows:raise Problem(409,'Mindestens eine ausdrücklich geprüfte Quelle für den Export aufnehmen.')
                legacy=None
                if state['subject_kind']=='customer':
                    for project in self.db.execute('SELECT id FROM projects WHERE customer_id=?',(state['subject_id'],)):
                        self.office.project(fresh,project['id'])
                    original=BusinessFoundation(self.office).export_contact(fresh,state['subject_id'])
                    legacy=dict(id=original['id'],coverage=original['coverage'],limitations=original['limitations'])
                payload=canonical(dict(case_id=case_id,export_id=export_id,subject_kind=state['subject_kind'],subject_id=state['subject_id'],
                    data=rows,legacy_contact_review=legacy,automatic_completeness=False,limitations=['Manuell geprüfte Auswahl; keine automatische vollständige Auskunft.',
                    'Externe Systeme, Empfänger, Backups und ausgelassene geschützte Quellen bleiben im Fall dokumentiert.'])) .encode()
                total+=len(payload)
                if total>MAX_EXPORT:raise Problem(413,'Personenexport überschreitet die geprüfte Größe.')
                package.writestr('subject-data.json',payload)
                package.writestr('README.txt','Personenbezogene vertrauliche Daten. Nur an den geprüften Betroffenen oder dessen bestätigte Vertretung übergeben. Keine Nachricht wurde versandt. Das Archiv ist nicht verschlüsselt.\n')
            raw=stream.getvalue()
            if len(raw)>MAX_EXPORT:raise Problem(413,'Personenexport überschreitet die geprüfte Größe.')
            meta=dict(id=export_id,case_id=case_id,source_revision=state['revision'],source_inventory_sha256=state['inventory']['sha256'],
                sha256=sha(raw),size=len(raw),source_count=len(rows),expires_on=data['expires_on'],automatic_completeness=False)
            self.db.execute('INSERT INTO business_privacy_case_exports(id,case_id,case_revision,metadata_json,sha256,size,expires_on,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                (export_id,case_id,state['revision'],canonical(meta),sha(raw),len(raw),data['expires_on'],fresh['id'],self.now()))
            self.db.execute('INSERT INTO business_privacy_case_export_blobs(export_id,content) VALUES(?,?)',(export_id,raw))
            state['actions'].append(dict(kind='export_created',export_id=export_id,sha256=sha(raw),at=self.now()))
            return dict(case_id=case_id,export_id=export_id)
        return self._command(actor,case_id,'export',data,change)

    def download(self,actor,case_id,export_id):
        identifier(export_id)
        with transaction(self.office):
            fresh,_,state=self._load(actor,case_id)
            if state and state['subject_kind']=='employee':require_permission(self.office,fresh,'personnel.export')
            row=self.db.execute('SELECT * FROM business_privacy_case_exports WHERE id=? AND case_id=?',(export_id,case_id)).fetchone()
            if row is None:raise Problem(404,'Fallgebundener Export nicht verfügbar.')
            if state is None or self._purged('export',export_id) or row['expires_on']<self.today():raise Problem(410,'Privater Export ist abgelaufen oder wurde gelöscht.')
            _,_,snapshot=self._load(fresh,case_id,row['case_revision'])
            for source in snapshot['inventory']['sources']:
                review=snapshot['reviews'].get(source['key'])
                if review and review['decision'] in ('include','redact'):resolve(self.office,fresh,source,export=True)
            blob=self.db.execute('SELECT content FROM business_privacy_case_export_blobs WHERE export_id=?',(export_id,)).fetchone()
            if blob is None or sha(bytes(blob['content']))!=row['sha256']:raise Problem(409,'Exportinhalt fehlt oder wurde verändert.')
            self.office.audit(fresh,'privacy.case.export_downloaded',export_id)
            return BinaryAttachment(bytes(blob['content']),'Datenauskunft-'+case_id+'.zip')

    def correct(self,actor,case_id,data):
        _shape(data,('request_id','revision','source_revision','changes','reason','confirmed'))
        def change(fresh,state):
            if not state['identity'] or state['request_kind']!='rectification' or data['confirmed'] is not True:raise Problem(409,'Bestätigten Berichtigungsfall mit geprüfter Identität öffnen.')
            if state['subject_kind']!='customer':raise Problem(409,'Diese Quelle benötigt ihre bestehende Fachberichtigung; Durchführung im manuellen Quellenentscheid dokumentieren.')
            changes=data['changes']
            if not isinstance(changes,dict) or not changes or set(changes)-{'name','contact','email','phone','address','notes'}:raise Problem(400,'Nur ausdrücklich ausgewählte Kontaktstammdaten berichtigen.')
            before=BusinessFoundation(self.office).contact(fresh,state['subject_id'])
            after=BusinessFoundation(self.office).save_contact(fresh,dict(request_id=data['request_id'],revision=data['source_revision'],**changes),state['subject_id'])
            state['actions'].append(dict(kind='contact_rectified',before_sha256=sha(before),after_sha256=sha(after),source_revision=after['revision'],reason=_reference(data['reason']),at=self.now()))
            state['inventory']=None;state['reviews']={};state['manual_reviews']={};state['status']='verified'
        return self._command(actor,case_id,'correct',data,change)

    def erase(self,actor,case_id,data):
        _shape(data,('request_id','revision','contact_revision','reason','confirmed'))
        def change(fresh,state):
            self._ready(fresh,state)
            if state['request_kind']!='erasure' or state['subject_kind']!='customer' or data['confirmed'] is not True:raise Problem(409,'Nur ausdrücklich geprüfte Kontaktstammdaten können hier anonymisiert werden.')
            require_permission(self.office,fresh,'contacts.write')
            if not any(source['table']=='customers' and state['reviews'][source['key']]['decision']=='erase_master' for source in state['inventory']['sources']):raise Problem(409,'Kontaktstamm in der Quellenprüfung ausdrücklich zur Anonymisierung auswählen.')
            result=BusinessFoundation(self.office).erase_contact(fresh,state['subject_id'],dict(request_id=data['request_id'],revision=data['contact_revision'],confirmed=True))
            state['actions'].append(dict(kind='contact_erasure',result=result,reason=_reference(data['reason']),at=self.now(),scope='contact_master_only',case_evidence_retained_until=state['retain_until']))
            # Source changes after successful erasure invalidate prior previews.
            if result['status']=='erased':state['inventory']=None;state['reviews']={};state['manual_reviews']={};state['status']='verified'
            return dict(case_id=case_id,erasure_request_id=result['id'],status=result['status'])
        return self._command(actor,case_id,'erase',data,change)

    def close(self,actor,case_id,data):
        _shape(data,('request_id','revision','outcome','response_date','response_evidence','reason','confirmed'))
        def change(fresh,state):
            if (not state['identity'] and data['outcome']!='refused') or data['confirmed'] is not True or data['outcome'] not in ('fulfilled','partially_fulfilled','refused'):
                raise Problem(400,'Geprüfte Antwort und ausdrücklichen Abschluss angeben.')
            if _date(data['response_date'])<_date(state['received_date']) or _date(data['response_date'])>_date(self.today()):raise Problem(400,'Tatsächliches Antwortdatum prüfen.')
            if data['outcome']=='fulfilled':
                self._ready(fresh,state)
                if state['inventory']['blocked_tables'] or state['inventory']['closure_limit_reached']:raise Problem(409,'Gesperrte Quellen verhindern eine vollständige Erledigungsbestätigung.')
                if state['request_kind']=='erasure' and not any(v['kind']=='contact_erasure' and v['result']['status']=='erased' for v in state['actions']):raise Problem(409,'Löschung ist nicht nachgewiesen; begründete Teilantwort oder Ablehnung dokumentieren.')
            state['response']=dict(outcome=data['outcome'],response_date=data['response_date'],response_evidence=_reference(data['response_evidence']),reason=_reference(data['reason']),
                confirmed_by=fresh['id'],automatic_completeness=False,external_messages_sent=False)
            state['status']='closed'
        return self._command(actor,case_id,'close',data,change)

    def purge(self,actor,case_id,data,*,export_id=None):
        _shape(data,('request_id','revision','confirmed','reason'))
        kind='export' if export_id else 'case';object_id=identifier(export_id or case_id)
        with transaction(self.office):
            fresh,event,state=self._load(actor,case_id);self._gate()
            if fresh['role']!='owner':raise Problem(403,'Private Arbeitskopien löscht ausschließlich die aktive Geschäftsführung.')
            operation='purge_'+kind+':'+object_id
            fingerprint,replay=self._receipt(fresh,case_id,operation,data)
            if replay:return dict(case=self.view(fresh,case_id),receipt=replay)
            if state is None:raise Problem(409,'Private Fallinhalte bereits gelöscht.')
            if data['revision']!=event['revision'] or data['confirmed'] is not True:raise Problem(409,'Aktuellen Fallstand ausdrücklich bestätigen.')
            _reference(data['reason'])
            if state['legal_hold']:raise Problem(409,'Dokumentierte Aufbewahrungssperre zuerst begründet bearbeiten.')
            if kind=='case' and (state['status']!='closed' or state['retain_until']>=self.today()):raise Problem(409,'Private Fallinhalte erst nach Abschluss und Ablauf der dokumentierten Aufbewahrung löschen.')
            if export_id and not self.db.execute('SELECT 1 FROM business_privacy_case_exports WHERE id=? AND case_id=?',(export_id,case_id)).fetchone():raise Problem(404,'Fallgebundener Export nicht vorhanden.')
            import business_schema
            helper=getattr(business_schema,'checkpoint_before_privacy_'+kind+'_purge',None)
            if helper is None:raise Problem(409,'Unabhängiger Datenschutz-Checkpoint unterstützt diesen Vorgang noch nicht.')
            checkpoint=helper(self.office,object_id,data['request_id'])
            if not isinstance(checkpoint,dict) or not re.fullmatch(r'[a-f0-9]{64}',checkpoint.get('digest','')):raise Problem(409,'Unabhängiger Löschcheckpoint nicht bestätigt.')
            _purge_private(self.office,kind,object_id,checkpoint['digest'],fresh['id'],self.now())
            reference=dict(case_id=case_id,purged_kind=kind,object_id=object_id)
            self._remember(fresh,case_id,operation,data,fingerprint,reference)
            self.office.audit(fresh,'privacy.case.purged_'+kind,object_id)
            return dict(case=self.view(fresh,case_id),receipt=reference)


def _purge_private(office,kind,object_id,checkpoint,actor_id,stamp):
    if not office.db.execute('SELECT 1 FROM business_privacy_case_purges WHERE kind=? AND object_id=?',(kind,object_id)).fetchone():
        office.db.execute('INSERT INTO business_privacy_case_purges(kind,object_id,checkpoint_digest,created_by,created_at) VALUES(?,?,?,?,?)',(kind,object_id,checkpoint,actor_id,stamp))
    if kind=='case':
        office.db.execute('DELETE FROM business_privacy_case_contents WHERE case_id=?',(object_id,))
        office.db.execute('DELETE FROM business_privacy_case_export_blobs WHERE export_id IN (SELECT id FROM business_privacy_case_exports WHERE case_id=?)',(object_id,))
    else:office.db.execute('DELETE FROM business_privacy_case_export_blobs WHERE export_id=?',(object_id,))


def reapply_privacy_checkpoint(office,event):
    from business_schema import privacy_subject_hash
    from core import now_iso
    kind={'purge_privacy_case':'case','purge_privacy_export':'export'}.get(event.get('operation'))
    if kind is None or event.get('subject_kind')!='privacy_'+kind:raise ValueError('Unsupported private case checkpoint')
    query='SELECT DISTINCT case_id AS id FROM business_privacy_case_events' if kind=='case' else 'SELECT id FROM business_privacy_case_exports'
    for row in office.db.execute(query).fetchall():
        if privacy_subject_hash('privacy_'+kind,row['id'])==event.get('subject_hash'):
            owner=office.db.execute("SELECT id FROM users WHERE role='owner' AND active=1 ORDER BY id LIMIT 1").fetchone()
            if owner is None:raise ValueError('Private purge requires accountable owner')
            _purge_private(office,kind,row['id'],sha(event),owner['id'],now_iso())


def validate_integrity(office):
    previous={}
    for row in office.db.execute('SELECT * FROM business_privacy_case_events ORDER BY case_id,revision'):
        try:
            identifier(row['id']);identifier(row['case_id'])
            event=dict(row);digest=event.pop('event_sha256')
            if sha(event)!=digest:raise ValueError('Changed private event')
            old=previous.get(row['case_id'])
            if row['revision']!=(old['revision']+1 if old else 1) or row['previous_hash']!=(old['event_sha256'] if old else None):raise ValueError('Private case chain gap')
            metadata=json.loads(row['metadata_json'])
            if metadata['id']!=row['case_id'] or metadata['request_kind'] not in KINDS:raise ValueError('Case metadata binding')
            content=office.db.execute('SELECT * FROM business_privacy_case_contents WHERE event_id=?',(row['id'],)).fetchone()
            purged=office.db.execute("SELECT 1 FROM business_privacy_case_purges WHERE kind='case' AND object_id=?",(row['case_id'],)).fetchone()
            if purged and content is not None or not purged and content is None:raise ValueError('Case content/purge mismatch')
            if content:
                state=_decode(content['content'])
                if content['case_id']!=row['case_id'] or sha(bytes(content['content']))!=row['content_sha256'] or state['id']!=row['case_id'] or state['revision']!=row['revision'] or any(state[k]!=v for k,v in metadata.items()):raise ValueError('Changed private content')
                if state['subject_hash']!=sha([state['id'],state['subject_kind'],state['subject_id']]):raise ValueError('Changed subject binding')
            previous[row['case_id']]=row
        except (KeyError,TypeError,ValueError,Problem) as error:raise ValueError('Invalid privacy case evidence') from error
    for row in office.db.execute('SELECT * FROM business_privacy_case_exports'):
        blob=office.db.execute('SELECT content FROM business_privacy_case_export_blobs WHERE export_id=?',(row['id'],)).fetchone()
        purged=office.db.execute("SELECT 1 FROM business_privacy_case_purges WHERE (kind='case' AND object_id=?) OR (kind='export' AND object_id=?)",(row['case_id'],row['id'])).fetchone()
        if row['case_id'] not in previous or purged and blob or not purged and not blob:raise ValueError('Private export/purge mismatch')
        if blob and (sha(bytes(blob['content']))!=row['sha256'] or len(blob['content'])!=row['size']):raise ValueError('Changed private export')
    return True


def methods(path):
    if path=='/privacy/cases':return 'GET, POST'
    if path=='/privacy/cases/options':return 'GET'
    if re.fullmatch('/privacy/cases/'+ID+r'(?:/(?:sources|sources/[a-f0-9]{64}|exports/'+ID+'|commands/'+ID+'))?',path):return 'GET'
    if re.fullmatch('/privacy/cases/'+ID+r'/(?:identity|scan|review|manual|manage|export|correct|erase|close|purge|exports/'+ID+'/purge)',path):return 'POST'
    return None


def dispatch(office,actor,path,method,data):
    allowed=methods(path)
    if allowed is None:return None
    if method not in allowed.split(', '):raise Problem(405,'Methode nicht erlaubt.')
    if not isinstance(data,dict):raise Problem(400,'JSON-Objekt erwartet.')
    query=data.get('_query',{})
    if path=='/privacy/cases/options':
        if set(data)-{'_query'} or set(query)-{'q'}:raise Problem(400,'Nur den Suchbegriff angeben.')
        return PrivacyCases(office).options(actor,query.get('q','')),200,'application/json'
    if query:raise Problem(400,'Keine zusätzlichen Datenschutzfilter erlaubt.')
    payload={k:v for k,v in data.items() if k!='_query'}
    if method=='GET' and payload:raise Problem(400,'GET ohne Anfragekörper erwartet.')
    api=PrivacyCases(office)
    if path=='/privacy/cases':return (api.list(actor) if method=='GET' else api.create(actor,payload)),200,'application/json'
    pieces=path.split('/');case_id=pieces[3]
    if len(pieces)==4:return api.view(actor,case_id),200,'application/json'
    operation=pieces[4]
    if operation=='commands':return api.command_status(actor,case_id,pieces[5]),200,'application/json'
    if operation=='sources':return (api.sources(actor,case_id) if len(pieces)==5 else api.source(actor,case_id,pieces[5])),200,'application/json'
    if operation=='exports':
        if method=='GET':return api.download(actor,case_id,pieces[5]),200,'application/zip'
        return api.purge(actor,case_id,payload,export_id=pieces[5]),200,'application/json'
    return getattr(api,operation)(actor,case_id,payload),200,'application/json'
