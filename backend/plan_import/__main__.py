"""Local import CLI; no HTTP endpoint, production database or external service."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

from .store import ImportStore, LeaseLost, StoreError, MAX_DERIVED_BYTES, MAX_RECOGNITION_BYTES


PROCESS_TIMEOUT_SECONDS = 55
ERROR_MESSAGE = "Lokale Verarbeitung fehlgeschlagen; das Original bleibt erhalten."


def _stop(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def _paths(store, job):
    if job["status"] == "needs_review":
        return {**job, "review_path": str(store.artifact_path(job["job_id"], "review.html")),
                "preview_path": str(store.artifact_path(job["job_id"], "preview.png")),
                "result_path": str(store.recognition_path(job["job_id"]))}
    return job


def work_one(store, *, job_id=None, ocr_languages="eng"):
    """Claim briefly, process outside SQLite, then publish only under a live lease."""
    if sys.platform != "linux":
        raise StoreError("Der isolierte Importworker benötigt Linux.")
    job = store.claim(worker_id="cli-" + uuid.uuid4().hex, job_id=job_id, lease_seconds=90)
    if job is None:
        return None
    process = None
    try:
        source = store.source_path(job["source_id"])
        # Private staging is on the store's filesystem. It never changes sources.
        with tempfile.TemporaryDirectory(prefix=".worker-", dir=store.root) as directory:
            os.chmod(directory, 0o700)
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
            environment["TMPDIR"] = directory
            environment["SMARTPLAN_IMPORT_SUPERVISED"] = "1"
            for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "OMP_THREAD_LIMIT",
                         "OPENCV_FOR_THREADS_NUM"):
                environment[name] = "1"
            arguments = [
                sys.executable, "-m", "plan_import.process", "--source", str(source),
                "--output", directory, "--sha256", job["sha256"],
                "--media-type", job["media_type"], "--page", str(job["page"]),
                "--ocr-languages", ocr_languages,
            ]
            with tempfile.TemporaryFile(dir=directory) as output, tempfile.TemporaryFile(dir=directory) as errors:
                process = subprocess.Popen(arguments, stdout=output, stderr=errors,
                                           stdin=subprocess.DEVNULL, start_new_session=True,
                                           env=environment)
                try:
                    process.wait(timeout=PROCESS_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired:
                    _stop(process)
                    return store.fail(job["job_id"], job["lease_token"],
                                      code="processing_timeout", message=ERROR_MESSAGE)
                # OCR shares this worker group, including descendants which
                # might otherwise outlive the parser's normal/error exit.
                _stop(process)
                output.seek(0)
                diagnostic = output.read(65537)
                if len(diagnostic) > 65536:
                    diagnostic = b""
                try:
                    outcome = json.loads(diagnostic)
                except (ValueError, UnicodeError):
                    outcome = {}
                if process.returncode != 0 or outcome.get("status") != "needs_review":
                    code = outcome.get("error_code", "processing_failed")
                    if not isinstance(code, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", code):
                        code = "processing_failed"
                    return store.fail(job["job_id"], job["lease_token"], code=code, message=ERROR_MESSAGE)
            derived = {}
            for name in ("preview.png", "review.html"):
                path = Path(directory) / name
                if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_DERIVED_BYTES:
                    raise StoreError("Ungültiges Verarbeitungsergebnis.")
                derived[name] = path.read_bytes()
            result_path = Path(directory) / "result.json"
            if (result_path.is_symlink() or not result_path.is_file() or
                    result_path.stat().st_size > MAX_RECOGNITION_BYTES):
                raise StoreError("Ungültiges Erkennungsergebnis.")
            result = json.loads(result_path.read_bytes())
            if (result.get("status") != "needs_review" or
                    result.get("source", {}).get("sha256") != job["sha256"]):
                raise StoreError("Erkennungsergebnis gehört nicht zur Quelle.")
            published = store.complete(job["job_id"], job["lease_token"],
                                       derived=derived, recognition=result)
            return _paths(store, published)
    except LeaseLost:
        # A slow/dead attempt cannot replace a newer attempt or its result.
        return store.status(job["job_id"])
    except Exception:
        try:
            return store.fail(job["job_id"], job["lease_token"],
                              code="processing_failed", message=ERROR_MESSAGE)
        except LeaseLost:
            return store.status(job["job_id"])
    finally:
        if process is not None:
            _stop(process)


def doctor():
    packages = {}
    for name in ("pillow", "numpy", "opencv-python-headless", "pypdfium2"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    binary = shutil.which("tesseract")
    languages, tesseract_version = [], None
    if binary:
        try:
            completed = subprocess.run([binary, "--list-langs"], stdin=subprocess.DEVNULL,
                                       capture_output=True, timeout=5, check=True)
            languages = [line.strip() for line in completed.stdout.decode("utf-8", errors="replace").splitlines()
                         if re.fullmatch(r"[a-zA-Z0-9_]+", line.strip())]
            completed = subprocess.run([binary, "--version"], stdin=subprocess.DEVNULL,
                                       capture_output=True, timeout=5, check=True)
            tesseract_version = completed.stdout.decode("utf-8", errors="replace").splitlines()[0][:100]
        except (OSError, subprocess.SubprocessError, IndexError):
            languages = []
    return {
        "ready": sys.platform == "linux" and all(packages.values()) and "eng" in languages,
        "platform": sys.platform, "packages": packages,
        "ocr": {"version": tesseract_version, "installed_languages": languages,
                "scope": "printed_text_only"},
        "formats": ["image/jpeg", "image/png", "application/pdf"],
        "unsupported": ["HEIC", "DXF", "DWG", "encrypted_pdf"],
        "external_processing": False,
        "note": "Importkern; keine Kamera-/App-Anbindung, Wandsemantik oder Handschriftauswertung.",
    }


def _parser():
    parser = argparse.ArgumentParser(description="Lokaler Foto-/PDF-Importkern, ohne externen Auswertungsdienst.")
    parser.add_argument("--store", help="Eigener privater Importordner; keine Office-Datenbank.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Lokale Abhängigkeiten anzeigen.")
    for name in ("submit", "run"):
        command = commands.add_parser(name)
        command.add_argument("source")
        command.add_argument("--request-id", default=None)
        command.add_argument("--page", type=int, default=1, help="PDF-Seite, beginnend mit 1.")
        if name == "run":
            command.add_argument("--ocr-languages", default="eng")
    command = commands.add_parser("status")
    command.add_argument("job_id")
    command = commands.add_parser("work")
    command.add_argument("--job", default=None)
    command.add_argument("--watch", action="store_true", help="Warteschlange bis Strg+C abarbeiten.")
    command.add_argument("--ocr-languages", default="eng")
    return parser


def main(argv=None):
    parser = _parser()
    args = parser.parse_args(argv)
    def terminate(signum, frame):
        # Unwind work_one's finally on a normal service/terminal termination.
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, terminate)
    if args.command == "doctor":
        result = doctor()
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0 if result["ready"] else 1
    if not args.store:
        parser.error("--store ist für Aufträge erforderlich.")
    try:
        store = ImportStore(args.store)
        if args.command in ("submit", "run"):
            if not 1 <= args.page <= 50:
                raise StoreError("PDF-Seite muss zwischen 1 und 50 liegen.")
            job = store.capture(args.source, request_id=args.request_id or uuid.uuid4().hex,
                                page=args.page - 1)
            if args.command == "run" and job["status"] in ("queued", "running"):
                job = work_one(store, job_id=job["job_id"], ocr_languages=args.ocr_languages) or store.status(job["job_id"])
            result = _paths(store, job)
        elif args.command == "status":
            result = _paths(store, store.status(args.job_id))
        else:
            while True:
                result = work_one(store, job_id=args.job, ocr_languages=args.ocr_languages)
                if result is None:
                    result = {"status": "idle"}
                if not args.watch:
                    break
                print(json.dumps(result, ensure_ascii=False, allow_nan=False), flush=True)
                if result["status"] == "idle":
                    time.sleep(2)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 1 if result["status"] == "failed" else 0
    except StoreError as error:
        print(json.dumps({"status": "error", "message": str(error)}, ensure_ascii=False))
        return 1
    except KeyboardInterrupt:
        print(json.dumps({"status": "interrupted", "message": "Originale bleiben erhalten; unterbrochene Aufträge werden nach Ablauf ihrer Lease wieder aufgenommen."}))
        return 130


if __name__ == "__main__":
    sys.exit(main())
