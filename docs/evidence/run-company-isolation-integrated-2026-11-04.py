from pathlib import Path
import os,sys,subprocess,hashlib,json,time,datetime
r=Path(__file__).resolve().parents[2];name=sys.argv[1]
py='/tmp/smartplan-backend-verified/bin/python';flutter='/workspace/toolchains/flutter/bin/flutter'
env=os.environ.copy();env.update(PYTHONPATH=str(r/'backend')+':'+str(r/'backend/online')+':'+str(r/'scripts'),PYTHONDONTWRITEBYTECODE='1',SMARTPLAN_TEST_PYTHON=py,SMARTPLAN_TEST_PARSER_PYTHON=py,PUB_CACHE='/workspace/toolchains/pub-cache',PATH='/workspace/toolchains/clang-19/bin:'+os.environ['PATH'])
commands={
 'native':([flutter,'test','--no-pub','--reporter','expanded','test/business_company_assistant_isolation_review_test.dart','test/business_assistant_test.dart','test/business_speech_test.dart','test/business_company_events_test.dart','test/business_company_events_independent_review_test.dart','test/business_company_events_http_test.dart'],r/'app'),
 'http':([py,'-m','unittest','-v','online.test_company_isolation_ci','online.test_company_isolation_current','online.test_company_assistant_isolation_review'],r),
 'node':(['node','--test',*map(str,sorted((r/'web/office/tests').glob('*.test.mjs')))],r/'web/office'),
 'analyze':([flutter,'analyze','--no-pub'],r/'app'),
 'packages':([py,'-m','unittest','-v','scripts/test_native_release.py'],r),
}
cmd,cwd=commands[name]
files=subprocess.check_output(['git','ls-files','-c','-o','--exclude-standard','-z'],cwd=r).decode().split('\0')
sources={p:hashlib.sha256((r/p).read_bytes()).hexdigest() for p in sorted(set(files)) if p and p.startswith(('app/','backend/','web/office/','scripts/','.github/')) and (r/p).is_file()}
log=r/f'docs/evidence/company-isolation-integrated-{name}-2026-11-04.txt';started=datetime.datetime.now(datetime.timezone.utc).isoformat();t=time.monotonic()
with log.open('w') as f:
 f.write('Command: '+repr(cmd)+'\nCwd: '+str(cwd)+'\nStarted: '+started+'\n');f.flush();result=subprocess.run(cmd,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT)
changed=[p for p,h in sources.items() if hashlib.sha256((r/p).read_bytes()).hexdigest()!=h]
d={'name':name,'started':started,'command':cmd,'exit_code':result.returncode,'seconds':round(time.monotonic()-t,3),'source_files':sources,'changed_during_run':changed,'log':str(log.relative_to(r)),'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest()}
(r/f'docs/evidence/company-isolation-integrated-{name}-2026-11-04.json').write_text(json.dumps(d,indent=2)+'\n')
print(name,result.returncode,d['seconds'],'changed',changed);print(log.read_text()[-2200:]);sys.exit(result.returncode or bool(changed))
