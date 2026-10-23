"""Mandatory-on-request acceptance tests for the real Linux parser boundary.

Normal backend discovery reports these expensive Linux tests as disabled. The
dedicated CI job sets SMARTPLAN_REQUIRE_IMPORT_SANDBOX=1; capability failures are
then failures, never skips or an unsandboxed fallback. All documents, secrets,
listeners and processes below are synthetic and owned by this test process.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import uuid


REQUIRED = os.environ.get('SMARTPLAN_REQUIRE_IMPORT_SANDBOX') == '1'
MIB = 1024 * 1024


def process_identity(pid):
    """Avoid mistaking an unreaped zombie or a reused PID for a live child."""
    try:
        text = Path(f'/proc/{pid}/stat').read_text()
        fields = text[text.rindex(')') + 2:].split()
        return fields[0], fields[19]
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return None


def running(pid, identity):
    current = process_identity(pid)
    return current is not None and current[1] == identity[1] and current[0] != 'Z'


def kill_owned(pid, identity):
    if identity is None:
        return
    try:
        descriptor = os.pidfd_open(pid)
    except ProcessLookupError:
        return
    try:
        if running(pid, identity):
            # The descriptor pins the target even if /proc changes after the
            # identity check; cleanup never signals a later holder of its PID.
            try:
                signal.pidfd_send_signal(descriptor, signal.SIGKILL)
            except ProcessLookupError:
                pass
    finally:
        os.close(descriptor)


def escaped_children(marker):
    result = []
    for candidate in Path('/proc').iterdir():
        if not candidate.name.isdecimal():
            continue
        try:
            arguments = (candidate / 'cmdline').read_bytes().split(b'\0')
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if arguments[-3:-1] == [marker.encode(), b'smartplan-escaped-child']:
            pid = int(candidate.name)
            identity = process_identity(pid)
            if identity is not None:
                result.append((pid, identity))
    return result


def synthetic_launcher_diagnostic(runner):
    """Test-only startup evidence; no imported source or production logs."""
    from online.import_sandbox import launch_environment
    report = {}
    for name, path in {
        'apparmor_context': '/proc/self/attr/current',
        'apparmor_userns_restriction': '/proc/sys/kernel/apparmor_restrict_unprivileged_userns',
        'unprivileged_userns_clone': '/proc/sys/kernel/unprivileged_userns_clone',
    }.items():
        try:
            report[name] = Path(path).read_text().strip()[:512]
        except OSError:
            report[name] = 'unavailable'
    try:
        version = subprocess.run([str(runner.bwrap), '--version'], env=launch_environment(),
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=2)
        report['bwrap_version'] = version.stdout.decode(errors='replace')[:512].strip()
        with tempfile.TemporaryDirectory(prefix='smartplan-synthetic-launcher-diagnostic-') as temporary:
            stage = Path(temporary)
            (stage / 'output').mkdir(mode=0o700)
            (stage / 'source.bin').write_bytes(b'Synthetic launcher diagnostic only')
            command = runner._command(stage, ['/runtime/bin/python', '-c', 'print("synthetic-runtime-ready")'])
            process = subprocess.Popen(command, env=launch_environment(), stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       close_fds=True, start_new_session=True)
            try:
                output, errors = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                output, errors = process.communicate(timeout=3)
                report['timed_out'] = True
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=3)
            report.update(returncode=process.returncode,
                          stdout=output.decode(errors='replace')[-2048:],
                          stderr=errors.decode(errors='replace')[-4096:])
    except Exception as error:
        report['diagnostic_error'] = type(error).__name__ + ': ' + str(error)[:2048]
    return report


@unittest.skipUnless(
    REQUIRED,
    'Real Linux isolation is opt-in: SMARTPLAN_REQUIRE_IMPORT_SANDBOX=1 '
    '(mandatory in the dedicated sandbox CI job).',
)
class RealImportSandboxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform != 'linux':
            raise AssertionError('Mandatory parser isolation tests require Linux.')
        from online.import_sandbox import SandboxRunner
        cls.worker_python = os.environ.get('SMARTPLAN_IMPORT_TEST_WORKER_PYTHON', sys.executable)
        cls.runner = SandboxRunner(cls.worker_python)
        try:
            cls.readiness = cls.runner.doctor(ocr_languages='eng')
        except Exception as error:
            diagnostic = synthetic_launcher_diagnostic(cls.runner)
            raise AssertionError('Mandatory real sandbox startup failed; synthetic launcher diagnostic: '
                                 + json.dumps(diagnostic, sort_keys=True)) from error
        if cls.readiness.get('ready') is not True:
            raise AssertionError('The real parser sandbox did not pass its startup probe.')

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='smartplan-isolation-test-')
        self.root = Path(self.temporary.name).resolve()
        self.stage = self.root / 'stage'
        self.stage.mkdir(mode=0o700)
        (self.stage / 'output').mkdir(mode=0o700)
        self.source = self.stage / 'source.bin'
        self.source.write_bytes(b'Synthetic immutable source\n')
        self.original = self.source.read_bytes()
        self.processes = []

    def tearDown(self):
        for process in reversed(self.processes):
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)
        try:
            self.assertEqual(self.source.read_bytes(), self.original)
        finally:
            self.temporary.cleanup()

    def source_bytes(self, content):
        self.source.write_bytes(content)
        self.original = content

    def probe(self, script, arguments=(), *, environment=None, timeout=20):
        command = self.runner._command(
            self.stage, ['/runtime/bin/python', '-c', script, *map(str, arguments)],
        )
        process = subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, start_new_session=True, close_fds=True,
            env=environment,
        )
        self.processes.append(process)
        output, errors = process.communicate(timeout=timeout)
        self.assertEqual(process.returncode, 0, errors.decode(errors='replace')[-6000:])
        self.assertLessEqual(len(output), 65536)
        return json.loads(output)

    def test_doctor_checks_real_runtime_and_local_ocr(self):
        self.assertIs(self.readiness['ready'], True)
        self.assertIs(self.runner.sandboxed, True)
        # This is a second real probe, not a mock of import or executable lookup.
        report = self.probe('''
import json, subprocess
import cv2, numpy, PIL, pypdfium2
languages = subprocess.run(['tesseract', '--list-langs'], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
assert 'eng' in languages.stdout.decode().splitlines()
print(json.dumps({'pillow': bool(PIL.__version__), 'opencv': bool(cv2.__version__)}))
''')
        self.assertEqual(report, {'pillow': True, 'opencv': True})

    def test_doctor_works_with_no_new_privileges_and_unix_netlink_only(self):
        # Load the real socket-family filter only in this host subprocess. The
        # unittest controller keeps its own policy and can still run loopback
        # acceptance tests. This covers the relevant systemd restriction, not
        # the complete service unit (which has a separate acceptance harness).
        script = r'''
import ctypes
import ctypes.util
import errno
import json
import socket
import sys

from online.import_sandbox import SandboxRunner

library = ctypes.util.find_library('seccomp')
assert library, 'libseccomp2 is required for the real address-family acceptance test'
seccomp = ctypes.CDLL(library, use_errno=True)
libc = ctypes.CDLL(None, use_errno=True)

class Comparison(ctypes.Structure):
    _fields_ = [('arg', ctypes.c_uint), ('op', ctypes.c_int),
                ('datum_a', ctypes.c_uint64), ('datum_b', ctypes.c_uint64)]

seccomp.seccomp_init.argtypes = [ctypes.c_uint32]
seccomp.seccomp_init.restype = ctypes.c_void_p
seccomp.seccomp_release.argtypes = [ctypes.c_void_p]
seccomp.seccomp_release.restype = None
seccomp.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
seccomp.seccomp_syscall_resolve_name.restype = ctypes.c_int
seccomp.seccomp_rule_add_array.argtypes = [
    ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int,
    ctypes.c_uint, ctypes.POINTER(Comparison),
]
seccomp.seccomp_rule_add_array.restype = ctypes.c_int
seccomp.seccomp_load.argtypes = [ctypes.c_void_p]
seccomp.seccomp_load.restype = ctypes.c_int
libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong,
                       ctypes.c_ulong, ctypes.c_ulong]
libc.prctl.restype = ctypes.c_int

SCMP_ACT_ALLOW = 0x7fff0000
SCMP_ACT_ERRNO_EPERM = 0x00050000 | errno.EPERM
SCMP_CMP_LT, SCMP_CMP_EQ, SCMP_CMP_GT = 2, 4, 6
PR_SET_NO_NEW_PRIVS, PR_GET_NO_NEW_PRIVS = 38, 39
assert socket.AF_UNIX < socket.AF_NETLINK
socket_call = seccomp.seccomp_syscall_resolve_name(b'socket')
assert socket_call >= 0, 'Native socket syscall could not be resolved'
context = seccomp.seccomp_init(SCMP_ACT_ALLOW)
assert context, 'Could not allocate the real seccomp filter'
try:
    # All other syscalls stay usable. Reject every socket-family value except
    # these two, including values below/above the permitted range. Separate
    # comparisons avoid libseccomp's restriction on repeated args in one rule.
    comparisons = [(SCMP_CMP_LT, socket.AF_UNIX),
                   (SCMP_CMP_GT, socket.AF_NETLINK)]
    comparisons += [(SCMP_CMP_EQ, family)
                    for family in range(socket.AF_UNIX + 1, socket.AF_NETLINK)]
    for operation, family in comparisons:
        comparison = Comparison(0, operation, family, 0)
        status = seccomp.seccomp_rule_add_array(
            context, SCMP_ACT_ERRNO_EPERM, socket_call, 1, ctypes.byref(comparison))
        assert status == 0, ('Could not add socket-family restriction', status)
    assert libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) == 0
    status = seccomp.seccomp_load(context)
    assert status == 0, ('Could not activate the real seccomp filter', status)
finally:
    seccomp.seccomp_release(context)

assert libc.prctl(PR_GET_NO_NEW_PRIVS, 0, 0, 0, 0) == 1
with open('/proc/self/status') as stream:
    status = dict(line.rstrip().split(':', 1) for line in stream if ':' in line)
assert status['NoNewPrivs'].strip() == '1'

for family in (socket.AF_INET, socket.AF_INET6, socket.AF_PACKET):
    try:
        connection = socket.socket(family, socket.SOCK_STREAM)
    except OSError as error:
        assert error.errno == errno.EPERM, (family, error.errno)
    else:
        connection.close()
        raise AssertionError('Disallowed socket family crossed the filter')
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM):
    pass
with socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, socket.NETLINK_ROUTE):
    pass

report = SandboxRunner(sys.argv[1]).doctor(ocr_languages='eng')
assert report.get('ready') is True, 'Sandbox doctor failed under inherited service restrictions'
print(json.dumps({'ready': True, 'no_new_privileges': True,
                  'inet_blocked_with_eperm': True,
                  'unix_allowed': True, 'netlink_allowed': True}))
'''
        process = subprocess.Popen(
            [self.worker_python, '-B', '-c', script, self.worker_python],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, start_new_session=True, close_fds=True,
        )
        self.processes.append(process)
        output, errors = process.communicate(timeout=30)
        self.assertEqual(process.returncode, 0, errors.decode(errors='replace')[-6000:])
        self.assertLessEqual(len(output), 65536)
        self.assertEqual(json.loads(output), {
            'ready': True, 'no_new_privileges': True,
            'inet_blocked_with_eperm': True,
            'unix_allowed': True, 'netlink_allowed': True,
        })

    def test_host_canaries_credentials_and_inherited_descriptors_are_hidden(self):
        private = self.root / 'private-home'
        private.mkdir(mode=0o700)
        paths = []
        for name in ('office.sqlite', 'vault.key', '.profile', 'controller.canary'):
            path = private / name
            path.write_bytes(b'controlled-test-canary-content')
            paths.append(str(path))
        environment = dict(os.environ, HOME=str(private),
                           SMARTPLAN_DATABASE_DSN='synthetic-database-canary',
                           SMARTPLAN_VAULT_KEY='synthetic-vault-canary',
                           HTTP_PROXY='http://synthetic-proxy.invalid:1',
                           HTTPS_PROXY='http://synthetic-proxy.invalid:1',
                           ALL_PROXY='http://synthetic-proxy.invalid:1',
                           SMARTPLAN_TEST_SENTINEL='synthetic-environment-canary')
        with (private / 'controller.canary').open('rb') as descriptor:
            os.set_inheritable(descriptor.fileno(), True)
            report = self.probe('''
import json, os, pathlib, sys
paths = json.loads(sys.argv[1])
for path in paths:
    assert not pathlib.Path(path).exists(), 'Host private path is visible'
    assert not pathlib.Path('/proc/1/root' + path).exists(), 'Host root exposed through proc'
for key in ('HOME', 'SMARTPLAN_DATABASE_DSN', 'SMARTPLAN_VAULT_KEY',
            'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'SMARTPLAN_TEST_SENTINEL'):
    assert key not in os.environ, 'Inherited environment value crossed boundary'
for descriptor in pathlib.Path('/proc/self/fd').iterdir():
    try:
        target = os.readlink(descriptor)
    except FileNotFoundError:
        continue
    assert 'controller.canary' not in target, 'Inherited host descriptor crossed boundary'
assert pathlib.Path('/input/source.bin').read_bytes() == b'Synthetic immutable source\\n'
print(json.dumps({'host_paths_hidden': True, 'environment_hidden': True, 'fds_closed': True}))
''', [json.dumps(paths)], environment=environment)
        self.assertTrue(all(report.values()))

    def test_private_network_namespace_cannot_reach_host_loopback(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen(1)
            listener.settimeout(0.15)
            report = self.probe('''
import json, os, socket, sys
host_namespace, port = sys.argv[1], int(sys.argv[2])
assert os.readlink('/proc/self/ns/net') != host_namespace
with socket.socket() as connection:
    connection.settimeout(1)
    try:
        connection.connect(('127.0.0.1', port))
    except OSError:
        reached = False
    else:
        reached = True
assert not reached, 'Sandbox reached the host loopback listener'
print(json.dumps({'network_namespace_distinct': True, 'host_loopback_unreachable': True}))
''', [os.readlink('/proc/self/ns/net'), listener.getsockname()[1]])
            with self.assertRaises(socket.timeout):
                listener.accept()
        self.assertTrue(all(report.values()))

    def test_source_code_runtime_and_export_directory_stay_read_only(self):
        report = self.probe('''
import errno, json, os, pathlib
for path in ('/', '/proc', '/dev', '/app/plan_import', '/runtime', '/input/source.bin', '/export'):
    assert os.statvfs(path).f_flag & os.ST_RDONLY, 'Mount is not readonly: ' + path
for path in ('/input/source.bin', '/app/plan_import/__init__.py', '/runtime/pyvenv.cfg'):
    try:
        descriptor = os.open(path, os.O_WRONLY)
    except OSError as error:
        assert error.errno in (errno.EROFS, errno.EACCES, errno.EPERM), (path, error.errno)
    else:
        os.close(descriptor)
        raise AssertionError('Readonly inode accepted write: ' + path)
for path in ('/host-escape', '/input/extra', '/export/extra', '/dev/extra', '/proc/extra'):
    try:
        pathlib.Path(path).write_bytes(b'not allowed')
    except OSError as error:
        assert error.errno in (errno.EROFS, errno.EACCES, errno.EPERM, errno.ENOENT), error.errno
    else:
        raise AssertionError('Readonly directory accepted write: ' + path)
pathlib.Path('/export/preview.png').write_bytes(b'controlled-preview-export')
pathlib.Path('/export/result.json').write_text('{"controlled_result":true}')
assert pathlib.Path('/input/source.bin').read_bytes() == b'Synthetic immutable source\\n'
print(json.dumps({'readonly_mounts': True, 'exact_exports_writable': True}))
''')
        self.assertTrue(all(report.values()))
        self.assertEqual((self.stage / 'output' / 'preview.png').read_bytes(), b'controlled-preview-export')
        self.assertEqual(json.loads((self.stage / 'output' / 'result.json').read_bytes()), {'controlled_result': True})
        self.assertEqual({path.name for path in (self.stage / 'output').iterdir()}, {'preview.png', 'result.json'})

    def test_private_tmpfs_mounts_enforce_real_allocated_byte_limits(self):
        report = self.probe('''
import errno, json, os, pathlib
results = {}
chunk = b'x' * (1024 * 1024)
for mount, maximum in (('/tmp', 128 * 1024 * 1024), ('/output', 96 * 1024 * 1024)):
    info = os.statvfs(mount)
    capacity = info.f_blocks * info.f_frsize
    assert 0 < capacity <= maximum, (mount, capacity)
    path = pathlib.Path(mount) / 'bounded-allocation'
    count = 0
    exhausted = False
    try:
        with path.open('wb', buffering=0) as target:
            for _ in range(maximum // len(chunk) + 2):
                try:
                    written = target.write(chunk)
                    count += written
                except OSError as error:
                    assert error.errno == errno.ENOSPC, (mount, error.errno)
                    exhausted = True
                    break
    finally:
        path.unlink(missing_ok=True)
    assert exhausted and 0 < count <= maximum, (mount, count)
    results[mount] = {'capacity': capacity, 'written': count, 'enospc': exhausted}
print(json.dumps(results))
''', timeout=25)
        self.assertLessEqual(report['/tmp']['capacity'], 128 * MIB)
        self.assertLessEqual(report['/output']['capacity'], 96 * MIB)
        self.assertTrue(report['/tmp']['enospc'] and report['/output']['enospc'])
        # Only the two predetermined export inodes may exist on the host.
        self.assertEqual({path.name for path in (self.stage / 'output').iterdir()}, {'preview.png', 'result.json'})

    def test_setsid_descendant_dies_after_controller_or_parser_group_is_killed(self):
        child_script = """
import json, os, pathlib, time
os.setsid()
pathlib.Path('/export/result.json').write_text(json.dumps({'ready': True, 'pid': os.getpid(), 'pgid': os.getpgrp()}))
while True:
    time.sleep(10)
"""
        parser_script = """
import subprocess, sys, time
subprocess.Popen([sys.executable, '-c', sys.argv[1], sys.argv[2], 'smartplan-escaped-child'],
                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
while True:
    time.sleep(10)
"""
        controller_script = """
import json, pathlib, subprocess, sys
process = subprocess.Popen(json.loads(sys.argv[1]), stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           start_new_session=True, close_fds=True)
pathlib.Path(sys.argv[2]).write_text(json.dumps({'parser_pid': process.pid}))
process.wait()
"""
        for mode in ('controller', 'parser_group'):
            with self.subTest(mode=mode):
                marker = uuid.uuid4().hex
                controller_marker = self.root / ('controller-' + marker + '.json')
                export = self.stage / 'output' / 'result.json'
                command = self.runner._command(self.stage, [
                    '/runtime/bin/python', '-c', parser_script, child_script, marker,
                ])
                export.write_bytes(b'')
                controller = subprocess.Popen(
                    [self.worker_python, '-c', controller_script, json.dumps(command), str(controller_marker)],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                    start_new_session=True, close_fds=True,
                )
                self.processes.append(controller)
                parser_pid = None
                parser_identity = None
                descendants = []
                try:
                    deadline = time.monotonic() + 8
                    handshake = None
                    while time.monotonic() < deadline:
                        if controller.poll() is not None:
                            self.fail('Synthetic controller exited before sandbox handshake.')
                        try:
                            parser_pid = json.loads(controller_marker.read_bytes())['parser_pid']
                            parser_identity = process_identity(parser_pid)
                            handshake = json.loads(export.read_bytes())
                        except (FileNotFoundError, json.JSONDecodeError):
                            time.sleep(0.02)
                            continue
                        descendants = escaped_children(marker)
                        if handshake.get('ready') and descendants:
                            break
                        time.sleep(0.02)
                    self.assertTrue(handshake and handshake.get('ready'), 'No escaped-child handshake.')
                    self.assertEqual(handshake['pid'], handshake['pgid'], 'The descendant did not create its own session.')
                    self.assertEqual(len(descendants), 1, descendants)
                    self.assertTrue(running(*descendants[0]))
                    if mode == 'controller':
                        controller.kill()
                    else:
                        os.killpg(parser_pid, signal.SIGKILL)
                    controller.wait(timeout=5)
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        parser_alive = parser_identity is not None and running(parser_pid, parser_identity)
                        if not parser_alive and not any(running(pid, identity) for pid, identity in descendants):
                            break
                        time.sleep(0.02)
                    self.assertFalse(parser_identity is not None and running(parser_pid, parser_identity), 'Sandbox launcher survived cleanup.')
                    self.assertFalse(any(running(pid, identity) for pid, identity in descendants), 'A setsid descendant escaped sandbox cleanup.')
                finally:
                    if controller.poll() is None:
                        controller.kill()
                    controller.wait(timeout=5)
                    if parser_pid is not None:
                        kill_owned(parser_pid, parser_identity)
                    for pid, identity in descendants + escaped_children(marker):
                        kill_owned(pid, identity)
                    if controller.stderr is not None:
                        controller.stderr.close()

    def kernel(self, content, media_type, page=0):
        self.source_bytes(content)
        job = {'sha256': hashlib.sha256(content).hexdigest(), 'media_type': media_type, 'page': page}
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            process = self.runner.start(stage=self.stage, job=job, ocr_languages='eng', stdout=output, stderr=errors)
            self.processes.append(process)
            self.assertEqual(os.getsid(process.pid), process.pid, 'Parser must have its own outer session.')
            process.wait(timeout=40)
            output.seek(0)
            errors.seek(0)
            self.assertEqual(process.returncode, 0, errors.read(6000).decode(errors='replace'))
            self.assertEqual(json.loads(output.read(65537))['status'], 'needs_review')
        output = self.stage / 'output'
        self.assertEqual({path.name for path in output.iterdir()}, {'preview.png', 'result.json'})
        result = json.loads((output / 'result.json').read_bytes())
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual(result['source']['sha256'], job['sha256'])
        self.assertEqual(result['source']['selected_page'], page)
        from PIL import Image
        with Image.open(output / 'preview.png') as preview:
            preview.load()
            self.assertEqual(preview.format, 'PNG')
            self.assertEqual(preview.size, (result['preview']['width'], result['preview']['height']))
        self.assertTrue(result['analysis']['line_candidates'])
        return result

    def test_real_png_pillow_opencv_tesseract_pipeline_exports_review_candidates(self):
        from PIL import Image, ImageDraw, ImageFont
        with Image.new('RGB', (900, 650), 'white') as image:
            drawing = ImageDraw.Draw(image)
            drawing.rectangle((40, 40, 850, 600), outline='black', width=5)
            font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 48)
            drawing.text((130, 220), 'FLOOR 12', fill='black', font=font)
            data = io.BytesIO()
            image.save(data, format='PNG')
        result = self.kernel(data.getvalue(), 'image/png')
        text = ' '.join(item['text'] for item in result['analysis']['text_candidates'])
        self.assertIn('FLOOR', text.upper())

    def test_real_pdf_pdfium_page_selection_and_local_text_pipeline(self):
        from reportlab.pdfgen import canvas
        data = io.BytesIO()
        document = canvas.Canvas(data, pagesize=(500, 350), invariant=1)
        for index in range(2):
            document.setFont('Helvetica', 25)
            document.drawString(80, 220, f'FLOOR {index + 1}')
            document.rect(35, 35, 420, 270, stroke=1, fill=0)
            document.showPage()
        document.save()
        result = self.kernel(data.getvalue(), 'application/pdf', page=1)
        extracted = ''.join(item['text'] for item in result['pdf_text'])
        self.assertIn('FLOOR2', ''.join(extracted.split()))


if __name__ == '__main__':
    unittest.main()
