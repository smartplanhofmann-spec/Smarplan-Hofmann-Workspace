"""Authenticated deletion/cancellation, physical active-data purge and retries."""
import json
import unittest
from unittest.mock import patch

import test_plan_imports as imports_fixture
import test_online as pg_fixture
import test_admin_api as desktop_fixture
from core import Problem
from online.plan_imports import PlanImports, LeaseLost, validate_integrity
from online.store import PostgresOffice, migrate, SCHEMA_VERSION


class DeletionApiTests(unittest.TestCase):
    setUp = imports_fixture.PlanImportApiTests.setUp
    tearDown = imports_fixture.PlanImportApiTests.tearDown
    open_app = imports_fixture.PlanImportApiTests.open_app
    call = imports_fixture.PlanImportApiTests.call
    manifest = imports_fixture.PlanImportApiTests.manifest
    upload = imports_fixture.PlanImportApiTests.upload
    publish = imports_fixture.PlanImportApiTests.publish

    @property
    def plans(self):
        return '/projects/' + self.project + '/plans'

    @property
    def feed(self):
        return '/projects/' + self.project + '/plan-deletions'

    def create_plan(self, request='1' * 32, title='Synthetic private drawing'):
        data = {'title': title, 'walls': [{'id': 'w', 'points': [[0, 0], [20, 30]]}], 'request_id': request}
        return self.call('POST', self.plans, data, status=201).json, data

    def test_manual_delete_purges_versions_and_cached_payloads_without_touching_other_plans(self):
        plan, creation = self.create_plan()
        update = {'title': 'Private second revision', 'walls': [], 'revision': 1, 'request_id': '2' * 32}
        self.call('POST', self.plans + '/' + plan['id'], update)
        other, _ = self.create_plan('3' * 32, 'Other original stays')
        before = self.office.db.execute('SELECT result FROM plan_requests WHERE request_id=?', ('3' * 32,)).fetchone()[0]
        request = {'request_id': '4' * 32, 'id': plan['id']}
        receipt = self.call('POST', self.plans + '/delete', request).json
        self.assertEqual(self.call('POST', self.plans + '/delete', request).json, receipt)
        self.assertEqual((receipt['status'], receipt['kind'], receipt['id']), ('deleted', 'plan', plan['id']))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM plan_versions WHERE id=?', (plan['id'],)).fetchone()[0], 0)
        for row in self.office.db.execute('SELECT result FROM plan_requests WHERE request_id IN (?,?)', ('1' * 32, '2' * 32)):
            self.assertTrue(json.loads(row[0])['deleted'])
            self.assertNotIn('walls', json.loads(row[0]))
            self.assertNotIn('title', json.loads(row[0]))
        self.assertEqual(self.office.db.execute('SELECT result FROM plan_requests WHERE request_id=?', ('3' * 32,)).fetchone()[0], before)
        self.assertEqual(self.call('GET', self.plans).json, [other])
        self.call('GET', self.plans + '/' + plan['id'], status=410)
        self.call('POST', self.plans, creation, status=410)
        self.call('POST', self.plans + '/' + plan['id'], update, status=410)
        self.assertEqual(self.office.db.execute("SELECT COUNT(*) FROM audit WHERE action='plan.deleted'").fetchone()[0], 1)
        self.assertEqual(self.call('GET', self.feed).json[0]['id'], plan['id'])

    def test_cancellation_before_creation_blocks_late_create_and_cached_retry_for_both_kinds(self):
        for kind, collection, creation in (
                ('plan', self.plans, {'request_id': '5' * 32, 'title': 'Never uploaded', 'walls': []}),
                ('import', self.base, self.manifest(imports_fixture.png(), request_id='6' * 32))):
            with self.subTest(kind=kind):
                request = {'request_id': ('7' if kind == 'plan' else '8') * 32,
                           'create_request_id': creation['request_id']}
                first = self.call('POST', collection + '/delete', request).json
                self.assertIsNone(first['id'])
                self.assertTrue(first['deleted'])
                self.assertEqual(self.call('POST', collection + '/delete', request).json, first)
                self.call('POST', collection, creation, status=410)
                self.call('POST', collection, creation, status=410)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM plan_versions').fetchone()[0], 0)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM plan_imports').fetchone()[0], 0)

    def test_lost_manifest_response_cancel_purges_chunks_and_blocks_future_upload(self):
        source = imports_fixture.png()
        manifest = self.manifest(source)
        first = self.call('POST', self.base, manifest, status=201).json
        path = self.base + '/' + first['id']
        self.call('PUT', path + '/chunks/0', source, mime='application/octet-stream')
        request = {'request_id': '9' * 32, 'create_request_id': manifest['request_id']}
        receipt = self.call('POST', self.base + '/delete', request).json
        self.assertEqual(receipt['id'], first['id'])
        self.assertEqual(self.call('POST', self.base + '/delete', request).json, receipt)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM plan_import_chunks').fetchone()[0], 0)
        self.call('POST', self.base, manifest, status=410)
        self.call('PUT', path + '/chunks/0', source, mime='application/octet-stream', status=410)
        self.call('POST', path + '/complete', {}, status=410)
        self.call('GET', path + '/source', status=410)
        self.assertEqual(self.call('GET', self.base).json, [])
        self.assertTrue(validate_integrity(self.office))

    def test_running_import_delete_invalidates_lease_and_cannot_resurrect_active_bytes(self):
        path, job = self.upload()
        imports = PlanImports(self.office)
        with self.office.lock, self.office.db:
            claimed = imports.claim()
        self.call('POST', self.base + '/delete', {'request_id': 'b' * 32, 'id': job['id']})
        with self.office.lock, self.office.db:
            for operation in (lambda: imports.fail(job['id'], claimed['lease_token']),
                              lambda: imports.release(job['id'], claimed['lease_token']),
                              lambda: imports.publish(job['id'], claimed['lease_token'], preview=imports_fixture.png(), result={})):
                with self.assertRaises(LeaseLost):
                    operation()
            private = imports._status(imports._row(job['id']))
            self.assertEqual(private['status'], 'deleted')
            self.assertNotIn('filename', private)
            self.assertIsNone(imports.claim())
        for suffix in ('', '/source', '/preview', '/result'):
            self.call('GET', path + suffix, status=410)
        self.assertTrue(validate_integrity(self.office))

    def test_published_import_purges_source_preview_result_but_not_another_same_hash_import(self):
        _, deleted = self.upload()
        self.publish(deleted['id'])
        other_path, other = self.upload(request_id='c' * 32)
        self.call('POST', self.base + '/delete', {'request_id': 'd' * 32, 'id': deleted['id']})
        row = self.office.db.execute('SELECT * FROM plan_imports WHERE id=?', (deleted['id'],)).fetchone()
        for key in ('preview', 'result', 'preview_sha256', 'result_sha256', 'lease_token', 'lease_until'):
            self.assertIsNone(row[key])
        self.assertEqual((row['filename'], row['title']), ('', ''))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM plan_import_chunks WHERE import_id=?', (deleted['id'],)).fetchone()[0], 0)
        self.assertEqual(self.call('GET', other_path + '/source').data, imports_fixture.png())
        self.assertEqual(self.call('GET', self.base).json[0]['id'], other['id'])
        self.assertTrue(validate_integrity(self.office))

    def test_target_mismatch_revision_conflict_and_request_reuse_do_not_delete(self):
        first, _ = self.create_plan()
        second, _ = self.create_plan('2' * 32)
        route = self.plans + '/delete'
        self.call('POST', route, {'request_id': '3' * 32, 'id': first['id'], 'create_request_id': '2' * 32}, status=409)
        self.call('POST', route, {'request_id': '3' * 32, 'id': first['id'], 'revision': 2}, status=409)
        request = {'request_id': '3' * 32, 'id': first['id'], 'revision': 1}
        self.call('POST', route, request)
        self.call('POST', route, {**request, 'id': second['id']}, status=409)
        self.assertEqual(self.call('GET', self.plans).json, [second])

    def test_delete_and_feed_require_fresh_role_project_and_offline_credentials(self):
        plan, _ = self.create_plan()
        tech_id = self.office.add_user('tech@example.test', 'Technician-password-123', 'technician')
        tech = self.office.login('tech@example.test', 'Technician-password-123')
        route = self.plans + '/delete'
        request = {'request_id': '4' * 32, 'id': plan['id']}
        self.call('POST', route, request, token=None, status=401)
        self.call('POST', route, request, token=tech, status=404)
        self.office.assign(self.owner, self.project, tech_id)
        offline = self.call('POST', '/offline/access', {}, token=tech, status=201).json['token']
        self.call('POST', route, request, token=offline)
        self.call('GET', self.feed, token=offline)
        self.office.assign(self.owner, self.project, tech_id, remove=True)
        self.call('POST', route, request, token=offline, status=404)
        self.office.assign(self.owner, self.project, tech_id)
        with self.office.db:
            self.office.db.execute('UPDATE users SET password=? WHERE id=?', ('changed', tech_id))
        self.call('GET', self.feed, token=offline, status=401)
        accountant_id = self.office.add_user('accounts@example.test', 'Accountant-password-123', 'accountant')
        accountant = self.office.login('accounts@example.test', 'Accountant-password-123')
        self.office.assign(self.owner, self.project, accountant_id)
        self.call('GET', self.feed, token=accountant)
        self.call('POST', route, request, token=accountant, status=403)
        other = self.office.add_project(self.owner, 'Other', 'Synthetic')
        self.call('GET', '/projects/' + other + '/plans/' + plan['id'], status=404)

    def test_unknown_create_cancellation_is_actor_scoped_and_private_to_creator(self):
        self.call('POST', self.plans + '/delete', {'request_id': '1' * 32, 'create_request_id': '2' * 32})
        tech_id = self.office.add_user('tech@example.test', 'Technician-password-123', 'technician')
        tech = self.office.login('tech@example.test', 'Technician-password-123')
        self.office.assign(self.owner, self.project, tech_id)
        self.assertEqual(self.call('GET', self.feed, token=tech).json, [])
        created = self.call('POST', self.plans, {'request_id': '2' * 32, 'title': 'Independent actor', 'walls': []}, token=tech, status=201).json
        self.assertEqual(self.call('GET', self.plans).json[0]['id'], created['id'])

    def test_failed_delete_transaction_restores_tombstone_and_active_original_bytes(self):
        path, job = self.upload()
        with patch.object(self.office, 'audit', side_effect=RuntimeError('Synthetic interrupted delete')):
            self.call('POST', self.base + '/delete', {'request_id': 'e' * 32, 'id': job['id']}, status=500)
        self.assertEqual(self.call('GET', path + '/source').data, imports_fixture.png())
        self.assertEqual(self.call('GET', self.feed).json, [])
        self.assertTrue(validate_integrity(self.office))

    def test_backup_integrity_rejects_resurrected_cached_wall_data_after_delete(self):
        plan, _ = self.create_plan()
        self.call('POST', self.plans + '/delete', {'request_id': '2' * 32, 'id': plan['id']})
        with self.office.db:
            self.office.db.execute('UPDATE plan_requests SET result=? WHERE user_id=? AND request_id=?',
                (json.dumps({'id': plan['id'], 'kind': 'plan', 'deleted': True, 'walls': ['Synthetic private wall']}),
                 self.owner_id, '1' * 32))
        with self.assertRaisesRegex(ValueError, 'cached drawing payload'):
            validate_integrity(self.office)

    def test_backup_integrity_rejects_resurrected_original_chunk_after_delete(self):
        _, job = self.upload()
        self.call('POST', self.base + '/delete', {'request_id': '2' * 32, 'id': job['id']})
        source = imports_fixture.png()
        with self.office.db:
            self.office.db.execute('INSERT INTO plan_import_chunks(import_id,chunk_index,data,sha256,size) VALUES(?,?,?,?,?)',
                                   (job['id'], 0, source, imports_fixture.sha(source), len(source)))
        with self.assertRaisesRegex(ValueError, 'active source'):
            validate_integrity(self.office)


class DesktopDeletionTests(unittest.TestCase):
    setUp = desktop_fixture.AdminApiTests.setUp
    tearDown = desktop_fixture.AdminApiTests.tearDown
    request = desktop_fixture.AdminApiTests.request
    login = desktop_fixture.AdminApiTests.login
    project = desktop_fixture.AdminApiTests.project

    def test_real_desktop_http_cancel_late_create_and_delete_cached_create(self):
        project = self.project()
        plans = '/api/projects/' + project + '/plans'
        request = {'request_id': '1' * 32, 'create_request_id': '2' * 32}
        receipt = self.request(plans + '/delete', self.owner, request)
        self.assertEqual(self.request(plans + '/delete', self.owner, request), receipt)
        self.request(plans, self.owner, {'request_id': '2' * 32, 'title': 'Late', 'walls': []}, status=410)
        creation = {'request_id': '3' * 32, 'title': 'Stored', 'walls': []}
        created = self.request(plans, self.owner, creation, status=201)
        self.request(plans + '/delete', self.owner, {'request_id': '4' * 32, 'create_request_id': '3' * 32})
        self.request(plans, self.owner, creation, status=410)
        self.request(plans + '/' + created['id'], self.owner, status=410)
        self.assertEqual(self.request(plans, self.owner), [])
        self.assertEqual(len(self.request('/api/projects/' + project + '/plan-deletions', self.owner)), 2)


@unittest.skipUnless(pg_fixture.DSN, 'Disposable SMARTPLAN_TEST_DSN required')
class PostgresDeletionTests(unittest.TestCase):
    setUp = pg_fixture.OnlineApiTests.setUp
    tearDown = pg_fixture.OnlineApiTests.tearDown
    request = pg_fixture.OnlineApiTests.request
    login = pg_fixture.OnlineApiTests.login

    def test_other_connection_cancels_lost_manifest_and_invalidates_existing_worker_lease(self):
        token = self.login()['token']
        project = self.request('/projects', {'name': 'Deletion', 'customer': 'Synthetic'}, token, 201).json['id']
        imports = PlanImports(self.office)
        source = imports_fixture.png()
        manifest = {'request_id': '1' * 32, 'filename': 'private.png', 'media_type': 'image/png', 'size': len(source),
                    'sha256': imports_fixture.sha(source), 'page': 0, 'title': 'Private original'}
        with self.office.lock, self.office.db:
            actor = self.office.user(token)
            job = imports.create(actor, project, manifest)
            imports.put_chunk(actor, project, job['id'], 0, source)
            imports.complete_upload(actor, project, job['id'])
            lease = imports.claim()
        second = PostgresOffice(pg_fixture.DSN)
        try:
            with second.lock, second.db:
                receipt = PlanImports(second).delete(second.user(token), project,
                           {'request_id': '2' * 32, 'create_request_id': manifest['request_id']})
            self.assertEqual(receipt['id'], job['id'])
            with self.office.lock, self.office.db:
                with self.assertRaises(LeaseLost):
                    imports.publish(job['id'], lease['lease_token'], preview=source, result={})
                with self.assertRaises(Problem) as gone:
                    imports.create(actor, project, manifest)
                self.assertEqual(gone.exception.status, 410)
                self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM plan_import_chunks WHERE import_id=?', (job['id'],)).fetchone()[0], 0)
                self.assertTrue(validate_integrity(self.office))
        finally:
            second.db.close()

    def test_additive_migration_from_schema3_preserves_manual_plan_and_creates_deletion_table(self):
        token = self.login()['token']
        project = self.request('/projects', {'name': 'Migration', 'customer': 'Synthetic'}, token, 201).json['id']
        plans = '/projects/' + project + '/plans'
        plan = self.request(plans, {'title': 'Kept', 'walls': []}, token, 201).json
        with self.office.lock, self.office.db:
            self.office.db.execute('DROP TABLE plan_deletions')
            self.office.db.execute('UPDATE smartplan_schema SET version=3')
        migrate(pg_fixture.DSN)
        migrate(pg_fixture.DSN)
        self.assertEqual(self.office.db.execute('SELECT version FROM smartplan_schema').fetchone()[0], SCHEMA_VERSION)
        self.assertEqual(self.request(plans + '/' + plan['id'], token=token).json, plan)
        self.request(plans + '/delete', {'request_id': '3' * 32, 'id': plan['id']}, token)
        self.request(plans + '/' + plan['id'], token=token, status=410)

    def test_concurrent_create_and_cancel_never_leave_a_live_plan_or_import(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        import plan_deletions
        token = self.login()['token']
        project = self.request('/projects', {'name': 'Create cancel race', 'customer': 'Synthetic'}, token, 201).json['id']
        for kind, create_id, delete_id in (('plan', '4' * 32, '5' * 32), ('import', '6' * 32, '7' * 32)):
            barrier = threading.Barrier(2)
            def operation(action):
                office = PostgresOffice(pg_fixture.DSN)
                try:
                    barrier.wait(timeout=5)
                    with office.lock, office.db:
                        actor = office.user(token)
                        if action == 'delete':
                            return plan_deletions.delete(office, actor, project, kind,
                                                        {'request_id': delete_id, 'create_request_id': create_id})
                        try:
                            if kind == 'plan':
                                return office.save_plan(actor, project, {'request_id': create_id, 'title': 'Race', 'walls': []})
                            source = imports_fixture.png()
                            return PlanImports(office).create(actor, project, {'request_id': create_id, 'filename': 'race.png',
                                'title': 'Race', 'media_type': 'image/png', 'size': len(source),
                                'sha256': imports_fixture.sha(source), 'page': 0})
                        except Problem as error:
                            self.assertEqual(error.status, 410)
                            return {'deleted': True}
                finally:
                    office.db.close()
            with self.subTest(kind=kind), ThreadPoolExecutor(max_workers=2) as executor:
                outcomes = list(executor.map(operation, ('create', 'delete')))
                self.assertTrue(outcomes[1]['deleted'])
                actor = self.office.user(token)
                self.assertEqual(self.office.plans(actor, project), [])
                self.assertEqual(PlanImports(self.office).list(actor, project), [])
                self.assertTrue(validate_integrity(self.office))


if __name__ == '__main__':
    unittest.main(verbosity=2)
