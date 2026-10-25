"""Synthetic real-SQLite workflows and permission contracts for project work."""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from core import Office, Problem
from project_workspace import ProjectWorkspace, ensure_sqlite_schema, validate_integrity


class ProjectWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='smartplan-workspace-')
        self.path = Path(self.temporary.name) / 'office.sqlite'
        self.office = Office(self.path)
        ensure_sqlite_schema(self.office)
        self.now = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
        self.workspace = ProjectWorkspace(self.office, clock=lambda: self.now)
        self.owner = self.actor('owner')
        self.manager = self.actor('manager')
        self.technician = self.actor('technician')
        self.accountant = self.actor('accountant')
        self.outsider = self.actor('technician', 'outsider')
        self.project = self.office.add_project(self.owner, 'Synthetic retrofit', 'Synthetic Customer')
        self.other_project = self.office.add_project(self.owner, 'Separate project', 'Other Customer')
        for actor in (self.manager, self.technician, self.accountant):
            self.office.assign(self.owner, self.project, actor['id'])

    def tearDown(self):
        self.office.db.close()
        self.temporary.cleanup()

    def actor(self, role, label=None):
        email = (label or role) + '@example.test'
        identifier = self.office.add_user(email, 'Synthetic-password-123', role)
        return dict(id=identifier, email=email, role=role)

    def perform(self, function, *args, **kwargs):
        with self.office.lock, self.office.db:
            return function(*args, **kwargs)

    def error(self, status, function, *args, **kwargs):
        with self.assertRaises(Problem) as caught:
            self.perform(function, *args, **kwargs)
        self.assertEqual(caught.exception.status, status)

    def request(self, **data):
        return dict(request_id=uuid.uuid4().hex, **data)

    def create(self, kind, **data):
        return self.perform(self.workspace.save_item, self.technician, self.project, kind, self.request(**data))

    def classify_link(self, identifier, classification):
        from business_foundation import BusinessFoundation
        service = BusinessFoundation(self.office)
        current = service.classification(self.owner, self.project, 'link', identifier)
        return service.classify(self.owner, self.project, 'link', identifier,
            self.request(revision=current['revision'], expected_source_fingerprint=current['source_fingerprint'],
                         classification=classification))

    def test_empty_dashboard_contains_only_real_existing_project_data(self):
        result = self.perform(self.workspace.dashboard, self.owner, self.project)
        self.assertEqual(result['project']['name'], 'Synthetic retrofit')
        self.assertEqual(result['profile']['revision'], 0)
        self.assertEqual(result['profile']['phase'], 'planning')
        self.assertEqual(result['profile']['deposit_status'], 'not_recorded')
        self.assertEqual(result['profile']['materials_status'], 'not_recorded')
        self.assertTrue(all(count == 0 for count in result['counters'].values()))
        self.assertEqual(result['open_tasks'], [])
        self.assertEqual(result['latest_diary'], [])
        self.assertEqual(result['links'], [])
        self.assertNotIn(self.outsider['id'], {member['id'] for member in result['team']})

    def test_full_project_workflow_survives_reopen(self):
        profile = self.perform(self.workspace.save_profile, self.manager, self.project, self.request(
            revision=0, description='Replace distribution board', site_address='Synthetic street 1',
            phase='awaiting_deposit', deposit_status='requested', materials_status='to_order',
            start_date='2026-11-02', end_date='2026-11-06'))
        task = self.create('tasks', title='Check material list', assignee_id=self.technician['id'],
                           due_date='2026-10-23', priority='high')
        diary = self.create('diary', entry_date='2026-10-24', work_performed='Survey completed',
                            issues='Access key required', next_steps='Confirm appointment', crew_count=2)
        appointment = self.create('appointments', title='Installation', start_at='2026-11-02T08:00:00+01:00',
                                  end_at='2026-11-02T12:00:00+01:00')
        link = self.create('links', title='Project Dropbox folder', category='dropbox',
                           url='https://www.dropbox.com/scl/fo/synthetic?dl=0')
        self.perform(self.workspace.save_item, self.technician, self.project, 'tasks',
                     self.request(revision=task['revision'], status='in_progress'), task['id'])
        reopened = Office(self.path)
        try:
            ensure_sqlite_schema(reopened)
            workspace = ProjectWorkspace(reopened, clock=lambda: self.now)
            with reopened.lock, reopened.db:
                dashboard = workspace.dashboard(self.owner, self.project)
            self.assertEqual(dashboard['profile'], profile)
            self.assertEqual(dashboard['open_tasks'][0]['status'], 'in_progress')
            self.assertEqual(dashboard['latest_diary'][0], diary)
            self.assertEqual(dashboard['upcoming_appointments'][0], appointment)
            self.assertEqual(dashboard['links'][0], link)
            self.assertEqual(dashboard['counters']['tasks_overdue'], 1)
        finally:
            reopened.db.close()

    def test_every_kind_requires_fresh_project_scope_for_list_detail_and_write(self):
        values = {
            'tasks': {'title': 'Task'},
            'diary': {'work_performed': 'Synthetic diary'},
            'appointments': {'title': 'Meeting', 'start_at': '2026-10-25T08:00:00Z', 'end_at': '2026-10-25T09:00:00Z'},
            'links': {'title': 'Contract', 'url': 'https://example.test/contract'},
        }
        for kind, body in values.items():
            item = self.create(kind, **body)
            self.error(404, self.workspace.list_items, self.outsider, self.project, kind)
            self.error(404, self.workspace.get_item, self.outsider, self.project, kind, item['id'])
            self.error(404, self.workspace.save_item, self.outsider, self.project, kind, self.request(**body))
            self.error(404, self.workspace.get_item, self.owner, self.other_project, kind, item['id'])
            self.error(404, self.workspace.save_item, self.owner, self.other_project, kind,
                       self.request(revision=1, **body), item['id'])
            if kind == 'links':
                self.error(404, self.workspace.get_item, self.accountant, self.project, kind, item['id'])
                self.classify_link(item['id'], 'operational')
            # An accountant sees assigned project data but cannot mutate it.
            self.assertEqual(self.perform(self.workspace.get_item, self.accountant, self.project, kind, item['id']), item)
            self.error(403, self.workspace.save_item, self.accountant, self.project, kind, self.request(**body))
        self.office.assign(self.owner, self.project, self.technician['id'], remove=True)
        self.error(404, self.workspace.dashboard, self.technician, self.project)

    def test_profile_updates_require_manager_role_and_current_revision(self):
        body = self.request(revision=0, description='Initial scope')
        self.error(403, self.workspace.save_profile, self.technician, self.project, body)
        first = self.perform(self.workspace.save_profile, self.manager, self.project, body)
        second = self.perform(self.workspace.save_profile, self.manager, self.project,
                              self.request(revision=1, deposit_status='received', phase='procurement'))
        self.assertEqual(second['revision'], 2)
        self.assertEqual(second['description'], 'Initial scope')
        self.assertEqual(second['deposit_status'], 'received')
        self.assertEqual(second['materials_status'], 'not_recorded')
        self.error(409, self.workspace.save_profile, self.manager, self.project,
                   self.request(revision=first['revision'], phase='execution'))
        self.assertEqual(self.perform(self.workspace.profile, self.owner, self.project), second)

    def test_retries_return_same_result_once_and_never_change_a_newer_version(self):
        body = self.request(title='Prepare offer', due_date='2026-10-25')
        first = self.perform(self.workspace.save_item, self.owner, self.project, 'tasks', body)
        self.assertEqual(self.perform(self.workspace.save_item, self.owner, self.project, 'tasks', body), first)
        changed = self.perform(self.workspace.save_item, self.owner, self.project, 'tasks',
                               self.request(revision=1, status='done'), first['id'])
        self.assertEqual(self.perform(self.workspace.save_item, self.owner, self.project, 'tasks', body), first)
        self.assertEqual(self.perform(self.workspace.get_item, self.owner, self.project, 'tasks', first['id']), changed)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM workspace_items').fetchone()[0], 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM workspace_versions').fetchone()[0], 2)
        self.assertEqual(self.office.db.execute("SELECT COUNT(*) FROM audit WHERE action LIKE 'workspace.tasks.%'").fetchone()[0], 2)
        self.error(409, self.workspace.save_item, self.owner, self.project, 'tasks', {**body, 'title': 'Other content'})
        self.error(409, self.workspace.save_item, self.owner, self.project, 'diary',
                   {'request_id': body['request_id'], 'work_performed': 'Wrong request namespace'})
        self.error(409, self.workspace.save_item, self.owner, self.other_project, 'tasks', body)

    def test_request_replay_cannot_bypass_revoked_project_access(self):
        body = self.request(title='Before revocation')
        self.perform(self.workspace.save_item, self.technician, self.project, 'tasks', body)
        self.office.assign(self.owner, self.project, self.technician['id'], remove=True)
        self.error(404, self.workspace.save_item, self.technician, self.project, 'tasks', body)

    def test_assignees_must_be_active_project_members(self):
        for target in (self.outsider['id'], 'f' * 32, True, 'not-an-id'):
            self.error(400, self.workspace.save_item, self.owner, self.project, 'tasks',
                       self.request(title='Invalid assignee', assignee_id=target))
        self.office.update_user(self.owner, self.manager['id'], {'active': False})
        self.error(400, self.workspace.save_item, self.owner, self.project, 'tasks',
                   self.request(title='Inactive assignee', assignee_id=self.manager['id']))
        assigned = self.create('tasks', title='Owner is in project team', assignee_id=self.owner['id'])
        self.assertEqual(assigned['assignee_id'], self.owner['id'])
        team = self.perform(self.workspace.team, self.technician, self.project)
        self.assertNotIn(self.manager['id'], {member['id'] for member in team})
        self.assertTrue(all(set(member) == {'id', 'email', 'role'} for member in team))

    def test_conflicting_item_updates_preserve_both_record_and_history(self):
        first = self.create('diary', work_performed='First observation')
        second = self.perform(self.workspace.save_item, self.manager, self.project, 'diary',
                              self.request(revision=1, issues='Second observation'), first['id'])
        self.error(409, self.workspace.save_item, self.technician, self.project, 'diary',
                   self.request(revision=1, work_performed='Stale edit'), first['id'])
        versions = self.office.db.execute('SELECT payload FROM workspace_versions WHERE object_id=? '
                                           'ORDER BY revision', (first['id'],)).fetchall()
        self.assertEqual([json.loads(row[0]) for row in versions], [first, second])
        self.assertEqual(self.perform(self.workspace.get_item, self.owner, self.project, 'diary', first['id']), second)

    def test_task_date_priority_and_typed_values_are_validated(self):
        for changes in ({'due_date': '2026-02-30'}, {'due_date': '24.10.2026'}, {'due_date': True},
                        {'priority': 'urgent'}, {'status': 'invented'}, {'title': ''}, {'title': '\x00'},
                        {'unknown': 'not stored'}, {'request_id': 'bad'}, {'title': '\ud800'}, {'details': '\x01invalid'}):
            self.error(400, self.workspace.save_item, self.owner, self.project, 'tasks', self.request(title='Task') | changes)
        self.error(400, self.workspace.save_item, self.owner, self.project, 'tasks', self.request(title='Task', revision=0))
        self.assertEqual(self.perform(self.workspace.list_items, self.owner, self.project, 'tasks'), [])

    def test_profile_dates_and_manually_recorded_milestones_are_strict(self):
        for body in ({'phase': 'unknown'}, {'deposit_status': 0}, {'materials_status': 'available'},
                     {'start_date': '2026-11-06', 'end_date': '2026-11-02'}, {'start_date': '2026-02-30'},
                     {'description': 'x' * 10001}, {'site_address': '\x00invalid'}):
            self.error(400, self.workspace.save_profile, self.owner, self.project, self.request(revision=0, **body))
        self.assertEqual(self.perform(self.workspace.profile, self.owner, self.project)['revision'], 0)

    def test_project_phases_never_impose_an_order_or_invent_financial_milestones(self):
        running = self.perform(self.workspace.save_profile, self.manager, self.project,
                               self.request(revision=0, phase='execution'))
        self.assertEqual(running['deposit_status'], 'not_recorded')
        self.assertEqual(running['materials_status'], 'not_recorded')
        completed = self.perform(self.workspace.save_profile, self.manager, self.project,
                                 self.request(revision=1, phase='completed'))
        self.assertEqual(completed['deposit_status'], 'not_recorded')
        replanned = self.perform(self.workspace.save_profile, self.manager, self.project,
                                 self.request(revision=2, phase='planning'))
        self.assertEqual(replanned['phase'], 'planning')
        self.assertIsNone(replanned['start_date'])
        self.assertIsNone(replanned['end_date'])

    def test_diary_requires_work_and_valid_crew_without_inventing_weather(self):
        for body in ({'work_performed': ''}, {'work_performed': 'Work', 'crew_count': True},
                     {'work_performed': 'Work', 'crew_count': -1}, {'work_performed': 'Work', 'entry_date': '2026-02-30'}):
            self.error(400, self.workspace.save_item, self.technician, self.project, 'diary', self.request(**body))
        entry = self.create('diary', work_performed='Work recorded')
        self.assertEqual(entry['weather'], '')
        self.assertIsNone(entry['crew_count'])
        self.assertEqual(entry['entry_date'], '2026-10-24')

    def test_appointment_requires_timezone_and_positive_interval(self):
        valid = dict(title='Appointment', start_at='2026-10-25T10:00:00+01:00', end_at='2026-10-25T12:00:00+01:00')
        for changes in ({'start_at': '2026-10-25T10:00:00'}, {'start_at': 'invalid'},
                        {'end_at': '2026-10-25T09:00:00+01:00'}, {'end_at': valid['start_at']}, {'status': 'draft'}):
            self.error(400, self.workspace.save_item, self.owner, self.project, 'appointments', self.request(**(valid | changes)))
        appointment = self.create('appointments', **valid)
        self.assertEqual(appointment['start_at'], '2026-10-25T09:00:00+00:00')

    def test_calendar_export_has_stable_identity_utf8_folding_and_no_line_injection(self):
        self.perform(self.workspace.save_profile, self.owner, self.project,
                     self.request(revision=0, site_address='Synthetic street; 1, second floor'))
        appointment = self.create('appointments', title='ä' * 180 + '\nEND:VEVENT',
                                  details='First line\r\nBEGIN:VEVENT;comma,slash\\end',
                                  start_at='2026-10-25T10:00:00+01:00', end_at='2026-10-25T11:00:00+01:00')
        encoded = self.perform(self.workspace.calendar, self.accountant, self.project, appointment['id'])
        self.assertTrue(encoded.endswith(b'\r\n'))
        self.assertTrue(all(len(line) <= 75 for line in encoded.split(b'\r\n')))
        unfolded = encoded.decode().replace('\r\n ', '')
        self.assertEqual(unfolded.count('\r\nBEGIN:VEVENT\r\n'), 1)
        self.assertEqual(unfolded.count('\r\nEND:VEVENT\r\n'), 1)
        self.assertIn('DTSTART:20261025T090000Z\r\n', unfolded)
        self.assertIn('LOCATION:Synthetic street\\; 1\\, second floor', unfolded)
        self.assertIn('\\nBEGIN:VEVENT\\;comma\\,slash\\\\end', unfolded)
        self.assertEqual(encoded, self.perform(self.workspace.calendar, self.owner, self.project, appointment['id']))
        self.error(404, self.workspace.calendar, self.outsider, self.project, appointment['id'])

    def test_external_links_are_real_https_references_and_can_be_hidden(self):
        for url in ('http://example.test', 'javascript:alert(1)', 'https://user:password@example.test/doc',
                    'https://example.test/\nprivate', 'https://not a host/path', 'https://example.test:0/doc'):
            self.error(400, self.workspace.save_item, self.owner, self.project, 'links', self.request(title='Link', url=url))
        body = self.request(title='Sevdesk offer', category='offer', url='https://my.sevdesk.de/synthetic-offer')
        self.error(403, self.workspace.save_item, self.technician, self.project, 'links', body)
        link = self.perform(self.workspace.save_item, self.owner, self.project, 'links', body)
        self.classify_link(link['id'], 'financial')
        self.error(404, self.workspace.get_item, self.technician, self.project, 'links', link['id'])
        self.assertEqual(self.perform(self.workspace.get_item, self.accountant, self.project, 'links', link['id']), link)
        self.assertEqual(self.perform(self.workspace.dashboard, self.owner, self.project)['links'], [link])
        self.perform(self.workspace.save_item, self.owner, self.project, 'links',
                     self.request(revision=1, active=False), link['id'])
        self.assertEqual(self.perform(self.workspace.dashboard, self.owner, self.project)['links'], [])
        self.assertEqual(len(self.perform(self.workspace.list_items, self.owner, self.project, 'links')), 1)

    def test_dashboard_filters_finished_tasks_cancelled_and_past_appointments(self):
        self.create('tasks', title='Overdue', due_date='2026-10-23')
        self.create('tasks', title='Today', due_date='2026-10-24')
        self.create('tasks', title='Done', due_date='2026-10-01', status='done')
        self.create('tasks', title='Cancelled', due_date='2026-10-01', status='cancelled')
        for title, start, end, status in (
            ('Old', '2026-10-23T10:00:00Z', '2026-10-23T11:00:00Z', 'scheduled'),
            ('Future', '2026-10-25T10:00:00Z', '2026-10-25T11:00:00Z', 'scheduled'),
            ('Cancelled', '2026-10-25T12:00:00Z', '2026-10-25T13:00:00Z', 'cancelled')):
            self.create('appointments', title=title, start_at=start, end_at=end, status=status)
        result = self.perform(self.workspace.dashboard, self.owner, self.project)
        self.assertEqual(result['counters']['tasks_open'], 2)
        self.assertEqual(result['counters']['tasks_overdue'], 1)
        self.assertEqual(result['counters']['appointments_upcoming'], 1)
        self.assertEqual([entry['title'] for entry in result['upcoming_appointments']], ['Future'])
        self.assertEqual(self.perform(self.workspace.dashboard, self.owner, self.other_project)['counters']['tasks_open'], 0)

    def test_failed_request_receipt_write_rolls_back_the_entire_mutation(self):
        # The public dispatcher owns the transaction. A late DB failure cannot
        # leave an unacknowledged task, version or audit event behind.
        self.office.db.execute("CREATE TRIGGER synthetic_receipt_failure BEFORE INSERT ON workspace_requests "
                               "BEGIN SELECT RAISE(ABORT,'synthetic disk failure'); END")
        self.office.db.commit()
        with self.assertRaises(self.office.integrity_error):
            self.create('tasks', title='Must roll back')
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM workspace_items').fetchone()[0], 0)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM workspace_versions').fetchone()[0], 0)
        self.assertEqual(self.office.db.execute("SELECT COUNT(*) FROM audit WHERE action LIKE 'workspace.%'").fetchone()[0], 0)

    def test_integrity_uses_retained_versions_without_reauthorizing_historical_assignees(self):
        task = self.create('tasks', title='Retained original', assignee_id=self.manager['id'])
        self.perform(self.workspace.save_item, self.owner, self.project, 'tasks',
                     self.request(revision=1, status='done'), task['id'])
        self.office.update_user(self.owner, self.manager['id'], {'active': False})
        self.assertTrue(validate_integrity(self.office))
        with self.office.db:
            self.office.db.execute('UPDATE workspace_items SET payload=? WHERE id=?',
                                   (json.dumps({'title': 'tampered'}), task['id']))
        with self.assertRaises(ValueError):
            validate_integrity(self.office)

    def test_disabling_a_former_assignee_does_not_block_completion_of_the_existing_task(self):
        task = self.create('tasks', title='Existing responsibility', assignee_id=self.manager['id'])
        self.office.update_user(self.owner, self.manager['id'], {'active': False})
        completed = self.perform(self.workspace.save_item, self.owner, self.project, 'tasks',
                                 self.request(revision=1, status='done'), task['id'])
        self.assertEqual(completed['status'], 'done')
        self.assertEqual(completed['assignee_id'], self.manager['id'])
        self.error(400, self.workspace.save_item, self.owner, self.project, 'tasks',
                   self.request(title='New assignment', assignee_id=self.manager['id']))


if __name__ == '__main__':
    unittest.main()
