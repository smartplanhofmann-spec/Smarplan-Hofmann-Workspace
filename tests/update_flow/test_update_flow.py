"""Exercise the real update shell in an isolated disposable Linux filesystem.

Only service, PostgreSQL, and interpreter boundaries are simulated. Filesystem
moves, symlinks, shell conditions, traps and command ordering execute unchanged.
Real PostgreSQL migration/restore is covered by backend/online/test_release.py.
"""
import json
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


def require_disposable_container():
    if (os.getuid() != 0 or os.environ.get('SMARTPLAN_UPDATE_FLOW_CONTAINER') != '1' or
            not Path('/.dockerenv').is_file() or not SOURCE.is_dir() or
            not Path('/SMARTPLAN_UPDATE_FLOW_FIXTURE').is_file()):
        raise RuntimeError('Run only through scripts/test-update-flow.sh in its disposable Docker container.')


class UpdateFlowTests(unittest.TestCase):
    def setUp(self):
        require_disposable_container()
        for path in (CHECKOUT, APP, CONFIG, HTTPS, STATE, Path('/test-bin'),
                     Path('/var/lib/smartplan-online'), Path('/opt/smartplan-https')):
            if path.exists():
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
        shutil.copyfile(SOURCE / 'tests/update_flow/command_stub.py', '/test-bin/command_stub.py')
        Path('/test-bin/command_stub.py').chmod(0o755)
        for name in ('git', 'runuser', 'systemctl', 'curl', 'createdb', 'sleep', 'python3', 'mv', 'psql'):
            Path('/test-bin', name).symlink_to('/test-bin/command_stub.py')
        Path('/opt/smartplan-https/bin/caddy').symlink_to('/test-bin/command_stub.py')
        script_dir = CHECKOUT / 'deploy/hetzner/online'
        shutil.copyfile(SOURCE / 'deploy/hetzner/online/update-online.sh', script_dir / 'update-online.sh')
        shutil.copyfile(SOURCE / 'deploy/hetzner/online/Caddyfile', script_dir / 'Caddyfile')
        shutil.copyfile(script_dir / 'Caddyfile', HTTPS / 'Caddyfile')
        for unit in ('smartplan-online.service', 'smartplan-online-backup.service'):
            shutil.copyfile(SOURCE / 'deploy/hetzner/online' / unit, script_dir / unit)
            shutil.copyfile(script_dir / unit, Path('/etc/systemd/system') / unit)
        (CONFIG / 'service.env').write_text("SMARTPLAN_DATABASE_DSN='dbname=smartplan_online user=smartplan-online host=/var/run/postgresql'\nSMARTPLAN_PUBLIC_HOST=office.smartplan-hofmann.de\nOTHER_SETTING=preserved\n")
        (CONFIG / 'service.env').chmod(0o640)
        (APP / 'SOURCE_COMMIT').write_text(OLD + '\n')
        Path('/var/lib/smartplan-online/vault.key').write_text('synthetic-vault-marker')
        (STATE / 'databases/smartplan_online.json').write_text(json.dumps(['before-update']))
        self.original_config = (CONFIG / 'service.env').read_bytes()
        self.original_caddy = (HTTPS / 'Caddyfile').read_bytes()
        self.configure()

    def configure(self, *, fault='none', physical=False, timer=True, import_worker=False):
        (STATE / 'scenario.json').write_text(json.dumps({'fault': fault}))
        (STATE / 'services.json').write_text(json.dumps({'smartplan-online.service': True, 'smartplan-https.service': True,
                                                        'smartplan-online-backup.timer': timer,
                                                        'smartplan-plan-import.service': import_worker, 'gate': False}))
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
        for fault in ('unit_contents_api', 'unit_contents_backup', 'unit_fragment', 'unit_dropin', 'unit_environment'):
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


if __name__ == '__main__':
    require_disposable_container()
    unittest.main(verbosity=2)
