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

PROCESS_TIMEOUT_SECONDS = 55


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


def work_one(office, *, worker_python=None, process_timeout=PROCESS_TIMEOUT_SECONDS, ocr_languages='eng'):
    """Claim/publish briefly; original bytes and all results remain in the DB."""
    if sys.platform != 'linux':
        raise RuntimeError('The supervised import worker requires Linux.')
    if not isinstance(process_timeout, (int, float)) or not 1 <= process_timeout <= 60:
        raise ValueError('A bounded parser timeout of at most 60 seconds is required.')
    if not isinstance(ocr_languages, str) or not re.fullmatch(r'[A-Za-z0-9_]+(?:\+[A-Za-z0-9_]+)*', ocr_languages):
        raise ValueError('Local OCR language IDs required')
    imports = PlanImports(office)
    with office.lock, office.db:
        job = imports.claim(lease_seconds=90)
        if job is None:
            return None
    process = None

    def fail(code):
        with office.lock, office.db:
            try:
                return imports.fail(job['id'], job['lease_token'], code)
            except LeaseLost:
                return imports._status(imports._row(job['id']))

    try:
        with office.lock, office.db:
            imports._lease(job['id'], job['lease_token'])
            source = imports.source_bytes(job)
        with tempfile.TemporaryDirectory(prefix='smartplan-project-import-') as directory:
            stage = Path(directory)
            source_path = stage / 'source.bin'
            descriptor = os.open(source_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(source)
            arguments = [os.fspath(worker_python or sys.executable), '-m', 'plan_import.process',
                         '--source', str(source_path), '--output', str(stage), '--sha256', job['sha256'],
                         '--media-type', job['media_type'], '--page', str(job['page']),
                         '--ocr-languages', ocr_languages]
            with tempfile.TemporaryFile(dir=stage) as output, tempfile.TemporaryFile(dir=stage) as errors:
                process = subprocess.Popen(arguments, stdin=subprocess.DEVNULL, stdout=output, stderr=errors,
                                           env=child_environment(stage), start_new_session=True)
                try:
                    process.wait(timeout=process_timeout)
                except subprocess.TimeoutExpired:
                    _stop(process)
                    return fail('processing_timeout')
                _stop(process)
                output.seek(0)
                diagnostic = output.read(65537)
                try:
                    outcome = json.loads(diagnostic) if len(diagnostic) <= 65536 else {}
                except (ValueError, UnicodeError):
                    outcome = {}
                if process.returncode != 0 or not isinstance(outcome, dict) or outcome.get('status') != 'needs_review':
                    return fail(outcome.get('error_code', 'processing_failed') if isinstance(outcome, dict) else 'processing_failed')
            preview = _read(stage / 'preview.png', MAX_PREVIEW_BYTES)
            result = json.loads(_read(stage / 'result.json', MAX_RESULT_BYTES))
            with office.lock, office.db:
                return imports.publish(job['id'], job['lease_token'], preview=preview, result=result)
    except LeaseLost:
        with office.lock, office.db:
            return imports._status(imports._row(job['id']))
    except Exception:
        return fail('processing_failed')
    finally:
        if process is not None:
            _stop(process)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker-python', default=os.environ.get('SMARTPLAN_IMPORT_WORKER_PYTHON'))
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--ocr-languages', default='eng')
    args = parser.parse_args(argv)
    if args.once and args.watch:
        parser.error('Use either --once or --watch.')
    from online.store import PostgresOffice
    office = PostgresOffice(os.environ['SMARTPLAN_DATABASE_DSN'])
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(128 + signum))
    try:
        while True:
            result = work_one(office, worker_python=args.worker_python, ocr_languages=args.ocr_languages)
            # No source names, extracted text, raw parser diagnostics or secrets.
            print(json.dumps({'id': result['id'], 'status': result['status']} if result else {'status': 'idle'}), flush=True)
            if not args.watch:
                return 0
            if result is None:
                time.sleep(2)
    finally:
        office.db.close()


if __name__ == '__main__':
    sys.exit(main())
