#!/usr/local/bin/python3
"""Synthetic service boundary for the real update-online.sh control-flow tests.

This file is installed only inside the disposable runner container. Business-data
backup/migration is tested separately against real PostgreSQL, not by this stub.
"""
import io
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import types

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


def installer_dsn_preflight(script):
    """Run the real file/DSN guards; replace only libpq/dependency boundaries."""
    def forbidden_database(*unused_args, **unused_kwargs):
        event('forbidden_database_access')
        raise AssertionError('The installer must never connect, migrate or claim a job.')

    def conninfo(dsn):
        result = {}
        for field in shlex.split(dsn):
            key, separator, value = field.partition('=')
            if not separator or key in result:
                raise ValueError('Unsupported synthetic libpq connection string')
            result[key] = value
        return result

    def make_conninfo(dsn, **values):
        return ' '.join(key + '=' + shlex.quote(str(value)) for key, value in {**conninfo(dsn), **values}.items())

    psycopg = types.ModuleType('psycopg')
    psycopg.connect = forbidden_database
    psycopg.sql = types.ModuleType('psycopg.sql')
    sys.modules['psycopg'] = psycopg
    adapter = types.ModuleType('psycopg.conninfo')
    adapter.conninfo_to_dict, adapter.make_conninfo = conninfo, make_conninfo
    sys.modules['psycopg.conninfo'] = adapter
    package = types.ModuleType('online')
    package.__path__ = []
    sys.modules['online'] = package
    dependencies = {'backup': ('backup',), 'restore': ('restore_dump',),
                    'store': ('migrate', 'PostgresOffice'), 'plan_imports': ('validate_integrity',)}
    for name, attributes in dependencies.items():
        module = types.ModuleType('online.' + name)
        for attribute in attributes:
            setattr(module, attribute, forbidden_database)
        module.SCHEMA_VERSION = 7
        sys.modules[module.__name__] = module
    spec = importlib.util.spec_from_file_location('online.release', '/source/backend/online/release.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    event('installer_dsn_preflight')
    exec(compile(script, '<actual-installer-preflight>', 'exec'), {'__name__': '__main__'})


if command == 'git':
    if 'status' in args:
        if scenario['fault'] == 'install_dirty':
            print(' M backend/online/import_worker.py')
        sys.exit(0)
    if 'rev-parse' in args:
        print('a' * 40)
        sys.exit(0)
    if 'archive' in args:
        event('archive', paths=args[args.index('archive') + 2:])
        with tarfile.open(fileobj=sys.stdout.buffer, mode='w|') as archive:
            for name, data in {'backend/generation': b'new\n', 'backend/online/requirements.lock': b'',
                               'backend/online/release.py': b'# Synthetic boundary\n',
                               'backend/business_schema.py': b'# Synthetic boundary\n',
                               'web/office/index.html': b'<title>Synthetic office fixture</title>'}.items():
                info = tarfile.TarInfo(name)
                info.size, info.mode = len(data), 0o644
                archive.addfile(info, io.BytesIO(data))
        sys.exit(0)
elif command == 'runuser':
    event('runuser', role=args[args.index('-u') + 1])
    os.environ['SMARTPLAN_FIXTURE_RUNUSER_ROLE'] = args[args.index('-u') + 1]
    if '/usr/bin/env' in args and '-i' in args:
        # The installer doctor really runs as the service UID; setpriv is real.
        os.execv('/usr/sbin/runuser', ['/usr/sbin/runuser', *args])
    command_index = args.index('--') + 1
    os.execvp(args[command_index], args[command_index:])
elif command == 'systemctl':
    action = args[0]
    services = read_state()
    unit = next((a for a in args if a.endswith(('.service', '.timer'))), '')
    if action == 'is-active':
        if unit == 'smartplan-plan-import.service' and scenario['fault'] == 'import_worker_late_start':
            services[unit] = True
            save_state(services)
            event('import_worker_late_start')
            sys.exit(3)
        sys.exit(0 if services.get(unit, False) else 3)
    if action == 'show':
        property_name = next(arg.split('=', 1)[1] for arg in args if arg.startswith('--property='))
        event('systemctl_show', unit=unit, property=property_name)
        fault = scenario['fault']
        if fault.startswith('worker_unit_'):
            fault = fault.removeprefix('worker_') if unit == 'smartplan-plan-import.service' else 'none'
        if fault.startswith('lead_unit_'):
            fault = fault.removeprefix('lead_') if unit.startswith('smartplan-lead-replies.') else 'none'
        if property_name == 'ActiveState':
            if unit == 'smartplan-plan-import.service':
                print('activating' if services.get('import_worker_restart_pending') else
                      'active' if services.get(unit, False) else 'inactive')
            elif unit == 'smartplan-lead-replies.service':
                print('activating' if services.get('lead_replies_restart_pending') else
                      'active' if services.get(unit, False) else 'inactive')
            else:
                print('active' if services.get(unit, False) else 'inactive')
        elif property_name == 'LoadState':
            print('loaded' if Path('/etc/systemd/system', unit).exists() or fault == 'unit_vendor'
                  else 'not-found')
        elif property_name == 'FragmentPath':
            print('/run/systemd/system/unknown.service' if fault == 'unit_fragment'
                  else '/etc/systemd/system/' + unit)
        elif property_name == 'DropInPaths':
            print('/etc/systemd/system/fixture-override.conf' if fault == 'unit_dropin' else '')
        elif property_name == 'Environment':
            print('FIXTURE_PRIVATE_SETTING=must-not-appear' if fault == 'unit_environment' else '')
        elif property_name == 'EnvironmentFiles':
            print('/untrusted/FIXTURE_PRIVATE_SETTING (ignore_errors=no)' if fault == 'unit_envfile'
                  else '/etc/smartplan-online/service.env (ignore_errors=no)')
        elif property_name == 'KillMode':
            print('process' if fault == 'unit_killmode' else 'control-group')
        elif property_name == 'SendSIGKILL':
            print('no' if fault == 'unit_no_sigkill' else 'yes')
        elif property_name == 'TimeoutStopUSec':
            print('infinity' if fault == 'unit_stop_timeout' else
                  '10s' if unit == 'smartplan-lead-replies.service' else '20s')
        else:
            raise SystemExit('Unexpected systemd property: ' + property_name)
        sys.exit(0)
    event('systemctl', action=action, unit=unit, generation=generation())
    if action in ('reset-failed', 'daemon-reload'):
        sys.exit(0)
    if action in ('start', 'stop'):
        if unit.startswith('smartplan-lead-replies.'):
            if action == 'stop' and scenario['fault'] == 'lead_stop' and unit.endswith('.service'):
                sys.exit(1)
            if action == 'stop' and ((scenario['fault'] == 'lead_false_stop' and unit.endswith('.service')) or
                                      (scenario['fault'] == 'lead_timer_false_stop' and unit.endswith('.timer'))):
                sys.exit(0)
            if action == 'start' and generation() == 'new' and scenario['fault'] == 'lead_timer_start_new':
                sys.exit(1)
            if action == 'stop' and unit.endswith('.service'):
                services['lead_replies_restart_pending'] = False
        if action == 'stop' and unit == 'smartplan-online.service' and scenario['fault'] == 'service_stop':
            event('failed_service_stop')
            sys.exit(1)
        if unit == 'smartplan-plan-import.service':
            if action == 'stop' and scenario['fault'] == 'import_worker_stop':
                event('failed_import_worker_stop')
                sys.exit(1)
            if action == 'stop' and scenario['fault'] == 'import_worker_false_stop':
                event('unconfirmed_import_worker_stop')
                sys.exit(0)
            if action == 'start' and ((generation() == 'new' and scenario['fault'] == 'import_worker_start_new') or
                                      (generation() == 'old' and scenario['fault'] == 'import_worker_start_old')):
                event('failed_import_worker_start', generation=generation())
                sys.exit(1)
            if action == 'stop':
                services['import_worker_restart_pending'] = False
            elif generation() == 'new' and scenario['fault'] == 'import_worker_write_then_timer_failure':
                database = active_database()
                path = STATE / 'databases' / (database + '.json')
                rows = json.loads(path.read_text())
                if 'accepted-by-worker-after-activation' not in rows:
                    rows.append('accepted-by-worker-after-activation')
                    path.write_text(json.dumps(rows))
                event('import_worker_write', database=database)
        if (action == 'start' and unit == 'smartplan-online-backup.timer' and generation() == 'new' and
                scenario['fault'] == 'import_worker_write_then_timer_failure'):
            event('failed_timer_start')
            sys.exit(1)
        services[unit] = action == 'start'
        save_state(services)
        if (action == 'stop' and unit == 'smartplan-plan-import.service' and
                scenario['fault'] == 'terminate_after_import_worker_stop' and
                not (STATE / 'termination-sent').exists()):
            (STATE / 'termination-sent').write_text('sent')
            os.kill(os.getppid(), signal.SIGTERM)
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
    if generation() == 'new' and scenario['fault'] in ('readiness', 'import_worker_start_old'):
        sys.exit(22)
    event('ready_probe', generation=generation(), database=active_database())
    schema = 6 if scenario['fault'] == 'obsolete_schema' else 7
    capabilities = ['project_plans', 'offline_plan_access', 'plan_imports', 'plan_deletion',
                    'project_workspace', 'inquiry_intake', 'gmail_intake', 'mail_attachments', 'business_integrations', 'business_suite']
    if scenario['fault'] == 'missing_mail_attachments':
        capabilities.remove('mail_attachments')
    if scenario['fault'] == 'missing_business_integrations':
        capabilities.remove('business_integrations')
    if scenario['fault'] == 'missing_business_suite':
        capabilities.remove('business_suite')
    mode = 'legacy' if scenario['fault'] == 'preserve_legacy_mode' else 'business'
    if mode == 'legacy':
        capabilities.remove('business_suite')
    version = '0.11.0-online-pilot' if scenario['fault'] == 'obsolete_version' else '0.12.0-online-pilot'
    print(json.dumps({'status': 'ok', 'database': 'ok', 'version': version if generation() == 'new' else '0.10.0-online-pilot',
                      'schema_version': schema if generation() == 'new' else 5,
                      'compatibility_mode': mode,
                      'capabilities': capabilities if generation() == 'new' else []}))
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
    assert '--owner=smartplan-migrator' in args
    event('createdb', database=database, owner='smartplan-migrator')
    (STATE / 'databases' / (database + '.json')).write_text('[]')
    sys.exit(0)
elif command == 'caddy':
    event('caddy_validate')
    sys.exit(0)
elif command == 'apt-get':
    event('package', action=args[0], packages=args[1:])
    if args[0] == 'install':
        (STATE / 'installed-system-packages').write_text('Synthetic shared packages remain installed.\n')
        if scenario['fault'] == 'install_foreign_runtime':
            runtime = Path('/opt/smartplan-plan-import')
            runtime.mkdir()
            (runtime / 'keep.txt').write_text('Foreign operator object.\n')
    sys.exit(1 if scenario['fault'] == 'install_apt_' + args[0] else 0)
elif command == 'systemd-analyze':
    event('unit_verify', path=args[-1])
    sys.exit(1 if scenario['fault'] == 'install_verify' else 0)
elif command == 'install':
    if scenario['fault'] == 'install_partial_unit' and args[-1] == '/etc/systemd/system/smartplan-plan-import.service':
        Path(args[-1]).write_text('Synthetic interrupted unit copy.\n')
        event('partial_unit_install')
        sys.exit(1)
    if scenario['fault'] == 'install_terminate_after_unit' and args[-1] == '/etc/systemd/system/smartplan-plan-import.service':
        result = subprocess.run(['/usr/bin/install', *args])
        if result.returncode == 0:
            os.kill(os.getppid(), signal.SIGTERM)
        sys.exit(result.returncode)
    os.execv('/usr/bin/install', ['/usr/bin/install', *args])
elif command == 'mkdir':
    result = subprocess.run(['/usr/bin/mkdir', *args])
    if (result.returncode == 0 and args[-1] == '/opt/smartplan-plan-import'
            and scenario['fault'] == 'install_terminate_after_mkdir'):
        os.kill(os.getppid(), signal.SIGTERM)
    sys.exit(result.returncode)
elif command == 'sleep':
    sys.exit(0)
elif command in ('python', 'python3', 'python3.12'):
    if args[:2] == ['-m', 'venv']:
        event('venv', path=args[2])
        binary = Path(args[2]) / 'bin/python'
        binary.parent.mkdir(parents=True)
        binary.symlink_to('/test-bin/command_stub.py')
        sys.exit(1 if scenario['fault'] == 'install_venv' else 0)
    if args[:2] in (['-m', 'pip'], ['-m', 'compileall']):
        if args[1] == 'pip':
            event('pip', action=args[2], flags=args[3:], interpreter=sys.argv[0])
            if args[2] == 'check' and scenario['fault'] == 'install_foreign_unit':
                Path('/etc/systemd/system/smartplan-plan-import.service').write_text('Foreign operator object.\n')
            if scenario['fault'] == 'install_pip_' + args[2]:
                sys.exit(1)
        sys.exit(0)
    if args[:2] == ['-m', 'online.import_worker']:
        status = Path('/proc/self/status').read_text()
        nnp = int(next(line.split(':', 1)[1].strip() for line in status.splitlines() if line.startswith('NoNewPrivs:')))
        evidence = {'uid': os.getuid(), 'gid': os.getgid(), 'no_new_privileges': nnp, 'arguments': args,
                    'environment_names': sorted(os.environ),
                    'unit_exists': Path('/etc/systemd/system/smartplan-plan-import.service').exists()}
        Path('/test-state/doctor/evidence.json').write_text(json.dumps(evidence))
        assert '--doctor' in args and '--watch' not in args and '--once' not in args
        assert os.getuid() == 2001 and nnp == 1, 'Real service UID and NoNewPrivileges required'
        assert 'SMARTPLAN_DATABASE_DSN' not in os.environ and 'FIXTURE_PRIVATE_SETTING' not in os.environ
        print(json.dumps({'ready': scenario['fault'] != 'install_doctor'}))
        sys.exit(1 if scenario['fault'] == 'install_doctor' else 0)
    if args[:2] == ['-m', 'online.release']:
        action = args[2]
        values = [arg for arg in args[3:] if arg != '--privileged-operator']
        flags = dict(zip(values[::2], values[1::2]))
        if '--privileged-operator' in args:
            flags['--privileged-operator'] = True
        event('helper', action=action, flags=flags, role=os.environ.get('SMARTPLAN_FIXTURE_RUNUSER_ROLE'))
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
            if scenario['fault'] == 'activating_marker' and flags['--value'] == 'activating':
                event('failed_activating_marker')
                sys.exit(1)
            sys.exit(0)
        if action == 'validate':
            assert not read_state()['smartplan-online.service'], 'DB inspection before service stop'
            assert not read_state().get('smartplan-plan-import.service'), 'DB inspection before importworker stop'
            assert not read_state().get('import_worker_restart_pending'), 'DB inspection with pending importworker restart'
            assert read_state().get('gate'), 'DB inspection without public gate'
            sys.exit(0)
        if action == 'security':
            assert os.environ['SMARTPLAN_FIXTURE_RUNUSER_ROLE'] == 'postgres'
            assert read_state()['gate'] and not read_state()['smartplan-online.service']
            assert not read_state().get('smartplan-plan-import.service')
            assert not read_state().get('smartplan-online-backup.timer')
            assert not read_state().get('smartplan-lead-replies.timer')
            assert not read_state().get('smartplan-lead-replies.service')
            assert not read_state().get('lead_replies_restart_pending')
            sys.exit(1 if scenario['fault'] == 'business_security' else 0)
        if action == 'privacy-configure':
            assert not read_state()['smartplan-online.service'] and read_state()['gate']
            installer_dsn_preflight('from online.release import configure_privacy_environment\n'
                                    'configure_privacy_environment("/etc/smartplan-online/service.env")\n')
            print(json.dumps({'configured': True}))
            sys.exit(0)
        if action == 'privacy-init':
            assert os.environ['SMARTPLAN_FIXTURE_RUNUSER_ROLE'] == 'smartplan-online'
            assert all(os.environ.get(name) for name in ('SMARTPLAN_PRIVACY_CHECKPOINT_FILE',
                       'SMARTPLAN_PRIVACY_CHECKPOINT_KEY_FILE', 'SMARTPLAN_PRIVACY_INSTALLATION_ID'))
            assert not read_state()['smartplan-online.service'] and read_state()['gate']
            if scenario['fault'] == 'privacy_checkpoint':
                raise SystemExit('Synthetic missing/current checkpoint failure')
            print(json.dumps({'generation': 0, 'digest': 'a' * 64}))
            sys.exit(0)
        if action == 'prepare':
            assert flags.get('--privileged-operator') is True
            assert os.environ['SMARTPLAN_FIXTURE_RUNUSER_ROLE'] == 'postgres'
            assert flags['--backup-directory'].startswith('/var/lib/smartplan-online-operator/updates/')
            assert not read_state()['smartplan-online.service']
            assert not read_state().get('smartplan-plan-import.service'), 'DB clone before importworker stop'
            assert not read_state().get('import_worker_restart_pending'), 'DB clone with pending importworker restart'
            assert not read_state().get('smartplan-lead-replies.timer'), 'DB clone before lead timer stop'
            assert not read_state().get('smartplan-lead-replies.service'), 'DB clone before lead worker stop'
            assert not read_state().get('lead_replies_restart_pending'), 'DB clone with pending lead worker restart'
            candidate = flags['--candidate']
            original = json.loads((STATE / 'databases/smartplan_online.json').read_text())
            (STATE / 'databases' / (candidate + '.json')).write_text(json.dumps(original))
            backup = Path(flags['--backup-directory']) / 'fixture.dump'
            backup.write_text(json.dumps(original))
            (Path(str(backup) + '.sha256')).write_text('synthetic-backup\n')
            Path(flags['--output']).write_text(json.dumps({'backup': str(backup), 'source_schema': 6, 'target_schema': 7,
                'business': {'compatibility_mode': 'legacy' if scenario['fault'] == 'preserve_legacy_mode' else 'business'}}))
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
        if 'smartplan_import_install_check' in script:
            installer_dsn_preflight(script)
            sys.exit(0)
        if 'read_environment, validate_dsns' in script:
            installer_dsn_preflight(script)
            sys.exit(0)
        if len(args) == 5:
            source, target, mode, group = args[1:]
            shutil.copyfile(source, target)
            os.chmod(target, int(mode, 8))
            event('atomic_copy', source=source, target=target)
            sys.exit(0)
        if len(args) == 12:
            path, update_id, candidate, previous_app, previous_venv, release, old_commit, new_commit, import_worker_active, lead_present, lead_timer_active = args[1:]
            Path(path).write_text(json.dumps({'update_id': update_id, 'candidate_database': candidate,
                'source_database': active_database(), 'previous_app': previous_app, 'previous_venv': previous_venv,
                'previous_app_was_link': Path('/opt/smartplan-online/app').is_symlink(),
                'previous_venv_was_link': Path('/opt/smartplan-online/venv').is_symlink(),
                'new_release': release, 'original_commit': old_commit, 'new_commit': new_commit,
                'import_worker_was_active': import_worker_active == '1',
                'lead_replies_present': lead_present == '1', 'lead_timer_was_active': lead_timer_active == '1'}))
            event('journal_metadata', path=path)
            sys.exit(0)
        event('inline_preflight')
        sys.exit(0)

raise SystemExit('Unhandled synthetic boundary: ' + command + ' ' + repr(args))
