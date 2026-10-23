"""Synthetic-only durability, lease and path tests; standard-library deps only."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from plan_import import store


class ImportStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='synthetic-plan-store-')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.now = 1000.0
        self.root = self.base / 'private-output'
        self.store = store.ImportStore(self.root, clock=lambda: self.now)
        self.input = self.base / 'synthetic.pdf'
        self.bytes = b'%PDF-1.7\nSynthetic fixture, not a real plan.\n'
        self.input.write_bytes(self.bytes)

    def capture(self, request='fixture-1', **kwargs):
        return self.store.capture(self.input, request_id=request, **kwargs)

    def claim(self, job, worker='synthetic-worker', seconds=90):
        return self.store.claim(worker_id=worker, job_id=job['job_id'], lease_seconds=seconds)

    def complete(self, job, **kwargs):
        return self.store.complete(job['job_id'], job['lease_token'],
                                   derived=kwargs.get('derived', {'preview.png': b'synthetic preview',
                                                                  'review.html': b'<p>Synthetic review</p>'}),
                                   recognition=kwargs.get('recognition', {'kind': 'synthetic', 'walls': []}))

    def count(self, table):
        with sqlite3.connect(self.store.database) as connection:
            return connection.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]

    def test_original_capture_is_immutable_private_durable_and_idempotent(self):
        captured = self.capture(page=3)
        self.assertEqual(captured['status'], 'queued')
        self.assertEqual(captured['page'], 3)
        self.assertEqual(captured['sha256'], hashlib.sha256(self.bytes).hexdigest())
        self.assertEqual(captured['media_type'], 'application/pdf')
        self.assertEqual(captured['source_filename'], 'synthetic.pdf')
        source = self.store.source_path(captured['source_id'])
        self.assertEqual(source.read_bytes(), self.bytes)
        self.assertEqual(stat.S_IMODE(source.stat().st_mode), 0o400)
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.store.database.stat().st_mode), 0o600)
        self.store = store.ImportStore(self.root, clock=lambda: self.now)
        self.assertEqual(self.capture(page=3), captured)
        self.assertEqual(self.count('jobs'), 1)
        self.assertEqual(self.count('sources'), 1)
        self.assertNotIn('lease_token', self.store.status(captured['job_id']))
        self.assertNotIn('path', self.store.status(captured['job_id']))

    def test_request_id_cannot_change_source_or_selected_page(self):
        original = self.capture(page=1)
        for page in (0, 2):
            with self.assertRaises(store.StoreError):
                self.capture(page=page)
        self.input.write_bytes(self.bytes + b'changed')
        with self.assertRaises(store.StoreError):
            self.capture(page=1)
        self.assertEqual(self.count('jobs'), 1)
        self.assertEqual(self.store.source_path(original['source_id']).read_bytes(), self.bytes)

    def test_source_changed_during_capture_is_not_accepted(self):
        real = os.fstat
        calls = 0
        def mutate_before_second_stat(descriptor):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.input.write_bytes(self.bytes + b'changed during capture')
            return real(descriptor)
        with patch.object(store.os, 'fstat', side_effect=mutate_before_second_stat):
            with self.assertRaises(store.StoreError):
                self.capture()
        self.assertEqual(self.count('jobs'), 0)
        self.assertEqual(list(self.store.originals.iterdir()), [])

    def test_page_media_and_source_size_guards_leave_no_accepted_sources(self):
        for page in (-1, 50, True, 0.5, '1', None):
            with self.subTest(page=page), self.assertRaises(store.StoreError):
                self.capture(page=page)
        with self.assertRaises(store.StoreError):
            self.capture(media_type='image/png')
        self.input.write_bytes(b'')
        with self.assertRaises(store.StoreError):
            self.capture()
        with self.input.open('wb') as target:
            target.truncate(store.MAX_SOURCE_BYTES + 1)
        with self.assertRaises(store.StoreError):
            self.capture()
        self.assertEqual(self.count('jobs'), 0)
        self.assertEqual(list(self.store.originals.iterdir()), [])
        self.input.write_bytes(b'%PDF-' + b'0' * (store.MAX_SOURCE_BYTES - 5))
        captured = self.capture()
        self.assertEqual(captured['size'], store.MAX_SOURCE_BYTES)
        self.assertEqual(self.store.source_path(captured['source_id']).stat().st_size, store.MAX_SOURCE_BYTES)

    def test_root_source_and_artifact_symlinks_and_traversal_are_rejected(self):
        external = self.base / 'external'
        external.mkdir(mode=0o700)
        link = self.base / 'symlink'
        link.symlink_to(external, target_is_directory=True)
        with self.assertRaises(store.StoreError):
            store.ImportStore(link / 'output')
        self.assertFalse((external / 'output').exists())
        source_link = self.base / 'input-link.pdf'
        source_link.symlink_to(self.input)
        with self.assertRaises(store.StoreError):
            self.store.capture(source_link, request_id='source-link')
        with self.assertRaises(store.StoreError):
            self.store.source_path('../outside')
        captured = self.claim(self.capture())
        for name in ('../escape', '/absolute.png', '.hidden', 'a/b.png', 'a\\b.png', 'x..png'):
            with self.subTest(name=name), self.assertRaises(store.StoreError):
                self.complete(captured, derived={name: b'no'})
        self.assertEqual(list(self.store.derived.iterdir()), [])
        self.assertEqual(list(external.iterdir()), [])

    def test_replaced_managed_directory_is_never_followed(self):
        external = self.base / 'external'
        external.mkdir(mode=0o700)
        self.store.originals.rmdir()
        self.store.originals.symlink_to(external, target_is_directory=True)
        with self.assertRaises(store.StoreError):
            self.capture()
        self.assertEqual(list(external.iterdir()), [])

    def test_fifo_and_public_root_are_rejected_without_blocking(self):
        public = self.base / 'public'
        public.mkdir(mode=0o755)
        public.chmod(0o755)
        with self.assertRaises(store.StoreError):
            store.ImportStore(public)
        fifo = self.base / 'fifo'
        os.mkfifo(fifo)
        with self.assertRaises(store.StoreError):
            self.store.capture(fifo, request_id='fifo')

    def test_existing_original_filename_is_never_overwritten(self):
        source_id, job_id, temp_id = 'a' * 32, 'b' * 32, 'c' * 32
        destination = self.store.originals / (source_id + '.bin')
        destination.write_bytes(b'pre-existing content')
        destination.chmod(0o400)
        with patch.object(store.uuid, 'uuid4', side_effect=[SimpleNamespace(hex=value)
                                                          for value in (source_id, job_id, temp_id)]):
            with self.assertRaises(FileExistsError):
                self.capture()
        self.assertEqual(destination.read_bytes(), b'pre-existing content')
        self.assertEqual(self.count('jobs'), 0)
        self.assertEqual([path.name for path in self.store.originals.iterdir()], [destination.name])

    def test_expired_lease_is_taken_over_and_stale_worker_cannot_write(self):
        captured = self.capture()
        first = self.claim(captured, 'first')
        self.assertIsNone(self.claim(captured, 'second'))
        self.now += 91
        restarted = store.ImportStore(self.root, clock=lambda: self.now)
        second = restarted.claim(worker_id='second', job_id=captured['job_id'])
        self.assertNotEqual(first['lease_token'], second['lease_token'])
        self.assertEqual(second['attempts'], 2)
        with self.assertRaises(store.LeaseLost):
            self.complete(first)
        with self.assertRaises(store.LeaseLost):
            self.store.fail(first['job_id'], first['lease_token'], code='stale', message='Old attempt')
        self.assertEqual(list(self.store.derived.iterdir()), [])
        finished = self.complete(second)
        self.assertEqual(finished['status'], 'needs_review')
        self.assertIsNone(self.claim(captured, 'third'))
        self.assertEqual(restarted.result(captured['job_id']), {'kind': 'synthetic', 'walls': []})

    def test_concurrent_workers_claim_only_once(self):
        captured = self.capture()
        second = store.ImportStore(self.root, clock=lambda: self.now)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(target.claim, worker_id='worker-' + str(index), job_id=captured['job_id'])
                       for index, target in enumerate((self.store, second))]
            claims = [future.result() for future in futures]
        self.assertEqual(sum(result is not None for result in claims), 1)

    def test_lease_time_starts_after_the_write_lock_has_been_acquired(self):
        captured = self.capture()
        real = self.store._connection
        @contextmanager
        def delayed_lock(*, write=False):
            with real(write=write) as connection:
                if write:
                    self.now += 30
                yield connection
        with patch.object(self.store, '_connection', side_effect=delayed_lock):
            claimed = self.claim(captured, seconds=1)
        self.assertEqual(claimed['lease_until'], self.now + 1)
        self.assertEqual(self.complete(claimed)['status'], 'needs_review')

    def test_results_are_separate_verified_and_completion_is_idempotent(self):
        captured = self.capture()
        claimed = self.claim(captured)
        finished = self.complete(claimed)
        self.assertEqual(self.complete(claimed), finished)
        self.assertNotIn('lease_token', finished)
        original = self.store.source_path(finished['source_id'])
        preview = self.store.artifact_path(finished['job_id'], 'preview.png')
        recognition = self.store.recognition_path(finished['job_id'])
        self.assertEqual(original.parent, self.store.originals)
        self.assertTrue(preview.is_relative_to(self.store.derived))
        self.assertTrue(recognition.is_relative_to(self.store.recognition))
        self.assertEqual(preview.read_bytes(), b'synthetic preview')
        self.assertEqual(original.read_bytes(), self.bytes)
        with self.assertRaises(store.LeaseLost):
            self.complete(claimed, recognition={'kind': 'changed'})
        preview.chmod(0o600)
        preview.write_bytes(b'corrupted')
        with self.assertRaises(store.StoreError):
            self.store.status(finished['job_id'])

    def test_source_hash_mismatch_and_nonfinite_recognition_block_completion(self):
        captured = self.capture()
        claimed = self.claim(captured)
        with self.assertRaises(store.StoreError):
            self.complete(claimed, recognition={'confidence': float('nan')})
        self.assertEqual(list(self.store.derived.iterdir()), [])
        original = self.store.source_path(captured['source_id'])
        original.chmod(0o600)
        original.write_bytes(self.bytes + b'corruption')
        with self.assertRaises(store.StoreError):
            self.complete(claimed)
        self.assertEqual(self.store.status(captured['job_id'])['status'], 'running')

    def test_failed_file_fsync_accepts_nothing_and_preserves_input(self):
        with patch.object(store.os, 'fsync', side_effect=OSError('Synthetic disk failure')):
            with self.assertRaises(OSError):
                self.capture()
        self.assertEqual(self.input.read_bytes(), self.bytes)
        self.assertEqual(self.count('jobs'), 0)
        self.assertEqual(list(self.store.originals.iterdir()), [])
        self.assertEqual(self.capture()['status'], 'queued')

    def test_partial_result_publication_can_resume_but_never_claims_success_early(self):
        captured = self.capture()
        claimed = self.claim(captured)
        real = store._publish
        calls = 0
        def interrupt(path, content):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('Synthetic result interruption')
            return real(path, content)
        with patch.object(store, '_publish', side_effect=interrupt):
            with self.assertRaises(OSError):
                self.complete(claimed)
        self.assertEqual(self.store.status(captured['job_id'])['status'], 'running')
        with self.assertRaises(store.StoreError):
            self.store.result(captured['job_id'])
        self.assertEqual(self.complete(claimed)['status'], 'needs_review')
        self.assertEqual(self.store.source_path(captured['source_id']).read_bytes(), self.bytes)

    def test_directory_fsync_failure_leaves_no_confirmed_reference_and_retry_is_safe(self):
        real = store._fsync_directory
        def failure(path):
            if path == self.store.originals:
                raise OSError('Synthetic directory fsync failure')
            return real(path)
        with patch.object(store, '_fsync_directory', side_effect=failure):
            with self.assertRaises(OSError):
                self.capture()
        self.assertEqual(self.count('jobs'), 0)
        orphan = next(self.store.originals.iterdir())
        self.assertEqual(orphan.read_bytes(), self.bytes)
        captured = self.capture()
        self.assertEqual(self.count('jobs'), 1)
        self.assertEqual(self.store.source_path(captured['source_id']).read_bytes(), self.bytes)
        self.assertEqual(orphan.read_bytes(), self.bytes)

    def test_lost_acknowledgment_after_actual_commit_reuses_exact_job(self):
        real_connect = sqlite3.connect
        class LostAcknowledgment:
            def __init__(self, connection):
                object.__setattr__(self, 'connection', connection)
            def __getattr__(self, name):
                return getattr(self.connection, name)
            def __setattr__(self, name, value):
                setattr(self.connection, name, value)
            def commit(self):
                self.connection.commit()
                raise OSError('Synthetic lost commit acknowledgment')
        with patch.object(store.sqlite3, 'connect', side_effect=lambda *a, **kw: LostAcknowledgment(real_connect(*a, **kw))):
            with self.assertRaises(OSError):
                self.capture()
        self.assertEqual(self.count('jobs'), 1)
        captured = self.capture()
        self.assertEqual(captured['status'], 'queued')
        self.assertEqual(self.count('sources'), 1)
        self.assertEqual(len(list(self.store.originals.iterdir())), 1)

    def test_expiry_during_publication_never_confirms_late_result(self):
        captured = self.capture()
        claimed = self.claim(captured, seconds=1)
        real = store._publish
        def publish_then_expire(path, content):
            real(path, content)
            self.now += 2
        with patch.object(store, '_publish', side_effect=publish_then_expire):
            with self.assertRaises(store.LeaseLost):
                self.complete(claimed)
        self.assertEqual(self.store.status(captured['job_id'])['status'], 'running')
        with self.assertRaises(store.StoreError):
            self.store.result(captured['job_id'])
        fresh = self.claim(captured, 'fresh')
        self.assertEqual(self.complete(fresh)['status'], 'needs_review')

    def test_failed_jobs_and_exhausted_crashes_preserve_originals(self):
        captured = self.capture()
        for _ in range(store.MAX_ATTEMPTS):
            self.assertIsNotNone(self.claim(captured))
            self.now += 91
        self.assertIsNone(self.claim(captured))
        exhausted = self.store.status(captured['job_id'])
        self.assertEqual((exhausted['status'], exhausted['error_code']), ('failed', 'lease_exhausted'))
        self.assertEqual(self.store.source_path(captured['source_id']).read_bytes(), self.bytes)
        another = self.capture('fixture-2')
        claimed = self.claim(another)
        self.store.fail(claimed['job_id'], claimed['lease_token'], code='unsupported', message='Synthetic unsupported input')
        self.assertEqual(self.store.status(claimed['job_id'])['status'], 'failed')
        self.assertIsNone(self.claim(another))

    def test_foreign_database_is_not_changed_to_wal(self):
        root = self.base / 'foreign'
        root.mkdir(mode=0o700)
        database = root / 'imports.sqlite3'
        with sqlite3.connect(database) as connection:
            connection.execute('CREATE TABLE unrelated(value TEXT)')
            connection.execute("INSERT INTO unrelated VALUES('preserve')")
        database.chmod(0o600)
        before = database.read_bytes()
        with self.assertRaises(store.StoreError):
            store.ImportStore(root)
        self.assertEqual(database.read_bytes(), before)
        with sqlite3.connect(database) as connection:
            self.assertEqual(connection.execute('PRAGMA journal_mode').fetchone()[0], 'delete')
            self.assertEqual(connection.execute('SELECT value FROM unrelated').fetchone()[0], 'preserve')

    def test_missing_database_during_operation_is_never_recreated(self):
        captured = self.capture()
        self.store.database.unlink()
        with self.assertRaises(FileNotFoundError):
            self.store.status(captured['job_id'])
        self.assertFalse(self.store.database.exists())
        self.assertEqual(len(list(self.store.originals.iterdir())), 1)
        with self.assertRaises(store.StoreError):
            store.ImportStore(self.root)
        self.assertFalse(self.store.database.exists())

    def test_truncated_metadata_is_not_reinitialized_on_restart(self):
        self.capture()
        self.store.database.write_bytes(b'')
        with self.assertRaises(store.StoreError):
            store.ImportStore(self.root)
        self.assertEqual(self.store.database.stat().st_size, 0)
        self.assertEqual(len(list(self.store.originals.iterdir())), 1)


if __name__ == '__main__':
    unittest.main()
