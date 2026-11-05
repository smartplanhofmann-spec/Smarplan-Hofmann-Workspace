"""Remaining exact CI online commands in an owned disposable PG16 cluster. No credentials are written to evidence."""
from pathlib import Path
import hashlib
import json
import os
import secrets
import shlex
import socket
import subprocess
import time
import uuid

import psycopg

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parent
PORT = 55435
DOCKER = ['docker', '--host=unix:///var/run/docker.sock']
name = 'smartplan-project-replay-review-' + uuid.uuid4().hex[:12]
environment = dict(os.environ)
for key in ('DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH'):
    environment.pop(key, None)
environment['POSTGRES_PASSWORD'] = secrets.token_urlsafe(32)
dsn = f"host=127.0.0.1 port={PORT} dbname=smartplan_check user=postgres password={environment['POSTGRES_PASSWORD']}"
paths = [str(p.relative_to(ROOT)) for p in (ROOT/'backend').rglob('*.py') if '.venv' not in p.parts]

def hashes():
    return {path: hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in paths}
def docker(*args):
    return subprocess.run(DOCKER+list(args), env=environment, text=True, capture_output=True)

with socket.socket() as probe:
    probe.bind(('127.0.0.1', PORT))
before = hashes()
image = docker('image', 'inspect', 'postgres:16', '--format', '{{.Id}}')
assert image.returncode == 0
started = False
result = None
cleanup = None
start = time.monotonic()
try:
    created = docker('run', '--detach', '--rm', '--name', name,
        '--publish', f'127.0.0.1:{PORT}:5432', '--env', 'POSTGRES_PASSWORD',
        '--env', 'POSTGRES_DB=smartplan_check', 'postgres:16')
    if created.returncode:
        raise RuntimeError('Disposable PostgreSQL container could not start.')
    started = True
    deadline = time.monotonic()+45
    while True:
        try:
            with psycopg.connect(dsn, connect_timeout=2) as connection:
                version = connection.execute('SHOW server_version').fetchone()[0]
            break
        except psycopg.Error:
            if time.monotonic() >= deadline:
                raise RuntimeError('Disposable PostgreSQL did not become ready.') from None
            time.sleep(.25)
    assert version.startswith('16.')
    test_environment = dict(os.environ)
    test_environment['SMARTPLAN_TEST_DSN'] = dsn
    test_environment['PYTHONPATH'] = 'backend'
    workflow=(ROOT/'.github/workflows/checks.yml').read_text().splitlines()
    commands=[];collect=False
    for line in workflow:
        if "-p 'test_business*.py'" in line:collect=True;continue
        if collect and line.lstrip().startswith('- name:'):break
        if collect and line.strip().startswith('python -m unittest '):commands.append(shlex.split(line.strip()))
    assert len(commands)==13,len(commands)
    outcomes=[]
    for index,command in enumerate(commands):
        command[0]='/tmp/smartplan-backend-verified/bin/python'
        tick=time.monotonic()
        completed=subprocess.run(command,cwd=ROOT,env=test_environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=900)
        log=completed.stdout.replace(environment['POSTGRES_PASSWORD'],'[redacted-disposable-password]')
        name=f'{index+1:02d}-'+command[-2] if command[-1]=='-v' else f'{index+1:02d}-'+command[-1]
        name=name.replace('/','_').replace('*','all')
        (EVIDENCE/(name+'.txt')).write_text(log)
        outcomes.append(dict(command=['python',*command[1:]],exit_code=completed.returncode,duration_seconds=round(time.monotonic()-tick,3),log=name+'.txt'))
        (EVIDENCE/'commands.json').write_text(json.dumps(outcomes,indent=2)+'\n')
        print(str(index+1)+'/13 '+name+': '+str(completed.returncode),flush=True)
    result=subprocess.CompletedProcess([],int(any(row['exit_code'] for row in outcomes)))

finally:
    if started:
        cleanup = docker('rm', '--force', name)
    metadata = dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(), exit_code=None if result is None else result.returncode,
        postgres_version=locals().get('version'), port=PORT, image_id=image.stdout.strip(),
        duration_seconds=round(time.monotonic()-start, 3),
        before_sha256=before, after_sha256=hashes(),
        cleanup_exit_code=None if cleanup is None else cleanup.returncode,
        credentials_saved=False)
    (EVIDENCE/'postgres-result.json').write_text(json.dumps(metadata, indent=2)+'\n')
    environment.pop('POSTGRES_PASSWORD', None)
print(json.dumps({key: metadata[key] for key in ('exit_code', 'postgres_version', 'duration_seconds', 'cleanup_exit_code')}))
raise SystemExit(1 if result is None else result.returncode)
