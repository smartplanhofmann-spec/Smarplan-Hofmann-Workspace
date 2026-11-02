"""Additive, operator-bound identity for one company per database/process."""
from datetime import datetime
import re


def runtime_privileges():
    return {'business_instance_identity': ('SELECT',)}


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA', 'BLOB'):
        raise ValueError('Unsupported binary storage type')
    return ['''CREATE TABLE IF NOT EXISTS business_instance_identity(
      singleton INTEGER PRIMARY KEY CHECK(singleton=1),
      instance_id TEXT NOT NULL CHECK(length(instance_id)=32),
      public_host TEXT NOT NULL, storage_root TEXT NOT NULL,
      vault_fingerprint TEXT NOT NULL CHECK(length(vault_fingerprint)=64),
      created_at TEXT NOT NULL)''']


def guard_statements(dialect):
    if dialect == 'sqlite':
        return [f'''CREATE TRIGGER IF NOT EXISTS business_instance_identity_{action.lower()}_guard
          BEFORE {action} ON business_instance_identity BEGIN
          SELECT RAISE(ABORT,'instance identity is immutable'); END''' for action in ('UPDATE', 'DELETE')] + [
          '''CREATE TRIGGER IF NOT EXISTS business_instance_identity_insert_guard
          BEFORE INSERT ON business_instance_identity
          WHEN EXISTS(SELECT 1 FROM business_instance_identity)
          BEGIN SELECT RAISE(ABORT,'instance identity is immutable'); END''']
    if dialect == 'postgresql':
        return ['''CREATE OR REPLACE FUNCTION business_instance_identity_guard() RETURNS trigger
          LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'instance identity is immutable'; END; $$''',
          '''DROP TRIGGER IF EXISTS business_instance_identity_guard ON business_instance_identity''',
          '''CREATE TRIGGER business_instance_identity_guard BEFORE UPDATE OR DELETE ON business_instance_identity
          FOR EACH ROW EXECUTE FUNCTION business_instance_identity_guard()''']
    raise ValueError('Unsupported database dialect')


def validate_integrity(office):
    rows = office.db.execute('SELECT * FROM business_instance_identity').fetchall()
    if len(rows) > 1:
        raise ValueError('Ambiguous instance identity')
    for row in rows:
        if (row['singleton'] != 1 or not re.fullmatch(r'[a-f0-9]{32}', row['instance_id'])
                or not re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)+', row['public_host'])
                or not re.fullmatch(r'[a-f0-9]{64}', row['vault_fingerprint'])
                or not row['storage_root'].startswith('/') or row['storage_root'] == '/'
                or '\x00' in row['storage_root']
                or any(part in ('.', '..') for part in row['storage_root'].split('/'))
                or datetime.fromisoformat(row['created_at']).tzinfo is None):
            raise ValueError('Invalid instance identity')
    return True
