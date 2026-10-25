"""Project dashboard, tasks, site diary, appointments and document links.

Domain operations run inside the caller's Office lock/transaction. External
links and calendar exports are explicit handoffs, not connected live services.
All rows and request receipts remain in the existing project permission scope.
"""
from datetime import date, datetime, timezone
import json
import re
import sqlite3
from urllib.parse import urlsplit
import uuid

from core import Problem, canonical, digest, text_field


WRITERS = ('owner', 'manager', 'technician')
KINDS = ('tasks', 'diary', 'appointments', 'links')
PROFILE_FIELDS = {'description', 'site_address', 'phase', 'deposit_status', 'materials_status',
                  'start_date', 'end_date'}
ITEM_FIELDS = {
    'tasks': {'title', 'details', 'status', 'priority', 'due_date', 'assignee_id'},
    'diary': {'entry_date', 'work_performed', 'issues', 'next_steps', 'weather', 'crew_count'},
    'appointments': {'title', 'details', 'start_at', 'end_at', 'status'},
    'links': {'title', 'category', 'url', 'active'},
}


def schema_statements():
    return [
        '''CREATE TABLE IF NOT EXISTS project_profiles(
          project_id TEXT PRIMARY KEY REFERENCES projects(id), payload TEXT NOT NULL,
          revision INTEGER NOT NULL CHECK(revision>0),
          updated_by TEXT NOT NULL REFERENCES users(id), updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS workspace_items(
          id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
          kind TEXT NOT NULL CHECK(kind IN ('tasks','diary','appointments','links')),
          payload TEXT NOT NULL CHECK(length(payload)<=65536),
          revision INTEGER NOT NULL CHECK(revision>0),
          created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL,
          updated_by TEXT NOT NULL REFERENCES users(id), updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS workspace_versions(
          kind TEXT NOT NULL, object_id TEXT NOT NULL, revision INTEGER NOT NULL,
          project_id TEXT NOT NULL REFERENCES projects(id), payload TEXT NOT NULL,
          PRIMARY KEY(kind,object_id,revision))''',
        '''CREATE TABLE IF NOT EXISTS workspace_requests(
          user_id TEXT NOT NULL REFERENCES users(id), request_id TEXT NOT NULL,
          project_id TEXT NOT NULL REFERENCES projects(id), request_hash TEXT NOT NULL,
          result TEXT NOT NULL, PRIMARY KEY(user_id,request_id))''',
        'CREATE INDEX IF NOT EXISTS workspace_items_project ON workspace_items(project_id,kind,created_at,id)',
        'CREATE INDEX IF NOT EXISTS workspace_versions_project ON workspace_versions(project_id,kind,object_id)',
    ]


def ensure_sqlite_schema(office):
    if isinstance(office.db, sqlite3.Connection):
        with office.lock, office.db:
            for statement in schema_statements():
                office.db.execute(statement)


def validate_integrity(office):
    """Validate current records against retained revisions and retry receipts.

    Called on a workspace-capable schema, e.g. before backup/after restore; it
    does not depend on today's role, assignment or account activation state.
    """
    expected = {}
    for row in office.db.execute('SELECT * FROM project_profiles').fetchall():
        payload = json.loads(row['payload'])
        if not isinstance(payload, dict) or set(payload) != PROFILE_FIELDS:
            raise ValueError('Invalid stored project profile')
        value = dict(payload, project_id=row['project_id'], revision=row['revision'],
                     updated_by=row['updated_by'], updated_at=row['updated_at'])
        expected[('profile', row['project_id'])] = value
    for row in office.db.execute('SELECT * FROM workspace_items').fetchall():
        payload = json.loads(row['payload'])
        if row['kind'] not in ITEM_FIELDS or not isinstance(payload, dict) or set(payload) != ITEM_FIELDS[row['kind']]:
            raise ValueError('Invalid stored project item')
        value = dict(payload, id=row['id'], project_id=row['project_id'], revision=row['revision'],
                     created_by=row['created_by'], created_at=row['created_at'],
                     updated_by=row['updated_by'], updated_at=row['updated_at'])
        expected[(row['kind'], row['id'])] = value
    versions = {}
    for row in office.db.execute('SELECT * FROM workspace_versions ORDER BY kind,object_id,revision').fetchall():
        key = row['kind'], row['object_id']
        value = json.loads(row['payload'])
        if (key not in expected or not isinstance(value, dict) or value.get('project_id') != row['project_id']
                or expected[key]['project_id'] != row['project_id'] or value.get('revision') != row['revision']
                or value.get('id', value.get('project_id')) != row['object_id']):
            raise ValueError('Invalid project revision history')
        items = versions.setdefault(key, [])
        if row['revision'] != len(items) + 1:
            raise ValueError('Missing project revision')
        items.append(value)
    for key, current in expected.items():
        history = versions.get(key, [])
        if len(history) != current['revision'] or not history or history[-1] != current:
            raise ValueError('Project record does not match its revision history')
    saved_versions = {canonical(value) for items in versions.values() for value in items}
    for row in office.db.execute('SELECT * FROM workspace_requests').fetchall():
        value = json.loads(row['result'])
        if (not _id(row['request_id']) or not re.fullmatch(r'[a-f0-9]{64}', row['request_hash'])
                or not isinstance(value, dict) or value.get('project_id') != row['project_id']
                or canonical(value) not in saved_versions):
            raise ValueError('Invalid project mutation receipt')
    return True


def _optional_text(value, name, maximum):
    if (not isinstance(value, str) or len(value) > maximum
            or any((ord(char) < 32 and char not in '\r\n\t') or ord(char) == 127 for char in value)):
        raise Problem(400, 'Ungültiges Feld: ' + name)
    return value.strip()


def _required_text(value, name, maximum):
    result = text_field(value, name, maximum)
    return _optional_text(result, name, maximum)


def _choice(value, choices, name):
    if not isinstance(value, str) or value not in choices:
        raise Problem(400, 'Ungültiges Feld: ' + name)
    return value


def _date(value, name, *, required=False):
    if value in (None, '') and not required:
        return None
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise Problem(400, 'Datum erwartet: ' + name)
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise Problem(400, 'Ungültiges Datum: ' + name)
    if not 1900 <= parsed.year <= 2200:
        raise Problem(400, 'Datum außerhalb des unterstützten Bereichs: ' + name)
    return parsed.isoformat()


def _instant(value, name):
    if not isinstance(value, str) or len(value) > 40:
        raise Problem(400, 'Zeitpunkt mit Zeitzone erwartet: ' + name)
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise Problem(400, 'Ungültiger Zeitpunkt: ' + name)
    if parsed.tzinfo is None or parsed.utcoffset() is None or not 1900 <= parsed.year <= 2200:
        raise Problem(400, 'Zeitpunkt mit Zeitzone erwartet: ' + name)
    return parsed.astimezone(timezone.utc).isoformat(timespec='seconds')


def _id(value):
    return isinstance(value, str) and re.fullmatch(r'[a-f0-9]{32}', value)


def _fold_ics(line):
    lines, part, size = [], '', 0
    for char in line:
        width = len(char.encode('utf-8'))
        if size + width > 75:
            lines.append(part)
            part, size = ' ', 1
        part += char
        size += width
    lines.append(part)
    return '\r\n'.join(lines)


def _ics_text(value):
    return value.replace('\\', '\\\\').replace('\r\n', '\n').replace('\r', '\n').replace(
        '\n', '\\n').replace(';', '\\;').replace(',', '\\,')


class ProjectWorkspace:
    def __init__(self, office, *, clock=None):
        self.office, self.db = office, office.db
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _now(self):
        return self.clock().astimezone(timezone.utc)

    def _authorize(self, user, project, *, write=False, profile=False):
        if write:
            if profile:
                import business_api
                if business_api.document_policy_installed(self.office):
                    from business_foundation import require_permission
                    require_permission(self.office, user, 'projects.manage', project)
                else:
                    self.office.require(user, ('owner', 'manager'))
            else:
                self.office.require(user, WRITERS)
        return self.office.project(user, project)

    def team(self, user, project):
        self._authorize(user, project)
        return [dict(row) for row in self.db.execute(
            "SELECT u.id,u.email,u.role FROM users u WHERE u.active=1 AND (u.role='owner' OR EXISTS "
            ' (SELECT 1 FROM assignments a WHERE a.user_id=u.id AND a.project_id=?)) ORDER BY u.email,u.id',
            (project,)).fetchall()]

    def profile(self, user, project):
        self._authorize(user, project)
        row = self.db.execute('SELECT * FROM project_profiles WHERE project_id=?', (project,)).fetchone()
        if row:
            return dict(json.loads(row['payload']), project_id=project, revision=row['revision'],
                        updated_by=row['updated_by'], updated_at=row['updated_at'])
        return dict(project_id=project, description='', site_address='', phase='planning',
                    deposit_status='not_recorded', materials_status='not_recorded',
                    start_date=None, end_date=None, revision=0, updated_by=None, updated_at=None)

    def _request(self, user, project, action, identifier, data, fields, *, update=False):
        if (not isinstance(data, dict) or not _id(data.get('request_id'))
                or set(data) - fields - {'request_id', 'revision'}
                or not (set(data) & fields)):
            raise Problem(400, 'Vollständige Eingabe mit eindeutiger Anfrage-ID erwartet')
        if update:
            if type(data.get('revision')) is not int or data['revision'] < 0:
                raise Problem(400, 'Ausgangsversion erwartet')
        elif 'revision' in data:
            raise Problem(400, 'Neue Einträge haben noch keine Ausgangsversion')
        try:
            fingerprint = digest(canonical(dict(project_id=project, action=action, id=identifier, data=data)))
        except (TypeError, ValueError, UnicodeError):
            raise Problem(400, 'Gültige Unicode- und JSON-Eingabe erwartet')
        previous = self.db.execute('SELECT request_hash,result FROM workspace_requests '
                                   'WHERE user_id=? AND request_id=?', (user['id'], data['request_id'])).fetchone()
        if previous:
            if previous['request_hash'] != fingerprint:
                raise Problem(409, 'Anfrage-ID wurde bereits für einen anderen Inhalt verwendet')
            return fingerprint, json.loads(previous['result'])
        return fingerprint, None

    def _remember(self, user, project, data, fingerprint, result):
        self.db.execute('INSERT INTO workspace_requests(user_id,request_id,project_id,request_hash,result) '
                        'VALUES(?,?,?,?,?)', (user['id'], data['request_id'], project, fingerprint, canonical(result)))

    def _version(self, kind, identifier, project, result):
        self.db.execute('INSERT INTO workspace_versions(kind,object_id,revision,project_id,payload) VALUES(?,?,?,?,?)',
                        (kind, identifier, result['revision'], project, canonical(result)))

    def save_profile(self, user, project, data):
        self._authorize(user, project, write=True, profile=True)
        fingerprint, previous = self._request(user, project, 'profile', project, data, PROFILE_FIELDS, update=True)
        if previous is not None:
            return previous
        current = self.profile(user, project)
        if data['revision'] != current['revision']:
            raise Problem(409, 'Projektübersicht wurde inzwischen geändert. Neu laden.')
        value = {key: data.get(key, current[key]) for key in PROFILE_FIELDS}
        value['description'] = _optional_text(value['description'], 'Projektbeschreibung', 10000)
        value['site_address'] = _optional_text(value['site_address'], 'Baustellenadresse', 2000)
        value['phase'] = _choice(value['phase'], ('planning', 'scheduling', 'awaiting_deposit', 'procurement',
            'execution', 'final_invoice', 'completed', 'on_hold'), 'Projektphase')
        value['deposit_status'] = _choice(value['deposit_status'],
            ('not_recorded', 'not_required', 'requested', 'received'), 'Anzahlung')
        value['materials_status'] = _choice(value['materials_status'],
            ('not_recorded', 'not_planned', 'to_order', 'ordered', 'delivered'), 'Materialbestellung')
        for field in ('start_date', 'end_date'):
            value[field] = _date(value[field], field)
        if value['start_date'] and value['end_date'] and value['end_date'] < value['start_date']:
            raise Problem(400, 'Projektende liegt vor dem Beginn')
        revision, stamp = current['revision'] + 1, self._now().isoformat(timespec='seconds')
        if current['revision'] == 0:
            self.db.execute('INSERT INTO project_profiles(project_id,payload,revision,updated_by,updated_at) VALUES(?,?,?,?,?)',
                            (project, canonical(value), revision, user['id'], stamp))
        else:
            self.db.execute('UPDATE project_profiles SET payload=?,revision=?,updated_by=?,updated_at=? WHERE project_id=?',
                            (canonical(value), revision, user['id'], stamp, project))
        result = dict(value, project_id=project, revision=revision, updated_by=user['id'], updated_at=stamp)
        self._version('profile', project, project, result)
        self.office.audit(user, 'workspace.profile.saved', project)
        self._remember(user, project, data, fingerprint, result)
        return result

    def _kind(self, kind):
        if kind not in KINDS:
            raise Problem(404, 'Projektbereich nicht verfügbar')

    def _item(self, row):
        return dict(json.loads(row['payload']), id=row['id'], project_id=row['project_id'],
                    revision=row['revision'], created_by=row['created_by'], created_at=row['created_at'],
                    updated_by=row['updated_by'], updated_at=row['updated_at'])

    def list_items(self, user, project, kind):
        self._kind(kind)
        self._authorize(user, project)
        result = [self._item(row) for row in self.db.execute('SELECT * FROM workspace_items '
                   'WHERE project_id=? AND kind=? ORDER BY created_at,id', (project, kind)).fetchall()]
        if kind == 'links':
            from business_api import can_read_document
            result = [item for item in result if can_read_document(
                self.office, user, project, 'link', item['id'], item.get('category'))]
        if kind == 'tasks':
            result.sort(key=lambda item: (item['status'] in ('done', 'cancelled'), item['due_date'] or '9999',
                                         item['priority'] != 'high', item['id']))
        elif kind == 'diary':
            result.sort(key=lambda item: (item['entry_date'], item['created_at'], item['id']), reverse=True)
        elif kind == 'appointments':
            result.sort(key=lambda item: (item['start_at'], item['id']))
        return result

    def get_item(self, user, project, kind, identifier):
        self._kind(kind)
        self._authorize(user, project)
        row = self.db.execute('SELECT * FROM workspace_items WHERE id=? AND project_id=? AND kind=?',
                              (identifier, project, kind)).fetchone()
        if not row:
            raise Problem(404, 'Eintrag nicht verfügbar')
        value = self._item(row)
        if kind == 'links':
            from business_api import require_document
            require_document(self.office, user, project, 'link', identifier, value.get('category'))
        return value

    def _values(self, user, project, kind, data, current=None):
        defaults = {
            'tasks': dict(title='', details='', status='todo', priority='normal', due_date=None, assignee_id=None),
            'diary': dict(entry_date=self._now().date().isoformat(), work_performed='', issues='',
                          next_steps='', weather='', crew_count=None),
            'appointments': dict(title='', details='', start_at='', end_at='', status='scheduled'),
            'links': dict(title='', category='document', url='', active=True),
        }
        values = {key: data.get(key, (current or defaults[kind])[key]) for key in ITEM_FIELDS[kind]}
        if kind in ('tasks', 'appointments', 'links'):
            values['title'] = _required_text(values['title'], 'Titel', 200)
        if kind in ('tasks', 'appointments'):
            values['details'] = _optional_text(values['details'], 'Beschreibung', 10000)
        if kind == 'tasks':
            values['status'] = _choice(values['status'], ('todo', 'in_progress', 'done', 'cancelled'), 'Aufgabenstatus')
            values['priority'] = _choice(values['priority'], ('normal', 'high'), 'Priorität')
            values['due_date'] = _date(values['due_date'], 'Fälligkeitsdatum')
            target = values['assignee_id']
            if target == '':
                target = None
            reassigned = current is None or target != current['assignee_id']
            if target is not None and (not _id(target) or (reassigned and target not in {
                    member['id'] for member in self.team(user, project)})):
                raise Problem(400, 'Verantwortlicher muss ein aktives Mitglied dieses Projekts sein')
            values['assignee_id'] = target
        elif kind == 'diary':
            values['entry_date'] = _date(values['entry_date'], 'Tagebuchdatum', required=True)
            values['work_performed'] = _required_text(values['work_performed'], 'Ausgeführte Arbeiten', 10000)
            for key, maximum in (('issues', 10000), ('next_steps', 5000), ('weather', 200)):
                values[key] = _optional_text(values[key], key, maximum)
            crew = values['crew_count']
            if crew is not None and (type(crew) is not int or not 0 <= crew <= 1000):
                raise Problem(400, 'Personenanzahl zwischen 0 und 1000 erwartet')
        elif kind == 'appointments':
            values['status'] = _choice(values['status'], ('scheduled', 'cancelled'), 'Terminstatus')
            values['start_at'] = _instant(values['start_at'], 'Terminbeginn')
            values['end_at'] = _instant(values['end_at'], 'Terminende')
            if values['end_at'] <= values['start_at']:
                raise Problem(400, 'Terminende muss nach dem Beginn liegen')
        else:
            values['category'] = _choice(values['category'],
                ('dropbox', 'offer', 'invoice', 'contract', 'document', 'other'), 'Dokumentart')
            url = values['url']
            if (not isinstance(url, str) or len(url) > 2048 or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in url)):
                raise Problem(400, 'Gültiger HTTPS-Link erwartet')
            try:
                parsed = urlsplit(url)
                parsed.port
            except ValueError:
                raise Problem(400, 'Gültiger HTTPS-Link erwartet')
            if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None or parsed.password is not None
                    or (parsed.port is not None and not 1 <= parsed.port <= 65535)):
                raise Problem(400, 'HTTPS-Link ohne eingebettete Zugangsdaten erwartet')
            values['url'] = url
            if type(values['active']) is not bool:
                raise Problem(400, 'Aktiv muss ein Wahrheitswert sein')
        return values

    def save_item(self, user, project, kind, data, identifier=None):
        self._kind(kind)
        self._authorize(user, project, write=True)
        if identifier is not None and not _id(identifier):
            raise Problem(404, 'Eintrag nicht verfügbar')
        if kind == 'links':
            from business_api import require_link_write
            require_link_write(self.office, user, project, identifier,
                               data.get('category') if isinstance(data, dict) else None)
        fingerprint, previous = self._request(user, project, kind, identifier, data, ITEM_FIELDS[kind], update=identifier is not None)
        if previous is not None:
            # A historical link receipt must not replay a formerly public URL
            # after classification, URL revision or role/assignment changes.
            return self.get_item(user, project, kind, previous['id']) if kind == 'links' else previous
        current = self.get_item(user, project, kind, identifier) if identifier else None
        if current is not None and data['revision'] != current['revision']:
            raise Problem(409, 'Eintrag wurde inzwischen geändert. Neu laden; Eingabe bleibt erhalten.')
        values = self._values(user, project, kind, data, current)
        stamp = self._now().isoformat(timespec='seconds')
        if current:
            revision = current['revision'] + 1
            self.db.execute('UPDATE workspace_items SET payload=?,revision=?,updated_by=?,updated_at=? '
                            'WHERE id=? AND project_id=? AND kind=?',
                            (canonical(values), revision, user['id'], stamp, identifier, project, kind))
            result = dict(values, id=identifier, project_id=project, revision=revision,
                          created_by=current['created_by'], created_at=current['created_at'], updated_by=user['id'], updated_at=stamp)
        else:
            identifier, revision = uuid.uuid4().hex, 1
            self.db.execute('INSERT INTO workspace_items(id,project_id,kind,payload,revision,created_by,created_at,updated_by,updated_at) '
                            'VALUES(?,?,?,?,?,?,?,?,?)',
                            (identifier, project, kind, canonical(values), revision, user['id'], stamp, user['id'], stamp))
            result = dict(values, id=identifier, project_id=project, revision=revision,
                          created_by=user['id'], created_at=stamp, updated_by=user['id'], updated_at=stamp)
        self._version(kind, identifier, project, result)
        self.office.audit(user, 'workspace.' + kind + ('.updated' if current else '.created'), identifier)
        self._remember(user, project, data, fingerprint, result)
        return result

    def dashboard(self, user, project):
        record = self._authorize(user, project)
        tasks = self.list_items(user, project, 'tasks')
        diary = self.list_items(user, project, 'diary')
        appointments = self.list_items(user, project, 'appointments')
        now = self._now()
        today = now.date().isoformat()
        active_tasks = [task for task in tasks if task['status'] in ('todo', 'in_progress')]
        upcoming = [item for item in appointments if item['status'] == 'scheduled'
                    and datetime.fromisoformat(item['end_at']) >= now]
        report_count = self.db.execute('SELECT COUNT(*) AS count FROM reports WHERE project_id=?', (project,)).fetchone()[0]
        plan_count = len(self.office.plans(user, project))
        has_imports = not isinstance(self.db, sqlite3.Connection) or self.db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='plan_imports'").fetchone() is not None
        import_count = self.db.execute("SELECT COUNT(*) AS count FROM plan_imports i WHERE project_id=? "
            "AND NOT EXISTS (SELECT 1 FROM plan_deletions d WHERE d.kind='import' AND d.object_id=i.id)",
            (project,)).fetchone()[0] if has_imports else 0
        return dict(project=record, profile=self.profile(user, project), team=self.team(user, project),
                    counters=dict(tasks_open=len(active_tasks), tasks_overdue=sum(bool(task['due_date'] and task['due_date'] < today)
                        for task in active_tasks), appointments_upcoming=len(upcoming), diary_entries=len(diary),
                        reports=report_count, plans=plan_count, imports=import_count),
                    open_tasks=active_tasks[:20], upcoming_appointments=upcoming[:10],
                    latest_diary=diary[:5], links=[item for item in self.list_items(user, project, 'links') if item['active']])

    def calendar(self, user, project, identifier):
        appointment = self.get_item(user, project, 'appointments', identifier)
        profile = self.profile(user, project)
        def stamp(value):
            return datetime.fromisoformat(value).astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Smartplan Hofmann//Office 0.9//DE',
                 'CALSCALE:GREGORIAN', 'BEGIN:VEVENT', 'UID:' + identifier + '@smartplan-hofmann.de',
                 'DTSTAMP:' + stamp(appointment['updated_at']), 'DTSTART:' + stamp(appointment['start_at']),
                 'DTEND:' + stamp(appointment['end_at']), 'SEQUENCE:' + str(appointment['revision'] - 1),
                 'STATUS:' + ('CANCELLED' if appointment['status'] == 'cancelled' else 'CONFIRMED'),
                 'SUMMARY:' + _ics_text(appointment['title']), 'DESCRIPTION:' + _ics_text(appointment['details']),
                 'LOCATION:' + _ics_text(profile['site_address']), 'END:VEVENT', 'END:VCALENDAR']
        return ('\r\n'.join(_fold_ics(line) for line in lines) + '\r\n').encode('utf-8')
