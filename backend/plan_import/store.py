"""Private, local-only source capture and leased import jobs.

This pilot store is deliberately separate from Office and its schema. Sources are
immutable; derived files and recognition output are published before SQLite may
refer to them. An interrupted publication can leave an unreferenced file, never
a confirmed result without its files. No imported document grants filesystem or
network authority.
"""
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import time
import uuid


MAX_SOURCE_BYTES = 20 * 1024 * 1024
MAX_DERIVED_BYTES = 40 * 1024 * 1024
MAX_RECOGNITION_BYTES = 1024 * 1024
MAX_ATTEMPTS = 3
_IDENTIFIER = re.compile(r'[a-f0-9]{32}')
_REQUEST = re.compile(r'[A-Za-z0-9_-]{1,128}')
_ARTIFACT = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}')
_APPLICATION_ID = 0x5350494D


class StoreError(ValueError):
    """A safe local-store validation or consistency error."""


class LeaseLost(StoreError):
    """The attempt no longer owns a live job lease."""


def _json(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError) as error:
        raise StoreError('Recognition output must be finite JSON.') from error


def _id(value):
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise StoreError('A lowercase UUID identifier is required.')
    return value


def _request(value):
    if not isinstance(value, str) or not _REQUEST.fullmatch(value):
        raise StoreError('A request/worker identifier of 1–128 letters, digits, _ or - is required.')
    return value


def _name(value):
    if not isinstance(value, str) or not _ARTIFACT.fullmatch(value) or '..' in value:
        raise StoreError('Artifact names must be safe, flat filenames.')
    return value


def _no_symlinks(path):
    if '..' in path.parts:
        raise StoreError('Parent traversal is not permitted.')
    for component in reversed((path, *path.parents)):
        try:
            if stat.S_ISLNK(component.lstat().st_mode):
                raise StoreError('Symlink paths are not permitted.')
        except FileNotFoundError:
            continue


def _fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _directory(path):
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or
            stat.S_IMODE(info.st_mode) != 0o700):
        raise StoreError('Store directories must be owned by this user and have mode 0700.')


def _regular(info, *, private=True):
    if not stat.S_ISREG(info.st_mode):
        raise StoreError('A regular file is required.')
    if private and (info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1):
        raise StoreError('Store files must be private, user-owned and not hard-linked.')


def _mkdir(path):
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        _directory(path)
    else:
        _fsync_directory(path.parent)


def _publish(path, content):
    """Publish a new file atomically without replacing any existing name.

    link+unlink provides an atomic no-replace publication, unlike os.replace or
    portable rename. Both names are on the same private filesystem/directory.
    """
    _directory(path.parent)
    temporary = path.parent / ('.pending-' + uuid.uuid4().hex)
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), 0o400)
            os.fsync(stream.fileno())
        os.link(temporary, path, follow_symlinks=False)
        temporary.unlink()
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _read(path, *, maximum, expected=None):
    _no_symlinks(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        _regular(os.fstat(stream.fileno()))
        content = stream.read(maximum + 1)
    if len(content) > maximum:
        raise StoreError('Stored file exceeds its size limit.')
    if expected and (len(content) != expected['size'] or hashlib.sha256(content).hexdigest() != expected['sha256']):
        raise StoreError('Stored file integrity check failed.')
    return content


def _media(content):
    if content.startswith(b'%PDF-'):
        return 'application/pdf'
    if content.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if content.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if len(content) >= 16 and content[4:8] == b'ftyp':
        brands = {content[index:index + 4] for index in range(8, min(len(content), 64), 4)}
        if brands & {b'heic', b'heix', b'hevc', b'hevx'}:
            return 'image/heic'
        if brands & {b'mif1', b'msf1'}:
            return 'image/heif'
    return 'application/octet-stream'


class ImportStore:
    def __init__(self, root, *, clock=None):
        self.root = Path(root).absolute()
        self._clock = clock or time.time
        _no_symlinks(self.root)
        # The caller supplies an existing parent; do not manufacture public
        # intermediate directories or change permissions of existing paths.
        _mkdir(self.root)
        _directory(self.root)
        self.originals = self.root / 'originals'
        self.derived = self.root / 'derived'
        self.recognition = self.root / 'recognition'
        self.database = self.root / 'imports.sqlite3'
        if (not self.database.exists() and not self.database.is_symlink() and
                any(path.exists() or path.is_symlink()
                    for path in (self.originals, self.derived, self.recognition))):
            raise StoreError('Store metadata is missing; preserve the existing files and inspect the store.')
        for path in (self.originals, self.derived, self.recognition):
            _mkdir(path)
        try:
            descriptor = os.open(self.database, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
            created = True
        except FileExistsError:
            descriptor = os.open(self.database, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
            created = False
        try:
            _regular(os.fstat(descriptor))
        finally:
            os.close(descriptor)
        with self._connection() as connection:
            # Do not even change journal mode on an unrelated SQLite database.
            app_id = connection.execute('PRAGMA application_id').fetchone()[0]
            version = connection.execute('PRAGMA user_version').fetchone()[0]
            tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if (app_id, version) != (_APPLICATION_ID, 1) and (not created or app_id or version or tables):
                raise StoreError('Unknown import-store database; preserve and inspect it.')
            connection.execute('PRAGMA journal_mode=WAL')
            connection.execute('BEGIN IMMEDIATE')
            app_id = connection.execute('PRAGMA application_id').fetchone()[0]
            version = connection.execute('PRAGMA user_version').fetchone()[0]
            tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if (app_id, version) != (_APPLICATION_ID, 1):
                if app_id or version or tables:
                    raise StoreError('Unknown import-store database; preserve and inspect it.')
                connection.execute('''CREATE TABLE sources(
                    source_id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, size INTEGER NOT NULL,
                    media_type TEXT NOT NULL, source_filename TEXT NOT NULL, created_at REAL NOT NULL)''')
                connection.execute('''CREATE TABLE jobs(
                    job_id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL,
                    source_id TEXT NOT NULL REFERENCES sources(source_id), page INTEGER NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('queued','running','needs_review','failed')),
                    created_at REAL NOT NULL, updated_at REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                    worker_id TEXT, lease_token TEXT, lease_until REAL,
                    result_token TEXT, result_hash TEXT, manifest TEXT,
                    error_code TEXT, error_message TEXT)''')
                connection.execute(f'PRAGMA application_id={_APPLICATION_ID}')
                connection.execute('PRAGMA user_version=1')
            connection.commit()
        _fsync_directory(self.root)

    @contextmanager
    def _connection(self, *, write=False):
        _no_symlinks(self.root)
        for path in (self.root, self.originals, self.derived, self.recognition):
            _directory(path)
        _regular(self.database.lstat())
        for suffix in ('-wal', '-shm', '-journal'):
            path = Path(str(self.database) + suffix)
            if path.exists() or path.is_symlink():
                _regular(path.lstat())
        # __init__ alone creates this file explicitly with mode 0600. Losing it
        # later must fail closed, not silently create a new unrelated database.
        connection = sqlite3.connect(self.database.as_uri() + '?mode=rw', uri=True,
                                     timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('PRAGMA synchronous=FULL')
            if write:
                connection.execute('BEGIN IMMEDIATE')
            yield connection
            if write:
                connection.commit()
        except BaseException:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def _job(self, connection, job_id):
        row = connection.execute('''SELECT j.*, s.sha256, s.size, s.media_type, s.source_filename
            FROM jobs j JOIN sources s ON s.source_id=j.source_id WHERE job_id=?''', (_id(job_id),)).fetchone()
        if not row:
            raise StoreError('Import job not found.')
        return dict(row)

    @staticmethod
    def _public(job):
        result = {key: value for key, value in job.items()
                  if key not in ('lease_token', 'result_token', 'result_hash', 'manifest')}
        if job['manifest']:
            manifest = json.loads(job['manifest'])
            result['artifacts'] = manifest['derived']
            result['recognition'] = manifest['recognition']
        return result

    def capture(self, source_path, *, request_id, page=0, media_type=None):
        _request(request_id)
        if type(page) is not int or not 0 <= page < 50:
            raise StoreError('Selected page must be an integer from 0 through 49.')
        path = Path(source_path).absolute()
        _no_symlinks(path)
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, 'rb') as stream:
            before = os.fstat(stream.fileno())
            _regular(before, private=False)
            if not 0 < before.st_size <= MAX_SOURCE_BYTES:
                raise StoreError('Source must contain 1 byte through 20 MiB.')
            content = stream.read(MAX_SOURCE_BYTES + 1)
            after = os.fstat(stream.fileno())
        if (len(content) != before.st_size or len(content) > MAX_SOURCE_BYTES or
                (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) !=
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
            raise StoreError('Source changed during capture; nothing was accepted.')
        detected = _media(content[:1024])
        if media_type is not None and media_type != detected:
            raise StoreError('Declared media type does not match the source signature.')
        checksum = hashlib.sha256(content).hexdigest()
        with self._connection(write=True) as connection:
            row = connection.execute('SELECT job_id FROM jobs WHERE request_id=?', (request_id,)).fetchone()
            if row:
                job = self._job(connection, row['job_id'])
                if (job['sha256'], job['size'], job['media_type'], job['page']) != (checksum, len(content), detected, page):
                    raise StoreError('Request identifier already belongs to different source input.')
                self.source_path(job['source_id'])
                return self._public(job)
            source_id, job_id = uuid.uuid4().hex, uuid.uuid4().hex
            _publish(self.originals / (source_id + '.bin'), content)
            timestamp = self._clock()
            connection.execute('INSERT INTO sources VALUES(?,?,?,?,?,?)',
                               (source_id, checksum, len(content), detected, path.name, timestamp))
            connection.execute('''INSERT INTO jobs(job_id,request_id,source_id,page,status,created_at,updated_at)
                VALUES(?,?,?,?,'queued',?,?)''', (job_id, request_id, source_id, page, timestamp, timestamp))
            return self._public(self._job(connection, job_id))

    def source(self, source_id):
        with self._connection() as connection:
            row = connection.execute('SELECT * FROM sources WHERE source_id=?', (_id(source_id),)).fetchone()
            if not row:
                raise StoreError('Import source not found.')
            return dict(row)

    def source_path(self, source_id):
        source = self.source(source_id)
        path = self.originals / (_id(source_id) + '.bin')
        _read(path, maximum=MAX_SOURCE_BYTES, expected=source)
        return path

    def status(self, job_id):
        with self._connection() as connection:
            job = self._job(connection, job_id)
            if job['status'] == 'needs_review':
                self._verified_result(job)
            return self._public(job)

    @staticmethod
    def _duration(lease_seconds):
        if (type(lease_seconds) not in (int, float) or not math.isfinite(lease_seconds) or
                not 0 < lease_seconds <= 3600):
            raise StoreError('Lease duration must be positive and at most 3600 seconds.')
        return lease_seconds

    def claim(self, *, worker_id, lease_seconds=90, job_id=None):
        _request(worker_id)
        self._duration(lease_seconds)
        with self._connection(write=True) as connection:
            timestamp = self._clock()
            connection.execute('''UPDATE jobs SET status='failed',updated_at=?,lease_token=NULL,
                lease_until=NULL,error_code='lease_exhausted',error_message='Worker attempts exhausted.'
                WHERE status='running' AND lease_until<=? AND attempts>=?''',
                               (timestamp, timestamp, MAX_ATTEMPTS))
            query = "SELECT job_id FROM jobs WHERE attempts<? AND (status='queued' OR (status='running' AND lease_until<=?))"
            arguments = [MAX_ATTEMPTS, timestamp]
            if job_id is not None:
                query += ' AND job_id=?'
                arguments.append(_id(job_id))
            row = connection.execute(query + ' ORDER BY created_at,job_id LIMIT 1', arguments).fetchone()
            if not row:
                return None
            token = uuid.uuid4().hex
            connection.execute('''UPDATE jobs SET status='running',worker_id=?,lease_token=?,lease_until=?,
                attempts=attempts+1,updated_at=?,error_code=NULL,error_message=NULL WHERE job_id=?''',
                               (worker_id, token, timestamp + lease_seconds, timestamp, row['job_id']))
            result = self._public(self._job(connection, row['job_id']))
            result['lease_token'] = token
            return result

    def _leased(self, connection, job_id, token):
        job = self._job(connection, job_id)
        if (job['status'] != 'running' or job['lease_token'] != _id(token) or
                job['lease_until'] <= self._clock()):
            raise LeaseLost('Job lease expired or belongs to another attempt.')
        return job

    def complete(self, job_id, lease_token, *, derived, recognition):
        if not isinstance(derived, dict) or not 1 <= len(derived) <= 20:
            raise StoreError('One through twenty derived artifacts are required.')
        for name, content in derived.items():
            _name(name)
            if not isinstance(content, bytes):
                raise StoreError('Derived artifacts must contain bytes.')
        if sum(len(content) for content in derived.values()) > MAX_DERIVED_BYTES:
            raise StoreError('Derived artifacts exceed the output limit.')
        if not isinstance(recognition, dict):
            raise StoreError('Recognition output must be a JSON object.')
        output = _json(recognition)
        if len(output) > MAX_RECOGNITION_BYTES:
            raise StoreError('Recognition output exceeds the output limit.')
        manifest = dict(derived={name: dict(sha256=hashlib.sha256(content).hexdigest(), size=len(content))
                                 for name, content in sorted(derived.items())},
                        recognition=dict(sha256=hashlib.sha256(output).hexdigest(), size=len(output)))
        manifest_hash = hashlib.sha256(_json(manifest)).hexdigest()
        with self._connection(write=True) as connection:
            job = self._job(connection, job_id)
            if (job['status'] == 'needs_review' and job['result_token'] == _id(lease_token) and
                    job['result_hash'] == manifest_hash):
                self._verified_result(job)
                return self._public(job)
            self._leased(connection, job_id, lease_token)
            self.source_path(job['source_id'])
            paths = []
            for base in (self.derived, self.recognition):
                directory = base / _id(job_id)
                _mkdir(directory)
                directory = directory / _id(lease_token)
                _mkdir(directory)
                paths.append(directory)
            publications = [(paths[0] / name, content, manifest['derived'][name]) for name, content in derived.items()]
            publications.append((paths[1] / 'result.json', output, manifest['recognition']))
            for path, content, expected in publications:
                if path.exists() or path.is_symlink():
                    _read(path, maximum=MAX_DERIVED_BYTES, expected=expected)
                    _fsync_directory(path.parent)
                else:
                    _publish(path, content)
            # File I/O can outlast the lease; a late result stays unpublished in
            # metadata and must not replace the next attempt's result.
            self._leased(connection, job_id, lease_token)
            connection.execute('''UPDATE jobs SET status='needs_review',updated_at=?,lease_token=NULL,
                lease_until=NULL,result_token=?,result_hash=?,manifest=? WHERE job_id=?''',
                               (self._clock(), lease_token, manifest_hash, _json(manifest).decode(), job_id))
            return self._public(self._job(connection, job_id))

    def fail(self, job_id, lease_token, *, code, message):
        if not isinstance(code, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', code):
            raise StoreError('A bounded error code is required.')
        if not isinstance(message, str) or not message or len(message) > 1000:
            raise StoreError('A bounded error message is required.')
        with self._connection(write=True) as connection:
            self._leased(connection, job_id, lease_token)
            connection.execute('''UPDATE jobs SET status='failed',updated_at=?,lease_token=NULL,
                lease_until=NULL,error_code=?,error_message=? WHERE job_id=?''',
                               (self._clock(), code, message, job_id))
            return self._public(self._job(connection, job_id))

    def _verified_result(self, job):
        if job['status'] != 'needs_review' or not job['result_token'] or not job['manifest']:
            raise StoreError('No review result is available.')
        manifest = json.loads(job['manifest'])
        for name, expected in manifest['derived'].items():
            path = self.derived / _id(job['job_id']) / _id(job['result_token']) / _name(name)
            _read(path, maximum=MAX_DERIVED_BYTES, expected=expected)
        path = self.recognition / _id(job['job_id']) / _id(job['result_token']) / 'result.json'
        return _read(path, maximum=MAX_RECOGNITION_BYTES, expected=manifest['recognition'])

    def result(self, job_id):
        with self._connection() as connection:
            return json.loads(self._verified_result(self._job(connection, job_id)))

    def artifact_path(self, job_id, name):
        _name(name)
        with self._connection() as connection:
            job = self._job(connection, job_id)
            self._verified_result(job)
            if name not in json.loads(job['manifest'])['derived']:
                raise StoreError('Artifact not found.')
            return self.derived / _id(job_id) / _id(job['result_token']) / name

    def recognition_path(self, job_id):
        with self._connection() as connection:
            job = self._job(connection, job_id)
            self._verified_result(job)
            return self.recognition / _id(job_id) / _id(job['result_token']) / 'result.json'
