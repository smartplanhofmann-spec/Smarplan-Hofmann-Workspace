"""Idempotent attendance events, daily approvals and short-lived positions.

No payroll or provider IO. Positions never enter event fingerprints, ordinary
receipts, audit, CSV or cost reports. Approval needs a durable independent
privacy checkpoint before removing any recorded position.
"""
import csv
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import io
import json
import re
import uuid

from core import Problem, canonical, digest
from business_planning import (Planning, _atomic, _date, _fresh, _has, _id, _instant,
                               _integer, _remember, _request, _require, _shape, _text, _zone)


def schema_statements(binary_type='BYTEA'):
    return [
        '''CREATE TABLE IF NOT EXISTS business_time_categories(
        id TEXT PRIMARY KEY,name TEXT NOT NULL,supplement_percent TEXT NOT NULL,active INTEGER NOT NULL,
        revision INTEGER NOT NULL,updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_time_rules(
        id TEXT PRIMARY KEY,effective_from TEXT NOT NULL,revision INTEGER NOT NULL UNIQUE,timezone TEXT NOT NULL,
        daily_target_minutes INTEGER,auto_pause_after_minutes INTEGER NOT NULL,auto_pause_minutes INTEGER NOT NULL,
        second_after_minutes INTEGER NOT NULL,second_pause_minutes INTEGER NOT NULL,location_enabled INTEGER NOT NULL,
        reminder_time TEXT,created_by TEXT NOT NULL REFERENCES users(id),updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_time_entries(
        id TEXT PRIMARY KEY,employee_id TEXT NOT NULL REFERENCES business_employees(id),project_id TEXT NOT NULL REFERENCES projects(id),
        category_id TEXT REFERENCES business_time_categories(id),status TEXT NOT NULL CHECK(status IN('working','paused','stopped')),
        started_at TEXT NOT NULL,ended_at TEXT,last_at TEXT NOT NULL,timezone TEXT NOT NULL,device_id TEXT NOT NULL,
        revision INTEGER NOT NULL,last_sequence INTEGER NOT NULL,hourly_cost_minor BIGINT NOT NULL,supplement_percent TEXT NOT NULL,
        updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_time_active(
        employee_id TEXT PRIMARY KEY REFERENCES business_employees(id),entry_id TEXT NOT NULL UNIQUE REFERENCES business_time_entries(id))''',
        '''CREATE TABLE IF NOT EXISTS business_time_events(
        id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL UNIQUE,
        entry_id TEXT NOT NULL REFERENCES business_time_entries(id),action TEXT NOT NULL CHECK(action IN('start','pause','resume','stop')),
        occurred_at TEXT NOT NULL,received_at TEXT NOT NULL,device_id TEXT NOT NULL,sequence INTEGER NOT NULL,
        expected_revision INTEGER NOT NULL,request_hash TEXT NOT NULL,location_hash TEXT,location_redacted_at TEXT,
        UNIQUE(entry_id,sequence))''',
        '''CREATE TABLE IF NOT EXISTS business_time_locations(
        event_id TEXT PRIMARY KEY REFERENCES business_time_events(id),employee_id TEXT NOT NULL REFERENCES business_employees(id),
        work_date TEXT NOT NULL,latitude TEXT NOT NULL,longitude TEXT NOT NULL,accuracy TEXT)''',
        '''CREATE TABLE IF NOT EXISTS business_time_days(
        employee_id TEXT NOT NULL REFERENCES business_employees(id),work_date TEXT NOT NULL,revision INTEGER NOT NULL,
        status TEXT NOT NULL CHECK(status IN('draft','approved')),worked_seconds BIGINT,break_seconds BIGINT,
        auto_pause_seconds BIGINT,net_seconds BIGINT,target_seconds BIGINT,absence_seconds BIGINT,
        rule_id TEXT REFERENCES business_time_rules(id),approved_by TEXT REFERENCES users(id),approved_at TEXT,
        PRIMARY KEY(employee_id,work_date))''',
        '''CREATE TABLE IF NOT EXISTS business_time_segments(
        entry_id TEXT NOT NULL REFERENCES business_time_entries(id),work_date TEXT NOT NULL,
        worked_seconds BIGINT NOT NULL,break_seconds BIGINT NOT NULL,PRIMARY KEY(entry_id,work_date))''',
        '''CREATE TABLE IF NOT EXISTS business_time_requests(
        user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,operation TEXT NOT NULL,
        request_hash TEXT NOT NULL,result_json TEXT NOT NULL,PRIMARY KEY(user_id,request_id))''',
        '''CREATE TABLE IF NOT EXISTS business_time_privacy(
        employee_id TEXT NOT NULL REFERENCES business_employees(id),work_date TEXT NOT NULL,
        checkpoint_generation BIGINT NOT NULL,redacted_at TEXT NOT NULL,PRIMARY KEY(employee_id,work_date))''',
        '''CREATE TABLE IF NOT EXISTS business_time_adjustments(
        id TEXT PRIMARY KEY,employee_id TEXT NOT NULL REFERENCES business_employees(id),effective_date TEXT NOT NULL,
        seconds BIGINT NOT NULL,reason TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_time_corrections(
        id TEXT PRIMARY KEY,entry_id TEXT NOT NULL REFERENCES business_time_entries(id),work_date TEXT NOT NULL,
        delta_seconds BIGINT NOT NULL,reason TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        'CREATE INDEX IF NOT EXISTS business_time_employee_range ON business_time_entries(employee_id,started_at,ended_at)',
        'CREATE INDEX IF NOT EXISTS business_time_location_day ON business_time_locations(employee_id,work_date)',
    ]


def _percent(value):
    try:
        if not isinstance(value, str) or len(value) > 20:
            raise ValueError()
        number = Decimal(value)
        if not number.is_finite() or not 0 <= number <= 1000 or number.as_tuple().exponent < -4:
            raise ValueError()
        return format(number, 'f')
    except (InvalidOperation, ValueError):
        raise Problem(400, 'Zuschlag als genaue Dezimalzahl zwischen 0 und 1000 erwartet.') from None


def _position(value):
    if not isinstance(value, dict) or set(value) - {'latitude', 'longitude', 'accuracy'} or not {'latitude', 'longitude'} <= set(value):
        raise Problem(400, 'Einzelne gültige Start-/Stoppkoordinate erwartet.')
    result = {}
    try:
        for key, limit in (('latitude', Decimal(90)), ('longitude', Decimal(180)), ('accuracy', Decimal(1000000))):
            if key not in value:
                continue
            if isinstance(value[key], bool) or len(str(value[key])) > 40:
                raise ValueError()
            number = Decimal(str(value[key]))
            if not number.is_finite() or not -limit <= number <= limit or key == 'accuracy' and number < 0:
                raise ValueError()
            result[key] = format(number.quantize(Decimal('0.000001')), 'f')
    except (InvalidOperation, ValueError, TypeError):
        raise Problem(400, 'Gültige begrenzte Einzelkoordinate erwartet.') from None
    return result


class TimeTracking:
    def __init__(self, office, *, clock=None):
        self.office, self.db = office, office.db
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.planning = Planning(office, clock=self.clock)

    def now(self):
        return self.clock().astimezone(timezone.utc).isoformat(timespec='seconds')

    def _receipt(self, actor, action, data):
        return _request(self.db, actor, action, data, table='business_time_requests')

    def _remember(self, actor, action, data, fp, result):
        _remember(self.db, actor, action, data, fp, result, table='business_time_requests')

    def _employee(self, actor, identifier=None, *, write=False):
        actor = _fresh(self.office, actor)
        own = self.db.execute('SELECT * FROM business_employees WHERE user_id=?', (actor['id'],)).fetchone()
        if identifier is None:
            if not own:
                raise Problem(409, 'Für diesen Zugang zuerst ein Mitarbeiterprofil anlegen.')
            identifier = own['id']
        if own and identifier == own['id']:
            _require(self.office, actor, 'time.own')
        else:
            _require(self.office, actor, 'personnel.manage' if write else 'personnel.read')
        employee = self.planning.employee(identifier)
        if not employee['active'] or not employee['user_active']:
            raise Problem(409, 'Mitarbeiterprofil ist gesperrt.')
        return actor, employee

    def owns_employee(self, actor, identifier):
        actor = _fresh(self.office, actor)
        employee = self.planning.employee(identifier)
        return employee['user_id'] == actor['id']

    def _project_access(self, actor, employee, project_id, *, write=False):
        permission = ('time.own' if employee['user_id'] == actor['id'] else
                      'personnel.manage' if write else 'personnel.read')
        return _require(self.office, actor, permission, project_id)

    def _rule(self, day):
        row = self.db.execute('SELECT * FROM business_time_rules WHERE effective_from<=? ORDER BY effective_from DESC,revision DESC LIMIT 1', (day,)).fetchone()
        return dict(row) if row else {'id': None, 'revision': 0, 'timezone': 'Europe/Berlin', 'daily_target_minutes': None,
            'auto_pause_after_minutes': 0, 'auto_pause_minutes': 0, 'second_after_minutes': 0, 'second_pause_minutes': 0,
            'location_enabled': 0, 'reminder_time': None}

    @_atomic
    def rules(self, actor, query=None):
        _require(self.office, actor, 'time.own')
        return {'items': [dict(row, location_enabled=bool(row['location_enabled'])) for row in self.db.execute('SELECT * FROM business_time_rules ORDER BY effective_from DESC,revision DESC').fetchall()]}

    @_atomic
    def save_rule(self, actor, data):
        actor = _require(self.office, actor, 'personnel.manage')
        _shape(data, ('effective_from', 'timezone', 'daily_target_minutes', 'auto_pause_after_minutes', 'auto_pause_minutes',
                      'second_after_minutes', 'second_pause_minutes', 'location_enabled', 'reminder_time'))
        fp, previous = self._receipt(actor, 'rule', data)
        if previous is not None:
            return previous
        old = self.db.execute('SELECT * FROM business_time_rules ORDER BY revision DESC LIMIT 1').fetchone()
        if data.get('id') and (not old or data['id'] != old['id'] or data.get('revision') != old['revision']):
            raise Problem(409, 'Betriebsregel wurde inzwischen geändert.')
        value = dict(old or self._rule(self.now()[:10]))
        value.update({k: v for k, v in data.items() if k not in ('id', 'revision', 'request_id')})
        value['effective_from'] = _date(data.get('effective_from', self.now()[:10])).isoformat()
        _zone(value['timezone'])
        for name in ('auto_pause_after_minutes', 'auto_pause_minutes', 'second_after_minutes', 'second_pause_minutes'):
            _integer(value[name], 0, 1440)
        if value['daily_target_minutes'] is not None:
            _integer(value['daily_target_minutes'], 0, 1440)
        if type(value['location_enabled']) not in (bool, int) or value['location_enabled'] not in (0, 1):
            raise Problem(400, 'Standortfreigabe muss ein Wahrheitswert sein.')
        value['location_enabled'] = int(value['location_enabled'])
        if value['reminder_time'] is not None and (not isinstance(value['reminder_time'], str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', value['reminder_time'])):
            raise Problem(400, 'Erinnerungszeit HH:MM erwartet.')
        if value['second_after_minutes'] and value['second_after_minutes'] <= value['auto_pause_after_minutes']:
            raise Problem(400, 'Zweite Pausenschwelle muss nach der ersten liegen.')
        value.update(id=uuid.uuid4().hex, revision=(old['revision'] if old else 0) + 1, created_by=actor['id'], updated_at=self.now())
        keys = ('id', 'effective_from', 'revision', 'timezone', 'daily_target_minutes', 'auto_pause_after_minutes', 'auto_pause_minutes',
                'second_after_minutes', 'second_pause_minutes', 'location_enabled', 'reminder_time', 'created_by', 'updated_at')
        self.db.execute('INSERT INTO business_time_rules(' + ','.join(keys) + ') VALUES(' + ','.join('?' for _ in keys) + ')', tuple(value[k] for k in keys))
        self.db.execute("UPDATE business_time_days SET revision=revision+1 WHERE work_date>=? AND status='draft'", (value['effective_from'],))
        value['location_enabled'] = bool(value['location_enabled'])
        self._remember(actor, 'rule', data, fp, value)
        self.office.audit(actor, 'time.rule.versioned', value['id'])
        return value

    @_atomic
    def categories(self, actor, query=None):
        _require(self.office, actor, 'time.own')
        return {'items': [dict(row, active=bool(row['active'])) for row in self.db.execute('SELECT * FROM business_time_categories ORDER BY name,id').fetchall()]}

    @_atomic
    def save_category(self, actor, data):
        actor = _require(self.office, actor, 'personnel.manage')
        _shape(data, ('name', 'supplement_percent', 'active'))
        fp, previous = self._receipt(actor, 'category', data)
        if previous is not None:
            return previous
        old = self.db.execute('SELECT * FROM business_time_categories WHERE id=?', (_id(data['id']),)).fetchone() if data.get('id') else None
        if data.get('id') and (not old or old['revision'] != data.get('revision')):
            raise Problem(409, 'Zeitkategorie wurde inzwischen geändert.')
        value = dict(old or {'id': uuid.uuid4().hex, 'supplement_percent': '0', 'active': True})
        value.update({k: v for k, v in data.items() if k in ('name', 'supplement_percent', 'active')})
        value['name'], value['supplement_percent'] = _text(value.get('name')), _percent(value['supplement_percent'])
        if type(value['active']) not in (bool, int) or value['active'] not in (0, 1):
            raise Problem(400, 'Aktivstatus muss ein Wahrheitswert sein.')
        value['active'] = int(value['active'])
        value.update(revision=(old['revision'] if old else 0) + 1, updated_at=self.now())
        keys = ('id', 'name', 'supplement_percent', 'active', 'revision', 'updated_at')
        self.db.execute('INSERT INTO business_time_categories(' + ','.join(keys) + ') VALUES(?,?,?,?,?,?) '
            'ON CONFLICT(id) DO UPDATE SET name=excluded.name,supplement_percent=excluded.supplement_percent,active=excluded.active,revision=excluded.revision,updated_at=excluded.updated_at', tuple(value[k] for k in keys))
        value['active'] = bool(value['active'])
        self._remember(actor, 'category', data, fp, value)
        return value

    def _touch(self, employee, day):
        row = self.db.execute('SELECT status FROM business_time_days WHERE employee_id=? AND work_date=?', (employee, day)).fetchone()
        if row and row['status'] == 'approved':
            raise Problem(409, 'Dieser Arbeitstag ist freigegeben; eine nachvollziehbare Korrektur ist erforderlich.')
        self.db.execute("INSERT INTO business_time_days(employee_id,work_date,revision,status) VALUES(?,?,1,'draft') "
                        'ON CONFLICT(employee_id,work_date) DO UPDATE SET revision=business_time_days.revision+1', (employee, day))

    def _split(self, start, end, zone):
        cursor = start
        while cursor < end:
            day = cursor.astimezone(zone).date()
            boundary = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(timezone.utc)
            stop = min(end, boundary)
            yield day.isoformat(), int((stop - cursor).total_seconds())
            cursor = stop

    def _segments(self, entry):
        events = self.db.execute('SELECT action,occurred_at FROM business_time_events WHERE entry_id=? ORDER BY sequence', (entry['id'],)).fetchall()
        result = {}
        for first, second in zip(events, events[1:]):
            key = 'break_seconds' if first['action'] == 'pause' else 'worked_seconds'
            for day, seconds in self._split(_instant(first['occurred_at']), _instant(second['occurred_at']), _zone(entry['timezone'])):
                value = result.setdefault(day, {'worked_seconds': 0, 'break_seconds': 0})
                value[key] += seconds
        return result

    def _entry(self, actor, row):
        result = {key: row[key] for key in ('id', 'employee_id', 'project_id', 'category_id', 'status', 'started_at', 'ended_at',
                                           'last_at', 'timezone', 'revision', 'last_sequence', 'updated_at')}
        result.update(start_at=result['started_at'], sequence=result['last_sequence'])
        result['events'] = [dict(e) for e in self.db.execute('SELECT id,action,occurred_at,received_at,device_id,sequence FROM business_time_events WHERE entry_id=? ORDER BY sequence', (row['id'],)).fetchall()]
        segments = self._segments(row)
        result['worked_seconds'] = sum(item['worked_seconds'] for item in segments.values())
        result['break_seconds'] = sum(item['break_seconds'] for item in segments.values())
        result['corrections'] = [dict(r) for r in self.db.execute('SELECT id,work_date,delta_seconds,reason,created_by,created_at FROM business_time_corrections WHERE entry_id=? ORDER BY created_at,id', (row['id'],)).fetchall()]
        if row['status'] == 'stopped' and segments:
            approved = sum(bool(self.db.execute("SELECT 1 FROM business_time_days WHERE employee_id=? AND work_date=? AND status='approved'", (row['employee_id'], day)).fetchone()) for day in segments)
            if approved:
                result['status'] = 'approved' if approved == len(segments) else 'partially_approved'
        if _has(self.office, actor, 'personnel.read', row['project_id']):
            result.update(hourly_cost_minor=row['hourly_cost_minor'], supplement_percent=row['supplement_percent'])
        return result

    @_atomic
    def event(self, actor, data):
        _shape(data, ('entry_id', 'event_id', 'employee_id', 'device_id', 'sequence', 'project_id', 'action', 'occurred_at', 'category_id', 'position'))
        actor, employee = self._employee(actor, data.get('employee_id'), write=True)
        actor = self._project_access(actor, employee, _id(data.get('project_id')), write=True)
        user = self.db.execute('SELECT id,email,role FROM users WHERE id=?', (employee['user_id'],)).fetchone()
        self.office.project(dict(user), data['project_id'])
        identifier, request = _id(data.get('entry_id')), _id(data.get('request_id'))
        if data.get('event_id', request) != request:
            raise Problem(400, 'Ereignis-ID muss der stabilen Anfrage-ID entsprechen.')
        device, sequence, revision = _text(data.get('device_id'), 128), _integer(data.get('sequence'), 1, 10**9), _integer(data.get('revision'), 0, 10**9)
        if not device.isprintable() or any(c.isspace() for c in device):
            raise Problem(400, 'Stabile Gerätekennung ohne Leer- oder Steuerzeichen erwartet.')
        action, occurred = data.get('action'), _instant(data.get('occurred_at'))
        if action not in ('start', 'pause', 'resume', 'stop'):
            raise Problem(400, 'Start, Pause, Fortsetzen oder Stopp erwartet.')
        if occurred > self.clock().astimezone(timezone.utc) + timedelta(minutes=5) or occurred < self.clock().astimezone(timezone.utc) - timedelta(days=366):
            raise Problem(400, 'Zeitereignis liegt außerhalb des zulässigen Erfassungszeitraums.')
        old = self.db.execute('SELECT * FROM business_time_entries WHERE id=?', (identifier,)).fetchone()
        category = data.get('category_id') if action == 'start' else old['category_id'] if old else None
        if old and (old['employee_id'] != employee['id'] or old['project_id'] != data['project_id']):
            raise Problem(409, 'Zeitereignis gehört nicht zu diesem Mitarbeiter und Projekt.')
        core = dict(entry_id=identifier, employee_id=employee['id'], project_id=data['project_id'], category_id=category,
                    action=action, occurred_at=occurred.isoformat(), device_id=device, sequence=sequence, revision=revision)
        fingerprint = digest(canonical(core))
        location = _position(data['position']) if data.get('position') is not None else None
        if location and action not in ('start', 'stop'):
            raise Problem(400, 'Standort ist ausschließlich bei Start oder Stopp zulässig.')
        receipt = self.db.execute('SELECT * FROM business_time_events WHERE request_id=?', (request,)).fetchone()
        if receipt:
            if receipt['user_id'] != actor['id'] or receipt['request_hash'] != fingerprint:
                raise Problem(409, 'Diese Zeitoperation wurde bereits mit anderem Inhalt verarbeitet.')
            if not receipt['location_redacted_at'] and receipt['location_hash'] != (digest(canonical(location)) if location else None):
                raise Problem(409, 'Diese Zeitoperation enthielt eine andere Standortangabe.')
            return {'entry': self._entry(actor, old), 'event_id': receipt['id'], 'request_id': request, 'idempotent': True}
        local_day = occurred.astimezone(_zone(old['timezone'] if old else self._rule(occurred.date().isoformat())['timezone'])).date().isoformat()
        rule = self._rule(local_day)
        if location and not rule['location_enabled']:
            raise Problem(403, 'Standort ist für den Betrieb nicht freigeschaltet.')
        if self.db.execute('SELECT 1 FROM business_time_privacy WHERE employee_id=? AND work_date=?', (employee['id'], local_day)).fetchone():
            raise Problem(409, 'Dieser Arbeitstag wurde bereits freigegeben und seine Standortdaten gelöscht.')
        if action == 'start':
            if old or revision != 0 or sequence != 1 or self.db.execute('SELECT 1 FROM business_time_active WHERE employee_id=?', (employee['id'],)).fetchone():
                raise Problem(409, 'Für diesen Mitarbeiter läuft bereits eine Erfassung oder die Ausgangsversion ist veraltet.')
            if self.db.execute("SELECT 1 FROM business_time_entries WHERE employee_id=? AND (ended_at IS NULL OR ended_at>?) AND started_at<=?", (employee['id'], occurred.isoformat(), occurred.isoformat())).fetchone():
                raise Problem(409, 'Die Erfassung überschneidet eine bestehende Zeit.')
            category_row = self.db.execute('SELECT * FROM business_time_categories WHERE id=? AND active=1', (_id(category),)).fetchone() if category else None
            if category and not category_row:
                raise Problem(400, 'Aktive Zeitkategorie erwartet.')
            terms = self.db.execute('SELECT * FROM business_employee_terms WHERE employee_id=? AND effective_from<=? ORDER BY effective_from DESC,revision DESC LIMIT 1', (employee['id'], local_day)).fetchone()
            row = dict(id=identifier, employee_id=employee['id'], project_id=data['project_id'], category_id=category, status='working',
                       started_at=occurred.isoformat(), ended_at=None, last_at=occurred.isoformat(), timezone=rule['timezone'], device_id=device,
                       revision=1, last_sequence=1, hourly_cost_minor=terms['hourly_cost_minor'] if terms else employee['hourly_cost_minor'],
                       supplement_percent=category_row['supplement_percent'] if category_row else '0', updated_at=self.now())
            keys = tuple(row)
            self.db.execute('INSERT INTO business_time_entries(' + ','.join(keys) + ') VALUES(' + ','.join('?' for _ in keys) + ')', tuple(row.values()))
            self.db.execute('INSERT INTO business_time_active(employee_id,entry_id) VALUES(?,?)', (employee['id'], identifier))
        else:
            if not old or revision != old['revision'] or sequence != old['last_sequence'] + 1:
                raise Problem(409, 'Zeitstand wurde inzwischen geändert. Bitte den Konflikt vergleichen.')
            if old['status'] not in (('working',) if action == 'pause' else ('paused',) if action == 'resume' else ('working', 'paused')):
                raise Problem(409, 'Diese Aktion passt nicht zum aktuellen Stempelstatus.')
            if occurred <= _instant(old['last_at']) or occurred - _instant(old['started_at']) > timedelta(hours=72):
                raise Problem(409, 'Zeitereignisse müssen aufsteigend sein und der Einsatz darf höchstens 72 Stunden dauern.')
            if self.db.execute('SELECT 1 FROM business_time_entries WHERE employee_id=? AND id<>? AND started_at<? AND (ended_at IS NULL OR ended_at>?)',
                               (employee['id'], identifier, occurred.isoformat(), old['started_at'])).fetchone():
                raise Problem(409, 'Der Zeitraum überschneidet eine andere Erfassung.')
            row = dict(old, status='paused' if action == 'pause' else 'working' if action == 'resume' else 'stopped',
                       last_at=occurred.isoformat(), ended_at=occurred.isoformat() if action == 'stop' else None,
                       revision=revision + 1, last_sequence=sequence, updated_at=self.now())
            self.db.execute('UPDATE business_time_entries SET status=?,last_at=?,ended_at=?,revision=?,last_sequence=?,updated_at=? WHERE id=?',
                            tuple(row[k] for k in ('status', 'last_at', 'ended_at', 'revision', 'last_sequence', 'updated_at', 'id')))
            if action == 'stop':
                self.db.execute('DELETE FROM business_time_active WHERE employee_id=?', (employee['id'],))
        event_id = request
        self.db.execute('INSERT INTO business_time_events(id,user_id,request_id,entry_id,action,occurred_at,received_at,device_id,sequence,expected_revision,request_hash,location_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                        (event_id, actor['id'], request, identifier, action, occurred.isoformat(), self.now(), device, sequence, revision, fingerprint,
                         digest(canonical(location)) if location else None))
        if location:
            self.db.execute('INSERT INTO business_time_locations(event_id,employee_id,work_date,latitude,longitude,accuracy) VALUES(?,?,?,?,?,?)',
                            (event_id, employee['id'], local_day, location['latitude'], location['longitude'], location.get('accuracy')))
        days = {local_day}
        if action == 'stop':
            for day, segment in self._segments(row).items():
                days.add(day)
                self.db.execute('INSERT INTO business_time_segments(entry_id,work_date,worked_seconds,break_seconds) VALUES(?,?,?,?)',
                                (identifier, day, segment['worked_seconds'], segment['break_seconds']))
        for day in days:
            self._touch(employee['id'], day)
        self.office.audit(actor, 'time.event.' + action, event_id)
        return {'entry': self._entry(actor, row), 'event_id': event_id, 'request_id': request, 'idempotent': False}

    @_atomic
    def get_entry(self, actor, identifier):
        actor = _fresh(self.office, actor)
        row = self.db.execute('SELECT * FROM business_time_entries WHERE id=?', (_id(identifier),)).fetchone()
        if not row:
            raise Problem(404, 'Zeitbeleg nicht verfügbar.')
        actor, employee = self._employee(actor, row['employee_id'])
        self._project_access(actor, employee, row['project_id'])
        return self._entry(actor, row)

    @_atomic
    def entries(self, actor, query=None):
        query = query or {}
        actor, employee = self._employee(actor, query.get('employee_id'))
        if query.get('project_id'):
            self._project_access(actor, employee, _id(query['project_id']))
        result = []
        for row in self.db.execute('SELECT * FROM business_time_entries WHERE employee_id=? ORDER BY started_at,id', (employee['id'],)).fetchall():
            if query.get('project_id') and row['project_id'] != query['project_id']:
                continue
            try:
                self._project_access(actor, employee, row['project_id'])
            except Problem as error:
                if error.status in (403, 404):
                    continue
                raise
            local_day = _instant(row['started_at']).astimezone(_zone(row['timezone'])).date().isoformat()
            if query.get('from') and local_day < _date(query['from']).isoformat() or query.get('to') and local_day > _date(query['to']).isoformat():
                continue
            result.append(self._entry(actor, row))
        return {'items': result}

    def _day(self, employee, day):
        record = self.db.execute('SELECT * FROM business_time_days WHERE employee_id=? AND work_date=?', (employee['id'], day)).fetchone()
        if record and record['status'] == 'approved':
            correction = self.db.execute('SELECT COALESCE(SUM(c.delta_seconds),0) FROM business_time_corrections c JOIN business_time_entries e ON e.id=c.entry_id WHERE e.employee_id=? AND c.work_date=?', (employee['id'], day)).fetchone()[0]
            return dict(record, date=day, approved_net_seconds=record['net_seconds'], correction_seconds=correction,
                        net_seconds=record['net_seconds'] + correction)
        rows = self.db.execute('SELECT s.* FROM business_time_segments s JOIN business_time_entries e ON e.id=s.entry_id WHERE e.employee_id=? AND s.work_date=?', (employee['id'], day)).fetchall()
        worked, breaks = sum(r['worked_seconds'] for r in rows), sum(r['break_seconds'] for r in rows)
        rule = self._rule(day)
        required = 0
        for after, minutes in ((rule['auto_pause_after_minutes'], rule['auto_pause_minutes']), (rule['second_after_minutes'], rule['second_pause_minutes'])):
            if after and worked > after * 60:
                required = max(required, minutes * 60)
        automatic = min(worked, max(0, required - breaks))
        terms = self.db.execute('SELECT weekly_minutes FROM business_employee_terms WHERE employee_id=? AND effective_from<=? ORDER BY effective_from DESC,revision DESC LIMIT 1', (employee['id'], day)).fetchone()
        target_minutes = rule['daily_target_minutes'] if rule['daily_target_minutes'] is not None else (terms['weekly_minutes'] if terms else employee['weekly_minutes']) // 5
        target = target_minutes * 60 if _date(day).weekday() < 5 else 0
        if employee['employment_from'] and day < employee['employment_from'] or employee['employment_to'] and day > employee['employment_to']:
            target = 0
        absence = self.db.execute("SELECT 1 FROM business_absences WHERE employee_id=? AND status='approved' AND start_date<=? AND end_date>=?", (employee['id'], day, day)).fetchone()
        credit = max(0, target - (worked - automatic)) if absence else 0
        return dict(employee_id=employee['id'], date=day, work_date=day, revision=record['revision'] if record else 0,
                    status='draft', worked_seconds=worked, break_seconds=breaks, auto_pause_seconds=automatic,
                    net_seconds=worked - automatic, target_seconds=target, absence_seconds=credit, rule_id=rule['id'], correction_seconds=0)

    @_atomic
    def summary(self, actor, query=None):
        query = query or {}
        actor, employee = self._employee(actor, query.get('employee_id'))
        first = _date(query.get('from', self.now()[:10]))
        last = _date(query.get('to', first.isoformat()))
        if last < first or (last - first).days > 5 * 366:
            raise Problem(400, 'Auswertungsbereich von höchstens fünf Jahren erwartet.')
        days = [self._day(employee, (first + timedelta(days=n)).isoformat()) for n in range((last - first).days + 1)]
        keys = ('worked_seconds', 'break_seconds', 'auto_pause_seconds', 'net_seconds', 'target_seconds', 'absence_seconds', 'correction_seconds')
        result = dict(employee_id=employee['id'], days=days, **{key: sum(day[key] for day in days) for key in keys})
        adjustments = self.db.execute('SELECT COALESCE(SUM(seconds),0) AS seconds FROM business_time_adjustments WHERE employee_id=? AND effective_date>=? AND effective_date<=?',
                                     (employee['id'], first.isoformat(), last.isoformat())).fetchone()[0]
        result.update(adjustment_seconds=adjustments, balance_seconds=result['net_seconds'] + result['absence_seconds'] + adjustments - result['target_seconds'])
        return result

    @_atomic
    def approve_day(self, actor, day, data):
        actor = _require(self.office, actor, 'time.approve')
        day = _date(day).isoformat()
        _shape(data, ('employee_id',))
        employee = self.planning.employee(data.get('employee_id'))
        operation = 'approve:' + employee['id'] + ':' + day
        fp, previous = self._receipt(actor, operation, data)
        if previous is not None:
            return previous
        current = self._day(employee, day)
        if current['revision'] != data.get('revision') or current['status'] == 'approved' or current['revision'] == 0:
            raise Problem(409, 'Arbeitstag wurde inzwischen geändert oder noch nicht erfasst.')
        zone = _zone(self._rule(day)['timezone'])
        end = datetime.combine(_date(day) + timedelta(days=1), time.min, zone).astimezone(timezone.utc).isoformat()
        if self.db.execute("SELECT 1 FROM business_time_entries WHERE employee_id=? AND status<>'stopped' AND started_at<?", (employee['id'], end)).fetchone():
            raise Problem(409, 'Vor der Tagesfreigabe laufende Erfassungen beenden.')
        locations = self.db.execute('SELECT 1 FROM business_time_locations WHERE employee_id=? AND work_date=?', (employee['id'], day)).fetchone()
        generation = 0
        if locations:
            from business_schema import checkpoint_before_location_purge
            checkpoint = checkpoint_before_location_purge(self.office, employee['id'], day, data['request_id'])
            generation = checkpoint['generation']
        self._purge_locations(employee['id'], day, generation)
        result = dict(current, status='approved', revision=current['revision'] + 1, approved_by=actor['id'], approved_at=self.now())
        keys = ('status', 'revision', 'worked_seconds', 'break_seconds', 'auto_pause_seconds', 'net_seconds', 'target_seconds', 'absence_seconds', 'rule_id', 'approved_by', 'approved_at')
        self.db.execute('UPDATE business_time_days SET ' + ','.join(k + '=?' for k in keys) + ' WHERE employee_id=? AND work_date=?',
                        tuple(result[k] for k in keys) + (employee['id'], day))
        self._remember(actor, operation, data, fp, result)
        self.office.audit(actor, 'time.day.approved', employee['id'] + ':' + day)
        return result

    def _purge_locations(self, employee_id, day, generation):
        events = self.db.execute('SELECT v.id,v.occurred_at,e.timezone FROM business_time_events v JOIN business_time_entries e ON e.id=v.entry_id WHERE e.employee_id=?', (employee_id,)).fetchall()
        for event in events:
            if _instant(event['occurred_at']).astimezone(_zone(event['timezone'])).date().isoformat() == day:
                self.db.execute('UPDATE business_time_events SET location_hash=NULL,location_redacted_at=? WHERE id=?', (self.now(), event['id']))
        self.db.execute('DELETE FROM business_time_locations WHERE employee_id=? AND work_date=?', (employee_id, day))
        self.db.execute('INSERT INTO business_time_privacy(employee_id,work_date,checkpoint_generation,redacted_at) VALUES(?,?,?,?) '
                        'ON CONFLICT(employee_id,work_date) DO UPDATE SET checkpoint_generation=excluded.checkpoint_generation,redacted_at=excluded.redacted_at',
                        (employee_id, day, generation, self.now()))

    @_atomic
    def privacy_deletions(self, actor, query=None):
        actor, employee = self._employee(actor, (query or {}).get('employee_id'))
        rows = self.db.execute('SELECT v.id,v.request_id,v.location_redacted_at FROM business_time_events v JOIN business_time_entries e ON e.id=v.entry_id '
                               'WHERE e.employee_id=? AND v.location_redacted_at IS NOT NULL ORDER BY v.location_redacted_at,v.id', (employee['id'],)).fetchall()
        return {'items': [dict(row) for row in rows]}

    @_atomic
    def export_csv(self, actor, query=None):
        actor = _require(self.office, actor, 'personnel.read')
        summary = self.summary(actor, query)
        output = io.StringIO(newline='')
        writer = csv.writer(output, delimiter=';', lineterminator='\r\n')
        writer.writerow(['Datum', 'Mitarbeiter-ID', 'Netto-Stunden', 'Pausen-Minuten', 'Soll-Stunden', 'Freigabe', 'Korrektur-Sekunden'])
        for day in summary['days']:
            if day['status'] == 'approved':
                writer.writerow([day['date'], summary['employee_id'], format(Decimal(day['net_seconds']) / Decimal(3600), '.2f').replace('.', ','),
                                 str((day['break_seconds'] + day['auto_pause_seconds']) // 60),
                                 format(Decimal(day['target_seconds']) / Decimal(3600), '.2f').replace('.', ','), 'Freigegeben', day['correction_seconds']])
        self.office.audit(actor, 'time.payroll_preparation.exported', summary['employee_id'])
        return {'filename': 'stundenliste.csv', 'media_type': 'text/csv', 'content': output.getvalue()}

    def _approved_rows(self, project_id):
        result = []
        rows = self.db.execute('SELECT e.id,e.employee_id,e.project_id,e.hourly_cost_minor,e.supplement_percent,s.work_date,s.worked_seconds,d.net_seconds,d.worked_seconds AS day_worked '
            'FROM business_time_entries e JOIN business_time_segments s ON e.id=s.entry_id JOIN business_time_days d '
            "ON d.employee_id=e.employee_id AND d.work_date=s.work_date WHERE d.status='approved' ORDER BY e.employee_id,s.work_date,e.id").fetchall()
        groups = {}
        for row in rows:
            groups.setdefault((row['employee_id'], row['work_date']), []).append(row)
        for values in groups.values():
            allocations = [int(Decimal(r['worked_seconds']) * Decimal(r['net_seconds']) / Decimal(r['day_worked'])) if r['day_worked'] else 0 for r in values]
            remainder = values[0]['net_seconds'] - sum(allocations)
            for index in range(remainder):
                allocations[index % len(allocations)] += 1
            for row, net in zip(values, allocations):
                if row['project_id'] == project_id:
                    correction = self.db.execute('SELECT COALESCE(SUM(delta_seconds),0) FROM business_time_corrections WHERE entry_id=? AND work_date=?', (row['id'], row['work_date'])).fetchone()[0]
                    result.append(dict(row, allocated_net_seconds=net + correction, correction_seconds=correction))
        return result

    @_atomic
    def approved_work(self, actor, project_id):
        actor = _require(self.office, actor, 'documents.read', project_id)
        self.office.project(actor, _id(project_id))
        result = [{'entry_id': row['id'], 'work_date': row['work_date'], 'net_seconds': row['allocated_net_seconds']}
                  for row in self._approved_rows(project_id)]
        return {'items': result, 'total_net_seconds': sum(row['net_seconds'] for row in result)}

    @_atomic
    def approved_billable(self, actor, project_id, entry_ids):
        actor = _require(self.office, actor, 'finance.read', project_id)
        self.office.project(actor, _id(project_id))
        if not isinstance(entry_ids, list) or not 1 <= len(entry_ids) <= 100:
            raise Problem(400, 'Ein bis hundert freigegebene Zeitbelege auswählen.')
        entry_ids = [_id(value) for value in entry_ids]
        if len(set(entry_ids)) != len(entry_ids):
            raise Problem(400, 'Zeitbelege dürfen nicht doppelt ausgewählt werden.')
        allocated = self._approved_rows(project_id)
        result = []
        for identifier in entry_ids:
            entry = self.db.execute('SELECT * FROM business_time_entries WHERE id=? AND project_id=?', (identifier, project_id)).fetchone()
            if not entry or entry['status'] != 'stopped':
                raise Problem(409, 'Zeitquelle ist nicht abgeschlossen oder gehört nicht zum Projekt.')
            segments = self.db.execute('SELECT * FROM business_time_segments WHERE entry_id=? ORDER BY work_date', (identifier,)).fetchall()
            approvals, values = [], []
            for segment in segments:
                approval = self.db.execute("SELECT revision,approved_at,rule_id FROM business_time_days WHERE employee_id=? AND work_date=? AND status='approved'",
                                           (entry['employee_id'], segment['work_date'])).fetchone()
                if not approval:
                    raise Problem(409, 'Alle Tage des Zeitbelegs müssen vor der Übernahme freigegeben sein.')
                source = next(row for row in allocated if row['id'] == identifier and row['work_date'] == segment['work_date'])
                values.append({'work_date': segment['work_date'], 'net_seconds': source['allocated_net_seconds']})
                approvals.append(dict(approval, work_date=segment['work_date']))
            if not values:
                raise Problem(409, 'Zeitquelle enthält keine freigegebene Dauer.')
            corrections = [dict(row) for row in self.db.execute('SELECT id,work_date,delta_seconds,created_at FROM business_time_corrections WHERE entry_id=? ORDER BY work_date,created_at,id', (identifier,)).fetchall()]
            snapshot = {'entry_id': identifier, 'revision': entry['revision'], 'project_id': project_id,
                        'started_at': entry['started_at'], 'ended_at': entry['ended_at'], 'segments': values,
                        'approvals': approvals, 'corrections': corrections}
            result.append({'entry_id': identifier, 'revision': entry['revision'], 'source_hash': digest(canonical(snapshot)),
                           'net_seconds': sum(value['net_seconds'] for value in values), 'segments': values,
                           'label': 'Freigegebene Projektzeit', 'date': values[0]['work_date']})
        return {'items': result}

    @_atomic
    def approved_costs(self, actor, project_id):
        actor = _require(self.office, actor, 'finance.read', project_id)
        self.office.project(actor, _id(project_id))
        result = []
        for row in self._approved_rows(project_id):
            net = row['allocated_net_seconds']
            value = Decimal(net) * Decimal(row['hourly_cost_minor']) * (Decimal(1) + Decimal(row['supplement_percent']) / Decimal(100)) / Decimal(3600)
            cost = int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))
            result.append({'entry_id': row['id'], 'work_date': row['work_date'], 'net_seconds': net,
                           'hourly_cost_minor': row['hourly_cost_minor'], 'supplement_percent': row['supplement_percent'],
                           'cost_minor': cost, 'cost_state': 'confirmed_rate' if row['hourly_cost_minor'] > 0 else 'missing_rate'})
        missing = sum(item['cost_state'] == 'missing_rate' for item in result)
        return {'items': result, 'total_cost_minor': sum(item['cost_minor'] for item in result), 'currency': 'EUR',
                'complete': missing == 0, 'missing_rates_count': missing}

    @_atomic
    def adjust_account(self, actor, data):
        actor = _require(self.office, actor, 'personnel.manage')
        _shape(data, ('employee_id', 'effective_date', 'seconds', 'reason'))
        employee = self.planning.employee(data.get('employee_id'))
        fp, previous = self._receipt(actor, 'account-adjustment', data)
        if previous is not None:
            return previous
        seconds = data.get('seconds')
        if type(seconds) is not int or abs(seconds) > 366 * 86400:
            raise Problem(400, 'Begrenzte Kontokorrektur in Sekunden erwartet.')
        value = dict(id=uuid.uuid4().hex, employee_id=employee['id'], effective_date=_date(data.get('effective_date')).isoformat(),
                     seconds=seconds, reason=_text(data.get('reason'), 2000), created_by=actor['id'], created_at=self.now())
        keys = tuple(value)
        self.db.execute('INSERT INTO business_time_adjustments(' + ','.join(keys) + ') VALUES(' + ','.join('?' for _ in keys) + ')', tuple(value.values()))
        self._remember(actor, 'account-adjustment', data, fp, value)
        self.office.audit(actor, 'time.account.adjusted', value['id'])
        return value

    @_atomic
    def correct_entry(self, actor, identifier, data):
        actor = _require(self.office, actor, 'time.approve')
        _shape(data, ('work_date', 'delta_seconds', 'reason'))
        row = self.db.execute('SELECT * FROM business_time_entries WHERE id=?', (_id(identifier),)).fetchone()
        if not row:
            raise Problem(404, 'Zeitbeleg nicht verfügbar.')
        self.office.project(actor, row['project_id'])
        day = _date(data.get('work_date')).isoformat()
        fp, previous = self._receipt(actor, 'correction:' + identifier, data)
        if previous is not None:
            return previous
        approved = self.db.execute("SELECT 1 FROM business_time_days WHERE employee_id=? AND work_date=? AND status='approved'", (row['employee_id'], day)).fetchone()
        delta = data.get('delta_seconds')
        if row['status'] != 'stopped' or not approved or type(delta) is not int or not 0 < abs(delta) <= 86400:
            raise Problem(409, 'Nur freigegebene Einzelzeiten mit begründeter begrenzter Korrektur ändern.')
        source = next((r for r in self._approved_rows(row['project_id']) if r['id'] == identifier and r['work_date'] == day), None)
        if not source or source['allocated_net_seconds'] + delta < 0:
            raise Problem(409, 'Korrektur darf die freigegebene Einzelzeit nicht negativ machen.')
        result = dict(id=uuid.uuid4().hex, entry_id=identifier, work_date=day, delta_seconds=delta,
                      reason=_text(data.get('reason'), 2000), created_by=actor['id'], created_at=self.now())
        keys = tuple(result)
        self.db.execute('INSERT INTO business_time_corrections(' + ','.join(keys) + ') VALUES(' + ','.join('?' for _ in keys) + ')', tuple(result.values()))
        self._remember(actor, 'correction:' + identifier, data, fp, result)
        self.office.audit(actor, 'time.entry.corrected', result['id'])
        return result


def reapply_privacy_checkpoint(office, event):
    from business_schema import privacy_subject_hash
    if event.get('operation') != 'purge_time_locations':
        return False
    service = TimeTracking(office)
    groups = office.db.execute('SELECT DISTINCT employee_id,work_date FROM business_time_locations').fetchall()
    matched = False
    for row in groups:
        subject = privacy_subject_hash('time_day', row['employee_id'] + ':' + row['work_date'])
        if subject == event.get('subject_hash'):
            service._purge_locations(row['employee_id'], row['work_date'], event['generation'])
            matched = True
    return matched


def validate_integrity(office):
    service = TimeTracking(office)
    try:
        for row in office.db.execute('SELECT * FROM business_time_categories').fetchall():
            _id(row['id']); _text(row['name']); _percent(row['supplement_percent']); _integer(row['revision'], 1)
            if row['active'] not in (0, 1):
                raise ValueError('Invalid time category')
        for index, row in enumerate(office.db.execute('SELECT * FROM business_time_rules ORDER BY revision').fetchall()):
            _id(row['id']); _date(row['effective_from']); _zone(row['timezone'])
            if row['revision'] != index + 1 or row['location_enabled'] not in (0, 1):
                raise ValueError('Invalid versioned time rule')
            for key in ('auto_pause_after_minutes', 'auto_pause_minutes', 'second_after_minutes', 'second_pause_minutes'):
                _integer(row[key], 0, 1440)
        for entry in office.db.execute('SELECT * FROM business_time_entries').fetchall():
            _id(entry['id']); _id(entry['employee_id']); _id(entry['project_id']); _integer(entry['revision'], 1)
            _integer(entry['hourly_cost_minor'], 0); _percent(entry['supplement_percent']); _zone(entry['timezone'])
            events = office.db.execute('SELECT * FROM business_time_events WHERE entry_id=? ORDER BY sequence', (entry['id'],)).fetchall()
            state, previous = None, None
            for index, event in enumerate(events):
                if event['sequence'] != index + 1 or event['expected_revision'] != index or previous and event['occurred_at'] <= previous:
                    raise ValueError('Invalid attendance event sequence')
                action = event['action']
                if action == 'start' and state is None:
                    state = 'working'
                elif action == 'pause' and state == 'working':
                    state = 'paused'
                elif action == 'resume' and state == 'paused':
                    state = 'working'
                elif action == 'stop' and state in ('working', 'paused'):
                    state = 'stopped'
                else:
                    raise ValueError('Invalid attendance transition')
                if not re.fullmatch(r'[a-f0-9]{64}', event['request_hash']):
                    raise ValueError('Invalid attendance operation hash')
                core = dict(entry_id=entry['id'], employee_id=entry['employee_id'], project_id=entry['project_id'], category_id=entry['category_id'],
                            action=action, occurred_at=_instant(event['occurred_at']).isoformat(), device_id=event['device_id'],
                            sequence=event['sequence'], revision=event['expected_revision'])
                if digest(canonical(core)) != event['request_hash']:
                    raise ValueError('Attendance event hash differs from its immutable fields')
                position = office.db.execute('SELECT * FROM business_time_locations WHERE event_id=?', (event['id'],)).fetchone()
                if position:
                    value = {k: position[k] for k in ('latitude', 'longitude', 'accuracy') if position[k] is not None}
                    if (action not in ('start', 'stop') or event['location_redacted_at'] or digest(canonical(_position(value))) != event['location_hash']
                            or position['employee_id'] != entry['employee_id'] or position['work_date'] != _instant(event['occurred_at']).astimezone(_zone(entry['timezone'])).date().isoformat()):
                        raise ValueError('Invalid attendance position')
                elif event['location_hash']:
                    raise ValueError('Missing attendance position')
                previous = event['occurred_at']
            if (not events or entry['revision'] != len(events) or entry['last_sequence'] != len(events) or state != entry['status'] or entry['last_at'] != previous
                    or entry['started_at'] != events[0]['occurred_at'] or (entry['ended_at'] != previous if state == 'stopped' else entry['ended_at'] is not None)):
                raise ValueError('Attendance entry differs from its events')
            active = office.db.execute('SELECT entry_id FROM business_time_active WHERE employee_id=?', (entry['employee_id'],)).fetchone()
            if (state != 'stopped') != bool(active and active['entry_id'] == entry['id']):
                raise ValueError('Attendance active cursor mismatch')
            if state == 'stopped':
                stored = {r['work_date']: {'worked_seconds': r['worked_seconds'], 'break_seconds': r['break_seconds']} for r in office.db.execute('SELECT * FROM business_time_segments WHERE entry_id=?', (entry['id'],)).fetchall()}
                if stored != service._segments(entry):
                    raise ValueError('Attendance day segments mismatch')
        for row in office.db.execute('SELECT * FROM business_time_days').fetchall():
            _date(row['work_date']); _integer(row['revision'], 1)
            if row['status'] == 'approved':
                for key in ('worked_seconds', 'break_seconds', 'auto_pause_seconds', 'net_seconds', 'target_seconds', 'absence_seconds'):
                    _integer(row[key], 0)
                if row['net_seconds'] != row['worked_seconds'] - row['auto_pause_seconds'] or not row['approved_by'] or not row['approved_at']:
                    raise ValueError('Invalid approved attendance day')
                totals = office.db.execute('SELECT COALESCE(SUM(s.worked_seconds),0) AS worked_seconds,COALESCE(SUM(s.break_seconds),0) AS break_seconds FROM business_time_segments s JOIN business_time_entries e ON e.id=s.entry_id WHERE e.employee_id=? AND s.work_date=?', (row['employee_id'], row['work_date'])).fetchone()
                if totals['worked_seconds'] != row['worked_seconds'] or totals['break_seconds'] != row['break_seconds']:
                    raise ValueError('Approved attendance differs from original events')
        for row in office.db.execute('SELECT * FROM business_time_privacy').fetchall():
            if office.db.execute('SELECT 1 FROM business_time_locations WHERE employee_id=? AND work_date=?', (row['employee_id'], row['work_date'])).fetchone():
                raise ValueError('Approved position reappeared')
        for row in office.db.execute('SELECT * FROM business_time_corrections').fetchall():
            _id(row['id']); _date(row['work_date']); _text(row['reason'], 2000)
            if type(row['delta_seconds']) is not int or not 0 < abs(row['delta_seconds']) <= 86400:
                raise ValueError('Invalid time correction')
            entry = office.db.execute('SELECT employee_id,project_id,status FROM business_time_entries WHERE id=?', (row['entry_id'],)).fetchone()
            if (not entry or entry['status'] != 'stopped' or not office.db.execute("SELECT 1 FROM business_time_days WHERE employee_id=? AND work_date=? AND status='approved'", (entry['employee_id'], row['work_date'])).fetchone()):
                raise ValueError('Time correction without approved source')
        for row in office.db.execute('SELECT * FROM business_time_requests').fetchall():
            _id(row['request_id'])
            if not re.fullmatch(r'[a-f0-9]{64}', row['request_hash']) or not isinstance(json.loads(row['result_json']), dict):
                raise ValueError('Invalid time receipt')
        projects = {r[0] for r in office.db.execute('SELECT DISTINCT e.project_id FROM business_time_corrections c JOIN business_time_entries e ON e.id=c.entry_id').fetchall()}
        for project in projects:
            if any(row['allocated_net_seconds'] < 0 for row in service._approved_rows(project)):
                raise ValueError('Time corrections produce negative duration')
    except (Problem, ValueError, TypeError, KeyError) as error:
        raise ValueError('Time integrity check failed') from error
    return True


def protected_tables():
    return ('business_time_requests', 'business_time_rules', 'business_time_adjustments', 'business_time_corrections')


def methods(path):
    if path in ('/time/events',):
        return 'POST'
    if path in ('/time/categories', '/time/rules', '/time/accounts'):
        return 'GET, POST'
    if path in ('/time/entries', '/time/export', '/time/privacy-deletions', '/time/summary') or re.fullmatch(r'/time/entries/[a-f0-9]{32}', path):
        return 'GET'
    if re.fullmatch(r'/time/days/\d{4}-\d{2}-\d{2}/approve', path):
        return 'POST'
    if re.fullmatch(r'/time/entries/[a-f0-9]{32}/correct', path):
        return 'POST'
    return None


def dispatch(office, actor, path, method, data):
    service, query = TimeTracking(office), data.get('_query', {})
    if path == '/time/events' and method == 'POST':
        return service.event(actor, data), 200, 'application/json'
    if path in ('/time/categories', '/time/rules'):
        kind = path.rsplit('/', 1)[1]
        result = getattr(service, kind)(actor, query) if method == 'GET' else getattr(service, 'save_' + ('category' if kind == 'categories' else 'rule'))(actor, data)
        return result, 200 if method == 'GET' else 201, 'application/json'
    if path == '/time/entries' and method == 'GET':
        return service.entries(actor, query), 200, 'application/json'
    match = re.fullmatch(r'/time/entries/([a-f0-9]{32})', path)
    if match and method == 'GET':
        return service.get_entry(actor, match[1]), 200, 'application/json'
    if path in ('/time/accounts', '/time/summary'):
        return (service.summary(actor, query) if method == 'GET' else service.adjust_account(actor, data)), 200, 'application/json'
    if path == '/time/export' and method == 'GET':
        result = service.export_csv(actor, query)
        return result['content'].encode('utf-8-sig'), 200, 'text/csv'
    if path == '/time/privacy-deletions' and method == 'GET':
        return service.privacy_deletions(actor, query), 200, 'application/json'
    match = re.fullmatch(r'/time/days/(\d{4}-\d{2}-\d{2})/approve', path)
    if match and method == 'POST':
        return service.approve_day(actor, match[1], data), 200, 'application/json'
    match = re.fullmatch(r'/time/entries/([a-f0-9]{32})/correct', path)
    if match and method == 'POST':
        return service.correct_entry(actor, match[1], data), 201, 'application/json'
    return None
