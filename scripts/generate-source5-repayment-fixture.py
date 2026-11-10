"""Actually accepted controlled repayment originals for independent client verification."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'backend'))
from test_business_payroll_source5_repayments import ActualSource5RepaymentWorkflow
from business_payroll_multiple_cases import PayrollMultipleCases


def main():
    fixture=ActualSource5RepaymentWorkflow('runTest');fixture.setUp()
    try:
        prior,details=fixture.repayment(capture_sources=True)
        paid,command=fixture.f.save_account(fixture.f.data,'payment',details)
        value=dict(schema_version=1,scope='controlled actual employee repayment, unchanged original Source5 gross',
            employee=fixture.f.employee,files=[fixture.f.data['file']],initial_run=fixture.initial_run,
            initial_payment=fixture.initial_payment,prior_run=fixture.prior_run,
            run=fixture.run,run_input=fixture.repayment_input,run_preview=fixture.repayment_preview,
            run_command=fixture.repayment_command,prior_payment=prior,details=details,payment=paid,payment_command=command,
            case=fixture.case,sources=fixture.repayment_sources)
        target=ROOT/'app/test/fixtures/source5_repayment.json'
        target.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
        print(target.relative_to(ROOT),target.stat().st_size,'bytes; actual accepted repayment original')
    finally:
        fixture.doCleanups()


if __name__=='__main__':main()
