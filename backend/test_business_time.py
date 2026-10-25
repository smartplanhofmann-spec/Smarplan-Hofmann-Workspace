"""Time contracts first: offline retries, device conflicts, approval and privacy."""
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import json
import os
import sqlite3
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from test_business_planning import BusinessFixture, rid


class TimeTrackingTests(BusinessFixture, unittest.TestCase):
    def setUp(self):
        from business_time import TimeTracking, schema_statements
        self.prepare()
        self.now = self.now.replace(hour=20)
        for statement in schema_statements():
            self.office.db.execute(statement)
        self.time = TimeTracking(self.office, clock=lambda: self.now)
        self.entry_id = rid()

    def event(self, action, at, *, revision=0, sequence=1, **changes):
        return {'request_id': rid(), 'entry_id': self.entry_id, 'device_id': 'synthetic-device-one',
                'sequence': sequence, 'revision': revision, 'project_id': self.project,
                'action': action, 'occurred_at': at, **changes}

    def stamp(self, body, actor=None):
        return self.call(self.time, 'event', actor or self.technician, body)

    def finish_day(self):
        self.stamp(self.event('start', '2026-10-26T08:00:00+01:00'))
        return self.stamp(self.event('stop', '2026-10-26T16:00:00+01:00', revision=1, sequence=2))

    def private_checkpoint(self):
        private = Path(self.temporary.name) / 'privacy'
        private.mkdir(mode=0o700)
        key = private / 'key'
        key.write_bytes(b'S' * 32)
        key.chmod(0o600)
        environment = patch.dict('os.environ', {
            'SMARTPLAN_PRIVACY_CHECKPOINT_FILE': str(private / 'checkpoint.json'),
            'SMARTPLAN_PRIVACY_CHECKPOINT_KEY_FILE': str(key),
            'SMARTPLAN_PRIVACY_INSTALLATION_ID': rid(),
        })
        environment.start()
        self.addCleanup(environment.stop)
        from business_schema import initialize_privacy_checkpoint
        initialize_privacy_checkpoint(self.office)
        return private

    def test_offline_events_survive_restart_retry_once_and_device_conflicts_do_not_double_count(self):
        from business_time import TimeTracking
        start = self.event('start', '2026-10-26T08:00:00+01:00')
        receipt = self.stamp(start)
        self.assertFalse(receipt['idempotent'])
        self.time = TimeTracking(self.office, clock=lambda: self.now)
        self.assertTrue(self.stamp(start)['idempotent'])
        self.problem(409, lambda: self.stamp({**start, 'occurred_at': '2026-10-26T09:00:00+01:00'}))
        self.problem(409, lambda: self.stamp(self.event('start', '2026-10-26T08:00:00+01:00',
            entry_id=rid(), device_id='synthetic-device-two')))
        pause = self.event('pause', '2026-10-26T12:00:00+01:00', revision=1, sequence=2)
        self.stamp(pause)
        self.problem(409, lambda: self.stamp(self.event('stop', '2026-10-26T13:00:00+01:00',
            revision=1, sequence=2, device_id='synthetic-device-two')))
        self.stamp(self.event('resume', '2026-10-26T12:30:00+01:00', revision=2, sequence=3))
        self.stamp(self.event('stop', '2026-10-26T16:30:00+01:00', revision=3, sequence=4))
        summary = self.call(self.time, 'summary', self.technician, {'from': '2026-10-26', 'to': '2026-10-26'})
        self.assertEqual(summary['worked_seconds'], 8 * 3600)
        self.assertEqual(summary['break_seconds'], 1800)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_time_events').fetchone()[0], 4)

    def test_impossible_transitions_future_times_and_cross_project_access_are_rejected(self):
        self.problem(409, lambda: self.stamp(self.event('pause', '2026-10-26T08:00:00+01:00')))
        self.problem(400, lambda: self.stamp(self.event('start', '2036-10-26T08:00:00+01:00')))
        self.problem(404, lambda: self.stamp(self.event('start', '2026-10-26T08:00:00+01:00', project_id=self.other)))
        self.stamp(self.event('start', '2026-10-26T08:00:00+01:00'))
        self.problem(409, lambda: self.stamp(self.event('resume', '2026-10-26T09:00:00+01:00', revision=1, sequence=2)))
        self.problem(409, lambda: self.stamp(self.event('stop', '2026-10-26T07:00:00+01:00', revision=1, sequence=2)))

    @unittest.skipUnless(os.name == 'posix', 'Protected privacy checkpoint requires the POSIX Hetzner server')
    def test_day_approval_is_revision_bound_purges_location_and_retry_never_restores_it(self):
        self.private_checkpoint()
        self.call(self.time, 'save_rule', self.owner, {'request_id': rid(), 'effective_from': '2026-01-01',
            'location_enabled': True, 'daily_target_minutes': 480, 'auto_pause_after_minutes': 360,
            'auto_pause_minutes': 30})
        start = self.event('start', '2026-10-26T08:00:00+01:00', position={'latitude': '50.123456', 'longitude': '8.123456'})
        self.stamp(start)
        stop = self.event('stop', '2026-10-26T16:30:00+01:00', revision=1, sequence=2,
            position={'latitude': '50.123457', 'longitude': '8.123457'})
        self.stamp(stop)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_time_locations').fetchone()[0], 2)
        summary = self.call(self.time, 'summary', self.owner, {'employee_id': self.employee['id'], 'from': '2026-10-26', 'to': '2026-10-26'})
        self.problem(403, lambda: self.call(self.time, 'approve_day', self.technician, '2026-10-26', {
            'request_id': rid(), 'employee_id': self.employee['id'], 'revision': summary['days'][0]['revision']}))
        body = {'request_id': rid(), 'employee_id': self.employee['id'], 'revision': summary['days'][0]['revision']}
        approval = self.call(self.time, 'approve_day', self.owner, '2026-10-26', body)
        self.assertEqual(self.call(self.time, 'approve_day', self.owner, '2026-10-26', body), approval)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_time_locations').fetchone()[0], 0)
        self.assertTrue(self.stamp(start)['idempotent'])
        self.assertTrue(self.stamp(stop)['idempotent'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_time_locations').fetchone()[0], 0)
        stored = str([dict(r) for r in self.office.db.execute('SELECT * FROM business_time_events')])
        self.assertNotIn('50.123456', stored)
        self.assertNotIn('8.123457', stored)
        self.assertNotIn('latitude', json.dumps(self.call(self.time, 'export_csv', self.owner, {
            'employee_id': self.employee['id'], 'from': '2026-10-26', 'to': '2026-10-26'})))

    def test_location_is_opt_in_start_stop_only_and_never_general_audit_data(self):
        position = {'latitude': '50.111111', 'longitude': '8.222222'}
        self.problem(403, lambda: self.stamp(self.event('start', '2026-10-26T08:00:00+01:00', position=position)))
        self.stamp(self.event('start', '2026-10-26T08:00:00+01:00'))
        self.problem(400, lambda: self.stamp(self.event('pause', '2026-10-26T09:00:00+01:00', revision=1, sequence=2, position=position)))
        self.assertNotIn('50.111111', str([dict(r) for r in self.office.db.execute('SELECT * FROM audit')]))

    def test_dst_elapsed_duration_and_local_days_are_based_on_utc_and_berlin(self):
        self.stamp(self.event('start', '2026-10-25T01:30:00+02:00'))
        self.stamp(self.event('stop', '2026-10-25T03:30:00+01:00', revision=1, sequence=2))
        result = self.call(self.time, 'summary', self.technician, {'from': '2026-10-25', 'to': '2026-10-25'})
        self.assertEqual(result['worked_seconds'], 3 * 3600)
        self.assertEqual(result['days'][0]['date'], '2026-10-25')

    def test_other_personnel_and_cost_exports_require_explicit_permission_and_rates_are_snapshots(self):
        self.finish_day()
        self.problem(403, lambda: self.call(self.time, 'summary', self.technician, {'employee_id': rid(), 'from': '2026-10-26', 'to': '2026-10-26'}))
        self.problem(403, lambda: self.call(self.time, 'export_csv', self.technician, {'from': '2026-10-26', 'to': '2026-10-26'}))
        first = self.call(self.time, 'entries', self.technician, {})['items'][0]
        self.assertNotIn('hourly_cost_minor', first)
        self.call(self.planning, 'save_employee', self.owner, {'request_id': rid(), 'id': self.employee['id'],
            'revision': self.employee['revision'], 'hourly_cost_minor': 9900})
        summary = self.call(self.time, 'summary', self.owner, {'employee_id': self.employee['id'], 'from': '2026-10-26', 'to': '2026-10-26'})
        self.call(self.time, 'approve_day', self.owner, '2026-10-26', {'request_id': rid(),
            'employee_id': self.employee['id'], 'revision': summary['days'][0]['revision']})
        costs = self.call(self.time, 'approved_costs', self.owner, self.project)
        self.assertEqual(costs['items'][0]['hourly_cost_minor'], 3500)

    def test_two_concurrent_devices_create_exactly_one_active_session(self):
        from core import Problem
        barrier = threading.Barrier(2)
        bodies = [self.event('start', '2026-10-26T08:00:00+01:00', entry_id=rid(), device_id='synthetic-device-' + str(n)) for n in range(2)]
        def start(body):
            barrier.wait(timeout=3)
            try:
                return self.time.event(self.technician, body)
            except Problem as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(start, bodies))
        self.assertEqual(sum(isinstance(result, dict) for result in outcomes), 1)
        self.assertEqual(outcomes.count(409), 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_time_active').fetchone()[0], 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_time_events').fetchone()[0], 1)

    def test_rule_pause_is_per_day_across_projects_and_operational_duration_has_no_costs(self):
        self.office.assign(self.owner, self.other, self.technician['id'])
        self.call(self.time, 'save_rule', self.owner, {'request_id': rid(), 'effective_from': '2026-01-01',
            'auto_pause_after_minutes': 360, 'auto_pause_minutes': 30})
        self.stamp(self.event('start', '2026-10-26T08:00:00+01:00'))
        self.stamp(self.event('stop', '2026-10-26T10:00:00+01:00', revision=1, sequence=2))
        self.entry_id = rid()
        self.stamp(self.event('start', '2026-10-26T10:15:00+01:00', project_id=self.other))
        self.stamp(self.event('stop', '2026-10-26T16:15:00+01:00', project_id=self.other, revision=1, sequence=2))
        day = self.call(self.time, 'summary', self.owner, {'employee_id': self.employee['id'], 'from': '2026-10-26', 'to': '2026-10-26'})
        self.assertEqual(day['net_seconds'], 27000)
        self.assertEqual(day['auto_pause_seconds'], 1800)
        self.call(self.time, 'approve_day', self.owner, '2026-10-26', {'request_id': rid(),
            'employee_id': self.employee['id'], 'revision': day['days'][0]['revision']})
        first = self.call(self.time, 'approved_work', self.technician, self.project)
        second = self.call(self.time, 'approved_work', self.technician, self.other)
        self.assertEqual(first['total_net_seconds'] + second['total_net_seconds'], 27000)
        self.assertNotIn('hourly_cost', str(first))
        self.problem(403, lambda: self.call(self.time, 'approved_costs', self.technician, self.project))
        from business_time import validate_integrity
        self.assertTrue(validate_integrity(self.office))

    def test_missing_checkpoint_blocks_geo_approval_without_losing_positions_or_committing_day(self):
        self.call(self.time, 'save_rule', self.owner, {'request_id': rid(), 'effective_from': '2026-01-01', 'location_enabled': True})
        self.stamp(self.event('start', '2026-10-26T08:00:00+01:00', position={'latitude': '50', 'longitude': '8'}))
        self.stamp(self.event('stop', '2026-10-26T16:00:00+01:00', revision=1, sequence=2))
        day = self.call(self.time, 'summary', self.owner, {'employee_id': self.employee['id'], 'from': '2026-10-26', 'to': '2026-10-26'})
        with patch.dict('os.environ', {}, clear=True):
            self.problem(409, lambda: self.call(self.time, 'approve_day', self.owner, '2026-10-26', {
                'request_id': rid(), 'employee_id': self.employee['id'], 'revision': day['days'][0]['revision']}))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_time_locations').fetchone()[0], 1)
        self.assertEqual(self.call(self.time, 'summary', self.owner, {'employee_id': self.employee['id'], 'from': '2026-10-26', 'to': '2026-10-26'})['days'][0]['status'], 'draft')

    @unittest.skipUnless(os.name == 'posix', 'Protected privacy restore requires the POSIX Hetzner server')
    def test_independent_checkpoint_removes_geo_from_a_real_older_restored_sqlite_snapshot(self):
        from business_schema import privacy_restore_guard
        from business_time import validate_integrity
        from core import Office
        self.private_checkpoint()
        self.call(self.time, 'save_rule', self.owner, {'request_id': rid(), 'effective_from': '2026-01-01', 'location_enabled': True})
        self.stamp(self.event('start', '2026-10-26T08:00:00+01:00', position={'latitude': '50.333333', 'longitude': '8.444444'}))
        self.stamp(self.event('stop', '2026-10-26T16:00:00+01:00', revision=1, sequence=2))
        older = Path(self.temporary.name) / 'older.db'
        with sqlite3.connect(older) as target:
            self.office.db.backup(target)
        day = self.call(self.time, 'summary', self.owner, {'employee_id': self.employee['id'], 'from': '2026-10-26', 'to': '2026-10-26'})
        self.call(self.time, 'approve_day', self.owner, '2026-10-26', {'request_id': rid(),
            'employee_id': self.employee['id'], 'revision': day['days'][0]['revision']})
        restored = Office(older)
        self.addCleanup(restored.db.close)
        self.assertEqual(restored.db.execute('SELECT COUNT(*) FROM business_time_locations').fetchone()[0], 1)
        privacy_restore_guard(restored)
        self.assertEqual(restored.db.execute('SELECT COUNT(*) FROM business_time_locations').fetchone()[0], 0)
        self.assertEqual(restored.db.execute('SELECT COUNT(*) FROM business_time_events WHERE location_hash IS NOT NULL').fetchone()[0], 0)
        self.assertEqual(restored.db.execute("SELECT COUNT(*) FROM business_time_days WHERE status='approved'").fetchone()[0], 0)
        self.assertTrue(validate_integrity(restored))

    def test_approved_correction_is_append_only_preserves_original_and_changes_confirmed_costs_once(self):
        self.finish_day()
        query = {'employee_id': self.employee['id'], 'from': '2026-10-26', 'to': '2026-10-26'}
        day = self.call(self.time, 'summary', self.owner, query)
        self.call(self.time, 'approve_day', self.owner, '2026-10-26', {'request_id': rid(),
            'employee_id': self.employee['id'], 'revision': day['days'][0]['revision']})
        before = dict(self.office.db.execute('SELECT * FROM business_time_entries WHERE id=?', (self.entry_id,)).fetchone())
        body = {'request_id': rid(), 'work_date': '2026-10-26', 'delta_seconds': -1800, 'reason': 'Synthetic explicitly approved duration correction'}
        self.problem(403, lambda: self.call(self.time, 'correct_entry', self.technician, self.entry_id, body))
        correction = self.call(self.time, 'correct_entry', self.owner, self.entry_id, body)
        self.assertEqual(self.call(self.time, 'correct_entry', self.owner, self.entry_id, body), correction)
        self.assertEqual(dict(self.office.db.execute('SELECT * FROM business_time_entries WHERE id=?', (self.entry_id,)).fetchone()), before)
        self.assertEqual(self.call(self.time, 'summary', self.owner, query)['net_seconds'], 27000)
        self.assertEqual(self.call(self.time, 'approved_costs', self.owner, self.project)['total_cost_minor'], 26250)
        self.problem(409, lambda: self.call(self.time, 'correct_entry', self.owner, self.entry_id,
            {**body, 'request_id': rid(), 'delta_seconds': -86400}))
        from business_time import validate_integrity
        self.assertTrue(validate_integrity(self.office))

    def test_actual_reopen_preserves_event_receipts_and_corruption_is_detected(self):
        from business_time import TimeTracking, validate_integrity
        from core import Office
        body = self.event('start', '2026-10-26T08:00:00+01:00')
        first = self.stamp(body)
        self.office.db.close()
        self.office = Office(self.path)
        self.addCleanup(self.office.db.close)
        self.time = TimeTracking(self.office, clock=lambda: self.now)
        replay = self.stamp(body)
        self.assertEqual(replay['event_id'], first['event_id'])
        self.assertTrue(replay['idempotent'])
        self.assertTrue(validate_integrity(self.office))
        with self.office.db:
            self.office.db.execute('UPDATE business_time_events SET device_id=?', ('tampered-synthetic-device',))
        with self.assertRaises(ValueError):
            validate_integrity(self.office)

    def test_late_audit_failure_rolls_back_entry_event_active_cursor_and_day(self):
        body = self.event('start', '2026-10-26T08:00:00+01:00')
        with patch.object(self.office, 'audit', side_effect=RuntimeError('Synthetic late audit failure')):
            with self.assertRaises(RuntimeError):
                self.stamp(body)
        for table in ('business_time_entries', 'business_time_events', 'business_time_active', 'business_time_days'):
            self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0], 0)
        self.assertFalse(self.stamp(body)['idempotent'])

    def test_two_sqlite_office_instances_serialize_the_same_employee(self):
        from business_time import TimeTracking
        from core import Office, Problem
        other = Office(self.path)
        self.addCleanup(other.db.close)
        services = [self.time, TimeTracking(other, clock=lambda: self.now)]
        barrier = threading.Barrier(2)
        def run(index):
            body = self.event('start', '2026-10-26T08:00:00+01:00', entry_id=rid(), device_id='synthetic-separate-process-' + str(index))
            barrier.wait(timeout=3)
            try:
                return services[index].event(self.technician, body)
            except Problem as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(run, range(2)))
        self.assertEqual(sum(isinstance(item, dict) for item in outcomes), 1)
        self.assertEqual(outcomes.count(409), 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_time_events').fetchone()[0], 1)

    def test_billable_snapshot_contains_only_approved_duration_and_detects_later_correction(self):
        self.finish_day()
        self.problem(409, lambda: self.call(self.time, 'approved_billable', self.owner, self.project, [self.entry_id]))
        query = {'employee_id': self.employee['id'], 'from': '2026-10-26', 'to': '2026-10-26'}
        day = self.call(self.time, 'summary', self.owner, query)
        self.call(self.time, 'approve_day', self.owner, '2026-10-26', {'request_id': rid(),
            'employee_id': self.employee['id'], 'revision': day['days'][0]['revision']})
        before = self.call(self.time, 'approved_billable', self.owner, self.project, [self.entry_id])['items'][0]
        self.assertEqual(before['net_seconds'], 28800)
        self.assertEqual(before['revision'], 2)
        self.assertNotIn('hourly_cost_minor', str(before))
        self.assertNotIn('employee_id', before)
        self.assertNotIn('name', before)
        self.problem(403, lambda: self.call(self.time, 'approved_billable', self.technician, self.project, [self.entry_id]))
        self.problem(409, lambda: self.call(self.time, 'approved_billable', self.owner, self.other, [self.entry_id]))
        self.call(self.time, 'correct_entry', self.owner, self.entry_id, {'request_id': rid(), 'work_date': '2026-10-26',
            'delta_seconds': -1800, 'reason': 'Synthetic corrected invoice source duration'})
        after = self.call(self.time, 'approved_billable', self.owner, self.project, [self.entry_id])['items'][0]
        self.assertEqual(after['net_seconds'], 27000)
        self.assertNotEqual(after['source_hash'], before['source_hash'])
        self.assertEqual(self.call(self.time, 'approved_billable', self.owner, self.project, [self.entry_id])['items'][0], after)


if __name__ == '__main__':
    unittest.main()
