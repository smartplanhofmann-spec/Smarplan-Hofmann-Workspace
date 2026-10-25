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


def allows_workspace(token):
    """Classify only the granted namespace; never use this as authentication."""
    return isinstance(token, str) and token.startswith((WORKSPACE_PREFIX, BUSINESS_PREFIX))


def allows_business(token):
    """Namespace classification only; user() still authenticates the full hash."""
    return isinstance(token, str) and token.startswith(BUSINESS_PREFIX)


def credential(row):
    return digest(canonical([row['id'], row['salt'], row['password'], row['role'], row['active']]))


def issue(office, user, *, workspace=False, business=False, business_capabilities=None):
    if type(workspace) is not bool or type(business) is not bool or (business and not workspace):
        raise Problem(400, 'Ungültiger Offline-Zugriffsbereich')
    row = office.db.execute('SELECT * FROM users WHERE id=? AND active=1', (user['id'],)).fetchone()
    if not row:
        raise Problem(401, 'Bitte anmelden')
    caps = ['time_events'] if business_capabilities is None else business_capabilities
    if business and (not isinstance(caps, (list, tuple)) or not caps or any(not isinstance(cap, str) for cap in caps) or len(set(caps)) != len(caps)
                     or any(cap not in ('time_events', 'field_media') for cap in caps)):
        raise Problem(400, 'Ungültiger Gerätezugriffsbereich')
    if not business and business_capabilities is not None:
        raise Problem(400, 'Ausdrücklicher Business-Gerätezugang erforderlich')
    issued = int(time.time())
    expires = issued + 7 * 24 * 3600
    prefix = BUSINESS_PREFIX if business else WORKSPACE_PREFIX if workspace else PREFIX
    token = prefix + secrets.token_urlsafe(32)
    office.db.execute('DELETE FROM plan_sessions WHERE expiry<?', (issued,))
    office.db.execute('INSERT INTO plan_sessions(token,user_id,expiry,credential) VALUES(?,?,?,?)',
                      (digest(token), row['id'], expires, credential(row)))
    if business:
        office.db.execute('INSERT INTO business_device_grants(token_hash,user_id,capabilities_json,issued_at,expiry) VALUES(?,?,?,?,?)',
                          (digest(token), row['id'], canonical(sorted(caps)), datetime.fromtimestamp(issued, timezone.utc).isoformat(), expires))
    office.audit(user, 'business.offline_access' if business else 'workspace.offline_access' if workspace else 'plan.offline_access', user['id'])
    return dict(token=token, issued_at=datetime.fromtimestamp(issued, timezone.utc).isoformat(),
                expires_at=datetime.fromtimestamp(expires, timezone.utc).isoformat())


def user(office, token):
    with office.lock:
        row = office.db.execute('SELECT u.*,s.expiry,s.credential FROM users u JOIN plan_sessions s ON u.id=s.user_id '
                                'WHERE s.token=? AND u.active=1', (digest(token),)).fetchone()
        if not row or row['expiry'] <= time.time() or row['credential'] != credential(row):
            raise Problem(401, 'Offline-Zugang abgelaufen oder widerrufen. Bitte online anmelden.')
        return {key: row[key] for key in ('id', 'email', 'role')}


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
            or any(value not in ('time_events', 'field_media') for value in caps)):
        raise Problem(403, 'Ungültige Gerätefreigabe.')
    return caps
