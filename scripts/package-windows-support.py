"""Build reproducible Windows support sources for the development package."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import zipfile

ROOT = Path(__file__).resolve().parent.parent
BACKEND_FILES = ("backup.py", "restore.py", "core.py", "server.py", "onedrive.py",
                 "windows_office.py", "plans.py", "plan_access.py", "plan_deletions.py",
                 "project_workspace.py", "inquiries.py", "inbound_connectors.py", "inquiry_attachments.py",
                 "workspace_api.py", "external_integrations.py", "integration_bridge.py",
                 "business_api.py", "business_schema.py", "business_foundation.py",
                 "business_documents.py", "business_finance.py", "business_einvoice.py", "business_delivery.py",
                 "business_planning.py", "business_time.py", "business_operations.py",
                 "business_inventory.py", "business_maintenance.py", "business_adapters.py",
                 "requirements.lock")
WINDOWS_FILES = ("Starten.cmd", "Sicherung_erstellen.cmd", "Sicherung_wiederherstellen.cmd",
                 "Run.cmd", "START_HIER.txt")
OFFLINE_INSTALLER_FILES = ('Python_Umgebung_aktualisieren.cmd', 'Python_Umgebung_aktualisieren.py')
SOURCE_ONLY_NOTICE = '''Smartplan Windows - reines Quell-/Supportpaket

Dieses ZIP enthaelt KEINE Python-Abhaengigkeiten und keinen Offline-Updater.
Es ist kein vollstaendiges Windows-App-/Python-Offlinepaket.
Fuer ein Update der bestehenden privaten Python-3.12-Umgebung bitte das
vollstaendige Smartplan-Office-Windows-Paket desselben 0.12-Updates laden.
Darin muessen python-wheels, backend/requirements.lock und
Python_Umgebung_aktualisieren.cmd zusammen enthalten sein.
Die App und den lokalen Server schliessen, dann den Updater ausdruecklich starten.
Python wird dabei nicht neu installiert; Geschaeftsdaten bleiben ungeoeffnet.
Dieses Quellpaket allein ersetzt keine neue App und keine fehlenden Wheels.
'''


def build(destination, wheels_dir=None):
    files = [("backend/" + name, ROOT / "backend" / name) for name in BACKEND_FILES]
    files.extend((name, ROOT / 'windows' / name) for name in WINDOWS_FILES)
    manifest = None
    if wheels_dir is not None:
        spec = importlib.util.spec_from_file_location('smartplan_offline_installer', ROOT / 'windows' / OFFLINE_INSTALLER_FILES[1])
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        manifest = installer.wheel_manifest(wheels_dir, ROOT / 'backend/requirements.lock')
        files.extend((name, ROOT / 'windows' / name) for name in OFFLINE_INSTALLER_FILES)
        files.extend(('python-wheels/' + name, Path(wheels_dir) / name) for name in manifest['files_sha256'])
    contents = [(name, source.read_bytes()) for name, source in files]
    if manifest is None:
        contents.append(('QUELLPAKET_HINWEIS.txt', SOURCE_ONLY_NOTICE.encode('utf-8')))
    else:
        contents.append(('python-wheels/WHEELS_SHA256.json', (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode('utf-8')))
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in sorted(contents):
            if name.endswith((".cmd", ".txt")):
                value = value.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            info = zipfile.ZipInfo("Smartplan_Windows_Start_und_Sicherung/" + name, (2026, 10, 20, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, value)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(destination.suffix + ".sha256").write_text(digest + "  " + destination.name + "\n", encoding="ascii")
    print(destination.name, destination.stat().st_size, "bytes", digest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', nargs='?', type=Path, default=ROOT / 'downloads/Smartplan_Windows_Start_und_Sicherung.zip')
    parser.add_argument('--wheels-dir', type=Path, help='Vollstaendige Windows-x64/Python-3.12-Wheels aus backend/requirements.lock')
    options = parser.parse_args()
    build(options.destination, wheels_dir=options.wheels_dir)
