"""Re-run this handoff's local synthetic evidence; requires existing test tools."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import time

root=Path(__file__).resolve().parents[3]
evidence=Path(__file__).resolve().parent
paths=['web/office/office.js','web/office/tests/e2e.cjs','web/office/tests/project-customer-flow.cjs',
       'web/office/tests/inventory-article-refs-flow.cjs','web/office/tests/inventory-article-refs.test.mjs',
       'backend/business_inventory.py','backend/business_foundation.py','backend/business_documents.py','backend/core.py']
def hashes():
    return {p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths}
before=hashes();results=[]
for workflow,folder in [('project-customer','final-customer'),('inventory-article-refs','final-warehouse')]:
    env=dict(os.environ,XDG_CONFIG_HOME='/tmp/smartplan-project-flow-chromium-config',
        SMARTPLAN_BROWSER_TEST_PYTHON=sys.executable,SMARTPLAN_BROWSER_WORKFLOW=workflow,
        SMARTPLAN_BROWSER_NAMESPACE_SANDBOX='1',SMARTPLAN_BROWSER_SCREENSHOT_DIR=str(evidence/folder))
    env.setdefault('NODE_PATH','/workspace/Smarplan-Hofmann-Workspace/web/office/node_modules')
    started=time.monotonic()
    with (evidence/(folder+'.txt')).open('w') as log:
        run=subprocess.run(['node','web/office/tests/e2e.cjs'],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
    results.append(dict(workflow=workflow,exit_code=run.returncode,duration_seconds=round(time.monotonic()-started,3),log=folder+'.txt'))
    if run.returncode:
        break
after=hashes()
value=dict(before_sha256=before,after_sha256=after,sources_unchanged=before==after,results=results)
(evidence/'final-browser-runs.json').write_text(json.dumps(value,indent=2)+'\n')
print(json.dumps(dict(sources_unchanged=before==after,results=results)))
sys.exit(int(before!=after or len(results)!=2 or any(r['exit_code'] for r in results)))
