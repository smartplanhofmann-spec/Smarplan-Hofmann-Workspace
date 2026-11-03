"""Create synthetic real-domain snapshots for the two private travel clients.

No production data, provider, network or outgoing payment is involved.
"""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'backend'))
from test_business_travel_allowances import TravelWorkflowTests
from test_business_planning import rid
from business_travel_allowances import _ref
from travel_allowance_cash import record_payment,public_source


def snapshot():
    fixture=TravelWorkflowTests()
    fixture.setUp()
    try:
        airport=fixture.api.save_site(fixture.technician,dict(request_id=rid(),employee_id=fixture.employee['id'],id=rid(),revision=0,status='active',correction_reason='',details={**fixture.place['details'],'name':'Synthetic departure airport','kind':'mobile'}))['result']
        origin=fixture.upload(purpose='expense_receipt',visible=True,actor=fixture.technician,marker=b'Synthetic separately evidenced transport expense')
        expense=fixture.hr.save_expense(fixture.technician,dict(request_id=rid(),employee_id=fixture.employee['id'],revision=0,
            purpose='Synthetic transport expense',start_date='2026-10-26',end_date='2026-10-26',items=[dict(date='2026-10-26',description='Actual synthetic ticket',amount_minor=1000,currency='EUR',receipt_file_id=origin['id'],project_id=fixture.project)]))
        expense=fixture.hr.expense_action(fixture.technician,expense['id'],'submit',dict(request_id=rid(),revision=expense['revision']))
        expense=fixture.hr.expense_action(fixture.owner,expense['id'],'approve',dict(request_id=rid(),revision=expense['revision'],reason='Synthetic independent original verification'))
        trip_body=fixture.trip_body(expense_refs=[_ref(expense)],expense_allocations=[dict(expense_ref=_ref(expense),receipt_file_id=origin['id'],kind='transport',business_minor=600,private_minor=400,provided_minor=0,review_note='Actual synthetic original split, no input VAT')])
        segment=trip_body['details']['segments'][0];segment['transport']='flight';segment['activity']='transit'
        trip_body['details']['transport_facts']=[dict(id=rid(),kind='flight',legs=[dict(segment_id=segment['id'],departure_site_ref=_ref(airport),arrival_site_ref=_ref(fixture.place))],stopovers=[],source_file_ids=[fixture.file['id']])]
        saved=fixture.api.save_trip(fixture.technician,trip_body)
        trip=fixture.api.trip_action(fixture.technician,saved['target_id'],'submit',dict(request_id=rid(),employee_id=fixture.employee['id'],revision=saved['revision'],source_hash=fixture.api._basis(fixture.employee['id']),confirmed=True))['result']
        approval_body=fixture.approval(trip)
        preview_body={key:value for key,value in approval_body.items() if key not in ('request_id','id','revision','source_hash','preview_hash','confirmed')}
        preview=fixture.api.preview(fixture.owner,preview_body)
        approval=fixture.api.approve(fixture.owner,approval_body)
        payment_body=fixture.payment(approval['result'],1000)
        paid=record_payment(fixture.api,fixture.owner,payment_body)
        legacy_origin=fixture.upload(purpose='expense_receipt',visible=True,actor=fixture.technician,marker=b'Synthetic fully business paid historical expense')
        legacy_expense=fixture.hr.save_expense(fixture.technician,dict(request_id=rid(),employee_id=fixture.employee['id'],revision=0,purpose='Synthetic earlier paid expense',start_date='2026-10-27',end_date='2026-10-27',items=[dict(date='2026-10-27',description='Original earlier business ticket',amount_minor=1000,currency='EUR',receipt_file_id=legacy_origin['id'],project_id=None)]))
        legacy_expense=fixture.hr.expense_action(fixture.technician,legacy_expense['id'],'submit',dict(request_id=rid(),revision=legacy_expense['revision']))
        legacy_expense=fixture.hr.expense_action(fixture.owner,legacy_expense['id'],'approve',dict(request_id=rid(),revision=legacy_expense['revision'],reason='Reviewed actual legacy original'))
        legacy_expense=fixture.hr.expense_action(fixture.owner,legacy_expense['id'],'reimburse',dict(request_id=rid(),revision=legacy_expense['revision'],payment_reference='SYN-LEGACY-ACTUAL-PAYMENT',paid_on='2026-10-28',amount_minor=1000,confirmed=True))
        legacy_trip_body=fixture.trip_body(expense_refs=[_ref(legacy_expense)],expense_allocations=[dict(expense_ref=_ref(legacy_expense),receipt_file_id=legacy_origin['id'],kind='transport',business_minor=1000,private_minor=0,provided_minor=0,review_note='Entire original is business, actual earlier reimbursement retained')])
        ld=legacy_trip_body['details'];ld['departed_at']='2026-10-27T08:00:00+01:00';ld['returned_at']='2026-10-27T18:00:00+01:00';ld['segments'][0]['from']=ld['departed_at'];ld['segments'][0]['to']=ld['returned_at']
        legacy_trip=fixture.api.save_trip(fixture.technician,legacy_trip_body)['result']
        legacy_trip=fixture.api.trip_action(fixture.technician,legacy_trip['id'],'submit',dict(request_id=rid(),employee_id=fixture.employee['id'],revision=legacy_trip['revision'],source_hash=fixture.api._basis(fixture.employee['id']),confirmed=True))['result']
        legacy_approval=fixture.approval(legacy_trip,period_from='2026-10-27',period_to='2026-10-27')
        legacy_settlement=fixture.api.approve(fixture.owner,legacy_approval)['result']
        from business_personnel_workflow import _sha
        original_payment=legacy_expense['payments'][0]
        legacy_body=fixture.payment(legacy_settlement,1000,action='adopt_legacy',paid_on=original_payment['paid_on'],reference=original_payment['reference'],legacy_payment=dict(expense_ref=_ref(legacy_expense),payment_index=0,payment_hash=_sha(original_payment)))
        legacy_receipt=record_payment(fixture.api,fixture.owner,legacy_body)
        legacy=dict(expense=legacy_expense,settlement=legacy_settlement,body=legacy_body,receipt=legacy_receipt,cash_source=public_source(fixture.office,legacy_receipt['target_id']))
        return dict(provenance='Synthetic actual TravelAllowances/PersonnelWorkflow domain commands; generated by web/office/tests/travel_fixture.py',
            legacy=legacy,employee=fixture.employee,sources=fixture.api.sources(fixture.owner,fixture.employee['id']),
            trip_body=trip_body,trip_receipt=saved,trip=trip,preview_body=preview_body,preview=preview,approval_body=approval_body,approval_receipt=approval,
            payment_body=payment_body,payment_receipt=paid,cash_source=public_source(fixture.office,paid['target_id']))
    finally:
        fixture.tearDown()
        fixture.doCleanups()

if __name__=='__main__':
    target=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'app/test/fixtures/travel_allowances.json'
    value=snapshot();target.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(target=str(target),rule_version=value['preview']['rule_version'],totals=value['preview']['totals']),ensure_ascii=False))
