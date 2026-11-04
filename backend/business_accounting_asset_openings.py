"""Immutable evidenced historical assets, separate from acquisitions and cash."""
import base64
import binascii
from datetime import date,datetime,timedelta,timezone
import json
import re
import sqlite3
import uuid
import unicodedata
from urllib.parse import quote
from zoneinfo import ZoneInfo

from core import Problem,canonical
from business_operations import identifier,instant,iso_date,transaction,_image_check
from business_accounting import Accounting
from business_foundation import require_permission
from business_accounting_openings import (OpeningBalances,MAX_FILE,ID,sha,shape,hash_value,integer,line,
    profile_reference,event_reference,state_hash,stored)
from accounting_asset_opening_rules import RULE_VERSION,ROUNDING,asset_key,normalize_asset,original_schedule,continuation

FEATURES=('accounting_historical_assets',)
BASE='/accounting/historical-assets'
TABLES=tuple('business_accounting_asset_opening_'+name for name in ('originals','events','requests'))
INPUT={'expected_revision','state_hash','asset_key','profile_ref','status','opening_date','asset','source','reason'}
FLAGS=dict(schema_version=1,rule_version=RULE_VERSION,cash_flow_created=False,tax_postings_created=False,
           acquisition_created=False,euer_postings_created=False,balance_timing='start_of_day',timezone='Europe/Berlin')


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA','BLOB'):raise ValueError('Unsupported asset original binary type')
    return [f'''CREATE TABLE IF NOT EXISTS {TABLES[0]}(
        id TEXT PRIMARY KEY,asset_key TEXT NOT NULL,filename TEXT NOT NULL,media_type TEXT NOT NULL,
        size INTEGER NOT NULL CHECK(size>0),sha256 TEXT NOT NULL,original {binary_type} NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,UNIQUE(asset_key,sha256))''',
        f'''CREATE TABLE IF NOT EXISTS {TABLES[1]}(
        id TEXT PRIMARY KEY,sequence INTEGER NOT NULL UNIQUE CHECK(sequence>0),asset_key TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK(revision>0),previous_hash TEXT,payload_json TEXT NOT NULL,content_hash TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,UNIQUE(asset_key,revision))''',
        f'''CREATE TABLE IF NOT EXISTS {TABLES[2]}(
        user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,operation TEXT NOT NULL,
        request_json TEXT NOT NULL,request_hash TEXT NOT NULL,result_json TEXT NOT NULL,PRIMARY KEY(user_id,request_id))''']


def protected_tables():return TABLES
def runtime_privileges():return {table:('SELECT','INSERT') for table in TABLES}


def guard_statements(dialect):
    if dialect=='sqlite':
        values=[f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable historical asset evidence'); END"
                for table in TABLES for action in ('UPDATE','DELETE')]
        conditions=('id=NEW.id OR (asset_key=NEW.asset_key AND sha256=NEW.sha256)',
                    'id=NEW.id OR sequence=NEW.sequence OR (asset_key=NEW.asset_key AND revision=NEW.revision)',
                    'user_id=NEW.user_id AND request_id=NEW.request_id')
        return values+[f"CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition}) BEGIN SELECT RAISE(ABORT,'immutable historical asset evidence'); END"
                       for table,condition in zip(TABLES,conditions)]
    if dialect!='postgresql':raise ValueError('Unsupported historical asset dialect')
    values=["CREATE OR REPLACE FUNCTION business_asset_opening_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable historical asset evidence'; END; $$"]
    for table in TABLES:
        for action in ('UPDATE','DELETE'):
            name=table+'_'+action.lower()+'_guard'
            values.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION business_asset_opening_immutable_guard(); END IF; END $$")
    return values


def installed(office):
    from business_schema import _tables
    tables=_tables(office);present=set(TABLES)&tables
    marker='business_schema_migrations' in tables and office.db.execute("SELECT 1 FROM business_schema_migrations WHERE module='business_accounting_asset_openings'").fetchone()
    if not present and not marker:return False
    if present!=set(TABLES) or not marker:raise Problem(409,'Historischer Anlagenvortrag ist unvollständig installiert.')
    for dependency in ('business_accounting_euer','business_accounting_openings'):
        if not office.db.execute('SELECT 1 FROM business_schema_migrations WHERE module=?',(dependency,)).fetchone():
            raise Problem(409,'Abhängigkeiten des historischen Anlagenvortrags fehlen.')
    return True


class HistoricalAssets:
    def __init__(self,office,*,clock=None):
        self.office=office;self.db=office.db;self.clock=clock or (lambda:datetime.now(timezone.utc))

    now=OpeningBalances.now
    _lock=OpeningBalances._lock
    _profile=OpeningBalances._profile

    def _access(self,actor,write=False):
        fresh=Accounting(self.office)._access(actor,'accounting.admin' if write else None)
        if write:
            require_permission(self.office,fresh,'accounting.prepare');require_permission(self.office,fresh,'finance.write')
        if not installed(self.office):raise Problem(409,'Historischer Anlagenvortrag ist nicht installiert.')
        return fresh

    def _gate(self):
        from business_schema import require_capability
        require_capability(self.office,'business_accounting_asset_openings');Accounting(self.office)._write_gate()

    def _request(self,actor,operation,command):
        digest=sha([operation,command]);row=self.db.execute(f'SELECT * FROM {TABLES[2]} WHERE user_id=? AND request_id=?',(actor['id'],command['request_id'])).fetchone()
        if row:
            if row['operation']!=operation or row['request_json']!=canonical(command) or row['request_hash']!=digest:
                raise Problem(409,'Vorgangskennung wurde mit anderen ursprünglichen Anlagenwerten verwendet.')
            return digest,json.loads(row['result_json'])
        return digest,None

    def _remember(self,actor,operation,command,digest,result):
        self.db.execute(f'INSERT INTO {TABLES[2]}(user_id,request_id,operation,request_json,request_hash,result_json) VALUES(?,?,?,?,?,?)',
                        (actor['id'],command['request_id'],operation,canonical(command),digest,canonical(result)))

    @stored
    def _original(self,original_id,*,require_receipt=True):
        identifier(original_id);row=self.db.execute(f'SELECT * FROM {TABLES[0]} WHERE id=?',(original_id,)).fetchone()
        if not row:raise Problem(404,'Geschütztes Anlagenoriginal nicht vorhanden.')
        raw=bytes(row['original']);size=len(raw)
        if not 0<size<=MAX_FILE or size!=row['size'] or sha(raw)!=row['sha256'] or asset_key(row['asset_key'])!=row['asset_key']:
            raise Problem(409,'Anlagenoriginal besteht die Integritätsprüfung nicht.')
        if row['media_type'] not in ('application/pdf','image/png','image/jpeg'):raise Problem(409,'Unbekanntes Originalformat.')
        line(row['filename'],'Originaldateiname',200)
        if '/' in row['filename'] or '\\' in row['filename']:raise Problem(409,'Ungültiger Originaldateiname.')
        _image_check(raw,row['media_type']);identifier(row['created_by']);instant(row['created_at'])
        if require_receipt:
            accepted=False
            for receipt in self.db.execute(f"SELECT * FROM {TABLES[2]} WHERE operation='original'"):
                result=json.loads(receipt['result_json']);shape(result,('original_id',))
                if result['original_id']!=original_id:continue
                command=json.loads(receipt['request_json']);shape(command,('request_id','asset_key','filename','media_type','size','sha256'))
                identifier(command['request_id'])
                if (canonical(command)!=receipt['request_json'] or command['request_id']!=receipt['request_id']
                        or sha(['original',command])!=receipt['request_hash'] or any(command[key]!=row[key] for key in ('asset_key','filename','media_type','size','sha256'))):
                    raise Problem(409,'Ursprüngliche Anlagenoriginal-Annahme wurde verändert.')
                if receipt['user_id']==row['created_by']:accepted=True
            if not accepted:raise Problem(409,'Ursprüngliche Annahmequittung des Anlagenoriginals fehlt.')
        return dict({key:row[key] for key in row.keys() if key!='original'},path=BASE+'/originals/'+original_id),raw

    def upload_original(self,actor,data):
        shape(data,('request_id','asset_key','filename','media_type','content_base64'));identifier(data['request_id'])
        key=asset_key(data['asset_key'])
        if key!=data['asset_key']:raise Problem(400,'Original benötigt die normalisierte eindeutige Anlagenkennung.')
        line(data['filename'],'Originaldateiname',200)
        if '/' in data['filename'] or '\\' in data['filename'] or data['media_type'] not in ('application/pdf','image/png','image/jpeg'):
            raise Problem(400,'Einfacher Dateiname und PDF-/PNG-/JPEG-Anlagenoriginal erforderlich.')
        if not isinstance(data['content_base64'],str):raise Problem(400,'Originalbytes als Base64-Zeichenfolge erforderlich.')
        if len(data['content_base64'])>((MAX_FILE+2)//3)*4:raise Problem(413,'Anlagenoriginal bis 5 MiB erforderlich.')
        try:raw=base64.b64decode(data['content_base64'],validate=True)
        except (ValueError,binascii.Error):raise Problem(400,'Gültige Originalbytes erforderlich.') from None
        if not raw:raise Problem(400,'Leeres Anlagenoriginal ist nicht zulässig.')
        if len(raw)>MAX_FILE:raise Problem(413,'Anlagenoriginal bis 5 MiB erforderlich.')
        _image_check(raw,data['media_type'])
        safe={key:value for key,value in data.items() if key!='content_base64'};safe.update(size=len(raw),sha256=sha(raw))
        with transaction(self.office):
            self._lock();fresh=self._access(actor,True);self._gate();digest,replay=self._request(fresh,'original',safe)
            if replay:return self._original(replay['original_id'])[0]
            old=self.db.execute(f'SELECT id FROM {TABLES[0]} WHERE asset_key=? AND sha256=?',(key,safe['sha256'])).fetchone()
            if old:
                value=self._original(old['id'])[0]
                if value['filename']!=data['filename'] or value['media_type']!=data['media_type']:raise Problem(409,'Dasselbe Anlagenoriginal besitzt bereits andere ursprüngliche Dateimetadaten.')
            else:
                original_id=uuid.uuid4().hex
                self.db.execute(f'INSERT INTO {TABLES[0]}(id,asset_key,filename,media_type,size,sha256,original,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                                (original_id,key,data['filename'],data['media_type'],len(raw),safe['sha256'],raw,fresh['id'],self.now()))
                value=self._original(original_id,require_receipt=False)[0]
            self._remember(fresh,'original',safe,digest,dict(original_id=value['id']));self.office.audit(fresh,'business.accounting.asset_original',value['id'])
            return value

    def original(self,actor,original_id):
        from workspace_api import BinaryAttachment
        with transaction(self.office):
            self._access(actor);value,raw=self._original(original_id);self._access(actor)
            return BinaryAttachment(raw,value['filename']),value['media_type']

    def identity(self,actor,data):
        shape(data,('inventory_number',))
        with transaction(self.office):
            self._access(actor)
            return dict(schema_version=1,inventory_number=data['inventory_number'],asset_key=asset_key(data['inventory_number']))

    @staticmethod
    def _inputs(data,confirm=False):
        shape(data,INPUT|({'request_id','preview_hash','confirmation'} if confirm else set()))
        integer(data['expected_revision']);hash_value(data['state_hash'])
        if asset_key(data['asset_key'])!=data['asset_key']:raise Problem(400,'Normalisierte ursprüngliche Anlagenkennung erforderlich.')
        shape(data['profile_ref'],('id','revision','entry_sha256'));identifier(data['profile_ref']['id']);integer(data['profile_ref']['revision'],1);hash_value(data['profile_ref']['entry_sha256'])
        if data['status'] not in ('active','void'):raise Problem(400,'Belegte Anlagenübernahme oder ausdrückliche Aufhebung erforderlich.')
        iso_date(data['opening_date']);normalize_asset(data['asset'],data['opening_date']);line(data['reason'],'Prüf-/Korrekturgrund')
        if asset_key(data['asset']['inventory_number'])!=data['asset_key']:raise Problem(400,'Inventarnummer und unveränderliche Anlagenkennung widersprechen sich.')
        if confirm:
            identifier(data['request_id']);hash_value(data['preview_hash'])
            if data['confirmation'] is not True:raise Problem(400,'Historische Anlage und sämtliche Vortragswerte ausdrücklich bestätigen.')

    def _source(self,key,opening_date,source):
        shape(source,('original_id','sha256','position','history_through'));hash_value(source['sha256']);line(source['position'],'Eindeutige Originalposition',300);iso_date(source['history_through'])
        if source['history_through']!=(date.fromisoformat(opening_date)-timedelta(days=1)).isoformat():
            raise Problem(400,'Originalhistorie muss unmittelbar bis vor den bestätigten Übernahmestichtag reichen.')
        original=self._original(source['original_id'])[0]
        if original['asset_key']!=key or original['sha256']!=source['sha256']:raise Problem(409,'Anlagenoriginal gehört nicht zur ursprünglichen Inventaridentität.')
        return dict(original=original,position=source['position'],position_key=unicodedata.normalize('NFKC',source['position']).strip().casefold(),
                    history_through=source['history_through'],source_path=original['path'])

    def _open(self,data,old):
        from business_accounting_euer import EuerAccounting
        ledger=EuerAccounting(self.office)._ledger();earliest=min(data['opening_date'],old['opening_date'] if old else data['opening_date'])[:7]
        if any(period>=earliest and value['status']=='closed' for period,value in ledger['periods'].items()):
            raise Problem(409,'Betroffene EÜR-Perioden vor Änderung des Anlagenvortrags begründet wieder öffnen.')
        if any(entry['effect']['operation']=='opening_depreciation' and entry['effect']['source']['asset_key']==data['asset_key'] for entry in ledger['active'].values()):
            raise Problem(409,'Aktive Folgeabschreibungen vor Änderung ihrer historischen Anlagenquelle ausdrücklich gegenbuchen.')
        if data['status']=='active' and any(entry['effect']['operation']=='asset' and entry['effect']['source']['receipt']['original_sha256']==data['source']['sha256'] for entry in ledger['active'].values()):
            raise Problem(409,'Dieses Original ist bereits als neue EÜR-Anlage gebunden; keinen doppelten Anlagenvortrag anlegen.')

    def _prepare(self,ledger,data,*,historical=False):
        self._inputs(data)
        if data['expected_revision']!=len(ledger['entries']) or data['state_hash']!=state_hash(ledger['entries']):raise Problem(409,'Anlagenvortrag wurde geändert; aktuelle Vorschau erforderlich.')
        old=ledger['current'].get(data['asset_key']);profile=self._profile(data['profile_ref'])
        if data['opening_date']!=profile['profile']['bookkeeping_start']:raise Problem(409,'Historische Übernahme muss genau am bestätigten Buchführungsbeginn liegen.')
        if data['status']=='void':
            if not old or old['status']!='active' or any(data[key]!=old[key] for key in ('profile_ref','opening_date','asset','source')):
                raise Problem(409,'Aufhebung benötigt genau die aktive unveränderte Anlagenfassung.')
        elif not historical:
            if data['profile_ref']!=profile_reference(self._profile()):raise Problem(409,'Aktuelles ausdrücklich bestätigtes Buchführungsprofil erforderlich.')
            if data['opening_date']>self.clock().astimezone(ZoneInfo('Europe/Berlin')).date().isoformat():raise Problem(409,'Keinen künftigen Anlagenbestand als tatsächlich übernommen bestätigen.')
        proof=self._source(data['asset_key'],data['opening_date'],data['source'])
        if data['status']=='active' and any(entry['status']=='active' and entry['asset_key']!=data['asset_key']
                and entry['source_proof']['original']['sha256']==proof['original']['sha256']
                and entry['source_proof']['position_key']==proof['position_key'] for entry in ledger['current'].values()):
            raise Problem(409,'Dieselbe ursprüngliche Anlagenposition ist bereits unter einer anderen Inventarkennung übernommen.')
        if not historical:
            from business_accounting_open_items import require_unreserved_original
            require_unreserved_original(self.office,data['source']['sha256'])
            self._open(data,old)
        value=dict({key:data[key] for key in INPUT},**FLAGS,profile=profile,source_proof=proof,previous_ref=event_reference(old) if old else None,
                   original_schedule=original_schedule(data['asset']),start_year=continuation(data['asset'],data['opening_date'],int(data['opening_date'][:4])))
        return dict(value,preview_hash=sha(value))

    @stored
    def _ledger(self):
        ledger=dict(entries=[],current={},by_id={});receipts={}
        for row in self.db.execute(f"SELECT * FROM {TABLES[2]} WHERE operation='confirm'"):
            result=json.loads(row['result_json']);shape(result,('entry_id',))
            if result['entry_id'] in receipts:raise Problem(409,'Doppelte Anlagenvortragsquittung.')
            receipts[result['entry_id']]=row
        for row in self.db.execute(f'SELECT * FROM {TABLES[1]} ORDER BY sequence'):
            value=json.loads(row['payload_json']);previous=ledger['entries'][-1]['content_hash'] if ledger['entries'] else None
            if (canonical(value)!=row['payload_json'] or sha(value)!=row['content_hash'] or row['sequence']!=len(ledger['entries'])+1 or row['previous_hash']!=previous
                    or any(value.get(key)!=row[key] for key in ('id','sequence','asset_key','revision','previous_hash','created_by','created_at'))):
                raise Problem(409,'Unveränderliche Anlagenvortragsfolge ist ungültig.')
            old=ledger['current'].get(row['asset_key']);identifier(row['id']);identifier(row['created_by']);instant(row['created_at'])
            if row['revision']!=(old['revision']+1 if old else 1):raise Problem(409,'Anlagenfassungen sind nicht lückenlos.')
            receipt=receipts.get(row['id'])
            if not receipt:raise Problem(409,'Ursprüngliche Anlagenannahmequittung fehlt.')
            command=json.loads(receipt['request_json']);self._inputs(command,True)
            if (canonical(command)!=receipt['request_json'] or command['request_id']!=receipt['request_id'] or receipt['user_id']!=row['created_by']
                    or sha(['confirm',command])!=receipt['request_hash']):raise Problem(409,'Ursprünglicher Anlagenauftrag wurde verändert.')
            preview=self._prepare(ledger,{key:command[key] for key in INPUT},historical=True)
            expected=dict(preview,id=row['id'],sequence=row['sequence'],revision=row['revision'],previous_hash=previous,created_by=row['created_by'],created_at=row['created_at'])
            if value!=expected or command['preview_hash']!=preview['preview_hash']:raise Problem(409,'Anlagenvortrag ist nicht aus seinen Originalen reproduzierbar.')
            value=dict(value,content_hash=row['content_hash']);ledger['entries'].append(value);ledger['current'][row['asset_key']]=value;ledger['by_id'][row['id']]=value
        if len(receipts)!=len(ledger['entries']):raise Problem(409,'Verwaiste Anlagenvortragsquittung.')
        return ledger

    def state(self,actor):
        with transaction(self.office):
            fresh=self._access(actor);ledger=self._ledger();profile=self._profile(optional=True);writable=True
            try:self._access(fresh,True);self._gate()
            except Problem:writable=False
            originals=[self._original(row['id'])[0] for row in self.db.execute(f'SELECT id FROM {TABLES[0]} ORDER BY created_at,id')]
            return dict(**FLAGS,revision=len(ledger['entries']),state_hash=state_hash(ledger['entries']),profile=profile,
                        profile_ref=profile_reference(profile) if profile else None,items=list(ledger['current'].values()),originals=originals,
                        can_prepare=writable and profile is not None,max_original_bytes=MAX_FILE,supported_rounding=list(ROUNDING))

    def history(self,actor,key):
        if key!=asset_key(key):raise Problem(400,'Normalisierte Anlagenkennung erforderlich.')
        with transaction(self.office):
            self._access(actor);return dict(schema_version=1,asset_key=key,items=[entry for entry in self._ledger()['entries'] if entry['asset_key']==key])

    def preview(self,actor,data):
        self._inputs(data)
        with transaction(self.office):
            self._lock();self._access(actor,True);self._gate();return self._prepare(self._ledger(),data)

    def confirm(self,actor,data):
        self._inputs(data,True)
        with transaction(self.office):
            self._lock();fresh=self._access(actor,True);self._gate();ledger=self._ledger();digest,replay=self._request(fresh,'confirm',data)
            if replay:return ledger['by_id'][replay['entry_id']]
            try:
                preview=self._prepare(ledger,{key:data[key] for key in INPUT})
                if preview['preview_hash']!=data['preview_hash']:raise Problem(409,'Genau passende unveränderte Anlagenvorschau erforderlich.')
            except Problem as error:
                if error.status==409:raise Problem(409,error.message,request_resolution='not_accepted') from None
                raise
            old=ledger['current'].get(data['asset_key'])
            value=dict(preview,id=uuid.uuid4().hex,sequence=len(ledger['entries'])+1,revision=old['revision']+1 if old else 1,
                       previous_hash=ledger['entries'][-1]['content_hash'] if ledger['entries'] else None,created_by=fresh['id'],created_at=self.now())
            self._access(fresh,True)
            self.db.execute(f'INSERT INTO {TABLES[1]}(id,sequence,asset_key,revision,previous_hash,payload_json,content_hash,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                            (value['id'],value['sequence'],value['asset_key'],value['revision'],value['previous_hash'],canonical(value),sha(value),fresh['id'],value['created_at']))
            self._remember(fresh,'confirm',data,digest,dict(entry_id=value['id']));self.office.audit(fresh,'business.accounting.historical_asset_confirmed',value['id'])
            return dict(value,content_hash=sha(value))


def public_source(office,entry_id):
    identifier(entry_id);entry=HistoricalAssets(office)._ledger()['by_id'].get(entry_id)
    if not entry:raise Problem(404,'Historische Anlagenfassung fehlt.')
    value=dict(kind='opening_asset',schema_version=1,rule_version=RULE_VERSION,id=entry['id'],revision=entry['revision'],entry_hash=entry['content_hash'],
               asset_key=entry['asset_key'],status=entry['status'],opening_date=entry['opening_date'],profile_ref=entry['profile_ref'],
               asset=entry['asset'],source_proof=entry['source_proof'],source_path=BASE+'/history?asset_key='+quote(entry['asset_key'],safe=''))
    return dict(value,source_hash=sha(value))


def financial_access(office,actor,write=False):return HistoricalAssets(office)._access(actor,write)


def entrypoint(office,actor):
    if not installed(office):return None
    try:financial_access(office,actor)
    except Problem as error:
        if error.status in (403,404):return None
        raise
    return BASE


def validate_integrity(office):
    if not installed(office):return True
    api=HistoricalAssets(office)
    try:
        ledger=api._ledger();originals=set();covered=set()
        for row in office.db.execute(f'SELECT id FROM {TABLES[0]}'):originals.add(row['id']);api._original(row['id'])
        for row in office.db.execute(f'SELECT * FROM {TABLES[2]}'):
            command=json.loads(row['request_json']);result=json.loads(row['result_json']);identifier(row['user_id']);identifier(row['request_id'])
            if canonical(command)!=row['request_json'] or command['request_id']!=row['request_id'] or sha([row['operation'],command])!=row['request_hash']:raise ValueError('Changed historical asset receipt')
            if row['operation']=='original':
                shape(command,('request_id','asset_key','filename','media_type','size','sha256'));shape(result,('original_id',));original=api._original(result['original_id'])[0]
                if any(command[key]!=original[key] for key in ('asset_key','filename','media_type','size','sha256')):raise ValueError('Changed asset original receipt')
                covered.add(original['id'])
            elif row['operation']!='confirm' or result['entry_id'] not in ledger['by_id']:raise ValueError('Unknown historical asset receipt')
        if originals!=covered:raise ValueError('Missing historical asset original receipt')
        if isinstance(office.db,sqlite3.Connection):
            norm=lambda value:re.sub(r'\s+',' ',value.replace('IF NOT EXISTS ','')).strip().lower()
            for statement in guard_statements('sqlite'):
                name=re.search(r'CREATE TRIGGER IF NOT EXISTS (\w+)',statement)[1];row=office.db.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",(name,)).fetchone()
                if not row or norm(row[0])!=norm(statement):raise ValueError('Missing historical asset immutable guard')
        else:
            from business_documents import _validate_pg_guards
            _validate_pg_guards(office.db,guard_statements('postgresql'))
    except (Problem,ValueError,TypeError,KeyError,ArithmeticError) as error:raise ValueError('Invalid historical asset originals or journal') from error
    return True


def restore_horizon(office):
    with office.lock:
        if not installed(office):return None
        validate_integrity(office);tables={}
        for table in TABLES:
            values=[]
            for row in office.db.execute('SELECT * FROM '+table):
                value=dict(row)
                if 'original' in value:value['original']=dict(sha256=sha(bytes(value['original'])),size=len(value['original']))
                values.append(value)
            tables[table]=sorted(values,key=canonical)
        return dict(schema_version=1,table_counts={key:len(values) for key,values in tables.items()},sha256=sha(dict(schema_version=1,tables=tables)))


def methods(path):
    if path in (BASE,BASE+'/history') or re.fullmatch(BASE+'/originals/'+ID,path):return 'GET'
    if path in (BASE+'/originals',BASE+'/preview',BASE+'/confirm',BASE+'/identity'):return 'POST'
    return None


def dispatch(office,actor,path,method,data):
    allowed=methods(path)
    if allowed is None:return None
    if method!=allowed:raise Problem(405,'HTTP-Methode nicht erlaubt.')
    api=HistoricalAssets(office)
    if method=='POST':
        if not isinstance(data,dict) or '_query' in data:raise Problem(400,'Genauer JSON-Anlagenbefehl ohne Filter erforderlich.')
        action=path.rsplit('/',1)[-1];value=getattr(api,'upload_original' if action=='originals' else action)(actor,data)
        return value,200 if action in ('preview','identity') else 201,'application/json'
    if not isinstance(data,dict) or set(data)-{'_query'}:raise Problem(400,'GET erwartet keinen Anfragekörper.')
    query=data.get('_query',{})
    if path==BASE+'/history':shape(query,('asset_key',));value=api.history(actor,query['asset_key'])
    else:
        shape(query,())
        if '/originals/' in path:
            raw,media_type=api.original(actor,path.rsplit('/',1)[-1]);return raw,200,media_type
        value=api.state(actor)
    return value,200,'application/json'
