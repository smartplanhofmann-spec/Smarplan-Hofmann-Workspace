"""Canonical internal appointments, employee bookings and private absences.

Services are pure database operations. The caller owns the transaction and
Office lock; schema changes are explicit migration operations, never startup IO.
"""
import calendar as month_calendar
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from functools import wraps
import json
import re
import sqlite3
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import uuid

from core import Problem, canonical, digest

FEATURES = ('project_timeline',)
TIMELINE_MAX_DAYS = 1096
TIMELINE_MAX_PROJECTS = 500
_TIMELINE_SELECT = '''SELECT p.id,p.name,pp.payload AS profile_payload,
    COALESCE(pp.revision,0) AS profile_revision,bp.status_id,
    s.name AS status_name,s.color AS status_color,s.terminal AS status_terminal
    FROM projects p LEFT JOIN project_profiles pp ON pp.project_id=p.id
    LEFT JOIN business_project_profiles bp ON bp.project_id=p.id
    LEFT JOIN business_project_statuses s ON s.id=bp.status_id'''


@contextmanager
def _transaction(office):
    with office.lock:
        if isinstance(office.db, sqlite3.Connection) and office.db.in_transaction:
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
        elif isinstance(office.db, sqlite3.Connection):
            office.db.execute('BEGIN IMMEDIATE')
            try:
                yield
            except BaseException:
                office.db.rollback()
                raise
            else:
                office.db.commit()
        else:
            with office.db:
                yield


def _atomic(function):
    @wraps(function)
    def operation(self, *args, **kwargs):
        with _transaction(self.office):
            return function(self, *args, **kwargs)
    return operation


def schema_statements(binary_type='BYTEA'):
    return [
        '''CREATE TABLE IF NOT EXISTS business_employees(
        id TEXT PRIMARY KEY,user_id TEXT NOT NULL UNIQUE REFERENCES users(id),name TEXT NOT NULL,
        active INTEGER NOT NULL CHECK(active IN(0,1)),weekly_minutes INTEGER NOT NULL CHECK(weekly_minutes BETWEEN 0 AND 10080),
        hourly_cost_minor BIGINT NOT NULL CHECK(hourly_cost_minor>=0),employment_from TEXT,employment_to TEXT,
        revision INTEGER NOT NULL,updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_employee_terms(
        employee_id TEXT NOT NULL REFERENCES business_employees(id),effective_from TEXT NOT NULL,revision INTEGER NOT NULL,
        weekly_minutes INTEGER NOT NULL,hourly_cost_minor BIGINT NOT NULL,
        PRIMARY KEY(employee_id,effective_from,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_resources(
        id TEXT PRIMARY KEY,name TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN('vehicle','machine','tool')),
        active INTEGER NOT NULL CHECK(active IN(0,1)),code TEXT UNIQUE,revision INTEGER NOT NULL,updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_appointment_series(
        id TEXT PRIMARY KEY,project_id TEXT REFERENCES projects(id),frequency TEXT NOT NULL,
        interval_count INTEGER NOT NULL,occurrence_count INTEGER NOT NULL,timezone TEXT NOT NULL,
        start_at TEXT NOT NULL,end_at TEXT NOT NULL,title TEXT NOT NULL,details TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_appointments(
        id TEXT PRIMARY KEY,project_id TEXT REFERENCES projects(id),kind TEXT NOT NULL CHECK(kind IN('appointment','shift')),
        title TEXT NOT NULL,details TEXT NOT NULL,start_at TEXT NOT NULL,end_at TEXT NOT NULL,timezone TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN('scheduled','cancelled')),series_id TEXT REFERENCES business_appointment_series(id),occurrence_index INTEGER,
        revision INTEGER NOT NULL,updated_by TEXT NOT NULL REFERENCES users(id),updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_appointment_employees(
        appointment_id TEXT NOT NULL REFERENCES business_appointments(id),employee_id TEXT NOT NULL REFERENCES business_employees(id),
        PRIMARY KEY(appointment_id,employee_id))''',
        '''CREATE TABLE IF NOT EXISTS business_appointment_resources(
        appointment_id TEXT NOT NULL REFERENCES business_appointments(id),resource_id TEXT NOT NULL REFERENCES business_resources(id),
        PRIMARY KEY(appointment_id,resource_id))''',
        '''CREATE TABLE IF NOT EXISTS business_absences(
        id TEXT PRIMARY KEY,employee_id TEXT NOT NULL REFERENCES business_employees(id),start_date TEXT NOT NULL,end_date TEXT NOT NULL,
        kind TEXT NOT NULL CHECK(kind IN('vacation','sick','other')),details TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN('pending','approved','rejected','cancelled')),
        revision INTEGER NOT NULL,requested_by TEXT NOT NULL REFERENCES users(id),approved_by TEXT REFERENCES users(id),updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_planning_requests(
        user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,operation TEXT NOT NULL,
        request_hash TEXT NOT NULL,result_json TEXT NOT NULL,PRIMARY KEY(user_id,request_id))''',
        'CREATE INDEX IF NOT EXISTS business_appointments_range ON business_appointments(start_at,end_at,project_id)',
        'CREATE INDEX IF NOT EXISTS business_absences_range ON business_absences(employee_id,start_date,end_date)',
    ]


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{32}', value):
        raise Problem(400, 'Gültige eindeutige ID erwartet.')
    return value


def _text(value, maximum=200, *, empty=False):
    if (not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip())
            or any(ord(c) < 32 and c not in '\n\r\t' or ord(c) == 127 for c in value)):
        raise Problem(400, 'Gültiger begrenzter Text erwartet.')
    return value.strip()


def _integer(value, low=0, high=10**12):
    if type(value) is not int or not low <= value <= high:
        raise Problem(400, 'Gültige ganze Zahl erwartet.')
    return value


def _date(value):
    try:
        if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError()
        result = date.fromisoformat(value)
        if not 1900 <= result.year <= 2200:
            raise ValueError()
        return result
    except (ValueError, TypeError):
        raise Problem(400, 'Gültiges ISO-Datum erwartet.') from None


def _instant(value):
    try:
        if not isinstance(value, str) or len(value) > 40:
            raise ValueError()
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.tzinfo is None or result.utcoffset() is None or not 1900 <= result.year <= 2200:
            raise ValueError()
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError):
        raise Problem(400, 'Zeitpunkt mit Zeitzone erwartet.') from None


def _zone(value):
    try:
        if not isinstance(value, str) or len(value) > 100:
            raise ValueError()
        return ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError):
        raise Problem(400, 'Gültige IANA-Zeitzone erwartet.') from None


def _fresh(office, actor):
    if not isinstance(actor, dict):
        raise Problem(401, 'Bitte anmelden.')
    row = office.db.execute('SELECT id,email,role,active FROM users WHERE id=?', (actor.get('id'),)).fetchone()
    if not row or row['active'] != 1:
        raise Problem(401, 'Bitte anmelden.')
    return dict(row)


def _require(office, actor, permission, project_id=None):
    from business_foundation import require_permission
    return require_permission(office, _fresh(office, actor), permission, project_id)


def _has(office, actor, permission, project_id=None):
    try:
        _require(office, actor, permission, project_id)
    except Problem as error:
        if error.status in (403, 404):
            return False
        raise
    return True


def _request(db, actor, operation, data, *, table='business_planning_requests'):
    if not isinstance(data, dict):
        raise Problem(400, 'JSON-Objekt erwartet.')
    request = _id(data.get('request_id'))
    try:
        fingerprint = digest(canonical({'operation': operation, 'data': data}))
    except (ValueError, TypeError, UnicodeError):
        raise Problem(400, 'Gültige JSON-Eingabe erwartet.') from None
    row = db.execute('SELECT * FROM ' + table + ' WHERE user_id=? AND request_id=?', (actor['id'], request)).fetchone()
    if row:
        if row['operation'] != operation or row['request_hash'] != fingerprint:
            raise Problem(409, 'Diese Anfrage-ID wurde bereits mit anderem Inhalt verwendet.')
        return fingerprint, json.loads(row['result_json'])
    return fingerprint, None


def _remember(db, actor, operation, data, fingerprint, result, *, table='business_planning_requests'):
    db.execute('INSERT INTO ' + table + '(user_id,request_id,operation,request_hash,result_json) VALUES(?,?,?,?,?)',
               (actor['id'], data['request_id'], operation, fingerprint, canonical(result)))


def _shape(data, fields):
    if not isinstance(data, dict) or set(data) - set(fields) - {'id', 'revision', 'request_id'}:
        raise Problem(400, 'Unbekannte oder unvollständige Eingabefelder.')


class Planning:
    def __init__(self, office, *, clock=None):
        self.office, self.db = office, office.db
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def now(self):
        return self.clock().astimezone(timezone.utc).isoformat(timespec='seconds')

    def employee(self, identifier):
        row = self.db.execute('SELECT e.*,u.active AS user_active FROM business_employees e JOIN users u ON u.id=e.user_id WHERE e.id=?',
                              (_id(identifier),)).fetchone()
        if not row:
            raise Problem(404, 'Mitarbeiter nicht verfügbar.')
        return dict(row)

    def own_employee(self, actor):
        actor = _fresh(self.office, actor)
        row = self.db.execute('SELECT id FROM business_employees WHERE user_id=? AND active=1', (actor['id'],)).fetchone()
        if not row:
            raise Problem(409, 'Für diesen Zugang zuerst ein Mitarbeiterprofil anlegen.')
        return self.employee(row['id'])

    def _employee_view(self, row, actor, project_id=None):
        result = {k: row[k] for k in ('id', 'user_id', 'name', 'active', 'revision', 'updated_at')}
        result['active'] = bool(result['active'])
        if _has(self.office, actor, 'personnel.read', project_id):
            result.update({k: row[k] for k in ('weekly_minutes', 'hourly_cost_minor', 'employment_from', 'employment_to')})
        return result

    @_atomic
    def employees(self, actor, query=None):
        actor = _fresh(self.office, actor)
        query = query or {}
        project_id = query.get('project_id')
        full = _has(self.office, actor, 'personnel.read', project_id)
        if not full:
            _require(self.office, actor, 'planning.read', query.get('project_id'))
        allowed = {p['id'] for p in self.office.projects(actor)
                   if _has(self.office, actor, 'planning.read', p['id'])}
        if query.get('project_id'):
            self.office.project(actor, _id(query['project_id']))
            allowed = {query['project_id']}
        result = []
        for row in self.db.execute('SELECT * FROM business_employees ORDER BY name,id').fetchall():
            if (full and not project_id) or row['user_id'] == actor['id'] or any(self.db.execute(
                    'SELECT 1 FROM assignments WHERE user_id=? AND project_id=?', (row['user_id'], p)).fetchone() for p in allowed):
                result.append(self._employee_view(row, actor, project_id))
        return {'items': result}

    @_atomic
    def save_employee(self, actor, data):
        actor = _require(self.office, actor, 'personnel.manage')
        _shape(data, ('user_id', 'name', 'active', 'weekly_minutes', 'hourly_cost_minor', 'employment_from', 'employment_to', 'effective_from'))
        fp, previous = _request(self.db, actor, 'employee', data)
        if previous is not None:
            return previous
        current = self.employee(data['id']) if data.get('id') else None
        if current and data.get('revision') != current['revision']:
            raise Problem(409, 'Mitarbeiterprofil wurde inzwischen geändert.')
        if current and data.get('user_id', current['user_id']) != current['user_id']:
            raise Problem(409, 'Ein Mitarbeiterprofil kann nicht auf einen anderen Zugang umgebucht werden.')
        value = dict(current or {'id': uuid.uuid4().hex, 'active': 1, 'weekly_minutes': 2400,
                                'hourly_cost_minor': 0, 'employment_from': None, 'employment_to': None})
        value.update({k: v for k, v in data.items() if k in ('user_id', 'name', 'active', 'weekly_minutes', 'hourly_cost_minor', 'employment_from', 'employment_to')})
        value['user_id'], value['name'] = _id(value.get('user_id')), _text(value.get('name'))
        if type(value['active']) not in (bool, int) or value['active'] not in (0, 1):
            raise Problem(400, 'Aktiv muss ein Wahrheitswert sein.')
        value['active'] = int(value['active'])
        _integer(value['weekly_minutes'], 0, 10080)
        _integer(value['hourly_cost_minor'], 0, 10**9)
        for key in ('employment_from', 'employment_to'):
            if value[key] is not None:
                value[key] = _date(value[key]).isoformat()
        if value['employment_from'] and value['employment_to'] and value['employment_from'] > value['employment_to']:
            raise Problem(400, 'Beschäftigungsende liegt vor Beginn.')
        if not self.db.execute('SELECT 1 FROM users WHERE id=? AND active=1', (value['user_id'],)).fetchone():
            raise Problem(400, 'Aktiver Benutzer erwartet.')
        duplicate = self.db.execute('SELECT id FROM business_employees WHERE user_id=?', (value['user_id'],)).fetchone()
        if duplicate and duplicate['id'] != value['id']:
            raise Problem(409, 'Für diesen Zugang existiert bereits ein Mitarbeiterprofil.')
        value.update(revision=(current['revision'] if current else 0) + 1, updated_at=self.now())
        keys = ('id', 'user_id', 'name', 'active', 'weekly_minutes', 'hourly_cost_minor', 'employment_from', 'employment_to', 'revision', 'updated_at')
        self.db.execute('INSERT INTO business_employees(' + ','.join(keys) + ') VALUES(' + ','.join('?' for _ in keys) + ') '
            'ON CONFLICT(id) DO UPDATE SET ' + ','.join(k + '=excluded.' + k for k in keys[1:]), tuple(value[k] for k in keys))
        effective = _date(data.get('effective_from', self.now()[:10] if current else '1900-01-01')).isoformat()
        self.db.execute('INSERT INTO business_employee_terms(employee_id,effective_from,revision,weekly_minutes,hourly_cost_minor) VALUES(?,?,?,?,?)',
                        (value['id'], effective, value['revision'], value['weekly_minutes'], value['hourly_cost_minor']))
        result = self._employee_view(value, actor)
        self.office.audit(actor, 'personnel.employee.saved', value['id'])
        _remember(self.db, actor, 'employee', data, fp, result)
        return result

    @_atomic
    def resources(self, actor, query=None):
        _require(self.office, actor, 'planning.read', (query or {}).get('project_id'))
        return {'items': [dict(row, active=bool(row['active'])) for row in self.db.execute('SELECT * FROM business_resources ORDER BY name,id').fetchall()]}

    @_atomic
    def save_resource(self, actor, data):
        actor = _require(self.office, actor, 'planning.write')
        _shape(data, ('name', 'kind', 'active', 'code'))
        fp, previous = _request(self.db, actor, 'resource', data)
        if previous is not None:
            return previous
        current = self.db.execute('SELECT * FROM business_resources WHERE id=?', (_id(data['id']),)).fetchone() if data.get('id') else None
        if data.get('id') and not current:
            raise Problem(404, 'Ressource nicht verfügbar.')
        if current and data.get('revision') != current['revision']:
            raise Problem(409, 'Ressource wurde inzwischen geändert.')
        value = dict(current or {'id': uuid.uuid4().hex, 'active': True, 'code': None})
        value.update({k: v for k, v in data.items() if k in ('name', 'kind', 'active', 'code')})
        value['name'] = _text(value.get('name'))
        if value.get('kind') not in ('vehicle', 'machine', 'tool') or type(value['active']) not in (bool, int) or value['active'] not in (0, 1):
            raise Problem(400, 'Ressourcenart oder Aktivstatus ungültig.')
        value['active'] = int(value['active'])
        value['code'] = _text(value['code'], 200) if value['code'] else None
        if value['code'] and self.db.execute('SELECT 1 FROM business_resources WHERE code=? AND id<>?', (value['code'], value['id'])).fetchone():
            raise Problem(409, 'Dieser Ressourcen-Code ist bereits vergeben.')
        value.update(revision=(current['revision'] if current else 0) + 1, updated_at=self.now())
        self.db.execute('INSERT INTO business_resources(id,name,kind,active,code,revision,updated_at) VALUES(?,?,?,?,?,?,?) '
            'ON CONFLICT(id) DO UPDATE SET name=excluded.name,kind=excluded.kind,active=excluded.active,code=excluded.code,revision=excluded.revision,updated_at=excluded.updated_at',
            tuple(value[k] for k in ('id', 'name', 'kind', 'active', 'code', 'revision', 'updated_at')))
        value['active'] = bool(value['active'])
        _remember(self.db, actor, 'resource', data, fp, value)
        self.office.audit(actor, 'planning.resource.saved', value['id'])
        return value

    def _appointment(self, row):
        result = dict(row)
        for kind in ('employee', 'resource'):
            result[kind + '_ids'] = [r[0] for r in self.db.execute('SELECT ' + kind + '_id FROM business_appointment_' + kind + 's WHERE appointment_id=? ORDER BY ' + kind + '_id', (row['id'],)).fetchall()]
        return result

    def _values(self, actor, project, data, current=None, *, kind='appointment'):
        values = dict(current or {'id': uuid.uuid4().hex, 'details': '', 'timezone': 'Europe/Berlin', 'status': 'scheduled',
                                 'employee_ids': [], 'resource_ids': [], 'series_id': None, 'occurrence_index': None})
        values.update({k: v for k, v in data.items() if k in ('title', 'details', 'timezone', 'start_at', 'end_at', 'status', 'employee_ids', 'resource_ids')})
        values['title'], values['details'] = _text(values.get('title')), _text(values['details'], 10000, empty=True)
        _zone(values['timezone'])
        values['start_at'], values['end_at'] = _instant(values.get('start_at')).isoformat(), _instant(values.get('end_at')).isoformat()
        if values['start_at'] >= values['end_at'] or values['status'] not in ('scheduled', 'cancelled'):
            raise Problem(400, 'Gültiger Terminzeitraum und Status erwartet.')
        if (_instant(values['end_at']) - _instant(values['start_at'])).days > 366:
            raise Problem(400, 'Ein einzelner Einsatz darf höchstens ein Jahr dauern.')
        for name in ('employee_ids', 'resource_ids'):
            if not isinstance(values[name], list) or len(values[name]) > 100:
                raise Problem(400, 'Eindeutige begrenzte Mitarbeiter-/Ressourcenliste erwartet.')
            values[name] = [_id(identifier) for identifier in values[name]]
            if len(set(values[name])) != len(values[name]):
                raise Problem(400, 'Mitarbeiter und Ressourcen dürfen nicht doppelt zugewiesen werden.')
            values[name].sort()
        for identifier in values['employee_ids']:
            employee = self.employee(identifier)
            if not employee['active'] or not employee['user_active']:
                if not (current and values['status'] == 'cancelled' and identifier in current['employee_ids']):
                    raise Problem(400, 'Aktiver Mitarbeiter erwartet.')
            user = self.db.execute('SELECT id,email,role FROM users WHERE id=?', (employee['user_id'],)).fetchone()
            if project:
                try:
                    self.office.project(dict(user), project)
                except Problem:
                    raise Problem(400, 'Mitarbeiter muss diesem Projekt zugeordnet sein.') from None
        for identifier in values['resource_ids']:
            if not self.db.execute('SELECT 1 FROM business_resources WHERE id=? AND active=1', (identifier,)).fetchone():
                raise Problem(400, 'Aktive Ressource erwartet.')
        values.update(project_id=project, kind=kind)
        return values

    def _conflicts(self, values):
        if values['status'] == 'cancelled':
            return []
        result = []
        for key in ('employee', 'resource'):
            for identifier in values[key + '_ids']:
                rows = self.db.execute('SELECT a.id,a.start_at,a.end_at FROM business_appointments a JOIN business_appointment_' + key + 's b ON b.appointment_id=a.id '
                    "WHERE b." + key + "_id=? AND a.status='scheduled' AND a.start_at<? AND a.end_at>? AND a.id<>?",
                    (identifier, values['end_at'], values['start_at'], values['id'])).fetchall()
                result.extend({'kind': key, key + '_id': identifier, 'start_at': r['start_at'], 'end_at': r['end_at']} for r in rows)
        zone = _zone(values['timezone'])
        start_day = _instant(values['start_at']).astimezone(zone).date().isoformat()
        end_day = (_instant(values['end_at']) - timedelta(microseconds=1)).astimezone(zone).date().isoformat()
        for employee in values['employee_ids']:
            for row in self.db.execute("SELECT start_date,end_date FROM business_absences WHERE employee_id=? AND status='approved' AND start_date<=? AND end_date>=?",
                                       (employee, end_day, start_day)).fetchall():
                result.append({'kind': 'absence', 'employee_id': employee, 'start_date': row['start_date'], 'end_date': row['end_date']})
        return result

    @_atomic
    def conflicts(self, actor, project_id, data):
        _require(self.office, actor, 'planning.write', project_id)
        current = None
        if data.get('id'):
            row = self.db.execute('SELECT * FROM business_appointments WHERE id=? AND project_id=?', (_id(data['id']), project_id)).fetchone()
            if not row:
                raise Problem(404, 'Termin nicht verfügbar.')
            current = self._appointment(row)
        return {'items': self._conflicts(self._values(actor, project_id, data, current))}

    @_atomic
    def save_appointment(self, actor, project_id, data, *, kind='appointment'):
        actor = _require(self.office, actor, 'planning.write', project_id)
        if project_id:
            self.office.project(actor, _id(project_id))
        _shape(data, ('project_id', 'title', 'details', 'start_at', 'end_at', 'timezone', 'employee_ids', 'resource_ids', 'status', 'recurrence', 'override_conflicts', 'override_reason'))
        operation = 'appointment:' + str(project_id) + ':' + kind
        fp, previous = _request(self.db, actor, operation, data)
        if previous is not None:
            return previous
        row = self.db.execute('SELECT * FROM business_appointments WHERE id=?', (_id(data['id']),)).fetchone() if data.get('id') else None
        if data.get('id') and (not row or row['project_id'] != project_id or row['kind'] != kind):
            raise Problem(404, 'Termin nicht verfügbar.')
        current = self._appointment(row) if row else None
        if current and data.get('revision') != current['revision']:
            raise Problem(409, 'Termin wurde inzwischen verschoben. Bitte vergleichen.')
        values = self._values(actor, project_id, data, current, kind=kind)
        occurrences = [values]
        recurrence = data.get('recurrence')
        if recurrence is not None:
            if current or not isinstance(recurrence, dict) or set(recurrence) != {'frequency', 'interval', 'count'}:
                raise Problem(400, 'Serie benötigt Frequenz, Intervall und begrenzte Anzahl; bestehende Termine einzeln ändern.')
            frequency = recurrence['frequency']
            if frequency not in ('daily', 'weekly', 'monthly'):
                raise Problem(400, 'Tägliche, wöchentliche oder monatliche Serie erwartet.')
            interval, count = _integer(recurrence['interval'], 1, 52), _integer(recurrence['count'], 1, 365)
            zone = _zone(values['timezone'])
            start, end = _instant(values['start_at']).astimezone(zone), _instant(values['end_at']).astimezone(zone)
            series_id = uuid.uuid4().hex
            occurrences = []
            for index in range(count):
                def shifted(moment):
                    if frequency in ('daily', 'weekly'):
                        naive = moment.replace(tzinfo=None) + timedelta(days=index * interval * (7 if frequency == 'weekly' else 1))
                    else:
                        number = moment.year * 12 + moment.month - 1 + index * interval
                        year, month = divmod(number, 12)
                        naive = moment.replace(tzinfo=None, year=year, month=month + 1,
                                               day=min(moment.day, month_calendar.monthrange(year, month + 1)[1]))
                    local = naive.replace(tzinfo=zone, fold=moment.fold)
                    utc = local.astimezone(timezone.utc)
                    if utc.astimezone(zone).replace(tzinfo=None) != naive or not 1900 <= utc.year <= 2200:
                        raise Problem(400, 'Ein Serientermin liegt in einer nicht existierenden Ortszeit.')
                    if utc - _instant(values['start_at']) > timedelta(days=5 * 366):
                        raise Problem(400, 'Eine einzelne Serie ist auf fünf Jahre begrenzt.')
                    return utc.isoformat()
                occurrences.append(dict(values, id=values['id'] if index == 0 else uuid.uuid4().hex,
                                        start_at=shifted(start), end_at=shifted(end), series_id=series_id, occurrence_index=index))
            self.db.execute('INSERT INTO business_appointment_series(id,project_id,frequency,interval_count,occurrence_count,timezone,start_at,end_at,title,details,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                            (series_id, project_id, frequency, interval, count, values['timezone'], values['start_at'], values['end_at'], values['title'], values['details'], actor['id'], self.now()))
        all_conflicts = []
        for item in occurrences:
            collisions = self._conflicts(item)
            if collisions:
                if data.get('override_conflicts') is not True:
                    raise Problem(409, 'Mitarbeiter, Ressource oder Abwesenheit kollidieren. Bitte Zeitraum prüfen.')
                _require(self.office, actor, 'planning.override', project_id)
                _text(data.get('override_reason'), 1000)
                all_conflicts.extend(collisions)
            item.update(revision=(current['revision'] if current else 0) + 1, updated_by=actor['id'], updated_at=self.now())
            keys = ('id', 'project_id', 'kind', 'title', 'details', 'start_at', 'end_at', 'timezone', 'status', 'series_id', 'occurrence_index', 'revision', 'updated_by', 'updated_at')
            self.db.execute('INSERT INTO business_appointments(' + ','.join(keys) + ') VALUES(' + ','.join('?' for _ in keys) + ') '
                'ON CONFLICT(id) DO UPDATE SET ' + ','.join(k + '=excluded.' + k for k in keys[1:]), tuple(item[k] for k in keys))
            for name in ('employee', 'resource'):
                self.db.execute('DELETE FROM business_appointment_' + name + 's WHERE appointment_id=?', (item['id'],))
                for identifier in item[name + '_ids']:
                    self.db.execute('INSERT INTO business_appointment_' + name + 's(appointment_id,' + name + '_id) VALUES(?,?)', (item['id'], identifier))
        result = dict(occurrences[0], conflicts=all_conflicts)
        if recurrence:
            result['occurrence_ids'] = [item['id'] for item in occurrences]
        if all_conflicts:
            self.office.audit(actor, 'planning.conflict.overridden', result['id'])
        self.office.audit(actor, 'planning.appointment.saved', result['id'])
        if project_id and _has(self.office, actor, 'documents.read', project_id):
            from business_foundation import BusinessFoundation
            BusinessFoundation(self.office, clock=self.now).event(actor, project_id, 'planning.changed',
                'Einsatzplanung aktualisiert', refs={'appointment_id': result['id'], 'revision': result['revision']})
        _remember(self.db, actor, operation, data, fp, result)
        return result

    def save_shift(self, actor, data):
        return self.save_appointment(actor, data.get('project_id'), data, kind='shift')

    def _timeline_item(self, actor, row):
        profile = json.loads(row['profile_payload']) if row['profile_payload'] is not None else {}
        first, last = profile.get('start_date'), profile.get('end_date')
        if first is not None:
            first = _date(first).isoformat()
        if last is not None:
            last = _date(last).isoformat()
        if first is not None and last is not None and last < first:
            raise Problem(500, 'Gespeicherter Projektzeitraum ist ungültig.')
        status = None
        if row['status_id'] is not None:
            if row['status_name'] is None:
                raise Problem(500, 'Gespeicherter Projektstatus ist ungültig.')
            status = dict(id=row['status_id'], name=row['status_name'], color=row['status_color'],
                          terminal=bool(row['status_terminal']))
        return dict(id=row['id'], name=row['name'], start_date=first, end_date=last,
                    revision=row['profile_revision'], phase=profile.get('phase', 'planning'), status=status,
                    can_edit=_has(self.office, actor, 'projects.manage', row['id']),
                    planning_state='scheduled' if first is not None and last is not None else
                                   'partial' if first is not None or last is not None else 'unscheduled')

    @_atomic
    def timeline(self, actor, query=None):
        """Civil project dates, independent of appointment instants and HR/finance."""
        query = query or {}
        if not isinstance(query, dict) or set(query) - {'from', 'to', 'project_id'}:
            raise Problem(400, 'Datumsbereich und optional ein Projekt erwartet.')
        actor = _fresh(self.office, actor)
        project = _id(query['project_id']) if query.get('project_id') is not None else None
        actor = _require(self.office, actor, 'planning.read', project)
        year = self.clock().astimezone(timezone.utc).year
        first = _date(query.get('from', f'{year:04d}-01-01'))
        last = _date(query.get('to', f'{year:04d}-12-31'))
        if last < first or (last - first).days + 1 > TIMELINE_MAX_DAYS:
            raise Problem(400, 'Projektplanung benötigt einen Bereich von höchstens 1096 Tagen.')
        conditions, parameters = [], []
        if project is not None:
            conditions.append('p.id=?')
            parameters.append(project)
        elif actor['role'] != 'owner':
            # Do not fetch profiles from unrelated projects. The fresh domain
            # permission check below remains authoritative for every DTO.
            conditions.append('EXISTS(SELECT 1 FROM assignments a WHERE a.project_id=p.id AND a.user_id=?)')
            parameters.append(actor['id'])
            conditions.append("NOT EXISTS(SELECT 1 FROM business_permission_grants g WHERE g.user_id=? "
                              "AND g.permission='planning.read' AND g.scope=p.id AND g.effect='deny')")
            parameters.append(actor['id'])
        rows = self.db.execute(_TIMELINE_SELECT + (' WHERE ' + ' AND '.join(conditions) if conditions else '') +
                               ' ORDER BY p.id LIMIT 501', tuple(parameters)).fetchall()
        if len(rows) > TIMELINE_MAX_PROJECTS:
            raise Problem(413, 'Zu viele Projekte für eine gemeinsame Ansicht; bitte ein Projekt auswählen.')
        scheduled, unplanned = [], []
        for row in rows:
            if not _has(self.office, actor, 'planning.read', row['id']):
                continue
            item = self._timeline_item(actor, row)
            if item['planning_state'] != 'scheduled':
                unplanned.append(item)
            elif item['start_date'] <= last.isoformat() and item['end_date'] >= first.isoformat():
                scheduled.append(item)
        scheduled.sort(key=lambda item: (item['start_date'], item['name'].casefold(), item['id']))
        unplanned.sort(key=lambda item: (item['name'].casefold(), item['id']))
        return {'from': first.isoformat(), 'to': last.isoformat(), 'items': scheduled, 'unplanned': unplanned}

    @_atomic
    def save_project_dates(self, actor, project_id, data):
        """Use the canonical workspace profile, its revision and retry receipt."""
        if not isinstance(data, dict) or set(data) != {'request_id', 'revision', 'start_date', 'end_date'}:
            raise Problem(400, 'Vorgangs-ID, Projektversion, Beginn und Ende erwartet.')
        project_id = _id(project_id)
        actor = _require(self.office, actor, 'planning.read', project_id)
        actor = _require(self.office, actor, 'projects.manage', project_id)
        from project_workspace import ProjectWorkspace
        ProjectWorkspace(self.office, clock=self.clock).save_profile(actor, project_id, data)
        row = self.db.execute(_TIMELINE_SELECT + ' WHERE p.id=?', (project_id,)).fetchone()
        if row is None:
            raise Problem(404, 'Projekt nicht verfügbar.')
        # A lost-response retry acknowledges today's canonical state, even if
        # another profile edit has happened since the original committed write.
        return self._timeline_item(actor, row)

    @_atomic
    def calendar(self, actor, query=None):
        actor, query = _fresh(self.office, actor), query or {}
        _require(self.office, actor, 'planning.read', query.get('project_id'))
        zone = _zone(query.get('timezone', 'Europe/Berlin'))
        from_value = query.get('from', self.now()[:10])
        first_at = (_instant(from_value) if isinstance(from_value, str) and len(from_value) > 10 else
                    datetime.combine(_date(from_value), time.min, zone).astimezone(timezone.utc))
        start = first_at.astimezone(zone).date()
        to_value = query.get('to', (start + timedelta(days=31)).isoformat())
        last_at = (_instant(to_value) if isinstance(to_value, str) and len(to_value) > 10 else
                   datetime.combine(_date(to_value) + timedelta(days=1), time.min, zone).astimezone(timezone.utc))
        end = (last_at - timedelta(microseconds=1)).astimezone(zone).date()
        if last_at <= first_at or last_at - first_at > timedelta(days=5 * 366):
            raise Problem(400, 'Kalenderbereich muss zwischen null und fünf Jahren liegen.')
        first, last = first_at.isoformat(), last_at.isoformat()
        allowed = {p['id'] for p in self.office.projects(actor)
                   if _has(self.office, actor, 'planning.read', p['id'])}
        if query.get('project_id'):
            self.office.project(actor, _id(query['project_id']))
            allowed = {query['project_id']}
        employees = self.employees(actor, {'project_id': query['project_id']} if query.get('project_id') else {})['items']
        allowed_employees = {e['id'] for e in employees}
        employee = query.get('employee_id')
        if employee and _id(employee) not in allowed_employees:
            raise Problem(404, 'Mitarbeiterkalender nicht verfügbar.')
        result = []
        for row in self.db.execute('SELECT * FROM business_appointments WHERE start_at<? AND end_at>? ORDER BY start_at,id', (last, first)).fetchall():
            item = self._appointment(row)
            if row['project_id'] not in allowed and not (row['project_id'] is None and any(e in allowed_employees for e in item['employee_ids'])):
                continue
            if employee and employee not in item['employee_ids']:
                continue
            result.append(item)
        absences = []
        for row in self.db.execute("SELECT id,employee_id,start_date,end_date,revision FROM business_absences WHERE status='approved' AND start_date<=? AND end_date>=? ORDER BY start_date,id", (end.isoformat(), start.isoformat())).fetchall():
            if row['employee_id'] in allowed_employees and (not employee or row['employee_id'] == employee):
                absences.append(dict(row, status='unavailable'))
        return {'appointments': result, 'employees': employees if _has(self.office, actor, 'personnel.read', query.get('project_id')) else
                [{k: v for k, v in e.items() if k not in ('hourly_cost_minor', 'weekly_minutes', 'employment_from', 'employment_to')} for e in employees],
                'resources': self.resources(actor)['items'], 'absences': absences}

    def appointments(self, actor, query=None):
        return {'items': self.calendar(actor, query)['appointments']}

    @_atomic
    def absences(self, actor, query=None):
        actor, query = _fresh(self.office, actor), query or {}
        own = self.db.execute('SELECT id FROM business_employees WHERE user_id=?', (actor['id'],)).fetchone()
        full = _has(self.office, actor, 'personnel.read')
        if not full:
            _require(self.office, actor, 'time.own')
        employee = query.get('employee_id')
        if employee and not full and (not own or employee != own['id']):
            raise Problem(403, 'Nur eigene Abwesenheiten sind zugänglich.')
        return {'items': [dict(row) for row in self.db.execute('SELECT * FROM business_absences ORDER BY start_date,id').fetchall()
                          if (full or own and row['employee_id'] == own['id']) and (not employee or row['employee_id'] == employee)]}

    @_atomic
    def save_absence(self, actor, data):
        actor = _fresh(self.office, actor)
        _shape(data, ('employee_id', 'start_date', 'end_date', 'kind', 'details'))
        employee = self.employee(data.get('employee_id'))
        _require(self.office, actor, 'time.own' if employee['user_id'] == actor['id'] else 'personnel.manage')
        fp, previous = _request(self.db, actor, 'absence', data)
        if previous is not None:
            return previous
        current = self.db.execute('SELECT * FROM business_absences WHERE id=?', (_id(data['id']),)).fetchone() if data.get('id') else None
        if data.get('id') and (not current or current['employee_id'] != employee['id']):
            raise Problem(404, 'Abwesenheit nicht verfügbar.')
        if current and (current['revision'] != data.get('revision') or current['status'] != 'pending'):
            raise Problem(409, 'Abwesenheit ist geändert oder bereits entschieden.')
        first, last = _date(data.get('start_date')), _date(data.get('end_date'))
        if last < first or (last - first).days > 366 or data.get('kind') not in ('vacation', 'sick', 'other'):
            raise Problem(400, 'Gültige Abwesenheit erwartet.')
        result = dict(id=current['id'] if current else uuid.uuid4().hex, employee_id=employee['id'], start_date=first.isoformat(),
                      end_date=last.isoformat(), kind=data['kind'], details=_text(data.get('details', ''), 5000, empty=True), status='pending',
                      revision=(current['revision'] if current else 0) + 1, requested_by=actor['id'], approved_by=None, updated_at=self.now())
        keys = tuple(result)
        self.db.execute('INSERT INTO business_absences(' + ','.join(keys) + ') VALUES(' + ','.join('?' for _ in keys) + ') '
            'ON CONFLICT(id) DO UPDATE SET ' + ','.join(k + '=excluded.' + k for k in keys[1:]), tuple(result.values()))
        _remember(self.db, actor, 'absence', data, fp, result)
        self.office.audit(actor, 'personnel.absence.requested', result['id'])
        return result

    @_atomic
    def approve_absence(self, actor, identifier, data):
        actor = _require(self.office, actor, 'time.approve')
        _shape(data, ('status',))
        fp, previous = _request(self.db, actor, 'absence-decision:' + _id(identifier), data)
        if previous is not None:
            return previous
        current = self.db.execute('SELECT * FROM business_absences WHERE id=?', (identifier,)).fetchone()
        if not current:
            raise Problem(404, 'Abwesenheit nicht verfügbar.')
        if current['revision'] != data.get('revision') or data.get('status') not in ('approved', 'rejected', 'cancelled'):
            raise Problem(409, 'Abwesenheitsentscheidung ist veraltet oder ungültig.')
        result = dict(current, status=data['status'], revision=current['revision'] + 1, approved_by=actor['id'], updated_at=self.now())
        self.db.execute('UPDATE business_absences SET status=?,revision=?,approved_by=?,updated_at=? WHERE id=?',
                        (result['status'], result['revision'], actor['id'], result['updated_at'], identifier))
        self.office.audit(actor, 'personnel.absence.decided', identifier)
        _remember(self.db, actor, 'absence-decision:' + identifier, data, fp, result)
        return result


def validate_integrity(office):
    db = office.db
    try:
        for row in db.execute('SELECT * FROM business_employees').fetchall():
            _id(row['id']); _id(row['user_id']); _text(row['name']); _integer(row['revision'], 1)
            _integer(row['weekly_minutes'], 0, 10080); _integer(row['hourly_cost_minor'], 0)
            if not db.execute('SELECT 1 FROM users WHERE id=?', (row['user_id'],)).fetchone():
                raise ValueError('Employee user missing')
            if row['active'] not in (0, 1):
                raise ValueError('Invalid employee activation')
            for key in ('employment_from', 'employment_to'):
                if row[key] is not None:
                    _date(row[key])
        for row in db.execute('SELECT * FROM business_employee_terms').fetchall():
            _id(row['employee_id']); _date(row['effective_from']); _integer(row['revision'], 1)
            _integer(row['weekly_minutes'], 0, 10080); _integer(row['hourly_cost_minor'], 0)
        for row in db.execute('SELECT * FROM business_resources').fetchall():
            _id(row['id']); _text(row['name']); _integer(row['revision'], 1); _instant(row['updated_at'])
            if row['kind'] not in ('vehicle', 'machine', 'tool') or row['active'] not in (0, 1):
                raise ValueError('Invalid planning resource')
        for row in db.execute('SELECT * FROM business_appointment_series').fetchall():
            _id(row['id']); _zone(row['timezone']); _integer(row['occurrence_count'], 1, 365)
            _integer(row['interval_count'], 1, 52)
            if row['frequency'] not in ('daily', 'weekly', 'monthly'):
                raise ValueError('Invalid appointment series')
        for row in db.execute('SELECT * FROM business_appointments').fetchall():
            _id(row['id']); _zone(row['timezone']); _integer(row['revision'], 1)
            if _instant(row['start_at']) >= _instant(row['end_at']):
                raise ValueError('Invalid appointment interval')
            _text(row['title']); _text(row['details'], 10000, empty=True); _instant(row['updated_at'])
            if row['status'] not in ('scheduled', 'cancelled') or row['kind'] not in ('appointment', 'shift') or row['kind'] == 'appointment' and row['project_id'] is None:
                raise ValueError('Invalid appointment type or project')
            if row['series_id']:
                series = db.execute('SELECT project_id,occurrence_count FROM business_appointment_series WHERE id=?', (row['series_id'],)).fetchone()
                if not series or series['project_id'] != row['project_id'] or type(row['occurrence_index']) is not int or not 0 <= row['occurrence_index'] < series['occurrence_count']:
                    raise ValueError('Appointment series mismatch')
            elif row['occurrence_index'] is not None:
                raise ValueError('Occurrence without series')
        for row in db.execute('SELECT * FROM business_absences').fetchall():
            if _date(row['start_date']) > _date(row['end_date']):
                raise ValueError('Invalid absence interval')
            _integer(row['revision'], 1); _text(row['details'], 5000, empty=True)
            if row['kind'] not in ('vacation', 'sick', 'other') or row['status'] not in ('pending', 'approved', 'rejected', 'cancelled'):
                raise ValueError('Invalid absence state')
        for row in db.execute('SELECT * FROM business_planning_requests').fetchall():
            _id(row['request_id'])
            if not re.fullmatch(r'[a-f0-9]{64}', row['request_hash']) or not isinstance(json.loads(row['result_json']), dict):
                raise ValueError('Invalid planning receipt')
    except (Problem, TypeError, ValueError, KeyError) as error:
        raise ValueError('Planning integrity check failed') from error
    return True


def protected_tables():
    return ('business_planning_requests', 'business_employee_terms', 'business_appointment_series')


def dispatch(office, actor, path, method, data):
    service = Planning(office)
    query = data.get('_query', {})
    match = re.fullmatch(r'/(employees|resources|appointments|absences|shifts)(?:/([a-f0-9]{32}))?', path)
    if match:
        kind, identifier = match.groups()
        if method == 'GET':
            if identifier and kind in ('appointments', 'shifts'):
                actor = _fresh(office, actor)
                row = office.db.execute('SELECT * FROM business_appointments WHERE id=?', (identifier,)).fetchone()
                if not row or kind == 'shifts' and row['kind'] != 'shift':
                    raise Problem(404, 'Eintrag nicht verfügbar.')
                _require(office, actor, 'planning.read', row['project_id'])
                item = service._appointment(row)
                if row['project_id'] is None:
                    allowed = {employee['id'] for employee in service.employees(actor)['items']}
                    if not any(employee in allowed for employee in item['employee_ids']):
                        raise Problem(404, 'Eintrag nicht verfügbar.')
                return item, 200, 'application/json'
            if kind == 'shifts':
                result = {'items': [item for item in service.appointments(actor, query)['items'] if item['kind'] == 'shift']}
            else:
                result = getattr(service, kind)(actor, query)
            if identifier:
                result = next((item for item in result['items'] if item['id'] == identifier), None)
                if result is None:
                    raise Problem(404, 'Eintrag nicht verfügbar.')
            return result, 200, 'application/json'
        if method == 'POST':
            body = dict(data)
            if identifier:
                body['id'] = identifier
            singular = {'employees': 'employee', 'resources': 'resource', 'appointments': 'appointment', 'absences': 'absence', 'shifts': 'shift'}[kind]
            result = (service.save_appointment(actor, body.get('project_id'), body) if kind == 'appointments'
                      else getattr(service, 'save_' + singular)(actor, body))
            return result, 200 if identifier else 201, 'application/json'
    match = re.fullmatch(r'/absences/([a-f0-9]{32})/approve', path)
    if match and method == 'POST':
        return service.approve_absence(actor, match[1], data), 200, 'application/json'
    if path == '/planning/calendar' and method == 'GET':
        return service.calendar(actor, query), 200, 'application/json'
    if path == '/planning/timeline' and method == 'GET':
        return service.timeline(actor, query), 200, 'application/json'
    match = re.fullmatch(r'/planning/projects/([a-f0-9]{32})/dates', path)
    if match and method == 'POST':
        return service.save_project_dates(actor, match[1], data), 200, 'application/json'
    if path == '/planning/conflicts' and method in ('GET', 'POST'):
        body = query if method == 'GET' else data
        return service.conflicts(actor, body.get('project_id'), body), 200, 'application/json'
    return None


def methods(path):
    if re.fullmatch(r'/(employees|resources|appointments|absences|shifts)(?:/[a-f0-9]{32})?', path):
        return 'GET, POST'
    if re.fullmatch(r'/absences/[a-f0-9]{32}/approve', path):
        return 'POST'
    if re.fullmatch(r'/planning/projects/[a-f0-9]{32}/dates', path):
        return 'POST'
    return {'/planning/calendar': 'GET', '/planning/timeline': 'GET', '/planning/conflicts': 'GET, POST'}.get(path)
