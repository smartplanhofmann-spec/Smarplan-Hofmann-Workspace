"""Controlled negative probe: remove only owner's context fix in a temporary copy.

This is not represented as a historical pre-fix source snapshot.
The product workspace and frozen review artifacts stay unchanged.
"""
from pathlib import Path
import json,shutil,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[3]
with tempfile.TemporaryDirectory(prefix='year-context-negative-') as directory:
    target=Path(directory)
    office=target/'web/office';(office/'tests/fixtures').mkdir(parents=True)
    for source in (ROOT/'web/office').glob('*.js'):shutil.copyfile(source,office/source.name)
    shutil.copyfile(ROOT/'web/office/package.json',office/'package.json')
    shutil.copyfile(ROOT/'web/office/tests/accounting-year-package-independent.test.mjs',office/'tests/accounting-year-package-independent.test.mjs')
    shutil.copyfile(ROOT/'web/office/tests/fixtures/accounting-year-package-independent.json',office/'tests/fixtures/accounting-year-package-independent.json')
    (target/'docs/fixtures').mkdir(parents=True)
    shutil.copyfile(ROOT/'docs/fixtures/accounting_year_package_v1.json',target/'docs/fixtures/accounting_year_package_v1.json')
    path=office/'accounting-euer.js';text=path.read_text()
    changes=[(',exportGeneration=0',''),(' function invalidateExport(){exportGeneration++;}\n',''),('function clear(){invalidateExport();','function clear(){'),('const intent=++exportGeneration,base=context()','const base=context()'),('intent!==exportGeneration||',''),('render,clear,invalidateExport,openPending','render,clear,openPending')]
    for before,after in changes:
        assert text.count(before)==1,before
        text=text.replace(before,after)
    path.write_text(text)
    path=office/'office.js';text=path.read_text();assert text.count('accountingEuer.invalidateExport();')==1
    path.write_text(text.replace('accountingEuer.invalidateExport();',''))
    completed=subprocess.run(['node','--test','--test-isolation=none','web/office/tests/accounting-year-package-independent.test.mjs'],cwd=target,text=True,capture_output=True)
    print(completed.stdout);print(completed.stderr)
    assert completed.returncode!=0
    assert 'tests 21' in completed.stdout and 'pass 18' in completed.stdout and 'fail 3' in completed.stdout
    for name in ['initial original export success cannot return after background and foreground','initial original export error cannot return after background and foreground','latest original export intent wins before either initial request created a dialog']:
        assert ('✖ '+name) in completed.stdout,name
    print(json.dumps(dict(controlled_temporary_copy=True,historical_snapshot_claimed=False,unchanged_test_assertions=True,expected_failures=3,other_passed=18,product_mutated=False)))
