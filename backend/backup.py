"""Consistent SQLite backup; never overwrite an existing destination."""
import argparse
from contextlib import closing
import os
import sqlite3
from pathlib import Path


def backup(source, destination):
    source, destination = Path(source).resolve(), Path(destination).absolute()
    if not source.is_file():
        raise FileNotFoundError("Quelldatenbank nicht gefunden")
    if source == destination.resolve():
        raise ValueError("Quelle und Ziel müssen verschieden sein")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Atomic exclusive creation avoids overwriting a user file or following a target symlink.
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as reader:
            with closing(sqlite3.connect(destination)) as writer, writer:
                reader.backup(writer)
                if writer.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("Integritätsprüfung der Sicherung fehlgeschlagen")
                if writer.execute("PRAGMA foreign_key_check").fetchone():
                    raise ValueError("Ungültige Datenbankbeziehungen")
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print("Sicherung erstellt:", backup(args.source, args.destination))
