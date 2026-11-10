"""Accepted controlled factor/claim originals for independent clients."""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'backend'))
from test_business_payroll_factor_entitlements import FactorEntitlementFixture


def bundle(f):
    return dict(schema_version=1,scope='actual original-bound full-month factor with separately evidenced unpaid claim',
        employee=f.f.employee,files=[f.f.data['file']],profile=f.f.data['profile'],identity=f.f.identity,
        period=f.base,claim=f.claim,sources=f.sources,case_input=f.case_input,
        case_preview=f.case_preview,case_command=f.case_command,case=f.case,
        run_input=f.run_input,run_preview=f.run_preview,run_command=f.run_command,run=f.run)

def main():
    f=FactorEntitlementFixture('runTest');f.setUp()
    try:
        f.unpaid();f.accepted()
        value=bundle(f)
        hourly=FactorEntitlementFixture('runTest');hourly.setUp()
        try:
            hourly.hourly_public_holiday();hourly.accepted();value['hourly']=bundle(hourly)
        finally:hourly.doCleanups()
        target=ROOT/'app/test/fixtures/payroll_factor_claims.json'
        target.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
        print(target.relative_to(ROOT),target.stat().st_size,'bytes; actually accepted factor/P4 case and run')
    finally:f.doCleanups()


if __name__=='__main__':main()
