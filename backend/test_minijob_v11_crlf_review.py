"""Execute actual CRLF modules, then reopen their originals under LF modules."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from core import Office
from business_payroll import Payroll
from business_payroll_calculation_cases import PayrollCalculationCases, validate_case_sources
from payroll_periods_2026 import build_period_plan
from payroll_individual_minijob_2026 import build_plan


class MinijobV11CrlfReview(unittest.TestCase):
    def test_actual_crlf_v4_v5_v11_originals_reopen_unchanged_under_lf(self):
        source = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(prefix='synthetic-minijob-v11-crlf-') as directory:
            root = Path(directory)
            target = root / 'backend'
            shutil.copytree(source, target, ignore=shutil.ignore_patterns(
                '.venv', '__pycache__', '*.pyc', '*.sqlite3', '*.db'))
            for path in target.rglob('*.py'):
                raw = path.read_bytes().replace(b'\r\n', b'\n')
                path.write_bytes(raw.replace(b'\n', b'\r\n'))
            self.assertIn(b'\r\n', (target / 'payroll_periods_2026.py').read_bytes())
            runner = root / 'produce.py'
            runner.write_text('''import json, sqlite3, sys, unittest
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from core import canonical
from test_payroll_individual_minijob import IndividualMinijobFixture
from test_business_payroll_periods import command
from business_payroll_facts import reference
owner=unittest.TestCase();fixture=IndividualMinijobFixture(owner);f=fixture.f
try:
    old,old_command=fixture.legacy_case()
    upgrade_command=fixture.upgrade_command(old)
    case=fixture.api.save(f.owner,upgrade_command)
    inputs=dict(source_schema_version=3,employee_id=f.employee['id'],calculation_case_ref=reference(case))
    run_command=command(f.payroll,f.owner,inputs);run=f.payroll.finalize(f.owner,run_command)
    pdf=f.payroll.export(f.owner,run['id'],'pdf')[0]
    Path(sys.argv[2]).write_text(canonical(dict(old=old,old_command=old_command,case=case,
        upgrade_command=upgrade_command,run=run,run_command=run_command,owner=f.owner)))
    Path(sys.argv[3]).write_bytes(pdf)
    f.office.db.commit()
    copy=sqlite3.connect(sys.argv[4]);f.office.db.backup(copy);copy.close()
finally:owner.doCleanups()
''')
            document, pdf, database = root / 'original.json', root / 'original.pdf', root / 'original.sqlite3'
            result = subprocess.run([sys.executable, '-I', str(runner), str(target),
                str(document), str(pdf), str(database)], capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr)
            stored = json.loads(document.read_text())
            case = stored['case']; old = stored['old']
            self.assertEqual(old['rule_version'], 'de_2026_segments_entitlements_v5')
            self.assertEqual(case['source_contract_version'], 3)
            self.assertEqual(build_period_plan(case['sources']['period_case']['sources']),
                             case['sources']['period_case']['plan'])
            self.assertEqual(build_plan(case['sources']), case['plan'])
            office = Office(database)
            try:
                self.assertTrue(validate_case_sources(office, old))
                self.assertTrue(validate_case_sources(office, case))
                cases = PayrollCalculationCases(office)
                self.assertEqual(cases.save(stored['owner'], stored['old_command']), old)
                self.assertEqual(cases.save(stored['owner'], stored['upgrade_command']), case)
                payroll = Payroll(office)
                self.assertEqual(payroll.finalize(stored['owner'], stored['run_command']), stored['run'])
                self.assertEqual(payroll.export(stored['owner'], stored['run']['id'], 'pdf')[0], pdf.read_bytes())
                self.assertEqual(stored['run']['calculation']['net_minor'], 43334)
            finally:
                office.db.close()


if __name__ == '__main__':
    unittest.main()
