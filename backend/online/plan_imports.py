"""Database-canonical project sources, resumable chunks and leased import jobs.

Call operations inside the caller's Office lock/transaction. Parsing and OCR
never run here. Both originals and published results are covered by DB backups.
"""
import hashlib
import json
import re
import sqlite3
import time
import uuid
from datetime import datetime, timezone

from core import Problem, canonical, text_field
import plan_deletions

CHUNK_SIZE = 262144
MAX_SOURCE_BYTES = 20 * 1024 * 1024
MAX_PREVIEW_BYTES = 40 * 1024 * 1024
MAX_RESULT_BYTES = 1024 * 1024
MAX_ATTEMPTS = 3
MEDIA_TYPES = {'image/jpeg', 'image/png', 'application/pdf'}
FIELDS = ('id,project_id,user_id,request_id,manifest_hash,filename,media_type,size,sha256,page,title,'
          'status,created_at,updated_at,attempts,lease_token,lease_until,error_code,preview_sha256,result_sha256,'
          'length(preview) AS preview_size')


class LeaseLost(RuntimeError):
    """A stale worker cannot publish over another attempt."""


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA', 'BLOB'):
        raise ValueError('Unsupported binary storage type')
    return [f'''CREATE TABLE IF NOT EXISTS plan_imports(
      id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
      user_id TEXT NOT NULL REFERENCES users(id), request_id TEXT NOT NULL,
      manifest_hash TEXT NOT NULL, filename TEXT NOT NULL, media_type TEXT NOT NULL,
      size INTEGER NOT NULL CHECK(size>0 AND size<=20971520), sha256 TEXT NOT NULL,
      page INTEGER NOT NULL CHECK(page>=0 AND page<50), title TEXT NOT NULL,
      status TEXT NOT NULL CHECK(status IN ('uploading','queued','running','needs_review','failed')),
      created_at DOUBLE PRECISION NOT NULL, updated_at DOUBLE PRECISION NOT NULL,
      attempts INTEGER NOT NULL DEFAULT 0, lease_token TEXT, lease_until DOUBLE PRECISION,
      error_code TEXT, preview {binary_type} CHECK(preview IS NULL OR length(preview)<=41943040), preview_sha256 TEXT,
      result TEXT CHECK(result IS NULL OR length(result)<=1048576), result_sha256 TEXT, UNIQUE(user_id,request_id))''',
      f'''CREATE TABLE IF NOT EXISTS plan_import_chunks(
      import_id TEXT NOT NULL REFERENCES plan_imports(id), chunk_index INTEGER NOT NULL CHECK(chunk_index>=0),
      data {binary_type} NOT NULL, sha256 TEXT NOT NULL, size INTEGER NOT NULL CHECK(size>0 AND size<=262144),
      CHECK(length(data)=size),
      PRIMARY KEY(import_id,chunk_index))''',
      'CREATE INDEX IF NOT EXISTS plan_imports_project ON plan_imports(project_id,created_at)',
      'CREATE INDEX IF NOT EXISTS plan_imports_queue ON plan_imports(status,lease_until,created_at)']


def ensure_sqlite_schema(office):
    """Add local-test tables at application startup; PostgreSQL uses migrate()."""
    if isinstance(office.db, sqlite3.Connection):
        with office.lock, office.db:
            for statement in schema_statements('BLOB'):
                office.db.execute(statement)


def _hash(value):
    return hashlib.sha256(value).hexdigest()


def _json(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, UnicodeError) as error:
        raise ValueError('Finite JSON recognition result required') from error


def _manifest(data, project_id):
    if not isinstance(data, dict) or set(data) != {'request_id', 'filename', 'media_type', 'size', 'sha256', 'page', 'title'}:
        raise Problem(400, 'Vollständiges Importmanifest erwartet')
    for key, length in (('request_id', 32), ('sha256', 64)):
        if not isinstance(data[key], str) or not re.fullmatch(r'[a-f0-9]{' + str(length) + '}', data[key]):
            raise Problem(400, 'Import-ID oder Prüfsumme ungültig')
    filename = text_field(data['filename'], 'Dateiname', 200)
    if any(char in filename for char in ('/', '\\')) or any(ord(char) < 32 for char in filename):
        raise Problem(400, 'Ein einfacher Dateiname ist erforderlich')
    if not isinstance(data['media_type'], str) or data['media_type'] not in MEDIA_TYPES:
        raise Problem(415, 'JPEG, PNG oder PDF erwartet')
    if type(data['size']) is not int or not 1 <= data['size'] <= MAX_SOURCE_BYTES:
        raise Problem(400, 'Quelldatei darf höchstens 20 MiB groß sein')
    if type(data['page']) is not int or not 0 <= data['page'] < 50 or (data['media_type'] != 'application/pdf' and data['page'] != 0):
        raise Problem(400, 'Ungültige PDF-Seite; Bilder verwenden Seite 0')
    return {**data, 'filename': filename, 'title': text_field(data['title'], 'Plantitel', 200), 'project_id': project_id}


def _validate_result(row, preview, result):
    if not isinstance(preview, bytes) or not preview.startswith(b'\x89PNG\r\n\x1a\n') or len(preview) > MAX_PREVIEW_BYTES:
        raise ValueError('Bounded PNG preview required')
    if (not isinstance(result, dict) or type(result.get('schema_version')) is not int
            or result['schema_version'] != 1 or result.get('status') != 'needs_review'
            or not isinstance(result.get('source'), dict) or result['source'].get('sha256') != row['sha256']
            or type(result['source'].get('selected_page')) is not int
            or result['source']['selected_page'] != row['page']):
        raise ValueError('Recognition result must match the source, selected page and result schema')
    encoded = _json(result)
    if len(encoded.encode('utf-8')) > MAX_RESULT_BYTES:
        raise ValueError('Recognition result too large')
    return encoded


class PlanImports:
    def __init__(self, office, *, clock=time.time):
        self.office, self.db, self.clock = office, office.db, clock

    def authorize(self, user, project_id, *, write=False):
        if write:
            self.office.require(user, ('owner', 'manager', 'technician'))
        self.office.project(user, project_id)

    def _row(self, import_id, project_id=None):
        row = self.db.execute('SELECT ' + FIELDS + ' FROM plan_imports WHERE id=?', (import_id,)).fetchone()
        if not row or (project_id is not None and row['project_id'] != project_id):
            raise Problem(404, 'Planquelle nicht verfügbar')
        return row

    def _status(self, row):
        deleted = plan_deletions.by_object(self.db, 'import', row['id'])
        if deleted:
            return plan_deletions.receipt(deleted)
        result = {key: row[key] for key in ('id', 'project_id', 'filename', 'media_type', 'size',
                                             'sha256', 'page', 'title', 'status', 'attempts',
                                             'preview_sha256', 'preview_size', 'result_sha256')}
        result.update(chunk_size=CHUNK_SIZE, chunk_count=(row['size'] + CHUNK_SIZE - 1) // CHUNK_SIZE,
                      uploaded_chunks=[item[0] for item in self.db.execute(
                          'SELECT chunk_index FROM plan_import_chunks WHERE import_id=? ORDER BY chunk_index', (row['id'],))],
                      preview_available=row['preview_sha256'] is not None,
                      result_available=row['result_sha256'] is not None,
                      error_code=row['error_code'], error_message=None)
        for key in ('created_at', 'updated_at'):
            result[key] = datetime.fromtimestamp(row[key], timezone.utc).isoformat()
        if row['error_code']:
            result['error'] = 'Verarbeitung fehlgeschlagen; die Originalquelle bleibt erhalten.'
            result['error_message'] = result['error']
        return result

    def create(self, user, project_id, data):
        self.authorize(user, project_id, write=True)
        manifest = _manifest(data, project_id)
        plan_deletions.assert_create_live(self.db, 'import', project_id, user['id'], manifest['request_id'])
        fingerprint = _hash(canonical(manifest).encode('utf-8'))
        previous = self.db.execute('SELECT ' + FIELDS + ' FROM plan_imports WHERE user_id=? AND request_id=?',
                                   (user['id'], manifest['request_id'])).fetchone()
        if previous:
            if previous['manifest_hash'] != fingerprint:
                raise Problem(409, 'Import-ID wurde bereits für einen anderen Inhalt verwendet')
            return self._status(previous)
        import_id, now = uuid.uuid4().hex, self.clock()
        self.db.execute('INSERT INTO plan_imports(id,project_id,user_id,request_id,manifest_hash,filename,media_type,'
                        'size,sha256,page,title,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (import_id, project_id, user['id'], manifest['request_id'], fingerprint, manifest['filename'],
                         manifest['media_type'], manifest['size'], manifest['sha256'], manifest['page'], manifest['title'],
                         'uploading', now, now))
        self.office.audit(user, 'plan_import.created', import_id)
        return self._status(self._row(import_id))

    def list(self, user, project_id):
        self.authorize(user, project_id)
        return [self._status(row) for row in self.db.execute('SELECT ' + FIELDS + ' FROM plan_imports '
                "WHERE project_id=? AND NOT EXISTS (SELECT 1 FROM plan_deletions d WHERE d.kind='import' "
                'AND d.object_id=plan_imports.id) ORDER BY created_at DESC,id DESC', (project_id,)).fetchall()]

    def get(self, user, project_id, import_id):
        self.authorize(user, project_id)
        row = self._row(import_id, project_id)
        plan_deletions.assert_object_live(self.db, 'import', import_id)
        return self._status(row)

    def delete(self, user, project_id, data):
        return plan_deletions.delete(self.office, user, project_id, 'import', data)

    def put_chunk(self, user, project_id, import_id, index, data):
        self.authorize(user, project_id, write=True)
        row = self._row(import_id, project_id)
        plan_deletions.assert_object_live(self.db, 'import', import_id)
        count = (row['size'] + CHUNK_SIZE - 1) // CHUNK_SIZE
        if type(index) is not int or not 0 <= index < count:
            raise Problem(400, 'Ungültiger Uploadabschnitt')
        expected = min(CHUNK_SIZE, row['size'] - index * CHUNK_SIZE)
        if not isinstance(data, bytes) or len(data) != expected:
            raise Problem(400, 'Uploadabschnitt hat nicht die erwartete Länge')
        previous = self.db.execute('SELECT data,sha256 FROM plan_import_chunks WHERE import_id=? AND chunk_index=?',
                                   (import_id, index)).fetchone()
        if previous:
            if bytes(previous['data']) != data or previous['sha256'] != _hash(data):
                raise Problem(409, 'Ein gespeicherter Originalabschnitt darf nicht ersetzt werden')
            return self._status(row)
        if row['status'] != 'uploading':
            raise Problem(409, 'Upload ist bereits abgeschlossen')
        self.db.execute('INSERT INTO plan_import_chunks(import_id,chunk_index,data,sha256,size) VALUES(?,?,?,?,?)',
                        (import_id, index, data, _hash(data), len(data)))
        self.db.execute('UPDATE plan_imports SET updated_at=? WHERE id=?', (self.clock(), import_id))
        return self._status(self._row(import_id))

    def source_bytes(self, row, *, require_complete=True):
        chunks = self.db.execute('SELECT chunk_index,data,sha256,size FROM plan_import_chunks '
                                 'WHERE import_id=? ORDER BY chunk_index', (row['id'],)).fetchall()
        expected_count = (row['size'] + CHUNK_SIZE - 1) // CHUNK_SIZE
        if require_complete and len(chunks) != expected_count:
            raise Problem(409, 'Upload ist noch nicht vollständig')
        pieces = []
        for chunk in chunks:
            index, content = chunk['chunk_index'], bytes(chunk['data'])
            if (not 0 <= index < expected_count or len(content) != min(CHUNK_SIZE, row['size'] - index * CHUNK_SIZE)
                    or chunk['size'] != len(content) or _hash(content) != chunk['sha256']):
                raise ValueError('Stored source chunk failed integrity validation')
            pieces.append(content)
        content = b''.join(pieces)
        if require_complete and (len(content) != row['size'] or _hash(content) != row['sha256']):
            raise Problem(409, 'Die vollständige Quelldatei stimmt nicht mit der Prüfsumme überein')
        return content

    def complete_upload(self, user, project_id, import_id):
        self.authorize(user, project_id, write=True)
        row = self._row(import_id, project_id)
        plan_deletions.assert_object_live(self.db, 'import', import_id)
        self.source_bytes(row)
        if row['status'] == 'uploading':
            self.db.execute("UPDATE plan_imports SET status='queued',updated_at=? WHERE id=?", (self.clock(), import_id))
            self.office.audit(user, 'plan_import.queued', import_id)
        return self._status(self._row(import_id))

    def source(self, user, project_id, import_id):
        self.authorize(user, project_id)
        row = self._row(import_id, project_id)
        plan_deletions.assert_object_live(self.db, 'import', import_id)
        if row['status'] == 'uploading':
            raise Problem(409, 'Upload ist noch nicht bestätigt')
        return self.source_bytes(row), row['media_type']

    def artifact(self, user, project_id, import_id, kind):
        self.authorize(user, project_id)
        row = self._row(import_id, project_id)
        plan_deletions.assert_object_live(self.db, 'import', import_id)
        if row['status'] != 'needs_review':
            raise Problem(409, 'Erkennungsergebnis ist noch nicht verfügbar')
        column = 'preview' if kind == 'preview' else 'result'
        saved = self.db.execute('SELECT preview,result FROM plan_imports WHERE id=?', (import_id,)).fetchone()[column]
        content = bytes(saved) if column == 'preview' else saved.encode('utf-8')
        if _hash(content) != row[column + '_sha256']:
            raise ValueError('Stored recognition artifact failed integrity validation')
        return content, 'image/png' if column == 'preview' else 'application/json'

    def claim(self, *, lease_seconds=90):
        if not isinstance(lease_seconds, (int, float)) or not 1 <= lease_seconds <= 300:
            raise ValueError('Bounded lease required')
        now = self.clock()
        rows = self.db.execute('SELECT ' + FIELDS + " FROM plan_imports WHERE (status='queued' OR "
                               "(status='running' AND lease_until<=?)) AND NOT EXISTS "
                               "(SELECT 1 FROM plan_deletions d WHERE d.kind='import' AND d.object_id=plan_imports.id) "
                               'ORDER BY created_at,id', (now,)).fetchall()
        for row in rows:
            if row['attempts'] >= MAX_ATTEMPTS:
                self.db.execute("UPDATE plan_imports SET status='failed',error_code='attempts_exhausted',"
                                'lease_token=NULL,lease_until=NULL,updated_at=? WHERE id=?', (now, row['id']))
                continue
            token = uuid.uuid4().hex
            self.db.execute("UPDATE plan_imports SET status='running',attempts=attempts+1,lease_token=?,"
                            'lease_until=?,updated_at=?,error_code=NULL WHERE id=?', (token, now + lease_seconds, now, row['id']))
            return dict(self._row(row['id']))
        return None

    def _lease(self, import_id, token):
        row = self._row(import_id)
        if plan_deletions.by_object(self.db, 'import', import_id):
            raise LeaseLost('Import was deleted')
        if row['status'] != 'running' or row['lease_token'] != token or row['lease_until'] <= self.clock():
            raise LeaseLost('Import lease expired or replaced')
        return row

    def fail(self, import_id, token, code='processing_failed'):
        self._lease(import_id, token)
        if not isinstance(code, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', code):
            code = 'processing_failed'
        self.db.execute("UPDATE plan_imports SET status='failed',error_code=?,lease_token=NULL,lease_until=NULL,"
                        'updated_at=? WHERE id=?', (code, self.clock(), import_id))
        return self._status(self._row(import_id))

    def release(self, import_id, token):
        """Refund a live attempt after infrastructure failure or graceful stop."""
        self._lease(import_id, token)
        self.db.execute("UPDATE plan_imports SET status='queued',attempts=CASE WHEN attempts>0 THEN attempts-1 ELSE 0 END,"
                        'lease_token=NULL,lease_until=NULL,error_code=NULL,updated_at=? WHERE id=?',
                        (self.clock(), import_id))
        return self._status(self._row(import_id))

    def publish(self, import_id, token, *, preview, result):
        row = self._lease(import_id, token)
        self.source_bytes(row)
        encoded = _validate_result(row, preview, result)
        self.db.execute("UPDATE plan_imports SET status='needs_review',preview=?,preview_sha256=?,result=?,result_sha256=?,"
                        'lease_token=NULL,lease_until=NULL,updated_at=? WHERE id=?',
                        (preview, _hash(preview), encoded, _hash(encoded.encode('utf-8')), self.clock(), import_id))
        return self._status(self._row(import_id))


def validate_integrity(office):
    """Backup/release verification, including partial uploads and all artifacts."""
    plan_deletions.validate_integrity(office)
    from workspace_api import validate_integrity as validate_workspace
    validate_workspace(office)
    from inquiry_attachments import validate_integrity as validate_attachments
    validate_attachments(office)
    from external_integrations import validate_integrity as validate_integrations
    validate_integrations(office)
    from integration_bridge import validate_integrity as validate_bridge
    validate_bridge(office)
    imports = PlanImports(office)
    for row in office.db.execute('SELECT ' + FIELDS + ' FROM plan_imports').fetchall():
        if plan_deletions.by_object(office.db, 'import', row['id']):
            saved = office.db.execute('SELECT preview,result FROM plan_imports WHERE id=?', (row['id'],)).fetchone()
            if (office.db.execute('SELECT 1 FROM plan_import_chunks WHERE import_id=?', (row['id'],)).fetchone()
                    or saved['preview'] is not None or saved['result'] is not None
                    or row['preview_sha256'] is not None or row['result_sha256'] is not None
                    or row['lease_token'] is not None or row['lease_until'] is not None
                    or row['filename'] or row['title']):
                raise ValueError('Deleted import still contains active source, result or lease data')
            continue
        imports.source_bytes(row, require_complete=row['status'] != 'uploading')
        saved = office.db.execute('SELECT preview,result FROM plan_imports WHERE id=?', (row['id'],)).fetchone()
        for column in ('preview', 'result'):
            content = saved[column]
            if content is None:
                if row[column + '_sha256'] is not None or row['status'] == 'needs_review':
                    raise ValueError('Missing canonical import artifact')
                continue
            content = bytes(content) if column == 'preview' else content.encode('utf-8')
            if _hash(content) != row[column + '_sha256']:
                raise ValueError('Canonical import artifact hash mismatch')
        if row['status'] == 'needs_review':
            _validate_result(row, bytes(saved['preview']), json.loads(saved['result']))
        elif saved['preview'] is not None or saved['result'] is not None:
            raise ValueError('Artifacts must belong to a reviewed import attempt')
    return True
