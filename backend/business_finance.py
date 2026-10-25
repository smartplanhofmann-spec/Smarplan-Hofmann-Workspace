"""Append-only payment allocation and explicitly approved six-stage dunning.

No sender is started here. Outbox entries are approved intentions, never proof
that a customer received a message. Ambiguous delivery blocks automatic retry.
"""
from datetime import date,datetime,timezone,timedelta
from decimal import Decimal
import base64
import io
import json
import os
import re
import sqlite3
import uuid

from core import Problem,canonical
from inquiries import _transaction
from business_documents import Documents,Download,_atomic,_checked_integrity,_hash,_id,_text,_date,decimal_value,money,require,financial_release,INVOICES,_eur


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BLOB','BYTEA'):raise ValueError('Invalid binary type')
    return [
        '''CREATE TABLE IF NOT EXISTS business_finance_requests(user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,
        operation TEXT NOT NULL,request_hash TEXT NOT NULL,result_json TEXT NOT NULL,at TEXT NOT NULL,PRIMARY KEY(user_id,request_id))''',
        '''CREATE TABLE IF NOT EXISTS business_payments(id TEXT PRIMARY KEY,source_id TEXT NOT NULL UNIQUE,
        kind TEXT NOT NULL CHECK(kind IN ('receipt','refund')),amount TEXT NOT NULL,currency TEXT NOT NULL CHECK(currency='EUR'),
        booking_date TEXT NOT NULL,reference TEXT NOT NULL,reverses TEXT REFERENCES business_payments(id),
        created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_payment_allocations(id TEXT PRIMARY KEY,payment_id TEXT NOT NULL REFERENCES business_payments(id),
        document_id TEXT NOT NULL REFERENCES business_documents(id),amount TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(payment_id,document_id))''',
        '''CREATE TABLE IF NOT EXISTS business_dunning_settings(id TEXT PRIMARY KEY CHECK(id='main'),revision INTEGER NOT NULL,
        payload_json TEXT NOT NULL,updated_by TEXT NOT NULL REFERENCES users(id),updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_dunning_rule_versions(revision INTEGER PRIMARY KEY,payload_json TEXT NOT NULL,
        payload_sha256 TEXT NOT NULL,at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_dunning_proposals(id TEXT PRIMARY KEY,document_id TEXT NOT NULL REFERENCES business_documents(id),
        project_id TEXT NOT NULL REFERENCES projects(id),level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 6),
        payload_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        f'''CREATE TABLE IF NOT EXISTS business_dunning_approvals(id TEXT PRIMARY KEY,proposal_id TEXT NOT NULL UNIQUE REFERENCES business_dunning_proposals(id),
        document_id TEXT NOT NULL REFERENCES business_documents(id),level INTEGER NOT NULL,payload_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL,
        pdf {binary_type} NOT NULL,pdf_sha256 TEXT NOT NULL,approved_by TEXT NOT NULL REFERENCES users(id),approved_at TEXT NOT NULL,
        UNIQUE(document_id,level))''',
        f'''CREATE TABLE IF NOT EXISTS business_dunning_editions(id TEXT PRIMARY KEY CHECK(length(id)=32),
        approval_id TEXT NOT NULL REFERENCES business_dunning_approvals(id),edition INTEGER NOT NULL CHECK(edition>1),
        supersedes_id TEXT NOT NULL,proposal_id TEXT NOT NULL UNIQUE REFERENCES business_dunning_proposals(id),
        operation_id TEXT NOT NULL UNIQUE CHECK(length(operation_id)=32),payload_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL,
        pdf {binary_type} NOT NULL,pdf_sha256 TEXT NOT NULL,approved_by TEXT NOT NULL REFERENCES users(id),approved_at TEXT NOT NULL,
        UNIQUE(approval_id,edition))''',
        '''CREATE TABLE IF NOT EXISTS business_finance_outbox(id TEXT PRIMARY KEY,approval_id TEXT NOT NULL UNIQUE REFERENCES business_dunning_approvals(id),
        operation_id TEXT NOT NULL UNIQUE,recipient TEXT NOT NULL,payload_sha256 TEXT NOT NULL,created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_outbox_receipts(id TEXT PRIMARY KEY,outbox_id TEXT NOT NULL REFERENCES business_finance_outbox(id),
        operation_id TEXT NOT NULL,outcome TEXT NOT NULL CHECK(outcome IN ('sending','sent','failed','unknown','not_sent')),
        ordinal INTEGER NOT NULL,provider_receipt TEXT,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,UNIQUE(outbox_id,ordinal))''',
        f'''CREATE TABLE IF NOT EXISTS business_incoming_receipts(id TEXT PRIMARY KEY,project_id TEXT REFERENCES projects(id),filename TEXT NOT NULL,
        media_type TEXT NOT NULL,original {binary_type} NOT NULL,sha256 TEXT NOT NULL,payload_json TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_receipt_reviews(receipt_id TEXT NOT NULL REFERENCES business_incoming_receipts(id),
        revision INTEGER NOT NULL,payload_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL,reviewed_by TEXT NOT NULL REFERENCES users(id),
        reviewed_at TEXT NOT NULL,PRIMARY KEY(receipt_id,revision))''',
        'CREATE INDEX IF NOT EXISTS business_allocations_document ON business_payment_allocations(document_id)',
        'CREATE INDEX IF NOT EXISTS business_dunning_document ON business_dunning_approvals(document_id,level)',
        'CREATE INDEX IF NOT EXISTS business_outbox_events ON business_outbox_receipts(outbox_id,created_at,id)',
    ]


_PROTECTED=('business_finance_requests','business_payments','business_payment_allocations','business_dunning_rule_versions',
    'business_dunning_proposals','business_dunning_approvals','business_dunning_editions','business_finance_outbox','business_outbox_receipts','business_incoming_receipts','business_receipt_reviews')


def protected_tables():return _PROTECTED


def guard_statements(dialect):
    if dialect=='sqlite':return [f"CREATE TRIGGER IF NOT EXISTS {t}_{a.lower()}_guard BEFORE {a} ON {t} BEGIN SELECT RAISE(ABORT,'immutable finance ledger'); END" for t in _PROTECTED for a in ('UPDATE','DELETE')]
    if dialect!='postgresql':raise ValueError('Unsupported dialect')
    output=["CREATE OR REPLACE FUNCTION business_finance_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable finance ledger'; END; $$"]
    for table in _PROTECTED:
        for action in ('UPDATE','DELETE'):
            name=table+'_'+action.lower()+'_guard'
            output.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION business_finance_immutable_guard(); END IF; END $$")
    return output


def default_rules():
    return {'enabled':False,'levels':[{'level':i,'kind':'reminder' if i<=3 else 'demand',
        'name':('Zahlungserinnerung ' if i<=3 else 'Mahnung ')+str(i if i<=3 else i-3),
        'days':7,'fee':'0.00','interest_percent':'0','subject':('Zahlungserinnerung' if i<=3 else 'Mahnung'),
        'text':'Bitte prüfen Sie die offene Forderung. Bereits veranlasste Zahlungen berücksichtigen wir nach Bestätigung.'} for i in range(1,7)]}


def _rules(value):
    if not isinstance(value,dict) or set(value)!={'enabled','levels'} or type(value['enabled']) is not bool:raise Problem(400,'Mahnregeln erwartet')
    levels=value['levels']
    if not isinstance(levels,list) or len(levels)>6 or value['enabled'] and not levels:raise Problem(400,'Bis zu sechs Stufen, aktiv mindestens eine, erwartet')
    output=[];counts={'reminder':0,'demand':0};demands_started=False
    for index,row in enumerate(levels,1):
        if not isinstance(row,dict) or type(row.get('level')) is not int or row.get('level')!=index or row.get('kind') not in counts:raise Problem(400,'Fortlaufende Stufen 1 bis 6 mit Erinnerung oder Mahnung erwartet')
        if row['kind']=='reminder' and demands_started:raise Problem(400,'Erinnerungen müssen vor Mahnungen stehen')
        demands_started=demands_started or row['kind']=='demand';counts[row['kind']]+=1
        if counts[row['kind']]>3:raise Problem(400,'Höchstens drei Erinnerungen und drei Mahnungen')
        if set(row)-{'level','kind','name','days','fee','interest_percent','subject','text'}:raise Problem(400,'Ungültige Mahnfelder')
        if type(row.get('days')) is not int or not 1<=row['days']<=365:raise Problem(400,'Mahnabstand muss 1 bis 365 Tage sein')
        output.append({**row,'name':_text(row.get('name'),'Stufenname',200),'subject':_text(row.get('subject'),'Betreff',300),
            'text':_text(row.get('text'),'Mahntext',10000),'fee':money(decimal_value(row.get('fee','0'))),
            'interest_percent':str(decimal_value(row.get('interest_percent','0'),maximum=Decimal(100)))})
    return {'enabled':value['enabled'],'levels':output}


class Finance:
    def __init__(self,office,*,clock=lambda:datetime.now(timezone.utc)):
        self.office,self.db,self.clock=office,office.db,clock

    def _now(self):return self.clock().astimezone(timezone.utc).isoformat(timespec='microseconds')

    def _receipt(self,actor,data,operation):
        _id(data.get('request_id'));digest=_hash(canonical({'operation':operation,'data':data}))
        row=self.db.execute('SELECT * FROM business_finance_requests WHERE user_id=? AND request_id=?',(actor['id'],data['request_id'])).fetchone()
        if row:
            if row['operation']!=operation or row['request_hash']!=digest:raise Problem(409,'Vorgangskennung wurde mit anderem Inhalt verwendet')
            result=json.loads(row['result_json'])
            def scope(value):
                if isinstance(value,dict):
                    permission='finance.approve' if any(word in operation for word in ('approve','deliver','receipt.review','outbox.receipt')) else 'finance.write'
                    if value.get('project_id'):require(self.office,actor,permission,value['project_id'])
                    for child in value.values():scope(child)
                elif isinstance(value,list):
                    for child in value:scope(child)
            scope(result)
            return result,digest
        return None,digest

    def _remember(self,actor,data,operation,digest,result):
        self.db.execute('INSERT INTO business_finance_requests(user_id,request_id,operation,request_hash,result_json,at) VALUES(?,?,?,?,?,?)',
            (actor['id'],data['request_id'],operation,digest,canonical(result),self._now()))
        return result

    def settings(self,actor):
        require(self.office,actor,'finance.read');row=self.db.execute("SELECT * FROM business_dunning_settings WHERE id='main'").fetchone()
        return dict(id='main',revision=row['revision'] if row else 0,**(json.loads(row['payload_json']) if row else default_rules()))

    def save_settings(self,actor,data):
        actor=require(self.office,actor,'settings.manage');replay,digest=self._receipt(actor,data,'dunning.settings')
        if replay:return replay
        old=self.settings(actor)
        if data.get('revision')!=old['revision']:raise Problem(409,'Mahnregeln wurden geändert')
        value=_rules({k:v for k,v in data.items() if k not in ('request_id','revision')});revision=old['revision']+1;now=self._now();payload=canonical(value)
        self.db.execute("INSERT INTO business_dunning_settings(id,revision,payload_json,updated_by,updated_at) VALUES('main',?,?,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,payload_json=excluded.payload_json,updated_by=excluded.updated_by,updated_at=excluded.updated_at",(revision,payload,actor['id'],now))
        self.db.execute('INSERT INTO business_dunning_rule_versions(revision,payload_json,payload_sha256,at) VALUES(?,?,?,?)',(revision,payload,_hash(payload),now))
        return self._remember(actor,data,'dunning.settings',digest,dict(id='main',revision=revision,**value))

    def _payment_sum(self,identifier):
        rows=self.db.execute('SELECT a.amount,p.kind FROM business_payment_allocations a JOIN business_payments p ON p.id=a.payment_id WHERE a.document_id=?',(identifier,)).fetchall()
        return sum((Decimal(r['amount'])*(1 if r['kind']=='receipt' else -1) for r in rows),Decimal(0))

    def _mail(self,outbox_id):
        row=self.db.execute('SELECT o.*,a.document_id,a.level,a.payload_json,a.pdf,a.pdf_sha256,a.approved_at,a.proposal_id,a.approved_by FROM business_finance_outbox o JOIN business_dunning_approvals a ON a.id=o.approval_id WHERE o.id=?',(outbox_id,)).fetchone()
        if not row:raise Problem(404,'Versandauftrag nicht verfügbar')
        value=dict(row);value.update(edition=1,approval_version_id=row['approval_id'],original_operation_id=row['operation_id'])
        edition=self.db.execute('SELECT * FROM business_dunning_editions WHERE approval_id=? ORDER BY edition DESC LIMIT 1',(row['approval_id'],)).fetchone()
        if edition:
            value.update({key:edition[key] for key in ('edition','operation_id','payload_json','payload_sha256','pdf','pdf_sha256','approved_at','approved_by','proposal_id')})
            value['approval_version_id']=edition['id']
        return value

    def _versions(self,row):
        original=self.db.execute('SELECT * FROM business_dunning_approvals WHERE id=?',(row['approval_id'],)).fetchone()
        result=[{'id':original['id'],'edition':1,'proposal_id':original['proposal_id'],'operation_id':row['original_operation_id'],
            'payload_sha256':original['payload_sha256'],'pdf_sha256':original['pdf_sha256'],'approved_at':original['approved_at']}]
        result.extend({key:e[key] for key in ('id','edition','proposal_id','operation_id','payload_sha256','pdf_sha256','approved_at')}
            for e in self.db.execute('SELECT * FROM business_dunning_editions WHERE approval_id=? ORDER BY edition',(row['approval_id'],)).fetchall())
        for item in result:item['status']=self._operation_state(row['id'],item['operation_id'])
        return result

    def _operation_state(self,outbox_id,operation_id):
        rows=self.db.execute('SELECT * FROM business_outbox_receipts WHERE outbox_id=? AND operation_id=? ORDER BY ordinal DESC',(outbox_id,operation_id)).fetchall()
        return rows[0]['outcome'] if rows else 'pending'

    def _outcome(self,outbox_id):
        row=self._mail(outbox_id)
        return self._operation_state(outbox_id,row['operation_id'])

    def _supersession_conflict(self,row):
        older=[v for v in self._versions(row) if v['operation_id']!=row['operation_id']]
        if any(v['status'] in ('sending','unknown') for v in older):return True
        if not any(v['status']=='sent' for v in older):return False
        current=self.db.execute('SELECT * FROM business_outbox_receipts WHERE outbox_id=? AND operation_id=? ORDER BY ordinal DESC LIMIT 1',(row['id'],row['operation_id'])).fetchone()
        last_sent=max((r['ordinal'] for r in self.db.execute("SELECT ordinal,operation_id FROM business_outbox_receipts WHERE outbox_id=? AND outcome='sent'",(row['id'],)).fetchall() if r['operation_id']!=row['operation_id']),default=0)
        return not(current and current['ordinal']>last_sent and (current['outcome']=='not_sent' or current['outcome']=='sent' and (current['provider_receipt'] or '').startswith('reconciled_supersession:')))

    def _stage_state(self,row):
        if self._supersession_conflict(row):return 'unknown'
        state=self._operation_state(row['id'],row['operation_id'])
        if state=='not_sent' and any(v['status']=='sent' for v in self._versions(row)):return 'sent'
        return state

    def _document_conflict(self,document_id):
        rows=self.db.execute('SELECT o.id FROM business_finance_outbox o JOIN business_dunning_approvals a ON a.id=o.approval_id WHERE a.document_id=?',(document_id,)).fetchall()
        return any(self._supersession_conflict(self._mail(row['id'])) for row in rows)

    def _item(self,actor,document):
        value=json.loads(document['payload_json']);amount=Decimal(value['totals']['gross']);paid=self._payment_sum(document['id']);credit=Decimal(0)
        rows=self.db.execute("SELECT d.payload_json FROM business_document_relations r JOIN business_documents d ON d.id=r.target_id WHERE r.source_id=? AND r.kind='cancels' AND d.status='final'",(document['id'],)).fetchall()
        for row in rows:credit+=Decimal(json.loads(row['payload_json'])['totals']['gross'])
        approvals=self.db.execute('SELECT * FROM business_dunning_approvals WHERE document_id=? ORDER BY level DESC',(document['id'],)).fetchall()
        current=approvals[0] if approvals else None;level=current['level'] if current else 0;rules=self.settings(actor);today=self.clock().date()
        due=date.fromisoformat(value['due_date']);next_date=None
        if level<len(rules['levels']):
            base=date.fromisoformat(current['approved_at'][:10]) if current else due
            next_date=base+timedelta(days=rules['levels'][level]['days'])
        blocked=False;delivery=None;mail=None;can_revise=False;last_reminder=None
        sent_times=[r for r in self.db.execute("SELECT r.created_at,r.provider_receipt FROM business_outbox_receipts r JOIN business_finance_outbox o ON o.id=r.outbox_id JOIN business_dunning_approvals a ON a.id=o.approval_id WHERE a.document_id=? AND r.outcome='sent' ORDER BY r.created_at DESC",(document['id'],)).fetchall() if not (r['provider_receipt'] or '').startswith('reconciled_supersession:')]
        if sent_times:last_reminder=sent_times[0]['created_at']
        if current:
            outbox=self.db.execute('SELECT id FROM business_finance_outbox WHERE approval_id=?',(current['id'],)).fetchone()
            mail=self._mail(outbox['id']) if outbox else None
            delivery=self._stage_state(mail) if mail else 'missing'
            blocked=delivery!='sent'
            if mail:
                previous=json.loads(mail['payload_json']);state=self._operation_state(mail['id'],mail['operation_id'])
                changed=any(previous.get(key)!=new for key,new in (('open',money(amount-paid-credit)),('paid',money(paid)),('credited',money(credit)),('rules_revision',rules['revision']),('sender',os.environ.get('SMARTPLAN_SMTP_FROM',''))))
                can_revise=(rules['enabled'] and amount-paid-credit>0 and 1<=level<=len(rules['levels']) and state in ('pending','failed','not_sent') and changed
                    and not self._supersession_conflict(mail) and not any(v['status']=='sent' for v in self._versions(mail)))
        if current:
            if self._document_conflict(document['id']):blocked=True;delivery='unknown';can_revise=False
            if blocked:next_date=None
            elif last_reminder and level<len(rules['levels']):next_date=date.fromisoformat(last_reminder[:10])+timedelta(days=rules['levels'][level]['days'])
        notes=[json.loads(r['result_json']) for r in self.db.execute('SELECT result_json FROM business_finance_requests WHERE operation=?',('open_item.note:'+document['id'],)).fetchall()]
        note=max(notes,key=lambda n:n['revision']) if notes else None
        return {'id':document['id'],'document_id':document['id'],'project_id':document['project_id'],'number':document['number'],'buyer':value['buyer'],
            'due_date':value['due_date'],'gross':money(amount),'paid':money(paid),'credited':money(credit),'open':money(amount-paid-credit),
            'overdue_days':max(0,(today-due).days),'level':level,'last_reminder':last_reminder,
            'next_due_date':next_date.isoformat() if next_date else None,'days_until_next':(next_date-today).days if next_date else None,
            'delivery_state':delivery,'blocked_by_delivery':blocked,'rules_revision':rules['revision'],
            'note':note['note'] if note else '', 'note_revision':note['revision'] if note else 0,
            'can_revise_unsent':can_revise,'supersedes':mail['approval_version_id'] if can_revise else None,
            'supersession_conflict':self._document_conflict(document['id']) if current else False,
            'base_approval_id':current['id'] if can_revise else None,
            'eligible':rules['enabled'] and amount-paid-credit>0 and next_date is not None and today>=next_date and not blocked}

    def open_items(self,actor,project_id=None,sort='due_date',descending=False):
        require(self.office,actor,'finance.read',project_id);result=[]
        if sort not in ('due_date','open','next_due_date','level','number','last_reminder') or type(descending) is not bool:raise Problem(400,'Gültige OP-Sortierung erwartet')
        for row in self.db.execute("SELECT * FROM business_documents WHERE status='final' ORDER BY created_at,id").fetchall():
            if row['kind'] not in INVOICES or row['kind']=='credit_note' or project_id and row['project_id']!=project_id:continue
            try:require(self.office,actor,'finance.read',row['project_id'])
            except Problem as error:
                if error.status in (403,404):continue
                raise
            result.append(self._item(actor,row))
        result.sort(key=lambda item:((Decimal(item['open']) if sort=='open' else item[sort] if item[sort] is not None else (0 if sort=='level' else '')),item['id']),reverse=descending)
        return {'items':result,'currency':'EUR'}

    def note(self,actor,identifier,data):
        row=Documents(self.office)._row(actor,identifier,'finance.write');actor=require(self.office,actor,'finance.write',row['project_id'])
        if row['status']!='final' or row['kind'] not in INVOICES or row['kind']=='credit_note':raise Problem(409,'OP-Notiz benötigt eine finale Ausgangsrechnung')
        replay,digest=self._receipt(actor,data,'open_item.note:'+identifier)
        if replay:return replay
        current=self._item(actor,row)
        if data.get('revision')!=current['note_revision']:raise Problem(409,'OP-Notiz wurde geändert')
        value={'id':uuid.uuid4().hex,'document_id':identifier,'project_id':row['project_id'],'revision':current['note_revision']+1,
            'note':_text(data.get('note'),'OP-Notiz',4000,empty=True),'updated_at':self._now()}
        return self._remember(actor,data,'open_item.note:'+identifier,digest,value)

    def payments(self,actor):
        require(self.office,actor,'finance.read');result=[]
        for row in self.db.execute('SELECT * FROM business_payments ORDER BY created_at DESC,id').fetchall():
            allocations=[dict(r) for r in self.db.execute('SELECT document_id,amount FROM business_payment_allocations WHERE payment_id=?',(row['id'],)).fetchall()]
            current=require(self.office,actor,'finance.read')
            if not allocations and current['role']!='owner' and row['created_by']!=current['id']:continue
            try:
                for allocation in allocations:Documents(self.office)._row(actor,allocation['document_id'])
            except Problem as error:
                if error.status in (403,404):continue
                raise
            result.append({**dict(row),'allocations':allocations,'unallocated':money(Decimal(row['amount'])-sum((Decimal(r['amount']) for r in allocations),Decimal(0)))})
        return {'items':result}

    def record_payment(self,actor,data):
        actor=require(self.office,actor,'finance.write');allocations=data.get('allocations',[])
        financial_release(self.office)
        if not isinstance(allocations,list) or len(allocations)>100:raise Problem(400,'Zahlungszuordnungen erwartet')
        seen=set();assigned=Decimal(0)
        for allocation in allocations:
            if not isinstance(allocation,dict) or set(allocation)!={'document_id','amount'}:raise Problem(400,'Zahlungszuordnung erwartet')
            row=Documents(self.office)._row(actor,allocation['document_id'],'finance.write')
            if row['status']!='final' or row['kind'] not in INVOICES or row['kind']=='credit_note':raise Problem(409,'Zahlung nur einer finalen Rechnung zuordnen')
            if row['id'] in seen:raise Problem(400,'Rechnung doppelt zugeordnet')
            seen.add(row['id']);amount=decimal_value(allocation['amount'])
            if amount<=0 or money(amount)!=allocation['amount']:raise Problem(400,'Positive Centbeträge erwartet')
            assigned+=amount
        replay,digest=self._receipt(actor,data,'payment.record')
        if replay:return replay
        amount=decimal_value(data.get('amount'));kind=data.get('kind','receipt')
        if amount<=0 or assigned>amount or money(amount)!=data['amount'] or kind not in ('receipt','refund') or data.get('currency','EUR')!='EUR':raise Problem(400,'Positive EUR-Zahlung mit gültiger Zuordnung erwartet')
        source=_text(data.get('source_id'),'Stabile Zahlungsquellen-ID',200);booking=_date(data.get('booking_date'));reference=_text(data.get('reference',''),'Verwendungszweck',1000,empty=True)
        old=self.db.execute('SELECT * FROM business_payments WHERE source_id=?',(source,)).fetchone()
        if old:raise Problem(409,'Zahlungsquelle wurde bereits gebucht; bestehenden Beleg prüfen')
        if kind=='refund':
            for allocation in allocations:
                if Decimal(allocation['amount'])>self._payment_sum(allocation['document_id']):raise Problem(409,'Erstattung übersteigt die bestätigte Zahlung')
        identifier=uuid.uuid4().hex;now=self._now()
        self.db.execute('INSERT INTO business_payments(id,source_id,kind,amount,currency,booking_date,reference,reverses,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
            (identifier,source,kind,money(amount),'EUR',booking,reference,None,actor['id'],now))
        for allocation in allocations:self.db.execute('INSERT INTO business_payment_allocations(id,payment_id,document_id,amount,created_at) VALUES(?,?,?,?,?)',(uuid.uuid4().hex,identifier,allocation['document_id'],allocation['amount'],now))
        return self._remember(actor,data,'payment.record',digest,{'id':identifier,'kind':kind,'amount':money(amount),'allocations':allocations,'unallocated':money(amount-assigned),'status':'confirmed'})

    def propose(self,actor,data):
        actor=require(self.office,actor,'finance.write',data.get('project_id'));replay,digest=self._receipt(actor,data,'dunning.propose')
        if replay:return replay
        selected=data.get('document_ids')
        if selected is not None and (not isinstance(selected,list) or len(selected)>200):raise Problem(400,'Belegauswahl erwartet')
        items=self.open_items(actor,data.get('project_id'))['items'];rules=self.settings(actor);result=[]
        for item in items:
            if not(item['eligible'] or item['can_revise_unsent']) or selected is not None and item['id'] not in selected:continue
            try:require(self.office,actor,'finance.write',item['project_id'])
            except Problem as error:
                if error.status in (403,404):continue
                raise
            target_level=item['level'] if item['can_revise_unsent'] else item['level']+1
            rule=rules['levels'][target_level-1];fee=Decimal(rule['fee'])
            # Proposed interest is disclosed and must be explicitly approved;
            # the configured percentage is not a legal entitlement assertion.
            interest=Decimal(money(Decimal(item['open'])*Decimal(rule['interest_percent'])/Decimal(100)*Decimal(item['overdue_days'])/Decimal(365)))
            snapshot={'document_id':item['id'],'number':item['number'],'project_id':item['project_id'],'buyer':item['buyer'],
                'open':item['open'],'paid':item['paid'],'credited':item['credited'],'due_date':item['due_date'],'level':target_level,
                'rules_revision':rules['revision'],'rule':rule,'fee':money(fee),'interest':money(interest),
                'total':money(Decimal(item['open'])+fee+interest),'proposed_date':self.clock().date().isoformat()}
            issuer,issuer_revision=Documents(self.office)._settings_row()
            snapshot.update(issuer=issuer,issuer_revision=issuer_revision,sender=os.environ.get('SMARTPLAN_SMTP_FROM',''))
            if item['can_revise_unsent']:snapshot.update(supersedes=item['supersedes'],base_approval_id=item['base_approval_id'])
            payload=canonical(snapshot);identifier=uuid.uuid4().hex
            self.db.execute('INSERT INTO business_dunning_proposals(id,document_id,project_id,level,payload_json,payload_sha256,created_by,created_at) VALUES(?,?,?,?,?,?,?,?)',
                (identifier,item['id'],item['project_id'],target_level,payload,_hash(payload),actor['id'],self._now()))
            result.append({'id':identifier,'status':'needs_approval',**snapshot})
        return self._remember(actor,data,'dunning.propose',digest,{'items':result,'sent':False})

    def approve(self,actor,proposal_id,data):
        proposal=self.db.execute('SELECT * FROM business_dunning_proposals WHERE id=?',(_id(proposal_id),)).fetchone()
        if not proposal:raise Problem(404,'Mahnvorschlag nicht verfügbar')
        actor=require(self.office,actor,'finance.approve',proposal['project_id']);replay,digest=self._receipt(actor,data,'dunning.approve:'+proposal_id)
        financial_release(self.office)
        if replay:return replay
        if data.get('confirmation') is not True:raise Problem(400,'Betrag, Empfänger und Text ausdrücklich freigeben')
        snapshot=json.loads(proposal['payload_json']);doc=Documents(self.office)._row(actor,proposal['document_id']);fresh=self._item(actor,doc)
        _,issuer_revision=Documents(self.office)._settings_row()
        if snapshot['issuer_revision']!=issuer_revision or snapshot['sender']!=os.environ.get('SMARTPLAN_SMTP_FROM',''):raise Problem(409,'Briefpapier oder Absender wurden geändert; Mahnung erneut prüfen')
        replacement=bool(snapshot.get('supersedes'))
        valid_level=(fresh['can_revise_unsent'] and snapshot['level']==fresh['level'] and snapshot['supersedes']==fresh['supersedes'] and snapshot.get('base_approval_id')==fresh['base_approval_id']) if replacement else (fresh['eligible'] and snapshot['level']==fresh['level']+1)
        if not valid_level or snapshot['rules_revision']!=fresh['rules_revision'] or any(snapshot[k]!=fresh[k] for k in ('open','paid','credited')):raise Problem(409,'Zahlung, Mahnstufe oder Regeln wurden geändert; Vorschlag erneut prüfen')
        if snapshot['proposed_date']!=self.clock().date().isoformat():raise Problem(409,'Mahnvorschlag ist nicht mehr aktuell')
        recipient=snapshot['buyer'].get('email')
        if not recipient or '\r' in recipient or '\n' in recipient or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',recipient):raise Problem(409,'Gültigen Empfänger vor der Freigabe hinterlegen')
        identifier=uuid.uuid4().hex;outbox=uuid.uuid4().hex;operation=uuid.uuid4().hex;now=self._now();pdf=_dunning_pdf(snapshot)
        if replacement:
            original=self.db.execute('SELECT id FROM business_finance_outbox WHERE approval_id=?',(snapshot['base_approval_id'],)).fetchone()
            if not original:raise Problem(409,'Zu ersetzender Versandauftrag fehlt')
            mail=self._mail(original['id']);state=self._operation_state(mail['id'],mail['operation_id'])
            if mail['approval_version_id']!=snapshot['supersedes'] or state not in ('pending','failed','not_sent') or self._supersession_conflict(mail) or any(v['status']=='sent' for v in self._versions(mail)):raise Problem(409,'Vorherige Fassung ist bereits versandt oder unklar')
            if mail['edition']>=100:raise Problem(409,'Fassungslimit erreicht; Vorgang durch Betreiber prüfen lassen')
            if state!='not_sent':
                ordinal=self.db.execute('SELECT count(*) AS count FROM business_outbox_receipts WHERE outbox_id=?',(mail['id'],)).fetchone()['count']+1
                self.db.execute("INSERT INTO business_outbox_receipts(id,outbox_id,operation_id,outcome,ordinal,provider_receipt,created_by,created_at) VALUES(?,?,?,'not_sent',?,'superseded_before_delivery',?,?)",
                    (uuid.uuid4().hex,mail['id'],mail['operation_id'],ordinal,actor['id'],now))
            edition=mail['edition']+1
            self.db.execute('INSERT INTO business_dunning_editions(id,approval_id,edition,supersedes_id,proposal_id,operation_id,payload_json,payload_sha256,pdf,pdf_sha256,approved_by,approved_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                (identifier,mail['approval_id'],edition,mail['approval_version_id'],proposal_id,operation,proposal['payload_json'],proposal['payload_sha256'],pdf,_hash(pdf),actor['id'],now))
            return self._remember(actor,data,'dunning.approve:'+proposal_id,digest,{'id':identifier,'outbox_id':mail['id'],'operation_id':operation,'level':proposal['level'],'edition':edition,'status':'pending','sent':False})
        self.db.execute('INSERT INTO business_dunning_approvals(id,proposal_id,document_id,level,payload_json,payload_sha256,pdf,pdf_sha256,approved_by,approved_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
            (identifier,proposal_id,proposal['document_id'],proposal['level'],proposal['payload_json'],proposal['payload_sha256'],pdf,_hash(pdf),actor['id'],now))
        self.db.execute('INSERT INTO business_finance_outbox(id,approval_id,operation_id,recipient,payload_sha256,created_at) VALUES(?,?,?,?,?,?)',
            (outbox,identifier,operation,recipient,proposal['payload_sha256'],now))
        return self._remember(actor,data,'dunning.approve:'+proposal_id,digest,{'id':identifier,'outbox_id':outbox,'operation_id':operation,'level':proposal['level'],'edition':1,'status':'pending','sent':False})

    def outbox(self,actor):
        require(self.office,actor,'finance.read');result=[]
        from business_delivery import configuration
        try:configuration();configured=True
        except Problem:configured=False
        for row in self.db.execute('SELECT o.*,a.document_id,a.level FROM business_finance_outbox o JOIN business_dunning_approvals a ON a.id=o.approval_id ORDER BY o.created_at DESC,o.id').fetchall():
            try:Documents(self.office)._row(actor,row['document_id'])
            except Problem as error:
                if error.status in (403,404):continue
                raise
            active=self._mail(row['id'])
            result.append({**{key:active[key] for key in ('id','approval_id','document_id','level','recipient','payload_sha256','operation_id','created_at','edition','approval_version_id')},
                'status':self._operation_state(active['id'],active['operation_id']),'stage_state':self._stage_state(active),
                'supersession_conflict':self._supersession_conflict(active),'blocked_by_previous_conflict':self._document_conflict(active['document_id']),
                'editions':self._versions(active),'sender_configured':configured})
        return {'items':result}

    def proposal(self,actor,identifier):
        row=self.db.execute('SELECT * FROM business_dunning_proposals WHERE id=?',(_id(identifier),)).fetchone()
        if not row:raise Problem(404,'Mahnvorschlag nicht verfügbar')
        require(self.office,actor,'finance.read',row['project_id'])
        approved=self.db.execute('SELECT id FROM business_dunning_approvals WHERE proposal_id=?',(identifier,)).fetchone()
        if not approved:approved=self.db.execute('SELECT id FROM business_dunning_editions WHERE proposal_id=?',(identifier,)).fetchone()
        return {'id':identifier,'payload_sha256':row['payload_sha256'],'status':'approved' if approved else 'needs_approval',**json.loads(row['payload_json'])}

    def dunning_pdf(self,actor,identifier,*,outbox=False):
        if outbox:
            row=self._mail(_id(identifier))
            Documents(self.office)._row(actor,row['document_id'])
        else:
            proposal=self.proposal(actor,identifier)
            row=self.db.execute('SELECT * FROM business_dunning_approvals WHERE proposal_id=?',(identifier,)).fetchone()
            if not row:row=self.db.execute('SELECT * FROM business_dunning_editions WHERE proposal_id=?',(identifier,)).fetchone()
            if not row:return _dunning_pdf({**proposal,'preview':True})
        value=bytes(row['pdf'])
        if _hash(value)!=row['pdf_sha256']:raise Problem(409,'Mahnarchiv-Prüfsumme stimmt nicht')
        return value

    def record_delivery(self,actor,outbox_id,data):
        """Reconcile a real, operation-bound delivery proof; no network action."""
        row=self._mail(_id(outbox_id))
        document=Documents(self.office)._row(actor,row['document_id'],'finance.approve');actor=require(self.office,actor,'finance.approve',document['project_id'])
        replay,digest=self._receipt(actor,data,'outbox.receipt:'+outbox_id)
        if replay:return replay
        operation=data.get('operation_id');outcome=data.get('outcome')
        if operation not in {v['operation_id'] for v in self._versions(row)} or outcome not in ('sending','sent','failed','unknown','not_sent'):raise Problem(400,'Gebundene Versandquittung erwartet')
        state=self._operation_state(outbox_id,operation)
        if state=='sending' and outcome in ('sent','not_sent'):
            claim=self.db.execute("SELECT created_at FROM business_outbox_receipts WHERE outbox_id=? AND operation_id=? AND outcome='sending' ORDER BY ordinal DESC LIMIT 1",(outbox_id,operation)).fetchone()
            if not claim or (self.clock()-datetime.fromisoformat(claim['created_at'])).total_seconds()<120:raise Problem(409,'Laufenden Versand nicht manuell überschreiben')
            if data.get('confirmation') is not True or not data.get('provider_receipt'):raise Problem(409,'Überfälligen Versand nur mit tatsächlichem Nachweis abgleichen')
            ordinal=self.db.execute('SELECT count(*) AS count FROM business_outbox_receipts WHERE outbox_id=?',(outbox_id,)).fetchone()['count']+1
            self.db.execute("INSERT INTO business_outbox_receipts(id,outbox_id,operation_id,outcome,ordinal,provider_receipt,created_by,created_at) VALUES(?,?,?,'unknown',?,'stale_sender_claim',?,?)",
                (uuid.uuid4().hex,outbox_id,operation,ordinal,actor['id'],self._now()))
            state='unknown'
        allowed={'pending':{'sending','not_sent'},'sending':{'sent','failed','unknown'},'failed':{'sending','not_sent'},'unknown':{'sent','not_sent'},'not_sent':{'sending'},'sent':set()}
        acknowledge=(state=='sent' and outcome=='sent' and operation==row['operation_id'] and data.get('acknowledge_conflict') is True and self._supersession_conflict(row))
        if acknowledge:allowed['sent']={'sent'}
        if outcome not in allowed[state]:raise Problem(409,'Versandzustand erlaubt diesen Übergang nicht')
        receipt=data.get('provider_receipt')
        if outcome in ('sent','not_sent') and (data.get('confirmation') is not True or not receipt):raise Problem(400,'Tatsächlichen Versandnachweis ausdrücklich bestätigen')
        if receipt is not None:receipt=_text(receipt,'Quittungsreferenz',200)
        if acknowledge:receipt='reconciled_supersession:'+receipt
        if outcome=='sending' and data.get('adapter')!='test_sink':raise Problem(409,'Kein produktiver Versandadapter eingerichtet; Versand nicht behaupten')
        if outcome=='sending' and operation!=row['operation_id']:raise Problem(409,'Abgelöste Fassung nicht erneut starten')
        # The local synthetic sink is accepted only by explicit internal callers,
        # not by the public HTTP dispatch below.
        identifier=uuid.uuid4().hex
        ordinal=self.db.execute('SELECT count(*) AS count FROM business_outbox_receipts WHERE outbox_id=?',(outbox_id,)).fetchone()['count']+1
        self.db.execute('INSERT INTO business_outbox_receipts(id,outbox_id,operation_id,outcome,ordinal,provider_receipt,created_by,created_at) VALUES(?,?,?,?,?,?,?,?)',
            (identifier,outbox_id,operation,outcome,ordinal,receipt,actor['id'],self._now()))
        return self._remember(actor,data,'outbox.receipt:'+outbox_id,digest,{'id':identifier,'outbox_id':outbox_id,'operation_id':operation,'status':outcome})

    def deliver(self,actor,outbox_id,data,*,transport=None):
        from business_delivery import configured_transport,DeliveryReceipt
        with _transaction(self.office):
            row=self._mail(_id(outbox_id))
            document=Documents(self.office)._row(actor,row['document_id'],'finance.approve');fresh_actor=require(self.office,actor,'finance.approve',document['project_id'])
            financial_release(self.office)
            replay,digest=self._receipt(fresh_actor,data,'dunning.deliver:'+outbox_id)
            state=self._operation_state(outbox_id,row['operation_id'])
            if replay:
                previous_operation=replay.get('operation_id',row['original_operation_id']);previous_state=self._operation_state(outbox_id,previous_operation)
                return {'outbox_id':outbox_id,'operation_id':previous_operation,'status':previous_state,'accepted_by_server':previous_state=='sent','recipient_delivery_confirmed':False}
            if self._supersession_conflict(row) or any(v['status'] in ('sent','sending','unknown') for v in self._versions(row) if v['operation_id']!=row['operation_id']):raise Problem(409,'Quittung einer früheren Fassung zuerst verbindlich klären')
            if data.get('confirmation') is not True or data.get('payload_sha256')!=row['payload_sha256']:raise Problem(409,'Mahninhalt, Empfänger und PDF ausdrücklich bestätigen')
            if state not in ('pending','not_sent'):raise Problem(409,'Versand bereits gestartet oder unklar; zuerst verbindlich abgleichen')
            if state=='not_sent' and data.get('retry_confirmation') is not True:raise Problem(409,'Belegten Nichtversand und erneuten Versand ausdrücklich bestätigen')
            snapshot=json.loads(row['payload_json']);fresh=self._item(actor,document)
            if fresh['supersession_conflict']:raise Problem(409,'Quittung einer früheren Mahnfassung zuerst verbindlich klären')
            if not self.settings(actor)['enabled']:raise Problem(409,'Mahnwesen ist deaktiviert; keinen Versand starten')
            if any(snapshot[key]!=fresh[key] for key in ('open','paid','credited')) or Decimal(fresh['open'])<=0:raise Problem(409,'Zahlungsstand wurde nach Freigabe geändert; nicht versenden')
            if snapshot['sender']!=os.environ.get('SMARTPLAN_SMTP_FROM',''):raise Problem(409,'Freigegebener SMTP-Absender wurde geändert')
            pdf=bytes(row['pdf'])
            if _hash(pdf)!=row['pdf_sha256']:raise Problem(409,'Freigegebenes Mahn-PDF ist beschädigt')
            if transport is None:transport=configured_transport()
            self._remember(fresh_actor,data,'dunning.deliver:'+outbox_id,digest,{'outbox_id':outbox_id,'operation_id':row['operation_id']})
            ordinal=self.db.execute('SELECT count(*) AS count FROM business_outbox_receipts WHERE outbox_id=?',(outbox_id,)).fetchone()['count']+1
            self.db.execute("INSERT INTO business_outbox_receipts(id,outbox_id,operation_id,outcome,ordinal,created_by,created_at) VALUES(?,?,?,'sending',?,?,?)",
                (uuid.uuid4().hex,outbox_id,row['operation_id'],ordinal,fresh_actor['id'],self._now()))
            job={'operation_id':row['operation_id'],'recipient':row['recipient'],'expected_sender':snapshot['sender'],'subject':snapshot['rule']['subject']+' '+snapshot['number'],
                'text':snapshot['rule']['text']+'\n\nOffene Hauptforderung: '+_eur(snapshot['open'])+'\nFreigegebener Gesamtbetrag: '+_eur(snapshot['total']),
                'attachments':[{'filename':'Mahnung-'+snapshot['number']+'-'+str(snapshot['level'])+'.pdf','media_type':'application/pdf','bytes':pdf,'sha256':row['pdf_sha256']}]}
        try:
            with _transaction(self.office):
                require(self.office,actor,'finance.approve',document['project_id']);financial_release(self.office)
                active=self._mail(outbox_id)
                if active['operation_id']!=job['operation_id'] or self._supersession_conflict(active) or self._operation_state(outbox_id,job['operation_id'])!='sending':raise Problem(409,'Freigegebene Fassung wurde vor dem Versand abgelöst')
                current_balance=self._item(actor,Documents(self.office)._row(actor,row['document_id']))
                if current_balance['supersession_conflict']:raise Problem(409,'Frühere Mahnfassung ist unklar; keinen weiteren Versand starten')
                if any(snapshot[key]!=current_balance[key] for key in ('open','paid','credited')):raise Problem(409,'Zahlungsstand wurde vor dem Versand geändert')
        except Problem:
            with _transaction(self.office):
                if self._operation_state(outbox_id,job['operation_id'])=='sending':
                    next_ordinal=self.db.execute('SELECT count(*) AS count FROM business_outbox_receipts WHERE outbox_id=?',(outbox_id,)).fetchone()['count']+1
                    self.db.execute("INSERT INTO business_outbox_receipts(id,outbox_id,operation_id,outcome,ordinal,provider_receipt,created_by,created_at) VALUES(?,?,?,'failed',?,'authorization_changed_before_io',?,?)",
                        (uuid.uuid4().hex,outbox_id,job['operation_id'],next_ordinal,fresh_actor['id'],self._now()))
            raise
        try:receipt=transport.send(job)
        except Exception:receipt=DeliveryReceipt('unknown',job['operation_id'],error_code='delivery_unconfirmed')
        if not isinstance(receipt,DeliveryReceipt) or receipt.operation_id!=job['operation_id'] or receipt.status not in ('accepted','failed','unknown'):receipt=DeliveryReceipt('unknown',job['operation_id'],error_code='invalid_delivery_receipt')
        outcome='sent' if receipt.status=='accepted' else receipt.status
        with _transaction(self.office):
            next_ordinal=self.db.execute('SELECT count(*) AS count FROM business_outbox_receipts WHERE outbox_id=?',(outbox_id,)).fetchone()['count']+1
            current=self._operation_state(outbox_id,job['operation_id'])
            if current not in ('sending','unknown') and outcome!='sent':outcome='unknown'
            self.db.execute('INSERT INTO business_outbox_receipts(id,outbox_id,operation_id,outcome,ordinal,provider_receipt,created_by,created_at) VALUES(?,?,?,?,?,?,?,?)',
                (uuid.uuid4().hex,outbox_id,job['operation_id'],outcome,next_ordinal,receipt.receipt_id,fresh_actor['id'],self._now()))
        with _transaction(self.office):
            require(self.office,actor,'finance.approve',document['project_id'])
            financial_release(self.office)
            return {'outbox_id':outbox_id,'operation_id':job['operation_id'],'status':outcome,'accepted_by_server':outcome=='sent','recipient_delivery_confirmed':False}

    def capture_receipt(self,actor,data):
        actor=require(self.office,actor,'finance.write',data.get('project_id'));replay,digest=self._receipt(actor,data,'receipt.capture')
        if replay:return replay
        project_id=data.get('project_id')
        if data.get('media_id'):
            if data.get('original_base64') is not None:raise Problem(400,'Genau eine Originalquelle erwartet')
            from business_operations import verified_receipt_media
            media=verified_receipt_media(self.office,actor,data['media_id'],project_id)
            original=media['bytes'];filename=media['filename'];mime=media['media_type'];project_id=media['project_id']
        else:
            try:original=base64.b64decode(data.get('original_base64',''),validate=True)
            except (ValueError,TypeError):raise Problem(400,'Originaldatei erwartet') from None
            filename=data.get('filename');mime=data.get('media_type')
        filename=_text(filename,'Dateiname',200)
        if '/' in filename or '\\' in filename:raise Problem(400,'Einfacher Dateiname erwartet')
        if not 1<=len(original)<=20*1024*1024:raise Problem(413,'Originaldatei darf höchstens 20 MiB haben')
        suggestion={}
        if mime=='application/xml':
            from business_einvoice import inspect_invoice
            suggestion=inspect_invoice(original)
        elif mime=='application/pdf' and original.startswith(b'%PDF-'):pass
        elif mime in ('image/jpeg','image/png'):
            from PIL import Image
            try:
                with Image.open(io.BytesIO(original)) as image:
                    if image.format!=('JPEG' if mime=='image/jpeg' else 'PNG') or image.width*image.height>40_000_000:raise ValueError()
                    image.verify()
            except Exception:raise Problem(400,'Begrenztes Fotooriginal erwartet') from None
        else:raise Problem(415,'PDF, JPEG, PNG oder unterstütztes UBL-XML erwartet')
        identifier=uuid.uuid4().hex;value={'status':'needs_review','suggestion':suggestion,'note':_text(data.get('note',''),'Notiz',2000,empty=True),'sha256':_hash(original)}
        self.db.execute('INSERT INTO business_incoming_receipts(id,project_id,filename,media_type,original,sha256,payload_json,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
            (identifier,project_id,filename,mime,original,_hash(original),canonical(value),actor['id'],self._now()))
        return self._remember(actor,data,'receipt.capture',digest,{'id':identifier,'project_id':project_id,'filename':filename,'media_type':mime,**value})

    def _incoming(self,actor,identifier,permission='finance.read'):
        row=self.db.execute('SELECT * FROM business_incoming_receipts WHERE id=?',(_id(identifier),)).fetchone()
        if not row:raise Problem(404,'Eingangsbeleg nicht verfügbar')
        current=require(self.office,actor,permission,row['project_id'])
        if row['project_id'] is None and current['role']!='owner' and current['id']!=row['created_by']:raise Problem(403,'Dieser unzugeordnete Eingangsbeleg ist nicht freigegeben')
        return row

    def receipt(self,actor,identifier):
        row=self._incoming(actor,identifier);review=self.db.execute('SELECT * FROM business_receipt_reviews WHERE receipt_id=? ORDER BY revision DESC LIMIT 1',(identifier,)).fetchone()
        return {'id':identifier,'project_id':row['project_id'],'filename':row['filename'],'media_type':row['media_type'],'sha256':row['sha256'],
            'revision':review['revision'] if review else 0,'created_at':row['created_at'],**json.loads(row['payload_json']),
            **(json.loads(review['payload_json']) if review else {})}

    def receipts(self,actor,project_id=None):
        require(self.office,actor,'finance.read',project_id);result=[]
        for row in self.db.execute('SELECT id,project_id FROM business_incoming_receipts ORDER BY created_at DESC,id').fetchall():
            if project_id and row['project_id']!=project_id:continue
            try:result.append(self.receipt(actor,row['id']))
            except Problem as error:
                if error.status in (403,404):continue
                raise
        return {'items':result}

    def receipt_original(self,actor,identifier):
        row=self._incoming(actor,identifier);value=bytes(row['original'])
        if _hash(value)!=row['sha256']:raise Problem(409,'Originalprüfsumme stimmt nicht')
        return value,row['media_type']

    def review_receipt(self,actor,identifier,data):
        row=self._incoming(actor,identifier,'finance.approve');actor=require(self.office,actor,'finance.approve',row['project_id'])
        replay,digest=self._receipt(actor,data,'receipt.review:'+identifier)
        if replay:return replay
        current=self.receipt(actor,identifier)
        if data.get('revision')!=current['revision']:raise Problem(409,'Eingangsbeleg wurde bereits geprüft')
        allowed={'vendor','invoice_number','issue_date','net','tax','gross','currency','status','note'}
        value={k:v for k,v in data.items() if k not in ('request_id','revision')}
        if set(value)-allowed or value.get('status') not in ('reviewed','rejected') or value.get('currency','EUR')!='EUR':raise Problem(400,'Geprüfte EUR-Belegdaten erwartet')
        for key in ('vendor','invoice_number','note'):value[key]=_text(value.get(key,''),key,2000,empty=key=='note')
        value['issue_date']=_date(value.get('issue_date'));value['currency']='EUR'
        for key in ('net','tax','gross'):value[key]=money(decimal_value(value.get(key)))
        if Decimal(value['net'])+Decimal(value['tax'])!=Decimal(value['gross']):raise Problem(400,'Netto und Steuer ergeben nicht den Bruttobetrag')
        revision=current['revision']+1;payload=canonical(value)
        self.db.execute('INSERT INTO business_receipt_reviews(receipt_id,revision,payload_json,payload_sha256,reviewed_by,reviewed_at) VALUES(?,?,?,?,?,?)',
            (identifier,revision,payload,_hash(payload),actor['id'],self._now()))
        return self._remember(actor,data,'receipt.review:'+identifier,digest,self.receipt(actor,identifier))


def _dunning_pdf(value):
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Image
    from reportlab.lib.styles import getSampleStyleSheet
    from xml.sax.saxutils import escape
    result=io.BytesIO();styles=getSampleStyleSheet();story=[]
    if value.get('preview'):story.extend([Paragraph('VORSCHAU · noch nicht freigegeben',styles['Heading2']),Spacer(1,14)])
    seller=value['issuer']
    if seller.get('logo_base64'):
        logo=Image(io.BytesIO(base64.b64decode(seller['logo_base64'],validate=True)));logo._restrictSize(150,65);story.extend([logo,Spacer(1,12)])
    for line in (seller['company_name'],seller['address_line'],seller['postal_code']+' '+seller['city'],seller['email']+' · '+seller['phone']):
        story.extend([Paragraph(escape(line),styles['Normal']),Spacer(1,7)])
    story.append(Spacer(1,14))
    for line in (value['buyer']['name'],value['buyer'].get('address_line',''),value['buyer'].get('postal_code','')+' '+value['buyer'].get('city',''),
        value['rule']['name']+' · '+value['number'],'Fällig: '+value['due_date'],value['rule']['text'],
        'Offene Hauptforderung: '+_eur(value['open']),'Freigegebene Gebühr: '+_eur(value['fee']),
        'Freigegebener Zins: '+_eur(value['interest']),'Zu prüfen / zu zahlen: '+_eur(value['total'])):
        story.extend([Paragraph(escape(line).replace('\n','<br/>'),styles['Normal']),Spacer(1,9)])
    for line in ('IBAN: '+seller['iban']+' · BIC: '+seller['bic'],seller['footer']):story.extend([Paragraph(escape(line),styles['Normal']),Spacer(1,9)])
    SimpleDocTemplate(result).build(story);return result.getvalue()


for _name in ('settings','save_settings','open_items','note','payments','record_payment','propose','approve','outbox','proposal','dunning_pdf','record_delivery','capture_receipt','receipt','receipts','receipt_original','review_receipt'):
    setattr(Finance,_name,_atomic(getattr(Finance,_name)))
BusinessFinance=Finance


@_checked_integrity
def validate_integrity(office):
    db=office.db
    settings=db.execute("SELECT * FROM business_dunning_settings WHERE id='main'").fetchone()
    versions=db.execute('SELECT * FROM business_dunning_rule_versions ORDER BY revision').fetchall()
    if settings:
        if ([v['revision'] for v in versions]!=list(range(1,settings['revision']+1)) or not versions or versions[-1]['payload_json']!=settings['payload_json']):raise ValueError('Incomplete dunning rule history')
    elif versions:raise ValueError('Dunning history lacks current configuration')
    for row in db.execute('SELECT * FROM business_payments').fetchall():
        amount=decimal_value(row['amount'])
        assigned=sum((Decimal(r['amount']) for r in db.execute('SELECT amount FROM business_payment_allocations WHERE payment_id=?',(row['id'],)).fetchall()),Decimal(0))
        if amount<=0 or assigned>amount:raise ValueError('Invalid payment allocation ledger')
    for row in db.execute('SELECT a.*,d.status,d.kind FROM business_payment_allocations a JOIN business_documents d ON d.id=a.document_id').fetchall():
        amount=decimal_value(row['amount'])
        if amount<=0 or money(amount)!=row['amount'] or row['status']!='final' or row['kind'] not in INVOICES or row['kind']=='credit_note':raise ValueError('Invalid payment source document/cent amount')
    for table in ('business_dunning_rule_versions','business_dunning_proposals','business_dunning_approvals','business_dunning_editions','business_receipt_reviews'):
        for row in db.execute('SELECT * FROM '+table).fetchall():
            if _hash(row['payload_json'])!=row['payload_sha256']:raise ValueError('Invalid dunning snapshot hash')
            value=json.loads(row['payload_json'])
            if table=='business_dunning_rule_versions':_rules(value)
            if table in ('business_dunning_approvals','business_dunning_editions') and (_hash(bytes(row['pdf']))!=row['pdf_sha256'] or not bytes(row['pdf']).startswith(b'%PDF-')):raise ValueError('Invalid dunning PDF archive')
            if table=='business_dunning_approvals':
                original=db.execute('SELECT * FROM business_dunning_proposals WHERE id=?',(row['proposal_id'],)).fetchone()
                if not original or original['payload_json']!=row['payload_json'] or original['document_id']!=row['document_id'] or original['level']!=row['level']:raise ValueError('Approval differs from reviewed proposal')
            if table=='business_dunning_editions':
                original=db.execute('SELECT * FROM business_dunning_proposals WHERE id=?',(row['proposal_id'],)).fetchone()
                base=db.execute('SELECT * FROM business_dunning_approvals WHERE id=?',(row['approval_id'],)).fetchone()
                if (not original or not base or original['payload_json']!=row['payload_json'] or original['document_id']!=base['document_id'] or original['level']!=base['level']
                    or value.get('base_approval_id')!=base['id'] or value.get('supersedes')!=row['supersedes_id']):raise ValueError('Replacement edition differs from reviewed proposal')
            if table=='business_receipt_reviews':
                if value.get('status') not in ('reviewed','rejected') or value.get('currency')!='EUR' or decimal_value(value['net'])+decimal_value(value['tax'])!=decimal_value(value['gross']):raise ValueError('Invalid incoming review amounts')
    for document in db.execute('SELECT DISTINCT document_id FROM business_dunning_approvals').fetchall():
        levels=[r['level'] for r in db.execute('SELECT level FROM business_dunning_approvals WHERE document_id=? ORDER BY level',(document['document_id'],)).fetchall()]
        if levels!=list(range(1,len(levels)+1)):raise ValueError('Gap in approved dunning stages')
    for row in db.execute('SELECT o.*,a.payload_sha256 AS approved_hash FROM business_finance_outbox o JOIN business_dunning_approvals a ON a.id=o.approval_id').fetchall():
        if row['payload_sha256']!=row['approved_hash']:raise ValueError('Outbox differs from approved artifact')
        editions=db.execute('SELECT * FROM business_dunning_editions WHERE approval_id=? ORDER BY edition',(row['approval_id'],)).fetchall()
        if [e['edition'] for e in editions]!=list(range(2,len(editions)+2)) or len(editions)>99:raise ValueError('Incomplete dunning edition history')
        previous_id=row['approval_id'];previous_operation=row['operation_id'];operations={previous_operation}
        for edition in editions:
            if edition['supersedes_id']!=previous_id or not db.execute("SELECT 1 FROM business_outbox_receipts WHERE outbox_id=? AND operation_id=? AND outcome='not_sent'",(row['id'],previous_operation)).fetchone():raise ValueError('Replacement lacks a withdrawn unsent predecessor')
            previous_id=edition['id'];previous_operation=edition['operation_id'];operations.add(previous_operation)
        events=db.execute('SELECT * FROM business_outbox_receipts WHERE outbox_id=? ORDER BY ordinal',(row['id'],)).fetchall()
        states={op:'pending' for op in operations};allowed={'pending':{'sending','not_sent'},'sending':{'sent','failed','unknown'},'failed':{'sending','not_sent'},'unknown':{'sent','not_sent'},'not_sent':{'sending','sent','unknown'},'sent':{'sent','unknown'}}
        for index,event in enumerate(events,1):
            previous=states.get(event['operation_id'])
            restored=event['outcome']=='unknown' and event['provider_receipt']=='disaster_restore_delivery_unconfirmed' and previous not in ('sent','unknown')
            if event['ordinal']!=index or previous is None or not restored and event['outcome'] not in allowed[previous]:raise ValueError('Invalid finance delivery receipt journal')
            states[event['operation_id']]=event['outcome']
    for row in db.execute('SELECT * FROM business_incoming_receipts').fetchall():
        if _hash(bytes(row['original']))!=row['sha256']:raise ValueError('Incoming original digest mismatch')
        payload=json.loads(row['payload_json'])
        if payload.get('status')!='needs_review' or payload.get('sha256')!=row['sha256']:raise ValueError('Incoming original was not captured as a reviewable source')
        revisions=[r['revision'] for r in db.execute('SELECT revision FROM business_receipt_reviews WHERE receipt_id=? ORDER BY revision',(row['id'],)).fetchall()]
        if revisions!=list(range(1,len(revisions)+1)):raise ValueError('Gap in incoming review history')
    if isinstance(db,sqlite3.Connection):
        normalize=lambda s:re.sub(r'\s+',' ',s.replace('IF NOT EXISTS ','')).strip().lower()
        for sql in guard_statements('sqlite'):
            name=re.search(r'CREATE TRIGGER IF NOT EXISTS (\w+)',sql)[1]
            row=db.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",(name,)).fetchone()
            if not row or normalize(row[0])!=normalize(sql):raise ValueError('Missing or modified finance guard')
    else:
        from business_documents import _validate_pg_guards
        _validate_pg_guards(db,guard_statements('postgresql'))
    return True


def sanitize_after_restore(office):
    """Disaster restore loses external delivery certainty, never actual history."""
    changed=0;api=Finance(office)
    with _transaction(office):
        rows=office.db.execute('SELECT o.*,a.approved_by FROM business_finance_outbox o JOIN business_dunning_approvals a ON a.id=o.approval_id').fetchall()
        for row in rows:
            for version in api._versions(api._mail(row['id'])):
                if version['status'] in ('sent','unknown'):continue
                ordinal=office.db.execute('SELECT count(*) AS count FROM business_outbox_receipts WHERE outbox_id=?',(row['id'],)).fetchone()['count']+1
                office.db.execute("INSERT INTO business_outbox_receipts(id,outbox_id,operation_id,outcome,ordinal,provider_receipt,created_by,created_at) VALUES(?,?,?,'unknown',?,'disaster_restore_delivery_unconfirmed',?,?)",
                    (uuid.uuid4().hex,row['id'],version['operation_id'],ordinal,row['approved_by'],api._now()))
                changed+=1
    return {'dunning_mail_unknown':changed}


def methods(path):
    if path in ('/finance/open-items','/finance/outbox'):return 'GET'
    if re.fullmatch(r'/finance/open-items/[a-f0-9]{32}/note',path):return 'POST'
    if path in ('/finance/payments','/finance/dunning/settings'):return 'GET, POST'
    if path=='/finance/receipts':return 'GET, POST'
    if re.fullmatch(r'/finance/receipts/[a-f0-9]{32}',path):return 'GET, POST'
    if re.fullmatch(r'/finance/receipts/[a-f0-9]{32}/original',path):return 'GET'
    if path=='/finance/dunning/preview':return 'POST'
    if re.fullmatch(r'/finance/dunning/proposals/[a-f0-9]{32}/approve',path):return 'POST'
    if re.fullmatch(r'/finance/dunning/proposals/[a-f0-9]{32}(?:/pdf)?',path):return 'GET'
    if re.fullmatch(r'/finance/outbox/[a-f0-9]{32}/pdf',path):return 'GET'
    if re.fullmatch(r'/finance/outbox/[a-f0-9]{32}/reconcile',path):return 'POST'
    if re.fullmatch(r'/finance/outbox/[a-f0-9]{32}/deliver',path):return 'POST'
    return None


def dispatch(office,actor,path,method,data):
    allowed=methods(path)
    if not allowed:return None
    if method not in allowed.split(', '):raise Problem(405,'Methode nicht erlaubt')
    api=Finance(office)
    if method=='GET':data=data.get('_query',{})
    if path=='/finance/open-items':
        if data.get('descending','false') not in ('true','false'):raise Problem(400,'Sortierrichtung true/false erwartet')
        result=api.open_items(actor,data.get('project_id'),data.get('sort','due_date'),data.get('descending','false')=='true')
    elif path.startswith('/finance/open-items/'):result=api.note(actor,path.split('/')[3],data)
    elif path=='/finance/payments':result=api.payments(actor) if method=='GET' else api.record_payment(actor,data)
    elif path=='/finance/dunning/settings':result=api.settings(actor) if method=='GET' else api.save_settings(actor,data)
    elif path=='/finance/dunning/preview':result=api.propose(actor,data)
    elif path=='/finance/outbox':result=api.outbox(actor)
    elif path=='/finance/receipts':result=api.receipts(actor,data.get('project_id')) if method=='GET' else api.capture_receipt(actor,data)
    elif path.startswith('/finance/receipts/'):
        identifier=path.split('/')[3]
        if path.endswith('/original'):
            value,mime=api.receipt_original(actor,identifier);return Download(value,api.receipt(actor,identifier)['filename']),200,mime
        result=api.receipt(actor,identifier) if method=='GET' else api.review_receipt(actor,identifier,data)
    elif '/proposals/' in path:
        identifier=path.split('/')[4]
        if path.endswith('/pdf'):return Download(api.dunning_pdf(actor,identifier),'Mahnvorschau-'+identifier+'.pdf'),200,'application/pdf'
        result=api.proposal(actor,identifier) if method=='GET' else api.approve(actor,identifier,data)
    elif path.endswith('/pdf'):
        identifier=path.split('/')[3]
        return Download(api.dunning_pdf(actor,identifier,outbox=True),'Mahnung-'+identifier+'.pdf'),200,'application/pdf'
    elif path.endswith('/deliver'):result=api.deliver(actor,path.split('/')[3],data)
    else:
        if data.get('outcome') not in ('sent','not_sent'):raise Problem(409,'Öffentlich sind nur ausdrückliche, belegte Versandabgleiche erlaubt')
        result=api.record_delivery(actor,path.split('/')[3],data)
    return result,200,'application/json'
