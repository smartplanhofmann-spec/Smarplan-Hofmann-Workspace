"""Restore only into an empty, different PostgreSQL database; revoke saved sessions."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import psycopg
from psycopg.conninfo import make_conninfo
from online.store import PostgresOffice, migrate
from online.plan_imports import validate_integrity


def restore_dump(source, active_dsn, target_dsn):
    """Restore into a different empty DB; caller must validate schema and contents."""
    source = Path(source)
    sidecar = Path(str(source) + '.sha256')
    if source.is_symlink() or sidecar.is_symlink():
        raise ValueError('Sicherungsdateien dürfen keine Symlinks sein.')
    expected = sidecar.read_text().strip().split('  ', 1)
    with source.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if expected != [actual, source.name]:
        raise ValueError('Prüfsumme der Sicherung stimmt nicht überein.')
    with psycopg.connect(active_dsn) as active, psycopg.connect(target_dsn) as target:
        if active.info.dbname == target.info.dbname:
            raise ValueError('Die aktive Datenbank darf nicht Wiederherstellungsziel sein.')
        if target.execute("SELECT 1 FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema')").fetchone():
            raise ValueError('Wiederherstellungsziel muss leer sein.')
    with source.open('rb') as stream:
        result = subprocess.run(['pg_restore', '--exit-on-error', '--single-transaction', '--no-owner', '--no-acl',
                                 '--dbname', target_dsn], stdin=stream, stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE, timeout=300)
    if result.returncode:
        raise RuntimeError('Wiederherstellung fehlgeschlagen; neue Zieldatenbank bleibt vom Betrieb getrennt.')


def restore(source, active_dsn, target_dsn):
    restore_dump(source, active_dsn, target_dsn)
    # Older supported backups are upgraded only in the separate empty target.
    # The active database is never migrated or restored by this command.
    migrate(target_dsn)
    office = PostgresOffice(target_dsn)
    try:
        with office.lock, office.db:
            for row in office.db.execute('SELECT pdf,pdf_hash FROM reports WHERE pdf IS NOT NULL'):
                if hashlib.sha256(row['pdf']).hexdigest() != row['pdf_hash']:
                    raise ValueError('PDF-Integritätsprüfung fehlgeschlagen.')
            validate_integrity(office)
            for table in ('sessions', 'plan_sessions', 'auth_challenges', 'login_limits'):
                office.db.execute(f'DELETE FROM {table}')
            office.db.execute('UPDATE inbound_import_tokens SET revoked_at=? WHERE revoked_at IS NULL', (time.time(),))
    finally:
        office.db.close()


if __name__ == '__main__':
    if len(sys.argv) != 3 or not re.fullmatch(r'[a-z][a-z0-9_]{1,62}', sys.argv[2]):
        raise SystemExit('Aufruf: python -m online.restore DATEI.dump NEUER_DATENBANKNAME')
    active_dsn = os.environ['SMARTPLAN_DATABASE_DSN']
    restore(sys.argv[1], active_dsn, make_conninfo(active_dsn, dbname=sys.argv[2]))
    print('Sicherung in neue Datenbank wiederhergestellt; alte Sitzungen verworfen. Nicht automatisch aktiviert.')
