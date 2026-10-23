#!/usr/local/bin/python3
"""Synthetic service boundary for the real update-online.sh control-flow tests.

This file is installed only inside the disposable runner container. Business-data
backup/migration is tested separately against real PostgreSQL, not by this stub.
"""
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tarfile

STATE = Path('/test-state')
args = sys.argv[1:]
command = Path(sys.argv[0]).name
scenario = json.loads((STATE / 'scenario.json').read_text())


def event(name, **data):
    fd = os.open(STATE / 'events.jsonl', os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, (json.dumps({'event': name, **data}) + '\n').encode())
    finally:
        os.close(fd)


def read_state():
    return json.loads((STATE / 'services.json').read_text())


def save_state(value):
    (STATE / 'services.json').write_text(json.dumps(value))


def active_database():
    line = next(line for line in Path('/etc/smartplan-online/service.env').read_text().splitlines()
                if line.startswith('SMARTPLAN_DATABASE_DSN='))
    dsn = shlex.split(line.split('=', 1)[1])[0]
    return next(field.split('=', 1)[1] for field in dsn.split() if field.startswith('dbname='))


def generation():
    path = Path('/opt/smartplan-online/app/backend/generation')
    return path.read_text().strip() if path.exists() else 'temporarily-absent'


def append_public_write():
    database = active_database()
    path = STATE / 'databases' / (database + '.json')
    rows = json.loads(path.read_text())
    if 'accepted-after-publication' not in rows:
        rows.append('accepted-after-publication')
        path.write_text(json.dumps(rows))
    event('public_write', database=database)


if command == 'git':
    if 'status' in args:
        sys.exit(0)
    if 'rev-parse' in args:
        print('a' * 40)
        sys.exit(0)
    if 'archive' in args:
        with tarfile.open(fileobj=sys.stdout.buffer, mode='w|') as archive:
            for name, data in {'backend/generation': b'new\n', 'backend/online/requirements.lock': b''}.items():
                info = tarfile.TarInfo(name)
                info.size, info.mode = len(data), 0o644
                archive.addfile(info, io.BytesIO(data))
        sys.exit(0)
elif command == 'runuser':
    event('runuser', role=args[args.index('-u') + 1])
    command_index = args.index('--') + 1
    os.execvp(args[command_index], args[command_index:])
elif command == 'systemctl':
    action = args[0]
    services = read_state()
    unit = next((a for a in args if a.endswith(('.service', '.timer'))), '')
    if action == 'is-active':
        sys.exit(0 if services.get(unit, False) else 3)
    if action == 'show':
        property_name = next(arg.split('=', 1)[1] for arg in args if arg.startswith('--property='))
        event('systemctl_show', unit=unit, property=property_name)
        if property_name == 'ActiveState':
            print('inactive')
        elif property_name == 'FragmentPath':
            print('/run/systemd/system/unknown.service' if scenario['fault'] == 'unit_fragment'
                  else '/etc/systemd/system/' + unit)
        elif property_name == 'DropInPaths':
            print('/etc/systemd/system/fixture-override.conf' if scenario['fault'] == 'unit_dropin' else '')
        elif property_name == 'Environment':
            print('FIXTURE_PRIVATE_SETTING=must-not-appear' if scenario['fault'] == 'unit_environment' else '')
        else:
            raise SystemExit('Unexpected systemd property: ' + property_name)
        sys.exit(0)
    event('systemctl', action=action, unit=unit, generation=generation())
    if action in ('reset-failed', 'daemon-reload'):
        sys.exit(0)
    if action in ('start', 'stop'):
        if action == 'stop' and unit == 'smartplan-online.service' and scenario['fault'] == 'service_stop':
            event('failed_service_stop')
            sys.exit(1)
        services[unit] = action == 'start'
        save_state(services)
        sys.exit(0)
    if action in ('reload', 'restart'):
        if action == 'restart':
            services[unit] = True
        maintenance = '# FLOW_TEST_MAINTENANCE' in Path('/etc/smartplan-https/Caddyfile').read_text()
        services['gate'] = maintenance
        save_state(services)
        event('gate', closed=maintenance)
        if not maintenance and generation() == 'new':
            append_public_write()
            if scenario['fault'] == 'reload_after_activation':
                sys.exit(1)
        sys.exit(0)
elif command == 'curl':
    services = read_state()
    if any('https://' in a for a in args):
        if services.get('gate'):
            print('200' if scenario['fault'] == 'gate_probe' else '503', end='')
        else:
            print('500' if scenario['fault'] == 'public_probe' and generation() == 'new' else '401', end='')
        sys.exit(0)
    if not services.get('smartplan-online.service'):
        sys.exit(7)
    if generation() == 'new' and scenario['fault'] == 'readiness':
        sys.exit(22)
    event('ready_probe', generation=generation(), database=active_database())
    print(json.dumps({'status': 'ok', 'database': 'ok', 'schema_version': 2 if generation() == 'new' else 1,
                      'capabilities': ['project_plans', 'offline_plan_access'] if generation() == 'new' else []}))
    sys.exit(0)
elif command == 'mv':
    failed = False
    if not (STATE / 'mv-fault-used').exists():
        if scenario['fault'] == 'move_app' and args[-2] == '/opt/smartplan-online/app' and '/app.before-' in args[-1]:
            failed = True
        if scenario['fault'] == 'move_venv' and args[-2] == '/opt/smartplan-online/venv' and '/venv.before-' in args[-1]:
            failed = True
        if scenario['fault'] == 'switch_link' and '/app.update-' in args[-2] and args[-1] == '/opt/smartplan-online/app':
            failed = True
    if failed:
        (STATE / 'mv-fault-used').touch()
        event('failed_mv', paths=args[-2:])
        sys.exit(1)
    os.execv('/usr/bin/mv', ['/usr/bin/mv', *args])
elif command == 'psql':
    event('postgres_data_directory')
    print('/var/lib/postgresql/16/main')
    sys.exit(0)
elif command == 'createdb':
    database = args[-1]
    event('createdb', database=database)
    (STATE / 'databases' / (database + '.json')).write_text('[]')
    sys.exit(0)
elif command == 'caddy':
    event('caddy_validate')
    sys.exit(0)
elif command == 'sleep':
    sys.exit(0)
elif command in ('python', 'python3'):
    if args[:2] == ['-m', 'venv']:
        binary = Path(args[2]) / 'bin/python'
        binary.parent.mkdir(parents=True)
        binary.symlink_to('/test-bin/command_stub.py')
        sys.exit(0)
    if args[:2] in (['-m', 'pip'], ['-m', 'compileall']):
        sys.exit(0)
    if args[:2] == ['-m', 'online.release']:
        action = args[2]
        flags = dict(zip(args[3::2], args[4::2]))
        event('helper', action=action, flags=flags)
        if action == 'size':
            print('1024')
            sys.exit(0)
        if action == 'capacity':
            sys.exit(1 if scenario['fault'] == 'capacity' else 0)
        if action == 'maintenance':
            Path(flags['--output']).write_text('# FLOW_TEST_MAINTENANCE\n' + Path(flags['--path']).read_text())
            sys.exit(0)
        if action == 'phase':
            Path(flags['--path']).write_text(flags['--value'] + '\n')
            sys.exit(0)
        if action == 'validate':
            assert not read_state()['smartplan-online.service'], 'DB inspection before service stop'
            assert read_state().get('gate'), 'DB inspection without public gate'
            sys.exit(0)
        if action == 'prepare':
            assert not read_state()['smartplan-online.service']
            candidate = flags['--candidate']
            original = json.loads((STATE / 'databases/smartplan_online.json').read_text())
            (STATE / 'databases' / (candidate + '.json')).write_text(json.dumps(original))
            backup = Path(flags['--backup-directory']) / 'fixture.dump'
            backup.write_text(json.dumps(original))
            (Path(str(backup) + '.sha256')).write_text('synthetic-backup\n')
            Path(flags['--output']).write_text(json.dumps({'backup': str(backup), 'source_schema': 1, 'target_schema': 2}))
            sys.exit(0)
        if action == 'configure':
            path = Path(flags['--path'])
            lines = path.read_text().splitlines(keepends=True)
            path.write_text(''.join("SMARTPLAN_DATABASE_DSN='dbname=" + flags['--candidate'] + " user=smartplan-online host=/var/run/postgresql'\n"
                                    if line.startswith('SMARTPLAN_DATABASE_DSN=') else line for line in lines))
            sys.exit(0)
    if args and args[0] == '-c':
        # Run the real JSON assertions; passing the fixture is not assumed.
        os.execv('/usr/local/bin/python3', ['/usr/local/bin/python3', *args])
    if args and args[0] == '-':
        script = sys.stdin.read()
        if len(args) == 5:
            source, target, mode, group = args[1:]
            shutil.copyfile(source, target)
            os.chmod(target, int(mode, 8))
            event('atomic_copy', source=source, target=target)
            sys.exit(0)
        if len(args) == 9:
            path, update_id, candidate, previous_app, previous_venv, release, old_commit, new_commit = args[1:]
            Path(path).write_text(json.dumps({'update_id': update_id, 'candidate_database': candidate,
                'source_database': active_database(), 'previous_app': previous_app, 'previous_venv': previous_venv,
                'previous_app_was_link': Path('/opt/smartplan-online/app').is_symlink(),
                'previous_venv_was_link': Path('/opt/smartplan-online/venv').is_symlink(),
                'new_release': release, 'original_commit': old_commit, 'new_commit': new_commit}))
            event('journal_metadata', path=path)
            sys.exit(0)
        event('inline_preflight')
        sys.exit(0)

raise SystemExit('Unhandled synthetic boundary: ' + command + ' ' + repr(args))
