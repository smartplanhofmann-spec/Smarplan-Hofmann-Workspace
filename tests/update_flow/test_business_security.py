"""Run the unchanged security shell with a real postgres Unix UID in Docker.

Only the database/interpreter boundary is simulated here. The companion real PG
acceptance verifies grants/ownership; these cases prove shell guards and ordering.
"""
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

from test_update_flow import OperatorFlowFixture, SOURCE, STATE, APP, CONFIG


class BusinessSecurityFlow(OperatorFlowFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        for name, text in (('passwd', 'postgres:x:2003:2003::/nonexistent:/bin/false\n'),
                           ('group', 'postgres:x:2003:\n')):
            path = Path('/etc') / name
            if 'postgres:' not in path.read_text():
                with path.open('a') as stream:
                    stream.write(text)
        self.release = APP / 'releases/security-fixture'
        self.backend = self.release / 'app/backend'
        (self.backend / 'online').mkdir(parents=True)
        (self.backend / 'online/release.py').write_text('# Synthetic interpreter boundary only.\n')
        (self.backend / 'business_schema.py').write_text('# Synthetic interpreter boundary only.\n')
        (self.release / 'venv/bin').mkdir(parents=True)
        self.python = self.release / 'venv/bin/python'
        self.python.write_text('''#!/usr/local/bin/python3
import json,os,sys
from pathlib import Path
if sys.argv[1:] == ['-']:
    text=sys.stdin.read()
    assert 'read_environment' in text and 'validate_dsns' in text
    print('dbname=smartplan_online user=smartplan-online host=/var/run/postgresql')
else:
    assert sys.argv[1:]==['-m','online.release','security']
    assert os.getuid()==2003,'Real operator UID required'
    assert os.environ['SMARTPLAN_DATABASE_DSN']=='dbname=smartplan_online user=smartplan-online host=/var/run/postgresql'
    Path('/test-state/operator.json').write_text(json.dumps({'uid':os.getuid(),'arguments':sys.argv[1:]}))
    if Path('/test-state/operator-fail').exists():raise SystemExit(7)
''')
        self.python.chmod(0o755)
        # Unlike the ordinary update fixture, this boundary really changes UID.
        Path('/test-bin/runuser').unlink()
        Path('/test-bin/runuser').symlink_to('/usr/sbin/runuser')
        systemctl = Path('/test-bin/systemctl-security')
        systemctl.write_text('''#!/usr/local/bin/python3
import json,sys
from pathlib import Path
assert sys.argv[1]=='show'
unit=sys.argv[2]
state=json.loads(Path('/test-state/security-services.json').read_text())
print(state.get(unit,'inactive'))
''')
        systemctl.chmod(0o755)
        Path('/test-bin/systemctl').unlink()
        Path('/test-bin/systemctl').symlink_to(systemctl)
        (STATE / 'security-services.json').write_text('{}')
        STATE.chmod(0o777)  # Disposable evidence sink; source/config stay private.
        self.script = SOURCE / 'deploy/hetzner/online/prepare-business-security.sh'

    def run_security(self, *, inherited=False, args=None):
        invocation = ['bash', str(self.script), *(args if args is not None else [str(self.python), str(self.backend)])]
        if inherited:
            invocation = ['bash', '-c', 'exec 9>/run/lock/smartplan-online-update.lock\nflock -n 9\nexec bash "$@"',
                          'fixture', str(self.script), '--under-update-lock', str(self.python), str(self.backend)]
        return subprocess.run(invocation, env=dict(os.environ, PATH='/test-bin:' + os.environ['PATH']),
                              capture_output=True, text=True, timeout=15)

    def assert_no_operator(self):
        self.assertFalse((STATE / 'operator.json').exists())
        self.assert_original_data()
        self.assertEqual((CONFIG / 'service.env').read_bytes(), self.original_config)

    def test_stopped_installation_runs_real_operator_uid_and_preserves_data_and_configuration(self):
        result = self.run_security()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((STATE / 'operator.json').read_text())['uid'], 2003)
        self.assert_original_data()
        self.assertEqual((CONFIG / 'service.env').read_bytes(), self.original_config)

    def test_inherited_actual_update_lock_is_accepted_without_reopening_or_unlocking_it(self):
        (CONFIG / 'UPDATE_IN_PROGRESS').write_text('stopped\n')
        result = self.run_security(inherited=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((CONFIG / 'UPDATE_IN_PROGRESS').read_text(), 'stopped\n')

    def test_every_active_or_restarting_writer_blocks_before_operator_or_database_action(self):
        for unit in ('smartplan-online.service', 'smartplan-online-backup.timer',
                     'smartplan-online-backup.service', 'smartplan-plan-import.service',
                     'smartplan-lead-replies.service', 'smartplan-lead-replies.timer'):
            for value in ('active', 'activating', 'deactivating', 'reloading'):
                with self.subTest(unit=unit, value=value):
                    (STATE / 'security-services.json').write_text(json.dumps({unit: value}))
                    self.assertNotEqual(self.run_security().returncode, 0)
                    self.assert_no_operator()

    def test_shared_lock_refusal_and_missing_inherited_descriptor_never_run_operator(self):
        with Path('/run/lock/smartplan-online-update.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertNotEqual(self.run_security().returncode, 0)
        self.assertNotEqual(self.run_security(args=['--under-update-lock', str(self.python), str(self.backend)]).returncode, 0)
        self.assert_no_operator()

    def test_untrusted_or_group_writable_staged_code_is_refused_without_operator(self):
        self.assertNotEqual(self.run_security(args=['/usr/local/bin/python3', str(self.backend)]).returncode, 0)
        self.python.chmod(0o775)
        self.assertNotEqual(self.run_security().returncode, 0)
        self.assert_no_operator()

    def test_pending_unknown_update_blocks_standalone_and_operator_failure_preserves_everything(self):
        journal = CONFIG / 'UPDATE_IN_PROGRESS'
        journal.write_text('activating\n')
        self.assertNotEqual(self.run_security().returncode, 0)
        self.assert_no_operator()
        journal.unlink()
        (STATE / 'operator-fail').write_text('synthetic failure')
        self.assertEqual(self.run_security().returncode, 7)
        self.assert_original_data()
        self.assertEqual((CONFIG / 'service.env').read_bytes(), self.original_config)
        self.assertTrue(self.python.exists())


if __name__ == '__main__':
    unittest.main()
