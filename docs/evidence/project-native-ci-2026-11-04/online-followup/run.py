"""Own network-none PG16 namespace; never bind or inspect host port 55433."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import uuid

ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
DOCKER=['docker','--host=unix:///var/run/docker.sock']
env=dict(os.environ)
for key in ('DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'):env.pop(key,None)
env['POSTGRES_PASSWORD']=secrets.token_urlsafe(32)
name='smartplan-private-online-'+uuid.uuid4().hex[:12]
def docker(*args):return subprocess.run(DOCKER+list(args),env=env,text=True,capture_output=True,timeout=60)
paths=[p for p in subprocess.check_output(['git','ls-files','backend'],cwd=ROOT,text=True).splitlines() if p.endswith('.py')]
def hashes():return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
before=hashes();outcomes=[];started=False;cleanup=None;tick=time.monotonic()
assert docker('image','inspect','postgres:16','--format','{{.Id}}').returncode==0
try:
 result=docker('run','--detach','--rm','--network','none','--name',name,'--env','POSTGRES_PASSWORD','--env','POSTGRES_DB=smartplan_check','postgres:16','postgres','-p','55433','-c','listen_addresses=127.0.0.1')
 if result.returncode:raise RuntimeError('Own network-none PostgreSQL could not start')
 started=True
 for index in range(160):
  if docker('exec',name,'pg_isready','-h','127.0.0.1','-p','55433','-U','postgres','-d','smartplan_check').returncode==0:break
  time.sleep(.25)
 else:raise RuntimeError('Own private PostgreSQL did not become ready')
 pid=int(docker('inspect',name,'--format','{{.State.Pid}}').stdout.strip())
 assert pid>1 and os.readlink(f'/proc/{pid}/ns/net')!=os.readlink('/proc/self/ns/net')
 version=docker('exec','--user','postgres',name,'psql','-p','55433','-Atc','SHOW server_version').stdout.strip()
 test_env=dict(os.environ,PYTHONPATH='backend',SMARTPLAN_TEST_DSN='host=127.0.0.1 port=55433 dbname=smartplan_check user=postgres password='+env['POSTGRES_PASSWORD'])
 commands=[['-m','unittest','-v','online.test_year_values_full_financial_restore_pg'],['-m','unittest','discover','-s','backend/online','-p','test_provisioning*.py','-v']]
 for index,args in enumerate(commands):
  cmd=['nsenter','--target',str(pid),'--net','--','/tmp/smartplan-backend-verified/bin/python',*args]
  begin=time.monotonic();result=subprocess.run(cmd,cwd=ROOT,env=test_env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=900)
  log=result.stdout.replace(env['POSTGRES_PASSWORD'],'[redacted-disposable-password]')
  (OUT/(str(index+1)+'-tests.txt')).write_text(log)
  outcomes.append({'command':['python',*args],'exit_code':result.returncode,'duration_seconds':round(time.monotonic()-begin,3),'log':str(index+1)+'-tests.txt'})
  print(str(index+1)+'/2: '+str(result.returncode),flush=True)
finally:
 if started:cleanup=docker('rm','--force',name)
 metadata={'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'postgres_version':locals().get('version'),'network':'none; loopback only inside owned container namespace','host_ports_published':False,'host_55433_read_or_modified':False,'namespace_distinct':locals().get('pid') is not None,'before_sha256':before,'after_sha256':hashes(),'results':outcomes,'cleanup_exit_code':None if cleanup is None else cleanup.returncode,'credentials_saved':False,'duration_seconds':round(time.monotonic()-tick,3)}
 (OUT/'result.json').write_text(json.dumps(metadata,indent=2)+'\n')
print(json.dumps({'results':[r['exit_code'] for r in outcomes],'cleanup':metadata['cleanup_exit_code'],'duration_seconds':metadata['duration_seconds']}),flush=True)
raise SystemExit(0 if len(outcomes)==2 and all(r['exit_code']==0 for r in outcomes) else 1)
