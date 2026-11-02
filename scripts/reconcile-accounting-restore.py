#!/usr/bin/env python3
"""Release a reviewed local SQLite restore after stopping every app/server.

This OS-operator command opens an existing database without migration. An
exclusive writer transaction does not prove that all WAL readers have stopped.
The independent source/payment evidence remains the operator's responsibility.
"""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import threading
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from business_schema import reconcile_local_financial_restore, state
from core import Problem


MAX_REPORT_BYTES = 4 * 1024 * 1024


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Mehrdeutiger Prüfbericht.')
        value[key] = item
    return value


def _nonfinite(value):
    raise ValueError('Ungültiger Prüfbericht.')


def read_evidence(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Prüfbericht darf kein Symlink sein.')
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_REPORT_BYTES
                or os.name == 'posix' and (info.st_uid not in (0, os.geteuid()) or info.st_mode & 0o077)):
            raise ValueError('Regulärer, privater und begrenzter Betreiber-Prüfbericht erforderlich.')
        raw = stream.read(MAX_REPORT_BYTES + 1)
        after = os.fstat(stream.fileno())
        if len(raw) != info.st_size or (after.st_size, after.st_mtime_ns) != (info.st_size, info.st_mtime_ns):
            raise ValueError('Prüfbericht wurde während des Lesens verändert.')
    try:
        evidence = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique, parse_constant=_nonfinite)
    except (UnicodeError, ValueError, RecursionError):
        raise ValueError('Eindeutiger UTF-8-JSON-Prüfbericht erwartet.') from None
    return evidence, hashlib.sha256(raw).hexdigest()


def reconcile(database, evidence_path, *, application_stopped=False):
    if application_stopped is not True:
        raise ValueError('Zuerst alle Apps/Server vollständig stoppen und --application-stopped bestätigen.')
    database = Path(database).absolute()
    info = database.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('Vorhandene reguläre SQLite-Datenbank ohne Symlink erforderlich.')
    evidence, evidence_sha256 = read_evidence(evidence_path)
    with closing(sqlite3.connect(database.as_uri() + '?mode=rw', uri=True, timeout=5)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        current = database.lstat()
        if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino) or not stat.S_ISREG(current.st_mode):
            raise ValueError('Datenbank wurde während des Öffnens ersetzt.')
        office = SimpleNamespace(db=connection, lock=threading.RLock())
        result = reconcile_local_financial_restore(office, evidence, evidence_sha256,
                                                   application_stopped=True)
    return {**result, 'evidence_sha256': evidence_sha256}


def inspect(database):
    """A consistent read-only local snapshot, deliberately not a review report."""
    database = Path(database).absolute()
    info = database.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('Vorhandene reguläre SQLite-Datenbank ohne Symlink erforderlich.')
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=5)) as connection:
        connection.row_factory = sqlite3.Row
        current = database.lstat()
        if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino) or not stat.S_ISREG(current.st_mode):
            raise ValueError('Datenbank wurde während des Öffnens ersetzt.')
        office = SimpleNamespace(db=connection, lock=threading.RLock(), _allow_restore_pending=True)
        connection.execute('BEGIN')
        try:
            current = state(office)
            if current['storage_version'] != 7:
                raise ValueError('Legacy-Datenbank besitzt keinen Business-Finanzfreigabestand.')
            accounting = None
            if 'business_accounting' in current.get('read_capabilities', []):
                from business_accounting import restore_horizon
                accounting = restore_horizon(office)
            numbers = [dict(company_id=row['company_id'], series=row['series'], year=row['year'],
                            last_value=row['next_value'] - 1) for row in connection.execute(
                'SELECT * FROM business_document_counters ORDER BY company_id,series,year')]
            return dict(inspection_only=True, evidence_schema=2 if accounting is not None else 1,
                restore_id=current['restore_id'], restore_pending=current['restore_pending'],
                financial_reconciliation_required=current['financial_reconciliation_required'],
                number_horizons=numbers, accounting_horizon=accounting, external_review_required=True,
                notice='Nur lokaler Snapshot. Kein Prüfbericht und keine Freigabe; externe Quellen und Zahlungen seit der Sicherung unabhängig prüfen.')
        finally:
            connection.rollback()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, type=Path, help='Vorhandene lokale SQLite-Datei')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--evidence', type=Path, help='Privater, unabhängig geprüfter JSON-Bericht für die Freigabe')
    mode.add_argument('--inspect', action='store_true', help='Nur lokale Horizonte und Sperren lesen; kein Prüfbericht, keine Freigabe')
    parser.add_argument('--application-stopped', action='store_true',
                        help='Alle Apps und Server dieser Datenbank sind vollständig beendet')
    args = parser.parse_args(argv)
    try:
        if args.inspect:
            if args.application_stopped:
                raise ValueError('--application-stopped gehört ausschließlich zum Freigabeaufruf mit --evidence.')
            result = inspect(args.database)
        else:
            result = reconcile(args.database, args.evidence, application_stopped=args.application_stopped)
    except (Problem, ValueError, OSError, RuntimeError, sqlite3.DatabaseError) as error:
        parser.error(error.message if isinstance(error, Problem) else str(error))
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
