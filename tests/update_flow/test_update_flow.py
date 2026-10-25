"""Exercise the real update shell in an isolated disposable Linux filesystem.

Only service, PostgreSQL, and interpreter boundaries are simulated. Filesystem
moves, symlinks, shell conditions, traps and command ordering execute unchanged.
Real PostgreSQL migration/restore is covered by backend/online/test_release.py.
"""
import json
import fcntl
import os
from pathlib import Path
import shutil
import subprocess
import unittest

SOURCE = Path('/source')
STATE = Path('/test-state')
CHECKOUT = Path('/opt/smartplan-test')
APP = Path('/opt/smartplan-online')
CONFIG = Path('/etc/smartplan-online')
HTTPS = Path('/etc/smartplan-https')
OLD = 'b' * 40
NEW = 'a' * 40
IMPORT_RUNTIME = Path('/opt/smartplan-plan-import')
IMPORT_UNIT = Path('/etc/systemd/system/smartplan-plan-import.service')
IMPORT_CODE = ('online/import_worker.py', 'online/import_sandbox.py', 'online/plan_imports.py',
               'plan_import/process.py', 'plan_import/sandbox_entry.py', 'plan_import/sandbox_probe.py',
               'plan_import/requirements.lock')


def require_disposable_container():
    if (os.getuid() != 0 or os.environ.get('SMARTPLAN_UPDATE_FLOW_CONTAINER') != '1' or
            not Path('/.dockerenv').is_file() or not SOURCE.is_dir() or
            not Path('/SMARTPLAN_UPDATE_FLOW_FIXTURE').is_file()):
        raise RuntimeError('Run only through scripts/test-update-flow.sh in its disposable Docker container.')


class OperatorFlowFixture:
    def setUp(self):
        require_disposable_container()
        for directory in (Path('/etc/systemd/system'), Path('/run/systemd/system')):
            for link in directory.glob('*.wants/smartplan-plan-import.service'):
                link.unlink()
        for path in (CHECKOUT, APP, CONFIG, HTTPS, STATE, Path('/test-bin'),
                     Path('/var/lib/smartplan-online'), Path('/var/lib/smartplan-online-operator'), Path('/opt/smartplan-https'),
                     Path('/opt/smartplan-plan-import'),
                     Path('/etc/systemd/system/smartplan-plan-import.service'),
                     Path('/etc/systemd/system/smartplan-lead-replies.service'),
                     Path('/etc/systemd/system/smartplan-lead-replies.timer'),
                     Path('/etc/systemd/system/smartplan-plan-import.service.d')):
            if path.is_symlink() or path.is_file():
                path.unlink()
            elif path.exists():
                shutil.rmtree(path)
        for path in (CHECKOUT / 'deploy/hetzner/online', APP, CONFIG, HTTPS,
                     STATE / 'databases', Path('/test-bin'), Path('/var/lib/smartplan-online'),
                     Path('/opt/smartplan-https/bin'), Path('/run/systemd/system'), Path('/run/lock'),
                     Path('/etc/systemd/system')):
            path.mkdir(parents=True, exist_ok=True)
        for database in ('passwd', 'group'):
            path = Path('/etc') / database
            text = path.read_text()
            if 'smartplan-online:' not in text:
                entries = ('smartplan-online:x:2001:2001::/nonexistent:/bin/false\nsmartplan-https:x:2002:2002::/nonexistent:/bin/false\n'
                           if database == 'passwd' else 'smartplan-online:x:2001:\nsmartplan-https:x:2002:\n')
                with path.open('a') as stream:
                    stream.write(entries)
            if 'postgres:' not in path.read_text():
                with path.open('a') as stream:
                    stream.write('postgres:x:2003:2003::/nonexistent:/bin/false\n' if database == 'passwd'
                                 else 'postgres:x:2003:\n')
        shutil.copyfile(SOURCE / 'tests/update_flow/command_stub.py', '/test-bin/command_stub.py')
        Path('/test-bin/command_stub.py').chmod(0o755)
        for name in ('git', 'runuser', 'systemctl', 'curl', 'createdb', 'sleep', 'python3', 'python3.12',
                     'mv', 'psql', 'apt-get', 'systemd-analyze', 'install', 'mkdir'):
            Path('/test-bin', name).symlink_to('/test-bin/command_stub.py')
        Path('/opt/smartplan-https/bin/caddy').symlink_to('/test-bin/command_stub.py')
        script_dir = CHECKOUT / 'deploy/hetzner/online'
        shutil.copyfile(SOURCE / 'deploy/hetzner/online/update-online.sh', script_dir / 'update-online.sh')
        shutil.copyfile(SOURCE / 'deploy/hetzner/online/prepare-business-security.sh', script_dir / 'prepare-business-security.sh')
        shutil.copyfile(SOURCE / 'deploy/hetzner/online/Caddyfile.v0.11', script_dir / 'Caddyfile.v0.11')
        shutil.copyfile(SOURCE / 'deploy/hetzner/online/Caddyfile', script_dir / 'Caddyfile')
        shutil.copyfile(script_dir / 'Caddyfile', HTTPS / 'Caddyfile')
        for unit in ('smartplan-online.service', 'smartplan-online-backup.service', 'smartplan-plan-import.service'):
            shutil.copyfile(SOURCE / 'deploy/hetzner/online' / unit, script_dir / unit)
            shutil.copyfile(script_dir / unit, Path('/etc/systemd/system') / unit)
        for unit in ('smartplan-lead-replies.service', 'smartplan-lead-replies.timer'):
            shutil.copyfile(SOURCE / 'deploy/hetzner/online' / unit, script_dir / unit)
        (CONFIG / 'service.env').write_text("SMARTPLAN_DATABASE_DSN='dbname=smartplan_online user=smartplan-online host=/var/run/postgresql'\nSMARTPLAN_PUBLIC_HOST=office.smartplan-hofmann.de\nOTHER_SETTING=preserved\n")
        (CONFIG / 'service.env').chmod(0o640)
        (APP / 'SOURCE_COMMIT').write_text(OLD + '\n')
        Path('/var/lib/smartplan-online/vault.key').write_text('synthetic-vault-marker')
        (STATE / 'databases/smartplan_online.json').write_text(json.dumps(['before-update']))
        self.original_config = (CONFIG / 'service.env').read_bytes()
        self.original_caddy = (HTTPS / 'Caddyfile').read_bytes()
        self.configure()

    def configure(self, *, fault='none', physical=False, timer=True, import_worker=False,
                  worker_installed=True, worker_restarting=False, lead_installed=False,
                  lead_timer=False, lead_worker=False, lead_restarting=False):
        (STATE / 'scenario.json').write_text(json.dumps({'fault': fault}))
        (STATE / 'services.json').write_text(json.dumps({'smartplan-online.service': True, 'smartplan-https.service': True,
                                                        'smartplan-online-backup.timer': timer,
                                                        'smartplan-plan-import.service': import_worker,
                                                        'smartplan-lead-replies.timer': lead_timer,
                                                        'smartplan-lead-replies.service': lead_worker,
                                                        'lead_replies_restart_pending': lead_restarting,
                                                        'import_worker_restart_pending': worker_restarting, 'gate': False}))
        worker_unit = Path('/etc/systemd/system/smartplan-plan-import.service')
        if worker_installed:
            shutil.copyfile(CHECKOUT / 'deploy/hetzner/online/smartplan-plan-import.service', worker_unit)
        elif worker_unit.exists():
            worker_unit.unlink()
        for name in ('smartplan-lead-replies.service', 'smartplan-lead-replies.timer'):
            unit = Path('/etc/systemd/system') / name
            if lead_installed:
                shutil.copyfile(CHECKOUT / 'deploy/hetzner/online' / name, unit)
            elif unit.exists():
                unit.unlink()
        for name in ('app', 'venv'):
            link = APP / name
            if link.is_symlink():
                link.unlink()
            elif link.exists():
                shutil.rmtree(link)
        target = APP if physical else APP / 'releases/old'
        (target / 'app/backend').mkdir(parents=True, exist_ok=True)
        (target / 'app/backend/generation').write_text('old\n')
        (target / 'venv/bin').mkdir(parents=True, exist_ok=True)
        binary = target / 'venv/bin/python'
        if binary.is_symlink():
            binary.unlink()
        binary.symlink_to('/test-bin/command_stub.py')
        if not physical:
            (APP / 'app').symlink_to(target / 'app', target_is_directory=True)
            (APP / 'venv').symlink_to(target / 'venv', target_is_directory=True)

    def run_update(self):
        environment = dict(os.environ, PATH='/test-bin:' + os.environ['PATH'])
        return subprocess.run(['bash', str(CHECKOUT / 'deploy/hetzner/online/update-online.sh')],
                              env=environment, capture_output=True, text=True, timeout=30)

    def events(self):
        path = STATE / 'events.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def services(self):
        return json.loads((STATE / 'services.json').read_text())

    def assert_original_data(self):
        self.assertEqual(json.loads((STATE / 'databases/smartplan_online.json').read_text()), ['before-update'])
        self.assertEqual(Path('/var/lib/smartplan-online/vault.key').read_text(), 'synthetic-vault-marker')

    def assert_old_release(self, *, physical=False):
        self.assertEqual((CONFIG / 'service.env').read_bytes(), self.original_config)
        self.assertEqual((HTTPS / 'Caddyfile').read_bytes(), self.original_caddy)
        self.assertEqual((APP / 'SOURCE_COMMIT').read_text().strip(), OLD)
        self.assertEqual((APP / 'app/backend/generation').read_text().strip(), 'old')
        self.assertEqual((APP / 'app').is_symlink(), not physical)
        self.assertEqual((APP / 'venv').is_symlink(), not physical)
        self.assertTrue(self.services()['smartplan-online.service'])
        self.assertFalse(self.services()['gate'])
        self.assert_original_data()


class UpdateFlowTests(OperatorFlowFixture, unittest.TestCase):
    def test_success_preserves_original_and_reopens_candidate_only_after_verification(self):
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_original_data()
        self.assertEqual((APP / 'SOURCE_COMMIT').read_text().strip(), NEW)
        self.assertNotEqual((CONFIG / 'service.env').read_bytes(), self.original_config)
        self.assertEqual((HTTPS / 'Caddyfile').read_bytes(), self.original_caddy)
        self.assertTrue(self.services()['smartplan-online-backup.timer'])
        self.assertFalse((CONFIG / 'UPDATE_IN_PROGRESS').exists())
        metadata = json.loads(next((CONFIG / 'updates').glob('*/metadata.json')).read_text())
        self.assertEqual(metadata['source_database'], 'smartplan_online')
        self.assertEqual(metadata['original_commit'], OLD)
        self.assertEqual(metadata['new_commit'], NEW)
        self.assertTrue(metadata['previous_app_was_link'])
        events = self.events()
        prepare = next(i for i, event in enumerate(events) if event.get('action') == 'prepare')
        stopped = next(i for i, event in enumerate(events) if event.get('unit') == 'smartplan-online.service' and event.get('action') == 'stop')
        activating = next(i for i, event in enumerate(events) if event.get('action') == 'phase' and event['flags'].get('--value') == 'activating')
        public_write = next(i for i, event in enumerate(events) if event['event'] == 'public_write')
        gate_restart = next(i for i, event in enumerate(events) if event.get('unit') == 'smartplan-https.service' and event.get('action') == 'restart')
        self.assertLess(gate_restart, stopped)
        self.assertLess(stopped, prepare)
        self.assertLess(activating, public_write)
        ready = [i for i, event in enumerate(events) if event['event'] == 'ready_probe' and event['generation'] == 'new']
        self.assertTrue(ready)
        self.assertLess(max(ready), public_write)
        security = next(i for i, event in enumerate(events) if event.get('action') == 'security')
        created = next(i for i, event in enumerate(events) if event.get('event') == 'createdb')
        self.assertLess(stopped, security)
        self.assertLess(security, created)
        self.assertLess(created, prepare)
        prepared = events[prepare]
        self.assertEqual(prepared['role'], 'postgres')
        self.assertTrue(prepared['flags']['--privileged-operator'])
        self.assertTrue((APP / 'app/web/office/index.html').is_file())
        self.assertEqual(next(e for e in events if e['event'] == 'archive')['paths'], ['backend', 'web'])

    def test_exact_legacy_caddy_is_migrated_only_after_candidate_verification(self):
        old = CHECKOUT / 'deploy/hetzner/online/Caddyfile.v0.11'
        shutil.copyfile(old, HTTPS / 'Caddyfile')
        self.original_caddy = old.read_bytes()
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((HTTPS / 'Caddyfile').read_bytes(), (SOURCE / 'deploy/hetzner/online/Caddyfile').read_bytes())
        self.assertEqual(next((CONFIG / 'updates').glob('*/Caddyfile.before')).read_bytes(), self.original_caddy)
        self.assert_original_data()

    def test_legacy_caddy_is_restored_on_prepublication_failure_and_unknown_config_is_refused(self):
        old = CHECKOUT / 'deploy/hetzner/online/Caddyfile.v0.11'
        shutil.copyfile(old, HTTPS / 'Caddyfile')
        self.original_caddy = old.read_bytes()
        self.configure(fault='readiness')
        self.assertNotEqual(self.run_update().returncode, 0)
        self.assert_old_release()
        (HTTPS / 'Caddyfile').write_bytes(self.original_caddy + b'\n# Unknown local override\n')
        before = (HTTPS / 'Caddyfile').read_bytes()
        events_before = len(self.events())
        self.assertNotEqual(self.run_update().returncode, 0)
        self.assertEqual((HTTPS / 'Caddyfile').read_bytes(), before)
        self.assertFalse(any(e['event'] == 'createdb' for e in self.events()[events_before:]))

    def test_failed_role_preparation_cannot_create_candidate_or_publish(self):
        self.configure(fault='business_security', import_worker=True)
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assert_old_release()
        self.assertTrue(self.services()['smartplan-plan-import.service'])
        self.assertFalse(any(e['event'] in ('createdb', 'public_write') for e in self.events()))

    def test_operator_path_symlink_is_refused_without_widening_runtime_private_directory(self):
        runtime = Path('/var/lib/smartplan-online')
        runtime.chmod(0o700)
        Path('/var/lib/smartplan-online-operator').symlink_to(runtime, target_is_directory=True)
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assert_old_release()
        self.assertEqual(runtime.stat().st_mode & 0o777, 0o700)
        self.assertFalse(any(e.get('action') in ('security', 'prepare') for e in self.events()))

    def test_missing_business_suite_capability_cannot_open_public_gate(self):
        self.configure(fault='missing_business_suite')
        self.assertNotEqual(self.run_update().returncode, 0)
        self.assert_old_release()
        self.assertFalse(any(e['event'] == 'public_write' for e in self.events()))

    def test_update_preserves_explicit_legacy_mode_instead_of_reenabling_business_writes(self):
        self.configure(fault='preserve_legacy_mode')
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(next((CONFIG / 'updates').glob('*/report.json')).read_text())
        self.assertEqual(report['business']['compatibility_mode'], 'legacy')
        self.assert_original_data()

    def test_checkpoint_failure_restores_original_env_without_replacing_or_exposing_private_key(self):
        self.configure(fault='privacy_checkpoint', import_worker=True)
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assert_old_release()
        key = Path('/var/lib/smartplan-online/privacy/key')
        self.assertEqual(key.stat().st_uid, 2001)
        self.assertEqual(key.stat().st_mode & 0o777, 0o600)
        self.assertEqual(key.parent.stat().st_mode & 0o777, 0o700)
        before = key.read_bytes()
        self.assertNotIn(before, (result.stdout + result.stderr).encode())
        self.assertFalse(any(e['event'] == 'public_write' for e in self.events()))
        self.configure(fault='none')
        self.assertEqual(self.run_update().returncode, 0)
        self.assertEqual(key.read_bytes(), before)

    def test_readiness_failure_rolls_back_symlink_installation_before_publication(self):
        self.configure(fault='readiness')
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assert_old_release()
        self.assertFalse((CONFIG / 'UPDATE_IN_PROGRESS').exists())
        self.assertFalse(any(event['event'] == 'public_write' for event in self.events()))

    def test_obsolete_schema_cannot_open_public_gate(self):
        self.configure(fault='obsolete_schema')
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assert_old_release()
        self.assertFalse(any(event['event'] == 'public_write' for event in self.events()))

    def test_missing_attachment_capability_cannot_open_public_gate(self):
        self.configure(fault='missing_mail_attachments')
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assert_old_release()
        self.assertFalse(any(event['event'] == 'public_write' for event in self.events()))

    def test_missing_integration_capability_cannot_open_public_gate(self):
        self.configure(fault='missing_business_integrations')
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assert_old_release()
        self.assertFalse(any(event['event'] == 'public_write' for event in self.events()))

    def test_old_release_version_cannot_open_public_gate_even_with_current_schema(self):
        self.configure(fault='obsolete_version')
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assert_old_release()
        self.assertFalse(any(event['event'] == 'public_write' for event in self.events()))

    def test_active_importworker_stops_before_clone_and_restarts_after_durable_activation(self):
        self.configure(import_worker=True)
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.services()['smartplan-plan-import.service'])
        metadata = json.loads(next((CONFIG / 'updates').glob('*/metadata.json')).read_text())
        self.assertTrue(metadata['import_worker_was_active'])
        events = self.events()
        stop = next(i for i, event in enumerate(events) if event.get('unit') == 'smartplan-plan-import.service' and event.get('action') == 'stop')
        prepare = next(i for i, event in enumerate(events) if event.get('action') == 'prepare')
        activating = max(i for i, event in enumerate(events) if event.get('action') == 'phase' and event['flags'].get('--value') == 'activating')
        start = next(i for i, event in enumerate(events) if event.get('unit') == 'smartplan-plan-import.service' and event.get('action') == 'start')
        self.assertLess(stop, prepare)
        self.assertLess(activating, start)
        self.assertEqual(events[start]['generation'], 'new')
        self.assertFalse((CONFIG / 'UPDATE_IN_PROGRESS').exists())

    def test_preactivation_rollback_restarts_only_the_previously_active_importworker(self):
        for active in (False, True):
            with self.subTest(active=active):
                self.setUp()
                self.configure(fault='readiness', import_worker=active)
                result = self.run_update()
                self.assertNotEqual(result.returncode, 0)
                self.assert_old_release()
                self.assertEqual(self.services()['smartplan-plan-import.service'], active)
                starts = [event for event in self.events() if event.get('unit') == 'smartplan-plan-import.service' and event.get('action') == 'start']
                self.assertEqual(len(starts), int(active))
                if starts:
                    self.assertEqual(starts[0]['generation'], 'old')

    def test_unconfirmed_importworker_stop_keeps_gate_and_original_without_database_switch(self):
        self.configure(fault='import_worker_stop', import_worker=True)
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assert_original_data()
        self.assertEqual((CONFIG / 'service.env').read_bytes(), self.original_config)
        self.assertEqual((APP / 'SOURCE_COMMIT').read_text().strip(), OLD)
        self.assertTrue(self.services()['gate'])
        self.assertTrue((CONFIG / 'UPDATE_IN_PROGRESS').exists())
        self.assertFalse(any(event['event'] == 'createdb' or event.get('action') == 'configure' for event in self.events()))

    def test_restarting_or_late_started_importworker_is_stopped_without_automatic_resume(self):
        for fault, restarting in (('none', True), ('import_worker_late_start', False)):
            with self.subTest(fault=fault, restarting=restarting):
                self.setUp()
                self.configure(fault=fault, worker_restarting=restarting)
                result = self.run_update()
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse(self.services()['smartplan-plan-import.service'])
                self.assertFalse(self.services()['import_worker_restart_pending'])
                events = self.events()
                stop = next(i for i, event in enumerate(events) if event.get('unit') == 'smartplan-plan-import.service'
                            and event.get('action') == 'stop')
                prepare = next(i for i, event in enumerate(events) if event.get('action') == 'prepare')
                self.assertLess(stop, prepare)
                self.assertFalse(any(event.get('unit') == 'smartplan-plan-import.service'
                                     and event.get('action') == 'start' for event in events))

    def test_successful_stop_exit_with_still_active_importworker_cannot_prepare_a_database(self):
        self.configure(fault='import_worker_false_stop', import_worker=True)
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assert_original_data()
        self.assertEqual((CONFIG / 'service.env').read_bytes(), self.original_config)
        self.assertEqual((APP / 'SOURCE_COMMIT').read_text().strip(), OLD)
        self.assertTrue(self.services()['gate'])
        self.assertTrue((CONFIG / 'UPDATE_IN_PROGRESS').exists())
        self.assertFalse(any(event['event'] == 'createdb' or event.get('action') in ('prepare', 'configure')
                             for event in self.events()))

    def test_sigterm_after_importworker_stop_restores_only_the_previously_active_worker(self):
        self.configure(fault='terminate_after_import_worker_stop', import_worker=True)
        result = self.run_update()
        self.assertEqual(result.returncode, 143, result.stdout + result.stderr)
        self.assert_old_release()
        self.assertTrue(self.services()['smartplan-plan-import.service'])
        starts = [event for event in self.events() if event.get('unit') == 'smartplan-plan-import.service'
                  and event.get('action') == 'start']
        self.assertEqual([event['generation'] for event in starts], ['old'])
        self.assertFalse((CONFIG / 'UPDATE_IN_PROGRESS').exists())
        self.assertFalse(any(event['event'] == 'createdb' or event.get('action') == 'prepare' for event in self.events()))

    def test_failed_new_importworker_resume_preserves_activated_candidate(self):
        self.configure(fault='import_worker_start_new', import_worker=True)
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((APP / 'SOURCE_COMMIT').read_text().strip(), NEW)
        self.assertEqual((APP / 'app/backend/generation').read_text().strip(), 'new')
        self.assertNotEqual((CONFIG / 'service.env').read_bytes(), self.original_config)
        self.assertEqual((CONFIG / 'UPDATE_IN_PROGRESS').read_text().strip(), 'activating')
        self.assertTrue(any(event['event'] == 'public_write' for event in self.events()))
        self.assertFalse(self.services()['smartplan-plan-import.service'])
        self.assert_original_data()

    def test_unconfirmed_activation_marker_does_not_resume_importworker_or_publish_http(self):
        self.configure(fault='activating_marker', import_worker=True)
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((APP / 'SOURCE_COMMIT').read_text().strip(), NEW)
        self.assertNotEqual((CONFIG / 'service.env').read_bytes(), self.original_config)
        self.assertTrue(self.services()['gate'])
        self.assertTrue((CONFIG / 'UPDATE_IN_PROGRESS').exists())
        self.assertFalse(self.services()['smartplan-plan-import.service'])
        self.assertFalse(any(event.get('unit') == 'smartplan-plan-import.service' and event.get('action') == 'start' for event in self.events()))
        self.assertFalse(any(event['event'] == 'public_write' for event in self.events()))
        self.assert_original_data()

    def test_failed_old_importworker_resume_keeps_maintenance_and_journal(self):
        self.configure(fault='import_worker_start_old', import_worker=True)
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((APP / 'SOURCE_COMMIT').read_text().strip(), OLD)
        self.assertEqual((CONFIG / 'service.env').read_bytes(), self.original_config)
        self.assertTrue(self.services()['gate'])
        self.assertTrue((CONFIG / 'UPDATE_IN_PROGRESS').exists())
        self.assertFalse(self.services()['smartplan-plan-import.service'])
        self.assertFalse(any(event['event'] == 'public_write' for event in self.events()))

    def test_inactive_importworker_is_never_automatically_started_on_success(self):
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.services()['smartplan-plan-import.service'])
        self.assertFalse(any(event.get('unit') == 'smartplan-plan-import.service' and event.get('action') == 'start' for event in self.events()))
        self.assertTrue(any(event.get('unit') == 'smartplan-plan-import.service' and event.get('action') == 'stop'
                            for event in self.events()))

    def test_installation_without_importworker_does_not_create_or_start_one(self):
        self.configure(worker_installed=False)
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(Path('/etc/systemd/system/smartplan-plan-import.service').exists())
        self.assertFalse(any(event.get('unit') == 'smartplan-plan-import.service'
                             and event.get('action') in ('start', 'stop') for event in self.events()))

    def test_worker_write_after_durable_activation_survives_a_later_timer_failure(self):
        self.configure(fault='import_worker_write_then_timer_failure', import_worker=True)
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((APP / 'SOURCE_COMMIT').read_text().strip(), NEW)
        self.assertNotEqual((CONFIG / 'service.env').read_bytes(), self.original_config)
        self.assertEqual((CONFIG / 'UPDATE_IN_PROGRESS').read_text().strip(), 'activating')
        events = self.events()
        activation = max(i for i, event in enumerate(events) if event.get('action') == 'phase'
                         and event['flags'].get('--value') == 'activating')
        writes = [(i, event) for i, event in enumerate(events) if event['event'] == 'import_worker_write']
        self.assertTrue(writes)
        self.assertLess(activation, writes[0][0])
        candidate = writes[0][1]['database']
        self.assertNotEqual(candidate, 'smartplan_online')
        self.assertIn('accepted-by-worker-after-activation',
                      json.loads((STATE / 'databases' / (candidate + '.json')).read_text()))
        self.assert_original_data()

    def test_readiness_failure_restores_original_physical_directories(self):
        self.configure(fault='readiness', physical=True)
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assert_old_release(physical=True)

    def test_failed_legacy_directory_moves_restore_both_original_directories(self):
        for fault in ('move_app', 'move_venv'):
            with self.subTest(fault=fault):
                self.setUp()
                self.configure(fault=fault, physical=True)
                result = self.run_update()
                self.assertNotEqual(result.returncode, 0)
                self.assert_old_release(physical=True)
                self.assertFalse((CONFIG / 'UPDATE_IN_PROGRESS').exists())
                self.assertTrue(any(e['event'] == 'failed_mv' for e in self.events()))

    def test_failed_symlink_switch_cleans_its_temporary_link_and_restores_old_release(self):
        self.configure(fault='switch_link')
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assert_old_release()
        self.assertEqual(list(APP.glob('*.update-*')), [])
        self.assertFalse((CONFIG / 'UPDATE_IN_PROGRESS').exists())

    def test_unconfirmed_service_stop_keeps_gate_and_journal_without_database_or_code_switch(self):
        self.configure(fault='service_stop')
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assert_original_data()
        self.assertEqual((APP / 'SOURCE_COMMIT').read_text().strip(), OLD)
        self.assertEqual((CONFIG / 'service.env').read_bytes(), self.original_config)
        self.assertEqual((APP / 'app/backend/generation').read_text().strip(), 'old')
        self.assertTrue(self.services()['gate'])
        self.assertTrue((CONFIG / 'UPDATE_IN_PROGRESS').exists())
        self.assertFalse(any(e['event'] == 'createdb' or e.get('action') == 'configure' for e in self.events()))

    def test_insufficient_capacity_aborts_before_gate_or_service_stop(self):
        self.configure(fault='capacity')
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assert_old_release()
        self.assertFalse((CONFIG / 'UPDATE_IN_PROGRESS').exists())
        self.assertFalse(any(e['event'] == 'gate' or e['event'] == 'createdb' or e.get('action') == 'stop' for e in self.events()))

    def test_unknown_units_or_overrides_abort_before_gate_or_database_mutation(self):
        for fault in ('unit_contents_api', 'unit_contents_backup', 'unit_fragment', 'unit_dropin',
                      'unit_environment', 'unit_envfile'):
            with self.subTest(fault=fault):
                self.setUp()
                self.configure(fault=fault)
                if fault.startswith('unit_contents_'):
                    name = 'smartplan-online.service' if fault.endswith('_api') else 'smartplan-online-backup.service'
                    with (Path('/etc/systemd/system') / name).open('a') as stream:
                        stream.write('\n# Unknown synthetic operator customization\n')
                result = self.run_update()
                self.assertNotEqual(result.returncode, 0)
                self.assert_old_release()
                self.assertFalse((CONFIG / 'UPDATE_IN_PROGRESS').exists())
                self.assertFalse(any(e['event'] in ('gate', 'createdb') or e.get('action') in ('stop', 'prepare')
                                     for e in self.events()))
                self.assertNotIn('FIXTURE_PRIVATE_SETTING', result.stdout + result.stderr)
                self.assertNotIn('must-not-appear', result.stdout + result.stderr)

    def test_unknown_worker_units_or_unsafe_effective_settings_abort_before_maintenance(self):
        for fault in ('worker_unit_contents', 'worker_unit_symlink', 'worker_unit_fragment', 'worker_unit_dropin',
                      'worker_unit_environment', 'worker_unit_envfile', 'worker_unit_killmode',
                      'worker_unit_no_sigkill', 'worker_unit_stop_timeout', 'worker_unit_vendor'):
            with self.subTest(fault=fault):
                self.setUp()
                self.configure(fault=fault, worker_installed=fault != 'worker_unit_vendor')
                unit = Path('/etc/systemd/system/smartplan-plan-import.service')
                if fault == 'worker_unit_contents':
                    with unit.open('a') as stream:
                        stream.write('\n# Unknown synthetic operator customization\n')
                elif fault == 'worker_unit_symlink':
                    copy = STATE / 'worker.service'
                    shutil.copyfile(unit, copy)
                    unit.unlink()
                    unit.symlink_to(copy)
                result = self.run_update()
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assert_old_release()
                self.assertFalse((CONFIG / 'UPDATE_IN_PROGRESS').exists())
                self.assertFalse(any(event['event'] in ('gate', 'createdb')
                                     or event.get('action') in ('stop', 'prepare') for event in self.events()))
                self.assertNotIn('FIXTURE_PRIVATE_SETTING', result.stdout + result.stderr)
                self.assertNotIn('must-not-appear', result.stdout + result.stderr)
                property_name = {'worker_unit_fragment': 'FragmentPath', 'worker_unit_dropin': 'DropInPaths',
                                 'worker_unit_environment': 'Environment', 'worker_unit_envfile': 'EnvironmentFiles',
                                 'worker_unit_killmode': 'KillMode', 'worker_unit_no_sigkill': 'SendSIGKILL',
                                 'worker_unit_stop_timeout': 'TimeoutStopUSec', 'worker_unit_vendor': 'LoadState'}.get(fault)
                if property_name:
                    self.assertTrue(any(event['event'] == 'systemctl_show'
                                        and event.get('unit') == 'smartplan-plan-import.service'
                                        and event.get('property') == property_name for event in self.events()))

    def test_gate_probe_failure_never_creates_or_prepares_a_database(self):
        self.configure(fault='gate_probe')
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assert_old_release()
        self.assertFalse(any(event['event'] == 'createdb' or event.get('action') == 'prepare' for event in self.events()))

    def test_post_publication_failure_preserves_new_database_and_accepted_write(self):
        for fault in ('reload_after_activation', 'public_probe'):
            with self.subTest(fault=fault):
                self.setUp()
                self.configure(fault=fault)
                result = self.run_update()
                self.assertNotEqual(result.returncode, 0)
                self.assert_original_data()
                self.assertEqual((APP / 'SOURCE_COMMIT').read_text().strip(), NEW)
                self.assertEqual((APP / 'app/backend/generation').read_text().strip(), 'new')
                writes = [e for e in self.events() if e['event'] == 'public_write']
                self.assertTrue(writes)
                candidate = writes[-1]['database']
                self.assertNotEqual(candidate, 'smartplan_online')
                self.assertEqual(json.loads((STATE / 'databases' / (candidate + '.json')).read_text()), ['before-update', 'accepted-after-publication'])
                self.assertEqual((CONFIG / 'UPDATE_IN_PROGRESS').read_text().strip(), 'activating')
                before = len(self.events())
                second = self.run_update()
                self.assertNotEqual(second.returncode, 0)
                self.assertEqual(len(self.events()), before)

    def test_existing_unknown_journal_blocks_before_any_service_or_database_changes(self):
        (CONFIG / 'UPDATE_IN_PROGRESS').write_text('unknown-interrupted-phase\n')
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assert_old_release()
        self.assertEqual(self.events(), [])

    def test_initially_inactive_backup_timer_remains_inactive_after_success_or_rollback(self):
        for fault in ('none', 'readiness'):
            with self.subTest(fault=fault):
                self.setUp()
                self.configure(fault=fault, timer=False)
                result = self.run_update()
                self.assertEqual(result.returncode, 0 if fault == 'none' else 1, result.stdout + result.stderr)
                self.assertFalse(self.services()['smartplan-online-backup.timer'])
                self.assertFalse(any(e.get('unit') == 'smartplan-online-backup.timer' and e.get('action') == 'start' for e in self.events()))


class InstallImportFlowTests(OperatorFlowFixture, unittest.TestCase):
    """The installer prepares only; no update cases are inherited or rerun."""

    def setUp(self):
        super().setUp()
        self.configure(worker_installed=False)
        script_dir = CHECKOUT / 'deploy/hetzner/online'
        shutil.copyfile(SOURCE / 'deploy/hetzner/online/install-plan-import.sh', script_dir / 'install-plan-import.sh')
        # Only this disposable container impersonates the supported host OS.
        Path('/etc/os-release').write_text('ID=ubuntu\nVERSION_ID="24.04"\n')
        (APP / 'SOURCE_COMMIT').write_text(NEW + '\n')
        (APP / 'app/backend/generation').write_text('new\n')
        for name in IMPORT_CODE:
            content = (SOURCE / 'backend' / name).read_bytes()
            for root in (CHECKOUT / 'backend', APP / 'app/backend'):
                destination = root / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
        # Real runuser/setpriv execute the simulated doctor as uid/gid 2001.
        for directory in (APP, STATE, Path('/test-bin'), *APP.rglob('*')):
            if directory.is_dir():
                directory.chmod(0o755)
        (STATE / 'scenario.json').chmod(0o644)
        doctor = STATE / 'doctor'
        doctor.mkdir(mode=0o700)
        os.chown(doctor, 2001, 2001)
        self.remember_existing_state()

    def remember_existing_state(self):
        self.preserved = {path: path.read_bytes() for path in
                          (CONFIG / 'service.env', HTTPS / 'Caddyfile', APP / 'SOURCE_COMMIT',
                           Path('/var/lib/smartplan-online/vault.key'), APP / 'app/backend/generation',
                           *(APP / 'app/backend' / name for name in IMPORT_CODE))}
        self.original_services = (STATE / 'services.json').read_bytes()

    def set_fault(self, fault):
        (STATE / 'scenario.json').write_text(json.dumps({'fault': fault}))
        (STATE / 'scenario.json').chmod(0o644)

    def run_install(self, *arguments):
        environment = dict(os.environ, PATH='/test-bin:' + os.environ['PATH'],
                           SMARTPLAN_DATABASE_DSN='synthetic-must-not-enter-doctor',
                           FIXTURE_PRIVATE_SETTING='must-not-appear', PYTHONPATH='/untrusted-synthetic-path')
        return subprocess.run(['bash', str(CHECKOUT / 'deploy/hetzner/online/install-plan-import.sh'), *arguments],
                              env=environment, capture_output=True, text=True, timeout=20)

    def assert_existing_state_untouched(self):
        for path, content in self.preserved.items():
            self.assertEqual(path.read_bytes(), content, str(path))
        self.assertEqual((STATE / 'services.json').read_bytes(), self.original_services)
        self.assertEqual(json.loads((STATE / 'databases/smartplan_online.json').read_text()), ['before-update'])
        events = self.events()
        self.assertFalse(any(event.get('action') in ('start', 'stop', 'enable', 'restart', 'reload')
                             and event['event'] == 'systemctl' for event in events))
        self.assertFalse(any(event['event'] in ('createdb', 'public_write', 'import_worker_write',
                                               'forbidden_database_access') for event in events))
        self.assertFalse(any(event['event'] == 'package' and event['action'] not in ('update', 'install')
                             for event in events), 'Shared packages must not be removed during cleanup.')
        self.assertFalse(any(event.get('action') in ('prepare', 'configure', 'validate')
                             and event['event'] == 'helper' for event in events))

    def assert_no_install_mutations(self):
        self.assert_existing_state_untouched()
        self.assertFalse(any(event['event'] in ('package', 'venv', 'pip', 'unit_verify') for event in self.events()))
        self.assertFalse((STATE / 'doctor/evidence.json').exists())

    def test_success_prepares_inactive_unit_after_real_uid_nnp_doctor_without_database_access(self):
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_existing_state_untouched()
        self.assertTrue((IMPORT_RUNTIME / 'venv/bin/python').is_file())
        self.assertEqual(IMPORT_UNIT.read_bytes(), (SOURCE / 'deploy/hetzner/online/smartplan-plan-import.service').read_bytes())
        self.assertEqual(IMPORT_UNIT.stat().st_mode & 0o777, 0o644)
        doctor = json.loads((STATE / 'doctor/evidence.json').read_text())
        self.assertEqual((doctor['uid'], doctor['gid'], doctor['no_new_privileges']), (2001, 2001, 1))
        self.assertFalse(doctor['unit_exists'], 'Runtime acceptance must precede unit installation.')
        self.assertIn('--doctor', doctor['arguments'])
        self.assertNotIn('--watch', doctor['arguments'])
        self.assertEqual(doctor['arguments'][doctor['arguments'].index('--worker-python') + 1],
                         str(IMPORT_RUNTIME / 'venv/bin/python'))
        self.assertNotIn('SMARTPLAN_DATABASE_DSN', doctor['environment_names'])
        self.assertNotIn('PYTHONPATH', doctor['environment_names'])
        self.assertNotIn('FIXTURE_PRIVATE_SETTING', doctor['environment_names'])
        events = self.events()
        preflight = next(i for i, event in enumerate(events) if event['event'] == 'installer_dsn_preflight')
        packages = next(i for i, event in enumerate(events) if event['event'] == 'package')
        self.assertLess(preflight, packages)
        self.assertTrue(any(event['event'] == 'pip' and event['action'] == 'install'
                            and '--only-binary=:all:' in event['flags'] for event in events))
        self.assertTrue(all(event['interpreter'] == str(IMPORT_RUNTIME / 'venv/bin/python')
                            for event in events if event['event'] == 'pip'))
        package_install = next(event for event in events if event['event'] == 'package' and event['action'] == 'install')
        self.assertTrue({'python3.12-venv', 'bubblewrap', 'tesseract-ocr', 'tesseract-ocr-eng',
                         'tesseract-ocr-deu', 'fonts-dejavu-core'} <= set(package_install['packages']))
        self.assertTrue(any(event['event'] == 'unit_verify' for event in events))
        self.assertTrue((STATE / 'installed-system-packages').is_file())
        self.assertFalse((CONFIG / 'UPDATE_IN_PROGRESS').exists())

    def test_old_dirty_mismatched_or_inactive_api_blocks_before_package_changes(self):
        for condition in ('old_commit', 'dirty', 'mismatched_code', 'inactive_api'):
            with self.subTest(condition=condition):
                self.setUp()
                if condition == 'old_commit':
                    (APP / 'SOURCE_COMMIT').write_text(OLD + '\n')
                elif condition == 'dirty':
                    self.set_fault('install_dirty')
                elif condition == 'mismatched_code':
                    (APP / 'app/backend/online/import_sandbox.py').write_text('Synthetic locally modified module.\n')
                else:
                    services = self.services()
                    services['smartplan-online.service'] = False
                    (STATE / 'services.json').write_text(json.dumps(services))
                self.remember_existing_state()
                result = self.run_install()
                self.assertNotEqual(result.returncode, 0)
                self.assert_no_install_mutations()
                self.assertFalse(IMPORT_RUNTIME.exists())
                self.assertFalse(IMPORT_UNIT.exists())

    def test_shared_operator_lock_blocks_before_any_installer_mutation(self):
        with Path('/run/lock/smartplan-online-update.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Verwaltung läuft', result.stderr)
        self.assert_no_install_mutations()
        self.assertFalse(IMPORT_RUNTIME.exists())
        self.assertFalse(IMPORT_UNIT.exists())

    def test_pending_update_regular_or_dangling_journal_blocks_installation(self):
        for kind in ('regular', 'symlink'):
            with self.subTest(kind=kind):
                self.setUp()
                marker = CONFIG / 'UPDATE_IN_PROGRESS'
                if kind == 'regular':
                    marker.write_text('activating\n')
                else:
                    marker.symlink_to('/nonexistent-synthetic-journal')
                result = self.run_install()
                self.assertNotEqual(result.returncode, 0)
                self.assert_no_install_mutations()
                self.assertTrue(marker.is_symlink() if kind == 'symlink' else marker.is_file())
                self.assertFalse(IMPORT_RUNTIME.exists())
                self.assertFalse(IMPORT_UNIT.exists())

    def test_existing_runtime_unit_symlink_or_dropin_is_never_overwritten(self):
        for kind in ('runtime', 'runtime_symlink', 'unit', 'unit_symlink', 'dropin'):
            with self.subTest(kind=kind):
                self.setUp()
                existing = STATE / 'preexisting'
                existing.mkdir()
                sentinel = existing / 'keep.txt'
                sentinel.write_text('Preexisting operator bytes.\n')
                if kind == 'runtime':
                    IMPORT_RUNTIME.mkdir()
                    sentinel = IMPORT_RUNTIME / 'keep.txt'
                    sentinel.write_text('Preexisting operator bytes.\n')
                elif kind == 'runtime_symlink':
                    IMPORT_RUNTIME.symlink_to(existing, target_is_directory=True)
                elif kind == 'unit':
                    IMPORT_UNIT.write_text('Preexisting operator bytes.\n')
                    sentinel = IMPORT_UNIT
                elif kind == 'unit_symlink':
                    IMPORT_UNIT.symlink_to(sentinel)
                else:
                    dropin = Path(str(IMPORT_UNIT) + '.d')
                    dropin.mkdir()
                    sentinel = dropin / 'keep.conf'
                    sentinel.write_text('Preexisting operator bytes.\n')
                result = self.run_install()
                self.assertNotEqual(result.returncode, 0)
                self.assert_no_install_mutations()
                self.assertEqual(sentinel.read_text(), 'Preexisting operator bytes.\n')
                if kind.endswith('_symlink'):
                    self.assertTrue((IMPORT_RUNTIME if kind.startswith('runtime') else IMPORT_UNIT).is_symlink())

    def test_real_configuration_guards_reject_duplicate_nonpeer_or_public_dsn_before_packages(self):
        for kind in ('duplicate', 'remote', 'permissions'):
            with self.subTest(kind=kind):
                self.setUp()
                environment = CONFIG / 'service.env'
                if kind == 'duplicate':
                    with environment.open('a') as stream:
                        stream.write("export SMARTPLAN_DATABASE_DSN='dbname=other user=smartplan-online host=/var/run/postgresql'\n")
                elif kind == 'remote':
                    environment.write_text("SMARTPLAN_DATABASE_DSN='dbname=smartplan_online user=smartplan-online host=example.invalid'\n")
                else:
                    environment.chmod(0o666)
                self.remember_existing_state()
                result = self.run_install()
                self.assertNotEqual(result.returncode, 0)
                self.assert_no_install_mutations()
                self.assertTrue(any(event['event'] == 'installer_dsn_preflight' for event in self.events()))
                self.assertNotIn('must-not-appear', result.stdout + result.stderr)

    def test_missing_fragment_with_still_active_worker_is_not_treated_as_empty_installation(self):
        services = self.services()
        services['smartplan-plan-import.service'] = True
        (STATE / 'services.json').write_text(json.dumps(services))
        self.remember_existing_state()
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assert_no_install_mutations()
        self.assertFalse(IMPORT_RUNTIME.exists())
        self.assertFalse(IMPORT_UNIT.exists())

    def test_existing_persistent_or_runtime_activation_link_is_preserved_and_blocks_packages(self):
        for directory in (Path('/etc/systemd/system'), Path('/run/systemd/system')):
            with self.subTest(directory=directory):
                self.setUp()
                wants = directory / 'multi-user.target.wants'
                wants.mkdir(exist_ok=True)
                link = wants / 'smartplan-plan-import.service'
                link.symlink_to(IMPORT_UNIT)
                result = self.run_install()
                self.assertNotEqual(result.returncode, 0)
                self.assert_no_install_mutations()
                self.assertTrue(link.is_symlink())
                self.assertEqual(link.readlink(), IMPORT_UNIT)
                self.assertFalse(IMPORT_RUNTIME.exists())
                self.assertFalse(IMPORT_UNIT.exists())

    def test_package_runtime_and_doctor_failures_remove_only_new_artifacts(self):
        for fault in ('install_apt_update', 'install_apt_install', 'install_venv',
                      'install_pip_install', 'install_pip_check', 'install_doctor', 'install_verify', 'install_partial_unit'):
            with self.subTest(fault=fault):
                self.setUp()
                self.set_fault(fault)
                sentinel = APP / 'releases/keep-operator-data'
                sentinel.write_text('Existing release bytes.\n')
                result = self.run_install()
                self.assertNotEqual(result.returncode, 0)
                self.assert_existing_state_untouched()
                self.assertFalse(IMPORT_RUNTIME.exists() or IMPORT_RUNTIME.is_symlink())
                self.assertFalse(IMPORT_UNIT.exists() or IMPORT_UNIT.is_symlink())
                self.assertEqual(sentinel.read_text(), 'Existing release bytes.\n')
                if fault != 'install_apt_update':
                    self.assertTrue((STATE / 'installed-system-packages').is_file(), 'Shared packages are retained after failure.')

    def test_sigterm_between_creation_and_next_shell_statement_cleans_only_owned_artifacts(self):
        for fault in ('install_terminate_after_mkdir', 'install_terminate_after_unit'):
            with self.subTest(fault=fault):
                self.setUp()
                self.set_fault(fault)
                sentinel = APP / 'releases/keep-operator-data'
                sentinel.write_text('Existing release bytes.\n')
                result = self.run_install()
                self.assertEqual(result.returncode, 143, result.stdout + result.stderr)
                self.assert_existing_state_untouched()
                self.assertFalse(IMPORT_RUNTIME.exists() or IMPORT_RUNTIME.is_symlink())
                self.assertFalse(IMPORT_UNIT.exists() or IMPORT_UNIT.is_symlink())
                self.assertEqual(sentinel.read_text(), 'Existing release bytes.\n')
                self.assertTrue((STATE / 'installed-system-packages').is_file())

    def test_objects_appearing_during_preparation_are_preserved_when_ownership_was_not_acquired(self):
        for fault in ('install_foreign_runtime', 'install_foreign_unit'):
            with self.subTest(fault=fault):
                self.setUp()
                self.set_fault(fault)
                result = self.run_install()
                self.assertNotEqual(result.returncode, 0)
                self.assert_existing_state_untouched()
                if fault == 'install_foreign_runtime':
                    self.assertEqual((IMPORT_RUNTIME / 'keep.txt').read_text(), 'Foreign operator object.\n')
                    self.assertFalse(IMPORT_UNIT.exists())
                else:
                    self.assertEqual(IMPORT_UNIT.read_text(), 'Foreign operator object.\n')
                    self.assertFalse(IMPORT_RUNTIME.exists())
                self.assertTrue((STATE / 'installed-system-packages').is_file())


if __name__ == '__main__':
    require_disposable_container()
    unittest.main(verbosity=2)
