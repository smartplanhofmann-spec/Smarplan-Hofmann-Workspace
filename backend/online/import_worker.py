"""Explicit local import worker; parser/OCR runs outside Office transactions.

Use a dedicated Python with plan_import/requirements.lock for the child. Neither
the database DSN nor vault/OAuth credentials enter its allowlisted environment.
"""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time

from online.plan_imports import PlanImports, LeaseLost, MAX_PREVIEW_BYTES, MAX_RESULT_BYTES
from online.import_sandbox import SandboxRunner, DevelopmentRunner, SandboxUnavailable

PROCESS_TIMEOUT_SECONDS = 55


class _ValidatedRunner:
    """Cache only successful readiness checks for one trusted runner instance."""
    def __init__(self, runner):
        self.runner = runner
        self.sandboxed = runner.sandboxed
        self.ready = {}

    def doctor(self, *, ocr_languages='eng'):
        if ocr_languages not in self.ready:
            result = self.runner.doctor(ocr_languages=ocr_languages)
            if not isinstance(result, dict) or result.get('ready') is not True:
                raise SandboxUnavailable('The configured parser runner is not ready.')
            if self.sandboxed and result.get('sandboxed') is not True:
                raise SandboxUnavailable('The parser doctor did not confirm sandbox isolation.')
            self.ready[ocr_languages] = result
        return self.ready[ocr_languages]

    def start(self, **kwargs):
        return self.runner.start(**kwargs)

    def parser_started(self, stage):
        check = getattr(self.runner, 'parser_started', None)
        return callable(check) and check(stage) is True


def _stop(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def child_environment(directory):
    """Explicit allowlist: no inherited DB, vault, OAuth or proxy credentials."""
    return {'PATH': '/usr/local/bin:/usr/bin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
            'TMPDIR': str(directory),
            'PYTHONPATH': str(Path(__file__).resolve().parents[1]),
            'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1',
            'SMARTPLAN_IMPORT_SUPERVISED': '1', 'OPENBLAS_NUM_THREADS': '1',
            'OMP_NUM_THREADS': '1', 'OMP_THREAD_LIMIT': '1', 'OPENCV_FOR_THREADS_NUM': '1'}


def _read(path, maximum):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
            raise ValueError('Unbounded worker output')
        content = stream.read(maximum + 1)
        if len(content) > maximum:
            raise ValueError('Unbounded worker output')
        return content


def work_one(office, *, worker_python=None, runner=None,
             process_timeout=PROCESS_TIMEOUT_SECONDS, ocr_languages='eng'):
    """Claim/publish briefly; original bytes and all results remain in the DB."""
    if sys.platform != 'linux':
        raise RuntimeError('The supervised import worker requires Linux.')
    if not isinstance(process_timeout, (int, float)) or not 1 <= process_timeout <= 60:
        raise ValueError('A bounded parser timeout of at most 60 seconds is required.')
    if not isinstance(ocr_languages, str) or not re.fullmatch(r'[A-Za-z0-9_]+(?:\+[A-Za-z0-9_]+)*', ocr_languages):
        raise ValueError('Local OCR language IDs required')
    runner = runner or SandboxRunner(os.fspath(worker_python or sys.executable))
    runner = runner if isinstance(runner, _ValidatedRunner) else _ValidatedRunner(runner)
    runner.doctor(ocr_languages=ocr_languages)
    imports = PlanImports(office)
    job = None
    claimed = False
    process = None

    def stop():
        nonlocal process
        if process is not None:
            _stop(process)
            process = None

    def fail(code):
        with office.lock, office.db:
            try:
                return imports.fail(job['id'], job['lease_token'], code)
            except LeaseLost:
                return imports._status(imports._row(job['id']))

    def release():
        if job is None:
            return None
        with office.lock, office.db:
            try:
                return imports.release(job['id'], job['lease_token'])
            except LeaseLost:
                return imports._status(imports._row(job['id']))

    try:
        with office.lock, office.db:
            job = imports.claim(lease_seconds=90)
        claimed = True
        if job is None:
            return None
        with office.lock, office.db:
            imports._lease(job['id'], job['lease_token'])
            source = imports.source_bytes(job)
        with tempfile.TemporaryDirectory(prefix='smartplan-project-import-') as directory:
            stage = Path(directory)
            artifacts = stage / 'output'
            artifacts.mkdir(mode=0o700)
            source_path = stage / 'source.bin'
            descriptor = os.open(source_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(source)
            with tempfile.TemporaryFile(dir=stage) as output, tempfile.TemporaryFile(dir=stage) as errors:
                process = runner.start(stage=stage, job=job, ocr_languages=ocr_languages, stdout=output, stderr=errors)
                try:
                    deadline = time.monotonic() + process_timeout
                    while True:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise subprocess.TimeoutExpired(process.args, process_timeout)
                        try:
                            process.wait(timeout=min(1.0, remaining))
                            break
                        except subprocess.TimeoutExpired:
                            # A deletion revokes the lease. Stop the parser
                            # family before removing staging; late results or
                            # a refund must never revive the deleted source.
                            with office.lock, office.db:
                                imports._lease(job['id'], job['lease_token'])
                except subprocess.TimeoutExpired:
                    _stop(process)
                    process = None
                    return fail('processing_timeout')
                except BaseException:
                    _stop(process)
                    process = None
                    raise
                _stop(process)
                returncode = process.returncode
                process = None
                output.seek(0)
                diagnostic = output.read(65537)
                try:
                    outcome = json.loads(diagnostic) if len(diagnostic) <= 65536 else {}
                except (ValueError, UnicodeError):
                    outcome = {}
                if isinstance(outcome, dict) and outcome.get('status') == 'failed':
                    return fail(outcome.get('error_code', 'processing_failed'))
                if returncode != 0 or not isinstance(outcome, dict) or outcome.get('status') != 'needs_review':
                    if runner.parser_started(stage):
                        return fail('processing_failed')
                    raise SandboxUnavailable('The parser launcher did not produce a valid kernel outcome.')
            preview = _read(artifacts / 'preview.png', MAX_PREVIEW_BYTES)
            result = json.loads(_read(artifacts / 'result.json', MAX_RESULT_BYTES))
            with office.lock, office.db:
                return imports.publish(job['id'], job['lease_token'], preview=preview, result=result)
    except LeaseLost:
        with office.lock, office.db:
            return imports._status(imports._row(job['id']))
    except SandboxUnavailable:
        stop()
        release()
        raise
    except (OSError, MemoryError) as error:
        stop()
        release()
        raise SandboxUnavailable('Local parser infrastructure failed; the job remains queued.') from error
    except Exception:
        if not claimed:
            raise
        return fail('processing_failed')
    except BaseException:
        stop()
        release()
        raise
    finally:
        if process is not None:
            _stop(process)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker-python', default=os.environ.get('SMARTPLAN_IMPORT_WORKER_PYTHON'),
                        help='Required absolute executable path, or SMARTPLAN_IMPORT_WORKER_PYTHON.')
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--ocr-languages', default='eng')
    parser.add_argument('--doctor', action='store_true', help='Validate the runner before opening the database.')
    parser.add_argument('--unsandboxed-development', action='store_true', help='Synthetic local fixtures only; never for server processing.')
    args = parser.parse_args(argv)
    if args.once and args.watch:
        parser.error('Use either --once or --watch.')
    if not args.worker_python:
        parser.error('Configure --worker-python or SMARTPLAN_IMPORT_WORKER_PYTHON before starting the worker.')
    worker_python = Path(args.worker_python)
    if not worker_python.is_absolute() or not worker_python.is_file() or not os.access(worker_python, os.X_OK):
        parser.error('Worker Python must be an existing absolute executable path.')
    runner = _ValidatedRunner(DevelopmentRunner(args.worker_python) if args.unsandboxed_development
                              else SandboxRunner(args.worker_python))
    try:
        readiness = runner.doctor(ocr_languages=args.ocr_languages)
    except SandboxUnavailable as error:
        print(json.dumps({'status': 'unavailable', 'message': str(error)}), flush=True)
        return 2
    if args.doctor:
        print(json.dumps(readiness), flush=True)
        return 0
    from online.store import PostgresOffice
    office = PostgresOffice(os.environ['SMARTPLAN_DATABASE_DSN'])
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(128 + signum))
    try:
        while True:
            result = work_one(office, runner=runner, ocr_languages=args.ocr_languages)
            # No source names, extracted text, raw parser diagnostics or secrets.
            print(json.dumps({'id': result['id'], 'status': result['status']} if result else {'status': 'idle'}), flush=True)
            if not args.watch:
                return 1 if result and result['status'] == 'failed' else 0
            if result is None:
                time.sleep(2)
    except SandboxUnavailable as error:
        print(json.dumps({'status': 'unavailable', 'message': str(error)}), flush=True)
        return 2
    finally:
        office.db.close()


if __name__ == '__main__':
    sys.exit(main())
