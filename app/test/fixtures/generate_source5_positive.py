"""Generate shared native/browser fixtures through actual accepted workflows."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
parser=argparse.ArgumentParser()
parser.add_argument('--backend-root',type=Path,default=ROOT/'backend')
args=parser.parse_args()
sys.path.insert(0,str(args.backend_root.resolve()))
from test_business_payroll_positive_corrections import PositiveCorrectionFixture

f=PositiveCorrectionFixture('runTest')
try:
    f.setUp()
    def snapshot(prior_run=None,prior_payment=None):
        employee=f.f.employee['id']
        return deepcopy(dict(run=f.run,run_input=f.run_input,run_preview=f.preview,run_command=f.command,
            case=f.case,case_command=f.case_command,payment=f.payment,payment_command=f.payment_command,
            prior_run=prior_run,prior_payment=prior_payment,employee=f.f.employee,
            files=f.f.hr.files(f.f.owner,dict(employee_id=employee))['items'],
            sources=f.m.api.sources(f.f.owner,dict(employee_id=employee,month=f.run['source']['month']))))
    f.first();initial=snapshot()
    old_run,old_payment=deepcopy(f.run),deepcopy(f.payment)
    f.correction(1500000);f.pay();first=snapshot(old_run,old_payment)
    old_run,old_payment=deepcopy(f.run),deepcopy(f.payment)
    f.correction(1000000);f.pay('SOURCE5-SECOND-CORRECTED-BONUS');second=snapshot(old_run,old_payment)
    result=dict(initial=initial,correction=first,second_correction=second)
    path=Path(__file__).with_name('source5_positive_corrections.json')
    path.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(dict(bytes=path.stat().st_size,first_additional=first['run']['settlement_transition']['additional_net_minor'],
        second_additional=second['run']['settlement_transition']['additional_net_minor'])))
finally:
    f.doCleanups()
