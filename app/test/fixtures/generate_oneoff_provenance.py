"""Freeze actual accepted historical Windows one-off originals for both clients."""
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'backend'))
from test_business_payroll_oneoff_provenance import OneoffOriginalTransport
from payroll_oneoff_composition_2026 import calculate_oneoff_source
from payroll_multiple_oneoff_2026 import calculate_multiple_source

OneoffOriginalTransport.setUpClass()
test=OneoffOriginalTransport('runTest')
try:
    single=test.fixture4()
    with patch('business_payroll_oneoff_cases.calculate_oneoff_source',side_effect=test.windows_calculate):
        case,_=single.workflow()
    run=single.f.payroll.finalize(single.f.owner,single.command(case))
    multiple=test.fixture5()
    with patch('business_payroll_multiple_cases.calculate_multiple_source',side_effect=test.windows_calculate):
        old=multiple.paid_upgrade()
    def original(run,key,calculate):
        record=run['source'][key];snapshot=record['sources']['calculation_source']
        return dict(preview=dict(source=run['source'],calculation=run['calculation'],can_finalize=True),
            calculation_lf=calculate(snapshot,rule_version=record['rule_version'],source_contract_version=1))
    result=dict(single=original(run,'one_off_case',calculate_oneoff_source),
        multiple=original(old['run'],'multiple_one_off_case',calculate_multiple_source),
        multiple_payment=dict(run_metadata={key:value for key,value in old['run'].items() if key not in ('source','calculation')},
            details=old['payment']['details'],plan=old['payment']['sources']['single_payment_plan'],
            prior_payment=old['old_payment']))
    target=Path(__file__).with_name('oneoff_provenance_workflow.json')
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(bytes=target.stat().st_size,single_rule=case['rule_version'],
        multiple_rule=result['multiple']['preview']['calculation']['rule_version'])))
finally:
    test.doCleanups();OneoffOriginalTransport.doClassCleanups()
