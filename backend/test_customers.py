"""HTTP customer permissions and migration from the actual pre-CRM schema."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

import test_admin_api as admin_api
from backup import backup
from core import Office, Problem
from restore import restore


LEGACY_SCHEMA = """
CREATE TABLE users(id TEXT PRIMARY KEY,email TEXT UNIQUE,salt TEXT,password TEXT,role TEXT,active INTEGER DEFAULT 1);
CREATE TABLE sessions(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),expiry REAL);
CREATE TABLE projects(id TEXT PRIMARY KEY,name TEXT,customer TEXT);
CREATE TABLE assignments(user_id TEXT REFERENCES users(id),project_id TEXT REFERENCES projects(id),PRIMARY KEY(user_id,project_id));
CREATE TABLE reports(id TEXT PRIMARY KEY,project_id TEXT REFERENCES projects(id),payload TEXT,pdf BLOB,pdf_hash TEXT,onedrive_id TEXT);
CREATE TABLE audit(id INTEGER PRIMARY KEY,user_id TEXT,action TEXT,object_id TEXT,at TEXT);
CREATE TABLE secrets(name TEXT PRIMARY KEY,value TEXT);
"""


class CustomerApiTests(unittest.TestCase):
    setUp = admin_api.AdminApiTests.setUp
    tearDown = admin_api.AdminApiTests.tearDown
    request = admin_api.AdminApiTests.request
    login = admin_api.AdminApiTests.login
    create_user = admin_api.AdminApiTests.create_user
    project = admin_api.AdminApiTests.project

    def customer(self, **changes):
        return self.request("/api/customers", self.owner,
                            {"name": "Müller & Söhne", **changes}, status=201)

    def test_customer_creation_edit_project_link_and_original_signed_pdf(self):
        customer = self.customer(contact=" Anna Müller ", email="anna@example.test", phone="+49 123 456",
                                 address="Parkweg 7\n12345 Musterstadt", notes="Termin vorher abstimmen")
        self.assertEqual(customer["contact"], "Anna Müller")
        self.assertNotIn("dedupe_key", customer)
        self.assertEqual(self.request("/api/customers", self.owner)[0]["project_count"], 0)
        pid = self.request("/api/projects", self.owner,
                           {"name": "Neubau", "customer_id": customer["id"]}, status=201)["id"]
        report = self.request(f"/api/projects/{pid}/reports", self.owner,
                              {"kind": "Servicebericht", "description": "Geprüft"}, status=201)
        rid = report["id"]
        self.request(f"/api/reports/{rid}/sign", self.owner,
                     {"content_hash": report["content_hash"], "signer": "Testkunde", "strokes": [[[0.1, 0.2], [0.7, 0.8]]]})
        pdf = self.request(f"/api/reports/{rid}/pdf", self.owner, pdf=True)
        self.request("/api/customers/" + customer["id"], self.owner, {"name": "Müller Gebäudetechnik"})
        project = self.request("/api/projects", self.owner)[0]
        self.assertEqual(project["customer_id"], customer["id"])
        self.assertEqual(project["customer"], "Müller Gebäudetechnik")
        self.assertEqual(self.request(f"/api/reports/{rid}", self.owner)["content"], report["content"])
        self.assertEqual(pdf, self.request(f"/api/reports/{rid}/pdf", self.owner, pdf=True))
        fresh = self.request(f"/api/projects/{pid}/reports", self.owner,
                             {"kind": "Servicebericht", "description": "Weiterer Termin"}, status=201)
        self.assertEqual(fresh["content"]["customer"], "Müller Gebäudetechnik")
        self.assertEqual(self.request("/api/customers", self.owner)[0]["project_count"], 1)

    def test_archiving_reactivation_and_existing_project_reassignment(self):
        first = self.customer()
        second = self.customer(name="Anderer Kunde")
        pid = self.project()
        linked = self.request(f"/api/projects/{pid}/customer", self.owner, {"customer_id": first["id"]})
        self.assertEqual(linked["customer"], first["name"])
        self.request("/api/customers/" + first["id"], self.owner, {"active": False})
        self.assertEqual(len(self.request("/api/projects", self.owner)), 1)
        self.request("/api/projects", self.owner, {"name": "Nicht anlegen", "customer_id": first["id"]}, status=409)
        self.request(f"/api/projects/{pid}/customer", self.owner, {"customer_id": first["id"]}, status=409)
        self.request(f"/api/projects/{pid}/customer", self.owner, {"customer_id": second["id"]})
        self.request("/api/customers/" + first["id"], self.owner, {"active": True})
        self.request(f"/api/projects/{pid}/customer", self.owner, {"customer_id": first["id"]})
        self.assertEqual(self.request("/api/projects", self.owner)[0]["customer_id"], first["id"])

    def test_contacts_and_notes_are_owner_only_even_for_assigned_roles(self):
        customer = self.customer(notes="Interne Kundennotiz")
        pid = self.request("/api/projects", self.owner, {"name": "Projekt", "customer_id": customer["id"]}, status=201)["id"]
        self.request("/api/customers", status=401)
        for role in ("manager", "technician", "accountant"):
            uid = self.create_user(role + "@example.test", role)
            token = self.login(role + "@example.test", "Technician-password-123")
            self.request("/api/assignments", self.owner, {"project_id": pid, "user_id": uid})
            self.assertEqual(self.request("/api/projects", token)[0]["customer"], customer["name"])
            self.request("/api/customers", token, status=403)
            self.request("/api/customers/" + customer["id"], token, status=403)
            self.request("/api/customers", token, {"name": "Unerlaubt"}, status=403)
            self.request("/api/customers/" + customer["id"], token, {"notes": "Unerlaubt"}, status=403)
            self.request(f"/api/projects/{pid}/customer", token, {"customer_id": customer["id"]}, status=403)

    def test_validation_deduplication_and_wrong_methods_do_not_change_data(self):
        customer = self.customer(address="Parkweg 7\nMusterstadt")
        self.request("/api/customers", self.owner, {"name": "  MÜLLER & SÖHNE ", "address": "parkweg 7  musterstadt"}, status=409)
        other = self.customer(address="Andere Straße 2")  # Same name at another address is legitimate.
        self.request("/api/customers/" + other["id"], self.owner, {"address": "Parkweg 7\nMusterstadt"}, status=409)
        for invalid in ({}, {"name": " "}, {"email": "invalid"}, {"active": "false"},
                        {"notes": None}, {"phone": 123}, {"address": "x" * 2001}, {"unexpected": "x"}):
            self.request("/api/customers/" + customer["id"], self.owner, invalid, status=400)
        self.request("/api/customers", self.owner, method="DELETE", status=405)
        self.request("/api/customers/" + customer["id"], self.owner, method="DELETE", status=405)
        self.request("/api/customers/" + "0" * 32, self.owner, status=404)
        self.assertEqual(len(self.request("/api/customers", self.owner)), 2)
        self.assertEqual(self.request("/api/customers/" + other["id"], self.owner)["address"], "Andere Straße 2")

    def test_customer_database_backup_restore_keeps_links_and_revokes_sessions(self):
        customer = self.customer(notes="Gesicherte Notiz")
        pid = self.request("/api/projects", self.owner, {"name": "Projekt", "customer_id": customer["id"]}, status=201)["id"]
        report = self.request(f"/api/projects/{pid}/reports", self.owner,
                              {"kind": "Servicebericht", "description": "Gesicherter Bericht"}, status=201)
        self.request(f"/api/reports/{report['id']}/sign", self.owner,
                     {"content_hash": report["content_hash"], "signer": "Testkunde", "strokes": [[[0.1, 0.2], [0.7, 0.8]]]})
        expected_pdf = self.request(f"/api/reports/{report['id']}/pdf", self.owner, pdf=True)
        root = Path(self.temp.name)
        saved = backup(root / "office.sqlite3", root / "backup.sqlite3")
        restored = Office(restore(saved, root / "restored.sqlite3"))
        try:
            with self.assertRaises(Problem):
                restored.user(self.owner)
            actor = restored.user(restored.login("owner@example.test", "Owner-password-123"))
            self.assertEqual(restored.customer(actor, customer["id"])["notes"], "Gesicherte Notiz")
            self.assertEqual(restored.projects(actor)[0]["customer_id"], customer["id"])
            self.assertEqual(restored.pdf(actor, report["id"]), expected_pdf)
        finally:
            # tearDown removes this directory before unittest runs addCleanup.
            # Windows requires the database handle closed before that removal.
            restored.db.close()


class CustomerMigrationTests(unittest.TestCase):
    def test_legacy_migration_is_repeatable_and_preserves_ids_payloads_and_pdf(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = Office(root / "source.sqlite3")
            try:
                source.add_user("owner@example.test", "Owner-password-123", "owner")
                token = source.login("owner@example.test", "Owner-password-123")
                actor = source.user(token)
                pid = source.add_project(actor, "Altes Projekt", "Musterkunde")
                source.add_project(actor, "Zweites Projekt", "MUSTERKUNDE")
                report = source.draft(actor, pid, "Servicebericht", "Vor der Migration")
                source.sign(actor, report["id"], report["content_hash"], "Testkunde", [[[0.1, 0.2], [0.7, 0.8]]])
                expected = source.pdf(actor, report["id"])
                legacy_path = root / "legacy.sqlite3"
                with closing(sqlite3.connect(legacy_path)) as legacy, legacy:
                    legacy.executescript(LEGACY_SCHEMA)
                    for table in ("users", "sessions", "projects", "assignments", "reports", "audit", "secrets"):
                        columns = [r[1] for r in legacy.execute("PRAGMA table_info(" + table + ")")]
                        rows = source.db.execute("SELECT " + ",".join(columns) + " FROM " + table).fetchall()
                        legacy.executemany("INSERT INTO " + table + " VALUES(" + ",".join("?" for _ in columns) + ")", rows)
                for _ in range(2):
                    migrated = Office(legacy_path)
                    try:
                        owner = migrated.user(token)
                        self.assertEqual(len(migrated.customers(owner)), 1)
                        self.assertEqual(migrated.customers(owner)[0]["project_count"], 2)
                        self.assertEqual(migrated.project(owner, pid)["id"], pid)
                        self.assertEqual(migrated.report(owner, report["id"])["content"], report["content"])
                        self.assertEqual(migrated.pdf(owner, report["id"]), expected)
                        self.assertEqual(migrated.db.execute("PRAGMA user_version").fetchone()[0], 1)
                    finally:
                        migrated.db.close()
            finally:
                source.db.close()

    def test_invalid_legacy_data_rolls_back_schema_change(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.sqlite3"
            with closing(sqlite3.connect(path)) as legacy, legacy:
                legacy.executescript(LEGACY_SCHEMA)
                legacy.execute("INSERT INTO projects VALUES('old','Projekt','')")
            with self.assertRaises(Problem):
                Office(path)
            with closing(sqlite3.connect(path)) as legacy:
                self.assertEqual(legacy.execute("PRAGMA user_version").fetchone()[0], 0)
                self.assertNotIn("customer_id", [r[1] for r in legacy.execute("PRAGMA table_info(projects)")])
                self.assertIsNone(legacy.execute("SELECT name FROM sqlite_master WHERE name='customers'").fetchone())
                self.assertEqual(legacy.execute("SELECT * FROM projects").fetchone(), ("old", "Projekt", ""))


if __name__ == "__main__":
    unittest.main()
