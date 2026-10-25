"""Restore only into an empty, different PostgreSQL database; revoke saved sessions."""
import hashlib
import argparse
import os
from pathlib import Path
import re
import subprocess
import time
import uuid

import psycopg
from psycopg.conninfo import make_conninfo
from online.store import PostgresOffice, migrate
from online.plan_imports import validate_integrity


def restore_dump(source, active_dsn, target_dsn, *, owner_role=None):
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
    if owner_role not in (None, 'smartplan-migrator'):
        raise ValueError('Unbekannte Wiederherstellungsrolle.')
    command = ['pg_restore', '--exit-on-error', '--single-transaction', '--no-owner', '--no-acl']
    if owner_role:
        command.extend(['--role', owner_role])
    command.extend(['--dbname', target_dsn])
    with source.open('rb') as stream:
        result = subprocess.run(command, stdin=stream, stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE, timeout=300)
    if result.returncode:
        raise RuntimeError('Wiederherstellung fehlgeschlagen; neue Zieldatenbank bleibt vom Betrieb getrennt.')


def restore(source, active_dsn, target_dsn, *, privileged_operator=False, test_mode=False):
    if privileged_operator:
        from online.release import operator_dsns, no_other_clients
        active_dsn, target_dsn = operator_dsns(active_dsn, target_dsn, test_mode=test_mode)
        no_other_clients(active_dsn)
    owner = 'smartplan-migrator' if privileged_operator else None
    restore_dump(source, active_dsn, target_dsn, owner_role=owner)
    # Older supported backups are upgraded only in the separate empty target.
    # The active database is never migrated or restored by this command.
    migrate(target_dsn, owner_role=owner, require_business_modules=privileged_operator)
    office = PostgresOffice(target_dsn, allow_restore_pending=True)
    try:
        with office.lock, office.db:
            for row in office.db.execute('SELECT pdf,pdf_hash FROM reports WHERE pdf IS NOT NULL'):
                if hashlib.sha256(row['pdf']).hexdigest() != row['pdf_hash']:
                    raise ValueError('PDF-Integritätsprüfung fehlgeschlagen.')
            validate_integrity(office)
            from business_schema import validate_integrity as validate_business, privacy_restore_guard, apply_runtime_privileges
            validate_business(office)
            # A restored pending intent may already have been sent after this
            # backup. Preserve that uncertainty; never silently resume delivery.
            from business_documents import sanitize_after_restore as sanitize_documents
            from business_finance import sanitize_after_restore as sanitize_finance
            from business_adapters import sanitize_after_restore as sanitize_adapters
            sanitize_documents(office)
            sanitize_finance(office)
            sanitize_adapters(office)
            restore_id = uuid.uuid4().hex
            office.db.execute('UPDATE business_restore_state SET pending=1,financial_reconciliation_required=1,restore_id=? WHERE singleton=1',
                              (restore_id,))
            # A disaster restore must not reactivate saved provider accounts or
            # OAuth callbacks. Candidate releases intentionally retain them.
            from integration_bridge import sanitize_after_restore as sanitize_bridge, validate_integrity as validate_bridge
            sanitize_bridge(office)
            from external_integrations import sanitize_after_restore, validate_integrity as validate_integrations
            sanitize_after_restore(office)
            validate_integrations(office)
            validate_bridge(office)
            # Upload limits are transient traffic counters. Active attachment
            # byte quotas are derived from retained files, never reset here.
            for table in ('sessions', 'plan_sessions', 'auth_challenges', 'login_limits', 'inquiry_attachment_limits'):
                office.db.execute(f'DELETE FROM {table}')
            office.db.execute('UPDATE inbound_import_tokens SET revoked_at=? WHERE revoked_at IS NULL', (time.time(),))
            if privileged_operator:
                apply_runtime_privileges(office)
            else:
                # The direct local/test path has the same OS identity as its
                # private checkpoint. Privileged server restore is deliberately
                # two-stage: postgres must never receive the runtime vault key.
                privacy_restore_guard(office)
                validate_integrity(office)
                validate_business(office)
                office.db.execute('UPDATE business_restore_state SET pending=0 WHERE singleton=1')
    finally:
        office.db.close()
    if privileged_operator:
        no_other_clients(active_dsn)
    return {'restore_pending': privileged_operator, 'financial_reconciliation_required': True,
            'restore_id': restore_id, 'schema_version': 7}


def complete_restore(office):
    """Runtime-UID verifier, after operator restore and before any public access."""
    from business_schema import (require_runtime_security, privacy_restore_guard,
                                 validate_integrity as validate_business)
    require_runtime_security(office)
    if not getattr(office, '_allow_restore_pending', False):
        raise ValueError('Expliziter Restore-Prüfkontext erforderlich.')
    with office.lock, office.db:
        validate_integrity(office)
        validate_business(office)
        privacy_restore_guard(office)
        for row in office.db.execute('SELECT pdf,pdf_hash FROM reports WHERE pdf IS NOT NULL'):
            if hashlib.sha256(row['pdf']).hexdigest() != row['pdf_hash']:
                raise ValueError('PDF-Integritätsprüfung fehlgeschlagen.')
        validate_integrity(office)
        validate_business(office)
        office.db.execute('UPDATE business_restore_state SET pending=0 WHERE singleton=1')
    return {'restore_pending': False, 'schema_version': 7, 'status': 'verified'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dump')
    parser.add_argument('database')
    parser.add_argument('--privileged-operator', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z][a-z0-9_]{1,62}', args.database):
        parser.error('Getrennter neuer Datenbankname erforderlich.')
    if not args.privileged_operator:
        parser.error('Schema-7-Serverrestore benötigt --privileged-operator und den koordinierten Writerstopp.')
    active_dsn = os.environ['SMARTPLAN_DATABASE_DSN']
    result = restore(args.dump, active_dsn, make_conninfo(active_dsn, dbname=args.database),
                     privileged_operator=args.privileged_operator)
    import json
    print(json.dumps(result, sort_keys=True))
