"""Actual project milestone records, access checks and retained history."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import uuid

from core import Office, Problem
from business_foundation import BusinessFoundation
from business_project_milestones import ProjectMilestones, TABLES, validate_integrity


def request(**values):
    result = dict(schema_version=1, request_id=uuid.uuid4().hex, title='Freigabe Süd – Phase 1',
                  details='Original prüfen.\nAussagekräftige Dokumentation.', due_date='2026-11-30',
                  assignee_id=None, status='planned')
    result.update(values)
    return result


class MilestoneFixture:
    def __init__(self, folder):
        self.office = Office(Path(folder) / 'milestones.sqlite3')
        self.owner = dict(id=self.office.add_user('milestone-owner@example.test', 'Synthetic-milestone-password-123', 'owner'),
                          email='milestone-owner@example.test', role='owner')
        self.manager = dict(id=self.office.add_user('milestone-manager@example.test', 'Synthetic-manager-password-123', 'manager'),
                            email='milestone-manager@example.test', role='manager')
        self.technician = dict(id=self.office.add_user('milestone-tech@example.test', 'Synthetic-tech-password-123', 'technician'),
                               email='milestone-tech@example.test', role='technician')
        self.project = self.office.add_project(self.owner, 'Synthetisches Meilensteinprojekt', 'Synthetischer Kunde')
        self.other_project = self.office.add_project(self.owner, 'Anderes Projekt', 'Anderer Kunde')
        self.office.assign(self.owner, self.project, self.manager['id'])
        self.office.assign(self.owner, self.project, self.technician['id'])
        self.now = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
        self.api = ProjectMilestones(self.office, clock=lambda: self.now)

    def command(self, current=None, **changes):
        data = request()
        if current is not None:
            data.update({field: current[field] for field in ('title', 'details', 'due_date', 'assignee_id', 'status')})
            data['revision'] = current['revision']
        data.update(changes)
        return data

    def export(self):
        from project_workspace import ProjectWorkspace
        workspace = ProjectWorkspace(self.office).dashboard(self.owner, self.project)
        create_command = self.command(assignee_id=self.manager['id'], title=' Freigabe Süd 🚧 – Phase 1 ', details='Original prüfen.\nÜbernahme unverändert.\n')
        created = self.api.create(self.owner, self.project, create_command)
        self.now += timedelta(minutes=1)
        update_command = self.command(created, status='achieved')
        updated = self.api.update(self.owner, self.project, created['id'], update_command)
        self.now += timedelta(minutes=1)
        cancel_command = self.command(updated, status='cancelled', details='Begründet zurückgestellt.')
        cancelled = self.api.update(self.owner, self.project, created['id'], cancel_command)
        self.office.assign(self.owner, self.project, self.manager['id'], True)
        self.now += timedelta(minutes=1)
        reopen_command = self.command(cancelled, status='planned', due_date=None)
        reopened = self.api.update(self.owner, self.project, created['id'], reopen_command)
        empty_command = self.command(title='Abschlussprotokoll', due_date=None, assignee_id=None)
        empty_created = self.api.create(self.owner, self.project, empty_command)
        validate_integrity(self.office)
        return dict(schema_version=1, project_id=self.project, other_project_id=self.other_project,
                    actor=self.owner, workspace=workspace,
                    workspace_after_assignee_removed=ProjectWorkspace(self.office).dashboard(self.owner, self.project),
                    create_command=create_command, created=created, update_command=update_command, updated=updated,
                    cancel_command=cancel_command, cancelled=cancelled, reopen_command=reopen_command, reopened=reopened,
                    empty_command=empty_command, empty_created=empty_created,
                    history=self.api.history(self.owner, self.project, created['id']), listing=self.api.listing(self.owner, self.project))


class ProjectMilestoneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic-milestones-')
        self.addCleanup(self.temp.cleanup)
        self.f = MilestoneFixture(self.temp.name)
        self.addCleanup(self.f.office.db.close)
        self.office, self.api, self.owner, self.project = self.f.office, self.f.api, self.f.owner, self.f.project

    def problem(self, status, fn, *args):
        with self.assertRaises(Problem) as caught:
            fn(*args)
        self.assertEqual(caught.exception.status, status, caught.exception.message)
        return caught.exception

    def count(self):
        return tuple(self.office.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0] for table in TABLES)

    def test_full_history_and_original_receipts_survive_changes_without_side_effects(self):
        unchanged = {table: self.office.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]
                     for table in ('workspace_items', 'business_appointments', 'business_documents', 'business_time_entries')}
        result = self.f.export()
        self.assertEqual([item['status'] for item in result['history']['items']], ['planned', 'achieved', 'cancelled', 'planned'])
        self.assertEqual(self.api.create(self.owner, self.project, result['create_command']), result['created'])
        self.assertEqual(self.api.update(self.owner, self.project, result['created']['id'], result['update_command']), result['updated'])
        self.assertEqual(self.count(), (2, 5, 5))
        for table, count in unchanged.items():
            self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0], count)
        self.assertTrue(validate_integrity(self.office))

    def test_fresh_scoped_read_and_write_rights_apply_to_original_replay(self):
        body = self.f.command()
        created = self.api.create(self.f.manager, self.project, body)
        self.assertEqual(self.api.get(self.f.technician, self.project, created['id']), created)
        self.problem(403, self.api.create, self.f.technician, self.project, self.f.command())
        self.problem(404, self.api.listing, self.f.manager, self.f.other_project)
        BusinessFoundation(self.office).save_grant(self.owner, dict(request_id=uuid.uuid4().hex, user_id=self.f.manager['id'],
            permission='planning.read', scope=self.project, effect='deny', revision=0))
        self.problem(403, self.api.create, self.f.manager, self.project, body)
        self.problem(403, self.api.history, self.f.manager, self.project, created['id'])
        with self.office.db:
            self.office.db.execute('UPDATE users SET active=0 WHERE id=?', (self.f.technician['id'],))
        self.problem(401, self.api.get, self.f.technician, self.project, created['id'])

    def test_assignee_requires_current_team_unless_exact_previous_assignment_is_preserved(self):
        original = self.api.create(self.owner, self.project, self.f.command(assignee_id=self.f.manager['id']))
        self.office.assign(self.owner, self.project, self.f.manager['id'], True)
        updated = self.api.update(self.owner, self.project, original['id'], self.f.command(original, status='achieved'))
        self.assertEqual(updated['assignee_id'], self.f.manager['id'])
        self.problem(400, self.api.create, self.owner, self.project, self.f.command(assignee_id=self.f.manager['id']))
        cleared = self.api.update(self.owner, self.project, updated['id'], self.f.command(updated, assignee_id=None))
        self.problem(400, self.api.update, self.owner, self.project, original['id'], self.f.command(cleared, assignee_id=self.f.manager['id']))

    def test_strict_schema_and_dates_do_not_create_partial_records(self):
        body = self.f.command()
        for changes in ({'schema_version':True}, {'schema_version':2}, {'due_date':'2026-02-30'},
                        {'due_date':''}, {'assignee_id':''}, {'status':'done'}, {'title':' '*5},
                        {'title':'\ud800'}, {'details':'\udfff'},
                        {'title':'x'*201}, {'details':'x'*10001}, {'project_id':self.f.other_project}):
            with self.subTest(changes=changes):
                self.problem(400, self.api.create, self.owner, self.project, body | changes)
        self.assertEqual(self.count(), (0, 0, 0))

    def test_revision_conflict_is_definite_nonacceptance_but_request_collision_is_not(self):
        body = self.f.command(); initial = self.api.create(self.owner, self.project, body)
        changed = self.api.update(self.owner, self.project, initial['id'], self.f.command(initial, status='achieved'))
        error = self.problem(409, self.api.update, self.owner, self.project, initial['id'], self.f.command(initial, status='cancelled'))
        self.assertEqual(error.request_resolution, 'not_accepted')
        collision = self.problem(409, self.api.create, self.owner, self.project, body | {'title':'Andere Eingabe'})
        self.assertIsNone(collision.request_resolution)
        self.assertEqual(self.api.get(self.owner, self.project, initial['id']), changed)
        self.assertEqual(self.count(), (1, 2, 2))

    def test_late_failure_and_outer_transaction_rollback_retain_no_partial_record(self):
        with patch.object(self.office, 'audit', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.api.create(self.owner, self.project, self.f.command())
        self.assertEqual(self.count(), (0, 0, 0))
        with self.assertRaises(RuntimeError):
            with self.office.db:
                self.office.db.execute('BEGIN')
                self.api.create(self.owner, self.project, self.f.command())
                raise RuntimeError('Synthetic outer rollback')
        self.assertEqual(self.count(), (0, 0, 0))

    def test_immutable_rows_and_current_identity_are_protected(self):
        original = self.api.create(self.owner, self.project, self.f.command())
        for statement in ('UPDATE business_project_milestone_versions SET payload_json=payload_json',
                          'DELETE FROM business_project_milestone_versions',
                          'UPDATE business_project_milestone_requests SET result_json=result_json',
                          'DELETE FROM business_project_milestone_requests',
                          'DELETE FROM business_project_milestones',
                          'UPDATE business_project_milestones SET revision=revision'):
            with self.subTest(statement=statement), self.assertRaises(sqlite3.DatabaseError):
                with self.office.db:
                    self.office.db.execute(statement)
        self.assertEqual(self.api.get(self.owner, self.project, original['id']), original)

    def test_rehashed_history_column_tamper_does_not_become_a_valid_original(self):
        original = self.api.create(self.owner, self.project, self.f.command())
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_project_milestone_versions_update_guard')
            self.office.db.execute('UPDATE business_project_milestone_versions SET project_id=?', (self.f.other_project,))
        self.problem(409, self.api.get, self.owner, self.project, original['id'])
        with self.assertRaises((Problem, ValueError)):
            validate_integrity(self.office)

    def test_hidden_reserved_current_fields_are_rejected_before_metadata_merge(self):
        original = self.api.create(self.owner, self.project, self.f.command())
        stored = self.office.db.execute('SELECT payload_json FROM business_project_milestones').fetchone()[0]
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_project_milestones_update_guard')
        for field, value in (('id', 'f'*32), ('schema_version', 999), ('revision', 17)):
            with self.subTest(field=field):
                bad = json.loads(stored); bad[field] = value
                with self.office.db:
                    self.office.db.execute('UPDATE business_project_milestones SET payload_json=?', (json.dumps(bad),))
                self.problem(409, self.api.get, self.owner, self.project, original['id'])
                with self.assertRaises((Problem, ValueError)):
                    validate_integrity(self.office)
                with self.office.db:
                    self.office.db.execute('UPDATE business_project_milestones SET payload_json=?', (stored,))

    def test_original_replay_rejects_replacement_by_a_valid_later_revision(self):
        body = self.f.command()
        original = self.api.create(self.owner, self.project, body)
        revised = self.api.update(self.owner, self.project, original['id'], self.f.command(original, status='achieved'))
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_project_milestone_requests_update_guard')
            self.office.db.execute('UPDATE business_project_milestone_requests SET result_json=? WHERE request_id=?',
                                  (json.dumps(revised), body['request_id']))
        error = self.problem(409, self.api.create, self.owner, self.project, body)
        self.assertIsNone(error.request_resolution)
        with self.assertRaises((Problem, ValueError)):
            validate_integrity(self.office)

    def test_clock_adjustment_does_not_rewrite_creation_or_reject_valid_revision(self):
        original = self.api.create(self.owner, self.project, self.f.command())
        self.f.now -= timedelta(minutes=5)
        revised = self.api.update(self.owner, self.project, original['id'], self.f.command(original, status='achieved'))
        self.assertEqual(revised['created_at'], original['created_at'])
        self.assertLess(revised['updated_at'], original['updated_at'])
        self.assertTrue(validate_integrity(self.office))

    def test_historical_assignee_may_leave_team_but_must_still_exist(self):
        result = self.f.export()
        self.assertTrue(validate_integrity(self.office))
        self.assertEqual(result['history']['items'][0]['assignee_id'], self.f.manager['id'])
        with self.office.db:
            self.office.db.execute('DELETE FROM users WHERE id=?', (self.f.manager['id'],))
        with self.assertRaisesRegex(ValueError, 'Missing milestone author'):
            validate_integrity(self.office)

    def test_additive_migration_preserves_original_workspace_schema_and_rows(self):
        import business_schema
        from project_workspace import ProjectWorkspace
        specs = business_schema.registry()
        older_specs = tuple(spec for spec in specs if spec.name != 'business_project_milestones')
        with patch.object(business_schema, 'registry', return_value=older_specs):
            older = Office(Path(self.temp.name)/'older.sqlite3')
        self.addCleanup(older.db.close)
        actor = dict(id=older.add_user('older@example.test', 'Synthetic-older-password-123', 'owner'), role='owner')
        project = older.add_project(actor, 'Preserved original project', 'Preserved customer')
        workspace = ProjectWorkspace(older)
        original = workspace.save_item(actor, project, 'tasks', dict(request_id=uuid.uuid4().hex, title='Original task'))
        checksums = [tuple(row) for row in older.db.execute('SELECT module,version,checksum FROM business_schema_migrations ORDER BY module,version')]
        ddl = [tuple(row) for row in older.db.execute("SELECT name,sql FROM sqlite_master WHERE name IN ('workspace_items','workspace_versions','workspace_requests') ORDER BY name")]
        rows = {table: [tuple(row) for row in older.db.execute('SELECT * FROM ' + table)]
                for table in ('workspace_items', 'workspace_versions', 'workspace_requests', 'projects', 'customers')}
        business_schema.ensure_schema(older, registry=specs, activate=True)
        retained = [tuple(row) for row in older.db.execute("SELECT module,version,checksum FROM business_schema_migrations WHERE module!='business_project_milestones' ORDER BY module,version")]
        self.assertEqual(retained, checksums)
        self.assertEqual([tuple(row) for row in older.db.execute("SELECT name,sql FROM sqlite_master WHERE name IN ('workspace_items','workspace_versions','workspace_requests') ORDER BY name")], ddl)
        for table, values in rows.items():
            self.assertEqual([tuple(row) for row in older.db.execute('SELECT * FROM ' + table)], values)
        self.assertEqual(workspace.get_item(actor, project, 'tasks', original['id']), original)
        self.assertEqual(ProjectMilestones(older).listing(actor, project)['items'], [])

    def test_paused_planning_and_readonly_reject_all_writes_but_preserve_original_reads(self):
        import business_api
        import business_schema
        from business_organization import Organization
        body = self.f.command()
        original = self.api.create(self.owner, self.project, body)
        change = self.f.command(original, status='achieved')
        updated = self.api.update(self.owner, self.project, original['id'], change)
        organization = Organization(self.office)
        settings = organization.get(self.owner)
        modules = {key: dict(visible=value['visibility_override'], enabled=value['enabled'])
                   for key, value in settings['modules'].items()}
        modules['planning']['enabled'] = False
        organization.save(self.owner, dict(request_id=uuid.uuid4().hex, revision=settings['revision'], needs=settings['needs'], modules=modules))
        operations = ((self.api.create, (self.owner, self.project, body)),
                      (self.api.create, (self.owner, self.project, self.f.command())),
                      (self.api.update, (self.owner, self.project, original['id'], change)),
                      (self.api.update, (self.owner, self.project, original['id'], self.f.command(updated))))
        before = self.count()
        for function, args in operations:
            self.problem(423, function, *args)
        self.assertEqual(self.api.get(self.owner, self.project, original['id']), updated)
        self.assertEqual(self.api.history(self.owner, self.project, original['id'])['items'], [original, updated])
        settings = organization.get(self.owner); modules['planning']['enabled'] = True
        organization.save(self.owner, dict(request_id=uuid.uuid4().hex, revision=settings['revision'], needs=settings['needs'], modules=modules))
        business_schema.set_mode(self.office, 'legacy')
        for function, args in operations:
            self.problem(409, function, *args)
        route = '/business/projects/' + self.project + '/milestones/' + original['id']
        value, status, _ = business_api.dispatch(self.office, self.owner, route, 'GET', {})
        self.assertEqual((value, status), (updated, 200))
        self.assertEqual(self.count(), before)
        business_schema.set_mode(self.office, 'business')
        self.assertEqual(self.api.create(self.owner, self.project, body), original)
        self.assertEqual(self.api.update(self.owner, self.project, original['id'], change), updated)

    def test_actual_sqlite_backup_restore_retains_original_commands(self):
        from backup import backup
        from restore import restore
        result = self.f.export()
        archived = backup(Path(self.temp.name)/'milestones.sqlite3', Path(self.temp.name)/'backup.sqlite3')
        restored = Office(restore(archived, Path(self.temp.name)/'restored.sqlite3'))
        self.addCleanup(restored.db.close)
        api = ProjectMilestones(restored)
        self.assertEqual(api.history(self.owner, self.project, result['created']['id']), result['history'])
        self.assertEqual(api.create(self.owner, self.project, result['create_command']), result['created'])
        self.assertTrue(validate_integrity(restored))


if __name__ == '__main__':
    unittest.main()
