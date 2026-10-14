import tempfile
import unittest
from pathlib import Path

from backup import backup
from core import Office, Problem
from restore import restore


class BackupTests(unittest.TestCase):
    def test_live_backup_can_be_restored_with_signed_pdf_and_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            office = Office(root / "source.sqlite3")
            restored = None
            try:
                office.add_user("owner@example.test", "Owner-password-123", "owner")
                old_token = office.login("owner@example.test", "Owner-password-123")
                owner = office.user(old_token)
                project = office.add_project(owner, "Projekt", "Kunde")
                report = office.draft(owner, project, "Servicebericht", "Erledigt")
                office.sign(owner, report["id"], report["content_hash"], "Kunde", [[[0.1, 0.2], [0.8, 0.7]]])
                expected = office.pdf(owner, report["id"])
                target = backup(root / "source.sqlite3", root / "backup.sqlite3")
                restored = Office(restore(target, root / "restored.sqlite3"))
                with self.assertRaises(Problem) as error:
                    restored.user(old_token)
                self.assertEqual(error.exception.status, 401)
                restored_owner = restored.user(restored.login("owner@example.test", "Owner-password-123"))
                self.assertEqual(restored.projects(restored_owner)[0]["id"], project)
                self.assertEqual(restored.pdf(restored_owner, report["id"]), expected)
                self.assertEqual(restored.report(restored_owner, report["id"])["status"], "signed")
            finally:
                office.db.close()
                if restored:
                    restored.db.close()

    def test_existing_backup_and_missing_source_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.sqlite3"
            office = Office(source)
            office.db.close()
            target = root / "existing.sqlite3"
            target.write_bytes(b"user-file")
            with self.assertRaises(FileExistsError):
                backup(source, target)
            self.assertEqual(target.read_bytes(), b"user-file")
            with self.assertRaises(FileNotFoundError):
                backup(root / "missing.sqlite3", root / "new.sqlite3")
            self.assertFalse((root / "new.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
