"""Canonical inquiry originals, resumable SPIN uploads and project handover.

No file is executed, parsed, downloaded from a provider or written to disk here.
Mutations preserve an enclosing caller transaction; standalone SQLite mutations
reserve the writer before checking the shared quota. PostgreSQL uses Office's
existing transaction/advisory lock. Normal callers must authenticate before
passing an actor; current activation, role and project scope are rechecked here.
"""
from contextlib import contextmanager
import hashlib
import math
import re
import sqlite3
import time
import uuid

from core import Problem, canonical
from inbound_connectors import InboundConnectors, _account
from inquiries import Inquiries


CHUNK_SIZE = 262144
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_MESSAGE_BYTES = 60 * 1024 * 1024
MAX_FILES = 30
MAX_RESERVED_BYTES = 2 * 1024 * 1024 * 1024
MAX_UPLOAD_OPS_PER_MINUTE = 600
_ID = re.compile(r'[a-f0-9]{32}')
_SOURCE_ID = re.compile(r'[A-Za-z0-9_-]{1,128}')
_SHA = re.compile(r'[a-f0-9]{64}')
_MEDIA = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+/[!#$%&'*+.^_`|~0-9A-Za-z-]+")
_DESCRIPTOR = ('source_attachment_id', 'filename', 'media_type', 'size', 'sha256')
_COPY_ACTION = 'inquiry_attachment.plan_copied'


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA', 'BLOB'):
        raise ValueError('Unsupported binary storage type')
    return [
        '''CREATE TABLE IF NOT EXISTS inquiry_attachment_sets(
          inquiry_id TEXT PRIMARY KEY REFERENCES inquiries(id), manifest_hash TEXT NOT NULL CHECK(length(manifest_hash)=64),
          expected_count INTEGER NOT NULL CHECK(expected_count>=0 AND expected_count<=30),
          total_bytes BIGINT NOT NULL CHECK(total_bytes>=0 AND total_bytes<=62914560),
          created_at DOUBLE PRECISION NOT NULL,
          CHECK((expected_count=0 AND total_bytes=0) OR (expected_count>0 AND total_bytes>0)))''',
        '''CREATE TABLE IF NOT EXISTS inquiry_attachments(
          id TEXT PRIMARY KEY CHECK(length(id)=32), inquiry_id TEXT NOT NULL REFERENCES inquiries(id),
          source_attachment_id TEXT NOT NULL CHECK(length(source_attachment_id)>0 AND length(source_attachment_id)<=2048),
          filename TEXT NOT NULL CHECK(length(filename)>0 AND length(filename)<=200),
          media_type TEXT NOT NULL CHECK(length(media_type)>0 AND length(media_type)<=100),
          size INTEGER NOT NULL CHECK(size>0 AND size<=20971520), sha256 TEXT NOT NULL CHECK(length(sha256)=64),
          status TEXT NOT NULL CHECK(status IN ('uploading','ready','deleted')),
          created_at DOUBLE PRECISION NOT NULL, updated_at DOUBLE PRECISION NOT NULL, deleted_at DOUBLE PRECISION,
          UNIQUE(inquiry_id,source_attachment_id),
          CHECK((status='deleted' AND deleted_at IS NOT NULL) OR (status<>'deleted' AND deleted_at IS NULL)))''',
        f'''CREATE TABLE IF NOT EXISTS inquiry_attachment_chunks(
          attachment_id TEXT NOT NULL REFERENCES inquiry_attachments(id),
          chunk_index INTEGER NOT NULL CHECK(chunk_index>=0 AND chunk_index<80),
          data {binary_type} NOT NULL, sha256 TEXT NOT NULL CHECK(length(sha256)=64),
          size INTEGER NOT NULL CHECK(size>0 AND size<=262144), CHECK(length(data)=size),
          PRIMARY KEY(attachment_id,chunk_index))''',
        '''CREATE TABLE IF NOT EXISTS inquiry_attachment_limits(
          token_id TEXT PRIMARY KEY REFERENCES inbound_import_tokens(id),
          window_started_at DOUBLE PRECISION NOT NULL,
          window_count INTEGER NOT NULL CHECK(window_count>=0 AND window_count<=600))''',
        'CREATE INDEX IF NOT EXISTS inquiry_attachments_inquiry ON inquiry_attachments(inquiry_id,source_attachment_id)',
        'CREATE INDEX IF NOT EXISTS inquiry_attachments_quota ON inquiry_attachments(status)',
    ]


def ensure_sqlite_schema(office):
    if isinstance(office.db, sqlite3.Connection):
        with office.lock, office.db:
            for statement in schema_statements('BLOB'):
                office.db.execute(statement)


@contextmanager
def _transaction(office):
    with office.lock:
        if not isinstance(office.db, sqlite3.Connection):
            with office.db:
                yield
            return
        standalone = not office.db.in_transaction
        if standalone:
            office.db.execute('BEGIN IMMEDIATE')
        name = 'attachments_' + uuid.uuid4().hex
        office.db.execute('SAVEPOINT ' + name)
        try:
            yield
        except BaseException:
            office.db.execute('ROLLBACK TO SAVEPOINT ' + name)
            office.db.execute('RELEASE SAVEPOINT ' + name)
            if standalone:
                office.db.rollback()
            raise
        else:
            office.db.execute('RELEASE SAVEPOINT ' + name)
            if standalone:
                office.db.commit()


def _identifier(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise Problem(400, 'Ungültige Anhang- oder Anfrage-ID')
    return value


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _descriptor(value):
    if not isinstance(value, dict) or set(value) != set(_DESCRIPTOR):
        raise Problem(400, 'Vollständige Anhangbeschreibung erwartet')
    source, filename, media = (value[key] for key in _DESCRIPTOR[:3])
    if not isinstance(source, str) or not 1 <= len(source) <= 2048 or not source.isprintable():
        raise Problem(400, 'Ungültige ursprüngliche Anhangkennung')
    if (not isinstance(filename, str) or not 1 <= len(filename) <= 200 or not filename.strip()
            or not filename.isprintable() or '/' in filename or '\\' in filename
            or filename.strip() in ('.', '..')):
        raise Problem(400, 'Ein einfacher Dateiname mit höchstens 200 Zeichen ist erforderlich')
    if not isinstance(media, str) or len(media) > 100 or not _MEDIA.fullmatch(media):
        raise Problem(400, 'Gültiger MIME-Typ ohne Parameter erwartet')
    if type(value['size']) is not int or value['size'] <= 0:
        raise Problem(400, 'Eine positive Dateigröße ist erforderlich')
    if value['size'] > MAX_FILE_BYTES:
        raise Problem(413, 'Ein Anhang darf höchstens 20 MiB groß sein')
    if not isinstance(value['sha256'], str) or not _SHA.fullmatch(value['sha256']):
        raise Problem(400, 'SHA-256-Prüfsumme des vollständigen Originals erwartet')
    return dict(value, filename=filename.strip(), media_type=media.lower())


def _manifest_hash(files):
    descriptors = [{key: row[key] for key in _DESCRIPTOR} for row in files]
    return _hash(canonical(sorted(descriptors, key=lambda item: item['source_attachment_id'])).encode('utf-8'))


class InquiryAttachments:
    def __init__(self, office, *, clock=time.time):
        self.office, self.db, self.clock = office, office.db, clock

    def _fresh(self, actor):
        if not isinstance(actor, dict) or not isinstance(actor.get('id'), str):
            raise Problem(401, 'Bitte anmelden')
        row = self.db.execute('SELECT id,email,role,active FROM users WHERE id=?', (actor['id'],)).fetchone()
        if not row or row['active'] != 1:
            raise Problem(401, 'Bitte anmelden')
        return {key: row[key] for key in ('id', 'email', 'role')}

    def _inquiry(self, actor, inquiry_id):
        actor = self._fresh(actor)
        inquiries = Inquiries(self.office)
        inquiries._authorize(actor)
        return actor, inquiries._row(inquiry_id)

    def _project(self, actor, project_id, *, write=False):
        actor = self._fresh(actor)
        self.office.project(actor, _identifier(project_id))
        if write:
            self.office.require(actor, ('owner', 'manager', 'technician'))
        return actor

    def _credential(self, token):
        return InboundConnectors(self.office, clock=self.clock)._credential(token, self.clock())

    def _bot_file(self, credential, attachment_id):
        row = self.db.execute('SELECT a.* FROM inquiry_attachments a JOIN inquiries i ON i.id=a.inquiry_id '
                              "WHERE a.id=? AND i.source='gmail' AND i.source_account=? AND i.created_by=?",
                              (_identifier(attachment_id), credential['source_account'], credential['owner_id'])).fetchone()
        if not row:
            raise Problem(404, 'Anhang nicht verfügbar')
        if row['status'] == 'deleted':
            raise Problem(410, 'Dieser Anhang wurde gelöscht')
        return row

    def _rate(self, credential):
        now = self.clock()
        previous = self.db.execute('SELECT * FROM inquiry_attachment_limits WHERE token_id=?',
                                   (credential['id'],)).fetchone()
        live = previous is not None and now < previous['window_started_at'] + 60
        count = previous['window_count'] if live else 0
        if count >= MAX_UPLOAD_OPS_PER_MINUTE:
            raise Problem(429, 'Anhangübernahme bitte später wiederholen')
        self.db.execute('INSERT INTO inquiry_attachment_limits(token_id,window_started_at,window_count) VALUES(?,?,?) '
                        'ON CONFLICT(token_id) DO UPDATE SET window_started_at=excluded.window_started_at,'
                        'window_count=excluded.window_count',
                        (credential['id'], previous['window_started_at'] if live else now, count + 1))

    @contextmanager
    def _upload_operation(self, token, attachment_id=None):
        """Count authenticated upload failures without partial file mutations.

        Public upload routes call this standalone. An explicit enclosing caller
        transaction still owns its final commit/rollback, including this counter.
        """
        failure = None
        with _transaction(self.office):
            credential = self._credential(token)
            self._rate(credential)
            try:
                with _transaction(self.office):
                    row = self._bot_file(credential, attachment_id) if attachment_id is not None else None
                    yield credential, row
            except Problem as error:
                failure = error
        if failure is not None:
            raise failure

    def _file(self, attachment_id, *, inquiry_id=None, project_id=None):
        row = self.db.execute('SELECT a.* FROM inquiry_attachments a JOIN inquiries i ON i.id=a.inquiry_id WHERE a.id=?'
                              + (' AND a.inquiry_id=?' if inquiry_id is not None else '')
                              + (" AND i.status='converted' AND i.project_id=?" if project_id is not None else ''),
                              (_identifier(attachment_id),) + ((inquiry_id,) if inquiry_id is not None else ())
                              + ((project_id,) if project_id is not None else ())).fetchone()
        if not row:
            raise Problem(404, 'Anhang nicht verfügbar')
        return row

    def _metadata(self, row, *, chunks=False):
        result = {key: row[key] for key in ('id', *_DESCRIPTOR, 'status')}
        if chunks:
            result['received_chunks'] = [item[0] for item in self.db.execute(
                'SELECT chunk_index FROM inquiry_attachment_chunks WHERE attachment_id=? ORDER BY chunk_index', (row['id'],))]
        return result

    def _summary(self, inquiry_id, *, chunks=False, deleted=False):
        announced = self.db.execute('SELECT * FROM inquiry_attachment_sets WHERE inquiry_id=?', (inquiry_id,)).fetchone()
        if not announced:
            return dict(status='not_announced', expected_count=None, ready_count=0, deleted_count=0, total_bytes=0, files=[])
        rows = self.db.execute('SELECT * FROM inquiry_attachments WHERE inquiry_id=? ORDER BY source_attachment_id,id',
                               (inquiry_id,)).fetchall()
        if (announced['expected_count'] != len(rows) or announced['total_bytes'] != sum(row['size'] for row in rows)
                or announced['manifest_hash'] != _manifest_hash(rows)):
            raise ValueError('Attachment set does not match immutable file descriptors')
        ready = sum(row['status'] == 'ready' for row in rows)
        removed = sum(row['status'] == 'deleted' for row in rows)
        return dict(status='complete' if ready + removed == len(rows) else 'uploading',
                    expected_count=announced['expected_count'], ready_count=ready, deleted_count=removed,
                    total_bytes=announced['total_bytes'],
                    files=[self._metadata(row, chunks=chunks) for row in rows if deleted or row['status'] != 'deleted'])

    def announce(self, token, data):
        if not isinstance(data, dict) or set(data) != {'source_account', 'source_id', 'attachments'}:
            raise Problem(400, 'Postfach, Nachrichten-ID und vollständiges Anhangmanifest erwartet')
        account = _account(data['source_account'])
        try:
            account.encode('utf-8')
        except UnicodeError:
            raise Problem(400, 'Gültiges Gmail-Postfach erwartet') from None
        if not isinstance(data['source_id'], str) or not _SOURCE_ID.fullmatch(data['source_id']):
            raise Problem(400, 'Stabile Gmail-Nachrichten-ID erwartet')
        if not isinstance(data['attachments'], list):
            raise Problem(400, 'Liste der ursprünglichen Anhänge erwartet')
        if len(data['attachments']) > MAX_FILES:
            raise Problem(413, 'Eine Nachricht darf höchstens 30 Anhänge enthalten')
        files = [_descriptor(value) for value in data['attachments']]
        if len({value['source_attachment_id'] for value in files}) != len(files):
            raise Problem(400, 'Ursprüngliche Anhangkennungen müssen eindeutig sein')
        total = sum(value['size'] for value in files)
        if total > MAX_MESSAGE_BYTES:
            raise Problem(413, 'Die Anhänge einer Nachricht dürfen zusammen höchstens 60 MiB groß sein')
        fingerprint = _manifest_hash(files)
        with self._upload_operation(token) as (credential, _):
            if credential['source_account'] != account:
                raise Problem(403, 'Importzugang gehört zu einem anderen Gmail-Postfach')
            inquiry = self.db.execute("SELECT id FROM inquiries WHERE source='gmail' AND source_account=? AND source_id=? "
                                      'AND created_by=?', (account, data['source_id'], credential['owner_id'])).fetchone()
            if not inquiry:
                raise Problem(404, 'Zuerst die zugehörige Nachricht übernehmen')
            previous = self.db.execute('SELECT manifest_hash FROM inquiry_attachment_sets WHERE inquiry_id=?',
                                       (inquiry['id'],)).fetchone()
            if previous:
                if previous['manifest_hash'] != fingerprint:
                    raise Problem(409, 'Das ursprüngliche Anhangmanifest darf nicht verändert werden')
            else:
                reserved = self.db.execute("SELECT COALESCE(SUM(size),0) FROM inquiry_attachments WHERE status<>'deleted'").fetchone()[0]
                if reserved + total > MAX_RESERVED_BYTES:
                    raise Problem(413, 'Anhangspeicher ausgeschöpft; nicht mehr benötigte Anhänge zuerst löschen')
                now = self.clock()
                self.db.execute('INSERT INTO inquiry_attachment_sets(inquiry_id,manifest_hash,expected_count,total_bytes,created_at) '
                                'VALUES(?,?,?,?,?)', (inquiry['id'], fingerprint, len(files), total, now))
                for value in files:
                    self.db.execute('INSERT INTO inquiry_attachments(id,inquiry_id,source_attachment_id,filename,media_type,size,'
                                    'sha256,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                                    (uuid.uuid4().hex, inquiry['id'], *(value[key] for key in _DESCRIPTOR), 'uploading', now, now))
                actor = dict(id=credential['owner_id'], email=credential['email'], role=credential['role'])
                self.office.audit(actor, 'inquiry_attachments.announced', inquiry['id'])
            result = self._summary(inquiry['id'], chunks=True, deleted=True)
            result['chunk_size'] = CHUNK_SIZE
            return result

    def put_chunk(self, token, attachment_id, index, data):
        with self._upload_operation(token, attachment_id) as (_, row):
            count = (row['size'] + CHUNK_SIZE - 1) // CHUNK_SIZE
            if type(index) is not int or not 0 <= index < count:
                raise Problem(400, 'Ungültiger Uploadabschnitt')
            if isinstance(data, bytes) and len(data) > CHUNK_SIZE:
                raise Problem(413, 'Uploadabschnitt ist zu groß')
            if not isinstance(data, bytes) or len(data) != min(CHUNK_SIZE, row['size'] - index * CHUNK_SIZE):
                raise Problem(400, 'Uploadabschnitt hat nicht die erwartete Länge')
            previous = self.db.execute('SELECT data,sha256 FROM inquiry_attachment_chunks WHERE attachment_id=? AND chunk_index=?',
                                       (row['id'], index)).fetchone()
            if previous:
                if bytes(previous['data']) != data or previous['sha256'] != _hash(data):
                    raise Problem(409, 'Ein gespeicherter Originalabschnitt darf nicht ersetzt werden')
            else:
                if row['status'] != 'uploading':
                    raise Problem(409, 'Upload ist bereits abgeschlossen')
                self.db.execute('INSERT INTO inquiry_attachment_chunks(attachment_id,chunk_index,data,sha256,size) VALUES(?,?,?,?,?)',
                                (row['id'], index, data, _hash(data), len(data)))
                self.db.execute('UPDATE inquiry_attachments SET updated_at=? WHERE id=?', (self.clock(), row['id']))
            return self._metadata(self._file(row['id']), chunks=True)

    def _source_bytes(self, row, *, require_complete=True):
        chunks = self.db.execute('SELECT chunk_index,data,sha256,size FROM inquiry_attachment_chunks '
                                 'WHERE attachment_id=? ORDER BY chunk_index', (row['id'],)).fetchall()
        if row['status'] == 'deleted':
            if chunks:
                raise ValueError('Deleted attachment still contains original bytes')
            raise Problem(410, 'Dieser Anhang wurde gelöscht')
        expected_count = (row['size'] + CHUNK_SIZE - 1) // CHUNK_SIZE
        if require_complete and len(chunks) != expected_count:
            raise Problem(409, 'Anhang ist noch nicht vollständig übertragen')
        pieces = []
        for chunk in chunks:
            index, content = chunk['chunk_index'], bytes(chunk['data'])
            if (type(index) is not int or not 0 <= index < expected_count
                    or len(content) != min(CHUNK_SIZE, row['size'] - index * CHUNK_SIZE)
                    or chunk['size'] != len(content) or _hash(content) != chunk['sha256']):
                raise ValueError('Stored attachment chunk failed integrity validation')
            pieces.append(content)
        content = b''.join(pieces)
        if require_complete and (len(content) != row['size'] or _hash(content) != row['sha256']):
            raise Problem(409, 'Das vollständige Original stimmt nicht mit der Prüfsumme überein')
        return content

    def complete(self, token, attachment_id):
        with self._upload_operation(token, attachment_id) as (credential, row):
            self._source_bytes(row)
            if row['status'] == 'uploading':
                self.db.execute("UPDATE inquiry_attachments SET status='ready',updated_at=? WHERE id=?", (self.clock(), row['id']))
                actor = dict(id=credential['owner_id'], email=credential['email'], role=credential['role'])
                self.office.audit(actor, 'inquiry_attachment.ready', row['id'])
            return self._metadata(self._file(row['id']), chunks=True)

    def for_inquiry(self, actor, inquiry_id):
        with _transaction(self.office):
            _, inquiry = self._inquiry(actor, inquiry_id)
            return self.summary(inquiry['id'])

    def summary(self, inquiry_id):
        """Internal metadata view after caller authorization; never an auth API."""
        return self._summary(_identifier(inquiry_id))

    def for_project(self, actor, project_id):
        with _transaction(self.office):
            self._project(actor, project_id)
            inquiries = self.db.execute("SELECT id,subject FROM inquiries WHERE project_id=? AND status='converted' "
                                        'ORDER BY received_at,id', (project_id,)).fetchall()
            result = dict(status='complete', expected_count=0, ready_count=0, deleted_count=0,
                          total_bytes=0, files=[], pending_count=0, unannounced_count=0)
            for inquiry in inquiries:
                current = self._summary(inquiry['id'])
                if current['expected_count'] is None:
                    result['unannounced_count'] += 1
                else:
                    result['expected_count'] += current['expected_count']
                for key in ('ready_count', 'deleted_count', 'total_bytes'):
                    result[key] += current[key]
                result['pending_count'] += sum(row['status'] == 'uploading' for row in current['files'])
                result['files'].extend(dict(row, inquiry_id=inquiry['id'], subject=inquiry['subject']) for row in current['files'])
            if result['unannounced_count']:
                result['expected_count'] = None
                result['status'] = 'not_announced'
            if result['pending_count']:
                result['status'] = 'uploading'
            return result

    def _content(self, row):
        if row['status'] == 'deleted':
            raise Problem(410, 'Dieser Anhang wurde gelöscht')
        if row['status'] != 'ready':
            raise Problem(409, 'Anhang ist noch nicht vollständig bestätigt')
        return self._source_bytes(row), self._metadata(row)

    def content_inquiry(self, actor, inquiry_id, attachment_id):
        with _transaction(self.office):
            self._inquiry(actor, inquiry_id)
            return self._content(self._file(attachment_id, inquiry_id=inquiry_id))

    def content_project(self, actor, project_id, attachment_id):
        with _transaction(self.office):
            self._project(actor, project_id)
            return self._content(self._file(attachment_id, project_id=project_id))

    def remove_inquiry(self, actor, inquiry_id, attachment_id):
        with _transaction(self.office):
            actor, _ = self._inquiry(actor, inquiry_id)
            row = self._file(attachment_id, inquiry_id=inquiry_id)
            if row['status'] != 'deleted':
                now = self.clock()
                self.db.execute('DELETE FROM inquiry_attachment_chunks WHERE attachment_id=?', (row['id'],))
                self.db.execute("UPDATE inquiry_attachments SET status='deleted',updated_at=?,deleted_at=? WHERE id=?",
                                (now, now, row['id']))
                self.office.audit(actor, 'inquiry_attachment.deleted', row['id'])
            return dict(id=row['id'], status='deleted', deleted=True)

    def copy_to_plan(self, actor, project_id, attachment_id, data):
        with _transaction(self.office):
            actor = self._project(actor, project_id, write=True)
            row = self._file(attachment_id, project_id=project_id)
            content, _ = self._content(row)
            if not isinstance(data, dict) or set(data) != {'request_id', 'page', 'title'}:
                raise Problem(400, 'Import-ID, Seite und Plantitel erwartet')
            _identifier(data['request_id'])
            if row['media_type'] not in ('application/pdf', 'image/png', 'image/jpeg'):
                raise Problem(415, 'Nur PDF, JPEG und PNG können als Planquelle übernommen werden')
            try:
                from online.plan_imports import PlanImports
            except ImportError:
                raise Problem(409, 'Planimport ist in dieser Installation nicht verfügbar') from None
            if isinstance(self.db, sqlite3.Connection) and not self.db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='plan_imports'").fetchone():
                raise Problem(409, 'Planimport ist in dieser Installation nicht verfügbar')
            previous = self.db.execute('SELECT id FROM plan_imports WHERE user_id=? AND request_id=?',
                                       (actor['id'], data['request_id'])).fetchone()
            # Bind retries to the original attachment as well as PlanImports'
            # immutable manifest, even when two attachments contain equal bytes.
            if previous and not self.db.execute('SELECT 1 FROM audit WHERE user_id=? AND action=? AND object_id=?',
                    (actor['id'], _COPY_ACTION, row['id'] + ':' + previous['id'])).fetchone():
                raise Problem(409, 'Diese Import-ID gehört zu einer anderen Planübernahme')
            imports = PlanImports(self.office, clock=self.clock)
            job = imports.create(actor, project_id, dict(data, filename=row['filename'], media_type=row['media_type'],
                                                       size=row['size'], sha256=row['sha256']))
            for index, start in enumerate(range(0, len(content), CHUNK_SIZE)):
                imports.put_chunk(actor, project_id, job['id'], index, content[start:start + CHUNK_SIZE])
            result = imports.complete_upload(actor, project_id, job['id'])
            if not previous:
                self.office.audit(actor, _COPY_ACTION, row['id'] + ':' + job['id'])
            return result


def validate_integrity(office):
    """Validate immutable manifests, reservations, partial chunks and originals."""
    attachments = InquiryAttachments(office)
    with office.lock:
        sets = office.db.execute('SELECT * FROM inquiry_attachment_sets').fetchall()
        known = {row['inquiry_id'] for row in sets}
        files = office.db.execute('SELECT * FROM inquiry_attachments').fetchall()
        identifiers = {row['id'] for row in files}
        reserved = 0
        try:
            for announced in sets:
                _identifier(announced['inquiry_id'])
                inquiry = office.db.execute('SELECT source FROM inquiries WHERE id=?', (announced['inquiry_id'],)).fetchone()
                if not inquiry or inquiry['source'] != 'gmail':
                    raise ValueError('Attachment manifest has no canonical Gmail inquiry')
                if (type(announced['expected_count']) is not int or not 0 <= announced['expected_count'] <= MAX_FILES
                        or type(announced['total_bytes']) is not int or not 0 <= announced['total_bytes'] <= MAX_MESSAGE_BYTES
                        or not isinstance(announced['manifest_hash'], str) or not _SHA.fullmatch(announced['manifest_hash'])
                        or type(announced['created_at']) not in (float, int) or not math.isfinite(announced['created_at'])):
                    raise ValueError('Invalid attachment manifest bounds')
                attachments._summary(announced['inquiry_id'], deleted=True)
            for row in files:
                _identifier(row['id'])
                descriptor = {key: row[key] for key in _DESCRIPTOR}
                if row['inquiry_id'] not in known or _descriptor(descriptor) != descriptor:
                    raise ValueError('Attachment has no immutable canonical manifest')
                for key in ('created_at', 'updated_at'):
                    if type(row[key]) not in (float, int) or not math.isfinite(row[key]):
                        raise ValueError('Invalid attachment timestamp')
                if row['status'] == 'deleted':
                    if (type(row['deleted_at']) not in (float, int) or not math.isfinite(row['deleted_at'])
                            or office.db.execute('SELECT 1 FROM inquiry_attachment_chunks WHERE attachment_id=?', (row['id'],)).fetchone()):
                        raise ValueError('Deleted attachment still contains original bytes or no deletion time')
                elif row['status'] in ('uploading', 'ready') and row['deleted_at'] is None:
                    reserved += row['size']
                    attachments._source_bytes(row, require_complete=row['status'] == 'ready')
                else:
                    raise ValueError('Invalid attachment state')
            if reserved > MAX_RESERVED_BYTES:
                raise ValueError('Attachment reservation quota exceeded')
            for chunk in office.db.execute('SELECT attachment_id FROM inquiry_attachment_chunks').fetchall():
                if chunk['attachment_id'] not in identifiers:
                    raise ValueError('Orphan original attachment chunk')
            for row in office.db.execute('SELECT * FROM inquiry_attachment_limits').fetchall():
                if (type(row['window_count']) is not int or not 0 <= row['window_count'] <= MAX_UPLOAD_OPS_PER_MINUTE
                        or type(row['window_started_at']) not in (float, int) or not math.isfinite(row['window_started_at'])
                        or not office.db.execute('SELECT 1 FROM inbound_import_tokens WHERE id=?', (row['token_id'],)).fetchone()):
                    raise ValueError('Invalid attachment upload limit')
        except (Problem, TypeError, KeyError, UnicodeError) as error:
            raise ValueError('Invalid canonical inquiry attachments') from error
    return True
