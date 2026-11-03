"""Explicit additive business migrations and a data-preserving compatibility mode.

This module performs no migration while reading state or constructing a domain
service. A downgrade changes active writers, never the canonical storage version
or business data. Registered modules are trusted packaged code, never DB input.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import tempfile
import uuid

from core import Problem


STORAGE_VERSION = 7
LEGACY_VERSION = 6
MODULE_NAMES = tuple('business_' + name for name in (
    'foundation', 'documents', 'finance', 'planning', 'time', 'operations',
    'inventory', 'maintenance', 'adapters', 'organization', 'instance', 'purchasing', 'portal', 'accounting',
    'accounting_allocations', 'accounting_components', 'accounting_refunds', 'accounting_capacity', 'accounting_refunds_v2', 'accounting_profile',
    'project_economics', 'asset_provenance', 'customer_workspace', 'personnel_workflow', 'accounting_euer', 'assistant', 'payroll', 'inventory_counts', 'sales', 'payroll_accounts', 'assistant_speech', 'company_handover', 'migrations', 'custom_fields', 'privacy_cases', 'payroll_cash', 'service', 'bank_reconciliation', 'resource_custody', 'purchase_changes'))
CONTROL_TABLES = frozenset((
    'business_schema_state', 'business_schema_migrations', 'business_schema_events',
    'business_feature_flags', 'business_privacy_anchors', 'business_device_grants', 'business_restore_state',
    'business_financial_reconciliations'))
_NAME = re.compile(r'[a-z][a-z0-9_]{1,79}\Z')
_FLAG = re.compile(r'[a-z][a-z0-9_.]{1,79}\Z')


@dataclass(frozen=True)
class ModuleSpec:
    name: str
    version: int
    loader: object


def registry():
    """Only packaged modules exist during parallel development; no fake caps.

    A previously installed module missing from the package always fails closed.
    Production release additionally requires the complete fixed module list.
    """
    return tuple(ModuleSpec(name, 1, lambda name=name: importlib.import_module(name))
                 for name in MODULE_NAMES if importlib.util.find_spec(name) is not None)


def require_complete_registry():
    found = {spec.name for spec in registry()}
    if found != set(MODULE_NAMES):
        raise RuntimeError('Business-Paket unvollständig; keine Migration oder Freigabe.')


def registered_table_names():
    """Trusted schema inventory, also used by genuine historical test fixtures."""
    names = set(CONTROL_TABLES)
    for spec in registry():
        for statement in spec.loader().schema_statements(binary_type='BYTEA'):
            match = re.match(r'\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-z][a-z0-9_]*)', statement, re.I)
            if match:
                names.add(match.group(1))
    return frozenset(names)


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA', 'BLOB'):
        raise ValueError('Unsupported binary storage type')
    return [
        '''CREATE TABLE IF NOT EXISTS business_schema_state(
          singleton INTEGER PRIMARY KEY CHECK(singleton=1), storage_version INTEGER NOT NULL CHECK(storage_version=7),
          compatibility_mode TEXT NOT NULL CHECK(compatibility_mode IN ('legacy','business')),
          generation INTEGER NOT NULL CHECK(generation>0), checksum TEXT NOT NULL CHECK(length(checksum)=64))''',
        '''CREATE TABLE IF NOT EXISTS business_schema_migrations(
          module TEXT NOT NULL, version INTEGER NOT NULL CHECK(version>0), checksum TEXT NOT NULL CHECK(length(checksum)=64),
          applied_at TEXT NOT NULL, PRIMARY KEY(module,version))''',
        '''CREATE TABLE IF NOT EXISTS business_schema_events(
          generation INTEGER PRIMARY KEY CHECK(generation>0), compatibility_mode TEXT NOT NULL
          CHECK(compatibility_mode IN ('legacy','business')), at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_feature_flags(
          name TEXT PRIMARY KEY, enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
          revision INTEGER NOT NULL CHECK(revision>0), updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_privacy_anchors(
          installation_id TEXT PRIMARY KEY CHECK(length(installation_id)=32),
          generation INTEGER NOT NULL CHECK(generation>=0), digest TEXT NOT NULL CHECK(length(digest)=64))''',
        '''CREATE TABLE IF NOT EXISTS business_device_grants(
          token_hash TEXT PRIMARY KEY REFERENCES plan_sessions(token) ON DELETE CASCADE,
          user_id TEXT NOT NULL REFERENCES users(id), capabilities_json TEXT NOT NULL,
          issued_at TEXT NOT NULL, expiry DOUBLE PRECISION NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_restore_state(
          singleton INTEGER PRIMARY KEY CHECK(singleton=1), pending INTEGER NOT NULL CHECK(pending IN (0,1)),
          financial_reconciliation_required INTEGER NOT NULL CHECK(financial_reconciliation_required IN (0,1)),
          restore_id TEXT CHECK(restore_id IS NULL OR length(restore_id)=32))''',
        '''CREATE TABLE IF NOT EXISTS business_financial_reconciliations(
          generation INTEGER PRIMARY KEY CHECK(generation>0), restore_id TEXT NOT NULL UNIQUE CHECK(length(restore_id)=32),
          evidence_sha256 TEXT NOT NULL CHECK(length(evidence_sha256)=64), operator_name TEXT NOT NULL,
          reviewed_by TEXT NOT NULL, at TEXT NOT NULL)''',
    ]


def _sqlite(office):
    return isinstance(office.db, sqlite3.Connection)


@contextmanager
def _transaction(office):
    with office.lock:
        if not _sqlite(office):
            with office.db:
                yield
            return
        name = 'business_schema_' + uuid.uuid4().hex
        office.db.execute('SAVEPOINT ' + name)
        try:
            yield
        except BaseException:
            office.db.execute('ROLLBACK TO SAVEPOINT ' + name)
            office.db.execute('RELEASE SAVEPOINT ' + name)
            raise
        else:
            office.db.execute('RELEASE SAVEPOINT ' + name)


def _tables(office):
    if _sqlite(office):
        return {row[0] for row in office.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    return {row[0] for row in office.db.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'").fetchall()}


def _specifications(provided):
    specs = tuple(registry() if provided is None else provided)
    names = set()
    for spec in specs:
        if (not isinstance(spec, ModuleSpec) or not _NAME.fullmatch(spec.name)
                or spec.name in names or type(spec.version) is not int or spec.version < 1
                or not callable(spec.loader)):
            raise ValueError('Invalid trusted business module registry')
        names.add(spec.name)
    return specs


def _definition(office, spec):
    module = spec.loader()
    statements = module.schema_statements(binary_type='BLOB' if _sqlite(office) else 'BYTEA')
    guards = getattr(module, 'guard_statements', None)
    guards = guards('sqlite' if _sqlite(office) else 'postgresql') if guards is not None else []
    if (not isinstance(statements, (tuple, list)) or not isinstance(guards, (tuple, list))
            or any(not isinstance(value, str) or not value.strip() for value in [*statements, *guards])):
        raise ValueError('Invalid business migration statements')
    checksum = hashlib.sha256(json.dumps(dict(name=spec.name, version=spec.version,
        schema=statements, guards=guards), sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return module, [*statements, *guards], checksum


def _legacy_state():
    return dict(storage_version=LEGACY_VERSION, compatibility_mode='legacy', generation=0,
                capabilities=[], read_capabilities=[], readonly=True, restore_pending=False,
                financial_reconciliation_required=False, restore_id=None)


def _control_checksum():
    return hashlib.sha256(_canonical(schema_statements())).hexdigest()


def state(office, *, registry=None):
    """Read and verify control metadata, without creating or repairing anything."""
    with office.lock:
        tables = _tables(office)
        if 'business_schema_state' not in tables:
            if tables & CONTROL_TABLES or any(name.startswith('business_') for name in tables):
                raise RuntimeError('Unvollständiges Business-Schema; explizite Prüfung erforderlich.')
            return _legacy_state()
        if not CONTROL_TABLES <= tables:
            raise RuntimeError('Unvollständiges Business-Schemajournal.')
        pending = office.db.execute('SELECT * FROM business_restore_state').fetchall()
        if (len(pending) != 1 or pending[0]['singleton'] != 1 or pending[0]['pending'] not in (0, 1)
                or pending[0]['financial_reconciliation_required'] not in (0, 1)
                or pending[0]['financial_reconciliation_required'] and not pending[0]['restore_id']):
            raise RuntimeError('Ungültiger Restore-Freigabestand.')
        restore_pending = pending[0]['pending'] == 1
        if restore_pending and not getattr(office, '_allow_restore_pending', False):
            raise RuntimeError('Wiederherstellung wartet auf geschützte Datenschutzprüfung; keine Freigabe.')
        rows = office.db.execute('SELECT * FROM business_schema_state').fetchall()
        if len(rows) != 1:
            raise RuntimeError('Mehrdeutiger Business-Schemastand.')
        row = rows[0]
        if (row['singleton'] != 1 or row['storage_version'] != STORAGE_VERSION
                or row['compatibility_mode'] not in ('legacy', 'business')
                or type(row['generation']) is not int or row['generation'] < 1
                or row['checksum'] != _control_checksum()):
            raise RuntimeError('Nicht unterstützter Business-Schemastand.')
        events = office.db.execute('SELECT * FROM business_schema_events ORDER BY generation').fetchall()
        if (len(events) != row['generation'] or any(item['generation'] != n + 1 for n, item in enumerate(events))
                or not events or events[-1]['compatibility_mode'] != row['compatibility_mode']):
            raise RuntimeError('Business-Kompatibilitätshistorie ungültig.')
        specs = _specifications(registry)
        installed = office.db.execute('SELECT * FROM business_schema_migrations ORDER BY module,version').fetchall()
        expected = {spec.name: spec for spec in specs}
        if len(installed) != len(specs) or {item['module'] for item in installed} != set(expected):
            raise RuntimeError('Business-Module fehlen oder benötigen eine explizite Migration.')
        for item in installed:
            spec = expected[item['module']]
            _, _, checksum = _definition(office, spec)
            if item['version'] != spec.version or item['checksum'] != checksum:
                raise RuntimeError('Business-Migrationsversion oder Checksumme weicht ab.')
        return dict(storage_version=STORAGE_VERSION, compatibility_mode=row['compatibility_mode'],
                    generation=row['generation'], capabilities=sorted(expected) if row['compatibility_mode'] == 'business' else [],
                    read_capabilities=sorted(expected), readonly=row['compatibility_mode'] != 'business',
                    restore_pending=restore_pending,
                    financial_reconciliation_required=pending[0]['financial_reconciliation_required'] == 1,
                    restore_id=pending[0]['restore_id'])


def _change_mode(office, mode):
    row = office.db.execute('SELECT * FROM business_schema_state').fetchone()
    if row['compatibility_mode'] == mode:
        return
    generation = row['generation'] + 1
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    office.db.execute('UPDATE business_schema_state SET compatibility_mode=?,generation=? WHERE singleton=1',
                      (mode, generation))
    office.db.execute('INSERT INTO business_schema_events(generation,compatibility_mode,at) VALUES(?,?,?)',
                      (generation, mode, stamp))
    if mode == 'legacy':
        # Returning to business mode never silently re-enables external effects.
        office.db.execute('UPDATE business_feature_flags SET enabled=0,revision=revision+1,updated_at=? WHERE enabled=1',
                          (stamp,))


def ensure_schema(office, *, registry=None, activate=True):
    """Explicit all-or-nothing additive up. Never call from an HTTP operation."""
    if type(activate) is not bool:
        raise ValueError('Explicit boolean activation required')
    specs = _specifications(registry)
    with _transaction(office):
        tables = _tables(office)
        present = 'business_schema_state' in tables
        if not present and (tables & CONTROL_TABLES or any(name.startswith('business_') for name in tables)):
            raise RuntimeError('Unbekanntes partielles Business-Schema nicht überschreiben.')
        if present:
            # Validate known prior modules before adding newly packaged modules.
            installed = office.db.execute('SELECT module,version,checksum FROM business_schema_migrations').fetchall()
            expected = {spec.name: spec for spec in specs}
            if any(item['module'] not in expected for item in installed):
                raise RuntimeError('Installierte Business-Module fehlen im Paket.')
            for item in installed:
                spec = expected[item['module']]
                if item['version'] != spec.version or _definition(office, spec)[2] != item['checksum']:
                    raise RuntimeError('Nicht unterstützte Business-Migrationsänderung.')
        else:
            for statement in schema_statements():
                office.db.execute(statement)
            office.db.execute('INSERT INTO business_restore_state(singleton,pending,financial_reconciliation_required,restore_id) VALUES(1,0,0,NULL)')
            stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
            initial_mode = 'business' if activate else 'legacy'
            office.db.execute('INSERT INTO business_schema_state(singleton,storage_version,compatibility_mode,generation,checksum) VALUES(1,?,?,1,?)',
                              (STORAGE_VERSION, initial_mode, _control_checksum()))
            office.db.execute('INSERT INTO business_schema_events(generation,compatibility_mode,at) VALUES(1,?,?)',
                              (initial_mode, stamp))
        for spec in specs:
            module, statements, checksum = _definition(office, spec)
            old = office.db.execute('SELECT checksum FROM business_schema_migrations WHERE module=? AND version=?',
                                    (spec.name, spec.version)).fetchone()
            if old is None:
                for statement in statements:
                    office.db.execute(statement)
                office.db.execute('INSERT INTO business_schema_migrations(module,version,checksum,applied_at) VALUES(?,?,?,?)',
                                  (spec.name, spec.version, checksum, datetime.now(timezone.utc).isoformat(timespec='seconds')))
            elif old['checksum'] != checksum:
                raise RuntimeError('Business-Migrationschecksumme weicht ab.')
            validator = getattr(module, 'validate_integrity', None)
            if validator is not None:
                validator(office)
        state(office, registry=specs)
        if activate:
            _change_mode(office, 'business')
        return state(office, registry=specs)


def ensure_sqlite_schema(office, *, registry=None):
    """Explicit SQLite Office-start migration; Postgres startup remains read-only."""
    if _sqlite(office):
        tables = _tables(office)
        row = (office.db.execute('SELECT compatibility_mode FROM business_schema_state').fetchone()
               if 'business_schema_state' in tables else None)
        return ensure_schema(office, registry=registry, activate=not row or row['compatibility_mode'] != 'legacy')


def validate_integrity(office, *, registry=None):
    specs = _specifications(registry)
    value = state(office, registry=specs)
    if value['storage_version'] == LEGACY_VERSION:
        return True
    for row in office.db.execute('SELECT * FROM business_device_grants').fetchall():
        try:
            caps = json.loads(row['capabilities_json'])
            issued = datetime.fromisoformat(row['issued_at'])
            session = office.db.execute('SELECT user_id,expiry FROM plan_sessions WHERE token=?', (row['token_hash'],)).fetchone()
            if (not re.fullmatch(r'[a-f0-9]{64}', row['token_hash']) or not isinstance(caps, list) or not caps
                    or any(not isinstance(cap, str) or cap not in ('time_events', 'field_media', 'offline_reports') for cap in caps)
                    or len(set(caps)) != len(caps) or issued.tzinfo is None
                    or type(row['expiry']) not in (int, float) or not math.isfinite(row['expiry'])
                    # ISO serialization can round sub-microsecond epoch values;
                    # the exact session expiry still bounds actual authority.
                    or not 0 < row['expiry'] - issued.timestamp() <= 7 * 24 * 3600 + 1
                    or not session or session['user_id'] != row['user_id'] or row['expiry'] > session['expiry']):
                raise ValueError('Invalid explicit business device grant')
        except (TypeError, KeyError, json.JSONDecodeError, OverflowError) as error:
            raise ValueError('Invalid explicit business device grant') from error
    for spec in specs:
        module, _, _ = _definition(office, spec)
        validator = getattr(module, 'validate_integrity', None)
        if validator is not None:
            validator(office)
    return True


def set_mode(office, mode, *, registry=None):
    if mode not in ('legacy', 'business'):
        raise ValueError('Unbekannter Business-Kompatibilitätsmodus.')
    if mode == 'business':
        return ensure_schema(office, registry=registry)
    with _transaction(office):
        value = state(office, registry=registry)
        if value['storage_version'] == LEGACY_VERSION:
            return value
        validate_integrity(office, registry=registry)
        _change_mode(office, mode)
        return state(office, registry=registry)


def require_capability(office, name):
    if name not in state(office)['capabilities']:
        raise Problem(409, 'Business-Funktion ist in diesem Kompatibilitätsstand nicht freigegeben.')


def require_financial_release(office):
    """Issuance/outbound after disaster recovery requires a fresh operator review."""
    with office.lock:
        if 'business_restore_state' in _tables(office):
            pending = office.db.execute('SELECT pending FROM business_restore_state WHERE singleton=1').fetchone()
            if pending and pending[0] == 1:
                raise Problem(409, 'Geschützte Datenschutzprüfung vor der Beleg- oder Versandfreigabe abschließen.')
    value = state(office)
    if value['storage_version'] != STORAGE_VERSION or value['restore_pending'] or value['financial_reconciliation_required']:
        raise Problem(409, 'Wiederhergestellte Nummern- und Versandstände zuerst durch den Betreiber abgleichen lassen.')
    return True


def feature_enabled(office, name):
    if not isinstance(name, str) or not _FLAG.fullmatch(name):
        return False
    if state(office)['compatibility_mode'] != 'business':
        return False
    row = office.db.execute('SELECT enabled FROM business_feature_flags WHERE name=?', (name,)).fetchone()
    return bool(row and row['enabled'] == 1)


def set_feature_flag(office, actor, name, enabled):
    if not isinstance(name, str) or not _FLAG.fullmatch(name) or type(enabled) is not bool:
        raise Problem(400, 'Ungültige Business-Freigabe.')
    from business_foundation import require_permission
    with _transaction(office):
        require_permission(office, actor, 'settings.manage')
        if state(office)['compatibility_mode'] != 'business':
            raise Problem(409, 'Business-Schreibfunktionen sind im Rückkehrmodus gesperrt.')
        old = office.db.execute('SELECT enabled FROM business_feature_flags WHERE name=?', (name,)).fetchone()
        if old is not None and old['enabled'] == int(enabled):
            return
        office.db.execute('INSERT INTO business_feature_flags(name,enabled,revision,updated_at) VALUES(?,?,1,?) '
                         'ON CONFLICT(name) DO UPDATE SET enabled=excluded.enabled,revision=business_feature_flags.revision+1,updated_at=excluded.updated_at',
                         (name, int(enabled), datetime.now(timezone.utc).isoformat(timespec='seconds')))


def require_runtime_security(office):
    """Fail closed for PostgreSQL issuance; SQLite cannot prove role separation."""
    if _sqlite(office):
        return False
    try:
        from online.instance_roles import for_office
        roles = for_office(office)
        row = office.db.execute('''SELECT current_user AS name,session_user AS session_name,r.rolsuper,r.rolcreatedb,r.rolcreaterole,
          r.rolreplication,r.rolbypassrls,d.datdba=r.oid AS owns_database,pg_get_userbyid(d.datdba) AS database_owner,
          has_database_privilege(current_user,current_database(),'CREATE') AS creates_database_objects,
          has_database_privilege(current_user,current_database(),'TEMP') AS creates_temporary_objects,
          has_schema_privilege(current_user,'public','CREATE') AS creates_schema_objects
          FROM pg_roles r JOIN pg_database d ON d.datname=current_database() WHERE r.rolname=current_user''').fetchone()
        if (not row or row['name'] != roles.runtime or row['session_name'] != roles.runtime
                or row['database_owner'] != roles.owner or any(row[name] for name in (
                'rolsuper', 'rolcreatedb', 'rolcreaterole', 'rolreplication', 'rolbypassrls',
                'owns_database', 'creates_database_objects', 'creates_temporary_objects', 'creates_schema_objects'))):
            raise ValueError('Unsafe runtime role')
        if office.db.execute("SELECT pg_has_role(current_user,?,'MEMBER')",(roles.owner,)).fetchone()[0]:
            raise ValueError('Runtime can assume migration ownership')
        if roles.slug is not None:
            from online.instance_roles import verify_database
            verify_database(office)
            if office.db.execute("SELECT 1 FROM pg_roles WHERE rolname<>current_user AND pg_has_role(current_user,oid,'MEMBER') LIMIT 1").fetchone():
                raise ValueError('Company runtime has an unexpected role membership')
            if office.db.execute("SELECT 1 FROM pg_roles WHERE rolname<>current_user AND NOT rolsuper AND rolcanlogin AND has_database_privilege(oid,current_database(),'CONNECT') LIMIT 1").fetchone():
                raise ValueError('A different runtime can connect to this company database')
            for other in office.db.execute("SELECT datname FROM pg_database WHERE datname NOT IN ('postgres','template0','template1') AND (left(datname,3)='sp_' OR pg_get_userbyid(datdba) IN ('smartplan-online','smartplan-migrator')) AND has_database_privilege(current_user,oid,'CONNECT')").fetchall():
                if not roles.owns_database_name(other['datname']):
                    raise ValueError('Company runtime can connect to a different company database')
        if office.db.execute("SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                             "WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S','f') AND pg_get_userbyid(c.relowner)<>? LIMIT 1",(roles.owner,)).fetchone():
            raise ValueError('Application relation has unexpected ownership')
        if office.db.execute("SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                             "WHERE n.nspname='public' AND pg_get_userbyid(p.proowner)<>? LIMIT 1",(roles.owner,)).fetchone():
            raise ValueError('Application function has unexpected ownership')
        policy = runtime_privileges()
        for permissions in office.db.execute("""SELECT tablename,
          has_any_column_privilege(current_user,'public.'||quote_ident(tablename),'INSERT') AS may_insert,
          has_any_column_privilege(current_user,'public.'||quote_ident(tablename),'UPDATE') AS may_update,
          has_table_privilege(current_user,'public.'||quote_ident(tablename),'DELETE') AS may_delete,
          has_table_privilege(current_user,'public.'||quote_ident(tablename),'TRUNCATE') AS may_truncate
          FROM pg_tables WHERE schemaname='public'""").fetchall():
            name = permissions['tablename']
            allowed = policy.get(name, ('SELECT', 'INSERT', 'UPDATE', 'DELETE'))
            if permissions['may_truncate']:
                raise ValueError('Runtime can truncate application data')
            for privilege in ('INSERT', 'UPDATE', 'DELETE'):
                if name == 'business_restore_state' and privilege == 'UPDATE':
                    continue  # Only pending may be updated; prove columns below.
                if privilege not in allowed and permissions['may_' + privilege.lower()]:
                    raise ValueError('Unexpected destructive runtime grant')
        for column in ('singleton', 'financial_reconciliation_required', 'restore_id'):
            if office.db.execute("SELECT has_column_privilege(current_user,'business_restore_state',?,'UPDATE')", (column,)).fetchone()[0]:
                raise ValueError('Runtime can approve its own restore')
    except Exception as error:
        raise Problem(409, 'Sichere PostgreSQL-Rollentrennung ist vor der Belegausstellung erforderlich.') from None
    return True


def runtime_privileges():
    result = {name: ('SELECT',) for name in CONTROL_TABLES}
    result['audit'] = ('SELECT', 'INSERT')
    result['business_feature_flags'] = ('SELECT', 'INSERT', 'UPDATE')
    result['business_privacy_anchors'] = ('SELECT', 'INSERT', 'UPDATE')
    result['business_device_grants'] = ('SELECT', 'INSERT')
    result['business_restore_state'] = ('SELECT',)
    for spec in registry():
        module = spec.loader()
        protected = getattr(module, 'protected_tables', lambda: ())()
        for table in protected:
            if not _NAME.fullmatch(table) or not table.startswith('business_'):
                raise ValueError('Invalid protected business table')
            result[table] = ('SELECT', 'INSERT')
        explicit = getattr(module, 'runtime_privileges', lambda: {})()
        for table, privileges in explicit.items():
            if (not _NAME.fullmatch(table) or not table.startswith('business_')
                    or not isinstance(privileges, (tuple, list))
                    or set(privileges) - {'SELECT', 'INSERT', 'UPDATE', 'DELETE'}):
                raise ValueError('Invalid explicit runtime table privileges')
            if table in protected and set(privileges) - {'SELECT', 'INSERT'}:
                raise ValueError('Protected table cannot grant destructive runtime privileges')
            result[table] = tuple(privileges)
    return result


def apply_runtime_privileges(office):
    """Trusted operator only; ordinary service connections cannot grant ownership."""
    if _sqlite(office):
        raise ValueError('PostgreSQL operator required')
    from psycopg import sql
    from online.instance_roles import for_office
    runtime = sql.Identifier(for_office(office).runtime)
    connection = getattr(office.db, 'connection', office.db)
    actual = _tables(office)
    policy = runtime_privileges()
    database = connection.execute('SELECT current_database()').fetchone()[0]
    connection.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC,{}').format(sql.Identifier(database),runtime))
    connection.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(database),runtime))
    connection.execute(sql.SQL('REVOKE ALL ON SCHEMA public FROM PUBLIC,{}').format(runtime))
    connection.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(runtime))
    for table in sorted(actual):
        if not _NAME.fullmatch(table):
            raise ValueError('Unexpected application table name')
        connection.execute(sql.SQL('REVOKE ALL ON TABLE public.{} FROM PUBLIC,{}').format(sql.Identifier(table),runtime))
        columns = [row[0] for row in connection.execute(
            "SELECT a.attname FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' "
            "AND c.relname=%s AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum", (table,)).fetchall()]
        if columns:
            # Table REVOKE does not remove earlier column-specific grants.
            connection.execute(sql.SQL('REVOKE ALL ({}) ON TABLE public.{} FROM PUBLIC,{}').format(
                sql.SQL(',').join(map(sql.Identifier, columns)), sql.Identifier(table),runtime))
        privileges = policy.get(table, ('SELECT', 'INSERT', 'UPDATE', 'DELETE'))
        if privileges:
            connection.execute(sql.SQL('GRANT {} ON TABLE public.{} TO {}').format(
                sql.SQL(','.join(privileges)), sql.Identifier(table),runtime))
    if 'business_restore_state' in actual:
        # The runtime verifier can clear privacy pending only, never approve
        # financial reconciliation or rewrite the restore identity.
        connection.execute(sql.SQL('GRANT UPDATE(pending) ON business_restore_state TO {}').format(runtime))
    connection.execute(sql.SQL('GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {}').format(runtime))


def financial_accounting_horizon(office):
    """Read the installed financial scope without rewriting E1a's version-1 proof.

    The caller owns a consistent snapshot/transaction. No actor, migration,
    commit, dynamically computed open-item amount or approval is created here.
    """
    with office.lock:
        installed = state(office).get('read_capabilities', [])
        accounting = 'business_accounting' in installed
        allocations = 'business_accounting_allocations' in installed
        components = 'business_accounting_components' in installed
        refunds = 'business_accounting_refunds' in installed
        capacity = 'business_accounting_capacity' in installed
        refunds_v2 = 'business_accounting_refunds_v2' in installed
        profile = 'business_accounting_profile' in installed
        euer = 'business_accounting_euer' in installed
        payroll_cash = 'business_payroll_cash' in installed
        bank_reconciliation = 'business_bank_reconciliation' in installed
        if bank_reconciliation and not payroll_cash:
            raise ValueError('Bank reconciliation requires the complete installed financial schema')
        if payroll_cash and not euer:
            raise ValueError('Payroll cash sources require the installed EÜR journal')
        if euer and not profile:
            raise ValueError('EÜR journal requires the installed accounting profile')
        if profile and not (accounting and allocations and components and refunds and capacity and refunds_v2):
            raise ValueError('Accounting preparation profile requires the complete installed financial scope')
        if refunds_v2 and not (accounting and allocations and components and refunds and capacity):
            raise ValueError('Versioned refund origins require the complete prejournal, allocations, components, refund origins and capacity')
        if capacity and not (accounting and allocations and components and refunds):
            raise ValueError('Component reuse requires the installed prejournal, allocations, components and refund origins')
        if refunds and not (accounting and allocations and components):
            raise ValueError('Refund origins require the installed prejournal, allocations and components')
        if components and not (accounting and allocations):
            raise ValueError('Document components require the installed prejournal and payment allocations')
        if allocations and not accounting:
            raise ValueError('Payment allocations require the installed accounting prejournal')
        if not accounting:
            return None
        from business_accounting import restore_horizon
        prejournal = restore_horizon(office)
        if prejournal is None:
            raise ValueError('Installed accounting horizon is missing')
        if not allocations:
            return prejournal
        from business_accounting_allocations import restore_horizon as allocation_horizon
        extra = allocation_horizon(office)
        if extra is None:
            raise ValueError('Installed allocation horizon is missing')
        horizon = dict(schema_version=2, prejournal=prejournal, allocations=extra)
        if not components:
            return horizon
        from business_accounting_components import restore_horizon as component_horizon
        documented = component_horizon(office)
        if documented is None:
            raise ValueError('Installed document component horizon is missing')
        horizon = dict(horizon, schema_version=3, components=documented)
        if not refunds:
            return horizon
        from business_accounting_refunds import restore_horizon as refund_horizon
        returned = refund_horizon(office)
        if returned is None:
            raise ValueError('Installed refund origin horizon is missing')
        horizon = dict(horizon, schema_version=4, refunds=returned)
        if not capacity:
            return horizon
        from business_accounting_capacity import restore_horizon as capacity_horizon
        # The coupled C2/R2 streams share only this read's verified snapshot.
        joint_cache = {} if refunds_v2 else None
        reused = capacity_horizon(office, cache=joint_cache) if refunds_v2 else capacity_horizon(office)
        if reused is None:
            raise ValueError('Installed component reuse horizon is missing')
        horizon = dict(horizon, schema_version=5, capacity=reused)
        if not refunds_v2:
            return horizon
        from business_accounting_refunds_v2 import restore_horizon as versioned_refund_horizon
        versioned_returns = versioned_refund_horizon(office, cache=joint_cache)
        if versioned_returns is None:
            raise ValueError('Installed versioned refund origin horizon is missing')
        horizon = dict(horizon, schema_version=6, refunds_v2=versioned_returns)
        if not profile:
            return horizon
        from business_accounting_profile import restore_horizon as profile_horizon
        preparation = profile_horizon(office)
        if preparation is None:
            raise ValueError('Installed accounting preparation profile horizon is missing')
        horizon = dict(horizon, schema_version=7, profile=preparation)
        if not euer:
            return horizon
        from business_accounting_euer import restore_horizon as euer_horizon
        journal = euer_horizon(office)
        if journal is None:
            raise ValueError('Installed EÜR journal horizon is missing')
        horizon = dict(horizon, schema_version=8, euer=journal)
        if not payroll_cash:
            return horizon
        from business_payroll_cash import restore_horizon as payroll_cash_horizon
        wage_payments = payroll_cash_horizon(office)
        if wage_payments is None:
            raise ValueError('Installed payroll cash horizon is missing')
        horizon = dict(horizon, schema_version=9, payroll_cash=wage_payments)
        if not bank_reconciliation:
            return horizon
        from business_bank_reconciliation import restore_horizon as bank_horizon
        bank = bank_horizon(office)
        if bank is None:
            raise ValueError('Installed bank reconciliation horizon is missing')
        return dict(horizon, schema_version=10, bank_reconciliation=bank)


def _validate_prejournal_horizon(horizon):
    counts = {'accounts_count', 'account_versions_count', 'cash_events_count', 'source_links_count', 'max_sequence'}
    if (not isinstance(horizon, dict) or set(horizon) != counts | {'schema_version', 'sha256'}
            or type(horizon['schema_version']) is not int or horizon['schema_version'] != 1
            or any(type(horizon[key]) is not int or horizon[key] < 0 for key in counts)
            or not isinstance(horizon['sha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', horizon['sha256'])):
        raise ValueError('Exact version-1 accounting prejournal horizon required')


def _validate_financial_accounting_horizon(horizon, report_schema):
    if report_schema == 2:
        _validate_prejournal_horizon(horizon)
        return
    if report_schema == 11:
        if (not isinstance(horizon, dict) or set(horizon) != {'schema_version', 'prejournal', 'allocations', 'components', 'refunds', 'capacity', 'refunds_v2', 'profile', 'euer', 'payroll_cash', 'bank_reconciliation'}
                or type(horizon['schema_version']) is not int or horizon['schema_version'] != 10):
            raise ValueError('Exact version-10 combined accounting horizon required')
        previous = {key: value for key, value in horizon.items() if key != 'bank_reconciliation'}
        previous['schema_version'] = 9
        _validate_financial_accounting_horizon(previous, 10)
        bank_tables = {'business_bank_account_versions', 'business_bank_statements', 'business_bank_transactions',
                       'business_bank_statement_lines', 'business_bank_match_events', 'business_bank_reconciliations', 'business_bank_requests'}
        bank = horizon['bank_reconciliation']
        if (not isinstance(bank, dict) or set(bank) != {'schema_version', 'table_counts', 'sha256'}
                or type(bank['schema_version']) is not int or bank['schema_version'] != 1
                or not isinstance(bank['table_counts'], dict) or set(bank['table_counts']) != bank_tables
                or any(type(value) is not int or value < 0 for value in bank['table_counts'].values())
                or not isinstance(bank['sha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', bank['sha256'])):
            raise ValueError('Exact version-1 bank reconciliation horizon required')
        return
    if report_schema == 10:
        if (not isinstance(horizon, dict) or set(horizon) != {'schema_version', 'prejournal', 'allocations', 'components', 'refunds', 'capacity', 'refunds_v2', 'profile', 'euer', 'payroll_cash'}
                or type(horizon['schema_version']) is not int or horizon['schema_version'] != 9):
            raise ValueError('Exact version-9 combined accounting horizon required')
        previous = {key: value for key, value in horizon.items() if key != 'payroll_cash'}
        previous['schema_version'] = 8
        _validate_financial_accounting_horizon(previous, 9)
        # Keep this exact scope when future payroll or accounting modules grow.
        payroll_cash_tables = {'business_payroll_cash_batches', 'business_payroll_cash_evidence',
                               'business_payroll_cash_parts', 'business_payroll_cash_requests'}
        cash = horizon['payroll_cash']
        if (not isinstance(cash, dict) or set(cash) != {'schema_version', 'table_counts', 'sha256'}
                or type(cash['schema_version']) is not int or cash['schema_version'] != 1
                or not isinstance(cash['table_counts'], dict) or set(cash['table_counts']) != payroll_cash_tables
                or any(type(value) is not int or value < 0 for value in cash['table_counts'].values())
                or not isinstance(cash['sha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', cash['sha256'])):
            raise ValueError('Exact version-1 payroll cash horizon required')
        return
    if report_schema == 9:
        if (not isinstance(horizon, dict) or set(horizon) != {'schema_version', 'prejournal', 'allocations', 'components', 'refunds', 'capacity', 'refunds_v2', 'profile', 'euer'}
                or type(horizon['schema_version']) is not int or horizon['schema_version'] != 8):
            raise ValueError('Exact version-8 combined accounting horizon required')
        previous = {key: value for key, value in horizon.items() if key != 'euer'}
        previous['schema_version'] = 7
        _validate_financial_accounting_horizon(previous, 8)
        journal = horizon['euer']
        if (not isinstance(journal, dict) or set(journal) != {'schema_version', 'table_counts', 'sha256'}
                or type(journal['schema_version']) is not int or journal['schema_version'] != 1
                or not isinstance(journal['table_counts'], dict)
                or set(journal['table_counts']) != {'business_euer_entries', 'business_euer_requests'}
                or any(type(value) is not int or value < 0 for value in journal['table_counts'].values())
                or not isinstance(journal['sha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', journal['sha256'])):
            raise ValueError('Exact version-1 EÜR journal horizon required')
        return
    if report_schema == 8:
        if (not isinstance(horizon, dict) or set(horizon) != {'schema_version', 'prejournal', 'allocations', 'components', 'refunds', 'capacity', 'refunds_v2', 'profile'}
                or type(horizon['schema_version']) is not int or horizon['schema_version'] != 7):
            raise ValueError('Exact version-7 combined accounting horizon required')
        _validate_financial_accounting_horizon(dict(schema_version=6, prejournal=horizon['prejournal'],
            allocations=horizon['allocations'], components=horizon['components'], refunds=horizon['refunds'],
            capacity=horizon['capacity'], refunds_v2=horizon['refunds_v2']), 7)
        # This schema-8 inventory is fixed independently of future modules.
        profile_tables = {'business_accounting_profile_versions', 'business_accounting_profile_requests'}
        preparation = horizon['profile']
        if (not isinstance(preparation, dict) or set(preparation) != {'schema_version', 'table_counts', 'sha256'}
                or type(preparation['schema_version']) is not int or preparation['schema_version'] != 1
                or not isinstance(preparation['table_counts'], dict) or set(preparation['table_counts']) != profile_tables
                or any(type(value) is not int or value < 0 for value in preparation['table_counts'].values())
                or not isinstance(preparation['sha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', preparation['sha256'])):
            raise ValueError('Exact version-1 accounting preparation profile horizon required')
        return
    if report_schema == 7:
        if (not isinstance(horizon, dict) or set(horizon) != {'schema_version', 'prejournal', 'allocations', 'components', 'refunds', 'capacity', 'refunds_v2'}
                or type(horizon['schema_version']) is not int or horizon['schema_version'] != 6):
            raise ValueError('Exact version-6 combined accounting horizon required')
        _validate_financial_accounting_horizon(dict(schema_version=5, prejournal=horizon['prejournal'],
            allocations=horizon['allocations'], components=horizon['components'], refunds=horizon['refunds'],
            capacity=horizon['capacity']), 6)
        # This schema-7 inventory is fixed independently of future module versions.
        refund_tables_v2 = {'business_accounting_refunds_v2_handoffs', 'business_accounting_refunds_v2_entries',
                            'business_accounting_refunds_v2_lines', 'business_accounting_refunds_v2_requests',
                            'business_accounting_refunds_v2_releases'}
        returned = horizon['refunds_v2']
        if (not isinstance(returned, dict) or set(returned) != {'schema_version', 'table_counts', 'sha256'}
                or type(returned['schema_version']) is not int or returned['schema_version'] != 1
                or not isinstance(returned['table_counts'], dict) or set(returned['table_counts']) != refund_tables_v2
                or any(type(value) is not int or value < 0 for value in returned['table_counts'].values())
                or not isinstance(returned['sha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', returned['sha256'])):
            raise ValueError('Exact version-1 versioned refund origin horizon required')
        return
    if report_schema == 6:
        if (not isinstance(horizon, dict) or set(horizon) != {'schema_version', 'prejournal', 'allocations', 'components', 'refunds', 'capacity'}
                or type(horizon['schema_version']) is not int or horizon['schema_version'] != 5):
            raise ValueError('Exact version-5 combined accounting horizon required')
        _validate_financial_accounting_horizon(dict(schema_version=4, prejournal=horizon['prejournal'],
            allocations=horizon['allocations'], components=horizon['components'], refunds=horizon['refunds']), 5)
        # Freeze the schema-6 scope so later modules cannot reinterpret its receipt.
        capacity_tables = {'business_accounting_capacity_handoffs', 'business_accounting_capacity_segments',
                           'business_accounting_capacity_releases', 'business_accounting_capacity_entries',
                           'business_accounting_capacity_lines', 'business_accounting_capacity_requests'}
        reused = horizon['capacity']
        if (not isinstance(reused, dict) or set(reused) != {'schema_version', 'table_counts', 'sha256'}
                or type(reused['schema_version']) is not int or reused['schema_version'] != 1
                or not isinstance(reused['table_counts'], dict) or set(reused['table_counts']) != capacity_tables
                or any(type(value) is not int or value < 0 for value in reused['table_counts'].values())
                or not isinstance(reused['sha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', reused['sha256'])):
            raise ValueError('Exact version-1 component reuse horizon required')
        return
    if report_schema == 5:
        if (not isinstance(horizon, dict) or set(horizon) != {'schema_version', 'prejournal', 'allocations', 'components', 'refunds'}
                or type(horizon['schema_version']) is not int or horizon['schema_version'] != 4):
            raise ValueError('Exact version-4 combined accounting horizon required')
        _validate_financial_accounting_horizon(dict(schema_version=3, prejournal=horizon['prejournal'],
            allocations=horizon['allocations'], components=horizon['components']), 4)
        # Historical schema-5 receipts keep this exact inventory in future releases.
        refund_tables = {'business_accounting_refund_entries', 'business_accounting_refund_lines',
                         'business_accounting_refund_requests'}
        returned = horizon['refunds']
        if (not isinstance(returned, dict) or set(returned) != {'schema_version', 'table_counts', 'sha256'}
                or type(returned['schema_version']) is not int or returned['schema_version'] != 1
                or not isinstance(returned['table_counts'], dict) or set(returned['table_counts']) != refund_tables
                or any(type(value) is not int or value < 0 for value in returned['table_counts'].values())
                or not isinstance(returned['sha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', returned['sha256'])):
            raise ValueError('Exact version-1 refund origin horizon required')
        return
    if report_schema == 4:
        if (not isinstance(horizon, dict) or set(horizon) != {'schema_version', 'prejournal', 'allocations', 'components'}
                or type(horizon['schema_version']) is not int or horizon['schema_version'] != 3):
            raise ValueError('Exact version-3 combined accounting horizon required')
        _validate_financial_accounting_horizon(dict(schema_version=2,
            prejournal=horizon['prejournal'], allocations=horizon['allocations']), 3)
        # This schema-4 inventory is fixed, independently of future modules.
        component_tables = {'business_accounting_component_entries', 'business_accounting_component_lines',
                            'business_accounting_component_requests'}
        documented = horizon['components']
        if (not isinstance(documented, dict) or set(documented) != {'schema_version', 'table_counts', 'sha256'}
                or type(documented['schema_version']) is not int or documented['schema_version'] != 1
                or not isinstance(documented['table_counts'], dict) or set(documented['table_counts']) != component_tables
                or any(type(value) is not int or value < 0 for value in documented['table_counts'].values())
                or not isinstance(documented['sha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', documented['sha256'])):
            raise ValueError('Exact version-1 document component horizon required')
        return
    if (not isinstance(horizon, dict) or set(horizon) != {'schema_version', 'prejournal', 'allocations'}
            or type(horizon['schema_version']) is not int or horizon['schema_version'] != 2):
        raise ValueError('Exact version-2 combined accounting horizon required')
    _validate_prejournal_horizon(horizon['prejournal'])
    # Freeze the declared schema-3 contract independently of future module
    # inventory changes. Parsing an old receipt never loads/migrates a module.
    allocation_tables = {'business_accounting_allocation_entries', 'business_accounting_allocation_requests'}
    extra = horizon['allocations']
    if (not isinstance(extra, dict) or set(extra) != {'schema_version', 'table_counts', 'sha256'}
            or type(extra['schema_version']) is not int or extra['schema_version'] != 1
            or not isinstance(extra['table_counts'], dict) or set(extra['table_counts']) != allocation_tables
            or any(type(value) is not int or value < 0 for value in extra['table_counts'].values())
            or not isinstance(extra['sha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', extra['sha256'])):
        raise ValueError('Exact version-1 additional allocation horizon required')


def _reconcile_financial_report(office, evidence, evidence_sha256, operator_name):
    """Common validation inside an already authorized exclusive transaction.

    The caller hashes the actual report bytes. External payment/source review
    remains an explicit operator attestation, not an inference from DB hashes.
    This helper grants no actor identity and is not an HTTP operation.
    """
    if not isinstance(evidence_sha256, str) or not re.fullmatch(r'[a-f0-9]{64}', evidence_sha256):
        raise ValueError('Valid evidence hash required')
    value = state(office)
    if value['restore_pending']:
        raise Problem(409, 'Datenschutzprüfung vor Finanzfreigabe abschließen.')
    accounting_installed = 'business_accounting' in value.get('read_capabilities', [])
    allocations_installed = 'business_accounting_allocations' in value.get('read_capabilities', [])
    components_installed = 'business_accounting_components' in value.get('read_capabilities', [])
    refunds_installed = 'business_accounting_refunds' in value.get('read_capabilities', [])
    capacity_installed = 'business_accounting_capacity' in value.get('read_capabilities', [])
    refunds_v2_installed = 'business_accounting_refunds_v2' in value.get('read_capabilities', [])
    profile_installed = 'business_accounting_profile' in value.get('read_capabilities', [])
    euer_installed = 'business_accounting_euer' in value.get('read_capabilities', [])
    payroll_cash_installed = 'business_payroll_cash' in value.get('read_capabilities', [])
    bank_installed = 'business_bank_reconciliation' in value.get('read_capabilities', [])
    if bank_installed and not payroll_cash_installed:
        raise ValueError('Bank reconciliation requires the complete installed financial schema')
    if payroll_cash_installed and not euer_installed:
        raise ValueError('Payroll cash sources require the installed EÜR journal')
    if euer_installed and not profile_installed:
        raise ValueError('EÜR journal requires the installed accounting profile')
    if profile_installed and not (accounting_installed and allocations_installed and components_installed and refunds_installed and capacity_installed and refunds_v2_installed):
        raise ValueError('Accounting preparation profile requires the complete installed financial scope')
    if refunds_v2_installed and not (accounting_installed and allocations_installed and components_installed and refunds_installed and capacity_installed):
        raise ValueError('Versioned refund origins require the complete prejournal, allocations, components, refund origins and capacity')
    if capacity_installed and not (accounting_installed and allocations_installed and components_installed and refunds_installed):
        raise ValueError('Component reuse requires the installed prejournal, allocations, components and refund origins')
    if refunds_installed and not (accounting_installed and allocations_installed and components_installed):
        raise ValueError('Refund origins require the installed prejournal, allocations and components')
    if components_installed and not (accounting_installed and allocations_installed):
        raise ValueError('Document components require the installed prejournal and payment allocations')
    if allocations_installed and not accounting_installed:
        raise ValueError('Payment allocations require the installed accounting prejournal')
    required_schema = 11 if bank_installed else 10 if payroll_cash_installed else 9 if euer_installed else 8 if profile_installed else 7 if refunds_v2_installed else 6 if capacity_installed else 5 if refunds_installed else 4 if components_installed else 3 if allocations_installed else 2 if accounting_installed else 1
    declared_schema = evidence.get('schema') if isinstance(evidence, dict) else None
    if type(declared_schema) is not int or declared_schema not in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11):
        raise ValueError('Known explicit financial report schema required')
    fields = {'schema', 'restore_id', 'reviewed_by', 'reviewed_at', 'number_horizons', 'outbound_reconciled'}
    if declared_schema >= 2:
        fields |= {'accounting_horizon', 'accounting_reconciled', 'accounting_external_review'}
    if (not isinstance(evidence, dict) or set(evidence) != fields
            or evidence['restore_id'] != value['restore_id'] or evidence['outbound_reconciled'] is not True
            or not isinstance(evidence['reviewed_by'], str) or not 1 <= len(evidence['reviewed_by'].strip()) <= 200):
        raise ValueError('Review report must bind this restore, reviewer and all required financial scopes')
    try:
        reviewed = datetime.fromisoformat(evidence['reviewed_at'])
    except (TypeError, ValueError):
        raise ValueError('Valid review timestamp required') from None
    if reviewed.tzinfo is None or reviewed.timestamp() > datetime.now(timezone.utc).timestamp() + 300:
        raise ValueError('Valid review timestamp required')
    horizons = evidence['number_horizons']
    if not isinstance(horizons, list) or len(horizons) > 10000:
        raise ValueError('Bounded reviewed number horizons required')
    supplied = {}
    for item in horizons:
        if (not isinstance(item, dict) or set(item) != {'company_id', 'series', 'year', 'last_value'}
                or not isinstance(item['company_id'], str) or not isinstance(item['series'], str)
                or type(item['year']) is not int or type(item['last_value']) is not int or item['last_value'] < 0):
            raise ValueError('Invalid reviewed number horizon')
        key = item['company_id'], item['series'], item['year']
        if key in supplied:
            raise ValueError('Duplicate reviewed number horizon')
        supplied[key] = item['last_value']
    if declared_schema >= 2:
        _validate_financial_accounting_horizon(evidence['accounting_horizon'], declared_schema)
        external = evidence['accounting_external_review']
        if (evidence['accounting_reconciled'] is not True
                or not isinstance(external, dict) or set(external) != {'reviewed_since_backup', 'evidence_sha256', 'note'}
                or external['reviewed_since_backup'] is not True
                or not isinstance(external['evidence_sha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', external['evidence_sha256'])
                or not isinstance(external['note'], str) or not 1 <= len(external['note'].strip()) <= 2000):
            raise ValueError('Reviewed accounting horizon and independent source/payment evidence required')
    previous = office.db.execute('SELECT * FROM business_financial_reconciliations WHERE restore_id=?', (value['restore_id'],)).fetchone()
    if not value['financial_reconciliation_required']:
        if previous and previous['evidence_sha256'] == evidence_sha256:
            # A previously committed report remains the same receipt even if
            # legitimate new financial events followed its successful release.
            return {'reconciled': True, 'generation': previous['generation']}
        raise Problem(409, 'Keine offene Finanzfreigabe oder abweichender bereits bestätigter Nachweis.')
    if previous:
        raise Problem(409, 'Restore-Identität wurde bereits finanziell freigegeben.')
    if declared_schema != required_schema:
        raise ValueError('New financial reconciliation requires the complete installed report scope')
    expected = {(row['company_id'], row['series'], row['year']): row['next_value'] - 1
                for row in office.db.execute('SELECT * FROM business_document_counters').fetchall()}
    if supplied != expected:
        raise Problem(409, 'Ausgestellte Nummern fehlen oder sind nicht vollständig abgeglichen; Originalbelege zuerst wiederherstellen.')
    if accounting_installed:
        if evidence['accounting_horizon'] != financial_accounting_horizon(office):
            raise Problem(409, 'Wiederhergestellte Geldfluss- und Quellenstände sind nicht vollständig abgeglichen.')
    validate_integrity(office)
    generation = office.db.execute('SELECT COALESCE(MAX(generation),0)+1 FROM business_financial_reconciliations').fetchone()[0]
    office.db.execute('INSERT INTO business_financial_reconciliations(generation,restore_id,evidence_sha256,operator_name,reviewed_by,at) VALUES(?,?,?,?,?,?)',
                     (generation, value['restore_id'], evidence_sha256, operator_name, evidence['reviewed_by'].strip(), reviewed.isoformat()))
    office.db.execute('UPDATE business_restore_state SET financial_reconciliation_required=0 WHERE singleton=1')
    return {'reconciled': True, 'generation': generation}


def reconcile_financial_restore(office, evidence, evidence_sha256):
    """PostgreSQL operator only; never changes archives, counters or cash events."""
    if _sqlite(office):
        raise Problem(409, 'Finanzabgleich benötigt den geschützten PostgreSQL-Operatorpfad.')
    with _transaction(office):
        from online.instance_roles import for_office
        roles = for_office(office)
        who = office.db.execute('SELECT current_user AS current_name,session_user AS session_name').fetchone()
        if who['session_name'] != 'postgres' or who['current_name'] not in ('postgres', roles.owner):
            raise Problem(403, 'Finanzabgleich ausschließlich durch den Datenbankbetreiber.')
        clients = office.db.execute("SELECT COUNT(*) FROM pg_stat_activity WHERE datname=current_database() AND backend_type='client backend' AND pid<>pg_backend_pid()").fetchone()[0]
        if clients:
            raise Problem(409, 'Finanzabgleich benötigt vollständig gestoppte Datenbanknutzer.')
        return _reconcile_financial_report(office, evidence, evidence_sha256, who['session_name'])


def reconcile_local_financial_restore(office, evidence, evidence_sha256, *, application_stopped=False):
    """Explicit local OS-operator path, separate from ordinary application APIs.

    BEGIN EXCLUSIVE serializes writers. In WAL mode readers may remain; the
    required stopped-application attestation is not a process-discovery claim.
    The caller opens an existing SQLite file directly, without Office/migration.
    """
    if not _sqlite(office) or application_stopped is not True:
        raise Problem(409, 'Lokale SQLite-Datei und ausdrücklich bestätigter vollständiger App-/Serverstopp erforderlich.')
    with office.lock:
        if office.db.in_transaction:
            raise Problem(409, 'Lokaler Finanzabgleich benötigt eine eigene exklusive Transaktion.')
        operator_name = 'sqlite-local-uid:' + str(os.geteuid()) if hasattr(os, 'geteuid') else 'sqlite-local-os-operator'
        try:
            office.db.execute('BEGIN EXCLUSIVE')
            result = _reconcile_financial_report(office, evidence, evidence_sha256, operator_name)
            office.db.commit()
            return result
        except BaseException:
            office.db.rollback()
            raise


_PRIVACY_VARIABLES = ('SMARTPLAN_PRIVACY_CHECKPOINT_FILE', 'SMARTPLAN_PRIVACY_CHECKPOINT_KEY_FILE',
                      'SMARTPLAN_PRIVACY_INSTALLATION_ID')
_PRIVACY_OPERATIONS = {'anonymize_customer': 'customer', 'purge_time_locations': 'time_day',
    'purge_privacy_case': 'privacy_case', 'purge_privacy_export': 'privacy_export'}
_PRIVACY_MAX_BYTES = 8 * 1024 * 1024


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _privacy_config():
    values = [os.environ.get(name) for name in _PRIVACY_VARIABLES]
    if not all(values) or not re.fullmatch(r'[a-f0-9]{32}', values[2] or ''):
        raise Problem(409, 'Unabhängiger Datenschutz-Checkpoint ist nicht sicher eingerichtet.')
    if os.name != 'posix':
        raise Problem(409, 'Datenschutz-Checkpoint benötigt den geschützten Serverpfad.')
    target, key_path = Path(values[0]), Path(values[1])
    if not target.is_absolute() or not key_path.is_absolute():
        raise Problem(409, 'Datenschutz-Checkpoint benötigt den geschützten Serverpfad.')
    for path in (target, key_path):
        for parent in (path.parent, *path.parent.parents):
            if parent.is_symlink():
                raise Problem(409, 'Unsicherer Datenschutz-Checkpoint-Pfad.')
    info = target.parent.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise Problem(409, 'Datenschutz-Checkpoint-Verzeichnis ist nicht privat.')
    descriptor = os.open(key_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077 or info.st_size != 32:
            raise Problem(409, 'Datenschutz-Checkpoint-Schlüssel ist nicht sicher eingerichtet.')
        key = os.read(descriptor, 33)
    finally:
        os.close(descriptor)
    if len(key) != 32:
        raise Problem(409, 'Datenschutz-Checkpoint-Schlüssel ist ungültig.')
    return target, key, values[2]


def privacy_subject_hash(kind, identifier=None):
    # Customer-only shorthand retained for the early Foundation caller contract.
    if identifier is None:
        kind, identifier = 'customer', kind
    if kind not in _PRIVACY_OPERATIONS.values() or not isinstance(identifier, str) or not 1 <= len(identifier) <= 100:
        raise ValueError('Invalid privacy subject')
    _, key, installation = _privacy_config()
    return hmac.new(key, _canonical([installation, kind, identifier]), hashlib.sha256).hexdigest()


def _privacy_empty(installation):
    return dict(schema=1, installation_id=installation, generation=0, events=[])


def _privacy_digest(value, key):
    return hmac.new(key, _canonical(value), hashlib.sha256).hexdigest()


def _privacy_read(path, key, installation, *, allow_new=False):
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    except FileNotFoundError:
        if allow_new:
            return _privacy_empty(installation)
        raise Problem(409, 'Aktueller unabhängiger Datenschutz-Checkpoint fehlt.') from None
    try:
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077
                or info.st_size > _PRIVACY_MAX_BYTES):
            raise Problem(409, 'Datenschutz-Checkpoint ist nicht vertrauenswürdig.')
        with os.fdopen(descriptor, 'rb', closefd=False) as stream:
            raw = stream.read(_PRIVACY_MAX_BYTES + 1)
    finally:
        os.close(descriptor)
    def unique(pairs):
        result = {}
        for name, value in pairs:
            if name in result:
                raise ValueError('Duplicate checkpoint field')
            result[name] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=unique)
        signature = value.pop('digest')
        if (set(value) != {'schema', 'installation_id', 'generation', 'events'} or value['schema'] != 1
                or value['installation_id'] != installation or type(value['generation']) is not int
                or not isinstance(value['events'], list) or len(value['events']) != value['generation']
                or not isinstance(signature, str) or not hmac.compare_digest(signature, _privacy_digest(value, key))):
            raise ValueError('Checkpoint binding/signature mismatch')
        seen = set()
        for n, event in enumerate(value['events'], 1):
            if (set(event) != {'generation', 'operation', 'subject_kind', 'subject_hash', 'request_id', 'at'}
                    or event['generation'] != n or event['operation'] not in _PRIVACY_OPERATIONS
                    or event['subject_kind'] != _PRIVACY_OPERATIONS[event['operation']]
                    or not isinstance(event['subject_hash'], str) or not re.fullmatch(r'[a-f0-9]{64}', event['subject_hash'])
                    or not isinstance(event['request_id'], str) or not re.fullmatch(r'[a-f0-9]{32}', event['request_id'])
                    or event['request_id'] in seen or not isinstance(event['at'], str)
                    or datetime.fromisoformat(event['at']).tzinfo is None):
                raise ValueError('Invalid checkpoint event')
            seen.add(event['request_id'])
        return value
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError):
        raise Problem(409, 'Datenschutz-Checkpoint ist beschädigt oder nicht aktuell verifizierbar.') from None


def _privacy_write(path, value, key):
    data = _canonical(dict(value, digest=_privacy_digest(value, key))) + b'\n'
    if len(data) > _PRIVACY_MAX_BYTES:
        raise Problem(409, 'Datenschutz-Checkpoint benötigt eine kontrollierte Archivierung.')
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


@contextmanager
def _privacy_lock(path):
    import fcntl
    descriptor = os.open(str(path) + '.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise Problem(409, 'Datenschutz-Checkpoint-Sperre ist nicht privat.')
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def _privacy_record(office, kind, identifier, request_id, operation):
    if not isinstance(request_id, str) or not re.fullmatch(r'[a-f0-9]{32}', request_id):
        raise Problem(400, 'Eindeutige Datenschutzvorgangs-ID erforderlich.')
    if state(office)['storage_version'] != STORAGE_VERSION:
        raise Problem(409, 'Datenschutz benötigt den ausdrücklich migrierten Business-Bestand.')
    path, key, installation = _privacy_config()
    subject = privacy_subject_hash(kind, identifier)
    with _transaction(office), _privacy_lock(path):
        anchors = office.db.execute('SELECT * FROM business_privacy_anchors').fetchall()
        if anchors and (len(anchors) != 1 or anchors[0]['installation_id'] != installation):
            raise Problem(409, 'Datenschutz-Checkpoint gehört zu einer anderen Installation.')
        value = _privacy_read(path, key, installation, allow_new=not anchors)
        if not anchors and value['generation']:
            raise Problem(409, 'Datenschutz-Installationsbindung fehlt; unabhängige Entscheidungen zuerst abgleichen.')
        digest = _privacy_digest(value, key)
        if anchors and (anchors[0]['generation'] > value['generation']
                        or (anchors[0]['generation'] == value['generation'] and anchors[0]['digest'] != digest)):
            raise Problem(409, 'Datenschutz-Checkpoint wurde zurückgesetzt.')
        old = next((event for event in value['events'] if event['request_id'] == request_id), None)
        if old:
            if old['subject_hash'] != subject or old['operation'] != operation:
                raise Problem(409, 'Datenschutzvorgangs-ID wurde für einen anderen Inhalt verwendet.')
            event = old
        else:
            event = dict(generation=value['generation'] + 1, operation=operation, subject_kind=kind,
                         subject_hash=subject, request_id=request_id,
                         at=datetime.now(timezone.utc).isoformat(timespec='seconds'))
            value = dict(value, generation=event['generation'], events=[*value['events'], event])
            _privacy_write(path, value, key)  # MUST precede any destructive DB change.
        digest = _privacy_digest(value, key)
        office.db.execute('INSERT INTO business_privacy_anchors(installation_id,generation,digest) VALUES(?,?,?) '
                         'ON CONFLICT(installation_id) DO UPDATE SET generation=excluded.generation,digest=excluded.digest',
                         (installation, value['generation'], digest))
        return dict(event, digest=digest)


def initialize_privacy_checkpoint(office):
    """Explicit server setup only, before enabling any actual data erasure."""
    if state(office)['storage_version'] != STORAGE_VERSION:
        raise Problem(409, 'Datenschutz-Setup benötigt Schema 7.')
    path, key, installation = _privacy_config()
    with _transaction(office), _privacy_lock(path):
        rows = office.db.execute('SELECT * FROM business_privacy_anchors').fetchall()
        value = _privacy_read(path, key, installation, allow_new=not rows)
        digest = _privacy_digest(value, key)
        if rows:
            if len(rows) != 1 or rows[0]['installation_id'] != installation or rows[0]['generation'] != value['generation'] or rows[0]['digest'] != digest:
                raise Problem(409, 'Datenschutz-Setup darf keinen bestehenden Stand überschreiben.')
        else:
            if value['generation']:
                raise Problem(409, 'Vorhandene Datenschutzentscheidungen erfordern kontrollierten Abgleich.')
            tables = _tables(office)
            if (('business_time_privacy' in tables and office.db.execute('SELECT 1 FROM business_time_privacy LIMIT 1').fetchone())
                    or ('business_privacy_requests' in tables and office.db.execute("SELECT 1 FROM business_privacy_requests WHERE status='erased' LIMIT 1").fetchone())
                    or ('business_privacy_case_purges' in tables and office.db.execute('SELECT 1 FROM business_privacy_case_purges LIMIT 1').fetchone())):
                raise Problem(409, 'Bereits gelöschte Fachdaten benötigen den bestehenden unabhängigen Datenschutznachweis.')
            _privacy_write(path, value, key)
            office.db.execute('INSERT INTO business_privacy_anchors(installation_id,generation,digest) VALUES(?,0,?)',
                              (installation, digest))
        return dict(installation_id=installation, generation=value['generation'], digest=digest)


def checkpoint_before_erasure(office, customer_id, request_id):
    if not isinstance(customer_id, str) or not re.fullmatch(r'[a-f0-9]{32}', customer_id):
        raise Problem(400, 'Ungültiger Datenschutzkontakt.')
    return _privacy_record(office, 'customer', customer_id, request_id, 'anonymize_customer')


def checkpoint_before_location_purge(office, employee_id, day_iso, request_id):
    if (not isinstance(employee_id, str) or not re.fullmatch(r'[a-f0-9]{32}', employee_id)
            or not isinstance(day_iso, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day_iso)):
        raise Problem(400, 'Ungültiger Datenschutz-Zeitraum.')
    datetime.fromisoformat(day_iso)
    return _privacy_record(office, 'time_day', employee_id + ':' + day_iso, request_id, 'purge_time_locations')


def checkpoint_before_privacy_case_purge(office, case_id, request_id):
    if not isinstance(case_id, str) or not re.fullmatch(r'[a-f0-9]{32}', case_id):
        raise Problem(400, 'Ungültiger Datenschutzfall.')
    return _privacy_record(office, 'privacy_case', case_id, request_id, 'purge_privacy_case')


def checkpoint_before_privacy_export_purge(office, export_id, request_id):
    if not isinstance(export_id, str) or not re.fullmatch(r'[a-f0-9]{32}', export_id):
        raise Problem(400, 'Ungültiger Datenschutzexport.')
    return _privacy_record(office, 'privacy_export', export_id, request_id, 'purge_privacy_export')


def privacy_restore_guard(office):
    """Reapply the independent newest decisions BEFORE a restored DB is usable.

    A backup predating installation binding is rejected rather than guessed to
    belong to this installation. No old snapshot can declare a missing journal
    to be an empty one once independent server configuration exists.
    """
    anchors = office.db.execute('SELECT * FROM business_privacy_anchors').fetchall()
    configured = any(os.environ.get(name) for name in _PRIVACY_VARIABLES)
    if not configured and not anchors:
        return
    path, key, installation = _privacy_config()
    with _transaction(office), _privacy_lock(path):
        value = _privacy_read(path, key, installation)
        digest = _privacy_digest(value, key)
        if (len(anchors) != 1 or anchors[0]['installation_id'] != installation
                or anchors[0]['generation'] > value['generation']
                or (anchors[0]['generation'] == value['generation'] and anchors[0]['digest'] != digest)):
            raise Problem(409, 'Wiederherstellung ohne passenden aktuellen Datenschutznachweis gesperrt.')
        for event in value['events']:
            module = importlib.import_module(
                'business_foundation' if event['subject_kind'] == 'customer' else
                'business_time' if event['subject_kind'] == 'time_day' else 'business_privacy_cases')
            handler = getattr(module, 'reapply_privacy_checkpoint', None)
            if handler is None:
                raise Problem(409, 'Datenschutzentscheidung kann in diesem Rückkehr-Build nicht sicher angewendet werden.')
            handler(office, dict(event))
        office.db.execute('UPDATE business_privacy_anchors SET generation=?,digest=? WHERE installation_id=?',
                         (value['generation'], digest, installation))
