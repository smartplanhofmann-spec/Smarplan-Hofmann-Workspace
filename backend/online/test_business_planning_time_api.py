"""Real MFA/Flask/SQLite business planning and narrow offline attendance."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

from cryptography.fernet import Fernet

from business_schema import ensure_schema
from core import Office
from online.web import create_app
from test_business_planning import rid
from test_workspace_api import WorkspaceHttpFlow


class BusinessPlanningTimeApiTests(WorkspaceHttpFlow, unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='smartplan-business-calendar-http-')
        self.addCleanup(self.temporary.cleanup)
        self.office = Office(Path(self.temporary.name) / 'office.db')
        self.addCleanup(self.office.db.close)
        ensure_schema(self.office)
        self.key = Fernet.generate_key()
        self.owner_id = self.office.add_user('owner@example.test', 'Owner-password-123', 'owner')
        self.office.db.executescript('''
            CREATE TABLE IF NOT EXISTS mfa(user_id TEXT PRIMARY KEY REFERENCES users(id),secret TEXT NOT NULL,
                last_step BIGINT NOT NULL DEFAULT -1,recovery TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS auth_challenges(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),
                credential TEXT NOT NULL,secret TEXT NOT NULL,expiry DOUBLE PRECISION NOT NULL,failures INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS login_limits(key TEXT PRIMARY KEY,failures INTEGER NOT NULL,reset_at DOUBLE PRECISION NOT NULL);
        ''')
        self.app = create_app(office=self.office, key=self.key, host='office.example.test')
        self.client, self.secrets = self.app.test_client(), {}
        self.token = self.mfa_login()
        self.owner = self.office.user(self.token)
        self.project = self.call('POST', '/projects', {'name': 'Synthetic installation', 'customer': 'Synthetic customer'}, status=201).json['id']
        self.technician_id, self.technician = self.add_actor('technician')
        self.employee = self.call('POST', '/business/employees', {'request_id': rid(), 'user_id': self.technician_id,
            'name': 'Synthetic field technician', 'weekly_minutes': 2400, 'hourly_cost_minor': 3500}, status=201).json

    def test_project_move_and_resource_conflict_are_the_same_employee_calendar_over_http(self):
        tomorrow = datetime.now(timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
        body = {'request_id': rid(), 'project_id': self.project, 'title': 'Synthetic visit',
                'start_at': tomorrow.isoformat(), 'end_at': (tomorrow + timedelta(hours=1)).isoformat(),
                'employee_ids': [self.employee['id']], 'resource_ids': [], 'timezone': 'Europe/Berlin'}
        first = self.call('POST', '/business/appointments', body, status=201).json
        self.assertEqual(self.call('POST', '/business/appointments', body, status=201).json, first)
        self.call('POST', '/business/appointments', {**body, 'request_id': rid()}, status=409)
        moved = self.call('POST', '/business/appointments/' + first['id'], {
            **body, 'request_id': rid(), 'revision': first['revision'],
            'start_at': (tomorrow + timedelta(hours=2)).isoformat(), 'end_at': (tomorrow + timedelta(hours=3)).isoformat()}).json
        day = tomorrow.astimezone(ZoneInfo('Europe/Berlin')).date().isoformat()
        calendar = self.call('GET', '/business/planning/calendar?from=' + day + '&to=' + day + '&employee_id=' + self.employee['id'], token=self.technician).json
        self.assertEqual(calendar['appointments'][0]['id'], first['id'])
        self.assertEqual(calendar['appointments'][0]['start_at'], moved['start_at'])
        self.assertNotIn('hourly_cost_minor', str(calendar))
        self.call('POST', '/business/appointments/' + first['id'], {
            **body, 'request_id': rid(), 'revision': first['revision']}, status=409)

    def test_offline_grant_retries_own_stamps_then_owner_approves_and_exports_without_hr_leak(self):
        grant = self.call('POST', '/business/offline/access', {}, token=self.technician, status=201).json
        self.assertIn('time_events', grant['capabilities'])
        offline = grant['token']
        entry = rid()
        start_at = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=3)
        start = {'request_id': rid(), 'entry_id': entry, 'device_id': 'synthetic-offline-device', 'sequence': 1,
                 'revision': 0, 'project_id': self.project, 'action': 'start', 'occurred_at': start_at.isoformat()}
        first = self.call('POST', '/business/time/events', start, token=offline).json
        repeated = self.call('POST', '/business/time/events', start, token=offline).json
        self.assertEqual(first['event_id'], repeated['event_id'])
        self.assertTrue(repeated['idempotent'])
        stop = {**start, 'request_id': rid(), 'action': 'stop', 'sequence': 2, 'revision': 1,
                'occurred_at': (start_at + timedelta(hours=1)).isoformat()}
        self.call('POST', '/business/time/events', stop, token=offline)
        current = self.call('GET', '/business/time/entries/' + entry, token=offline).json
        self.assertEqual(current['worked_seconds'], 3600)
        self.assertNotIn('hourly_cost_minor', current)
        self.call('GET', '/business/time/entries', token=offline, status=403)
        self.call('GET', '/customers', token=offline, status=403)
        self.call('GET', '/inquiries', token=offline, status=403)
        day = start_at.astimezone(ZoneInfo('Europe/Berlin')).date().isoformat()
        query = '?employee_id=' + self.employee['id'] + '&from=' + day + '&to=' + day
        summary = self.call('GET', '/business/time/accounts' + query).json
        approved = self.call('POST', '/business/time/days/' + day + '/approve', {
            'request_id': rid(), 'employee_id': self.employee['id'], 'revision': summary['days'][0]['revision']}).json
        self.assertEqual(approved['status'], 'approved')
        exported = self.call('GET', '/business/time/export' + query)
        self.assertEqual(exported.mimetype, 'text/csv')
        self.assertIn('Freigegeben', exported.data.decode('utf-8-sig'))
        self.assertNotIn(b'latitude', exported.data)
        _, accountant = self.add_actor('accountant')
        self.call('GET', '/business/time/accounts' + query, token=accountant, status=403)
        self.call('POST', '/assignments', {'project_id': self.project, 'user_id': self.technician_id, 'remove': True})
        self.call('POST', '/business/time/events', stop, token=offline, status=404)


if __name__ == '__main__':
    unittest.main()
