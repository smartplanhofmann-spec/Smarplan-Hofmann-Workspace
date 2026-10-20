"""Local Windows start, verified backups and non-destructive restore.

Only the UI imports tkinter; lifecycle/backup code also runs in Linux CI.
No package installation, network downloads or default accounts are performed.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
import uuid

from backup import backup
from restore import restore


class SupportError(Exception):
    pass


class InstallationLock:
    """An OS lock releases even if the launcher crashes; stale files are harmless."""
    def __init__(self, root):
        self.path = Path(root) / "office.lock"
        self.stream = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("a+b")
        self.stream.seek(0, 2)
        if not self.stream.tell():
            self.stream.write(b"0")
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self.stream.close()
            self.stream = None
            raise SupportError("Smartplan läuft bereits oder eine Sicherung ist noch aktiv. "
                               "Bitte zuerst die App und das Startfenster schließen.") from error
        return self

    def __exit__(self, *args):
        if self.stream:
            if os.name == "nt":
                import msvcrt
                self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream, fcntl.LOCK_UN)
            self.stream.close()


def stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]


def load_config(root):
    path = Path(root) / "start-config.json"
    if not path.exists():
        return {"data_dir": str(Path(root) / "data")}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("data_dir"), str):
        raise SupportError("Die Startkonfiguration ist ungültig. Bitte nicht löschen; Support kontaktieren.")
    return value


def save_config(root, config):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    temporary = root / ("start-config-" + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(root / "start-config.json")
    finally:
        temporary.unlink(missing_ok=True)


def validate_database(path):
    path = Path(path).resolve()
    if not path.is_file():
        raise SupportError("Die vorhandene Smartplan-Datenbank wurde nicht gefunden:\n" + str(path)
                           + "\nEs wird keine leere Ersatzdatenbank angelegt.")
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as database:
        tables = {row[0] for row in database.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"users", "sessions", "projects", "assignments", "reports", "audit", "secrets"} <= tables:
            raise SupportError("Die Datei ist keine vollständige Smartplan-Datenbank.")
        if not database.execute("SELECT 1 FROM users WHERE role='owner' AND active=1").fetchone():
            raise SupportError("In dieser Datenbank fehlt ein aktiver Zugang der Geschäftsführung.")


def file_hash(path):
    checksum = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def create_backup(data_dir, destination_dir, reason="manuell"):
    source = Path(data_dir) / "office.sqlite3"
    validate_database(source)
    target = Path(destination_dir) / ("smartplan-" + stamp() + "-" + reason + ".sqlite3")
    backup(source, target)
    try:
        # Sidecar creation is exclusive, just like the database backup.
        with target.with_suffix(".sqlite3.sha256").open("x", encoding="ascii") as checksum:
            checksum.write(file_hash(target) + "\n")
    except Exception:
        # Keep the valid database even if its checksum cannot be written.
        raise SupportError("Datenbank gesichert, aber Prüfsumme konnte nicht gespeichert werden:\n" + str(target))
    return target


def verified_restore(root, config, source):
    """Prepare a new data directory, then switch config only after full validation."""
    root, source = Path(root), Path(source).resolve()
    checksum_file = source.with_suffix(".sqlite3.sha256")
    if not checksum_file.is_file():
        raise SupportError("Die zugehörige .sqlite3.sha256-Datei fehlt. Bitte beide Sicherungsdateien auswählen bzw. zusammen ablegen.")
    expected = checksum_file.read_text(encoding="ascii").strip()
    if len(expected) != 64 or file_hash(source) != expected:
        raise SupportError("Die Prüfsumme stimmt nicht. Die Sicherung wurde nicht wiederhergestellt.")
    current = Path(config["data_dir"]) / "office.sqlite3"
    if source == current.resolve():
        raise SupportError("Bitte eine Sicherung auswählen, nicht die aktuell verwendete Datenbank.")
    restored_dir = root / "restored" / stamp()
    restored_dir.mkdir(parents=True)
    staged = restored_dir / "verified-source.tmp"
    try:
        # Verify the exact private copy used for restore, even if the external file changes.
        with source.open("rb") as reader, staged.open("xb") as writer:
            shutil.copyfileobj(reader, writer)
        if file_hash(staged) != expected:
            raise SupportError("Die Sicherung hat sich beim Einlesen verändert.")
        validate_database(staged)
        previous = create_backup(config["data_dir"], root / "backups", "vor-wiederherstellung")
        target = restore(staged, restored_dir / "office.sqlite3")
        validate_database(target)
        updated = {**config, "data_dir": str(restored_dir), "previous_data_dir": config["data_dir"]}
        save_config(root, updated)
    finally:
        staged.unlink(missing_ok=True)
    return restored_dir, previous


def ensure_port_free(port):
    with socket.socket() as connection:
        connection.settimeout(0.5)
        if connection.connect_ex(("127.0.0.1", port)) == 0:
            raise SupportError("Auf Port " + str(port) + " läuft bereits ein Server. "
                               "Schließe die bisherige Smartplan-App und beende den alten Server "
                               "in seinem Terminal mit Strg+C. Starte danach erneut.")


def stop_child(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def launch(root, config, app_path, *, port=8765, run_app=None):
    """Caller holds InstallationLock. Always stop only the child we started."""
    root = Path(root)
    app_path = Path(app_path)
    if not app_path.is_file():
        raise SupportError("Die Windows-App wurde nicht gefunden. Bitte erneut auswählen.")
    data_dir = Path(config["data_dir"]).resolve()
    validate_database(data_dir / "office.sqlite3")
    ensure_port_free(port)
    before = create_backup(data_dir, root / "backups", "vor-start")
    environment = os.environ.copy()
    environment["OFFICE_DATA_DIR"] = str(data_dir)
    launch_id = uuid.uuid4().hex
    environment["SMARTPLAN_LAUNCH_ID"] = launch_id
    # Health requests never go through the corporate/injected HTTP proxy.
    local_http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    with (log_dir / ("server-" + stamp() + ".log")).open("wb") as log:
        server = subprocess.Popen(
            [sys.executable, "-u", str(Path(__file__).with_name("server.py")), "--port", str(port)],
            cwd=Path(__file__).parent, env=environment, stdin=subprocess.DEVNULL,
            stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            deadline = time.monotonic() + 20
            while True:
                if server.poll() is not None:
                    raise SupportError("Der Server konnte nicht starten. Protokollordner:\n" + str(log_dir))
                try:
                    with local_http.open("http://127.0.0.1:" + str(port) + "/health", timeout=1) as response:
                        status = json.load(response)
                    if status.get("status") == "ok" and status.get("launch_id") == launch_id:
                        break
                except (OSError, ValueError):
                    pass
                if time.monotonic() >= deadline:
                    raise SupportError("Der Server antwortet nicht. Protokollordner:\n" + str(log_dir))
                time.sleep(0.1)
            print("Smartplan läuft. Dieses Startfenster geöffnet lassen.", flush=True)
            print("Sicherung vor dem Start: " + str(before), flush=True)
            if run_app is None:
                result = subprocess.run([str(app_path)], cwd=app_path.parent, check=False)
                if result.returncode:
                    raise SupportError("Die Windows-App wurde mit einem Fehler beendet: " + str(result.returncode))
            else:
                run_app(port)
        finally:
            stop_child(server)
            after = create_backup(data_dir, root / "backups", "nach-ende")
            print("Sicherung nach dem Schließen: " + str(after), flush=True)
    return after


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "backup", "restore"))
    args = parser.parse_args()
    import tkinter as tk
    from tkinter import filedialog, messagebox
    window = tk.Tk()
    window.withdraw()
    try:
        local_data = os.environ.get("LOCALAPPDATA")
        if not local_data:
            raise SupportError("LOCALAPPDATA fehlt; bitte auf dem eingerichteten Windows-PC ausführen.")
        root = Path(local_data) / "SmartplanOffice"
        with InstallationLock(root):
            config = load_config(root)
            if args.action == "start":
                bundled = Path(__file__).parent.parent / "smartplan_office.exe"
                app = bundled if bundled.is_file() else Path(config.get("app_path", "__missing__"))
                if not app.is_file():
                    messagebox.showinfo("Smartplan Office", "Bitte einmal die bereits entpackte smartplan_office.exe auswählen.\nDie Auswahl wird für weitere Starts gespeichert.")
                    selected = filedialog.askopenfilename(title="Smartplan-App auswählen", filetypes=[("Smartplan Office", "smartplan_office.exe")])
                    if not selected:
                        return 0
                    app = Path(selected)
                if app.name.lower() != "smartplan_office.exe":
                    raise SupportError("Bitte die Datei smartplan_office.exe auswählen.")
                if not (app.parent / "flutter_windows.dll").is_file() or not (app.parent / "data").is_dir():
                    raise SupportError("Das App-Paket ist unvollständig. Bitte das gesamte Windows-ZIP entpacken und alle Dateien zusammen lassen.")
                validate_database(Path(config["data_dir"]) / "office.sqlite3")
                config["app_path"] = str(app.resolve())
                save_config(root, config)
                launch(root, config, app)
            elif args.action == "backup":
                destination = filedialog.askdirectory(title="Sicherungsordner wählen, z. B. auf einem USB-Laufwerk")
                if not destination:
                    return 0
                saved = create_backup(config["data_dir"], destination)
                messagebox.showinfo("Sicherung erstellt", "Datenbank und Prüfsumme wurden gespeichert:\n" + str(saved) + "\n\nBeide Dateien zusammen aufbewahren.")
            else:
                ensure_port_free(8765)
                selected = filedialog.askopenfilename(title="Smartplan-Sicherung auswählen", filetypes=[("Smartplan-Sicherung", "*.sqlite3")])
                if not selected:
                    return 0
                if not messagebox.askyesno("Sicherung wiederherstellen", "Diese Sicherung als Arbeitsstand verwenden?\n\n" + selected + "\n\nDie aktuellen Daten werden vorher gesichert und bleiben im bisherigen Ordner erhalten. Änderungen nach dem Sicherungszeitpunkt fehlen im wiederhergestellten Stand. Danach erneut anmelden.", default=messagebox.NO):
                    return 0
                target, previous = verified_restore(root, config, selected)
                messagebox.showinfo("Wiederherstellung abgeschlossen", "Neuer Datenordner:\n" + str(target) + "\n\nSicherung des vorherigen Stands:\n" + str(previous) + "\n\nJetzt Starten.cmd öffnen und erneut anmelden.")
        return 0
    except Exception as error:
        messagebox.showerror("Smartplan Office", str(error))
        return 1
    finally:
        window.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
