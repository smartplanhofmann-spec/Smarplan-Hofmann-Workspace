"""Versioned offline device origin binding and read-only legacy reconciliation.

This does not infer the origin of unbound client caches. The server validates
its actual fixed instance, current account, token and supplied stored origin.
"""
from datetime import datetime
import json
import math
import re
import time

from core import Problem, canonical, digest, text_field
from business_foundation import _fresh, require_permission

FEATURES = ('offline_instance_binding',)
TABLE = 'business_offline_instance_grants'
HEADER = 'X-Smartplan-Offline-Binding'
ID = r'[a-f0-9]{32}'


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA', 'BLOB'):
        raise ValueError('Unsupported offline binding binary type')
    return [f'''CREATE TABLE IF NOT EXISTS {TABLE}(
        token_hash TEXT PRIMARY KEY REFERENCES plan_sessions(token) ON DELETE CASCADE,
        instance_id TEXT NOT NULL CHECK(length(instance_id)=32),
        account_id TEXT NOT NULL REFERENCES users(id), issued_at TEXT NOT NULL,
        expiry DOUBLE PRECISION NOT NULL)''']


def runtime_privileges():
    # Revocation deletes the parent session and cascades to this private row.
    return {TABLE: ('SELECT', 'INSERT')}


def guard_statements(dialect):
    if dialect == 'sqlite':
        return [f"CREATE TRIGGER IF NOT EXISTS {TABLE}_update_guard BEFORE UPDATE ON {TABLE} "
                "BEGIN SELECT RAISE(ABORT,'immutable offline origin'); END",
                f"CREATE TRIGGER IF NOT EXISTS {TABLE}_insert_guard BEFORE INSERT ON {TABLE} "
                f"WHEN EXISTS(SELECT 1 FROM {TABLE} WHERE token_hash=NEW.token_hash) "
                "BEGIN SELECT RAISE(ABORT,'immutable offline origin'); END"]
    if dialect == 'postgresql':
        return ["CREATE OR REPLACE FUNCTION business_offline_instance_grant_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ "
                "BEGIN RAISE EXCEPTION 'immutable offline origin'; END; $$",
                f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{TABLE}_update_guard' "
                f"AND tgrelid='{TABLE}'::regclass) THEN CREATE TRIGGER {TABLE}_update_guard BEFORE UPDATE ON {TABLE} "
                "FOR EACH ROW EXECUTE FUNCTION business_offline_instance_grant_immutable(); END IF; END $$"]
    raise ValueError('Unsupported offline binding dialect')


def instance_id(office):
    from business_schema import _tables
    if 'business_instance_identity' not in _tables(office):
        return None
    from business_instance import validate_integrity
    validate_integrity(office)
    rows = office.db.execute('SELECT instance_id FROM business_instance_identity').fetchall()
    return rows[0]['instance_id'] if rows else None


def binding(office, actor, *, required=False):
    fresh = _fresh(office, actor)
    instance = instance_id(office)
    if instance is None:
        if required:
            raise Problem(409, 'Offline V2 benötigt eine ausdrücklich gebundene Unternehmensinstanz.')
        return None
    return dict(schema_version=1, instance_id=instance, account_id=fresh['id'])


def context(office, actor):
    with office.lock:
        value = binding(office, actor)
        return dict(schema_version=2, mode='bound_v2' if value else 'unbound_legacy', binding=value)


def runtime_features(office):
    return FEATURES if instance_id(office) is not None else ()


def register(office, actor, token, issued_at, expiry):
    from business_schema import _tables
    if TABLE not in _tables(office):
        raise Problem(409, 'Offline-V2-Migration ist noch nicht verfügbar.')
    value = binding(office, actor, required=True)
    office.db.execute(f'INSERT INTO {TABLE}(token_hash,instance_id,account_id,issued_at,expiry) VALUES(?,?,?,?,?)',
                      (digest(token), value['instance_id'], value['account_id'], issued_at, expiry))
    return value


def token_binding(office, actor, token):
    from business_schema import _tables
    expected = binding(office, actor, required=True)
    if TABLE not in _tables(office):
        raise Problem(403, 'Der gebundene Offline-Zugang ist nicht verfügbar.')
    row = office.db.execute(f'SELECT * FROM {TABLE} WHERE token_hash=?', (digest(token),)).fetchone()
    if (row is None or row['instance_id'] != expected['instance_id'] or row['account_id'] != expected['account_id']):
        raise Problem(403, 'Der Offline-Zugang gehört nicht zu dieser Unternehmensanmeldung.')
    session = office.db.execute('SELECT user_id,expiry FROM plan_sessions WHERE token=?', (digest(token),)).fetchone()
    try:
        issued = datetime.fromisoformat(row['issued_at'])
        active = (session is not None and session['user_id'] == expected['account_id']
                  and issued.tzinfo is not None and issued.timestamp() <= time.time() < row['expiry']
                  and 0 < row['expiry'] - issued.timestamp() <= 7 * 86400
                  and session['expiry'] == row['expiry'])
    except (TypeError, ValueError, OverflowError):
        active = False
    if not active:
        raise Problem(403, 'Die gespeicherte Offline-Freigabe ist nicht unverändert aktiv.')
    return expected


def validate_integrity(office):
    instance = instance_id(office)
    for row in office.db.execute(f'SELECT * FROM {TABLE}').fetchall():
        session = office.db.execute('SELECT user_id,expiry FROM plan_sessions WHERE token=?', (row['token_hash'],)).fetchone()
        try:
            issued = datetime.fromisoformat(row['issued_at'])
            valid = (instance is not None and row['instance_id'] == instance
                     and re.fullmatch(r'[a-f0-9]{64}', row['token_hash']) is not None
                     and re.fullmatch(ID, row['account_id']) is not None and issued.tzinfo is not None
                     and type(row['expiry']) in (int, float) and math.isfinite(row['expiry'])
                     and 0 < row['expiry'] - issued.timestamp() <= 7 * 86400 and session is not None
                     and session['user_id'] == row['account_id'] and session['expiry'] == row['expiry'])
        except (TypeError, ValueError):
            valid = False
        if not valid:
            raise ValueError('Invalid offline instance grant')
    return True


def _identifier(value, name):
    if not isinstance(value, str) or re.fullmatch(ID, value) is None:
        raise Problem(400, name + ' muss eine eindeutige Kennung sein.')
    return value


def legacy_lookup(office, actor, data):
    # A legacy payload has no proven company origin. Only hashes and identifiers
    # may cross this boundary; original content stays on the client.
    expected = {'schema_version', 'nonce', 'kind', 'project_id', 'plan_id', 'request_id', 'request_hash'}
    if (not isinstance(data, dict) or set(data) != expected or type(data['schema_version']) is not int
            or data['schema_version'] != 2 or data['kind'] != 'plan_write'):
        raise Problem(400, 'Nur Kennungen und Originalhash zum lesenden Planabgleich senden.')
    nonce = _identifier(data['nonce'], 'Abgleichkennung')
    project = _identifier(data['project_id'], 'Projektkennung')
    plan = data['plan_id']
    if plan is not None:
        _identifier(plan, 'Plankennung')
    request_id = _identifier(data['request_id'], 'Ursprüngliche Auftragskennung')
    fingerprint = data['request_hash']
    if not isinstance(fingerprint, str) or re.fullmatch(r'[a-f0-9]{64}', fingerprint) is None:
        raise Problem(400, 'Eindeutigen ursprünglichen SHA-256-Hash senden.')
    encoded = canonical(data).encode('utf-8')
    if len(encoded) > 4096:
        raise Problem(413, 'Planabgleich ist zu groß.')
    from plans import validate_drawing
    with office.lock, office.db:
        fresh = require_permission(office, actor, 'documents.read', project)
        scope = binding(office, fresh, required=True)
        prior = office.db.execute('SELECT * FROM plan_requests WHERE user_id=? AND request_id=?',
                                  (fresh['id'], request_id)).fetchone()
        if prior is None:
            raise Problem(404, 'Keine eindeutig passende ursprüngliche Planannahme gefunden. Der lokale Auftrag bleibt ungeklärt.')
        if prior['project_id'] != project or prior['request_hash'] != fingerprint:
            raise Problem(409, 'Die gespeicherte Planannahme passt nicht zum ursprünglichen Auftrag.')
        try:
            original = json.loads(prior['result'])
            identifier = _identifier(original['id'], 'Ursprüngliche Plankennung')
            if (set(original) != {'id', 'project_id', 'title', 'revision', 'status', 'units', 'walls', 'updated_at', 'updated_by'}
                    or original['project_id'] != project or plan is not None and identifier != plan
                    or type(original['revision']) is not int
                    or (original['revision'] != 1 if plan is None else original['revision'] < 2)
                    or original['title'] != text_field(original['title'], 'Plantitel', 200)
                    or canonical(original['walls']) != canonical(validate_drawing(original['walls']))
                    or original['status'] != 'draft' or original['units'] != 'unitless'
                    or original['updated_by'] != fresh['id']
                    or datetime.fromisoformat(original['updated_at']).tzinfo is None):
                raise ValueError('Invalid original')
            archived = office.db.execute('SELECT payload FROM plan_versions WHERE id=? AND revision=? AND project_id=?',
                                         (identifier, original['revision'], project)).fetchone()
            if archived is None or canonical(json.loads(archived['payload'])) != canonical(original):
                raise ValueError('Missing original archive')
            from plan_deletions import by_object
            if by_object(office.db, 'plan', identifier):
                raise ValueError('Deleted plan')
        except (TypeError, ValueError, KeyError, Problem):
            raise Problem(409, 'Die ursprüngliche Planfassung ist nicht eindeutig und unverändert verfügbar.') from None
        return dict(schema_version=2, nonce=nonce, lookup_hash=digest(encoded.decode('utf-8')), binding=scope,
                    kind='plan_write', project_id=project, plan_id=plan, request_id=request_id,
                    request_hash=fingerprint, original=original)


def methods(path):
    return 'POST' if path == '/offline/recovery/lookup' else None


def dispatch(office, actor, path, method, data):
    if methods(path) is None:
        return None
    if method != 'POST':
        raise Problem(405, 'Nur der lesende POST-Abgleich ist verfügbar.')
    return legacy_lookup(office, actor, data), 200, 'application/json'
