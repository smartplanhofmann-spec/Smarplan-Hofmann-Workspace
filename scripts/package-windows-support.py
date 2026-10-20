"""Build a small, reproducible update for users with the existing Windows app."""
from pathlib import Path
import hashlib
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
BACKEND_FILES = ("backup.py", "restore.py", "core.py", "server.py", "onedrive.py",
                 "windows_office.py", "requirements.lock")
WINDOWS_FILES = ("Starten.cmd", "Sicherung_erstellen.cmd", "Sicherung_wiederherstellen.cmd",
                 "Run.cmd", "START_HIER.txt")


def build(destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, source in [("backend/" + name, ROOT / "backend" / name) for name in BACKEND_FILES] + [
            (name, ROOT / "windows" / name) for name in WINDOWS_FILES
        ]:
            contents = source.read_bytes()
            if name.endswith((".cmd", ".txt")):
                contents = contents.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            info = zipfile.ZipInfo("Smartplan_Windows_Start_und_Sicherung/" + name, (2026, 10, 20, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, contents)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(destination.suffix + ".sha256").write_text(digest + "  " + destination.name + "\n", encoding="ascii")
    print(destination.name, destination.stat().st_size, "bytes", digest)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else ROOT / "downloads" / "Smartplan_Windows_Start_und_Sicherung.zip")
