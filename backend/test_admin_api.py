"""Real HTTP checks for administration and the complete report workflow."""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from core import Office
from onedrive import OneDrive
from server import make_handler


class AdminApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.office = Office(Path(self.temp.name) / "office.sqlite3")
        self.owner_id = self.office.add_user("owner@example.test", "Owner-password-123", "owner")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.office, OneDrive(self.office)))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.owner = self.login("owner@example.test", "Owner-password-123")

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.office.db.close()
        self.temp.cleanup()

    def request(self, path, token=None, body=None, method=None, status=200, pdf=False):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(self.base + path, headers=headers,
                                     data=None if body is None else json.dumps(body).encode(), method=method)
        try:
            response = urllib.request.urlopen(req)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            self.assertEqual(response.status, status)
            data = response.read()
            if pdf:
                self.assertEqual(response.headers["Content-Type"], "application/pdf")
                self.assertIn("filename=", response.headers["Content-Disposition"])
                self.assertTrue(data.startswith(b"%PDF"))
                return data
            return json.loads(data)

    def login(self, email, password):
        return self.request("/api/login", body={"email": email, "password": password})["token"]

    def create_user(self, email="tech@example.test", role="technician"):
        return self.request("/api/users", self.owner,
                            {"email": email, "password": "Technician-password-123", "role": role}, status=201)["id"]

    def project(self):
        return self.request("/api/projects", self.owner,
                            {"name": "Baustelle", "customer": "Musterkunde"}, status=201)["id"]

    def test_owner_can_create_list_change_and_deactivate_users(self):
        uid = self.create_user()
        token = self.login("tech@example.test", "Technician-password-123")
        users = self.request("/api/users", self.owner)
        self.assertEqual(len(users), 2)
        self.assertTrue(all(set(u) == {"id", "email", "role", "active"} for u in users))
        self.request("/api/users", token, status=403)
        self.request("/api/users/" + uid, token, {"role": "owner"}, status=403)
        self.request("/api/users/" + uid, self.owner, {"role": "manager"})
        self.request("/api/me", token, status=401)
        token = self.login("tech@example.test", "Technician-password-123")
        self.assertEqual(self.request("/api/me", token)["role"], "manager")
        self.request("/api/users/" + uid, self.owner, {"active": False})
        self.request("/api/me", token, status=401)
        self.request("/api/login", body={"email": "tech@example.test", "password": "Technician-password-123"}, status=401)
        self.request("/api/users/" + uid, self.owner, {"active": True})
        self.request("/api/me", token, status=401)  # Reactivation never resurrects an old session.
        self.login("tech@example.test", "Technician-password-123")

    def test_password_reset_invalidates_sessions_and_old_password(self):
        uid = self.create_user()
        token = self.login("tech@example.test", "Technician-password-123")
        self.request("/api/users/" + uid, self.owner, {"password": "New-password-123"})
        self.request("/api/me", token, status=401)
        self.request("/api/login", body={"email": "tech@example.test", "password": "Technician-password-123"}, status=401)
        self.login("tech@example.test", "New-password-123")

    def test_invalid_admin_input_and_self_lockout_are_rejected(self):
        for changes in ({"role": "unknown"}, {"active": "false"}, {"password": "short"}, {}, {"email": "other@example.test"}):
            self.request("/api/users/" + self.owner_id, self.owner, changes, status=400)
        for changes in ({"active": False}, {"role": "technician"}):
            self.request("/api/users/" + self.owner_id, self.owner, changes, status=409)
        self.request("/api/users/" + "0" * 32, self.owner, {"active": False}, status=404)
        self.request("/api/users", self.owner, {"email": "invalid", "password": "Valid-password-123"}, status=400)
        self.create_user()
        self.request("/api/users", self.owner,
                     {"email": "TECH@example.test", "password": "Valid-password-123"}, status=409)
        self.assertEqual(self.request("/api/me", self.owner)["role"], "owner")

    def test_assignment_removal_revokes_report_and_pdf_access(self):
        uid = self.create_user()
        token = self.login("tech@example.test", "Technician-password-123")
        pid = self.project()
        assignment = {"project_id": pid, "user_id": uid}
        self.request("/api/assignments", self.owner, assignment)
        self.request("/api/assignments", self.owner, assignment)  # Repeatable, no duplicate rows.
        self.assertEqual(len(self.request(f"/api/projects/{pid}/assignments", self.owner)), 1)
        self.request(f"/api/projects/{pid}/assignments", token, status=403)
        report = self.request(f"/api/projects/{pid}/reports", token,
                              {"kind": "Servicebericht", "description": "Leuchten geprüft"}, status=201)
        self.request("/api/assignments", token, assignment, status=403)
        self.request("/api/assignments", self.owner, dict(assignment, remove="false"), status=400)
        self.request("/api/assignments", self.owner, dict(assignment, remove=True))
        self.request("/api/assignments", self.owner, dict(assignment, remove=True))
        self.assertEqual(self.request("/api/projects", token), [])
        self.request(f"/api/reports/{report['id']}", token, status=404)
        self.request(f"/api/reports/{report['id']}/pdf", token, status=404)
        self.assertEqual(self.request(f"/api/projects/{pid}/assignments", self.owner), [])

    def test_report_draft_signature_pdf_and_accountant_read_access(self):
        pid = self.project()
        report = self.request(f"/api/projects/{pid}/reports", self.owner,
                              {"kind": "Lieferschein", "description": "10 Schalter geliefert"}, status=201)
        rid = report["id"]
        self.assertEqual(self.request(f"/api/projects/{pid}/reports", self.owner)[0]["id"], rid)
        self.request(f"/api/reports/{rid}/pdf", self.owner, pdf=True)
        self.request(f"/api/reports/{rid}/sign", self.owner,
                     {"content_hash": report["content_hash"], "signer": "Kunde Muster",
                      "strokes": [[[0.1, 0.2], [0.7, 0.8]]]}, status=200)
        signed_pdf = self.request(f"/api/reports/{rid}/pdf", self.owner, pdf=True)
        self.assertEqual(signed_pdf, self.request(f"/api/reports/{rid}/pdf", self.owner, pdf=True))
        aid = self.create_user("accounts@example.test", "accountant")
        self.request("/api/assignments", self.owner, {"user_id": aid, "project_id": pid})
        accountant = self.login("accounts@example.test", "Technician-password-123")
        self.assertEqual(self.request(f"/api/reports/{rid}", accountant)["status"], "signed")
        self.assertEqual(signed_pdf, self.request(f"/api/reports/{rid}/pdf", accountant, pdf=True))
        self.request(f"/api/projects/{pid}/reports", accountant,
                     {"kind": "Lieferschein", "description": "Neue Lieferung"}, status=403)
        self.request(f"/api/reports/{rid}/sign", accountant, {}, status=403)

    def test_wrong_http_methods_never_mutate_data(self):
        uid = self.create_user()
        pid = self.project()
        report = self.request(f"/api/projects/{pid}/reports", self.owner,
                              {"kind": "Servicebericht", "description": "Prüfung"}, status=201)
        for path, method in [("/api/projects", "DELETE"), ("/api/users", "PUT"),
                             (f"/api/users/{uid}", "GET"), ("/api/me", "POST"),
                             (f"/api/reports/{report['id']}/sign", "GET"),
                             (f"/api/reports/{report['id']}", "POST")]:
            self.request(path, self.owner, method=method, status=405)
        self.assertEqual(len(self.request("/api/projects", self.owner)), 1)
        self.assertEqual(self.request(f"/api/reports/{report['id']}", self.owner)["status"], "draft")


if __name__ == "__main__":
    unittest.main()
