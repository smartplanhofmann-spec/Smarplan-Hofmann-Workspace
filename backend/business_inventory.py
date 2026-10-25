"""Append-only stock movements, explicit reservations and project cost snapshots.

Proposals never contact suppliers or imply a purchase has been sent.
"""
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import json
import re
import uuid

from core import Problem, canonical
from business_operations import Domain, decimal, identifier, money, quantity, request_schema, text


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BLOB','BYTEA'): raise ValueError('Unsupported binary column type')
    return request_schema('business_inventory_requests')+[
        '''CREATE TABLE IF NOT EXISTS business_stock_locations(
        id TEXT PRIMARY KEY, name TEXT NOT NULL, active INTEGER NOT NULL CHECK(active IN (0,1)), revision INTEGER NOT NULL,
        updated_by TEXT NOT NULL REFERENCES users(id), updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_stock_movements(
        id TEXT PRIMARY KEY, sequence_number INTEGER NOT NULL UNIQUE,
        kind TEXT NOT NULL CHECK(kind IN ('receive','issue','return','transfer')),
        article_id TEXT NOT NULL, article_snapshot_json TEXT NOT NULL,
        from_location_id TEXT REFERENCES business_stock_locations(id), to_location_id TEXT REFERENCES business_stock_locations(id),
        project_id TEXT REFERENCES projects(id), quantity TEXT NOT NULL, unit_cost_net TEXT NOT NULL, cost_net TEXT NOT NULL,
        reversal_of TEXT REFERENCES business_stock_movements(id), reservation_id TEXT,
        note TEXT NOT NULL, created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_stock_reservations(
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), article_id TEXT NOT NULL,
        location_id TEXT NOT NULL REFERENCES business_stock_locations(id), article_snapshot_json TEXT NOT NULL,
        quantity TEXT NOT NULL, picked_quantity TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('reserved','partial','picked','released')),
        revision INTEGER NOT NULL, created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL,
        updated_by TEXT NOT NULL REFERENCES users(id), updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_stock_reorder_rules(
        location_id TEXT NOT NULL REFERENCES business_stock_locations(id), article_id TEXT NOT NULL,
        minimum TEXT NOT NULL, target TEXT NOT NULL, updated_by TEXT NOT NULL REFERENCES users(id), updated_at TEXT NOT NULL,
        PRIMARY KEY(location_id,article_id))''',
        '''CREATE TABLE IF NOT EXISTS business_project_budgets(
        project_id TEXT PRIMARY KEY REFERENCES projects(id), revision INTEGER NOT NULL,
        material_net TEXT NOT NULL, labor_net TEXT NOT NULL, machine_net TEXT NOT NULL, other_net TEXT NOT NULL,
        updated_by TEXT NOT NULL REFERENCES users(id), updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_budget_versions(
        project_id TEXT NOT NULL REFERENCES projects(id), revision INTEGER NOT NULL, payload_json TEXT NOT NULL,
        PRIMARY KEY(project_id,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_change_orders(
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), title TEXT NOT NULL,
        amount_net TEXT NOT NULL, approved INTEGER NOT NULL CHECK(approved IN (0,1)),
        source_document_id TEXT, created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_purchase_orders(
        id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id), supplier_name TEXT NOT NULL,
        payload_json TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('draft','approved')),
        revision INTEGER NOT NULL, created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL,
        updated_by TEXT NOT NULL REFERENCES users(id), updated_at TEXT NOT NULL)''',
        'CREATE INDEX IF NOT EXISTS business_movements_article ON business_stock_movements(article_id,created_at,id)',
        'CREATE INDEX IF NOT EXISTS business_movements_project ON business_stock_movements(project_id,created_at,id)',
        'CREATE INDEX IF NOT EXISTS business_reservations_location ON business_stock_reservations(location_id,article_id,status)',
    ]


def runtime_privileges():
    return {
        'business_inventory_requests':('SELECT','INSERT'),
        'business_stock_movements':('SELECT','INSERT'),
        'business_budget_versions':('SELECT','INSERT'),
        'business_stock_locations':('SELECT','INSERT','UPDATE'),
        'business_stock_reservations':('SELECT','INSERT','UPDATE'),
        'business_stock_reorder_rules':('SELECT','INSERT','DELETE'),
        'business_project_budgets':('SELECT','INSERT','UPDATE'),
        'business_change_orders':('SELECT','INSERT','UPDATE'),
        'business_purchase_orders':('SELECT','INSERT','UPDATE'),
    }


class BusinessInventory(Domain):
    receipt_table='business_inventory_requests'

    def _article(self,article_id,*,allow_inactive=False):
        identifier(article_id,'Artikel-ID')
        row=self.office.db.execute('SELECT id,revision,payload_json FROM business_articles WHERE id=?',(article_id,)).fetchone()
        if not row: raise Problem(404,'Artikel nicht verfügbar')
        value=json.loads(row['payload_json'])
        if not allow_inactive and not value.get('active',True): raise Problem(409,'Artikel ist deaktiviert')
        if value.get('kind') not in ('material','machine'): raise Problem(400,'Nur physische Artikel können im Lager gebucht werden')
        return dict(value,id=row['id'],revision=row['revision'])

    def _location(self,location_id,*,require_active=True):
        row=self.office.db.execute('SELECT * FROM business_stock_locations WHERE id=?',(location_id,)).fetchone()
        if not row or (require_active and not row['active']): raise Problem(404,'Lagerort nicht verfügbar')
        return dict(row)

    def save_location(self,actor,data,location_id=None):
        def save(fresh,body):
            if set(body)-{'name','active','revision'}: raise Problem(400,'Unbekannte Lagerortfelder')
            old=self._location(location_id,require_active=False) if location_id else None
            if old: self.check_revision(body,old)
            name=text(body.get('name',old['name'] if old else None),'Lagerort',200,required=True)
            active=body.get('active',True if old is None else bool(old['active']))
            if type(active) is not bool: raise Problem(400,'Aktiv muss ein Wahrheitswert sein')
            if old and not active:
                articles=self.office.db.execute('SELECT DISTINCT article_id FROM business_stock_movements WHERE from_location_id=? OR to_location_id=?',(location_id,location_id)).fetchall()
                if any(any(value!=0 for value in (self._stock(location_id,row['article_id'])[0],self._stock(location_id,row['article_id'])[2])) for row in articles):
                    raise Problem(409,'Lagerort mit Bestand oder Reservierungen kann nicht deaktiviert werden')
            now=self.now()
            if old:
                self.office.db.execute('UPDATE business_stock_locations SET name=?,active=?,revision=revision+1,updated_by=?,updated_at=? WHERE id=?',(name,int(active),fresh['id'],now,location_id))
            else:
                identifier_=uuid.uuid4().hex
                self.office.db.execute('INSERT INTO business_stock_locations(id,name,active,revision,updated_by,updated_at) VALUES(?,?,?,1,?,?)',(identifier_,name,int(active),fresh['id'],now))
            row=self.office.db.execute('SELECT * FROM business_stock_locations WHERE id=?',(location_id or identifier_,)).fetchone()
            return dict(row,active=bool(row['active']))
        return self.write(actor,'inventory.write','business.location.saved',None,data,location_id,save)

    def list_locations(self,actor):
        with self.office.lock:
            self.access(actor,'inventory.read')
            return [dict(row,active=bool(row['active'])) for row in self.office.db.execute('SELECT * FROM business_stock_locations ORDER BY name,id').fetchall()]

    def _stock(self,location_id,article_id):
        on_hand,value=Decimal(0),Decimal(0)
        for row in self.office.db.execute('SELECT * FROM business_stock_movements WHERE article_id=? AND (from_location_id=? OR to_location_id=?) ORDER BY sequence_number',(article_id,location_id,location_id)).fetchall():
            sign=1 if row['to_location_id']==location_id else -1
            on_hand+=sign*Decimal(row['quantity']); value+=sign*Decimal(row['cost_net'])
        reserved=sum((Decimal(row['quantity'])-Decimal(row['picked_quantity']) for row in self.office.db.execute(
            "SELECT quantity,picked_quantity FROM business_stock_reservations WHERE article_id=? AND location_id=? AND status IN ('reserved','partial')",(article_id,location_id)).fetchall()),Decimal(0))
        return on_hand,value,reserved

    def balance(self,actor,location_id,article_id):
        with self.office.lock:
            fresh=self.access(actor,'inventory.read'); self._location(location_id,require_active=False)
            article=self._article(article_id,allow_inactive=True)
            on_hand,value,reserved=self._stock(location_id,article_id)
            result=dict(location_id=location_id,article_id=article_id,article_name=article['name'],article_code=article.get('code',''),unit=article['unit'],on_hand=quantity(on_hand),reserved=quantity(reserved),available=quantity(on_hand-reserved),currency='EUR')
            from business_foundation import permissions
            if 'finance.read' in permissions(self.office,fresh): result['stock_value_net']=money(value)
            return result

    def _movement(self,row,*,financial=True):
        value=dict(row); value['article_snapshot']=json.loads(value.pop('article_snapshot_json'))
        if not financial:
            for key in ('unit_cost_net','cost_net'): value.pop(key,None)
            for key in ('cost_price_net','unit_price_net'): value['article_snapshot'].pop(key,None)
        return value

    def _public(self,actor,value,project_id=None):
        """Re-filter replay receipts after a financial permission was withdrawn."""
        from business_foundation import require_permission
        try:
            require_permission(self.office,actor,'finance.read',project_id=project_id)
            return value
        except Problem as error:
            if error.status!=403: raise
        hidden={'unit_cost_net','cost_net','cost_price_net','unit_price_net','stock_value_net'}
        def redact(item):
            if isinstance(item,dict): return {key:redact(child) for key,child in item.items() if key not in hidden}
            if isinstance(item,list): return [redact(child) for child in item]
            return item
        return redact(value)

    def _post_move(self,fresh,body,*,reservation_id=None):
        if set(body)-{'kind','article_id','from_location_id','to_location_id','project_id','quantity','unit_cost_net','reversal_of','note'}:
            raise Problem(400,'Unbekannte Bewegungsfelder')
        kind=body.get('kind')
        if kind not in ('receive','issue','return','transfer'): raise Problem(400,'Unbekannte Lagerbewegung')
        article=self._article(body.get('article_id'),allow_inactive=kind in ('issue','return','transfer')); amount=decimal(body.get('quantity'),'Menge',positive=True)
        source=body.get('from_location_id'); destination=body.get('to_location_id'); project_id=body.get('project_id')
        if kind in ('issue','transfer'):
            self._location(source)
            if (kind=='issue' and destination is not None) or (kind=='transfer' and (not destination or destination==source)):
                raise Problem(400,'Ungültige Quell-/Ziellagerorte')
        elif source is not None or not destination: raise Problem(400,'Zugang benötigt nur einen Ziellagerort')
        if destination: self._location(destination)
        if kind in ('issue','return') and not project_id: raise Problem(400,'Entnahme/Rückgabe benötigt ein Projekt')
        if project_id: self.access(fresh,'inventory.write',project_id)
        if kind=='transfer' and project_id: raise Problem(400,'Umbuchung wird keinem Projekt berechnet')
        original=None
        if kind=='return':
            if 'unit_cost_net' in body: raise Problem(400,'Rückgabe übernimmt den historischen Entnahmepreis')
            original=self.office.db.execute("SELECT * FROM business_stock_movements WHERE id=? AND kind='issue' AND article_id=? AND project_id=?",(body.get('reversal_of'),article['id'],project_id)).fetchone()
            if not original: raise Problem(400,'Rückgabe benötigt die ursprüngliche Entnahme')
            already=sum((Decimal(row['quantity']) for row in self.office.db.execute('SELECT quantity FROM business_stock_movements WHERE reversal_of=?',(original['id'],)).fetchall()),Decimal(0))
            if already+amount>Decimal(original['quantity']): raise Problem(409,'Rückgabe übersteigt die Entnahme')
            unit_cost=Decimal(original['cost_net'])/Decimal(original['quantity'])
        elif kind=='receive':
            if 'unit_cost_net' in body: self.access(fresh,'finance.write',project_id)
            unit_cost=decimal(body.get('unit_cost_net',article.get('cost_price_net','0')),'Einstandspreis')
            if unit_cost<0: raise Problem(400,'Einstandspreis darf nicht negativ sein')
            if unit_cost==0 and 'unit_cost_net' not in body: raise Problem(400,'Einstandspreis fehlt; einen tatsächlichen Nullpreis ausdrücklich bestätigen')
        else:
            if 'unit_cost_net' in body or body.get('reversal_of'): raise Problem(400,'Entnahmepreise entstehen aus dem Lagerjournal')
            on_hand,stock_value,reserved=self._stock(source,article['id'])
            own=Decimal(0)
            if reservation_id:
                row=self.office.db.execute('SELECT quantity,picked_quantity FROM business_stock_reservations WHERE id=?',(reservation_id,)).fetchone()
                own=Decimal(row['quantity'])-Decimal(row['picked_quantity'])
            if on_hand<amount or on_hand-reserved+own<amount: raise Problem(409,'Nicht genügend freier Bestand')
            unit_cost=stock_value/on_hand if on_hand else Decimal(0)
        cost=(unit_cost*amount).quantize(Decimal('.0001'),rounding=ROUND_HALF_UP)
        if cost>Decimal('999999999999.9999'): raise Problem(400,'Bewegungswert überschreitet den unterstützten Bereich')
        if kind in ('issue','transfer') and amount==on_hand: cost=stock_value
        if kind=='return' and already+amount==Decimal(original['quantity']):
            returned_cost=sum((Decimal(row['cost_net']) for row in self.office.db.execute('SELECT cost_net FROM business_stock_movements WHERE reversal_of=?',(original['id'],)).fetchall()),Decimal(0))
            cost=Decimal(original['cost_net'])-returned_cost
        identifier_,now=uuid.uuid4().hex,self.now()
        sequence=self.office.db.execute('SELECT COALESCE(MAX(sequence_number),0)+1 AS next_number FROM business_stock_movements').fetchone()['next_number']
        self.office.db.execute('''INSERT INTO business_stock_movements(id,sequence_number,kind,article_id,article_snapshot_json,from_location_id,to_location_id,
            project_id,quantity,unit_cost_net,cost_net,reversal_of,reservation_id,note,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (identifier_,sequence,kind,article['id'],canonical(article),source,destination,project_id,quantity(amount),quantity(unit_cost),quantity(cost),original['id'] if original else None,reservation_id,text(body.get('note',''),'Notiz',2000),fresh['id'],now))
        return self._movement(self.office.db.execute('SELECT * FROM business_stock_movements WHERE id=?',(identifier_,)).fetchone())

    def move(self,actor,data):
        project_id=data.get('project_id') if isinstance(data,dict) else None
        result=self.write(actor,'inventory.write','business.stock.moved',project_id,data,None,lambda fresh,body:self._post_move(fresh,body))
        return self._public(actor,result,project_id)

    def reserve(self,actor,project_id,data):
        def reserve_(fresh,body):
            if set(body)-{'article_id','location_id','quantity'}: raise Problem(400,'Unbekannte Reservierungsfelder')
            article=self._article(body.get('article_id')); location=self._location(body.get('location_id')); amount=decimal(body.get('quantity'),'Menge',positive=True)
            on_hand,_,reserved=self._stock(location['id'],article['id'])
            if on_hand-reserved<amount: raise Problem(409,'Nicht genügend freier Bestand')
            identifier_,now=uuid.uuid4().hex,self.now()
            self.office.db.execute('''INSERT INTO business_stock_reservations(id,project_id,article_id,location_id,article_snapshot_json,quantity,picked_quantity,status,revision,created_by,created_at,updated_by,updated_at)
                VALUES(?,?,?,?,?,?,'0.0000','reserved',1,?,?,?,?)''',(identifier_,project_id,article['id'],location['id'],canonical(article),quantity(amount),fresh['id'],now,fresh['id'],now))
            return self._reservation(self.row('business_stock_reservations',project_id,identifier_))
        return self._public(actor,self.write(actor,'inventory.write','business.stock.reserved',project_id,data,None,reserve_),project_id)

    def _reservation(self,row):
        value=dict(row); value['article_snapshot']=json.loads(value.pop('article_snapshot_json'))
        value['remaining_quantity']=quantity(Decimal(row['quantity'])-Decimal(row['picked_quantity'])) if row['status']!='released' else '0.0000'
        return value

    def release_reservation(self,actor,project_id,reservation_id,data):
        def release(fresh,body):
            row=self.row('business_stock_reservations',project_id,reservation_id)
            self.check_revision(body,row)
            if set(body)!={'revision'}: raise Problem(400,'Unerwartete Freigabefelder')
            if row['status']=='picked': raise Problem(409,'Reservierung ist vollständig entnommen')
            self.office.db.execute("UPDATE business_stock_reservations SET status='released',revision=revision+1,updated_by=?,updated_at=? WHERE id=?",(fresh['id'],self.now(),reservation_id))
            return self._reservation(self.row('business_stock_reservations',project_id,reservation_id))
        return self._public(actor,self.write(actor,'inventory.write','business.stock.reservation_released',project_id,data,reservation_id,release),project_id)

    def pick(self,actor,project_id,data):
        def pick_(fresh,body):
            items=body.get('items')
            if set(body)!={'items'} or not isinstance(items,list) or not 1<=len(items)<=100: raise Problem(400,'Kommissionierung benötigt Positionen')
            seen=set(); movements=[]
            for item in items:
                if not isinstance(item,dict) or set(item)!={'reservation_id','quantity'} or item['reservation_id'] in seen: raise Problem(400,'Ungültige Kommissionierungsposition')
                seen.add(item['reservation_id']); row=self.row('business_stock_reservations',project_id,item['reservation_id'])
                amount=decimal(item['quantity'],'Entnahmemenge',positive=True); remaining=Decimal(row['quantity'])-Decimal(row['picked_quantity'])
                if row['status'] not in ('reserved','partial') or amount>remaining: raise Problem(409,'Reservierte Menge reicht nicht aus')
                movement=self._post_move(fresh,dict(kind='issue',article_id=row['article_id'],from_location_id=row['location_id'],project_id=project_id,quantity=item['quantity']),reservation_id=row['id'])
                picked=Decimal(row['picked_quantity'])+amount
                self.office.db.execute('UPDATE business_stock_reservations SET picked_quantity=?,status=?,revision=revision+1,updated_by=?,updated_at=? WHERE id=?',(quantity(picked),'picked' if picked==Decimal(row['quantity']) else 'partial',fresh['id'],self.now(),row['id']))
                movements.append(movement)
            return dict(id=uuid.uuid4().hex,project_id=project_id,status='picked',items=movements,created_at=self.now())
        return self._public(actor,self.write(actor,'inventory.write','business.stock.picked',project_id,data,None,pick_),project_id)

    def lookup(self,actor,code):
        with self.office.lock:
            fresh=self.access(actor,'inventory.read'); code=text(code,'Code',200,required=True)
            matches=[]
            for row in self.office.db.execute('SELECT id,revision,payload_json FROM business_articles').fetchall():
                value=json.loads(row['payload_json'])
                if value.get('active',True) and value.get('code')==code:
                    matches.append(dict(value,id=row['id'],revision=row['revision']))
            if not matches: raise Problem(404,'Code nicht gefunden')
            if len(matches)!=1: raise Problem(409,'Code ist mehreren Artikeln zugeordnet')
            return self._public(fresh,matches[0])

    def set_reorder_rule(self,actor,data):
        def save(fresh,body):
            if set(body)!={'location_id','article_id','minimum','target'}: raise Problem(400,'Ungültige Nachbestellregel')
            self._location(body['location_id']); self._article(body['article_id'])
            minimum=decimal(body['minimum'],'Meldebestand'); target=decimal(body['target'],'Zielbestand')
            if minimum<0 or target<minimum: raise Problem(400,'Zielbestand muss mindestens dem Meldebestand entsprechen')
            self.office.db.execute('DELETE FROM business_stock_reorder_rules WHERE location_id=? AND article_id=?',(body['location_id'],body['article_id']))
            self.office.db.execute('INSERT INTO business_stock_reorder_rules(location_id,article_id,minimum,target,updated_by,updated_at) VALUES(?,?,?,?,?,?)',(body['location_id'],body['article_id'],quantity(minimum),quantity(target),fresh['id'],self.now()))
            return dict(body,id=body['location_id']+':'+body['article_id'],updated_at=self.now())
        return self.write(actor,'inventory.write','business.stock.reorder_rule',None,data,None,save)

    def reorder_suggestions(self,actor):
        with self.office.lock:
            self.access(actor,'inventory.read'); result=[]
            for row in self.office.db.execute('SELECT * FROM business_stock_reorder_rules ORDER BY location_id,article_id').fetchall():
                on_hand,_,reserved=self._stock(row['location_id'],row['article_id']); available=on_hand-reserved
                if available<Decimal(row['minimum']): result.append(dict(location_id=row['location_id'],article_id=row['article_id'],available=quantity(available),suggested_quantity=quantity(Decimal(row['target'])-available),status='proposal'))
            return result

    def save_budget(self,actor,project_id,data):
        def save(fresh,body):
            fields=('material_net','labor_net','machine_net','other_net')
            if set(body)-set(fields)-{'revision'}: raise Problem(400,'Unbekannte Budgetfelder')
            old=self.office.db.execute('SELECT * FROM business_project_budgets WHERE project_id=?',(project_id,)).fetchone()
            if old: self.check_revision(body,old)
            amounts={field:money(decimal(body.get(field,old[field] if old else '0'),'Budget')) for field in fields}
            if any(Decimal(value)<0 for value in amounts.values()): raise Problem(400,'Budget darf nicht negativ sein')
            revision=old['revision']+1 if old else 1; now=self.now()
            if old:
                self.office.db.execute('UPDATE business_project_budgets SET revision=?,material_net=?,labor_net=?,machine_net=?,other_net=?,updated_by=?,updated_at=? WHERE project_id=?',
                    (revision,*(amounts[field] for field in fields),fresh['id'],now,project_id))
            else:
                self.office.db.execute('INSERT INTO business_project_budgets(project_id,revision,material_net,labor_net,machine_net,other_net,updated_by,updated_at) VALUES(?,?,?,?,?,?,?,?)',(project_id,revision,*(amounts[field] for field in fields),fresh['id'],now))
            result=dict(id=project_id,project_id=project_id,revision=revision,**amounts,currency='EUR',updated_by=fresh['id'],updated_at=now)
            self.office.db.execute('INSERT INTO business_budget_versions(project_id,revision,payload_json) VALUES(?,?,?)',(project_id,revision,canonical(result)))
            return result
        return self.write(actor,'finance.write','business.budget.saved',project_id,data,project_id,save)

    def add_change_order(self,actor,project_id,data):
        def add(fresh,body):
            if set(body)-{'title','amount_net','approved','source_document_id'}: raise Problem(400,'Unbekannte Nachtragsfelder')
            approved=body.get('approved',False)
            if type(approved) is not bool: raise Problem(400,'Freigabe muss ein Wahrheitswert sein')
            if approved: self.access(fresh,'finance.approve',project_id)
            amount=decimal(body.get('amount_net'),'Nachtrag',places=2)
            source=body.get('source_document_id')
            if source is not None:
                identifier(source,'Beleg-ID')
                # Only explicit same-project commercial references; no inferred acceptance.
                row=self.office.db.execute('SELECT project_id FROM business_documents WHERE id=?',(source,)).fetchone()
                if not row or row['project_id']!=project_id: raise Problem(400,'Belegreferenz gehört nicht zum Projekt')
            identifier_,now=uuid.uuid4().hex,self.now(); title=text(body.get('title'),'Nachtrag',300,required=True)
            self.office.db.execute('INSERT INTO business_change_orders(id,project_id,title,amount_net,approved,source_document_id,created_by,created_at) VALUES(?,?,?,?,?,?,?,?)',(identifier_,project_id,title,money(amount),int(approved),source,fresh['id'],now))
            return dict(id=identifier_,event='change_order.created',project_id=project_id,title=title,amount_net=money(amount),approved=approved,source_document_id=source,revision=1,created_by=fresh['id'],created_at=now,updated_at=now,approved_by=fresh['id'] if approved else None,approved_at=now if approved else None)
        return self.write(actor,'finance.write','business.change_order.created',project_id,data,None,add)

    def _change(self,row):
        receipts=[]
        for receipt in self.office.db.execute('SELECT user_id,result_json FROM business_inventory_requests WHERE result_json LIKE ?',('%"id":"'+row['id']+'"%',)).fetchall():
            value=json.loads(receipt['result_json'])
            if value.get('id')==row['id'] and value.get('event') in ('change_order.created','change_order.approved'):
                receipts.append((receipt['user_id'],value))
        creations=[value for user,value in receipts if value['event']=='change_order.created' and value.get('created_by')==user]
        approvals=[value for user,value in receipts if value['event']=='change_order.approved' and value.get('approved_by')==user]
        if len(creations)!=1 or len(approvals)>1: raise ValueError('Missing change-order provenance')
        created=creations[0]
        fields=('id','project_id','title','amount_net','source_document_id','created_by','created_at')
        if any(created.get(field)!=row[field] for field in fields): raise ValueError('Change order differs from its proposal')
        result=approvals[0] if approvals else created
        if approvals and (created['approved'] or result.get('revision')!=2 or any(result.get(field)!=created[field] for field in fields)):
            raise ValueError('Invalid change-order approval')
        if bool(row['approved'])!=result.get('approved'): raise ValueError('Unproven change-order approval')
        return result

    def approve_change_order(self,actor,project_id,change_id,data):
        def approve(fresh,body):
            if set(body)!={'revision'} or type(body['revision']) is not int: raise Problem(400,'Nachtragsversion erwartet')
            row=self.row('business_change_orders',project_id,change_id); previous=self._change(row)
            if previous['approved'] or body['revision']!=previous['revision']: raise Problem(409,'Nachtrag wurde geändert oder bereits freigegeben')
            changed=self.office.db.execute('UPDATE business_change_orders SET approved=1 WHERE id=? AND approved=0',(change_id,))
            if changed.rowcount!=1: raise Problem(409,'Nachtrag bereits freigegeben')
            now=self.now()
            return dict(previous,event='change_order.approved',approved=True,revision=2,approved_by=fresh['id'],approved_at=now,updated_at=now)
        return self.write(actor,'finance.approve','business.change_order.approved',project_id,data,change_id,approve)

    def cost_report(self,actor,project_id):
        with self.office.lock:
            self.access(actor,'finance.read',project_id)
            budget=self.office.db.execute('SELECT * FROM business_project_budgets WHERE project_id=?',(project_id,)).fetchone()
            changes=[self._change(row) for row in self.office.db.execute('SELECT * FROM business_change_orders WHERE project_id=? AND approved=1 ORDER BY created_at,id',(project_id,)).fetchall()]
            materials=[]; material_cost=Decimal(0)
            for row in self.office.db.execute("SELECT * FROM business_stock_movements WHERE project_id=? AND kind IN ('issue','return') ORDER BY sequence_number",(project_id,)).fetchall():
                value=self._movement(row); material_cost+=Decimal(row['cost_net'])*(1 if row['kind']=='issue' else -1); materials.append(value)
            from business_time import TimeTracking
            times=TimeTracking(self.office).approved_costs(actor,project_id)
            labor=Decimal(times['total_cost_minor'])/100
            complete=times.get('complete',True)
            planned=sum((Decimal(budget[field]) for field in ('material_net','labor_net','machine_net','other_net')),Decimal(0)) if budget else Decimal(0)
            extra=sum((Decimal(row['amount_net']) for row in changes),Decimal(0))
            return dict(project_id=project_id,currency='EUR',budget_revision=budget['revision'] if budget else 0,budget_net=money(planned),approved_changes_net=money(extra),approved_changes=changes,
                material_actual_net=money(material_cost),labor_actual_net=money(labor),actual_net=money(material_cost+labor),remaining_net=money(planned+extra-material_cost-labor) if complete else None,
                costs_complete=complete,missing_rates_count=times.get('missing_rates_count',0),material_movements=materials,approved_times=times['items'],cost_basis='posted_material_and_approved_time')

    def save_order(self,actor,data,order_id=None):
        project_id=data.get('project_id') if isinstance(data,dict) else None
        def save(fresh,body):
            if set(body)-{'project_id','supplier_name','items','status','revision'}: raise Problem(400,'Unbekannte Bestellfelder')
            old=self.office.db.execute('SELECT * FROM business_purchase_orders WHERE id=?',(order_id,)).fetchone() if order_id else None
            if order_id and old is None: raise Problem(404,'Bestellvorschlag nicht verfügbar')
            if old:
                if old['project_id']!=project_id: raise Problem(409,'Projektbindung kann nicht geändert werden')
                self.check_revision(body,old)
                if old['status']=='approved': raise Problem(409,'Freigegebener Bestellvorschlag ist unveränderlich')
            status=body.get('status','draft')
            if status not in ('draft','approved'): raise Problem(400,'Externer Bestellversand ist nicht eingerichtet')
            if status=='approved': self.access(fresh,'finance.approve',project_id)
            items=body.get('items')
            if not isinstance(items,list) or not 1<=len(items)<=200: raise Problem(400,'Bestellvorschlag benötigt Positionen')
            normalized=[]
            for item in items:
                if not isinstance(item,dict) or set(item)!={'article_id','quantity'}: raise Problem(400,'Ungültige Bestellposition')
                article=self._article(item['article_id']); amount=decimal(item['quantity'],positive=True)
                normalized.append(dict(article_id=article['id'],article_snapshot=article,quantity=quantity(amount)))
            supplier=text(body.get('supplier_name'),'Lieferant',300,required=True)
            identifier_,now=order_id or uuid.uuid4().hex,self.now()
            if old:
                self.office.db.execute('UPDATE business_purchase_orders SET supplier_name=?,payload_json=?,status=?,revision=revision+1,updated_by=?,updated_at=? WHERE id=?',(supplier,canonical(normalized),status,fresh['id'],now,identifier_))
            else:
                self.office.db.execute('INSERT INTO business_purchase_orders(id,project_id,supplier_name,payload_json,status,revision,created_by,created_at,updated_by,updated_at) VALUES(?,?,?,?,?,1,?,?,?,?)',(identifier_,project_id,supplier,canonical(normalized),status,fresh['id'],now,fresh['id'],now))
            row=self.office.db.execute('SELECT * FROM business_purchase_orders WHERE id=?',(identifier_,)).fetchone()
            value=dict(row); value['items']=json.loads(value.pop('payload_json')); value['delivery_status']='not_sent'
            return value
        return self._public(actor,self.write(actor,'inventory.write','business.purchase_order.saved',project_id,data,order_id,save),project_id)


def _validate_integrity(office):
    api=BusinessInventory(office)
    stock={}; returns={}; picks={}
    next_sequence=1
    for row in office.db.execute('SELECT * FROM business_stock_movements ORDER BY sequence_number').fetchall():
        if row['sequence_number']!=next_sequence: raise ValueError('Missing stock journal sequence')
        next_sequence+=1
        if row['kind'] not in ('receive','issue','return','transfer'): raise ValueError('Invalid stock movement')
        amount=decimal(row['quantity'],positive=True); cost=decimal(row['cost_net']); unit=decimal(row['unit_cost_net'])
        snapshot=json.loads(row['article_snapshot_json'])
        if snapshot.get('id')!=row['article_id'] or type(snapshot.get('revision')) is not int or unit<0 or cost<0 or abs(cost-unit*amount)>amount*Decimal('.00005')+Decimal('.0001'): raise ValueError('Invalid movement valuation')
        source,destination=row['from_location_id'],row['to_location_id']
        if (row['kind'] in ('receive','return') and (source is not None or not destination)) or (row['kind']=='issue' and (not source or destination is not None or not row['project_id'])) or (row['kind']=='transfer' and (not source or not destination or source==destination)): raise ValueError('Invalid movement locations')
        if source:
            stock[(source,row['article_id'])]=stock.get((source,row['article_id']),Decimal(0))-amount
            if stock[(source,row['article_id'])]<0: raise ValueError('Negative historical stock')
        if destination: stock[(destination,row['article_id'])]=stock.get((destination,row['article_id']),Decimal(0))+amount
        if row['kind']=='return': returns[row['reversal_of']]=returns.get(row['reversal_of'],Decimal(0))+amount
        if row['reservation_id']: picks[row['reservation_id']]=picks.get(row['reservation_id'],Decimal(0))+amount
    if any(value<0 for value in stock.values()): raise ValueError('Negative stock')
    for original_id,amount in returns.items():
        original=office.db.execute("SELECT * FROM business_stock_movements WHERE id=? AND kind='issue'",(original_id,)).fetchone()
        if not original or amount>Decimal(original['quantity']): raise ValueError('Invalid stock return')
    for row in office.db.execute('SELECT * FROM business_stock_reservations').fetchall():
        amount=decimal(row['quantity'],positive=True); picked=decimal(row['picked_quantity'])
        if picked<0 or picked>amount or picked!=picks.get(row['id'],Decimal(0)): raise ValueError('Reservation movement mismatch')
    for location_id,article_id in stock:
        on_hand,_,reserved=api._stock(location_id,article_id)
        if reserved>on_hand: raise ValueError('Overcommitted stock')
    for row in office.db.execute('SELECT * FROM business_project_budgets').fetchall():
        history=office.db.execute('SELECT payload_json FROM business_budget_versions WHERE project_id=? AND revision=?',(row['project_id'],row['revision'])).fetchone()
        if not history: raise ValueError('Missing budget history')
        latest=json.loads(history['payload_json'])
        if any(latest.get(field)!=row[field] for field in ('project_id','revision','material_net','labor_net','machine_net','other_net','updated_by','updated_at')): raise ValueError('Budget history mismatch')
    for row in office.db.execute('SELECT * FROM business_change_orders').fetchall(): api._change(row)
    return True


def validate_integrity(office):
    try:
        return _validate_integrity(office)
    except (Problem,TypeError,KeyError,json.JSONDecodeError,InvalidOperation) as error:
        raise ValueError('Invalid inventory data') from error


def methods(path):
    if re.fullmatch(r'/projects/[a-f0-9]{32}/changes/[a-f0-9]{32}/approve',path): return 'POST'
    if path in ('/inventory/stock','/inventory/scan','/inventory/reorder-suggestions') or re.fullmatch(r'/projects/[a-f0-9]{32}/costs',path): return 'GET'
    if path=='/inventory/pick' or re.fullmatch(r'/inventory/reservations/[a-f0-9]{32}/release',path): return 'POST'
    if path in ('/budgets','/inventory/reorder-rules') or re.fullmatch(r'/projects/[a-f0-9]{32}/changes',path): return 'GET, POST'
    match=re.fullmatch(r'/inventory/(locations|movements|reservations|orders)(?:/([a-f0-9]{32}))?',path)
    if match:
        if match[1] in ('movements','reservations') and match[2]: return 'GET'
        return 'GET, POST'
    return None


def dispatch(office,actor,path,method,data):
    if methods(path) is None: return None
    api=BusinessInventory(office); query=data.get('_query',{})
    body={k:v for k,v in data.items() if k!='_query'}
    def parameter(key):
        value=query.get(key)
        return value[0] if isinstance(value,list) and len(value)==1 else value
    project_id=parameter('project_id') if method=='GET' else body.get('project_id')
    if path=='/inventory/scan' and method=='GET': return api.lookup(actor,parameter('code')),200,'application/json'
    if path=='/inventory/stock' and method=='GET':
        if parameter('location_id') and parameter('article_id'): return api.balance(actor,parameter('location_id'),parameter('article_id')),200,'application/json'
        api.access(actor,'inventory.read'); result=[]
        for row in office.db.execute('SELECT DISTINCT article_id FROM business_stock_movements').fetchall():
            for location in api.list_locations(actor): result.append(api.balance(actor,location['id'],row['article_id']))
        return {'items':result},200,'application/json'
    if path=='/inventory/reorder-suggestions' and method=='GET': return {'items':api.reorder_suggestions(actor)},200,'application/json'
    if path=='/inventory/reorder-rules' and method=='POST': return api.set_reorder_rule(actor,body),200,'application/json'
    if path=='/inventory/reorder-rules' and method=='GET':
        api.access(actor,'inventory.read')
        return {'items':[dict(row) for row in office.db.execute('SELECT * FROM business_stock_reorder_rules ORDER BY location_id,article_id').fetchall()]},200,'application/json'
    if path=='/inventory/pick' and method=='POST': return api.pick(actor,project_id,{k:v for k,v in body.items() if k!='project_id'}),200,'application/json'
    if path=='/budgets':
        if not project_id: raise Problem(400,'project_id fehlt')
        if method=='POST': return api.save_budget(actor,project_id,{k:v for k,v in body.items() if k!='project_id'}),200,'application/json'
        api.access(actor,'finance.read',project_id)
        rows=office.db.execute('SELECT * FROM business_project_budgets WHERE project_id=?',(project_id,)).fetchall()
        return {'items':[dict(row,currency='EUR') for row in rows]},200,'application/json'
    approval=re.fullmatch(r'/projects/([a-f0-9]{32})/changes/([a-f0-9]{32})/approve',path)
    if approval and method=='POST': return api.approve_change_order(actor,approval[1],approval[2],body),200,'application/json'
    match=re.fullmatch(r'/projects/([a-f0-9]{32})/(costs|changes)',path)
    if match:
        project_id,action=match.groups()
        if action=='costs' and method=='GET': return api.cost_report(actor,project_id),200,'application/json'
        if action=='changes' and method=='POST': return api.add_change_order(actor,project_id,body),201,'application/json'
        if action=='changes' and method=='GET':
            api.access(actor,'finance.read',project_id)
            return {'items':[api._change(row) for row in office.db.execute('SELECT * FROM business_change_orders WHERE project_id=? ORDER BY created_at,id',(project_id,)).fetchall()]},200,'application/json'
    match=re.fullmatch(r'/inventory/(locations|movements|reservations|orders)(?:/([a-f0-9]{32}))?(?:/(release))?',path)
    if match:
        resource,object_id,action=match.groups()
        if resource=='locations':
            if method=='GET':
                if object_id:
                    api.access(actor,'inventory.read')
                    return api._location(object_id,require_active=False),200,'application/json'
                return {'items':api.list_locations(actor)},200,'application/json'
            if method=='POST': return api.save_location(actor,body,object_id),200 if object_id else 201,'application/json'
        if resource=='movements':
            if method=='POST' and not object_id: return api.move(actor,body),201,'application/json'
            if method=='GET':
                if object_id:
                    row=office.db.execute('SELECT * FROM business_stock_movements WHERE id=?',(object_id,)).fetchone()
                    if not row: raise Problem(404,'Lagerbewegung nicht verfügbar')
                    api.access(actor,'inventory.read',row['project_id'])
                    return api._public(actor,api._movement(row),row['project_id']),200,'application/json'
                fresh=api.access(actor,'inventory.read',project_id)
                from business_foundation import permissions
                financial='finance.read' in permissions(office,fresh)
                rows=office.db.execute('SELECT * FROM business_stock_movements WHERE project_id=? ORDER BY sequence_number',(project_id,)).fetchall() if project_id else office.db.execute('SELECT * FROM business_stock_movements ORDER BY sequence_number').fetchall()
                items=[]
                for row in rows:
                    if row['project_id']:
                        try: api.access(actor,'inventory.read',row['project_id'])
                        except Problem as error:
                            if error.status in (403,404): continue
                            raise
                    items.append(api._public(actor,api._movement(row),row['project_id']))
                return {'items':items},200,'application/json'
        if resource=='reservations':
            if not project_id: raise Problem(400,'project_id fehlt')
            if method=='POST' and action=='release': return api.release_reservation(actor,project_id,object_id,{k:v for k,v in body.items() if k!='project_id'}),200,'application/json'
            if method=='POST' and not object_id: return api.reserve(actor,project_id,{k:v for k,v in body.items() if k!='project_id'}),201,'application/json'
            if method=='GET':
                api.access(actor,'inventory.read',project_id)
                if object_id: return api._public(actor,api._reservation(api.row('business_stock_reservations',project_id,object_id)),project_id),200,'application/json'
                return {'items':[api._public(actor,api._reservation(row),project_id) for row in office.db.execute('SELECT * FROM business_stock_reservations WHERE project_id=? ORDER BY created_at,id',(project_id,)).fetchall()]},200,'application/json'
        if resource=='orders':
            if method=='POST': return api.save_order(actor,body,object_id),200 if object_id else 201,'application/json'
            if method=='GET':
                api.access(actor,'finance.read',project_id)
                if object_id:
                    row=office.db.execute('SELECT * FROM business_purchase_orders WHERE id=?',(object_id,)).fetchone()
                    if not row: raise Problem(404,'Bestellvorschlag nicht verfügbar')
                    api.access(actor,'finance.read',row['project_id'])
                    value=dict(row); value['items']=json.loads(value.pop('payload_json')); value['delivery_status']='not_sent'
                    return value,200,'application/json'
                rows=office.db.execute('SELECT * FROM business_purchase_orders WHERE project_id=? ORDER BY created_at,id',(project_id,)).fetchall() if project_id else office.db.execute('SELECT * FROM business_purchase_orders ORDER BY created_at,id').fetchall()
                items=[]
                for row in rows:
                    if row['project_id']:
                        try: api.access(actor,'finance.read',row['project_id'])
                        except Problem as error:
                            if error.status in (403,404): continue
                            raise
                    value=dict(row); value['items']=json.loads(value.pop('payload_json')); value['delivery_status']='not_sent'; items.append(value)
                return {'items':items},200,'application/json'
    raise Problem(405,'Methode nicht unterstützt')
