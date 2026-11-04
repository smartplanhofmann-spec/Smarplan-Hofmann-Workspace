#!/usr/bin/env python3
"""Actual v2 carryover exports; never overwrite the frozen v1 client fixture."""
import base64
from copy import deepcopy
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'backend/online')]
import test_accounting_year_package_v2 as fixtures
from business_accounting_euer import dispatch
from accounting_year_package_v1 import sha
from accounting_year_verify_v2 import verify


def capture(f,entry):
    path='/accounting/euer/exports/'+entry['id'];actor=f.owner;office=f.office
    exported,status,kind=dispatch(office,actor,path,'GET',{});assert status==200 and kind=='application/json'
    metadata,status,kind=dispatch(office,actor,path+'/evidence','GET',{});assert status==200 and kind=='application/json'
    raw,status,kind=dispatch(office,actor,path+'/evidence/archive','GET',{});assert status==200 and kind=='application/zip'
    assert verify(bytes(raw),metadata['sha256'])['intrinsic_dependency_closure'] is False
    return dict(export=exported,metadata=metadata,archive_base64=base64.b64encode(raw).decode())


def main():
    result=dict(schema_version=1,format='smartplan-year-evidence-v2',synthetic_only=True,scenarios={})
    f=fixtures.YearPackageCarryover('runTest');f.setUp()
    try:
        pending=f.f.f.euer.post('export',{'year':2026});result['scenarios']['pending_review']=capture(f,pending)
        payload=deepcopy(f.f.payload);payload['coverage']={'from':'2026-08-01','through':'2026-10-31'};payload['controls']=payload['controls'][:2]
        entry,_=f.f.save(payload);posted=f.f.classify(entry);export=f.f.f.euer.post('export',{'year':2026})
        result['scenarios']['partial_coverage']=capture(f,export)
        f.f.f.euer.post('reverse',{'entry_id':posted['id']});f.f.save(dict(payload,status='void'))
        entry,_=f.f.save();f.f.classify(entry);payment,_=f.f.f.payment(f.f.old,'59.50',day='2026-11-01');f.f.f.classify(payment)
        final=f.f.f.euer.post('export',{'year':2026});result['scenarios']['complete_history']=capture(f,final)
        result['scenarios']['old_partial_after_correction']=capture(f,export)
        assert result['scenarios']['partial_coverage']==result['scenarios']['old_partial_after_correction']
    finally:f.doCleanups()
    raw=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode()
    for name in ('docs/fixtures/accounting_year_package_v2.json','app/test/fixtures/accounting_year_package_v2.json'):
        p=ROOT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    print(json.dumps(dict(bytes=len(raw),sha256=sha(raw),scenarios=list(result['scenarios']))))

if __name__=='__main__':main()
