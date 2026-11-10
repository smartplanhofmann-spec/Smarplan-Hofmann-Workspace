"""Actual CRLF source execution; no handcrafted provenance substitutions."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from core import Office, canonical
from business_payroll import Payroll
from business_payroll_calculation_cases import validate_case_sources
from payroll_factor_periods_2026 import build_factor_period_plan
from payroll_factor_claim_travel_2026 import build_plan


class FactorClaimTravelCrlfReview(unittest.TestCase):
    def test_actual_crlf_v13_preserves_component_originals_and_run_on_lf(self):
        source = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(prefix='synthetic-factor-travel-crlf-') as directory:
            root = Path(directory)
            target = root / 'backend'
            shutil.copytree(source, target, ignore=shutil.ignore_patterns(
                '.venv', '__pycache__', '*.pyc', '*.sqlite3', '*.db'))
            for path in target.rglob('*.py'):
                raw = path.read_bytes().replace(b'\r\n', b'\n')
                path.write_bytes(raw.replace(b'\n', b'\r\n'))
            runner = root / 'produce.py'
            runner.write_text('''import json, sqlite3, sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from core import canonical
from test_business_payroll_factor_claim_travel import FactorClaimTravelFixture
from test_business_payroll_periods import command
from business_payroll_facts import reference
f=FactorClaimTravelFixture('runTest');f.setUp()
try:
    saved,body=f.save_case(f.proposal())
    inputs=dict(source_schema_version=3,employee_id=f.f.employee['id'],calculation_case_ref=reference(saved))
    cmd=command(f.f.payroll,f.f.owner,inputs);run=f.f.payroll.finalize(f.f.owner,cmd)
    pdf=f.f.payroll.export(f.f.owner,run['id'],'pdf')[0]
    Path(sys.argv[2]).write_text(canonical(dict(case=saved,command=cmd,run=run,owner=f.f.owner)))
    Path(sys.argv[3]).write_bytes(pdf)
    f.f.office.db.commit()
    copy=sqlite3.connect(sys.argv[4]);f.f.office.db.backup(copy);copy.close()
finally:f.doCleanups()
''')
            document, pdf, database = root / 'original.json', root / 'original.pdf', root / 'original.sqlite3'
            result = subprocess.run([sys.executable, '-I', str(runner), str(target),
                str(document), str(pdf), str(database)], capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr)
            stored = json.loads(document.read_text())
            case = stored['case']; period = case['sources']['period_case']
            self.assertEqual(build_factor_period_plan(period['sources']), period['plan'])
            self.assertEqual(build_plan(case['sources']), case['plan'])
            office = Office(database)
            try:
                self.assertTrue(validate_case_sources(office, case))
                payroll = Payroll(office)
                self.assertEqual(payroll.finalize(stored['owner'], stored['command']), stored['run'])
                self.assertEqual(payroll.export(stored['owner'], stored['run']['id'], 'pdf')[0], pdf.read_bytes())
                self.assertEqual(stored['run']['calculation']['net_minor'], 285054)
            finally:
                office.db.close()


if __name__ == '__main__':
    unittest.main()
