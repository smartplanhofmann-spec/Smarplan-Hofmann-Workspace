"""Offline candidate-database preparation for a coordinated operator update.

Never migrate or restore into the active database. No credentials or row contents
are logged. A prepared candidate does not itself activate a new release.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import tempfile

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from online.backup import backup
from online.restore import restore_dump
from online.store import migrate, PostgresOffice, SCHEMA_VERSION

NAME = re.compile(r'[a-z][a-z0-9_]{1,62}')


def validate_dsns(active_dsn, candidate_dsn, *, test_mode=False):
    source, target = conninfo_to_dict(active_dsn), conninfo_to_dict(candidate_dsn)
    if not test_mode and any(os.environ.get(name) for name in ('PGHOSTADDR', 'PGPORT', 'PGSERVICE', 'PGSERVICEFILE', 'PGOPTIONS')):
        raise ValueError('Unerwartete libpq-Umgebungsauswahl. Lokale Serverkonfiguration zuerst prüfen.')
    if not NAME.fullmatch(source.get('dbname', '')) or not NAME.fullmatch(target.get('dbname', '')):
        raise ValueError('Gültige explizite Datenbanknamen erforderlich.')
    if source['dbname'] == target['dbname']:
        raise ValueError('Die aktive Datenbank darf niemals Ziel des Updates sein.')
    if {k: v for k, v in source.items() if k != 'dbname'} != {k: v for k, v in target.items() if k != 'dbname'}:
        raise ValueError('Quelle und Kandidat müssen dieselbe lokale Verbindung verwenden.')
    # No service files, hidden credentials, URI options, remote routes or role changes.
    allowed = {'dbname', 'host', 'port', 'user', 'connect_timeout', 'application_name'}
    if test_mode:
        allowed.add('password')  # Explicit disposable CI credentials only; peer production stays password-free.
    if set(source) - allowed or set(target) - allowed:
        raise ValueError('Für das Update wird eine explizite lokale Verbindung ohne Passwort erwartet.')
    if test_mode:
        if (source['dbname'] != 'smartplan_check' or target['dbname'] != 'smartplan_release_check' or
                source.get('host') not in ('127.0.0.1', 'localhost') or source.get('user') != 'postgres'):
            raise ValueError('Testmodus ausschließlich für die benannten lokalen Einwegdatenbanken.')
    elif (source.get('host') != '/var/run/postgresql' or source.get('user') != 'smartplan-online' or
          source.get('port', '5432') != '5432'):
        raise ValueError('Produktionsupdate erwartet lokale PostgreSQL-Peer-Anmeldung des Dienstkontos.')
    return source, target


def no_other_clients(dsn):
    with psycopg.connect(dsn, connect_timeout=5) as connection:
        count = connection.execute("SELECT COUNT(*) FROM pg_stat_activity WHERE datname=current_database() "
                                   "AND backend_type='client backend' AND pid<>pg_backend_pid()").fetchone()[0]
        if count:
            raise RuntimeError('Andere Datenbankverbindungen aktiv. Dienste/Verwaltung geordnet anhalten; keine fremden Prozesse beenden.')


def public_tables(connection):
    return [row[0] for row in connection.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]


def snapshot_fingerprint(dsn):
    """Hash every row of every public table; only counts/digests leave this function."""
    result = {}
    with psycopg.connect(dsn, connect_timeout=5) as connection:
        connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        for table in public_tables(connection):
            digest, count = hashlib.sha256(), 0
            query = sql.SQL('SELECT row_to_json(t)::text FROM public.{} t ORDER BY row_to_json(t)::text').format(sql.Identifier(table))
            with connection.cursor(name='release_fingerprint') as cursor:
                cursor.execute(query)
                for row in cursor:
                    digest.update(row[0].encode('utf-8'))
                    digest.update(b'\n')
                    count += 1
            result[table] = {'rows': count, 'digest': digest.hexdigest()}
    return result


def sequence_state(dsn):
    with psycopg.connect(dsn, connect_timeout=5) as connection:
        return dict(connection.execute("SELECT sequencename,last_value FROM pg_sequences "
                                       "WHERE schemaname='public' ORDER BY sequencename"))


def inspect_source(dsn):
    no_other_clients(dsn)
    with psycopg.connect(dsn, connect_timeout=5) as connection:
        rows = connection.execute('SELECT version FROM smartplan_schema').fetchall()
        if len(rows) != 1 or rows[0][0] not in (1, SCHEMA_VERSION):
            raise RuntimeError('Quellschema für dieses Update nicht unterstützt.')
        return rows[0][0]


def prepare(active_dsn, candidate_dsn, backup_directory, *, test_mode=False):
    validate_dsns(active_dsn, candidate_dsn, test_mode=test_mode)
    source_schema = inspect_source(active_dsn)
    with psycopg.connect(candidate_dsn, connect_timeout=5) as target:
        if target.execute("SELECT 1 FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema')").fetchone():
            raise ValueError('Kandidat muss vollständig leer sein.')
    original = snapshot_fingerprint(active_dsn)
    sequences = sequence_state(active_dsn)
    saved = backup(active_dsn, backup_directory)
    no_other_clients(active_dsn)
    if snapshot_fingerprint(active_dsn) != original or sequence_state(active_dsn) != sequences:
        raise RuntimeError('Quelle wurde während der Sicherung geändert; Update nicht fortsetzen.')
    restore_dump(saved, active_dsn, candidate_dsn)
    if snapshot_fingerprint(candidate_dsn) != original or sequence_state(candidate_dsn) != sequences:
        raise RuntimeError('Rücksicherung stimmt nicht vollständig mit der Quelle überein.')
    migrate(candidate_dsn)
    migrated = snapshot_fingerprint(candidate_dsn)
    if any(migrated.get(table) != content for table, content in original.items() if table != 'smartplan_schema'):
        raise RuntimeError('Migration hat vorhandene Geschäftsdaten verändert.')
    office = PostgresOffice(candidate_dsn)
    try:
        with office.lock, office.db:
            if not office.db.execute("SELECT 1 FROM users WHERE active=1 AND role='owner'").fetchone():
                raise RuntimeError('Kandidat besitzt keine aktive Geschäftsführung.')
            for row in office.db.execute('SELECT pdf,pdf_hash FROM reports WHERE pdf IS NOT NULL'):
                if hashlib.sha256(row['pdf']).hexdigest() != row['pdf_hash']:
                    raise ValueError('PDF-Integritätsprüfung im Kandidaten fehlgeschlagen.')
    finally:
        office.db.close()
    no_other_clients(active_dsn)
    if snapshot_fingerprint(active_dsn) != original or sequence_state(active_dsn) != sequences:
        raise RuntimeError('Quelle wurde während der Vorbereitung geändert; Kandidaten nicht aktivieren.')
    return {'backup': str(saved), 'source_schema': source_schema, 'target_schema': SCHEMA_VERSION,
            'tables': original, 'sequences': sequences}


def atomic_write(path, content, *, mode=0o600, uid=None, gid=None):
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            os.fchmod(stream.fileno(), mode)
            if uid is not None and gid is not None:
                os.fchown(stream.fileno(), uid, gid)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


def read_environment(path, *, test_mode=False):
    path = Path(path)
    info = path.lstat()
    expected_uid = os.getuid() if test_mode else 0
    if not stat.S_ISREG(info.st_mode) or info.st_uid != expected_uid or info.st_mode & 0o037 or info.st_size > 65536:
        raise ValueError('Dienstkonfiguration auf Eigentümer, Dateityp und Rechte prüfen.')
    data = path.read_bytes()
    lines = data.decode('utf-8').splitlines(keepends=True)
    candidates = [i for i, line in enumerate(lines)
                  if re.match(r'^\s*(?:export\s+)?SMARTPLAN_DATABASE_DSN\s*=', line)]
    if len(candidates) != 1 or not lines[candidates[0]].startswith('SMARTPLAN_DATABASE_DSN='):
        raise ValueError('Genau eine kanonische explizite Datenbankzeile erforderlich.')
    index = candidates[0]
    values = shlex.split(lines[index].split('=', 1)[1].strip())
    if len(values) != 1:
        raise ValueError('Datenbankzeile muss ein korrekt zitiertes einzelnes Feld enthalten.')
    return info, lines, index, values[0]


def update_environment(path, new_database, *, test_mode=False):
    if not isinstance(new_database, str) or not NAME.fullmatch(new_database):
        raise ValueError('Ungültiger Kandidatenname.')
    info, lines, index, active = read_environment(path, test_mode=test_mode)
    candidate = make_conninfo(active, dbname=new_database)
    validate_dsns(active, candidate, test_mode=test_mode)
    lines[index] = 'SMARTPLAN_DATABASE_DSN=' + shlex.quote(candidate) + '\n'
    atomic_write(path, ''.join(lines).encode('utf-8'), mode=stat.S_IMODE(info.st_mode), uid=info.st_uid, gid=info.st_gid)


def check_capacity(data_directory, backup_directory, database_bytes):
    if type(database_bytes) is not int or database_bytes <= 0:
        raise ValueError('Positive PostgreSQL-Datenbankgröße erforderlich.')
    data, target = Path(data_directory), Path(backup_directory)
    margin = 256 * 1024 * 1024
    if data.stat().st_dev == target.stat().st_dev:
        if shutil.disk_usage(data).free < 3 * database_bytes + 2 * margin:
            raise RuntimeError('Zu wenig freier Platz für Datenbankklon, Dump und WAL-Reserve.')
    elif (shutil.disk_usage(data).free < 2 * database_bytes + margin or
          shutil.disk_usage(target).free < database_bytes + margin):
        raise RuntimeError('Zu wenig Platz auf PostgreSQL- oder Sicherungsdateisystem.')


def maintenance_config(config):
    marker = '\thandle @online {\n'
    end_marker = '\n\t@application '
    if config.count(marker) != 1 or config.count(end_marker) != 1:
        raise ValueError('Bekannte Online-Caddy-Konfiguration erforderlich.')
    start, end = config.index(marker), config.index(end_marker)
    return config[:start] + ('\thandle @online {\n\t\theader Retry-After "60"\n'
                            '\t\trespond `{"error":"Serverupdate. Lokale Eingaben bleiben erhalten."}` 503\n\t}\n') + config[end:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['validate', 'prepare', 'configure', 'maintenance', 'phase', 'size', 'capacity'])
    parser.add_argument('--candidate')
    parser.add_argument('--path')
    parser.add_argument('--output')
    parser.add_argument('--backup-directory')
    parser.add_argument('--value')
    args = parser.parse_args()
    if args.action == 'size':
        with psycopg.connect(os.environ['SMARTPLAN_DATABASE_DSN'], connect_timeout=5) as connection:
            print(connection.execute('SELECT pg_database_size(current_database())').fetchone()[0])
    elif args.action == 'capacity':
        check_capacity(args.path, args.backup_directory, int(args.value))
    elif args.action in ('validate', 'prepare'):
        if not args.candidate or not NAME.fullmatch(args.candidate):
            parser.error('Kandidatenname erforderlich.')
        active = os.environ['SMARTPLAN_DATABASE_DSN']
        target = make_conninfo(active, dbname=args.candidate)
        validate_dsns(active, target)
        if args.action == 'validate':
            inspect_source(active)
        else:
            if not args.output or not args.backup_directory:
                parser.error('Berichtsdatei und Sicherungsordner erforderlich.')
            result = prepare(active, target, args.backup_directory)
            atomic_write(args.output, (json.dumps(result, sort_keys=True) + '\n').encode())
            print('Kandidat rückgesichert, Daten verglichen und Migration geprüft.')
    elif args.action == 'configure':
        update_environment(args.path, args.candidate)
    elif args.action == 'maintenance':
        atomic_write(args.output, maintenance_config(Path(args.path).read_text()).encode(), mode=0o644)
    else:
        if args.value not in ('prepared', 'maintenance', 'stopped', 'verified', 'activating', 'active', 'rolled_back'):
            parser.error('Unbekannte Updatephase.')
        atomic_write(args.path, (args.value + '\n').encode())


if __name__ == '__main__':
    main()
