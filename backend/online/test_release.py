"""Candidate release safety with real disposable PostgreSQL dumps/restores.

Never use a production DSN. The only permitted source/candidate names are
smartplan_check and smartplan_release_check on the same loopback PostgreSQL.
"""
import hashlib
import os
from pathlib import Path
import shlex
import stat
import struct
import tempfile
import unittest
import zlib
from types import SimpleNamespace
from unittest.mock import patch

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo

import plan_access
from online import release
from online.store import migrate, PostgresOffice, SCHEMA_VERSION
from online.plan_imports import PlanImports, CHUNK_SIZE
from online.restore import restore

DSN = os.environ.get('SMARTPLAN_TEST_DSN')
CANDIDATE = make_conninfo(DSN, dbname='smartplan_release_check') if DSN else None
V4_TABLES = ('plan_deletions', 'project_profiles', 'workspace_items', 'workspace_versions',
             'workspace_requests', 'inquiries', 'inquiry_requests', 'inbound_import_tokens')
V5_TABLES = ('inquiry_attachment_sets', 'inquiry_attachments',
             'inquiry_attachment_chunks', 'inquiry_attachment_limits')
TEST_SOURCE = 'host=127.0.0.1 port=55432 dbname=smartplan_check user=postgres'
TEST_CANDIDATE = make_conninfo(TEST_SOURCE, dbname='smartplan_release_check')


class ReleaseGuards(unittest.TestCase):
    def test_production_requires_same_standard_peer_cluster_without_hidden_credentials(self):
        source = 'host=/var/run/postgresql dbname=smartplan_online user=smartplan-online'
        target = make_conninfo(source, dbname='smartplan_online_candidate')
        release.validate_dsns(source, target)
        release.validate_dsns(make_conninfo(source, port=5432), make_conninfo(target, port=5432))
        for bad_source in (
                make_conninfo(source, host='127.0.0.1'),
                make_conninfo(source, hostaddr='203.0.113.4'),
                make_conninfo(source, port=55432),
                make_conninfo(source, user='postgres'),
                make_conninfo(source, password='synthetic-disallowed-value'),
                make_conninfo(source, options='-c search_path=other'),
                'service=untrusted dbname=smartplan_online'):
            with self.subTest(kind=tuple(conninfo_to_dict(bad_source))):
                with self.assertRaises((ValueError, RuntimeError)):
                    release.validate_dsns(bad_source, make_conninfo(bad_source, dbname='smartplan_online_candidate'))
        with self.assertRaises((ValueError, RuntimeError)):
            release.validate_dsns(source, source)

    def test_test_mode_never_allows_other_database_names_hosts_or_roles(self):
        release.validate_dsns(TEST_SOURCE, TEST_CANDIDATE, test_mode=True)
        release.validate_dsns(make_conninfo(TEST_SOURCE, password='synthetic-ci-only'),
                              make_conninfo(TEST_CANDIDATE, password='synthetic-ci-only'), test_mode=True)
        with self.assertRaises((ValueError, RuntimeError)):
            release.validate_dsns(make_conninfo(TEST_SOURCE, password='synthetic-ci-only'),
                                  make_conninfo(TEST_CANDIDATE, password='different-synthetic-ci-value'), test_mode=True)
        for source, target in (
                (make_conninfo(TEST_SOURCE, dbname='smartplan_online'), TEST_CANDIDATE),
                (TEST_SOURCE, make_conninfo(TEST_CANDIDATE, dbname='smartplan_other')),
                (TEST_SOURCE, make_conninfo(TEST_CANDIDATE, port=5432)),
                (make_conninfo(TEST_SOURCE, host='example.test'), make_conninfo(TEST_CANDIDATE, host='example.test')),
                (make_conninfo(TEST_SOURCE, user='smartplan-online'), make_conninfo(TEST_CANDIDATE, user='smartplan-online'))):
            with self.assertRaises((ValueError, RuntimeError)):
                release.validate_dsns(source, target, test_mode=True)

    def test_environment_update_preserves_other_bytes_and_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'service.env'
            prefix = '# Bestehende Einstellungen bleiben unverändert.\n'
            suffix = "SMARTPLAN_PUBLIC_HOST=office.example.test\nCUSTOM='with spaces and $literal'\n\n"
            path.write_text(prefix + 'SMARTPLAN_DATABASE_DSN=' + shlex.quote(TEST_SOURCE) + '\n' + suffix)
            path.chmod(0o640)
            before = path.stat()
            release.update_environment(path, 'smartplan_release_check', test_mode=True)
            after = path.stat()
            self.assertEqual((before.st_uid, before.st_gid, stat.S_IMODE(before.st_mode)),
                             (after.st_uid, after.st_gid, stat.S_IMODE(after.st_mode)))
            result = path.read_text()
            self.assertTrue(result.startswith(prefix))
            self.assertTrue(result.endswith(suffix))
            line = next(line for line in result.splitlines() if line.startswith('SMARTPLAN_DATABASE_DSN='))
            self.assertEqual(conninfo_to_dict(shlex.split(line.split('=', 1)[1])[0]), conninfo_to_dict(TEST_CANDIDATE))

    def test_ambiguous_or_unsafe_environment_is_never_partly_rewritten(self):
        canonical = 'SMARTPLAN_DATABASE_DSN=' + shlex.quote(TEST_SOURCE) + '\n'
        cases = (
            canonical + canonical,
            canonical + 'export ' + canonical,
            canonical + '  ' + canonical,
            'export ' + canonical,
            '  ' + canonical,
            'SMARTPLAN_PUBLIC_HOST=office.example.test\n',
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'service.env'
            for text in cases:
                path.write_text(text)
                path.chmod(0o640)
                with self.assertRaises((ValueError, RuntimeError)):
                    release.update_environment(path, 'smartplan_release_check', test_mode=True)
                self.assertEqual(path.read_text(), text)
            path.write_text(canonical)
            for mode in (0o660, 0o644, 0o602):
                path.chmod(mode)
                with self.assertRaises((ValueError, RuntimeError)):
                    release.update_environment(path, 'smartplan_release_check', test_mode=True)
                self.assertEqual(path.read_text(), canonical)
            path.chmod(0o640)
            link = Path(directory) / 'link.env'
            link.symlink_to(path)
            with self.assertRaises((ValueError, RuntimeError)):
                release.update_environment(link, 'smartplan_release_check', test_mode=True)
            for name in ('smartplan_check', '../smartplan_release_check', 'not a database'):
                with self.assertRaises((ValueError, RuntimeError)):
                    release.update_environment(path, name, test_mode=True)
                self.assertEqual(path.read_text(), canonical)

    def test_maintenance_blocks_the_complete_online_handler_and_keeps_other_routes(self):
        source = Path(__file__).resolve().parents[2] / 'deploy/hetzner/online/Caddyfile'
        original = source.read_text()
        maintenance = release.maintenance_config(original)
        self.assertIn('respond `{"error":"Serverupdate. Lokale Eingaben bleiben erhalten."}` 503', maintenance)
        self.assertIn('@online path /api/v1/* /health /ready', maintenance)
        self.assertNotIn('reverse_proxy 127.0.0.1:8766', maintenance)
        self.assertEqual(original[original.index('\n\t@application '):], maintenance[maintenance.index('\n\t@application '):])
        with self.assertRaises((ValueError, RuntimeError)):
            release.maintenance_config('unknown proxy configuration')


    def test_phase_publication_is_atomic_and_private_on_write_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'phase'
            release.atomic_write(path, b'verified\n')
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            with patch('online.release.os.replace', side_effect=OSError('Synthetic publication failure')):
                with self.assertRaises(OSError):
                    release.atomic_write(path, b'activating\n')
            self.assertEqual(path.read_text(), 'verified\n')
            self.assertEqual([item.name for item in Path(directory).iterdir()], ['phase'])
            release.atomic_write(path, b'activating\n')
            self.assertEqual(path.read_text(), 'activating\n')

    def test_failed_directory_fsync_can_leave_activation_marker_and_must_not_be_assumed_uncommitted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'phase'
            release.atomic_write(path, b'verified\n')
            real_fsync = os.fsync
            def fail_directory(descriptor):
                if stat.S_ISDIR(os.fstat(descriptor).st_mode):
                    raise OSError('Synthetic directory durability failure')
                return real_fsync(descriptor)
            with patch('online.release.os.fsync', side_effect=fail_directory):
                with self.assertRaises(OSError):
                    release.atomic_write(path, b'activating\n')
            self.assertEqual(path.read_text(), 'activating\n')
            self.assertEqual([item.name for item in Path(directory).iterdir()], ['phase'])


    def test_capacity_on_shared_filesystem_checks_combined_headroom_without_mutation(self):
        database = 64 * 1024 * 1024
        required = 3 * database + 512 * 1024 * 1024
        with tempfile.TemporaryDirectory() as directory:
            data, backups = Path(directory) / 'data', Path(directory) / 'backups'
            data.mkdir()
            backups.mkdir()
            (data / 'existing.data').write_bytes(b'database sentinel')
            (backups / 'existing.dump').write_bytes(b'backup sentinel')
            before = {item.relative_to(directory): item.read_bytes() for item in Path(directory).rglob('*') if item.is_file()}
            with patch('online.release.psycopg.connect', side_effect=AssertionError('Capacity check must not contact any database')) as connect, \
                    patch('online.release.backup', side_effect=AssertionError('Capacity check must not create a dump')) as backup, \
                    patch('online.release.shutil.disk_usage') as usage:
                for available, succeeds in ((required, True), (required - 1, False), (required + database, True)):
                    usage.return_value = SimpleNamespace(free=available)
                    if succeeds:
                        release.check_capacity(data, backups, database)
                    else:
                        with self.assertRaises(RuntimeError):
                            release.check_capacity(data, backups, database)
                connect.assert_not_called()
                backup.assert_not_called()
            self.assertEqual({item.relative_to(directory): item.read_bytes() for item in Path(directory).rglob('*') if item.is_file()}, before)

    def test_capacity_on_separate_filesystems_requires_both_individual_reserves(self):
        database = 64 * 1024 * 1024
        margin = 256 * 1024 * 1024
        minimum_data, minimum_backup = 2 * database + margin, database + margin
        data = SimpleNamespace(stat=lambda: SimpleNamespace(st_dev=1))
        backups = SimpleNamespace(stat=lambda: SimpleNamespace(st_dev=2))
        with patch('online.release.Path', side_effect=lambda value: data if value == 'data' else backups), \
                patch('online.release.shutil.disk_usage') as usage, \
                patch('online.release.psycopg.connect', side_effect=AssertionError('Capacity check must be read-only')) as connect, \
                patch('online.release.restore_dump', side_effect=AssertionError('Capacity check must not restore')) as restore:
            for data_free, backup_free, succeeds in (
                    (minimum_data, minimum_backup, True),
                    (minimum_data - 1, minimum_backup, False),
                    (minimum_data, minimum_backup - 1, False)):
                usage.side_effect = lambda path: SimpleNamespace(free=data_free if path is data else backup_free)
                if succeeds:
                    release.check_capacity('data', 'backups', database)
                else:
                    with self.assertRaises(RuntimeError):
                        release.check_capacity('data', 'backups', database)
            connect.assert_not_called()
            restore.assert_not_called()

    def test_capacity_rejects_invalid_database_sizes_before_inspecting_filesystems(self):
        with patch('online.release.shutil.disk_usage') as usage, \
                patch('online.release.psycopg.connect', side_effect=AssertionError('No database calls allowed')) as connect:
            for size in (0, -1, True, False, 1.5, '1024', None):
                with self.subTest(size_type=type(size).__name__):
                    with self.assertRaises(ValueError):
                        release.check_capacity('/does-not-exist', '/does-not-exist-either', size)
            usage.assert_not_called()
            connect.assert_not_called()


@unittest.skipUnless(DSN, 'Disposable SMARTPLAN_TEST_DSN required')
class CandidateRelease(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        release.validate_dsns(DSN, CANDIDATE, test_mode=True)
        with psycopg.connect(DSN, autocommit=True) as connection:
            if connection.execute("SELECT 1 FROM pg_database WHERE datname='smartplan_release_check'").fetchone():
                raise RuntimeError('Disposable candidate already exists; preserve and inspect it before this test run.')
            connection.execute('CREATE DATABASE smartplan_release_check TEMPLATE template0')

    @classmethod
    def tearDownClass(cls):
        with psycopg.connect(DSN, autocommit=True) as connection:
            connection.execute('DROP DATABASE smartplan_release_check')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='smartplan-release-test-')
        for dsn in (DSN, CANDIDATE):
            with psycopg.connect(dsn, autocommit=True) as connection:
                connection.execute('DROP SCHEMA public CASCADE')
                connection.execute('CREATE SCHEMA public')
        migrate(DSN)
        office = PostgresOffice(DSN)
        try:
            office.add_user('release@example.test', 'Release-test-password-123', 'owner')
            token = office.login('release@example.test', 'Release-test-password-123')
            self.user = office.user(token)
            project = office.add_project(self.user, 'Fiktives Releaseprojekt', 'Fiktiver Kunde')
            self.project = project
            report = office.draft(self.user, project, 'Servicebericht', 'Ausschließlich synthetische Prüfung.')
            office.sign(self.user, report['id'], report['content_hash'], 'Fiktiver Unterzeichner', [[[0.1, 0.2], [0.8, 0.7]]])
            office.save_plan(self.user, project, {'title': 'Fiktives EG', 'walls': [], 'request_id': 'c' * 32})
            with office.lock, office.db:
                plan_access.issue(office, self.user)
        finally:
            office.db.close()

    def tearDown(self):
        self.temp.cleanup()

    def source_v1(self):
        self.source_v2()
        with psycopg.connect(DSN) as connection:
            connection.execute('DROP TABLE plan_versions,plan_requests,plan_sessions')
            connection.execute('UPDATE smartplan_schema SET version=1')

    def source_v2(self):
        self.source_v3()
        with psycopg.connect(DSN) as connection:
            connection.execute('DROP TABLE IF EXISTS plan_import_chunks,plan_imports')
            connection.execute('UPDATE smartplan_schema SET version=2')

    def source_v3(self):
        with psycopg.connect(DSN) as connection:
            connection.execute(psycopg.sql.SQL('DROP TABLE IF EXISTS {}').format(
                psycopg.sql.SQL(',').join(map(psycopg.sql.Identifier, V5_TABLES + V4_TABLES))))
            connection.execute('UPDATE smartplan_schema SET version=3')

    def prepare(self):
        return release.prepare(DSN, CANDIDATE, self.temp.name, test_mode=True)

    def seed_imports(self):
        # A real small PNG with a large uncompressed text chunk spans two upload
        # chunks. The bytes, source metadata and results must travel together.
        def png(padding=0):
            def chunk(kind, payload):
                return (struct.pack('>I', len(payload)) + kind + payload +
                        struct.pack('>I', zlib.crc32(kind + payload)))
            return (b'\x89PNG\r\n\x1a\n' +
                    chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)) +
                    chunk(b'tEXt', b'synthetic\x00' + b'x' * padding) +
                    chunk(b'IDAT', zlib.compress(b'\x00\x12\x34\x56')) + chunk(b'IEND', b''))
        source, preview = png(CHUNK_SIZE + 41), png()
        checksum = hashlib.sha256(source).hexdigest()
        result = {'schema_version': 1, 'status': 'needs_review',
                  'source': {'sha256': checksum, 'selected_page': 0}, 'calibration': {'status': 'unknown'}}
        office = PostgresOffice(DSN)
        ids = {}
        try:
            imports = PlanImports(office)
            with office.lock, office.db:
                for index, status in enumerate(('needs_review', 'uploading', 'failed', 'running'), 1):
                    job = imports.create(self.user, self.project,
                        dict(request_id=str(index) * 32, filename='synthetischer-plan.png',
                             media_type='image/png', size=len(source), sha256=checksum,
                             page=0, title='Fiktiver ' + status))
                    ids[status] = job['id']
                    if status == 'uploading':
                        imports.put_chunk(self.user, self.project, job['id'], 1, source[CHUNK_SIZE:])
                        continue
                    for number, start in enumerate(range(0, len(source), CHUNK_SIZE)):
                        imports.put_chunk(self.user, self.project, job['id'], number, source[start:start + CHUNK_SIZE])
                    imports.complete_upload(self.user, self.project, job['id'])
                    claimed = imports.claim()
                    self.assertEqual(claimed['id'], job['id'])
                    if status == 'needs_review':
                        imports.publish(job['id'], claimed['lease_token'], preview=preview, result=result)
                    elif status == 'failed':
                        imports.fail(job['id'], claimed['lease_token'], 'synthetic_failure')
        finally:
            office.db.close()
        return ids, source, preview, result

    def test_restore_migrates_v1_without_changing_source_or_existing_rows(self):
        self.source_v1()
        before = release.snapshot_fingerprint(DSN)
        result = self.prepare()
        self.assertEqual((result['source_schema'], result['target_schema']), (1, SCHEMA_VERSION))
        self.assertEqual(result['tables'], before)
        self.assertEqual(release.snapshot_fingerprint(DSN), before)
        candidate = release.snapshot_fingerprint(CANDIDATE)
        self.assertEqual({key: value for key, value in candidate.items() if key in before and key != 'smartplan_schema'},
                         {key: value for key, value in before.items() if key != 'smartplan_schema'})
        self.assertEqual(candidate['plan_versions']['rows'], 0)
        self.assertEqual(candidate['plan_requests']['rows'], 0)
        self.assertEqual(candidate['plan_sessions']['rows'], 0)
        self.assertEqual(candidate['plan_imports']['rows'], 0)
        self.assertEqual(candidate['plan_import_chunks']['rows'], 0)
        archive = Path(result['backup'])
        self.assertTrue(archive.is_file())
        self.assertEqual(stat.S_IMODE(archive.stat().st_mode), 0o600)
        self.assertEqual(Path(str(archive) + '.sha256').read_text().split('  ', 1)[0], hashlib.sha256(archive.read_bytes()).hexdigest())
        office = PostgresOffice(CANDIDATE)
        office.db.close()

    def test_v2_roundtrip_preserves_signed_pdf_plan_retry_records_and_device_grants(self):
        self.source_v2()
        before = release.snapshot_fingerprint(DSN)
        result = self.prepare()
        self.assertEqual((result['source_schema'], result['target_schema']), (2, SCHEMA_VERSION))
        self.assertEqual(release.snapshot_fingerprint(DSN), before)
        candidate = release.snapshot_fingerprint(CANDIDATE)
        self.assertEqual({key: value for key, value in candidate.items() if key in before and key != 'smartplan_schema'},
                         {key: value for key, value in before.items() if key != 'smartplan_schema'})
        self.assertEqual(candidate['plan_imports']['rows'], 0)
        self.assertEqual(candidate['plan_import_chunks']['rows'], 0)
        self.assertEqual(release.sequence_state(CANDIDATE), release.sequence_state(DSN))
        self.assertEqual(before['plan_versions']['rows'], 1)
        self.assertEqual(before['plan_requests']['rows'], 1)
        self.assertEqual(before['plan_sessions']['rows'], 1)

    def test_v3_roundtrip_preserves_original_chunks_partial_uploads_leases_and_results(self):
        ids, source, preview, _ = self.seed_imports()
        self.source_v3()
        before = release.snapshot_fingerprint(DSN)
        prepared = self.prepare()
        self.assertEqual((prepared['source_schema'], prepared['target_schema']), (3, SCHEMA_VERSION))
        self.assertEqual(release.snapshot_fingerprint(DSN), before)
        candidate = release.snapshot_fingerprint(CANDIDATE)
        self.assertEqual({key: value for key, value in candidate.items() if key in before and key != 'smartplan_schema'},
                         {key: value for key, value in before.items() if key != 'smartplan_schema'})
        for table in V4_TABLES + V5_TABLES:
            self.assertEqual(candidate[table]['rows'], 0, table)
        self.assertEqual(before['plan_imports']['rows'], 4)
        self.assertEqual(before['plan_import_chunks']['rows'], 7)
        office = PostgresOffice(CANDIDATE)
        try:
            imports = PlanImports(office)
            with office.lock, office.db:
                self.assertEqual(imports.source(self.user, self.project, ids['needs_review'])[0], source)
                self.assertEqual(imports.source(self.user, self.project, ids['failed'])[0], source)
                self.assertEqual(imports.artifact(self.user, self.project, ids['needs_review'], 'preview')[0], preview)
                self.assertEqual(imports.get(self.user, self.project, ids['uploading'])['uploaded_chunks'], [1])
                self.assertEqual(imports.get(self.user, self.project, ids['running'])['status'], 'running')
        finally:
            office.db.close()

    def test_corrupt_import_bytes_or_artifacts_reject_candidate_without_changing_source(self):
        ids, _, _, _ = self.seed_imports()
        for kind in ('chunk', 'preview', 'result'):
            with self.subTest(kind=kind):
                statement, import_id = {
                    'chunk': ("UPDATE plan_import_chunks SET data=repeat('x',size)::bytea WHERE import_id=%s AND chunk_index=1", ids['uploading']),
                    'preview': ("UPDATE plan_imports SET preview='\\x00'::bytea WHERE id=%s", ids['needs_review']),
                    'result': ("UPDATE plan_imports SET result='{}' WHERE id=%s", ids['needs_review']),
                }[kind]
                with psycopg.connect(CANDIDATE, autocommit=True) as connection:
                    connection.execute('DROP SCHEMA public CASCADE')
                    connection.execute('CREATE SCHEMA public')
                with psycopg.connect(DSN) as connection:
                    connection.execute(statement, (import_id,))
                before = release.snapshot_fingerprint(DSN)
                with self.assertRaises((ValueError, RuntimeError)):
                    self.prepare()
                self.assertEqual(release.snapshot_fingerprint(DSN), before)
                # Reset only the test import tables and retain all other data.
                with psycopg.connect(DSN) as connection:
                    connection.execute('DELETE FROM plan_import_chunks')
                    connection.execute('DELETE FROM plan_imports')
                ids, _, _, _ = self.seed_imports()

    def test_explicit_restore_verifies_imports_and_revokes_sessions_without_losing_sources(self):
        ids, source, preview, _ = self.seed_imports()
        before = release.snapshot_fingerprint(DSN)
        saved = release.backup(DSN, self.temp.name)
        restore(saved, DSN, CANDIDATE)
        candidate = release.snapshot_fingerprint(CANDIDATE)
        self.assertEqual(release.snapshot_fingerprint(DSN), before)
        for table in ('plan_imports', 'plan_import_chunks', 'plan_versions', 'plan_requests'):
            self.assertEqual(candidate[table], before[table])
        for table in ('sessions', 'plan_sessions', 'auth_challenges', 'login_limits'):
            self.assertEqual(candidate[table]['rows'], 0)
        office = PostgresOffice(CANDIDATE)
        try:
            imports = PlanImports(office)
            with office.lock, office.db:
                self.assertEqual(imports.source(self.user, self.project, ids['needs_review'])[0], source)
                self.assertEqual(imports.artifact(self.user, self.project, ids['needs_review'], 'preview')[0], preview)
        finally:
            office.db.close()

    def test_explicit_restore_upgrades_v1_and_v2_backups_without_changing_active_source(self):
        for version in (2, 1):
            with self.subTest(version=version):
                if version == 2:
                    self.source_v2()
                else:
                    self.source_v1()
                with psycopg.connect(CANDIDATE, autocommit=True) as connection:
                    connection.execute('DROP SCHEMA public CASCADE')
                    connection.execute('CREATE SCHEMA public')
                before = release.snapshot_fingerprint(DSN)
                saved = release.backup(DSN, self.temp.name)
                restore(saved, DSN, CANDIDATE)
                self.assertEqual(release.snapshot_fingerprint(DSN), before)
                office = PostgresOffice(CANDIDATE)
                try:
                    with office.lock, office.db:
                        self.assertEqual(office.db.execute('SELECT version FROM smartplan_schema').fetchone()[0], SCHEMA_VERSION)
                        self.assertEqual(office.db.execute('SELECT COUNT(*) FROM plan_imports').fetchone()[0], 0)
                        self.assertEqual(office.db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0], 0)
                        self.assertEqual(office.db.execute('SELECT COUNT(*) FROM reports').fetchone()[0], 1)
                finally:
                    office.db.close()

    def test_fingerprint_covers_bytes_nulls_duplicates_and_ignores_physical_row_order(self):
        with psycopg.connect(DSN) as connection:
            connection.execute('CREATE TABLE release_probe(label TEXT, payload BYTEA)')
            connection.execute('INSERT INTO release_probe VALUES(%s,%s),(%s,%s),(%s,%s)',
                               ('Büro Ω', bytes([0, 255]), None, None, None, None))
        first = release.snapshot_fingerprint(DSN)['release_probe']
        self.assertEqual(first['rows'], 3)
        with psycopg.connect(DSN) as connection:
            connection.execute('DELETE FROM release_probe')
            connection.execute('INSERT INTO release_probe VALUES(%s,%s),(%s,%s),(%s,%s)',
                               (None, None, None, None, 'Büro Ω', bytes([0, 255])))
        self.assertEqual(release.snapshot_fingerprint(DSN)['release_probe'], first)
        with psycopg.connect(DSN) as connection:
            connection.execute("UPDATE release_probe SET label='Anderer Inhalt' WHERE label IS NOT NULL")
        changed = release.snapshot_fingerprint(DSN)['release_probe']
        self.assertEqual(changed['rows'], first['rows'])
        self.assertNotEqual(changed['digest'], first['digest'])

    def test_existing_candidate_and_foreign_source_client_are_rejected(self):
        before = release.snapshot_fingerprint(DSN)
        with psycopg.connect(CANDIDATE) as connection:
            connection.execute('CREATE TABLE preserve_me(value TEXT)')
            connection.execute("INSERT INTO preserve_me VALUES('keep')")
        with self.assertRaises((ValueError, RuntimeError)):
            self.prepare()
        self.assertEqual(release.snapshot_fingerprint(DSN), before)
        with psycopg.connect(CANDIDATE) as connection:
            self.assertEqual(connection.execute('SELECT value FROM preserve_me').fetchone()[0], 'keep')
            connection.execute('DROP TABLE preserve_me')
        with psycopg.connect(DSN, application_name='unexpected-release-test-client'):
            with self.assertRaises((ValueError, RuntimeError)):
                self.prepare()
        self.assertEqual(release.snapshot_fingerprint(DSN), before)

    def test_bad_checksum_or_restore_failure_never_changes_the_source(self):
        before = release.snapshot_fingerprint(DSN)
        real_backup = release.backup
        def corrupt(*args, **kwargs):
            saved = real_backup(*args, **kwargs)
            Path(str(saved) + '.sha256').write_text('0' * 64 + '  ' + saved.name + '\n')
            return saved
        with patch('online.release.backup', side_effect=corrupt):
            with self.assertRaises((ValueError, RuntimeError)):
                self.prepare()
        self.assertEqual(release.snapshot_fingerprint(DSN), before)
        self.assertEqual(release.snapshot_fingerprint(CANDIDATE), {})
        with patch('online.release.restore_dump', side_effect=RuntimeError('Synthetic interrupted restore')):
            with self.assertRaises(RuntimeError):
                self.prepare()
        self.assertEqual(release.snapshot_fingerprint(DSN), before)
        self.assertEqual(release.snapshot_fingerprint(CANDIDATE), {})

    def test_migration_failure_or_invalid_pdf_retains_original_database(self):
        self.source_v1()
        before = release.snapshot_fingerprint(DSN)
        with patch('online.release.migrate', side_effect=RuntimeError('Synthetic migration interruption')):
            with self.assertRaises(RuntimeError):
                self.prepare()
        self.assertEqual(release.snapshot_fingerprint(DSN), before)
        with psycopg.connect(CANDIDATE, autocommit=True) as connection:
            connection.execute('DROP SCHEMA public CASCADE')
            connection.execute('CREATE SCHEMA public')
        with psycopg.connect(DSN) as connection:
            connection.execute("UPDATE reports SET pdf='\\x00'::bytea WHERE pdf IS NOT NULL")
        corrupt = release.snapshot_fingerprint(DSN)
        with self.assertRaises((ValueError, RuntimeError)):
            self.prepare()
        self.assertEqual(release.snapshot_fingerprint(DSN), corrupt)
