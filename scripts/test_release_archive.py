"""Exercise the real release exports with Git and root-equivalent tar modes.

The operator-flow container deliberately stubs Git and cannot catch archive
header permissions. GNU tar --same-permissions reproduces root extraction even
when this host-side test runs without root; no system paths or services are used.
"""
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPORTS = {
    "update-online.sh": ("backend", "web"),
    "install-online.sh": ("backend",),
}


class ReleaseArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="smartplan-release-archive-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repository = self.root / "repository"
        self.environment = {key: value for key, value in os.environ.items()
                            if not key.startswith("GIT_")}
        self.environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        self.run_command("git", "-c", "init.templateDir=", "init", "--quiet", str(self.repository))
        self.git("config", "user.name", "Synthetic Release Fixture")
        self.git("config", "user.email", "release-fixture@example.test")
        for name, data in {
            "backend/online/release.py": b"# immutable synthetic release A\n",
            "backend/business_schema.py": b"# immutable synthetic schema A\n",
            "backend/executable": b"#!/bin/sh\nexit 0\n",
            "web/office/index.html": b"<title>Synthetic release A</title>\n",
            "unrelated-private-fixture": b"must never enter a release\n",
        }.items():
            path = self.repository / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (self.repository / "backend/executable").chmod(0o755)
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "Synthetic release A")
        self.commit = self.git("rev-parse", "HEAD").stdout.strip()

    def run_command(self, *arguments, **kwargs):
        return subprocess.run(arguments, env=self.environment, check=True,
                              capture_output=True, text=True, timeout=20, **kwargs)

    def git(self, *arguments):
        return self.run_command("git", "-C", str(self.repository), *arguments)

    def export(self, script_name, destination):
        script = ROOT / "deploy/hetzner/online" / script_name
        lines = [line.strip() for line in script.read_text().splitlines()
                 if line.lstrip().startswith("git ") and " archive " in line]
        self.assertEqual(len(lines), 1, "Exactly one actual production export is required")
        invocation, extraction = lines[0].split(" | ")
        self.assertTrue(extraction.startswith("tar -x -C "), extraction)
        # Execute the production Git command unchanged. Only the tar destination
        # and root-equivalent permission handling are specific to this fixture.
        environment = dict(self.environment, smartplan_repo=str(self.repository),
                           smartplan_commit=self.commit, smartplan_output=str(destination))
        destination.mkdir()
        subprocess.run(["bash", "-c", "set -euo pipefail\numask 0077\n" + invocation +
                        ' | tar -x --same-permissions -C "$smartplan_output"'],
                       env=environment, check=True, capture_output=True, text=True, timeout=20)

    def assert_export(self, destination, exported_roots):
        expected = {}
        for root in exported_roots:
            for name in self.git("ls-tree", "-r", "--name-only", self.commit, root).stdout.splitlines():
                expected[name] = self.git("show", f"{self.commit}:{name}").stdout.encode()
        files = {path.relative_to(destination).as_posix(): path.read_bytes()
                 for path in destination.rglob("*") if path.is_file()}
        self.assertEqual(files, expected)
        for path in destination.rglob("*"):
            with self.subTest(path=path.relative_to(destination)):
                executable = path.name == "executable"
                expected_mode = 0o755 if path.is_dir() or executable else 0o644
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), expected_mode)
                self.assertEqual(path.stat().st_uid, os.getuid())

    def test_real_exports_override_permissive_git_archive_modes_without_changing_files(self):
        for mask in ("0000", "0002"):
            self.git("config", "tar.umask", mask)
            for script, roots in EXPORTS.items():
                with self.subTest(script=script, local_tar_umask=mask):
                    destination = self.root / (script + "-" + mask)
                    self.export(script, destination)
                    self.assert_export(destination, roots)

    def test_real_exports_stay_bound_to_the_captured_commit_when_head_moves(self):
        (self.repository / "backend/online/release.py").write_text("# different synthetic release B\n")
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "Synthetic release B")
        self.assertNotEqual(self.git("rev-parse", "HEAD").stdout.strip(), self.commit)
        self.git("config", "tar.umask", "0000")
        for script, roots in EXPORTS.items():
            with self.subTest(script=script):
                destination = self.root / (script + "-pinned")
                self.export(script, destination)
                self.assert_export(destination, roots)


if __name__ == "__main__":
    unittest.main(verbosity=2)
