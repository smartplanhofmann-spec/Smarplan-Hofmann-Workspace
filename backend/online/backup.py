"""Consistent PostgreSQL dump, exclusive destinations and a SHA-256 sidecar."""
import datetime
import hashlib
import os
from pathlib import Path
import subprocess


def backup(dsn, directory):
    directory = Path(directory)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    filename = 'online-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.dump'
    destination = directory / filename
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            result = subprocess.run(['pg_dump', '--format=custom', '--no-owner', '--no-acl', '--dbname', dsn],
                                    stdout=stream, stderr=subprocess.PIPE, timeout=300)
            if result.returncode:
                raise RuntimeError('PostgreSQL-Sicherung fehlgeschlagen; pg_dump/Verbindung prüfen.')
            stream.flush()
            os.fsync(stream.fileno())
        with destination.open('rb') as stream:
            checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
        descriptor = os.open(str(destination) + '.sha256', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(checksum + '  ' + filename + '\n')
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return destination


if __name__ == '__main__':
    print('PostgreSQL-Sicherung erstellt:', backup(os.environ['SMARTPLAN_DATABASE_DSN'], '/var/lib/smartplan-online/backups'))
