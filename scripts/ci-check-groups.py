"""Run complete, disjoint CI groups with retained per-command evidence.

The plan preserves the previous explicit unittest selections. Wildcard
discoveries expand to their actual files before distribution; each command
still runs in a fresh process against this group's own disposable database.
No test selection is inferred from changed files or earlier success.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PLAN = Path(__file__).with_name('ci-check-plan.json')


def tasks(suite, root=ROOT, plan_path=PLAN):
    plan = json.loads(plan_path.read_text())
    if plan.get('schema_version') != 1:
        raise ValueError('Unsupported check plan')
    result = []
    if suite == 'online':
        for index, arguments in enumerate(plan['online']):
            if not isinstance(arguments, list) or not all(isinstance(v, str) for v in arguments):
                raise ValueError('Invalid unittest arguments')
            if '-p' in arguments:
                position = arguments.index('-p') + 1
                directory = root / arguments[arguments.index('-s') + 1]
                matches = sorted(directory.glob(arguments[position]))
                if not matches:
                    raise ValueError('Empty unittest discovery: ' + arguments[position])
                for path in matches:
                    argv = list(arguments)
                    argv[position] = path.name
                    result.append(dict(id=f'online-{index:03d}-{path.stem}',
                                       argv=[sys.executable, '-m', 'unittest', *argv], cwd=str(root)))
            else:
                result.append(dict(id=f'online-{index:03d}',
                                   argv=[sys.executable, '-m', 'unittest', *arguments], cwd=str(root)))
    elif suite == 'browser':
        for row in plan['browser']:
            script = row['script']
            if script.startswith('/') or '..' in Path(script).parts or not (root / 'web/office' / script).is_file():
                raise ValueError('Missing or invalid browser script')
            result.append(dict(id=row['id'], argv=['node', script], cwd=str(root / 'web/office'),
                               workflow=row.get('workflow'), postgres=row.get('postgres', False)))
    else:
        raise ValueError('Unknown suite')
    if not result or len({row['id'] for row in result}) != len(result):
        raise ValueError('Empty or duplicate check IDs')
    return result


def select(all_tasks, group, groups):
    if groups < 1 or not 0 <= group < groups or groups > len(all_tasks):
        raise ValueError('Invalid or empty check group')
    return [row for index, row in enumerate(all_tasks) if index % groups == group]


def run(selected, suite, report, environ=None, *, annotations=True):
    """Execute every selected command; any failure makes the group fail."""
    if not selected:
        raise ValueError('Empty check execution')
    report = Path(report)
    report.parent.mkdir(parents=True, exist_ok=True)
    logdir = report.with_suffix('.logs')
    logdir.mkdir(exist_ok=True)
    base = dict(os.environ if environ is None else environ)
    base['PYTHONPATH'] = os.pathsep.join(str(ROOT / p) for p in ('', 'backend', 'backend/business_tests', 'backend/online', 'scripts'))
    # Browser fixtures that do not use PG must not inherit another fixture's
    # database selector. A PG task still requires its own guarded test DSN.
    base.pop('SMARTPLAN_BROWSER_WORKFLOW', None)
    results = []
    metadata = dict(suite=suite, selected=[row['id'] for row in selected],
                    plan_sha256=hashlib.sha256(PLAN.read_bytes()).hexdigest())
    report.write_text(json.dumps(dict(metadata, complete=False, results=[]), indent=2)+'\n')
    for row in selected:
        env = dict(base)
        if suite == 'browser':
            if row.get('workflow'):
                env['SMARTPLAN_BROWSER_WORKFLOW'] = row['workflow']
            if row.get('postgres'):
                if not env.get('SMARTPLAN_TEST_DSN'):
                    raise ValueError('This browser check needs its own disposable PostgreSQL DSN')
            else:
                env.pop('SMARTPLAN_TEST_DSN', None)
            screenshot_dir = base.get('SMARTPLAN_BROWSER_SCREENSHOT_DIR')
            if screenshot_dir:
                env['SMARTPLAN_BROWSER_SCREENSHOT_DIR'] = str(Path(screenshot_dir) / row['id'])
        print('SMARTPLAN_CHECK_BEGIN ' + row['id'], flush=True)
        started = time.monotonic()
        logfile = logdir / (row['id'] + '.txt')
        try:
            with logfile.open('w') as output:
                process = subprocess.run(row['argv'], cwd=row['cwd'], env=env, stdout=output, stderr=subprocess.STDOUT, check=False)
            code = process.returncode
        except OSError as error:
            logfile.write_text(type(error).__name__ + ': ' + str(error) + '\n')
            code = 127
        detail = logfile.read_text(errors='replace')
        print(detail, end='' if detail.endswith('\n') else '\n', flush=True)
        results.append(dict(id=row['id'], exit_code=code, seconds=round(time.monotonic()-started, 3), log=logfile.name))
        # Persist partial results before the next independent command starts.
        report.write_text(json.dumps(dict(metadata, complete=False, results=results), indent=2)+'\n')
        print(f'SMARTPLAN_CHECK_END {row["id"]} exit={code}', flush=True)
        if code and annotations:
            lines = detail.splitlines()
            selected_lines = lines if len(lines) <= 50 else lines[:30]+['[middle diagnostic lines omitted]']+lines[-20:]
            bounded = '\n'.join(line[:500] for line in selected_lines)[:25000]
            escaped = bounded.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
            print('::error title=Check '+row['id']+'::'+escaped, flush=True)
    failed = sum(row['exit_code'] != 0 for row in results)
    report.write_text(json.dumps(dict(metadata, complete=True, failed=failed, results=results), indent=2)+'\n')
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=('online', 'browser'), required=True)
    parser.add_argument('--group', type=int, required=True)
    parser.add_argument('--groups', type=int, default=6)
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    selected = select(tasks(args.suite), args.group, args.groups)
    if args.list:
        print(json.dumps(selected, indent=2))
        return 0
    if args.report is None:
        parser.error('--report is required for execution')
    if args.suite == 'online' and not os.environ.get('SMARTPLAN_TEST_DSN'):
        parser.error('Online checks require an explicit disposable PostgreSQL DSN')
    return run(selected, args.suite, args.report)


if __name__ == '__main__':
    raise SystemExit(main())
