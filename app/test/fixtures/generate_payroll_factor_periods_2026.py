"""Controlled factor-period originals, corrections and employee statements."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'backend/online')]
from test_business_payroll_factor_periods import FactorPeriodWorkflow
from test_business_payroll_periods import inputs,command
from business_payroll_statements import project,package

fixture=FactorPeriodWorkflow('runTest');fixture.setUp();f=fixture.f
try:
    fact,body,period_preview=f.period()
    run_input=inputs(f.employee['id'],fact)
    preview=f.payroll.preview(f.owner,run_input);run_command=command(f.payroll,f.owner,run_input)
    run=f.payroll.finalize(f.owner,run_command)
    sources=f.api.sources(f.owner,dict(employee_id=f.employee['id']))
    changed,corrected_preview,corrected_command,corrected_run=fixture.correct(fact,run)
    value=dict(employee=f.employee,file=f.data['file'],profile=run['source']['profile'],
        period_case=fact,period_body=body,period_preview=period_preview,facts_sources=sources,
        inputs=run_input,preview=preview,command=run_command,run=run,statement=package(project(run)),
        corrected_period_case=changed,corrected_inputs=corrected_run['source']['input'],
        corrected_preview=corrected_preview,corrected_command=corrected_command,
        corrected_run=corrected_run,corrected_statement=package(project(corrected_run)))
    target=ROOT/'app/test/fixtures/payroll_factor_periods_2026_workflow.json'
    target.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(fixture=str(target.relative_to(ROOT)),net_minor=run['calculation']['net_minor'],
        corrected_net_minor=corrected_run['calculation']['net_minor'],tax_days=fact['plan']['tax_periods'][0]['tax_days'])))
finally:fixture.doCleanups()
