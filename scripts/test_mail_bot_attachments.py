"""Portable attachment-client contracts with actual private files; no network."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

if os.name == "posix":
    import test_mail_bot as body_fixture
    from core import Office
    from online.web import create_app
    from cryptography.fernet import Fernet


DIRECTORY = Path(__file__).resolve().parents[1] / "integrations/mail_bot"
spec = importlib.util.spec_from_file_location("smartplan_attachment_bot", DIRECTORY / "send_attachments.py")
bot = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(DIRECTORY))
try:
    spec.loader.exec_module(bot)
finally:
    sys.path.pop(0)


class Reply(io.BytesIO):
    def __init__(self, value, status=200, content_type="application/json", raw=None):
        super().__init__(json.dumps(value).encode() if raw is None else raw)
        self.status = status
        self.headers = {"Content-Type": content_type}


class AttachmentClient(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="smartplan-attachment-bot-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.original = self.directory / "original-private.pdf"
        self.content = b"Original synthetic PDF-like bytes; never parse or execute.\x00" + b"x" * bot.CHUNK_SIZE
        self.private(self.original, self.content)
        self.manifest = self.directory / "manifest-private.json"
        self.value = {"source_account": "office@example.test", "source_id": "native-mail-17", "attachments": [{
            "source_attachment_id": "native-attachment-0001", "filename": "Synthetic ü.pdf",
            "media_type": "application/pdf", "path": self.original.name}]}
        self.save_manifest()
        self.token = "opaque"
        self.env = patch.dict(os.environ, {"SMARTPLAN_INTAKE_TOKEN": self.token})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.requests, self.chunks = [], {}
        self.row, self.phase = None, "uploading"
        self.hook = None
        self.lost_chunk = False
        self.transport = patch.object(bot.urllib.request, "build_opener", side_effect=self.opener)
        self.transport.start()
        self.addCleanup(self.transport.stop)

    def private(self, path, contents):
        path.write_bytes(contents)
        path.chmod(0o600)

    def save_manifest(self):
        self.private(self.manifest, json.dumps(self.value, ensure_ascii=False).encode())

    def opener(self, *handlers):
        self.assertEqual(len(handlers), 1)
        self.assertIsInstance(handlers[0], bot.NoRedirect)
        return self

    def batch(self):
        files = [] if self.row is None else [{**self.row, "status": self.phase,
                                             "received_chunks": sorted(self.chunks)}]
        ready = sum(item["status"] == "ready" for item in files)
        deleted = sum(item["status"] == "deleted" for item in files)
        return {"status": "complete" if ready + deleted == len(files) else "uploading",
                "expected_count": len(files), "ready_count": ready, "deleted_count": deleted,
                "total_bytes": sum(item["size"] for item in files), "chunk_size": bot.CHUNK_SIZE, "files": files}

    def open(self, request, timeout):
        self.assertEqual(timeout, 20)
        self.assertEqual(request.get_header("Authorization"), "Bearer " + self.token)
        self.assertTrue(request.full_url == bot.ENDPOINT or request.full_url.startswith(bot.ENDPOINT + "/"))
        self.requests.append(request)
        if self.hook:
            result = self.hook(request)
            if result is not None:
                return result
        if request.full_url == bot.ENDPOINT:
            self.assertEqual(request.get_method(), "POST")
            payload = json.loads(request.data)
            self.assertEqual(set(payload), {"source_account", "source_id", "attachments"})
            self.assertEqual(payload["source_id"], self.value["source_id"])
            if payload["attachments"]:
                descriptor = payload["attachments"][0]
                if self.row:
                    self.assertEqual({key: self.row[key] for key in bot.DESCRIPTOR_FIELDS}, descriptor)
                else:
                    self.row = {"id": "a" * 32, **descriptor}
            return Reply(self.batch(), status=201)
        if "/chunks/" in request.full_url:
            self.assertEqual(request.get_method(), "PUT")
            self.assertEqual(request.get_header("Content-type"), "application/octet-stream")
            index = int(request.full_url.rsplit("/", 1)[1])
            if index in self.chunks:
                self.assertEqual(self.chunks[index], request.data)
            self.chunks[index] = request.data
            if self.lost_chunk:
                self.lost_chunk = False
                raise urllib.error.URLError("Synthetic lost acknowledgement; no credential logging")
            return Reply(self.batch()["files"][0])
        self.assertTrue(request.full_url.endswith("/complete"))
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(json.loads(request.data), {})
        self.assertEqual(b"".join(self.chunks[index] for index in sorted(self.chunks)), self.content)
        self.phase = "ready"
        return Reply(self.batch()["files"][0])

    def cli(self, mode="--send", *extra):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = bot.main(["--manifest", str(self.manifest), mode, *extra])
        output = out.getvalue() + err.getvalue()
        self.assertNotIn(self.token, output)
        self.assertNotIn(self.original.name, output)
        self.assertNotIn("Synthetic ü.pdf", output)
        self.assertNotIn(self.value["source_id"], output)
        return code, json.loads(out.getvalue() or err.getvalue())

    def test_check_hashes_actual_original_without_credentials_or_network(self):
        with patch.dict(os.environ, {}, clear=True):
            code, result = self.cli("--check")
        self.assertEqual((code, result), (0, {"status": "validated", "sent": False, "expected_count": 1}))
        payload, _ = bot.load_manifest(self.manifest)
        self.assertEqual(payload["attachments"][0]["sha256"], hashlib.sha256(self.content).hexdigest())
        self.assertEqual(payload["attachments"][0]["size"], len(self.content))
        self.assertEqual(self.requests, [])
        self.assertEqual(self.original.read_bytes(), self.content)

    def test_real_bytes_are_chunked_and_only_final_complete_set_confirms_success(self):
        code, result = self.cli()
        self.assertEqual(code, 0)
        self.assertEqual(result, {"status": "complete", "expected_count": 1, "ready_count": 1,
                                  "deleted_count": 0, "total_bytes": len(self.content)})
        self.assertEqual([len(self.chunks[i]) for i in sorted(self.chunks)], [bot.CHUNK_SIZE, len(self.content) - bot.CHUNK_SIZE])
        self.assertEqual(b"".join(self.chunks[i] for i in sorted(self.chunks)), self.content)
        self.assertEqual(self.original.read_bytes(), self.content)
        self.assertEqual(sum(request.full_url == bot.ENDPOINT for request in self.requests), 2)

    def test_lost_chunk_receipt_resumes_from_server_without_reposting_parent_body(self):
        self.lost_chunk = True
        code, result = self.cli()
        self.assertEqual((code, result["status"], result["error"]), (3, "pending", "NETWORK_UNCONFIRMED"))
        self.assertEqual(set(self.chunks), {0})
        self.requests.clear()
        code, result = self.cli()
        self.assertEqual((code, result["status"]), (0, "complete"))
        puts = [request.full_url for request in self.requests if request.get_method() == "PUT"]
        self.assertEqual(puts, [bot.ENDPOINT + "/" + "a" * 32 + "/chunks/1"])
        self.assertFalse(any(request.full_url == bot.ENDPOINT.removesuffix("/attachments") for request in self.requests))

    def test_empty_manifest_is_explicit_complete_and_existing_deleted_files_are_not_revived(self):
        self.value["attachments"] = []
        self.save_manifest()
        code, result = self.cli()
        self.assertEqual((code, result["status"], result["expected_count"]), (0, "complete", 0))
        self.assertTrue(all(request.full_url == bot.ENDPOINT for request in self.requests))
        self.value["attachments"] = [{"source_attachment_id": "original-attachment", "filename": "Retained.pdf",
                                      "media_type": "application/pdf", "path": self.original.name}]
        self.save_manifest()
        self.phase, self.requests = "deleted", []
        code, result = self.cli()
        self.assertEqual((code, result["ready_count"], result["deleted_count"]), (0, 0, 1))
        self.assertTrue(all(request.full_url == bot.ENDPOINT for request in self.requests))

    def test_ready_files_are_not_uploaded_again(self):
        self.assertEqual(self.cli()[0], 0)
        self.requests.clear()
        self.assertEqual(self.cli()[0], 0)
        self.assertTrue(all(request.full_url == bot.ENDPOINT for request in self.requests))

    def test_foreign_ids_metadata_counts_and_chunk_claims_never_confirm(self):
        for field, bad in (("chunk_size", 1), ("expected_count", True), ("ready_count", 1),
                           ("deleted_count", 1), ("total_bytes", 0), ("status", "complete")):
            with self.subTest(field=field):
                self.row = None
                def wrong(request):
                    if request.full_url != bot.ENDPOINT:
                        self.fail("Malformed batch must stop before binary upload")
                    expected = bot.load_manifest(self.manifest)[0]["attachments"][0]
                    self.row = {"id": "a" * 32, **expected}
                    reply = self.batch();reply[field] = bad
                    return Reply(reply, 201)
                self.hook = wrong
                self.assertEqual(self.cli()[1]["error"], "UNCONFIRMED_ATTACHMENTS")
        self.row = None
        for field, bad in (("id", "../foreign"), ("sha256", "b" * 64), ("size", True),
                           ("source_attachment_id", "foreign-source"), ("received_chunks", [0, 0]),
                           ("received_chunks", [80]), ("received_chunks", [False])):
            with self.subTest(file_field=field):
                def wrong_file(request):
                    expected = bot.load_manifest(self.manifest)[0]["attachments"][0]
                    self.row = {"id": "a" * 32, **expected}
                    reply = self.batch();reply["files"][0][field] = bad
                    return Reply(reply, 201)
                self.hook = wrong_file
                self.assertEqual(self.cli()[1]["error"], "UNCONFIRMED_ATTACHMENTS")

    def test_wrong_chunk_or_complete_receipts_remain_pending(self):
        for phase in ("chunk", "complete"):
            with self.subTest(phase=phase):
                self.row, self.chunks, self.phase = None, {}, "uploading"
                def wrong(request):
                    if (phase == "chunk" and "/chunks/" in request.full_url
                            or phase == "complete" and request.full_url.endswith("/complete")):
                        reply = self.batch()["files"][0]
                        reply["id"] = "b" * 32
                        return Reply(reply)
                self.hook = wrong
                self.assertEqual(self.cli()[1]["error"], "UNCONFIRMED_ATTACHMENTS")

    def test_final_complete_cannot_substitute_a_different_server_file_id(self):
        def substitute(request):
            if request.full_url == bot.ENDPOINT and self.phase == "ready":
                reply = self.batch()
                reply["files"][0]["id"] = "b" * 32
                return Reply(reply, 201)
        self.hook = substitute
        self.assertEqual(self.cli()[1]["error"], "UNCONFIRMED_ATTACHMENTS")

    def test_network_server_update_auth_limit_and_redirect_errors_are_sanitized_without_retry(self):
        for status in (301, 400, 401, 403, 404, 409, 413, 429, 500, 503):
            with self.subTest(status=status):
                self.requests.clear()
                def failed(request):
                    raise urllib.error.HTTPError(request.full_url, status, "DO NOT PRINT " + self.token,
                                                 {"Retry-After": "300"}, io.BytesIO(b"private server body"))
                self.hook = failed
                code, result = self.cli()
                self.assertEqual((code, result["status"], result["http_status"]), (3, "pending", status))
                self.assertEqual(len(self.requests), 1)
                self.assertEqual(result["retry_after_seconds"], 300)
                if status == 404:
                    self.assertEqual(result["error"], "SERVER_UPDATE_OR_PARENT_REQUIRED")

    def test_nonjson_truncated_or_oversized_receipt_is_not_success(self):
        for reply in (lambda: Reply({}, content_type="text/html"),
                      lambda: Reply({}, raw=b"not json"),
                      lambda: Reply({}, raw=b"x" * (bot.MAX_RECEIPT_BYTES + 1)),
                      lambda: Reply({}, status=204)):
            with self.subTest(reply=reply):
                self.hook = lambda request: reply()
                self.assertEqual(self.cli()[0], 3)

    def test_changed_original_after_preflight_is_visible_and_never_deleted(self):
        def mutate(request):
            if request.full_url == bot.ENDPOINT:
                self.private(self.original, self.content + b"changed")
        self.hook = mutate
        code, result = self.cli()
        self.assertEqual((code, result["error"]), (3, "ATTACHMENT_CHANGED"))
        self.assertEqual(len(self.requests), 1)
        self.assertTrue(self.original.read_bytes().endswith(b"changed"))

    def test_original_size_manifest_count_and_identity_limits_are_enforced_before_network(self):
        variants = [dict(self.value, source_id="<not-native@example.test>"),
                    dict(self.value, attachments=self.value["attachments"] * 31),
                    dict(self.value, attachments=self.value["attachments"] * 2)]
        for value in variants:
            with self.subTest(value=value["source_id"]):
                self.private(self.manifest, json.dumps(value).encode())
                self.assertEqual(self.cli("--check")[0], 2)
        self.save_manifest()
        with self.original.open("r+b") as stream:
            stream.truncate(bot.MAX_FILE_BYTES + 1)
        self.assertEqual(self.cli("--check")[1]["error"], "ATTACHMENT_SIZE_LIMIT")
        self.assertEqual(self.requests, [])

    def test_actual_twenty_mib_file_and_sixty_mib_mail_boundary(self):
        with self.original.open("r+b") as stream:
            stream.truncate(20 * 1024 * 1024)
        descriptor = self.value["attachments"][0]
        self.value["attachments"] = [dict(descriptor, source_attachment_id="native-" + str(i)) for i in range(3)]
        self.save_manifest()
        self.assertEqual(self.cli("--check")[0], 0)
        extra = self.directory / "one-byte.bin"
        self.private(extra, b"x")
        self.value["attachments"].append(dict(descriptor, source_attachment_id="native-last", path=extra.name))
        self.save_manifest()
        self.assertEqual(self.cli("--check")[1]["error"], "ATTACHMENT_TOTAL_LIMIT")
        self.assertEqual(self.requests, [])

    @unittest.skipUnless(os.name == "posix", "POSIX file identity and private mode checks")
    def test_fifo_symlink_and_public_files_fail_without_blocking_or_network(self):
        self.original.unlink()
        os.mkfifo(self.original, 0o600)
        self.assertEqual(self.cli("--check")[1]["error"], "UNSAFE_ATTACHMENT_FILE")
        self.original.unlink()
        target = self.directory / "private-real.bin"
        self.private(target, b"kept")
        self.original.symlink_to(target)
        self.assertEqual(self.cli("--check")[1]["error"], "UNSAFE_ATTACHMENT_FILE")
        self.original.unlink()
        self.private(self.original, b"kept")
        self.original.chmod(0o644)
        self.assertEqual(self.cli("--check")[1]["error"], "UNSAFE_ATTACHMENT_FILE")
        self.assertEqual(self.requests, [])

    def test_stdlib_subprocess_check_works_without_backend_or_credentials(self):
        environment = {key: value for key, value in os.environ.items() if key not in ("PYTHONPATH", "SMARTPLAN_INTAKE_TOKEN")}
        result = subprocess.run([sys.executable, str(DIRECTORY / "send_attachments.py"),
                                 "--manifest", str(self.manifest), "--check"],
                                cwd=self.directory, env=environment, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "validated")
        self.assertNotIn(str(self.original), result.stdout + result.stderr)


@unittest.skipUnless(os.name == "posix", "Real online receiver is POSIX-only; portable client tests remain mandatory")
class AttachmentHttpAcceptance(unittest.TestCase):
    def setUp(self):
        self.fixture = body_fixture.MailBotHttpAcceptance("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.directory = Path(self.fixture.temp.name)
        self.original = self.directory / "private-original.pdf"
        self.content = b"%PDF-original-private-" + b"z" * bot.CHUNK_SIZE
        self.original.write_bytes(self.content)
        self.original.chmod(0o600)
        self.manifest = self.directory / "private-attachments.json"
        self.manifest.write_text(json.dumps({
            "source_account": self.fixture.payload["source_account"],
            "source_id": self.fixture.payload["source_id"], "attachments": [{
                "source_attachment_id": "native-file-01", "filename": "Original.pdf", "media_type": "application/pdf",
                "path": self.original.name}]}), encoding="utf-8")
        self.manifest.chmod(0o600)
        self.client, self.office = self.fixture.client, self.fixture.office
        self.lost = False
        self.requests = []
        transport = patch.object(bot.urllib.request, "build_opener", return_value=self)
        transport.start()
        self.addCleanup(transport.stop)

    def open(self, request, timeout):
        self.assertEqual(timeout, 20)
        self.assertTrue(request.full_url.startswith(bot.ENDPOINT))
        self.requests.append(request)
        response = self.client.open(request.full_url.removeprefix(self.fixture.base),
                                    method=request.get_method(), data=request.data,
                                    headers=dict(request.header_items()), base_url=self.fixture.base)
        if self.lost and request.get_method() == "PUT":
            self.lost = False
            raise urllib.error.URLError("Synthetic lost response after database commit")
        if response.status_code >= 400:
            raise urllib.error.HTTPError(request.full_url, response.status_code, "private", response.headers,
                                         io.BytesIO(response.data))
        return Reply(None, status=response.status_code, content_type=response.content_type, raw=response.data)

    def deliver(self):
        payload, originals = bot.load_manifest(self.manifest)
        return bot.send_attachments(payload, originals, self.fixture.connector["token"])

    def test_actual_parent_lookup_resume_after_reopen_preserves_original_and_single_inquiry(self):
        parent = self.fixture.call("/intake/gmail", self.fixture.payload, self.fixture.connector["token"])
        self.assertEqual(parent.status_code, 201)
        self.lost = True
        with self.assertRaises(bot.DeliveryError) as interrupted:
            self.deliver()
        self.assertEqual(interrupted.exception.code, "NETWORK_UNCONFIRMED")
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiry_attachment_chunks').fetchone()[0], 1)
        # A new receiver/controller instance consumes only committed database state.
        reopened = Office(self.directory / "office.db")
        self.addCleanup(reopened.db.close)
        app = create_app(office=reopened, key=Fernet.generate_key(), host="office.smartplan-hofmann.de")
        self.client, self.office, self.requests = app.test_client(), reopened, []
        result = self.deliver()
        self.assertEqual((result["status"], result["ready_count"]), ("complete", 1))
        puts = [request.full_url for request in self.requests if request.get_method() == "PUT"]
        self.assertEqual(len(puts), 1)
        self.assertTrue(puts[0].endswith('/chunks/1'))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiries').fetchone()[0], 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiry_attachments').fetchone()[0], 1)
        stored = b''.join(bytes(row[0]) for row in self.office.db.execute(
            'SELECT data FROM inquiry_attachment_chunks ORDER BY chunk_index'))
        self.assertEqual(stored, self.content)
        self.assertEqual(self.original.read_bytes(), self.content)
        self.assertEqual(self.deliver()["status"], "complete")

    def test_parent_not_reposted_or_invented_when_only_attachments_are_requested(self):
        with self.assertRaises(bot.DeliveryError) as missing:
            self.deliver()
        self.assertEqual((missing.exception.http_status, missing.exception.code),
                         (404, "SERVER_UPDATE_OR_PARENT_REQUIRED"))
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiries').fetchone()[0], 0)
        self.assertEqual(self.original.read_bytes(), self.content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
