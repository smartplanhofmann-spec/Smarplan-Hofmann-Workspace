"""Actual supplier returns and evidenced amendments of immutable purchase sources.

No supplier, payment, tax or project-cost effect is inferred. Supplier returns
are their own canonical stock-out journal, interleaved with native stock/counts.
"""
import base64
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP
import hashlib
import json
import re
import uuid

from core import Problem,canonical
from business_operations import Domain,decimal,identifier,iso_date,quantity,text,transaction

FEATURES=('purchase_changes',)
ID=r'[a-f0-9]{32}'
MAX_FILE=2*1024*1024
TABLES=('business_purchase_amendments','business_purchase_receipt_terms','business_supplier_returns',
        'business_supplier_return_lines','business_purchase_change_evidence','business_purchase_change_requests')
BASIS=('source_revision','expected_receipt_revision','expected_amendment_revision','expected_return_revision','source_sha256')
FIELDS={'amendments':('kind','reference','effective_on','reason','evidence_id','lines'),
        'supplier-returns':('reference','returned_on','reason','evidence_id','lines')}


def sha(value):return hashlib.sha256(value if isinstance(value,bytes) else canonical(value).encode()).hexdigest()
def shape(value,required,optional=()):
    if not isinstance(value,dict) or set(value)-set(required)-set(optional) or set(required)-set(value):raise Problem(400,'Unvollständige oder unbekannte Einkaufsänderungsfelder.')
def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA','BLOB'):raise ValueError('Unsupported storage type')
    return [
        f'''CREATE TABLE IF NOT EXISTS business_purchase_change_evidence(
        id TEXT PRIMARY KEY,order_id TEXT NOT NULL REFERENCES business_purchase_orders(id),filename TEXT NOT NULL,media_type TEXT NOT NULL,
        content {binary_type} NOT NULL,sha256 TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
        UNIQUE(order_id,filename))''',
        '''CREATE TABLE IF NOT EXISTS business_purchase_amendments(
        id TEXT PRIMARY KEY,order_id TEXT NOT NULL REFERENCES business_purchase_confirmations(order_id),revision INTEGER NOT NULL CHECK(revision>0),
        receipt_revision INTEGER NOT NULL CHECK(receipt_revision>=0),reference_key TEXT NOT NULL,evidence_id TEXT NOT NULL REFERENCES business_purchase_change_evidence(id),
        payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
        UNIQUE(order_id,revision),UNIQUE(order_id,reference_key))''',
        '''CREATE TABLE IF NOT EXISTS business_purchase_receipt_terms(
        receipt_id TEXT PRIMARY KEY REFERENCES business_purchase_receipts(id),amendment_id TEXT NOT NULL REFERENCES business_purchase_amendments(id),
        amendment_sha256 TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_supplier_returns(
        id TEXT PRIMARY KEY,order_id TEXT NOT NULL REFERENCES business_purchase_confirmations(order_id),revision INTEGER NOT NULL CHECK(revision>0),
        reference_key TEXT NOT NULL,evidence_id TEXT NOT NULL REFERENCES business_purchase_change_evidence(id),payload_json TEXT NOT NULL,
        sha256 TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
        UNIQUE(order_id,revision),UNIQUE(order_id,reference_key))''',
        '''CREATE TABLE IF NOT EXISTS business_supplier_return_lines(
        id TEXT PRIMARY KEY,return_id TEXT NOT NULL REFERENCES business_supplier_returns(id),receipt_id TEXT NOT NULL,line_index INTEGER NOT NULL,
        article_id TEXT NOT NULL,location_id TEXT NOT NULL REFERENCES business_stock_locations(id),quantity TEXT NOT NULL,
        unit_cost_net TEXT NOT NULL,book_value_net TEXT NOT NULL,sequence_number INTEGER NOT NULL UNIQUE CHECK(sequence_number>0),
        after_movement_sequence INTEGER NOT NULL CHECK(after_movement_sequence>=0),after_adjustment_sequence INTEGER NOT NULL CHECK(after_adjustment_sequence>=0),
        payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,UNIQUE(return_id,receipt_id,line_index),
        FOREIGN KEY(receipt_id,line_index) REFERENCES business_purchase_receipt_lines(receipt_id,line_index))''',
        '''CREATE TABLE IF NOT EXISTS business_purchase_change_requests(
        user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,operation TEXT NOT NULL,request_json TEXT NOT NULL,
        request_hash TEXT NOT NULL,result_json TEXT NOT NULL,result_sha256 TEXT NOT NULL,PRIMARY KEY(user_id,request_id))''',
    ]
def protected_tables():return TABLES
def runtime_privileges():return {table:('SELECT','INSERT') for table in TABLES}
def guard_statements(dialect):
    result=[]
    if dialect=='postgresql':result.append("CREATE OR REPLACE FUNCTION business_purchase_change_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable purchase change'; END; $$")
    conditions=('id=NEW.id OR (order_id=NEW.order_id AND (revision=NEW.revision OR reference_key=NEW.reference_key))',
        'receipt_id=NEW.receipt_id','id=NEW.id OR (order_id=NEW.order_id AND (revision=NEW.revision OR reference_key=NEW.reference_key))',
        'id=NEW.id OR sequence_number=NEW.sequence_number OR (return_id=NEW.return_id AND receipt_id=NEW.receipt_id AND line_index=NEW.line_index)',
        'id=NEW.id OR (order_id=NEW.order_id AND filename=NEW.filename)','user_id=NEW.user_id AND request_id=NEW.request_id')
    for table,condition in zip(TABLES,conditions):
        for action in ('UPDATE','DELETE'):
            name=table+'_'+action.lower()+'_guard'
            if dialect=='sqlite':result.append(f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable purchase change'); END")
            elif dialect=='postgresql':result.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION business_purchase_change_guard(); END IF; END $$")
            else:raise ValueError('Unsupported dialect')
        if dialect=='sqlite':result.append(f"CREATE TRIGGER IF NOT EXISTS {table}_replace_guard BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition}) BEGIN SELECT RAISE(ABORT,'immutable purchase change'); END")
    return result

def installed(office):
    from business_schema import _tables
    present=set(TABLES)&_tables(office)
    if present and present!=set(TABLES):raise Problem(503,'Einkaufsänderungen sind nur teilweise eingerichtet; Migration prüfen.')
    return bool(present)
def payload(row):
    value=json.loads(row['payload_json'])
    if sha(value)!=row['sha256']:raise Problem(500,'Unveränderlicher Einkaufsnachweis ist beschädigt.')
    return value
def amendments(office,order_id):
    if not installed(office):return []
    return [payload(row) for row in office.db.execute('SELECT * FROM business_purchase_amendments WHERE order_id=? ORDER BY revision',(order_id,))]
def return_lines(office):
    if not installed(office):return []
    result=[]
    for row in office.db.execute('SELECT * FROM business_supplier_return_lines ORDER BY sequence_number'):
        value=payload(row)
        if any(value[key]!=row[key] for key in ('id','return_id','receipt_id','line_index','article_id','location_id','quantity','unit_cost_net','book_value_net','sequence_number','after_movement_sequence','after_adjustment_sequence')):raise Problem(500,'Retourenjournal und Originalnachweis stimmen nicht überein.')
        result.append(value)
    return result
def returned_quantity(office,receipt_id,line_index):
    return sum((Decimal(line['quantity']) for line in return_lines(office) if line['receipt_id']==receipt_id and line['line_index']==line_index),Decimal(0))
def current_limits(office,order_id,source):
    versions=amendments(office,order_id)
    return ([Decimal(line['authorized_quantity']) for line in versions[-1]['lines']] if versions else [Decimal(line['quantity']) for line in source['items']],versions[-1] if versions else None)
def receipt_limits(office,receipt,source):
    if installed(office):
        row=office.db.execute('SELECT * FROM business_purchase_receipt_terms WHERE receipt_id=?',(receipt['id'],)).fetchone()
        if row:
            amendment=office.db.execute('SELECT * FROM business_purchase_amendments WHERE id=?',(row['amendment_id'],)).fetchone()
            if amendment is None or amendment['order_id']!=receipt['order_id'] or amendment['sha256']!=row['amendment_sha256'] or amendment['receipt_revision']>=receipt['receipt_revision']:raise ValueError('Invalid original receipt authorization')
            return [Decimal(line['authorized_quantity']) for line in payload(amendment)['lines']]
    return [Decimal(line['quantity']) for line in source['items']]
def authorize_receipt(office,order_id,body):
    versions=amendments(office,order_id);revision=versions[-1]['revision'] if versions else 0
    if (revision or 'expected_amendment_revision' in body) and (type(body.get('expected_amendment_revision')) is not int or body['expected_amendment_revision']!=revision):raise Problem(409,'Bestellung wurde ausdrücklich geändert; aktuelle Änderungsrevision prüfen.')
    return versions[-1] if versions else None
def bind_receipt(office,receipt_id,amendment):
    if amendment:office.db.execute('INSERT INTO business_purchase_receipt_terms VALUES(?,?,?)',(receipt_id,amendment['id'],sha(amendment)))

def validate_command_request(request,record,action):
    """A receipt authenticates the actual complete decision, not just its nonce."""
    from business_purchasing import _reference
    shape(request,(*BASIS,*FIELDS[action],'request_id','preview_sha256','confirmation'))
    identifier(request['request_id'])
    if request['confirmation'] is not True:raise ValueError('Original decision was not explicitly confirmed')
    expected=(record['source_revision'],record['receipt_revision'],record['amendment_revision'],record['return_revision'])
    if any(type(request[key]) is not int or request[key]!=value for key,value in zip(BASIS[:4],expected)):raise ValueError('Original decision basis differs')
    if any(request[key]!=record[key] for key in ('source_sha256','preview_sha256','evidence_id')):raise ValueError('Original decision proof differs')
    if _reference(request['reference'],'Belegreferenz')!=(record['reference'],record['reference_key']) or text(request['reason'],'Grund',3000,required=True)!=record['reason']:raise ValueError('Original decision text differs')
    date_key='effective_on' if action=='amendments' else 'returned_on'
    if iso_date(request[date_key])!=record[date_key]:raise ValueError('Original actual date differs')
    if not isinstance(request['lines'],list) or not 1<=len(request['lines'])<=200:raise ValueError('Invalid original decision lines')
    normalized=[];seen=set()
    for line in request['lines']:
        fields=('line_index','authorized_quantity') if action=='amendments' else ('receipt_id','line_index','quantity')
        shape(line,fields);index=line['line_index']
        if type(index) is not int or index<0:raise ValueError('Invalid original position index')
        key=index if action=='amendments' else (identifier(line['receipt_id']),index)
        if key in seen:raise ValueError('Duplicate original decision position')
        seen.add(key);field='authorized_quantity' if action=='amendments' else 'quantity'
        normalized.append(dict(line,**{field:quantity(decimal(line[field],positive=action!='amendments'))}))
    if action=='amendments':
        if request['kind']!=record['kind']:raise ValueError('Original change kind differs')
        normalized.sort(key=lambda line:line['line_index'])
        expected_lines=[{key:line[key] for key in ('line_index','authorized_quantity')} for line in record['lines']]
    else:
        normalized.sort(key=lambda line:(line['receipt_id'],str(line['line_index'])))
        expected_lines=[{key:line[key] for key in ('receipt_id','line_index','quantity')} for line in record['lines']]
    if normalized!=expected_lines:raise ValueError('Original decision quantities differ from accepted preview')

def validate_file_request(request,row):
    shape(request,('request_id','filename','media_type','content_base64_sha256'));identifier(request['request_id'])
    if text(request['filename'],'Dateiname',200,required=True)!=row['filename'] or request['media_type']!=row['media_type'] or request['content_base64_sha256']!=sha(base64.b64encode(bytes(row['content'])).decode()):raise ValueError('Original file request differs from stored original')

def mixed_stock_events(office):
    """Replay order, including counts and multi-line returns at one boundary."""
    from business_inventory_counts import adjustments
    movements=[dict(row) for row in office.db.execute('SELECT * FROM business_stock_movements ORDER BY sequence_number')]
    counts=adjustments(office);returned=return_lines(office);max_movement=len(movements)
    by_boundary={};last=(-1,-1)
    for row in counts:by_boundary.setdefault(row['after_movement_sequence'],[]).append(((row['sequence_number'],0,0),'count',row))
    for expected,row in enumerate(returned,1):
        boundary=(row['after_movement_sequence'],row['after_adjustment_sequence'])
        if row['sequence_number']!=expected or boundary<last or not 0<=boundary[0]<=max_movement or not 0<=boundary[1]<=len(counts):raise ValueError('Invalid supplier return journal boundaries')
        if any(c['sequence_number']<=boundary[1] and c['after_movement_sequence']>boundary[0] or c['sequence_number']>boundary[1] and c['after_movement_sequence']<boundary[0] for c in counts):raise ValueError('Supplier return crosses an inventory count boundary')
        last=boundary;by_boundary.setdefault(boundary[0],[]).append(((boundary[1],1,expected),'supplier_return',row))
    for boundary in range(max_movement+1):
        for _,kind,row in sorted(by_boundary.pop(boundary,[]),key=lambda value:value[0]):yield kind,row
        if boundary<max_movement:yield 'movement',movements[boundary]
    if by_boundary:raise ValueError('Unknown stock journal boundary')


class PurchaseChanges(Domain):
    def __init__(self,office,*,clock=None):
        super().__init__(office,clock=clock);self.db=office.db
        from business_purchasing import Purchasing
        self.purchasing=Purchasing(office,clock=clock);self.inventory=self.purchasing.inventory
    def authority(self,actor,order_id,action=None):
        order=self.purchasing._row(order_id);actor=self.access(actor,'inventory.read',order['project_id'])
        if action:
            actor=self.access(actor,'inventory.write',order['project_id'])
            actor=self.access(actor,'finance.approve' if action=='amendments' else 'finance.write',order['project_id'])
        return actor,order
    def financial(self,actor,project_id):
        try:self.access(actor,'finance.read',project_id);return True
        except Problem as error:
            if error.status!=403:raise
            return False
    def gate(self):
        from business_schema import require_capability,state
        require_capability(self.office,'business_purchase_changes')
        if state(self.office)['readonly']:raise Problem(423,'Einkaufsänderungen sind nur lesbar.')
    def active(self,actor):
        from business_organization import require_active
        require_active(self.office,actor,'/inventory/orders','business_inventory')
    def file(self,order_id,file_id):
        row=self.db.execute('SELECT * FROM business_purchase_change_evidence WHERE id=? AND order_id=?',(identifier(file_id),order_id)).fetchone()
        if row is None:raise Problem(404,'Originalbeleg gehört nicht zu dieser Bestellung.')
        if sha(bytes(row['content']))!=row['sha256']:raise Problem(409,'Originalbeleg ist beschädigt.')
        return row
    def files(self,order_id):
        return [dict(id=row['id'],order_id=order_id,filename=row['filename'],media_type=row['media_type'],size=row['size'],sha256=row['sha256']) for row in self.db.execute('SELECT id,filename,media_type,LENGTH(content) AS size,sha256 FROM business_purchase_change_evidence WHERE order_id=? ORDER BY created_at,id',(order_id,))]
    def records(self,kind,order_id):
        table='business_purchase_amendments' if kind=='amendments' else 'business_supplier_returns'
        return [payload(row) for row in self.db.execute('SELECT * FROM '+table+' WHERE order_id=? ORDER BY revision',(order_id,))]
    def record_view(self,value):return {k:v for k,v in value.items() if k not in ('proof','reference_key')}
    def public(self,actor,project_id,value):
        financial=self.financial(actor,project_id)
        hidden={'stock_value_net','unit_cost_net','cost_net','book_value_net','receipt_unit_cost_net','total_book_value_net'}
        def visit(item):
            if isinstance(item,list):return [visit(child) for child in item]
            if isinstance(item,dict):return {key:(financial if key=='financial_values_visible' else visit(child)) for key,child in item.items() if key not in ('proof','reference_key') and (financial or key not in hidden)}
            return item
        return visit(value)
    def native_receipts(self,order):
        source=self.purchasing._source(order)
        return [self.purchasing._receipt(row,source) for row in self.db.execute('SELECT * FROM business_purchase_receipts WHERE order_id=? ORDER BY receipt_revision',(order['id'],))]
    def stock_basis(self,location_id,article_id):
        from business_inventory_counts import adjustments
        on_hand,value,reserved=self.inventory._stock(location_id,article_id)
        rows=[dict(row) for row in self.db.execute('SELECT * FROM business_stock_movements WHERE article_id=? AND (from_location_id=? OR to_location_id=?) ORDER BY sequence_number',(article_id,location_id,location_id))]
        counts=[r for r in adjustments(self.office) if r['article_id']==article_id and r['location_id']==location_id]
        returned=[r for r in return_lines(self.office) if r['article_id']==article_id and r['location_id']==location_id]
        reservations=[dict(row) for row in self.db.execute('SELECT * FROM business_stock_reservations WHERE article_id=? AND location_id=? ORDER BY id',(article_id,location_id))]
        return dict(location_id=location_id,article_id=article_id,quantity=quantity(on_hand),value_net=quantity(value),reserved=quantity(reserved),movements_sha256=sha(rows),counts_sha256=sha(counts),returns_sha256=sha(returned),reservations_sha256=sha(reservations))
    def source(self,order):
        confirmation=self.purchasing._confirmation(order);receipts=self.native_receipts(order)
        keys=sorted({(r['location_id'],l['article_id']) for r in receipts for l in r['lines']})
        origins=[dict(r) for r in self.db.execute('SELECT o.asset_id,o.receipt_id,o.line_index,o.quantity,o.content_hash FROM business_asset_origins o JOIN business_purchase_receipts r ON r.id=o.receipt_id WHERE r.order_id=? ORDER BY o.asset_id',(order['id'],))]
        boundaries=dict(movement=self.db.execute('SELECT COALESCE(MAX(sequence_number),0) FROM business_stock_movements').fetchone()[0],
            count=self.db.execute('SELECT COALESCE(MAX(sequence_number),0) FROM business_inventory_adjustments').fetchone()[0],
            supplier_return=self.db.execute('SELECT COALESCE(MAX(sequence_number),0) FROM business_supplier_return_lines').fetchone()[0])
        return dict(order=self.purchasing._source(order),confirmation=dict(confirmation) if confirmation else None,receipts=receipts,journal_boundaries=boundaries,
            amendments=[dict(id=r['id'],revision=r['revision'],sha256=sha(r)) for r in self.records('amendments',order['id'])],
            returns=[dict(id=r['id'],revision=r['revision'],sha256=sha(r)) for r in self.records('supplier-returns',order['id'])],
            stocks=[self.stock_basis(location,article) for location,article in keys],origins=origins,files=self.files(order['id']))
    def capacity(self,receipt_id,line_index):
        bound=sum((Decimal(row['quantity']) for row in self.db.execute('SELECT quantity FROM business_asset_origins WHERE receipt_id=? AND line_index=?',(receipt_id,line_index))),Decimal(0))
        returned=returned_quantity(self.office,receipt_id,line_index)
        return returned,bound
    def _detail(self,actor,order_id):
        with transaction(self.office):
            actor,order=self.authority(actor,order_id);source=self.source(order);native=self.purchasing._order(order);items=[]
            original=self.purchasing._source(order)['items'];receipts=self.native_receipts(order)
            for entry in native['items']:
                returned=sum((returned_quantity(self.office,r['id'],entry['line_index']) for r in receipts),Decimal(0))
                items.append(dict(entry,original_ordered_quantity=original[entry['line_index']]['quantity'],authorized_quantity=entry['ordered_quantity'],returned_quantity=quantity(returned),retained_quantity=quantity(Decimal(entry['received_quantity'])-returned)))
            for receipt in receipts:
                for line in receipt['lines']:
                    returned,bound=self.capacity(receipt['id'],line['line_index']);stock,value,reserved=self.inventory._stock(receipt['location_id'],line['article_id'])
                    line.update(returned_quantity=quantity(returned),bound_quantity=quantity(bound),returnable_quantity=quantity(Decimal(line['quantity'])-returned-bound),free_quantity=quantity(stock-reserved),stock_value_net=quantity(value))
            value=dict(id=order_id,order_id=order_id,project_id=order['project_id'],supplier_name=order['supplier_name'],source_revision=order['revision'],receipt_revision=self.purchasing._receipt_revision(order_id),
                amendment_revision=len(source['amendments']),return_revision=len(source['returns']),source_sha256=sha(source),confirmation=native['confirmation'],items=items,receipts=receipts,
                amendments=[self.record_view(r) for r in self.records('amendments',order_id)],returns=[self.record_view(r) for r in self.records('supplier-returns',order_id)],files=self.files(order_id),financial_values_visible=True)
            return value
    def detail(self,actor,order_id):
        with transaction(self.office):
            value=self._detail(actor,order_id)
            return self.public(actor,value['project_id'],value)
    def raw_detail(self,actor,order_id):
        # Store one full immutable acceptance; the response is freshly redacted.
        return self._detail(actor,order_id)
    def historical_detail(self,record,action):
        """Rebuild the *accepted* view, never substitute today's balances."""
        from business_inventory_counts import adjustments
        proof=record['proof'];order=self.purchasing._row(record['order_id'])
        if proof['order']!=self.purchasing._source(order) or proof['receipts']!=self.native_receipts(order)[:record['receipt_revision']]:raise ValueError('Historical purchase source changed')
        versions={kind:self.records(kind,record['order_id']) for kind in ('amendments','supplier-returns')}
        prior={}
        for key,kind in (('amendments','amendments'),('returns','supplier-returns')):
            known={value['id']:value for value in versions[kind]};prior[key]=[]
            for header in proof[key]:
                value=known[header['id']]
                if sha(value)!=header['sha256'] or value['revision']!=header['revision']:raise ValueError('Historical change source changed')
                prior[key].append(value)
        after={key:list(values) for key,values in prior.items()}
        after['amendments' if action=='amendments' else 'returns'].append(record)
        boundaries=proof['journal_boundaries']
        if set(boundaries)!={'movement','count','supplier_return'} or any(type(v) is not int or v<0 for v in boundaries.values()):raise ValueError('Invalid historical journal cursor')
        all_movements=[dict(r) for r in self.db.execute('SELECT * FROM business_stock_movements ORDER BY sequence_number')]
        all_counts=adjustments(self.office);all_returns=return_lines(self.office)
        if any(boundaries[key]>len(rows) for key,rows in (('movement',all_movements),('count',all_counts),('supplier_return',all_returns))):raise ValueError('Historical journal cursor exceeds original ledger')
        movements=all_movements[:boundaries['movement']];counts=all_counts[:boundaries['count']];returned=all_returns[:boundaries['supplier_return']]
        after_returns=list(returned)
        if action=='supplier-returns':
            expected=list(range(boundaries['supplier_return']+1,boundaries['supplier_return']+len(record['lines'])+1))
            if [line['sequence_number'] for line in record['lines']]!=expected:raise ValueError('Accepted return is not at its reviewed journal boundary')
            after_returns.extend(record['lines'])
        new_source=json.loads(canonical(proof));new_source['amendments' if action=='amendments' else 'returns'].append(dict(id=record['id'],revision=record['revision'],sha256=sha(record)))
        new_source['journal_boundaries']['supplier_return']=len(after_returns)
        stocks={}
        for original in proof['stocks']:
            location,article=original['location_id'],original['article_id']
            moves=[r for r in movements if r['article_id']==article and location in (r['from_location_id'],r['to_location_id'])]
            changes=[r for r in counts if r['article_id']==article and r['location_id']==location]
            old_returns=[r for r in returned if r['article_id']==article and r['location_id']==location]
            if any(original[key]!=sha(rows) for key,rows in (('movements_sha256',moves),('counts_sha256',changes),('returns_sha256',old_returns))):raise ValueError('Historical stock journal prefix changed')
            amount=sum((Decimal(r['quantity'])*(1 if r['to_location_id']==location else -1) for r in moves),Decimal(0))+sum((Decimal(r['quantity_delta']) for r in changes),Decimal(0))-sum((Decimal(r['quantity']) for r in old_returns),Decimal(0))
            value=sum((Decimal(r['cost_net'])*(1 if r['to_location_id']==location else -1) for r in moves),Decimal(0))+sum((Decimal(r['value_delta_net']) for r in changes),Decimal(0))-sum((Decimal(r['book_value_net']) for r in old_returns),Decimal(0))
            if original['quantity']!=quantity(amount) or original['value_net']!=quantity(value) or not 0<=Decimal(original['reserved'])<=amount:raise ValueError('Historical stock totals differ from original journal')
            selected=[r for r in after_returns if r['article_id']==article and r['location_id']==location]
            new_amount=amount-sum((Decimal(r['quantity']) for r in selected if r['sequence_number']>boundaries['supplier_return']),Decimal(0))
            new_value=value-sum((Decimal(r['book_value_net']) for r in selected if r['sequence_number']>boundaries['supplier_return']),Decimal(0))
            stocks[(location,article)]=dict(original,quantity=quantity(new_amount),value_net=quantity(new_value),returns_sha256=sha(selected))
        new_source['stocks']=[stocks[(s['location_id'],s['article_id'])] for s in proof['stocks']]
        receipts=json.loads(canonical(proof['receipts']));items=[]
        def capacity(receipt_id,index):
            sent=sum((Decimal(l['quantity']) for r in after['returns'] for l in r['lines'] if l['receipt_id']==receipt_id and l['line_index']==index),Decimal(0))
            bound=sum((Decimal(o['quantity']) for o in proof['origins'] if o['receipt_id']==receipt_id and o['line_index']==index),Decimal(0))
            return sent,bound
        for index,original in enumerate(proof['order']['items']):
            article=original['article_snapshot'];authorized=Decimal(after['amendments'][-1]['lines'][index]['authorized_quantity']) if after['amendments'] else Decimal(original['quantity'])
            received=sum((Decimal(l['quantity']) for r in receipts for l in r['lines'] if l['line_index']==index),Decimal(0))
            sent=sum((capacity(r['id'],index)[0] for r in receipts),Decimal(0))
            items.append(dict(line_index=index,article_id=article['id'],article_name=article['name'],article_code=article.get('code',''),unit=article['unit'],ordered_quantity=quantity(authorized),received_quantity=quantity(received),remaining_quantity=quantity(authorized-received),original_ordered_quantity=original['quantity'],authorized_quantity=quantity(authorized),returned_quantity=quantity(sent),retained_quantity=quantity(received-sent)))
        for receipt in receipts:
            for line in receipt['lines']:
                sent,bound=capacity(receipt['id'],line['line_index']);stock=stocks[(receipt['location_id'],line['article_id'])]
                line.update(returned_quantity=quantity(sent),bound_quantity=quantity(bound),returnable_quantity=quantity(Decimal(line['quantity'])-sent-bound),free_quantity=quantity(Decimal(stock['quantity'])-Decimal(stock['reserved'])),stock_value_net=stock['value_net'])
        confirmation={k:proof['confirmation'][k] for k in ('order_reference','ordered_on','confirmed_by','confirmed_at')}
        return dict(id=record['order_id'],order_id=record['order_id'],project_id=record['project_id'],supplier_name=proof['order']['supplier_name'],source_revision=record['source_revision'],receipt_revision=record['receipt_revision'],amendment_revision=len(after['amendments']),return_revision=len(after['returns']),source_sha256=sha(new_source),confirmation=confirmation,items=items,receipts=receipts,amendments=[self.record_view(v) for v in after['amendments']],returns=[self.record_view(v) for v in after['returns']],files=proof['files'],financial_values_visible=True)
    def receipt(self,actor,operation,data,order):
        identifier(data['request_id']);safe=dict(data)
        if 'content_base64' in safe:safe['content_base64_sha256']=sha(safe.pop('content_base64'))
        fingerprint=sha([operation,safe]);row=self.db.execute('SELECT * FROM business_purchase_change_requests WHERE user_id=? AND request_id=?',(actor['id'],data['request_id'])).fetchone()
        if row:
            if row['operation']!=operation or row['request_hash']!=fingerprint:raise Problem(409,'Vorgangs-ID wurde bereits anders verwendet.')
            if json.loads(row['request_json'])!=safe:raise Problem(500,'Ursprünglicher Einkaufsauftrag ist beschädigt.')
            result=json.loads(row['result_json'])
            if sha(result)!=row['result_sha256']:raise Problem(500,'Ursprüngliche Einkaufsquittung ist beschädigt.')
            self.purchasing._confirmation(order)
            if operation.startswith('files:'):
                original=self.file(order['id'],result['id'])
                try:validate_file_request(safe,original)
                except (KeyError,TypeError,ValueError,Problem) as error:raise Problem(500,'Originalauftrag und Originaldatei stimmen nicht überein.') from error
            else:
                kind=operation.split(':')[0];record=next((r for r in self.records(kind,order['id']) if r['id']==result['record']['id']),None)
                if record is None or self.record_view(record)!=result['record']:raise Problem(500,'Originalquittung und Einkaufsnachweis stimmen nicht überein.')
                self.file(order['id'],record['evidence_id'])
                try:
                    validate_command_request(safe,record,kind)
                    if result['order']!=self.historical_detail(record,kind):raise ValueError('Historical acceptance differs')
                except (KeyError,TypeError,ValueError,StopIteration,Problem) as error:raise Problem(500,'Historische Einkaufsquittung stimmt nicht mit ihren Originalquellen überein.') from error
            return safe,fingerprint,result
        return safe,fingerprint,None
    def remember(self,actor,operation,safe,fingerprint,result):
        self.db.execute('INSERT INTO business_purchase_change_requests VALUES(?,?,?,?,?,?,?)',(actor['id'],safe['request_id'],operation,canonical(safe),fingerprint,canonical(result),sha(result)))
        return result
    def upload(self,actor,order_id,data):
        shape(data,('request_id','filename','media_type','content_base64'))
        with transaction(self.office):
            actor,order=self.authority(actor,order_id,'files');self.gate();operation='files:'+order_id
            safe,fingerprint,previous=self.receipt(actor,operation,data,order)
            if previous:return previous
            self.active(actor);filename=text(data['filename'],'Dateiname',200,required=True)
            if filename in ('.','..') or any(c in filename for c in '/\\') or any(ord(c)<32 or ord(c)==127 for c in filename):raise Problem(400,'Dateiname ohne Pfad oder Steuerzeichen wählen.')
            if data['media_type'] not in ('application/pdf','image/png','image/jpeg','application/xml','text/xml'):raise Problem(400,'PDF, PNG, JPEG oder XML-Original wählen.')
            if not isinstance(data['content_base64'],str) or len(data['content_base64'])>4*((MAX_FILE+2)//3):raise Problem(413,'Original darf höchstens 2 MiB umfassen.')
            try:raw=base64.b64decode(data['content_base64'],validate=True)
            except (ValueError,TypeError):raise Problem(400,'Ungültige Originaldatei.') from None
            if base64.b64encode(raw).decode()!=data['content_base64']:raise Problem(400,'Eindeutige kanonische Base64-Datei erwartet.')
            if not 0<len(raw)<=MAX_FILE:raise Problem(413,'Original benötigt 1 Byte bis 2 MiB.')
            if data['media_type']=='application/pdf' and not raw.startswith(b'%PDF-'):raise Problem(400,'PDF-Dateikopf fehlt.')
            files=self.files(order_id)
            if any(f['filename']==filename for f in files):raise Problem(409,'Originalname bereits vorhanden; Originale werden nicht ersetzt.')
            if len(files)>=100:raise Problem(413,'Höchstens 100 Originale je Bestellung.')
            result=dict(id=uuid.uuid4().hex,order_id=order_id,filename=filename,media_type=data['media_type'],size=len(raw),sha256=sha(raw))
            self.db.execute('INSERT INTO business_purchase_change_evidence VALUES(?,?,?,?,?,?,?,?)',(result['id'],order_id,filename,data['media_type'],raw,result['sha256'],actor['id'],self.now()))
            return self.remember(actor,operation,safe,fingerprint,result)
    def original(self,actor,order_id,file_id):
        with transaction(self.office):
            actor,order=self.authority(actor,order_id);self.access(actor,'finance.read',order['project_id']);row=self.file(order_id,file_id)
            from business_documents import Download
            return Download(bytes(row['content']),row['filename']),200,'application/octet-stream'
    def _preview(self,actor,order,action,data):
        from business_purchasing import _reference
        shape(data,(*BASIS,*FIELDS[action]));source=self.source(order)
        confirmation=self.purchasing._confirmation(order)
        if confirmation is None:raise Problem(409,'Tatsächlich extern erteilte Bestellung zuerst dokumentieren.')
        expected=(order['revision'],self.purchasing._receipt_revision(order['id']),len(source['amendments']),len(source['returns']))
        if any(type(data[key]) is not int or data[key]!=value for key,value in zip(BASIS[:4],expected)) or data['source_sha256']!=sha(source):raise Problem(409,'Bestellung, Bestand, Reservierung oder Herkunft wurde geändert; Vorschau neu prüfen.')
        reference,key=_reference(data['reference'],'Belegreferenz');reason=text(data['reason'],'Grund',3000,required=True);evidence=self.file(order['id'],data['evidence_id'])
        table='business_purchase_amendments' if action=='amendments' else 'business_supplier_returns'
        if self.db.execute('SELECT 1 FROM '+table+' WHERE order_id=? AND reference_key=?',(order['id'],key)).fetchone():raise Problem(409,'Dieser externe Beleg ist bereits dokumentiert.')
        date_key='effective_on' if action=='amendments' else 'returned_on';date=iso_date(data[date_key])
        if not confirmation['ordered_on']<=date<=self.now()[:10]:raise Problem(400,'Tatsächliches Datum muss zwischen Bestellung und heute liegen.')
        if not isinstance(data['lines'],list) or not 1<=len(data['lines'])<=200:raise Problem(400,'Eine bis 200 eindeutige Positionen wählen.')
        normalized=dict(data,reference=reference,reason=reason);lines=[];seen=set()
        current=self.purchasing._order(order);total=Decimal(0)
        if action=='amendments':
            if data['kind'] not in ('quantity_change','replacement','cancel_remaining'):raise Problem(400,'Konkrete Mengenänderung, Ersatzfreigabe oder Reststornierung wählen.')
            for line in data['lines']:
                shape(line,('line_index','authorized_quantity'));index=line['line_index']
                if type(index) is not int or not 0<=index<len(current['items']) or index in seen:raise Problem(400,'Jede ursprüngliche Bestellposition genau einmal wählen.')
                seen.add(index);item=current['items'][index];amount=decimal(line['authorized_quantity']);received=Decimal(item['received_quantity']);previous=Decimal(item['ordered_quantity'])
                if amount<received:raise Problem(409,'Mengenfreigabe darf bereits empfangene Ware nicht stornieren.')
                if data['kind']=='cancel_remaining' and amount!=received:raise Problem(400,'Reststornierung muss alle offenen Restmengen schließen.')
                if data['kind']=='replacement' and amount<previous:raise Problem(400,'Ersatzfreigabe darf keine andere Menge reduzieren.')
                lines.append({k:item[k] for k in ('line_index','article_id','article_name','unit','received_quantity')}|dict(previous_authorized_quantity=quantity(previous),authorized_quantity=quantity(amount),remaining_quantity=quantity(amount-received)))
            if len(seen)!=len(current['items']) or not any(l['authorized_quantity']!=l['previous_authorized_quantity'] for l in lines):raise Problem(400,'Vollständige tatsächliche Mengenänderung erforderlich.')
            lines.sort(key=lambda l:l['line_index']);normalized['lines']=[dict(line_index=l['line_index'],authorized_quantity=l['authorized_quantity']) for l in lines]
        else:
            native={r['id']:r for r in self.native_receipts(order)};stock={}
            for line in sorted(data['lines'],key=lambda l:(str(l.get('receipt_id','')),str(l.get('line_index',''))) if isinstance(l,dict) else ('','')):
                shape(line,('receipt_id','line_index','quantity'));receipt=native.get(identifier(line['receipt_id']));index=line['line_index']
                if receipt is None:raise Problem(404,'Wareneingang gehört nicht zu dieser Bestellung.')
                original=next((l for l in receipt['lines'] if l['line_index']==index),None)
                if type(index) is not int or original is None or (receipt['id'],index) in seen:raise Problem(400,'Eindeutige tatsächliche Lieferposition wählen.')
                seen.add((receipt['id'],index));amount=decimal(line['quantity'],positive=True)
                if date<receipt['received_on']:raise Problem(400,'Rücksendung darf nicht vor dem Wareneingang liegen.')
                self.inventory._location(receipt['location_id']);article=self.inventory._article(original['article_id'],allow_inactive=True)
                if article['unit']!=original['unit']:raise Problem(409,'Keine automatische Umdeutung der Liefereinheit.')
                returned,bound=self.capacity(receipt['id'],index);remaining=Decimal(original['quantity'])-returned-bound
                group=(receipt['location_id'],original['article_id'])
                if group not in stock:stock[group]=list(self.inventory._stock(*group))
                available,value,reserved=stock[group]
                if amount>remaining:raise Problem(409,'Retoure übersteigt die noch nicht zurückgesendete und nicht gerätegebundene Liefermenge.')
                if amount>available-reserved:raise Problem(409,'Nicht genügend freier Lagerbestand; Reservierung oder tatsächliche Projektrückgabe zuerst klären.')
                unit=value/available if available else Decimal(0);cost=value if amount==available else (unit*amount).quantize(Decimal('.0001'),rounding=ROUND_HALF_UP)
                if cost<0 or cost>Decimal('999999999999.9999'):raise Problem(409,'Retourenbewertung liegt außerhalb des unterstützten Bereichs.')
                lines.append(dict(receipt_id=receipt['id'],line_index=index,article_id=original['article_id'],article_name=original['article_name'],unit=original['unit'],location_id=receipt['location_id'],quantity=quantity(amount),received_quantity=original['quantity'],returned_quantity=quantity(returned),bound_quantity=quantity(bound),returnable_quantity=quantity(remaining),free_quantity=quantity(available-reserved),stock_quantity=quantity(available),stock_value_net=quantity(value),unit_cost_net=quantity(unit),book_value_net=quantity(cost),receipt_unit_cost_net=original['unit_cost_net']))
                stock[group]=[available-amount,value-cost,reserved];total+=cost
            normalized['lines']=[{k:line[k] for k in ('receipt_id','line_index','quantity')} for line in lines]
        preview=dict(order_id=order['id'],action=action,source_sha256=sha(source),values=normalized,lines=lines,financial_values_visible=True)
        if action=='supplier-returns':preview['total_book_value_net']=quantity(total)
        preview['preview_sha256']=sha(preview)
        return preview,source,key,evidence
    def preview(self,actor,order_id,action,data):
        with transaction(self.office):
            actor,order=self.authority(actor,order_id,action);preview,_,_,_=self._preview(actor,order,action,data)
            return self.public(actor,order['project_id'],preview)
    def confirm(self,actor,order_id,action,data):
        shape(data,(*BASIS,*FIELDS[action],'request_id','preview_sha256','confirmation'))
        with transaction(self.office):
            actor,order=self.authority(actor,order_id,action);self.gate();operation=action+':'+order_id
            safe,fingerprint,previous=self.receipt(actor,operation,data,order)
            if previous:return self.public(actor,order['project_id'],previous)
            self.active(actor)
            if data['confirmation'] is not True:raise Problem(400,'Tatsächliche Rücksendung bzw. belegte externe Vereinbarung ausdrücklich bestätigen.')
            values={key:data[key] for key in (*BASIS,*FIELDS[action])};preview,source,key,evidence=self._preview(actor,order,action,values)
            if data['preview_sha256']!=preview['preview_sha256']:raise Problem(409,'Vorschau stimmt nicht mit den unveränderten Eingaben überein.')
            record=dict(id=uuid.uuid4().hex,order_id=order_id,project_id=order['project_id'],revision=len(source['amendments' if action=='amendments' else 'returns'])+1,created_by=actor['id'],created_at=self.now(),source_sha256=sha(source),source_revision=order['revision'],receipt_revision=data['expected_receipt_revision'],amendment_revision=data['expected_amendment_revision'],return_revision=data['expected_return_revision'],reference=preview['values']['reference'],reference_key=key,reason=preview['values']['reason'],evidence_id=evidence['id'],evidence_sha256=evidence['sha256'],preview_sha256=preview['preview_sha256'],lines=preview['lines'],proof=source)
            if action=='amendments':
                record.update(kind=data['kind'],effective_on=data['effective_on'])
                self.db.execute('INSERT INTO business_purchase_amendments VALUES(?,?,?,?,?,?,?,?,?,?)',(record['id'],order_id,record['revision'],record['receipt_revision'],key,evidence['id'],canonical(record),sha(record),actor['id'],record['created_at']))
            else:
                record.update(returned_on=data['returned_on'],total_book_value_net=preview['total_book_value_net'])
                movement=self.db.execute('SELECT COALESCE(MAX(sequence_number),0) FROM business_stock_movements').fetchone()[0]
                count=self.db.execute('SELECT COALESCE(MAX(sequence_number),0) FROM business_inventory_adjustments').fetchone()[0]
                sequence=self.db.execute('SELECT COALESCE(MAX(sequence_number),0) FROM business_supplier_return_lines').fetchone()[0]
                record['lines']=[dict(line,id=uuid.uuid4().hex,return_id=record['id'],sequence_number=sequence+i+1,after_movement_sequence=movement,after_adjustment_sequence=count) for i,line in enumerate(record['lines'])]
                self.db.execute('INSERT INTO business_supplier_returns VALUES(?,?,?,?,?,?,?,?,?)',(record['id'],order_id,record['revision'],key,evidence['id'],canonical(record),sha(record),actor['id'],record['created_at']))
                for line in record['lines']:
                    fields=('id','return_id','receipt_id','line_index','article_id','location_id','quantity','unit_cost_net','book_value_net','sequence_number','after_movement_sequence','after_adjustment_sequence')
                    self.db.execute('INSERT INTO business_supplier_return_lines VALUES('+','.join('?' for _ in range(14))+')',tuple(line[k] for k in fields)+(canonical(line),sha(line)))
            result=dict(order=self.raw_detail(actor,order_id),record=self.record_view(record),financial_values_visible=True)
            self.office.audit(actor,'business.purchase.'+action,order_id)
            self.remember(actor,operation,safe,fingerprint,result)
            return self.public(actor,order['project_id'],result)


def methods(path):
    prefix=r'/purchasing/orders/'+ID
    if re.fullmatch(prefix+r'/changes',path) or re.fullmatch(prefix+r'/change-files/'+ID+r'/original',path):return 'GET'
    if re.fullmatch(prefix+r'/(?:change-files|amendments(?:/preview)?|supplier-returns(?:/preview)?)',path):return 'POST'
    return None

def dispatch(office,actor,path,method,data):
    allowed=methods(path)
    if allowed is None:return None
    if method!=allowed:raise Problem(405,'Methode nicht erlaubt.')
    if not isinstance(data,dict):raise Problem(400,'JSON-Objekt erwartet.')
    api=PurchaseChanges(office);query=data.get('_query',{});body={k:v for k,v in data.items() if k!='_query'}
    if query or method=='GET' and body:raise Problem(400,'Keine zusätzlichen Abfragekanäle erlaubt.')
    parts=path.split('/');order_id=parts[3];action=parts[4]
    if method=='GET':
        if action=='changes':return api.detail(actor,order_id),200,'application/json'
        return api.original(actor,order_id,parts[5])
    try:
        if action=='change-files':result=api.upload(actor,order_id,body)
        elif path.endswith('/preview'):result=api.preview(actor,order_id,action,body)
        else:result=api.confirm(actor,order_id,action,body)
    except Problem as error:
        if error.status==409 and isinstance(body.get('request_id'),str) and re.fullmatch(ID,body['request_id']):
            from business_foundation import _fresh
            with transaction(office):
                fresh=_fresh(office,actor)
                if not office.db.execute('SELECT 1 FROM business_purchase_change_requests WHERE user_id=? AND request_id=?',(fresh['id'],body['request_id'])).fetchone():raise Problem(409,error.message,request_resolution='not_accepted') from None
        raise
    return result,200,'application/json'


def validate_integrity(office):
    """Frozen originals, then shared chronological stock valuation and bindings."""
    api=PurchaseChanges(office);db=office.db
    try:
        from business_purchasing import _reference
        all_amendments={r['id']:payload(r) for r in db.execute('SELECT * FROM business_purchase_amendments')}
        all_returns={r['id']:payload(r) for r in db.execute('SELECT * FROM business_supplier_returns')}
        stored_lines=return_lines(office);list(mixed_stock_events(office))
        for file in db.execute('SELECT * FROM business_purchase_change_evidence'):
            if not 0<len(file['content'])<=MAX_FILE or sha(bytes(file['content']))!=file['sha256']:raise ValueError('Invalid purchase original bytes')
        for raw_order in db.execute('SELECT * FROM business_purchase_orders'):
            order=dict(raw_order);original=api.purchasing._source(order);confirmation=api.purchasing._confirmation(order)
            native=api.native_receipts(order);amended=api.records('amendments',order['id']);returned=api.records('supplier-returns',order['id'])
            for kind,records in (('amendments',amended),('supplier-returns',returned)):
                table='business_purchase_amendments' if kind=='amendments' else 'business_supplier_returns'
                for revision,record in enumerate(records,1):
                    row=db.execute('SELECT * FROM '+table+' WHERE id=?',(record['id'],)).fetchone();proof=record['proof']
                    if record['revision']!=revision or record['order_id']!=order['id'] or record['project_id']!=order['project_id'] or record['source_revision']!=order['revision'] or any(record[k]!=row[k] for k in ('id','order_id','revision','reference_key','evidence_id','created_by','created_at')):raise ValueError('Invalid change identity/version')
                    if kind=='amendments' and record['receipt_revision']!=row['receipt_revision']:raise ValueError('Changed amendment receipt boundary')
                    if record['source_sha256']!=sha(proof) or proof['order']!=original or proof['confirmation']!=(dict(confirmation) if confirmation else None):raise ValueError('Changed original purchase source')
                    if confirmation is None or _reference(record['reference'],'Belegreferenz')[1]!=record['reference_key']:raise ValueError('Invalid change reference')
                    if proof['receipts']!=native[:record['receipt_revision']] or len(proof['receipts'])!=record['receipt_revision']:raise ValueError('Changed receipt prefix')
                    for key,store,expected_revision in (('amendments',all_amendments,record['amendment_revision']),('returns',all_returns,record['return_revision'])):
                        if len(proof[key])!=expected_revision:raise ValueError('Invalid source revision')
                        for index,header in enumerate(proof[key],1):
                            old=store[header['id']]
                            if old['order_id']!=order['id'] or old['revision']!=index or header!={'id':old['id'],'revision':index,'sha256':sha(old)}:raise ValueError('Changed history source')
                    if record['amendment_revision' if kind=='amendments' else 'return_revision']!=revision-1:raise ValueError('Invalid predecessor')
                    evidence=api.file(order['id'],record['evidence_id'])
                    if evidence['sha256']!=record['evidence_sha256'] or not any(f['id']==evidence['id'] and f['sha256']==evidence['sha256'] for f in proof['files']):raise ValueError('Missing original evidence')
                    date_key='effective_on' if kind=='amendments' else 'returned_on'
                    if not confirmation['ordered_on']<=iso_date(record[date_key])<=record['created_at'][:10]:raise ValueError('Invalid actual change date')
                    text(record['reason'],'Grund',3000,required=True)
                    input_values=dict(source_revision=record['source_revision'],expected_receipt_revision=record['receipt_revision'],expected_amendment_revision=record['amendment_revision'],expected_return_revision=record['return_revision'],source_sha256=record['source_sha256'],reference=record['reference'],reason=record['reason'],evidence_id=record['evidence_id'],**{date_key:record[date_key]})
                    preview_lines=[]
                    if kind=='amendments':
                        previous=all_amendments[proof['amendments'][-1]['id']]['lines'] if proof['amendments'] else None
                        quantities=[sum((Decimal(l['quantity']) for r in proof['receipts'] for l in r['lines'] if l['line_index']==index),Decimal(0)) for index in range(len(original['items']))]
                        if len(record['lines'])!=len(original['items']) or record['kind'] not in ('quantity_change','replacement','cancel_remaining'):raise ValueError('Invalid amended positions')
                        changed=False
                        for index,line in enumerate(record['lines']):
                            article=original['items'][index]['article_snapshot'];before=Decimal(previous[index]['authorized_quantity']) if previous else Decimal(original['items'][index]['quantity']);amount=decimal(line['authorized_quantity'])
                            if amount<quantities[index] or record['kind']=='replacement' and amount<before or record['kind']=='cancel_remaining' and amount!=quantities[index]:raise ValueError('Invalid amended delivery capacity')
                            expected=dict(line_index=index,article_id=article['id'],article_name=article['name'],unit=article['unit'],received_quantity=quantity(quantities[index]),previous_authorized_quantity=quantity(before),authorized_quantity=quantity(amount),remaining_quantity=quantity(amount-quantities[index]))
                            if expected!=line:raise ValueError('Amended position differs from original')
                            changed=changed or amount!=before
                        if not changed:raise ValueError('Empty amendment')
                        preview_lines=record['lines'];input_values.update(kind=record['kind'],lines=[dict(line_index=l['line_index'],authorized_quantity=l['authorized_quantity']) for l in preview_lines])
                    else:
                        children=[l for l in stored_lines if l['return_id']==record['id']]
                        if not 1<=len(children)<=200 or record['lines']!=children:raise ValueError('Missing supplier stock-out originals')
                        for line in children:
                            receipt=next(r for r in proof['receipts'] if r['id']==line['receipt_id']);source=next(l for l in receipt['lines'] if l['line_index']==line['line_index'])
                            prior=sum((Decimal(l['quantity']) for l in stored_lines if l['receipt_id']==line['receipt_id'] and l['line_index']==line['line_index'] and l['sequence_number']<line['sequence_number']),Decimal(0))
                            bound=sum((Decimal(o['quantity']) for o in proof['origins'] if o['receipt_id']==line['receipt_id'] and o['line_index']==line['line_index']),Decimal(0))
                            for origin in proof['origins']:
                                actual=db.execute('SELECT content_hash FROM business_asset_origins WHERE asset_id=?',(origin['asset_id'],)).fetchone()
                                if actual is None or actual['content_hash']!=origin['content_hash']:raise ValueError('Changed source device origin')
                            capacity=Decimal(source['quantity'])-prior-bound;amount=decimal(line['quantity'],positive=True)
                            if amount>capacity or line['location_id']!=receipt['location_id'] or record['returned_on']<receipt['received_on'] or any(line[k]!=source[k] for k in ('article_id','article_name','unit')):raise ValueError('Supplier return exceeds actual source')
                            basis=next(s for s in proof['stocks'] if s['location_id']==line['location_id'] and s['article_id']==line['article_id'])
                            if line['received_quantity']!=source['quantity'] or line['returned_quantity']!=quantity(prior) or line['bound_quantity']!=quantity(bound) or line['returnable_quantity']!=quantity(capacity) or Decimal(line['free_quantity'])!=Decimal(line['stock_quantity'])-Decimal(basis['reserved']) or amount>Decimal(line['free_quantity']):raise ValueError('Changed return capacity or reservations')
                            if line['receipt_unit_cost_net']!=source['unit_cost_net']:raise ValueError('Changed original receipt price')
                            preview_lines.append({k:v for k,v in line.items() if k not in ('id','return_id','sequence_number','after_movement_sequence','after_adjustment_sequence')})
                        if quantity(sum((Decimal(l['book_value_net']) for l in children),Decimal(0)))!=record['total_book_value_net']:raise ValueError('Invalid return book value sum')
                        input_values['lines']=[{k:l[k] for k in ('receipt_id','line_index','quantity')} for l in preview_lines]
                    preview=dict(order_id=order['id'],action=kind,source_sha256=record['source_sha256'],values=input_values,lines=preview_lines,financial_values_visible=True)
                    if kind=='supplier-returns':preview['total_book_value_net']=record['total_book_value_net']
                    if sha(preview)!=record['preview_sha256']:raise ValueError('Changed accepted preview')
            for receipt in native:
                active=[a for a in amended if a['receipt_revision']<receipt['receipt_revision']]
                binding=db.execute('SELECT * FROM business_purchase_receipt_terms WHERE receipt_id=?',(receipt['id'],)).fetchone()
                if bool(active)!=bool(binding):raise ValueError('Missing original delivery authorization')
                if binding and (binding['amendment_id']!=active[-1]['id'] or binding['amendment_sha256']!=sha(active[-1])):raise ValueError('Wrong original delivery authorization')
                for line in receipt['lines']:
                    actual_returned,actual_bound=api.capacity(receipt['id'],line['line_index'])
                    if actual_returned+actual_bound>Decimal(line['quantity']):raise ValueError('Shared returned/device quantity exceeded')
        for row in db.execute('SELECT * FROM business_purchase_change_requests'):
            request=json.loads(row['request_json']);result=json.loads(row['result_json']);action,order_id=row['operation'].split(':')
            if request['request_id']!=row['request_id'] or sha([row['operation'],request])!=row['request_hash'] or sha(result)!=row['result_sha256']:raise ValueError('Invalid original change receipt')
            if action=='files':
                original_file=api.file(order_id,result['id']);validate_file_request(request,original_file)
                if result!=next(f for f in api.files(order_id) if f['id']==result['id']):raise ValueError('File receipt differs from original')
            else:
                original=(all_amendments if action=='amendments' else all_returns)[result['record']['id']]
                validate_command_request(request,original,action)
                if original['order_id']!=order_id or original['created_by']!=row['user_id'] or result['record']!=api.record_view(original) or result['order']['id']!=order_id or result['order']['project_id']!=original['project_id'] or request['preview_sha256']!=original['preview_sha256'] or request['source_sha256']!=original['source_sha256']:raise ValueError('Change receipt differs from original')
                if result['order']!=api.historical_detail(original,action):raise ValueError('Historical order receipt differs from original source prefixes')
    except (KeyError,TypeError,ValueError,IndexError,StopIteration,Problem,InvalidOperation) as error:raise ValueError('Invalid purchase change evidence') from error
    return True
