"""Portable stdlib client contracts and POSIX server acceptance; synthetic only."""
from contextlib import redirect_stderr, redirect_stdout
from email.message import Message
import http.client
import importlib.util
import io
import json
import hashlib
import os
from pathlib import Path
import tempfile
import shutil
import time
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
import urllib.response
import zipfile
from urllib.parse import urlsplit

# The distributable client and archive use only Python's standard library.
# The online server is a POSIX deployment target; never import it on Windows.
if os.name == "posix":
    from cryptography.fernet import Fernet
    from core import Office
    from online.auth import totp
    from online.web import create_app


BUILD_OPENER = urllib.request.build_opener
ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "integrations" / "mail_bot"
spec = importlib.util.spec_from_file_location("smartplan_mail_bot", DIRECTORY / "send_inquiry.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)
pack_spec = importlib.util.spec_from_file_location("smartplan_mail_bot_package", DIRECTORY / "package.py")
package = importlib.util.module_from_spec(pack_spec)
pack_spec.loader.exec_module(package)


class Reply(io.BytesIO):
    def __init__(self, status, raw, content_type="application/json"):
        super().__init__(raw)
        self.status = status
        self.headers = {"Content-Type": content_type}


class ClientFixture:
    """Synthetic files, credentials and mocked transport; no test methods or server."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="smartplan-mail-bot-synthetic-")
        self.addCleanup(self.temp.cleanup)
        self.connector = {"token": "SPIN_" + "Z" * 43}
        self.payload = json.loads((DIRECTORY / "examples" / "inquiry.json").read_text(encoding="utf-8"))
        self.payload.update(source_account="office@example.test", source_id="synthetic-native-id-17")
        self.input = Path(self.temp.name) / "immutable-original.json"
        self.input.write_text(json.dumps(self.payload, ensure_ascii=False), encoding="utf-8")
        self.calls = []
        self.env = patch.dict(os.environ, {"SMARTPLAN_INTAKE_TOKEN": self.connector["token"]})
        self.env.start()
        self.addCleanup(self.env.stop)

    def _start_transport(self):
        self.transport = patch.object(bot.urllib.request, "build_opener",
                                      side_effect=lambda *handlers: self._opener(handlers))
        self.transport.start()
        self.addCleanup(self.transport.stop)

    def _opener(self, handlers):
        self.assertEqual(len(handlers), 1)
        self.assertIsInstance(handlers[0], bot.NoRedirect)
        return self

    def _check_request(self, request, timeout):
        self.assertEqual(request.full_url, bot.ENDPOINT)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(timeout, 20)
        self.calls.append(request.full_url)

    def open(self, request, timeout):
        self._check_request(request, timeout)
        raise AssertionError("Client contract must supply an explicit synthetic HTTP reply")

    def run_cli(self, *extra):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = bot.main(["--input", str(self.input), *extra])
        self.assertNotIn(self.connector["token"], out.getvalue() + err.getvalue())
        self.assertNotIn(self.payload["message"], out.getvalue() + err.getvalue())
        return code, out.getvalue(), err.getvalue()


class MailBotClient(ClientFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self._start_transport()

    def test_check_is_explicitly_local_and_validates_real_example_without_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            code, output, error = self.run_cli("--check")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(json.loads(output), {"status": "validated", "sent": False})
        self.assertEqual(self.calls, [])

    def test_opaque_bound_credential_is_not_rejected_by_its_visible_format(self):
        handle = "opaque"
        receipt = {"id": "b" * 32, "status": "received",
                   "ingested_at": "2026-10-24T09:00:00+00:00"}
        seen = []

        def gateway(request, timeout):
            self._check_request(request, timeout)
            seen.append(request.get_header("Authorization"))
            return Reply(201, json.dumps(receipt).encode())

        with patch.dict(os.environ, {"SMARTPLAN_INTAKE_TOKEN": handle}):
            with patch.object(self, "open", side_effect=gateway):
                code, output, error = self.run_cli("--send")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(json.loads(output), receipt)
        self.assertEqual(seen, ["Bearer " + handle])
        self.assertNotIn(handle, output + error)

    def test_credential_header_injection_is_rejected_before_transport(self):
        for credential in ("", "a b", "a\tb", "a\nb", "a\rb", "a\x7fb",
                           "ä", "a" * 194, None, 123456):
            with self.subTest(kind=type(credential).__name__):
                with self.assertRaises(bot.DeliveryError):
                    bot.send_envelope(self.payload, credential)
        self.assertEqual(self.calls, [])

    def test_invalid_or_extra_business_fields_never_reach_network(self):
        variants = (
            {**self.payload, "customer_id": "a" * 32},
            {**self.payload, "status": "accepted"},
            {**self.payload, "attachments": ["not allowed"]},
            {**self.payload, "source_id": "<rfc-message-id@example.test>"},
            {**self.payload, "source_id": ""},
            {**self.payload, "message": " "},
            {**self.payload, "message": "x" * 40001},
            {**self.payload, "subject": "Header\ninjection"},
            {**self.payload, "received_at": "2026-10-24T10:00:00"},
            {**self.payload, "received_at": None},
            {**self.payload, "source_account": "not-an-email"},
        )
        for value in variants:
            with self.subTest(keys=list(value), source=value.get("source_id")):
                with self.assertRaises(bot.DeliveryError):
                    bot.send_envelope(value, self.connector["token"])
        self.assertEqual(self.calls, [])

    def test_duplicate_json_fields_nonfinite_values_and_oversized_files_fail_locally(self):
        for raw in (b'{"source_id":"first","source_id":"second"}',
                    b'{"message":NaN}', b"\xff", b" " * 200001):
            self.input.write_bytes(raw)
            code, output, error = self.run_cli("--check")
            self.assertEqual(code, 2)
            self.assertEqual(output, "")
            self.assertEqual(json.loads(error)["status"], "not_sent")
        self.assertEqual(self.calls, [])

    def test_http_errors_are_bounded_sanitized_and_keep_original_for_retry(self):
        original = self.input.read_bytes()
        for status in (302, 401, 409, 413, 429, 500, 503):
            with self.subTest(status=status):
                raw = (self.connector["token"] + self.payload["message"]).encode()
                error = urllib.error.HTTPError(bot.ENDPOINT, status, "secret", {}, io.BytesIO(raw))
                with patch.object(self, "open", side_effect=error):
                    code, output, message = self.run_cli("--send")
                self.assertEqual(code, 3)
                self.assertEqual(output, "")
                self.assertEqual(json.loads(message)["http_status"], status)
                self.assertEqual(self.input.read_bytes(), original)

    def test_only_complete_success_receipts_count_as_delivered(self):
        good = {"id": "a" * 32, "status": "received", "ingested_at": "2026-10-24T09:00:00+00:00"}
        variants = (
            Reply(200, json.dumps(good).encode()),
            Reply(201, b"<html>not a receipt</html>", "text/html"),
            Reply(201, b" " * 4097),
            Reply(201, b"invalid json"),
            Reply(201, json.dumps({**good, "status": "queued"}).encode()),
            Reply(201, json.dumps({**good, "id": "x"}).encode()),
            Reply(201, json.dumps({**good, "ingested_at": "2026-10-24T09:00:00"}).encode()),
        )
        for response in variants:
            with self.subTest(status=response.status):
                with patch.object(self, "open", return_value=response):
                    code, output, error = self.run_cli("--send")
                self.assertEqual(code, 3)
                self.assertEqual(output, "")
                self.assertEqual(json.loads(error)["status"], "unconfirmed")
        with patch.object(self, "open", return_value=Reply(
                201, json.dumps({**good, "extra": "confidential unexpected field"}).encode())):
            code, output, error = self.run_cli("--send")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(json.loads(output), good)

    def test_malformed_or_interrupted_http_is_unconfirmed_without_raw_provider_text(self):
        confidential = (self.connector["token"] + self.payload["message"]).encode()
        for error in (http.client.BadStatusLine(confidential.decode()),
                      http.client.IncompleteRead(confidential, 100)):
            with patch.object(self, "open", side_effect=error):
                code, output, message = self.run_cli("--send")
            self.assertEqual(code, 3)
            self.assertEqual(output, "")
            self.assertEqual(json.loads(message), {
                "status": "unconfirmed", "error": "NETWORK_UNCONFIRMED"})

    def test_plaintext_key_as_accidental_argument_is_not_echoed(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            with self.assertRaises(SystemExit) as failure:
                bot.main(["--input", str(self.input), "--send", "--token", self.connector["token"]])
        self.assertEqual(failure.exception.code, 2)
        self.assertNotIn(self.connector["token"], out.getvalue() + err.getvalue())
        self.assertEqual(json.loads(err.getvalue())["error"], "INVALID_ARGUMENTS")

    def test_private_key_file_is_an_alternative_to_environment(self):
        secret = Path(self.temp.name) / "private-token"
        secret.write_text(self.connector["token"], encoding="utf-8")
        secret.chmod(0o600)
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(bot.load_token(secret), self.connector["token"])
        with self.assertRaises(bot.DeliveryError) as failure:
            bot.load_token(secret)
        self.assertEqual(failure.exception.code, "USE_ONE_CREDENTIAL_SOURCE")
        if os.name == "posix":
            with patch.dict(os.environ, {}, clear=True):
                secret.chmod(0o640)
                with self.assertRaises(bot.DeliveryError) as failure:
                    bot.load_token(secret)
                self.assertEqual(failure.exception.code, "UNSAFE_CREDENTIAL_FILE")
                secret.chmod(0o600)
                link = Path(self.temp.name) / "token-link"
                link.symlink_to(secret)
                with self.assertRaises(bot.DeliveryError) as failure:
                    bot.load_token(link)
                self.assertEqual(failure.exception.code, "UNSAFE_CREDENTIAL_FILE")
                fifo = Path(self.temp.name) / "not-a-credential-file"
                os.mkfifo(fifo, mode=0o600)
                with self.assertRaises(bot.DeliveryError) as failure:
                    bot.load_token(fifo)
                self.assertEqual(failure.exception.code, "UNSAFE_CREDENTIAL_FILE")

    def test_real_stdlib_redirect_pipeline_never_forwards_the_bearer(self):
        seen = []

        class FakeHTTPS(urllib.request.HTTPSHandler):
            def https_open(self, request):
                seen.append(request.full_url)
                headers = Message()
                headers["Location"] = "https://example.test/credential-collector"
                response = urllib.response.addinfourl(io.BytesIO(b"confidential"), headers,
                                                       request.full_url, 302)
                response.msg = "Found"
                return response

        # Use Python's actual opener/redirect/error pipeline with only the
        # network layer replaced. It must never request the Location target.
        opener = BUILD_OPENER(bot.NoRedirect(), FakeHTTPS())
        with patch.object(bot.urllib.request, "build_opener", return_value=opener):
            with self.assertRaises(bot.DeliveryError) as failure:
                bot.send_envelope(self.payload, self.connector["token"])
        self.assertEqual(failure.exception.http_status, 302)
        self.assertEqual(seen, [bot.ENDPOINT])


@unittest.skipUnless(os.name == "posix", "Smartplan online server is POSIX-only; portable client tests run separately")
class MailBotHttpAcceptance(ClientFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.office = Office(Path(self.temp.name) / "office.db")
        self.addCleanup(self.office.db.close)
        # SQLite's local prototype has no online MFA tables. Use the same
        # test-only tables as WorkspaceApiTests, without modifying local Office.
        self.office.db.executescript("""
            CREATE TABLE mfa(user_id TEXT PRIMARY KEY REFERENCES users(id),secret TEXT NOT NULL,
              last_step INTEGER NOT NULL DEFAULT -1,recovery TEXT NOT NULL);
            CREATE TABLE auth_challenges(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),
              credential TEXT NOT NULL,secret TEXT NOT NULL,expiry REAL NOT NULL,
              failures INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE login_limits(key TEXT PRIMARY KEY,failures INTEGER NOT NULL,
              reset_at REAL NOT NULL);
        """)
        self.office.add_user("owner@example.test", "Synthetic-password-123", "owner")
        self.app = create_app(office=self.office, key=Fernet.generate_key(),
                              host=urlsplit(bot.ENDPOINT).hostname)
        self.client = self.app.test_client()
        self.base = "https://" + urlsplit(bot.ENDPOINT).hostname
        pending = self.call("/login", {"email": "owner@example.test",
                                       "password": "Synthetic-password-123"}).json
        self.assertTrue(pending["mfa_required"])
        self.token = self.call("/login/verify", {
            "challenge": pending["challenge"],
            "code": totp(pending["enrollment"]["secret"], int(time.time() // 30)),
        }).json["token"]
        self.connector = self.call("/inbound/gmail/tokens", {
            "name": "Synthetic mail bot", "source_account": "office@example.test",
        }, self.token).json
        os.environ["SMARTPLAN_INTAKE_TOKEN"] = self.connector["token"]
        self.lose_ack = False
        self._start_transport()

    def call(self, path, data=None, token=None, method="POST"):
        headers = {"Authorization": "Bearer " + token} if token else {}
        return self.client.open("/api/v1" + path, method=method, json=data,
                                base_url=self.base, headers=headers)

    def open(self, request, timeout):
        self._check_request(request, timeout)
        response = self.client.post(urlsplit(request.full_url).path, data=request.data,
                                    headers=dict(request.header_items()), base_url=self.base)
        if self.lose_ack:
            self.lose_ack = False
            raise urllib.error.URLError("Synthetic lost response; confidential provider details")
        if response.status_code >= 400:
            raise urllib.error.HTTPError(request.full_url, response.status_code,
                                         "Sensitive provider detail", {}, io.BytesIO(response.data))
        return Reply(response.status_code, response.data, response.content_type)

    def test_real_mfa_issued_key_imports_once_and_customer_suggestion_stays_in_office(self):
        with patch.dict(os.environ, {}, clear=True):
            code, output, error = self.run_cli("--check")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(json.loads(output), {"status": "validated", "sent": False})
        self.assertEqual(self.calls, [])
        self.assertEqual(self.call("/inquiries", token=self.token, method="GET").json, [])
        customer = self.call("/customers", {"name": "Synthetischer Bestandskunde",
                                           "email": self.payload["sender_email"]}, self.token).json
        first = bot.send_envelope(self.payload, self.connector["token"])
        second = bot.send_envelope(self.payload, self.connector["token"])
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(set(first), {"id", "status", "ingested_at"})
        self.assertEqual(first["status"], "received")
        inbox = self.call("/inquiries", token=self.token, method="GET").json
        self.assertEqual(len(inbox), 1)
        entry = self.call("/inquiries/" + first["id"], token=self.token, method="GET").json
        self.assertEqual(entry["message"], self.payload["message"])
        self.assertIn("Aufmaß", entry["message"])
        self.assertEqual([c["id"] for c in entry["candidate_customers"]], [customer["id"]])
        self.assertEqual(len(self.call("/customers", token=self.token, method="GET").json), 1)
        self.assertEqual(self.call("/projects", token=self.token, method="GET").json, [])
        # A bot delivery credential is neither an application session nor a
        # customer/project reader. Source text cannot extend those privileges.
        for path in ("/inquiries", "/customers", "/projects", "/users"):
            self.assertEqual(self.call(path, token=self.connector["token"], method="GET").status_code, 401)

    def test_lost_ack_is_unconfirmed_then_same_payload_retries_without_duplicate(self):
        original = self.input.read_bytes()
        self.lose_ack = True
        code, output, error = self.run_cli("--send")
        self.assertEqual(code, 3)
        self.assertEqual(output, "")
        self.assertEqual(json.loads(error), {"status": "unconfirmed", "error": "NETWORK_UNCONFIRMED"})
        self.assertEqual(len(self.call("/inquiries", token=self.token, method="GET").json), 1)
        code, output, error = self.run_cli("--send")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(json.loads(output)["status"], "received")
        self.assertEqual(self.input.read_bytes(), original)
        self.assertEqual(len(self.call("/inquiries", token=self.token, method="GET").json), 1)

    def test_gateway_substitution_succeeds_but_a_six_digit_value_alone_is_rejected(self):
        # This proves only compatibility with a documented, actually configured
        # gateway. It does not assert that the user's unidentified bot has one.
        handle = "opaque"
        original_open = self.open

        def bound_gateway(request, timeout):
            self.assertEqual(request.get_header("Authorization"), "Bearer " + handle)
            request.remove_header("Authorization")
            request.add_header("Authorization", "Bearer " + self.connector["token"])
            return original_open(request, timeout)

        with patch.dict(os.environ, {"SMARTPLAN_INTAKE_TOKEN": handle}):
            with patch.object(self, "open", side_effect=bound_gateway):
                code, output, error = self.run_cli("--send")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(json.loads(output)["status"], "received")
        self.assertEqual(len(self.call("/inquiries", token=self.token, method="GET").json), 1)
        for rejected in ("123456", handle):
            with patch.dict(os.environ, {"SMARTPLAN_INTAKE_TOKEN": rejected}):
                code, output, error = self.run_cli("--send")
            self.assertEqual(code, 3)
            self.assertEqual(output, "")
            self.assertEqual(json.loads(error)["http_status"], 401)
            self.assertNotIn(rejected, error)
        self.assertEqual(len(self.call("/inquiries", token=self.token, method="GET").json), 1)

    def test_changed_original_conflicts_and_wrong_mailbox_or_revoked_key_does_not_write(self):
        bot.send_envelope(self.payload, self.connector["token"])
        for data, status in (({**self.payload, "message": "Changed immutable original"}, 409),
                             ({**self.payload, "source_account": "other@example.test"}, 403)):
            with self.assertRaises(bot.DeliveryError) as failure:
                bot.send_envelope(data, self.connector["token"])
            self.assertEqual(failure.exception.http_status, status)
        self.call("/inbound/gmail/tokens/" + self.connector["id"] + "/revoke", {}, self.token)
        with self.assertRaises(bot.DeliveryError) as failure:
            bot.send_envelope({**self.payload, "source_id": "different-id"}, self.connector["token"])
        self.assertEqual(failure.exception.http_status, 401)
        self.assertEqual(len(self.call("/inquiries", token=self.token, method="GET").json), 1)


class MailBotArchive(unittest.TestCase):
    def test_only_reviewed_files_and_matching_hashes_are_packaged(self):
        with tempfile.TemporaryDirectory(prefix="smartplan-bot-package-") as temporary:
            folder = Path(temporary) / "source"
            folder.mkdir()
            for name in package.FILES:
                target = folder / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(DIRECTORY / name, target)
            secret = "SPIN_" + "Z" * 43
            (folder / "credentials.env").write_text(secret)
            (folder / "office.db").write_bytes(b"UNRELATED_PRIVATE_DATABASE")
            output = Path(temporary) / "kit.zip"
            with patch.object(package, "DIRECTORY", folder):
                manifest = package.build(output)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(set(archive.namelist()), {
                    "Smartplan-Mailbot/README.md", "Smartplan-Mailbot/BOT_AUFTRAG.md",
                    "Smartplan-Mailbot/openapi.json", "Smartplan-Mailbot/send_inquiry.py",
                    "Smartplan-Mailbot/examples/inquiry.json", "Smartplan-Mailbot/MANIFEST.json",
                })
                self.assertFalse(manifest["external_bot_connected"])
                self.assertEqual(manifest["minimum_schema_version"], 4)
                for name, expected_hash in manifest["files_sha256"].items():
                    raw = archive.read(package.PREFIX + name)
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), expected_hash)
                    self.assertNotIn(secret.encode(), raw)
                    self.assertNotIn(b"UNRELATED_PRIVATE_DATABASE", raw)

    def test_existing_archive_is_preserved(self):
        with tempfile.TemporaryDirectory(prefix="smartplan-bot-package-") as temporary:
            output = Path(temporary) / "already-exists.zip"
            output.write_bytes(b"preserve existing delivery bundle")
            with self.assertRaises(FileExistsError):
                package.build(output)
            self.assertEqual(output.read_bytes(), b"preserve existing delivery bundle")


if __name__ == "__main__":
    unittest.main()
