"""Explicit physical counts and immutable stock adjustments.

Count differences never become project consumption or supplier receipts. The
old stock journal stays unchanged; adjustments are ordered after a recorded
movement boundary so both ledgers can be replayed together on restore.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
import re
import uuid

from core import Problem, canonical
from business_operations import Domain, decimal, identifier, iso_date, quantity, text, transaction

FEATURES = ('inventory_counts',)
TABLES = ('business_inventory_count_events', 'business_inventory_count_requests', 'business_inventory_adjustments')


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BLOB', 'BYTEA'):
        raise ValueError('Unsupported binary type')
    return [
        '''CREATE TABLE IF NOT EXISTS business_inventory_count_events(
        id TEXT PRIMARY KEY, count_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>0),
        operation TEXT NOT NULL CHECK(operation IN ('open','count','approve','cancel')),
        previous_hash TEXT NOT NULL, state_json TEXT NOT NULL, state_sha256 TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL,
        UNIQUE(count_id,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_inventory_count_requests(
        user_id TEXT NOT NULL REFERENCES users(id), request_id TEXT NOT NULL,
        request_hash TEXT NOT NULL, event_id TEXT NOT NULL REFERENCES business_inventory_count_events(id),
        PRIMARY KEY(user_id,request_id))''',
        '''CREATE TABLE IF NOT EXISTS business_inventory_adjustments(
        id TEXT PRIMARY KEY, sequence_number INTEGER NOT NULL UNIQUE CHECK(sequence_number>0),
        count_id TEXT NOT NULL, event_id TEXT NOT NULL REFERENCES business_inventory_count_events(id),
        location_id TEXT NOT NULL REFERENCES business_stock_locations(id), article_id TEXT NOT NULL,
        after_movement_sequence INTEGER NOT NULL CHECK(after_movement_sequence>=0),
        quantity_delta TEXT NOT NULL, value_delta_net TEXT NOT NULL,
        UNIQUE(count_id,article_id))''',
    ]


def protected_tables():
    return TABLES


def runtime_privileges():
    return {table: ('SELECT', 'INSERT') for table in TABLES}


def guard_statements(dialect):
    if dialect == 'sqlite':
        result = [f"CREATE TRIGGER IF NOT EXISTS {table}_{operation.lower()}_guard BEFORE {operation} ON {table} "
                "BEGIN SELECT RAISE(ABORT,'immutable inventory count'); END"
                for table in TABLES for operation in ('UPDATE', 'DELETE')]
        conditions = ('id=NEW.id OR (count_id=NEW.count_id AND revision=NEW.revision)',
            'user_id=NEW.user_id AND request_id=NEW.request_id',
            'id=NEW.id OR sequence_number=NEW.sequence_number OR (count_id=NEW.count_id AND article_id=NEW.article_id)')
        for table,condition in zip(TABLES,conditions):
            result.append(f'CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} '
                          f'WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition}) '
                          "BEGIN SELECT RAISE(ABORT,'immutable inventory count'); END")
        return result
    if dialect != 'postgresql':
        raise ValueError('Unsupported dialect')
    result = ["""CREATE OR REPLACE FUNCTION business_inventory_count_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'immutable inventory count'; END; $$"""]
    for table in TABLES:
        name = table + '_immutable_guard'
        result.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) "
                      f'THEN CREATE TRIGGER {name} BEFORE UPDATE OR DELETE ON {table} '
                      'FOR EACH ROW EXECUTE FUNCTION business_inventory_count_immutable(); END IF; END $$')
    return result


def _hash(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def adjustments(office):
    """Historical installations may not have the additive module yet."""
    from business_schema import _tables
    if TABLES[2] not in _tables(office):
        return []
    return [dict(row) for row in office.db.execute('SELECT * FROM business_inventory_adjustments ORDER BY sequence_number')]


def inventory_article_ids(office):
    return sorted({row['article_id'] for row in office.db.execute('SELECT DISTINCT article_id FROM business_stock_movements')}
                  | {row['article_id'] for row in adjustments(office)})


class InventoryCounts(Domain):
    def __init__(self, office, *, clock=None):
        super().__init__(office, clock=clock)
        from business_inventory import BusinessInventory
        self.stock = BusinessInventory(office, clock=clock)
        self.db = office.db

    def _row(self, count_id, revision=None):
        identifier(count_id)
        if revision is None:
            row = self.db.execute('SELECT * FROM business_inventory_count_events WHERE count_id=? ORDER BY revision DESC LIMIT 1', (count_id,)).fetchone()
        else:
            if type(revision) is not int or revision < 1:
                raise Problem(400, 'Gültige Inventurversion erwartet.')
            row = self.db.execute('SELECT * FROM business_inventory_count_events WHERE count_id=? AND revision=?', (count_id, revision)).fetchone()
        if row is None:
            raise Problem(404, 'Inventur nicht verfügbar.')
        return row

    def _basis(self, location_id, article_ids):
        location = self.stock._location(location_id)
        items = []
        existing_adjustments = adjustments(self.office)
        for article_id in sorted(article_ids):
            article = self.stock._article(article_id, allow_inactive=True)
            on_hand, value, reserved = self.stock._stock(location_id, article_id)
            movements = [dict(row) for row in self.db.execute(
                'SELECT * FROM business_stock_movements WHERE article_id=? AND (from_location_id=? OR to_location_id=?) ORDER BY sequence_number',
                (article_id, location_id, location_id))]
            reservations = [dict(row) for row in self.db.execute(
                'SELECT * FROM business_stock_reservations WHERE article_id=? AND location_id=? ORDER BY id', (article_id, location_id))]
            relevant_adjustments = [row for row in existing_adjustments if row['location_id'] == location_id and row['article_id'] == article_id]
            items.append(dict(article=self.stock._operational_article(article), on_hand=quantity(on_hand),
                value_net=quantity(value), reserved=quantity(reserved),
                movements_sha256=_hash(movements), reservations_sha256=_hash(reservations),
                adjustments_sha256=_hash(relevant_adjustments)))
            from business_purchase_changes import return_lines
            returned = [row for row in return_lines(self.office) if row['location_id']==location_id and row['article_id']==article_id]
            if returned:
                items[-1]['supplier_returns_sha256'] = _hash(returned)
        return dict(location=location, items=items)

    def _financial(self, actor):
        try:
            self.access(actor, 'finance.read')
            return True
        except Problem as error:
            if error.status != 403:
                raise
            return False

    def _public(self, actor, row):
        self.access(actor, 'inventory.read')
        state = json.loads(row['state_json'])
        financial = self._financial(actor)
        lines = {line['article_id']: line for line in state['lines']}
        items = []
        for item in state['basis']['items']:
            article = item['article']
            counted = lines.get(article['id'])
            value = dict(article=article, on_hand=item['on_hand'], reserved=item['reserved'],
                counted_quantity=counted['quantity'] if counted else None,
                reason=counted['reason'] if counted else '',
                difference=quantity(Decimal(counted['quantity']) - Decimal(item['on_hand'])) if counted else None)
            if financial:
                value['value_net'] = item['value_net']
                approved = next((v for v in state.get('valuation', []) if v['article_id'] == article['id']), None)
                if approved:
                    value['adjustment_value_net'] = approved['value_delta_net']
            items.append(value)
        current = None
        if state['status'] in ('open','counted'):
            try:
                current = _hash(self._basis(state['location_id'], [item['article']['id'] for item in state['basis']['items']])) == state['basis_sha256']
            except Problem as error:
                if error.status not in (400,404,409): raise
                current = False
        return dict(id=row['count_id'], revision=row['revision'], event_id=row['id'], status=state['status'],
            title=state['title'], counted_on=state['counted_on'], location_id=state['location_id'],
            location_name=state['basis']['location']['name'], correction_of=state['correction_of'],
            reason=state['reason'], items=items, basis_current=current,
            created_by=state['created_by'], created_at=state['created_at'],
            updated_by=row['created_by'], updated_at=row['created_at'],
            history_sha256=row['state_sha256'], financial_values_visible=financial,
            scope='selected_articles_at_one_location', project_cost_effect='none')

    def get(self, actor, count_id, revision=None):
        with self.office.lock:
            self.access(actor, 'inventory.read')
            return self._public(actor, self._row(count_id, revision))

    def list(self, actor):
        with self.office.lock:
            self.access(actor, 'inventory.read')
            ids = [row['count_id'] for row in self.db.execute('SELECT DISTINCT count_id FROM business_inventory_count_events')]
            return dict(items=[self._public(actor, self._row(identifier_)) for identifier_ in ids])

    def sources(self, actor, location_id):
        with self.office.lock:
            self.access(actor, 'inventory.read')
            identifier(location_id)
            location = self.stock._location(location_id)
            items = []
            for row in self.db.execute('SELECT id FROM business_articles ORDER BY id'):
                try:
                    article = self.stock._article(row['id'], allow_inactive=True)
                except Problem as error:
                    if error.status == 400:
                        continue
                    raise
                items.append(dict(article=self.stock._operational_article(article), **self.stock.balance(actor, location_id, article['id'])))
            return dict(location=location, items=items)

    def history(self, actor, count_id):
        with self.office.lock:
            self.access(actor, 'inventory.read'); self._row(count_id)
            return dict(items=[self._public(actor, row) for row in self.db.execute(
                'SELECT * FROM business_inventory_count_events WHERE count_id=? ORDER BY revision', (count_id,))])

    def _rights(self, actor, approval=False):
        fresh = self.access(actor, 'inventory.read')
        self.access(fresh, 'inventory.write')
        if approval:
            for permission in ('finance.read', 'finance.write', 'finance.approve'):
                self.access(fresh, permission)
        return fresh

    def _append(self, actor, count_id, operation, state, previous=None):
        event_id = uuid.uuid4().hex
        revision = previous['revision'] + 1 if previous else 1
        predecessor = previous['state_sha256'] if previous else ''
        stamp = self.now()
        digest = _hash([count_id, revision, operation, predecessor, state, actor['id'], stamp])
        self.db.execute('INSERT INTO business_inventory_count_events '
            '(id,count_id,revision,operation,previous_hash,state_json,state_sha256,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
            (event_id,count_id,revision,operation,predecessor,canonical(state),digest,actor['id'],stamp))
        return self._row(count_id)

    def command(self, actor, operation, data, count_id=None):
        if not isinstance(data, dict):
            raise Problem(400, 'JSON-Objekt erwartet.')
        request = identifier(data.get('request_id'), 'Vorgangs-ID')
        fingerprint = _hash([operation, count_id, data])
        with transaction(self.office):
            fresh = self._rights(actor, approval=operation == 'approve')
            from business_organization import require_active
            require_active(self.office, fresh, '/inventory/counts', 'business_inventory')
            prior = self.db.execute('SELECT * FROM business_inventory_count_requests WHERE user_id=? AND request_id=?', (fresh['id'], request)).fetchone()
            if prior:
                if prior['request_hash'] != fingerprint:
                    raise Problem(409, 'Vorgangs-ID bereits mit anderem Inhalt verwendet.')
                event = self.db.execute('SELECT * FROM business_inventory_count_events WHERE id=?', (prior['event_id'],)).fetchone()
                return self._public(fresh, event)
            body = {key:value for key,value in data.items() if key != 'request_id'}
            try:
                event = self._command(fresh, operation, body, count_id)
            except Problem as error:
                if error.status == 409:
                    raise Problem(409, error.message, request_resolution='not_accepted') from None
                raise
            self.db.execute('INSERT INTO business_inventory_count_requests(user_id,request_id,request_hash,event_id) VALUES(?,?,?,?)',
                (fresh['id'],request,fingerprint,event['id']))
            self.office.audit(fresh, 'inventory.count.' + operation, event['count_id'])
            return self._public(fresh, event)

    def _command(self, actor, operation, body, count_id):
        if operation == 'open':
            if set(body) != {'location_id','article_ids','title','counted_on','correction_of','reason'}:
                raise Problem(400, 'Lagerort, Artikelauswahl, Titel, Zähltag, Korrekturbezug und Grund erwartet.')
            identifier(body['location_id'])
            ids = body['article_ids']
            if not isinstance(ids,list) or not 1 <= len(ids) <= 200 or len(set(map(str,ids))) != len(ids):
                raise Problem(400, 'Ein bis 200 eindeutige Artikel auswählen.')
            for article_id in ids:
                identifier(article_id)
            title = text(body['title'],'Titel',200,required=True)
            reason = text(body['reason'],'Grund',2000,required=True)
            date = iso_date(body['counted_on'])
            if body['correction_of'] is not None:
                old = json.loads(self._row(body['correction_of'])['state_json'])
                if old['status'] != 'approved' or old['location_id'] != body['location_id'] or sorted(ids) != sorted(i['article']['id'] for i in old['basis']['items']):
                    raise Problem(409, 'Korrektur muss eine freigegebene Inventur mit demselben Zählumfang referenzieren.')
            basis = self._basis(body['location_id'],ids)
            state = dict(status='open',title=title,counted_on=date,reason=reason,location_id=body['location_id'],
                correction_of=body['correction_of'],basis=basis,basis_sha256=_hash(basis),lines=[],
                created_by=actor['id'],created_at=self.now())
            return self._append(actor,uuid.uuid4().hex,operation,state)
        previous = self._row(count_id)
        state = json.loads(previous['state_json'])
        if type(body.get('revision')) is not int or body['revision'] != previous['revision']:
            raise Problem(409, 'Inventur wurde inzwischen geändert. Neu laden.')
        if state['status'] not in ('open','counted'):
            raise Problem(409, 'Abgeschlossene Inventur bleibt unverändert; gegebenenfalls neue Korrektur zählen.')
        if operation == 'cancel':
            if set(body) != {'revision','reason'}:
                raise Problem(400, 'Version und Abbruchgrund erwartet.')
            state.update(status='cancelled',reason=text(body['reason'],'Abbruchgrund',2000,required=True))
        elif operation == 'count':
            if set(body) != {'revision','lines'} or not isinstance(body['lines'],list):
                raise Problem(400, 'Version und vollständige Zählpositionen erwartet.')
            expected = {item['article']['id']:item for item in state['basis']['items']}
            lines = []
            for line in body['lines']:
                if not isinstance(line,dict) or set(line) != {'article_id','quantity','reason'}:
                    raise Problem(400, 'Ungültige Zählposition.')
                identifier(line['article_id'])
                if line['article_id'] not in expected:
                    raise Problem(400, 'Ungültige oder doppelte Zählposition.')
                source = expected.pop(line['article_id'])
                amount = decimal(line['quantity'],'Gezählte Menge')
                if amount < 0:
                    raise Problem(400, 'Gezählte Menge darf nicht negativ sein.')
                reason = text(line['reason'],'Differenzgrund',2000,required=amount != Decimal(source['on_hand']))
                lines.append(dict(article_id=line['article_id'],quantity=quantity(amount),reason=reason))
            if expected:
                raise Problem(400, 'Alle ausgewählten Artikel ausdrücklich zählen, einschließlich Nullmengen.')
            if _hash(self._basis(state['location_id'],[i['article']['id'] for i in state['basis']['items']])) != state['basis_sha256']:
                raise Problem(409, 'Lagerstand oder Reservierung seit Zählbeginn geändert. Inventur abbrechen und neu zählen.')
            state.update(status='counted',lines=sorted(lines,key=lambda item:item['article_id']))
        elif operation == 'approve':
            if set(body) != {'revision','confirmed','zero_stock_unit_costs'} or body['confirmed'] is not True:
                raise Problem(400, 'Ausdrückliche Inventurfreigabe erwartet.')
            valuation = self._valuation(state,body['zero_stock_unit_costs'])
            state.update(status='approved',valuation=valuation)
            event = self._append(actor,count_id,operation,state,previous)
            boundary = self.db.execute('SELECT COALESCE(MAX(sequence_number),0) AS n FROM business_stock_movements').fetchone()['n']
            sequence = self.db.execute('SELECT COALESCE(MAX(sequence_number),0) AS n FROM business_inventory_adjustments').fetchone()['n']
            for item in valuation:
                if Decimal(item['quantity_delta']) == 0:
                    continue
                sequence += 1
                self.db.execute('INSERT INTO business_inventory_adjustments '
                    '(id,sequence_number,count_id,event_id,location_id,article_id,after_movement_sequence,quantity_delta,value_delta_net) VALUES(?,?,?,?,?,?,?,?,?)',
                    (uuid.uuid4().hex,sequence,count_id,event['id'],state['location_id'],item['article_id'],boundary,item['quantity_delta'],item['value_delta_net']))
            return event
        else:
            raise Problem(400, 'Unbekannte Inventuraktion.')
        return self._append(actor,count_id,operation,state,previous)

    def _valuation(self, state, prices, *, check_current=True):
        if state['status'] != 'counted':
            raise Problem(409, 'Zuerst die vollständige Zählung speichern.')
        if not isinstance(prices,dict):
            raise Problem(400, 'Ausdrückliche Preise für Mehrbestand ohne bisherigen Bestand erwartet.')
        if check_current and _hash(self._basis(state['location_id'],[i['article']['id'] for i in state['basis']['items']])) != state['basis_sha256']:
            raise Problem(409, 'Lagerstand, Reservierung oder Artikel seit Zählbeginn geändert. Neu zählen.')
        remaining = set(prices)
        lines = {line['article_id']:line for line in state['lines']}
        result = []
        for item in state['basis']['items']:
            article = item['article']['id']
            previous, counted = Decimal(item['on_hand']), Decimal(lines[article]['quantity'])
            if counted < Decimal(item['reserved']):
                raise Problem(409, 'Gezählter Bestand unterschreitet Reservierungen. Reservierungen fachlich klären und neu zählen.')
            delta, value = counted-previous, Decimal(item['value_net'])
            if delta > 0 and previous == 0:
                if article not in prices:
                    raise Problem(400, 'Mehrbestand ohne bisherigen Bestand benötigt ausdrücklich einen Einstandspreis, auch bei Nullpreis.')
                unit = decimal(prices[article],'Einstandspreis')
                if unit < 0:
                    raise Problem(400, 'Einstandspreis darf nicht negativ sein.')
                remaining.remove(article)
            else:
                unit = value/previous if previous else Decimal(0)
            value_delta = -value if counted == 0 else (delta*unit).quantize(Decimal('.0001'),rounding=ROUND_HALF_UP)
            if abs(value_delta) > Decimal('999999999999.9999'):
                raise Problem(400, 'Inventurwert überschreitet unterstützten Bereich.')
            result.append(dict(article_id=article,quantity_delta=quantity(delta),value_delta_net=quantity(value_delta),
                unit_cost_net=quantity(unit),cost_basis='explicit_zero_stock_price' if previous == 0 and delta > 0 else 'historical_weighted_cost'))
        if remaining:
            raise Problem(400, 'Preise dürfen ausschließlich für Mehrbestand ohne bisherigen Bestand angegeben werden.')
        return result

    def preview(self, actor, count_id, data):
        with self.office.lock:
            self._rights(actor,approval=True)
            if not isinstance(data,dict) or set(data) != {'revision','zero_stock_unit_costs'}:
                raise Problem(400, 'Version und ausdrücklich erforderliche Preise erwartet.')
            row = self._row(count_id)
            if type(data['revision']) is not int or row['revision'] != data['revision']:
                raise Problem(409, 'Inventurversion inzwischen geändert.')
            return dict(id=count_id,revision=row['revision'],items=self._valuation(json.loads(row['state_json']),data['zero_stock_unit_costs']),
                project_cost_effect='none',currency='EUR')


def validate_integrity(office):
    try:
        prior = {}; approved = {}; states = {}
        for row in office.db.execute('SELECT * FROM business_inventory_count_events ORDER BY count_id,revision'):
            state = json.loads(row['state_json'])
            previous = prior.get(row['count_id'])
            if row['revision'] != (previous['revision']+1 if previous else 1) or row['previous_hash'] != (previous['state_sha256'] if previous else ''):
                raise ValueError('Broken count history')
            if _hash([row['count_id'],row['revision'],row['operation'],row['previous_hash'],state,row['created_by'],row['created_at']]) != row['state_sha256'] or _hash(state['basis']) != state['basis_sha256']:
                raise ValueError('Changed count history')
            if (previous is None) != (row['operation']=='open') or state['status'] != {'open':'open','count':'counted','approve':'approved','cancel':'cancelled'}[row['operation']]:
                raise ValueError('Invalid count transition')
            if previous:
                before = states[row['count_id']]
                if before['status'] not in ('open','counted') or state['basis'] != before['basis']:
                    raise ValueError('Modified completed count or original basis')
            if state['status']=='approved':
                if states[row['count_id']]['status']!='counted' or state['lines']!=states[row['count_id']]['lines']:
                    raise ValueError('Approval changed recorded count')
                zero_articles={item['article']['id'] for item in state['basis']['items'] if Decimal(item['on_hand'])==0}
                prices={item['article_id']:item['unit_cost_net'] for item in state['valuation']
                        if item['article_id'] in zero_articles and Decimal(item['quantity_delta'])>0}
                expected_valuation=InventoryCounts(office)._valuation(dict(state,status='counted'),prices,check_current=False)
                if expected_valuation!=state['valuation']:
                    raise ValueError('Invented inventory valuation')
                approved[row['id']] = (row, state)
            prior[row['count_id']] = dict(row); states[row['count_id']] = state
        seen = set(); last_boundary = -1
        max_movement = office.db.execute('SELECT COALESCE(MAX(sequence_number),0) AS n FROM business_stock_movements').fetchone()['n']
        for sequence, row in enumerate(adjustments(office),1):
            if row['sequence_number'] != sequence or not last_boundary <= row['after_movement_sequence'] <= max_movement:
                raise ValueError('Invalid adjustment order')
            last_boundary = row['after_movement_sequence']
            event, state = approved[row['event_id']]
            expected = next(v for v in state['valuation'] if v['article_id']==row['article_id'])
            if row['count_id'] != event['count_id'] or row['location_id'] != state['location_id'] or any(row[key] != expected[key] for key in ('quantity_delta','value_delta_net')) or decimal(row['quantity_delta']) == 0:
                raise ValueError('Adjustment differs from approval')
            seen.add((row['event_id'],row['article_id']))
        expected = {(event_id,line['article_id']) for event_id,(_,state) in approved.items() for line in state['valuation'] if Decimal(line['quantity_delta']) != 0}
        if seen != expected:
            raise ValueError('Missing approved stock adjustment')
        for row in office.db.execute('SELECT * FROM business_inventory_count_requests'):
            identifier(row['request_id'])
            if not re.fullmatch(r'[a-f0-9]{64}',row['request_hash']) or not office.db.execute('SELECT 1 FROM business_inventory_count_events WHERE id=? AND created_by=?',(row['event_id'],row['user_id'])).fetchone():
                raise ValueError('Invalid inventory receipt')
    except (Problem,KeyError,TypeError,ValueError,InvalidOperation,StopIteration,json.JSONDecodeError) as error:
        raise ValueError('Invalid inventory count data') from error
    return True


def methods(path):
    if path == '/inventory/count-sources': return 'GET'
    if path == '/inventory/counts': return 'GET, POST'
    if re.fullmatch(r'/inventory/counts/[a-f0-9]{32}(?:/history)?',path): return 'GET'
    if re.fullmatch(r'/inventory/counts/[a-f0-9]{32}/(?:count|approve|cancel|preview)',path): return 'POST'
    return None


def dispatch(office, actor, path, method, data):
    allowed = methods(path)
    if allowed is None: return None
    if method not in allowed.split(', '): raise Problem(405,'HTTP-Methode nicht erlaubt.')
    api = InventoryCounts(office)
    query = data.get('_query',{}) if method=='GET' else {}
    if path=='/inventory/count-sources':
        if set(query)!={'location_id'}: raise Problem(400,'Lagerort erwartet.')
        result = api.sources(actor,query['location_id'])
    elif path=='/inventory/counts':
        if query: raise Problem(400,'Keine Suchparameter erlaubt.')
        result = api.list(actor) if method=='GET' else api.command(actor,'open',data)
    else:
        count_id, _, action = path[len('/inventory/counts/'):].partition('/')
        if method=='GET':
            if action=='history':
                if query: raise Problem(400,'Keine Suchparameter erlaubt.')
                result = api.history(actor,count_id)
            else:
                if set(query)-{'revision'}: raise Problem(400,'Nur historische Version erlaubt.')
                raw = query.get('revision')
                if raw is not None and (not isinstance(raw,str) or not re.fullmatch(r'[1-9]\d{0,6}',raw)): raise Problem(400,'Ungültige Version.')
                result = api.get(actor,count_id,int(raw) if raw else None)
        elif action=='preview': result = api.preview(actor,count_id,data)
        else: result = api.command(actor,action,data,count_id)
    return result,201 if method=='POST' and path=='/inventory/counts' else 200,'application/json'
