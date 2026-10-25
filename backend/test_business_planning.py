"""Planning contracts first: canonical calendars, collisions and private HR data."""
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
import uuid

from core import Office, Problem


def rid():
    return uuid.uuid4().hex


class BusinessFixture:
    def prepare(self):
        from business_foundation import schema_statements as foundation_schema
        from business_planning import Planning, schema_statements as planning_schema
        self.temporary = tempfile.TemporaryDirectory(prefix='smartplan-business-planning-')
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / 'office.db'
        self.office = Office(self.path)
        self.addCleanup(self.office.db.close)
        from business_schema import ensure_schema
        ensure_schema(self.office)
        for statement in [*foundation_schema(), *planning_schema()]:
            self.office.db.execute(statement)
        self.now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
        self.owner_id = self.office.add_user('owner@example.test', 'Synthetic-owner-password-123', 'owner')
        self.owner = {'id': self.owner_id, 'role': 'owner', 'email': 'owner@example.test'}
        uid = self.office.add_user('technician@example.test', 'Synthetic-technician-password-123', 'technician')
        self.technician = {'id': uid, 'role': 'technician', 'email': 'technician@example.test'}
        self.project = self.office.add_project(self.owner, 'Synthetic site', 'Synthetic customer')
        self.other = self.office.add_project(self.owner, 'Other site', 'Other customer')
        self.office.assign(self.owner, self.project, uid)
        self.planning = Planning(self.office, clock=lambda: self.now)
        self.employee = self.call(self.planning, 'save_employee', self.owner, {
            'request_id': rid(), 'user_id': uid, 'name': 'Synthetic technician',
            'weekly_minutes': 2400, 'hourly_cost_minor': 3500})

    def call(self, service, method, *args, **kwargs):
        with self.office.lock, self.office.db:
            return getattr(service, method)(*args, **kwargs)

    def problem(self, status, callback):
        with self.assertRaises(Problem) as raised:
            callback()
        self.assertEqual(raised.exception.status, status, raised.exception.message)

    def appointment(self, **changes):
        return {'request_id': rid(), 'title': 'Synthetic survey',
                'start_at': '2026-10-27T09:00:00+01:00', 'end_at': '2026-10-27T10:00:00+01:00',
                'timezone': 'Europe/Berlin', 'employee_ids': [self.employee['id']], 'resource_ids': [], **changes}


class PlanningTests(BusinessFixture, unittest.TestCase):
    def setUp(self):
        self.prepare()

    def test_project_move_immediately_changes_the_same_employee_calendar_and_retries_once(self):
        body = self.appointment()
        first = self.call(self.planning, 'save_appointment', self.owner, self.project, body)
        self.assertEqual(self.call(self.planning, 'save_appointment', self.owner, self.project, body), first)
        moved = self.call(self.planning, 'save_appointment', self.owner, self.project, {
            **body, 'id': first['id'], 'revision': first['revision'], 'request_id': rid(),
            'start_at': '2026-10-28T11:00:00+01:00', 'end_at': '2026-10-28T12:00:00+01:00'})
        result = self.call(self.planning, 'calendar', self.technician, {
            'from': '2026-10-27', 'to': '2026-10-29', 'employee_id': self.employee['id']})
        self.assertEqual([item['id'] for item in result['appointments']], [first['id']])
        self.assertEqual(result['appointments'][0]['start_at'], moved['start_at'])
        self.problem(409, lambda: self.call(self.planning, 'save_appointment', self.owner, self.project, {
            **body, 'id': first['id'], 'revision': 1, 'request_id': rid()}))

    def test_employee_and_resource_conflicts_require_explicit_audited_override(self):
        resource = self.call(self.planning, 'save_resource', self.owner, {
            'request_id': rid(), 'name': 'Synthetic vehicle', 'kind': 'vehicle', 'code': 'SYN-VEHICLE'})
        first = self.appointment(resource_ids=[resource['id']])
        self.call(self.planning, 'save_appointment', self.owner, self.project, first)
        second = self.appointment(resource_ids=[resource['id']],
            start_at='2026-10-27T09:30:00+01:00', end_at='2026-10-27T10:30:00+01:00')
        conflicts = self.call(self.planning, 'conflicts', self.owner, self.project, second)['items']
        self.assertEqual({c['kind'] for c in conflicts}, {'employee', 'resource'})
        self.problem(409, lambda: self.call(self.planning, 'save_appointment', self.owner, self.project, second))
        saved = self.call(self.planning, 'save_appointment', self.owner, self.project, {
            **second, 'override_conflicts': True, 'override_reason': 'Explicit synthetic coordination'})
        self.assertTrue(saved['conflicts'])
        self.assertEqual(self.office.db.execute("SELECT COUNT(*) FROM audit WHERE action='planning.conflict.overridden'").fetchone()[0], 1)

    def test_weekly_series_preserves_wall_clock_across_dst_and_single_occurrence_exception(self):
        first = self.call(self.planning, 'save_appointment', self.owner, self.project, self.appointment(
            start_at='2026-03-22T09:00:00+01:00', end_at='2026-03-22T10:00:00+01:00',
            recurrence={'frequency': 'weekly', 'interval': 1, 'count': 2}))
        items = self.call(self.planning, 'calendar', self.owner, {'from': '2026-03-20', 'to': '2026-04-02'})['appointments']
        self.assertEqual([item['start_at'] for item in items], ['2026-03-22T08:00:00+00:00', '2026-03-29T07:00:00+00:00'])
        self.assertEqual({item['series_id'] for item in items}, {first['series_id']})
        original = dict(self.office.db.execute('SELECT * FROM business_appointment_series WHERE id=?', (first['series_id'],)).fetchone())
        moved = self.call(self.planning, 'save_appointment', self.owner, self.project, self.appointment(
            id=items[1]['id'], revision=items[1]['revision'], start_at='2026-03-30T11:00:00+02:00',
            end_at='2026-03-30T12:00:00+02:00'))
        current = self.call(self.planning, 'calendar', self.owner, {'from': '2026-03-20', 'to': '2026-04-02'})['appointments']
        self.assertEqual(current[0], items[0])
        self.assertEqual(current[1]['id'], moved['id'])
        self.assertEqual(current[1]['occurrence_index'], 1)
        self.assertEqual(dict(self.office.db.execute('SELECT * FROM business_appointment_series WHERE id=?', (first['series_id'],)).fetchone()), original)

    def test_approved_absence_blocks_booking_but_calendar_never_exposes_private_reason(self):
        absence = self.call(self.planning, 'save_absence', self.technician, {
            'request_id': rid(), 'employee_id': self.employee['id'], 'start_date': '2026-10-27',
            'end_date': '2026-10-27', 'kind': 'sick', 'details': 'Synthetic private medical information'})
        self.problem(403, lambda: self.call(self.planning, 'approve_absence', self.technician, absence['id'], {
            'request_id': rid(), 'revision': absence['revision'], 'status': 'approved'}))
        self.call(self.planning, 'approve_absence', self.owner, absence['id'], {
            'request_id': rid(), 'revision': absence['revision'], 'status': 'approved'})
        view = self.call(self.planning, 'calendar', self.technician, {'from': '2026-10-26', 'to': '2026-10-29'})
        self.assertEqual(len(view['absences']), 1)
        self.assertNotIn('sick', str(view))
        self.assertNotIn('medical', str(view))
        self.problem(409, lambda: self.call(self.planning, 'save_appointment', self.owner, self.project, self.appointment()))

    def test_shift_is_a_canonical_employee_booking_and_private_hr_costs_are_filtered(self):
        shift = self.call(self.planning, 'save_shift', self.owner, {
            **self.appointment(), 'project_id': self.project})
        calendar = self.call(self.planning, 'calendar', self.technician, {'from': '2026-10-26', 'to': '2026-10-29'})
        self.assertEqual(calendar['appointments'][0]['id'], shift['id'])
        self.assertEqual(calendar['appointments'][0]['kind'], 'shift')
        self.assertNotIn('hourly_cost_minor', str(calendar))
        self.problem(403, lambda: self.call(self.planning, 'save_employee', self.technician, {
            'request_id': rid(), 'id': self.employee['id'], 'revision': 1, 'hourly_cost_minor': 1}))

    def test_scope_and_role_are_rechecked_before_replay(self):
        body = self.appointment()
        self.call(self.planning, 'save_appointment', self.owner, self.project, body)
        self.problem(403, lambda: self.call(self.planning, 'save_appointment', self.technician, self.project, body))
        with self.office.db:
            self.office.db.execute('UPDATE users SET active=0 WHERE id=?', (self.owner_id,))
        self.problem(401, lambda: self.call(self.planning, 'save_appointment', self.owner, self.project, body))

    def test_schema_is_idempotent_and_integrity_rejects_cross_project_employee_assignment(self):
        from business_planning import schema_statements, validate_integrity
        for statement in schema_statements():
            self.office.db.execute(statement)
        self.problem(400, lambda: self.call(self.planning, 'save_appointment', self.owner, self.other, self.appointment()))
        self.assertTrue(validate_integrity(self.office))

    def test_series_conflict_rolls_back_all_occurrences_and_dst_gap_is_never_silently_shifted(self):
        self.call(self.planning, 'save_appointment', self.owner, self.project, self.appointment(
            start_at='2026-10-28T09:00:00+01:00', end_at='2026-10-28T10:00:00+01:00'))
        self.problem(409, lambda: self.call(self.planning, 'save_appointment', self.owner, self.project, self.appointment(
            recurrence={'frequency': 'daily', 'interval': 1, 'count': 3})))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_appointments').fetchone()[0], 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_appointment_series').fetchone()[0], 0)
        self.problem(400, lambda: self.call(self.planning, 'save_appointment', self.owner, self.project, self.appointment(
            start_at='2026-03-28T02:30:00+01:00', end_at='2026-03-28T03:30:00+01:00',
            recurrence={'frequency': 'daily', 'interval': 1, 'count': 2})))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_appointments').fetchone()[0], 1)

    def test_employee_identity_cannot_be_reassigned_and_malformed_member_lists_are_400(self):
        self.problem(409, lambda: self.call(self.planning, 'save_employee', self.owner, {
            'request_id': rid(), 'id': self.employee['id'], 'revision': self.employee['revision'], 'user_id': self.owner_id}))
        self.problem(400, lambda: self.call(self.planning, 'save_appointment', self.owner, self.project,
            self.appointment(employee_ids=[{'id': self.employee['id']}])))
        self.assertEqual(self.planning.employee(self.employee['id'])['user_id'], self.technician['id'])

    def test_exact_instant_week_range_and_historical_detail_do_not_depend_on_today(self):
        from business_planning import dispatch
        item = self.call(self.planning, 'save_appointment', self.owner, self.project, self.appointment(
            start_at='2026-01-05T09:00:00+01:00', end_at='2026-01-05T10:00:00+01:00'))
        week = self.call(self.planning, 'calendar', self.technician, {
            'from': '2026-01-04T23:00:00Z', 'to': '2026-01-11T23:00:00Z'})
        self.assertEqual([entry['id'] for entry in week['appointments']], [item['id']])
        result, status, _ = dispatch(self.office, self.technician, '/appointments/' + item['id'], 'GET', {})
        self.assertEqual((status, result['id']), (200, item['id']))


if __name__ == '__main__':
    unittest.main()
