#!/usr/bin/env python3
"""Generate synthetic client receipts through the actual private backend."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'backend'))
from business_payroll_facts import reference
from payroll_factor_periods_2026 import calculate_factor_period_source
from payroll_factor_2026 import calculate_factor
from test_business_payroll_periods import command
from test_payroll_factor_taxfree_travel import FactorTravelFixture


def main():
    fixture=FactorTravelFixture('runTest');fixture.setUp()
    try:
        f=fixture.f
        sources=fixture.api.sources(f.owner,dict(employee_id=f.employee['id'],month='2026-10'))
        body,preview=fixture.prepare();saved=fixture.api.save(f.owner,body)
        run_input=dict(source_schema_version=3,employee_id=f.employee['id'],calculation_case_ref=reference(saved))
        run_preview=f.payroll.preview(f.owner,run_input)
        run_command=command(f.payroll,f.owner,run_input);run=f.payroll.finalize(f.owner,run_command)
        value=dict(schema_version=1,synthetic_only=True,employee_id=f.employee['id'],sources=sources,
            command=body,preview=preview,saved=saved,run_input=run_input,run_preview=run_preview,
            run_command=run_command,run=run,
            v9_base_calculation=calculate_factor_period_source(fixture.base['sources']),
            v8_base_calculation=calculate_factor(f.data['profile']['profile'],'2026-10',500000,full_month_confirmed=True),
            history=fixture.api.get(f.owner,saved['id'],True),
            ledger=f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026')))
        correction_body,correction_preview,corrected,correction_input,correction_command,correction=fixture.correct_factor(saved,run)
        value.update(correction_sources=fixture.api.sources(f.owner,dict(employee_id=f.employee['id'],month='2026-10')),
            correction_case_command=correction_body,correction_case_preview=correction_preview,
            correction_case=corrected,correction_input=correction_input,correction_command=correction_command,
            correction_run=correction,history=fixture.api.get(f.owner,saved['id'],True))
        output=ROOT/'app/test/fixtures/payroll_factor_travel.json'
        output.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(output)
    finally:fixture.doCleanups()


if __name__=='__main__':main()
