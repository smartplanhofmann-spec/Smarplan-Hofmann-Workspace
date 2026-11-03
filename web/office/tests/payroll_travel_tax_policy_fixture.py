"""Actual synthetic employer-policy events shared by both client test suites."""
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'backend/online')]

from test_business_payroll_calculation_cases import CalculationCaseTests
from test_business_payroll import rid


def fixture():
    test=CalculationCaseTests('runTest');test.setUp()
    try:
        api=test.api;actor=test.f.owner
        before=api.policy_sources(actor,{})
        saved,body=test.policy()
        preview_body={key:body[key] for key in ('employee_id','employee_revision','kind','rule_version','source_contract_version','details','source_file_ids')}
        preview=api.preview(actor,preview_body)
        sources=api.policy_sources(actor,{})
        correction=deepcopy(body)
        correction.update(request_id=rid(),id=saved['id'],revision=saved['revision'],correction_reason='Synthetic employer policy evidence clarified')
        correction['details']['verification_note']='Synthetic corrected and reviewed employer decision'
        corrected_preview=api.preview(actor,{key:correction[key] for key in preview_body})
        correction['preview_hash']=corrected_preview['preview_hash']
        corrected=api.save(actor,correction)
        void_body=deepcopy(correction)
        void_body.update(request_id=rid(),revision=corrected['revision'],status='void',correction_reason='Synthetic mistaken employer decision withdrawn')
        void=api.save(actor,void_body)
        return dict(sources_before=before,sources=sources,body=body,preview=preview,saved=saved,
                    correction_body=correction,correction_preview=corrected_preview,corrected=corrected,
                    void_body=void_body,void=void,history=api.get(actor,saved['id'],True),
                    capabilities=dict(readonly=False,features=['payroll_calculation_cases'],capabilities=['business_payroll_calculation_cases'],
                        permissions=['personnel.read','personnel.approve'],organization=dict(modules=dict(personnel=dict(enabled=True)))))
    finally:test.doCleanups()


if __name__=='__main__':
    destination=ROOT/'app/test/fixtures/payroll_travel_tax_policies.json'
    destination.write_text(json.dumps(fixture(),ensure_ascii=False,indent=2)+'\n')
    print('Actual synthetic employer policy fixture written; no company records used.')
