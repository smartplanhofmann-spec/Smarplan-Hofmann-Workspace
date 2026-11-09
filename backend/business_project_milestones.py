"""Manual project milestones with immutable revisions and exact request replay.

Milestones do not book appointments, consume tasks, release invoices or imply a
signed acceptance. Every public read/write observes current project authority.
"""
from datetime import date, datetime, timezone
import json
import re
import sqlite3
import uuid

from core import Problem, canonical, digest
from business_foundation import require_permission
from business_operations import transaction

FEATURES = ('project_milestones',)
TABLES = ('business_project_milestones', 'business_project_milestone_versions',
          'business_project_milestone_requests')
FIELDS = frozenset(('title', 'details', 'due_date', 'assignee_id', 'status'))
RECORD_FIELDS = FIELDS | {'schema_version', 'id', 'project_id', 'revision',
                          'created_by', 'created_at', 'updated_by', 'updated_at', 'content_hash'}
STATUSES = ('planned', 'achieved', 'cancelled')
ID = r'[a-f0-9]{32}'
BASE = r'/projects/(' + ID + r')/milestones'


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA', 'BLOB'):
        raise ValueError('Unsupported milestone binary type')
    return [
        '''CREATE TABLE IF NOT EXISTS business_project_milestones(
        id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),
        payload_json TEXT NOT NULL,revision INTEGER NOT NULL CHECK(revision>0),
        created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
        updated_by TEXT NOT NULL REFERENCES users(id),updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_project_milestone_versions(
        milestone_id TEXT NOT NULL REFERENCES business_project_milestones(id),
        project_id TEXT NOT NULL REFERENCES projects(id),revision INTEGER NOT NULL CHECK(revision>0),
        payload_json TEXT NOT NULL,PRIMARY KEY(milestone_id,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_project_milestone_requests(
        user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,
        project_id TEXT NOT NULL REFERENCES projects(id),operation TEXT NOT NULL CHECK(operation IN ('create','update')),
        request_json TEXT NOT NULL,request_hash TEXT NOT NULL,result_json TEXT NOT NULL,
        PRIMARY KEY(user_id,request_id))''',
        'CREATE INDEX IF NOT EXISTS business_project_milestones_project ON business_project_milestones(project_id,id)',
    ]


def protected_tables():
    return TABLES[1:]


def runtime_privileges():
    return {TABLES[0]: ('SELECT', 'INSERT', 'UPDATE'),
            **{table: ('SELECT', 'INSERT') for table in TABLES[1:]}}


def guard_statements(dialect):
    if dialect == 'sqlite':
        result = [f"CREATE TRIGGER IF NOT EXISTS {table}_{op.lower()}_guard BEFORE {op} ON {table} "
                  "BEGIN SELECT RAISE(ABORT,'immutable milestone history'); END"
                  for table in TABLES[1:] for op in ('UPDATE', 'DELETE')]
        result.extend([
            "CREATE TRIGGER IF NOT EXISTS business_project_milestone_versions_insert_guard BEFORE INSERT ON business_project_milestone_versions "
            "WHEN EXISTS(SELECT 1 FROM business_project_milestone_versions WHERE milestone_id=NEW.milestone_id AND revision=NEW.revision) "
            "BEGIN SELECT RAISE(ABORT,'immutable milestone history'); END",
            "CREATE TRIGGER IF NOT EXISTS business_project_milestone_requests_insert_guard BEFORE INSERT ON business_project_milestone_requests "
            "WHEN EXISTS(SELECT 1 FROM business_project_milestone_requests WHERE user_id=NEW.user_id AND request_id=NEW.request_id) "
            "BEGIN SELECT RAISE(ABORT,'immutable milestone receipt'); END",
            "CREATE TRIGGER IF NOT EXISTS business_project_milestones_insert_guard BEFORE INSERT ON business_project_milestones "
            "WHEN EXISTS(SELECT 1 FROM business_project_milestones WHERE id=NEW.id) "
            "BEGIN SELECT RAISE(ABORT,'immutable milestone identity'); END",
            "CREATE TRIGGER IF NOT EXISTS business_project_milestones_delete_guard BEFORE DELETE ON business_project_milestones "
            "BEGIN SELECT RAISE(ABORT,'retained milestone'); END",
            "CREATE TRIGGER IF NOT EXISTS business_project_milestones_update_guard BEFORE UPDATE ON business_project_milestones "
            "WHEN NEW.id!=OLD.id OR NEW.project_id!=OLD.project_id OR NEW.created_by!=OLD.created_by OR "
            "NEW.created_at!=OLD.created_at OR NEW.revision!=OLD.revision+1 "
            "BEGIN SELECT RAISE(ABORT,'immutable milestone identity'); END",
        ])
        return result
    if dialect != 'postgresql':
        raise ValueError('Unsupported milestone dialect')
    result = ["CREATE OR REPLACE FUNCTION business_project_milestone_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ "
              "BEGIN RAISE EXCEPTION 'immutable milestone history'; END; $$",
              "CREATE OR REPLACE FUNCTION business_project_milestone_current_guard() RETURNS trigger LANGUAGE plpgsql AS $$ "
              "BEGIN IF TG_OP='DELETE' THEN RAISE EXCEPTION 'retained milestone'; END IF; "
              "IF NEW.id IS DISTINCT FROM OLD.id OR NEW.project_id IS DISTINCT FROM OLD.project_id OR "
              "NEW.created_by IS DISTINCT FROM OLD.created_by OR NEW.created_at IS DISTINCT FROM OLD.created_at OR "
              "NEW.revision != OLD.revision+1 THEN RAISE EXCEPTION 'immutable milestone identity'; END IF; RETURN NEW; END; $$"]
    for table in TABLES[1:]:
        name = table + '_immutable_guard'
        result.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) "
                      f'THEN CREATE TRIGGER {name} BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW '
                      'EXECUTE FUNCTION business_project_milestone_immutable(); END IF; END $$')
    result.append("DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='business_project_milestones_current_guard' "
                  "AND tgrelid='business_project_milestones'::regclass) THEN CREATE TRIGGER business_project_milestones_current_guard "
                  "BEFORE UPDATE OR DELETE ON business_project_milestones FOR EACH ROW "
                  "EXECUTE FUNCTION business_project_milestone_current_guard(); END IF; END $$")
    return result


def _id(value):
    if not isinstance(value, str) or re.fullmatch(ID, value) is None:
        raise ValueError('Invalid milestone identity')
    return value


def _values(data):
    if not isinstance(data, dict) or set(data) != FIELDS:
        raise ValueError('Invalid milestone fields')
    for field, maximum, required in (('title', 200, True), ('details', 10000, False)):
        value = data[field]
        if isinstance(value, str):
            value.encode('utf-8')  # Reject invalid scalars before canonical hashes or storage.
        if (not isinstance(value, str) or len(value) > maximum or required and not value.strip()
                or any(ord(char) < 32 and char not in '\r\n\t' or ord(char) == 127 for char in value)):
            raise ValueError('Invalid milestone text')
    if data['status'] not in STATUSES:
        raise ValueError('Invalid milestone status')
    if data['assignee_id'] is not None:
        _id(data['assignee_id'])
    if data['due_date'] is not None:
        value = data['due_date']
        if not isinstance(value, str) or re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) is None:
            raise ValueError('Invalid milestone due date')
        if not 1900 <= date.fromisoformat(value).year <= 2200:
            raise ValueError('Invalid milestone due date')
    return {field: data[field] for field in FIELDS}


def _command(data, update=False):
    expected = FIELDS | {'schema_version', 'request_id'} | ({'revision'} if update else set())
    if not isinstance(data, dict) or set(data) != expected or type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise ValueError('Invalid milestone command')
    _id(data['request_id'])
    if update and (type(data['revision']) is not int or not 1 <= data['revision'] < 2**31):
        raise ValueError('Invalid milestone revision')
    return _values({field: data[field] for field in FIELDS})


def _valid_record(value):
    if not isinstance(value, dict) or set(value) != RECORD_FIELDS:
        raise ValueError('Invalid milestone record')
    if type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('Invalid milestone schema')
    for key in ('id', 'project_id', 'created_by', 'updated_by'):
        _id(value[key])
    if type(value['revision']) is not int or not 1 <= value['revision'] < 2**31:
        raise ValueError('Invalid milestone revision')
    _values({field: value[field] for field in FIELDS})
    if value['revision'] == 1 and (value['created_by'] != value['updated_by'] or value['created_at'] != value['updated_at']):
        raise ValueError('Invalid milestone creation provenance')
    for field in ('created_at', 'updated_at'):
        parsed = datetime.fromisoformat(value[field])
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError('Invalid milestone timestamp')
    if value['content_hash'] != digest(canonical({key: item for key, item in value.items() if key != 'content_hash'})):
        raise ValueError('Invalid milestone hash')
    return value


def _record(row):
    value = dict(_values(json.loads(row['payload_json'])), schema_version=1,
                 **{key: row[key] for key in ('id', 'project_id', 'revision', 'created_by', 'created_at', 'updated_by', 'updated_at')})
    value['content_hash'] = digest(canonical(value))
    return _valid_record(value)


def _request_hash(project_id, operation, milestone_id, data):
    return digest(canonical(dict(project_id=project_id, operation=operation, milestone_id=milestone_id, data=data)))


class ProjectMilestones:
    def __init__(self, office, *, clock=None):
        self.office, self.db = office, office.db
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _serialize(self):
        if not isinstance(self.db, sqlite3.Connection):
            self.db.execute('SELECT pg_advisory_xact_lock(1296649285,1347571530)')

    def _access(self, actor, project_id, *, write=False):
        try:
            _id(project_id)
        except ValueError:
            raise Problem(400, 'Gültige Projektkennung erwartet.') from None
        fresh = require_permission(self.office, actor, 'planning.read', project_id)
        if write:
            fresh = require_permission(self.office, fresh, 'projects.manage', project_id)
            from business_schema import state
            if 'business_project_milestones' not in state(self.office)['capabilities']:
                raise Problem(409, 'Meilensteine sind in diesem Betriebsmodus nicht schreibend freigegeben.')
            from business_organization import require_active
            require_active(self.office, fresh, '/projects/' + project_id + '/milestones', 'business_project_milestones')
        return fresh

    def _read(self, project_id, milestone_id):
        try:
            _id(milestone_id)
        except ValueError:
            raise Problem(404, 'Meilenstein nicht verfügbar.') from None
        row = self.db.execute('SELECT * FROM business_project_milestones WHERE id=? AND project_id=?',
                              (milestone_id, project_id)).fetchone()
        if row is None:
            raise Problem(404, 'Meilenstein nicht verfügbar.')
        try:
            current = _record(row)
            versions = []
            for item in self.db.execute(
                    'SELECT * FROM business_project_milestone_versions WHERE milestone_id=? ORDER BY revision', (milestone_id,)).fetchall():
                value = _valid_record(json.loads(item['payload_json']))
                if (value['id'] != item['milestone_id'] or value['project_id'] != item['project_id']
                        or value['revision'] != item['revision']):
                    raise ValueError('Milestone history row mismatch')
                versions.append(value)
            if len(versions) != current['revision'] or not versions or versions[-1] != current:
                raise ValueError('Incomplete milestone history')
            for index, original in enumerate(versions, 1):
                if (original['revision'] != index or original['id'] != milestone_id or original['project_id'] != project_id
                        or any(original[field] != current[field] for field in ('created_by', 'created_at'))):
                    raise ValueError('Invalid milestone history')
            return current, versions
        except (TypeError, ValueError, KeyError):
            raise Problem(409, 'Gespeicherte Meilenstein-Historie ist nicht vollständig prüfbar.') from None

    def listing(self, actor, project_id):
        with transaction(self.office):
            self._serialize()
            self._access(actor, project_id)
            items = [self._read(project_id, row['id'])[0] for row in self.db.execute(
                'SELECT id FROM business_project_milestones WHERE project_id=? ORDER BY id', (project_id,)).fetchall()]
            items.sort(key=lambda value: (value['status'] != 'planned', value['due_date'] or '9999-12-31', value['id']))
            return dict(schema_version=1, project_id=project_id, items=items)

    def get(self, actor, project_id, milestone_id):
        with transaction(self.office):
            self._serialize()
            self._access(actor, project_id)
            return self._read(project_id, milestone_id)[0]

    def history(self, actor, project_id, milestone_id):
        with transaction(self.office):
            self._serialize()
            self._access(actor, project_id)
            return dict(schema_version=1, project_id=project_id, milestone_id=milestone_id,
                        items=self._read(project_id, milestone_id)[1])

    def create(self, actor, project_id, data):
        return self._save(actor, project_id, data)

    def update(self, actor, project_id, milestone_id, data):
        return self._save(actor, project_id, data, milestone_id)

    def _save(self, actor, project_id, data, milestone_id=None):
        try:
            _id(project_id)
            if milestone_id is not None:
                _id(milestone_id)
            values = _command(data, update=milestone_id is not None)
        except (TypeError, ValueError, KeyError):
            raise Problem(400, 'Vollständigen Meilenstein mit gültigen Angaben und Versionsnummer senden.') from None
        operation = 'create' if milestone_id is None else 'update'
        fingerprint = _request_hash(project_id, operation, milestone_id, data)
        with transaction(self.office):
            self._serialize()
            fresh = self._access(actor, project_id, write=True)
            prior = self.db.execute('SELECT * FROM business_project_milestone_requests WHERE user_id=? AND request_id=?',
                                    (fresh['id'], data['request_id'])).fetchone()
            if prior:
                if (prior['project_id'] != project_id or prior['operation'] != operation or prior['request_hash'] != fingerprint
                        or prior['request_json'] != canonical(data)):
                    raise Problem(409, 'Diese Auftragskennung ist bereits an einen anderen Meilensteinauftrag gebunden.')
                try:
                    result = _valid_record(json.loads(prior['result_json']))
                    if (result['project_id'] != project_id or milestone_id is not None and result['id'] != milestone_id
                            or result['revision'] != (1 if milestone_id is None else data['revision'] + 1)
                            or result['updated_by'] != fresh['id']
                            or any(result[field] != values[field] for field in FIELDS)):
                        raise ValueError('Foreign milestone receipt')
                    _, versions = self._read(project_id, result['id'])
                    if result != versions[result['revision'] - 1]:
                        raise ValueError('Changed milestone receipt')
                    return result
                except (TypeError, ValueError, KeyError, IndexError):
                    raise Problem(409, 'Gespeicherte Meilensteinquittung ist nicht prüfbar.') from None
            current = self._read(project_id, milestone_id)[0] if milestone_id else None
            if current and current['revision'] != data['revision']:
                raise Problem(409, 'Der Meilenstein wurde inzwischen geändert. Aktuellen Stand neu laden.',
                              request_resolution='not_accepted')
            if values['assignee_id'] is not None and (current is None or values['assignee_id'] != current['assignee_id']):
                from project_workspace import ProjectWorkspace
                team = {row['id'] for row in ProjectWorkspace(self.office).team(fresh, project_id)}
                if values['assignee_id'] not in team:
                    raise Problem(400, 'Verantwortlichen aus dem aktuellen Projektteam wählen.')
            stamp = self.clock().astimezone(timezone.utc).isoformat(timespec='seconds')
            if current is None:
                milestone_id = uuid.uuid4().hex
                self.db.execute('INSERT INTO business_project_milestones '
                                '(id,project_id,payload_json,revision,created_by,created_at,updated_by,updated_at) VALUES(?,?,?,1,?,?,?,?)',
                                (milestone_id, project_id, canonical(values), fresh['id'], stamp, fresh['id'], stamp))
            else:
                self.db.execute('UPDATE business_project_milestones SET payload_json=?,revision=revision+1,updated_by=?,updated_at=? '
                                'WHERE id=? AND project_id=? AND revision=?',
                                (canonical(values), fresh['id'], stamp, milestone_id, project_id, current['revision']))
            row = self.db.execute('SELECT * FROM business_project_milestones WHERE id=?', (milestone_id,)).fetchone()
            result = _record(row)
            self.db.execute('INSERT INTO business_project_milestone_versions(milestone_id,project_id,revision,payload_json) VALUES(?,?,?,?)',
                            (milestone_id, project_id, result['revision'], canonical(result)))
            self.db.execute('INSERT INTO business_project_milestone_requests '
                            '(user_id,request_id,project_id,operation,request_json,request_hash,result_json) VALUES(?,?,?,?,?,?,?)',
                            (fresh['id'], data['request_id'], project_id, operation, canonical(data), fingerprint, canonical(result)))
            self.office.audit(fresh, 'project.milestone.' + ('created' if current is None else 'updated'), milestone_id)
            return result


def validate_integrity(office):
    service = ProjectMilestones(office)
    known = {}
    for row in office.db.execute('SELECT id,project_id FROM business_project_milestones').fetchall():
        current, versions = service._read(row['project_id'], row['id'])
        for value in versions:
            for field in ('created_by', 'updated_by', 'assignee_id'):
                if value[field] is not None and office.db.execute('SELECT 1 FROM users WHERE id=?', (value[field],)).fetchone() is None:
                    raise ValueError('Missing milestone author')
            known[(value['id'], value['revision'])] = value
    version_count = office.db.execute('SELECT COUNT(*) FROM business_project_milestone_versions').fetchone()[0]
    if version_count != len(known):
        raise ValueError('Orphaned milestone history')
    receipts = set()
    for row in office.db.execute('SELECT * FROM business_project_milestone_requests').fetchall():
        try:
            _id(row['user_id']); _id(row['request_id']); _id(row['project_id'])
            data = json.loads(row['request_json'])
            values = _command(data, update=row['operation'] == 'update')
            result = _valid_record(json.loads(row['result_json']))
            original = known.get((result['id'], result['revision']))
            if (row['operation'] not in ('create', 'update') or original != result or result['project_id'] != row['project_id']
                    or result['updated_by'] != row['user_id'] or data['request_id'] != row['request_id']
                    or any(result[field] != values[field] for field in FIELDS)
                    or result['revision'] != (1 if row['operation'] == 'create' else data['revision'] + 1)
                    or row['request_hash'] != _request_hash(row['project_id'], row['operation'],
                        None if row['operation'] == 'create' else result['id'], data)):
                raise ValueError('Invalid milestone receipt')
            key = (result['id'], result['revision'])
            if key in receipts:
                raise ValueError('Repeated milestone acceptance')
            receipts.add(key)
        except (TypeError, ValueError, KeyError):
            raise ValueError('Invalid milestone receipt') from None
    if receipts != set(known):
        raise ValueError('Missing milestone receipt')
    return True


def methods(path):
    if re.fullmatch(BASE + r'/' + ID + r'/history', path):
        return 'GET'
    if re.fullmatch(BASE + r'(?:/' + ID + r')?', path):
        return 'GET, POST'
    return None


def dispatch(office, actor, path, method, data):
    allowed = methods(path)
    if allowed is None:
        return None
    if method not in allowed.split(', '):
        raise Problem(405, 'HTTP-Methode nicht erlaubt.')
    match = re.fullmatch(BASE + r'(?:/(' + ID + r')(?:/(history))?)?', path)
    project_id, milestone_id, history = match.groups()
    service = ProjectMilestones(office)
    if method == 'GET':
        if data:
            raise Problem(400, 'Keine zusätzlichen Meilensteinfilter erwartet.')
        result = service.history(actor, project_id, milestone_id) if history else (
            service.get(actor, project_id, milestone_id) if milestone_id else service.listing(actor, project_id))
        return result, 200, 'application/json'
    result = service.update(actor, project_id, milestone_id, data) if milestone_id else service.create(actor, project_id, data)
    return result, 200 if milestone_id else 201, 'application/json'
