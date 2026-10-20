import json
from pathlib import Path
import socket
import tempfile
import unittest
import urllib.request

from core import Office, Problem
from windows_office import (InstallationLock, SupportError, create_backup, file_hash,
                            launch, load_config, save_config, verified_restore)


class WindowsOfficeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "Büro & Testdaten"
        data = self.root / "data"
        data.mkdir(parents=True)
        self.config = {"data_dir": str(data)}
        self.office = Office(data / "office.sqlite3")
        self.addCleanup(self.office.db.close)
        self.office.add_user("owner@example.test", "Owner-password-123", "owner")
        self.token = self.office.login("owner@example.test", "Owner-password-123")
        self.owner = self.office.user(self.token)
        save_config(self.root, self.config)

    def unused_port(self):
        with socket.socket() as connection:
            connection.bind(("127.0.0.1", 0))
            return connection.getsockname()[1]

    def test_verified_restore_preserves_current_data_signed_pdf_and_revokes_sessions(self):
        project = self.office.add_project(self.owner, "Prüfprojekt", "Kunde")
        report = self.office.draft(self.owner, project, "Servicebericht", "Geprüft")
        self.office.sign(self.owner, report["id"], report["content_hash"], "Testkunde", [[[0.1, 0.2], [0.8, 0.7]]])
        pdf = self.office.pdf(self.owner, report["id"])
        saved = create_backup(self.config["data_dir"], self.root / "USB", "manuell")
        self.office.add_project(self.owner, "Nach der Sicherung", "Kunde")
        original_bytes = (Path(self.config["data_dir"]) / "office.sqlite3").read_bytes()
        target, previous = verified_restore(self.root, self.config, saved)
        self.assertEqual((Path(self.config["data_dir"]) / "office.sqlite3").read_bytes(), original_bytes)
        self.assertEqual(load_config(self.root)["data_dir"], str(target))
        self.assertEqual(load_config(self.root)["previous_data_dir"], self.config["data_dir"])
        self.assertTrue(previous.is_file())
        recovered = Office(target / "office.sqlite3")
        self.addCleanup(recovered.db.close)
        with self.assertRaises(Problem):
            recovered.user(self.token)
        owner = recovered.user(recovered.login("owner@example.test", "Owner-password-123"))
        self.assertEqual(len(recovered.projects(owner)), 1)
        self.assertEqual(recovered.pdf(owner, report["id"]), pdf)
        before_switch = Office(previous)
        self.addCleanup(before_switch.db.close)
        self.assertEqual(len(before_switch.projects(before_switch.user(self.token))), 2)

    def test_bad_or_missing_checksum_never_switches_working_data(self):
        saved = create_backup(self.config["data_dir"], self.root / "USB")
        checksum = saved.with_suffix(".sqlite3.sha256")
        checksum.unlink()
        with self.assertRaisesRegex(SupportError, "fehlt"):
            verified_restore(self.root, self.config, saved)
        checksum.write_text("0" * 64, encoding="ascii")
        with self.assertRaisesRegex(SupportError, "Prüfsumme"):
            verified_restore(self.root, self.config, saved)
        self.assertEqual(load_config(self.root), self.config)
        self.assertFalse((self.root / "restored").exists())

    def test_backup_repeated_and_missing_database_does_not_create_empty_data(self):
        first = create_backup(self.config["data_dir"], self.root / "USB")
        second = create_backup(self.config["data_dir"], self.root / "USB")
        self.assertNotEqual(first, second)
        self.assertEqual(file_hash(first), first.with_suffix(".sqlite3.sha256").read_text().strip())
        self.assertEqual(file_hash(second), second.with_suffix(".sqlite3.sha256").read_text().strip())
        with self.assertRaises(SupportError):
            create_backup(self.root / "missing", self.root / "USB")
        self.assertFalse((self.root / "missing").exists())

    def test_lock_blocks_second_launcher_and_releases_after_error(self):
        with self.assertRaisesRegex(RuntimeError, "simulated"):
            with InstallationLock(self.root):
                with self.assertRaises(SupportError):
                    with InstallationLock(self.root):
                        self.fail("second launcher acquired lock")
                raise RuntimeError("simulated")
        with InstallationLock(self.root):
            pass

    def test_existing_listener_is_not_stopped_or_reused(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            with self.assertRaisesRegex(SupportError, "bereits ein Server"):
                launch(self.root, self.config, Path(__file__), port=listener.getsockname()[1])
            with socket.create_connection(listener.getsockname(), timeout=1):
                pass
            self.assertFalse((self.root / "backups").exists())

    def test_real_server_lifecycle_saves_last_app_changes_and_stops_on_failure(self):
        port = self.unused_port()
        local = urllib.request.build_opener(urllib.request.ProxyHandler({}))

        def app(port):
            def request(route, body=None, token=None):
                headers = {"Content-Type": "application/json"}
                if token:
                    headers["Authorization"] = "Bearer " + token
                req = urllib.request.Request("http://127.0.0.1:" + str(port) + route,
                                             data=json.dumps(body).encode() if body is not None else None,
                                             headers=headers)
                with local.open(req, timeout=3) as response:
                    return json.load(response)
            token = request("/api/login", {"email": "owner@example.test", "password": "Owner-password-123"})["token"]
            request("/api/projects", {"name": "Aus der App", "customer": "Kunde"}, token)
            raise RuntimeError("simulated app failure")

        with InstallationLock(self.root):
            with self.assertRaisesRegex(RuntimeError, "simulated app failure"):
                launch(self.root, self.config, Path(__file__), port=port, run_app=app)
        snapshots = sorted((self.root / "backups").glob("*.sqlite3"))
        self.assertEqual(len(snapshots), 2)
        before = Office(next(path for path in snapshots if "vor-start" in path.name))
        self.addCleanup(before.db.close)
        after = Office(next(path for path in snapshots if "nach-ende" in path.name))
        self.addCleanup(after.db.close)
        self.assertEqual(len(before.projects(before.user(self.token))), 0)
        self.assertEqual(len(after.projects(after.user(self.token))), 1)
        with socket.socket() as connection:
            connection.settimeout(1)
            self.assertNotEqual(connection.connect_ex(("127.0.0.1", port)), 0)


if __name__ == "__main__":
    unittest.main()
