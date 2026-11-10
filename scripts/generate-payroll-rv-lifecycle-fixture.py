"""Generate controlled actual API originals for both RV clients; no providers."""
import json
from pathlib import Path
import sys

from test_business_payroll_rv_binding import RvPayrollBinding


def generate():
    cases=[]
    for name in ('established','pending','settled'):
        f=RvPayrollBinding('runTest');f.setUp()
        try:
            original_sources=f.api.sources(f.f.owner,dict(employee_id=f.f.employee['id']))
            body=f.body()
            if name!='established':
                from test_payroll_minijob_rv_lifecycle_2026 import request,settled
                (request if name=='pending' else settled)(body['details']['assessment'])
            preview=f.api.preview(f.f.owner,body)
            record,command=f.save(body)
            result=dict(name=name,employee=f.f.employee,sources_before=original_sources,input=body,preview=preview,
                command=command,record=record,sources=f.api.sources(f.f.owner,dict(employee_id=f.f.employee['id'])))
            if name=='settled':
                profile_command=f.profile_command(record)
                profile=f.f.payroll.save_profile(f.f.owner,profile_command)
                f.data['inputs'].update(profile_id=profile['id'],profile_revision=profile['revision'])
                result.update(profile_command=profile_command,profile=profile,
                    payroll_preview=f.f.payroll.preview(f.f.owner,f.data['inputs']))
                payroll_command=f.f.command(f.data)
                result.update(payroll_command=payroll_command,run=f.f.payroll.finalize(f.f.owner,payroll_command))
            cases.append(result)
        finally:f.doCleanups()
    return dict(schema_version=1,synthetic=True,external_transmission=False,cases=cases)


if __name__=='__main__':
    target=Path(sys.argv[1]);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(generate(),ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    print(str(target))
