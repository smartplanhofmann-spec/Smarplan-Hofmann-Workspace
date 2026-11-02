"""Explicit one-company instance binding; HTTP startup only verifies it.

This is a deployment boundary, not a request-selected tenant or an isolation
claim for multiple companies in one database. Never accept binding from HTTP.
"""
import argparse
import base64
import hashlib
import os
from pathlib import Path
import re
import stat

from cryptography.fernet import Fernet

from core import Problem, canonical, now_iso
from online.storage_backends import ServerStorage


MARKER = '.smartplan-instance.json'
ERROR = 'Unternehmensinstanz stimmt nicht mit Datenbank, Host, Schlüssel oder Serverablage überein.'


class InstanceConfigurationError(RuntimeError):
    pass


def _fail():
    raise InstanceConfigurationError(ERROR)


def identity(office):
    """Read only, including for legacy schemas where this module is absent."""
    from business_schema import _tables
    if 'business_instance_identity' not in _tables(office):
        return None
    rows = office.db.execute('SELECT * FROM business_instance_identity').fetchall()
    if not rows:
        return None
    if len(rows) != 1:
        _fail()
    from business_instance import validate_integrity
    try:
        validate_integrity(office)
    except (TypeError, ValueError):
        _fail()
    return dict(rows[0])


def _values(instance_id, host, key, server):
    if (not isinstance(instance_id, str) or not re.fullmatch(r'[a-f0-9]{32}', instance_id)
            or not isinstance(host, str) or not re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)+', host)
            or not isinstance(server, ServerStorage) or not server.configured()):
        _fail()
    try:
        Fernet(key)
        fingerprint = hashlib.sha256(base64.urlsafe_b64decode(key)).hexdigest()
    except (TypeError, ValueError):
        _fail()
    return dict(instance_id=instance_id, public_host=host,
                storage_root=os.path.normpath(server.base_path), vault_fingerprint=fingerprint)


def _marker(value):
    return dict(schema=1, **{key: value[key] for key in
                ('instance_id', 'public_host', 'vault_fingerprint')})


def verify_storage_marker(directory, expected):
    """Read a private regular marker through the already checked directory FD."""
    descriptor = None
    try:
        descriptor = os.open(MARKER, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                             dir_fd=directory)
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_mode & 0o077 or info.st_nlink != 1 or info.st_size > 4096):
            _fail()
        # Compare canonical bytes: duplicate JSON keys and trailing data are rejected too.
        if os.read(descriptor, 4097) != canonical(_marker(expected)).encode('utf-8'):
            _fail()
    except (OSError, ValueError):
        _fail()
    finally:
        if descriptor is not None:
            os.close(descriptor)


def verify(office, instance_id, host, key, storage):
    """No writes or automatic binding. Bound DBs cannot opt out by omitting config."""
    with office.lock:
        saved = identity(office)
        if saved is None and instance_id is None:
            # Historical mode must not reuse a root already reserved by another
            # company. Missing/unusable legacy paths retain lazy storage errors.
            server = getattr(storage, 'backends', {}).get('server')
            if isinstance(server, ServerStorage) and server.configured():
                try:
                    directory = server._open_root(create=False)
                except (OSError, Problem):
                    pass
                else:
                    os.close(directory)
            return None
        server = getattr(storage, 'backends', {}).get('server')
        expected = _values(instance_id, host, key, server)
        if (saved is None or storage.office is not office
                or any(saved[name] != value for name, value in expected.items())):
            _fail()
        if storage._selected() not in ('none', 'server'):
            raise InstanceConfigurationError('Gebundene Unternehmensinstanzen benötigen eine eigene Serverablage.')
        directory = None
        try:
            directory = server._open_root(create=False, binding_operation=True)
            verify_storage_marker(directory, expected)
        except (OSError, Problem):
            _fail()
        finally:
            if directory is not None:
                os.close(directory)
        # Every subsequent filesystem write checks the marker on its open root.
        server.instance_identity = expected
        storage.allowed_providers = frozenset(('none', 'server'))
        return {'instance_id': saved['instance_id'], 'public_host': saved['public_host']}


def verify_worker(office):
    """A DB-only import worker must use its bound company's fixed process config."""
    with office.lock:
        saved = identity(office)
        configured = os.environ.get('SMARTPLAN_INSTANCE_ID')
        if saved is None and configured is None:
            return
        if (saved is None or configured != saved['instance_id']
                or os.environ.get('SMARTPLAN_PUBLIC_HOST') != saved['public_host']):
            _fail()


def bind(office, instance_id, host, key, storage):
    """Explicit operator action, idempotent only for the exact same binding.

    Reserve the private storage marker before inserting the database identity.
    A crash may leave a reservation; retrying this exact bind safely finishes it.
    Never overwrite a marker or move existing company data.
    """
    import fcntl
    from business_schema import _tables, _transaction
    server = getattr(storage, 'backends', {}).get('server')
    expected = _values(instance_id, host, key, server)
    if storage.office is not office:
        _fail()
    with _transaction(office):
        if 'business_instance_identity' not in _tables(office):
            raise InstanceConfigurationError('Zuerst die additive Unternehmensinstanz-Migration ausführen.')
        saved = identity(office)
        if saved and any(saved[name] != value for name, value in expected.items()):
            _fail()
        if storage._selected() not in ('none', 'server'):
            raise InstanceConfigurationError('Vor der Bindung eine eigene Serverablage oder keine Ablage auswählen.')
        directory = None
        try:
            directory = server._open_root(binding_operation=True)
            fcntl.flock(directory, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                descriptor = os.open(MARKER, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                                     0o600, dir_fd=directory)
            except FileExistsError:
                verify_storage_marker(directory, expected)
            else:
                try:
                    with os.fdopen(descriptor, 'wb') as target:
                        target.write(canonical(_marker(expected)).encode('utf-8'))
                        target.flush()
                        os.fsync(target.fileno())
                    os.fsync(directory)
                except BaseException:
                    # Retain a partial reservation for explicit operator review, never guess ownership.
                    raise
            if saved is None:
                office.db.execute('''INSERT INTO business_instance_identity
                  (singleton,instance_id,public_host,storage_root,vault_fingerprint,created_at)
                  VALUES(1,?,?,?,?,?)''', (expected['instance_id'], expected['public_host'],
                    expected['storage_root'], expected['vault_fingerprint'], now_iso()))
        except (OSError, Problem):
            _fail()
        finally:
            if directory is not None:
                os.close(directory)
    return verify(office, instance_id, host, key, storage)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('bind', 'check'))
    args = parser.parse_args(argv)
    office = None
    try:
        from online.store import PostgresOffice
        from online.storage import Storage
        instance_id = os.environ.get('SMARTPLAN_INSTANCE_ID')
        if instance_id is None:
            raise InstanceConfigurationError('SMARTPLAN_INSTANCE_ID muss ausdrücklich konfiguriert sein.')
        host = os.environ['SMARTPLAN_PUBLIC_HOST']
        key = Path(os.environ['SMARTPLAN_VAULT_KEY_FILE']).read_bytes().strip()
        office = PostgresOffice(os.environ['SMARTPLAN_DATABASE_DSN'])
        storage = Storage(office, key, host)
        action = bind if args.action == 'bind' else verify
        action(office, instance_id, host, key, storage)
        print('Unternehmensinstanz gebunden.' if args.action == 'bind' else 'Unternehmensinstanz geprüft.')
    except InstanceConfigurationError as error:
        raise SystemExit(str(error)) from None
    except Exception:
        raise SystemExit('Instanzprüfung fehlgeschlagen; geschützte Betreiberkonfiguration und Migration prüfen.') from None
    finally:
        if office is not None:
            office.db.close()


if __name__ == '__main__':
    main()
