"""Exercise the real non-root launcher and online SQLite backup with fake data."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))
from core import Office
from restore import restore


@unittest.skipUnless(sys.platform == "linux" and os.geteuid() != 0,
                     "Linux non-root launcher check; run with the CI/development account")
class PrivatePilotTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.state = Path(self.folder.name) / "state"
        self.state.mkdir(mode=0o700)
        self.environment = {**os.environ, "OFFICE_DATA_DIR": str(self.state)}
        self.process = None
        self.log = tempfile.TemporaryFile()
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            self.port = listener.getsockname()[1]
        self.environment["SMARTPLAN_PILOT_PORT"] = str(self.port)
        self.base = f"http://127.0.0.1:{self.port}"

    def tearDown(self):
        self.stop()
        self.log.close()
        self.folder.cleanup()

    def stop(self):
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
            self.process = None

    def start(self):
        self.process = subprocess.Popen(
            ["/bin/bash", str(REPO / "deploy/hetzner/run-pilot.sh")],
            env=self.environment, stdout=self.log, stderr=self.log,
        )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.log.seek(0)
                self.fail("Launcher exited: " + self.log.read().decode())
            try:
                return self.request("/health")
            except urllib.error.URLError:
                time.sleep(0.05)
        self.fail("Pilot did not become ready")

    def request(self, path, data=None, token=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        body = None if data is None else json.dumps(data).encode()
        with self.opener.open(urllib.request.Request(self.base + path, data=body, headers=headers), timeout=3) as response:
            payload = response.read()
            return payload if response.headers.get_content_type() == "application/pdf" else json.loads(payload)

    def launcher(self, action, environment=None):
        return subprocess.run(
            ["/bin/bash", str(REPO / "deploy/hetzner/run-pilot.sh"), action],
            env=self.environment if environment is None else environment,
            capture_output=True, text=True, timeout=10,
        )

    def test_loopback_authorization_signed_pdf_and_persistence_after_restart(self):
        office = Office(self.state / "office.sqlite3")
        try:
            office.add_user("pilot@example.test", "Fiktives-Passwort-42!", "owner")
        finally:
            office.db.close()
        health = self.start()
        self.assertEqual(health["launch_id"], "smartplan-private-pilot")
        self.assertEqual(health["status"], "ok")
        # Inspect the real listening sockets: a wildcard bind must fail this test.
        listeners = []
        for table in ("/proc/net/tcp", "/proc/net/tcp6"):
            for line in Path(table).read_text().splitlines()[1:]:
                fields = line.split()
                address, port = fields[1].split(":")
                if int(port, 16) == self.port and fields[3] == "0A":
                    listeners.append(address)
        self.assertEqual(listeners, ["0100007F"])
        with self.assertRaises(urllib.error.HTTPError) as denied:
            self.request("/api/projects")
        self.assertEqual(denied.exception.code, 401)
        login = {"email": "pilot@example.test", "password": "Fiktives-Passwort-42!"}
        token = self.request("/api/login", login)["token"]
        customer = self.request("/api/customers", {"name": "Fiktiver Testkunde"}, token)
        project = self.request("/api/projects", {"name": "Pilot-Test", "customer_id": customer["id"]}, token)
        report = self.request(f"/api/projects/{project['id']}/reports",
                              {"kind": "Servicebericht", "description": "Fiktiver Neustarttest"}, token)
        self.request(f"/api/reports/{report['id']}/sign", {
            "content_hash": report["content_hash"], "signer": "Testperson",
            "strokes": [[[0.1, 0.2], [0.8, 0.7]]],
        }, token)
        pdf_path = f"/api/reports/{report['id']}/pdf"
        pdf = self.request(pdf_path, token=token)
        self.assertTrue(pdf.startswith(b"%PDF"))

        for _ in range(2):
            result = self.launcher("backup")
            self.assertEqual(result.returncode, 0, result.stderr)
        copies = sorted((self.state / "backups").glob("*.sqlite3"))
        self.assertEqual(len(copies), 2)
        for copy in copies:
            self.assertEqual(copy.stat().st_mode & 0o777, 0o600)
            sidecar = Path(str(copy) + ".sha256")
            self.assertEqual(sidecar.read_text().split()[0], hashlib.sha256(copy.read_bytes()).hexdigest())
            with closing(sqlite3.connect(copy)) as db:
                self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(db.execute("SELECT pdf FROM reports WHERE id=?", (report["id"],)).fetchone()[0], pdf)
        restored = Path(self.folder.name) / "restored.sqlite3"
        restore(copies[-1], restored)
        with closing(sqlite3.connect(restored)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM sessions").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT pdf FROM reports WHERE id=?", (report["id"],)).fetchone()[0], pdf)

        self.stop()
        self.start()
        token = self.request("/api/login", login)["token"]
        self.assertEqual(self.request(pdf_path, token=token), pdf)
        self.assertEqual(self.request("/api/projects", token=token)[0]["customer_id"], customer["id"])

    def test_missing_data_directory_and_invalid_port_do_not_start_or_create_database(self):
        environment = dict(self.environment)
        del environment["OFFICE_DATA_DIR"]
        result = self.launcher("run", environment)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("OFFICE_DATA_DIR", result.stderr)
        environment = {**self.environment, "SMARTPLAN_PILOT_PORT": "0"}
        result = self.launcher("run", environment)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Ungültiger Pilot-Port", result.stderr)
        self.assertFalse((self.state / "office.sqlite3").exists())

    def test_backup_before_first_start_does_not_create_an_empty_database(self):
        result = self.launcher("backup")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.state / "office.sqlite3").exists())
        self.assertFalse((self.state / "backups").exists())


if __name__ == "__main__":
    unittest.main()
