"""Revocable seven-day device access with explicit plan/workspace namespaces.

Namespace helpers never authenticate a token or authorize a project. Callers
must still resolve user() and apply the route and project permission checks.
"""
import secrets
import time
from datetime import datetime, timezone
from core import Problem, canonical, digest

PREFIX = 'offline_'
WORKSPACE_PREFIX = 'offline_workspace_'


def allows_workspace(token):
    """Classify only the granted namespace; never use this as authentication."""
    return isinstance(token, str) and token.startswith(WORKSPACE_PREFIX)


def credential(row):
    return digest(canonical([row['id'], row['salt'], row['password'], row['role'], row['active']]))


def issue(office, user, *, workspace=False):
    if type(workspace) is not bool:
        raise Problem(400, 'Ungültiger Offline-Zugriffsbereich')
    row = office.db.execute('SELECT * FROM users WHERE id=? AND active=1', (user['id'],)).fetchone()
    if not row:
        raise Problem(401, 'Bitte anmelden')
    issued = time.time()
    expires = issued + 7 * 24 * 3600
    prefix = WORKSPACE_PREFIX if workspace else PREFIX
    token = prefix + secrets.token_urlsafe(32)
    office.db.execute('DELETE FROM plan_sessions WHERE expiry<?', (issued,))
    office.db.execute('INSERT INTO plan_sessions(token,user_id,expiry,credential) VALUES(?,?,?,?)',
                      (digest(token), row['id'], expires, credential(row)))
    office.audit(user, 'workspace.offline_access' if workspace else 'plan.offline_access', user['id'])
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
