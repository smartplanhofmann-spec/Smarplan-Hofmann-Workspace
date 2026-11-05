"""Real temporary files/locks/atomic writes; fake systemd, HTTP and process IO.

No production paths, database connections, OCR or systemd changes are used.
"""
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / 'deploy/hetzner/online/complete-online-update.py'
spec = importlib.util.spec_from_file_location('forward_completion', SCRIPT)
completion = importlib.util.module_from_spec(spec)
spec.loader.exec_module(completion)
COMMIT = 'a93cb4d02eab610e5f2a8b07fbd1ee51ae99c3e5'


class FakeOperations:
    def __init__(self):
        self.state = dict(LoadState='loaded', ActiveState='active', SubState='running',
                          MainPID='1234', InvocationID='a' * 32)
        self.timers = {'smartplan-online-backup.timer': 'active', 'smartplan-lead-replies.timer': 'inactive'}
        self.started = []
        self.db = 'smartplan_candidate'
        self.ready = dict(status='ok', database='ok', schema_version=7, version='0.12.0-online-pilot',
                          compatibility_mode='business', capabilities=['project_plans', 'offline_plan_access',
                          'plan_imports', 'plan_deletion', 'project_workspace', 'inquiry_intake',
                          'gmail_intake', 'mail_attachments', 'business_integrations', 'business_suite'])
        self.http = '401'
        self.package_versions = {'pillow': '13.0.0'}
        self.bad_binding = False
        self.no_worker_proof = False
        self.changed_process = False
        self.queries = 0

    def service(self, unit):
        if unit.endswith('.timer'):
            return dict(LoadState='loaded', ActiveState=self.timers[unit])
        self.queries += 1
        state = dict(self.state)
        if self.changed_process and self.queries > 3:
            state['MainPID'] = '9999'
        return state

    def database(self, config, backend):
        return self.db, 'synthetic-private-dsn'

    def binding(self, pid, dsn, backend):
        completion.require(not self.bad_binding, 'Synthetic process mismatch')

    def readiness(self):
        return self.ready

    def public_status(self):
        return self.http

    def packages(self, python, locked):
        return self.package_versions

    def worker_proof(self, unit, state):
        completion.require(not self.no_worker_proof, 'Synthetic missing proof')

    def start(self, unit):
        self.started.append(unit)
        self.timers[unit] = 'active'


class CompletionTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.install, self.config = root / 'install', root / 'config'
        self.release = self.install / 'releases' / (COMMIT[:12] + '-20261105T183455-10529')
        self.app = self.release / 'app'
        (self.app / 'backend/plan_import').mkdir(parents=True)
        (self.release / 'venv').mkdir()
        (self.install / 'app').symlink_to(self.app)
        (self.install / 'venv').symlink_to(self.release / 'venv')
        self.journal = self.config / 'updates' / self.release.name
        self.journal.mkdir(parents=True)
        self.lock = root / 'management.lock'
        self.pending = self.config / 'UPDATE_IN_PROGRESS'
        self.metadata = dict(new_commit=COMMIT, new_release=str(self.release), update_id=self.release.name,
                             source_database='smartplan_original', candidate_database='smartplan_candidate',
                             import_worker_was_active=True, lead_replies_present=False,
                             lead_timer_was_active=False)
        self.save_metadata()
        self.put(self.journal / 'report.json', json.dumps({'business': {'compatibility_mode': 'business'}}))
        self.put(self.journal / 'phase', 'activating\n')
        self.put(self.pending, 'activating\n')
        self.put(self.install / 'SOURCE_COMMIT', COMMIT + '\n')
        self.put(self.app / 'backend/plan_import/requirements.lock', '# synthetic lock\npillow==13.0.0\n')
        self.put(root / 'original-database-sentinel', 'original data')
        self.put(root / 'candidate-database-sentinel', 'new accepted write')
        self.original = {p: p.read_bytes() for p in (self.journal / 'metadata.json', self.journal / 'report.json',
                         root / 'original-database-sentinel', root / 'candidate-database-sentinel')}
        self.ops = FakeOperations()

    def put(self, path, text):
        path.write_text(text, encoding='utf-8')
        path.chmod(0o600)

    def save_metadata(self):
        self.put(self.journal / 'metadata.json', json.dumps(self.metadata))

    def finish(self):
        return completion.complete(self.install, self.config, self.lock, Path('/synthetic/parser-python'),
                                   COMMIT, self.ops, uid=os.getuid())

    def unchanged(self):
        for path, data in self.original.items():
            self.assertEqual(path.read_bytes(), data)

    def rejected(self):
        with self.assertRaises((completion.CheckError, ValueError, OSError)):
            self.finish()
        self.assertEqual(self.pending.read_text(), 'activating\n')
        self.assertEqual((self.journal / 'phase').read_text(), 'activating\n')
        self.assertFalse((self.journal / 'forward-verification.json').exists())

    def test_healthy_completion_preserves_both_databases_and_original_reports(self):
        proof = self.finish()
        self.assertFalse(self.pending.exists())
        self.assertEqual((self.journal / 'phase').read_text(), 'active\n')
        self.assertEqual(proof['candidate_database'], 'smartplan_candidate')
        self.assertEqual(proof['original_backup_timer_state'], 'not_persisted_by_original_updater')
        report = self.journal / 'forward-verification.json'
        self.assertEqual(report.stat().st_mode & 0o777, 0o600)
        self.assertNotIn('synthetic-private-dsn', report.read_text())
        self.assertEqual(self.ops.started, [])
        self.unchanged()

    def test_repeat_after_completed_marker_removal_revalidates(self):
        self.finish()
        self.finish()
        self.assertFalse(self.pending.exists())
        self.unchanged()

    def test_missing_marker_without_proof_is_rejected(self):
        self.pending.unlink()
        with self.assertRaises(FileNotFoundError):
            self.finish()
        self.assertEqual((self.journal / 'phase').read_text(), 'activating\n')

    def test_wrong_commit_is_rejected(self):
        self.put(self.install / 'SOURCE_COMMIT', 'b' * 40)
        self.rejected()

    def test_foreign_journal_is_rejected(self):
        self.metadata['update_id'] = 'unrelated-newer-update'
        self.save_metadata()
        self.rejected()

    def test_symlink_metadata_is_rejected(self):
        metadata = self.journal / 'metadata.json'
        original = self.journal / 'metadata.original'
        metadata.rename(original)
        metadata.symlink_to(original)
        self.rejected()

    def test_unsafe_release_permissions_are_rejected(self):
        self.app.chmod(0o775)
        self.rejected()

    def test_nonprivate_metadata_is_rejected(self):
        (self.journal / 'metadata.json').chmod(0o640)
        self.rejected()

    def test_pre_activation_phase_is_rejected(self):
        self.put(self.pending, 'verified\n')
        with self.assertRaises(completion.CheckError):
            self.finish()
        self.assertEqual(self.pending.read_text(), 'verified\n')
        self.assertEqual((self.journal / 'phase').read_text(), 'activating\n')

    def test_other_release_venv_is_rejected(self):
        (self.install / 'venv').unlink()
        (self.install / 'venv').symlink_to(self.app)
        self.rejected()

    def test_wrong_candidate_or_running_process_is_rejected(self):
        self.ops.db = 'smartplan_original'
        self.rejected()
        self.ops.db = 'smartplan_candidate'
        self.ops.bad_binding = True
        self.rejected()

    def test_unhealthy_services_and_process_restart_are_rejected(self):
        self.ops.state['ActiveState'] = 'failed'
        self.rejected()
        self.ops.state['ActiveState'] = 'active'
        self.ops.changed_process = True
        self.ops.queries = 0
        self.rejected()

    def test_unhealthy_readiness_and_public_route_are_rejected(self):
        self.ops.ready['database'] = 'unavailable'
        self.rejected()
        self.ops.ready['database'] = 'ok'
        self.ops.http = '503'
        self.rejected()

    def test_wrong_parser_version_or_missing_loop_proof_is_rejected(self):
        self.ops.package_versions['pillow'] = '12.3.0'
        self.rejected()
        self.ops.package_versions['pillow'] = '13.0.0'
        self.ops.no_worker_proof = True
        self.rejected()

    def test_failed_backup_timer_blocks_completion(self):
        self.ops.timers['smartplan-online-backup.timer'] = 'failed'
        self.rejected()

    def test_intentionally_inactive_backup_timer_is_preserved(self):
        self.ops.timers['smartplan-online-backup.timer'] = 'inactive'
        self.finish()
        self.assertEqual(self.ops.started, [])

    def test_lead_timer_resumes_only_recorded_intent(self):
        self.metadata.update(lead_replies_present=True, lead_timer_was_active=True)
        self.save_metadata()
        self.finish()
        self.assertEqual(self.ops.started, ['smartplan-lead-replies.timer'])

    def test_intentionally_inactive_lead_timer_is_preserved(self):
        self.metadata.update(lead_replies_present=True, lead_timer_was_active=False)
        self.save_metadata()
        self.finish()
        self.assertEqual(self.ops.started, [])

    def test_busy_management_lock_blocks_completion(self):
        with self.lock.open('w') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.rejected()

    def test_interrupted_final_phase_retains_marker_and_is_retryable(self):
        real_write = completion.atomic_write
        def fail_pending(path, value):
            if path == self.pending:
                raise OSError('synthetic interrupted pending write')
            real_write(path, value)
        with patch.object(completion, 'atomic_write', side_effect=fail_pending):
            with self.assertRaises(OSError):
                self.finish()
        self.assertTrue(self.pending.exists())
        self.assertEqual((self.journal / 'phase').read_text(), 'active\n')
        self.finish()
        self.assertFalse(self.pending.exists())
        self.unchanged()


class WorkerProofTest(unittest.TestCase):
    def test_real_process_binding_uses_environment_and_release_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            backend = Path(temporary).resolve()
            child = subprocess.Popen([sys.executable, '-c',
                                      'import sys; print("ready", flush=True); sys.stdin.read()'],
                                     cwd=backend, env={'SMARTPLAN_DATABASE_DSN': 'synthetic-private-dsn'},
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(), 'ready')
                ops = completion.Operations()
                ops.binding(str(child.pid), 'synthetic-private-dsn', backend)
                with self.assertRaises(completion.CheckError):
                    ops.binding(str(child.pid), 'wrong database', backend)
                with self.assertRaises(completion.CheckError):
                    ops.binding(str(child.pid), 'synthetic-private-dsn', backend / 'other')
            finally:
                child.communicate('', timeout=5)

    def test_current_invocation_and_pid_are_used_and_real_json_is_validated(self):
        state = dict(InvocationID='a' * 32, MainPID='11672')
        doctor = dict(ready=True, sandboxed=True, languages=['deu', 'eng'],
                      namespaces=['net', 'pid', 'mnt'], temporary_storage_bounded=True)
        encoded = lambda value: json.dumps({'MESSAGE': json.dumps(value)}) + '\n'
        ops = completion.Operations()
        with patch.object(ops, 'command', side_effect=[encoded(doctor), encoded({'status': 'idle'})]) as call:
            ops.worker_proof('smartplan-plan-import.service', state)
        self.assertIn('_SYSTEMD_INVOCATION_ID=' + 'a' * 32, call.call_args_list[0].args)
        self.assertIn('_PID=11672', call.call_args_list[1].args)
        for changed in ({**doctor, 'sandboxed': False}, {**doctor, 'languages': ['eng']},
                        {**doctor, 'temporary_storage_bounded': False}):
            with patch.object(ops, 'command', side_effect=[encoded(changed), encoded({'status': 'idle'})]):
                with self.assertRaises(completion.CheckError):
                    ops.worker_proof('smartplan-plan-import.service', state)
        with patch.object(ops, 'command', side_effect=[encoded(doctor), encoded({'status': 'unavailable'})]):
            with self.assertRaises(completion.CheckError):
                ops.worker_proof('smartplan-plan-import.service', state)


if __name__ == '__main__':
    unittest.main()
