"""Project documentation with retained originals and immutable signed revisions.

No provider calls. The host API owns authentication and explicit schema migration;
these services recheck the current account, permission and project on every call.
"""
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import ast
import hashlib
import io
import json
import math
import re
import sqlite3
import uuid
from xml.sax.saxutils import escape

from core import Problem, Signature, canonical

CHUNK_SIZE = 262144
MAX_MEDIA_SIZE = 20 * 1024 * 1024
MEDIA_TYPES = {'image/png': 'PNG', 'image/jpeg': 'JPEG', 'image/webp': 'WEBP', 'application/pdf': 'PDF'}
ID = re.compile(r'[a-f0-9]{32}')


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA', 'BLOB'):
        raise ValueError('Unsupported binary column type')
    return request_schema('business_operations_requests') + [
        f'''CREATE TABLE IF NOT EXISTS business_media(
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
        filename TEXT NOT NULL, media_type TEXT NOT NULL, size INTEGER NOT NULL,
        sha256 TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('uploading','ready')),
        original {binary_type}, metadata_json TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>0),
        created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL,
        updated_by TEXT NOT NULL REFERENCES users(id), updated_at TEXT NOT NULL)''',
        f'''CREATE TABLE IF NOT EXISTS business_media_chunks(
        media_id TEXT NOT NULL REFERENCES business_media(id), chunk_index INTEGER NOT NULL CHECK(chunk_index>=0),
        data {binary_type} NOT NULL, sha256 TEXT NOT NULL, PRIMARY KEY(media_id,chunk_index))''',
        f'''CREATE TABLE IF NOT EXISTS business_operation_entries(
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), kind TEXT NOT NULL,
        payload_json TEXT NOT NULL, content_hash TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>0),
        pdf {binary_type}, pdf_sha256 TEXT,
        created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL,
        updated_by TEXT NOT NULL REFERENCES users(id), updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_operation_versions(
        kind TEXT NOT NULL, object_id TEXT NOT NULL, revision INTEGER NOT NULL,
        project_id TEXT NOT NULL REFERENCES projects(id), payload_json TEXT NOT NULL,
        PRIMARY KEY(kind,object_id,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_checklists(
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), payload_json TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK(revision>0), created_by TEXT NOT NULL REFERENCES users(id),
        created_at TEXT NOT NULL, updated_by TEXT NOT NULL REFERENCES users(id), updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_checklist_runs(
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), template_id TEXT NOT NULL REFERENCES business_checklists(id),
        payload_json TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>0), created_by TEXT NOT NULL REFERENCES users(id),
        created_at TEXT NOT NULL, updated_by TEXT NOT NULL REFERENCES users(id), updated_at TEXT NOT NULL)''',
        'CREATE INDEX IF NOT EXISTS business_media_project ON business_media(project_id,created_at,id)',
        'CREATE INDEX IF NOT EXISTS business_entries_project ON business_operation_entries(project_id,kind,created_at,id)',
    ]


def request_schema(table):
    return [f'''CREATE TABLE IF NOT EXISTS {table}(
        user_id TEXT NOT NULL REFERENCES users(id), request_id TEXT NOT NULL,
        request_hash TEXT NOT NULL, result_json TEXT NOT NULL,
        PRIMARY KEY(user_id,request_id))''']


def runtime_privileges():
    return {
        'business_operations_requests':('SELECT','INSERT'),
        'business_operation_versions':('SELECT','INSERT'),
        'business_media':('SELECT','INSERT','UPDATE'),
        'business_media_chunks':('SELECT','INSERT','DELETE'),
        'business_operation_entries':('SELECT','INSERT','UPDATE'),
        'business_checklists':('SELECT','INSERT','UPDATE'),
        'business_checklist_runs':('SELECT','INSERT','UPDATE'),
    }


@contextmanager
def transaction(office):
    with office.lock:
        if not isinstance(office.db, sqlite3.Connection):
            with office.db:
                yield
            return
        if not office.db.in_transaction:
            office.db.execute('BEGIN IMMEDIATE')
            try:
                yield
            except BaseException:
                office.db.rollback()
                raise
            else:
                office.db.commit()
            return
        name = 'business_' + uuid.uuid4().hex
        office.db.execute('SAVEPOINT ' + name)
        try:
            yield
        except BaseException:
            office.db.execute('ROLLBACK TO SAVEPOINT ' + name)
            office.db.execute('RELEASE SAVEPOINT ' + name)
            raise
        else:
            office.db.execute('RELEASE SAVEPOINT ' + name)


def text(value, name, maximum=1000, *, required=False):
    if not isinstance(value, str) or len(value) > maximum or any(ord(c) < 32 and c not in '\n\t' for c in value):
        raise Problem(400, 'Ungültiges Feld: ' + name)
    result = value.strip()
    if required and not result:
        raise Problem(400, 'Bitte ausfüllen: ' + name)
    return result


def identifier(value, name='ID'):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise Problem(400, 'Ungültige ' + name)
    return value


def decimal(value, name='Menge', *, positive=False, places=4):
    if not isinstance(value, str) or not re.fullmatch(r'-?\d{1,12}(?:\.\d{1,' + str(places) + r'})?', value):
        raise Problem(400, 'Dezimalzahl als Text erwartet: ' + name)
    result = Decimal(value)
    if not result.is_finite() or (positive and result <= 0):
        raise Problem(400, 'Ungültige Dezimalzahl: ' + name)
    return result


def quantity(value):
    return format(value.quantize(Decimal('.0001'), rounding=ROUND_HALF_UP), 'f')


def money(value):
    return format(value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP), 'f')


def iso_date(value, name='Datum', *, optional=False):
    if optional and value in ('', None):
        return None
    try:
        result = date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        result = None
    if result is None or not 1900 <= result.year <= 2200 or result.isoformat() != value:
        raise Problem(400, 'Ungültiges Datum: ' + name)
    return value


def instant(value, name='Zeitpunkt'):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) and len(value) <= 40 else None
    except ValueError:
        parsed = None
    if parsed is None or parsed.tzinfo is None or not 1900 <= parsed.year <= 2200:
        raise Problem(400, 'Zeitpunkt mit Zeitzone erwartet: ' + name)
    return parsed.astimezone(timezone.utc).isoformat(timespec='seconds')


class Domain:
    """Shared receipt and fresh authorization machinery, no schema side effects."""
    receipt_table = 'business_operations_requests'

    def __init__(self, office, *, clock=None):
        self.office = office
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def now(self):
        value = self.clock()
        if isinstance(value, (int, float)):
            value = datetime.fromtimestamp(value, timezone.utc)
        return value.astimezone(timezone.utc).isoformat(timespec='seconds')

    def access(self, actor, permission, project_id=None):
        from business_foundation import require_permission
        return require_permission(self.office, actor, permission, project_id=project_id)

    def write(self, actor, permission, action, project_id, data, target, callback):
        if not isinstance(data, dict):
            raise Problem(400, 'JSON-Objekt erwartet')
        request_id = identifier(data.get('request_id'), 'request_id')
        try:
            encoded=json.dumps([action,project_id,target,data],sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')
        except (TypeError,ValueError,UnicodeError):
            raise Problem(400,'Gültige begrenzte JSON-Daten erwartet') from None
        if len(encoded)>1_000_000: raise Problem(413,'Vorgang ist zu groß')
        fingerprint = hashlib.sha256(encoded).hexdigest()
        with transaction(self.office):
            fresh = self.access(actor, permission, project_id)
            row = self.office.db.execute(f'SELECT request_hash,result_json FROM {self.receipt_table} WHERE user_id=? AND request_id=?',
                                         (fresh['id'], request_id)).fetchone()
            if row:
                if row['request_hash'] != fingerprint:
                    raise Problem(409, 'request_id wurde bereits anders verwendet')
                return json.loads(row['result_json'])
            result = callback(fresh, {key: value for key, value in data.items() if key != 'request_id'})
            self.office.db.execute(f'INSERT INTO {self.receipt_table}(user_id,request_id,request_hash,result_json) VALUES(?,?,?,?)',
                                   (fresh['id'], request_id, fingerprint, canonical(result)))
            self.office.audit(fresh, action, result.get('id', target or project_id or request_id))
            return result

    def row(self, table, project_id, object_id):
        row = self.office.db.execute(f'SELECT * FROM {table} WHERE id=? AND project_id=?', (object_id, project_id)).fetchone()
        if row is None:
            raise Problem(404, 'Eintrag nicht verfügbar')
        return row

    def check_revision(self, data, current):
        if type(data.get('revision')) is not int or data['revision'] != current['revision']:
            raise Problem(409, 'Eintrag wurde inzwischen geändert')

    def _record(self, row):
        value = json.loads(row['payload_json'])
        return dict(value, **{key: row[key] for key in ('id', 'project_id', 'revision', 'created_by', 'created_at', 'updated_by', 'updated_at')})


UNIT_DIMENSIONS = {'m': (1, 0, 0), 'm2': (2, 0, 0), 'm3': (3, 0, 0),
                   'piece': (0, 1, 0), 'h': (0, 0, 1), 'factor': (0, 0, 0)}


def evaluate_measurement(line):
    if not isinstance(line, dict) or set(line) - {'description', 'unit', 'formula', 'variables'}:
        raise Problem(400, 'Ungültige Aufmaßposition')
    description = text(line.get('description'), 'Beschreibung', 1000, required=True)
    unit = line.get('unit')
    formula = text(line.get('formula'), 'Formel', 256, required=True)
    variables = line.get('variables')
    if not isinstance(unit,str) or unit not in UNIT_DIMENSIONS or not isinstance(variables, dict) or not 1 <= len(variables) <= 12:
        raise Problem(400, 'Aufmaßeinheit oder Variablen ungültig')
    parsed_variables = {}
    for key, value in variables.items():
        if (not isinstance(key, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,29}', key) or not isinstance(value, dict)
                or set(value) != {'value', 'unit'} or not isinstance(value['unit'],str) or value['unit'] not in UNIT_DIMENSIONS):
            raise Problem(400, 'Ungültige Aufmaßvariable')
        number = decimal(value['value'], key)
        if number < 0:
            raise Problem(400, 'Aufmaßwerte dürfen nicht negativ sein')
        parsed_variables[key] = (number, UNIT_DIMENSIONS[value['unit']])
    try:
        tree = ast.parse(formula, mode='eval')
    except (SyntaxError, ValueError):
        raise Problem(400, 'Ungültige Aufmaßformel')
    if len(list(ast.walk(tree))) > 80:
        raise Problem(400, 'Aufmaßformel zu komplex')

    def visit(node):
        if isinstance(node, ast.Name) and node.id in parsed_variables:
            return parsed_variables[node.id]
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            segment = ast.get_source_segment(formula, node)
            return decimal(segment, 'Formelkonstante'), (0, 0, 0)
        if isinstance(node, ast.BinOp) and type(node.op) in (ast.Add, ast.Sub, ast.Mult, ast.Div):
            left, ld = visit(node.left)
            right, rd = visit(node.right)
            if isinstance(node.op, (ast.Add, ast.Sub)):
                if ld != rd:
                    raise Problem(400, 'Einheiten der Summanden stimmen nicht überein')
                return (left + right if isinstance(node.op, ast.Add) else left - right), ld
            if isinstance(node.op, ast.Mult):
                return left * right, tuple(a + b for a, b in zip(ld, rd))
            if right == 0:
                raise Problem(400, 'Division durch null')
            return left / right, tuple(a - b for a, b in zip(ld, rd))
        raise Problem(400, 'Nur Zahlen, Variablen und + - * / sind erlaubt')
    try:
        with localcontext() as context:
            context.prec = 28
            result, dimension = visit(tree.body)
    except (InvalidOperation, ArithmeticError):
        raise Problem(400, 'Ungültiges Aufmaßergebnis')
    if dimension != UNIT_DIMENSIONS[unit] or not result.is_finite() or not 0 <= result <= Decimal('999999999999'):
        raise Problem(400, 'Formelergebnis und Einheit stimmen nicht überein')
    return dict(description=description, unit=unit, formula=formula, variables=variables, quantity=quantity(result))


def _annotations(value):
    if not isinstance(value, list) or len(value) > 200:
        raise Problem(400, 'Zu viele Markierungen')
    result = []
    for mark in value:
        if not isinstance(mark, dict) or mark.get('kind') not in ('line', 'rectangle', 'text'):
            raise Problem(400, 'Ungültige Markierung')
        kind = mark['kind']
        allowed = {'kind', 'color', 'point', 'text'} if kind == 'text' else {'kind', 'color', 'points'}
        if set(mark) - allowed:
            raise Problem(400, 'Unbekannte Markierungsfelder')
        color = mark.get('color', '#ff0000')
        if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise Problem(400, 'Ungültige Markierungsfarbe')
        points = [mark.get('point')] if kind == 'text' else mark.get('points')
        if not isinstance(points, list) or not (len(points) == 1 if kind == 'text' else 2 <= len(points) <= 100):
            raise Problem(400, 'Ungültige Markierungspunkte')
        if kind=='rectangle' and len(points)!=2: raise Problem(400,'Rechteck benötigt genau zwei Eckpunkte')
        for point in points:
            if (not isinstance(point, list) or len(point) != 2 or any(type(n) not in (int, float) or not math.isfinite(n) or not 0 <= n <= 1 for n in point)):
                raise Problem(400, 'Markierungen benötigen normalisierte Koordinaten')
        normalized = dict(kind=kind, color=color)
        if kind == 'text':
            normalized.update(point=points[0], text=text(mark.get('text'), 'Beschriftung', 500, required=True))
        else:
            normalized['points'] = points
        result.append(normalized)
    return result


def _image_check(content, media_type):
    if media_type == 'application/pdf':
        if not content.startswith(b'%PDF-') or b'%%EOF' not in content[-4096:]:
            raise Problem(400, 'Keine unterstützte PDF-Datei')
        return
    from PIL import Image, UnidentifiedImageError
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.format != MEDIA_TYPES[media_type] or image.width * image.height > 40_000_000 or max(image.size) > 15000:
                raise Problem(400, 'Bildformat oder Bildgröße nicht unterstützt')
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError):
        raise Problem(400, 'Bilddatei ist beschädigt oder nicht unterstützt')


def _strokes(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 100:
        raise Problem(400, 'Unterschrift fehlt')
    count = 0
    for stroke in value:
        if not isinstance(stroke, list) or not 2 <= len(stroke) <= 2000:
            raise Problem(400, 'Ungültige Unterschrift')
        count += len(stroke)
        for point in stroke:
            if not isinstance(point, list) or len(point) != 2 or any(type(n) not in (int, float) or not math.isfinite(n) or not 0 <= n <= 1 for n in point):
                raise Problem(400, 'Ungültige Unterschrift')
    if count > 10000:
        raise Problem(400, 'Unterschrift zu groß')
    return value


class BusinessOperations(Domain):
    def _media_permission(self,row,write=False):
        metadata=json.loads(row['metadata_json'])
        classification=metadata.get('classification','restricted')
        if classification=='personnel': return 'personnel.manage' if write else 'personnel.read'
        if classification=='restricted': return 'documents.classify'
        if classification=='financial': return 'finance.write' if write else 'finance.read'
        return 'documents.write' if write else 'documents.read'

    def _media_access(self,actor,row,write=False):
        metadata=json.loads(row['metadata_json'])
        fresh=self.access(actor,self._media_permission(row,write),row['project_id'])
        if metadata.get('purpose')=='receipt': self.access(fresh,'finance.write' if write else 'finance.read',row['project_id'])
        return fresh

    def _media_write_permission(self,project_id,media_id):
        with self.office.lock:
            return self._media_permission(self.row('business_media',project_id,media_id),True)

    def _media_result(self,actor,project_id,result):
        with self.office.lock:
            self._media_access(actor,self.row('business_media',project_id,result['id']))
            return result

    def _version(self, kind, value):
        self.office.db.execute('INSERT INTO business_operation_versions(kind,object_id,revision,project_id,payload_json) VALUES(?,?,?,?,?)',
                               (kind, value['id'], value['revision'], value['project_id'], canonical(value)))

    def _media(self, row):
        value = json.loads(row['metadata_json'])
        value.update({key: row[key] for key in ('id','project_id','filename','media_type','size','sha256','status','revision','created_by','created_at','updated_by','updated_at')})
        value['chunk_size'] = CHUNK_SIZE
        value['uploaded_chunks'] = list(range((row['size'] + CHUNK_SIZE - 1) // CHUNK_SIZE)) if row['status'] == 'ready' else [r['chunk_index'] for r in self.office.db.execute(
            'SELECT chunk_index FROM business_media_chunks WHERE media_id=? ORDER BY chunk_index', (row['id'],)).fetchall()]
        return value

    def new_media(self, actor, project_id, data):
        def create(fresh, body):
            if set(body) - {'filename','media_type','size','sha256','caption','captured_at','classification','purpose'}:
                raise Problem(400, 'Unbekannte Medienfelder')
            filename = text(body.get('filename'), 'Dateiname', 255, required=True)
            if '/' in filename or '\\' in filename or any(ord(c) < 32 for c in filename):
                raise Problem(400, 'Ungültiger Dateiname')
            if not isinstance(body.get('media_type'),str) or body['media_type'] not in MEDIA_TYPES or type(body.get('size')) is not int or not 1 <= body['size'] <= MAX_MEDIA_SIZE:
                raise Problem(400, 'Medientyp oder Größe nicht unterstützt')
            if not isinstance(body.get('sha256'), str) or not re.fullmatch(r'[a-f0-9]{64}', body['sha256']):
                raise Problem(400, 'SHA-256 fehlt')
            purpose=body.get('purpose','document' if body['media_type']=='application/pdf' else 'site_photo')
            if purpose not in ('site_photo','document','receipt') or (purpose=='site_photo' and body['media_type']=='application/pdf'):
                raise Problem(400,'Ungültiger Medienzweck')
            default='financial' if purpose=='receipt' else 'operational' if purpose=='site_photo' else 'restricted'
            classification=body.get('classification',default)
            if classification not in ('operational','financial','personnel','restricted') or (purpose=='receipt' and classification=='operational'):
                raise Problem(400,'Medienklassifikation verletzt den Dokumentzweck')
            if classification!=default: self.access(fresh,'documents.classify',project_id)
            metadata = dict(classification=classification,purpose=purpose,caption=text(body.get('caption', ''), 'Beschriftung', 2000), annotations=[],
                            captured_at=instant(body['captured_at']) if body.get('captured_at') else None)
            self._media_access(fresh,{'metadata_json':canonical(metadata),'project_id':project_id},True)
            identifier_, now = uuid.uuid4().hex, self.now()
            self.office.db.execute('''INSERT INTO business_media(id,project_id,filename,media_type,size,sha256,status,original,
                metadata_json,revision,created_by,created_at,updated_by,updated_at) VALUES(?,?,?,?,?,?,?,NULL,?,?,?,?,?,?)''',
                (identifier_, project_id, filename, body['media_type'], body['size'], body['sha256'], 'uploading', canonical(metadata), 1, fresh['id'], now, fresh['id'], now))
            value = self._media(self.row('business_media', project_id, identifier_))
            self._version('media', value)
            return value
        purpose=data.get('purpose') if isinstance(data,dict) else None
        permission='finance.write' if purpose=='receipt' else 'documents.write'
        return self._media_result(actor,project_id,self.write(actor, permission, 'business.media.created', project_id, data, None, create))

    def get_media(self, actor, project_id, media_id):
        with self.office.lock:
            row=self.row('business_media',project_id,media_id); self._media_access(actor,row)
            return self._media(row)

    def list_media(self, actor, project_id):
        with self.office.lock:
            self.access(actor, 'documents.read', project_id)
            result=[]
            for row in self.office.db.execute('SELECT * FROM business_media WHERE project_id=? ORDER BY created_at,id',(project_id,)).fetchall():
                try: self._media_access(actor,row)
                except Problem as error:
                    if error.status==403: continue
                    raise
                result.append(self._media(row))
            return result

    def put_media_chunk(self, actor, project_id, media_id, index, content):
        if type(index) is not int or index < 0 or not isinstance(content, bytes) or not 1 <= len(content) <= CHUNK_SIZE:
            raise Problem(400, 'Ungültiger Dateiblock')
        with transaction(self.office):
            row = self.row('business_media', project_id, media_id)
            self._media_access(actor,row,True)
            expected = min(CHUNK_SIZE, row['size'] - index * CHUNK_SIZE)
            if expected <= 0 or len(content) != expected:
                raise Problem(400, 'Dateiblock hat eine unerwartete Größe')
            if row['status'] == 'ready':
                if bytes(row['original'])[index*CHUNK_SIZE:index*CHUNK_SIZE+len(content)] != content:
                    raise Problem(409, 'Original kann nicht verändert werden')
                return self._media(row)
            previous = self.office.db.execute('SELECT data FROM business_media_chunks WHERE media_id=? AND chunk_index=?', (media_id,index)).fetchone()
            if previous:
                if bytes(previous['data']) != content:
                    raise Problem(409, 'Dateiblock wurde bereits anders übertragen')
            else:
                self.office.db.execute('INSERT INTO business_media_chunks(media_id,chunk_index,data,sha256) VALUES(?,?,?,?)', (media_id,index,content,hashlib.sha256(content).hexdigest()))
            return self._media(row)

    def complete_media(self, actor, project_id, media_id, data):
        def complete(fresh, body):
            if body:
                raise Problem(400, 'Unerwartete Abschlussfelder')
            row = self.row('business_media', project_id, media_id)
            self._media_access(fresh,row,True)
            if row['status'] == 'ready':
                return self._media(row)
            parts = self.office.db.execute('SELECT chunk_index,data,sha256 FROM business_media_chunks WHERE media_id=? ORDER BY chunk_index', (media_id,)).fetchall()
            count = (row['size'] + CHUNK_SIZE - 1) // CHUNK_SIZE
            if [part['chunk_index'] for part in parts] != list(range(count)):
                raise Problem(409, 'Datei ist noch unvollständig')
            if any(hashlib.sha256(bytes(part['data'])).hexdigest() != part['sha256'] for part in parts):
                raise Problem(409, 'Dateiblock-Prüfsumme stimmt nicht')
            content = b''.join(bytes(part['data']) for part in parts)
            if len(content) != row['size'] or hashlib.sha256(content).hexdigest() != row['sha256']:
                raise Problem(409, 'Original-Prüfsumme stimmt nicht')
            _image_check(content, row['media_type'])
            self.office.db.execute("UPDATE business_media SET original=?,status='ready',revision=revision+1,updated_by=?,updated_at=? WHERE id=?", (content,fresh['id'],self.now(),media_id))
            self.office.db.execute('DELETE FROM business_media_chunks WHERE media_id=?', (media_id,))
            value = self._media(self.row('business_media', project_id, media_id))
            self._version('media', value)
            return value
        return self._media_result(actor,project_id,self.write(actor, self._media_write_permission(project_id,media_id), 'business.media.completed', project_id, data, media_id, complete))

    def media_source(self, actor, project_id, media_id):
        with self.office.lock:
            row = self.row('business_media', project_id, media_id)
            self._media_access(actor,row)
            if row['status'] != 'ready':
                raise Problem(409, 'Original noch nicht vollständig')
            content = bytes(row['original'])
            if len(content) != row['size'] or hashlib.sha256(content).hexdigest() != row['sha256']:
                raise Problem(500, 'Original-Prüfsumme stimmt nicht')
            return content

    def annotate_media(self, actor, project_id, media_id, data):
        def save(fresh, body):
            if set(body) - {'revision','caption','annotations','classification'}:
                raise Problem(400, 'Unbekannte Markierungsfelder')
            row = self.row('business_media', project_id, media_id)
            self._media_access(fresh,row,True)
            self.check_revision(body,row)
            previous = json.loads(row['metadata_json'])
            if 'classification' in body:
                self.access(fresh,'documents.classify',project_id)
                if body['classification'] not in ('operational','financial','personnel','restricted') or (previous['purpose']=='receipt' and body['classification']=='operational'):
                    raise Problem(400,'Klassifikation verletzt den Dokumentzweck')
                previous['classification']=body['classification']
            previous.update(caption=text(body.get('caption',previous['caption']), 'Beschriftung',2000),
                            annotations=_annotations(body.get('annotations',previous['annotations'])))
            self.office.db.execute('UPDATE business_media SET metadata_json=?,revision=revision+1,updated_by=?,updated_at=? WHERE id=?',
                                   (canonical(previous),fresh['id'],self.now(),media_id))
            value=self._media(self.row('business_media',project_id,media_id)); self._version('media',value)
            return value
        return self._media_result(actor,project_id,self.write(actor,self._media_write_permission(project_id,media_id),'business.media.annotated',project_id,data,media_id,save))

    def _media_refs(self, project_id, value, actor=None):
        if not isinstance(value,list) or len(value)>100 or any(not isinstance(item,str) for item in value) or len(set(value))!=len(value):
            raise Problem(400,'Ungültige Medienreferenzen')
        for media_id in value:
            if not isinstance(media_id,str) or not ID.fullmatch(media_id):
                raise Problem(400,'Ungültige Medienreferenz')
            row=self.office.db.execute("SELECT * FROM business_media WHERE id=? AND project_id=? AND status='ready'",(media_id,project_id)).fetchone()
            if not row:
                raise Problem(400,'Medienreferenz ist nicht im Projekt verfügbar')
            if actor is not None: self._media_access(actor,row)
        return value

    def _entry_body(self, project_id, kind, body, previous=None, actor=None):
        allowed = {'title','media_ids','notes'}
        if kind=='diary': allowed |= {'entry_date','work','weather','crew_count','issues','article_lines','time_references'}
        elif kind=='defect': allowed |= {'details','location','due_date','assignee_id','status','resolution'}
        elif kind=='measurement': allowed |= {'lines'}
        elif kind=='service': allowed |= {'description'}
        else: raise Problem(400,'Unbekannte Dokumentationsart')
        if set(body)-allowed-{'revision'}:
            raise Problem(400,'Unbekannte Dokumentationsfelder')
        value=dict(previous or {}); value.update({key:item for key,item in body.items() if key!='revision'})
        value['title']=text(value.get('title'),'Titel',300,required=True)
        value['notes']=text(value.get('notes',''),'Notizen',10000)
        value['media_ids']=self._media_refs(project_id,value.get('media_ids',[]),actor)
        if kind=='diary':
            value['entry_date']=iso_date(value.get('entry_date',self.now()[:10]))
            for field in ('work','weather','issues'): value[field]=text(value.get(field,''),field,10000 if field!='weather' else 1000)
            count=value.get('crew_count',0)
            if type(count) is not int or not 0<=count<=1000: raise Problem(400,'Ungültige Personenzahl')
            value['crew_count']=count
            if 'article_lines' in body:
                lines=body['article_lines']
                if not isinstance(lines,list) or len(lines)>200: raise Problem(400,'Zu viele Artikelpositionen')
                normalized=[]
                for line in lines:
                    if not isinstance(line,dict) or set(line)!={'article_id','quantity'}: raise Problem(400,'Artikelübernahme benötigt ID und Menge')
                    source=self.office.db.execute('SELECT id,revision,payload_json FROM business_articles WHERE id=?',(identifier(line['article_id']),)).fetchone()
                    if not source: raise Problem(400,'Artikelreferenz ist nicht verfügbar')
                    article=json.loads(source['payload_json'])
                    if not article.get('active',True): raise Problem(400,'Artikelreferenz ist deaktiviert')
                    normalized.append(dict(article_id=source['id'],article_revision=source['revision'],quantity=quantity(decimal(line['quantity'],positive=True)),**{key:article[key] for key in ('code','name','unit','kind')}))
                value['article_lines']=normalized
            else: value.setdefault('article_lines',[])
            if 'time_references' in body:
                references=body['time_references']
                if not isinstance(references,list) or len(references)>200: raise Problem(400,'Zu viele Zeitreferenzen')
                from business_time import TimeTracking
                approved=TimeTracking(self.office).approved_work(actor,project_id)
                sources={(item['entry_id'],item['work_date']):item for item in approved['items']}
                normalized=[]; seen=set()
                for reference in references:
                    if not isinstance(reference,dict) or set(reference)!={'entry_id','work_date'}: raise Problem(400,'Zeitübernahme benötigt Eintrag und Arbeitstag')
                    key=(identifier(reference['entry_id']),iso_date(reference['work_date']))
                    if key in seen or key not in sources: raise Problem(400,'Zeitreferenz ist nicht genehmigt oder doppelt')
                    seen.add(key); normalized.append(sources[key])
                value['time_references']=normalized
            else: value.setdefault('time_references',[])
            value['imported_net_seconds']=sum(item['net_seconds'] for item in value['time_references'])
            value['status']='draft'
        elif kind=='defect':
            for field in ('details','location','resolution'): value[field]=text(value.get(field,''),field,10000)
            value['due_date']=iso_date(value.get('due_date'),optional=True)
            assignee=value.get('assignee_id')
            if assignee and not self.office.db.execute('SELECT 1 FROM users u JOIN assignments a ON a.user_id=u.id WHERE u.id=? AND u.active=1 AND a.project_id=?',(assignee,project_id)).fetchone():
                raise Problem(400,'Zuständiger ist dem Projekt nicht zugeordnet')
            value['assignee_id']=assignee
            value['status']=value.get('status','open')
            if value['status'] not in ('open','in_progress','resolved','accepted'): raise Problem(400,'Ungültiger Mangelstatus')
            if value['status'] in ('resolved','accepted') and not value['resolution']: raise Problem(400,'Mangelabschluss benötigt einen Nachweis')
        elif kind=='measurement':
            lines=value.get('lines')
            if not isinstance(lines,list) or not 1<=len(lines)<=200: raise Problem(400,'Aufmaß benötigt 1 bis 200 Positionen')
            value['lines']=[evaluate_measurement({key:v for key,v in line.items() if key!='quantity'}) if isinstance(line,dict) else evaluate_measurement(line) for line in lines]
            value['status']='draft'
        else:
            value['description']=text(value.get('description',''),'Beschreibung',30000)
            value['status']='draft'
        return value

    def _entry(self,row):
        value=self._record(row); value['kind']=row['kind']; value['content_hash']=row['content_hash']
        if row['pdf_sha256']: value['pdf_sha256']=row['pdf_sha256']
        return value

    def _insert_entry(self,fresh,project_id,kind,body):
        identifier_,now=uuid.uuid4().hex,self.now()
        content_hash=hashlib.sha256(canonical([project_id,kind,body]).encode()).hexdigest()
        self.office.db.execute('''INSERT INTO business_operation_entries(id,project_id,kind,payload_json,content_hash,revision,pdf,pdf_sha256,created_by,created_at,updated_by,updated_at)
            VALUES(?,?,?,?,?,1,NULL,NULL,?,?,?,?)''',(identifier_,project_id,kind,canonical(body),content_hash,fresh['id'],now,fresh['id'],now))
        value=self._entry(self.row('business_operation_entries',project_id,identifier_)); self._version('entry',value)
        return value

    def save_entry(self,actor,project_id,kind,data,entry_id=None):
        def save(fresh,body):
            previous=None
            if entry_id:
                row=self.row('business_operation_entries',project_id,entry_id)
                if row['kind']!=kind: raise Problem(404,'Dokument nicht verfügbar')
                previous=json.loads(row['payload_json'])
                if previous.get('status')=='signed': raise Problem(409,'Unterzeichnete Fassung ist unveränderlich')
                self.check_revision(body,row)
            value=self._entry_body(project_id,kind,body,previous,fresh)
            if not entry_id: return self._insert_entry(fresh,project_id,kind,value)
            content_hash=hashlib.sha256(canonical([project_id,kind,value]).encode()).hexdigest()
            self.office.db.execute('UPDATE business_operation_entries SET payload_json=?,content_hash=?,revision=revision+1,updated_by=?,updated_at=? WHERE id=?',(canonical(value),content_hash,fresh['id'],self.now(),entry_id))
            result=self._entry(self.row('business_operation_entries',project_id,entry_id)); self._version('entry',result)
            return result
        return self.write(actor,'documents.write','business.entry.'+kind+'.saved',project_id,data,entry_id,save)

    def get_entry(self,actor,project_id,entry_id):
        with self.office.lock:
            self.access(actor,'documents.read',project_id)
            return self._entry(self.row('business_operation_entries',project_id,entry_id))

    def list_entries(self,actor,project_id,kind):
        with self.office.lock:
            self.access(actor,'documents.read',project_id)
            return [self._entry(row) for row in self.office.db.execute('SELECT * FROM business_operation_entries WHERE project_id=? AND kind=? ORDER BY created_at,id',(project_id,kind)).fetchall()]

    def export_project(self,actor,project_id):
        with self.office.lock:
            self.access(actor,'documents.read',project_id)
            entries=[self._entry(row) for row in self.office.db.execute('SELECT * FROM business_operation_entries WHERE project_id=? ORDER BY created_at,id',(project_id,)).fetchall()]
            versions=[json.loads(row['payload_json']) for row in self.office.db.execute("SELECT payload_json FROM business_operation_versions WHERE project_id=? AND kind='entry' ORDER BY object_id,revision",(project_id,)).fetchall()]
            result=dict(schema_version=1,project_id=project_id,exported_at=self.now(),entries=entries,entry_history=versions,media=self.list_media(actor,project_id))
            if len(canonical(result).encode())>4*1024*1024: raise Problem(413,'Dokumentationsexport ist zu groß; Projektabschnitt einzeln laden')
            return result

    def sign_entry(self,actor,project_id,entry_id,data):
        # Rendering uses a captured revision; access and that revision are rechecked at publication.
        with self.office.lock:
            self.access(actor,'documents.write',project_id)
            row=self.row('business_operation_entries',project_id,entry_id)
            before=self._entry(row)
        if not isinstance(data,dict): raise Problem(400,'JSON-Objekt erwartet')
        signer=text(data.get('signer'),'Unterzeichner',200,required=True)
        strokes=_strokes(data.get('strokes'))
        signed_at=self.now()
        rendered=dict(before,signer=signer,strokes=strokes,signed_at=signed_at,status='signed')
        pdf=_render_pdf(rendered)
        if len(pdf)>10*1024*1024: raise Problem(400,'PDF zu groß')
        def sign(fresh,body):
            if set(body)-{'revision','expected_hash','signer','strokes'}: raise Problem(400,'Unbekannte Signaturfelder')
            row=self.row('business_operation_entries',project_id,entry_id)
            current=self._entry(row)
            if current['status']=='signed': raise Problem(409,'Dokument bereits unterzeichnet')
            self.check_revision(body,row)
            if row['content_hash']!=body.get('expected_hash') or row['content_hash']!=before['content_hash']:
                raise Problem(409,'Dokumentfassung stimmt nicht überein')
            value=json.loads(row['payload_json']); value.update(status='signed',signer=signer,strokes=strokes,signed_at=signed_at,signed_by=fresh['id'],signed_content_hash=row['content_hash'])
            self.office.db.execute('UPDATE business_operation_entries SET payload_json=?,pdf=?,pdf_sha256=?,revision=revision+1,updated_by=?,updated_at=? WHERE id=?',
                (canonical(value),pdf,hashlib.sha256(pdf).hexdigest(),fresh['id'],signed_at,entry_id))
            result=self._entry(self.row('business_operation_entries',project_id,entry_id)); self._version('entry',result)
            return result
        return self.write(actor,'documents.write','business.entry.signed',project_id,data,entry_id,sign)

    def entry_pdf(self,actor,project_id,entry_id):
        with self.office.lock:
            self.access(actor,'documents.read',project_id)
            row=self.row('business_operation_entries',project_id,entry_id)
            if not row['pdf']: raise Problem(409,'Dokument ist noch nicht unterzeichnet')
            content=bytes(row['pdf'])
            if hashlib.sha256(content).hexdigest()!=row['pdf_sha256']: raise Problem(500,'PDF-Prüfsumme stimmt nicht')
            return content

    def save_checklist(self,actor,project_id,data,checklist_id=None):
        def save(fresh,body):
            if set(body)-{'revision','title','items'}: raise Problem(400,'Unbekannte Checklistenfelder')
            old=self.row('business_checklists',project_id,checklist_id) if checklist_id else None
            if old: self.check_revision(body,old)
            payload=json.loads(old['payload_json']) if old else {}
            payload.update({k:v for k,v in body.items() if k!='revision'})
            payload['title']=text(payload.get('title'),'Checkliste',300,required=True)
            items=json.loads(canonical(payload.get('items')))
            if not isinstance(items,list) or not 1<=len(items)<=100: raise Problem(400,'Checkliste benötigt 1 bis 100 Punkte')
            keys=set()
            for item in items:
                if not isinstance(item,dict) or set(item)!={'key','label','required','type'} or type(item['required']) is not bool or item['type'] not in ('boolean','text','number'):
                    raise Problem(400,'Ungültiger Checklistenpunkt')
                if not isinstance(item['key'],str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,49}',item['key']) or item['key'] in keys: raise Problem(400,'Checklistenpunkt benötigt einen eindeutigen Schlüssel')
                keys.add(item['key']); item['label']=text(item['label'],'Prüfpunkt',500,required=True)
            payload['items']=items
            now=self.now()
            if old:
                self.office.db.execute('UPDATE business_checklists SET payload_json=?,revision=revision+1,updated_by=?,updated_at=? WHERE id=?',(canonical(payload),fresh['id'],now,checklist_id))
            else:
                identifier_=uuid.uuid4().hex
                self.office.db.execute('INSERT INTO business_checklists(id,project_id,payload_json,revision,created_by,created_at,updated_by,updated_at) VALUES(?,?,?,1,?,?,?,?)',(identifier_,project_id,canonical(payload),fresh['id'],now,fresh['id'],now))
            value=self._record(self.row('business_checklists',project_id,checklist_id or identifier_)); self._version('checklist',value)
            return value
        return self.write(actor,'documents.write','business.checklist.saved',project_id,data,checklist_id,save)

    def start_checklist(self,actor,project_id,checklist_id,data):
        def start(fresh,body):
            if body: raise Problem(400,'Unerwartete Startfelder')
            template=self._record(self.row('business_checklists',project_id,checklist_id))
            payload=dict(title=template['title'],template_id=checklist_id,template_revision=template['revision'],items=template['items'],answers={},status='open',report_id=None)
            identifier_,now=uuid.uuid4().hex,self.now()
            self.office.db.execute('INSERT INTO business_checklist_runs(id,project_id,template_id,payload_json,revision,created_by,created_at,updated_by,updated_at) VALUES(?,?,?,?,1,?,?,?,?)',(identifier_,project_id,checklist_id,canonical(payload),fresh['id'],now,fresh['id'],now))
            value=self._record(self.row('business_checklist_runs',project_id,identifier_)); self._version('checklist_run',value)
            return value
        return self.write(actor,'documents.write','business.checklist.started',project_id,data,checklist_id,start)

    def answer_checklist(self,actor,project_id,run_id,data):
        def save(fresh,body):
            if set(body)-{'revision','answers'}: raise Problem(400,'Unbekannte Antwortfelder')
            row=self.row('business_checklist_runs',project_id,run_id); self.check_revision(body,row)
            payload=json.loads(row['payload_json'])
            if payload['status']!='open': raise Problem(409,'Abgeschlossene Prüfliste ist unveränderlich')
            answers=body.get('answers')
            items={item['key']:item for item in payload['items']}
            if not isinstance(answers,dict) or set(answers)-set(items): raise Problem(400,'Unbekannte Prüflistenantwort')
            for key,value in answers.items():
                typ=items[key]['type']
                if typ=='boolean' and type(value) is not bool: raise Problem(400,'Ja/Nein-Antwort erwartet')
                if typ=='text': text(value,'Antwort',2000)
                if typ=='number': decimal(value,'Antwort')
            payload['answers'].update(answers)
            self.office.db.execute('UPDATE business_checklist_runs SET payload_json=?,revision=revision+1,updated_by=?,updated_at=? WHERE id=?',(canonical(payload),fresh['id'],self.now(),run_id))
            value=self._record(self.row('business_checklist_runs',project_id,run_id)); self._version('checklist_run',value)
            return value
        return self.write(actor,'documents.write','business.checklist.answered',project_id,data,run_id,save)

    def report_from_checklist(self,actor,project_id,run_id,data):
        def report(fresh,body):
            if body: raise Problem(400,'Unerwartete Berichtsfelder')
            row=self.row('business_checklist_runs',project_id,run_id); payload=json.loads(row['payload_json'])
            if payload['report_id']: return self._entry(self.row('business_operation_entries',project_id,payload['report_id']))
            if any(item['required'] and (item['key'] not in payload['answers'] or payload['answers'][item['key']] in ('',None)) for item in payload['items']):
                raise Problem(409,'Pflichtantworten fehlen')
            body=dict(title=payload['title'],description='Prüfliste: '+payload['title'],checklist=dict(run_id=run_id,template_id=payload['template_id'],template_revision=payload['template_revision'],items=payload['items'],answers=payload['answers']),status='draft',notes='',media_ids=[])
            result=self._insert_entry(fresh,project_id,'service',body)
            payload.update(status='completed',report_id=result['id'])
            self.office.db.execute('UPDATE business_checklist_runs SET payload_json=?,revision=revision+1,updated_by=?,updated_at=? WHERE id=?',(canonical(payload),fresh['id'],self.now(),run_id))
            value=self._record(self.row('business_checklist_runs',project_id,run_id)); self._version('checklist_run',value)
            return result
        return self.write(actor,'documents.write','business.checklist.reported',project_id,data,run_id,report)


def _render_pdf(value):
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    stream=io.BytesIO(); styles=getSampleStyleSheet()
    document=SimpleDocTemplate(stream,pageCompression=0)
    story=[Paragraph('Smartplan – '+escape(value['title']),styles['Title']),Spacer(1,12)]
    for key in ('project_id','kind','content_hash'):
        story.append(Paragraph(escape(key+': '+str(value[key])),styles['Normal']))
    for key in ('description','work','issues','notes','details','location','resolution'):
        if value.get(key): story.append(Paragraph(escape(key+': '+str(value[key])).replace('\n','<br/>'),styles['Normal']))
    for line in value.get('lines',[]):
        unit={'m2':'m²','m3':'m³','piece':'Stk.','h':'Std.'}.get(line['unit'],line['unit'])
        story.append(Paragraph(escape(line['description']+': '+line['formula']+' = '+line['quantity'].replace('.',',')+' '+unit),styles['Normal']))
        story.append(Paragraph(escape('; '.join(key+': '+item['value'].replace('.',',')+' '+item['unit'] for key,item in line['variables'].items())),styles['Normal']))
    for line in value.get('article_lines',[]):
        story.append(Paragraph(escape(line['name']+': '+line['quantity']+' '+line['unit']+' (Artikelrevision '+str(line['article_revision'])+')'),styles['Normal']))
    for source in value.get('time_references',[]):
        story.append(Paragraph(escape('Genehmigte Zeit '+source['work_date']+': '+str(source['net_seconds'])+' Sekunden; Quelle '+source['entry_id']),styles['Normal']))
    checklist=value.get('checklist',{})
    for item in checklist.get('items',[]):
        answer=checklist['answers'].get(item['key'],'')
        story.append(Paragraph(escape(item['label']+': '+('Ja' if answer is True else 'Nein' if answer is False else str(answer))),styles['Normal']))
    story.extend([Spacer(1,20),Paragraph('Unterzeichner: '+escape(value['signer']),styles['Normal']),
                  Paragraph('Unterzeichnet (UTC): '+escape(value['signed_at']),styles['Normal']),Signature(value['strokes'])])
    document.build(story)
    return stream.getvalue()


def _validate_integrity(office):
    api=BusinessOperations(office)
    for row in office.db.execute('SELECT * FROM business_media').fetchall():
        metadata=json.loads(row['metadata_json']); _annotations(metadata['annotations'])
        if metadata.get('classification') not in ('operational','financial','personnel','restricted') or metadata.get('purpose') not in ('site_photo','document','receipt') or (metadata['purpose']=='receipt' and metadata['classification']=='operational'):
            raise ValueError('Invalid media classification')
        chunks=office.db.execute('SELECT * FROM business_media_chunks WHERE media_id=? ORDER BY chunk_index',(row['id'],)).fetchall()
        for chunk in chunks:
            data=bytes(chunk['data']); expected=min(CHUNK_SIZE,row['size']-chunk['chunk_index']*CHUNK_SIZE)
            if expected<=0 or len(data)!=expected or hashlib.sha256(data).hexdigest()!=chunk['sha256']: raise ValueError('Invalid media chunk')
        if row['status']=='ready':
            content=bytes(row['original'] or b'')
            if len(content)!=row['size'] or hashlib.sha256(content).hexdigest()!=row['sha256'] or chunks: raise ValueError('Invalid original media')
            _image_check(content,row['media_type'])
        elif row['original'] is not None: raise ValueError('Incomplete media has an original')
    expected={}
    for table,kind,reader in [('business_media','media',api._media),('business_operation_entries','entry',api._entry),('business_checklists','checklist',api._record),('business_checklist_runs','checklist_run',api._record)]:
        for row in office.db.execute(f'SELECT * FROM {table}').fetchall(): expected[(kind,row['id'])]=reader(row)
    histories={}
    for row in office.db.execute('SELECT * FROM business_operation_versions ORDER BY kind,object_id,revision').fetchall():
        key=(row['kind'],row['object_id']); value=json.loads(row['payload_json']); history=histories.setdefault(key,[])
        if key not in expected or value.get('project_id')!=row['project_id'] or value.get('id')!=row['object_id'] or value.get('revision')!=len(history)+1: raise ValueError('Invalid documentation history')
        history.append(value)
    for key,value in expected.items():
        history=histories.get(key,[])
        # Upload chunk progress is transient and does not create annotation revisions.
        current=dict(value)
        if key[0]=='media': current.pop('uploaded_chunks',None)
        stored=dict(history[-1]) if history else {}
        if key[0]=='media': stored.pop('uploaded_chunks',None)
        if len(history)!=value['revision'] or stored!=current: raise ValueError('Documentation history mismatch')
        if key[0]=='media':
            immutable=('id','project_id','filename','media_type','size','sha256','created_by','created_at')
            if any(any(item[field]!=history[0][field] for field in immutable) for item in history):
                raise ValueError('Original media manifest changed')
    for row in office.db.execute('SELECT * FROM business_operation_entries').fetchall():
        value=json.loads(row['payload_json'])
        if value.get('status')=='signed':
            previous=histories[('entry',row['id'])][-2]
            if value.get('signed_content_hash')!=row['content_hash'] or row['content_hash']!=previous['content_hash'] or not row['pdf'] or hashlib.sha256(bytes(row['pdf'])).hexdigest()!=row['pdf_sha256']: raise ValueError('Invalid signed documentation')
            original={key:item for key,item in value.items() if key not in ('signer','strokes','signed_at','signed_by','signed_content_hash')}
            original['status']=previous['status']
            if hashlib.sha256(canonical([row['project_id'],row['kind'],original]).encode()).hexdigest()!=row['content_hash']:
                raise ValueError('Signed content differs from its frozen source')
            _strokes(value['strokes']); instant(value['signed_at'])
        else:
            if hashlib.sha256(canonical([row['project_id'],row['kind'],value]).encode()).hexdigest()!=row['content_hash'] or row['pdf'] is not None: raise ValueError('Invalid documentation content')
        if row['kind']=='measurement':
            for line in value['lines']:
                if evaluate_measurement({k:v for k,v in line.items() if k!='quantity'})!=line: raise ValueError('Invalid stored measurement')
        if row['kind']=='diary':
            if value['imported_net_seconds']!=sum(item['net_seconds'] for item in value['time_references']): raise ValueError('Invalid diary time total')
            for item in value['time_references']:
                if set(item)!={'entry_id','work_date','net_seconds'} or type(item['net_seconds']) is not int or not 0<=item['net_seconds']<=26*3600: raise ValueError('Invalid diary time reference')
                identifier(item['entry_id']); iso_date(item['work_date'])
            for item in value['article_lines']:
                if set(item)!={'article_id','article_revision','quantity','code','name','unit','kind'} or type(item['article_revision']) is not int or item['article_revision']<1: raise ValueError('Invalid diary article snapshot')
                identifier(item['article_id']); decimal(item['quantity'],positive=True)
        if 'checklist' in value:
            proof=value['checklist']
            if row['kind']!='service' or set(proof)!={'run_id','template_id','template_revision','items','answers'}:
                raise ValueError('Invalid checklist report provenance')
            run=office.db.execute('SELECT * FROM business_checklist_runs WHERE id=? AND project_id=?',(proof['run_id'],row['project_id'])).fetchone()
            if run is None: raise ValueError('Missing checklist run')
            source=json.loads(run['payload_json'])
            if source.get('status')!='completed' or source.get('report_id')!=row['id'] or any(source.get(field)!=proof[field] for field in ('template_id','template_revision','items','answers')):
                raise ValueError('Checklist report differs from its completed run')
        api._media_refs(row['project_id'],value.get('media_ids',[]))
    for row in office.db.execute('SELECT * FROM business_checklist_runs').fetchall():
        value=json.loads(row['payload_json'])
        template=office.db.execute("SELECT payload_json FROM business_operation_versions WHERE kind='checklist' AND object_id=? AND revision=? AND project_id=?",(row['template_id'],value['template_revision'],row['project_id'])).fetchone()
        if not template or value['template_id']!=row['template_id'] or json.loads(template['payload_json'])['items']!=value['items']:
            raise ValueError('Checklist run differs from its frozen template')
        if value['status'] not in ('open','completed') or (value['status']=='open' and value.get('report_id') is not None):
            raise ValueError('Invalid checklist run state')
    known_versions={canonical(value) for values in histories.values() for value in values}
    for row in office.db.execute('SELECT * FROM business_operations_requests').fetchall():
        result=json.loads(row['result_json'])
        if not ID.fullmatch(row['request_id']) or not re.fullmatch(r'[a-f0-9]{64}',row['request_hash']) or canonical(result) not in known_versions:
            raise ValueError('Invalid documentation receipt')
    return True


def validate_integrity(office):
    try:
        return _validate_integrity(office)
    except (Problem,TypeError,KeyError,IndexError,json.JSONDecodeError,InvalidOperation) as error:
        raise ValueError('Invalid documentation data') from error


def own_operational_photo(office,actor,media_id):
    """Narrow offline-device guard, independent of an owner's wider normal rights.

    This does not grant general gallery, PDF, receipt or classification access.
    The HTTP adapter still validates the route and operation body separately.
    """
    with office.lock:
        row=office.db.execute('SELECT * FROM business_media WHERE id=?',(media_id,)).fetchone()
        if row is None: return False
        current=BusinessOperations(office).access(actor,'documents.read',row['project_id'])
        metadata=json.loads(row['metadata_json'])
        return (row['created_by']==current['id'] and row['media_type'] in ('image/jpeg','image/png')
                and metadata.get('purpose')=='site_photo' and metadata.get('classification')=='operational')


def verified_receipt_media(office,actor,media_id,project_id=None):
    """Return one complete financial original to the finance receipt service."""
    api=BusinessOperations(office)
    with office.lock:
        row=office.db.execute('SELECT * FROM business_media WHERE id=?',(media_id,)).fetchone()
        if row is None or (project_id is not None and row['project_id']!=project_id): raise Problem(404,'Belegoriginal nicht verfügbar')
        metadata=json.loads(row['metadata_json'])
        api.access(actor,'finance.write',row['project_id'])
        api._media_access(actor,row,True)
        if metadata.get('purpose')!='receipt' or metadata.get('classification')=='operational': raise Problem(400,'Nur ausdrücklich geschützte Belegoriginale übernehmen')
        if row['status']!='ready': raise Problem(409,'Belegoriginal ist noch unvollständig')
        original=bytes(row['original'] or b'')
        if len(original)!=row['size'] or hashlib.sha256(original).hexdigest()!=row['sha256']: raise Problem(500,'Belegoriginal-Prüfsumme stimmt nicht')
        return dict(bytes=original,filename=row['filename'],media_type=row['media_type'],sha256=row['sha256'],project_id=row['project_id'])


def methods(path):
    if path=='/documentation/export' or re.fullmatch(r'/checklist-runs(?:/[a-f0-9]{32})?',path): return 'GET'
    if re.fullmatch(r'/(media|receipt-media|diary|defects|measurements|service-reports|checklists)(?:/[a-f0-9]{32})?(?:/(content|chunks/\d+|complete|sign|pdf|start|answers|report))?', path):
        if path.endswith(('/content','/pdf')): return 'GET'
        if re.search(r'/(chunks/\d+|complete|sign|start|answers|report)$',path): return 'POST'
        return 'GET, POST'
    return None


def dispatch(office,actor,path,method,data):
    """Business API adapter. Query keys are supplied by the host, never trusted as SQL."""
    api=BusinessOperations(office); query=data.get('_query',{}) if isinstance(data,dict) else {}
    body={k:v for k,v in data.items() if k!='_query'} if isinstance(data,dict) else data
    project_id=query.get('project_id') if method=='GET' else body.get('project_id')
    if isinstance(project_id,list): project_id=project_id[0] if len(project_id)==1 else None
    if method!='GET' and isinstance(body,dict): body={k:v for k,v in body.items() if k!='project_id'}
    if path=='/documentation/export':
        if method!='GET': raise Problem(405,'Methode nicht unterstützt')
        if not project_id: raise Problem(400,'project_id fehlt')
        return api.export_project(actor,project_id),200,'application/json'
    run_match=re.fullmatch(r'/checklist-runs(?:/([a-f0-9]{32}))?',path)
    if run_match:
        if method!='GET': raise Problem(405,'Methode nicht unterstützt')
        run_id=run_match[1]
        if not project_id and run_id:
            row=office.db.execute('SELECT project_id FROM business_checklist_runs WHERE id=?',(run_id,)).fetchone()
            if row: project_id=row['project_id']
        if not project_id: raise Problem(400,'project_id fehlt')
        api.access(actor,'documents.read',project_id)
        if run_id: return api._record(api.row('business_checklist_runs',project_id,run_id)),200,'application/json'
        return {'items':[api._record(row) for row in office.db.execute('SELECT * FROM business_checklist_runs WHERE project_id=? ORDER BY created_at,id',(project_id,)).fetchall()]},200,'application/json'
    match=re.fullmatch(r'/(media|receipt-media|diary|defects|measurements|service-reports|checklists)(?:/([a-f0-9]{32}))?(?:/(content|chunks/\d+|complete|sign|pdf|start|answers|report))?',path)
    if not match: return None
    resource,object_id,action=match.groups()
    if not project_id:
        if object_id:
            table='business_media' if resource in ('media','receipt-media') else 'business_checklists' if resource=='checklists' and action!='answers' and action!='report' else 'business_checklist_runs' if resource=='checklists' else 'business_operation_entries'
            row=office.db.execute(f'SELECT project_id FROM {table} WHERE id=?',(object_id,)).fetchone()
            if row: project_id=row['project_id']
        if not project_id: raise Problem(400,'project_id fehlt')
    if resource in ('media','receipt-media'):
        if resource=='receipt-media':
            api.access(actor,'finance.read' if method=='GET' else 'finance.write',project_id)
            if object_id:
                metadata=json.loads(api.row('business_media',project_id,object_id)['metadata_json'])
                if metadata['purpose']!='receipt': raise Problem(404,'Belegfoto nicht verfügbar')
            elif method=='POST':
                if body.get('purpose','receipt')!='receipt': raise Problem(400,'Belegfoto benötigt geschützten Belegzweck')
                body=dict(body,purpose='receipt')
        if not object_id:
            if method=='GET':
                items=api.list_media(actor,project_id)
                if resource=='receipt-media': items=[item for item in items if item['purpose']=='receipt']
                return {'items':items},200,'application/json'
            if method=='POST': return api.new_media(actor,project_id,body),201,'application/json'
        elif action=='content' and method=='GET':
            row=api.get_media(actor,project_id,object_id)
            return api.media_source(actor,project_id,object_id),200,row['media_type']
        elif action and action.startswith('chunks/') and method=='POST':
            import base64
            if not isinstance(body,dict) or set(body)!={'content_base64'} or not isinstance(body['content_base64'],str) or len(body['content_base64'])>349528: raise Problem(400,'Ungültiger Dateiblock')
            try: content=base64.b64decode(body['content_base64'],validate=True)
            except ValueError: raise Problem(400,'Ungültige Base64-Dateidaten')
            return api.put_media_chunk(actor,project_id,object_id,int(action.split('/')[1]),content),200,'application/json'
        elif action=='complete' and method=='POST': return api.complete_media(actor,project_id,object_id,body),200,'application/json'
        elif action is None:
            if method=='GET': return api.get_media(actor,project_id,object_id),200,'application/json'
            if method=='POST': return api.annotate_media(actor,project_id,object_id,body),200,'application/json'
    elif resource=='checklists':
        if not object_id:
            if method=='GET':
                api.access(actor,'documents.read',project_id)
                return {'items':[api._record(row) for row in office.db.execute('SELECT * FROM business_checklists WHERE project_id=? ORDER BY created_at,id',(project_id,)).fetchall()]},200,'application/json'
            if method=='POST': return api.save_checklist(actor,project_id,body),201,'application/json'
        if method=='POST':
            function={'start':api.start_checklist,'answers':api.answer_checklist,'report':api.report_from_checklist,None:api.save_checklist}.get(action)
            if function:
                value=function(actor,project_id,body,object_id) if action is None else function(actor,project_id,object_id,body)
                return value,200,'application/json'
        if method=='GET' and action is None:
            api.access(actor,'documents.read',project_id)
            return api._record(api.row('business_checklists',project_id,object_id)),200,'application/json'
    else:
        kind={'diary':'diary','defects':'defect','measurements':'measurement','service-reports':'service'}[resource]
        if object_id:
            api.access(actor,'documents.read' if method=='GET' else 'documents.write',project_id)
            if api.row('business_operation_entries',project_id,object_id)['kind']!=kind: raise Problem(404,'Dokument nicht verfügbar')
        if action=='sign' and method=='POST': return api.sign_entry(actor,project_id,object_id,body),200,'application/json'
        if action=='pdf' and method=='GET': return api.entry_pdf(actor,project_id,object_id),200,'application/pdf'
        if action is None:
            if method=='GET': return (api.get_entry(actor,project_id,object_id) if object_id else {'items':api.list_entries(actor,project_id,kind)}),200,'application/json'
            if method=='POST': return api.save_entry(actor,project_id,kind,body,object_id),200 if object_id else 201,'application/json'
    raise Problem(405,'Methode nicht unterstützt')
