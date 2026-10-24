"""Disposable PostgreSQL acceptance for the schema-4 project/inbox package.

Reuse the release fixture by composition: importing this module must neither
connect to PostgreSQL nor discover the older CandidateRelease tests again.
The fixture's strict guard permits only the two named loopback test databases.
"""
import hashlib
import json
import time
import unittest
import uuid

from cryptography.fernet import Fernet
import psycopg
from psycopg import sql

from core import Problem, canonical, digest
from inbound_connectors import InboundConnectors
from inquiries import Inquiries
import plan_access
import plan_deletions
from project_workspace import ProjectWorkspace
from online import release
from online import test_release as fixture_module
from online.auth import Authentication, totp
from online.restore import restore
from online.store import PostgresOffice, SCHEMA_VERSION


V4_TABLES = frozenset((
    'plan_deletions', 'project_profiles', 'workspace_items',
    'workspace_versions', 'workspace_requests', 'inquiries', 'inquiry_requests',
    'inbound_import_tokens',
))
REVOKED_SESSION_TABLES = frozenset((
    'sessions', 'plan_sessions', 'auth_challenges', 'login_limits',
))


def request_id():
    return uuid.uuid4().hex


@unittest.skipUnless(fixture_module.DSN, 'SMARTPLAN_TEST_DSN is required for disposable PostgreSQL tests')
class WorkspaceRelease(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The existing fixture validates both DSNs before its first connection.
        fixture_module.CandidateRelease.setUpClass()

    @classmethod
    def tearDownClass(cls):
        fixture_module.CandidateRelease.tearDownClass()

    def setUp(self):
        self.fixture = fixture_module.CandidateRelease('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.source = fixture_module.DSN
        self.candidate = fixture_module.CANDIDATE
        self.actor, self.project = self.fixture.user, self.fixture.project
        self.assertEqual(SCHEMA_VERSION, 4)

    def seed_security(self):
        """Real TOTP enrollment, pending challenge, PDF and both grant kinds."""
        office = PostgresOffice(self.source)
        try:
            key = Fernet.generate_key()
            auth = Authentication(office, key)
            enrollment = auth.begin('release@example.test', 'Release-test-password-123', 'synthetic-release-ip')
            secret = enrollment['enrollment']['secret']
            logged_in = auth.finish(enrollment['challenge'], totp(secret, int(time.time() // 30)))
            pending = auth.begin('release@example.test', 'Release-test-password-123', 'synthetic-pending-ip')
            with office.lock, office.db:
                legacy = plan_access.issue(office, self.actor)['token']
                workspace = plan_access.issue(office, self.actor, workspace=True)['token']
                mfa = dict(office.db.execute('SELECT * FROM mfa WHERE user_id=?', (self.actor['id'],)).fetchone())
                pdfs = [dict(row) for row in office.db.execute(
                    'SELECT id,pdf,pdf_hash FROM reports WHERE pdf IS NOT NULL').fetchall()]
            self.assertTrue(pdfs)
            self.assertTrue(logged_in['recovery_codes'])
            return dict(key=key, secret=secret, normal=logged_in['token'], legacy=legacy,
                        workspace=workspace, recovery=logged_in['recovery_codes'],
                        challenge=pending['challenge'], mfa=mfa, pdfs=pdfs)
        finally:
            office.db.close()

    def assert_security_preserved(self, dsn, security, *, sessions=True):
        office = PostgresOffice(dsn)
        try:
            with office.lock, office.db:
                mfa = dict(office.db.execute('SELECT * FROM mfa WHERE user_id=?', (self.actor['id'],)).fetchone())
                self.assertEqual(mfa, security['mfa'])
                self.assertEqual(Fernet(security['key']).decrypt(mfa['secret'].encode()).decode(), security['secret'])
                self.assertEqual(json.loads(mfa['recovery']), [digest(code) for code in security['recovery']])
                pdfs = [dict(row) for row in office.db.execute(
                    'SELECT id,pdf,pdf_hash FROM reports WHERE pdf IS NOT NULL').fetchall()]
                self.assertEqual(pdfs, security['pdfs'])
                for row in pdfs:
                    self.assertTrue(bytes(row['pdf']).startswith(b'%PDF-'))
                    self.assertEqual(hashlib.sha256(row['pdf']).hexdigest(), row['pdf_hash'])
                if sessions:
                    self.assertEqual(office.user(security['normal']), self.actor)
                    for grant in ('legacy', 'workspace'):
                        self.assertEqual(plan_access.user(office, security[grant]), self.actor)
                    self.assertFalse(plan_access.allows_workspace(security['legacy']))
                    self.assertTrue(plan_access.allows_workspace(security['workspace']))
                    pending = office.db.execute('SELECT secret FROM auth_challenges WHERE token=?',
                                                (digest(security['challenge']),)).fetchone()
                    self.assertEqual(Fernet(security['key']).decrypt(pending['secret'].encode()).decode(), security['secret'])
                else:
                    checks = [lambda: office.user(security['normal'])]
                    checks.extend(lambda grant=grant: plan_access.user(office, security[grant])
                                  for grant in ('legacy', 'workspace'))
                    for check in checks:
                        with self.assertRaises(Problem) as rejected:
                            check()
                        self.assertEqual(rejected.exception.status, 401)
        finally:
            office.db.close()

    def seed_workspace(self):
        office = PostgresOffice(self.source)
        try:
            with office.lock, office.db:
                workspace = ProjectWorkspace(office)
                profile = workspace.save_profile(self.actor, self.project, dict(
                    request_id=request_id(), revision=0, description='Nur synthetische Abnahme.',
                    site_address='Musterweg 1', phase='execution'))
                task = workspace.save_item(self.actor, self.project, 'tasks', dict(
                    request_id=request_id(), title='Synthetisches Aufmaß', priority='high'))
                task = workspace.save_item(self.actor, self.project, 'tasks', dict(
                    request_id=request_id(), revision=task['revision'], status='in_progress'), task['id'])
                diary = workspace.save_item(self.actor, self.project, 'diary', dict(
                    request_id=request_id(), entry_date='2026-10-24',
                    work_performed='Fiktiven Raum vermessen.', crew_count=2))
                appointment = workspace.save_item(self.actor, self.project, 'appointments', dict(
                    request_id=request_id(), title='Synthetischer Vor-Ort-Termin',
                    start_at='2026-11-04T09:00:00+01:00', end_at='2026-11-04T10:00:00+01:00'))
                link = workspace.save_item(self.actor, self.project, 'links', dict(
                    request_id=request_id(), title='Fiktiver Dokumentverweis',
                    url='https://example.test/synthetic-document'))
                key = InboundConnectors(office).issue(self.actor, dict(
                    name='Synthetischer Gmail-Eingang', source_account='synthetic@example.test', expires_days=7))
                envelope = dict(source_account='synthetic@example.test', source_id='synthetic-release-message',
                                subject='Fiktive Projektanfrage', message='Nur synthetische Testdaten.',
                                sender_name='Fiktive Familie', sender_email='family@example.test',
                                received_at='2026-10-24T09:00:00+00:00')
                received = InboundConnectors(office).receive_gmail(key['token'], envelope)
                conversion_body = dict(request_id=request_id(), revision=1,
                                       project_name='Synthetisches Projekt aus Anfrage',
                                       customer={'name': 'Fiktive Familie', 'email': 'family@example.test'})
                conversion = Inquiries(office).convert(self.actor, received['id'], conversion_body)
                unconverted = Inquiries(office).create(self.actor, dict(
                    request_id=request_id(), subject='Zweite synthetische Anfrage',
                    message='Noch offen und keinem Projekt zugeordnet.'))
                live = office.plans(self.actor, self.project)[0]
                live = office.save_plan(self.actor, self.project, dict(
                    request_id=request_id(), revision=live['revision'],
                    title='Fiktives EG, zweite Version', walls=[]), live['id'])
                deleted_create = dict(request_id=request_id(), title='Absichtlich gelöschter Testplan', walls=[])
                deleted = office.save_plan(self.actor, self.project, deleted_create)
                deletion_body = dict(request_id=request_id(), id=deleted['id'],
                                     create_request_id=deleted_create['request_id'])
                deletion = plan_deletions.delete(office, self.actor, self.project, 'plan', deletion_body)
                token_row = dict(office.db.execute('SELECT * FROM inbound_import_tokens WHERE id=?', (key['id'],)).fetchone())
                return dict(profile=profile, tasks=task, diary=diary, appointments=appointment, links=link,
                            key=key, token_row=token_row, envelope=envelope, converted=conversion,
                            conversion_body=conversion_body, inquiry=unconverted, live=live,
                            deleted=deleted, deleted_create=deleted_create,
                            deletion=deletion, deletion_body=deletion_body)
        finally:
            office.db.close()

    def assert_workspace_preserved(self, dsn, data, *, revoked=False):
        office = PostgresOffice(dsn)
        try:
            with office.lock, office.db:
                workspace = ProjectWorkspace(office)
                self.assertEqual(workspace.profile(self.actor, self.project), data['profile'])
                for kind in ('tasks', 'diary', 'appointments', 'links'):
                    self.assertEqual(workspace.get_item(self.actor, self.project, kind, data[kind]['id']), data[kind])
                self.assertEqual(data['tasks']['revision'], 2)
                history = office.db.execute('SELECT revision FROM workspace_versions WHERE kind=? AND object_id=? '
                                            'ORDER BY revision', ('tasks', data['tasks']['id'])).fetchall()
                self.assertEqual([row[0] for row in history], [1, 2])
                converted = Inquiries(office).get(self.actor, data['converted']['inquiry']['id'])
                self.assertEqual(converted['status'], 'converted')
                self.assertEqual(converted['project_id'], data['converted']['project']['id'])
                self.assertEqual(office.project(self.actor, converted['project_id']), data['converted']['project'])
                self.assertEqual(Inquiries(office).convert(self.actor, converted['id'], data['conversion_body']),
                                 data['converted'])
                self.assertEqual(Inquiries(office).get(self.actor, data['inquiry']['id'])['status'], 'new')
                self.assertEqual(office.plan(self.actor, self.project, data['live']['id']), data['live'])
                self.assertEqual(plan_deletions.feed(office, self.actor, self.project), [data['deletion']])
                self.assertEqual(plan_deletions.delete(office, self.actor, self.project, 'plan', data['deletion_body']),
                                 data['deletion'])
                with self.assertRaises(Problem) as deleted:
                    office.plan(self.actor, self.project, data['deleted']['id'])
                self.assertEqual(deleted.exception.status, 410)
                with self.assertRaises(Problem) as retried_creation:
                    office.save_plan(self.actor, self.project, data['deleted_create'])
                self.assertEqual(retried_creation.exception.status, 410)
                self.assertEqual(office.db.execute('SELECT COUNT(*) FROM plan_versions WHERE id=?',
                                                  (data['deleted']['id'],)).fetchone()[0], 0)
                connector = InboundConnectors(office)
                token_row = dict(office.db.execute('SELECT * FROM inbound_import_tokens WHERE id=?',
                                                   (data['key']['id'],)).fetchone())
                if revoked:
                    self.assertIsNotNone(token_row.pop('revoked_at'))
                    old_row = dict(data['token_row'])
                    self.assertIsNone(old_row.pop('revoked_at'))
                    self.assertEqual(token_row, old_row)
                    with self.assertRaises(Problem) as rejected:
                        connector._credential(data['key']['token'], time.time())
                    self.assertEqual(rejected.exception.status, 401)
                else:
                    self.assertEqual(token_row, data['token_row'])
                    self.assertEqual(connector._credential(data['key']['token'], time.time())['id'], data['key']['id'])
        finally:
            office.db.close()

    def test_schema3_candidate_migrates_only_the_clone_and_preserves_legacy_credentials_and_pdf(self):
        security = self.seed_security()
        self.fixture.seed_imports()
        # Actually remove every v4 table, rather than relabeling a v4 database.
        with psycopg.connect(self.source) as connection:
            connection.execute(sql.SQL('DROP TABLE {}').format(
                sql.SQL(',').join(map(sql.Identifier, sorted(V4_TABLES)))))
            connection.execute('UPDATE smartplan_schema SET version=3')
        before = release.snapshot_fingerprint(self.source)
        self.assertTrue(V4_TABLES.isdisjoint(before))
        prepared = self.fixture.prepare()
        after = release.snapshot_fingerprint(self.candidate)
        self.assertEqual((prepared['source_schema'], prepared['target_schema']), (3, 4))
        self.assertEqual(prepared['tables'], before)
        self.assertEqual(set(after) - set(before), V4_TABLES)
        for table, fingerprint in before.items():
            if table != 'smartplan_schema':
                self.assertEqual(after[table], fingerprint, table)
        for table in V4_TABLES:
            self.assertEqual(after[table]['rows'], 0, table)
        self.assert_security_preserved(self.candidate, security)
        self.assertEqual(release.snapshot_fingerprint(self.source), before)

    def test_schema4_release_preserves_workspace_inbox_delivery_key_and_plan_deletion(self):
        security = self.seed_security()
        self.fixture.seed_imports()
        data = self.seed_workspace()
        before = release.snapshot_fingerprint(self.source)
        self.assertTrue(all(before[table]['rows'] > 0 for table in V4_TABLES))
        prepared = self.fixture.prepare()
        self.assertEqual((prepared['source_schema'], prepared['target_schema']), (4, 4))
        self.assertEqual(release.snapshot_fingerprint(self.candidate), before)
        self.assert_security_preserved(self.candidate, security)
        self.assert_workspace_preserved(self.candidate, data)
        self.assertEqual(release.snapshot_fingerprint(self.candidate), before)
        self.assertEqual(release.snapshot_fingerprint(self.source), before)

    def test_explicit_restore_retains_business_history_but_revokes_sessions_and_gmail_delivery_keys(self):
        security = self.seed_security()
        self.fixture.seed_imports()
        data = self.seed_workspace()
        before = release.snapshot_fingerprint(self.source)
        self.assertTrue(all(before[table]['rows'] > 0 for table in REVOKED_SESSION_TABLES))
        saved = release.backup(self.source, self.fixture.temp.name)
        restore(saved, self.source, self.candidate)
        restored = release.snapshot_fingerprint(self.candidate)
        self.assertEqual(set(restored), set(before))
        for table, fingerprint in before.items():
            if table in REVOKED_SESSION_TABLES:
                self.assertEqual(restored[table]['rows'], 0, table)
            elif table != 'inbound_import_tokens':
                self.assertEqual(restored[table], fingerprint, table)
        self.assertEqual(restored['inbound_import_tokens']['rows'], before['inbound_import_tokens']['rows'])
        self.assert_security_preserved(self.candidate, security, sessions=False)
        self.assert_workspace_preserved(self.candidate, data, revoked=True)
        self.assertEqual(release.snapshot_fingerprint(self.source), before)

    def test_corrupt_workspace_history_rejects_candidate_without_rewriting_the_source(self):
        data = self.seed_workspace()
        # Valid JSON and matching keys/revision, but the newest retained value
        # contradicts the current record. SQL constraints cannot detect this.
        corrupt = dict(data['tasks'], title='Verfälschte synthetische Historie')
        with psycopg.connect(self.source) as connection:
            connection.execute('UPDATE workspace_versions SET payload=%s WHERE kind=%s AND object_id=%s AND revision=%s',
                               (canonical(corrupt), 'tasks', data['tasks']['id'], 2))
        before = release.snapshot_fingerprint(self.source)
        with self.assertRaisesRegex(ValueError, 'Project record does not match its revision history'):
            self.fixture.prepare()
        self.assertEqual(release.snapshot_fingerprint(self.source), before)

    def test_restore_rejects_a_valid_dump_with_a_workspace_history_gap_before_revoking_any_credentials(self):
        self.seed_security()
        data = self.seed_workspace()
        office = PostgresOffice(self.source)
        try:
            with office.lock, office.db:
                ProjectWorkspace(office).save_item(self.actor, self.project, 'tasks', dict(
                    request_id=request_id(), revision=2, status='done'), data['tasks']['id'])
                office.db.execute('DELETE FROM workspace_versions WHERE kind=? AND object_id=? AND revision=?',
                                  ('tasks', data['tasks']['id'], 2))
        finally:
            office.db.close()
        before = release.snapshot_fingerprint(self.source)
        saved = release.backup(self.source, self.fixture.temp.name)
        with self.assertRaisesRegex(ValueError, 'Missing project revision'):
            restore(saved, self.source, self.candidate)
        # The target remains a separate, rejected copy. Session/key revocation
        # must not run before the logical integrity check has succeeded.
        self.assertEqual(release.snapshot_fingerprint(self.candidate), before)
        self.assertEqual(release.snapshot_fingerprint(self.source), before)


if __name__ == '__main__':
    unittest.main()
