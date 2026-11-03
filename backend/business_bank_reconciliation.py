"""Documented EUR statement imports and explicit links to existing cash only."""
import base64
import binascii
import calendar
import csv
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
import hashlib
import io
import json
import re
import sqlite3
import unicodedata
import uuid
from xml.sax.saxutils import escape

from core import Problem,canonical
from business_accounting import Accounting
from business_accounting_euer import EuerAccounting
from business_foundation import require_permission
from business_operations import identifier,iso_date,text,transaction

FEATURES=('bank_reconciliation',)
TABLES=tuple('business_bank_'+name for name in ('account_versions','statements','transactions','statement_lines','match_events','reconciliations','requests'))
ID=r'[a-f0-9]{32}'
HASH=r'[a-f0-9]{64}'
MAX_FILE=5*1024*1024
MAX_ROWS=10000
HEADERS=['transaction_id','booking_date','value_date','amount','currency','counterparty','reference']
IMPORT_FIELDS=('account_id','account_revision','bank_revision','statement_reference','period_from','period_to','opening_balance','closing_balance','filename','delimiter','content_base64','complete_statement_confirmed')


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA','BLOB'):raise ValueError('Unsupported bank binary type')
    return [
        '''CREATE TABLE IF NOT EXISTS business_bank_account_versions(account_id TEXT NOT NULL REFERENCES business_accounting_accounts(id),revision INTEGER NOT NULL CHECK(revision>0),payload_json TEXT NOT NULL,content_hash TEXT NOT NULL,previous_hash TEXT,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,PRIMARY KEY(account_id,revision))''',
        f'''CREATE TABLE IF NOT EXISTS business_bank_statements(id TEXT PRIMARY KEY,account_id TEXT NOT NULL REFERENCES business_accounting_accounts(id),reference_key TEXT NOT NULL,file_sha256 TEXT NOT NULL,original {binary_type} NOT NULL,payload_json TEXT NOT NULL,content_hash TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,UNIQUE(account_id,reference_key))''',
        '''CREATE TABLE IF NOT EXISTS business_bank_transactions(id TEXT PRIMARY KEY,account_id TEXT NOT NULL REFERENCES business_accounting_accounts(id),external_id TEXT NOT NULL,payload_json TEXT NOT NULL,content_hash TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,UNIQUE(account_id,external_id))''',
        '''CREATE TABLE IF NOT EXISTS business_bank_statement_lines(statement_id TEXT NOT NULL REFERENCES business_bank_statements(id),line_number INTEGER NOT NULL CHECK(line_number>0),transaction_id TEXT NOT NULL REFERENCES business_bank_transactions(id),PRIMARY KEY(statement_id,line_number),UNIQUE(statement_id,transaction_id))''',
        '''CREATE TABLE IF NOT EXISTS business_bank_match_events(transaction_id TEXT NOT NULL REFERENCES business_bank_transactions(id),revision INTEGER NOT NULL CHECK(revision>0),payload_json TEXT NOT NULL,content_hash TEXT NOT NULL,previous_hash TEXT,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,PRIMARY KEY(transaction_id,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_bank_reconciliations(id TEXT PRIMARY KEY,account_id TEXT NOT NULL REFERENCES business_accounting_accounts(id),period TEXT NOT NULL,payload_json TEXT NOT NULL,content_hash TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_bank_requests(user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,request_hash TEXT NOT NULL,result_json TEXT NOT NULL,PRIMARY KEY(user_id,request_id))''',
        'CREATE INDEX IF NOT EXISTS business_bank_period ON business_bank_reconciliations(account_id,period,created_at)',
        'CREATE INDEX IF NOT EXISTS business_bank_original ON business_bank_statements(account_id,file_sha256)']


def protected_tables():return TABLES
def runtime_privileges():return {table:('SELECT','INSERT') for table in TABLES}
def guard_statements(dialect):
    if dialect=='sqlite':
        result=[f"CREATE TRIGGER IF NOT EXISTS {table}_{op.lower()}_guard BEFORE {op} ON {table} BEGIN SELECT RAISE(ABORT,'immutable bank evidence'); END" for table in TABLES for op in ('UPDATE','DELETE')]
        keys=('account_id=NEW.account_id AND revision=NEW.revision','id=NEW.id OR (account_id=NEW.account_id AND reference_key=NEW.reference_key)','id=NEW.id OR (account_id=NEW.account_id AND external_id=NEW.external_id)','statement_id=NEW.statement_id AND (line_number=NEW.line_number OR transaction_id=NEW.transaction_id)','transaction_id=NEW.transaction_id AND revision=NEW.revision','id=NEW.id','user_id=NEW.user_id AND request_id=NEW.request_id')
        return result+[f"CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition}) BEGIN SELECT RAISE(ABORT,'immutable bank evidence'); END" for table,condition in zip(TABLES,keys)]
    if dialect!='postgresql':raise ValueError('Unsupported bank dialect')
    result=["CREATE OR REPLACE FUNCTION business_bank_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable bank evidence'; END; $$"]
    for table in TABLES:
        for op in ('UPDATE','DELETE'):
            name=table+'_'+op.lower()+'_guard'
            result.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} BEFORE {op} ON {table} FOR EACH ROW EXECUTE FUNCTION business_bank_immutable_guard(); END IF; END $$")
    return result


def _sha(value):return hashlib.sha256(value if isinstance(value,bytes) else canonical(value).encode('utf-8')).hexdigest()
def _shape(value,allowed,required=None):
    if not isinstance(value,dict) or set(value)-set(allowed) or not set(allowed if required is None else required)<=set(value):raise Problem(400,'Unvollständige oder unbekannte Bankabgleichfelder.')
def _integer(value,min_value=0):
    if type(value) is not int or not min_value<=value<=2147483646:raise Problem(400,'Gültige ganze Fassung erwartet.')
    return value
def _cents(value,signed=True):
    if not isinstance(value,str) or not re.fullmatch(('-?' if signed else '')+r'(?:0|[1-9][0-9]{0,10})\.[0-9]{2}',value) or value=='-0.00':raise Problem(400,'Exakten EUR-Centbetrag ohne Tausendertrennzeichen angeben.')
    return int(Decimal(value)*100)
def _money(value):return ('-' if value<0 else '')+str(abs(value)//100)+'.'+str(abs(value)%100).zfill(2)
def _line(value,label,maximum=500,required=True):
    value=text(value,label,maximum,required=required)
    if any(ord(char)<32 or ord(char)==127 for char in value):raise Problem(400,label+' muss einzeilig sein.')
    return value
def _key(value):return unicodedata.normalize('NFKC',value).casefold()
def _identity(value):return tuple(_key(value[key]) for key in ('booking_date','value_date','amount','currency','counterparty','reference'))
def _iban(value):
    value=''.join(_line(value,'IBAN',80).upper().split())
    if not re.fullmatch(r'[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}',value):raise Problem(400,'Strukturell gültige IBAN erforderlich.')
    expanded=''.join(char if char.isdigit() else str(ord(char)-55) for char in value[4:]+value[:4])
    if int(expanded)%97!=1:raise Problem(400,'IBAN-Prüfziffer stimmt nicht.')
    return value
def _period(value):
    if not isinstance(value,str) or not re.fullmatch(r'(19[0-9]{2}|20[0-9]{2}|21[0-9]{2}|2200)-(0[1-9]|1[0-2])',value):raise Problem(400,'Abgleichmonat als JJJJ-MM angeben.')
    y,m=map(int,value.split('-'));return value+'-01',value+'-'+str(calendar.monthrange(y,m)[1])
def _months(start,end):
    result=[];d=date.fromisoformat(start).replace(day=1);last=date.fromisoformat(end)
    while d<=last:result.append(d.isoformat()[:7]);d=(d.replace(day=28)+timedelta(days=4)).replace(day=1)
    return result


def parse_statement(original,delimiter,start,end):
    if not isinstance(original,bytes) or not 1<=len(original)<=MAX_FILE:raise Problem(400,'Bankdatei benötigt 1 Byte bis höchstens 5 MiB.')
    if delimiter not in (';',','):raise Problem(400,'Komma oder Semikolon ausdrücklich wählen.')
    try:
        content=original.decode('utf-8-sig');reader=csv.reader(io.StringIO(content,newline=''),delimiter=delimiter,strict=True)
        if next(reader,None)!=HEADERS:raise Problem(400,'Dateikopf muss exakt dem Vertrag smartplan_bank_csv_v1 entsprechen.')
        rows=[];seen=set();errors=[]
        for number,raw in enumerate(reader,2):
            if number>MAX_ROWS+1:raise Problem(400,'Höchstens 10.000 Bankzeilen unterstützt.')
            try:
                if len(raw)!=len(HEADERS):raise Problem(400,'Falsche Spaltenzahl.')
                item=dict(zip(HEADERS,raw));item['transaction_id']=_line(item['transaction_id'],'Stabile externe Transaktions-ID',200)
                if item['transaction_id'] in seen:raise Problem(400,'Transaktions-ID kommt innerhalb der Datei mehrfach vor.')
                seen.add(item['transaction_id']);iso_date(item['booking_date']);iso_date(item['value_date'])
                if not start<=item['booking_date']<=end:raise Problem(400,'Buchungstag liegt außerhalb des erklärten Auszugs.')
                if item['currency']!='EUR' or not _cents(item['amount']):raise Problem(400,'Nur tatsächliche EUR-Buchungen mit Betrag ungleich Null.')
                item['counterparty']=_line(item['counterparty'],'Gegenpartei',500,False);item['reference']=_line(item['reference'],'Verwendungszweck',2000,False)
                rows.append(dict(line_number=number-1,**item))
            except Problem as error:errors.append(dict(line_number=number,message=error.message))
        return rows,errors
    except (UnicodeError,csv.Error,ValueError) as error:raise Problem(400,'Ungültige UTF-8-CSV-Datei; keine Buchung wurde übernommen.') from error


class BankReconciliation:
    def __init__(self,office,*,clock=None):self.office=office;self.db=office.db;self.clock=clock or (lambda:datetime.now(timezone.utc))
    def now(self):return self.clock().astimezone(timezone.utc).isoformat(timespec='seconds')
    def _lock(self):
        if not isinstance(self.db,sqlite3.Connection):self.db.execute('SELECT pg_advisory_xact_lock(129842776,18494302)')
    def _access(self,actor,write=False,admin=False):
        fresh=Accounting(self.office)._access(actor)
        require_permission(self.office,fresh,'bank.read')
        if write:
            require_permission(self.office,fresh,'bank.prepare');require_permission(self.office,fresh,'accounting.prepare');require_permission(self.office,fresh,'finance.write')
            from business_schema import require_capability
            require_capability(self.office,'business_bank_reconciliation');Accounting(self.office)._write_gate()
        if admin:require_permission(self.office,fresh,'bank.admin');require_permission(self.office,fresh,'accounting.admin')
        return fresh
    def _open(self,days):
        periods=EuerAccounting(self.office)._ledger()['periods']
        if any(periods.get(day[:7],{}).get('status')=='closed' for day in days):raise Problem(409,'Betroffene EÜR-Periode zuerst mit dem bestehenden Abschlussrecht begründet wieder öffnen; der Bankprüfstand darf nicht still geändert werden.')
    def _event(self,row,kind):
        if not row:raise Problem(404,'Banknachweis nicht verfügbar.')
        keys={'account':('account_id','revision','previous_hash','created_by','created_at'),'statement':('id','account_id','reference_key','file_sha256','created_by','created_at'),'transaction':('id','account_id','external_id','created_by','created_at'),'match':('transaction_id','revision','previous_hash','created_by','created_at'),'reconciliation':('id','account_id','period','created_by','created_at')}[kind]
        envelope={key:row[key] for key in keys};envelope['payload']=json.loads(row['payload_json'])
        if _sha(envelope)!=row['content_hash']:raise Problem(409,'Banknachweis besteht die Integritätsprüfung nicht.')
        return dict(envelope,content_hash=row['content_hash'])
    def _insert(self,table,envelope,extra=None):
        values={key:value for key,value in envelope.items() if key!='payload'};values['payload_json']=canonical(envelope['payload']);values['content_hash']=_sha(envelope);values.update(extra or {})
        self.db.execute('INSERT INTO '+table+'('+','.join(values)+') VALUES('+','.join('?' for _ in values)+')',tuple(values.values()))
    def _request(self,actor,data,operation):
        identifier(data['request_id']);digest=_sha([operation,data]);row=self.db.execute('SELECT * FROM business_bank_requests WHERE user_id=? AND request_id=?',(actor['id'],data['request_id'])).fetchone()
        if row and row['request_hash']!=digest:raise Problem(409,'Vorgangs-ID wurde mit anderem Inhalt verwendet.')
        return digest,json.loads(row['result_json']) if row else None
    def _remember(self,actor,data,digest,reference):self.db.execute('INSERT INTO business_bank_requests(user_id,request_id,request_hash,result_json) VALUES(?,?,?,?)',(actor['id'],data['request_id'],digest,canonical(reference)))
    def _account(self,account_id,revision=None):
        identifier(account_id)
        row=self.db.execute('SELECT * FROM business_bank_account_versions WHERE account_id=? '+('AND revision=?' if revision is not None else 'ORDER BY revision DESC LIMIT 1'),(account_id,revision) if revision is not None else (account_id,)).fetchone()
        return self._event(row,'account')
    def accounts(self,actor):
        with transaction(self.office):
            self._access(actor);items=[self._event(row,'account') for row in self.db.execute('SELECT b.* FROM business_bank_account_versions b WHERE NOT EXISTS(SELECT 1 FROM business_bank_account_versions n WHERE n.account_id=b.account_id AND n.revision>b.revision) ORDER BY b.account_id')]
            return dict(items=items,available_accounts=[item for item in Accounting(self.office).accounts(actor)['items'] if item['kind']=='bank'],csv_contract=dict(version='smartplan_bank_csv_v1',columns=HEADERS,max_bytes=MAX_FILE,max_rows=MAX_ROWS),external_connection=False)
    def save_account(self,actor,data):
        _shape(data,('request_id','account_id','account_revision','revision','iban','label','active','coverage_from','coverage_to','reason'));identifier(data['account_id']);_integer(data['revision']);_integer(data['account_revision'],1)
        iban=_iban(data['iban']);label=_line(data['label'],'Bankbezeichnung',200);reason=_line(data['reason'],'Änderungsgrund',1000,bool(data['revision']))
        coverage_from=iso_date(data['coverage_from']);coverage_to=iso_date(data['coverage_to']) if data['coverage_to'] is not None else None
        if coverage_to is not None and coverage_to<coverage_from:raise Problem(400,'Kontonachweisende liegt vor seinem Beginn.')
        if type(data['active']) is not bool:raise Problem(400,'Aktivierung ausdrücklich angeben.')
        with transaction(self.office):
            self._lock();fresh=self._access(actor,True,True);digest,prior=self._request(fresh,data,'account')
            if prior:return self._account(prior['account_id'],prior['revision'])
            old=self._account(data['account_id']) if self.db.execute('SELECT 1 FROM business_bank_account_versions WHERE account_id=?',(data['account_id'],)).fetchone() else None
            account=Accounting(self.office)._account(data['account_id'])
            if account['kind']!='bank' or account['currency']!='EUR' or not account['active'] or account['revision']!=data['account_revision']:raise Problem(409,'Aktuelles aktives EUR-Bankkonto erforderlich.',request_resolution='not_accepted')
            if data['revision']!=(old['revision'] if old else 0):raise Problem(409,'Bankbindung wurde geändert.',request_resolution='not_accepted')
            if old and old['payload']['iban']!=iban:raise Problem(409,'Bankidentität bleibt unverändert; für eine andere IBAN ein neues Geldkonto anlegen.',request_resolution='not_accepted')
            if old and old['payload']['coverage_from']!=coverage_from:raise Problem(409,'Beginn der nachgewiesenen Kontoführung bleibt unverändert.',request_resolution='not_accepted')
            if coverage_to:
                for row in self.db.execute('SELECT payload_json FROM business_bank_statements WHERE account_id=?',(data['account_id'],)):
                    if json.loads(row['payload_json'])['period_to']>coverage_to:raise Problem(409,'Nachgewiesene Auszüge liegen hinter dem vorgesehenen Kontonachweisende.',request_resolution='not_accepted')
            for row in self.db.execute('SELECT * FROM business_bank_account_versions'):
                item=self._event(row,'account')
                if item['account_id']!=data['account_id'] and item['payload']['iban']==iban:raise Problem(409,'Diese IBAN ist bereits einem anderen Geldkonto zugeordnet.',request_resolution='not_accepted')
            self._open([row['period']+'-01' for row in self.db.execute('SELECT period FROM business_bank_reconciliations WHERE account_id=?',(data['account_id'],))])
            envelope=dict(account_id=data['account_id'],revision=data['revision']+1,previous_hash=old['content_hash'] if old else None,created_by=fresh['id'],created_at=self.now(),payload=dict(account=account,iban=iban,label=label,active=data['active'],coverage_from=coverage_from,coverage_to=coverage_to,reason=reason))
            self._access(fresh,True,True);self._insert(TABLES[0],envelope);self._remember(fresh,data,digest,dict(kind='account',account_id=data['account_id'],revision=envelope['revision']))
            return self._account(data['account_id'])
    def _import(self,actor,data):
        _shape(data,(*IMPORT_FIELDS,'distinct_transaction_confirmations'),IMPORT_FIELDS);identifier(data['account_id']);_integer(data['account_revision'],1);_integer(data['bank_revision'],1)
        binding=self._account(data['account_id']);account=Accounting(self.office)._account(data['account_id'])
        if binding['revision']!=data['bank_revision'] or account['revision']!=data['account_revision'] or not binding['payload']['active'] or not account['active']:raise Problem(409,'Aktuelle aktive Bank-/Geldkontofassung erforderlich.')
        start=iso_date(data['period_from']);end=iso_date(data['period_to'])
        if start>end or (date.fromisoformat(end)-date.fromisoformat(start)).days>366:raise Problem(400,'Auszugszeitraum umfasst höchstens 367 Tage.')
        if start<binding['payload']['coverage_from'] or binding['payload']['coverage_to'] is not None and end>binding['payload']['coverage_to']:raise Problem(400,'Auszug liegt außerhalb der ausdrücklich nachgewiesenen Kontoführung.')
        if data['complete_statement_confirmed'] is not True:raise Problem(400,'Vollständigkeit des erklärten Auszugs ausdrücklich bestätigen.')
        opening=_cents(data['opening_balance']);closing=_cents(data['closing_balance']);filename=_line(data['filename'],'Dateiname',200)
        if '/' in filename or '\\' in filename or not filename.lower().endswith('.csv'):raise Problem(400,'Einfachen CSV-Dateinamen angeben.')
        reference=_line(data['statement_reference'],'Auszugsreferenz',200)
        if not isinstance(data['content_base64'],str) or len(data['content_base64'])>((MAX_FILE+2)//3)*4:raise Problem(400,'Bankdatei ist zu groß.')
        try:original=base64.b64decode(data['content_base64'],validate=True)
        except (ValueError,binascii.Error):raise Problem(400,'Gültige Base64-Originaldatei erforderlich.') from None
        rows,errors=parse_statement(original,data['delimiter'],start,end)
        total=sum(_cents(row['amount']) for row in rows)
        if not errors and opening+total!=closing:errors.append(dict(line_number=None,message='Anfangssaldo plus Buchungen stimmt nicht mit Endsaldo überein.'))
        duplicates=[];identity_checks=[];confirmations=data.get('distinct_transaction_confirmations',{})
        if not isinstance(confirmations,dict) or len(confirmations)>MAX_ROWS:raise Problem(400,'Nachvollziehbare Identitätsprüfungen je externer ID erforderlich.')
        known={}
        for existing in self.db.execute('SELECT * FROM business_bank_transactions WHERE account_id=?',(data['account_id'],)):
            event=self._event(existing,'transaction');known.setdefault(_identity(event['payload']),[]).append(event['external_id'])
        suspected=set()
        for row in rows:
            existing=self.db.execute('SELECT * FROM business_bank_transactions WHERE account_id=? AND external_id=?',(data['account_id'],row['transaction_id'])).fetchone()
            if existing:
                event=self._event(existing,'transaction');payload={key:row[key] for key in HEADERS}
                if event['payload']!=payload:errors.append(dict(line_number=row['line_number']+1,message='Bekannte Transaktions-ID besitzt abweichenden Inhalt.'))
                else:duplicates.append(dict(line_number=row['line_number'],transaction_id=event['id']))
            similar=sorted(set(value for value in known.get(_identity(row),[]) if value!=row['transaction_id']))
            if similar and not existing:
                suspected.add(row['transaction_id']);confirmed=_line(confirmations.get(row['transaction_id'],''),'Prüfgrund eigenständiger Zahlung',1000,False)
                identity_checks.append(dict(line_number=row['line_number'],external_id=row['transaction_id'],similar_external_ids=similar,reason=confirmed,confirmed=bool(confirmed)))
                if not confirmed:errors.append(dict(line_number=row['line_number']+1,message='Inhaltsgleiche Buchung mit anderer ID: eigenständige tatsächliche Zahlung ausdrücklich belegen.'))
            known.setdefault(_identity(row),[]).append(row['transaction_id'])
        if set(confirmations)-suspected:
            # Re-importing the exact accepted original retains its original
            # distinctions, although its rows are now known canonical IDs.
            for external_id,reason in confirmations.items():_line(reason,'Prüfgrund eigenständiger Zahlung',1000,True)
            original_receipt=self.db.execute('SELECT payload_json FROM business_bank_statements WHERE account_id=? AND file_sha256=?',(data['account_id'],_sha(original))).fetchone()
            if not original_receipt or json.loads(original_receipt['payload_json']).get('distinct_transaction_confirmations')!=confirmations:raise Problem(400,'Identitätsprüfungen dürfen nur die ausdrücklich auffälligen Dateizeilen betreffen.')
        metadata=dict(contract='smartplan_bank_csv_v1',account=account,bank=binding,statement_reference=reference,period_from=start,period_to=end,opening_balance=data['opening_balance'],closing_balance=data['closing_balance'],filename=filename,delimiter=data['delimiter'],file_sha256=_sha(original),rows=rows,complete_statement_confirmed=True,distinct_transaction_confirmations=confirmations)
        repeated=self.db.execute('SELECT * FROM business_bank_statements WHERE account_id=? AND (reference_key=? OR file_sha256=?)',(data['account_id'],_key(reference),_sha(original))).fetchall()
        duplicate_statement=None
        for row in repeated:
            previous=self._event(row,'statement')
            if not rows and not errors and not previous['payload']['rows'] and previous['reference_key']!=_key(reference) and (end<previous['payload']['period_from'] or start>previous['payload']['period_to']):continue
            if previous['payload']!=metadata:errors.append(dict(line_number=None,message='Auszugsreferenz oder Originaldatei bereits mit anderem bestätigtem Inhalt verwendet.'))
            else:duplicate_statement=row['id']
        result=dict(metadata=metadata,errors=errors,duplicates=duplicates,identity_checks=identity_checks,duplicate_statement_id=duplicate_statement,can_import=not errors,total=_money(total))
        result['preview_hash']=_sha(result);return result,original
    def preview_import(self,actor,data):
        with transaction(self.office):self._access(actor,True);return self._import(actor,data)[0]
    def import_statement(self,actor,data):
        _shape(data,(*IMPORT_FIELDS,'distinct_transaction_confirmations','request_id','preview_hash','confirmation'),(*IMPORT_FIELDS,'request_id','preview_hash','confirmation'))
        if data['confirmation'] is not True:raise Problem(400,'Geprüften Auszug ausdrücklich bestätigen.')
        with transaction(self.office):
            self._lock();fresh=self._access(actor,True);digest,prior=self._request(fresh,data,'statement')
            if prior:return self.statement(fresh,prior['id'],include_current=False)
            try:
                preview,original=self._import(fresh,{key:data[key] for key in (*IMPORT_FIELDS,'distinct_transaction_confirmations') if key in data})
                if not preview['can_import'] or data['preview_hash']!=preview['preview_hash']:raise Problem(409,'Importvorschau ist fehlerhaft oder wurde verändert.')
                if preview['duplicate_statement_id']:
                    statement_id=preview['duplicate_statement_id']
                else:
                    metadata=preview['metadata'];self._open([month+'-01' for month in _months(metadata['period_from'],metadata['period_to'])]);statement_id=uuid.uuid4().hex
                    self._access(fresh,True);envelope=dict(id=statement_id,account_id=data['account_id'],reference_key=_key(metadata['statement_reference']),file_sha256=_sha(original),created_by=fresh['id'],created_at=self.now(),payload=metadata)
                    self._insert(TABLES[1],envelope,dict(original=original))
                    for row in metadata['rows']:
                        existing=self.db.execute('SELECT id FROM business_bank_transactions WHERE account_id=? AND external_id=?',(data['account_id'],row['transaction_id'])).fetchone()
                        transaction_id=existing['id'] if existing else uuid.uuid4().hex
                        if not existing:self._insert(TABLES[2],dict(id=transaction_id,account_id=data['account_id'],external_id=row['transaction_id'],created_by=fresh['id'],created_at=envelope['created_at'],payload={key:row[key] for key in HEADERS}))
                        self.db.execute('INSERT INTO business_bank_statement_lines(statement_id,line_number,transaction_id) VALUES(?,?,?)',(statement_id,row['line_number'],transaction_id))
                self._remember(fresh,data,digest,dict(kind='statement',id=statement_id));return self.statement(fresh,statement_id,include_current=False)
            except Problem as error:
                if error.status==409:raise Problem(409,error.message,request_resolution='not_accepted') from None
                raise
    def _transaction(self,transaction_id):
        identifier(transaction_id);return self._event(self.db.execute('SELECT * FROM business_bank_transactions WHERE id=?',(transaction_id,)).fetchone(),'transaction')
    def _match(self,transaction_id):
        row=self.db.execute('SELECT * FROM business_bank_match_events WHERE transaction_id=? ORDER BY revision DESC LIMIT 1',(transaction_id,)).fetchone()
        return self._event(row,'match') if row else dict(transaction_id=transaction_id,revision=0,content_hash=None,previous_hash=None,payload=dict(links=[],reason=''))
    def statements(self,actor,query):
        _shape(query,('account_id','limit','offset'),());account_id=query.get('account_id');identifier(account_id) if account_id else None
        limit,offset=self._page(query)
        with transaction(self.office):
            self._access(actor);rows=self.db.execute('SELECT id,account_id,reference_key,file_sha256,content_hash,created_by,created_at FROM business_bank_statements '+('WHERE account_id=? ' if account_id else '')+'ORDER BY created_at DESC,id LIMIT ? OFFSET ?',((account_id,) if account_id else ())+(limit+1,offset)).fetchall()
            return dict(items=[dict(row) for row in rows[:limit]],next_offset=offset+limit if len(rows)>limit else None)
    @staticmethod
    def _page(query):
        if any(not isinstance(query.get(key,default),str) or not re.fullmatch(r'[0-9]{1,8}',query.get(key,default)) for key,default in [('limit','50'),('offset','0')]):raise Problem(400,'Gültige Seitenzahlen erforderlich.')
        limit=int(query.get('limit','50'));offset=int(query.get('offset','0'))
        if not 1<=limit<=100:raise Problem(400,'Höchstens hundert Zeilen je Seite.')
        return limit,offset
    def statement(self,actor,statement_id,*,include_current=True):
        identifier(statement_id)
        with transaction(self.office):
            self._access(actor);row=self.db.execute('SELECT id,account_id,reference_key,file_sha256,payload_json,content_hash,created_by,created_at FROM business_bank_statements WHERE id=?',(statement_id,)).fetchone();event=self._event(row,'statement')
            lines=[dict(line,transaction=self._transaction(line['transaction_id']),**(dict(current=self._match(line['transaction_id'])) if include_current else {})) for line in self.db.execute('SELECT line_number,transaction_id FROM business_bank_statement_lines WHERE statement_id=? ORDER BY line_number',(statement_id,))]
            if include_current and any(line['current']['payload']['links'] for line in lines):self._sources(actor)
            return dict(statement=event,lines=lines,original=dict(filename=event['payload']['filename'],sha256=event['file_sha256'],path='/bank/statements/'+statement_id+'/original'))
    def original(self,actor,statement_id):
        with transaction(self.office):
            self._access(actor);identifier(statement_id);row=self.db.execute('SELECT * FROM business_bank_statements WHERE id=?',(statement_id,)).fetchone();event=self._event(row,'statement');content=bytes(row['original'])
            if _sha(content)!=event['file_sha256']:raise Problem(409,'Originalprüfsumme stimmt nicht.')
            self._access(actor);return content,'text/csv; charset=utf-8'
    def _sources(self,actor):
        catalog=EuerAccounting(self.office).sources(actor);sources={}
        ledger=EuerAccounting(self.office)._ledger()
        for movement in catalog['cash_movements']:
            kind=movement['source_kind'];source_id=movement['source_id'];parent=None
            if kind=='cash_event':parent=next(item['source']['source_hash'] for item in catalog['items'] if item['kind']=='cash' and item['id']==source_id)
            elif kind=='reviewed_external_cash':parent=ledger['by_id'][source_id]['entry_hash']
            elif kind=='payroll_cash':parent=next(item['source']['source_hash'] for item in catalog['items'] if item['kind']=='payroll_cash' and any(part['id']==source_id for part in item['source']['cash_movements']))
            elif kind=='travel_cash':parent=next(item['source']['source_hash'] for item in catalog['items'] if item['kind']=='travel_cash' and any(part['id']==source_id for part in item['source']['cash_movements']))
            else:raise Problem(409,'Unbekannte Geldquellenart muss vor dem Bankabgleich unterstützt werden.')
            value=dict(movement,origin_hash=parent,source_hash=_sha([movement,parent]));sources[kind+':'+source_id]=value
        return sources
    def _matches(self):return [self._event(row,'match') for row in self.db.execute('SELECT m.* FROM business_bank_match_events m WHERE NOT EXISTS(SELECT 1 FROM business_bank_match_events n WHERE n.transaction_id=m.transaction_id AND n.revision>m.revision) ORDER BY m.transaction_id')]
    def _capacity(self,sources,exclude=None):
        used={};stale=set()
        for event in self._matches():
            if event['transaction_id']==exclude:continue
            for link in event['payload']['links']:
                key=link['source']['source_kind']+':'+link['source']['source_id'];used[key]=used.get(key,0)+_cents(link['amount'],False)
                if sources.get(key)!=link['source']:stale.add(key)
        return used,stale
    def candidates(self,actor,transaction_id):
        with transaction(self.office):
            fresh=self._access(actor);bank=self._transaction(transaction_id);sources=self._sources(fresh);used,stale=self._capacity(sources,transaction_id);direction='in' if _cents(bank['payload']['amount'])>0 else 'out'
            return dict(transaction=bank,current=self._match(transaction_id),items=[dict(source=value,remaining=_money(max(0,_cents(value['amount'],False)-used.get(key,0))),stale_existing_links=key in stale) for key,value in sources.items() if value['account']['id']==bank['account_id'] and value['direction']==direction])
    def _prepare_match(self,actor,transaction_id,data):
        _shape(data,('revision','links','reason'));_integer(data['revision']);bank=self._transaction(transaction_id);current=self._match(transaction_id)
        if current['revision']!=data['revision']:raise Problem(409,'Zuordnungsfassung wurde verändert.')
        if not isinstance(data['links'],list) or len(data['links'])>100:raise Problem(400,'Höchstens hundert ausdrückliche Zuordnungsteile.')
        sources=self._sources(actor);used,stale=self._capacity(sources,transaction_id);links=[];seen=set();total=0;bank_amount=_cents(bank['payload']['amount']);days={bank['payload']['booking_date']}
        for item in data['links']:
            _shape(item,('source_kind','source_id','source_hash','amount','date_difference_reason'));key=str(item['source_kind'])+':'+str(item['source_id']);source=sources.get(key)
            if not source or source['source_hash']!=item['source_hash'] or key in stale:raise Problem(409,'Aktuelle unveränderte Geldquelle erforderlich; veraltete Zuordnungen zuerst ausdrücklich aufheben.')
            if key in seen:raise Problem(400,'Jede Geldquelle nur einmal je Bankzeile zuordnen.')
            seen.add(key);amount=_cents(item['amount'],False)
            if amount<=0 or source['account']['id']!=bank['account_id'] or source['direction']!=('in' if bank_amount>0 else 'out'):raise Problem(400,'Positiver Teilbetrag, dasselbe Konto und dieselbe Richtung erforderlich.')
            if used.get(key,0)+amount>_cents(source['amount'],False):raise Problem(409,'Zuordnung überschreitet den noch verfügbaren Geldflussbetrag.')
            difference=_line(item['date_difference_reason'],'Begründung abweichender Zahlungstage',1000,source['date']!=bank['payload']['booking_date'])
            total+=amount;days.add(source['date']);links.append(dict(source=source,amount=item['amount'],date_difference_reason=difference))
        for item in current['payload']['links']:days.add(item['source']['date'])
        self._open(days)
        if total>abs(bank_amount):raise Problem(400,'Zuordnungen überschreiten den Bankbetrag.')
        reason=_line(data['reason'],'Zuordnungs-/Korrekturgrund',1000,True)
        result=dict(transaction=bank,revision=current['revision']+1,previous_hash=current['content_hash'],links=links,reason=reason,matched_amount=_money(total),remaining=_money(abs(bank_amount)-total),complete=total==abs(bank_amount))
        result['preview_hash']=_sha(result);return result
    def preview_match(self,actor,transaction_id,data):
        with transaction(self.office):return self._prepare_match(self._access(actor,True),transaction_id,data)
    def save_match(self,actor,transaction_id,data):
        _shape(data,('request_id','revision','links','reason','preview_hash','confirmation'))
        if data['confirmation'] is not True:raise Problem(400,'Geprüfte Zuordnung ausdrücklich bestätigen.')
        with transaction(self.office):
            self._lock();fresh=self._access(actor,True);self._transaction(transaction_id);self._sources(fresh);digest,prior=self._request(fresh,data,'match:'+transaction_id)
            if prior:return self._event(self.db.execute('SELECT * FROM business_bank_match_events WHERE transaction_id=? AND revision=?',(transaction_id,prior['revision'])).fetchone(),'match')
            try:
                preview=self._prepare_match(fresh,transaction_id,{key:data[key] for key in ('revision','links','reason')})
                if preview['preview_hash']!=data['preview_hash']:raise Problem(409,'Zuordnungsvorschau wurde verändert.')
                self._access(fresh,True);self._sources(fresh)
                envelope=dict(transaction_id=transaction_id,revision=preview['revision'],previous_hash=preview['previous_hash'],created_by=fresh['id'],created_at=self.now(),payload={key:preview[key] for key in ('transaction','links','reason','matched_amount','remaining','complete','preview_hash')})
                self._insert(TABLES[4],envelope);self._remember(fresh,data,digest,dict(kind='match',transaction_id=transaction_id,revision=envelope['revision']));return self._match(transaction_id)
            except Problem as error:
                if error.status==409:raise Problem(409,error.message,request_resolution='not_accepted') from None
                raise
    def history(self,actor,transaction_id,query):
        _shape(query,('limit','offset'),());limit,offset=self._page(query)
        with transaction(self.office):
            fresh=self._access(actor);self._sources(fresh);self._transaction(transaction_id);rows=self.db.execute('SELECT * FROM business_bank_match_events WHERE transaction_id=? ORDER BY revision DESC LIMIT ? OFFSET ?',(transaction_id,limit+1,offset)).fetchall()
            return dict(items=[self._event(row,'match') for row in rows[:limit]],next_offset=offset+limit if len(rows)>limit else None)

    def _report(self,actor,data):
        _shape(data,('account_id','period','statement_ids','reason'));identifier(data['account_id']);start,end=_period(data['period']);binding=self._account(data['account_id'])
        if not isinstance(data['statement_ids'],list) or not 1<=len(data['statement_ids'])<=100:raise Problem(400,'Ein bis hundert unterschiedliche Auszüge für den Monat wählen.')
        for statement_id in data['statement_ids']:identifier(statement_id)
        if len(set(data['statement_ids']))!=len(data['statement_ids']):raise Problem(400,'Auszüge dürfen nicht doppelt ausgewählt werden.')
        coverage_from=max(start,binding['payload']['coverage_from']);coverage_to=min(end,binding['payload']['coverage_to'] or end)
        if coverage_from>coverage_to:raise Problem(400,'Monat liegt außerhalb der erklärten Kontoführung.')
        reason=_line(data['reason'],'Prüfgrund',1000,True);statements=[];transactions={};issues=[]
        for statement_id in data['statement_ids']:
            identifier(statement_id);detail=self.statement(actor,statement_id);event=detail['statement'];metadata=event['payload']
            self.original(actor,statement_id)
            if event['account_id']!=data['account_id']:raise Problem(400,'Alle gewählten Auszüge müssen zum selben Bankkonto gehören.')
            statements.append(event)
            for line in detail['lines']:transactions[line['transaction_id']]=line
        statements.sort(key=lambda item:(item['payload']['period_from'],item['id']))
        day=coverage_from;closing=None
        for event in statements:
            metadata=event['payload']
            if metadata['period_from']!=day or metadata['period_to']>coverage_to:issues.append(dict(code='statement_coverage_gap_or_overlap',id=event['id']))
            if closing is not None and closing!=metadata['opening_balance']:issues.append(dict(code='statement_balance_discontinuity',id=event['id']))
            closing=metadata['closing_balance'];day=(date.fromisoformat(metadata['period_to'])+timedelta(days=1)).isoformat()
        if day!=(date.fromisoformat(coverage_to)+timedelta(days=1)).isoformat():issues.append(dict(code='statement_coverage_incomplete',id=None))
        sources=self._sources(actor);used,stale=self._capacity(sources);selected_sources={};bank_rows=[];bank_sum=0
        for transaction_id,line in sorted(transactions.items(),key=lambda pair:(pair[1]['transaction']['payload']['booking_date'],pair[0])):
            bank=line['transaction'];match=line['current'];amount=_cents(bank['payload']['amount']);matched=0;row_issues=[]
            for link in match['payload']['links']:
                key=link['source']['source_kind']+':'+link['source']['source_id'];selected_sources[key]=sources.get(key)
                if sources.get(key)!=link['source'] or key in stale:row_issues.append('source_changed')
                else:matched+=_cents(link['amount'],False)
            if matched!=abs(amount):row_issues.append('bank_amount_unmatched')
            for code in sorted(set(row_issues)):issues.append(dict(code=code,id=transaction_id))
            bank_sum+=amount;bank_rows.append(dict(transaction=bank,match=match,matched_amount=_money(matched),remaining=_money(abs(amount)-matched),issues=sorted(set(row_issues))))
        cash_rows=[];cash_sum=0
        for key,source in sorted(sources.items()):
            if source['account']['id']!=data['account_id'] or not start<=source['date']<=end:continue
            selected_sources[key]=source;amount=_cents(source['amount'],False);allocated=used.get(key,0)
            if key in stale:issues.append(dict(code='source_changed',id=key))
            if allocated!=amount:issues.append(dict(code='cash_amount_unmatched',id=key))
            cash_sum+=amount*(1 if source['direction']=='in' else -1);cash_rows.append(dict(source=source,matched_amount=_money(allocated),remaining=_money(amount-allocated)))
        allocation_manifest=[event for event in self._matches() if event['transaction_id'] in transactions or any(link['source']['source_kind']+':'+link['source']['source_id'] in selected_sources for link in event['payload']['links'])]
        state=dict(bank=binding,statements=[dict(id=event['id'],content_hash=event['content_hash']) for event in statements],transactions=[dict(id=row['transaction']['id'],transaction_hash=row['transaction']['content_hash'],match_hash=row['match']['content_hash']) for row in bank_rows],sources=selected_sources,allocations=[dict(transaction_id=event['transaction_id'],revision=event['revision'],content_hash=event['content_hash']) for event in allocation_manifest])
        report=dict(schema_version=1,account_id=data['account_id'],period=data['period'],period_from=start,period_to=end,coverage_from=coverage_from,coverage_to=coverage_to,bank=binding,statement_ids=[event['id'] for event in statements],statements=state['statements'],bank_rows=bank_rows,cash_rows=cash_rows,source_manifest=selected_sources,allocation_manifest=allocation_manifest,opening_balance=statements[0]['payload']['opening_balance'],closing_balance=statements[-1]['payload']['closing_balance'],bank_movement_net=_money(bank_sum),cash_movement_net=_money(cash_sum),issues=issues,complete=not issues,reason=reason,state_hash=_sha(state),external_bank_verification=False,new_payment_created=False,tax_classification_changed=False)
        report['preview_hash']=_sha(report);return report
    def preview_reconciliation(self,actor,data):
        with transaction(self.office):return self._report(self._access(actor,True),data)
    def save_reconciliation(self,actor,data):
        _shape(data,('request_id','account_id','period','statement_ids','reason','preview_hash','confirmation'))
        if data['confirmation'] is not True:raise Problem(400,'Den tatsächlichen Prüfstand ausdrücklich bestätigen.')
        with transaction(self.office):
            self._lock();fresh=self._access(actor,True);self._sources(fresh);digest,prior=self._request(fresh,data,'reconciliation')
            if prior:return self.reconciliation_receipt(prior['id'])
            try:
                report=self._report(fresh,{key:data[key] for key in ('account_id','period','statement_ids','reason')})
                if report['preview_hash']!=data['preview_hash']:raise Problem(409,'Bankprüfstand wurde verändert; neue Vorschau prüfen.')
                report_id=uuid.uuid4().hex;envelope=dict(id=report_id,account_id=data['account_id'],period=data['period'],created_by=fresh['id'],created_at=self.now(),payload=report)
                self._access(fresh,True);self._insert(TABLES[5],envelope);self._remember(fresh,data,digest,dict(kind='reconciliation',id=report_id));return self.reconciliation_receipt(report_id)
            except Problem as error:
                if error.status==409:raise Problem(409,error.message,request_resolution='not_accepted') from None
                raise
    def _reconciliation(self,report_id):
        identifier(report_id);return self._event(self.db.execute('SELECT * FROM business_bank_reconciliations WHERE id=?',(report_id,)).fetchone(),'reconciliation')
    def reconciliation(self,actor,report_id):
        with transaction(self.office):
            fresh=self._access(actor);event=self._reconciliation(report_id);report=event['payload'];current=self._report(fresh,{key:report[key] for key in ('account_id','period','statement_ids','reason')})
            return dict(self.reconciliation_receipt(report_id),current=report['state_hash']==current['state_hash'],current_issues=current['issues'])
    def reconciliation_receipt(self,report_id):
        event=self._reconciliation(report_id);report=event['payload']
        return dict(record=event,exports={kind:dict(filename='Bankabgleich-'+report['period']+'-'+report_id+'.'+kind,media_type=mime,size=len(content),sha256=_sha(content)) for kind,(content,mime) in self._exports(event).items()})
    def reconciliations(self,actor,query):
        _shape(query,('account_id','period','limit','offset'),());limit,offset=self._page(query);conditions=[];args=[]
        for key in ('account_id','period'):
            if key in query:
                identifier(query[key]) if key=='account_id' else _period(query[key]);conditions.append(key+'=?');args.append(query[key])
        with transaction(self.office):
            self._access(actor);rows=self.db.execute('SELECT id,account_id,period,content_hash,created_by,created_at FROM business_bank_reconciliations '+('WHERE '+' AND '.join(conditions)+' ' if conditions else '')+'ORDER BY created_at DESC,id LIMIT ? OFFSET ?',tuple(args)+(limit+1,offset)).fetchall()
            return dict(items=[dict(row) for row in rows[:limit]],next_offset=offset+limit if len(rows)>limit else None)
    @staticmethod
    def _exports(event):
        report=event['payload'];stream=io.StringIO(newline='');writer=csv.writer(stream,delimiter=';',lineterminator='\r\n');writer.writerow(['transaction_id','booking_date','counterparty','reference','amount_eur','matched_eur','remaining_eur','issues'])
        for row in report['bank_rows']:
            item=row['transaction'];data=item['payload'];cells=[item['id'],data['booking_date'],data['counterparty'],data['reference'],data['amount'],row['matched_amount'],row['remaining'],','.join(row['issues'])]
            writer.writerow([("'"+value if index not in (4,5,6) and value[:1] in ('=','+','-','@','\t','\r') else value) for index,value in enumerate(cells)])
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer
        from reportlab.pdfgen.canvas import Canvas
        output=io.BytesIO();styles=getSampleStyleSheet();story=[]
        def line(value):story.extend([Paragraph(escape(str(value)),styles['Normal']),Spacer(1,5)])
        line('Bankabgleich '+report['period']);line('Bericht '+event['id']+' / '+event['content_hash']);line('Konto '+report['bank']['payload']['label']);line('Vollständig im erklärten Umfang: '+('Ja' if report['complete'] else 'Nein'));line('Anfangssaldo '+report['opening_balance']+' EUR / Endsaldo '+report['closing_balance']+' EUR');line('Auszugsbewegungen '+report['bank_movement_net']+' EUR / Geldquellen nach Zahlungstag '+report['cash_movement_net']+' EUR');line('Keine externe Bankverifikation. Dieser Abgleich erzeugt keine Zahlung oder Steuerbuchung.')
        for row in report['bank_rows']:
            value=row['transaction']['payload'];line(value['booking_date']+' / '+value['counterparty']+' / '+value['amount']+' EUR / Rest '+row['remaining']+' EUR / '+value['reference'])
        for issue in report['issues']:line('Offen: '+issue['code']+' / '+str(issue['id'] or 'Zeitraum'))
        SimpleDocTemplate(output,title='Bankabgleich').build(story,canvasmaker=lambda *args,**kwargs:Canvas(*args,**dict(kwargs,invariant=1)))
        return dict(json=(canonical(event).encode('utf-8'),'application/json; charset=utf-8'),csv=(('\ufeff'+stream.getvalue()).encode('utf-8'),'text/csv; charset=utf-8'),pdf=(output.getvalue(),'application/pdf'))
    def export(self,actor,report_id,kind):
        if kind not in ('json','csv','pdf'):raise Problem(400,'Unbekanntes Exportformat.')
        with transaction(self.office):
            fresh=self._access(actor);self._sources(fresh);record=self._reconciliation(report_id);result=self._exports(record)[kind];self._access(fresh);return result


def period_closure_proof(office,actor,period):
    """Called only for a new EÜR close; old manual attestations stay untouched."""
    from business_schema import _tables
    if not set(TABLES)<=_tables(office):return None
    api=BankReconciliation(office)
    bindings=[api._event(row,'account') for row in office.db.execute('SELECT a.* FROM business_bank_account_versions a WHERE NOT EXISTS(SELECT 1 FROM business_bank_account_versions n WHERE n.account_id=a.account_id AND n.revision>a.revision)')]
    if not bindings:return None
    api._lock();api._access(actor);proofs=[];start,end=_period(period)
    for binding in bindings:
        # Historical statement activity remains relevant after archival.
        account_id=binding['account_id'];has_rows=office.db.execute('SELECT id FROM business_bank_statements WHERE account_id=?',(account_id,)).fetchone()
        if end<binding['payload']['coverage_from'] or binding['payload']['coverage_to'] is not None and start>binding['payload']['coverage_to']:continue
        if not binding['payload']['active'] and not has_rows:continue
        candidates=office.db.execute('SELECT id FROM business_bank_reconciliations WHERE account_id=? AND period=? ORDER BY created_at DESC,id DESC',(account_id,period)).fetchall();found=None
        for row in candidates:
            value=api.reconciliation(actor,row['id'])
            if value['current'] and value['record']['payload']['complete']:found=value['record'];break
        if not found:raise Problem(409,'Für jedes eingerichtete Bankkonto ist ein aktueller vollständig bestätigter Monatsabgleich erforderlich.')
        proofs.append(dict(id=found['id'],account_id=account_id,content_hash=found['content_hash'],state_hash=found['payload']['state_hash']))
    return dict(schema_version=1,period=period,reconciliations=proofs,scope='explicitly_configured_bank_accounts',external_bank_verification=False)


def validate_period_closure_proof(office,proof,period):
    """Validate a historical close against its frozen reports, never today."""
    try:
        _shape(proof,('schema_version','period','reconciliations','scope','external_bank_verification'));_period(period)
        if proof['schema_version']!=1 or type(proof['schema_version']) is not int or proof['period']!=period or proof['scope']!='explicitly_configured_bank_accounts' or proof['external_bank_verification'] is not False or not isinstance(proof['reconciliations'],list):raise ValueError('Invalid bank period proof')
        api=BankReconciliation(office);seen=set()
        for reference in proof['reconciliations']:
            _shape(reference,('id','account_id','content_hash','state_hash'));record=api._reconciliation(reference['id']);report=record['payload']
            if reference['account_id'] in seen or record['account_id']!=reference['account_id'] or record['content_hash']!=reference['content_hash'] or report['state_hash']!=reference['state_hash'] or record['period']!=period or report['period']!=period or report['complete'] is not True:raise ValueError('Changed historical bank period reference')
            seen.add(reference['account_id'])
    except (Problem,KeyError,TypeError) as error:raise ValueError('Invalid historical bank period proof') from error
    return True


def _verify_source(office,source):
    _shape(source,('source_kind','source_id','account','date','direction','amount','source_path','origin_hash','source_hash'))
    identifier(source['source_id']);iso_date(source['date']);amount=_cents(source['amount'],False)
    movement={key:value for key,value in source.items() if key not in ('source_hash','origin_hash')}
    if amount<=0 or source['direction'] not in ('in','out') or not re.fullmatch(HASH,source['origin_hash']) or _sha([movement,source['origin_hash']])!=source['source_hash']:raise ValueError('Invalid bank cash snapshot')
    if source['source_kind']=='cash_event':
        event=Accounting(office)._event(None,source['source_id'])
        expected=dict(account=event['account'],date=event['cash_date'],direction=event['direction'],amount=event['amount'])
    elif source['source_kind']=='reviewed_external_cash':
        event=EuerAccounting(office)._ledger()['by_id'].get(source['source_id'])
        if not event or not event['effect'] or event['effect']['operation']!='external_cash' or event['entry_hash']!=source['origin_hash']:raise ValueError('Missing external cash snapshot')
        effect=event['effect'];expected=dict(account=effect['details']['cash_account'],date=effect['payload']['cash_date'],direction=effect['payload']['direction'],amount=effect['payload']['amount'])
    elif source['source_kind']=='payroll_cash':
        from business_payroll_cash import public_source
        reference=re.fullmatch(r'/payroll/cash/financial/('+ID+r')\?revision=([0-9]+)',source['source_path'])
        if not reference:raise ValueError('Invalid payroll bank source path')
        event=public_source(office,reference[1],int(reference[2]));part=next((item for item in event['cash_movements'] if item['id']==source['source_id']),None)
        if not part or event['source_hash']!=source['origin_hash']:raise ValueError('Missing payroll bank cash snapshot')
        expected={key:part[key] for key in ('account','date','direction','amount')}
    elif source['source_kind']=='travel_cash':
        from accounting_travel_sources import verify_bank_source
        expected=verify_bank_source(office,source)
    else:raise ValueError('Unknown bank cash source')
    if any(source[key]!=value for key,value in expected.items()):raise ValueError('Changed actual bank cash amount or identity')


def validate_integrity(office):
    from business_schema import _tables
    present=set(TABLES)&_tables(office)
    if not present:return True
    if present!=set(TABLES):raise ValueError('Incomplete bank schema')
    api=BankReconciliation(office);accounts={};iban_accounts={};transactions={};matches={}
    try:
        for row in office.db.execute('SELECT * FROM business_bank_account_versions ORDER BY account_id,revision'):
            event=api._event(row,'account');payload=event['payload'];previous=accounts.get(event['account_id']);_shape(payload,('account','iban','label','active','coverage_from','coverage_to','reason'))
            if _iban(payload['iban'])!=payload['iban'] or type(payload['active']) is not bool or Accounting(office)._account(event['account_id'],payload['account']['revision'])!=payload['account'] or payload['account']['kind']!='bank':raise ValueError('Invalid bank account binding')
            iso_date(payload['coverage_from']);iso_date(payload['coverage_to']) if payload['coverage_to'] is not None else None
            if payload['account']['currency']!='EUR' or not payload['account']['active'] or payload['coverage_to'] is not None and payload['coverage_to']<payload['coverage_from']:raise ValueError('Invalid bank currency or declared coverage')
            _line(payload['label'],'Bankbezeichnung',200);_line(payload['reason'],'Änderungsgrund',1000,bool(previous))
            if event['revision']!=(previous['revision']+1 if previous else 1) or event['previous_hash']!=(previous['content_hash'] if previous else None) or previous and (payload['iban']!=previous['payload']['iban'] or payload['coverage_from']!=previous['payload']['coverage_from'] or not payload['reason']):raise ValueError('Invalid bank account history')
            if payload['iban'] in iban_accounts and iban_accounts[payload['iban']]!=event['account_id']:raise ValueError('Reused bank identity')
            iban_accounts[payload['iban']]=event['account_id'];accounts[event['account_id']]=event
        for row in office.db.execute('SELECT * FROM business_bank_transactions ORDER BY id'):
            event=api._event(row,'transaction');payload=event['payload'];_shape(payload,HEADERS);iso_date(payload['booking_date']);iso_date(payload['value_date'])
            if payload['transaction_id']!=event['external_id'] or event['account_id'] not in accounts or payload['currency']!='EUR' or not _cents(payload['amount']):raise ValueError('Invalid bank transaction')
            _line(payload['counterparty'],'Gegenpartei',500,False);_line(payload['reference'],'Verwendungszweck',2000,False);transactions[event['id']]=event
        linked=set();originals={}
        for row in office.db.execute('SELECT * FROM business_bank_statements ORDER BY id'):
            event=api._event(row,'statement');metadata=event['payload'];original=bytes(row['original']);rows,errors=parse_statement(original,metadata['delimiter'],metadata['period_from'],metadata['period_to'])
            _shape(metadata,('contract','account','bank','statement_reference','period_from','period_to','opening_balance','closing_balance','filename','delimiter','file_sha256','rows','complete_statement_confirmed','distinct_transaction_confirmations'))
            start=iso_date(metadata['period_from']);end=iso_date(metadata['period_to']);binding=metadata['bank']['payload']
            if start>end or (date.fromisoformat(end)-date.fromisoformat(start)).days>366 or start<binding['coverage_from'] or binding['coverage_to'] is not None and end>binding['coverage_to'] or not binding['active'] or not metadata['account']['active']:raise ValueError('Invalid bank statement period or coverage')
            filename=_line(metadata['filename'],'Dateiname',200)
            if '/' in filename or '\\' in filename or not filename.lower().endswith('.csv'):raise ValueError('Invalid original filename')
            _line(metadata['statement_reference'],'Auszugsreferenz',200)
            confirmations=metadata['distinct_transaction_confirmations']
            if not isinstance(confirmations,dict) or set(confirmations)-{value['transaction_id'] for value in rows}:raise ValueError('Invalid distinct bank transaction proof')
            for reason in confirmations.values():_line(reason,'Prüfgrund eigenständiger Zahlung',1000,True)
            if errors or metadata['rows']!=rows or _sha(original)!=event['file_sha256'] or metadata['file_sha256']!=event['file_sha256'] or metadata['contract']!='smartplan_bank_csv_v1' or _key(metadata['statement_reference'])!=event['reference_key'] or metadata['complete_statement_confirmed'] is not True:raise ValueError('Changed bank original or parsed statement')
            if _cents(metadata['opening_balance'])+sum(_cents(item['amount']) for item in rows)!=_cents(metadata['closing_balance']):raise ValueError('Invalid bank balances')
            if api._account(event['account_id'],metadata['bank']['revision'])!=metadata['bank'] or Accounting(office)._account(event['account_id'],metadata['account']['revision'])!=metadata['account']:raise ValueError('Invalid captured bank account')
            key=(event['account_id'],event['file_sha256'])
            for previous in originals.get(key,[]):
                if rows or previous['rows'] or not (end<previous['period_from'] or start>previous['period_to']):raise ValueError('Duplicated original statement identity')
            originals.setdefault(key,[]).append(metadata)
            lines=office.db.execute('SELECT * FROM business_bank_statement_lines WHERE statement_id=? ORDER BY line_number',(event['id'],)).fetchall()
            if len(lines)!=len(rows):raise ValueError('Missing original bank rows')
            for line,value in zip(lines,rows):
                transaction=transactions.get(line['transaction_id'])
                if not transaction or transaction['account_id']!=event['account_id'] or line['line_number']!=value['line_number'] or transaction['payload']!={key:value[key] for key in HEADERS}:raise ValueError('Changed bank row binding')
                linked.add(transaction['id'])
        if linked!=set(transactions):raise ValueError('Orphan bank transaction')
        for row in office.db.execute('SELECT * FROM business_bank_match_events ORDER BY transaction_id,revision'):
            event=api._event(row,'match');payload=event['payload'];previous=matches.get(event['transaction_id']);bank=transactions[event['transaction_id']]
            if payload['transaction']!=bank or event['revision']!=(previous['revision']+1 if previous else 1) or event['previous_hash']!=(previous['content_hash'] if previous else None) or not payload['reason']:raise ValueError('Invalid bank match chain')
            total=0;seen=set()
            for link in payload['links']:
                _shape(link,('source','amount','date_difference_reason'));source=link['source'];_verify_source(office,source);key=source['source_kind']+':'+source['source_id'];amount=_cents(link['amount'],False)
                if key in seen or amount<=0 or amount>_cents(source['amount'],False) or source['account']['id']!=bank['account_id'] or source['direction']!=('in' if _cents(bank['payload']['amount'])>0 else 'out') or source['date']!=bank['payload']['booking_date'] and not link['date_difference_reason']:raise ValueError('Invalid bank matched amount or direction')
                seen.add(key);total+=amount
            remaining=abs(_cents(bank['payload']['amount']))-total
            if remaining<0 or payload['matched_amount']!=_money(total) or payload['remaining']!=_money(remaining) or payload['complete']!=(remaining==0):raise ValueError('Invalid bank match totals')
            preview=dict(transaction=bank,revision=event['revision'],previous_hash=event['previous_hash'],**{key:payload[key] for key in ('links','reason','matched_amount','remaining','complete')})
            if payload['preview_hash']!=_sha(preview):raise ValueError('Changed bank match preview')
            matches[event['transaction_id']]=event
        reserved={};origins={}
        for event in matches.values():
            for link in event['payload']['links']:
                source=link['source'];key=source['source_kind']+':'+source['source_id'];reserved[key]=reserved.get(key,0)+_cents(link['amount'],False)
                if key in origins and origins[key]!=source or reserved[key]>_cents(source['amount'],False):raise ValueError('Bank cash capacity was consumed more than once')
                origins[key]=source
        for row in office.db.execute('SELECT * FROM business_bank_reconciliations ORDER BY id'):
            event=api._event(row,'reconciliation');report=event['payload'];copy=dict(report);copy.pop('preview_hash')
            if report['preview_hash']!=_sha(copy) or report['account_id']!=event['account_id'] or report['period']!=event['period']:raise ValueError('Changed bank reconciliation preview')
            if api._account(event['account_id'],report['bank']['revision'])!=report['bank']:raise ValueError('Changed bank reconciliation account')
            captured={}
            for match in report['allocation_manifest']:
                stored=api._event(office.db.execute('SELECT * FROM business_bank_match_events WHERE transaction_id=? AND revision=?',(match['transaction_id'],match['revision'])).fetchone(),'match')
                if stored!=match or match['transaction_id'] in captured:raise ValueError('Changed bank allocation manifest')
                captured[match['transaction_id']]=match
            for source in report['source_manifest'].values():
                if source is not None:_verify_source(office,source)
            # Recompute the historical view from captured actual immutable
            # sources and exact match revisions, independent of current matches.
            historic=BankReconciliation(office);historic._access=lambda *args,**kwargs:None
            historic._account=lambda account_id,revision=None:report['bank']
            historic._sources=lambda actor:{key:value for key,value in report['source_manifest'].items() if value is not None}
            historic._matches=lambda:list(captured.values())
            historic._match=lambda transaction_id:captured.get(transaction_id,dict(transaction_id=transaction_id,revision=0,content_hash=None,previous_hash=None,payload=dict(links=[],reason='')))
            rebuilt=historic._report(None,{key:report[key] for key in ('account_id','period','statement_ids','reason')})
            if rebuilt!=report:raise ValueError('Bank reconciliation sums or completeness changed')
        for row in office.db.execute('SELECT * FROM business_bank_requests'):
            identifier(row['request_id']);reference=json.loads(row['result_json'])
            if not re.fullmatch(HASH,row['request_hash']):raise ValueError('Invalid bank receipt fingerprint')
            kind=reference['kind']
            if kind=='account':api._account(reference['account_id'],reference['revision'])
            elif kind=='statement':api._event(office.db.execute('SELECT * FROM business_bank_statements WHERE id=?',(reference['id'],)).fetchone(),'statement')
            elif kind=='match':api._event(office.db.execute('SELECT * FROM business_bank_match_events WHERE transaction_id=? AND revision=?',(reference['transaction_id'],reference['revision'])).fetchone(),'match')
            elif kind=='reconciliation':api._reconciliation(reference['id'])
            else:raise ValueError('Unknown bank receipt')
    except (Problem,KeyError,TypeError,json.JSONDecodeError,binascii.Error) as error:raise ValueError('Invalid bank reconciliation archive') from error
    return True


def restore_horizon(office):
    from business_schema import _tables
    if not set(TABLES)<=_tables(office):return None
    validate_integrity(office);snapshot={}
    for table in TABLES:
        rows=[]
        for record in office.db.execute('SELECT * FROM '+table):
            row=dict(record)
            if 'original' in row:row['original_sha256_verified']=_sha(bytes(row.pop('original')))
            rows.append(row)
        snapshot[table]=sorted(rows,key=canonical)
    return dict(schema_version=1,table_counts={table:len(rows) for table,rows in snapshot.items()},sha256=_sha(dict(schema_version=1,tables=snapshot)))


def methods(path):
    if path in ('/bank/accounts','/bank/statements','/bank/reconciliations'):return 'GET, POST'
    if path in ('/bank/import/preview','/bank/reconciliations/preview'):return 'POST'
    if re.fullmatch('/bank/statements/'+ID+'(?:/original)?',path):return 'GET'
    if re.fullmatch('/bank/transactions/'+ID+'/(?:candidates|history)',path):return 'GET'
    if re.fullmatch('/bank/transactions/'+ID+'/(?:preview|matches)',path):return 'POST'
    if re.fullmatch('/bank/reconciliations/'+ID+'(?:/(?:json|csv|pdf))?',path):return 'GET'
    return None


def dispatch(office,actor,path,method,data):
    allowed=methods(path)
    if allowed is None:return None
    if method not in allowed.split(', '):raise Problem(405,'HTTP-Methode nicht erlaubt.')
    api=BankReconciliation(office);parts=path.split('/');result=None
    if method=='GET':
        _shape(data,('_query',),());query=data.get('_query',{})
        if path in ('/bank/statements','/bank/reconciliations'):result=getattr(api,'statements' if path.endswith('statements') else 'reconciliations')(actor,query)
        elif path.endswith('/history'):result=api.history(actor,parts[3],query)
        else:
            _shape(query,())
            if path=='/bank/accounts':result=api.accounts(actor)
            elif path.startswith('/bank/statements/'):
                if path.endswith('/original'):
                    content,mime=api.original(actor,parts[3]);return content,200,mime
                result=api.statement(actor,parts[3])
            elif path.endswith('/candidates'):result=api.candidates(actor,parts[3])
            elif len(parts)==5:
                content,mime=api.export(actor,parts[3],parts[4]);return content,200,mime
            else:result=api.reconciliation(actor,parts[3])
    elif path=='/bank/accounts':result=api.save_account(actor,data)
    elif path=='/bank/import/preview':result=api.preview_import(actor,data)
    elif path=='/bank/statements':result=api.import_statement(actor,data)
    elif path=='/bank/reconciliations/preview':result=api.preview_reconciliation(actor,data)
    elif path=='/bank/reconciliations':result=api.save_reconciliation(actor,data)
    elif path.endswith('/preview'):result=api.preview_match(actor,parts[3],data)
    else:result=api.save_match(actor,parts[3],data)
    return result,200,'application/json'
