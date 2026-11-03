"""Generate reduced own-payroll DTOs and PDF bytes from actual temporary archives."""
from pathlib import Path
import argparse
import base64
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'backend' / 'online')]
import test_business_payroll_statements as statements
import test_business_payroll as monthly
from business_payroll_statements import PayrollStatements, render_pdf


def fixture():
    test = statements.PayrollStatementTests('runTest')
    test.setUp()
    try:
        page = test.api.records(test.f.technician, {'employee_id': test.f.employee['id']})
        value = page['items'][0]
        result = dict(employee=test.f.employee, actor=test.f.technician, page=page, statement=value,
                      pdf_base64=base64.b64encode(render_pdf(value)).decode())
        legacy = monthly.PayrollWorkflowTests('runTest')
        legacy.setUp()
        try:
            data = legacy.case('regular', 350000)
            run = legacy.payroll.finalize(legacy.owner, legacy.command(data))
            result['partial'] = PayrollStatements(legacy.office).get(legacy.technician, run['id'])['statement']
        finally:
            legacy.doCleanups()
        return result
    finally:
        test.doCleanups()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(fixture(), ensure_ascii=False, sort_keys=True, indent=2) + '\n')
