"""Explicit delivery-to-asset attribution, without another stock or cost posting.

Stock uses weighted averages, not serial-number lots. A user therefore confirms
the physical origin explicitly; this module never invents a FIFO relationship.
Original delivery documents and confirmed origins are retained append-only.
"""
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
import unicodedata
import uuid

from core import Problem, canonical
from business_operations import (BusinessOperations, Domain, decimal, identifier,
                                 quantity, request_schema, text, transaction)

FEATURES = ('asset_delivery_provenance',)
_TABLES = ('business_asset_provenance_requests', 'business_delivery_documents',
           'business_asset_origins')
_ID = r'[a-f0-9]{32}'


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BLOB', 'BYTEA'):
        raise ValueError('Unsupported binary storage type')
    return request_schema(_TABLES[0]) + [
        '''CREATE TABLE IF NOT EXISTS business_delivery_documents(
        receipt_id TEXT PRIMARY KEY REFERENCES business_purchase_receipts(id),
        project_id TEXT NOT NULL REFERENCES projects(id),
        media_id TEXT NOT NULL REFERENCES business_media(id),
        payload_json TEXT NOT NULL, content_hash TEXT NOT NULL CHECK(length(content_hash)=64),
        created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_asset_origins(
        asset_id TEXT PRIMARY KEY REFERENCES business_assets(id),
        project_id TEXT NOT NULL REFERENCES projects(id),
        receipt_id TEXT NOT NULL REFERENCES business_delivery_documents(receipt_id),
        line_index INTEGER NOT NULL CHECK(line_index>=0),
        issue_movement_id TEXT NOT NULL REFERENCES business_stock_movements(id),
        article_id TEXT NOT NULL, serial_key TEXT NOT NULL,
        quantity TEXT NOT NULL, payload_json TEXT NOT NULL,
        content_hash TEXT NOT NULL CHECK(length(content_hash)=64),
        created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL,
        FOREIGN KEY(receipt_id,line_index) REFERENCES business_purchase_receipt_lines(receipt_id,line_index),
        UNIQUE(article_id,serial_key))''',
        'CREATE INDEX IF NOT EXISTS business_asset_origins_issue ON business_asset_origins(issue_movement_id)',
        'CREATE INDEX IF NOT EXISTS business_asset_origins_receipt ON business_asset_origins(receipt_id,line_index)',
    ]


def protected_tables():
    return _TABLES


def runtime_privileges():
    return {table: ('SELECT', 'INSERT') for table in _TABLES}


def guard_statements(dialect):
    if dialect == 'sqlite':
        output = [f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} "
                  f"ON {table} BEGIN SELECT RAISE(ABORT,'immutable asset provenance'); END"
                  for table in _TABLES for action in ('UPDATE', 'DELETE')]
        conditions = {
            _TABLES[0]: 'user_id=NEW.user_id AND request_id=NEW.request_id',
            _TABLES[1]: 'receipt_id=NEW.receipt_id',
            _TABLES[2]: 'asset_id=NEW.asset_id OR (article_id=NEW.article_id AND serial_key=NEW.serial_key)',
        }
        for table, condition in conditions.items():
            output.append(f"CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} "
                          f"WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition}) "
                          "BEGIN SELECT RAISE(ABORT,'immutable asset provenance'); END")
        return output
    if dialect == 'postgresql':
        output = ["""CREATE OR REPLACE FUNCTION business_asset_provenance_immutable_guard()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'immutable asset provenance'; END; $$"""]
        for table in _TABLES:
            for action in ('UPDATE', 'DELETE'):
                name = table + '_' + action.lower() + '_guard'
                output.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE "
                              f"tgname='{name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} "
                              f"BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION "
                              "business_asset_provenance_immutable_guard(); END IF; END $$")
        return output
    raise ValueError('Unsupported guard dialect')


def _hash(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def _installed(office):
    from business_schema import _tables
    present = set(_TABLES).intersection(_tables(office))
    if present and present != set(_TABLES):
        raise Problem(503, 'Die Geräteherkunft ist nur teilweise eingerichtet; Migration prüfen')
    return bool(present)


def _serial(value):
    value = text(value, 'Seriennummer', 1000, required=True)
    if any(ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise Problem(400, 'Einzeilige Seriennummer erwartet')
    key = ' '.join(unicodedata.normalize('NFKC', value).casefold().split())
    if len(key.encode('utf-8')) > 1000:
        raise Problem(400, 'Seriennummer ist zu lang')
    return key


def ensure_asset_identity(office, asset_id, previous, changed):
    """Existing mutable asset details may not rewrite a confirmed serial identity."""
    if not _installed(office):
        return
    row = office.db.execute('SELECT asset_id FROM business_asset_origins WHERE asset_id=?', (asset_id,)).fetchone()
    if row and changed.get('serial_number', previous.get('serial_number')) != previous.get('serial_number'):
        raise Problem(409, 'Die Seriennummer eines gelieferten Geräts ist unveränderlich; Herkunft erhalten')


def _remaining_issue(office, row):
    returned = sum((Decimal(r['quantity']) for r in office.db.execute(
        "SELECT quantity FROM business_stock_movements WHERE kind='return' AND reversal_of=?", (row['id'],)).fetchall()), Decimal(0))
    bound = sum((Decimal(r['quantity']) for r in office.db.execute(
        'SELECT quantity FROM business_asset_origins WHERE issue_movement_id=?', (row['id'],)).fetchall()), Decimal(0))
    return Decimal(row['quantity']) - returned - bound


def ensure_return_available(office, issue_id, requested_quantity):
    if not _installed(office):
        return
    row = office.db.execute('SELECT * FROM business_stock_movements WHERE id=?', (issue_id,)).fetchone()
    if row and Decimal(requested_quantity) > _remaining_issue(office, row):
        raise Problem(409, 'Diese Entnahmemenge ist bereits einem gelieferten Gerät zugeordnet; Herkunft zuerst fachlich klären')


class AssetProvenance(Domain):
    receipt_table = _TABLES[0]

    def _authority(self, actor, project_id, *, write=False):
        identifier(project_id, 'Projekt-ID')
        fresh = self.access(actor, 'documents.read', project_id)
        self.access(fresh, 'inventory.read', project_id)
        if not _installed(self.office):
            raise Problem(503, 'Geräteherkunft ist in diesem Datenbestand noch nicht eingerichtet')
        if write:
            from business_schema import require_capability
            from business_organization import require_active
            self.access(fresh, 'documents.write', project_id)
            self.access(fresh, 'inventory.write', project_id)
            require_capability(self.office, 'business_asset_provenance')
            require_active(self.office, fresh, '/assets/from-delivery', 'business_asset_provenance')
        return fresh

    def _receipt(self, receipt_id):
        identifier(receipt_id, 'Lieferungs-ID')
        row = self.office.db.execute('SELECT * FROM business_purchase_receipts WHERE id=?', (receipt_id,)).fetchone()
        if row is None:
            raise Problem(404, 'Wareneingang nicht verfügbar')
        confirmation = self.office.db.execute('SELECT * FROM business_purchase_confirmations WHERE order_id=?', (row['order_id'],)).fetchone()
        if confirmation is None:
            raise Problem(500, 'Bestellbestätigung des Wareneingangs fehlt')
        source = json.loads(confirmation['source_json'])
        if _hash(source) != confirmation['source_sha256']:
            raise Problem(500, 'Bestellquelle ist beschädigt')
        if not source.get('project_id'):
            raise Problem(409, 'Eine Geräteherkunft benötigt eine projektgebundene Bestellung')
        return row, confirmation, source

    def _media(self, media_id, project_id, actor=None):
        identifier(media_id, 'Originaldatei-ID')
        row = self.office.db.execute('SELECT * FROM business_media WHERE id=? AND project_id=?', (media_id, project_id)).fetchone()
        if row is None or row['status'] != 'ready':
            raise Problem(404, 'Fertiges Belegoriginal ist im Projekt nicht verfügbar')
        metadata = json.loads(row['metadata_json'])
        if actor is not None:
            BusinessOperations(self.office)._media_access(actor, row)
        if metadata.get('purpose') not in ('document', 'site_photo'):
            raise Problem(400, 'Ein Lieferschein benötigt ein Dokument- oder Fotooriginal, keinen Buchhaltungsbeleg')
        original = row['original']
        if (not isinstance(original, (bytes, bytearray, memoryview)) or len(original) != row['size'] or
                hashlib.sha256(bytes(original)).hexdigest() != row['sha256']):
            raise Problem(500, 'Integritätsprüfung des Lieferscheinoriginals fehlgeschlagen')
        return dict(media_id=row['id'], filename=row['filename'], media_type=row['media_type'],
                    size=row['size'], sha256=row['sha256'])

    def _document(self, row, actor=None):
        value = json.loads(row['payload_json'])
        if _hash(value) != row['content_hash']:
            raise Problem(500, 'Lieferscheinbindung ist beschädigt')
        receipt, confirmation, source = self._receipt(row['receipt_id'])
        if actor is not None:
            self._authority(actor, row['project_id'])
        expected = dict(receipt_id=row['receipt_id'], order_id=receipt['order_id'], project_id=source['project_id'],
                        receipt_reference=receipt['receipt_reference'], received_on=receipt['received_on'],
                        order_reference=confirmation['order_reference'],
                        original=self._media(row['media_id'], row['project_id'], actor))
        if value != expected or row['project_id'] != source['project_id']:
            raise Problem(500, 'Lieferschein und Wareneingang stimmen nicht überein')
        return dict(value, content_hash=row['content_hash'], created_by=row['created_by'], created_at=row['created_at'],
                    download_path='/media/' + row['media_id'] + '/content')

    def document(self, actor, receipt_id):
        with transaction(self.office):
            _, _, source = self._receipt(receipt_id)
            self._authority(actor, source['project_id'])
            row = self.office.db.execute('SELECT * FROM business_delivery_documents WHERE receipt_id=?', (receipt_id,)).fetchone()
            if row is None:
                raise Problem(404, 'Noch kein Original-Lieferschein zugeordnet')
            return self._document(row, actor)

    def attach_document(self, actor, receipt_id, data):
        with transaction(self.office):
            receipt, confirmation, source = self._receipt(receipt_id)
            project_id = source['project_id']
            self._authority(actor, project_id, write=True)
            if not isinstance(data, dict) or set(data) != {'request_id', 'media_id', 'confirmed'} or data['confirmed'] is not True:
                raise Problem(400, 'Original-Lieferschein und ausdrückliche Bestätigung erwartet')
            original = self._media(data['media_id'], project_id, actor)

            def save(fresh, body):
                if self.office.db.execute('SELECT 1 FROM business_delivery_documents WHERE receipt_id=?', (receipt_id,)).fetchone():
                    raise Problem(409, 'Dieser Wareneingang besitzt bereits ein unveränderliches Original')
                value = dict(receipt_id=receipt_id, order_id=receipt['order_id'], project_id=project_id,
                             receipt_reference=receipt['receipt_reference'], received_on=receipt['received_on'],
                             order_reference=confirmation['order_reference'], original=original)
                self.office.db.execute('INSERT INTO business_delivery_documents(receipt_id,project_id,media_id,payload_json,content_hash,created_by,created_at) VALUES(?,?,?,?,?,?,?)',
                    (receipt_id, project_id, body['media_id'], canonical(value), _hash(value), fresh['id'], self.now()))
                return self.document(fresh, receipt_id)

            result = self.write(actor, 'documents.write', 'business.delivery.document_bound', project_id, data, receipt_id, save)
            # Current classification access applies to receipts just as it does to first writes.
            current = self.document(actor, receipt_id)
            if result != current:
                raise Problem(500, 'Original-Lieferschein und Empfangsbestätigung stimmen nicht überein')
            return result

    def _sources(self, project_id, receipt_id, line_index, issue_id):
        receipt, confirmation, source = self._receipt(receipt_id)
        if source['project_id'] != project_id:
            raise Problem(404, 'Lieferung gehört nicht zum Projekt')
        if type(line_index) is not int or line_index < 0:
            raise Problem(400, 'Lieferpositionsindex erwartet')
        line = self.office.db.execute('SELECT * FROM business_purchase_receipt_lines WHERE receipt_id=? AND line_index=?', (receipt_id, line_index)).fetchone()
        if line is None:
            raise Problem(404, 'Lieferposition nicht verfügbar')
        identifier(issue_id, 'Entnahme-ID')
        issue = self.office.db.execute('SELECT * FROM business_stock_movements WHERE id=?', (issue_id,)).fetchone()
        inbound = self.office.db.execute('SELECT * FROM business_stock_movements WHERE id=?', (line['movement_id'],)).fetchone()
        if issue is None or issue['project_id'] != project_id:
            raise Problem(404, 'Entnahme nicht im Projekt verfügbar')
        if (issue['kind'] != 'issue' or inbound is None or inbound['kind'] != 'receive' or
                issue['article_id'] != line['article_id'] or
                json.loads(issue['article_snapshot_json']).get('unit') != line['unit'] or
                issue['from_location_id'] != receipt['location_id'] or
                inbound['to_location_id'] != receipt['location_id'] or
                inbound['sequence_number'] >= issue['sequence_number']):
            raise Problem(409, 'Eine passende direkte Entnahme nach dieser Lieferung ist erforderlich; Transferketten werden nicht automatisch zugeordnet')
        ordered = source['items'][line_index]['article_snapshot']
        if ordered['id'] != line['article_id'] or ordered['unit'] != line['unit']:
            raise Problem(500, 'Artikelidentität der Lieferung ist beschädigt')
        return receipt, confirmation, line, issue, ordered

    def _origin(self, row, actor=None):
        value = json.loads(row['payload_json'])
        if _hash(value) != row['content_hash']:
            raise Problem(500, 'Geräteherkunft ist beschädigt')
        if actor is not None:
            self._authority(actor, row['project_id'])
        receipt, confirmation, line, issue, article = self._sources(row['project_id'], row['receipt_id'], row['line_index'], row['issue_movement_id'])
        document_row = self.office.db.execute('SELECT * FROM business_delivery_documents WHERE receipt_id=?', (row['receipt_id'],)).fetchone()
        if document_row is None:
            raise Problem(500, 'Original-Lieferschein der Geräteherkunft fehlt')
        document = self._document(document_row, actor)
        asset_row = self.office.db.execute('SELECT * FROM business_assets WHERE id=? AND project_id=?', (row['asset_id'], row['project_id'])).fetchone()
        if asset_row is None:
            raise Problem(500, 'Gerät der Herkunft fehlt')
        asset = json.loads(asset_row['payload_json'])
        if (value.get('asset_id') != row['asset_id'] or value.get('project_id') != row['project_id'] or
                value.get('receipt_id') != row['receipt_id'] or value.get('line_index') != row['line_index'] or
                value.get('issue_movement_id') != row['issue_movement_id'] or value.get('quantity') != row['quantity'] or
                value.get('article') != {key: article[key] for key in ('id', 'code', 'name', 'unit', 'kind')} or
                row['article_id'] != line['article_id'] or _serial(asset['serial_number']) != row['serial_key'] or
                value.get('serial_number') != asset['serial_number'] or value.get('document_hash') != document['content_hash'] or
                value.get('order_id') != receipt['order_id'] or value.get('order_reference') != confirmation['order_reference'] or
                value.get('receipt_reference') != receipt['receipt_reference'] or value.get('received_on') != receipt['received_on'] or
                value.get('location_id') != receipt['location_id'] or value.get('receipt_movement_id') != line['movement_id'] or
                value.get('issue_sequence_number') != issue['sequence_number'] or value.get('attribution') != 'explicitly_confirmed'):
            raise Problem(500, 'Geräteherkunft stimmt nicht mit ihren Originalquellen überein')
        historical = self.office.db.execute("SELECT payload_json FROM business_maintenance_versions WHERE kind='asset' AND object_id=? AND revision=?", (row['asset_id'], value.get('asset_revision'))).fetchone()
        if historical is None or json.loads(historical['payload_json'])['serial_number'] != value['serial_number']:
            raise Problem(500, 'Ursprüngliche Gerätefassung fehlt')
        decimal(row['quantity'], positive=True)
        return dict(value, content_hash=row['content_hash'], created_by=row['created_by'], created_at=row['created_at'], document=document)

    def origin(self, actor, asset_id):
        identifier(asset_id, 'Geräte-ID')
        with transaction(self.office):
            asset = self.office.db.execute('SELECT project_id FROM business_assets WHERE id=?', (asset_id,)).fetchone()
            if asset is None:
                raise Problem(404, 'Gerät nicht verfügbar')
            self._authority(actor, asset['project_id'])
            row = self.office.db.execute('SELECT * FROM business_asset_origins WHERE asset_id=?', (asset_id,)).fetchone()
            if row is None:
                raise Problem(404, 'Noch keine Lieferherkunft zugeordnet')
            return self._origin(row, actor)

    def _bind(self, actor, project_id, asset_id, data):
        if data.get('confirmed') is not True:
            raise Problem(400, 'Tatsächliche Herkunft und Menge ausdrücklich bestätigen')
        row = self.office.db.execute('SELECT * FROM business_assets WHERE id=? AND project_id=?', (asset_id, project_id)).fetchone()
        if row is None:
            raise Problem(404, 'Gerät nicht verfügbar')
        if data.get('asset_revision') != row['revision'] or type(data.get('asset_revision')) is not int:
            raise Problem(409, 'Gerät wurde geändert; aktuelle Fassung prüfen')
        if self.office.db.execute('SELECT 1 FROM business_asset_origins WHERE asset_id=?', (asset_id,)).fetchone():
            raise Problem(409, 'Dieses Gerät besitzt bereits eine unveränderliche Lieferherkunft')
        asset = json.loads(row['payload_json'])
        if not asset['active']:
            raise Problem(409, 'Für die Herkunftsbestätigung muss das Gerät aktiv sein')
        serial_key = _serial(asset['serial_number'])
        receipt, confirmation, line, issue, article = self._sources(project_id, data['receipt_id'], data['line_index'], data['issue_movement_id'])
        document = self.document(actor, data['receipt_id'])
        amount = decimal(data.get('quantity'), 'Gerätemenge', positive=True)
        assigned = sum((Decimal(r['quantity']) for r in self.office.db.execute('SELECT quantity FROM business_asset_origins WHERE receipt_id=? AND line_index=?', (receipt['id'], line['line_index'])).fetchall()), Decimal(0))
        from business_purchase_changes import returned_quantity
        returned = returned_quantity(self.office, receipt['id'], line['line_index'])
        if amount > Decimal(line['quantity']) - assigned - returned or amount > _remaining_issue(self.office, issue):
            raise Problem(409, 'Die bestätigte Menge übersteigt die noch ungebundene Liefer- oder Entnahmemenge')
        if self.office.db.execute('SELECT 1 FROM business_asset_origins WHERE article_id=? AND serial_key=?', (line['article_id'], serial_key)).fetchone():
            raise Problem(409, 'Diese Artikel-Seriennummer besitzt bereits eine Lieferherkunft')
        value = dict(asset_id=asset_id, project_id=project_id, asset_revision=row['revision'], serial_number=asset['serial_number'],
                     receipt_id=receipt['id'], line_index=line['line_index'], order_id=receipt['order_id'],
                     order_reference=confirmation['order_reference'], receipt_reference=receipt['receipt_reference'],
                     received_on=receipt['received_on'], location_id=receipt['location_id'], receipt_movement_id=line['movement_id'],
                     issue_movement_id=issue['id'], issue_sequence_number=issue['sequence_number'], quantity=quantity(amount),
                     article={key: article[key] for key in ('id', 'code', 'name', 'unit', 'kind')},
                     document_hash=document['content_hash'], attribution='explicitly_confirmed')
        self.office.db.execute('INSERT INTO business_asset_origins(asset_id,project_id,receipt_id,line_index,issue_movement_id,article_id,serial_key,quantity,payload_json,content_hash,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
            (asset_id, project_id, receipt['id'], line['line_index'], issue['id'], line['article_id'], serial_key,
             quantity(amount), canonical(value), _hash(value), actor['id'], self.now()))
        return self.origin(actor, asset_id)

    def bind(self, actor, asset_id, data):
        identifier(asset_id, 'Geräte-ID')
        if not isinstance(data, dict) or set(data) != {'request_id', 'asset_revision', 'receipt_id', 'line_index', 'issue_movement_id', 'quantity', 'confirmed'}:
            raise Problem(400, 'Gerätefassung, Lieferposition, Entnahme, Menge und Bestätigung erwartet')
        with transaction(self.office):
            asset = self.office.db.execute('SELECT project_id FROM business_assets WHERE id=?', (asset_id,)).fetchone()
            if asset is None:
                raise Problem(404, 'Gerät nicht verfügbar')
            project_id = asset['project_id']
            self._authority(actor, project_id, write=True)
            # Validate the currently protected original even on a stored replay.
            self.document(actor, data['receipt_id'])
            result = self.write(actor, 'documents.write', 'business.asset.origin_bound', project_id, data, asset_id,
                                lambda fresh, body: self._bind(fresh, project_id, asset_id, body))
            if result != self.origin(actor, asset_id):
                raise Problem(500, 'Geräteherkunft und Empfangsbestätigung stimmen nicht überein')
            return result

    def create(self, actor, data):
        fields = {'request_id', 'project_id', 'asset', 'receipt_id', 'line_index', 'issue_movement_id', 'quantity', 'confirmed'}
        if not isinstance(data, dict) or set(data) != fields:
            raise Problem(400, 'Geräteangaben, Lieferposition, Entnahme, Menge und Bestätigung erwartet')
        asset_fields = {'name', 'serial_number', 'asset_type', 'location', 'notes'}
        if not isinstance(data['asset'], dict) or set(data['asset']) - asset_fields or not {'name', 'serial_number'} <= set(data['asset']):
            raise Problem(400, 'Gerätename und Seriennummer erwartet')
        project_id = data['project_id']
        with transaction(self.office):
            self._authority(actor, project_id, write=True)
            self.document(actor, data['receipt_id'])

            def save(fresh, body):
                from business_maintenance import BusinessMaintenance
                # This nested domain call preserves the existing asset permissions,
                # versioning and receipt within the same database transaction.
                nested = uuid.uuid5(uuid.NAMESPACE_URL, 'smartplan:asset-origin:' + fresh['id'] + ':' + data['request_id']).hex
                asset = BusinessMaintenance(self.office, clock=self.clock).save_asset(fresh, project_id,
                    dict(body['asset'], request_id=nested))
                origin = self._bind(fresh, project_id, asset['id'], dict(body, asset_revision=asset['revision']))
                return dict(id=asset['id'], asset=asset, origin=origin)

            result = self.write(actor, 'documents.write', 'business.asset.created_from_delivery', project_id, data, None, save)
            if result['origin'] != self.origin(actor, result['id']):
                raise Problem(500, 'Geräteherkunft und Empfangsbestätigung stimmen nicht überein')
            return result

    def sources(self, actor, project_id, *, limit=25, offset=0):
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or not 0 <= offset <= 100000:
            raise Problem(400, 'Ungültige Seitenauswahl')
        with transaction(self.office):
            self._authority(actor, project_id)
            base = (' FROM business_purchase_receipt_lines l JOIN business_purchase_receipts r ON r.id=l.receipt_id '
                    'JOIN business_purchase_orders o ON o.id=r.order_id WHERE o.project_id=?')
            total = self.office.db.execute('SELECT COUNT(*) AS amount' + base, (project_id,)).fetchone()['amount']
            lines = self.office.db.execute('SELECT l.receipt_id,l.line_index' + base + ' ORDER BY r.created_at,r.id,l.line_index LIMIT ? OFFSET ?', (project_id, limit, offset)).fetchall()
            items = []
            for selected in lines:
                receipt, confirmation, source = self._receipt(selected['receipt_id'])
                line = self.office.db.execute('SELECT * FROM business_purchase_receipt_lines WHERE receipt_id=? AND line_index=?', (selected['receipt_id'], selected['line_index'])).fetchone()
                article = source['items'][line['line_index']]['article_snapshot']
                assigned = sum((Decimal(r['quantity']) for r in self.office.db.execute('SELECT quantity FROM business_asset_origins WHERE receipt_id=? AND line_index=?', (receipt['id'], line['line_index'])).fetchall()), Decimal(0))
                from business_purchase_changes import returned_quantity
                returned = returned_quantity(self.office, receipt['id'], line['line_index'])
                issues = []
                for issue in self.office.db.execute("SELECT * FROM business_stock_movements WHERE project_id=? AND article_id=? AND kind='issue' AND from_location_id=? ORDER BY sequence_number", (project_id, line['article_id'], receipt['location_id'])).fetchall():
                    try:
                        self._sources(project_id, receipt['id'], line['line_index'], issue['id'])
                    except Problem as error:
                        if error.status == 409:
                            continue
                        raise
                    remaining = _remaining_issue(self.office, issue)
                    if remaining > 0:
                        issues.append(dict(id=issue['id'], sequence_number=issue['sequence_number'], quantity=issue['quantity'],
                                           available_quantity=quantity(remaining), created_at=issue['created_at']))
                document = None
                try:
                    document = self.document(actor, receipt['id'])
                except Problem as error:
                    if error.status not in (403, 404):
                        raise
                items.append(dict(receipt_id=receipt['id'], line_index=line['line_index'], order_id=receipt['order_id'],
                    order_reference=confirmation['order_reference'], receipt_reference=receipt['receipt_reference'],
                    received_on=receipt['received_on'], location_id=receipt['location_id'], quantity=line['quantity'],
                    available_quantity=quantity(Decimal(line['quantity']) - assigned - returned),
                    article={key: article[key] for key in ('id', 'code', 'name', 'unit', 'kind')},
                    document=document, document_accessible=document is not None, issues=issues))
            return dict(items=items, total=total, next_offset=offset + limit if offset + limit < total else None)


def validate_integrity(office):
    try:
        api = AssetProvenance(office)
        expected = set()
        for row in office.db.execute('SELECT * FROM business_delivery_documents').fetchall():
            expected.add(canonical(api._document(row)))
        assigned_receipts, assigned_issues = {}, {}
        for row in office.db.execute('SELECT * FROM business_asset_origins').fetchall():
            value = api._origin(row)
            expected.add(canonical(value))
            original = office.db.execute("SELECT payload_json FROM business_maintenance_versions WHERE kind='asset' AND object_id=? AND revision=?", (row['asset_id'], value['asset_revision'])).fetchone()
            expected.add(canonical(dict(id=row['asset_id'], asset=json.loads(original['payload_json']), origin=value)))
            amount = decimal(row['quantity'], positive=True)
            key = (row['receipt_id'], row['line_index'])
            assigned_receipts[key] = assigned_receipts.get(key, Decimal(0)) + amount
            assigned_issues[row['issue_movement_id']] = assigned_issues.get(row['issue_movement_id'], Decimal(0)) + amount
        for (receipt_id, index), amount in assigned_receipts.items():
            source = office.db.execute('SELECT quantity FROM business_purchase_receipt_lines WHERE receipt_id=? AND line_index=?', (receipt_id, index)).fetchone()
            from business_purchase_changes import returned_quantity
            if amount + returned_quantity(office, receipt_id, index) > Decimal(source['quantity']):
                raise ValueError('Delivery origin capacity exceeded')
        for issue_id in assigned_issues:
            issue = office.db.execute('SELECT * FROM business_stock_movements WHERE id=?', (issue_id,)).fetchone()
            if _remaining_issue(office, issue) < 0:
                raise ValueError('Issued origin capacity exceeded')
        for row in office.db.execute('SELECT * FROM business_asset_provenance_requests').fetchall():
            identifier(row['request_id'])
            if not re.fullmatch(r'[a-f0-9]{64}', row['request_hash']) or canonical(json.loads(row['result_json'])) not in expected:
                raise ValueError('Invalid asset provenance receipt')
        return True
    except (Problem, KeyError, IndexError, TypeError, json.JSONDecodeError, InvalidOperation) as error:
        raise ValueError('Invalid asset provenance data') from error


def methods(path):
    if path == '/assets/from-delivery':
        return 'POST'
    if path == '/assets/origin-sources':
        return 'GET'
    if re.fullmatch(r'/assets/' + _ID + r'/origin', path) or re.fullmatch(r'/purchasing/receipts/' + _ID + r'/document', path):
        return 'GET, POST'
    return None


def dispatch(office, actor, path, method, data):
    if methods(path) is None:
        return None
    if method not in methods(path).split(', '):
        raise Problem(405, 'Methode nicht unterstützt')
    query = data.get('_query', {})
    body = {key: value for key, value in data.items() if key != '_query'}
    if method == 'POST' and query:
        raise Problem(400, 'Keine zusätzlichen URL-Parameter bei einer Herkunftsbestätigung')
    if method == 'GET' and body:
        raise Problem(400, 'GET erlaubt keinen Inhalt')
    api = AssetProvenance(office)
    if path == '/assets/from-delivery':
        return api.create(actor, body), 201, 'application/json'
    if path == '/assets/origin-sources':
        if set(query) - {'project_id', 'limit', 'offset'}:
            raise Problem(400, 'Unbekannte Suchparameter')
        values = {}
        for key, value in query.items():
            if isinstance(value, list):
                if len(value) != 1:
                    raise Problem(400, 'Suchparameter darf nur einmal vorkommen')
                value = value[0]
            values[key] = value
        try:
            limit, offset = int(values.get('limit', '25')), int(values.get('offset', '0'))
        except (ValueError, TypeError):
            raise Problem(400, 'Ungültige Seitenauswahl') from None
        return api.sources(actor, values.get('project_id'), limit=limit, offset=offset), 200, 'application/json'
    if query:
        raise Problem(400, 'Keine zusätzlichen URL-Parameter bei einer Herkunft')
    asset = re.fullmatch(r'/assets/(' + _ID + r')/origin', path)
    if asset:
        result = api.origin(actor, asset[1]) if method == 'GET' else api.bind(actor, asset[1], body)
    else:
        receipt = re.fullmatch(r'/purchasing/receipts/(' + _ID + r')/document', path)[1]
        result = api.document(actor, receipt) if method == 'GET' else api.attach_document(actor, receipt, body)
    return result, 200 if method == 'GET' else 201, 'application/json'
