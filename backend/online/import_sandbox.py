"""Fail-closed, unprivileged Linux namespaces for the local plan recognizer.

The controller keeps its database connection outside the namespace. Only one
source inode and two bounded export inodes cross this boundary. No host output
directory, credentials, PostgreSQL socket, home, or inherited environment is
made available to the parser. This requires working unprivileged bubblewrap;
there is deliberately no automatic development-mode fallback.
"""
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tempfile

from plan_import.sandbox_protocol import PARSER_STARTED


TMP_BYTES = 128 * 1024 * 1024
OUTPUT_BYTES = 96 * 1024 * 1024
EXPORT_NAMES = ('preview.png', 'result.json')


class SandboxUnavailable(RuntimeError):
    """An operator/runtime problem; do not consume a document attempt."""


def launch_environment():
    """The launcher itself receives no database, vault, OAuth or proxy values."""
    return {'PATH': '/usr/local/bin:/usr/bin:/bin', 'LANG': 'C.UTF-8',
            'LC_ALL': 'C.UTF-8', 'PYTHONNOUSERSITE': '1',
            'PYTHONDONTWRITEBYTECODE': '1', 'OPENBLAS_NUM_THREADS': '1',
            'OMP_NUM_THREADS': '1', 'OMP_THREAD_LIMIT': '1',
            'OPENCV_FOR_THREADS_NUM': '1'}


def _python_path(value):
    if not isinstance(value, (str, os.PathLike)):
        raise SandboxUnavailable('An explicit worker Python is required.')
    path = Path(value)
    if not path.is_absolute() or not path.is_file() or not os.access(path, os.X_OK):
        raise SandboxUnavailable('Worker Python must be an absolute executable path.')
    return path


def _language_ids(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_]+(?:\+[A-Za-z0-9_]+)*', value):
        raise SandboxUnavailable('Explicit local OCR language IDs are required.')


def _regular(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid():
        raise SandboxUnavailable('Private regular job files are required.')


def _stop(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


class DevelopmentRunner:
    """Explicit synthetic-only escape hatch, never selected by the service."""
    sandboxed = False

    def __init__(self, worker_python):
        self.worker_python = _python_path(worker_python)

    def doctor(self, *, ocr_languages='eng'):
        _language_ids(ocr_languages)
        _python_path(self.worker_python)
        return {'ready': True, 'sandboxed': False}

    def start(self, *, stage, job, ocr_languages, stdout, stderr):
        environment = launch_environment()
        environment.update({'TMPDIR': str(stage),
                            'PYTHONPATH': str(Path(__file__).resolve().parents[1]),
                            'SMARTPLAN_IMPORT_SUPERVISED': '1'})
        return subprocess.Popen(
            [str(self.worker_python), '-m', 'plan_import.process',
             '--source', str(stage / 'source.bin'), '--output', str(stage / 'output'),
             '--sha256', job['sha256'], '--media-type', job['media_type'],
             '--page', str(job['page']), '--ocr-languages', ocr_languages],
            env=environment, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
            close_fds=True, start_new_session=True)


class SandboxRunner:
    sandboxed = True

    def __init__(self, worker_python, *, bwrap='/usr/bin/bwrap'):
        self.worker_python = _python_path(worker_python)
        self.runtime = self.worker_python.parent.parent.resolve(strict=True)
        self.code = Path(__file__).resolve().parents[1] / 'plan_import'
        self.bwrap = Path(bwrap)

    def _configuration(self):
        if sys.platform != 'linux':
            raise SandboxUnavailable('The isolated parser requires Linux.')
        _python_path(self.worker_python)
        if not self.bwrap.is_absolute() or not self.bwrap.is_file() or not os.access(self.bwrap, os.X_OK):
            raise SandboxUnavailable('The system bubblewrap executable is required.')
        information = self.bwrap.stat()
        if information.st_uid != 0 or information.st_mode & (stat.S_ISUID | stat.S_ISGID | 0o022):
            raise SandboxUnavailable('An unprivileged, administrator-owned bubblewrap is required.')
        configuration = self.runtime / 'pyvenv.cfg'
        if self.worker_python.parent.name != 'bin' or not configuration.is_file():
            raise SandboxUnavailable('A dedicated Linux parser virtualenv is required.')
        values = {key.strip(): value.strip() for line in configuration.read_text().splitlines()
                  if '=' in line for key, value in (line.split('=', 1),)}
        if values.get('include-system-site-packages', '').strip().lower() != 'false':
            raise SandboxUnavailable('The parser virtualenv must exclude system site packages.')
        version = values.get('version', '')
        if not re.fullmatch(r'3\.\d+\.\d+', version):
            raise SandboxUnavailable('A supported CPython virtualenv is required.')
        home = Path(values.get('home', ''))
        interpreter = self.worker_python.resolve(strict=True)
        if not home.is_absolute() or interpreter.parent != home.resolve(strict=True):
            raise SandboxUnavailable('The parser base interpreter must match its virtualenv.')
        standard_library = home.parent / 'lib' / ('python' + '.'.join(version.split('.')[:2]))
        if not standard_library.is_dir():
            raise SandboxUnavailable('The parser standard library is unavailable.')
        # A Python installed outside /usr is supported without exposing its
        # whole prefix: only the interpreter, stdlib and libpython inodes enter.
        aliases = [path for path in home.glob('python*')
                   if re.fullmatch(r'python(?:3(?:\.\d+)?)?', path.name) and path.is_file()]
        self.base_mounts = [*sorted(set([interpreter, *aliases])), standard_library,
                            *sorted((home.parent / 'lib').glob('libpython*.so*'))]
        if not (self.code / 'sandbox_entry.py').is_file():
            raise SandboxUnavailable('The isolated parser entry point is missing.')

    def _prepare(self, stage):
        stage = Path(stage).absolute()
        if stage.resolve(strict=True) != stage:
            raise SandboxUnavailable('A canonical private job directory is required.')
        for directory in (stage, stage / 'output'):
            info = directory.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
                raise SandboxUnavailable('Private controller-owned job directories are required.')
        _regular(stage / 'source.bin')
        for name in EXPORT_NAMES:
            path = stage / 'output' / name
            try:
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            except FileExistsError:
                _regular(path)
            else:
                os.close(descriptor)
        return stage

    def _command(self, stage, command):
        """Internal argv builder, also used for real isolation acceptance probes."""
        self._configuration()
        stage = self._prepare(stage)
        arguments = [str(self.bwrap), '--unshare-all', '--unshare-user', '--disable-userns',
                     '--die-with-parent', '--new-session', '--cap-drop', 'ALL', '--clearenv']
        # Only software/runtime trees are visible. In particular, never mount
        # /etc, /run, /var, /home, /opt or the source checkout as a whole.
        for path in ('/usr/bin', '/usr/lib', '/usr/lib64', '/usr/local/bin', '/usr/local/lib',
                     '/usr/share/fonts', '/usr/share/fontconfig', '/usr/share/tesseract-ocr'):
            if Path(path).is_dir():
                arguments += ['--ro-bind', path, path]
        for path in ('/bin', '/lib', '/lib64'):
            source = Path(path)
            if source.is_symlink():
                arguments += ['--symlink', os.readlink(source), path]
            elif source.is_dir():
                arguments += ['--ro-bind', path, path]
        for path in ('/etc/fonts', '/etc/ld.so.cache'):
            if Path(path).exists():
                arguments += ['--ro-bind', path, path]
        for path in self.base_mounts:
            arguments += ['--ro-bind', str(path), str(path)]
        arguments += ['--ro-bind', str(self.runtime), '/runtime',
                      '--ro-bind', str(self.code), '/app/plan_import',
                      '--ro-bind', str(stage / 'source.bin'), '/input/source.bin',
                      '--proc', '/proc', '--dev', '/dev',
                      '--size', str(TMP_BYTES), '--tmpfs', '/tmp',
                      '--size', str(OUTPUT_BYTES), '--tmpfs', '/output']
        # Writable file binds, not a writable host directory. RLIMIT_FSIZE also
        # bounds malicious writes to each export; no extra host files can be made.
        for name in EXPORT_NAMES:
            arguments += ['--bind', str(stage / 'output' / name), '/export/' + name]
        environment = {'PATH': '/runtime/bin:/usr/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
                       'TMPDIR': '/tmp', 'XDG_CACHE_HOME': '/tmp/cache',
                       'PYTHONPATH': '/app', 'PYTHONNOUSERSITE': '1',
                       'PYTHONDONTWRITEBYTECODE': '1', 'SMARTPLAN_IMPORT_SUPERVISED': '1',
                       'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1',
                       'OMP_THREAD_LIMIT': '1', 'OPENCV_FOR_THREADS_NUM': '1'}
        for name, value in environment.items():
            arguments += ['--setenv', name, value]
        arguments += ['--chdir', '/output', '--remount-ro', '/dev',
                      '--remount-ro', '/proc', '--remount-ro', '/', '--', *command]
        return arguments

    def doctor(self, *, ocr_languages='eng'):
        _language_ids(ocr_languages)
        try:
            with tempfile.TemporaryDirectory(prefix='smartplan-sandbox-doctor-') as directory:
                stage = Path(directory)
                (stage / 'output').mkdir(mode=0o700)
                (stage / 'source.bin').write_bytes(b'Synthetic sandbox startup probe')
                namespace_ids = {name: os.readlink('/proc/self/ns/' + name) for name in ('net', 'pid', 'mnt')}
                command = ['/runtime/bin/python', '-m', 'plan_import.sandbox_probe',
                           '--ocr-languages', ocr_languages, '--host-namespaces', json.dumps(namespace_ids)]
                with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
                    process = subprocess.Popen(self._command(stage, command), env=launch_environment(),
                                               stdin=subprocess.DEVNULL, stdout=output, stderr=errors,
                                               close_fds=True, start_new_session=True)
                    try:
                        process.wait(timeout=20)
                    finally:
                        _stop(process)
                    output.seek(0)
                    data = output.read(65537)
                    report = json.loads(data) if len(data) <= 65536 else {}
                    if process.returncode != 0 or not isinstance(report, dict) or report.get('ready') is not True:
                        raise SandboxUnavailable('Isolated parser startup verification failed.')
                    return report
        except SandboxUnavailable:
            raise
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            # Do not expose parser logs, source paths or inherited values.
            raise SandboxUnavailable('Isolated parser startup verification failed.') from error

    def start(self, *, stage, job, ocr_languages, stdout, stderr):
        _language_ids(ocr_languages)
        command = ['/runtime/bin/python', '-m', 'plan_import.sandbox_entry',
                   '--source', '/input/source.bin', '--output', '/output',
                   '--sha256', job['sha256'], '--media-type', job['media_type'],
                   '--page', str(job['page']), '--ocr-languages', ocr_languages]
        try:
            return subprocess.Popen(self._command(stage, command), env=launch_environment(),
                                    stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                    close_fds=True, start_new_session=True)
        except OSError as error:
            raise SandboxUnavailable('Isolated parser could not be started.') from error

    def parser_started(self, stage):
        """Classify a crashed parser without trusting it to publish any result."""
        try:
            descriptor = os.open(Path(stage) / 'output' / 'result.json',
                                 os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= 1024 * 1024:
                    return False
                data = stream.read(1024 * 1024 + 1)
            if data == PARSER_STARTED:
                return True
            result = json.loads(data)
            return (isinstance(result, dict) and type(result.get('schema_version')) is int
                    and result['schema_version'] == 1 and result.get('status') == 'needs_review')
        except (OSError, ValueError, UnicodeError):
            return False
