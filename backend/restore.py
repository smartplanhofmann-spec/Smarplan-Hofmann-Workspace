"""Restore a backup to a new database and invalidate all saved sessions."""
import argparse
from contextlib import closing
import sqlite3
import uuid
from pathlib import Path

if __package__:
    from .backup import backup
else:
    from backup import backup


def restore(source, destination):
    target = backup(source, destination)
    try:
        with closing(sqlite3.connect(target)) as database, database:
            database.row_factory = sqlite3.Row
            # SQLite enables cascades per connection. Revoke dependent device
            # grants together with their sessions before any transaction starts.
            database.execute("PRAGMA foreign_keys=ON")
            database.execute("DELETE FROM sessions")
            if database.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='plan_sessions'").fetchone():
                database.execute("DELETE FROM plan_sessions")
            from business_portal import sanitize_after_restore
            sanitize_after_restore(database)
            from business_customer_workspace import sanitize_after_restore as sanitize_customer_workspace
            sanitize_customer_workspace(database)
            from business_assistant import sanitize_after_restore as sanitize_assistant
            sanitize_assistant(database)
            from business_company_events import sanitize_after_restore as sanitize_company_events
            sanitize_company_events(database)
            from business_assistant_speech import sanitize_after_restore as sanitize_speech
            sanitize_speech(database)
            if database.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='business_schema_state'").fetchone():
                # A backup cannot establish which financial events occurred
                # after it. Only the separate local operator command releases
                # this fresh restore identity; a normal app login never does.
                updated = database.execute('UPDATE business_restore_state SET '
                    'financial_reconciliation_required=1,restore_id=? WHERE singleton=1', (uuid.uuid4().hex,))
                if updated.rowcount != 1:
                    raise ValueError('Vollständiger Business-Restorestand erforderlich.')
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
