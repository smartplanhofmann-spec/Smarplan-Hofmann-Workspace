"""Revocable seven-day device access with explicit plan/workspace namespaces.

Namespace helpers never authenticate a token or authorize a project. Callers
must still resolve user() and apply the route and project permission checks.
"""
import secrets
import json
import time
from datetime import datetime, timezone
from core import Problem, canonical, digest

PREFIX = 'offline_'
WORKSPACE_PREFIX = 'offline_workspace_'
BUSINESS_PREFIX = 'offline_business_'
WORKSPACE_V2_PREFIX = 'offline_workspace_v2_'
BUSINESS_V2_PREFIX = 'offline_business_v2_'


def allows_workspace(token):
    """Classify only the granted namespace; never use this as authentication."""
    return isinstance(token, str) and token.startswith((WORKSPACE_PREFIX, BUSINESS_PREFIX))


def allows_business(token):
    """Namespace classification only; user() still authenticates the full hash."""
    return isinstance(token, str) and token.startswith(BUSINESS_PREFIX)


def is_v2(token):
    return isinstance(token, str) and token.startswith((WORKSPACE_V2_PREFIX, BUSINESS_V2_PREFIX))


def credential(row, *, instance_id=None):
    value = [row['id'], row['salt'], row['password'], row['role'], row['active']]
    if instance_id is not None:
        value.extend(['offline_instance_v2', instance_id])
    return digest(canonical(value))


def issue(office, user, *, workspace=False, business=False, business_capabilities=None, protocol_version=1):
    if type(protocol_version) is not int or protocol_version not in (1, 2) or protocol_version == 2 and not workspace:
        raise Problem(400, 'Ungültige Offline-Protokollversion')
    if type(workspace) is not bool or type(business) is not bool or (business and not workspace):
        raise Problem(400, 'Ungültiger Offline-Zugriffsbereich')
    row = office.db.execute('SELECT * FROM users WHERE id=? AND active=1', (user['id'],)).fetchone()
    if not row:
        raise Problem(401, 'Bitte anmelden')
    caps = ['time_events'] if business_capabilities is None else business_capabilities
    if business and (not isinstance(caps, (list, tuple)) or not caps or any(not isinstance(cap, str) for cap in caps) or len(set(caps)) != len(caps)
                     or any(cap not in ('time_events', 'field_media', 'offline_reports') for cap in caps)):
        raise Problem(400, 'Ungültiger Gerätezugriffsbereich')
    if not business and business_capabilities is not None:
        raise Problem(400, 'Ausdrücklicher Business-Gerätezugang erforderlich')
    origin = None
    if protocol_version == 2:
        from business_offline_binding import binding, TABLE
        from business_schema import _tables
        origin = binding(office, user, required=True)
        if TABLE not in _tables(office):
            raise Problem(409, 'Offline-V2-Migration ist noch nicht verfügbar.')
    issued = int(time.time())
    expires = issued + 7 * 24 * 3600
    prefix = BUSINESS_PREFIX if business else WORKSPACE_PREFIX if workspace else PREFIX
    if protocol_version == 2:
        prefix = BUSINESS_V2_PREFIX if business else WORKSPACE_V2_PREFIX
    token = prefix + secrets.token_urlsafe(32)
    office.db.execute('DELETE FROM plan_sessions WHERE expiry<?', (issued,))
    office.db.execute('INSERT INTO plan_sessions(token,user_id,expiry,credential) VALUES(?,?,?,?)',
                      (digest(token), row['id'], expires, credential(row, instance_id=origin['instance_id'] if origin else None)))
    if business:
        office.db.execute('INSERT INTO business_device_grants(token_hash,user_id,capabilities_json,issued_at,expiry) VALUES(?,?,?,?,?)',
                          (digest(token), row['id'], canonical(sorted(caps)), datetime.fromtimestamp(issued, timezone.utc).isoformat(), expires))
    office.audit(user, 'business.offline_access' if business else 'workspace.offline_access' if workspace else 'plan.offline_access', user['id'])
    result = dict(token=token, issued_at=datetime.fromtimestamp(issued, timezone.utc).isoformat(),
                  expires_at=datetime.fromtimestamp(expires, timezone.utc).isoformat())
    if protocol_version == 2:
        from business_offline_binding import register
        result.update(schema_version=2, binding=register(office, user, token, result['issued_at'], expires))
    return result


def user(office, token, *, allow_legacy_bound=False):
    with office.lock:
        row = office.db.execute('SELECT u.*,s.expiry,s.credential FROM users u JOIN plan_sessions s ON u.id=s.user_id '
                                'WHERE s.token=? AND u.active=1', (digest(token),)).fetchone()
        from business_offline_binding import instance_id, token_binding
        instance = instance_id(office)
        expected_instance = instance if is_v2(token) else None
        if (not row or row['expiry'] <= time.time() or is_v2(token) and instance is None
                or row['credential'] != credential(row, instance_id=expected_instance)):
            raise Problem(401, 'Offline-Zugang abgelaufen oder widerrufen. Bitte online anmelden.')
        actor = {key: row[key] for key in ('id', 'email', 'role')}
        if is_v2(token):
            token_binding(office, actor, token)
        elif instance is not None and not allow_legacy_bound:
            raise Problem(409, 'Dieser alte Offline-Zugang besitzt keine bestätigte Firmenbindung. Online anmelden und V2 verwenden; gespeicherte Aufträge bleiben erhalten.')
        return actor


def require_request_binding(office, actor, token, supplied):
    if not is_v2(token):
        from business_offline_binding import instance_id
        if instance_id(office) is not None:
            raise Problem(409, 'Dieser alte Offline-Zugang besitzt keine bestätigte Firmenbindung.')
        return
    from business_offline_binding import token_binding
    expected = token_binding(office, actor, token)
    if supplied != expected['instance_id'] + ':' + expected['account_id']:
        raise Problem(403, 'Die Offline-Anfrage gehört nicht zu dieser Firmen- und Kontoanmeldung.')


def revoke(office, token):
    office.db.execute('DELETE FROM plan_sessions WHERE token=?', (digest(token),))
    return {'ok': True}


def business_capabilities(office, token):
    """Authenticate the issued token and its explicit immutable device scopes."""
    if not allows_business(token):
        return []
    actor = user(office, token)
    row = office.db.execute('SELECT user_id,capabilities_json,expiry FROM business_device_grants WHERE token_hash=?', (digest(token),)).fetchone()
    if not row or row['user_id'] != actor['id'] or row['expiry'] <= time.time():
        raise Problem(403, 'Der Gerätezugang hat keine aktuelle Business-Freigabe.')
    try:
        caps = json.loads(row['capabilities_json'])
    except (TypeError, ValueError):
        raise Problem(403, 'Ungültige Gerätefreigabe.') from None
    if (not isinstance(caps, list) or not caps or any(not isinstance(value, str) for value in caps) or len(set(caps)) != len(caps)
            or any(value not in ('time_events', 'field_media', 'offline_reports') for value in caps)):
        raise Problem(403, 'Ungültige Gerätefreigabe.')
    return caps
