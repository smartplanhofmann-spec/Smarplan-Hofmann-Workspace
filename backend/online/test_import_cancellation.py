"""A real running parser family stops when its source is explicitly deleted."""
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time
import unittest

import test_plan_imports as fixture
from online.plan_imports import validate_integrity


@unittest.skipUnless(sys.platform == 'linux' and hasattr(os, 'pidfd_open'), 'Linux worker process identities required')
class RunningImportDeletionTests(unittest.TestCase):
    setUp = fixture.PlanImportApiTests.setUp
    tearDown = fixture.PlanImportApiTests.tearDown
    open_app = fixture.PlanImportApiTests.open_app
    call = fixture.PlanImportApiTests.call
    manifest = fixture.PlanImportApiTests.manifest
    upload = fixture.PlanImportApiTests.upload
    fake_worker = fixture.PlanImportApiTests.fake_worker

    def test_explicit_deletion_stops_parser_and_child_removes_staging_and_never_publishes(self):
        path, job = self.upload()
        other_path, _ = self.upload(request_id='e' * 32, title='Another retained original')
        marker = self.directory / 'running-parser.json'
        escaped = self.directory / 'escaped-child.txt'
        child = ('import time; from pathlib import Path; time.sleep(8); Path('
                 + repr(str(escaped)) + ').write_text("must not execute")')
        worker = self.fake_worker(
            'child=subprocess.Popen([sys.executable,"-c",' + repr(child) + '])\n'
            'args=sys.argv\nsource=Path(args[args.index("--source")+1])\n'
            'Path(' + repr(str(marker)) + ').write_text(json.dumps({"pids":[os.getpid(),child.pid],"stage":str(source.parent)}))\n'
            'time.sleep(20)\n')
        controller = ('import json,sys; from core import Office; from online.import_worker import work_one; '
                      'from online.import_sandbox import DevelopmentRunner; '
                      'office=Office(sys.argv[1]); '
                      'print(json.dumps(work_one(office,runner=DevelopmentRunner(sys.argv[2]),process_timeout=15))); '
                      'office.db.close()')
        environment = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1])}
        process = subprocess.Popen([sys.executable, '-c', controller, str(self.database), str(worker)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
                                   start_new_session=True)
        handles = []
        try:
            deadline = time.monotonic() + 6
            while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue(marker.exists(), 'The synthetic parser did not start')
            proof = json.loads(marker.read_text())
            handles = [os.pidfd_open(pid) for pid in proof['pids']]
            receipt = self.call('POST', self.base + '/delete',
                                {'request_id': 'f' * 32, 'id': job['id']}).json
            self.assertEqual(receipt['status'], 'deleted')
            output, errors = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 0, errors.decode(errors='replace'))
            self.assertEqual(json.loads(output)['status'], 'deleted')
            self.assertFalse(Path(proof['stage']).exists(), 'Cancelled source staging was retained')
            for descriptor in handles:
                self.assertTrue(select.select([descriptor], [], [], 1)[0], 'Parser descendant survived deletion')
            self.assertFalse(escaped.exists())
            self.call('GET', path, status=410)
            self.assertEqual(self.call('GET', other_path + '/source').data, fixture.png())
            self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM plan_import_chunks WHERE import_id=?',
                                                    (job['id'],)).fetchone()[0], 0)
            self.assertTrue(validate_integrity(self.office))
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.communicate(timeout=5)
            for descriptor in handles:
                os.close(descriptor)
