#!/usr/bin/env python3
"""Three actual loopback browser workflows, with unchanged source hash binding."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parent
RUN = EVIDENCE / (sys.argv[1] if len(sys.argv) > 1 else 'run-01')
WORKFLOWS = ('project-customer', 'inventory-article-refs', 'time-tracking')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    extensions = {'.py', '.js', '.cjs', '.mjs', '.json', '.css', '.html', '.toml', '.txt', '.sql'}
    paths = [p for base in ('backend', 'web/office') for p in (ROOT / base).rglob('*')
             if p.is_file() and p.suffix in extensions
             and not {'node_modules', '__pycache__', '.pytest_cache'} & set(p.parts)]
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(paths)}


def save(name, value):
    (RUN / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


RUN.mkdir(parents=True, exist_ok=False)
before = sources()
save('source-before.json', before)
env = dict(os.environ, XDG_CONFIG_HOME='/tmp/smartplan-project-flow-chromium-config',
           NODE_PATH='/workspace/Smarplan-Hofmann-Workspace/web/office/node_modules',
           SMARTPLAN_BROWSER_TEST_PYTHON='/tmp/smartplan-backend-verified/bin/python',
           SMARTPLAN_BROWSER_NAMESPACE_SANDBOX='1')
summary = {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
           'base_runtime': 'c875ea5a221e5d38533bb7d50a1d96b9c455d22f',
           'worktree': str(ROOT), 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
           'workflows': [], 'scope': 'Actual sandboxed Chromium, MFA and loopback Flask/SQLite; no PostgreSQL or deployment.'}
for workflow in WORKFLOWS:
    started = time.monotonic()
    command = ['node', 'web/office/tests/e2e.cjs']
    workflow_env = dict(env, SMARTPLAN_BROWSER_WORKFLOW=workflow,
                        SMARTPLAN_BROWSER_SCREENSHOT_DIR=str(RUN / workflow))
    with (RUN / (workflow + '.log')).open('w') as output:
        try:
            result = subprocess.run(command, cwd=ROOT, env=workflow_env, stdout=output,
                                    stderr=subprocess.STDOUT, timeout=240)
            code = result.returncode
        except subprocess.TimeoutExpired:
            output.write('\nBrowser workflow exceeded 240 seconds.\n')
            code = 124
    summary['workflows'].append({'workflow': workflow, 'command': command,
                                 'exit_code': code, 'seconds': round(time.monotonic() - started, 3)})
    save('summary.json', summary)
    print(f'{workflow}: exit {code}', flush=True)
after = sources()
save('source-after.json', after)
summary['source_changes'] = [path for path in sorted(before.keys() | after.keys()) if before.get(path) != after.get(path)]
summary['source_count'] = len(before)
summary['finished_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
summary['passed'] = not summary['source_changes'] and all(item['exit_code'] == 0 for item in summary['workflows'])
save('summary.json', summary)
sys.exit(0 if summary['passed'] else 1)
