"""Real disposable PostgreSQL acceptance for schema-6 and legacy attachments.

No production DSN is accepted. Fixture composition intentionally discovers only
this class's tests, not the older release or workspace acceptance classes.
"""
import hashlib
import unittest

import psycopg
from psycopg import sql

from core import Problem
from inquiry_attachments import CHUNK_SIZE, InquiryAttachments
import plan_deletions
from online.plan_imports import PlanImports
from online import release
from online import test_release as base_fixture
from online import test_release_workspace as workspace_fixture
from online.restore import restore
from online.store import PostgresOffice, SCHEMA_VERSION, migrate


ATTACHMENT_TABLES = frozenset(base_fixture.V5_TABLES)
INTEGRATION_TABLES = frozenset(base_fixture.V6_TABLES)
BUSINESS_TABLES = frozenset(base_fixture.V7_TABLES)
RESTORE_RESET_TABLES = frozenset((
    'sessions', 'plan_sessions', 'auth_challenges', 'login_limits', 'inquiry_attachment_limits',
))


@unittest.skipUnless(base_fixture.DSN, 'SMARTPLAN_TEST_DSN is required for disposable PostgreSQL tests')
class AttachmentRelease(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base_fixture.CandidateRelease.setUpClass()

    @classmethod
    def tearDownClass(cls):
        base_fixture.CandidateRelease.tearDownClass()

    def setUp(self):
        self.fixture = workspace_fixture.WorkspaceRelease('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.source, self.candidate = self.fixture.source, self.fixture.candidate
        self.actor, self.project = self.fixture.actor, self.fixture.project
        self.assertEqual(SCHEMA_VERSION, 7)

    def seed_attachments(self):
        security = self.fixture.seed_security()
        _, original, small_png, _ = self.fixture.fixture.seed_imports()
        workspace = self.fixture.seed_workspace()
        inquiry = workspace['converted']['inquiry']['id']
        project = workspace['converted']['project']['id']
        token = workspace['key']['token']
        bodies = dict(ready_image=original, ready_pdf=security['pdfs'][0]['pdf'],
                      partial_image=original, deleted_image=small_png)
        descriptors = [dict(source_attachment_id=kind, filename=kind + ('.pdf' if kind == 'ready_pdf' else '.png'),
                            media_type='application/pdf' if kind == 'ready_pdf' else 'image/png',
                            size=len(content), sha256=hashlib.sha256(content).hexdigest())
                       for kind, content in bodies.items()]
        manifest = dict(source_account=workspace['envelope']['source_account'],
                        source_id=workspace['envelope']['source_id'], attachments=descriptors)
        office = PostgresOffice(self.source)
        try:
            attachments = InquiryAttachments(office)
            announced = attachments.announce(token, manifest)
            files = {value['source_attachment_id']: value for value in announced['files']}
            self.assertEqual(announced['chunk_size'], CHUNK_SIZE)
            self.assertGreater(len(original), CHUNK_SIZE)
            for kind in ('ready_image', 'ready_pdf', 'deleted_image'):
                content = bodies[kind]
                for index, start in enumerate(range(0, len(content), CHUNK_SIZE)):
                    attachments.put_chunk(token, files[kind]['id'], index, content[start:start + CHUNK_SIZE])
                self.assertEqual(attachments.complete(token, files[kind]['id'])['status'], 'ready')
            # Preserve a real resumable transfer with an out-of-order tail.
            attachments.put_chunk(token, files['partial_image']['id'], 1, original[CHUNK_SIZE:])
            attachments.remove_inquiry(self.actor, inquiry, files['deleted_image']['id'])
            live_copy = attachments.copy_to_plan(self.actor, project, files['ready_image']['id'], dict(
                request_id=workspace_fixture.request_id(), page=0, title='Synthetischer Anhang als Planquelle'))
            deleted_request = workspace_fixture.request_id()
            deleted_copy = attachments.copy_to_plan(self.actor, project, files['ready_image']['id'], dict(
                request_id=deleted_request, page=0, title='Absichtlich gelöschte synthetische Plankopie'))
            with office.lock, office.db:
                plan_deletions.delete(office, self.actor, project, 'import', dict(
                    request_id=workspace_fixture.request_id(), id=deleted_copy['id'], create_request_id=deleted_request))
            self.assertEqual(attachments.content_inquiry(self.actor, inquiry, files['ready_image']['id'])[0], original)
            return dict(security=security, workspace=workspace, inquiry=inquiry, project=project,
                        token=token, bodies=bodies, descriptors=descriptors, manifest=manifest,
                        files=files, live_copy=live_copy, deleted_copy=deleted_copy)
        finally:
            office.db.close()

    def assert_attachments_preserved(self, dsn, data):
        office = PostgresOffice(dsn)
        try:
            attachments = InquiryAttachments(office)
            summary = attachments.for_inquiry(self.actor, data['inquiry'])
            self.assertEqual((summary['status'], summary['expected_count'], summary['ready_count'], summary['deleted_count']),
                             ('uploading', 4, 2, 1))
            self.assertEqual(summary['total_bytes'], sum(len(content) for content in data['bodies'].values()))
            files = {value['source_attachment_id']: value for value in summary['files']}
            self.assertEqual(set(files), {'ready_image', 'ready_pdf', 'partial_image'})
            descriptors = {value['source_attachment_id']: value for value in data['descriptors']}
            for kind, value in files.items():
                self.assertEqual(value['id'], data['files'][kind]['id'])
                self.assertEqual({key: value[key] for key in descriptors[kind]}, descriptors[kind])
            project = attachments.for_project(self.actor, data['project'])
            self.assertEqual(project['pending_count'], 1)
            self.assertEqual(project['expected_count'], 4)
            self.assertEqual({value['id'] for value in project['files']}, {value['id'] for value in files.values()})
            for kind in ('ready_image', 'ready_pdf'):
                identifier = files[kind]['id']
                for content, metadata in (
                        attachments.content_inquiry(self.actor, data['inquiry'], identifier),
                        attachments.content_project(self.actor, data['project'], identifier)):
                    self.assertEqual(content, data['bodies'][kind])
                    self.assertEqual(hashlib.sha256(content).hexdigest(), metadata['sha256'])
            for kind, status in (('partial_image', 409), ('deleted_image', 410)):
                with self.assertRaises(Problem) as unavailable:
                    attachments.content_inquiry(self.actor, data['inquiry'], data['files'][kind]['id'])
                self.assertEqual(unavailable.exception.status, status)
            with office.lock, office.db:
                partial = office.db.execute('SELECT chunk_index,data FROM inquiry_attachment_chunks WHERE attachment_id=?',
                                            (data['files']['partial_image']['id'],)).fetchall()
                self.assertEqual([(row['chunk_index'], bytes(row['data'])) for row in partial],
                                 [(1, data['bodies']['partial_image'][CHUNK_SIZE:])])
                self.assertEqual(office.db.execute('SELECT COUNT(*) FROM inquiry_attachment_chunks WHERE attachment_id=?',
                                                  (data['files']['deleted_image']['id'],)).fetchone()[0], 0)
                imports = PlanImports(office)
                self.assertEqual(imports.source(self.actor, data['project'], data['live_copy']['id'])[0], data['bodies']['ready_image'])
                with self.assertRaises(Problem) as removed_copy:
                    imports.get(self.actor, data['project'], data['deleted_copy']['id'])
                self.assertEqual(removed_copy.exception.status, 410)
        finally:
            office.db.close()

    def corrupt_ready_chunk(self, data, *, update_chunk_hash=False):
        identifier = data['files']['ready_image']['id']
        with psycopg.connect(self.source) as connection:
            original = bytes(connection.execute('SELECT data FROM inquiry_attachment_chunks '
                                               'WHERE attachment_id=%s AND chunk_index=0', (identifier,)).fetchone()[0])
            altered = bytes([original[0] ^ 1]) + original[1:]
            if update_chunk_hash:
                connection.execute('UPDATE inquiry_attachment_chunks SET data=%s,sha256=%s '
                                   'WHERE attachment_id=%s AND chunk_index=0',
                                   (altered, hashlib.sha256(altered).hexdigest(), identifier))
            else:
                connection.execute('UPDATE inquiry_attachment_chunks SET data=%s WHERE attachment_id=%s AND chunk_index=0',
                                   (altered, identifier))

    def test_schema4_candidate_preserves_all_old_business_data_and_adds_only_empty_attachment_tables(self):
        security = self.fixture.seed_security()
        self.fixture.fixture.seed_imports()
        workspace = self.fixture.seed_workspace()
        self.fixture.fixture.source_version(4)
        before = release.snapshot_fingerprint(self.source)
        sequences = release.sequence_state(self.source)
        self.assertTrue((ATTACHMENT_TABLES | INTEGRATION_TABLES | BUSINESS_TABLES).isdisjoint(before))
        prepared = self.fixture.fixture.prepare()
        after = release.snapshot_fingerprint(self.candidate)
        self.assertEqual((prepared['source_schema'], prepared['target_schema']), (4, SCHEMA_VERSION))
        self.assertEqual(prepared['tables'], before)
        self.assertEqual(set(after) - set(before), ATTACHMENT_TABLES | INTEGRATION_TABLES | BUSINESS_TABLES)
        for table, fingerprint in before.items():
            if table != 'smartplan_schema':
                self.assertEqual(after[table], fingerprint, table)
        for table in (ATTACHMENT_TABLES | INTEGRATION_TABLES | BUSINESS_TABLES) - base_fixture.CONTROL_TABLES:
            self.assertEqual(after[table]['rows'], 0, table)
        self.fixture.assert_security_preserved(self.candidate, security)
        self.fixture.assert_workspace_preserved(self.candidate, workspace)
        with psycopg.connect(self.candidate) as connection:
            self.assertEqual(connection.execute('SELECT version FROM smartplan_schema').fetchone()[0], SCHEMA_VERSION)
            byte_columns = connection.execute(
                "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='public' "
                "AND table_name='inquiry_attachment_chunks' AND data_type='bytea'").fetchone()[0]
            self.assertEqual(byte_columns, 1)
        # Re-running current migrations is data-idempotent as well.
        migrate(self.candidate)
        self.assertEqual(release.snapshot_fingerprint(self.candidate), after)
        self.assertEqual(release.sequence_state(self.candidate), sequences)
        self.assertEqual(release.snapshot_fingerprint(self.source), before)

    def test_current_release_preserves_ready_partial_deleted_originals_and_independent_plan_copies(self):
        data = self.seed_attachments()
        before = release.snapshot_fingerprint(self.source)
        self.assertTrue(all(before[table]['rows'] > 0 for table in ATTACHMENT_TABLES))
        prepared = self.fixture.fixture.prepare()
        self.assertEqual((prepared['source_schema'], prepared['target_schema']), (SCHEMA_VERSION, SCHEMA_VERSION))
        self.assertEqual(prepared['tables'], before)
        self.assertEqual(release.snapshot_fingerprint(self.candidate), before)
        self.fixture.assert_security_preserved(self.candidate, data['security'])
        self.fixture.assert_workspace_preserved(self.candidate, data['workspace'])
        self.assert_attachments_preserved(self.candidate, data)
        self.assertEqual(release.snapshot_fingerprint(self.candidate), before)
        self.assertEqual(release.snapshot_fingerprint(self.source), before)

    def test_explicit_restore_preserves_attachment_data_but_revokes_credentials_and_resets_only_traffic_limits(self):
        data = self.seed_attachments()
        before = release.snapshot_fingerprint(self.source)
        self.assertTrue(all(before[table]['rows'] > 0 for table in RESTORE_RESET_TABLES))
        saved = release.backup(self.source, self.fixture.fixture.temp.name)
        restore(saved, self.source, self.candidate)
        after = release.snapshot_fingerprint(self.candidate)
        self.assertEqual(set(after), set(before))
        for table, fingerprint in before.items():
            if table in RESTORE_RESET_TABLES:
                self.assertEqual(after[table]['rows'], 0, table)
            elif table not in ('inbound_import_tokens', 'business_restore_state'):
                self.assertEqual(after[table], fingerprint, table)
        self.fixture.assert_security_preserved(self.candidate, data['security'], sessions=False)
        self.fixture.assert_workspace_preserved(self.candidate, data['workspace'], revoked=True)
        self.assert_attachments_preserved(self.candidate, data)
        office = PostgresOffice(self.candidate)
        try:
            with self.assertRaises(Problem) as revoked:
                InquiryAttachments(office).announce(data['token'], data['manifest'])
            self.assertEqual(revoked.exception.status, 401)
        finally:
            office.db.close()
        self.assertEqual(release.snapshot_fingerprint(self.candidate), after)
        self.assertEqual(release.snapshot_fingerprint(self.source), before)

    def test_corrupt_ready_chunk_rejects_candidate_without_modifying_any_source_row(self):
        data = self.seed_attachments()
        self.corrupt_ready_chunk(data)
        before = release.snapshot_fingerprint(self.source)
        with self.assertRaisesRegex(ValueError, 'Stored attachment chunk failed integrity validation'):
            self.fixture.fixture.prepare()
        self.assertEqual(release.snapshot_fingerprint(self.source), before)

    def test_restore_rejects_self_consistent_chunks_with_wrong_original_hash_before_resetting_credentials(self):
        data = self.seed_attachments()
        self.corrupt_ready_chunk(data, update_chunk_hash=True)
        before = release.snapshot_fingerprint(self.source)
        saved = release.backup(self.source, self.fixture.fixture.temp.name)
        with self.assertRaisesRegex(ValueError, 'Invalid canonical inquiry attachments'):
            restore(saved, self.source, self.candidate)
        # Dump checksum, SQL constraints and per-chunk hashes all pass; the
        # immutable original hash must still reject this separate target.
        self.assertEqual(release.snapshot_fingerprint(self.candidate), before)
        self.assertEqual(release.snapshot_fingerprint(self.source), before)


if __name__ == '__main__':
    unittest.main()
