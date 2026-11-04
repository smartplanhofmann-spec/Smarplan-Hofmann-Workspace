import os,sys,json,time,hashlib,subprocess,pathlib,datetime
root=pathlib.Path(__file__).resolve().parents[2];name=sys.argv[1];py='/tmp/smartplan-backend-verified/bin/python';flutter='/workspace/toolchains/flutter/bin/flutter'
env=os.environ.copy();env.update(PYTHONPATH=str(root/'backend')+':'+str(root/'backend/online')+':'+str(root/'scripts'),PYTHONDONTWRITEBYTECODE='1',SMARTPLAN_TEST_PYTHON=py,PUB_CACHE='/workspace/toolchains/pub-cache',PATH='/workspace/toolchains/clang-19/bin:'+os.environ['PATH'])
if name=='backend':cmd=[py,'-m','unittest','discover','-s','backend','-v'];cwd=root;prefixes=['backend/']
elif name=='node':cmd=['node','--test',*map(str,sorted((root/'web/office/tests').glob('*.test.mjs')))];cwd=root/'web/office';prefixes=['web/office/','app/test/fixtures/']
elif name=='flutter':cmd=[flutter,'test','--no-pub','--reporter','expanded','test'];cwd=root/'app';prefixes=['app/','backend/']
elif name=='analyze':cmd=[flutter,'analyze','--no-pub'];cwd=root/'app';prefixes=['app/']
elif name=='packages':cmd=[py,'-m','unittest','-v','scripts/test_native_release.py'];cwd=root;prefixes=['backend/','scripts/']
elif name=='targeted':cmd=[py,'-m','unittest','-v','test_accounting_year_package','test_accounting_year_package_independent_review','test_accounting_year_package_http','test_business_accounting_euer','test_business_accounting_open_items','test_accounting_open_items_independent_review','test_accounting_open_items_boundaries','test_accounting_open_items_registration','test_accounting_open_items_transport'];cwd=root;prefixes=['backend/','scripts/']
elif name=='finance_http':cmd=[py,'-m','unittest','-v','online.test_accounting_http','online.test_accounting_allocations_http','online.test_accounting_components_http','online.test_accounting_refunds_http','online.test_accounting_refunds_v2_http','online.test_accounting_profile_http','online.test_accounting_capacity_http'];cwd=root;prefixes=['backend/']
else:raise SystemExit('unknown check')
files=subprocess.check_output(['git','ls-files','-c','-o','--exclude-standard','-z'],cwd=root).decode().split('\0');files=sorted(set(p for p in files if p and any(p.startswith(x) for x in prefixes)))
source={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in files if (root/p).is_file()}
log=root/f'docs/evidence/year-values-integrated-{name}-2026-11-04.txt';t=time.monotonic();started=datetime.datetime.now(datetime.timezone.utc).isoformat()
with log.open('w') as f:
 f.write('Command: '+repr(cmd)+'\nCwd: '+str(cwd)+'\nStarted UTC: '+started+'\n');f.flush();r=subprocess.run(cmd,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT)
elapsed=round(time.monotonic()-t,3);changes=[p for p,h in source.items() if not (root/p).is_file() or hashlib.sha256((root/p).read_bytes()).hexdigest()!=h]
result={'name':name,'started_at_utc':started,'command':cmd,'cwd':str(cwd),'exit_code':r.returncode,'duration_seconds':elapsed,'source_files':source,'source_changed_during_check':changes,'log':str(log.relative_to(root)),'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest()}
(root/f'work/verification/year-values-integrated-{name}-2026-11-04.json').write_text(json.dumps(result,indent=2)+'\n');print(name,r.returncode,elapsed,'seconds; changed inputs',changes,flush=True);print(log.read_text()[-1800:]);sys.exit(r.returncode or bool(changes))
