"""Synthetic U client fixture from actual P4/Source3 originals and receipts."""
import json
from pathlib import Path

from test_business_payroll_wage_interruptions import WageInterruptionWorkflow


def main():
    fixture=WageInterruptionWorkflow('runTest');fixture.setUp()
    try:
        f=fixture.f;details=fixture.originals();command,preview=fixture.command(details)
        sources=fixture.api.sources(f.owner,dict(employee_id=f.employee['id'],year='2026'))
        preview_request={key:command[key] for key in ('employee_id','employee_revision','kind','rule_version','source_contract_version','details','source_file_ids')}
        saved=fixture.api.save(f.owner,command)
        output=dict(sources=sources,preview_request=preview_request,preview=preview,command=command,saved=saved,
            history=fixture.api.get(f.owner,saved['id'],True),records=fixture.api.records(f.owner,dict(employee_id=f.employee['id'],year='2026')),
            ledger=f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026')))
        correction_body,correction_preview=fixture.command(details|dict(verification_note='Actual corrected original review'),
            id=saved['id'],revision=1,correction_reason='Review text corrected from actual original')
        corrected=fixture.api.save(f.owner,correction_body)
        from test_business_payroll import rid
        void_body=correction_body|dict(request_id=rid(),revision=2,status='void',correction_reason='Actual U assessment withdrawn')
        void=fixture.api.save(f.owner,void_body)
        output.update(correction_body=correction_body,correction_preview=correction_preview,corrected=corrected,
            void_body=void_body,void=void,history=fixture.api.get(f.owner,saved['id'],True),
            records_after_void=fixture.api.records(f.owner,dict(employee_id=f.employee['id'],year='2026')))
        target=Path(__file__).resolve().parents[1]/'app/test/fixtures/payroll_wage_interruptions.json'
        target.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
        print('Generated synthetic actual U fixture:',target.name)
    finally:fixture.doCleanups()


if __name__=='__main__':main()
