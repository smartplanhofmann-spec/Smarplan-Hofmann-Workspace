"""Synthetic source/receipt contract fixture from the real payroll service."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'backend/online')]
from test_business_payroll import PayrollWorkflowTests, rid
from business_payroll_statements import project, package


f = PayrollWorkflowTests('test_factor_correction_preserves_standard_original_and_exact_retry')
f.setUp()
try:
    data = f.case('regular', 500000, tax_class=4, health_additional_percent='2.90',
        tax_allowance_monthly_minor=0, tax_addition_monthly_minor=0,
        special_cases=['tax_factor'], tax_factor='0.753')
    preview = f.payroll.preview(f.owner, data['inputs'])
    command = f.command(data)
    run = f.payroll.finalize(f.owner, command)
    corrected_profile = f.payroll.save_profile(f.owner, dict(request_id=rid(),
        employee_id=f.employee['id'], id=data['profile']['id'], revision=1,
        profile=dict(data['profile']['profile'], tax_factor='0.900'),
        source_file_id=data['file']['id'], confirmed=True,
        correction_reason='Synthetic documented factor correction'))
    corrected_inputs = dict(data['inputs'], profile_revision=corrected_profile['revision'])
    corrected_preview = f.payroll.preview(f.owner, corrected_inputs)
    corrected_command = dict(corrected_inputs, request_id=rid(), id=run['id'], revision=1,
        preview_hash=corrected_preview['preview_hash'],
        accepted_scope=corrected_preview['calculation']['scope'], confirmed=True,
        correction_reason='Synthetic factor recalculation with original retained')
    corrected_run = f.payroll.finalize(f.owner, corrected_command)
    value = dict(employee=f.employee, **data, preview=preview, command=command, run=run,
        statement=package(project(run)), corrected_profile=corrected_profile,
        corrected_inputs=corrected_inputs, corrected_preview=corrected_preview,
        corrected_command=corrected_command, corrected_run=corrected_run,
        corrected_statement=package(project(corrected_run)))
    target = ROOT / 'app/test/fixtures/payroll_factor_2026_workflow.json'
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(fixture=str(target.relative_to(ROOT)),
        net_minor=run['calculation']['net_minor'],
        corrected_net_minor=corrected_run['calculation']['net_minor'],
        delta=corrected_run['delta'])))
finally:
    f.doCleanups()
