"""Real bound PostgreSQL milestone history, privacy links, migration and restore."""
from concurrent.futures import ThreadPoolExecutor
import threading
import unittest
from unittest.mock import patch
import uuid

import business_schema
from business_project_milestones import ProjectMilestones
from core import Problem
from online import release, test_business_company_handover_pg as bound
from online.store import PostgresOffice, migrate
from online.test_postgres_accounting_components_integration import disposable_restore, evidence_for, approve
from privacy_case_sources import inventory


def command(**changes):
    value = dict(schema_version=1, request_id=uuid.uuid4().hex,
                 title=' Meilenstein 🚧 ', details='Unveränderte Zeile\r\nZweite Zeile\n',
                 due_date='2026-12-01', assignee_id=None, status='planned')
    value.update(changes)
    return value


@unittest.skipUnless(bound.fixture.fixture.DSN, 'Guarded disposable loopback PostgreSQL required')
class ProjectMilestonesPostgres(unittest.TestCase):
    setUp = bound.CompanyHandoverPostgres.setUp
    reopen = bound.CompanyHandoverPostgres.reopen
    login = bound.CompanyHandoverPostgres.login
    call = bound.CompanyHandoverPostgres.call

    def original_workspace(self):
        project = self.office.add_project(self.owner, 'Synthetic milestone project', customer='Synthetic customer')
        task = self.call('POST', '/projects/'+project+'/tasks',
                         dict(request_id=uuid.uuid4().hex, title='Unchanged original task'), status=201).json
        return project, task

    def assert_original_task(self, project, task):
        self.assertEqual(self.call('GET', '/projects/'+project+'/tasks/'+task['id']).json, task)
        self.assertEqual(self.call('GET', '/projects/'+project+'/tasks/'+task['id']+'/history').json,
                         dict(items=[task]))

    def test_concurrent_original_privacy_reassignment_and_actual_restore(self):
        project, task = self.original_workspace()
        users = []
        for label in ('former', 'current'):
            identifier = self.office.add_user(label+'-milestone@example.test', 'Synthetic-password-123', 'technician')
            self.office.assign(self.owner, project, identifier)
            users.append(identifier)
        manager_id = self.office.add_user('middle-author@example.test', 'Synthetic-password-123', 'manager')
        self.office.assign(self.owner, project, manager_id)
        manager = dict(self.office.db.execute('SELECT * FROM users WHERE id=?', (manager_id,)).fetchone())
        path = '/business/projects/'+project+'/milestones'
        body = command(assignee_id=users[0])
        barrier = threading.Barrier(2)

        def create(_):
            office = PostgresOffice(self.runtime)
            try:
                barrier.wait(timeout=10)
                return ProjectMilestones(office).create(self.owner, project, body)
            finally:
                office.db.close()

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(create, range(2)))
        original = results[0]
        self.assertEqual(original, results[1])
        self.assertEqual(self.call('POST', path, body, status=201).json, original)
        complete_body = command(revision=1, assignee_id=users[0], status='achieved')
        complete = ProjectMilestones(self.office).update(manager, project, original['id'], complete_body)
        reassign_body = command(revision=2, assignee_id=users[1], status='planned')
        current = self.call('POST', path+'/'+original['id'], reassign_body).json
        expected = [original, complete, current]
        self.office.assign(self.owner, project, users[0], remove=True)
        self.office.assign(self.owner, project, manager_id, remove=True)
        former = dict(self.office.db.execute('SELECT * FROM users WHERE id=?', (users[0],)).fetchone())
        with self.assertRaises(Problem) as denied:
            ProjectMilestones(self.office).get(former, project, original['id'])
        self.assertEqual(denied.exception.status, 404)
        history = self.call('GET', path+'/'+original['id']+'/history').json
        self.assertEqual(history['items'], expected)
        self.assert_original_task(project, task)
        old_sources = inventory(self.office, self.owner, 'user', users[0])['sources']
        revisions = {row['primary_key']['revision'] for row in old_sources
                     if row['table']=='business_project_milestone_versions'
                     and row['primary_key']['milestone_id']==original['id']}
        self.assertEqual(revisions, {1, 2})
        self.assertFalse(any(row['table']=='business_project_milestones' and
                            row['primary_key'].get('id')==original['id'] for row in old_sources))
        author_sources = inventory(self.office, self.owner, 'user', manager_id)['sources']
        self.assertEqual({row['primary_key']['revision'] for row in author_sources
                          if row['table']=='business_project_milestone_versions'
                          and row['primary_key']['milestone_id']==original['id']}, {2})
        self.assertTrue(business_schema.validate_integrity(self.office))
        self.office.db.close()
        with disposable_restore(self.runtime) as (target, runtime, report):
            operator = PostgresOffice(target)
            try:
                approve(operator, evidence_for(operator, report))
            finally:
                operator.db.close()
            restored = PostgresOffice(runtime)
            try:
                service = ProjectMilestones(restored)
                self.assertEqual(service.create(self.owner, project, body), original)
                self.assertEqual(service.update(self.owner, project, original['id'], reassign_body), current)
                with self.assertRaises(Problem):
                    service.update(manager, project, original['id'], complete_body)
                self.assertEqual(service.history(self.owner, project, original['id'])['items'], expected)
                restored_sources = inventory(restored, self.owner, 'user', users[0])['sources']
                self.assertEqual([row for row in restored_sources if row['table'].startswith('business_project_milestone')],
                                 [row for row in old_sources if row['table'].startswith('business_project_milestone')])
                restored_author_sources = inventory(restored, self.owner, 'user', manager_id)['sources']
                self.assertEqual([row for row in restored_author_sources if row['table'].startswith('business_project_milestone')],
                                 [row for row in author_sources if row['table'].startswith('business_project_milestone')])
                self.assertTrue(business_schema.validate_integrity(restored))
            finally:
                restored.db.close()

    def test_additive_postgres_migration_keeps_existing_workspace_rows_and_schema(self):
        self.office.db.close()
        full = business_schema.registry()
        prior = tuple(spec for spec in full if spec.name != 'business_project_milestones')
        with patch.object(business_schema, 'registry', return_value=prior), \
             patch.object(business_schema, 'MODULE_NAMES', tuple(spec.name for spec in prior)):
            self.setUp()
            project, task = self.original_workspace()
            before = release.snapshot_fingerprint(bound.fixture.fixture.DSN)
            self.office.db.close()
        migrate(bound.fixture.fixture.DSN, owner_role='smartplan-migrator',
                compatibility_mode='business', require_business_modules=True)
        after = release.snapshot_fingerprint(bound.fixture.fixture.DSN)
        for table, fingerprint in before.items():
            if table not in ('business_schema_migrations', 'business_schema_state', 'business_schema_events'):
                self.assertEqual(after[table], fingerprint, table)
        release.secure_database(bound.fixture.fixture.DSN, test_mode=True)
        self.reopen()
        self.assert_original_task(project, task)
        result = self.call('POST', '/business/projects/'+project+'/milestones', command(), status=201).json
        self.assertEqual(result['revision'], 1)
        self.assertTrue(business_schema.validate_integrity(self.office))
