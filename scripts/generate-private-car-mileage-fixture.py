#!/usr/bin/env python3
"""Generate real synthetic V4 originals; no arithmetic or acceptance patches."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from test_business_travel_mileage import MileageFixture
from test_business_planning import rid
from business_travel_allowances import _ref,validate_integrity
from travel_allowance_cash import record_payment,public_source
from business_travel_mileage import catalog


def main():
    owner=unittest.TestCase();x=MileageFixture(owner);f=x.f
    try:
        x.submitted();x.approval()
        payment_command=f.payment(x.settlement,3000)
        payment_receipt=record_payment(x.api,f.owner,payment_command)
        initial=deepcopy(dict(trip_command=x.draft_command,draft=x.draft,submit_command=x.submit_command,
            draft_receipt=x.api.status(f.technician,x.draft_command['request_id']),
            submit_receipt=x.api.status(f.technician,x.submit_command['request_id']),
            settlement_receipt=x.api.status(f.owner,x.approve_command['request_id']),
            trip=x.trip,preview_command=x.preview_input,preview=x.preview,settlement_command=x.approve_command,
            settlement=x.settlement,payment_command=payment_command,payment_receipt=payment_receipt,
            payment=payment_receipt['result'],public_source=public_source(f.office,payment_receipt['target_id'])))
        reject_command=dict(request_id=rid(),employee_id=f.employee['id'],revision=x.trip['revision'],
            source_hash=x.api._basis(f.employee['id']),confirmed=True,reason='Independent evidenced reduction of original distance')
        rejected=x.api.trip_action(f.owner,x.trip['id'],'reject',reject_command)['result']
        correction=deepcopy(x.input);correction.update(request_id=rid(),revision=rejected['revision'],correction_reason='Original distance corrected with preserved previous payment')
        for leg in correction['details']['mileage']['legs']:leg['distance_m']=25000
        x.input=correction;x.submitted();x.approval(previous=initial['settlement'])
        refund_command=f.payment(x.settlement,1500,kind='repayment')
        refund_receipt=record_payment(x.api,f.owner,refund_command)
        corrected=deepcopy(dict(reject_command=reject_command,rejected=rejected,
            reject_receipt=x.api.status(f.owner,reject_command['request_id']),
            draft_receipt=x.api.status(f.technician,x.draft_command['request_id']),
            submit_receipt=x.api.status(f.technician,x.submit_command['request_id']),
            settlement_receipt=x.api.status(f.owner,x.approve_command['request_id']),
            trip_command=x.draft_command,draft=x.draft,submit_command=x.submit_command,trip=x.trip,
            preview_command=x.preview_input,preview=x.preview,settlement_command=x.approve_command,
            settlement=x.settlement,payment_command=refund_command,payment_receipt=refund_receipt,
            payment=refund_receipt['result'],public_source=public_source(f.office,refund_receipt['target_id'])))
        assert validate_integrity(f.office)
        document=dict(schema_version=1,provenance='actual_private_business_workflow_no_calculation_patches',
            catalog=catalog(),employee=f.employee,owner={k:f.owner[k] for k in ('id','email','role')},
            employee_actor={k:f.technician[k] for k in ('id','email','role')},project_id=f.project,
            sources=x.api.sources(f.owner,f.employee['id']),employee_sources=x.api.sources(f.technician,f.employee['id']),
            initial=initial,correction=corrected,
            trip_history=x.api.get(f.owner,'trip',x.trip['id'],history=True),
            settlement_history=x.api.get(f.owner,'settlement',x.settlement['id'],history=True),
            payments=x.api.listing(f.owner,'payment',f.employee['id']))
        path=ROOT/'app/test/fixtures/private_car_mileage.json';path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n')
        print(path)
    finally:owner.doCleanups()


if __name__=='__main__':main()
