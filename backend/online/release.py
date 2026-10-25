"""Offline candidate-database preparation for a coordinated operator update.

Never migrate or restore into the active database. No credentials or row contents
are logged. A prepared candidate does not itself activate a new release.
"""
import argparse
import hashlib
import json
import os
import pwd
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
from online.plan_imports import validate_integrity

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
        if len(rows) != 1 or rows[0][0] not in (1, 2, 3, 4, 5, 6, SCHEMA_VERSION):
            raise RuntimeError('Quellschema für dieses Update nicht unterstützt.')
        return rows[0][0]


def operator_dsns(active_dsn, candidate_dsn, *, test_mode=False):
    """Keep configured runtime peer DSNs; derive admin DSNs only for trusted EUID."""
    source, target = validate_dsns(active_dsn, candidate_dsn, test_mode=test_mode)
    if not test_mode and os.geteuid() != pwd.getpwnam('postgres').pw_uid:
        raise ValueError('Privilegierte Vorbereitung ausschließlich als lokaler PostgreSQL-Operator.')
    source_dsn = make_conninfo(active_dsn, user='postgres')
    target_dsn = make_conninfo(candidate_dsn, user='postgres')
    with psycopg.connect(source_dsn, connect_timeout=5) as connection:
        roles = connection.execute("SELECT rolname,rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
                                   "FROM pg_roles WHERE rolname IN ('smartplan-online','smartplan-migrator')").fetchall()
        found = {row[0]: row[1:] for row in roles}
        if (set(found) != {'smartplan-online', 'smartplan-migrator'} or found['smartplan-migrator'] != (False, False, False, False, False, False)
                or found['smartplan-online'] != (True, False, False, False, False, False)):
            raise ValueError('Bekannte getrennte PostgreSQL-Rollen zuerst vorbereiten.')
        if connection.execute("SELECT pg_has_role('smartplan-online','smartplan-migrator','MEMBER')").fetchone()[0]:
            raise ValueError('Runtime darf keine Migrationsrolle übernehmen.')
        owners = dict(connection.execute("SELECT datname,pg_get_userbyid(datdba) FROM pg_database WHERE datname IN (%s,%s)",
                                          (source['dbname'], target['dbname'])))
        allowed_source = ('smartplan-online', 'smartplan-migrator', 'postgres') if test_mode else ('smartplan-online', 'smartplan-migrator')
        if owners.get(source['dbname']) not in allowed_source or owners.get(target['dbname']) != 'smartplan-migrator':
            raise ValueError('Quell-/Kandidatenownership zuerst prüfen.')
    return source_dsn, target_dsn


def secure_database(active_dsn, *, test_mode=False):
    """Explicit, stopped local installation only. No REASSIGN OWNED cluster effects."""
    active = conninfo_to_dict(active_dsn)
    guard_name = 'smartplan_security_guard' if active.get('dbname') != 'smartplan_security_guard' else 'smartplan_security_guard2'
    if test_mode:
        validate_dsns(active_dsn, make_conninfo(active_dsn, dbname='smartplan_release_check'), test_mode=True)
    else:
        validate_dsns(active_dsn, make_conninfo(active_dsn, dbname=guard_name))
        if os.geteuid() != pwd.getpwnam('postgres').pw_uid:
            raise ValueError('Lokaler PostgreSQL-Operator erforderlich.')
    dsn = make_conninfo(active_dsn, user='postgres')
    no_other_clients(dsn)
    with psycopg.connect(dsn, connect_timeout=5) as connection:
        connection.execute("SET LOCAL lock_timeout='10s'")
        connection.execute('SELECT pg_advisory_xact_lock(741290518)')
        runtime = connection.execute("SELECT rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname='smartplan-online'").fetchone()
        if runtime != (True, False, False, False, False, False):
            raise ValueError('Unbekannte Runtime-Rollenrechte; nicht automatisch verändern.')
        migrator = connection.execute("SELECT rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname='smartplan-migrator'").fetchone()
        if migrator is None:
            connection.execute('CREATE ROLE "smartplan-migrator" NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS')
        elif migrator != (False, False, False, False, False, False):
            raise ValueError('Unbekannte Migrationsrollenrechte; nicht automatisch verändern.')
        if connection.execute("SELECT pg_has_role('smartplan-online','smartplan-migrator','MEMBER')").fetchone()[0]:
            raise ValueError('Runtime-Mitgliedschaft in Migrationsrolle zuerst ausdrücklich entfernen.')
        owner = connection.execute('SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database()').fetchone()[0]
        allowed_owners = ('smartplan-online', 'smartplan-migrator', 'postgres') if test_mode else ('smartplan-online', 'smartplan-migrator')
        if owner not in allowed_owners:
            raise ValueError('Fremde Datenbankownership nicht verändern.')
        if connection.execute("SELECT 1 FROM pg_namespace WHERE nspname NOT IN ('public','information_schema','pg_catalog') AND nspname NOT LIKE 'pg_toast%' AND nspname NOT LIKE 'pg_temp_%' LIMIT 1").fetchone():
            raise ValueError('Unbekannte Anwendungsschemas zuerst prüfen.')
        foreign = connection.execute("SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' "
                                     "AND c.relkind IN ('r','p','v','m','S','f') AND NOT(pg_get_userbyid(c.relowner)=ANY(%s)) LIMIT 1", (list(allowed_owners),)).fetchone()
        if foreign:
            raise ValueError('Fremde Objektownership nicht verändern.')
        connection.execute(sql.SQL('ALTER DATABASE {} OWNER TO "smartplan-migrator"').format(sql.Identifier(active['dbname'])))
        connection.execute('ALTER SCHEMA public OWNER TO "smartplan-migrator"')
        for kind, command in (('r', 'TABLE'), ('p', 'TABLE'), ('v', 'VIEW'), ('m', 'MATERIALIZED VIEW')):
            for name, in connection.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind=%s AND pg_get_userbyid(c.relowner)=ANY(%s)", (kind, list(allowed_owners))).fetchall():
                connection.execute(sql.SQL('ALTER {} public.{} OWNER TO "smartplan-migrator"').format(sql.SQL(command), sql.Identifier(name)))
        # Moving a table also moves its owned identity sequence. Handle only the
        # remaining standalone sequences, never REASSIGN OWNED shared databases.
        for name, in connection.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='S' AND pg_get_userbyid(c.relowner)=ANY(%s)", (list(allowed_owners),)).fetchall():
            connection.execute(sql.SQL('ALTER SEQUENCE public.{} OWNER TO "smartplan-migrator"').format(sql.Identifier(name)))
        for name, arguments in connection.execute("SELECT p.proname,pg_get_function_identity_arguments(p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND pg_get_userbyid(p.proowner)=ANY(%s)", (list(allowed_owners),)).fetchall():
            if not name.startswith(('business_', 'smartplan_')):
                raise ValueError('Unbekannte Funktionsownership zuerst prüfen.')
            connection.execute(sql.SQL('ALTER FUNCTION public.{}({}) OWNER TO "smartplan-migrator"').format(sql.Identifier(name), sql.SQL(arguments)))
        from online.store import Database
        from business_schema import apply_runtime_privileges
        office = PostgresOffice.__new__(PostgresOffice)
        office.lock = __import__('threading').RLock()
        office.db = Database.__new__(Database)
        office.db.connection = connection
        office.db.dsn, office.db.contexts = dsn, []
        apply_runtime_privileges(office)
    return dict(owner='smartplan-migrator', runtime='smartplan-online', password_created=False)


def _control_rows(dsn):
    from business_schema import CONTROL_TABLES
    result = {}
    with psycopg.connect(dsn, connect_timeout=5) as connection:
        for table in set(public_tables(connection)) & CONTROL_TABLES:
            result[table] = [json.loads(row[0]) for row in connection.execute(
                sql.SQL('SELECT row_to_json(t)::text FROM public.{} t').format(sql.Identifier(table)))]
    return result


def _verify_control_preserved(before, after, mode):
    for table in ('business_schema_migrations', 'business_schema_events'):
        old = {json.dumps(row, sort_keys=True) for row in before.get(table, [])}
        new = {json.dumps(row, sort_keys=True) for row in after.get(table, [])}
        if not old <= new:
            raise RuntimeError('Migration hat bestehende Schemaquittungen entfernt oder verändert.')
    new_flags = {row['name']: row for row in after.get('business_feature_flags', [])}
    for old in before.get('business_feature_flags', []):
        new = new_flags.get(old['name'])
        if new == old:
            continue
        if (mode != 'legacy' or not new or old['enabled'] != 1 or new['enabled'] != 0
                or new['revision'] != old['revision'] + 1 or set(new) != set(old)):
            raise RuntimeError('Nicht erlaubte Änderung bestehender Business-Freigaben.')


def prepare(active_dsn, candidate_dsn, backup_directory, *, test_mode=False,
            privileged_operator=False, compatibility_mode=None):
    validate_dsns(active_dsn, candidate_dsn, test_mode=test_mode)
    if compatibility_mode not in (None, 'legacy', 'business'):
        raise ValueError('Unbekannter Kandidaten-Kompatibilitätsmodus.')
    if not test_mode and not privileged_operator:
        raise ValueError('Schema 7 benötigt den geprüften privilegierten Operatorpfad.')
    if privileged_operator:
        from business_schema import require_complete_registry
        require_complete_registry()
        active_dsn, candidate_dsn = operator_dsns(active_dsn, candidate_dsn, test_mode=test_mode)
    source_schema = inspect_source(active_dsn)
    with psycopg.connect(candidate_dsn, connect_timeout=5) as target:
        if target.execute("SELECT 1 FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema')").fetchone():
            raise ValueError('Kandidat muss vollständig leer sein.')
    original = snapshot_fingerprint(active_dsn)
    controls = _control_rows(active_dsn)
    sequences = sequence_state(active_dsn)
    saved = backup(active_dsn, backup_directory)
    no_other_clients(active_dsn)
    if snapshot_fingerprint(active_dsn) != original or sequence_state(active_dsn) != sequences:
        raise RuntimeError('Quelle wurde während der Sicherung geändert; Update nicht fortsetzen.')
    if privileged_operator:
        restore_dump(saved, active_dsn, candidate_dsn, owner_role='smartplan-migrator')
    else:
        restore_dump(saved, active_dsn, candidate_dsn)
    if snapshot_fingerprint(candidate_dsn) != original or sequence_state(candidate_dsn) != sequences:
        raise RuntimeError('Rücksicherung stimmt nicht vollständig mit der Quelle überein.')
    migrate(candidate_dsn, owner_role='smartplan-migrator' if privileged_operator else None,
            compatibility_mode=compatibility_mode, require_business_modules=privileged_operator)
    migrated = snapshot_fingerprint(candidate_dsn)
    allowed_control = {'smartplan_schema', 'business_schema_state', 'business_schema_migrations',
                       'business_schema_events', 'business_feature_flags'}
    if any(migrated.get(table) != content for table, content in original.items() if table not in allowed_control):
        raise RuntimeError('Migration hat vorhandene Geschäftsdaten verändert.')
    _verify_control_preserved(controls, _control_rows(candidate_dsn), compatibility_mode)
    office = PostgresOffice(candidate_dsn)
    try:
        with office.lock, office.db:
            if not office.db.execute("SELECT 1 FROM users WHERE active=1 AND role='owner'").fetchone():
                raise RuntimeError('Kandidat besitzt keine aktive Geschäftsführung.')
            for row in office.db.execute('SELECT pdf,pdf_hash FROM reports WHERE pdf IS NOT NULL'):
                if hashlib.sha256(row['pdf']).hexdigest() != row['pdf_hash']:
                    raise ValueError('PDF-Integritätsprüfung im Kandidaten fehlgeschlagen.')
            validate_integrity(office)
            from business_schema import validate_integrity as validate_business, state, apply_runtime_privileges
            validate_business(office)
            business_state = state(office)
            if compatibility_mode and business_state['compatibility_mode'] != compatibility_mode:
                raise RuntimeError('Kandidat besitzt falschen Kompatibilitätsmodus.')
            if privileged_operator:
                apply_runtime_privileges(office)
    finally:
        office.db.close()
    if snapshot_fingerprint(candidate_dsn) != migrated or sequence_state(candidate_dsn) != sequences:
        raise RuntimeError('Kandidat wurde während der abschließenden Integritätsprüfung verändert.')
    no_other_clients(active_dsn)
    if snapshot_fingerprint(active_dsn) != original or sequence_state(active_dsn) != sequences:
        raise RuntimeError('Quelle wurde während der Vorbereitung geändert; Kandidaten nicht aktivieren.')
    return {'backup': str(saved), 'source_schema': source_schema, 'target_schema': SCHEMA_VERSION,
            'tables': original, 'sequences': sequences, 'business': business_state,
            'privileged_operator': privileged_operator}


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


def configure_privacy_environment(path, *, directory='/var/lib/smartplan-online/privacy', test_mode=False):
    """Root setup only: retain existing bindings, never replace a private key.

    No DB connections and no journal interpretation occur under root/postgres.
    The runtime subsequently verifies HMAC/anchors before candidate activation.
    """
    if not test_mode and (os.geteuid() != 0 or str(path) != '/etc/smartplan-online/service.env'):
        raise ValueError('Datenschutzkonfiguration ausschließlich im geschützten Betreiberpfad.')
    info, lines, _, _ = read_environment(path, test_mode=test_mode)
    account = None if test_mode else pwd.getpwnam('smartplan-online')
    uid, gid = (os.getuid(), os.getgid()) if test_mode else (account.pw_uid, account.pw_gid)
    names = ('SMARTPLAN_PRIVACY_CHECKPOINT_FILE', 'SMARTPLAN_PRIVACY_CHECKPOINT_KEY_FILE',
             'SMARTPLAN_PRIVACY_INSTALLATION_ID')
    values = {}
    for name in names:
        matches = [line for line in lines if re.match(r'^\s*(?:export\s+)?' + name + r'\s*=', line)]
        if not matches:
            continue
        if len(matches) != 1 or not matches[0].startswith(name + '='):
            raise ValueError('Datenschutzkonfiguration ist nicht eindeutig und kanonisch.')
        parsed = shlex.split(matches[0].split('=', 1)[1].strip())
        if len(parsed) != 1 or not parsed[0] or any(ord(c) < 32 for c in parsed[0]):
            raise ValueError('Ungültige Datenschutzkonfiguration.')
        values[name] = parsed[0]
    if values and set(values) != set(names):
        raise ValueError('Unvollständige Datenschutzkonfiguration nicht automatisch ersetzen.')

    def private(candidate, *, is_directory=False, expected_size=None):
        candidate = Path(candidate)
        if not candidate.is_absolute() or any(parent.is_symlink() for parent in candidate.parents):
            raise ValueError('Datenschutzpfad muss absolut und ohne Symlinkeltern sein.')
        current = candidate.lstat()
        expected = stat.S_ISDIR(current.st_mode) if is_directory else stat.S_ISREG(current.st_mode)
        if (not expected or current.st_uid != uid or current.st_mode & 0o077
                or expected_size is not None and current.st_size != expected_size):
            raise ValueError('Datenschutzdateien müssen privat dem Runtime-Dienstkonto gehören.')
        return current

    if not values:
        root = Path(directory)
        if not root.is_absolute() or any(parent.is_symlink() for parent in root.parents):
            raise ValueError('Ungültiger Datenschutz-Setup-Pfad.')
        if not root.exists() and not root.is_symlink():
            root.mkdir(mode=0o700)
            directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                # Use the held directory descriptor: its runtime-owned parent
                # must not redirect root writes if the entry is renamed.
                for name, data in (('key', os.urandom(32)), ('installation-id', (__import__('uuid').uuid4().hex + '\n').encode())):
                    descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600,
                                         dir_fd=directory_fd)
                    with os.fdopen(descriptor, 'wb') as stream:
                        os.fchown(stream.fileno(), uid, gid)
                        stream.write(data)
                        stream.flush()
                        os.fsync(stream.fileno())
                os.fchown(directory_fd, uid, gid)
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            descriptor = os.open(root.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        private(root, is_directory=True)
        private(root / 'key', expected_size=32)
        private(root / 'installation-id', expected_size=33)
        with os.fdopen(os.open(root / 'installation-id', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
            identity_info = os.fstat(stream.fileno())
            if not stat.S_ISREG(identity_info.st_mode) or identity_info.st_size != 33:
                raise ValueError('Ungültige Datenschutz-Installationsdatei.')
            installation = stream.read(34).decode('ascii').strip()
        values = dict(zip(names, (str(root / 'journal.json'), str(root / 'key'), installation)))
    if not re.fullmatch(r'[a-f0-9]{32}', values[names[2]]):
        raise ValueError('Ungültige Datenschutz-Installationsbindung.')
    journal, key = Path(values[names[0]]), Path(values[names[1]])
    if journal == key:
        raise ValueError('Journal und Schlüssel müssen getrennt bleiben.')
    private(journal.parent, is_directory=True)
    private(key, expected_size=32)
    if journal.exists() or journal.is_symlink():
        if private(journal).st_size > 8 * 1024 * 1024:
            raise ValueError('Datenschutzjournal ist zu groß.')
    if not any(re.match(r'^\s*(?:export\s+)?' + names[0] + r'\s*=', line) for line in lines):
        content = ''.join(lines)
        if content and not content.endswith('\n'):
            content += '\n'
        content += ''.join(name + '=' + shlex.quote(values[name]) + '\n' for name in names)
        atomic_write(path, content.encode(), mode=stat.S_IMODE(info.st_mode), uid=info.st_uid, gid=info.st_gid)
    return {'configured': True, 'installation_id': values[names[2]]}


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
    parser.add_argument('action', choices=['validate', 'prepare', 'configure', 'maintenance', 'phase', 'size', 'capacity', 'security', 'privacy-configure', 'privacy-init', 'privacy-check', 'reconcile-finance'])
    parser.add_argument('--candidate')
    parser.add_argument('--path')
    parser.add_argument('--output')
    parser.add_argument('--backup-directory')
    parser.add_argument('--value')
    parser.add_argument('--privileged-operator', action='store_true')
    parser.add_argument('--compatibility-mode', choices=['legacy', 'business'])
    args = parser.parse_args()
    if args.action == 'privacy-configure':
        print(json.dumps(configure_privacy_environment(args.path), sort_keys=True))
    elif args.action == 'privacy-init':
        active = os.environ['SMARTPLAN_DATABASE_DSN']
        if not args.candidate or not NAME.fullmatch(args.candidate):
            parser.error('Getrennten Kandidaten angeben.')
        target = make_conninfo(active, dbname=args.candidate)
        validate_dsns(active, target)
        if os.geteuid() != pwd.getpwnam('smartplan-online').pw_uid:
            raise ValueError('Checkpointprüfung ausschließlich als Runtime-Dienstkonto.')
        no_other_clients(active)
        from business_schema import (initialize_privacy_checkpoint, privacy_restore_guard,
                                     require_runtime_security, validate_integrity as validate_business)
        office = PostgresOffice(target)
        try:
            require_runtime_security(office)
            with office.lock, office.db:
                if office.db.execute('SELECT 1 FROM business_privacy_anchors').fetchone():
                    privacy_restore_guard(office)
                result = initialize_privacy_checkpoint(office)
                validate_integrity(office)
                validate_business(office)
                no_other_clients(active)
        finally:
            office.db.close()
        print(json.dumps(result, sort_keys=True))
    elif args.action == 'reconcile-finance':
        active = os.environ['SMARTPLAN_DATABASE_DSN']
        # Derive the operator connection only after the same local-peer/EUID
        # guard used by candidate preparation. No candidate is ever activated.
        if args.candidate and not NAME.fullmatch(args.candidate):
            parser.error('Gültigen getrennten Kandidaten angeben.')
        target = make_conninfo(active, dbname=args.candidate or 'smartplan_reconciliation_guard')
        validate_dsns(active, target)
        if os.geteuid() != pwd.getpwnam('postgres').pw_uid:
            raise ValueError('Finanzabgleich ausschließlich als lokaler PostgreSQL-Operator.')
        if not args.path:
            parser.error('Privaten Prüfbericht mit --path angeben.')
        with os.fdopen(os.open(args.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid not in (0, os.geteuid())
                    or info.st_mode & 0o077 or not 0 < info.st_size <= 4 * 1024 * 1024):
                raise ValueError('Regulärer, privater und begrenzter Betreiber-Prüfbericht erforderlich.')
            data = stream.read(4 * 1024 * 1024 + 1)
            after = os.fstat(stream.fileno())
            if len(data) != info.st_size or (after.st_size, after.st_mtime_ns) != (info.st_size, info.st_mtime_ns):
                raise ValueError('Prüfbericht wurde während des Lesens verändert.')
        def unique(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError('Mehrdeutiger Prüfbericht.')
                value[key] = item
            return value
        evidence = json.loads(data, object_pairs_hook=unique,
                              parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Ungültiger Prüfbericht.')))
        admin = make_conninfo(target if args.candidate else active, user='postgres')
        no_other_clients(make_conninfo(active, user='postgres'))
        no_other_clients(admin)
        from business_schema import reconcile_financial_restore
        office = PostgresOffice(admin)
        try:
            result = reconcile_financial_restore(office, evidence, hashlib.sha256(data).hexdigest())
        finally:
            office.db.close()
        print(json.dumps(result, sort_keys=True))
    elif args.action == 'privacy-check':
        active = os.environ['SMARTPLAN_DATABASE_DSN']
        if not args.candidate or not NAME.fullmatch(args.candidate):
            parser.error('Getrennten Kandidaten angeben.')
        target = make_conninfo(active, dbname=args.candidate)
        validate_dsns(active, target)
        if os.geteuid() != pwd.getpwnam('smartplan-online').pw_uid:
            raise ValueError('Datenschutzprüfung ausschließlich als Runtime-Dienstkonto.')
        no_other_clients(active)
        from online.restore import complete_restore
        office = PostgresOffice(target, allow_restore_pending=True)
        try:
            with office.lock, office.db:
                complete_restore(office)
                # A restarted source writer must roll the target back to pending,
                # including the privacy replay, rather than publishing success.
                no_other_clients(active)
        finally:
            office.db.close()
        print('Kandidat datenschutzgeprüft und verifiziert; keine automatische Aktivierung.')
    elif args.action == 'security':
        secure_database(os.environ['SMARTPLAN_DATABASE_DSN'])
        print('Lokale Datenbankownership und Runtime-Rechte getrennt; keine Passwörter erstellt.')
    elif args.action == 'size':
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
            result = prepare(active, target, args.backup_directory,
                             privileged_operator=args.privileged_operator,
                             compatibility_mode=args.compatibility_mode)
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
