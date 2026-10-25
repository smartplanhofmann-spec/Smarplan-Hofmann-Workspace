"""Optional disposable PostgreSQL attendance/booking races; no provider IO."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import threading
import unittest
from unittest.mock import patch

from psycopg.conninfo import conninfo_to_dict

from business_time import TimeTracking, validate_integrity
from core import Problem
from online.store import PostgresOffice
import test_business_planning as planning_fixture
import test_online as pg_fixture


if pg_fixture.DSN:
    config = conninfo_to_dict(pg_fixture.DSN)
    if config.get('dbname') != 'smartplan_check' or config.get('host') not in ('127.0.0.1', 'localhost'):
        raise RuntimeError('Only the disposable loopback smartplan_check database is permitted.')


@unittest.skipUnless(pg_fixture.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class PostgresPlanningAndTimeTests(planning_fixture.BusinessFixture, unittest.TestCase):
    def setUp(self):
        pg_fixture.reset()
        with patch.object(planning_fixture, 'Office', side_effect=lambda path: PostgresOffice(pg_fixture.DSN)):
            self.prepare()
        self.now = datetime(2026, 10, 26, 20, tzinfo=timezone.utc)
        self.time = TimeTracking(self.office, clock=lambda: self.now)

    def stamp(self, action, entry, occurred, revision=0, sequence=1, device='synthetic-pg-device'):
        return {'request_id': planning_fixture.rid(), 'entry_id': entry, 'project_id': self.project,
                'action': action, 'occurred_at': occurred, 'revision': revision, 'sequence': sequence, 'device_id': device}

    def test_postgres_move_uses_same_calendar_and_preserves_explicit_resource_booleans(self):
        resource = self.planning.save_resource(self.owner, {'request_id': planning_fixture.rid(), 'name': 'Synthetic PG vehicle',
            'kind': 'vehicle', 'active': True, 'code': planning_fixture.rid()})
        first = self.planning.save_appointment(self.owner, self.project, self.appointment(resource_ids=[resource['id']]))
        moved = self.planning.save_appointment(self.owner, self.project, self.appointment(
            id=first['id'], revision=first['revision'], resource_ids=[resource['id']],
            start_at='2026-10-28T12:00:00+01:00', end_at='2026-10-28T13:00:00+01:00'))
        values = self.planning.calendar(self.technician, {'from': '2026-10-27', 'to': '2026-10-29'})
        self.assertEqual(values['appointments'][0]['id'], moved['id'])
        self.assertEqual(values['appointments'][0]['start_at'], moved['start_at'])

    def test_postgres_idempotent_attendance_approval_and_snapshot_rate_cost(self):
        category = self.time.save_category(self.owner, {'request_id': planning_fixture.rid(), 'name': 'Synthetic PG site work',
            'supplement_percent': '25.00', 'active': True})
        self.time.save_rule(self.owner, {'request_id': planning_fixture.rid(), 'effective_from': '2026-01-01',
            'location_enabled': False, 'daily_target_minutes': 480, 'auto_pause_after_minutes': 360, 'auto_pause_minutes': 30})
        entry = planning_fixture.rid()
        start = dict(self.stamp('start', entry, '2026-10-26T08:00:00+01:00'), category_id=category['id'])
        self.time.event(self.technician, start)
        self.assertTrue(self.time.event(self.technician, start)['idempotent'])
        self.time.event(self.technician, self.stamp('stop', entry, '2026-10-26T16:30:00+01:00', 1, 2))
        summary = self.time.summary(self.owner, {'employee_id': self.employee['id'], 'from': '2026-10-26', 'to': '2026-10-26'})
        self.assertEqual(summary['net_seconds'], 8 * 3600)
        self.time.approve_day(self.owner, '2026-10-26', {'request_id': planning_fixture.rid(), 'employee_id': self.employee['id'],
            'revision': summary['days'][0]['revision']})
        self.assertEqual(self.time.approved_costs(self.owner, self.project)['total_cost_minor'], 35000)
        self.assertTrue(validate_integrity(self.office))

    def test_two_postgres_office_instances_serialize_start_for_one_employee(self):
        second = PostgresOffice(pg_fixture.DSN)
        self.addCleanup(second.db.close)
        services = [self.time, TimeTracking(second, clock=lambda: self.now)]
        barrier = threading.Barrier(2)
        def run(index):
            barrier.wait(timeout=3)
            body = self.stamp('start', planning_fixture.rid(), '2026-10-26T08:00:00+01:00', device='synthetic-pg-device-' + str(index))
            try:
                return services[index].event(self.technician, body)
            except Problem as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(run, range(2)))
        self.assertEqual(sum(isinstance(item, dict) for item in outcomes), 1)
        self.assertEqual(outcomes.count(409), 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_time_active').fetchone()[0], 1)
        self.assertTrue(validate_integrity(self.office))


if __name__ == '__main__':
    unittest.main()
