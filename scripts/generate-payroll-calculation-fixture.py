"""Generate synthetic client contracts through actual private domain commands.

Run with PYTHONPATH=backend:backend/online and the verified backend Python.
The disposable SQLite fixture is removed; no customer instance is contacted.
"""
import json
from pathlib import Path

from business_payroll_facts import reference
from payroll_travel_recording import validate_tax_recording
from test_business_payroll_calculations import CalculationPayrollWorkflow


def main():
    fixture=CalculationPayrollWorkflow('runTest');fixture.setUp()
    try:
        _,settlement=fixture.travel()
        policy,policy_command=fixture.policy(employer_bears_tax=False)
        f=fixture.f;details=fixture.details();details['travel_settlement_refs']=[reference(settlement)]
        details['flat_tax_decision']=dict(policy_ref=reference(policy),church_membership_evidence=None,
            employee_deduction_file_ref=dict(id=f.data['file']['id'],revision=1,content_hash=f.data['file']['content_hash']),
            tax_certificate_file_ref=None,tax_certificate_issued_on=None,record_on_finalize=True)
        sources=fixture.api.sources(f.owner,dict(employee_id=f.employee['id'],month='2026-10'))
        command,preview=fixture.request(details)
        preview_request={key:command[key] for key in ('employee_id','employee_revision','kind','rule_version','source_contract_version','details','source_file_ids')}
        saved=fixture.api.save(f.owner,command)
        run_input=dict(source_schema_version=3,employee_id=f.employee['id'],calculation_case_ref=reference(saved))
        run_preview=f.payroll.preview(f.owner,run_input);run_command=fixture.command(saved)
        run=f.payroll.finalize(f.owner,run_command);fixture.payment(run)
        output=dict(sources=sources,preview_request=preview_request,preview=preview,command=command,saved=saved,
            history=fixture.api.get(f.owner,saved['id'],True),run_input=run_input,run_preview=run_preview,run_command=run_command,run=run,
            ledger=f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026')),tax_recording=validate_tax_recording(f.office,run),
            policy_sources=fixture.api.policy_sources(f.owner,{}),policy_command=policy_command,policy=policy)
        target=Path(__file__).resolve().parents[1]/'app/test/fixtures/payroll_calculation_cases.json'
        target.write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n')
        print('Generated synthetic actual source3 client fixture:',target.name)
    finally:fixture.doCleanups()
    fixture=CalculationPayrollWorkflow('runTest');fixture.setUp()
    try:
        _,settlement=fixture.travel();policy,policy_command=fixture.policy(method='evidence')
        f=fixture.f;details=fixture.details();details['travel_settlement_refs']=[reference(settlement)]
        details['flat_tax_decision']=dict(policy_ref=reference(policy),
            church_membership_evidence=dict(kind='elstam',reference=reference(f.identity),church_tax=False),
            employee_deduction_file_ref=None,tax_certificate_file_ref=None,tax_certificate_issued_on=None,record_on_finalize=True)
        sources=fixture.api.sources(f.owner,dict(employee_id=f.employee['id'],month='2026-10'))
        command,preview=fixture.request(details)
        saved=fixture.api.save(f.owner,command)
        preview_request={key:command[key] for key in ('employee_id','employee_revision','kind','rule_version','source_contract_version','details','source_file_ids')}
        output=dict(sources=sources,preview_request=preview_request,preview=preview,command=command,saved=saved,
            policy=policy,policy_command=policy_command,history=fixture.api.get(f.owner,saved['id'],True))
        target=Path(__file__).resolve().parents[1]/'app/test/fixtures/payroll_calculation_case_evidence.json'
        target.write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n')
        print('Generated synthetic actual ELStAM case fixture:',target.name)
    finally:fixture.doCleanups()


if __name__=='__main__':main()
