#!/usr/bin/env python3
"""Verify and finish a forward-repaired update; never restore or migrate data.

Run a reviewed copy with the installed API Python as root. The CLI uses only
the existing fixed installation. Local tests inject a disposable path set and
external-operation adapter; they cannot redirect the production CLI.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile


class CheckError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise CheckError(message)


def protected(path, *, directory=False, private=False, uid=0):
    info = path.lstat()
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    require(kind(info.st_mode) and info.st_uid == uid
            and not info.st_mode & (0o077 if private else 0o022)
            and (directory or info.st_nlink == 1),
            'Eigentümer, Dateityp oder Rechte zuerst prüfen: ' + str(path))
    return info


def read(path, *, private=False, uid=0):
    info = protected(path, private=private, uid=uid)
    require(info.st_size <= 4 * 1024 * 1024, 'Unerwartete Dateigröße.')
    return path.read_text(encoding='utf-8')


def atomic_write(path, value):
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        Path(temporary).unlink(missing_ok=True)


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@contextmanager
def management_lock(path, *, uid=0):
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == uid
                and info.st_nlink == 1 and not info.st_mode & 0o022,
                'Unbekannte Verwaltungssperre.')
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise CheckError('Andere Verwaltung aktiv; Abschluss nicht begonnen.') from None
        yield
    finally:
        os.close(descriptor)


class Operations:
    def command(self, *args):
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        require(result.returncode == 0, 'Betreiberprüfung fehlgeschlagen: ' + args[0])
        return result.stdout

    def service(self, unit):
        values = self.command('systemctl', 'show', unit,
                              '--property=LoadState,ActiveState,SubState,MainPID,InvocationID')
        return dict(line.split('=', 1) for line in values.splitlines() if '=' in line)

    def start(self, unit):
        self.command('systemctl', 'start', unit)

    def binding(self, pid, dsn, backend):
        # Only compare in memory. Never print process environments or DSNs.
        entries = (Path('/proc') / pid / 'environ').read_bytes().split(b'\0')
        configured = [item for item in entries if item.startswith(b'SMARTPLAN_DATABASE_DSN=')]
        require(configured == [b'SMARTPLAN_DATABASE_DSN=' + dsn.encode()],
                'Laufender Prozess hat eine andere Datenbankkonfiguration.')
        require((Path('/proc') / pid / 'cwd').resolve(strict=True) == backend,
                'Laufender Prozess gehört zu einem anderen Release.')

    def database(self, config, backend):
        sys.path.insert(0, str(backend))
        from online.release import read_environment, validate_dsns
        from psycopg.conninfo import make_conninfo
        dsn = read_environment(config)[3]
        source, _ = validate_dsns(dsn, make_conninfo(dsn, dbname='smartplan_completion_guard'))
        return source['dbname'], dsn

    def readiness(self):
        return json.loads(self.command('curl', '--fail', '--silent', '--show-error',
                         '--max-time', '10', '--noproxy', '*',
                         '-H', 'Host: office.smartplan-hofmann.de',
                         '-H', 'X-Forwarded-Proto: https', 'http://127.0.0.1:8766/ready'))

    def public_status(self):
        # Real TLS, directed to this host's proxy; no DNS/proxy dependency.
        return self.command('curl', '--silent', '--show-error', '--max-time', '10',
                            '--noproxy', '*', '--resolve',
                            'office.smartplan-hofmann.de:443:127.0.0.1',
                            '--output', '/dev/null', '--write-out', '%{http_code}',
                            'https://office.smartplan-hofmann.de/api/v1/projects').strip()

    def packages(self, parser_python, locked):
        script = ('import json,sys; from importlib.metadata import version; '
                  'print(json.dumps({name:version(name) for name in sys.argv[1:]}))')
        return json.loads(self.command(str(parser_python), '-I', '-c', script, *locked))

    def worker_proof(self, unit, state):
        invocation = state['InvocationID']
        require(re.fullmatch(r'[a-f0-9]{32}', invocation) is not None,
                'Aktuelle systemd-Invocation fehlt.')
        common = ('journalctl', '--boot', '--unit', unit, '--no-pager', '--output=json',
                  '_SYSTEMD_INVOCATION_ID=' + invocation)
        doctor = self.command(*common, '--grep', '"ready"', '--lines=10')
        loop = self.command(*common, '_PID=' + state['MainPID'], '--lines=20')
        def messages(value):
            for line in value.splitlines():
                try:
                    yield json.loads(json.loads(line)['MESSAGE'])
                except (ValueError, KeyError, TypeError):
                    continue
        require(any(item.get('ready') is True and item.get('sandboxed') is True
                    and item.get('temporary_storage_bounded') is True
                    and {'net', 'pid', 'mnt'} <= set(item.get('namespaces', []))
                    and {'deu', 'eng'} <= set(item.get('languages', []))
                    for item in messages(doctor)), 'Sandbox-Prüfung der aktuellen Invocation fehlt.')
        require(any(item.get('status') == 'idle' or
                    (isinstance(item.get('id'), str) and item.get('status') in
                     {'needs_review', 'failed', 'applied', 'cancelled'})
                    for item in messages(loop)), 'Laufende Importschleife nicht bestätigt.')


def complete(install, config, lock, parser_python, expected_commit, operations, *, uid=0):
    require(re.fullmatch(r'[a-f0-9]{40}', expected_commit) is not None, 'Vollständiger Zielcommit erforderlich.')
    with management_lock(lock, uid=uid):
        for directory in (install, install / 'releases', config, config / 'updates'):
            protected(directory, directory=True, uid=uid)
        require((install / 'app').is_symlink() and (install / 'venv').is_symlink(),
                'Bekannte Releaseverknüpfungen erforderlich.')
        app = (install / 'app').resolve(strict=True)
        release = app.parent
        require(app.name == 'app' and release.parent == install / 'releases'
                and re.fullmatch(expected_commit[:12] + r'-\d{8}T\d{6}-\d+', release.name) is not None
                and (install / 'venv').resolve(strict=True) == release / 'venv',
                'Aktive Releasepfade passen nicht zum Zielcommit.')
        journal = config / 'updates' / release.name
        for directory in (release, app, app / 'backend', release / 'venv', journal):
            protected(directory, directory=True, uid=uid)
        require(read(install / 'SOURCE_COMMIT', uid=uid).strip() == expected_commit,
                'Installierter Commit stimmt nicht überein.')
        metadata = json.loads(read(journal / 'metadata.json', private=True, uid=uid))
        report = json.loads(read(journal / 'report.json', private=True, uid=uid))
        require(metadata.get('new_commit') == expected_commit
                and metadata.get('new_release') == str(release)
                and metadata.get('update_id') == release.name, 'Journal gehört zu einem anderen Update.')
        for key in ('import_worker_was_active', 'lead_replies_present', 'lead_timer_was_active'):
            require(type(metadata.get(key)) is bool, 'Journal enthält ungültigen Dienstzustand.')
        require(not metadata['lead_timer_was_active'] or metadata['lead_replies_present'],
                'Widersprüchlicher Lead-Timerzustand im Journal.')
        require(metadata['import_worker_was_active'], 'Dieser Abschluss erwartet den zuvor aktiven Importdienst.')
        candidate, source = metadata.get('candidate_database'), metadata.get('source_database')
        require(all(isinstance(name, str) and re.fullmatch(r'[a-z][a-z0-9_]{1,62}', name)
                    for name in (candidate, source)) and candidate != source, 'Ungültige Datenbankzuordnung.')
        phase = journal / 'phase'
        pending = config / 'UPDATE_IN_PROGRESS'
        require(read(phase, private=True, uid=uid).strip() in {'activating', 'active'},
                'Update hat die Aktivierungsgrenze nicht erreicht.')
        if pending.exists() or pending.is_symlink():
            require(read(pending, private=True, uid=uid).strip() in {'activating', 'active'},
                    'Unbekannte globale Updatephase.')
        else:
            previous = json.loads(read(journal / 'forward-verification.json', private=True, uid=uid))
            require(read(phase, private=True, uid=uid).strip() == 'active'
                    and previous.get('commit') == expected_commit
                    and previous.get('update_id') == release.name,
                    'Updatesperre fehlt ohne bestätigten früheren Abschluss.')
        database, dsn = operations.database(config / 'service.env', app / 'backend')
        require(database == candidate, 'Aktive Datenbank ist nicht der Journalkandidat.')
        units = ('smartplan-online.service', 'smartplan-https.service', 'smartplan-plan-import.service')
        states = {unit: operations.service(unit) for unit in units}
        for unit, state in states.items():
            require(state.get('LoadState') == 'loaded' and state.get('ActiveState') == 'active'
                    and state.get('SubState') == 'running'
                    and re.fullmatch(r'[1-9]\d*', state.get('MainPID', '')) is not None,
                    'Dienst läuft nicht stabil: ' + unit)
        for unit in (units[0], units[2]):
            operations.binding(states[unit]['MainPID'], dsn, app / 'backend')
        mode = report.get('business', {}).get('compatibility_mode')
        ready = operations.readiness()
        capabilities = set(ready.get('capabilities', []))
        require(mode in {'business', 'legacy'} and ready.get('status') == 'ok'
                and ready.get('database') == 'ok' and ready.get('schema_version') == 7
                and ready.get('version') == '0.12.0-online-pilot'
                and ready.get('compatibility_mode') == mode
                and {'project_plans', 'offline_plan_access', 'plan_imports', 'plan_deletion',
                     'project_workspace', 'inquiry_intake', 'gmail_intake', 'mail_attachments',
                     'business_integrations'} <= capabilities
                and (('business_suite' in capabilities) == (mode == 'business')),
                'API-/Datenbankbereitschaft stimmt nicht mit dem Migrationsbericht überein.')
        require(operations.public_status() == '401', 'Öffentliche HTTPS-Zugriffsprüfung fehlgeschlagen.')
        locked = {}
        for line in read(app / 'backend/plan_import/requirements.lock', uid=uid).splitlines():
            if line.strip() and not line.startswith('#'):
                name, version = line.strip().split('==')
                require(re.fullmatch(r'[a-zA-Z0-9_.-]+', name) is not None, 'Ungültige Paketliste.')
                locked[name] = version
        require(bool(locked) and operations.packages(parser_python, locked) == locked,
                'Parserpakete stimmen nicht mit dem aktiven Quellstand überein.')
        operations.worker_proof(units[2], states[units[2]])
        timers = {}
        if metadata['lead_replies_present']:
            timer = 'smartplan-lead-replies.timer'
            state = operations.service(timer)
            if metadata['lead_timer_was_active'] and state.get('ActiveState') == 'inactive':
                operations.start(timer)
                state = operations.service(timer)
            require(state.get('LoadState') == 'loaded'
                    and state.get('ActiveState') in {'active', 'inactive'}
                    and (not metadata['lead_timer_was_active'] or state['ActiveState'] == 'active'),
                    'Lead-Antwort-Timer nicht bestätigt.')
            timers[timer] = state['ActiveState']
        # Original backup-timer state was not persisted by the old updater.
        # Preserve the current state; never invent or enable its former intent.
        backup = operations.service('smartplan-online-backup.timer')
        require(backup.get('LoadState') == 'loaded'
                and backup.get('ActiveState') in {'active', 'inactive'}, 'Sicherungstimer zuerst prüfen.')
        timers['smartplan-online-backup.timer'] = backup['ActiveState']
        for unit in units:
            require(operations.service(unit) == states[unit], 'Dienst wurde während der Prüfung neu gestartet.')
        proof = dict(verified_at=datetime.now(timezone.utc).isoformat(), commit=expected_commit,
                     update_id=release.name, candidate_database=candidate, process_bindings_verified=True,
                     services=states, parser_packages=locked, current_invocation_sandbox_and_loop_verified=True,
                     timers=timers, original_backup_timer_state='not_persisted_by_original_updater',
                     public_unauthenticated_projects_status=401, database_ready=True)
        atomic_write(journal / 'forward-verification.json', json.dumps(proof, indent=2, sort_keys=True) + '\n')
        atomic_write(phase, 'active\n')
        if pending.exists():
            atomic_write(pending, 'active\n')
            pending.unlink()
            sync_directory(config)
        return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-commit', required=True)
    args = parser.parse_args()
    try:
        require(os.geteuid() == 0, 'Nur im bestehenden SSH-Fenster als root ausführen.')
        result = complete(Path('/opt/smartplan-online'), Path('/etc/smartplan-online'),
                          Path('/run/lock/smartplan-online-update.lock'),
                          Path('/opt/smartplan-plan-import/venv/bin/python'),
                          args.expected_commit, Operations())
    except Exception as error:
        # Unexpected dependency/JSON/subprocess errors may contain private data.
        message = str(error) if isinstance(error, CheckError) else type(error).__name__
        print('Abschluss nicht bestätigt: ' + message, file=sys.stderr)
        print('Neue Datenbank und Sicherungen beibehalten; nichts zurückspielen.', file=sys.stderr)
        return 1
    print('Update kontrolliert abgeschlossen: ' + result['commit'])
    print('Alle drei Dienste aktiv; aktuelle Sandbox und Datenbankzuordnung bestätigt.')
    print('Sicherungstimer: ' + result['timers']['smartplan-online-backup.timer'])
    print('Journal und Sicherungen bleiben erhalten. UPDATE_IN_PROGRESS ist entfernt.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
