"""Generate actual synthetic Source4 run and monetary client contracts."""
import json
from pathlib import Path

import business_schema
from business_payroll_facts import reference
import test_business_payroll_accounts as account_fixture
import test_business_payroll_periods as period_fixture
from test_business_payroll_oneoff_runs import OneoffRunWorkflow


def corrected_source4(fixture,original_case,original_run,original_payment):
    """Actual larger accepted claim; original transfer remains an exact part."""
    f=fixture.f;source=original_case['sources']['calculation_source']
    earning=source['one_off_earning'];details=earning['details']|dict(amount_minor=70000)
    body,_=f.request('one_off_earning',details)
    earning=f.annual.save(f.owner,body|dict(id=earning['id'],revision=earning['revision'],correction_reason='Actual documented contractual bonus amount corrected'))
    forecast=source['annual_tax_forecast'];details=forecast['details']|dict(current_one_off_ref=reference(earning))
    body,_=f.request('annual_tax_forecast',details)
    forecast=f.annual.save(f.owner,body|dict(id=forecast['id'],revision=forecast['revision'],correction_reason='Forecast bound to corrected actual bonus claim'))
    fixture.source=dict(source,one_off_earning=earning,annual_tax_forecast=forecast)
    body,case_preview=fixture.request(id=original_case['id'],revision=original_case['revision'],correction_reason='Actual revised claim and tax forecast reviewed')
    case=fixture.api.save(f.owner,body)
    inputs=dict(source_schema_version=4,employee_id=f.employee['id'],one_off_case_ref=reference(case))
    preview=f.payroll.preview(f.owner,inputs)
    command=fixture.command(case,id=original_run['id'],revision=original_run['revision'],correction_reason='Actual larger bonus; preserve paid original')
    run=f.payroll.finalize(f.owner,command)
    delta=run['calculation']['payout_minor']-original_run['calculation']['payout_minor']
    assert delta>0
    parts=original_payment['details']['payments']+[dict(paid_on='2026-10-31',amount_minor=delta,payment_reference='SYN-V6-ACTUAL-CORRECTION-DELTA')]
    payment,payment_command=fixture.payment(run,payments=parts)
    assert business_schema.validate_integrity(f.office)
    return dict(case_preview=case_preview,case_command=body,case=case,run_input=inputs,run_preview=preview,
        run_command=command,run=run,payment_command=payment_command,payment=payment)


def paid_v5_upgrade():
    fixture=OneoffRunWorkflow('runTest');fixture.setUp()
    try:
        case,_=fixture.workflow();f=fixture.f;running=case['sources']['calculation_source']['running_calculation_case']
        inputs=dict(source_schema_version=3,employee_id=f.employee['id'],calculation_case_ref=reference(running))
        old_command=period_fixture.command(f.payroll,f.owner,inputs);old=f.payroll.finalize(f.owner,old_command)
        original_part=dict(paid_on='2026-10-31',amount_minor=old['calculation']['payout_minor'],payment_reference='SYN-V5-FIXTURE-ORIGINAL-PAYMENT')
        old_payment,old_payment_command=f.save_account(f.data,'payment',account_fixture.PayrollAccountTests.payment_details(f,old,f.identity,payments=[original_part]))
        inputs=dict(source_schema_version=4,employee_id=f.employee['id'],one_off_case_ref=reference(case))
        preview=f.payroll.preview(f.owner,inputs)
        command=fixture.command(case,id=old['id'],revision=old['revision'],correction_reason='Actual separately evidenced bonus added to paid v5 original')
        run=f.payroll.finalize(f.owner,command);delta=run['calculation']['payout_minor']-old['calculation']['payout_minor']
        payment,payment_command=fixture.payment(run,payments=[original_part,dict(paid_on='2026-10-31',amount_minor=delta,payment_reference='SYN-V6-FIXTURE-ADDED-BONUS')])
        assert business_schema.validate_integrity(f.office)
        return dict(original_run=old,original_run_command=old_command,original_payment=old_payment,original_payment_command=old_payment_command,
            case=case,run_input=inputs,run_preview=preview,run_command=command,run=run,payment=payment,payment_command=payment_command)
    finally:fixture.doCleanups()


def main():
    fixture=OneoffRunWorkflow('runTest');fixture.setUp()
    try:
        fixture.source=fixture.c.source(flat_travel=True,shifted=True);f=fixture.f
        sources=fixture.api.sources(f.owner,dict(employee_id=f.employee['id'],month='2026-10'))
        command,preview=fixture.request();saved=fixture.api.save(f.owner,command)
        fields=('employee_id','employee_revision','kind','rule_version','source_contract_version','details','source_file_ids')
        run_input=dict(source_schema_version=4,employee_id=f.employee['id'],one_off_case_ref=reference(saved))
        run_preview=f.payroll.preview(f.owner,run_input);run_command=fixture.command(saved)
        run=f.payroll.finalize(f.owner,run_command);payment,payment_command=fixture.payment(run)
        ledger=f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026'))
        finance=fixture.finance();cash_sources=finance.api.sources(f.owner,f.employee['id'])
        net_body=finance.body(payment);net_command=finance.command(net_body);net=finance.api.confirm(f.owner,net_command)
        remit_body=finance.remittance(f.data,run,payment);remit_command=finance.command(remit_body);remit=finance.api.confirm(f.owner,remit_command)
        entries=[finance.post('payroll_cash',finance.payload(batch)) for batch in (net,remit)]
        output=dict(sources=sources,preview_request={key:command[key] for key in fields},preview=preview,command=command,saved=saved,
            history=fixture.api.get(f.owner,saved['id'],True),run_input=run_input,run_preview=run_preview,run_command=run_command,run=run,
            payment_command=payment_command,payment=payment,ledger=ledger,cash_sources=cash_sources,
            net_command=net_command,net_batch=net,remittance_command=remit_command,remittance_batch=remit,
            euer_entries=entries,euer_report=finance.euer.report(f.owner,2026))
        output['correction']=corrected_source4(fixture,saved,run,payment)
        output['paid_v5_upgrade']=paid_v5_upgrade()
        target=Path(__file__).resolve().parents[1]/'app/test/fixtures/payroll_oneoff_runs.json'
        target.write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n')
        print('Generated actual Source4 case, run and money fixture:',target.name)
    finally:fixture.doCleanups()


if __name__=='__main__':main()
