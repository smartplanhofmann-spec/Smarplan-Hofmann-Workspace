"""Exercise real HTTP fixtures through an owned symlinked temporary parent."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[4]
EVIDENCE=Path(__file__).resolve().parent
phase=sys.argv[1]
assert phase in ('before','after')
paths=['app/test/business_company_events_http_test.dart',
       'app/test/business_accounting_year_evidence_http_test.dart',
       'app/test/business_accounting_year_evidence_v2_http_test.dart',
       'backend/test_accounting_year_package.py',
       'backend/online/storage_backends.py','backend/online/instance.py']
hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
started=time.monotonic()
with tempfile.TemporaryDirectory(prefix='smartplan-owned-tmp-alias-',dir='/tmp') as parent:
    root=Path(parent);real=root/'real';real.mkdir();alias=root/'alias';alias.symlink_to(real,target_is_directory=True)
    env=dict(os.environ,TMPDIR=str(alias),PUB_CACHE='/workspace/toolchains/pub-cache')
    env['PATH']='/workspace/toolchains/clang-19/bin:'+env['PATH']
    command=['/workspace/toolchains/flutter/bin/flutter','test','--no-pub',
        *[p.removeprefix('app/') for p in paths[:3]],'--reporter','expanded']
    with (EVIDENCE/(phase+'-tests.txt')).open('w') as log:
        result=subprocess.run(command,cwd=ROOT/'app',env=env,stdout=log,stderr=subprocess.STDOUT,timeout=480)
metadata={'phase':phase,'exit_code':result.returncode,'duration_seconds':round(time.monotonic()-started,3),
    'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
    'source_sha256':hashes,'source_unchanged_during_run':all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==v for p,v in hashes.items()),
    'owned_symlink_parent_removed':not root.exists(),'real_HTTP_tests':3,
    'note':'Linux alias reproduces rejected macOS /var ancestor; actual macOS run is separate.'}
(EVIDENCE/(phase+'-result.json')).write_text(json.dumps(metadata,indent=2)+'\n')
print(json.dumps({k:metadata[k] for k in ('phase','exit_code','duration_seconds','owned_symlink_parent_removed')}))
raise SystemExit(0 if (result.returncode!=0 if phase=='before' else result.returncode==0) else 1)
