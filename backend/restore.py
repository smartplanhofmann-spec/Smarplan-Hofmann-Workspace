"""Restore a backup to a new database and invalidate all saved sessions."""
import argparse
from contextlib import closing
import sqlite3
from pathlib import Path

from backup import backup


def restore(source, destination):
    target = backup(source, destination)
    try:
        with closing(sqlite3.connect(target)) as database, database:
            database.execute("DELETE FROM sessions")
            if database.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='plan_sessions'").fetchone():
                database.execute("DELETE FROM plan_sessions")
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print("Wiederhergestellt, erneute Anmeldung erforderlich:", restore(args.source, args.destination))
