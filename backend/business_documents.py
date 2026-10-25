"""Commercial documents and exact decimal snapshots.

Own issuing is disabled until the company explicitly selects its issuer/cutover.
This technical archive does not replace the operator's reviewed GoBD procedure
or qualify a drawn signature as advanced/qualified under eIDAS.
Rendering is a separate, bounded step outside Office's transaction.
"""
from dataclasses import dataclass
from functools import wraps
from inquiries import _transaction
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP,ROUND_DOWN
import base64
import hashlib
import io
import json
import os
import re
import sqlite3
import threading
import uuid
from xml.sax.saxutils import escape

from core import Problem, canonical


KINDS=('estimate','offer','order_confirmation','delivery_note','invoice','advance_invoice','cumulative_invoice','final_invoice','credit_note')
INVOICES=('invoice','advance_invoice','cumulative_invoice','final_invoice','credit_note')
LABELS={'estimate':'Kostenvoranschlag','offer':'Angebot','order_confirmation':'Auftragsbestätigung','delivery_note':'Lieferschein',
        'invoice':'Rechnung','advance_invoice':'Abschlagsrechnung','cumulative_invoice':'Kumulierte Rechnung',
        'final_invoice':'Schlussrechnung','credit_note':'Stornogutschrift'}
PREFIXES={'estimate':'KV','offer':'AN','order_confirmation':'AB','delivery_note':'LS','invoice':'RE',
          'advance_invoice':'RE','cumulative_invoice':'RE','final_invoice':'RE','credit_note':'GS'}
MAX_PDF=10*1024*1024
_ID=re.compile(r'[a-f0-9]{32}\Z')
_DECIMAL=re.compile(r'-?(?:0|[1-9][0-9]{0,13})(?:\.[0-9]{1,4})?\Z')
_ISSUER_KEYS={'company_name','address_line','postal_code','city','country','vat_id','tax_number','email','phone',
              'iban','bic','website','footer','logo_base64','issuer_mode','issuing_enabled','cutover_date','cutover_ack',
              'einvoice_format','payment_terms','default_due_days'}


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA','BLOB'):raise ValueError('Invalid binary storage type')
    return [
        """CREATE TABLE IF NOT EXISTS business_commercial_settings(
          id TEXT PRIMARY KEY CHECK(id='main'),revision INTEGER NOT NULL CHECK(revision>0),
          payload_json TEXT NOT NULL,updated_by TEXT NOT NULL REFERENCES users(id),updated_at TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS business_articles(
          id TEXT PRIMARY KEY CHECK(length(id)=32),revision INTEGER NOT NULL CHECK(revision>0),
          payload_json TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),updated_by TEXT NOT NULL REFERENCES users(id),
          created_at TEXT NOT NULL,updated_at TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS business_article_versions(article_id TEXT NOT NULL REFERENCES business_articles(id),
          revision INTEGER NOT NULL,payload_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL,at TEXT NOT NULL,PRIMARY KEY(article_id,revision))""",
        """CREATE TABLE IF NOT EXISTS business_text_blocks(id TEXT PRIMARY KEY,revision INTEGER NOT NULL,payload_json TEXT NOT NULL,
          updated_by TEXT NOT NULL REFERENCES users(id),updated_at TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS business_templates(
          id TEXT PRIMARY KEY CHECK(length(id)=32),revision INTEGER NOT NULL CHECK(revision>0),
          payload_json TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),updated_by TEXT NOT NULL REFERENCES users(id),
          created_at TEXT NOT NULL,updated_at TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS business_documents(
          id TEXT PRIMARY KEY CHECK(length(id)=32),project_id TEXT NOT NULL REFERENCES projects(id),
          customer_id TEXT REFERENCES customers(id),kind TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('draft','final')),
          revision INTEGER NOT NULL CHECK(revision>0),payload_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL,
          number TEXT UNIQUE,created_by TEXT NOT NULL REFERENCES users(id),updated_by TEXT NOT NULL REFERENCES users(id),
          created_at TEXT NOT NULL,updated_at TEXT NOT NULL,finalized_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS business_document_versions(
          document_id TEXT NOT NULL REFERENCES business_documents(id),revision INTEGER NOT NULL,
          payload_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL,at TEXT NOT NULL,PRIMARY KEY(document_id,revision))""",
        """CREATE TABLE IF NOT EXISTS business_document_relations(
          target_id TEXT NOT NULL REFERENCES business_documents(id),source_id TEXT NOT NULL REFERENCES business_documents(id),
          kind TEXT NOT NULL CHECK(kind IN ('converted_from','deducts','cancels')),source_sha256 TEXT NOT NULL,
          PRIMARY KEY(target_id,source_id,kind))""",
        """CREATE TABLE IF NOT EXISTS business_document_time_billing(document_id TEXT NOT NULL REFERENCES business_documents(id),
          entry_id TEXT NOT NULL,source_hash TEXT NOT NULL,source_revision INTEGER NOT NULL,seconds INTEGER NOT NULL,
          PRIMARY KEY(document_id,entry_id))""",
        """CREATE TABLE IF NOT EXISTS business_document_counters(
          company_id TEXT NOT NULL,series TEXT NOT NULL,year INTEGER NOT NULL,next_value INTEGER NOT NULL CHECK(next_value>0),
          PRIMARY KEY(company_id,series,year))""",
        """CREATE TABLE IF NOT EXISTS business_document_numbers(
          document_id TEXT PRIMARY KEY REFERENCES business_documents(id),company_id TEXT NOT NULL,series TEXT NOT NULL,
          year INTEGER NOT NULL,value INTEGER NOT NULL CHECK(value>0),number TEXT NOT NULL UNIQUE,
          issued_at TEXT NOT NULL,UNIQUE(company_id,series,year,value))""",
        f"""CREATE TABLE IF NOT EXISTS business_document_archives(
          document_id TEXT PRIMARY KEY REFERENCES business_documents(id),payload_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL,
          pdf {binary_type} NOT NULL,pdf_sha256 TEXT NOT NULL,xml {binary_type},xml_sha256 TEXT,
          validation_json TEXT NOT NULL,archived_at TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS business_document_signatures(
          id TEXT PRIMARY KEY,document_id TEXT NOT NULL REFERENCES business_documents(id),payload_sha256 TEXT NOT NULL,
          actor_id TEXT NOT NULL REFERENCES users(id),payload_json TEXT NOT NULL,at TEXT NOT NULL)""",
        f"""CREATE TABLE IF NOT EXISTS business_signed_documents(signature_id TEXT PRIMARY KEY REFERENCES business_document_signatures(id),
          document_id TEXT NOT NULL REFERENCES business_documents(id),pdf {binary_type} NOT NULL,pdf_sha256 TEXT NOT NULL,
          original_pdf_sha256 TEXT NOT NULL,at TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS business_document_requests(
          user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,operation TEXT NOT NULL,
          project_id TEXT REFERENCES projects(id),request_hash TEXT NOT NULL,result_json TEXT NOT NULL,at TEXT NOT NULL,
          PRIMARY KEY(user_id,request_id))""",
        """CREATE TABLE IF NOT EXISTS business_document_outbox(id TEXT PRIMARY KEY,document_id TEXT NOT NULL REFERENCES business_documents(id),
          operation_id TEXT NOT NULL UNIQUE,payload_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS business_document_mail_receipts(id TEXT PRIMARY KEY,outbox_id TEXT NOT NULL REFERENCES business_document_outbox(id),
          operation_id TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('sending','accepted','failed','unknown','not_sent')),
          ordinal INTEGER NOT NULL,receipt_id TEXT,error_code TEXT,at TEXT NOT NULL,UNIQUE(outbox_id,ordinal))""",
        'CREATE INDEX IF NOT EXISTS business_documents_project ON business_documents(project_id,created_at)',
        'CREATE INDEX IF NOT EXISTS business_documents_kind ON business_documents(kind,status,created_at)',
    ]


_APPEND_ONLY=('business_article_versions','business_document_versions','business_document_relations','business_document_numbers',
              'business_document_archives','business_document_signatures','business_document_requests')
_APPEND_ONLY+=('business_document_outbox','business_document_mail_receipts','business_signed_documents','business_document_time_billing')


def guard_statements(dialect):
    if dialect=='sqlite':
        output=[]
        for table in _APPEND_ONLY:
            for action in ('UPDATE','DELETE'):
                output.append(f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable commercial archive'); END")
        for action in ('UPDATE','DELETE'):
            output.append(f"CREATE TRIGGER IF NOT EXISTS business_documents_{action.lower()}_guard BEFORE {action} ON business_documents WHEN OLD.status='final' BEGIN SELECT RAISE(ABORT,'immutable final document'); END")
        output.extend([
            "CREATE TRIGGER IF NOT EXISTS business_document_counters_update_guard BEFORE UPDATE ON business_document_counters WHEN NEW.company_id<>OLD.company_id OR NEW.series<>OLD.series OR NEW.year<>OLD.year OR NEW.next_value<>OLD.next_value+1 BEGIN SELECT RAISE(ABORT,'number counter must advance exactly one'); END",
            "CREATE TRIGGER IF NOT EXISTS business_document_counters_delete_guard BEFORE DELETE ON business_document_counters BEGIN SELECT RAISE(ABORT,'immutable number counter'); END",
            "CREATE TRIGGER IF NOT EXISTS business_document_counters_insert_guard BEFORE INSERT ON business_document_counters WHEN NEW.next_value<>1 BEGIN SELECT RAISE(ABORT,'number counter must start at one'); END"])
        return output
    if dialect=='postgresql':
        output=["""CREATE OR REPLACE FUNCTION business_document_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'immutable commercial archive'; END; $$""",
            """CREATE OR REPLACE FUNCTION business_document_final_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN IF OLD.status='final' THEN RAISE EXCEPTION 'immutable final document'; END IF;
IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW; END; $$"""]
        output.append("""CREATE OR REPLACE FUNCTION business_document_counter_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN IF TG_OP='DELETE' THEN RAISE EXCEPTION 'immutable number counter'; END IF;
IF TG_OP='INSERT' THEN IF NEW.next_value<>1 THEN RAISE EXCEPTION 'number counter must start at one'; END IF; RETURN NEW; END IF;
IF NEW.company_id<>OLD.company_id OR NEW.series<>OLD.series OR NEW.year<>OLD.year OR NEW.next_value<>OLD.next_value+1 THEN RAISE EXCEPTION 'number counter must advance exactly one'; END IF; RETURN NEW; END; $$""")
        for table in (*_APPEND_ONLY,'business_documents'):
            function='business_document_final_guard' if table=='business_documents' else 'business_document_immutable_guard'
            for action in ('UPDATE','DELETE'):
                name=table+'_'+action.lower()+'_guard'
                output.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION {function}(); END IF; END $$")
        for action in ('UPDATE','DELETE','INSERT'):
            name='business_document_counters_'+action.lower()+'_guard'
            output.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='business_document_counters'::regclass) THEN CREATE TRIGGER {name} BEFORE {action} ON business_document_counters FOR EACH ROW EXECUTE FUNCTION business_document_counter_guard(); END IF; END $$")
        return output
    raise ValueError('Unsupported guard dialect')


def _hash(value):
    return hashlib.sha256(value if isinstance(value,bytes) else value.encode('utf-8')).hexdigest()


def _id(value):
    if not isinstance(value,str) or not _ID.fullmatch(value):raise Problem(400,'Ungültige Vorgangskennung')
    return value


def _text(value,name,maximum=2000,*,empty=False):
    if not isinstance(value,str) or len(value)>maximum or any((ord(c)<32 and c not in '\n\r\t') or ord(c)==127 for c in value) or (not empty and not value.strip()):
        raise Problem(400,'Ungültiges Feld: '+name)
    return value.replace('\r\n','\n').replace('\r','\n').strip()


def _date(value):
    try:
        if not isinstance(value,str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',value):raise ValueError()
        return date.fromisoformat(value).isoformat()
    except ValueError:raise Problem(400,'Datum im Format YYYY-MM-DD erwartet') from None


def decimal_value(value,*,negative=False,maximum=Decimal('9999999999999')):
    if not isinstance(value,str) or not _DECIMAL.fullmatch(value):raise Problem(400,'Begrenzte Dezimalzeichenfolge erwartet')
    result=Decimal(value)
    if not result.is_finite() or abs(result)>maximum or (not negative and result<0):raise Problem(400,'Ungültiger Dezimalbetrag')
    return result


def money(value):
    return format(value.quantize(Decimal('.01'),rounding=ROUND_HALF_UP),'f')


def require(office,actor,permission,project_id=None):
    from business_foundation import require_permission
    if permission.startswith('finance.') and permission!='finance.read':require_permission(office,actor,'finance.read',project_id=project_id)
    return require_permission(office,actor,permission,project_id=project_id)


def financial_release(office):
    from business_schema import require_financial_release
    require_financial_release(office)


def calculate_positions(values,*,credit=False):
    if not isinstance(values,list) or not 1<=len(values)<=500:raise Problem(400,'1 bis 500 Positionen erwartet')
    positions=[];buckets={};bucket_kinds={};categories={key:Decimal(0) for key in ('labor','material','service','machine')};kind_tax={key:Decimal(0) for key in categories}
    for index,value in enumerate(values):
        if not isinstance(value,dict):raise Problem(400,'Gültige Position erwartet')
        quantity=decimal_value(value.get('quantity'))
        if quantity<=0:raise Problem(400,'Positionsmenge muss positiv sein')
        price=decimal_value(value.get('unit_price_net'))
        base_quantity=decimal_value(value.get('price_base_quantity','1'),maximum=Decimal('1000000'))
        if base_quantity<=0:raise Problem(400,'Preisbasis muss positiv sein')
        rate=decimal_value(value.get('tax_rate'),maximum=Decimal(100))
        rate=rate.normalize() if rate else Decimal(0)
        discount=decimal_value(value.get('discount_percent','0'),maximum=Decimal(100))
        kind=value.get('kind','service')
        if kind not in categories:raise Problem(400,'Positionsart Material/Lohn/Leistung/Maschine erwartet')
        category=value.get('tax_category','S' if rate else 'Z')
        if category not in ('S','Z','E','AE') or ((category=='S')!=(rate>0)):
            raise Problem(400,'Steuerkategorie und Steuersatz passen nicht zusammen')
        reason=_text(value.get('tax_exemption_reason',''),'Steuerbefreiungsgrund',1000,empty=True)
        if category in ('E','AE') and not reason:raise Problem(400,'Steuerbefreiung benötigt einen Grund')
        if quantity*price/base_quantity>Decimal('9999999999.99'):raise Problem(400,'Positionsbetrag überschreitet das zulässige Limit')
        net=(quantity*price/base_quantity*(Decimal(100)-discount)/100).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        key=(format(rate,'f'),category,reason)
        if any(k[:2]==key[:2] and k[2]!=reason for k in buckets):raise Problem(400,'Pro Steuergruppe muss der Befreiungsgrund übereinstimmen')
        buckets[key]=buckets.get(key,Decimal(0))+net
        kinds=bucket_kinds.setdefault(key,{k:Decimal(0) for k in categories});kinds[kind]+=net
        categories[kind]+=net
        position=dict(id=_id(value['id']) if value.get('id') else uuid.uuid4().hex,index=index+1,description=_text(value.get('description'),'Beschreibung',10000),
            quantity=format(quantity,'f'),unit=_text(value.get('unit'),'Einheit',20),unit_price_net=format(price,'f'),
            price_base_quantity=format(base_quantity,'f'),
            tax_rate=format(rate,'f'),tax_category=category,tax_exemption_reason=reason,kind=kind,
            discount_percent=format(discount,'f'),net=money(net))
        for field in ('article_id','article_revision','cost_price_net','code','source_type','source_id','source_revision','source_hash','source_seconds','components'):
            if field in value:position[field]=value[field]
        if 'article_id' in position:_id(position['article_id'])
        if 'cost_price_net' in position:decimal_value(position['cost_price_net'])
        positions.append(position)
    breakdown=[];tax=Decimal(0);net=Decimal(0)
    for (rate,category,reason),amount in sorted(buckets.items()):
        charge=(amount*Decimal(rate)/100).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        breakdown.append(dict(rate=rate,category=category,reason=reason,net=money(amount),tax=money(charge)))
        exact={k:n*Decimal(rate)/100 for k,n in bucket_kinds[(rate,category,reason)].items()}
        allocation={k:v.quantize(Decimal('.01'),rounding=ROUND_DOWN) for k,v in exact.items()}
        remaining=int((charge-sum(allocation.values(),Decimal(0)))*100)
        for k in sorted(exact,key=lambda k:(-(exact[k]-allocation[k]),k))[:remaining]:allocation[k]+=Decimal('.01')
        for k,v in allocation.items():kind_tax[k]+=v
        net+=amount;tax+=charge
    gross=net+tax
    by_kind={k:{'net':money(categories[k]),'tax':money(kind_tax[k]),'gross':money(categories[k]+kind_tax[k])} for k in categories}
    return dict(positions=positions,totals=dict(net=money(net),tax=money(tax),gross=money(gross),payable=money(gross),
        labor_net=by_kind['labor']['net'],labor_tax=by_kind['labor']['tax'],labor_gross=by_kind['labor']['gross'],
        material_net=by_kind['material']['net'],material_tax=by_kind['material']['tax'],material_gross=by_kind['material']['gross'],
        by_kind=by_kind,tax_breakdown=breakdown))


def _buyer(value):
    fields=('name','address_line','postal_code','city','country','email','endpoint_id','endpoint_scheme','vat_id')
    if not isinstance(value,dict) or set(value)-set(fields):raise Problem(400,'Empfängerdaten erwartet')
    result={key:_text(value.get(key,''),key,2000,empty=key!='name') for key in fields}
    result['country']=result['country'] or 'DE'
    if not re.fullmatch(r'[A-Z]{2}',result['country']):raise Problem(400,'ISO-Ländercode erwartet')
    return result


def default_settings():
    return dict(company_name='',address_line='',postal_code='',city='',country='DE',vat_id='',tax_number='',email='',phone='',
        iban='',bic='',website='',footer='',logo_base64='',issuer_mode='sevdesk',issuing_enabled=False,cutover_ack=False,
        cutover_date='',einvoice_format='none',payment_terms='Zahlbar ohne Abzug.',default_due_days=14)


def _settings(value):
    if not isinstance(value,dict) or set(value)-_ISSUER_KEYS:raise Problem(400,'Ungültige Ausstellerkonfiguration')
    result={**default_settings(),**value}
    for key in _ISSUER_KEYS-{'issuing_enabled','cutover_ack','default_due_days'}:
        result[key]=_text(result[key],key,400000 if key=='logo_base64' else 4000,empty=True)
    if result['issuer_mode'] not in ('sevdesk','own') or result['einvoice_format'] not in ('none','xrechnung','zugferd'):
        raise Problem(400,'Aussteller own/sevdesk und Profil none/xrechnung/zugferd erwartet')
    if type(result['issuing_enabled']) is not bool or type(result['cutover_ack']) is not bool:raise Problem(400,'Ausdrückliche Ausstellerentscheidung erwartet')
    if type(result['default_due_days']) is not int or not 0<=result['default_due_days']<=365:raise Problem(400,'Ungültiges Zahlungsziel')
    if result['cutover_date']:_date(result['cutover_date'])
    if result['country'] and not re.fullmatch('[A-Z]{2}',result['country']):raise Problem(400,'ISO-Ländercode des Ausstellers erwartet')
    if result['iban']:
        iban=result['iban'].replace(' ','').upper()
        if not re.fullmatch(r'[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}',iban):raise Problem(400,'Gültige IBAN erwartet')
        expanded=''.join(str(ord(c)-55) if c.isalpha() else c for c in iban[4:]+iban[:4])
        if int(expanded)%97!=1:raise Problem(400,'IBAN-Prüfziffer stimmt nicht')
        result['iban']=iban
    if result['bic']:
        result['bic']=result['bic'].replace(' ','').upper()
        if not re.fullmatch(r'[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?',result['bic']):raise Problem(400,'Gültigen BIC angeben')
    if result['issuing_enabled'] and (result['issuer_mode']!='own' or not result['cutover_ack'] or not result['cutover_date']):
        raise Problem(409,'Eigene Ausstellung benötigt bestätigten ausschließlichen Aussteller und Umstiegsdatum')
    if result['logo_base64']:
        try:
            from PIL import Image
            logo=base64.b64decode(result['logo_base64'],validate=True)
            if len(logo)>256*1024:raise ValueError()
            with Image.open(io.BytesIO(logo)) as image:
                if image.format not in ('PNG','JPEG') or not 0<image.width*image.height<=4000000:raise ValueError()
                image.verify()
        except Exception:raise Problem(400,'Begrenztes PNG/JPEG-Firmenlogo erwartet') from None
    return result


class Documents:
    def __init__(self,office,*,clock=None):
        self.office,self.db=office,office.db
        self.clock=clock or (lambda:datetime.now(timezone.utc))

    def _now(self):return self.clock().astimezone(timezone.utc).isoformat(timespec='seconds')

    def _issuer_security(self,kind):
        from business_schema import require_runtime_security
        proof=require_runtime_security(self.office)
        if kind in INVOICES and proof is not True:raise Problem(409,'Rechnungen ausschließlich über den geschützten Online-PostgreSQL-Dienst ausstellen')
        return 'postgresql_runtime_separated' if proof else 'sqlite_local_trigger_only'

    def _replay(self,actor,request,operation,payload,project=None):
        _id(request)
        fingerprint=_hash(canonical(dict(operation=operation,payload=payload,project_id=project)))
        row=self.db.execute('SELECT * FROM business_document_requests WHERE user_id=? AND request_id=?',(actor['id'],request)).fetchone()
        if row:
            if row['operation']!=operation or row['project_id']!=project or row['request_hash']!=fingerprint:
                raise Problem(409,'Diese Vorgangs-ID wurde bereits für andere Daten verwendet')
            return json.loads(row['result_json']),fingerprint
        return None,fingerprint

    def _remember(self,actor,request,operation,fingerprint,result,project=None):
        self.db.execute('INSERT INTO business_document_requests(user_id,request_id,operation,project_id,request_hash,result_json,at) VALUES(?,?,?,?,?,?,?)',
            (actor['id'],request,operation,project,fingerprint,canonical(result),self._now()))
        return result

    def settings(self,actor):
        require(self.office,actor,'settings.manage')
        row=self.db.execute("SELECT * FROM business_commercial_settings WHERE id='main'").fetchone()
        return dict(id='main',revision=row['revision'] if row else 0,updated_at=row['updated_at'] if row else None,
                    **(json.loads(row['payload_json']) if row else default_settings()))

    def _settings_row(self):
        row=self.db.execute("SELECT * FROM business_commercial_settings WHERE id='main'").fetchone()
        return (json.loads(row['payload_json']),row['revision']) if row else (default_settings(),0)

    def save_settings(self,actor,data):
        actor=require(self.office,actor,'settings.manage')
        if not isinstance(data,dict):raise Problem(400,'Ausstellereinstellungen erwartet')
        if isinstance(self.db,sqlite3.Connection) and data.get('issuing_enabled') is True:raise Problem(409,'Eigene Rechnungsstellung benötigt den geschützten Online-PostgreSQL-Dienst')
        request=data.get('request_id');values={k:v for k,v in data.items() if k not in ('request_id','revision')}
        replay,fingerprint=self._replay(actor,request,'settings',data)
        if replay:return replay
        old,revision=self._settings_row()
        if data.get('revision')!=revision:raise Problem(409,'Ausstellereinstellungen wurden geändert')
        value=_settings({**old,**values})
        if isinstance(self.db,sqlite3.Connection) and value['issuing_enabled']:raise Problem(409,'Lokale SQLite-Daten dürfen die Rechnungsstellung nicht aktivieren')
        self.db.execute("INSERT INTO business_commercial_settings(id,revision,payload_json,updated_by,updated_at) VALUES('main',?,?,?,?) "
            'ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,payload_json=excluded.payload_json,updated_by=excluded.updated_by,updated_at=excluded.updated_at',
            (revision+1,canonical(value),actor['id'],self._now()))
        return self._remember(actor,request,'settings',fingerprint,self.settings(actor))

    def articles(self,actor,query='',*,services=False):
        require(self.office,actor,'finance.read')
        if not isinstance(query,str) or len(query)>200:raise Problem(400,'Ungültige Suche')
        result=[]
        for row in self.db.execute('SELECT * FROM business_articles ORDER BY created_at,id').fetchall():
            item=dict(id=row['id'],revision=row['revision'],updated_at=row['updated_at'],**json.loads(row['payload_json']))
            if (not services or item['kind'] in ('labor','service')) and (not query or query.casefold() in (item['name']+' '+item['code']).casefold()):result.append(item)
        return {'items':result}

    def save_article(self,actor,data,article_id=None):
        actor=require(self.office,actor,'finance.write')
        if not isinstance(data,dict):raise Problem(400,'Artikel erwartet')
        request=data.get('request_id');payload={k:v for k,v in data.items() if k not in ('request_id','revision')}
        allowed={'code','name','kind','unit','unit_price_net','cost_price_net','tax_rate','tax_category','tax_exemption_reason','currency','active','components'}
        if set(payload)-allowed:raise Problem(400,'Ungültige Artikelfelder')
        old=None
        if article_id:
            _id(article_id);old=self.db.execute('SELECT * FROM business_articles WHERE id=?',(article_id,)).fetchone()
            if not old:raise Problem(404,'Artikel nicht verfügbar')
        operation='article:'+str(article_id)
        replay,fingerprint=self._replay(actor,request,operation,data)
        if replay:return replay
        if old and data.get('revision')!=old['revision']:raise Problem(409,'Artikel wurde geändert')
        value={**(json.loads(old['payload_json']) if old else {'code':'','currency':'EUR','active':True,'cost_price_net':'0','tax_rate':'19'}),**payload}
        if value.get('currency')!='EUR' or type(value.get('active')) is not bool:raise Problem(400,'EUR und ausdrücklicher Aktivstatus erwartet')
        for field in ('name','unit'):value[field]=_text(value.get(field),field,500)
        value['code']=_text(value.get('code',''),'Artikelnummer',100,empty=True)
        if value.get('kind') not in ('material','labor','service','machine'):raise Problem(400,'Artikelart erwartet')
        for field in ('unit_price_net','cost_price_net','tax_rate'):decimal_value(value.get(field))
        value.setdefault('tax_category','S' if Decimal(value['tax_rate']) else 'Z')
        value.setdefault('tax_exemption_reason','')
        components=value.get('components',[])
        if not isinstance(components,list) or len(components)>100 or components and value['kind'] not in ('service','labor'):raise Problem(400,'Stückliste nur für eine Leistung erwartet')
        snapshots=[]
        for component in components:
            if not isinstance(component,dict):raise Problem(400,'Stücklistenposition erwartet')
            component_id=_id(component.get('article_id'))
            if component_id==article_id:raise Problem(400,'Leistung darf sich nicht selbst enthalten')
            source=self.db.execute('SELECT * FROM business_articles WHERE id=?',(component_id,)).fetchone()
            if not source:raise Problem(404,'Stücklistenartikel nicht verfügbar')
            article=json.loads(source['payload_json'])
            if component.get('article_revision')!=source['revision'] or not article['active']:raise Problem(409,'Stücklistenartikel wurde geändert')
            quantity=decimal_value(component.get('quantity'))
            if quantity<=0 or quantity>100000:raise Problem(400,'Begrenzte positive Stücklistenmenge erwartet')
            snapshots.append(dict(article_id=component_id,article_revision=source['revision'],quantity=str(quantity),unit=article['unit'],name=article['name'],
                kind=article['kind'],cost_price_net=article['cost_price_net'],cost_net=money(quantity*Decimal(article['cost_price_net']))))
        value['components']=snapshots
        calculate_positions([{**value,'description':value['name'],'quantity':'1'}])
        identifier=article_id or uuid.uuid4().hex;revision=old['revision']+1 if old else 1;now=self._now()
        self.db.execute('INSERT INTO business_articles(id,revision,payload_json,created_by,updated_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?) '
            'ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,payload_json=excluded.payload_json,updated_by=excluded.updated_by,updated_at=excluded.updated_at',
            (identifier,revision,canonical(value),old['created_by'] if old else actor['id'],actor['id'],old['created_at'] if old else now,now))
        self.db.execute('INSERT INTO business_article_versions(article_id,revision,payload_json,payload_sha256,at) VALUES(?,?,?,?,?)',
            (identifier,revision,canonical(value),_hash(canonical(value)),now))
        return self._remember(actor,request,operation,fingerprint,dict(id=identifier,revision=revision,updated_at=now,**value))

    def text_blocks(self,actor):
        require(self.office,actor,'finance.read')
        return {'items':[dict(id=r['id'],revision=r['revision'],updated_at=r['updated_at'],**json.loads(r['payload_json'])) for r in self.db.execute('SELECT * FROM business_text_blocks ORDER BY id').fetchall()]}

    def save_text_block(self,actor,data,identifier=None):
        actor=require(self.office,actor,'settings.manage');replay,fingerprint=self._replay(actor,data.get('request_id'),'text-block:'+str(identifier),data)
        if replay:return replay
        old=self.db.execute('SELECT * FROM business_text_blocks WHERE id=?',(_id(identifier),)).fetchone() if identifier else None
        if identifier and not old:raise Problem(404,'Textbaustein nicht verfügbar')
        if old and data.get('revision')!=old['revision']:raise Problem(409,'Textbaustein wurde geändert')
        if set(data)-{'request_id','revision','name','text'}:raise Problem(400,'Textbausteinfelder erwartet')
        value={'name':_text(data.get('name'),'Bausteinname',200),'text':_text(data.get('text'),'Text',10000)}
        identifier_=identifier or uuid.uuid4().hex;revision=old['revision']+1 if old else 1;now=self._now()
        self.db.execute('INSERT INTO business_text_blocks(id,revision,payload_json,updated_by,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,payload_json=excluded.payload_json,updated_by=excluded.updated_by,updated_at=excluded.updated_at',
            (identifier_,revision,canonical(value),actor['id'],now))
        return self._remember(actor,data['request_id'],'text-block:'+str(identifier),fingerprint,dict(id=identifier_,revision=revision,updated_at=now,**value))

    def templates(self,actor):
        require(self.office,actor,'finance.read')
        return {'items':[dict(id=r['id'],revision=r['revision'],updated_at=r['updated_at'],**json.loads(r['payload_json']))
                         for r in self.db.execute('SELECT * FROM business_templates ORDER BY created_at,id').fetchall()]}

    def save_template(self,actor,data,template_id=None):
        actor=require(self.office,actor,'settings.manage')
        if not isinstance(data,dict):raise Problem(400,'Vorlage erwartet')
        replay,fingerprint=self._replay(actor,data.get('request_id'),'template:'+str(template_id),data)
        if replay:return replay
        old=self.db.execute('SELECT * FROM business_templates WHERE id=?',(_id(template_id),)).fetchone() if template_id else None
        if template_id and not old:raise Problem(404,'Vorlage nicht verfügbar')
        if old and data.get('revision')!=old['revision']:raise Problem(409,'Vorlage wurde geändert')
        values={**(json.loads(old['payload_json']) if old else {}),**{k:v for k,v in data.items() if k not in ('request_id','revision')}}
        if set(values)-{'name','kind','title','intro','notes','positions'}:raise Problem(400,'Ungültige Vorlagenfelder')
        if values.get('kind') not in KINDS:raise Problem(400,'Belegart erwartet')
        for field in ('name','title','intro','notes'):values[field]=_text(values.get(field,''),field,10000,empty=field in ('intro','notes'))
        values['positions']=calculate_positions(values.get('positions'))['positions']
        identifier=template_id or uuid.uuid4().hex;revision=old['revision']+1 if old else 1;now=self._now()
        self.db.execute('INSERT INTO business_templates(id,revision,payload_json,created_by,updated_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?) '
            'ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,payload_json=excluded.payload_json,updated_by=excluded.updated_by,updated_at=excluded.updated_at',
            (identifier,revision,canonical(values),old['created_by'] if old else actor['id'],actor['id'],old['created_at'] if old else now,now))
        return self._remember(actor,data['request_id'],'template:'+str(template_id),fingerprint,dict(id=identifier,revision=revision,updated_at=now,**values))

    def _row(self,actor,identifier,permission='finance.read'):
        _id(identifier)
        row=self.db.execute('SELECT * FROM business_documents WHERE id=?',(identifier,)).fetchone()
        if not row:raise Problem(404,'Beleg nicht verfügbar')
        require(self.office,actor,permission,row['project_id'])
        return row

    def _record(self,row):
        return dict(json.loads(row['payload_json']),id=row['id'],project_id=row['project_id'],customer_id=row['customer_id'],
            kind=row['kind'],status=row['status'],revision=row['revision'],number=row['number'],updated_at=row['updated_at'],
            finalized_at=row['finalized_at'],payload_sha256=row['payload_sha256'])

    def get(self,actor,identifier):return self._record(self._row(actor,identifier))

    def list(self,actor,project_id=None,kind=None,query=''):
        require(self.office,actor,'finance.read',project_id)
        query=_text(query,'Suche',200,empty=True).casefold()
        if kind is not None and kind not in KINDS:raise Problem(400,'Belegart erwartet')
        result=[]
        for row in self.db.execute('SELECT * FROM business_documents ORDER BY created_at DESC,id').fetchall():
            if project_id and row['project_id']!=project_id or kind and row['kind']!=kind:continue
            try:require(self.office,actor,'finance.read',row['project_id'])
            except Problem as error:
                if error.status in (403,404):continue
                raise
            item=self._record(row)
            if query and query not in ' '.join([item.get('title',''),item.get('number') or '',item['buyer']['name']]).casefold():continue
            result.append(item)
        return {'items':result}

    def _positions(self,values):
        if not isinstance(values,list):raise Problem(400,'Positionen erwartet')
        result=[]
        for value in values:
            if not isinstance(value,dict):raise Problem(400,'Position erwartet')
            if value.get('article_id') and not value.get('id'):
                row=self.db.execute('SELECT * FROM business_articles WHERE id=?',(_id(value['article_id']),)).fetchone()
                if not row:raise Problem(404,'Artikel nicht verfügbar')
                article=json.loads(row['payload_json'])
                if not article['active'] or value.get('article_revision')!=row['revision']:raise Problem(409,'Artikel wurde geändert oder deaktiviert')
                value={**article,'description':article['name'],**value,'article_revision':row['revision']}
            result.append(value)
        return calculate_positions(result)

    def time_sources(self,actor,project_id):
        require(self.office,actor,'finance.read',project_id)
        from business_time import TimeTracking
        time=TimeTracking(self.office)
        entries=time.approved_work(actor,project_id)['items'];identifiers=list(dict.fromkeys(e['entry_id'] for e in entries))
        items=[]
        # Diary may expose approved segments of an overnight entry. Invoice
        # candidates require the whole entry, but one pending day must not hide
        # unrelated fully approved work.
        for identifier in identifiers:
            try:items.extend(time.approved_billable(actor,project_id,[identifier])['items'])
            except Problem as error:
                if error.status==409:continue
                raise
        available=[]
        for item in items:
            if not self.db.execute("SELECT 1 FROM business_document_time_billing b JOIN business_documents d ON d.id=b.document_id WHERE b.entry_id=? AND d.status='final' AND NOT EXISTS(SELECT 1 FROM business_document_relations r JOIN business_documents c ON c.id=r.target_id WHERE r.source_id=d.id AND r.kind='cancels' AND c.status='final')",(item['entry_id'],)).fetchone():available.append(item)
        return {'items':available}

    def _time_values(self,actor,project_id,data,old=None):
        if 'time_entry_ids' not in data:return data
        identifiers=data['time_entry_ids']
        if not isinstance(identifiers,list) or not 1<=len(identifiers)<=100 or len(set(identifiers))!=len(identifiers):raise Problem(400,'1 bis100 eindeutige freigegebene Zeiteinträge auswählen')
        for identifier in identifiers:_id(identifier)
        from business_time import TimeTracking
        items=TimeTracking(self.office).approved_billable(actor,project_id,identifiers)['items']
        rate=decimal_value(data.get('hourly_rate_net'));tax=decimal_value(data.get('time_tax_rate','19'),maximum=Decimal(100))
        result={k:v for k,v in data.items() if k not in ('time_entry_ids','hourly_rate_net','time_tax_rate','time_description')}
        positions=list(data.get('positions',old.get('positions',[]) if old else []))
        for item in items:
            positions.append({'description':_text(data.get('time_description',item['label']),'Zeitbeschreibung',1000)+' · '+item['date'],
                'quantity':str(item['net_seconds']),'unit':'SEC','unit_price_net':str(rate),'price_base_quantity':'3600',
                'tax_rate':str(tax),'kind':'labor','source_type':'time','source_id':item['entry_id'],'source_revision':item['revision'],
                'source_hash':item['source_hash'],'source_seconds':item['net_seconds']})
        result['positions']=positions
        return result

    def _time_snapshot(self,actor,row,payload):
        positions=[p for p in payload['positions'] if p.get('source_type')=='time']
        if not positions or row['kind']=='credit_note':return []
        identifiers=[_id(p.get('source_id')) for p in positions]
        if len(set(identifiers))!=len(identifiers):raise Problem(409,'Zeiteintrag darf nur einmal in einem Beleg vorkommen')
        ancestors=set();pending=list(payload.get('previous_document_ids',[]))
        while pending:
            identifier=pending.pop()
            if identifier in ancestors:continue
            ancestors.add(identifier)
            if len(ancestors)>1000:raise Problem(409,'Rechnungskette überschreitet das Limit')
            pending.extend(r['source_id'] for r in self.db.execute("SELECT source_id FROM business_document_relations WHERE target_id=? AND kind='deducts'",(identifier,)).fetchall())
        fresh_positions=[];new=[]
        for position in positions:
            existing=self.db.execute("SELECT b.* FROM business_document_time_billing b JOIN business_documents d ON d.id=b.document_id WHERE b.entry_id=? AND d.status='final' AND NOT EXISTS(SELECT 1 FROM business_document_relations r JOIN business_documents c ON c.id=r.target_id WHERE r.source_id=d.id AND r.kind='cancels' AND c.status='final')",(position['source_id'],)).fetchall()
            if existing:
                if any(b['document_id'] not in ancestors or b['source_hash']!=position.get('source_hash') for b in existing):raise Problem(409,'Zeiteintrag wurde bereits in einer anderen Rechnung berechnet')
                continue
            fresh_positions.append(position)
        if fresh_positions:
            from business_time import TimeTracking
            values=TimeTracking(self.office).approved_billable(actor,row['project_id'],[p['source_id'] for p in fresh_positions])['items']
            by_id={v['entry_id']:v for v in values}
            for p in fresh_positions:
                item=by_id.get(p['source_id'])
                if (not item or item['source_hash']!=p.get('source_hash') or item['revision']!=p.get('source_revision') or item['net_seconds']!=p.get('source_seconds')
                        or Decimal(p['quantity'])!=item['net_seconds'] or p['unit']!='SEC' or Decimal(p['price_base_quantity'])!=3600 or p['kind']!='labor'):
                    raise Problem(409,'Freigegebene Projektzeit wurde geändert; Position erneut übernehmen')
                new.append({'entry_id':item['entry_id'],'source_hash':item['source_hash'],'source_revision':item['revision'],'seconds':item['net_seconds']})
        return new

    def _payload(self,data,old=None):
        allowed={'project_id','kind','title','issue_date','due_date','buyer_reference','notes','intro','buyer','positions',
                 'previous_document_ids','template_id','template_revision','currency','converted_from','cancels','cancel_reason'}
        values={k:v for k,v in data.items() if k not in ('request_id','revision')}
        if set(values)-allowed:raise Problem(400,'Ungültige Belegfelder')
        if values.get('template_id') and (not old or (values['template_id'],values.get('template_revision'))!=(old.get('template_id'),old.get('template_revision'))):
            template=self.db.execute('SELECT revision,payload_json FROM business_templates WHERE id=?',(_id(values['template_id']),)).fetchone()
            if not template:raise Problem(404,'Vorlage nicht verfügbar')
            if type(values.get('template_revision')) is not int or values['template_revision']!=template['revision']:raise Problem(409,'Vorlage wurde geändert; aktuelle Fassung erneut auswählen')
            source=json.loads(template['payload_json'])
            values={**{k:v for k,v in source.items() if k!='name'},**values,
                'template_source':{'id':values['template_id'],'revision':template['revision'],'sha256':_hash(template['payload_json']),'snapshot':source}}
        value={**(old or {}),**values}
        if value.get('kind') not in KINDS or value.get('currency','EUR')!='EUR':raise Problem(400,'EUR-Belegart erwartet')
        value['currency']='EUR';value['title']=_text(value.get('title',LABELS[value['kind']]),'Titel',500)
        value['issue_date']=_date(value.get('issue_date'))
        value['due_date']=_date(value.get('due_date',value['issue_date']))
        if value['due_date']<value['issue_date']:raise Problem(400,'Fälligkeit liegt vor dem Belegdatum')
        for key in ('buyer_reference','notes','intro'):value[key]=_text(value.get(key,''),key,10000,empty=True)
        value['buyer']=_buyer(value.get('buyer'))
        prior=value.get('previous_document_ids',[])
        if not isinstance(prior,list) or len(prior)>100 or len(set(prior))!=len(prior):raise Problem(400,'Eindeutige Vorbelege erwartet')
        value['previous_document_ids']=[_id(identifier) for identifier in prior]
        if prior and value['kind'] not in ('cumulative_invoice','final_invoice'):raise Problem(400,'Vorbelege nur für kumulierte oder Schlussrechnungen')
        value.update(self._positions(value.get('positions')))
        if old and old.get('kind')=='credit_note':value['totals']=old['totals']
        return value

    def _save(self,actor,identifier,project_id,customer_id,kind,value,old=None):
        revision=old['revision']+1 if old else 1;now=self._now();payload=canonical(value);digest=_hash(payload)
        if old:
            changed=self.db.execute("UPDATE business_documents SET revision=?,payload_json=?,payload_sha256=?,updated_by=?,updated_at=? WHERE id=? AND revision=? AND status='draft'",
                (revision,payload,digest,actor['id'],now,identifier,old['revision']))
            if changed.rowcount!=1:raise Problem(409,'Beleg wurde geändert')
        else:self.db.execute('INSERT INTO business_documents(id,project_id,customer_id,kind,status,revision,payload_json,payload_sha256,created_by,updated_by,created_at,updated_at) '
            "VALUES(?,?,?,?,'draft',?,?,?,?,?,?,?)",(identifier,project_id,customer_id,kind,revision,payload,digest,actor['id'],actor['id'],now,now))
        self.db.execute('INSERT INTO business_document_versions(document_id,revision,payload_json,payload_sha256,at) VALUES(?,?,?,?,?)',(identifier,revision,payload,digest,now))
        return self.get(actor,identifier)

    def create(self,actor,data):
        if not isinstance(data,dict):raise Problem(400,'Beleg erwartet')
        project_id=_id(data.get('project_id'));actor=require(self.office,actor,'finance.write',project_id)
        replay,fingerprint=self._replay(actor,data.get('request_id'),'document.create',data,project_id)
        if replay:return replay
        project=self.db.execute('SELECT * FROM projects WHERE id=?',(project_id,)).fetchone()
        customer=self.db.execute('SELECT * FROM customers WHERE id=?',(project['customer_id'],)).fetchone() if project['customer_id'] else None
        if not data.get('buyer'):
            data={**data,'buyer':{'name':customer['name'] if customer else project['customer'],'address_line':customer['address'] if customer else '',
                'email':customer['email'] if customer else '', 'country':'DE'}}
        value=self._payload(self._time_values(actor,project_id,data))
        if value['kind']=='credit_note' or value.get('cancels') or value.get('converted_from'):raise Problem(400,'Stornogutschrift ausschließlich aus einer finalen Rechnung erstellen')
        result=self._save(actor,uuid.uuid4().hex,project_id,project['customer_id'],value['kind'],value)
        return self._remember(actor,data['request_id'],'document.create',fingerprint,result,project_id)

    def update(self,actor,identifier,data):
        row=self._row(actor,identifier,'finance.write');actor=require(self.office,actor,'finance.write',row['project_id'])
        replay,fingerprint=self._replay(actor,data.get('request_id'),'document.update:'+identifier,data,row['project_id'])
        if replay:return replay
        if row['status']!='draft' or data.get('revision')!=row['revision']:raise Problem(409,'Beleg ist final oder wurde geändert')
        if row['kind']=='credit_note' and set(data)-{'request_id','revision','title','issue_date','due_date','notes','intro','cancel_reason'}:
            raise Problem(409,'Vollstorno muss Anschrift, Positionen und Beträge der Originalrechnung unverändert umkehren')
        old=json.loads(row['payload_json'])
        for field in ('project_id','kind','cancels','converted_from'):
            if field in data and data[field]!=old.get(field,row[field] if field in ('project_id','kind') else None):raise Problem(400,'Belegbezug ist unveränderlich')
        value=self._payload(self._time_values(actor,row['project_id'],data,old),old)
        result=self._save(actor,identifier,row['project_id'],row['customer_id'],row['kind'],value,row)
        return self._remember(actor,data['request_id'],'document.update:'+identifier,fingerprint,result,row['project_id'])

    def convert(self,actor,identifier,data):
        row=self._row(actor,identifier,'finance.write');actor=require(self.office,actor,'finance.write',row['project_id'])
        replay,fingerprint=self._replay(actor,data.get('request_id'),'document.convert:'+identifier,data,row['project_id'])
        if replay:return replay
        if data.get('revision')!=row['revision']:raise Problem(409,'Quellbeleg wurde geändert')
        target=data.get('target_kind')
        allowed={'estimate':('offer','order_confirmation'),'offer':('order_confirmation','invoice','advance_invoice','delivery_note'),'order_confirmation':('delivery_note','invoice','advance_invoice','final_invoice'),
                 'delivery_note':('invoice',),'advance_invoice':('cumulative_invoice','final_invoice'),'cumulative_invoice':('cumulative_invoice','final_invoice')}
        if target not in allowed.get(row['kind'],()):raise Problem(400,'Diese Umwandlung ist nicht vorgesehen')
        value=json.loads(row['payload_json']);value.update(kind=target,title=LABELS[target],converted_from=identifier)
        value.pop('previous_documents',None)
        value.pop('contract_totals',None);value.pop('previous_issued_gross',None)
        value.update(calculate_positions(value['positions']))
        value['previous_document_ids']=[]
        if target in ('cumulative_invoice','final_invoice') and row['kind'] in INVOICES and row['status']=='final':value['previous_document_ids']=[identifier]
        result=self._save(actor,uuid.uuid4().hex,row['project_id'],row['customer_id'],target,value)
        self.db.execute("INSERT INTO business_document_relations(target_id,source_id,kind,source_sha256) VALUES(?,?,'converted_from',?)",(result['id'],identifier,row['payload_sha256']))
        return self._remember(actor,data['request_id'],'document.convert:'+identifier,fingerprint,result,row['project_id'])

    def cancel(self,actor,identifier,data):
        row=self._row(actor,identifier,'finance.issue');actor=require(self.office,actor,'finance.issue',row['project_id'])
        replay,fingerprint=self._replay(actor,data.get('request_id'),'document.cancel:'+identifier,data,row['project_id'])
        if replay:return replay
        if row['kind'] not in INVOICES or row['kind']=='credit_note' or row['status']!='final' or data.get('revision')!=row['revision']:raise Problem(409,'Nur finale Rechnungen können storniert werden')
        if self.db.execute("SELECT 1 FROM business_document_relations r JOIN business_documents d ON d.id=r.target_id WHERE r.source_id=? AND r.kind='cancels'",(identifier,)).fetchone():raise Problem(409,'Stornobeleg existiert bereits')
        cancelled_date=_date(data.get('issue_date',self.clock().astimezone(timezone.utc).date().isoformat()))
        if cancelled_date<json.loads(row['payload_json'])['issue_date']:raise Problem(400,'Stornodatum darf nicht vor dem Rechnungsdatum liegen')
        value=json.loads(row['payload_json']);value.update(kind='credit_note',title='Stornogutschrift',cancels=identifier,
            cancelled_number=row['number'],cancel_reason=_text(data.get('reason'),'Stornogrund',2000),previous_document_ids=[],issue_date=cancelled_date,due_date=cancelled_date)
        value['totals']=json.loads(row['payload_json'])['totals']
        result=self._save(actor,uuid.uuid4().hex,row['project_id'],row['customer_id'],'credit_note',value)
        self.db.execute("INSERT INTO business_document_relations(target_id,source_id,kind,source_sha256) VALUES(?,?,'cancels',?)",(result['id'],identifier,row['payload_sha256']))
        return self._remember(actor,data['request_id'],'document.cancel:'+identifier,fingerprint,result,row['project_id'])

    def _prior_snapshot(self,actor,row,payload):
        previous=[];deducted=Decimal('0');deductions={};prior_labor=Decimal(0);prior_material=Decimal(0);prior_kinds={k:{v:Decimal(0) for v in ('net','tax','gross')} for k in ('labor','material','service','machine')}
        for identifier in payload.get('previous_document_ids',[]):
            prior=self._row(actor,identifier)
            if prior['status']!='final' or prior['kind'] not in ('advance_invoice','cumulative_invoice') or prior['project_id']!=row['project_id'] or prior['customer_id']!=row['customer_id']:
                raise Problem(409,'Vorbeleg gehört nicht zur abgeschlossenen Rechnungskette')
            if self.db.execute("SELECT 1 FROM business_document_relations r JOIN business_documents d ON d.id=r.target_id WHERE r.source_id=? AND r.kind='cancels' AND d.status='final'",(identifier,)).fetchone():raise Problem(409,'Stornierter Vorbeleg')
            if self.db.execute("SELECT 1 FROM business_document_relations r JOIN business_documents d ON d.id=r.target_id WHERE r.source_id=? AND r.kind='deducts' AND d.status='final' AND d.id<>? AND NOT EXISTS(SELECT 1 FROM business_document_relations c JOIN business_documents credit ON credit.id=c.target_id WHERE c.source_id=d.id AND c.kind='cancels' AND credit.status='final')",(identifier,row['id'])).fetchone():raise Problem(409,'Vorbeleg wurde bereits kumuliert; neuesten Kettenbeleg verwenden')
            value=json.loads(prior['payload_json']);prior_totals=value.get('contract_totals',value['totals']);deducted+=Decimal(prior_totals['gross'])
            prior_labor+=Decimal(prior_totals['labor_net']);prior_material+=Decimal(prior_totals['material_net'])
            for k,amounts in prior_totals['by_kind'].items():
                for part,amount in amounts.items():prior_kinds[k][part]+=Decimal(amount)
            for bucket in prior_totals['tax_breakdown']:
                key=(bucket['rate'],bucket['category'],bucket['reason']);before=deductions.setdefault(key,{'net':Decimal(0),'tax':Decimal(0)})
                before['net']+=Decimal(bucket['net']);before['tax']+=Decimal(bucket['tax'])
            previous.append(dict(id=identifier,number=prior['number'],sha256=prior['payload_sha256'],gross=prior_totals['gross'],issue_date=value['issue_date']))
        if previous:
            full=json.loads(canonical(payload['totals']));remaining=[]
            # A cumulative invoice bills only its incremental liability; the
            # archive also retains the full contract calculation separately.
            for bucket in full['tax_breakdown']:
                prior=deductions.pop((bucket['rate'],bucket['category'],bucket['reason']),{'net':Decimal(0),'tax':Decimal(0)})
                net=Decimal(bucket['net'])-prior['net'];tax=Decimal(bucket['tax'])-prior['tax']
                if net<0 or tax<0:raise Problem(409,'Vorbelege übersteigen die Schlussrechnung')
                remaining.append({**bucket,'net':money(net),'tax':money(tax)})
            if deductions:raise Problem(409,'Steuergruppen der Vorbelege stimmen nicht überein')
            net=sum((Decimal(b['net']) for b in remaining),Decimal(0));tax=sum((Decimal(b['tax']) for b in remaining),Decimal(0))
            if Decimal(full['labor_net'])<prior_labor or Decimal(full['material_net'])<prior_material:raise Problem(409,'Arbeits-/Materialanteil unterschreitet die bereits berechnete Leistung')
            payload['contract_totals']=full
            payload['totals']={**full,'net':money(net),'tax':money(tax),'gross':money(net+tax),'payable':money(net+tax),'tax_breakdown':remaining,
                'labor_net':money(Decimal(full['labor_net'])-prior_labor),'material_net':money(Decimal(full['material_net'])-prior_material)}
            by_kind={k:{part:money(Decimal(amount)-prior_kinds[k][part]) for part,amount in amounts.items()} for k,amounts in full['by_kind'].items()}
            if any(Decimal(amount)<0 for amounts in by_kind.values() for amount in amounts.values()):raise Problem(409,'Bereits berechnete Leistungs-/Steueranteile zunächst gutschreiben')
            payload['totals']['by_kind']=by_kind
            for k in ('labor','material'):
                for part in ('net','tax','gross'):payload['totals'][k+'_'+part]=by_kind[k][part]
            payload['previous_documents']=previous;payload['previous_issued_gross']=money(deducted)
        return previous

    def prepare_finalization(self,actor,identifier,revision):
        row=self._row(actor,identifier,'finance.issue');financial_release(self.office);archive_security=self._issuer_security(row['kind'])
        if row['status']=='final':return {'already_final':True,'id':identifier,'revision':revision,'project_id':row['project_id']}
        if row['revision']!=revision:raise Problem(409,'Beleg wurde geändert')
        settings,settings_revision=self._settings_row()
        if row['kind'] in INVOICES and (not settings['issuing_enabled'] or settings['issuer_mode']!='own' or not settings['cutover_ack']):
            raise Problem(409,'Eigene Rechnungsstellung ist bis zur bestätigten Umstellung deaktiviert')
        if row['kind'] in INVOICES and self.clock().astimezone(timezone.utc).date().isoformat()<settings['cutover_date']:
            raise Problem(409,'Ausschließlicher Ausstellerwechsel ist noch nicht wirksam')
        payload=json.loads(row['payload_json'])
        if row['kind']=='credit_note':
            source=self.db.execute("SELECT d.* FROM business_document_relations r JOIN business_documents d ON d.id=r.source_id WHERE r.target_id=? AND r.kind='cancels' AND r.source_sha256=d.payload_sha256",(identifier,)).fetchone()
            if not source or source['status']!='final' or source['kind'] not in INVOICES or source['kind']=='credit_note' or source['project_id']!=row['project_id'] or source['customer_id']!=row['customer_id']:
                raise Problem(409,'Stornogutschrift benötigt eine unveränderte finale Originalrechnung')
            original=json.loads(source['payload_json'])
            if payload['issue_date']<original['issue_date']:raise Problem(409,'Stornodatum darf nicht vor dem Originaldatum liegen')
            for field in ('buyer','positions','totals','currency','contract_totals','previous_documents'):
                if canonical(original.get(field))!=canonical(payload.get(field)):raise Problem(409,'Vollstorno weicht von der Originalrechnung ab')
            if payload.get('cancels')!=source['id'] or payload.get('cancelled_number')!=source['number']:raise Problem(409,'Stornobezug stimmt nicht mit dem Original überein')
        if row['kind'] in INVOICES and payload['issue_date']<settings['cutover_date']:raise Problem(409,'Belegdatum liegt vor dem Rechnungs-Cutover')
        for field in ('company_name','address_line','postal_code','city','country'):
            if not settings[field]:raise Problem(409,'Ausstelleranschrift vervollständigen')
        if row['kind'] in INVOICES and not(settings['vat_id'] or settings['tax_number']):raise Problem(409,'Steuerkennung des Ausstellers fehlt')
        if row['kind'] in INVOICES:
            for field in ('name','address_line','postal_code','city','country'):
                if not payload['buyer'].get(field):raise Problem(409,'Rechnungsanschrift vervollständigen')
        time_sources=self._time_snapshot(actor,row,payload)
        previous=self._prior_snapshot(actor,row,payload)
        series=PREFIXES[row['kind']];year=int(payload['issue_date'][:4])
        counter=self.db.execute("SELECT next_value FROM business_document_counters WHERE company_id='main' AND series=? AND year=?",(series,year)).fetchone()
        value=counter['next_value'] if counter else 1;number=f'{series}-{year}-{value:06d}'
        snapshot={**payload,'id':identifier,'project_id':row['project_id'],'kind':row['kind'],'number':number,'issuer':settings,
            'settings_revision':settings_revision,'document_revision':revision,'prepared_at':self._now(),'archive_version':1,
            'archive_security':archive_security}
        return {'id':identifier,'project_id':row['project_id'],'revision':revision,'source_sha256':row['payload_sha256'],'snapshot':snapshot,
            'series':series,'year':year,'value':value,'settings_revision':settings_revision,'prior':previous,'time_sources':time_sources}

    def finalize(self,actor,identifier,rendered,request_id):
        row=self._row(actor,identifier,'finance.issue');actor=require(self.office,actor,'finance.issue',row['project_id']);financial_release(self.office);self._issuer_security(row['kind'])
        if not isinstance(rendered,PreparedArtifacts) or rendered.prepared.get('id')!=identifier:raise Problem(400,'Geprüftes Renderartefakt erwartet')
        prepared=rendered.prepared
        replay,fingerprint=self._replay(actor,request_id,'document.finalize:'+identifier,{'document_id':identifier,'revision':prepared['revision']},row['project_id'])
        if replay:return replay
        if row['status']!='draft' or row['revision']!=prepared['revision'] or row['payload_sha256']!=prepared.get('source_sha256'):raise Problem(409,'Beleg wurde geändert oder bereits abgeschlossen')
        fresh=self.prepare_finalization(actor,identifier,row['revision'])
        # Rendering time is deliberately outside the transaction. Every input
        # capable of changing the final artifact is compared again before issue.
        for key in ('revision','source_sha256','series','year','value','settings_revision','prior','time_sources'):
            if fresh[key]!=prepared[key]:raise Problem(409,'Nummer, Einstellungen oder Vorbelege wurden geändert; erneut prüfen')
        candidate={**fresh['snapshot'],'prepared_at':prepared['snapshot']['prepared_at']}
        if canonical(candidate)!=canonical(prepared['snapshot']):raise Problem(409,'Renderquelle wurde verändert')
        if rendered.pdf_sha256!=_hash(rendered.pdf) or not rendered.pdf.startswith(b'%PDF-') or len(rendered.pdf)>MAX_PDF:raise Problem(409,'PDF-Prüfsumme stimmt nicht')
        if rendered.xml is not None and (rendered.xml_sha256!=_hash(rendered.xml) or rendered.validation.get('accepted') is not True or rendered.validation.get('xml_sha256')!=rendered.xml_sha256):raise Problem(409,'E-Rechnung ist nicht validiert oder an eine andere XML-Datei gebunden')
        self.db.execute("INSERT INTO business_document_counters(company_id,series,year,next_value) VALUES('main',?,?,1) ON CONFLICT(company_id,series,year) DO NOTHING",(prepared['series'],prepared['year']))
        changed=self.db.execute("UPDATE business_document_counters SET next_value=next_value+1 WHERE company_id='main' AND series=? AND year=? AND next_value=?",(prepared['series'],prepared['year'],prepared['value']))
        if changed.rowcount!=1:raise Problem(409,'Nummer wurde zwischenzeitlich vergeben')
        now=self._now();payload=canonical(prepared['snapshot']);digest=_hash(payload);number=prepared['snapshot']['number']
        self.db.execute('INSERT INTO business_document_numbers(document_id,company_id,series,year,value,number,issued_at) VALUES(?,?,?,?,?,?,?)',
            (identifier,'main',prepared['series'],prepared['year'],prepared['value'],number,now))
        self.db.execute('INSERT INTO business_document_archives(document_id,payload_json,payload_sha256,pdf,pdf_sha256,xml,xml_sha256,validation_json,archived_at) VALUES(?,?,?,?,?,?,?,?,?)',
            (identifier,payload,digest,rendered.pdf,rendered.pdf_sha256,rendered.xml,rendered.xml_sha256,canonical(rendered.validation),now))
        self.db.execute("UPDATE business_documents SET status='final',number=?,payload_json=?,payload_sha256=?,revision=revision+1,finalized_at=?,updated_at=?,updated_by=? WHERE id=? AND status='draft' AND revision=?",
            (number,payload,digest,now,now,actor['id'],identifier,row['revision']))
        self.db.execute('INSERT INTO business_document_versions(document_id,revision,payload_json,payload_sha256,at) VALUES(?,?,?,?,?)',(identifier,row['revision']+1,payload,digest,now))
        for source in prepared['prior']:
            self.db.execute("INSERT INTO business_document_relations(target_id,source_id,kind,source_sha256) VALUES(?,?,'deducts',?)",(identifier,source['id'],source['sha256']))
        if row['kind'] in INVOICES and row['kind']!='credit_note':
            for source in prepared['time_sources']:
                self.db.execute('INSERT INTO business_document_time_billing(document_id,entry_id,source_hash,source_revision,seconds) VALUES(?,?,?,?,?)',
                    (identifier,source['entry_id'],source['source_hash'],source['source_revision'],source['seconds']))
        return self._remember(actor,request_id,'document.finalize:'+identifier,fingerprint,self.get(actor,identifier),row['project_id'])

    def archive(self,actor,identifier,format='pdf'):
        row=self._row(actor,identifier)
        if format not in ('pdf','xml'):raise Problem(400,'Archivformat erwartet')
        archive=self.db.execute('SELECT * FROM business_document_archives WHERE document_id=?',(identifier,)).fetchone()
        if row['status']!='final' or not archive or archive[format] is None:raise Problem(404,'Archivdatei nicht vorhanden')
        value=bytes(archive[format])
        if _hash(value)!=archive[format+'_sha256']:raise Problem(409,'Archivprüfsumme stimmt nicht')
        return value

    def sign(self,actor,identifier,data):
        row=self._row(actor,identifier,'documents.write');actor=require(self.office,actor,'documents.write',row['project_id'])
        require(self.office,actor,'finance.read',row['project_id'])
        if row['kind'] not in ('offer','order_confirmation','delivery_note') or row['status']!='final':raise Problem(409,'Nur finale Angebote, Auftragsbestätigungen oder Lieferscheine unterzeichnen')
        replay,fingerprint=self._replay(actor,data.get('request_id'),'document.sign:'+identifier,data,row['project_id'])
        if replay:return replay
        if data.get('revision')!=row['revision'] or data.get('confirmation') is not True or data.get('level')!='simple':raise Problem(400,'Einfache Unterschrift mit ausdrücklicher Bestätigung erwartet')
        signer=_text(data.get('signer'),'Unterzeichner',200);strokes=data.get('strokes')
        if not isinstance(strokes,list) or not 1<=len(strokes)<=100:raise Problem(400,'Unterschriftzüge erwartet')
        points=0
        for stroke in strokes:
            if not isinstance(stroke,list) or len(stroke)<2:raise Problem(400,'Unterschriftzug erwartet')
            for point in stroke:
                points+=1
                if points>10000 or not isinstance(point,list) or len(point)!=2 or any(type(x) not in (int,float) or not 0<=x<=1 for x in point):raise Problem(400,'Begrenzte normierte Unterschriftkoordinaten erwartet')
        payload={'signer':signer,'strokes':strokes,'level':'simple','confirmation':True,'document_sha256':row['payload_sha256']}
        identifier_=uuid.uuid4().hex;now=self._now()
        self.db.execute('INSERT INTO business_document_signatures(id,document_id,payload_sha256,actor_id,payload_json,at) VALUES(?,?,?,?,?,?)',(identifier_,identifier,row['payload_sha256'],actor['id'],canonical(payload),now))
        original=self.db.execute('SELECT pdf_sha256 FROM business_document_archives WHERE document_id=?',(identifier,)).fetchone()
        signed_pdf=render_pdf({**json.loads(row['payload_json']),'signature':{**payload,'at':now,'original_pdf_sha256':original['pdf_sha256']}})
        self.db.execute('INSERT INTO business_signed_documents(signature_id,document_id,pdf,pdf_sha256,original_pdf_sha256,at) VALUES(?,?,?,?,?,?)',
            (identifier_,identifier,signed_pdf,_hash(signed_pdf),original['pdf_sha256'],now))
        return self._remember(actor,data['request_id'],'document.sign:'+identifier,fingerprint,dict(id=identifier_,document_id=identifier,level='simple',signed_at=now,signer=signer,
            signed_pdf_sha256=_hash(signed_pdf),original_pdf_sha256=original['pdf_sha256']),row['project_id'])

    def signatures(self,actor,identifier):
        self._row(actor,identifier)
        return {'items':[dict(id=r['id'],signed_at=r['at'],level='simple',signer=json.loads(r['payload_json'])['signer'],signed_pdf_sha256=r['pdf_sha256'],original_pdf_sha256=r['original_pdf_sha256'])
            for r in self.db.execute('SELECT s.*,a.pdf_sha256,a.original_pdf_sha256 FROM business_document_signatures s JOIN business_signed_documents a ON a.signature_id=s.id WHERE s.document_id=? ORDER BY s.at,s.id',(identifier,)).fetchall()]}

    def signed_pdf(self,actor,identifier,signature_id):
        self._row(actor,identifier)
        row=self.db.execute('SELECT * FROM business_signed_documents WHERE document_id=? AND signature_id=?',(identifier,_id(signature_id))).fetchone()
        if not row:raise Problem(404,'Unterschriebene Fassung nicht verfügbar')
        value=bytes(row['pdf'])
        if _hash(value)!=row['pdf_sha256']:raise Problem(409,'Signaturfassung ist beschädigt')
        return value

    def email_preview(self,actor,identifier):
        row=self._row(actor,identifier);value=json.loads(row['payload_json'])
        if row['status']!='final':raise Problem(409,'Vor dem Versand Beleg prüfen und abschließen')
        archive=self.db.execute('SELECT pdf_sha256,xml_sha256 FROM business_document_archives WHERE document_id=?',(identifier,)).fetchone()
        from business_delivery import _address
        recipient=_address(value['buyer'].get('email'))
        sender=os.environ.get('SMARTPLAN_SMTP_FROM','')
        if sender:
            try:sender=_address(sender)
            except Problem:sender=''
        result={'document_id':identifier,'document_sha256':row['payload_sha256'],'recipient':recipient,'sender':sender,
            'sender_configured':bool(sender and os.environ.get('SMARTPLAN_SMTP_ENABLED')=='1'),
            'subject':LABELS[row['kind']]+' '+row['number'],'text':'Guten Tag,\n\nanbei erhalten Sie '+LABELS[row['kind']]+' '+row['number']+'.\n\n'+value['issuer']['company_name'],
            'attachments':[{'filename':row['number']+'.pdf','media_type':'application/pdf','sha256':archive['pdf_sha256']}],
            'confirmation_required':True,'recipient_delivery_confirmed':False}
        if archive['xml_sha256']:result['attachments'].append({'filename':row['number']+'.xml','media_type':'application/xml','sha256':archive['xml_sha256']})
        result['preview_sha256']=_hash(canonical(result))
        return result

    def _mail_state(self,outbox_id):
        rows=self.db.execute('SELECT * FROM business_document_mail_receipts WHERE outbox_id=? ORDER BY ordinal DESC',(outbox_id,)).fetchall()
        state=rows[0]['status'] if rows else 'pending'
        return {'outbox_id':outbox_id,'status':state,'accepted_by_server':state=='accepted','recipient_delivery_confirmed':False,
            'receipt_id':rows[0]['receipt_id'] if rows else None,'retry_requires_review':state in ('sending','unknown')}

    def prepare_mail(self,actor,identifier,data):
        row=self._row(actor,identifier,'finance.approve');actor=require(self.office,actor,'finance.approve',row['project_id'])
        financial_release(self.office)
        replay,fingerprint=self._replay(actor,data.get('request_id'),'document.email:'+identifier,data,row['project_id'])
        if replay:return self._mail_state(replay['outbox_id'])
        preview=self.email_preview(actor,identifier)
        if data.get('confirmation') is not True or data.get('revision')!=row['revision'] or data.get('preview_sha256')!=preview['preview_sha256']:raise Problem(409,'Aktuelle Versandvorschau und Anhänge ausdrücklich bestätigen')
        for old in self.db.execute('SELECT * FROM business_document_outbox WHERE document_id=?',(identifier,)).fetchall():
            state=self._mail_state(old['id'])
            if state['status'] in ('sending','unknown'):raise Problem(409,'Unbestätigten Versand zuerst klären; keine blinde Wiederholung')
            if old['payload_sha256']==preview['preview_sha256']:return self._remember(actor,data['request_id'],'document.email:'+identifier,fingerprint,state,row['project_id'])
        outbox_id=uuid.uuid4().hex;operation=uuid.uuid4().hex
        self.db.execute('INSERT INTO business_document_outbox(id,document_id,operation_id,payload_json,payload_sha256,created_by,created_at) VALUES(?,?,?,?,?,?,?)',
            (outbox_id,identifier,operation,canonical(preview),preview['preview_sha256'],actor['id'],self._now()))
        state=self._mail_state(outbox_id)
        return self._remember(actor,data['request_id'],'document.email:'+identifier,fingerprint,state,row['project_id'])

    def send_mail(self,actor,identifier,data,*,transport=None):
        state=self.prepare_mail(actor,identifier,data)
        if state['status'] not in ('pending','not_sent'):return state
        if state['status']=='not_sent' and data.get('retry_confirmation') is not True:raise Problem(409,'Belegten Nichtversand und erneuten Versand ausdrücklich bestätigen')
        if transport is None:
            from business_delivery import configured_transport
            transport=configured_transport()
        with _transaction(self.office):
            self._row(actor,identifier,'finance.approve')
            financial_release(self.office)
            state=self._mail_state(state['outbox_id'])
            if state['status'] not in ('pending','not_sent'):return state
            outbox=self.db.execute('SELECT * FROM business_document_outbox WHERE id=?',(state['outbox_id'],)).fetchone();preview=json.loads(outbox['payload_json'])
            if self.email_preview(actor,identifier)['preview_sha256']!=outbox['payload_sha256']:raise Problem(409,'Versandquelle wurde geändert')
            attachments=[]
            for attachment in preview['attachments']:
                content=self.archive(actor,identifier,'pdf' if attachment['media_type']=='application/pdf' else 'xml')
                attachments.append({**attachment,'bytes':content})
            ordinal=self.db.execute('SELECT count(*) AS count FROM business_document_mail_receipts WHERE outbox_id=?',(outbox['id'],)).fetchone()['count']+1
            self.db.execute("INSERT INTO business_document_mail_receipts(id,outbox_id,operation_id,status,ordinal,at) VALUES(?,?,?,'sending',?,?)",(uuid.uuid4().hex,outbox['id'],outbox['operation_id'],ordinal,self._now()))
            job={'operation_id':outbox['operation_id'],'recipient':preview['recipient'],'subject':preview['subject'],'text':preview['text'],'expected_sender':preview['sender'],'attachments':attachments}
        # No Office lock or transaction surrounds actual SMTP I/O.
        from business_delivery import DeliveryReceipt
        try:
            with _transaction(self.office):
                self._row(actor,identifier,'finance.approve');financial_release(self.office)
        except Problem:
            with _transaction(self.office):
                self.db.execute("INSERT INTO business_document_mail_receipts(id,outbox_id,operation_id,status,ordinal,error_code,at) VALUES(?,?,?,'failed',?,'authorization_changed_before_io',?)",
                    (uuid.uuid4().hex,outbox['id'],job['operation_id'],ordinal+1,self._now()))
            raise
        try:receipt=transport.send(job)
        except Exception:receipt=DeliveryReceipt('unknown',job['operation_id'],error_code='delivery_unconfirmed')
        if not isinstance(receipt,DeliveryReceipt) or receipt.operation_id!=job['operation_id'] or receipt.status not in ('accepted','failed','unknown'):
            receipt=DeliveryReceipt('unknown',job['operation_id'],error_code='invalid_delivery_receipt')
        with _transaction(self.office):
            # Preserve the external outcome even if the initiating actor was
            # revoked during I/O. Authorization is checked before publishing.
            next_ordinal=self.db.execute('SELECT count(*) AS count FROM business_document_mail_receipts WHERE outbox_id=?',(outbox['id'],)).fetchone()['count']+1
            current=self._mail_state(outbox['id'])['status']
            if current not in ('sending','unknown') and receipt.status!='accepted':
                receipt=DeliveryReceipt('unknown',job['operation_id'],receipt.receipt_id,error_code='conflicting_delivery_evidence')
            self.db.execute('INSERT INTO business_document_mail_receipts(id,outbox_id,operation_id,status,ordinal,receipt_id,error_code,at) VALUES(?,?,?,?,?,?,?,?)',
                (uuid.uuid4().hex,outbox['id'],job['operation_id'],receipt.status,next_ordinal,receipt.receipt_id,receipt.error_code,self._now()))
        with _transaction(self.office):
            self._row(actor,identifier,'finance.approve')
            financial_release(self.office)
            return self._mail_state(outbox['id'])

    def reconcile_mail(self,actor,identifier,data):
        document=self._row(actor,identifier,'finance.approve');actor=require(self.office,actor,'finance.approve',document['project_id'])
        replay,fingerprint=self._replay(actor,data.get('request_id'),'document.email.reconcile:'+identifier,data,document['project_id'])
        if replay:return self._mail_state(replay['outbox_id'])
        outbox=self.db.execute('SELECT * FROM business_document_outbox WHERE id=? AND document_id=?',(_id(data.get('outbox_id')),identifier)).fetchone()
        if not outbox or data.get('operation_id')!=outbox['operation_id']:raise Problem(404,'Gebundener Versandauftrag nicht verfügbar')
        state=self._mail_state(outbox['id']);outcome=data.get('outcome')
        if state['status']=='sending':
            claimed=self.db.execute("SELECT at FROM business_document_mail_receipts WHERE outbox_id=? AND status='sending' ORDER BY ordinal DESC LIMIT 1",(outbox['id'],)).fetchone()
            if not claimed or (self.clock()-datetime.fromisoformat(claimed['at'])).total_seconds()<120:
                raise Problem(409,'Laufenden Versand nicht überschreiben; zuerst die tatsächliche Transportquittung abwarten')
            if data.get('confirmation') is not True or outcome not in ('accepted','not_sent'):raise Problem(409,'Überfälligen Versand anhand eines tatsächlichen Nachweises abgleichen')
            _text(data.get('proof'),'Nachweisreferenz',500)
            ordinal=self.db.execute('SELECT count(*) AS count FROM business_document_mail_receipts WHERE outbox_id=?',(outbox['id'],)).fetchone()['count']+1
            self.db.execute("INSERT INTO business_document_mail_receipts(id,outbox_id,operation_id,status,ordinal,error_code,at) VALUES(?,?,?,'unknown',?,'stale_sender_claim',?)",
                (uuid.uuid4().hex,outbox['id'],outbox['operation_id'],ordinal,self._now()))
            state=self._mail_state(outbox['id'])
        if state['status'] not in ('unknown','failed') or outcome not in ('accepted','not_sent') or data.get('confirmation') is not True:raise Problem(409,'Ungeklärten Versand anhand eines tatsächlichen Nachweises abgleichen')
        proof=_text(data.get('proof'),'Nachweisreferenz',500);ordinal=self.db.execute('SELECT count(*) AS count FROM business_document_mail_receipts WHERE outbox_id=?',(outbox['id'],)).fetchone()['count']+1
        self.db.execute('INSERT INTO business_document_mail_receipts(id,outbox_id,operation_id,status,ordinal,receipt_id,at) VALUES(?,?,?,?,?,?,?)',
            (uuid.uuid4().hex,outbox['id'],outbox['operation_id'],outcome,ordinal,_hash(proof),self._now()))
        return self._remember(actor,data['request_id'],'document.email.reconcile:'+identifier,fingerprint,self._mail_state(outbox['id']),document['project_id'])


@dataclass(frozen=True)
class PreparedArtifacts:
    prepared:dict
    pdf:bytes
    pdf_sha256:str
    xml:bytes|None=None
    xml_sha256:str|None=None
    validation:dict=None


class Download(bytes):
    def __new__(cls,value,filename):
        result=super().__new__(cls,value);result.filename=filename;return result


def _eur(value):
    whole,fraction=money(Decimal(value)).split('.')
    sign='-' if whole.startswith('-') else '';whole=whole.lstrip('-')
    groups=[]
    while whole:groups.insert(0,whole[-3:]);whole=whole[:-3]
    return sign+'.'.join(groups)+','+fraction+' €'


def epc_payload(snapshot):
    """EPC069-12 SCT QR, version002; this is a payment instruction, no receipt."""
    if snapshot['kind'] not in INVOICES or snapshot['kind']=='credit_note' or Decimal(snapshot['totals']['gross'])<=0:return None
    issuer=snapshot['issuer'];iban=issuer.get('iban','').replace(' ','').upper();bic=issuer.get('bic','').replace(' ','').upper()
    if not re.fullmatch(r'[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}',iban):return None
    expanded=''.join(str(ord(c)-55) if c.isalpha() else c for c in iban[4:]+iban[:4])
    if int(expanded)%97!=1 or bic and not re.fullmatch(r'[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?',bic):return None
    name=issuer['company_name'];reference=snapshot.get('number','');amount=Decimal(snapshot['totals']['gross'])
    if len(name)>70 or len(reference)>140 or amount>Decimal('999999999.99') or any(c in name+reference for c in '\r\n'):return None
    return '\n'.join(['BCD','002','1','SCT',bic,name,iban,'EUR'+money(amount),'','',reference,''])


def render_pdf(snapshot):
    """Render only the immutable data snapshot; no URLs, files or DB reads."""
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image
    output=io.BytesIO();styles=getSampleStyleSheet();style=ParagraphStyle('commercial',parent=styles['Normal'],fontSize=9,leading=12)
    doc=SimpleDocTemplate(output,pagesize=(210*mm,297*mm),rightMargin=17*mm,leftMargin=17*mm,topMargin=17*mm,bottomMargin=20*mm,
        title=snapshot['title'],author=snapshot['issuer']['company_name'],pageCompression=1)
    seller=snapshot['issuer'];buyer=snapshot['buyer'];story=[]
    def paragraph(value):return Paragraph(escape(str(value)).replace('\n','<br/>'),style)
    if seller.get('logo_base64'):
        raw=base64.b64decode(seller['logo_base64'],validate=True)
        image=Image(io.BytesIO(raw));image._restrictSize(55*mm,22*mm);story.extend([image,Spacer(1,5*mm)])
    story.extend([Paragraph(escape(seller['company_name']),styles['Heading1']),paragraph('\n'.join(filter(None,[seller['address_line'],seller['postal_code']+' '+seller['city'],seller['email'],seller['phone']]))) ,Spacer(1,8*mm),
        paragraph('\n'.join(filter(None,[buyer['name'],buyer.get('address_line'),buyer.get('postal_code','')+' '+buyer.get('city',''),buyer.get('country')]))),Spacer(1,7*mm),
        Paragraph(escape(LABELS[snapshot['kind']]+' '+snapshot.get('number','ENTWURF')),styles['Heading2']),paragraph(snapshot['title']),
        paragraph('Datum: '+snapshot['issue_date']+' · Fällig: '+snapshot['due_date']),paragraph('Käuferreferenz: '+snapshot.get('buyer_reference','')),Spacer(1,5*mm)])
    if snapshot.get('intro'):story.extend([paragraph(snapshot['intro']),Spacer(1,4*mm)])
    delivery=snapshot['kind']=='delivery_note'
    rows=[[paragraph(x) for x in (['Pos.','Leistung / Material','Menge','Einheit'] if delivery else ['Pos.','Leistung / Material','Menge','Einzel netto','USt.','Netto'])]]
    for p in snapshot['positions']:
        values=[str(p['index']),p['description'],p['quantity']+' '+p['unit']]
        values+=[''] if delivery else [_eur(p['unit_price_net'])+(' / '+p['price_base_quantity']+' '+p['unit'] if Decimal(p['price_base_quantity'])!=1 else ''),p['tax_rate']+' %',_eur(p['net'])]
        rows.append([paragraph(v) for v in values])
    table=Table(rows,colWidths=([10*mm,120*mm,30*mm,16*mm] if delivery else [10*mm,74*mm,22*mm,27*mm,17*mm,26*mm]),repeatRows=1)
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8edf1')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.5,colors.grey),('BOTTOMPADDING',(0,0),(-1,-1),7)]));story.extend([table,Spacer(1,5*mm)])
    if not delivery:
        totals=snapshot['totals']
        if snapshot.get('contract_totals'):story.append(paragraph('Gesamtleistung brutto: '+_eur(snapshot['contract_totals']['gross'])))
        for previous in snapshot.get('previous_documents',[]):story.append(paragraph('Abzüglich bereits berechnet: '+previous['number']+' / '+_eur(previous['gross'])+' (keine Zahlungsbestätigung)'))
        story.append(paragraph('Netto: '+_eur(totals['net'])))
        for b in totals['tax_breakdown']:story.append(paragraph('Umsatzsteuer '+b['rate']+' %: '+_eur(b['tax'])+((' · '+b['reason']) if b['reason'] else '')))
        story.extend([Paragraph(escape(('Gutschriftbetrag: ' if snapshot['kind']=='credit_note' else 'Gesamtbetrag: ')+_eur(totals['gross'])),styles['Heading2']),
            paragraph('Arbeitsleistung: netto '+_eur(totals['labor_net'])+' · Umsatzsteuer '+_eur(totals['labor_tax'])+' · brutto '+_eur(totals['labor_gross'])),
            paragraph('Material: netto '+_eur(totals['material_net'])+' · Umsatzsteuer '+_eur(totals['material_tax'])+' · brutto '+_eur(totals['material_gross'])),paragraph(seller['payment_terms'])])
    if snapshot.get('cancels'):story.append(paragraph('Storno zu Beleg-ID '+snapshot['cancels']+': '+snapshot.get('cancel_reason','')))
    if snapshot.get('notes'):story.extend([Spacer(1,4*mm),paragraph(snapshot['notes'])])
    story.extend([Spacer(1,6*mm),paragraph('Steuerkennung: '+(seller['vat_id'] or seller['tax_number'])),paragraph('IBAN: '+seller['iban']+' · BIC: '+seller['bic']),paragraph(seller['footer'])])
    epc=epc_payload(snapshot)
    if epc:
        from reportlab.graphics.barcode.qr import QrCodeWidget
        from reportlab.graphics.shapes import Drawing
        qr=QrCodeWidget(epc);bounds=qr.getBounds();size=30*mm
        drawing=Drawing(size,size,transform=[size/(bounds[2]-bounds[0]),0,0,size/(bounds[3]-bounds[1]),0,0]);drawing.add(qr)
        story.extend([Spacer(1,4*mm),drawing,paragraph('GiroCode: Zahlungsauftrag in Ihrer Banking-App prüfen; keine Zahlungsbestätigung.')])
    signature=snapshot.get('signature')
    if signature:
        from reportlab.graphics.shapes import Drawing,PolyLine
        story.extend([Spacer(1,8*mm),Paragraph('Unterschriebene Fassung',styles['Heading2']),paragraph('Unterzeichner: '+signature['signer']),
            paragraph('Zeitpunkt: '+signature['at']),paragraph('Einfache elektronische Unterschrift; keine fortgeschrittene oder qualifizierte Signatur.')])
        drawing=Drawing(160*mm,35*mm)
        for stroke in signature['strokes']:
            points=[coordinate for p in stroke for coordinate in (p[0]*160*mm,(1-p[1])*35*mm)]
            drawing.add(PolyLine(points,strokeWidth=1.2,strokeColor=colors.HexColor('#152c41')))
        story.extend([drawing,paragraph('Original-PDF SHA-256: '+signature['original_pdf_sha256']),paragraph('Beleginhalt SHA-256: '+signature['document_sha256'])])
    def footer(canvas,document):
        canvas.saveState();canvas.setFont('Helvetica',8);canvas.drawString(17*mm,12*mm,snapshot.get('number','ENTWURF'));canvas.drawRightString(193*mm,12*mm,'Seite '+str(document.page));canvas.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer);value=output.getvalue()
    if len(value)>MAX_PDF:raise Problem(413,'PDF ist zu groß')
    return value


def _render_prepared(prepared):
    if prepared.get('already_final'):return PreparedArtifacts(prepared,b'',_hash(b''),validation={})
    # Detach from caller mutation before producing bound, hash-verified artifacts.
    prepared=json.loads(canonical(prepared));snapshot=prepared['snapshot'];pdf=render_pdf(snapshot);xml=None;validation={}
    if snapshot['kind'] in INVOICES and snapshot['issuer']['einvoice_format']=='xrechnung':
        from business_einvoice import build_xrechnung,validate_xrechnung
        xml=build_xrechnung(snapshot);validation=validate_xrechnung(xml)
    elif snapshot['kind'] in INVOICES and snapshot['issuer']['einvoice_format']=='zugferd':
        from business_einvoice import build_zugferd
        pdf,xml,validation=build_zugferd(snapshot,pdf)
    return PreparedArtifacts(prepared,pdf,_hash(pdf),xml,_hash(xml) if xml is not None else None,validation)


_RENDER_GATE=threading.BoundedSemaphore(1)


def render_prepared(prepared):
    if prepared.get('already_final'):return _render_prepared(prepared)
    if not _RENDER_GATE.acquire(timeout=2):raise Problem(429,'Belegprüfung ist belegt; denselben Vorgang später erneut versuchen')
    try:return _render_prepared(prepared)
    finally:_RENDER_GATE.release()


def protected_tables():return _APPEND_ONLY


def runtime_privileges():
    return {'business_document_counters':('SELECT','INSERT','UPDATE'),
            'business_documents':('SELECT','INSERT','UPDATE')}


def _atomic(method):
    @wraps(method)
    def wrapped(self,*args,**kwargs):
        with _transaction(self.office):return method(self,*args,**kwargs)
    return wrapped


for _name in ('settings','save_settings','articles','save_article','text_blocks','save_text_block','templates','save_template','get','list','time_sources','create','update','convert','cancel',
              'prepare_finalization','finalize','archive','sign','signatures','signed_pdf','email_preview','prepare_mail','reconcile_mail'):
    setattr(Documents,_name,_atomic(getattr(Documents,_name)))
BusinessDocuments=Documents


def _checked_integrity(method):
    @wraps(method)
    def wrapped(*args,**kwargs):
        try:return method(*args,**kwargs)
        except ValueError:raise
        except Exception:raise ValueError('Invalid commercial/finance archive or ledger') from None
    return wrapped


@_checked_integrity
def validate_integrity(office):
    """Hashes and ledger continuity complement, rather than replace, SQL guards."""
    db=office.db
    settings=db.execute("SELECT * FROM business_commercial_settings WHERE id='main'").fetchone()
    settings_versions=[json.loads(r['result_json']) for r in db.execute("SELECT result_json FROM business_document_requests WHERE operation='settings'").fetchall()]
    if settings:
        settings_versions.sort(key=lambda value:value['revision'])
        if [v['revision'] for v in settings_versions]!=list(range(1,settings['revision']+1)):raise ValueError('Incomplete commercial settings history')
        current={k:v for k,v in settings_versions[-1].items() if k not in ('id','revision','updated_at')}
        if canonical(current)!=settings['payload_json']:raise ValueError('Commercial settings differ from approved history')
    elif settings_versions:raise ValueError('Commercial settings lack current configuration')
    for article in db.execute('SELECT * FROM business_articles').fetchall():
        history=db.execute('SELECT * FROM business_article_versions WHERE article_id=? ORDER BY revision',(article['id'],)).fetchall()
        if [v['revision'] for v in history]!=list(range(1,article['revision']+1)) or history[-1]['payload_json']!=article['payload_json']:raise ValueError('Incomplete article price history')
    for row in db.execute('SELECT * FROM business_documents').fetchall():
        value=json.loads(row['payload_json'])
        if row['kind'] not in KINDS or _hash(row['payload_json'])!=row['payload_sha256']:raise ValueError('Invalid commercial document digest')
        if value.get('template_source'):
            template=value['template_source']
            if _hash(canonical(template['snapshot']))!=template['sha256']:raise ValueError('Invalid template source snapshot')
        calculated=calculate_positions(value['positions'])
        if canonical(calculated['positions'])!=canonical(value['positions']) or canonical(calculated['totals'])!=canonical(value.get('contract_totals',value['totals'])):raise ValueError('Commercial monetary snapshot is inconsistent')
        versions=db.execute('SELECT revision,payload_sha256 FROM business_document_versions WHERE document_id=? ORDER BY revision',(row['id'],)).fetchall()
        if [v['revision'] for v in versions]!=list(range(1,row['revision']+1)) or versions[-1]['payload_sha256']!=row['payload_sha256']:raise ValueError('Incomplete commercial revision journal')
        if row['status']=='final':
            archive=db.execute('SELECT * FROM business_document_archives WHERE document_id=?',(row['id'],)).fetchone()
            number=db.execute('SELECT * FROM business_document_numbers WHERE document_id=?',(row['id'],)).fetchone()
            if not archive or not number or number['number']!=row['number'] or archive['payload_sha256']!=row['payload_sha256'] or archive['payload_json']!=row['payload_json']:raise ValueError('Incomplete final archive')
    for row in db.execute('SELECT * FROM business_document_archives').fetchall():
        if _hash(row['payload_json'])!=row['payload_sha256'] or _hash(bytes(row['pdf']))!=row['pdf_sha256'] or not bytes(row['pdf']).startswith(b'%PDF-'):raise ValueError('Invalid immutable archive')
        if (row['xml'] is None)!=(row['xml_sha256'] is None) or row['xml'] is not None and _hash(bytes(row['xml']))!=row['xml_sha256']:raise ValueError('Invalid XML archive')
        if row['xml'] is not None and json.loads(row['validation_json']).get('accepted') is not True:raise ValueError('Unvalidated invoice XML')
    for row in db.execute('SELECT * FROM business_signed_documents').fetchall():
        original=db.execute('SELECT pdf_sha256 FROM business_document_archives WHERE document_id=?',(row['document_id'],)).fetchone()
        if not original or original['pdf_sha256']!=row['original_pdf_sha256'] or _hash(bytes(row['pdf']))!=row['pdf_sha256']:raise ValueError('Invalid signed document archive')
    for table in ('business_document_versions','business_article_versions'):
        for row in db.execute('SELECT * FROM '+table).fetchall():
            if _hash(row['payload_json'])!=row['payload_sha256']:raise ValueError('Invalid document/article version digest')
    for counter in db.execute('SELECT * FROM business_document_counters').fetchall():
        numbers=db.execute('SELECT value FROM business_document_numbers WHERE company_id=? AND series=? AND year=? ORDER BY value',
            (counter['company_id'],counter['series'],counter['year'])).fetchall()
        if [r['value'] for r in numbers]!=list(range(1,counter['next_value'])):raise ValueError('Gap in commercial number register')
    for number in db.execute('SELECT * FROM business_document_numbers').fetchall():
        if not db.execute('SELECT 1 FROM business_document_counters WHERE company_id=? AND series=? AND year=? AND next_value>?',
                (number['company_id'],number['series'],number['year'],number['value'])).fetchone():raise ValueError('Number register has no counter')
    for row in db.execute('SELECT * FROM business_document_outbox').fetchall():
        payload=json.loads(row['payload_json']);digest=payload.pop('preview_sha256',None)
        if digest!=row['payload_sha256'] or _hash(canonical(payload))!=digest:raise ValueError('Mail preview digest mismatch')
        events=db.execute('SELECT * FROM business_document_mail_receipts WHERE outbox_id=? ORDER BY ordinal',(row['id'],)).fetchall()
        previous='pending';allowed={'pending':{'sending'},'sending':{'accepted','failed','unknown'},'unknown':{'accepted','not_sent'},'failed':{'accepted','not_sent'},'not_sent':{'sending','accepted','unknown'},'accepted':{'accepted','unknown'}}
        for index,event in enumerate(events,1):
            restored=event['status']=='unknown' and event['error_code']=='disaster_restore_delivery_unconfirmed' and previous not in ('accepted','unknown')
            if event['ordinal']!=index or event['operation_id']!=row['operation_id'] or not restored and event['status'] not in allowed[previous]:raise ValueError('Invalid document mail receipt journal')
            previous=event['status']
    if isinstance(db,sqlite3.Connection):
        expected=guard_statements('sqlite')
        normalize=lambda s:re.sub(r'\s+',' ',s.replace('IF NOT EXISTS ','')).strip().lower()
        for sql in expected:
            name=re.search(r'CREATE TRIGGER IF NOT EXISTS (\w+)',sql)[1]
            actual=db.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",(name,)).fetchone()
            if not actual or normalize(actual[0])!=normalize(sql):raise ValueError('Missing or modified commercial integrity guard: '+name)
    else:_validate_pg_guards(db,guard_statements('postgresql'))
    return True


def sanitize_after_restore(office):
    """Disaster restore only: a stale pending snapshot cannot prove no delivery.

    No external action, archive/counter mutation or automatic resend occurs.
    Successful/unknown receipts remain authoritative; other intents become
    unknown until an operator checks the actual external SMTP evidence.
    """
    changed=0;api=Documents(office)
    with _transaction(office):
        for row in office.db.execute('SELECT * FROM business_document_outbox').fetchall():
            if api._mail_state(row['id'])['status'] in ('accepted','unknown'):continue
            ordinal=office.db.execute('SELECT count(*) AS count FROM business_document_mail_receipts WHERE outbox_id=?',(row['id'],)).fetchone()['count']+1
            office.db.execute("INSERT INTO business_document_mail_receipts(id,outbox_id,operation_id,status,ordinal,error_code,at) VALUES(?,?,?,'unknown',?,'disaster_restore_delivery_unconfirmed',?)",
                (uuid.uuid4().hex,row['id'],row['operation_id'],ordinal,api._now()))
            changed+=1
    return {'document_mail_unknown':changed}


def _validate_pg_guards(db,statements):
    """Exact trigger/body checks reject disabled, conditional or replaced guards."""
    functions={}
    normalize=lambda s:re.sub(r'\s+',' ',s.replace('public.','').replace('"','')).strip().rstrip(';').lower()
    for sql in statements:
        match=re.search(r'CREATE OR REPLACE FUNCTION (\w+)\(\).*?AS \$\$(.*?)\$\$',sql,re.S)
        if match:functions[match[1]]=normalize(match[2])
    for sql in statements:
        match=re.search(r'CREATE TRIGGER (\w+) BEFORE (?:UPDATE|DELETE|INSERT) ON (\w+) FOR EACH ROW EXECUTE FUNCTION (\w+)\(\)',sql)
        if not match:continue
        name,table,function=match.groups()
        row=db.execute('SELECT t.tgenabled,pg_get_triggerdef(t.oid) AS definition,p.proname,p.prosrc,p.prosecdef '
            'FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid WHERE t.tgname=? AND t.tgrelid=?::regclass AND NOT t.tgisinternal',(name,table)).fetchone()
        if (not row or row['tgenabled']!='O' or row['proname']!=function or row['prosecdef']
                or normalize(row['definition'])!=normalize(match[0]) or normalize(row['prosrc'])!=functions[function]):
            raise ValueError('Missing or modified PostgreSQL commercial/finance integrity guard: '+name)


def methods(path):
    if path=='/documents/time-sources':return 'GET'
    if path in ('/documents','/articles','/services','/templates','/text-blocks','/commercial/settings','/settings/branding'):return 'GET, POST'
    if re.fullmatch(r'/(?:documents|articles|services|templates|text-blocks)/[a-f0-9]{32}',path):return 'GET, POST'
    if re.fullmatch(r'/documents/[a-f0-9]{32}/(?:convert|finalize|cancel|sign)',path):return 'POST'
    if re.fullmatch(r'/documents/[a-f0-9]{32}/(?:email|email-reconcile)',path):return 'POST'
    if re.fullmatch(r'/documents/[a-f0-9]{32}/(?:pdf|xml|preview|email-preview)',path):return 'GET'
    if re.fullmatch(r'/documents/[a-f0-9]{32}/signatures(?:/[a-f0-9]{32}/pdf)?',path):return 'GET'
    return None


def dispatch(office,actor,path,method,data):
    if not methods(path):return None
    api=Documents(office)
    if method=='GET':data=data.get('_query',{})
    if method not in methods(path).split(', '):raise Problem(405,'Methode nicht erlaubt')
    parts=path.strip('/').split('/');kind=parts[0];identifier=parts[1] if len(parts)>1 else None;action=parts[2] if len(parts)>2 else None
    if path=='/documents/time-sources':result=api.time_sources(actor,data.get('project_id'))
    elif path in ('/commercial/settings','/settings/branding'):result=api.settings(actor) if method=='GET' else api.save_settings(actor,data)
    elif kind in ('articles','services'):
        result=api.articles(actor,data.get('query',''),services=kind=='services') if method=='GET' else api.save_article(actor,data,identifier)
    elif kind=='templates':result=api.templates(actor) if method=='GET' else api.save_template(actor,data,identifier)
    elif kind=='text-blocks':result=api.text_blocks(actor) if method=='GET' else api.save_text_block(actor,data,identifier)
    elif not identifier:result=api.list(actor,data.get('project_id'),data.get('kind'),data.get('query','')) if method=='GET' else api.create(actor,data)
    elif action in ('pdf','xml'):
        document=api.get(actor,identifier)
        return Download(api.archive(actor,identifier,action),(document['number'] or identifier)+'.'+action),200,'application/pdf' if action=='pdf' else 'application/xml'
    elif action=='preview':
        value=api.get(actor,identifier)
        with _transaction(office):settings,revision=api._settings_row()
        return Download(render_pdf({**value,'issuer':settings}),'Entwurf-'+identifier+'.pdf'),200,'application/pdf'
    elif action=='finalize':
        prepared=api.prepare_finalization(actor,identifier,data.get('revision'))
        rendered=render_prepared(prepared)
        result=api.finalize(actor,identifier,rendered,data.get('request_id'))
    elif action=='email-preview':result=api.email_preview(actor,identifier)
    elif action=='email':result=api.send_mail(actor,identifier,data)
    elif action=='email-reconcile':result=api.reconcile_mail(actor,identifier,data)
    elif action=='signatures':
        if len(parts)==5:return Download(api.signed_pdf(actor,identifier,parts[3]),'Unterschrieben-'+identifier+'.pdf'),200,'application/pdf'
        result=api.signatures(actor,identifier)
    elif action:result=getattr(api,action)(actor,identifier,data)
    else:result=api.get(actor,identifier) if method=='GET' else api.update(actor,identifier,data)
    return result,200,'application/json'
