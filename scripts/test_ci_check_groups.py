"""Independent coverage of the frozen prior workflow and real process failures."""
import ast
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('check_groups', Path(__file__).with_name('ci-check-groups.py'))
groups = importlib.util.module_from_spec(spec)
spec.loader.exec_module(groups)


class CompleteChecks(unittest.TestCase):
    def test_every_previous_online_command_expands_to_exact_same_file_selection(self):
        baseline = (groups.ROOT/'scripts/testdata/ci-check-baseline-20261110.yml').read_bytes()
        plan = json.loads(groups.PLAN.read_text())
        self.assertEqual(hashlib.sha256(baseline).hexdigest(), plan['baseline_workflow_sha256'])
        block = baseline.decode().split('      - name: PostgreSQL-, Speicher- und OneDrive-Vertraege pruefen\n        run: |\n')[1].split('      - name: Check online units')[0]
        expected = []
        for line in block.splitlines():
            args = shlex.split(line.strip())
            if not args:
                continue
            if args[0].startswith('PYTHONPATH='):
                args = args[1:]
            self.assertEqual(args[:3], ['python', '-m', 'unittest'])
            if '-p' in args:
                pos = args.index('-p')+1
                for file in sorted((groups.ROOT/args[args.index('-s')+1]).glob(args[pos])):
                    actual = list(args[3:]); actual[pos-3] = file.name
                    expected.append(actual)
            else:
                expected.append(args[3:])
        self.assertGreaterEqual(len(plan['online']), 76)
        actual=Counter(tuple(r['argv'][3:]) for r in groups.tasks('online'))
        self.assertFalse(Counter(tuple(row) for row in expected)-actual)

    def test_every_existing_browser_command_and_all_supported_workflows_are_required(self):
        baseline = (groups.ROOT/'scripts/testdata/ci-check-baseline-20261110.yml').read_text()
        previous = set(re.findall(r'SMARTPLAN_BROWSER_WORKFLOW=([\w-]+) node tests/e2e.cjs', baseline))
        source = (groups.ROOT/'web/office/tests/e2e.cjs').read_text()
        allowed = set(ast.literal_eval(re.search(r'workflow===undefined\|\|(\[[^\n]+\])\.includes', source)[1]))
        tasks = groups.tasks('browser')
        current = {r['workflow'] for r in tasks if r['workflow']}
        self.assertEqual(current, allowed)
        self.assertLessEqual(previous, current)
        self.assertLessEqual({'accounting-allocation','accounting-capacity','accounting-components',
                              'accounting-profile','accounting-refunds','accounting-refunds-v2',
                              'planning-relogin','purchasing-catalog','purchasing-receipts'}, current-previous)
        expected_scripts = set(re.findall(r'node (tests/[\w-]+-e2e.cjs)', baseline))
        self.assertEqual({r['argv'][1] for r in tasks if r['argv'][1]!='tests/e2e.cjs'}, expected_scripts)
        self.assertEqual(sum(r['id']=='default' for r in tasks), 1)
        self.assertEqual([r['id'] for r in tasks if r['postgres']], ['document-time-billing'])

    def test_all_six_groups_are_nonempty_disjoint_and_complete(self):
        for suite in ('online', 'browser'):
            all_tasks = groups.tasks(suite)
            selected = [groups.select(all_tasks, index, 6) for index in range(6)]
            flattened = [r['id'] for batch in selected for r in batch]
            self.assertEqual(len(flattened), len(set(flattened)))
            self.assertEqual(set(flattened), {r['id'] for r in all_tasks})
            self.assertTrue(all(selected))
            for index, count in ((-1,6),(6,6),(0,0),(0,len(all_tasks)+1)):
                with self.assertRaises(ValueError): groups.select(all_tasks,index,count)

    def test_empty_discovery_cannot_turn_into_green(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); plan=root/'plan.json'
            plan.write_text(json.dumps({'schema_version':1,'online':[['discover','-s','missing','-p','test_*.py','-v']]}))
            with self.assertRaisesRegex(ValueError,'Empty unittest discovery'):
                groups.tasks('online',root,plan)

    def test_actual_failed_child_is_retained_and_subsequent_check_still_executes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); report=root/'report.json'; marker=root/'after-failure.txt'
            tasks=[dict(id='actual-failure',argv=[sys.executable,'-c','print("synthetic failure"); raise SystemExit(7)'],cwd=directory),
                   dict(id='after-failure',argv=[sys.executable,'-c','from pathlib import Path; Path("after-failure.txt").write_text("executed")'],cwd=directory)]
            self.assertEqual(groups.run(tasks,'online',report,annotations=False),1)
            result=json.loads(report.read_text())
            self.assertEqual([r['exit_code'] for r in result['results']],[7,0])
            self.assertEqual(result['failed'],1);self.assertTrue(result['complete'])
            self.assertEqual(marker.read_text(),'executed')
            self.assertIn('synthetic failure',(report.with_suffix('.logs')/'actual-failure.txt').read_text())

    def test_actual_browser_child_cannot_inherit_another_target_or_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);report=root/'report.json'
            script='import os; assert "SMARTPLAN_TEST_DSN" not in os.environ; assert os.environ["SMARTPLAN_BROWSER_WORKFLOW"]=="planning-relogin"; print("isolated")'
            task=dict(id='planning-relogin',argv=[sys.executable,'-c',script],cwd=directory,workflow='planning-relogin',postgres=False)
            env=dict(os.environ,SMARTPLAN_BROWSER_WORKFLOW='wrong-target',SMARTPLAN_TEST_DSN='must-not-reach-fixture')
            self.assertEqual(groups.run([task],'browser',report,env),0)
            missing=dict(task,postgres=True)
            with self.assertRaisesRegex(ValueError,'own disposable PostgreSQL'):
                groups.run([missing],'browser',root/'missing.json',{})

    def test_cli_refuses_online_execution_without_actual_database_selector(self):
        with tempfile.TemporaryDirectory() as directory:
            report=Path(directory)/'results.json';env=dict(os.environ)
            env.pop('SMARTPLAN_TEST_DSN',None)
            command=[sys.executable,str(groups.ROOT/'scripts/ci-check-groups.py'),'--suite','online','--group','0','--report',str(report)]
            result=subprocess.run(command,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertIn('explicit disposable PostgreSQL DSN',result.stderr)
            self.assertFalse(report.exists())

    def test_actual_timeout_is_red_and_later_command_still_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);report=root/'report.json'
            tasks=[dict(id='bounded-child',argv=[sys.executable,'-c','import time; time.sleep(10)'],cwd=directory),
                   dict(id='after-timeout',argv=[sys.executable,'-c','print("later check completed")'],cwd=directory)]
            self.assertEqual(groups.run(tasks,'online',report,annotations=False,timeout_seconds=0.25),1)
            result=json.loads(report.read_text());self.assertEqual([r['exit_code'] for r in result['results']],[124,0])
            self.assertTrue(result['complete']);self.assertEqual(result['failed'],1)
            self.assertIn('runtime limit',(report.with_suffix('.logs')/'bounded-child.txt').read_text())


if __name__ == '__main__':
    unittest.main()
