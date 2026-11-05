from pathlib import Path
import hashlib,json,os,subprocess,time
ROOT=Path.cwd();OUT=ROOT/'docs/evidence/project-time-clock-2026-11-05'
REL='app/test/business_backend_integration_test.dart'
before=subprocess.check_output(['git','show','e7089a6a1713ba454fcd56a5027eaec526d0eab7:'+REL],text=True)
after=(ROOT/REL).read_text();paths=[];results=[]
env=dict(os.environ,PATH='/workspace/toolchains/clang-19/bin:'+os.environ.get('PATH',''),PUB_CACHE='/workspace/toolchains/pub-cache',SMARTPLAN_TEST_PYTHON='/tmp/smartplan-backend-verified/bin/python')
try:
 for phase,source,cases in [('before',before,['05:30:00.123456']),('after',after,['01:30:00.123456','05:30:00.123456','12:30:00.123456'])]:
  fixtures=[]
  for index,stamp in enumerate(cases):
   assert source.count('DateTime.now().toUtc()')==1
   value=source.replace('DateTime.now().toUtc()',"DateTime.parse('2026-11-04T"+stamp+"Z')")
   value=value.replace('Real business HTTP preserves draft values and durable own time through the scoped grant',phase+' '+stamp+' real HTTP cache and exact offline replay')
   p=ROOT/'app/test'/('clock_probe_'+phase+'_'+str(index)+'.dart');assert not p.exists();p.write_text(value);paths.append(p);fixtures.append(str(p.relative_to(ROOT/'app')))
  tick=time.monotonic()
  cmd=['/workspace/toolchains/flutter/bin/flutter','test','--no-pub','--reporter','expanded','--concurrency=1',*fixtures]
  with (OUT/(phase+'.txt')).open('w') as log:r=subprocess.run(cmd,cwd=ROOT/'app',env=env,stdout=log,stderr=subprocess.STDOUT,timeout=300)
  results.append({'phase':phase,'exit_code':r.returncode,'UTC_fixture_clock_values':['2026-11-04T'+x+'Z' for x in cases],'seconds_assertions_unchanged':[7200,3600],'duration_seconds':round(time.monotonic()-tick,3),'source_sha256':hashlib.sha256(source.encode()).hexdigest()})
  (OUT/'results.json').write_text(json.dumps(results,indent=2)+'\n')
  print(phase+': '+str(r.returncode),flush=True)
finally:
 for p in paths:p.unlink(missing_ok=True)
 (OUT/'temporary-fixtures-cleaned.json').write_text(json.dumps({'all_removed':all(not p.exists() for p in paths),'count':len(paths)},indent=2)+'\n')
raise SystemExit(0 if len(results)==2 and results[0]['exit_code']==1 and results[1]['exit_code']==0 else 1)
