"""Password + TOTP authentication with database-backed limits and one-use challenges."""
import base64
import hashlib
import hmac
import json
import re
import secrets
import struct
import time
from urllib.parse import quote

from cryptography.fernet import Fernet
from core import Problem, canonical, digest, password_hash, text_field


def totp(secret, step, digits=6):
    key = base64.b32decode(secret, casefold=True)
    value = hmac.new(key, struct.pack('>Q', step), hashlib.sha1).digest()
    offset = value[-1] & 15
    number = struct.unpack('>I', value[offset:offset + 4])[0] & 0x7fffffff
    return str(number % (10 ** digits)).zfill(digits)


def fingerprint(user):
    return digest(canonical([user['password'], user['salt'], user['role'], user['active']]))


class Authentication:
    def __init__(self, office, key):
        self.office = office
        self.vault = Fernet(key)

    def limit(self, key, maximum, timestamp, increment=False):
        db = self.office.db
        row = db.execute('SELECT * FROM login_limits WHERE key=?', (key,)).fetchone()
        failures = row['failures'] if row and row['reset_at'] > timestamp else 0
        if failures >= maximum:
            return False
        if increment:
            db.execute('INSERT INTO login_limits VALUES(?,?,?) ON CONFLICT(key) DO UPDATE '
                       'SET failures=excluded.failures,reset_at=excluded.reset_at',
                       (key, failures + 1, row['reset_at'] if failures else timestamp + 300))
        return True

    def begin(self, email, password, address):
        email = text_field(email, 'E-Mail', 254).lower()
        if not isinstance(password, str) or not 1 <= len(password) <= 512:
            raise Problem(401, 'Anmeldung fehlgeschlagen')
        timestamp = time.time()
        account, remote = 'account:' + digest(email), 'ip:' + digest(address)
        error, result = None, None
        with self.office.lock, self.office.db as db:
            db.execute('DELETE FROM login_limits WHERE reset_at<=?', (timestamp,))
            db.execute('DELETE FROM auth_challenges WHERE expiry<=?', (timestamp,))
            db.execute('DELETE FROM sessions WHERE expiry<=?', (timestamp,))
            if not self.limit(remote, 60, timestamp, increment=True) or not self.limit(account, 5, timestamp):
                error = Problem(429, 'Bitte in fünf Minuten erneut versuchen')
            else:
                user = db.execute('SELECT * FROM users WHERE email=? AND active=1', (email,)).fetchone()
                calculated = password_hash(password, user['salt'] if user else '00' * 16)
                if not user or not hmac.compare_digest(calculated, user['password']):
                    self.limit(account, 5, timestamp, increment=True)
                    error = Problem(401, 'Anmeldung fehlgeschlagen')
                else:
                    mfa = db.execute('SELECT secret FROM mfa WHERE user_id=?', (user['id'],)).fetchone()
                    secret = self.vault.decrypt(mfa['secret'].encode()).decode() if mfa else base64.b32encode(secrets.token_bytes(20)).decode()
                    token = secrets.token_urlsafe(32)
                    # One pending login per account prevents accumulating enrollment attempts.
                    db.execute('DELETE FROM auth_challenges WHERE user_id=?', (user['id'],))
                    db.execute('INSERT INTO auth_challenges VALUES(?,?,?,?,?,0)',
                               (digest(token), user['id'], fingerprint(user), self.vault.encrypt(secret.encode()).decode(), timestamp + 300))
                    result = {'mfa_required': True, 'challenge': token}
                    if not mfa:
                        result['enrollment'] = {'secret': secret, 'uri': 'otpauth://totp/' +
                            quote('Smartplan Office:' + email, safe='') + '?secret=' + secret + '&issuer=Smartplan%20Office'}
        if error:
            raise error
        return result

    def finish(self, challenge, code):
        if not isinstance(challenge, str) or not 20 <= len(challenge) <= 100 or not isinstance(code, str) or len(code) > 100:
            raise Problem(401, 'Anmeldung abgelaufen oder Code ungültig')
        timestamp = time.time()
        error, result = None, None
        with self.office.lock, self.office.db as db:
            pending = db.execute('SELECT * FROM auth_challenges WHERE token=?', (digest(challenge),)).fetchone()
            user = db.execute('SELECT * FROM users WHERE id=?', (pending['user_id'],)).fetchone() if pending else None
            if (not pending or pending['expiry'] <= timestamp or pending['failures'] >= 5 or
                    not user or not user['active'] or fingerprint(user) != pending['credential']):
                error = Problem(401, 'Anmeldung abgelaufen oder Code ungültig')
            elif not self.limit('account:' + digest(user['email']), 5, timestamp):
                error = Problem(429, 'Bitte in fünf Minuten erneut versuchen')
            else:
                mfa = db.execute('SELECT * FROM mfa WHERE user_id=?', (user['id'],)).fetchone()
                secret = self.vault.decrypt(pending['secret'].encode()).decode()
                if mfa and self.vault.decrypt(mfa['secret'].encode()).decode() != secret:
                    error = Problem(401, 'Anmeldung abgelaufen oder Code ungültig')
                else:
                    code = code.strip().replace(' ', '').replace('-', '')
                    step = None
                    if re.fullmatch(r'\d{6}', code):
                        step = next((candidate for candidate in range(int(timestamp // 30) - 1, int(timestamp // 30) + 2)
                                     if candidate > (mfa['last_step'] if mfa else -1) and
                                     hmac.compare_digest(totp(secret, candidate), code)), None)
                    recovery = json.loads(mfa['recovery']) if mfa else []
                    recovery_hash = digest(code.lower())
                    recovered = any(hmac.compare_digest(recovery_hash, saved) for saved in recovery)
                    if step is None and not recovered:
                        db.execute('UPDATE auth_challenges SET failures=failures+1 WHERE token=?', (digest(challenge),))
                        self.limit('account:' + digest(user['email']), 5, timestamp, increment=True)
                        error = Problem(401, 'Anmeldung abgelaufen oder Code ungültig')
                    else:
                        codes = []
                        if not mfa:
                            codes = [secrets.token_hex(12) for _ in range(10)]
                            recovery = [digest(value) for value in codes]
                        elif recovered:
                            recovery.remove(recovery_hash)
                        db.execute('INSERT INTO mfa VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE '
                                   'SET last_step=excluded.last_step,recovery=excluded.recovery',
                                   (user['id'], pending['secret'], step if step is not None else mfa['last_step'], canonical(recovery)))
                        token = secrets.token_urlsafe(32)
                        db.execute('DELETE FROM auth_challenges WHERE user_id=?', (user['id'],))
                        db.execute('DELETE FROM login_limits WHERE key=?', ('account:' + digest(user['email']),))
                        db.execute('INSERT INTO sessions VALUES(?,?,?)', (digest(token), user['id'], timestamp + 8 * 3600))
                        self.office.audit(user, 'login.mfa', user['id'])
                        result = {'token': token}
                        if codes:
                            result['recovery_codes'] = codes
        if error:
            raise error
        return result
