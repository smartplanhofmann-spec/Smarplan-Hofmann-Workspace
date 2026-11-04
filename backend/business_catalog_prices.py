"""Own CSV v2: explicit dated price facts, source bindings and frozen selections.

No vendor protocol, automatic current-price rewrite, currency conversion or unit
conversion is implied. V1 adapters and their historical receipts stay separate.
"""
import base64
import csv
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import hashlib
import io
import json
import re
import sqlite3
import uuid

from core import Problem, canonical
from inquiries import _transaction
from business_foundation import require_permission
from business_operations import iso_date
from workspace_api import BinaryAttachment

FEATURES = ('catalog_prices_v2',)
PROFILE = 'catalog_csv_v2'
MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 2000
FIELDS = ('price_id', 'code', 'name', 'unit', 'price_role', 'price_net',
          'price_base_quantity', 'currency', 'tax_rate', 'valid_from', 'valid_until')
TABLES = ('business_catalog_price_sources', 'business_catalog_price_imports',
          'business_catalog_price_bindings', 'business_catalog_price_events',
          'business_catalog_price_applications', 'business_catalog_price_requests')
ID = r'[a-f0-9]{32}'
HASH = r'[a-f0-9]{64}'


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value).encode()).hexdigest()


def shape(value, required=(), optional=()):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or set(required) - set(value):
        raise Problem(400, 'Unvollständige oder unbekannte Katalog-v2-Felder.')


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(ID, value):
        raise Problem(400, 'Gültige Katalog-ID erwartet.')
    return value


def text(value, name, limit=200):
    if (not isinstance(value, str) or not value.strip() or len(value) > limit
            or any(ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF for char in value)):
        raise Problem(400, 'Ungültiges Feld: ' + name)
    return value.strip()


def amount(value, *, positive=False, maximum=Decimal('9999999999999')):
    if not isinstance(value, str) or not re.fullmatch(r'(0|[1-9][0-9]{0,12})(\.[0-9]{1,4})?', value):
        raise Problem(400, 'Nicht negativer Dezimaltext mit höchstens vier Nachkommastellen erwartet.')
    result = Decimal(value)
    if result > maximum or positive and result <= 0:
        raise Problem(400, 'Preis oder Bezugsmenge außerhalb des zulässigen Bereichs.')
    return result


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA', 'BLOB'):
        raise ValueError('Unsupported storage type')
    return [
        '''CREATE TABLE IF NOT EXISTS business_catalog_price_sources(
          id TEXT PRIMARY KEY,name TEXT NOT NULL,reference TEXT NOT NULL,payload_json TEXT NOT NULL,
          sha256 TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        f'''CREATE TABLE IF NOT EXISTS business_catalog_price_imports(
          id TEXT PRIMARY KEY,source_id TEXT NOT NULL REFERENCES business_catalog_price_sources(id),
          catalog_revision TEXT NOT NULL,source_version INTEGER NOT NULL CHECK(source_version>=0),
          filename TEXT NOT NULL,original {binary_type} NOT NULL,original_sha256 TEXT NOT NULL,
          rows_json TEXT NOT NULL,rows_sha256 TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
          UNIQUE(source_id,catalog_revision))''',
        '''CREATE TABLE IF NOT EXISTS business_catalog_price_bindings(
          source_id TEXT NOT NULL REFERENCES business_catalog_price_sources(id),code TEXT NOT NULL,
          revision INTEGER NOT NULL CHECK(revision>0),article_id TEXT NOT NULL REFERENCES business_articles(id),
          article_revision INTEGER NOT NULL CHECK(article_revision>0),unit TEXT NOT NULL,payload_json TEXT NOT NULL,
          sha256 TEXT NOT NULL,previous_hash TEXT NOT NULL,import_id TEXT NOT NULL REFERENCES business_catalog_price_imports(id),
          created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,PRIMARY KEY(source_id,code,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_catalog_price_events(
          id TEXT NOT NULL,revision INTEGER NOT NULL CHECK(revision>0),source_id TEXT NOT NULL REFERENCES business_catalog_price_sources(id),
          price_key TEXT NOT NULL,article_id TEXT NOT NULL REFERENCES business_articles(id),code TEXT NOT NULL,
          binding_revision INTEGER NOT NULL CHECK(binding_revision>0),status TEXT NOT NULL CHECK(status IN ('active','withdrawn')),
          payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,previous_hash TEXT NOT NULL,
          import_id TEXT NOT NULL REFERENCES business_catalog_price_imports(id),line_number INTEGER NOT NULL,
          created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,PRIMARY KEY(id,revision),
          UNIQUE(source_id,price_key,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_catalog_price_applications(
          import_id TEXT PRIMARY KEY REFERENCES business_catalog_price_imports(id),source_id TEXT NOT NULL REFERENCES business_catalog_price_sources(id),
          source_version INTEGER NOT NULL CHECK(source_version>0),payload_json TEXT NOT NULL,sha256 TEXT NOT NULL,
          created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,UNIQUE(source_id,source_version))''',
        '''CREATE TABLE IF NOT EXISTS business_catalog_price_requests(
          user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,operation TEXT NOT NULL,
          request_json TEXT NOT NULL,request_hash TEXT NOT NULL,result_json TEXT NOT NULL,result_sha256 TEXT NOT NULL,
          PRIMARY KEY(user_id,request_id))''',
    ]


def protected_tables():
    return TABLES


def runtime_privileges():
    return {table: ('SELECT', 'INSERT') for table in TABLES}


def guard_statements(dialect):
    keys = ('id=NEW.id', 'id=NEW.id OR (source_id=NEW.source_id AND catalog_revision=NEW.catalog_revision)',
            'source_id=NEW.source_id AND code=NEW.code AND revision=NEW.revision',
            '(id=NEW.id OR (source_id=NEW.source_id AND price_key=NEW.price_key)) AND revision=NEW.revision',
            'import_id=NEW.import_id OR (source_id=NEW.source_id AND source_version=NEW.source_version)',
            'user_id=NEW.user_id AND request_id=NEW.request_id')
    statements = []
    if dialect == 'postgresql':
        statements.append("CREATE OR REPLACE FUNCTION business_catalog_price_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable dated catalog fact'; END; $$")
    for table, key in zip(TABLES, keys):
        for action in ('UPDATE', 'DELETE'):
            name = table + '_' + action.lower() + '_guard'
            if dialect == 'sqlite':
                statements.append(f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable dated catalog fact'); END")
            elif dialect == 'postgresql':
                statements.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION business_catalog_price_guard(); END IF; END $$")
            else:
                raise ValueError('Unsupported dialect')
        if dialect == 'sqlite':
            statements.append(f"CREATE TRIGGER IF NOT EXISTS {table}_replace_guard BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {key}) BEGIN SELECT RAISE(ABORT,'immutable dated catalog fact'); END")
    return statements


def installed(office):
    from business_schema import _tables
    found = set(TABLES) & _tables(office)
    if found and found != set(TABLES):
        raise Problem(503, 'Datierte Katalogquellen sind nur teilweise eingerichtet.')
    return bool(found)


def parse_catalog(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise Problem(413, 'Katalogoriginal muss zwischen 1 Byte und 2 MiB groß sein.')
    if b'\x00' in raw:
        raise Problem(400, 'Nullbytes sind in Katalogdateien nicht zulässig.')
    try:
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''), delimiter=';', strict=True)
        if reader.fieldnames != list(FIELDS):
            raise Problem(400, 'Exakte Smartplan CSV-v2-Kopfzeile erwartet.')
        result, seen, identities = [], set(), {}
        for row in reader:
            if len(result) >= MAX_ROWS:
                raise Problem(413, 'Höchstens 2.000 Katalogpreispositionen erwartet.')
            if set(row) != set(FIELDS) or any(value is None for value in row.values()):
                raise Problem(400, 'Unvollständige CSV-v2-Position.')
            item = {key: text(row[key], key, 500 if key == 'name' else 20 if key == 'unit' else 100)
                    for key in ('price_id', 'code', 'name', 'unit')}
            if item['price_id'] in seen:
                raise Problem(400, 'Doppelte Preiskennung innerhalb der Originaldatei.')
            seen.add(item['price_id'])
            identity = (item['name'], item['unit'])
            if item['code'] in identities and identities[item['code']] != identity:
                raise Problem(400, 'Artikelnummer besitzt innerhalb der Datei abweichende Bezeichnung oder Einheit.')
            identities[item['code']] = identity
            if row['price_role'] not in ('purchase_net', 'sales_net') or row['currency'] != 'EUR':
                raise Problem(400, 'Ausdrückliche Einkauf-/Verkauf-Nettopreisrolle und EUR erforderlich.')
            for field in ('price_net', 'price_base_quantity', 'tax_rate'):
                amount(row[field], positive=field == 'price_base_quantity',
                       maximum=Decimal(100) if field == 'tax_rate' else Decimal(1000000) if field == 'price_base_quantity' else Decimal('9999999999999'))
            first = iso_date(row['valid_from'], 'Gültig ab')
            last = iso_date(row['valid_until'], 'Gültig bis') if row['valid_until'] else None
            if last is not None and last < first:
                raise Problem(400, 'Gültigkeitsende liegt vor dem Beginn.')
            item.update({key: row[key] for key in ('price_role', 'price_net', 'price_base_quantity', 'currency', 'tax_rate')})
            item.update(valid_from=first, valid_until=last)
            result.append(item)
    except (UnicodeError, csv.Error):
        raise Problem(400, 'Gültige UTF-8-CSV-v2-Datei erforderlich.') from None
    if not result:
        raise Problem(400, 'Mindestens eine datierte Preisposition erforderlich.')
    return result


def _payload(row):
    value = json.loads(row['payload_json'])
    if sha(value) != row['sha256']:
        raise Problem(409, 'Datierte Katalogquelle hat ihre Integritätsprüfung nicht bestanden.')
    return value


def _head_bindings(office, source_id):
    result = {}
    for row in _verified_bindings(office, source_id).values():
        result[row['code']] = row
    return result


def _head_prices(office, source_id=None):
    result = {}
    for row in _verified_events(office, source_id=source_id):
        result[row['id']] = row
    return result


def article_managed(office, article_id):
    if not installed(office):
        return False
    return office.db.execute('SELECT 1 FROM business_catalog_price_bindings WHERE article_id=?', (article_id,)).fetchone() is not None


class CatalogPrices:
    def __init__(self, office, clock=None):
        self.office, self.db = office, office.db
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def now(self):
        return self.clock().isoformat()

    def lock_source(self, source_id):
        # All process-local writers already hold the Office transaction lock.
        # PostgreSQL needs the same serialization across independent runtimes;
        # immutable source tables intentionally grant no UPDATE row-lock rights.
        if not isinstance(self.db, sqlite3.Connection):
            key = int.from_bytes(hashlib.sha256(('catalog-v2:' + identifier(source_id)).encode()).digest()[:8], 'big', signed=True)
            self.db.execute('SELECT pg_advisory_xact_lock(?)', (key,))

    def lock_command(self, actor, data):
        request_id = identifier(data.get('request_id'))
        if not isinstance(self.db, sqlite3.Connection):
            key = int.from_bytes(hashlib.sha256(('catalog-v2-command:' + actor['id'] + ':' + request_id).encode()).digest()[:8], 'big', signed=True)
            self.db.execute('SELECT pg_advisory_xact_lock(?)', (key,))

    def access(self, actor, *, write=False, configure=False):
        actor = require_permission(self.office, actor, 'finance.read')
        if write:
            actor = require_permission(self.office, actor, 'finance.write')
        if configure:
            actor = require_permission(self.office, actor, 'settings.manage')
        if write:
            from business_organization import require_active
            require_active(self.office, actor, '/documents', 'business_documents')
        return actor

    def request(self, actor, operation, data):
        request_id = identifier(data.get('request_id'))
        fingerprint = sha(dict(operation=operation, data=data))
        row = self.db.execute('SELECT * FROM business_catalog_price_requests WHERE user_id=? AND request_id=?', (actor['id'], request_id)).fetchone()
        if row:
            if row['operation'] != operation or row['request_hash'] != fingerprint or sha(json.loads(row['result_json'])) != row['result_sha256']:
                raise Problem(409, 'Diese Vorgangs-ID gehört zu einem anderen Katalogauftrag.')
            return request_id, fingerprint, json.loads(row['result_json'])
        return request_id, fingerprint, None

    def remember(self, actor, request_id, operation, body, fingerprint, result):
        self.db.execute('INSERT INTO business_catalog_price_requests VALUES(?,?,?,?,?,?,?)',
                        (actor['id'], request_id, operation, canonical(body), fingerprint, canonical(result), sha(result)))
        return result

    def source(self, source_id):
        row = self.db.execute('SELECT * FROM business_catalog_price_sources WHERE id=?', (identifier(source_id),)).fetchone()
        if row is None:
            raise Problem(404, 'Datierte Katalogquelle nicht verfügbar.')
        result = _payload(row)
        if result['id'] != row['id'] or result['name'] != row['name'] or result['reference'] != row['reference']:
            raise Problem(409, 'Katalogquellenidentität ist widersprüchlich.')
        version = self.db.execute('SELECT COUNT(*) FROM business_catalog_price_applications WHERE source_id=?', (source_id,)).fetchone()[0] + self.db.execute('SELECT COUNT(*) FROM business_catalog_price_events WHERE source_id=?', (source_id,)).fetchone()[0]
        return dict(result, source_version=version)

    def sources(self, actor):
        with self.office.lock:
            self.access(actor, configure=True)
            return dict(items=[self.source(row['id']) for row in self.db.execute('SELECT id FROM business_catalog_price_sources ORDER BY created_at,id')], profile=PROFILE)

    def create_source(self, actor, data):
        shape(data, ('request_id', 'name', 'reference'))
        with _transaction(self.office):
            actor = self.access(actor, write=True, configure=True)
            self.lock_command(actor, data)
            request_id, fingerprint, previous = self.request(actor, 'source.create', data)
            if previous:
                return previous
            value = dict(id=uuid.uuid4().hex, name=text(data['name'], 'Quellenname'), reference=text(data['reference'], 'Quellenreferenz'),
                         profile=PROFILE, created_by=actor['id'], created_at=self.now())
            self.db.execute('INSERT INTO business_catalog_price_sources VALUES(?,?,?,?,?,?,?)',
                            (value['id'], value['name'], value['reference'], canonical(value), sha(value), actor['id'], value['created_at']))
            self.office.audit(actor, 'business.catalog_prices.source_created', value['id'])
            return self.remember(actor, request_id, 'source.create', data, fingerprint, dict(value, source_version=0))

    def _import(self, import_id):
        row = self.db.execute('SELECT * FROM business_catalog_price_imports WHERE id=?', (identifier(import_id),)).fetchone()
        if row is None:
            raise Problem(404, 'Datierter Katalogimport nicht verfügbar.')
        rows = json.loads(row['rows_json'])
        upload_receipts = self.db.execute('SELECT * FROM business_catalog_price_requests WHERE operation=? AND user_id=?',
                                          ('import:' + row['source_id'],row['created_by'])).fetchall()
        bound = False
        for receipt in upload_receipts:
            body = json.loads(receipt['request_json'])
            result = json.loads(receipt['result_json'])
            if result != {'id':import_id}:
                continue
            try:
                bound = (sha(dict(operation=receipt['operation'],data=body)) == receipt['request_hash']
                    and sha(result) == receipt['result_sha256'] and body['request_id'] == receipt['request_id']
                    and body['filename'].strip() == row['filename'] and body['catalog_revision'].strip() == row['catalog_revision']
                    and base64.b64decode(body['content_base64'],validate=True) == bytes(row['original']))
            except (KeyError,TypeError,ValueError):
                bound = False
            if bound:
                break
        if not bound:
            raise Problem(409,'Katalogoriginal besitzt keine unveränderte Uploadquittung.')
        if sha(bytes(row['original'])) != row['original_sha256'] or sha(rows) != row['rows_sha256'] or parse_catalog(bytes(row['original'])) != rows:
            raise Problem(409, 'Katalogoriginal oder Positionen sind verändert.')
        application = self.db.execute('SELECT * FROM business_catalog_price_applications WHERE import_id=?', (import_id,)).fetchone()
        return dict(id=row['id'], source_id=row['source_id'], catalog_revision=row['catalog_revision'],
                    source_version=row['source_version'], profile=PROFILE, rows=rows, rows_sha256=row['rows_sha256'],
                    original=dict(filename=row['filename'], size=len(row['original']), sha256=row['original_sha256']),
                    status='applied' if application else 'staged', application=_payload(application) if application else None,
                    created_by=row['created_by'], created_at=row['created_at'])

    def stage(self, actor, source_id, data):
        shape(data, ('request_id', 'catalog_revision', 'filename', 'content_base64'))
        with _transaction(self.office):
            actor = self.access(actor, write=True, configure=True)
            self.lock_command(actor, data)
            self.lock_source(source_id)
            source = self.source(source_id)
            operation = 'import:' + source_id
            request_id, fingerprint, previous = self.request(actor, operation, data)
            if previous:
                return self._import(previous['id'])
            revision = text(data['catalog_revision'], 'Katalogrevision')
            filename = text(data['filename'], 'Dateiname')
            if filename in ('.', '..') or any(char in filename for char in '/\\'):
                raise Problem(400, 'Einfacher Dateiname ohne Verzeichnisse erwartet.')
            encoded = data['content_base64']
            if not isinstance(encoded, str) or len(encoded) > 4 * ((MAX_BYTES + 2) // 3):
                raise Problem(413, 'Katalogoriginal überschreitet 2 MiB.')
            try:
                raw = base64.b64decode(encoded, validate=True)
            except (ValueError, UnicodeError):
                raise Problem(400, 'Gültige Base64-Datei erwartet.') from None
            rows = parse_catalog(raw)
            existing = self.db.execute('SELECT id,original_sha256,filename FROM business_catalog_price_imports WHERE source_id=? AND catalog_revision=?',
                                       (source_id, revision)).fetchone()
            if existing:
                if existing['original_sha256'] != sha(raw) or existing['filename'] != filename:
                    raise Problem(409, 'Diese Katalogrevision besitzt bereits ein anderes Original.')
                import_id = existing['id']
            else:
                import_id = uuid.uuid4().hex
                self.db.execute('INSERT INTO business_catalog_price_imports VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                                (import_id, source_id, revision, source['source_version'], filename, raw, sha(raw), canonical(rows), sha(rows), actor['id'], self.now()))
                self.office.audit(actor, 'business.catalog_prices.import_staged', import_id)
            self.remember(actor, request_id, operation, data, fingerprint, {'id': import_id})
            return self._import(import_id)

    def detail(self, actor, import_id):
        with self.office.lock:
            self.access(actor, configure=True)
            value = self._import(import_id)
            bindings = _head_bindings(self.office, value['source_id'])
            suggestions = {}
            from business_documents import Documents
            for code in {row['code'] for row in value['rows']}:
                binding = bindings.get(code)
                if binding:
                    article = Documents(self.office).catalog_item(actor, 'business_articles', binding['article_id'])
                    suggestions[code] = dict(binding_revision=binding['revision'], binding_sha256=binding['sha256'], article=article)
            heads = _head_prices(self.office,value['source_id'])
            relevant = {row['price_id'] for row in value['rows']}
            price_heads = {row['price_key']:dict(price_id=row['id'],revision=row['revision'],sha256=row['sha256'],status=row['status'],price=row['payload']['price'])
                           for row in heads.values() if row['price_key'] in relevant}
            return dict(value, bindings=suggestions, price_heads=price_heads, current_source_version=self.source(value['source_id'])['source_version'])

    def history(self, actor, source_id, query):
        shape(query, (), ('offset', 'limit'))
        def number(key, default, high):
            raw = query.get(key, str(default))
            if not isinstance(raw, str) or not re.fullmatch(r'0|[1-9][0-9]{0,8}', raw) or not 0 <= int(raw) <= high:
                raise Problem(400, 'Ungültige Historienseitengrenze.')
            return int(raw)
        offset, limit = number('offset', 0, 100000000), number('limit', 20, 50)
        if not limit:
            raise Problem(400, 'Mindestens ein Historieneintrag erwartet.')
        with self.office.lock:
            self.access(actor, configure=True)
            self.source(source_id)
            items = []
            for row in self.db.execute('SELECT id FROM business_catalog_price_imports WHERE source_id=? ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?',
                                       (source_id, limit, offset)):
                value = self._import(row['id'])
                items.append({**{key: value[key] for key in ('id', 'source_id', 'catalog_revision', 'original', 'status', 'created_at')}, 'row_count': len(value['rows'])})
            total = self.db.execute('SELECT COUNT(*) FROM business_catalog_price_imports WHERE source_id=?', (source_id,)).fetchone()[0]
            return dict(items=items, total=total, offset=offset, limit=limit)

    def original(self, actor, import_id):
        with self.office.lock:
            self.access(actor, configure=True)
            value = self._import(import_id)
            row = self.db.execute('SELECT original FROM business_catalog_price_imports WHERE id=?', (import_id,)).fetchone()
            return BinaryAttachment(bytes(row['original']), value['original']['filename']), 200, 'application/octet-stream'

    def _preview(self, actor, import_id, data):
        shape(data, ('expected_source_version', 'bindings', 'replacements'))
        run = self._import(import_id)
        source = self.source(run['source_id'])
        if run['status'] != 'staged' or type(data['expected_source_version']) is not int or source['source_version'] != data['expected_source_version']:
            raise Problem(409, 'Katalogquellenstand wurde geändert; dasselbe Original mit aktuellem Quellenstand neu prüfen.')
        by_code = {item['code']: item for item in run['rows']}
        if not isinstance(data['bindings'], dict) or set(data['bindings']) != set(by_code) or not isinstance(data['replacements'], dict):
            raise Problem(400, 'Ausdrückliche Artikelentscheidung für jede Quellnummer und Korrekturzuordnung erwartet.')
        bound, decisions = _head_bindings(self.office, run['source_id']), {}
        from business_documents import Documents, calculate_positions
        documents = Documents(self.office)
        for code, item in by_code.items():
            choice = data['bindings'][code]
            shape(choice, ('action', 'article_id', 'article_revision', 'expected_binding_revision', 'confirm_name_difference'))
            prior = bound.get(code)
            if type(choice['expected_binding_revision']) is not int or choice['expected_binding_revision'] != (prior['revision'] if prior else 0):
                raise Problem(409, 'Artikelbindung wurde inzwischen geändert.')
            if type(choice['confirm_name_difference']) is not bool:
                raise Problem(400, 'Namensabweichung muss ausdrücklich bestätigt werden.')
            if choice['action'] == 'create':
                if choice['article_id'] is not None or choice['article_revision'] is not None or choice['confirm_name_difference']:
                    raise Problem(400, 'Neuanlage besitzt noch keine Artikel-ID oder bestätigte Namensabweichung.')
                article = None
            elif choice['action'] == 'bind':
                article = documents.catalog_item(actor, 'business_articles', identifier(choice['article_id']))
                if type(choice['article_revision']) is not int or article['revision'] != choice['article_revision']:
                    raise Problem(409, 'Zielartikel wurde seit der Auswahl geändert.')
                if article['active'] is not True or article['kind'] != 'material' or article['unit'] != item['unit']:
                    raise Problem(409, 'Aktiver Materialartikel mit exakt passender Einheit erforderlich; sonst neuen Artikel anlegen.')
                if article['name'] != item['name'] and choice['confirm_name_difference'] is not True:
                    raise Problem(409, 'Abweichende Artikelbezeichnung ausdrücklich bestätigen.')
            else:
                raise Problem(400, 'Artikel ausdrücklich neu anlegen oder vorhandenen Artikel zuordnen.')
            # Use the actual existing document boundary, including its unit and
            # tax validation, before creating any otherwise unusable article.
            calculate_positions([dict(description=item['name'], quantity='1', unit=item['unit'],
                                      unit_price_net=item['price_net'], price_base_quantity=item['price_base_quantity'],
                                      tax_rate=item['tax_rate'], kind='material')])
            same = bool(prior and article and prior['article_id'] == article['id'] and prior['unit'] == item['unit'])
            decisions[code] = dict(code=code, action=choice['action'], article_id=article['id'] if article else None,
                                   article_revision=article['revision'] if article else None,
                                   binding_revision=prior['revision'] if same else (prior['revision'] + 1 if prior else 1),
                                   binding_changed=not same, before_article=article, name=item['name'], unit=item['unit'])
        heads = _head_prices(self.office, run['source_id'])
        by_key = {row['price_key']: row for row in heads.values()}
        rows, replacement_keys, missing_replacements = [], set(), []
        for index, item in enumerate(run['rows'], 1):
            calculate_positions([dict(description=item['name'],quantity='1',unit=item['unit'],unit_price_net=item['price_net'],price_base_quantity=item['price_base_quantity'],tax_rate=item['tax_rate'],kind='material')])
            decision = decisions[item['code']]
            price_id = uuid.uuid5(uuid.NAMESPACE_URL, 'smartplan-catalog-price:' + run['source_id'] + ':' + item['price_id']).hex
            prior = by_key.get(item['price_id'])
            content = dict(item, article_id=decision['article_id'], binding_revision=decision['binding_revision'])
            unchanged = prior is not None and prior['status'] == 'active' and prior['payload']['price'] == content
            if prior and not unchanged:
                replacement_keys.add(item['price_id'])
                replacement = data['replacements'].get(item['price_id'])
                if replacement is None:
                    missing_replacements.append(dict(external_price_id=item['price_id'],revision=prior['revision'],sha256=prior['sha256']))
                else:
                    shape(replacement, ('revision', 'sha256'))
                    if type(replacement['revision']) is not int or replacement['revision'] != prior['revision'] or replacement['sha256'] != prior['sha256']:
                        raise Problem(409, 'Zu ersetzende Preisrevision stimmt nicht mehr überein.')
            rows.append(dict(line_number=index, price_id=price_id, external_price_id=item['price_id'],
                             action='unchanged' if unchanged else 'correct' if prior else 'create',
                             revision=prior['revision'] if unchanged else (prior['revision'] + 1 if prior else 1),
                             previous_hash=prior['sha256'] if prior and not unchanged else '',
                             before=prior['payload'] if prior else None, price=content))
        if set(data['replacements']) - replacement_keys:
            raise Problem(400, 'Nur tatsächlich geänderte vorhandene Preiskennungen ausdrücklich ersetzen.')
        projected = {key: value['payload']['price'] for key, value in heads.items() if value['status'] == 'active'}
        for row in rows:
            projected[row['price_id']] = row['price']
        active_bindings = {code: value['revision'] for code, value in bound.items()}
        active_bindings.update({code: value['binding_revision'] for code, value in decisions.items()})
        groups = {}
        for key, price in projected.items():
            if price['binding_revision'] != active_bindings.get(price['code']):
                continue  # A deliberate new article binding never rewrites old facts.
            group = (price['code'], price['price_role'])
            for other in groups.setdefault(group, []):
                if price['valid_from'] <= (other['valid_until'] or '9999-12-31') and other['valid_from'] <= (price['valid_until'] or '9999-12-31'):
                    raise Problem(409, 'Überlappende Gültigkeit derselben Artikelquelle und Preisrolle; bestehende Revision ausdrücklich korrigieren.')
            groups[group].append(price)
        value = dict(import_id=import_id, source_id=run['source_id'], source_version=source['source_version'],
                     original_sha256=run['original']['sha256'], rows_sha256=run['rows_sha256'],
                     decisions=data, bindings=list(decisions.values()), rows=rows, required_replacements=missing_replacements, ready=not missing_replacements)
        return dict(value, preview_sha256=sha(value))

    def preview(self, actor, import_id, data):
        with self.office.lock:
            actor = self.access(actor, configure=True)
            return self._preview(actor, import_id, data)

    def apply(self, actor, import_id, data):
        shape(data, ('request_id', 'preview_sha256', 'expected_source_version', 'bindings', 'replacements', 'confirmation'))
        if data['confirmation'] is not True or not isinstance(data['preview_sha256'], str) or not re.fullmatch(HASH, data['preview_sha256']):
            raise Problem(400, 'Vollständige Übernahmevorschau ausdrücklich bestätigen.')
        with _transaction(self.office):
            actor = self.access(actor, write=True, configure=True)
            self.lock_command(actor, data)
            operation = 'apply:' + identifier(import_id)
            self.lock_source(self._import(import_id)['source_id'])
            request_id, fingerprint, previous = self.request(actor, operation, data)
            if previous:
                return previous
            checked = self._preview(actor, import_id, {key: data[key] for key in ('expected_source_version', 'bindings', 'replacements')})
            if not checked['ready']:
                raise Problem(409,'Geänderte vorhandene Preise vor der Übernahme ausdrücklich als Korrekturen bestätigen.')
            if checked['preview_sha256'] != data['preview_sha256']:
                raise Problem(409, 'Katalogvorschau ist nicht mehr aktuell.')
            from business_documents import Documents
            documents, stamp = Documents(self.office), self.now()
            prior_bindings = _head_bindings(self.office, checked['source_id'])
            accepted_bindings = {}
            for decision in checked['bindings']:
                article_id = decision['article_id']
                article_revision = decision['article_revision']
                if decision['action'] == 'create':
                    first = next(row['price'] for row in checked['rows'] if row['price']['code'] == decision['code'])
                    article = documents.save_article(actor, dict(request_id=sha((request_id + ':article:' + decision['code']).encode())[:32],
                        code=decision['code'], name=decision['name'], unit=decision['unit'], kind='material', currency='EUR', active=True,
                        cost_price_net='0', cost_known=False, unit_price_net='0', tax_rate=first['tax_rate']))
                    article_id, article_revision = article['id'], article['revision']
                binding = dict(source_id=checked['source_id'], code=decision['code'], revision=decision['binding_revision'],
                               article_id=article_id, article_revision=article_revision if decision['binding_changed'] else prior_bindings[decision['code']]['article_revision'], unit=decision['unit'])
                if decision['binding_changed']:
                    before = prior_bindings.get(decision['code'])
                    binding_fact = dict(binding, previous_hash=before['sha256'] if before else '', import_id=import_id, created_by=actor['id'], created_at=stamp)
                    self.db.execute('INSERT INTO business_catalog_price_bindings VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                                    (checked['source_id'], decision['code'], binding['revision'], article_id, article_revision, decision['unit'],
                                     canonical(binding_fact), sha(binding_fact), before['sha256'] if before else '', import_id, actor['id'], stamp))
                accepted_bindings[decision['code']] = binding
            accepted_prices = []
            for row in checked['rows']:
                if row['action'] == 'unchanged':
                    prior = row['before']
                    record = self.db.execute('SELECT sha256 FROM business_catalog_price_events WHERE id=? AND revision=?',
                                             (row['price_id'], row['revision'])).fetchone()
                    accepted_prices.append(dict(price_id=row['price_id'], revision=row['revision'], sha256=record['sha256']))
                    continue
                binding = accepted_bindings[row['price']['code']]
                price = dict(row['price'], article_id=binding['article_id'])
                value = dict(id=row['price_id'], revision=row['revision'], source_id=checked['source_id'], price=price,
                             status='active', original_import_id=import_id, original_sha256=checked['original_sha256'],
                             line_number=row['line_number'], previous_hash=row['previous_hash'], created_by=actor['id'], created_at=stamp)
                self.db.execute('INSERT INTO business_catalog_price_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                                (value['id'], value['revision'], checked['source_id'], row['external_price_id'], binding['article_id'], price['code'],
                                 binding['revision'], 'active', canonical(value), sha(value), row['previous_hash'], import_id, row['line_number'], actor['id'], stamp))
                accepted_prices.append(dict(price_id=value['id'], revision=value['revision'], sha256=sha(value)))
            value = dict(import_id=import_id, source_id=checked['source_id'], source_version=self.source(checked['source_id'])['source_version'] + 1,
                         original_sha256=checked['original_sha256'], preview_sha256=checked['preview_sha256'],
                         bindings=list(accepted_bindings.values()), prices=accepted_prices,
                         request_id=request_id, request_sha256=fingerprint, created_by=actor['id'], created_at=stamp)
            self.db.execute('INSERT INTO business_catalog_price_applications VALUES(?,?,?,?,?,?,?)',
                            (import_id, checked['source_id'], value['source_version'], canonical(value), sha(value), actor['id'], stamp))
            self.office.audit(actor, 'business.catalog_prices.import_applied', import_id)
            return self.remember(actor, request_id, operation, data, fingerprint, value)

    def price_history(self, actor, price_id):
        with self.office.lock:
            self.access(actor, configure=True)
            events = _verified_events(self.office, price_id=identifier(price_id))
            if not events:
                raise Problem(404, 'Datierte Preisquelle nicht verfügbar.')
            return dict(items=[dict(event['payload'], sha256=event['sha256']) for event in events])

    def withdraw(self, actor, price_id, data):
        shape(data, ('request_id', 'revision', 'sha256', 'reason', 'confirmation'))
        if data['confirmation'] is not True:
            raise Problem(400, 'Preisrücknahme ausdrücklich bestätigen.')
        reason = text(data['reason'], 'Rücknahmegrund', 1000)
        with _transaction(self.office):
            actor = self.access(actor, write=True, configure=True)
            self.lock_command(actor, data)
            identifier(price_id)
            first = self.db.execute('SELECT source_id FROM business_catalog_price_events WHERE id=? ORDER BY revision DESC', (price_id,)).fetchone()
            if first is None:
                raise Problem(404, 'Datierte Preisquelle nicht verfügbar.')
            self.lock_source(first['source_id'])
            operation = 'withdraw:' + price_id
            request_id, fingerprint, previous = self.request(actor, operation, data)
            if previous:
                return previous
            previous = _verified_events(self.office, price_id=price_id)[-1]
            if (type(data['revision']) is not int or data['revision'] != previous['revision']
                    or data['sha256'] != previous['sha256'] or previous['status'] != 'active'):
                raise Problem(409, 'Aktive Preisrevision stimmt nicht mehr überein.')
            value = dict(previous['payload'], revision=previous['revision'] + 1, status='withdrawn',
                         previous_hash=previous['sha256'], reason=reason, request_id=request_id,
                         request_sha256=fingerprint, created_by=actor['id'], created_at=self.now())
            self.db.execute('INSERT INTO business_catalog_price_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (price_id, value['revision'], value['source_id'], previous['price_key'], previous['article_id'], previous['code'],
                 previous['binding_revision'], 'withdrawn', canonical(value), sha(value), previous['sha256'],
                 previous['import_id'], previous['line_number'], actor['id'], value['created_at']))
            result = dict(value, sha256=sha(value))
            self.office.audit(actor, 'business.catalog_prices.price_withdrawn', price_id)
            return self.remember(actor, request_id, operation, data, fingerprint, result)

    def candidates(self, actor, data):
        shape(data, ('article_id', 'price_role', 'effective_on'), ('source_id',))
        with self.office.lock:
            self.access(actor)
            article_id = identifier(data['article_id'])
            day = iso_date(data['effective_on'], 'Preisstand am')
            role = data['price_role']
            if role not in ('purchase_net', 'sales_net'):
                raise Problem(400, 'Ausdrückliche Preisrolle erforderlich.')
            source_id = identifier(data['source_id']) if 'source_id' in data else None
            from business_documents import Documents
            article = Documents(self.office).catalog_item(actor, 'business_articles', article_id)
            heads = {}
            for record in _verified_events(self.office, source_id=source_id):
                heads[record['id']] = record
            bindings, items = {}, []
            for record in heads.values():
                value, price = record['payload'], record['payload']['price']
                if record['article_id'] != article_id or price['price_role'] != role:
                    continue
                if value['source_id'] not in bindings:
                    bindings[value['source_id']] = _head_bindings(self.office, value['source_id'])
                current = bindings[value['source_id']][price['code']]
                status = ('withdrawn' if record['status'] != 'active' else
                          'retired_binding' if current['revision'] != price['binding_revision'] else
                          'unit_conflict' if article['unit'] != price['unit'] or article['kind'] != 'material' or not article['active'] else
                          'not_yet_valid' if day < price['valid_from'] else
                          'expired' if price['valid_until'] is not None and day > price['valid_until'] else 'eligible')
                source=self.source(value['source_id'])
                items.append(dict(price_id=record['id'], price_revision=record['revision'], price_sha256=record['sha256'],
                                  effective_on=day, source_id=value['source_id'], source_name=source['name'], source_reference=source['reference'],
                                  price=price, status=status))
            return dict(article_id=article_id, effective_on=day, price_role=role, items=items,
                        managed=article_managed(self.office, article_id))


def _verified_bindings(office, source_id=None):
    where, params = (' WHERE source_id=?', (source_id,)) if source_id else ('', ())
    records, previous = {}, {}
    for row in office.db.execute('SELECT * FROM business_catalog_price_bindings' + where + ' ORDER BY source_id,code,revision', params):
        value = _payload(row)
        fields = ('source_id', 'code', 'revision', 'article_id', 'article_revision', 'unit', 'previous_hash', 'import_id', 'created_by', 'created_at')
        key = (row['source_id'], row['code'])
        prior = previous.get(key)
        if (any(value.get(field) != row[field] for field in fields)
                or row['revision'] != (prior['revision'] + 1 if prior else 1)
                or row['previous_hash'] != (prior['sha256'] if prior else '')):
            raise Problem(409, 'Artikelbindungsidentität oder Revisionskette ist verändert.')
        article = office.db.execute('SELECT payload_json,payload_sha256 FROM business_article_versions WHERE article_id=? AND revision=?',
                                    (row['article_id'],row['article_revision'])).fetchone()
        article_value = json.loads(article['payload_json']) if article else {}
        if (article is None or sha(article_value) != article['payload_sha256'] or article_value.get('unit') != row['unit']
                or article_value.get('kind') != 'material' or article_value.get('active') is not True):
            raise Problem(409,'Artikelbindung besitzt keine passende ursprüngliche Materialartikelfassung.')
        records[(row['source_id'], row['code'], row['revision'])] = dict(row, payload=value)
        previous[key] = row
    return records


def _verified_events(office, *, source_id=None, price_id=None):
    service = CatalogPrices(office)
    where, params = (' WHERE source_id=?', (source_id,)) if source_id else ('', ())
    if price_id:
        where, params = ' WHERE id=?', (price_id,)
    imports, bindings, prior, records = {}, _verified_bindings(office, source_id), {}, []
    for row in office.db.execute('SELECT * FROM business_catalog_price_events' + where + ' ORDER BY id,revision', params):
        value = _payload(row)
        price = value.get('price', {})
        previous = prior.get(row['id'])
        if (any(value.get(key) != row[column] for key, column in (
                ('id', 'id'), ('revision', 'revision'), ('source_id', 'source_id'), ('status', 'status'),
                ('original_import_id', 'import_id'), ('line_number', 'line_number'), ('previous_hash', 'previous_hash'),
                ('created_by', 'created_by'), ('created_at', 'created_at')))
                or any(price.get(key) != row[column] for key, column in (
                    ('price_id', 'price_key'), ('article_id', 'article_id'), ('code', 'code'), ('binding_revision', 'binding_revision')))
                or row['revision'] != (previous['revision'] + 1 if previous else 1)
                or row['previous_hash'] != (previous['sha256'] if previous else '')
                or row['id'] != uuid.uuid5(uuid.NAMESPACE_URL, 'smartplan-catalog-price:' + row['source_id'] + ':' + row['price_key']).hex):
            raise Problem(409, 'Preisidentität oder Revisionskette ist verändert.')
        if row['import_id'] not in imports:
            imports[row['import_id']] = service._import(row['import_id'])
        original = imports[row['import_id']]
        index = row['line_number'] - 1
        binding = bindings.get((row['source_id'], row['code'], row['binding_revision']))
        if (original['source_id'] != row['source_id'] or original['status'] != 'applied'
                or value['original_sha256'] != original['original']['sha256']
                or not 0 <= index < len(original['rows']) or binding is None
                or binding['article_id'] != row['article_id'] or binding['unit'] != price.get('unit')
                or price != dict(original['rows'][index], article_id=row['article_id'], binding_revision=row['binding_revision'])):
            raise Problem(409, 'Preis ist nicht an sein angenommenes Original und seine Artikelbindung gebunden.')
        if row['status'] == 'active':
            proof = dict(price_id=row['id'], revision=row['revision'], sha256=row['sha256'])
            if proof not in original['application']['prices']:
                raise Problem(409, 'Preisrevision besitzt keine bindende Übernahmequittung.')
        else:
            if previous is None or previous['status'] != 'active' or previous['payload']['price'] != price:
                raise Problem(409, 'Preisrücknahme besitzt keine aktive Vorgängerrevision.')
            request = office.db.execute('SELECT * FROM business_catalog_price_requests WHERE user_id=? AND request_id=?',
                                       (row['created_by'], value.get('request_id'))).fetchone()
            if (request is None or request['operation'] != 'withdraw:' + row['id']
                    or request['request_hash'] != value.get('request_sha256')
                    or json.loads(request['result_json']) != dict(value, sha256=row['sha256'])):
                raise Problem(409, 'Preisrücknahme besitzt keine bindende Auftragsquittung.')
        record = dict(row, payload=value, binding=binding)
        prior[row['id']] = record
        records.append(record)
    return records


def _snapshot(office, record, day):
    value = record['payload']
    result = dict(contract=PROFILE, price_id=record['id'], price_revision=record['revision'], price_sha256=record['sha256'],
                  effective_on=day, source_id=value['source_id'], source_name=CatalogPrices(office).source(value['source_id'])['name'],
                  price=value['price'], original_import_id=value['original_import_id'], original_sha256=value['original_sha256'],
                  line_number=value['line_number'], binding_sha256=record['binding']['sha256'])
    return dict(result, snapshot_sha256=sha(result))


def validate_snapshot(office, snapshot, article_id=None, role=None):
    """Verify an already frozen selection against original facts, never today's head."""
    if not isinstance(snapshot, dict) or snapshot.get('contract') != PROFILE:
        raise Problem(409, 'Unveränderlicher datierter Preisnachweis erforderlich.')
    price_id = identifier(snapshot.get('price_id'))
    day = iso_date(snapshot.get('effective_on'), 'Preisstand am')
    records = _verified_events(office, price_id=price_id)
    record = next((row for row in records if row['revision'] == snapshot.get('price_revision')), None)
    if record is None or record['status'] != 'active' or snapshot != _snapshot(office, record, day):
        raise Problem(409, 'Datierter Preisnachweis ist verändert oder nicht angenommen.')
    price = snapshot['price']
    if (article_id is not None and price['article_id'] != article_id or role is not None and price['price_role'] != role
            or day < price['valid_from'] or price['valid_until'] is not None and day > price['valid_until']):
        raise Problem(409, 'Artikel, Preisrolle oder gewählter Gültigkeitstag passen nicht zum Nachweis.')
    return snapshot


def resolve_selection(office, actor, article_id, selection, role, lock=False):
    """Choose an explicit current revision at an explicit day; never fallback."""
    shape(selection, ('price_id', 'price_revision', 'price_sha256', 'effective_on'))
    service = CatalogPrices(office)
    service.access(actor)
    price_id = identifier(selection['price_id'])
    day = iso_date(selection['effective_on'], 'Preisstand am')
    if type(selection['price_revision']) is not int or role not in ('purchase_net', 'sales_net'):
        raise Problem(400, 'Ausdrückliche Preisrevision und Preisrolle erforderlich.')
    if lock:
        first = office.db.execute('SELECT source_id FROM business_catalog_price_events WHERE id=? ORDER BY revision DESC', (price_id,)).fetchone()
        if first:
            service.lock_source(first['source_id'])
    records = _verified_events(office, price_id=price_id)
    if not records:
        raise Problem(404, 'Datierte Preisquelle nicht verfügbar.')
    record, price = records[-1], records[-1]['payload']['price']
    from business_documents import Documents
    article = Documents(office).catalog_item(actor, 'business_articles', article_id)
    binding = _head_bindings(office, record['source_id'])[record['code']]
    if (record['status'] != 'active' or record['revision'] != selection['price_revision']
            or record['sha256'] != selection['price_sha256'] or binding['revision'] != record['binding_revision']
            or not article['active'] or article['kind'] != 'material' or article['unit'] != price['unit']):
        raise Problem(409, 'Gewählte Preisquelle wurde geändert, zurückgenommen oder anders gebunden.')
    snapshot = _snapshot(office, record, day)
    return validate_snapshot(office, snapshot, article_id, role)


def validate_integrity(office):
    if not installed(office):
        return
    try:
        if isinstance(office.db,sqlite3.Connection):
            normalize=lambda value:re.sub(r'\s+',' ',value.replace('IF NOT EXISTS ','')).strip().lower()
            for statement in guard_statements('sqlite'):
                name=re.search(r'CREATE TRIGGER IF NOT EXISTS (\w+)',statement)[1]
                actual=office.db.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",(name,)).fetchone()
                if actual is None or normalize(actual[0]) != normalize(statement):
                    raise ValueError('Missing or modified dated catalog integrity guard')
        else:
            from business_documents import _validate_pg_guards
            _validate_pg_guards(office.db,guard_statements('postgresql'))
        service = CatalogPrices(office)
        requests = []
        for row in office.db.execute('SELECT * FROM business_catalog_price_requests'):
            body, result = json.loads(row['request_json']), json.loads(row['result_json'])
            if (body.get('request_id') != row['request_id'] or sha(dict(operation=row['operation'],data=body)) != row['request_hash']
                    or sha(result) != row['result_sha256']):
                raise ValueError('Dated catalog command receipt changed')
            requests.append(dict(row, body=body, result=result))
        for row in office.db.execute('SELECT * FROM business_catalog_price_sources'):
            value = service.source(row['id'])
            if (any(value.get(key) != row[key] for key in ('created_by','created_at'))
                    or not any(receipt['operation'] == 'source.create' and receipt['user_id'] == row['created_by']
                               and receipt['result'] == dict(_payload(row),source_version=0)
                               and receipt['body']['name'].strip() == row['name']
                               and receipt['body']['reference'].strip() == row['reference'] for receipt in requests)):
                raise ValueError('Dated catalog source lacks original command')
        for row in office.db.execute('SELECT * FROM business_catalog_price_imports'):
            value = service._import(row['id'])
            if not any(receipt['operation'] == 'import:' + row['source_id'] and receipt['user_id'] == row['created_by']
                       and receipt['result'] == {'id':row['id']} and receipt['body']['filename'].strip() == row['filename']
                       and receipt['body']['catalog_revision'].strip() == row['catalog_revision']
                       and base64.b64decode(receipt['body']['content_base64'],validate=True) == bytes(row['original']) for receipt in requests):
                raise ValueError('Dated catalog original lacks upload command')
        bindings = _verified_bindings(office)
        for row in bindings.values():
            original = service._import(row['import_id'])
            binding = {key:row['payload'][key] for key in ('source_id','code','revision','article_id','article_revision','unit')}
            if (original['status'] != 'applied' or original['source_id'] != row['source_id']
                    or binding not in original['application']['bindings']
                    or not any(item['code'] == row['code'] and item['unit'] == row['unit'] for item in original['rows'])):
                raise ValueError('Dated catalog binding lacks acceptance evidence')
        events = _verified_events(office)
        by_revision = {(record['id'],record['revision']):record for record in events}
        for row in office.db.execute('SELECT * FROM business_catalog_price_applications'):
            value = _payload(row)
            if (any(value.get(key) != row[key] for key in ('import_id','source_id','source_version','created_by','created_at'))
                    or value['original_sha256'] != service._import(row['import_id'])['original']['sha256']
                    or not any(receipt['operation'] == 'apply:' + row['import_id'] and receipt['user_id'] == row['created_by']
                               and receipt['request_id'] == value['request_id'] and receipt['request_hash'] == value['request_sha256']
                               and receipt['result'] == value and receipt['body']['confirmation'] is True
                               and receipt['body']['preview_sha256'] == value['preview_sha256'] for receipt in requests)):
                raise ValueError('Dated catalog acceptance lacks original command')
            for proof in value['prices']:
                record = by_revision.get((proof['price_id'],proof['revision']))
                if record is None or record['sha256'] != proof['sha256'] or record['status'] != 'active':
                    raise ValueError('Dated catalog acceptance references absent price fact')
    except (Problem,KeyError,TypeError,ValueError,UnicodeError) as error:
        raise ValueError('Dated catalog source integrity failed: ' + str(error)) from error


def methods(path):
    if path == '/catalog-prices/sources' or re.fullmatch(r'/catalog-prices/sources/' + ID + r'/imports',path):
        return 'GET, POST'
    if re.fullmatch(r'/catalog-prices/(?:imports/' + ID + r'(?:/original)?|prices/' + ID + r'/history)',path):
        return 'GET'
    if path == '/catalog-prices/candidates' or re.fullmatch(r'/catalog-prices/(?:imports/' + ID + r'/(?:preview|apply)|prices/' + ID + r'/withdraw)',path):
        return 'POST'
    return None


def dispatch(office, actor, path, method, data):
    if methods(path) is None:
        return None
    if method not in methods(path).split(', '):
        raise Problem(405,'HTTP-Methode nicht erlaubt.')
    service = CatalogPrices(office)
    if method == 'GET':
        shape(data,(),('_query',))
        query = data.get('_query',{})
        match = re.fullmatch(r'/catalog-prices/sources/(' + ID + r')/imports',path)
        if match:
            return service.history(actor,match[1],query),200,'application/json'
        if query:
            raise Problem(400,'Dieser Abruf akzeptiert keine Filter.')
        if path == '/catalog-prices/sources':
            result = service.sources(actor)
        elif path.endswith('/history'):
            result = service.price_history(actor,path.split('/')[3])
        elif path.endswith('/original'):
            return service.original(actor,path.split('/')[3])
        else:
            result = service.detail(actor,path.split('/')[3])
    elif path == '/catalog-prices/sources':
        result = service.create_source(actor,data)
    elif path == '/catalog-prices/candidates':
        result = service.candidates(actor,data)
    elif '/sources/' in path:
        result = service.stage(actor,path.split('/')[3],data)
    elif path.endswith('/preview'):
        result = service.preview(actor,path.split('/')[3],data)
    elif path.endswith('/apply'):
        result = service.apply(actor,path.split('/')[3],data)
    else:
        result = service.withdraw(actor,path.split('/')[3],data)
    return result,200,'application/json'


def lock_selections(office, selections):
    """Prelock every explicit source in stable order inside a write transaction."""
    service, source_ids = CatalogPrices(office), set()
    for selection in selections:
        if isinstance(selection,dict) and isinstance(selection.get('price_id'),str) and re.fullmatch(ID,selection['price_id']):
            row=office.db.execute('SELECT source_id FROM business_catalog_price_events WHERE id=? ORDER BY revision DESC',(selection['price_id'],)).fetchone()
            if row:source_ids.add(row['source_id'])
    for source_id in sorted(source_ids):service.lock_source(source_id)
