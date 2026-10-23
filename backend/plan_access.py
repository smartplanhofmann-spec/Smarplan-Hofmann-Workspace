"""Revocable seven-day device access, restricted to project-plan operations."""
import secrets
import time
from datetime import datetime, timezone
from core import Problem, canonical, digest

PREFIX = 'offline_'


def credential(row):
    return digest(canonical([row['id'], row['salt'], row['password'], row['role'], row['active']]))


def issue(office, user):
    row = office.db.execute('SELECT * FROM users WHERE id=? AND active=1', (user['id'],)).fetchone()
    if not row:
        raise Problem(401, 'Bitte anmelden')
    issued = time.time()
    expires = issued + 7 * 24 * 3600
    token = PREFIX + secrets.token_urlsafe(32)
    office.db.execute('DELETE FROM plan_sessions WHERE expiry<?', (issued,))
    office.db.execute('INSERT INTO plan_sessions(token,user_id,expiry,credential) VALUES(?,?,?,?)',
                      (digest(token), row['id'], expires, credential(row)))
    office.audit(user, 'plan.offline_access', user['id'])
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
