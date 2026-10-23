"""Real controller/worker processes with synthetic local source documents."""
from hashlib import sha256
import importlib.util
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
import unittest

from PIL import Image, ImageDraw, ImageFont

from plan_import.store import ImportStore, StoreError


BACKEND = Path(__file__).resolve().parents[2]
HAS_WORKER = (sys.platform == 'linux'
              and all(importlib.util.find_spec(name) is not None
                      for name in ('pypdfium2', 'numpy', 'cv2', 'reportlab'))
              and bool(shutil.which('tesseract')))


def plan_png():
    output = BytesIO()
    with Image.new('RGB', (1200, 900), 'white') as image:
        draw = ImageDraw.Draw(image)
        draw.rectangle((40, 40, 1160, 860), outline='black', width=6)
        draw.line((600, 40, 600, 860), fill='black', width=6)
        draw.text((110, 220), 'FLOOR 12', font=ImageFont.load_default(size=64), fill='black')
        draw.line((800, 500, 900, 540, 850, 590), fill='red', width=5)
        image.save(output, format='PNG')
    return output.getvalue()


def plan_pdf():
    from reportlab.pdfgen.canvas import Canvas

    output = BytesIO()
    document = Canvas(output, pagesize=(500, 350), invariant=1)
    for title in ('FIRST 12', 'SECOND 24'):
        document.setFont('Helvetica-Bold', 26)
        document.drawString(60, 240, title)
        document.setLineWidth(2)
        document.rect(30, 30, 440, 290)
        document.line(300, 30, 300, 320)
        document.showPage()
    document.save()
    return output.getvalue()


def process_identity(pid):
    """Linux state, parent, group and birth time; zombies are already stopped."""
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    except (FileNotFoundError, ProcessLookupError):
        return None
    return {'state': fields[0], 'parent': int(fields[1]),
            'group': int(fields[2]), 'born': fields[19]}


@unittest.skipUnless(HAS_WORKER, 'CLI integration requires the local PDFium/OpenCV/Tesseract worker and ReportLab fixtures.')
class PlanImportCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='smartplan-import-cli-test-')
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.store_root = self.folder / 'private-import-store'
        self.environment = {**os.environ, 'PYTHONPATH': str(BACKEND)}

    def cli(self, *arguments, store=True, expected=0):
        command = [sys.executable, '-m', 'plan_import']
        if store:
            command += ['--store', str(self.store_root)]
        completed = subprocess.run(command + list(arguments), cwd=self.folder,
                                   env=self.environment, capture_output=True,
                                   text=True, timeout=60, check=False)
        self.assertEqual(completed.returncode, expected,
                         f'{arguments!r}: stdout={completed.stdout!r}; stderr={completed.stderr!r}')
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            self.fail(f'CLI must emit one JSON object, got {completed.stdout!r}: {error}')
        self.assertIsInstance(result, dict)
        return result

    def source_file(self, name, content):
        path = self.folder / name
        path.write_bytes(content)
        return path

    def assert_original_preserved(self, job, source, expected):
        storage = ImportStore(self.store_root)
        original = storage.source_path(job['source_id'])
        self.assertEqual(source.read_bytes(), expected)
        self.assertEqual(original.read_bytes(), expected)
        self.assertEqual(job['sha256'], sha256(expected).hexdigest())
        self.assertEqual(stat.S_IMODE(original.stat().st_mode), 0o400)
        return storage

    def assert_review_artifacts(self, job):
        self.assertEqual(job['status'], 'needs_review')
        storage = ImportStore(self.store_root)
        result = storage.result(job['job_id'])
        expected_paths = {
            'review_path': storage.artifact_path(job['job_id'], 'review.html'),
            'preview_path': storage.artifact_path(job['job_id'], 'preview.png'),
            'result_path': storage.recognition_path(job['job_id']),
        }
        for key, path in expected_paths.items():
            self.assertEqual(Path(job[key]), path)
            self.assertTrue(path.is_file())
            self.assertTrue(path.is_relative_to(self.store_root))
            self.assertGreater(path.stat().st_size, 0)
        self.assertEqual(json.loads(expected_paths['result_path'].read_text()), result)
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual(result['source']['sha256'], job['sha256'])
        self.assertGreater(len(result['analysis']['line_candidates']), 0,
                           'The real worker must find actual line candidates.')
        self.assertEqual(result['analysis']['status'], 'needs_review')
        self.assertEqual(result['calibration']['status'], 'unknown')
        with Image.open(expected_paths['preview_path']) as preview:
            self.assertEqual(preview.format, 'PNG')
            self.assertEqual(preview.size, (result['preview']['width'], result['preview']['height']))
            preview.load()
        html = expected_paths['review_path'].read_text()
        self.assertIn('data:image/png;base64,', html)
        self.assertIn("connect-src 'none'", html)
        return result

    def test_doctor_needs_no_store_and_creates_no_workspace_data(self):
        before = set(self.folder.iterdir())
        result = self.cli('doctor', store=False)
        self.assertIs(result['ready'], True)
        self.assertIs(result['external_processing'], False)
        self.assertEqual(set(self.folder.iterdir()), before)
        self.assertFalse(self.store_root.exists())

    def test_png_submit_work_status_and_idempotent_restart_keep_one_original(self):
        content = plan_png()
        # Content wins over the filename: this is a PNG carrying a CAD suffix.
        source = self.source_file('synthetic-capture.dwg', content)
        queued = self.cli('submit', str(source), '--request-id', 'camera-capture-1', '--page', '1')
        self.assertEqual(queued['status'], 'queued')
        self.assertEqual(queued['media_type'], 'image/png')
        self.assertEqual(queued['page'], 0)
        self.assert_original_preserved(queued, source, content)

        replay = self.cli('submit', str(source), '--request-id', 'camera-capture-1', '--page', '1')
        self.assertEqual((replay['job_id'], replay['source_id']), (queued['job_id'], queued['source_id']))

        processed = self.cli('work', '--job', queued['job_id'])
        result = self.assert_review_artifacts(processed)
        recognized = ' '.join(word['text'] for word in result['analysis']['text_candidates']).upper()
        self.assertIn('FLOOR', recognized)
        self.assertIn('12', recognized)
        self.assertFalse(result['pdf_text'], 'A photograph must not invent embedded PDF text.')
        self.assertIn('handwriting_not_interpreted', result['warnings'])

        # Every call launches a new controller: these reads do not share RAM.
        restarted = self.cli('status', queued['job_id'])
        self.assertEqual(restarted['job_id'], queued['job_id'])
        self.assertEqual(self.assert_review_artifacts(restarted), result)
        completed_replay = self.cli('submit', str(source), '--request-id', 'camera-capture-1', '--page', '1')
        self.assertEqual(completed_replay['job_id'], queued['job_id'])
        self.assertEqual(completed_replay['status'], 'needs_review')
        storage = self.assert_original_preserved(completed_replay, source, content)
        self.assertEqual(len(list(storage.originals.glob('*.bin'))), 1)
        with sqlite3.connect(storage.database) as database:
            self.assertEqual(database.execute('SELECT COUNT(*) FROM jobs').fetchone()[0], 1)
            self.assertEqual(database.execute('SELECT COUNT(*) FROM sources').fetchone()[0], 1)

    def test_pdf_run_selects_one_based_page_and_survives_controller_restart(self):
        content = plan_pdf()
        source = self.source_file('synthetic-two-floors.pdf', content)
        processed = self.cli('run', str(source), '--request-id', 'pdf-floor-2', '--page', '2')
        result = self.assert_review_artifacts(processed)
        self.assertEqual(processed['page'], 1)
        self.assertEqual(result['source']['selected_page'], 1)
        self.assertEqual(result['source']['page_count'], 2)
        embedded = ' '.join(word['text'] for word in result['pdf_text']).upper()
        self.assertIn('SECOND', embedded)
        self.assertIn('24', embedded)
        self.assertNotIn('FIRST', embedded)
        recognized = ' '.join(word['text'] for word in result['analysis']['text_candidates']).upper()
        self.assertIn('SECOND', recognized)
        self.assertIn('24', recognized)
        self.assert_original_preserved(processed, source, content)
        restarted = self.cli('status', processed['job_id'])
        self.assertEqual(self.assert_review_artifacts(restarted), result)

    def test_unsupported_dwg_is_durably_failed_without_empty_success_artifacts(self):
        content = b'AC1032' + b'\0' * 128
        source = self.source_file('synthetic-unsupported.dwg', content)
        queued = self.cli('submit', str(source), '--request-id', 'unsupported-dwg')
        self.assertEqual(queued['status'], 'queued')
        failed = self.cli('work', '--job', queued['job_id'], expected=1)
        self.assertEqual(failed['status'], 'failed')
        self.assertEqual(failed['error_code'], 'unsupported_format')
        restarted = self.cli('status', queued['job_id'], expected=1)
        self.assertEqual(restarted['status'], 'failed')
        self.assertEqual(restarted['error_code'], failed['error_code'])
        for key in ('review_path', 'preview_path', 'result_path'):
            self.assertFalse(restarted.get(key))
        storage = self.assert_original_preserved(restarted, source, content)
        with self.assertRaises(StoreError):
            storage.result(queued['job_id'])
        self.assertFalse(list(storage.derived.rglob('preview.png')))
        self.assertFalse(list(storage.recognition.rglob('result.json')))

    def test_reused_request_with_changed_bytes_cannot_replace_original_job(self):
        content = plan_png()
        source = self.source_file('synthetic-original.png', content)
        queued = self.cli('submit', str(source), '--request-id', 'fixed-request')
        changed = self.source_file('synthetic-changed.png', content + b'changed')
        self.cli('submit', str(changed), '--request-id', 'fixed-request', expected=1)
        restarted = self.cli('status', queued['job_id'])
        self.assertEqual(restarted['status'], 'queued')
        self.assertEqual((restarted['job_id'], restarted['source_id']), (queued['job_id'], queued['source_id']))
        self.assert_original_preserved(restarted, source, content)

    def test_sigterm_controller_stops_its_real_ocr_process_and_child(self):
        fake_bin = self.folder / 'fake-ocr-bin'
        fake_bin.mkdir(mode=0o700)
        marker = self.folder / 'private-ocr-processes.json'
        executable = fake_bin / 'tesseract'
        executable.write_text('#!' + sys.executable + '\n' + '''
import json
import os
from pathlib import Path
import subprocess
import sys
import time

if '--list-langs' in sys.argv:
    print('List of available languages (1):\\neng')
    raise SystemExit(0)
if '--version' in sys.argv:
    print('synthetic-test-tesseract')
    raise SystemExit(0)
marker = Path(os.environ['SMARTPLAN_TEST_OCR_MARKER'])
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)'],
                         stdin=subprocess.DEVNULL)
try:
    pending = marker.with_suffix('.pending')
    with pending.open('x') as stream:
        os.chmod(pending, 0o600)
        json.dump({'ocr_pid': os.getpid(), 'child_pid': child.pid,
                   'worker_pid': os.getppid(), 'group': os.getpgrp()}, stream)
    pending.replace(marker)
    time.sleep(300)
finally:
    if child.poll() is None:
        child.kill()
    child.wait()
''')
        executable.chmod(0o700)
        content = plan_png()
        source = self.source_file('synthetic-termination.png', content)
        environment = {**self.environment,
                       'PATH': str(fake_bin) + os.pathsep + os.environ.get('PATH', ''),
                       'SMARTPLAN_TEST_OCR_MARKER': str(marker)}
        controller = subprocess.Popen(
            [sys.executable, '-m', 'plan_import', '--store', str(self.store_root),
             'run', str(source), '--request-id', 'termination-test'],
            cwd=self.folder, env=environment, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        # Bind cleanup handles to the exact test processes, not reusable PIDs.
        process_handles = {}
        tracked = {}

        def remember(pid, identity):
            if pid not in tracked:
                tracked[pid] = identity
                if hasattr(os, 'pidfd_open'):
                    try:
                        process_handles[pid] = os.pidfd_open(pid)
                    except ProcessLookupError:
                        pass

        def remember_descendants():
            # Discover only children of this test's known process tree. This
            # also permits cleanup if the marker is never successfully written.
            if controller.poll() is not None:
                return
            pending, seen = [controller.pid], set()
            while pending:
                parent = pending.pop()
                if parent in seen:
                    continue
                seen.add(parent)
                try:
                    children = Path(f'/proc/{parent}/task/{parent}/children').read_text().split()
                except (FileNotFoundError, ProcessLookupError):
                    continue
                for child in children:
                    pid = int(child)
                    identity = process_identity(pid)
                    if identity is not None and identity['parent'] == parent:
                        remember(pid, identity)
                        pending.append(pid)

        try:
            deadline = time.monotonic() + 12
            while not marker.exists() and time.monotonic() < deadline:
                remember_descendants()
                if controller.poll() is not None:
                    stdout, stderr = controller.communicate(timeout=2)
                    self.fail(f'Controller exited before fake OCR started: {stdout!r} {stderr!r}')
                time.sleep(.02)
            self.assertTrue(marker.is_file(), 'Fake OCR must start before SIGTERM is sent.')
            self.assertEqual(stat.S_IMODE(marker.stat().st_mode), 0o600)
            processes = json.loads(marker.read_text())
            for name in ('worker_pid', 'ocr_pid', 'child_pid'):
                pid = processes[name]
                self.assertIs(type(pid), int)
                self.assertGreater(pid, 1)
                self.assertNotIn(pid, (os.getpid(), controller.pid))
                identity = process_identity(pid)
                self.assertIsNotNone(identity)
                remember(pid, identity)
            self.assertEqual(tracked[processes['worker_pid']]['parent'], controller.pid)
            self.assertEqual(tracked[processes['ocr_pid']]['parent'], processes['worker_pid'])
            self.assertEqual(tracked[processes['child_pid']]['parent'], processes['ocr_pid'])
            for identity in tracked.values():
                self.assertEqual(identity['group'], processes['worker_pid'])
            self.assertEqual(processes['group'], processes['worker_pid'])
            self.assertNotEqual(processes['group'], os.getpgrp())

            controller.send_signal(signal.SIGTERM)
            stdout, stderr = controller.communicate(timeout=10)
            self.assertEqual(controller.returncode, 143, f'{stdout!r} {stderr!r}')
            deadline = time.monotonic() + 5
            alive = list(tracked)
            while alive and time.monotonic() < deadline:
                alive = [pid for pid, original in tracked.items()
                         if (now := process_identity(pid)) is not None
                         and now['born'] == original['born'] and now['state'] != 'Z']
                if alive:
                    time.sleep(.02)
            self.assertFalse(alive, 'SIGTERM must leave no running worker, OCR process or OCR child.')
            storage = ImportStore(self.store_root)
            with sqlite3.connect(storage.database) as database:
                row = database.execute("SELECT job_id FROM jobs WHERE request_id='termination-test'").fetchone()
            self.assertIsNotNone(row)
            interrupted = storage.status(row[0])
            self.assertEqual(interrupted['status'], 'running', 'Interrupted job remains recoverable after its lease.')
            self.assert_original_preserved(interrupted, source, content)
            with self.assertRaises(StoreError):
                storage.result(row[0])
        finally:
            remember_descendants()
            if controller.poll() is None:
                controller.kill()
            controller.communicate(timeout=10)
            for pid, original in tracked.items():
                try:
                    if pid in process_handles and hasattr(signal, 'pidfd_send_signal'):
                        signal.pidfd_send_signal(process_handles[pid], signal.SIGKILL)
                    elif (now := process_identity(pid)) is not None and now['born'] == original['born']:
                        os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            for descriptor in process_handles.values():
                os.close(descriptor)


if __name__ == '__main__':
    unittest.main()
