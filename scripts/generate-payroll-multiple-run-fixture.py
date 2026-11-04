"""Generate real synthetic private Source5 cases, transfers and client contracts."""
import json
from pathlib import Path

import business_schema
from business_payroll_facts import reference
from test_business_payroll_multiple import MultipleWorkflow
from test_business_payroll_accounts import PayrollAccountTests
from test_business_payroll_calculations import CalculationPayrollWorkflow

CASE_FIELDS=('employee_id','employee_revision','kind','rule_version','source_contract_version','details','source_file_ids')


def generated_initial():
    w=MultipleWorkflow('runTest');w.setUp()
    try:
        f=w.f;sources=w.api.sources(f.owner,dict(employee_id=f.employee['id'],month='2026-10'))
        case,command=w.case();proposal={key:command[key] for key in CASE_FIELDS}
        preview=w.api.preview(f.owner,proposal)
        inputs=dict(source_schema_version=5,employee_id=f.employee['id'],multiple_one_off_case_ref=reference(case))
        run_preview=f.payroll.preview(f.owner,inputs);run_command=w.run_command(case);run=f.payroll.finalize(f.owner,run_command)
        calc=run['calculation'];running=calc['running_calculation'];running_due=running['net_minor']-running['net_deductions_minor']
        bonus=calc['net_minor']-calc['net_deductions_minor']-running_due
        parts=[dict(paid_on='2026-10-30',amount_minor=running_due,payment_reference='SYN-V7-INITIAL-RUNNING-30'),
            dict(paid_on='2026-10-31',amount_minor=bonus,payment_reference='SYN-V7-INITIAL-BONUS-31')]
        details=PayrollAccountTests.payment_details(f,run,f.identity,payments=parts)
        details.update(payment_source_schema_version=1,prior_payment_ref=None,settlement_allocations=[
            dict(payment_index=0,running_minor=running_due,one_off_allocations=[]),
            dict(payment_index=1,running_minor=0,one_off_allocations=[dict(event_key=w.source['components'][0]['planned_receipts'][0]['event_key'],net_minor=bonus)])])
        payment,payment_command=f.save_account(f.data,'payment',details)
        ledger=f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026'))
        finance=CalculationPayrollWorkflow.finance(w);cash_sources=finance.api.sources(f.owner,f.employee['id'])
        net_body=finance.body(payment);net_command=finance.command(net_body);net=finance.api.confirm(f.owner,net_command)
        remittance_body=finance.remittance(f.data,run,payment);remittance_command=finance.command(remittance_body)
        remittance=finance.api.confirm(f.owner,remittance_command)
        entries=[finance.post('payroll_cash',finance.payload(value)) for value in (net,remittance)]
        assert business_schema.validate_integrity(f.office)
        return dict(sources=sources,preview_request=proposal,preview=preview,command=command,saved=case,
            history=w.api.get(f.owner,case['id'],True),run_input=inputs,run_preview=run_preview,run_command=run_command,run=run,
            payment_command=payment_command,payment=payment,ledger=ledger,cash_sources=cash_sources,
            net_command=net_command,net_batch=net,remittance_command=remittance_command,remittance_batch=remittance,
            euer_entries=entries,euer_report=finance.euer.report(f.owner,2026))
    finally:w.doCleanups()


def generated_upgrade():
    w=MultipleWorkflow('runTest');w.setUp()
    try:
        state=w.paid_upgrade(cash=True);f=w.f;run=state['run'];finance=state['finance'];case=run['source']['multiple_one_off_case']
        inputs=run['source']['input'];preview=f.payroll.preview(f.owner,inputs)
        body=finance.body(state['payment']);body['sources'][0]['payment_indexes']=[1]
        cash_sources=finance.api.sources(f.owner,f.employee['id']);net_command=finance.command(body);net=finance.api.confirm(f.owner,net_command)
        entries=[finance.post('payroll_cash',finance.payload(value)) for value in (state['first'],net)]
        assert business_schema.validate_integrity(f.office)
        return dict(original_run=state['old'],original_payment=state['old_payment'],original_net_batch=state['first'],
            case=case,run_input=inputs,run_preview=preview,run_command=state['body'],run=run,
            payment_command=state['payment_body'],payment=state['payment'],cash_sources=cash_sources,
            net_command=net_command,net_batch=net,ledger=f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026')),
            euer_entries=entries,euer_report=finance.euer.report(f.owner,2026))
    finally:w.doCleanups()


def generated_blocked():
    w=MultipleWorkflow('runTest');w.setUp()
    try:
        w.c.additional(w.source,amount=10000);case,command=w.case();proposal={key:command[key] for key in CASE_FIELDS}
        inputs=dict(source_schema_version=5,employee_id=w.f.employee['id'],multiple_one_off_case_ref=reference(case))
        return dict(preview_request=proposal,preview=w.api.preview(w.f.owner,proposal),command=command,saved=case,
            run_input=inputs,run_preview=w.f.payroll.preview(w.f.owner,inputs))
    finally:w.doCleanups()


def main():
    output=generated_initial();output['paid_v5_upgrade']=generated_upgrade();output['blocked_multiple']=generated_blocked()
    target=Path(__file__).resolve().parents[1]/'app/test/fixtures/payroll_multiple_runs.json'
    target.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print('Generated real synthetic Source5 fixture:',target.name,'bytes:',target.stat().st_size)


if __name__=='__main__':main()
