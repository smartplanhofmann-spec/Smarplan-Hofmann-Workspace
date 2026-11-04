"""Actual synthetic Source3 zero-payable private account client contracts."""
import base64
import json
from pathlib import Path

from test_business_payroll import rid
from test_business_payroll_accounts import PayrollAccountTests
from test_business_payroll_calculations import CalculationPayrollWorkflow


def main():
    fixture=CalculationPayrollWorkflow('runTest');fixture.setUp()
    try:
        _,_,_,case,run=fixture.preemployment_zero_case();f=fixture.f
        api=f.account_api();query=dict(employee_id=f.employee['id'],year='2026')
        before=api.records(f.owner,dict(employee_id=f.employee['id']))
        details=PayrollAccountTests.payment_details(f,run,f.identity,payments=[])
        saved,command=f.save_account(f.data,'payment',details)
        correction=command|dict(request_id=rid(),id=saved['id'],revision=1,correction_reason='Actual protected zero-payable original reviewed again')
        corrected=api.save(f.owner,correction)
        ledger=f.payroll.ledger(f.owner,query)
        pdf=f.payroll.export_ledger(f.owner,query|dict(snapshot_hash=ledger['ledger']['snapshot_hash']),'pdf')[0]
        output=dict(employee=f.employee,run=run,case=case,identity=f.identity,records_before=before,
            command=command,saved=saved,correction_body=correction,corrected=corrected,
            history=api.get(f.owner,saved['id'],True),records=api.records(f.owner,dict(employee_id=f.employee['id'])),
            ledger=ledger,ledger_pdf_base64=base64.b64encode(pdf).decode(),
            sources=fixture.api.sources(f.owner,dict(employee_id=f.employee['id'],month='2026-10')))
        target=Path(__file__).resolve().parents[1]/'app/test/fixtures/payroll_zero_account.json'
        target.write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n')
        print('Generated actual zero-payable original and correction:',target.name)
    finally:fixture.doCleanups()


if __name__=='__main__':main()
