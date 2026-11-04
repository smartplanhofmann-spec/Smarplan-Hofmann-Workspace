from pathlib import Path
import json,os,subprocess,hashlib,time
root=Path(__file__).resolve().parents[3]
folder=root/'docs/evidence/project-native-ci-2026-11-04/import-recheck'
targets=json.loads((root/'docs/evidence/project-native-ci-2026-11-04/import-targets.json').read_text());outcomes=[]
for name in targets:
 start=time.monotonic();path=root/'backend/online'/name;before=hashlib.sha256(path.read_bytes()).hexdigest()
 with (folder/(name+'.txt')).open('w') as log:
  p=subprocess.run(['/tmp/smartplan-backend-verified/bin/python','-m','unittest','discover','-s','backend/online','-p',name,'-v'],cwd=root,env={**os.environ,'PYTHONPATH':'backend'},stdout=log,stderr=subprocess.STDOUT)
 outcomes.append({'module':name,'exit_code':p.returncode,'seconds':round(time.monotonic()-start,3),'source_sha256':before,'source_unchanged':before==hashlib.sha256(path.read_bytes()).hexdigest()})
 (folder/'results.json').write_text(json.dumps(outcomes,indent=2)+'\n')
print(json.dumps(outcomes,indent=2))
raise SystemExit(any(x['exit_code'] for x in outcomes))
