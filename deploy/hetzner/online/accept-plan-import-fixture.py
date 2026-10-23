"""Synthetic PostgreSQL/document checks for the isolated service acceptance run.

Called as the existing peer role by accept-plan-import.sh. This helper never
creates/drops databases or controls services. It accepts only the dedicated
nonce database and acceptance unit, never the production DSN or import queue.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys
import time


def digest(content):
    return hashlib.sha256(content).hexdigest()


def identity(pid):
    try:
        value = Path(f'/proc/{pid}/stat').read_text()
        fields = value[value.rindex(')') + 2:].split()
        return {'pid': pid, 'start_time': fields[19], 'state': fields[0]}
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None


def alive(saved):
    current = identity(saved['pid'])
    return current is not None and current['start_time'] == saved['start_time'] and current['state'] != 'Z'


def synthetic_png(second=False):
    from PIL import Image, ImageDraw, ImageFont
    size = (2200, 2200) if second else (900, 650)
    with Image.new('RGB', size, 'white') as image:
        drawing = ImageDraw.Draw(image)
        drawing.rectangle((35, 35, size[0] - 35, size[1] - 35), outline='black', width=5)
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 30 if second else 48)
        if second:
            # Enough real local OCR work to observe and stop a live parser,
            # without changing the production worker or using a fake executable.
            for row in range(45):
                drawing.text((90, 65 + 45 * row), f'FLOOR 2 ROOM {row + 1} SYNTHETIC ACCEPTANCE', fill='black', font=font)
        else:
            drawing.text((130, 220), 'FLOOR 1 SYNTHETIC', fill='black', font=font)
        output = io.BytesIO()
        image.save(output, format='PNG')
        return output.getvalue()


def control_group(unit):
    value = subprocess.run(
        ['/usr/bin/systemctl', 'show', '--property=ControlGroup', '--value', unit],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3,
    ).stdout.strip()
    if value != '/system.slice/' + unit:
        raise AssertionError('The acceptance unit does not have its own expected system cgroup.')
    return value


def group_processes(group):
    root = Path('/sys/fs/cgroup' + group)
    if not root.exists():
        return []
    processes = set()
    for file in [root / 'cgroup.procs', *root.glob('**/cgroup.procs')]:
        try:
            processes.update(int(line) for line in file.read_text().splitlines())
        except FileNotFoundError:
            pass
    return [saved for pid in sorted(processes) if (saved := identity(pid)) is not None and saved['state'] != 'Z']


def is_parser(saved):
    try:
        args = Path(f"/proc/{saved['pid']}/cmdline").read_bytes().split(b'\0')
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return False
    return len(args) >= 3 and args[1:3] == [b'-m', b'plan_import.sandbox_entry']


def seed(office, *, second):
    from online.plan_imports import CHUNK_SIZE, PlanImports
    email = 'import-acceptance@example.test'
    with office.lock, office.db:
        if second:
            owner = dict(office.db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone())
            projects = office.db.execute('SELECT id FROM projects').fetchall()
            previous = office.db.execute('SELECT status FROM plan_imports').fetchall()
            if len(projects) != 1 or len(previous) != 1 or previous[0]['status'] != 'needs_review':
                raise AssertionError('Second fixture requires the first synthetic review and only its project.')
            project = projects[0]['id']
        else:
            if office.db.execute('SELECT COUNT(*) FROM users').fetchone()[0] != 0:
                raise AssertionError('Acceptance database must have no preexisting users.')
            office.add_user(email, 'Synthetic-acceptance-password-123', 'owner')
            owner = dict(office.db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone())
            project = office.add_project(owner, 'Synthetic import acceptance', 'Synthetic fixture only')
        content = synthetic_png(second)
        imports = PlanImports(office)
        job = imports.create(owner, project, {
            'request_id': ('2' if second else '1') * 32,
            'filename': 'acceptance-second.png' if second else 'acceptance-first.png',
            'media_type': 'image/png', 'size': len(content), 'sha256': digest(content),
            'page': 0, 'title': 'Synthetic acceptance 2' if second else 'Synthetic acceptance 1',
        })
        for index, start in enumerate(range(0, len(content), CHUNK_SIZE)):
            imports.put_chunk(owner, project, job['id'], index, content[start:start + CHUNK_SIZE])
        queued = imports.complete_upload(owner, project, job['id'])
        if queued['status'] != 'queued' or queued['attempts'] != 0:
            raise AssertionError('Synthetic source was not queued without consuming an attempt.')
        return {'job_id': job['id'], 'status': 'queued', 'sha256': digest(content)}


def source_is_unchanged(imports, row):
    if row['filename'] not in ('acceptance-first.png', 'acceptance-second.png'):
        raise AssertionError('Only the two synthetic acceptance sources are permitted.')
    expected = synthetic_png(row['filename'] == 'acceptance-second.png')
    actual = imports.source_bytes(row)
    if actual != expected or digest(actual) != row['sha256']:
        raise AssertionError('The synthetic original or its manifest hash changed.')
    return row['sha256']


def wait_review(office, job_id, timeout):
    from online.plan_imports import PlanImports
    from PIL import Image
    imports = PlanImports(office)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        row = imports._row(job_id)
        if row['status'] == 'failed':
            raise AssertionError('Synthetic parser job failed: ' + str(row['error_code']))
        if row['status'] == 'needs_review':
            source_hash = source_is_unchanged(imports, row)
            artifacts = office.db.execute('SELECT preview,result FROM plan_imports WHERE id=?', (job_id,)).fetchone()
            preview = bytes(artifacts['preview'])
            encoded = artifacts['result'].encode('utf-8')
            result = json.loads(encoded)
            if digest(preview) != row['preview_sha256'] or digest(encoded) != row['result_sha256']:
                raise AssertionError('Published artifact checksums do not match their stored bytes.')
            if result['status'] != 'needs_review' or result['source']['sha256'] != source_hash or result['source']['selected_page'] != 0:
                raise AssertionError('Published recognition is not bound to the original and selected page.')
            if row['attempts'] != 1 or not result['analysis']['line_candidates']:
                raise AssertionError('Expected one real parser attempt with geometric candidates.')
            with Image.open(io.BytesIO(preview)) as image:
                image.load()
                if image.format != 'PNG' or image.size != (result['preview']['width'], result['preview']['height']):
                    raise AssertionError('The published preview is not the declared PNG image.')
            return {'job_id': job_id, 'status': 'needs_review', 'attempts': row['attempts'],
                    'sha256': source_hash, 'preview_sha256': row['preview_sha256'], 'result_sha256': row['result_sha256']}
        time.sleep(0.05)
    raise AssertionError('Synthetic recognition did not reach needs_review within the bounded wait.')


def wait_running(office, job_id, unit, database, timeout):
    from online.plan_imports import PlanImports
    imports = PlanImports(office)
    # Verify the large original before the live observation. Regenerating it
    # after observing a parser could let the job finish before the shell stops
    # the unit; verify_stopped checks the source again after the actual stop.
    source_hash = source_is_unchanged(imports, imports._row(job_id))
    deadline = time.monotonic() + timeout
    group = control_group(unit)
    while time.monotonic() < deadline:
        row = imports._row(job_id)
        processes = group_processes(group)
        parsers = [saved for saved in processes if is_parser(saved) and alive(saved)]
        if row['status'] == 'running' and parsers:
            return {'job_id': job_id, 'database': database, 'unit': unit, 'control_group': group,
                    'sha256': source_hash, 'processes': processes,
                    'parser_count': len(parsers), 'status': 'running'}
        if row['status'] in ('failed', 'needs_review'):
            raise AssertionError('Second job completed before a live parser could be observed and stopped.')
        time.sleep(0.02)
    raise AssertionError('No running synthetic job with a live parser appeared within the bounded wait.')


def verify_stopped(office, job_id, unit, database):
    from online.plan_imports import PlanImports
    encoded = sys.stdin.buffer.read(65537)
    if len(encoded) > 65536:
        raise AssertionError('Unbounded cgroup proof.')
    proof = json.loads(encoded)
    if (proof.get('unit') != unit or proof.get('database') != database or proof.get('job_id') != job_id
            or proof.get('control_group') != '/system.slice/' + unit or not proof.get('parser_count')):
        raise AssertionError('The running proof belongs to another acceptance job or unit.')
    processes = proof.get('processes')
    if not isinstance(processes, list) or not processes or len(processes) > 64:
        raise AssertionError('Missing bounded unit process identities.')
    imports = PlanImports(office)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        row = imports._row(job_id)
        remaining = [saved for saved in processes if alive(saved)]
        current = group_processes(proof['control_group'])
        if row['status'] == 'queued' and not remaining and not current:
            if row['attempts'] != 0 or row['lease_token'] is not None or row['lease_until'] is not None or row['error_code'] is not None:
                raise AssertionError('Graceful service stop did not refund its live lease and attempt.')
            artifacts = office.db.execute('SELECT preview,result FROM plan_imports WHERE id=?', (job_id,)).fetchone()
            if artifacts['preview'] is not None or artifacts['result'] is not None:
                raise AssertionError('An interrupted job published a partial recognition.')
            source_hash = source_is_unchanged(imports, row)
            if source_hash != proof['sha256']:
                raise AssertionError('Source checksum changed across service stop.')
            return {'job_id': job_id, 'status': 'queued', 'attempts': 0, 'sha256': source_hash,
                    'cgroup_empty': True, 'observed_processes_ended': len(processes)}
        time.sleep(0.05)
    raise AssertionError('Service stop did not leave a refunded queued source and an empty cgroup.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dsn', required=True)
    parser.add_argument('--unit', required=True)
    parser.add_argument('--timeout', type=int, default=45)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('seed-first')
    commands.add_parser('seed-second')
    for name in ('wait-review', 'wait-running', 'verify-stopped'):
        commands.add_parser(name).add_argument('--job', required=True)
    args = parser.parse_args()
    if os.environ.get('SMARTPLAN_IMPORT_ACCEPTANCE') != '1' or pwd.getpwuid(os.geteuid()).pw_name != 'smartplan-online':
        parser.error('Explicit synthetic acceptance under the smartplan-online peer identity is required.')
    from psycopg.conninfo import conninfo_to_dict
    parameters = conninfo_to_dict(args.dsn)
    database = parameters.get('dbname', '')
    nonce = database.removeprefix('smartplan_import_accept_')
    if (not re.fullmatch(r'smartplan_import_accept_[a-f0-9]{16,32}', database)
            or parameters.get('host') not in ('/var/run/postgresql', '/run/postgresql')
            or parameters.get('user') != 'smartplan-online' or parameters.get('password')
            or parameters.get('port', '5432') != '5432'
            or set(parameters) - {'dbname', 'host', 'user', 'port'}
            or args.unit != 'smartplan-plan-import-accept-' + nonce + '.service'
            or not 1 <= args.timeout <= 55):
        parser.error('Only the matching nonce database/unit over the local peer socket is accepted.')
    if getattr(args, 'job', None) and not re.fullmatch(r'[a-f0-9]{32}', args.job):
        parser.error('A synthetic import identifier is required.')
    # A script's directory replaces cwd on sys.path. Use the same installed
    # backend as the real unit even when the source helper lives in the checkout.
    sys.path.insert(0, '/opt/smartplan-online/app/backend')
    from online.store import PostgresOffice, migrate
    if args.command == 'seed-first':
        import psycopg
        with psycopg.connect(args.dsn, connect_timeout=5) as connection:
            count = connection.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'").fetchone()[0]
            if count:
                raise AssertionError('The acceptance database must be freshly created and empty.')
        migrate(args.dsn)
    office = PostgresOffice(args.dsn)
    try:
        office.db.execute("SET statement_timeout='2s'")
        if args.command in ('seed-first', 'seed-second'):
            report = seed(office, second=args.command == 'seed-second')
        elif args.command == 'wait-review':
            report = wait_review(office, args.job, args.timeout)
        elif args.command == 'wait-running':
            report = wait_running(office, args.job, args.unit, database, args.timeout)
        else:
            report = verify_stopped(office, args.job, args.unit, database)
        print(json.dumps(report, sort_keys=True))
    finally:
        office.db.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
