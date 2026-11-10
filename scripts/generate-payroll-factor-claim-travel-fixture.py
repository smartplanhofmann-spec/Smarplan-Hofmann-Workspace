"""Actual controlled V13 originals for independent browser and Dart verifiers."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from test_business_payroll_factor_claim_travel import FactorClaimTravelFixture
import test_business_payroll_factor_entitlements as claims_fixture
import test_business_payroll_periods as periods
from business_payroll_facts import reference
from business_payroll_statements import PayrollStatements
from payroll_factor_claim_travel_2026 import RULES,RULES_SHA256


def bundle(kind):
    fixture=FactorClaimTravelFixture('runTest')
    fixture.defer_claim=kind=='hourly'
    fixture.setUp()
    try:
        f=fixture.f
        if kind=='hourly':fixture.hourly_public_holiday()
        previous=None
        if kind=='unused_v12_upgrade':
            previous,_=fixture.save_case(claims_fixture.FactorEntitlementFixture.proposal(fixture))
        sources=fixture.api.sources(f.owner,dict(employee_id=f.employee['id'],month='2026-10'))
        body=fixture.proposal();preview=fixture.api.preview(f.owner,body)
        case,case_command=fixture.save_case(body,previous)
        run_input=dict(employee_id=f.employee['id'],source_schema_version=3,calculation_case_ref=reference(case))
        run_preview=f.payroll.preview(f.owner,run_input)
        run_command=periods.command(f.payroll,f.owner,run_input)
        run=f.payroll.finalize(f.owner,run_command)
        details=body['details']
        values=dict(month=details['month'],period_case_id=details['period_case_ref']['id'],
            employment_terms_ids=[r['id'] for r in details['employment_terms_refs']],
            profile_ids=[r['id'] for r in details['profile_refs']],identity_ids=[r['id'] for r in details['identity_refs']],
            entitlement_case_ids=[r['id'] for r in details['entitlement_case_refs']],
            travel_settlement_ids=[r['id'] for r in details['travel_settlement_refs']],
            travel_payment_ids=[r['id'] for r in details['travel_payment_refs']],
            source_file_ids=body['source_file_ids'],verification_note=details['verification_note'],
            correction_reason=case_command.get('correction_reason',''),confirm_unused_upgrade=previous is not None)
        return dict(kind=kind,employee=f.employee,period=fixture.base,claim=fixture.claim,
            settlement=fixture.settlement,payment=fixture.payment,sources=sources,values=values,previous=previous,
            case_input=body,case_preview=preview,case_command=case_command,case=case,
            run_input=run_input,run_preview=run_preview,run_command=run_command,run=run,
            own_statement=PayrollStatements(f.office).get(f.technician,run['id'])['statement'])
    finally:fixture.doCleanups()


def main():
    value=dict(schema_version=1,rules=RULES,rules_sha256=RULES_SHA256,
        cases=[bundle(kind) for kind in ('monthly','hourly','unused_v12_upgrade')])
    target=ROOT/'app/test/fixtures/payroll_factor_claim_travel.json'
    target.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n')
    print(target.relative_to(ROOT),target.stat().st_size,'bytes;3 actually accepted original/payment/case/run/privacy bundles')


if __name__=='__main__':main()
