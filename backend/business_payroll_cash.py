"""Explicit actual payroll disbursements with a private/public evidence boundary.

No bank IO, generated tax payments or rewriting of payroll/legacy cash schemas.
Public sources contain only grouped monetary evidence; private imports require HR.
"""
import json
import re

from core import Problem,canonical
from business_accounting import Accounting,_evidence
from business_foundation import require_permission
from business_operations import identifier,transaction,text
from business_personnel_workflow import PersonnelWorkflow,_sha,_shape,_integer
from business_payroll_accounts import PayrollAccounts
from payroll_cash_sources import Sources,COMPONENTS,CATEGORIES,calculated,part_key

FEATURES=('payroll_actual_cash',)
TABLES=tuple('business_payroll_cash_'+name for name in ('batches','evidence','parts','requests'))
INPUT=('batch_id','expected_revision','instance_id','action','kind','account_id','account_revision','sources','settlement','correction_file_id','reason')
ID=r'[a-f0-9]{32}'


def schema_statements(binary_type='BYTEA'):
    return ['''CREATE TABLE IF NOT EXISTS business_payroll_cash_batches(
      id TEXT NOT NULL,revision INTEGER NOT NULL CHECK(revision>0),sequence INTEGER NOT NULL UNIQUE CHECK(sequence>0),
      instance_id TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('net','remittance')),
      private_json TEXT NOT NULL,private_sha256 TEXT NOT NULL,public_json TEXT NOT NULL,public_sha256 TEXT NOT NULL,
      previous_hash TEXT,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,PRIMARY KEY(id,revision))''',
      '''CREATE TABLE IF NOT EXISTS business_payroll_cash_evidence(
      account_id TEXT NOT NULL REFERENCES business_accounting_accounts(id),evidence_key TEXT NOT NULL,
      batch_id TEXT NOT NULL,first_revision INTEGER NOT NULL,PRIMARY KEY(account_id,evidence_key),
      FOREIGN KEY(batch_id,first_revision) REFERENCES business_payroll_cash_batches(id,revision))''',
      '''CREATE TABLE IF NOT EXISTS business_payroll_cash_parts(
      part_key TEXT PRIMARY KEY,employee_id TEXT NOT NULL REFERENCES business_employees(id),batch_id TEXT NOT NULL,first_revision INTEGER NOT NULL,
      FOREIGN KEY(batch_id,first_revision) REFERENCES business_payroll_cash_batches(id,revision))''',
      '''CREATE TABLE IF NOT EXISTS business_payroll_cash_requests(
      user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,request_json TEXT NOT NULL,request_hash TEXT NOT NULL,result_json TEXT NOT NULL,
      PRIMARY KEY(user_id,request_id))''']


def protected_tables():return TABLES
def runtime_privileges():return {table:('SELECT','INSERT') for table in TABLES}


def guard_statements(dialect):
    result=[]
    if dialect=='postgresql':
        result.append("CREATE OR REPLACE FUNCTION business_payroll_cash_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable payroll cash'; END; $$")
    for table in TABLES:
        for action in ('UPDATE','DELETE'):
            name=table+'_'+action.lower()+'_guard'
            if dialect=='sqlite':result.append(f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable payroll cash'); END")
            elif dialect=='postgresql':result.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION business_payroll_cash_guard(); END IF; END $$")
            else:raise ValueError('Unknown payroll cash dialect')
    if dialect=='sqlite':
        conditions=('id=NEW.id AND revision=NEW.revision OR sequence=NEW.sequence','account_id=NEW.account_id AND evidence_key=NEW.evidence_key',
                    'part_key=NEW.part_key','user_id=NEW.user_id AND request_id=NEW.request_id')
        for table,condition in zip(TABLES,conditions):
            result.append(f"CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition}) BEGIN SELECT RAISE(ABORT,'immutable payroll cash'); END")
    return result


def installed(office):
    from business_schema import _tables
    present=set(TABLES)&_tables(office)
    if present and present!=set(TABLES):raise Problem(409,'Lohnzahlungsbrücke unvollständig installiert.')
    return bool(present)


def _money(value):return ('-' if value<0 else '')+str(abs(value)//100)+'.'+str(abs(value)%100).zfill(2)


def _instance(office):
    from business_instance import validate_integrity
    validate_integrity(office)
    row=office.db.execute('SELECT instance_id FROM business_instance_identity WHERE singleton=1').fetchone()
    if row is None:raise Problem(409,'Operator muss die Unternehmensinstanz zuerst fest binden.')
    return row['instance_id']


def _public(body,private,revision):
    groups={}
    for item in private['transactions']:
        direction='out' if item['amount_minor']>0 else 'in';key=(item['paid_on'],direction)
        categories=groups.setdefault(key,{})
        name='payroll_'+item['component'];categories[name]=categories.get(name,0)+abs(item['amount_minor'])
    movements=[dict(id=_sha([body['batch_id'],day,direction])[:32],date=day,account=private['account'],direction=direction,
        amount=_money(sum(categories.values())),categories={name:_money(value) for name,value in sorted(categories.items())})
        for (day,direction),categories in sorted(groups.items())]
    result=dict(kind='payroll_cash',id=body['batch_id'],revision=revision,instance_id=body['instance_id'],
        status='void' if body['action']=='void' else 'active',date=min([v['date'] for v in movements] or [private['prior_date']]),
        cash_movements=movements,proof_hash=_sha(private),source_path='/payroll/cash/financial/'+body['batch_id']+'?revision='+str(revision))
    return dict(result,source_hash=_sha(result))


def public_source(office,batch_id,revision=None):
    identifier(batch_id)
    sql='SELECT id,revision,instance_id,public_json,public_sha256 FROM business_payroll_cash_batches WHERE id=?';params=[batch_id]
    if revision is not None:_integer(revision,1);sql+=' AND revision=?';params.append(revision)
    row=office.db.execute(sql+' ORDER BY revision DESC LIMIT 1',tuple(params)).fetchone()
    if row is None:raise Problem(404,'Lohn-Geldflussquelle nicht verfügbar.')
    value=json.loads(row['public_json'])
    if (_sha(value)!=row['public_sha256'] or _sha({k:v for k,v in value.items() if k!='source_hash'})!=value['source_hash']
            or value['id']!=row['id'] or value['revision']!=row['revision'] or value['instance_id']!=row['instance_id']):
        raise Problem(409,'Öffentlicher Lohn-Geldflussnachweis ist beschädigt.')
    return value


def financial_access(office,actor,write=False):
    if actor is None:return None
    api=Accounting(office);fresh=api._access(actor)
    if write:api.access(fresh,'accounting.prepare');api.access(fresh,'finance.write')
    return fresh


def ensure_cash_available(office,account_id,evidence_key,original_sha256=None,*,own_batch=None):
    if not installed(office):return
    row=office.db.execute('SELECT batch_id FROM business_payroll_cash_evidence WHERE account_id=? AND evidence_key=?',
        (account_id,_evidence(evidence_key)[1])).fetchone()
    if row and row['batch_id']!=own_batch:raise Problem(409,'Zahlungsnachweis ist bereits im gemeinsamen Geldjournal reserviert.')
    if original_sha256:
        for row in office.db.execute('SELECT id,private_json,private_sha256 FROM business_payroll_cash_batches'):
            private=json.loads(row['private_json'])
            if _sha(private)!=row['private_sha256']:raise Problem(409,'Geschützter Geldflussnachweis ist beschädigt.')
            if row['id']!=own_batch and any(v['original_sha256']==original_sha256 for v in private['transactions']):
                raise Problem(409,'Original ist bereits als geschützter Lohnzahlungsnachweis gebunden.')


class PayrollCash:
    def __init__(self,office,*,clock=None):
        self.office,self.db=office,office.db;self.accounting=Accounting(office,clock=clock)
        self.hr=PersonnelWorkflow(office,clock=clock);self.accounts=PayrollAccounts(office,clock=clock);self.sources_api=Sources(self)

    def _access(self,actor,write=False):
        fresh=financial_access(self.office,actor,write);require_permission(self.office,fresh,'personnel.read')
        if write:
            require_permission(self.office,fresh,'personnel.approve');self.accounts.payroll._gate(fresh);self.hr._gate(fresh)
            from business_schema import require_capability
            require_capability(self.office,'business_payroll_cash');self.accounting._write_gate()
        return fresh

    def _row(self,batch_id,revision=None):
        identifier(batch_id);sql='SELECT * FROM business_payroll_cash_batches WHERE id=?';params=[batch_id]
        if revision is not None:_integer(revision,1);sql+=' AND revision=?';params.append(revision)
        return self.db.execute(sql+' ORDER BY revision DESC LIMIT 1',tuple(params)).fetchone()

    def _private(self,row):
        value=json.loads(row['private_json'])
        if _sha(value)!=row['private_sha256']:raise Problem(409,'Privater Lohnzahlungsnachweis ist beschädigt.')
        return value

    def _metadata(self,row):
        source=public_source(self.office,row['id'],row['revision'])
        return dict(id=row['id'],revision=row['revision'],kind=row['kind'],status=source['status'],instance_id=row['instance_id'],
            public_source=source,private_hash=row['private_sha256'],created_by=row['created_by'],created_at=row['created_at'])

    def _latest(self):
        return self.db.execute('SELECT e.* FROM business_payroll_cash_batches e WHERE NOT EXISTS '
            '(SELECT 1 FROM business_payroll_cash_batches n WHERE n.id=e.id AND n.revision>e.revision) ORDER BY e.sequence').fetchall()

    def state(self,actor):
        with transaction(self.office):
            fresh=self._access(actor);instance=_instance(self.office)
            try:self._access(fresh,True);writes=True
            except Problem as error:
                if error.status not in (403,409,423):raise
                writes=False
            return dict(instance_id=instance,writes_allowed=writes,batches=[self._metadata(row) for row in self._latest()],
                categories=list(CATEGORIES),limits=dict(max_sources=100,year=2026))

    def get(self,actor,batch_id,revision=None):
        with transaction(self.office):
            self._access(actor);row=self._row(batch_id,revision)
            if row is None or row['instance_id']!=_instance(self.office):raise Problem(404,'Lohnübernahme nicht verfügbar.')
            private=self._private(row)
            return dict(self._metadata(row),command=private['command'],source_records=private['source_records'],correction_file=private['correction_file'])

    def _used(self,scope,component,rows,exclude=None):
        total=0
        for row in rows:
            if row['id']==exclude:continue
            private=self._private(row)
            total+=sum(v['amount_minor'] for v in private['transactions'] if v['scope_key']==scope and v['component']==component)
        return total

    def sources(self,actor,employee_id):
        with transaction(self.office):
            fresh=self._access(actor);self.hr._employee(fresh,employee_id);instance=_instance(self.office)
            rows=self._latest();net=[];remittance=[]
            for value in self.accounts._all(employee_id):
                if value['kind'] not in ('payment','carryover'):continue
                ref=dict(account_record_id=value['id'],revision=value['revision'],content_hash=value['content_hash'])
                try:source=self.sources_api.account(fresh,ref);issues=[]
                except Problem as error:
                    if error.status not in (400,409):raise
                    source=None;issues=[error.message]
                month=value['sources']['run']['source']['month'] if value['kind']=='payment' else value['details']['month']
                payments=[]
                for index,payment in enumerate(value['details']['payments']):
                    reserved=self.db.execute('SELECT batch_id FROM business_payroll_cash_parts WHERE part_key=?',(part_key(employee_id,payment),)).fetchone()
                    payments.append(dict(payment,index=index,already_imported=bool(reserved),import_batch_id=reserved['batch_id'] if reserved else None))
                if not payments and not issues:
                    issues=['Für diesen belegten Nullbetrag ist keine Nettozahlung geschuldet; es gibt keinen Cash-Zahlungsteil.']
                net.append(dict(id=value['id'],revision=value['revision'],content_hash=value['content_hash'],kind=value['kind'],month=month,
                    source_file=value['source_file'],eligible=not issues,issues=issues,payments=payments))
                if value['kind']=='carryover':
                    amounts=calculated(value['sources']['calculation']);scope=employee_id+':'+month
                    remittance.append(dict(source_kind='carryover',id=value['id'],revision=value['revision'],content_hash=value['content_hash'],month=month,
                        calculated=amounts,remaining={k:max(0,v-self._used(scope,k,rows)) for k,v in amounts.items()},eligible=not issues,issues=issues))
            for value in self.accounts.payroll._all('run',employee_id):
                try:source=self.sources_api.remittance(fresh,dict(source_kind='run',id=value['id'],revision=value['revision'],content_hash=value['content_hash']));issues=[]
                except Problem as error:
                    if error.status not in (400,409):raise
                    source=None;issues=[error.message]
                amounts=calculated(value['calculation']) if source else {key:None for key in COMPONENTS};scope=employee_id+':'+value['source']['month']
                remittance.append(dict(source_kind='run',id=value['id'],revision=value['revision'],content_hash=value['content_hash'],month=value['source']['month'],
                    calculated=amounts,remaining={k:max(0,v-self._used(scope,k,rows)) if v is not None else None for k,v in amounts.items()},eligible=not issues,issues=issues))
            files=[dict(value,source_path='/personnel/files/'+value['id']+'/content') for value in self.hr.files(fresh,dict(employee_id=employee_id))['items'] if value['purpose']=='personnel']
            return dict(instance_id=instance,employee_id=employee_id,net_sources=net,remittance_sources=remittance,evidence_files=files,categories=list(CATEGORIES))

    def _inputs(self,data,confirm=False):
        fields=INPUT+(('request_id','preview_hash','confirmation') if confirm else ())
        _shape(data,fields,fields)
        for name in ('batch_id','instance_id','account_id'):identifier(data[name])
        _integer(data['expected_revision']);_integer(data['account_revision'],1)
        if data['action'] not in ('adopt','replace','void') or data['kind'] not in ('net','remittance'):
            raise Problem(400,'Bekannte Übernahmeart und ausdrücklichen Korrekturvorgang wählen.')
        if text(data['reason'],'Übernahmegrund',2000,required=True)!=data['reason']:raise Problem(400,'Unveränderten begründeten Übernahmetext angeben.')
        if confirm:
            identifier(data['request_id'])
            if data['confirmation'] is not True:raise Problem(400,'Tatsächliche Zahlung und geprüfte Vorschau ausdrücklich bestätigen.')
        return {key:data[key] for key in INPUT}

    def _prepare(self,actor,body,*,historical=False,prior_rows=None):
        previous=(next((row for row in prior_rows if row['id']==body['batch_id']),None) if historical else self._row(body['batch_id']))
        revision=previous['revision'] if previous else 0
        if revision!=body['expected_revision'] or (body['action']=='adopt')!=(not bool(previous)):
            raise Problem(409,'Übernahmefassung wurde geändert; aktuellen Nachweis erneut prüfen.')
        if previous and (previous['kind']!=body['kind'] or previous['instance_id']!=body['instance_id']):
            raise Problem(409,'Eine Nachweiskorrektur darf Art oder Unternehmensinstanz nicht wechseln.')
        old=self._private(previous) if previous else None
        account=self.accounting._account(body['account_id'],body['account_revision'])
        if not historical and body['action']!='void' and (not account['active'] or self.accounting._account(body['account_id'])['revision']!=body['account_revision']):
            raise Problem(409,'Aktuelles aktives Geldkonto erforderlich.')
        if body['action']=='void':
            if body['sources']!=[] or body['settlement'] is not None or account!=old['account']:
                raise Problem(400,'Rücknahme verwendet das ursprüngliche Geldkonto ohne neue Zahlungsquellen.')
            records=old['source_records'];transactions=[]
            for source in records:
                if actor is not None:self.hr._employee(actor,source['record']['employee_id'])
        else:records,transactions=self.sources_api.build(actor,body,current=not historical)
        correction=None
        if previous:
            correction=self.sources_api.file(actor,body['correction_file_id'])
            if correction['employee_id'] not in {source['record']['employee_id'] for source in old['source_records']}:
                raise Problem(404,'Korrekturbeleg gehört nicht zu den ursprünglichen Personalquellen.')
            if {source['record']['employee_id'] for source in records}!={source['record']['employee_id'] for source in old['source_records']}:
                raise Problem(400,'Nachweiskorrektur darf keine anderen Beschäftigten ersetzen.')
        elif body['correction_file_id'] is not None:raise Problem(400,'Erstübernahme hat keinen Korrekturbeleg.')
        private=dict(command=body,source_records=records,transactions=transactions,account=account,correction_file=correction,
            prior_date=json.loads(previous['public_json'])['date'] if previous else None)
        rows=prior_rows if historical else self._latest()
        if body['kind']=='net' and body['action']!='void':
            for source in records:
                full={part_key(source['record']['employee_id'],v):v['amount_minor'] for v in source['record']['details']['payments']}
                for row in rows:
                    if row['id']==body['batch_id']:continue
                    for item in self._private(row)['transactions']:
                        if item['component']=='net' and item['scope_key']==source['scope_key'] and full.get(item['part_key'])!=item['amount_minor']:
                            raise Problem(409,'Bereits belegte Zahlung fehlt oder wurde geändert; zuerst deren bestehenden Nachweis ausdrücklich korrigieren.')
        if body['kind']=='remittance':
            for source in records:
                available=calculated(source['calculation'])
                for component,ceiling in available.items():
                    selected=sum(v['amount_minor'] for v in transactions if v['scope_key']==source['scope_key'] and v['component']==component)
                    if selected and self._used(source['scope_key'],component,rows,body['batch_id'])+selected>ceiling:
                        raise Problem(409,'Belegte Abführungsanteile überschreiten den gebundenen Lauf oder wurden bereits übernommen.')
        identities={};parts=set()
        for item in transactions:
            identity=item['evidence_key'];spec=(item['paid_on'],item['amount_minor']>0)
            if identity in identities and identities[identity]!=spec:raise Problem(409,'Ein Zahlungsnachweis darf nicht verschiedene Tage oder Gegenrichtungen behaupten.')
            identities[identity]=spec
            if item['part_key']:
                if item['part_key'] in parts:raise Problem(409,'Doppelter tatsächlicher Nettozahlungsteil.')
                parts.add(item['part_key'])
        if not historical:
            for item in transactions:
                ensure_cash_available(self.office,account['id'],item['evidence_key'],own_batch=body['batch_id'])
                if self.db.execute('SELECT 1 FROM business_accounting_cash_events WHERE account_id=? AND evidence_key=?',(account['id'],item['evidence_key'])).fetchone():
                    raise Problem(409,'Nachweis ist bereits im vorhandenen Geldjournal erfasst.')
                if self.db.execute('SELECT 1 FROM business_accounting_receipt_bindings WHERE original_sha256=?',(item['original_sha256'],)).fetchone():
                    raise Problem(409,'Original ist bereits einem anderen Geldfluss zugeordnet.')
                from business_accounting_euer import ensure_cash_identity_available
                ensure_cash_identity_available(self.office,account['id'],item['evidence_key'],item['original_sha256'],payroll_batch_id=body['batch_id'])
                if item['part_key']:
                    used=self.db.execute('SELECT batch_id FROM business_payroll_cash_parts WHERE part_key=?',(item['part_key'],)).fetchone()
                    if used and used['batch_id']!=body['batch_id']:raise Problem(409,'Tatsächlicher Nettozahlungsteil wurde bereits übernommen.')
            from business_accounting_euer import EuerAccounting
            ledger=EuerAccounting(self.office)._ledger()
            dates={v['paid_on'] for v in transactions}|{v['paid_on'] for v in old['transactions']} if old else {v['paid_on'] for v in transactions}
            EuerAccounting._unlocked(ledger,[dict(date=day) for day in dates])
        source=_public(body,private,revision+1)
        preview=dict(batch_id=body['batch_id'],revision=revision+1,kind=body['kind'],instance_id=body['instance_id'],public_source=source,
            private_source_count=len(records),private_hash=_sha(private),warnings=['Keine Bankübertragung; EÜR-Einordnung gesondert bestätigen.'])
        return dict(preview,preview_hash=_sha(preview)),private

    def preview(self,actor,data):
        body=self._inputs(data)
        with transaction(self.office):
            fresh=self._access(actor,True)
            if body['instance_id']!=_instance(self.office):raise Problem(409,'Übernahme gehört zu einer anderen Unternehmensinstanz.')
            return self._prepare(fresh,body)[0]

    def confirm(self,actor,data):
        body=self._inputs(data,True)
        with transaction(self.office):
            fresh=self._access(actor,True)
            if body['instance_id']!=_instance(self.office):raise Problem(409,'Übernahme gehört zu einer anderen Unternehmensinstanz.')
            fingerprint=_sha(data)
            receipt=self.db.execute('SELECT * FROM business_payroll_cash_requests WHERE user_id=? AND request_id=?',(fresh['id'],data['request_id'])).fetchone()
            if receipt:
                if receipt['request_hash']!=fingerprint:raise Problem(409,'Vorgangskennung wurde mit anderem Inhalt verwendet.')
                return json.loads(receipt['result_json'])
            try:
                preview,private=self._prepare(fresh,body)
                if preview['preview_hash']!=data['preview_hash']:raise Problem(409,'Genau passende aktuelle Zahlungsvorschau bestätigen.')
            except Problem as error:
                if error.status==409:raise Problem(409,error.message,request_resolution='not_accepted') from None
                raise
            previous=self._row(body['batch_id']);sequence=(self.db.execute('SELECT MAX(sequence) FROM business_payroll_cash_batches').fetchone()[0] or 0)+1
            self.db.execute('INSERT INTO business_payroll_cash_batches VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                (body['batch_id'],preview['revision'],sequence,body['instance_id'],body['kind'],canonical(private),_sha(private),canonical(preview['public_source']),_sha(preview['public_source']),
                 previous['private_sha256'] if previous else None,fresh['id'],self.hr.now()))
            for item in private['transactions']:
                if not self.db.execute('SELECT 1 FROM business_payroll_cash_evidence WHERE account_id=? AND evidence_key=?',(body['account_id'],item['evidence_key'])).fetchone():
                    self.db.execute('INSERT INTO business_payroll_cash_evidence VALUES(?,?,?,?)',(body['account_id'],item['evidence_key'],body['batch_id'],preview['revision']))
                if item['part_key'] and not self.db.execute('SELECT 1 FROM business_payroll_cash_parts WHERE part_key=?',(item['part_key'],)).fetchone():
                    self.db.execute('INSERT INTO business_payroll_cash_parts VALUES(?,?,?,?)',(item['part_key'],item['employee_id'],body['batch_id'],preview['revision']))
            result=self._metadata(self._row(body['batch_id']))
            self.db.execute('INSERT INTO business_payroll_cash_requests VALUES(?,?,?,?,?)',(fresh['id'],data['request_id'],canonical(data),fingerprint,canonical(result)))
            self.office.audit(fresh,'payroll.cash.confirmed',body['batch_id']+':'+str(preview['revision']))
            return result


def validate_integrity(office):
    api=PayrollCash(office);latest={};evidence={};parts={};receipts={}
    for row in office.db.execute('SELECT * FROM business_payroll_cash_requests'):
        command=json.loads(row['request_json']);api._inputs(command,True)
        if canonical(command)!=row['request_json'] or _sha(command)!=row['request_hash'] or command['request_id']!=row['request_id']:
            raise ValueError('Changed payroll cash request')
        result=json.loads(row['result_json']);key=(result['id'],result['revision'])
        if key in receipts:raise ValueError('Duplicate payroll cash receipt')
        receipts[key]=(row,command,result)
    for sequence,row in enumerate(office.db.execute('SELECT * FROM business_payroll_cash_batches ORDER BY sequence'),1):
        private=api._private(row);body=private['command'];preview,recomputed=api._prepare(None,body,historical=True,prior_rows=list(latest.values()))
        previous=latest.get(row['id']);receipt,command,result=receipts.pop((row['id'],row['revision']))
        if (sequence!=row['sequence'] or recomputed!=private or row['revision']!=preview['revision'] or row['instance_id']!=body['instance_id'] or row['instance_id']!=_instance(office)
                or row['kind']!=body['kind'] or row['id']!=body['batch_id'] or row['private_sha256']!=preview['private_hash']
                or row['previous_hash']!=(previous['private_sha256'] if previous else None)
                or public_source(office,row['id'],row['revision'])!=preview['public_source']
                or {k:command[k] for k in INPUT}!=body or command['preview_hash']!=preview['preview_hash']
                or receipt['user_id']!=row['created_by'] or result!=api._metadata(row)):
            raise ValueError('Invalid payroll cash source chain')
        for item in private['transactions']:
            identity=(body['account_id'],item['evidence_key']);value=(row['id'],row['revision'])
            if identity in evidence and evidence[identity][0]!=row['id']:raise ValueError('Reused payroll bank evidence')
            evidence.setdefault(identity,value)
            if item['part_key']:
                if item['part_key'] in parts and parts[item['part_key']][1]!=row['id']:raise ValueError('Reused payroll payment part')
                parts.setdefault(item['part_key'],(item['employee_id'],row['id'],row['revision']))
        latest[row['id']]=row
    if receipts or evidence!={(row['account_id'],row['evidence_key']):(row['batch_id'],row['first_revision']) for row in office.db.execute('SELECT * FROM business_payroll_cash_evidence')}:
        raise ValueError('Invalid payroll cash reservation receipts')
    if parts!={row['part_key']:(row['employee_id'],row['batch_id'],row['first_revision']) for row in office.db.execute('SELECT * FROM business_payroll_cash_parts')}:
        raise ValueError('Invalid payroll cash part receipts')
    return True


def restore_horizon(office):
    if not installed(office):return None
    validate_integrity(office)
    tables={table:sorted((dict(row) for row in office.db.execute('SELECT * FROM '+table)),key=canonical) for table in TABLES}
    return dict(schema_version=1,table_counts={table:len(rows) for table,rows in tables.items()},sha256=_sha(dict(schema_version=1,tables=tables)))


def methods(path):
    if path in ('/payroll/cash','/payroll/cash/sources') or re.fullmatch('/payroll/cash/(?:batches|financial)/'+ID,path):return 'GET'
    if path in ('/payroll/cash/preview','/payroll/cash/batches'):return 'POST'
    return None


def dispatch(office,actor,path,method,data):
    allowed=methods(path)
    if allowed is None:return None
    if method!=allowed:raise Problem(405,'HTTP-Methode nicht erlaubt.')
    api=PayrollCash(office)
    if method=='POST':return (api.preview(actor,data) if path.endswith('/preview') else api.confirm(actor,data)),200 if path.endswith('/preview') else 201,'application/json'
    query=data.get('_query',{})
    if data not in ({},{'_query':query}):raise Problem(400,'Keine zusätzlichen Lohnzahlungsfelder erlaubt.')
    if path.endswith('/sources'):
        _shape(query,('employee_id',),('employee_id',));value=api.sources(actor,query['employee_id'])
    elif path=='/payroll/cash':
        if query:raise Problem(400,'Keine zusätzlichen Filter erlaubt.')
        value=api.state(actor)
    else:
        _shape(query,('revision',));revision=None
        if query:
            if not isinstance(query['revision'],str) or not re.fullmatch(r'[1-9][0-9]*',query['revision']):raise Problem(400,'Positive Quellenrevision erforderlich.')
            revision=int(query['revision'])
        if '/financial/' in path:
            with transaction(office):
                financial_access(office,actor);value=public_source(office,path.rsplit('/',1)[1],revision)
                if value['instance_id']!=_instance(office):raise Problem(404,'Geldflussquelle nicht verfügbar.')
        else:value=api.get(actor,path.rsplit('/',1)[1],revision)
    return value,200,'application/json'
