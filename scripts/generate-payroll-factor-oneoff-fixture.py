"""Actually accepted controlled V15 originals, run, payment and own statement."""
import base64
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'backend'))
from business_payroll_statements import PayrollStatements,render_pdf
from test_business_payroll_factor_oneoff_runs import FactorOneoffRunTests


def main():
    fixture=FactorOneoffRunTests('runTest');fixture.setUp()
    try:
        f=fixture.f;originals=fixture.fixture
        case_sources=originals.api.sources(f.owner,dict(employee_id=f.employee['id'],month='2026-10'))
        case_preview=originals.api.preview(f.owner,originals.proposal())
        annual_sources=originals.fixture.api.sources(f.owner,dict(employee_id=f.employee['id']))
        command=fixture.command(fixture.case);inputs={key:command[key] for key in ('employee_id','source_schema_version','one_off_case_ref')}
        preview=f.payroll.preview(f.owner,inputs);run=f.payroll.finalize(f.owner,command)
        payment,payment_command=fixture.payment(run);statements=PayrollStatements(f.office)
        statement=statements.get(f.technician,run['id'])['statement']
        value=dict(schema_version=1,synthetic_only=True,employee=f.employee,actor=f.technician,
            source=fixture.source,case_sources=case_sources,annual_sources=annual_sources,
            case=fixture.case,case_command=fixture.case_body,case_preview=case_preview,
            run_input=inputs,run_preview=preview,run_command=command,run=run,
            payment=payment,payment_command=payment_command,
            statement=statement,page=statements.records(f.technician),pdf_base64=base64.b64encode(render_pdf(statement)).decode())
        target=ROOT/'app/test/fixtures/payroll_factor_oneoff.json'
        target.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n')
        print(target.relative_to(ROOT),target.stat().st_size,'bytes; actual protected factor/P4/V2/V15 originals and payment')
    finally:fixture.doCleanups()


if __name__=='__main__':main()
