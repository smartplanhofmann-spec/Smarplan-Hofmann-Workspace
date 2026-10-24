"""Retry-safe removal of active plan data, with minimal durable tombstones.

All mutations run under the caller's Office transaction/lock. PostgreSQL's
existing transaction advisory lock also serializes delayed creates and deletes.
"""
import json
import re
import uuid

from core import Problem, canonical, digest, now_iso


def schema_statements():
    return ['''CREATE TABLE IF NOT EXISTS plan_deletions(
      deletion_id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('plan','import')),
      object_id TEXT, project_id TEXT NOT NULL REFERENCES projects(id),
      created_by TEXT REFERENCES users(id), create_request_id TEXT,
      deleted_by TEXT NOT NULL REFERENCES users(id), deleted_at TEXT NOT NULL,
      revision INTEGER, CHECK(object_id IS NOT NULL OR (created_by IS NOT NULL AND create_request_id IS NOT NULL)),
      UNIQUE(kind,object_id),
      UNIQUE(kind,project_id,created_by,create_request_id))''',
      'CREATE INDEX IF NOT EXISTS plan_deletions_project ON plan_deletions(project_id,deleted_at)']


def by_object(db, kind, identifier):
    return db.execute('SELECT * FROM plan_deletions WHERE kind=? AND object_id=?', (kind, identifier)).fetchone()


def by_create(db, kind, project, actor, request_id):
    if not request_id:
        return None
    return db.execute('SELECT * FROM plan_deletions WHERE kind=? AND project_id=? AND created_by=? '
                      'AND create_request_id=?', (kind, project, actor, request_id)).fetchone()


def assert_object_live(db, kind, identifier, project=None):
    deleted = by_object(db, kind, identifier)
    if deleted and project is not None and deleted['project_id'] != project:
        raise Problem(404, 'Plan nicht verfügbar')
    if deleted:
        raise Problem(410, 'Dieser Plan wurde gelöscht')


def assert_create_live(db, kind, project, actor, request_id):
    if by_create(db, kind, project, actor, request_id):
        raise Problem(410, 'Diese Erstellung wurde gelöscht oder abgebrochen')


def receipt(row, user=None):
    result = dict(deleted=True, status='deleted', kind=row['kind'], id=row['object_id'],
                  project_id=row['project_id'], deleted_at=row['deleted_at'])
    if row['revision'] is not None:
        result['revision'] = row['revision']
    if user and row['created_by'] == user['id'] and row['create_request_id']:
        result['create_request_id'] = row['create_request_id']
    return result


def feed(office, user, project):
    office.project(user, project)
    return [receipt(row, user) for row in office.db.execute(
        'SELECT * FROM plan_deletions WHERE project_id=? AND (object_id IS NOT NULL OR created_by=?) '
        'ORDER BY deleted_at,deletion_id', (project, user['id'])).fetchall()]


def validate_integrity(office):
    """Deleted plans cannot regain active versions or cached drawing payloads."""
    allowed = {'deleted', 'status', 'kind', 'id', 'project_id', 'deleted_at', 'revision', 'create_request_id'}
    for row in office.db.execute('SELECT * FROM plan_deletions').fetchall():
        if row['object_id'] is None:
            continue
        if row['kind'] == 'import':
            if not office.db.execute('SELECT 1 FROM plan_imports WHERE id=? AND project_id=?',
                                     (row['object_id'], row['project_id'])).fetchone():
                raise ValueError('Deleted import is missing its private cancellation metadata')
            continue
        if office.db.execute('SELECT 1 FROM plan_versions WHERE id=?', (row['object_id'],)).fetchone():
            raise ValueError('Deleted plan still has active drawing versions')
        for saved in office.db.execute('SELECT result FROM plan_requests WHERE project_id=?', (row['project_id'],)):
            result = json.loads(saved['result'])
            if result.get('id') == row['object_id'] and result.get('kind') in (None, 'plan'):
                if result.get('deleted') is not True or set(result) - allowed:
                    raise ValueError('Deleted plan still has a cached drawing payload')
    return True


def _identifier(value):
    return isinstance(value, str) and re.fullmatch(r'[a-f0-9]{32}', value)


def _data(value, kind):
    if (not isinstance(value, dict) or set(value) - {'request_id', 'id', 'create_request_id', 'revision'}
            or not _identifier(value.get('request_id')) or not any(key in value for key in ('id', 'create_request_id'))):
        raise Problem(400, 'Löschauftrag mit eindeutiger Anfrage- und Ziel-ID erwartet')
    for key in ('id', 'create_request_id'):
        if key in value and not _identifier(value[key]):
            raise Problem(400, 'Ungültiges Löschziel')
    if value.get('create_request_id') == value['request_id']:
        raise Problem(400, 'Löschauftrag benötigt eine eigene Anfrage-ID')
    if 'revision' in value and (kind != 'plan' or type(value['revision']) is not int or value['revision'] < 1):
        raise Problem(400, 'Ungültige Ausgangsversion')
    return value


def _active(office, project, kind, identifier):
    if kind == 'import':
        return office.db.execute('SELECT id,user_id,request_id FROM plan_imports WHERE id=? AND project_id=?',
                                 (identifier, project)).fetchone()
    row = office.db.execute('SELECT payload FROM plan_versions WHERE id=? AND project_id=? '
                            'ORDER BY revision DESC LIMIT 1', (identifier, project)).fetchone()
    return json.loads(row['payload']) if row else None


def _creation(office, project, kind, actor, request_id):
    if kind == 'import':
        row = office.db.execute('SELECT id FROM plan_imports WHERE project_id=? AND user_id=? AND request_id=?',
                                (project, actor, request_id)).fetchone()
        return row['id'] if row else None
    row = office.db.execute('SELECT result FROM plan_requests WHERE project_id=? AND user_id=? AND request_id=?',
                            (project, actor, request_id)).fetchone()
    if not row:
        return None
    result = json.loads(row['result'])
    if (result.get('kind') not in (None, 'plan') or not _identifier(result.get('id'))
            or (not result.get('deleted') and result.get('revision') != 1)):
        raise Problem(409, 'Anfrage gehört nicht zur ursprünglichen Planerstellung')
    return result['id']


def _creator(office, project, kind, identifier, active):
    if kind == 'import':
        return active['user_id'], active['request_id']
    for row in office.db.execute('SELECT user_id,request_id,result FROM plan_requests WHERE project_id=?', (project,)):
        result = json.loads(row['result'])
        if (result.get('id') == identifier and result.get('kind') in (None, 'plan')
                and result.get('revision') == 1 and not result.get('deleted')):
            return row['user_id'], row['request_id']
    return None, None


def _purge(office, row):
    identifier, project = row['object_id'], row['project_id']
    if identifier is None:
        return
    if row['kind'] == 'import':
        office.db.execute('DELETE FROM plan_import_chunks WHERE import_id=?', (identifier,))
        office.db.execute("UPDATE plan_imports SET filename='',title='',status='failed',error_code='deleted',"
                          'preview=NULL,preview_sha256=NULL,result=NULL,result_sha256=NULL,lease_token=NULL,lease_until=NULL '
                          'WHERE id=? AND project_id=?', (identifier, project))
        return
    office.db.execute('DELETE FROM plan_versions WHERE id=? AND project_id=?', (identifier, project))
    # Request hashes stay for collision/retry checks; old wall/title payloads do not.
    for previous in office.db.execute('SELECT user_id,request_id,result FROM plan_requests WHERE project_id=?', (project,)).fetchall():
        result = json.loads(previous['result'])
        if result.get('id') == identifier and result.get('kind') in (None, 'plan'):
            office.db.execute('UPDATE plan_requests SET result=? WHERE user_id=? AND request_id=?',
                              (canonical(receipt(row, {'id': previous['user_id']})), previous['user_id'], previous['request_id']))


def delete(office, user, project, kind, value):
    office.require(user, ('owner', 'manager', 'technician'))
    office.project(user, project)
    data = _data(value, kind)
    fingerprint = digest(canonical(dict(action='delete', kind=kind, project_id=project, data=data)))
    previous = office.db.execute('SELECT request_hash,result FROM plan_requests WHERE user_id=? AND request_id=?',
                                 (user['id'], data['request_id'])).fetchone()
    if previous:
        if previous['request_hash'] != fingerprint:
            raise Problem(409, 'Lösch-ID wurde bereits für einen anderen Auftrag verwendet')
        return json.loads(previous['result'])

    identifier = data.get('id')
    cancelled = by_create(office.db, kind, project, user['id'], data.get('create_request_id'))
    creation_id = (cancelled['object_id'] if cancelled else
                   _creation(office, project, kind, user['id'], data['create_request_id'])
                   if 'create_request_id' in data else None)
    if identifier is not None and 'create_request_id' in data and creation_id != identifier:
        raise Problem(409, 'Server-ID und ursprüngliche Erstellung passen nicht zusammen')
    identifier = identifier or creation_id
    tombstone = by_object(office.db, kind, identifier) if identifier else cancelled
    if tombstone and tombstone['project_id'] != project:
        raise Problem(404, 'Plan nicht verfügbar')
    if tombstone is None:
        active = _active(office, project, kind, identifier) if identifier else None
        if identifier and active is None:
            raise Problem(404, 'Plan nicht verfügbar')
        revision = None
        if kind == 'plan' and active:
            if 'revision' in data and data['revision'] != active['revision']:
                raise Problem(409, 'Plan wurde inzwischen geändert; Löschung erneut prüfen')
            revision = active['revision'] + 1
        creator, create_request = ((user['id'], data['create_request_id']) if 'create_request_id' in data else
                                   _creator(office, project, kind, identifier, active) if identifier else (None, None))
        deletion_id = uuid.uuid4().hex
        office.db.execute('INSERT INTO plan_deletions(deletion_id,kind,object_id,project_id,created_by,create_request_id,'
                          'deleted_by,deleted_at,revision) VALUES(?,?,?,?,?,?,?,?,?)',
                          (deletion_id, kind, identifier, project, creator, create_request, user['id'], now_iso(), revision))
        tombstone = office.db.execute('SELECT * FROM plan_deletions WHERE deletion_id=?', (deletion_id,)).fetchone()
        _purge(office, tombstone)
        office.audit(user, 'plan.deleted' if kind == 'plan' else 'plan_import.deleted', identifier or deletion_id)
    result = receipt(tombstone, user)
    office.db.execute('INSERT INTO plan_requests(user_id,request_id,project_id,request_hash,result) VALUES(?,?,?,?,?)',
                      (user['id'], data['request_id'], project, fingerprint, canonical(result)))
    return result
