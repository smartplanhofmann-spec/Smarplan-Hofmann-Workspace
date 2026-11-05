"""Run remaining existing browser CI journeys in isolated local fixtures."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time

ROOT=Path(__file__).resolve().parents[4]
EVIDENCE=Path(__file__).resolve().parent
OUTPUT=ROOT/'work/verification/remaining-browser-bd8caef'
workflow=(ROOT/'.github/workflows/checks.yml').read_text()
targets=re.findall(r'SMARTPLAN_BROWSER_WORKFLOW=([a-z0-9-]+) node tests/e2e\.cjs',workflow)
targets=[t for t in targets if t not in ('accounting-openings','project-economics')]
scripts=re.findall(r'\bnode tests/([a-z0-9-]+-e2e\.cjs)',workflow)
tasks=[(t,'e2e.cjs',t) for t in targets]+[(Path(s).stem,s,None) for s in scripts]
assert len(tasks)==len({t[0] for t in tasks})
tracked=subprocess.check_output(['git','ls-files','web/office'],cwd=ROOT,text=True).splitlines()
def hashes():return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in tracked}
before=hashes();results=[];started=time.monotonic()
metadata={'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
 'complete':False,'workers':3,'tests':len(tasks),'source_sha256':before,
 'not_repeated':['main browser flow passed in CI bd8caef','accounting-openings passed in CI bd8caef','project-economics passed separately with current selector fix'],
 'screenshots_root':str(OUTPUT),'results':results}
def save():
 metadata['duration_seconds']=round(time.monotonic()-started,3)
 (EVIDENCE/'result.json').write_text(json.dumps(metadata,indent=2)+'\n')
def run(task):
 name,script,focus=task;output=OUTPUT/name;output.mkdir(parents=True,exist_ok=True)
 env=dict(os.environ,SMARTPLAN_BROWSER_TEST_PYTHON='/tmp/smartplan-backend-verified/bin/python',
  SMARTPLAN_CHROMIUM_BINARY='/usr/lib/chromium/chromium',SMARTPLAN_BROWSER_NAMESPACE_SANDBOX='1',
  SMARTPLAN_BROWSER_SCREENSHOT_DIR=str(output))
 env.pop('SMARTPLAN_BROWSER_WORKFLOW',None)
 if focus:env['SMARTPLAN_BROWSER_WORKFLOW']=focus
 start=time.monotonic();timed_out=False
 with (EVIDENCE/(name+'.txt')).open('w') as log:
  process=subprocess.Popen(['node','tests/'+script],cwd=ROOT/'web/office',env=env,
   stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  try:status=process.wait(timeout=600)
  except subprocess.TimeoutExpired:
   timed_out=True
   try:os.killpg(process.pid,signal.SIGTERM)
   except ProcessLookupError:pass
   try:status=process.wait(timeout=5)
   except subprocess.TimeoutExpired:
    try:os.killpg(process.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    status=process.wait()
 return {'name':name,'exit_code':status,'timed_out':timed_out,'duration_seconds':round(time.monotonic()-start,3),
  'log':str((EVIDENCE/(name+'.txt')).relative_to(ROOT)),
  'artifacts':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in output.rglob('*') if p.is_file()}}
save();print('Starting '+str(len(tasks))+' existing independent browser journeys with 3 workers',flush=True)
with ThreadPoolExecutor(max_workers=3) as pool:
 for future in as_completed([pool.submit(run,t) for t in tasks]):
  result=future.result();results.append(result);save()
  print(result['name']+': '+str(result['exit_code'])+' ('+str(result['duration_seconds'])+'s)',flush=True)
metadata['complete']=True;metadata['sources_unchanged']=before==hashes();save()
failed=[r['name'] for r in results if r['exit_code']!=0]
print(json.dumps({'passed':len(results)-len(failed),'failed':failed,'sources_unchanged':metadata['sources_unchanged'],'duration_seconds':metadata['duration_seconds']}),flush=True)
raise SystemExit(bool(failed) or not metadata['sources_unchanged'])
