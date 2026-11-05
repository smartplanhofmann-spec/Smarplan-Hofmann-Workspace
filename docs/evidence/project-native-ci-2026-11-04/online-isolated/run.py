"""Unprivileged Python/PG/Caddy checks in owned offline containers only."""
import hashlib,json,os,secrets,subprocess,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
context=ROOT/'work/verification/online-private-context';image=(context/'image-ref.txt').read_text().strip()
env=dict(os.environ)
for k in ('DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'):env.pop(k,None)
env['POSTGRES_PASSWORD']=secrets.token_urlsafe(32)
env['SMARTPLAN_TEST_DSN']='host=127.0.0.1 port=55433 dbname=smartplan_check user=postgres password='+env['POSTGRES_PASSWORD']
DOCKER=['docker','--host=unix:///var/run/docker.sock'];name='smartplan-isolated-pg-'+uuid.uuid4().hex[:12]
def docker(*args,timeout=60):return subprocess.run(DOCKER+list(args),env=env,text=True,capture_output=True,timeout=timeout)
paths=[p for p in subprocess.check_output(['git','ls-files','backend','deploy/hetzner/online'],cwd=ROOT,text=True).splitlines() if (ROOT/p).is_file()]
def hashes():return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
before=hashes();outcomes=[];started=False;cleanup=None;tick=time.monotonic();runner=None
try:
 r=docker('run','--detach','--rm','--network','none','--name',name,'--env','POSTGRES_PASSWORD','--env','POSTGRES_DB=smartplan_check','postgres:16','postgres','-p','55433','-c','listen_addresses=127.0.0.1')
 if r.returncode:raise RuntimeError('Own offline PostgreSQL could not start')
 started=True
 for index in range(160):
  if docker('exec',name,'pg_isready','-h','127.0.0.1','-p','55433','-U','postgres','-d','smartplan_check').returncode==0:break
  time.sleep(.25)
 else:raise RuntimeError('Offline test PostgreSQL did not become ready')
 version=docker('exec','--user','postgres',name,'psql','-p','55433','-Atc','SHOW server_version').stdout.strip()
 commands=[['-m','unittest','-v','online.test_year_values_full_financial_restore_pg'],['-m','unittest','discover','-s','backend/online','-p','test_provisioning*.py','-v'],['backend/online/test_runtime.py'],['-m','unittest','discover','-s','backend/online','-p','test_release_tls.py','-v']]
 for index,args in enumerate(commands):
  runner='smartplan-isolated-runner-'+uuid.uuid4().hex[:12];start=time.monotonic()
  r=docker('run','--rm','--name',runner,'--network','container:'+name,'--read-only','--tmpfs','/tmp:rw,exec,nosuid,nodev,mode=1777,size=1g','--env','SMARTPLAN_TEST_DSN','--env','SMARTPLAN_CADDY_BINARY=/work/caddy',image,*args,timeout=900)
  log=r.stdout+'\n'+r.stderr;log=log.replace(env['POSTGRES_PASSWORD'],'[redacted-disposable-password]')
  (OUT/(str(index+1)+'-tests.txt')).write_text(log)
  outcomes.append({'command':['python',*args],'exit_code':r.returncode,'duration_seconds':round(time.monotonic()-start,3),'log':str(index+1)+'-tests.txt'})
  (OUT/'commands.json').write_text(json.dumps(outcomes,indent=2)+'\n')
  print(str(index+1)+'/4: '+str(r.returncode),flush=True);runner=None
finally:
 if runner:docker('rm','--force',runner)
 if started:cleanup=docker('rm','--force',name)
 metadata={'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'postgres_version':locals().get('version'),'image':image,'runtime_user':'postgres (non-root)','host_ports_published':False,'database_network':'none; runner shares only owned private namespace','host_55433_read_or_modified':False,'source_before':before,'source_after':hashes(),'results':outcomes,'cleanup_exit_code':None if cleanup is None else cleanup.returncode,'duration_seconds':round(time.monotonic()-tick,3),'credentials_saved':False}
 (OUT/'result.json').write_text(json.dumps(metadata,indent=2)+'\n')
print(json.dumps({'exit_codes':[r['exit_code'] for r in outcomes],'cleanup':metadata['cleanup_exit_code'],'duration_seconds':metadata['duration_seconds']}),flush=True)
raise SystemExit(0 if len(outcomes)==4 and all(r['exit_code']==0 for r in outcomes) else 1)
