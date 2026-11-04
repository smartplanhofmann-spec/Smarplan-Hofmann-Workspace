"""Immutable original-backed yearly journal carryover; no new cash or tax claim."""
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
from accounting_open_item_rules import normalize_item,entity_key as external_key,money,cents
from accounting_year_opening_rules import RULE_VERSION,year_key as entity_key,calculate

FEATURES=('accounting_year_values',)
BASE='/accounting/year-values'
TABLES=tuple('business_accounting_year_opening_'+name for name in ('originals','events','requests'))
INPUT={'expected_revision','state_hash','entity_key','profile_ref','operation','payload','reason'}
FLAGS=dict(schema_version=1,rule_version=RULE_VERSION,cash_flow_created=False,new_input_vat_claim_created=False,timezone='Europe/Berlin')


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA','BLOB'):raise ValueError('Unsupported year opening original binary type')
    return [f'''CREATE TABLE IF NOT EXISTS {TABLES[0]}(
        id TEXT PRIMARY KEY,entity_key TEXT NOT NULL,filename TEXT NOT NULL,media_type TEXT NOT NULL,
        size INTEGER NOT NULL CHECK(size>0),sha256 TEXT NOT NULL,original {binary_type} NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,UNIQUE(entity_key,sha256))''',
        f'''CREATE TABLE IF NOT EXISTS {TABLES[1]}(
        id TEXT PRIMARY KEY,sequence INTEGER NOT NULL UNIQUE CHECK(sequence>0),entity_key TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK(revision>0),previous_hash TEXT,payload_json TEXT NOT NULL,content_hash TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,UNIQUE(entity_key,revision))''',
        f'''CREATE TABLE IF NOT EXISTS {TABLES[2]}(
        user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,operation TEXT NOT NULL,
        request_json TEXT NOT NULL,request_hash TEXT NOT NULL,result_json TEXT NOT NULL,PRIMARY KEY(user_id,request_id))''']


def protected_tables():return TABLES
def runtime_privileges():return {table:('SELECT','INSERT') for table in TABLES}


def guard_statements(dialect):
    if dialect=='sqlite':
        values=[f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable year opening evidence'); END"
                for table in TABLES for action in ('UPDATE','DELETE')]
        conditions=('id=NEW.id OR (entity_key=NEW.entity_key AND sha256=NEW.sha256)',
                    'id=NEW.id OR sequence=NEW.sequence OR (entity_key=NEW.entity_key AND revision=NEW.revision)',
                    'user_id=NEW.user_id AND request_id=NEW.request_id')
        return values+[f"CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition}) BEGIN SELECT RAISE(ABORT,'immutable year opening evidence'); END"
                       for table,condition in zip(TABLES,conditions)]
    if dialect!='postgresql':raise ValueError('Unsupported year opening dialect')
    values=["CREATE OR REPLACE FUNCTION business_year_opening_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable year opening evidence'; END; $$"]
    for table in TABLES:
        for action in ('UPDATE','DELETE'):
            name=table+'_'+action.lower()+'_guard'
            values.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION business_year_opening_immutable_guard(); END IF; END $$")
    return values


def installed(office):
    from business_schema import _tables
    tables=_tables(office);present=set(TABLES)&tables
    marker='business_schema_migrations' in tables and office.db.execute("SELECT 1 FROM business_schema_migrations WHERE module='business_accounting_year_openings'").fetchone()
    if not present and not marker:return False
    if present!=set(TABLES) or not marker:raise Problem(409,'Historischer Jahresvortragvortrag ist unvollständig installiert.')
    for dependency in ('business_accounting_euer','business_accounting_openings','business_accounting_asset_openings','business_accounting_open_items'):
        if not office.db.execute('SELECT 1 FROM business_schema_migrations WHERE module=?',(dependency,)).fetchone():
            raise Problem(409,'Abhängigkeiten des historischen Jahresvortragvortrags fehlen.')
    return True


class YearValues:
    def __init__(self,office,*,clock=None):
        self.office=office;self.db=office.db;self.clock=clock or (lambda:datetime.now(timezone.utc))

    now=OpeningBalances.now
    _lock=OpeningBalances._lock
    _profile=OpeningBalances._profile

    def _access(self,actor,write=False):
        fresh=Accounting(self.office)._access(actor,'accounting.admin' if write else None)
        if write:
            require_permission(self.office,fresh,'accounting.prepare');require_permission(self.office,fresh,'finance.write')
            from business_organization import require_active
            require_active(self.office,fresh,BASE,'business_accounting_year_openings')
        if not installed(self.office):raise Problem(409,'Historischer Jahresvortragvortrag ist nicht installiert.')
        return fresh

    def _gate(self):
        from business_schema import require_capability
        require_capability(self.office,'business_accounting_year_openings');Accounting(self.office)._write_gate()

    def _request(self,actor,operation,command):
        digest=sha([operation,command]);row=self.db.execute(f'SELECT * FROM {TABLES[2]} WHERE user_id=? AND request_id=?',(actor['id'],command['request_id'])).fetchone()
        if row:
            if row['operation']!=operation or row['request_json']!=canonical(command) or row['request_hash']!=digest:
                raise Problem(409,'Vorgangskennung wurde mit anderen ursprünglichen Jahresvortragwerten verwendet.')
            return digest,json.loads(row['result_json'])
        return digest,None

    def _remember(self,actor,operation,command,digest,result):
        self.db.execute(f'INSERT INTO {TABLES[2]}(user_id,request_id,operation,request_json,request_hash,result_json) VALUES(?,?,?,?,?,?)',
                        (actor['id'],command['request_id'],operation,canonical(command),digest,canonical(result)))

    @stored
    def _original(self,original_id,*,require_receipt=True):
        identifier(original_id);row=self.db.execute(f'SELECT * FROM {TABLES[0]} WHERE id=?',(original_id,)).fetchone()
        if not row:raise Problem(404,'Geschütztes Jahresvortragoriginal nicht vorhanden.')
        raw=bytes(row['original']);size=len(raw)
        if not 0<size<=MAX_FILE or size!=row['size'] or sha(raw)!=row['sha256'] or entity_key(row['entity_key'])!=row['entity_key']:
            raise Problem(409,'Jahresvortragoriginal besteht die Integritätsprüfung nicht.')
        if row['media_type'] not in ('application/pdf','image/png','image/jpeg'):raise Problem(409,'Unbekanntes Originalformat.')
        line(row['filename'],'Originaldateiname',200)
        if '/' in row['filename'] or '\\' in row['filename']:raise Problem(409,'Ungültiger Originaldateiname.')
        _image_check(raw,row['media_type']);identifier(row['created_by']);instant(row['created_at'])
        if require_receipt:
            accepted=False
            for receipt in self.db.execute(f"SELECT * FROM {TABLES[2]} WHERE operation='original'"):
                result=json.loads(receipt['result_json']);shape(result,('original_id',))
                if result['original_id']!=original_id:continue
                command=json.loads(receipt['request_json']);shape(command,('request_id','entity_key','filename','media_type','size','sha256'))
                identifier(command['request_id'])
                if (canonical(command)!=receipt['request_json'] or command['request_id']!=receipt['request_id']
                        or sha(['original',command])!=receipt['request_hash'] or any(command[key]!=row[key] for key in ('entity_key','filename','media_type','size','sha256'))):
                    raise Problem(409,'Ursprüngliche Jahresvortragoriginal-Annahme wurde verändert.')
                if receipt['user_id']==row['created_by']:accepted=True
            if not accepted:raise Problem(409,'Ursprüngliche Annahmequittung des Jahresvortragoriginals fehlt.')
        return dict({key:row[key] for key in row.keys() if key!='original'},path=BASE+'/originals/'+original_id),raw

    def upload_original(self,actor,data):
        shape(data,('request_id','entity_key','filename','media_type','content_base64'));identifier(data['request_id'])
        key=entity_key(data['entity_key'])
        if key!=data['entity_key']:raise Problem(400,'Original benötigt die normalisierte eindeutige Jahresvortragkennung.')
        line(data['filename'],'Originaldateiname',200)
        if '/' in data['filename'] or '\\' in data['filename'] or data['media_type'] not in ('application/pdf','image/png','image/jpeg'):
            raise Problem(400,'Einfacher Dateiname und PDF-/PNG-/JPEG-Jahresvortragoriginal erforderlich.')
        if not isinstance(data['content_base64'],str):raise Problem(400,'Originalbytes als Base64-Zeichenfolge erforderlich.')
        if len(data['content_base64'])>((MAX_FILE+2)//3)*4:raise Problem(413,'Jahresvortragoriginal bis 5 MiB erforderlich.')
        try:raw=base64.b64decode(data['content_base64'],validate=True)
        except (ValueError,binascii.Error):raise Problem(400,'Gültige Originalbytes erforderlich.') from None
        if not raw:raise Problem(400,'Leeres Jahresvortragoriginal ist nicht zulässig.')
        if len(raw)>MAX_FILE:raise Problem(413,'Jahresvortragoriginal bis 5 MiB erforderlich.')
        _image_check(raw,data['media_type'])
        safe={key:value for key,value in data.items() if key!='content_base64'};safe.update(size=len(raw),sha256=sha(raw))
        with transaction(self.office):
            self._lock();fresh=self._access(actor,True);self._gate();digest,replay=self._request(fresh,'original',safe)
            if replay:return self._original(replay['original_id'])[0]
            old=self.db.execute(f'SELECT id FROM {TABLES[0]} WHERE entity_key=? AND sha256=?',(key,safe['sha256'])).fetchone()
            if old:
                value=self._original(old['id'])[0]
                if value['filename']!=data['filename'] or value['media_type']!=data['media_type']:raise Problem(409,'Dasselbe Jahresvortragoriginal besitzt bereits andere ursprüngliche Dateimetadaten.')
            else:
                original_id=uuid.uuid4().hex
                self.db.execute(f'INSERT INTO {TABLES[0]}(id,entity_key,filename,media_type,size,sha256,original,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                                (original_id,key,data['filename'],data['media_type'],len(raw),safe['sha256'],raw,fresh['id'],self.now()))
                value=self._original(original_id,require_receipt=False)[0]
            self._remember(fresh,'original',safe,digest,dict(original_id=value['id']));self.office.audit(fresh,'business.accounting.year_opening_original',value['id'])
            return value

    def original(self,actor,original_id):
        from workspace_api import BinaryAttachment
        with transaction(self.office):
            self._access(actor);value,raw=self._original(original_id);self._access(actor)
            return BinaryAttachment(raw,value['filename']),value['media_type']

    @staticmethod
    def _inputs(data,confirm=False):
        shape(data,INPUT|({'request_id','preview_hash','confirmation'} if confirm else set()))
        integer(data['expected_revision']);hash_value(data['state_hash'])
        if entity_key(data['entity_key'])!=data['entity_key']:raise Problem(400,'Normalisierte unveränderliche Jahresvortrag-/Zahlungskennung erforderlich.')
        if data['operation']!='year_values':raise Problem(400,'Bekannter Jahresvortragvorgang erforderlich.')
        shape(data['profile_ref'],('id','revision','entry_sha256'));identifier(data['profile_ref']['id']);integer(data['profile_ref']['revision'],1);hash_value(data['profile_ref']['entry_sha256'])
        line(data['reason'],'Prüf-/Korrekturgrund')
        if confirm:
            identifier(data['request_id']);hash_value(data['preview_hash'])
            if data['confirmation'] is not True:raise Problem(400,'Originale und tatsächliche Werte ausdrücklich bestätigen.')

    def _proof(self,key,value):
        from accounting_open_item_rules import proof
        proof(value);original=self._original(value['original_id'])[0]
        if original['entity_key']!=key or original['sha256']!=value['sha256']:raise Problem(409,'Original gehört nicht zu diesem unveränderlichen Jahresvortrag.')
        return original

    def _periods(self,days,*,following=False):
        from business_accounting_euer import EuerAccounting
        periods={key:value['status'] for key,value in EuerAccounting(self.office)._ledger()['periods'].items()}
        if any(periods.get(day[:7])=='closed' for day in days) or following and any(period>=min(days)[:7] and status=='closed' for period,status in periods.items()):raise Problem(409,'Betroffene EÜR-Periode vor Jahresvortragänderung ausdrücklich wieder öffnen.')

    def _resolve(self,year,source,profile,*,historical=False):
        from business_accounting_open_items import OpeningItems
        common={'kind','accounts','cash_entry_keys','vat_entry_key'}
        if not isinstance(source,dict):raise Problem(400,'Ursprüngliche Jahresquelle erforderlich.')
        if source.get('kind')=='opening_item':
            shape(source,common|{'entry_id','entry_hash'});identifier(source['entry_id']);hash_value(source['entry_hash'])
            domain=OpeningItems(self.office);ledger=domain._ledger();entry=ledger['by_id'].get(source['entry_id'])
            if not entry or entry['operation']!='item' or entry['content_hash']!=source['entry_hash'] or entry['payload']['status']!='active':raise Problem(409,'Unveränderte ursprüngliche Altpostenfassung erforderlich.')
            if not historical and (ledger['current'][entry['entity_key']]!=entry or entry['profile_ref']!=profile_reference(profile)):raise Problem(409,'Aktuelle Altpostenfassung und aktuelles Buchführungsprofil erforderlich.')
            record=entry['payload'];proofs=entry['proofs'];reference=entry['content_hash']
        elif source.get('kind')=='closed_trade':
            shape(source,common|{'record'});record=source['record']
            normalize_item(record,profile['profile']['bookkeeping_start'],profile['profile']['vat_effective_from'],allow_settled=True)
            proofs=[self._proof(year,v) for v in [record['invoice_proof'],record['cutover_proof']]+[p['proof'] for p in record['prior_payments']]+([record['prior_input_vat']['proof']] if record['prior_input_vat'] else [])]
            reference=sha(dict(record=record,proofs=proofs))
            if not historical:
                self._closed_trade_available(record,profile)
        else:raise Problem(400,'Kanonischer Altposten oder vollständig bezahlter externer Altbeleg erforderlich.')
        return dict(kind=source['kind'],source_ref=reference,record=record,accounts=source['accounts'],cash_entry_keys=source['cash_entry_keys'],vat_entry_key=source['vat_entry_key']),proofs

    def _closed_trade_available(self,record,profile):
        from business_accounting_open_items import OpeningItems
        from business_accounting_asset_openings import HistoricalAssets
        identity=normalize_item(record,profile['profile']['bookkeeping_start'],profile['profile']['vat_effective_from'],allow_settled=True)
        original=record['invoice_proof']['sha256']
        for entry in OpeningItems(self.office)._ledger()['entries']:
            if entry['operation']=='item' and (entry['payload']['invoice_proof']['sha256']==original or entry['details']['external_identity']==identity['external_identity'] or entry['details']['original_identity']==identity['original_identity']):raise Problem(409,'Vorhandene ursprüngliche Altpostenquelle kanonisch übernehmen; keine zweite externe Kopie.')
        if any(e['source']['sha256']==original for e in HistoricalAssets(self.office)._ledger()['entries']):raise Problem(409,'Anlagenoriginal benötigt seinen gesonderten Jahresvertrag.')
        if self.db.execute('SELECT 1 FROM business_incoming_receipts WHERE sha256=?',(original,)).fetchone() or self.db.execute('SELECT 1 FROM business_document_archives WHERE pdf_sha256=?',(original,)).fetchone():raise Problem(409,'Vorhandenes lokales Rechnungsoriginal nicht zusätzlich als externe Jahresquelle übernehmen.')

    def _known(self,payload,profile,*,ledger=None):
        from business_accounting_open_items import OpeningItems
        from business_accounting_asset_openings import HistoricalAssets
        from business_accounting_euer import EuerAccounting
        coverage=payload['coverage'];first=coverage['from'];last=coverage['through']
        included={s['entry_id'] for s in payload['sources'] if s['kind']=='opening_item'}
        for entry in OpeningItems(self.office)._ledger()['current'].values():
            if entry['operation']!='item' or entry['payload']['status']!='active':continue
            record=entry['payload'];days=[p['date'] for p in record['prior_payments']]+([record['prior_input_vat']['entitlement_date']] if record['prior_input_vat'] else [])
            if any(first<=day<=last for day in days) and entry['id'] not in included:raise Problem(409,'Bekannte ursprüngliche Altpostenwerte fehlen im erklärten Zeitraum.')
        for entry in HistoricalAssets(self.office)._ledger()['current'].values():
            if entry['status']=='active' and entry['opening_date']==profile['profile']['bookkeeping_start'] and cents(entry['asset']['depreciation_in_start_year'])>0:raise Problem(409,'Bekannte AfA vor Softwarebeginn benötigt einen eigenen belegten Jahresquellenvertrag.')
        journal=ledger or EuerAccounting(self.office)._ledger()
        for entry in journal['active'].values():
            if entry['effect']['operation']!='opening_year_values' and any(first<=p['date']<=last for p in entry['postings']):raise Problem(409,'Bereits erfasste lokale Journalwerte überschneiden den übernommenen Zeitraum.')

    def _prepare(self,ledger,data,*,historical=False):
        self._inputs(data)
        if data['expected_revision']!=len(ledger['entries']) or data['state_hash']!=state_hash(ledger['entries']):raise Problem(409,'Jahresvortragsbestand wurde geändert; neue Vorschau erforderlich.')
        old=ledger['current'].get(data['entity_key']);profile=self._profile(data['profile_ref']);facts=profile['profile'];payload=data['payload']
        from business_accounting_euer import EuerAccounting
        if not EuerAccounting._configured(profile) or facts['bookkeeping_start'][:4]!=data['entity_key']:raise Problem(409,'Ausdrückliches EÜR-/Ist-/Regelbesteuerungsprofil und zugehöriges Startjahr erforderlich.')
        shape(payload,('status','coverage','sources','controls','ledger_proof','attestations'))
        if payload['status'] not in ('active','void'):raise Problem(400,'Bekannter Jahresvortragsstatus erforderlich.')
        shape(payload['attestations'],('continuous_method','original_journal_complete','no_unsupported_values'))
        if any(v is not True for v in payload['attestations'].values()):raise Problem(409,'Unveränderte Methode und vollständige belegte Originaljournalprüfung ausdrücklich bestätigen.')
        if payload['status']=='void' and (not old or old['payload']['status']!='active' or any(payload[k]!=old['payload'][k] for k in payload if k!='status') or data['profile_ref']!=old['profile_ref']):raise Problem(409,'Nur genau die unveränderte aktive Jahresquelle ausdrücklich aufheben.')
        if not isinstance(payload['sources'],list) or len(payload['sources'])>1000:raise Problem(400,'Begrenzte ursprüngliche Quellenliste erforderlich.')
        journal_proof=self._proof(data['entity_key'],payload['ledger_proof']);proofs=[journal_proof];resolved=[]
        for value in payload['sources']:
            source,originals=self._resolve(data['entity_key'],value,profile,historical=historical or payload['status']=='void');resolved.append(source);proofs.extend(originals)
        if any(journal_proof['sha256']==p['sha256'] for p in proofs[1:]):raise Problem(409,'Eigenständiges Zeitraumjournal erforderlich; Einzelbeleg ist kein Vollständigkeitsnachweis.')
        details=calculate(profile,payload['coverage'],resolved,payload['controls'])
        for previous in ledger['entries']:
            if previous['entity_key']==data['entity_key']:continue
            for left in resolved:
                for right in previous['resolved_sources']:
                    l=normalize_item(left['record'],facts['bookkeeping_start'],facts['vat_effective_from'],allow_settled=True)
                    r=normalize_item(right['record'],previous['profile']['profile']['bookkeeping_start'],previous['profile']['profile']['vat_effective_from'],allow_settled=True)
                    if l['original_identity']==r['original_identity'] or l['external_identity']==r['external_identity'] or left['record']['invoice_proof']['sha256']==right['record']['invoice_proof']['sha256']:raise Problem(409,'Wirtschaftliches Original wurde bereits in einer anderen Jahresübernahme gebunden.')
        if not historical:
            if payload['status']!='void' and data['profile_ref']!=profile_reference(self._profile()):raise Problem(409,'Aktuelles Buchführungsprofil erneut prüfen.')
            if facts['bookkeeping_start']>self.clock().astimezone(ZoneInfo('Europe/Berlin')).date().isoformat():raise Problem(409,'Keinen künftigen Bestand als übernommen bestätigen.')
            journal=EuerAccounting(self.office)._ledger()
            if 'opening_year_values:'+data['entity_key'] in journal['active']:raise Problem(409,'Aktive EÜR-Jahresübernahme vor Quellenkorrektur ausdrücklich gegenbuchen.')
            days=[payload['coverage']['from'],payload['coverage']['through']]+[p['date'] for p in details['historical_postings']]
            if old:days += [old['payload']['coverage']['from'],old['payload']['coverage']['through']]
            self._periods(days,following=True)
            if payload['status']=='active':self._known(payload,profile,ledger=journal)
        value=dict({key:data[key] for key in INPUT},**FLAGS,profile=profile,proofs=proofs,resolved_sources=resolved,details=details,previous_ref=event_reference(old) if old else None)
        return dict(value,preview_hash=sha(value))

    @stored
    def _ledger(self):
        ledger=dict(entries=[],current={},by_id={});receipts={}
        for row in self.db.execute(f"SELECT * FROM {TABLES[2]} WHERE operation='confirm'"):
            result=json.loads(row['result_json']);shape(result,('entry_id',))
            if result['entry_id'] in receipts:raise Problem(409,'Doppelte Jahresvortragvortragsquittung.')
            receipts[result['entry_id']]=row
        for row in self.db.execute(f'SELECT * FROM {TABLES[1]} ORDER BY sequence'):
            value=json.loads(row['payload_json']);previous=ledger['entries'][-1]['content_hash'] if ledger['entries'] else None
            if (canonical(value)!=row['payload_json'] or sha(value)!=row['content_hash'] or row['sequence']!=len(ledger['entries'])+1 or row['previous_hash']!=previous
                    or any(value.get(key)!=row[key] for key in ('id','sequence','entity_key','revision','previous_hash','created_by','created_at'))):
                raise Problem(409,'Unveränderliche Jahresvortragvortragsfolge ist ungültig.')
            old=ledger['current'].get(row['entity_key']);identifier(row['id']);identifier(row['created_by']);instant(row['created_at'])
            if row['revision']!=(old['revision']+1 if old else 1):raise Problem(409,'Jahresvortragfassungen sind nicht lückenlos.')
            receipt=receipts.get(row['id'])
            if not receipt:raise Problem(409,'Ursprüngliche Jahresvortragannahmequittung fehlt.')
            command=json.loads(receipt['request_json']);self._inputs(command,True)
            if (canonical(command)!=receipt['request_json'] or command['request_id']!=receipt['request_id'] or receipt['user_id']!=row['created_by']
                    or sha(['confirm',command])!=receipt['request_hash']):raise Problem(409,'Ursprünglicher Jahresvortragauftrag wurde verändert.')
            preview=self._prepare(ledger,{key:command[key] for key in INPUT},historical=True)
            expected=dict(preview,id=row['id'],sequence=row['sequence'],revision=row['revision'],previous_hash=previous,created_by=row['created_by'],created_at=row['created_at'])
            if value!=expected or command['preview_hash']!=preview['preview_hash']:raise Problem(409,'Jahresvortragvortrag ist nicht aus seinen Originalen reproduzierbar.')
            value=dict(value,content_hash=row['content_hash']);ledger['entries'].append(value);ledger['current'][row['entity_key']]=value;ledger['by_id'][row['id']]=value
        if len(receipts)!=len(ledger['entries']):raise Problem(409,'Verwaiste Jahresvortragvortragsquittung.')
        return ledger

    def state(self,actor):
        with transaction(self.office):
            fresh=self._access(actor);ledger=self._ledger();profile=self._profile(optional=True);writable=True
            try:self._access(fresh,True);self._gate()
            except Problem:writable=False
            originals=[self._original(row['id'])[0] for row in self.db.execute(f'SELECT id FROM {TABLES[0]} ORDER BY created_at,id')]
            return dict(**FLAGS,revision=len(ledger['entries']),state_hash=state_hash(ledger['entries']),profile=profile,
                        profile_ref=profile_reference(profile) if profile else None,items=list(ledger['current'].values()),originals=originals,
                        can_prepare=writable and profile is not None,max_original_bytes=MAX_FILE)

    def history(self,actor,key):
        if key!=entity_key(key):raise Problem(400,'Normalisierte Jahresvortragkennung erforderlich.')
        with transaction(self.office):
            self._access(actor);return dict(schema_version=1,entity_key=key,items=[entry for entry in self._ledger()['entries'] if entry['entity_key']==key])

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
                if preview['preview_hash']!=data['preview_hash']:raise Problem(409,'Genau passende unveränderte Jahresvortragvorschau erforderlich.')
            except Problem as error:
                if error.status==409:raise Problem(409,error.message,request_resolution='not_accepted') from None
                raise
            old=ledger['current'].get(data['entity_key'])
            value=dict(preview,id=uuid.uuid4().hex,sequence=len(ledger['entries'])+1,revision=old['revision']+1 if old else 1,
                       previous_hash=ledger['entries'][-1]['content_hash'] if ledger['entries'] else None,created_by=fresh['id'],created_at=self.now())
            self._access(fresh,True)
            self.db.execute(f'INSERT INTO {TABLES[1]}(id,sequence,entity_key,revision,previous_hash,payload_json,content_hash,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                            (value['id'],value['sequence'],value['entity_key'],value['revision'],value['previous_hash'],canonical(value),sha(value),fresh['id'],value['created_at']))
            self._remember(fresh,'confirm',data,digest,dict(entry_id=value['id']));self.office.audit(fresh,'business.accounting.year_opening_confirmed',value['id'])
            return dict(value,content_hash=sha(value))


def public_source(office,year,revision=None):
    entity_key(year);ledger=YearValues(office)._ledger()
    entry=ledger['current'].get(year) if revision is None else next((e for e in ledger['entries'] if e['entity_key']==year and e['revision']==revision),None)
    if not entry:raise Problem(404,'Ursprünglicher Jahresvortrag fehlt.')
    value=dict(kind='opening_year_values',schema_version=1,rule_version=RULE_VERSION,id=year,revision=entry['revision'],entry_id=entry['id'],entry_hash=entry['content_hash'],
               status=entry['payload']['status'],date=entry['details']['opening_date'],profile_ref=entry['profile_ref'],coverage=entry['payload']['coverage'],
               details=entry['details'],proofs=entry['proofs'],attestations=entry['payload']['attestations'],cash_movements=[],source_path=BASE+'/years/'+year+'?revision='+str(entry['revision']))
    return dict(value,source_hash=sha(value))


def require_unreserved_original(office,original_sha256):
    if not installed(office):return
    for entry in YearValues(office)._ledger()['entries']:
        if any(p['sha256']==original_sha256 for p in entry['proofs']):raise Problem(409,'Original ist bereits im historischen Jahresjournal gebunden; keine zweite normale Quelle erzeugen.')


def require_item_change(office,record,profile):
    if not installed(office):return
    domain=YearValues(office);ledger=domain._ledger()
    candidate=normalize_item(record,profile['profile']['bookkeeping_start'],profile['profile']['vat_effective_from'])
    for entry in ledger['entries']:
        for source in entry['resolved_sources']:
            if source['kind']!='closed_trade':continue
            details=normalize_item(source['record'],entry['profile']['profile']['bookkeeping_start'],entry['profile']['profile']['vat_effective_from'],allow_settled=True)
            if candidate['original_identity']==details['original_identity'] or candidate['external_identity']==details['external_identity'] or record['invoice_proof']['sha256']==source['record']['invoice_proof']['sha256']:raise Problem(409,'Vollständig erledigte historische Rechnung nicht erneut als offene Schuld übernehmen.')
    from business_accounting_euer import EuerAccounting
    journal=EuerAccounting(office)._ledger()
    for entry in journal['active'].values():
        if entry['effect']['operation']!='opening_year_values':continue
        coverage=entry['effect']['source']['coverage'];days=[p['date'] for p in record['prior_payments']]+([record['prior_input_vat']['entitlement_date']] if record['prior_input_vat'] else [])
        source_entry=ledger['by_id'][entry['effect']['source']['entry_id']]
        bound=any(s['kind']=='opening_item' and normalize_item(s['record'],source_entry['profile']['profile']['bookkeeping_start'],source_entry['profile']['profile']['vat_effective_from'])['original_identity']==candidate['original_identity'] for s in source_entry['resolved_sources'])
        if bound or any(coverage['from']<=day<=coverage['through'] for day in days):raise Problem(409,'Abhängige Jahresübernahme vor Änderung ihrer ursprünglichen Altpostenwerte ausdrücklich gegenbuchen.')


def financial_access(office,actor,write=False):return YearValues(office)._access(actor,write)


def entrypoint(office,actor):
    if not installed(office):return None
    try:financial_access(office,actor)
    except Problem as error:
        if error.status in (403,404):return None
        raise
    return BASE


def validate_integrity(office):
    if not installed(office):return True
    api=YearValues(office)
    try:
        ledger=api._ledger();originals=set();covered=set()
        for row in office.db.execute(f'SELECT id FROM {TABLES[0]}'):originals.add(row['id']);api._original(row['id'])
        for row in office.db.execute(f'SELECT * FROM {TABLES[2]}'):
            command=json.loads(row['request_json']);result=json.loads(row['result_json']);identifier(row['user_id']);identifier(row['request_id'])
            if canonical(command)!=row['request_json'] or command['request_id']!=row['request_id'] or sha([row['operation'],command])!=row['request_hash']:raise ValueError('Changed year opening receipt')
            if row['operation']=='original':
                shape(command,('request_id','entity_key','filename','media_type','size','sha256'));shape(result,('original_id',));original=api._original(result['original_id'])[0]
                if any(command[key]!=original[key] for key in ('entity_key','filename','media_type','size','sha256')):raise ValueError('Changed year opening original receipt')
                covered.add(original['id'])
            elif row['operation']!='confirm' or result['entry_id'] not in ledger['by_id']:raise ValueError('Unknown year opening receipt')
        if originals!=covered:raise ValueError('Missing year opening original receipt')
        if isinstance(office.db,sqlite3.Connection):
            norm=lambda value:re.sub(r'\s+',' ',value.replace('IF NOT EXISTS ','')).strip().lower()
            for statement in guard_statements('sqlite'):
                name=re.search(r'CREATE TRIGGER IF NOT EXISTS (\w+)',statement)[1];row=office.db.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",(name,)).fetchone()
                if not row or norm(row[0])!=norm(statement):raise ValueError('Missing year opening immutable guard')
        else:
            from business_documents import _validate_pg_guards
            _validate_pg_guards(office.db,guard_statements('postgresql'))
    except (Problem,ValueError,TypeError,KeyError,ArithmeticError) as error:raise ValueError('Invalid year opening originals or journal') from error
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
    if path in (BASE,BASE+'/history') or (re.fullmatch(BASE+'/originals/'+ID,path) or re.fullmatch(BASE+r'/years/20[0-9]{2}',path)):return 'GET'
    if path in (BASE+'/originals',BASE+'/preview',BASE+'/confirm'):return 'POST'
    return None


def dispatch(office,actor,path,method,data):
    allowed=methods(path)
    if allowed is None:return None
    if method!=allowed:raise Problem(405,'HTTP-Methode nicht erlaubt.')
    api=YearValues(office)
    if method=='POST':
        if not isinstance(data,dict) or '_query' in data:raise Problem(400,'Genauer JSON-Jahresvortragbefehl ohne Filter erforderlich.')
        action=path.rsplit('/',1)[-1];value=getattr(api,'upload_original' if action=='originals' else action)(actor,data)
        return value,200 if action in ('preview','identity') else 201,'application/json'
    if not isinstance(data,dict) or set(data)-{'_query'}:raise Problem(400,'GET erwartet keinen Anfragekörper.')
    query=data.get('_query',{})
    if path==BASE+'/history':shape(query,('entity_key',));value=api.history(actor,query['entity_key'])
    elif '/years/' in path:
        shape(query,('revision',));api._access(actor)
        if not isinstance(query['revision'],str) or not re.fullmatch(r'[1-9][0-9]*',query['revision']):raise Problem(400,'Positive Zahlungsrevision erforderlich.')
        value=public_source(office,path.rsplit('/',1)[-1],int(query['revision']))
    else:
        shape(query,())
        if '/originals/' in path:
            raw,media_type=api.original(actor,path.rsplit('/',1)[-1]);return raw,200,media_type
        value=api.state(actor)
    return value,200,'application/json'
