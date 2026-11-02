"""Documented purchase orders and atomic, position-bound goods receipts.

This module never sends an order. Confirmation records an order already placed
outside the application. Supplier returns, changes to confirmed orders and unit
conversion are deliberately unsupported. Existing approved purchase proposals
remain the source; all purchasing records are additive and append-only.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import heapq
import json
import re
import unicodedata
import uuid

from core import Problem, canonical
from business_inventory import BusinessInventory
from business_operations import (Domain, decimal, identifier, iso_date, quantity,
                                 request_schema, text, transaction)


FEATURES = ('purchasing_receipts', 'purchasing_catalog')
_TABLES = ('business_purchasing_requests', 'business_purchase_confirmations',
           'business_purchase_receipts', 'business_purchase_receipt_lines')
_ID = r'[a-f0-9]{32}'


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA', 'BLOB'):
        raise ValueError('Unsupported binary storage type')
    return request_schema(_TABLES[0]) + [
        '''CREATE TABLE IF NOT EXISTS business_purchase_confirmations(
        order_id TEXT PRIMARY KEY REFERENCES business_purchase_orders(id),
        source_revision INTEGER NOT NULL CHECK(source_revision>0),
        source_json TEXT NOT NULL, source_sha256 TEXT NOT NULL CHECK(length(source_sha256)=64),
        order_reference TEXT NOT NULL, ordered_on TEXT NOT NULL,
        confirmed_by TEXT NOT NULL REFERENCES users(id), confirmed_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_purchase_receipts(
        id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES business_purchase_confirmations(order_id),
        source_revision INTEGER NOT NULL CHECK(source_revision>0),
        receipt_revision INTEGER NOT NULL CHECK(receipt_revision>0),
        receipt_reference TEXT NOT NULL, reference_key TEXT NOT NULL, received_on TEXT NOT NULL,
        location_id TEXT NOT NULL REFERENCES business_stock_locations(id),
        created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL,
        UNIQUE(order_id,receipt_revision), UNIQUE(order_id,reference_key))''',
        '''CREATE TABLE IF NOT EXISTS business_purchase_receipt_lines(
        receipt_id TEXT NOT NULL REFERENCES business_purchase_receipts(id),
        line_index INTEGER NOT NULL CHECK(line_index>=0), article_id TEXT NOT NULL,
        unit TEXT NOT NULL, quantity TEXT NOT NULL, unit_cost_net TEXT NOT NULL, cost_net TEXT NOT NULL,
        movement_id TEXT NOT NULL UNIQUE REFERENCES business_stock_movements(id),
        PRIMARY KEY(receipt_id,line_index))''',
        'CREATE INDEX IF NOT EXISTS business_purchase_receipts_order ON business_purchase_receipts(order_id,receipt_revision)',
    ]


def protected_tables():
    return _TABLES


def runtime_privileges():
    return {table: ('SELECT', 'INSERT') for table in _TABLES}


def guard_statements(dialect):
    if dialect == 'sqlite':
        output = [f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard "
                f"BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable purchase history'); END"
                for table in _TABLES for action in ('UPDATE', 'DELETE')]
        # SQLite REPLACE can remove the old row without firing DELETE triggers
        # when recursive_triggers is off. Reject every conflicting unique key
        # before insertion instead of relying on a connection PRAGMA.
        conflicts = {
            'business_purchasing_requests': 'user_id=NEW.user_id AND request_id=NEW.request_id',
            'business_purchase_confirmations': 'order_id=NEW.order_id',
            'business_purchase_receipts': 'id=NEW.id OR (order_id=NEW.order_id AND '
                '(receipt_revision=NEW.receipt_revision OR reference_key=NEW.reference_key))',
            'business_purchase_receipt_lines': '(receipt_id=NEW.receipt_id AND line_index=NEW.line_index) OR movement_id=NEW.movement_id',
        }
        for table, condition in conflicts.items():
            output.append(f"CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} "
                f"WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition}) "
                "BEGIN SELECT RAISE(ABORT,'immutable purchase history'); END")
        return output
    if dialect == 'postgresql':
        result = ["""CREATE OR REPLACE FUNCTION business_purchasing_immutable_guard()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'immutable purchase history'; END; $$"""]
        for table in _TABLES:
            for action in ('UPDATE', 'DELETE'):
                name = table + '_' + action.lower() + '_guard'
                result.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE "
                    f"tgname='{name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} "
                    f"BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION "
                    "business_purchasing_immutable_guard(); END IF; END $$")
        return result
    raise ValueError('Unsupported guard dialect')


def _sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _reference(value, name):
    value = text(value, name, 200, required=True)
    if any(ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise Problem(400, 'Einzeilige Belegreferenz erwartet: ' + name)
    normalized = ' '.join(unicodedata.normalize('NFKC', value).casefold().split())
    if not normalized or len(normalized) > 500:
        raise Problem(400, 'Ungültige Belegreferenz: ' + name)
    return value, normalized


class Purchasing(Domain):
    receipt_table = 'business_purchasing_requests'

    def __init__(self, office, *, clock=None):
        super().__init__(office, clock=clock)
        self.inventory = BusinessInventory(office, clock=clock)

    def _row(self, order_id):
        identifier(order_id, 'Bestell-ID')
        row = self.office.db.execute('SELECT * FROM business_purchase_orders WHERE id=?', (order_id,)).fetchone()
        if row is None:
            raise Problem(404, 'Bestellvorgang nicht verfügbar')
        return row

    def _source(self, row):
        items = json.loads(row['payload_json'])
        if not isinstance(items, list) or not 1 <= len(items) <= 200:
            raise Problem(500, 'Bestellquelle ist nicht konsistent')
        for item in items:
            if (not isinstance(item, dict) or set(item) != {'article_id', 'article_snapshot', 'quantity'}
                    or not isinstance(item['article_snapshot'], dict)
                    or item['article_snapshot'].get('id') != item['article_id']
                    or not isinstance(item['article_snapshot'].get('unit'), str)
                    or not item['article_snapshot']['unit']):
                raise Problem(500, 'Bestellposition ist nicht konsistent')
            identifier(item['article_id'], 'Artikel-ID')
            decimal(item['quantity'], positive=True)
        return dict(id=row['id'], project_id=row['project_id'], supplier_name=row['supplier_name'],
                    source_revision=row['revision'], items=items)

    def _confirmation(self, row):
        confirmation = self.office.db.execute(
            'SELECT * FROM business_purchase_confirmations WHERE order_id=?', (row['id'],)).fetchone()
        if confirmation is not None:
            source = self._source(row)
            if (row['status'] != 'approved' or row['revision'] != confirmation['source_revision']
                    or _sha(confirmation['source_json']) != confirmation['source_sha256']
                    or canonical(source) != confirmation['source_json']):
                raise Problem(500, 'Bestätigte Bestellquelle besteht die Integritätsprüfung nicht')
        return confirmation

    def _receipt_revision(self, order_id):
        return self.office.db.execute('SELECT COALESCE(MAX(receipt_revision),0) AS revision '
            'FROM business_purchase_receipts WHERE order_id=?', (order_id,)).fetchone()['revision']

    def _order(self, row, *, receipt_limit=None):
        source = self._source(row)
        confirmation = self._confirmation(row)
        totals = {}
        received = self.office.db.execute(
            'SELECT l.line_index,l.quantity,r.receipt_revision FROM business_purchase_receipt_lines l '
            'JOIN business_purchase_receipts r ON r.id=l.receipt_id WHERE r.order_id=? '
            'ORDER BY r.receipt_revision,l.line_index', (row['id'],)).fetchall()
        for line in received:
            if receipt_limit is None or line['receipt_revision'] <= receipt_limit:
                totals[line['line_index']] = totals.get(line['line_index'], Decimal(0)) + Decimal(line['quantity'])
        items = []
        for index, item in enumerate(source['items']):
            snapshot = item['article_snapshot']
            amount, arrived = Decimal(item['quantity']), totals.get(index, Decimal(0))
            if arrived < 0 or arrived > amount:
                raise Problem(500, 'Wareneingangsmenge ist nicht konsistent')
            items.append(dict(line_index=index, article_id=item['article_id'], article_name=snapshot['name'],
                article_code=snapshot.get('code', ''), unit=snapshot['unit'], ordered_quantity=quantity(amount),
                received_quantity=quantity(arrived), remaining_quantity=quantity(amount - arrived)))
        revision = self._receipt_revision(row['id']) if receipt_limit is None else receipt_limit
        status = 'proposal' if row['status'] == 'draft' else 'approved'
        if confirmation is not None:
            status = 'received' if all(item['remaining_quantity'] == '0.0000' for item in items) else (
                'partially_received' if revision else 'ordered')
        return dict(id=row['id'], project_id=row['project_id'], supplier_name=row['supplier_name'],
            source_revision=row['revision'], receipt_revision=revision, status=status, delivery_status='not_sent',
            confirmation=None if confirmation is None else {key: confirmation[key] for key in
                ('order_reference', 'ordered_on', 'confirmed_by', 'confirmed_at')}, items=items)

    def get(self, actor, order_id):
        with transaction(self.office):
            row = self._row(order_id)
            self.access(actor, 'inventory.read', row['project_id'])
            return self._order(row)

    def articles(self, actor, *, project_id=None, query='', limit=100, offset=0):
        """Operational catalogue metadata only, including articles without stock.

        Search uses Unicode casefold consistently on both database adapters.
        Bounded keyset reads avoid loading the entire financial catalogue; the
        selection heap retains at most offset + limit explicitly public DTOs.
        Pagination is bounded at offset 100000; larger sets need a narrower
        search. Neither this read nor the feature flag changes persisted schema.
        """
        if project_id is not None:
            identifier(project_id, 'Projekt-ID')
        query = text(query, 'Artikelsuche', 200)
        if any(ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF for char in query):
            raise Problem(400, 'Einzeilige Artikelsuche erwartet')
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or not 0 <= offset <= 100000:
            raise Problem(400, 'Limit zwischen 1 und 100 und Offset zwischen 0 und 100000 erwartet')
        query = query.casefold()
        with transaction(self.office):
            self.access(actor, 'inventory.read', project_id)
            total = 0

            def candidates():
                nonlocal total
                after = ''
                while True:
                    rows = self.office.db.execute('SELECT id,revision,payload_json FROM business_articles '
                        'WHERE id>? ORDER BY id LIMIT ?', (after, 256)).fetchall()
                    for row in rows:
                        value = json.loads(row['payload_json'])
                        if not isinstance(value, dict):
                            raise Problem(500, 'Artikelstamm ist nicht konsistent')
                        if value.get('active') is not True or value.get('kind') not in ('material', 'machine'):
                            continue
                        if any(not isinstance(value.get(field), str) for field in ('name', 'code', 'unit')):
                            raise Problem(500, 'Artikelstamm ist nicht konsistent')
                        if query and query not in (value['code'] + ' ' + value['name']).casefold():
                            continue
                        total += 1
                        # Never reuse the commercial snapshot or a price-key
                        # denylist: future financial fields stay private too.
                        yield dict(id=row['id'], revision=row['revision'], code=value['code'], name=value['name'],
                            kind=value['kind'], unit=value['unit'], active=True)
                    if len(rows) < 256:
                        return
                    after = rows[-1]['id']

            selected = heapq.nsmallest(offset + limit, candidates(),
                key=lambda item: (item['name'].casefold(), item['code'].casefold(), item['id']))
            items = selected[offset:]
            following = offset + len(items)
            return dict(items=items, total=total,
                        next_offset=following if following < total and following <= 100000 else None)

    def orders(self, actor, project_id=None):
        with transaction(self.office):
            if project_id is not None:
                identifier(project_id, 'Projekt-ID')
            self.access(actor, 'inventory.read', project_id)
            rows = self.office.db.execute('SELECT * FROM business_purchase_orders '
                + ('WHERE project_id=? ' if project_id is not None else '') + 'ORDER BY created_at,id',
                (project_id,) if project_id is not None else ()).fetchall()
            items = []
            for row in rows:
                try:
                    self.access(actor, 'inventory.read', row['project_id'])
                except Problem as error:
                    if error.status in (403, 404):
                        continue
                    raise
                items.append(self._order(row))
            return {'items': items}

    def _expected(self, row, body):
        if (type(body.get('source_revision')) is not int
                or body['source_revision'] != row['revision']):
            raise Problem(409, 'Bestellvorschlag wurde geändert; neu laden')
        revision = self._receipt_revision(row['id'])
        if (type(body.get('expected_receipt_revision')) is not int
                or body['expected_receipt_revision'] != revision):
            raise Problem(409, 'Wareneingänge wurden inzwischen geändert; neu laden')
        return revision

    def confirm(self, actor, order_id, data):
        with transaction(self.office):
            row = self._row(order_id)
            self.access(actor, 'inventory.write', row['project_id'])
            self.access(actor, 'finance.approve', row['project_id'])

            def save(fresh, body):
                if set(body) != {'source_revision', 'expected_receipt_revision', 'order_reference', 'ordered_on', 'confirmation'}:
                    raise Problem(400, 'Bestellreferenz, Datum, Versionen und ausdrückliche Bestätigung erwartet')
                self._expected(row, body)
                if row['status'] != 'approved':
                    raise Problem(409, 'Bestellvorschlag zuerst freigeben')
                if self._confirmation(row) is not None:
                    raise Problem(409, 'Bestellung ist bereits dokumentiert')
                if body['confirmation'] is not True:
                    raise Problem(400, 'Bereits extern erteilte Bestellung ausdrücklich bestätigen')
                reference, _ = _reference(body['order_reference'], 'Bestellreferenz')
                ordered_on = iso_date(body['ordered_on'], 'Bestelldatum')
                source = canonical(self._source(row))
                self.office.db.execute('INSERT INTO business_purchase_confirmations(order_id,source_revision,source_json,'
                    'source_sha256,order_reference,ordered_on,confirmed_by,confirmed_at) VALUES(?,?,?,?,?,?,?,?)',
                    (order_id, row['revision'], source, _sha(source), reference, ordered_on, fresh['id'], self.now()))
                return self._order(row)

            return self.write(actor, 'inventory.write', 'business.purchase.confirmed', row['project_id'], data, order_id, save)

    def _receipt(self, row, source):
        lines = []
        for line in self.office.db.execute('SELECT * FROM business_purchase_receipt_lines '
                'WHERE receipt_id=? ORDER BY line_index', (row['id'],)).fetchall():
            snapshot = source['items'][line['line_index']]['article_snapshot']
            lines.append(dict(line_index=line['line_index'], article_id=line['article_id'],
                article_name=snapshot['name'], unit=line['unit'], quantity=line['quantity'],
                movement_id=line['movement_id'], unit_cost_net=line['unit_cost_net'], cost_net=line['cost_net']))
        return dict(id=row['id'], order_id=row['order_id'], project_id=source['project_id'],
            source_revision=row['source_revision'], receipt_revision=row['receipt_revision'],
            receipt_reference=row['receipt_reference'], received_on=row['received_on'], location_id=row['location_id'],
            created_by=row['created_by'], created_at=row['created_at'], lines=lines)

    def receipts(self, actor, order_id):
        with transaction(self.office):
            order = self._row(order_id)
            self.access(actor, 'inventory.read', order['project_id'])
            self._confirmation(order)
            source = self._source(order)
            result = {'items': [self._receipt(row, source) for row in self.office.db.execute(
                'SELECT * FROM business_purchase_receipts WHERE order_id=? ORDER BY receipt_revision', (order_id,)).fetchall()]}
            return self.inventory._public(actor, result, order['project_id'])

    def receive(self, actor, order_id, data):
        with transaction(self.office):
            row = self._row(order_id)
            self.access(actor, 'inventory.write', row['project_id'])
            # Secondary authorization precedes the idempotency replay, too.
            self.access(actor, 'finance.write', row['project_id'])

            def save(fresh, body):
                if set(body) != {'source_revision', 'expected_receipt_revision', 'receipt_reference', 'received_on', 'location_id', 'lines'}:
                    raise Problem(400, 'Belegreferenz, Datum, Lager, Positionen und Versionen erwartet')
                revision = self._expected(row, body)
                confirmation = self._confirmation(row)
                if confirmation is None:
                    raise Problem(409, 'Bereits extern erteilte Bestellung zuerst dokumentieren')
                reference, reference_key = _reference(body['receipt_reference'], 'Wareneingangsbeleg')
                if self.office.db.execute('SELECT 1 FROM business_purchase_receipts WHERE order_id=? AND reference_key=?',
                        (order_id, reference_key)).fetchone():
                    raise Problem(409, 'Dieser Wareneingangsbeleg wurde bereits gebucht')
                received_on = iso_date(body['received_on'], 'Wareneingangsdatum')
                if received_on < confirmation['ordered_on']:
                    raise Problem(400, 'Wareneingang liegt vor dem dokumentierten Bestelldatum')
                location_id = identifier(body['location_id'], 'Lager-ID')
                self.inventory._location(location_id)
                lines = body['lines']
                if not isinstance(lines, list) or not 1 <= len(lines) <= 200:
                    raise Problem(400, 'Mindestens eine Wareneingangsposition erwartet')
                source = json.loads(confirmation['source_json'])
                current = self._order(row)
                seen, normalized = set(), []
                for line in lines:
                    if not isinstance(line, dict) or set(line) != {'line_index', 'quantity', 'unit_cost_net'}:
                        raise Problem(400, 'Positionsindex, Menge und tatsächlichen Einstandspreis angeben')
                    index = line['line_index']
                    if type(index) is not int or not 0 <= index < len(source['items']) or index in seen:
                        raise Problem(400, 'Ungültiger oder mehrfacher Bestellpositionsindex')
                    seen.add(index)
                    amount = decimal(line['quantity'], positive=True)
                    cost = decimal(line['unit_cost_net'], 'Einstandspreis')
                    if cost < 0:
                        raise Problem(400, 'Einstandspreis darf nicht negativ sein')
                    if cost * amount > Decimal('999999999999.9999'):
                        raise Problem(400, 'Wareneingangswert überschreitet den unterstützten Bereich')
                    if amount > Decimal(current['items'][index]['remaining_quantity']):
                        raise Problem(409, 'Wareneingang übersteigt die offene Bestellmenge')
                    ordered = source['items'][index]
                    article = self.inventory._article(ordered['article_id'])
                    if (article['unit'] != ordered['article_snapshot']['unit']
                            or article['kind'] != ordered['article_snapshot']['kind']):
                        raise Problem(409, 'Artikeleinheit oder Artikelart wurde geändert; keine automatische Umrechnung')
                    normalized.append((index, ordered, quantity(amount), quantity(cost)))
                receipt_id, stamp = uuid.uuid4().hex, self.now()
                self.office.db.execute('INSERT INTO business_purchase_receipts(id,order_id,source_revision,receipt_revision,'
                    'receipt_reference,reference_key,received_on,location_id,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                    (receipt_id, order_id, row['revision'], revision + 1, reference, reference_key, received_on, location_id, fresh['id'], stamp))
                for index, ordered, amount, cost in sorted(normalized, key=lambda item: item[0]):
                    movement = self.inventory._post_move(fresh, dict(kind='receive', article_id=ordered['article_id'],
                        to_location_id=location_id, project_id=row['project_id'], quantity=amount, unit_cost_net=cost,
                        note='Wareneingang ' + reference))
                    self.office.db.execute('INSERT INTO business_purchase_receipt_lines(receipt_id,line_index,article_id,unit,'
                        'quantity,unit_cost_net,cost_net,movement_id) VALUES(?,?,?,?,?,?,?,?)',
                        (receipt_id, index, ordered['article_id'], ordered['article_snapshot']['unit'], amount,
                         movement['unit_cost_net'], movement['cost_net'], movement['id']))
                stored = self.office.db.execute('SELECT * FROM business_purchase_receipts WHERE id=?', (receipt_id,)).fetchone()
                return self._receipt(stored, source)

            result = self.write(actor, 'inventory.write', 'business.purchase.received', row['project_id'], data, order_id, save)
            return self.inventory._public(actor, result, row['project_id'])


def _validate_integrity(office):
    api = Purchasing(office)
    expected_results = set()
    for confirmation in office.db.execute('SELECT * FROM business_purchase_confirmations').fetchall():
        row = api._row(confirmation['order_id'])
        api._confirmation(row)
        source = json.loads(confirmation['source_json'])
        _reference(confirmation['order_reference'], 'Bestellreferenz')
        iso_date(confirmation['ordered_on'])
        received = [Decimal(0) for _ in source['items']]
        expected_results.add(canonical(api._order(row, receipt_limit=0)))
        receipts = office.db.execute('SELECT * FROM business_purchase_receipts WHERE order_id=? '
                                    'ORDER BY receipt_revision', (row['id'],)).fetchall()
        for revision, receipt in enumerate(receipts, 1):
            if receipt['receipt_revision'] != revision or receipt['source_revision'] != source['source_revision']:
                raise ValueError('Invalid purchasing receipt revision')
            if _reference(receipt['receipt_reference'], 'Wareneingangsbeleg')[1] != receipt['reference_key']:
                raise ValueError('Invalid purchasing receipt reference')
            if iso_date(receipt['received_on']) < confirmation['ordered_on']:
                raise ValueError('Invalid purchasing receipt date')
            lines = office.db.execute('SELECT * FROM business_purchase_receipt_lines WHERE receipt_id=? '
                                      'ORDER BY line_index', (receipt['id'],)).fetchall()
            if not 1 <= len(lines) <= len(source['items']):
                raise ValueError('Invalid purchasing receipt lines')
            for line in lines:
                index = line['line_index']
                if type(index) is not int or not 0 <= index < len(source['items']):
                    raise ValueError('Invalid purchasing position')
                ordered = source['items'][index]
                amount = decimal(line['quantity'], positive=True)
                price = decimal(line['unit_cost_net'])
                value = decimal(line['cost_net'])
                if (line['article_id'] != ordered['article_id'] or line['unit'] != ordered['article_snapshot']['unit']
                        or price < 0 or value != (price * amount).quantize(Decimal('.0001'), rounding=ROUND_HALF_UP)):
                    raise ValueError('Invalid purchasing quantity, unit or value')
                received[index] += amount
                if received[index] > Decimal(ordered['quantity']):
                    raise ValueError('Purchasing overdelivery')
                movement = office.db.execute('SELECT * FROM business_stock_movements WHERE id=?', (line['movement_id'],)).fetchone()
                if (movement is None or movement['kind'] != 'receive' or movement['from_location_id'] is not None
                        or movement['project_id'] != source['project_id'] or movement['to_location_id'] != receipt['location_id']
                        or movement['created_by'] != receipt['created_by'] or movement['reversal_of'] is not None
                        or movement['reservation_id'] is not None
                        or any(movement[field] != line[field] for field in ('article_id', 'quantity', 'unit_cost_net', 'cost_net'))
                        or json.loads(movement['article_snapshot_json']).get('unit') != line['unit']):
                    raise ValueError('Purchasing receipt and stock movement disagree')
            expected_results.add(canonical(api._receipt(receipt, source)))
    for request in office.db.execute('SELECT * FROM business_purchasing_requests').fetchall():
        identifier(request['request_id'], 'request_id')
        if (not re.fullmatch(r'[a-f0-9]{64}', request['request_hash'])
                or canonical(json.loads(request['result_json'])) not in expected_results):
            raise ValueError('Invalid purchasing mutation receipt')
    return True


def validate_integrity(office):
    try:
        return _validate_integrity(office)
    except (Problem, TypeError, KeyError, IndexError, json.JSONDecodeError, InvalidOperation) as error:
        raise ValueError('Invalid purchasing data') from error


def methods(path):
    if path in ('/purchasing/orders', '/purchasing/articles'):
        return 'GET'
    match = re.fullmatch(r'/purchasing/orders/(' + _ID + r')(?:/(confirm|receipts))?', path)
    if match:
        return 'POST' if match[2] == 'confirm' else 'GET, POST' if match[2] == 'receipts' else 'GET'
    return None


def dispatch(office, actor, path, method, data):
    allowed = methods(path)
    if allowed is None:
        return None
    if method not in allowed.split(', '):
        raise Problem(405, 'Methode nicht erlaubt')
    api = Purchasing(office)
    query = data.get('_query', {})
    body = {key: value for key, value in data.items() if key != '_query'}
    if path == '/purchasing/articles':
        if (body or not isinstance(query, dict) or set(query) - {'project_id', 'query', 'limit', 'offset'}
                or any(not isinstance(value, str) for value in query.values())):
            raise Problem(400, 'Nur eindeutige Artikelfilter project_id, query, limit und offset erwartet')
        def page_value(name, default):
            value = query.get(name)
            if value is None:
                return default
            if not re.fullmatch(r'[0-9]{1,6}', value):
                raise Problem(400, 'Ganzzahliger Artikelfilter erwartet: ' + name)
            return int(value)
        return api.articles(actor, project_id=query.get('project_id'), query=query.get('query', ''),
            limit=page_value('limit', 100), offset=page_value('offset', 0)), 200, 'application/json'
    if path == '/purchasing/orders':
        if set(query) - {'project_id'}:
            raise Problem(400, 'Unbekannter Bestellfilter')
        return api.orders(actor, query.get('project_id')), 200, 'application/json'
    match = re.fullmatch(r'/purchasing/orders/(' + _ID + r')(?:/(confirm|receipts))?', path)
    order_id, action = match.groups()
    if query:
        raise Problem(400, 'Dieser Bestellpfad erwartet keinen Suchfilter')
    if action == 'confirm':
        return api.confirm(actor, order_id, body), 200, 'application/json'
    if action == 'receipts':
        return (api.receipts(actor, order_id), 200, 'application/json') if method == 'GET' else (
            api.receive(actor, order_id, body), 201, 'application/json')
    return api.get(actor, order_id), 200, 'application/json'
