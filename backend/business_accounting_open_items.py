"""Immutable evidenced historical receivables/payables and actual subsequent cash."""
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
from accounting_open_item_rules import RULE_VERSION,entity_key,normalize_item,payment_split,money,cents

FEATURES=('accounting_open_items',)
BASE='/accounting/open-items'
TABLES=tuple('business_accounting_open_item_'+name for name in ('originals','events','requests'))
INPUT={'expected_revision','state_hash','entity_key','profile_ref','operation','payload','reason'}
FLAGS=dict(schema_version=1,rule_version=RULE_VERSION,invoice_created=False,
           opening_cash_flow_created=False,opening_tax_postings_created=False,
           balance_timing='start_of_day',timezone='Europe/Berlin')


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA','BLOB'):raise ValueError('Unsupported opening item original binary type')
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
        values=[f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable opening item evidence'); END"
                for table in TABLES for action in ('UPDATE','DELETE')]
        conditions=('id=NEW.id OR (entity_key=NEW.entity_key AND sha256=NEW.sha256)',
                    'id=NEW.id OR sequence=NEW.sequence OR (entity_key=NEW.entity_key AND revision=NEW.revision)',
                    'user_id=NEW.user_id AND request_id=NEW.request_id')
        return values+[f"CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition}) BEGIN SELECT RAISE(ABORT,'immutable opening item evidence'); END"
                       for table,condition in zip(TABLES,conditions)]
    if dialect!='postgresql':raise ValueError('Unsupported opening item dialect')
    values=["CREATE OR REPLACE FUNCTION business_open_item_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable opening item evidence'; END; $$"]
    for table in TABLES:
        for action in ('UPDATE','DELETE'):
            name=table+'_'+action.lower()+'_guard'
            values.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION business_open_item_immutable_guard(); END IF; END $$")
    return values


def installed(office):
    from business_schema import _tables
    tables=_tables(office);present=set(TABLES)&tables
    marker='business_schema_migrations' in tables and office.db.execute("SELECT 1 FROM business_schema_migrations WHERE module='business_accounting_open_items'").fetchone()
    if not present and not marker:return False
    if present!=set(TABLES) or not marker:raise Problem(409,'Historischer Altpostenvortrag ist unvollständig installiert.')
    for dependency in ('business_accounting_euer','business_accounting_openings','business_accounting_asset_openings'):
        if not office.db.execute('SELECT 1 FROM business_schema_migrations WHERE module=?',(dependency,)).fetchone():
            raise Problem(409,'Abhängigkeiten des historischen Altpostenvortrags fehlen.')
    return True


class OpeningItems:
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
            require_active(self.office,fresh,BASE,'business_accounting_open_items')
        if not installed(self.office):raise Problem(409,'Historischer Altpostenvortrag ist nicht installiert.')
        return fresh

    def _gate(self):
        from business_schema import require_capability
        require_capability(self.office,'business_accounting_open_items');Accounting(self.office)._write_gate()

    def _request(self,actor,operation,command):
        digest=sha([operation,command]);row=self.db.execute(f'SELECT * FROM {TABLES[2]} WHERE user_id=? AND request_id=?',(actor['id'],command['request_id'])).fetchone()
        if row:
            if row['operation']!=operation or row['request_json']!=canonical(command) or row['request_hash']!=digest:
                raise Problem(409,'Vorgangskennung wurde mit anderen ursprünglichen Altpostenwerten verwendet.')
            return digest,json.loads(row['result_json'])
        return digest,None

    def _remember(self,actor,operation,command,digest,result):
        self.db.execute(f'INSERT INTO {TABLES[2]}(user_id,request_id,operation,request_json,request_hash,result_json) VALUES(?,?,?,?,?,?)',
                        (actor['id'],command['request_id'],operation,canonical(command),digest,canonical(result)))

    @stored
    def _original(self,original_id,*,require_receipt=True):
        identifier(original_id);row=self.db.execute(f'SELECT * FROM {TABLES[0]} WHERE id=?',(original_id,)).fetchone()
        if not row:raise Problem(404,'Geschütztes Altpostenoriginal nicht vorhanden.')
        raw=bytes(row['original']);size=len(raw)
        if not 0<size<=MAX_FILE or size!=row['size'] or sha(raw)!=row['sha256'] or entity_key(row['entity_key'])!=row['entity_key']:
            raise Problem(409,'Altpostenoriginal besteht die Integritätsprüfung nicht.')
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
                    raise Problem(409,'Ursprüngliche Altpostenoriginal-Annahme wurde verändert.')
                if receipt['user_id']==row['created_by']:accepted=True
            if not accepted:raise Problem(409,'Ursprüngliche Annahmequittung des Altpostenoriginals fehlt.')
        return dict({key:row[key] for key in row.keys() if key!='original'},path=BASE+'/originals/'+original_id),raw

    def upload_original(self,actor,data):
        shape(data,('request_id','entity_key','filename','media_type','content_base64'));identifier(data['request_id'])
        key=entity_key(data['entity_key'])
        if key!=data['entity_key']:raise Problem(400,'Original benötigt die normalisierte eindeutige Altpostenkennung.')
        line(data['filename'],'Originaldateiname',200)
        if '/' in data['filename'] or '\\' in data['filename'] or data['media_type'] not in ('application/pdf','image/png','image/jpeg'):
            raise Problem(400,'Einfacher Dateiname und PDF-/PNG-/JPEG-Altpostenoriginal erforderlich.')
        if not isinstance(data['content_base64'],str):raise Problem(400,'Originalbytes als Base64-Zeichenfolge erforderlich.')
        if len(data['content_base64'])>((MAX_FILE+2)//3)*4:raise Problem(413,'Altpostenoriginal bis 5 MiB erforderlich.')
        try:raw=base64.b64decode(data['content_base64'],validate=True)
        except (ValueError,binascii.Error):raise Problem(400,'Gültige Originalbytes erforderlich.') from None
        if not raw:raise Problem(400,'Leeres Altpostenoriginal ist nicht zulässig.')
        if len(raw)>MAX_FILE:raise Problem(413,'Altpostenoriginal bis 5 MiB erforderlich.')
        _image_check(raw,data['media_type'])
        safe={key:value for key,value in data.items() if key!='content_base64'};safe.update(size=len(raw),sha256=sha(raw))
        with transaction(self.office):
            self._lock();fresh=self._access(actor,True);self._gate();digest,replay=self._request(fresh,'original',safe)
            if replay:return self._original(replay['original_id'])[0]
            old=self.db.execute(f'SELECT id FROM {TABLES[0]} WHERE entity_key=? AND sha256=?',(key,safe['sha256'])).fetchone()
            if old:
                value=self._original(old['id'])[0]
                if value['filename']!=data['filename'] or value['media_type']!=data['media_type']:raise Problem(409,'Dasselbe Altpostenoriginal besitzt bereits andere ursprüngliche Dateimetadaten.')
            else:
                original_id=uuid.uuid4().hex
                self.db.execute(f'INSERT INTO {TABLES[0]}(id,entity_key,filename,media_type,size,sha256,original,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                                (original_id,key,data['filename'],data['media_type'],len(raw),safe['sha256'],raw,fresh['id'],self.now()))
                value=self._original(original_id,require_receipt=False)[0]
            self._remember(fresh,'original',safe,digest,dict(original_id=value['id']));self.office.audit(fresh,'business.accounting.open_item_original',value['id'])
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
        if entity_key(data['entity_key'])!=data['entity_key']:raise Problem(400,'Normalisierte unveränderliche Altposten-/Zahlungskennung erforderlich.')
        if data['operation'] not in ('item','payment'):raise Problem(400,'Bekannter Altpostenvorgang erforderlich.')
        shape(data['profile_ref'],('id','revision','entry_sha256'));identifier(data['profile_ref']['id']);integer(data['profile_ref']['revision'],1);hash_value(data['profile_ref']['entry_sha256'])
        line(data['reason'],'Prüf-/Korrekturgrund')
        if confirm:
            identifier(data['request_id']);hash_value(data['preview_hash'])
            if data['confirmation'] is not True:raise Problem(400,'Originale und tatsächliche Werte ausdrücklich bestätigen.')

    def _proof(self,key,value):
        from accounting_open_item_rules import proof
        proof(value);original=self._original(value['original_id'])[0]
        if original['entity_key']!=key or original['sha256']!=value['sha256']:raise Problem(409,'Original gehört nicht zu diesem unveränderlichen Altposten.')
        return original

    def _periods(self,days,*,following=False):
        from business_accounting_euer import EuerAccounting
        periods={key:value['status'] for key,value in EuerAccounting(self.office)._ledger()['periods'].items()}
        if any(periods.get(day[:7])=='closed' for day in days) or following and any(period>=min(days)[:7] and status=='closed' for period,status in periods.items()):raise Problem(409,'Betroffene EÜR-Periode vor Altpostenänderung ausdrücklich wieder öffnen.')

    def _followup_open(self,key):
        from business_accounting_euer import EuerAccounting
        ledger=EuerAccounting(self.office)._ledger()
        if 'opening_item_cash:'+key in ledger['active']:raise Problem(409,'Aktive EÜR-Zahlung vor Belegkorrektur ausdrücklich gegenbuchen.')
        from business_bank_reconciliation import BankReconciliation
        for event in BankReconciliation(self.office)._matches():
            if any(link['source']['source_kind']=='opening_item_cash' and link['source']['source_id']==key for link in event['payload']['links']):
                raise Problem(409,'Aktive Bankzuordnung vor Korrektur dieses Zahlungsnachweises ausdrücklich aufheben.')

    def _prepare(self,ledger,data,*,historical=False):
        self._inputs(data)
        if data['expected_revision']!=len(ledger['entries']) or data['state_hash']!=state_hash(ledger['entries']):raise Problem(409,'Altpostenbestand wurde geändert; neue Vorschau erforderlich.')
        old=ledger['current'].get(data['entity_key']);profile=self._profile(data['profile_ref']);facts=profile['profile']
        from business_accounting_euer import EuerAccounting
        if not EuerAccounting._configured(profile):raise Problem(409,'Ausdrückliches Einzelunternehmen-/EÜR-/Ist-/Regelbesteuerungsprofil erforderlich.')
        if old and old['operation']!=data['operation']:raise Problem(409,'Unveränderliche Kennung ist bereits für einen anderen Vorgang gebunden.')
        if not historical:
            if data['profile_ref']!=profile_reference(self._profile()):raise Problem(409,'Aktuelles Buchführungsprofil erneut prüfen.')
            if facts['bookkeeping_start']>self.clock().astimezone(ZoneInfo('Europe/Berlin')).date().isoformat():raise Problem(409,'Keinen künftigen Altbestand als übernommen bestätigen.')
        payload=data['payload'];proofs=[]
        if data['operation']=='item':
            opening=facts['bookkeeping_start'];details=normalize_item(payload,opening,facts['vat_effective_from'])
            for value in [payload['invoice_proof'],payload['cutover_proof']]+[p['proof'] for p in payload['prior_payments']]+([payload['prior_input_vat']['proof']] if payload['prior_input_vat'] else []):proofs.append(self._proof(data['entity_key'],value))
            if old and (old['details']['external_identity']!=details['external_identity'] or old['details']['original_identity']!=details['original_identity'] or old['payload']['invoice_proof']!=payload['invoice_proof']):
                raise Problem(409,'Externe Identität und ursprüngliche Rechnung bleiben unverändert; keine Umbenennung eines Altpostens.')
            if payload['status']=='void' and (not old or old['payload']['status']!='active' or any(payload[k]!=old['payload'][k] for k in payload if k!='status')):raise Problem(409,'Nur genau den unveränderten aktiven Altposten ausdrücklich aufheben.')
            for entry in ledger['entries']:
                if entry['operation']=='payment' and entry['payload']['proof']['sha256']==payload['invoice_proof']['sha256']:raise Problem(409,'Zahlungsnachweis darf nicht als neue ursprüngliche Handelsrechnung wiederverwendet werden.')
                if entry['operation']=='item' and entry['entity_key']!=data['entity_key'] and (
                    entry['details']['external_identity']==details['external_identity'] or entry['details']['original_identity']==details['original_identity']
                    or entry['payload']['invoice_proof']['sha256']==payload['invoice_proof']['sha256']):
                    raise Problem(409,'Ursprüngliche externe Rechnung ist bereits dauerhaft übernommen; keine zweite Forderung/Verbindlichkeit.')
            payments=[entry for entry in ledger['current'].values() if entry['operation']=='payment' and entry['payload']['item_key']==data['entity_key'] and entry['payload']['status']=='active']
            if payments and (not old or payload!=old['payload'] or opening!=old['details']['opening_date']):raise Problem(409,'Tatsächliche Folgezahlungen binden die Altpostenfassung; fehlerhafte Belege zuerst nachvollziehbar korrigieren.')
            if not historical:
                from business_accounting_year_openings import require_item_change
                require_item_change(self.office,payload,profile)
                self._periods([opening],following=True)
                # Existing ordinary originals must continue through their own
                # domain. This initial import cannot silently steal a source.
                original=payload['invoice_proof']['sha256']
                from business_accounting_asset_openings import HistoricalAssets,installed as assets_installed
                if assets_installed(self.office) and any(e['source']['sha256']==original for e in HistoricalAssets(self.office)._ledger()['entries']):raise Problem(409,'Original ist bereits als historische Anlage gebunden; kein zusätzlicher gewöhnlicher Altaufwand.')
                if self.db.execute('SELECT 1 FROM business_incoming_receipts WHERE sha256=?',(original,)).fetchone():raise Problem(409,'Original ist bereits im normalen Belegeingang gebunden; diesen Bestand nicht zusätzlich importieren.')
                if self.db.execute('SELECT 1 FROM business_document_archives WHERE pdf_sha256=?',(original,)).fetchone():raise Problem(409,'Archivierte lokale Rechnung nicht erneut als externen Altposten übernehmen.')
            details=dict(details,opening_date=opening)
        else:
            shape(payload,('status','item_key','item_id','item_hash','date','amount','account_id','account_revision','evidence_reference','proof'))
            if payload['status'] not in ('active','void'):raise Problem(400,'Bekannter tatsächlicher Zahlungsstatus erforderlich.')
            identifier(data['entity_key']);identifier(payload['item_id']);hash_value(payload['item_hash']);iso_date(payload['date']);integer(payload['account_revision'],1)
            item=ledger['current'].get(payload['item_key'])
            if not item or item['operation']!='item' or item['payload']['status']!='active' or item['id']!=payload['item_id'] or item['content_hash']!=payload['item_hash']:raise Problem(409,'Genau die aktive ursprüngliche Altpostenfassung erforderlich.')
            if item['profile_ref']!=data['profile_ref']:raise Problem(409,'Altposten wurde unter anderem Profil geprüft; Übernahme erneut prüfen.')
            if payload['date']<facts['bookkeeping_start']:raise Problem(409,'Folgezahlung muss tatsächlich ab Buchführungsbeginn liegen.')
            if not historical and payload['date']>self.clock().astimezone(ZoneInfo('Europe/Berlin')).date().isoformat():raise Problem(409,'Keine künftige Zahlung als tatsächlich erfolgt bestätigen.')
            original=self._proof(payload['item_key'],payload['proof']);proofs=[original]
            if original['sha256'] in {p['sha256'] for e in ledger['entries'] if e['operation']=='item' for p in e['proofs']}:raise Problem(409,'Tatsächliche Folgezahlung benötigt eigenen Zahlungsnachweis, nicht das ursprüngliche Rechnungs-/Altbestandsoriginal.')
            from business_accounting import _evidence
            unused,evidence_key=_evidence(payload['evidence_reference'])
            for previous in ledger['entries']:
                if previous['operation']=='payment' and previous['entity_key']!=data['entity_key'] and (
                    previous['details']['account']['id']==payload['account_id'] and previous['details']['evidence_key']==evidence_key
                    or previous['payload']['proof']['sha256']==original['sha256']):raise Problem(409,'Tatsächlicher Zahlungsnachweis ist bereits dauerhaft einem anderen Vorgang zugeordnet.')
            peers=[entry for entry in ledger['current'].values() if entry['operation']=='payment' and entry['entity_key']!=data['entity_key'] and entry['payload']['item_key']==payload['item_key'] and entry['payload']['status']=='active']
            if old:
                if old['payload']['item_key']!=payload['item_key']:raise Problem(409,'Ursprüngliche Zahlung darf nicht auf eine andere Rechnung verschoben werden.')
                if any(p['sequence']>old['sequence'] for p in peers):raise Problem(409,'Spätere Teilzahlungen vor Korrektur einer früheren Centaufteilung ausdrücklich korrigieren.')
                if not historical:self._followup_open(data['entity_key'])
            if payload['status']=='void' and (not old or old['payload']['status']!='active' or any(payload[k]!=old['payload'][k] for k in payload if k!='status')):raise Problem(409,'Nur unveränderten aktiven Zahlungsbeleg ausdrücklich aufheben; keine wirtschaftliche Rückzahlung vortäuschen.')
            if any(p['payload']['date']>payload['date'] for p in peers):raise Problem(409,'Tatsächliche Teilzahlungen chronologisch erfassen.')
            already=cents(item['details']['settled_before_start'])+sum(cents(p['payload']['amount']) for p in peers)
            split=payment_split(item['payload'],already,cents(payload['amount']))
            account=Accounting(self.office)._account(payload['account_id'],payload['account_revision'])
            if not account['active'] or account['currency']!='EUR':raise Problem(409,'Aktives EUR-Geldkonto erforderlich.')
            if not historical:
                if Accounting(self.office)._account(payload['account_id'])!=account:raise Problem(409,'Geldkonto wurde geändert; neue Vorschau erforderlich.')
                self._periods([payload['date']]+([old['payload']['date']] if old else []))
                ensure_other_cash_available(self.office,payload['account_id'],evidence_key,original['sha256'],data['entity_key'])
            details=dict(split,account=account,evidence_key=evidence_key,direction='in' if item['payload']['direction']=='receivable' else 'out',
                         category=item['payload']['category'],rate=item['payload']['rate'],item_ref=dict(id=item['id'],content_hash=item['content_hash']))
        value=dict({key:data[key] for key in INPUT},**FLAGS,profile=profile,proofs=proofs,details=details,previous_ref=event_reference(old) if old else None)
        return dict(value,preview_hash=sha(value))

    @stored
    def _ledger(self):
        ledger=dict(entries=[],current={},by_id={});receipts={}
        for row in self.db.execute(f"SELECT * FROM {TABLES[2]} WHERE operation='confirm'"):
            result=json.loads(row['result_json']);shape(result,('entry_id',))
            if result['entry_id'] in receipts:raise Problem(409,'Doppelte Altpostenvortragsquittung.')
            receipts[result['entry_id']]=row
        for row in self.db.execute(f'SELECT * FROM {TABLES[1]} ORDER BY sequence'):
            value=json.loads(row['payload_json']);previous=ledger['entries'][-1]['content_hash'] if ledger['entries'] else None
            if (canonical(value)!=row['payload_json'] or sha(value)!=row['content_hash'] or row['sequence']!=len(ledger['entries'])+1 or row['previous_hash']!=previous
                    or any(value.get(key)!=row[key] for key in ('id','sequence','entity_key','revision','previous_hash','created_by','created_at'))):
                raise Problem(409,'Unveränderliche Altpostenvortragsfolge ist ungültig.')
            old=ledger['current'].get(row['entity_key']);identifier(row['id']);identifier(row['created_by']);instant(row['created_at'])
            if row['revision']!=(old['revision']+1 if old else 1):raise Problem(409,'Altpostenfassungen sind nicht lückenlos.')
            receipt=receipts.get(row['id'])
            if not receipt:raise Problem(409,'Ursprüngliche Altpostenannahmequittung fehlt.')
            command=json.loads(receipt['request_json']);self._inputs(command,True)
            if (canonical(command)!=receipt['request_json'] or command['request_id']!=receipt['request_id'] or receipt['user_id']!=row['created_by']
                    or sha(['confirm',command])!=receipt['request_hash']):raise Problem(409,'Ursprünglicher Altpostenauftrag wurde verändert.')
            preview=self._prepare(ledger,{key:command[key] for key in INPUT},historical=True)
            expected=dict(preview,id=row['id'],sequence=row['sequence'],revision=row['revision'],previous_hash=previous,created_by=row['created_by'],created_at=row['created_at'])
            if value!=expected or command['preview_hash']!=preview['preview_hash']:raise Problem(409,'Altpostenvortrag ist nicht aus seinen Originalen reproduzierbar.')
            value=dict(value,content_hash=row['content_hash']);ledger['entries'].append(value);ledger['current'][row['entity_key']]=value;ledger['by_id'][row['id']]=value
        if len(receipts)!=len(ledger['entries']):raise Problem(409,'Verwaiste Altpostenvortragsquittung.')
        return ledger

    @staticmethod
    def _items(ledger):
        result=[]
        for item in ledger['current'].values():
            if item['operation']!='item':continue
            payments=[p for p in ledger['current'].values() if p['operation']=='payment' and p['payload']['item_key']==item['entity_key'] and p['payload']['status']=='active']
            active=item['payload']['status']=='active'
            result.append(dict(item,remaining=money(cents(item['details']['opening_remaining'])-sum(cents(p['payload']['amount']) for p in payments)) if active else None,
                remaining_net=money(cents(item['details']['opening_remaining_net'])-sum(cents(p['details']['net']) for p in payments)) if active else None,
                remaining_tax=money(cents(item['details']['opening_remaining_tax'])-sum(cents(p['details']['tax']) for p in payments)) if active else None))
        return result

    def state(self,actor):
        with transaction(self.office):
            fresh=self._access(actor);ledger=self._ledger();profile=self._profile(optional=True);writable=True
            try:self._access(fresh,True);self._gate()
            except Problem:writable=False
            originals=[self._original(row['id'])[0] for row in self.db.execute(f'SELECT id FROM {TABLES[0]} ORDER BY created_at,id')]
            return dict(**FLAGS,revision=len(ledger['entries']),state_hash=state_hash(ledger['entries']),profile=profile,
                        profile_ref=profile_reference(profile) if profile else None,items=self._items(ledger),payments=[entry for entry in ledger['current'].values() if entry['operation']=='payment'],originals=originals,
                        can_prepare=writable and profile is not None,max_original_bytes=MAX_FILE)

    def history(self,actor,key):
        if key!=entity_key(key):raise Problem(400,'Normalisierte Altpostenkennung erforderlich.')
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
                if preview['preview_hash']!=data['preview_hash']:raise Problem(409,'Genau passende unveränderte Altpostenvorschau erforderlich.')
            except Problem as error:
                if error.status==409:raise Problem(409,error.message,request_resolution='not_accepted') from None
                raise
            old=ledger['current'].get(data['entity_key'])
            value=dict(preview,id=uuid.uuid4().hex,sequence=len(ledger['entries'])+1,revision=old['revision']+1 if old else 1,
                       previous_hash=ledger['entries'][-1]['content_hash'] if ledger['entries'] else None,created_by=fresh['id'],created_at=self.now())
            self._access(fresh,True)
            self.db.execute(f'INSERT INTO {TABLES[1]}(id,sequence,entity_key,revision,previous_hash,payload_json,content_hash,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                            (value['id'],value['sequence'],value['entity_key'],value['revision'],value['previous_hash'],canonical(value),sha(value),fresh['id'],value['created_at']))
            self._remember(fresh,'confirm',data,digest,dict(entry_id=value['id']));self.office.audit(fresh,'business.accounting.open_item_confirmed',value['id'])
            return dict(value,content_hash=sha(value))


def public_source(office,payment_key,revision=None):
    identifier(payment_key);ledger=OpeningItems(office)._ledger()
    entry=ledger['current'].get(payment_key) if revision is None else next((e for e in ledger['entries'] if e['entity_key']==payment_key and e['revision']==revision),None)
    if not entry or entry['operation']!='payment':raise Problem(404,'Ursprüngliche Altpostenzahlung fehlt.')
    item=ledger['by_id'][entry['payload']['item_id']];payload=entry['payload'];details=entry['details']
    value=dict(kind='opening_item_cash',schema_version=1,rule_version=RULE_VERSION,id=payment_key,revision=entry['revision'],entry_id=entry['id'],entry_hash=entry['content_hash'],
               status=payload['status'],date=payload['date'],profile_ref=entry['profile_ref'],item_key=payload['item_key'],item_id=item['id'],item_hash=item['content_hash'],
               direction=details['direction'],category=details['category'],rate=details['rate'],net=details['net'],tax=details['tax'],gross=details['gross'],
               prior_input_vat=item['payload']['prior_input_vat'],proof=entry['proofs'][0],
               cash_movements=[] if payload['status']=='void' else [dict(id=payment_key,account=details['account'],date=payload['date'],direction=details['direction'],amount=payload['amount'])],
               source_path=BASE+'/payments/'+payment_key+'?revision='+str(entry['revision']))
    return dict(value,source_hash=sha(value))


def ensure_cash_available(office,account_id,evidence_key,original_sha256=None,*,own_payment=None):
    if not installed(office):return
    from business_accounting import _evidence
    key=_evidence(evidence_key)[1]
    for entry in OpeningItems(office)._ledger()['entries']:
        if entry['operation']!='payment' or entry['entity_key']==own_payment:continue
        if (entry['details']['account']['id']==account_id and entry['details']['evidence_key']==key
            or original_sha256 and entry['payload']['proof']['sha256']==original_sha256):raise Problem(409,'Tatsächlicher Zahlungsnachweis ist bereits dauerhaft im Altpostenjournal gebunden.')


def ensure_other_cash_available(office,account_id,evidence_key,original_sha256,own_payment):
    from business_accounting_euer import ensure_cash_identity_available
    ensure_cash_identity_available(office,account_id,evidence_key,original_sha256,opening_payment_id=own_payment)
    if office.db.execute('SELECT 1 FROM business_accounting_cash_events WHERE account_id=? AND evidence_key=?',(account_id,evidence_key)).fetchone():raise Problem(409,'Tatsächlicher Zahlungsnachweis ist bereits im Geldjournal erfasst.')
    if office.db.execute('SELECT 1 FROM business_accounting_source_links WHERE original_sha256=?',(original_sha256,)).fetchone():raise Problem(409,'Zahlungsoriginal ist bereits im Geldjournal gebunden.')
    if office.db.execute('SELECT 1 FROM business_incoming_receipts WHERE sha256=?',(original_sha256,)).fetchone():raise Problem(409,'Zahlungsoriginal ist bereits im normalen Belegeingang gebunden.')


def require_unreserved_original(office,original_sha256):
    if not installed(office):return
    for entry in OpeningItems(office)._ledger()['entries']:
        if any(original['sha256']==original_sha256 for original in entry['proofs']):raise Problem(409,'Original ist bereits im Altposten-/Zahlungsjournal gebunden; keine zweite gewöhnliche Quelle erzeugen.')


def financial_access(office,actor,write=False):return OpeningItems(office)._access(actor,write)


def entrypoint(office,actor):
    if not installed(office):return None
    try:financial_access(office,actor)
    except Problem as error:
        if error.status in (403,404):return None
        raise
    return BASE


def validate_integrity(office):
    if not installed(office):return True
    api=OpeningItems(office)
    try:
        ledger=api._ledger();originals=set();covered=set()
        for row in office.db.execute(f'SELECT id FROM {TABLES[0]}'):originals.add(row['id']);api._original(row['id'])
        for row in office.db.execute(f'SELECT * FROM {TABLES[2]}'):
            command=json.loads(row['request_json']);result=json.loads(row['result_json']);identifier(row['user_id']);identifier(row['request_id'])
            if canonical(command)!=row['request_json'] or command['request_id']!=row['request_id'] or sha([row['operation'],command])!=row['request_hash']:raise ValueError('Changed opening item receipt')
            if row['operation']=='original':
                shape(command,('request_id','entity_key','filename','media_type','size','sha256'));shape(result,('original_id',));original=api._original(result['original_id'])[0]
                if any(command[key]!=original[key] for key in ('entity_key','filename','media_type','size','sha256')):raise ValueError('Changed opening item original receipt')
                covered.add(original['id'])
            elif row['operation']!='confirm' or result['entry_id'] not in ledger['by_id']:raise ValueError('Unknown opening item receipt')
        if originals!=covered:raise ValueError('Missing opening item original receipt')
        if isinstance(office.db,sqlite3.Connection):
            norm=lambda value:re.sub(r'\s+',' ',value.replace('IF NOT EXISTS ','')).strip().lower()
            for statement in guard_statements('sqlite'):
                name=re.search(r'CREATE TRIGGER IF NOT EXISTS (\w+)',statement)[1];row=office.db.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",(name,)).fetchone()
                if not row or norm(row[0])!=norm(statement):raise ValueError('Missing opening item immutable guard')
        else:
            from business_documents import _validate_pg_guards
            _validate_pg_guards(office.db,guard_statements('postgresql'))
    except (Problem,ValueError,TypeError,KeyError,ArithmeticError) as error:raise ValueError('Invalid opening item originals or journal') from error
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
    if path in (BASE,BASE+'/history') or re.fullmatch(BASE+'/(originals|payments)/'+ID,path):return 'GET'
    if path in (BASE+'/originals',BASE+'/preview',BASE+'/confirm'):return 'POST'
    return None


def dispatch(office,actor,path,method,data):
    allowed=methods(path)
    if allowed is None:return None
    if method!=allowed:raise Problem(405,'HTTP-Methode nicht erlaubt.')
    api=OpeningItems(office)
    if method=='POST':
        if not isinstance(data,dict) or '_query' in data:raise Problem(400,'Genauer JSON-Altpostenbefehl ohne Filter erforderlich.')
        action=path.rsplit('/',1)[-1];value=getattr(api,'upload_original' if action=='originals' else action)(actor,data)
        return value,200 if action in ('preview','identity') else 201,'application/json'
    if not isinstance(data,dict) or set(data)-{'_query'}:raise Problem(400,'GET erwartet keinen Anfragekörper.')
    query=data.get('_query',{})
    if path==BASE+'/history':shape(query,('entity_key',));value=api.history(actor,query['entity_key'])
    elif '/payments/' in path:
        shape(query,('revision',));api._access(actor)
        if not isinstance(query['revision'],str) or not re.fullmatch(r'[1-9][0-9]*',query['revision']):raise Problem(400,'Positive Zahlungsrevision erforderlich.')
        value=public_source(office,path.rsplit('/',1)[-1],int(query['revision']))
    else:
        shape(query,())
        if '/originals/' in path:
            raw,media_type=api.original(actor,path.rsplit('/',1)[-1]);return raw,200,media_type
        value=api.state(actor)
    return value,200,'application/json'
