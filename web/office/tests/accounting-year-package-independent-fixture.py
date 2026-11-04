"""Real immutable export siblings and current EÜR state for UI context review."""
from pathlib import Path
import importlib.util
import json
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'backend/online')]
spec=importlib.util.spec_from_file_location('year_fixture_capture',ROOT/'scripts/generate-accounting-year-package-fixture.py')
capture=importlib.util.module_from_spec(spec);spec.loader.exec_module(capture)
from test_accounting_year_package import YearPackageTests

case=YearPackageTests('runTest');case.setUp()
try:
    first,unused,unused2=case.year()
    case.f.configure(bookkeeping_start='2026-07-01')
    second=case.f.post('export',dict(year=2026))
    value=dict(synthetic_only=True,generated_by=Path(__file__).relative_to(ROOT).as_posix(),
               state=case.f.api.state(case.owner),first=capture.capture(case.office,case.owner,first),
               second=capture.capture(case.office,case.owner,second))
    path=ROOT/'web/office/tests/fixtures/accounting-year-package-independent.json'
    path.parent.mkdir(exist_ok=True,parents=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print('Actual accepted export siblings and current state captured:',path)
finally:
    case.doCleanups()
