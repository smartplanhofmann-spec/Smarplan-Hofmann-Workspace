"""Actual employee originals, independent mileage review and existing cash/EÜR."""
from copy import deepcopy
from pathlib import Path
import base64
import unittest

from core import Problem, canonical
import business_schema
from business_foundation import BusinessFoundation
from business_travel_allowances import TravelAllowances, _ref, validate_integrity
from business_travel_mileage import MileageTravel, RULE_VERSION, dispatch
from business_accounting_euer import EuerAccounting
from travel_allowance_cash import record_payment, public_source, restore_horizon
from test_business_planning import rid
import test_business_travel_allowances as travel
import test_business_travel_finance as finance
import test_business_bank_reconciliation as bank


class MileageFixture:
    def __init__(self, owner):
        class CanonicalTravelFixture(travel.TravelWorkflowTests):
            def prepare(self):
                super().prepare()
                self.temporary.name=str(Path(self.temporary.name).resolve(strict=True))
        self.f=f=CanonicalTravelFixture('runTest');f.setUp();owner.addCleanup(f.doCleanups)
        self.api=MileageTravel(f.office,clock=lambda:f.now)
        preparation=bank.BankTests('runTest');preparation.office=f.office;preparation.owner=f.owner;preparation.configure()
        self.vehicle=f.upload(visible=True,marker=b'Synthetic private car and employee vehicle costs')
        self.evidence=f.upload(visible=True,marker=b'Synthetic complete driven route no other reimbursement')
        for key in ('home','place'):
            before=getattr(f,key)
            command=dict(request_id=rid(),employee_id=f.employee['id'],id=before['id'],revision=before['revision'],
                status='active',correction_reason='Bind actual private personnel original',
                details=dict(before['details'],source_file_ids=[self.evidence['id']]))
            setattr(f,key,f.api.save_site(f.owner,command)['result'])
        self.input=dict(request_id=rid(),employee_id=f.employee['id'],id=rid(),revision=0,correction_reason='',details=dict(
            purpose='Actual domestic customer measurement',project_id=f.project,
            departed_at='2026-10-26T08:00:00+01:00',returned_at='2026-10-26T13:00:00+01:00',timezone='Europe/Berlin',
            home_site_ref=_ref(f.home),first_workplace_ref=None,source_file_ids=[self.vehicle['id'],self.evidence['id']],
            mileage=dict(schema_version=1,vehicle_kind='private_car',vehicle_registration='SYNTHETIC-1',
                vehicle_file_id=self.vehicle['id'],declaration_file_id=self.evidence['id'],
                employee_bears_vehicle_costs=True,no_employer_vehicle=True,only_business_travel=True,
                no_commuting_or_family_home=True,no_collection_point_or_wide_area=True,no_other_reimbursement=True,
                review_note='Actual complete private-car journey and own vehicle costs evidenced',legs=[
                    dict(id=rid(),departed_at='2026-10-26T08:00:00+01:00',arrived_at='2026-10-26T09:00:00+01:00',
                        from_site_ref=_ref(f.home),to_site_ref=_ref(f.place),distance_m=50000,evidence_file_id=self.evidence['id']),
                    dict(id=rid(),departed_at='2026-10-26T12:00:00+01:00',arrived_at='2026-10-26T13:00:00+01:00',
                        from_site_ref=_ref(f.place),to_site_ref=_ref(f.home),distance_m=50000,evidence_file_id=self.evidence['id'])])))

    def submitted(self):
        f=self.f;self.draft_command=deepcopy(self.input)
        self.draft=self.api.save_trip(f.technician,self.draft_command)['result']
        self.submit_command=dict(request_id=rid(),employee_id=f.employee['id'],revision=self.draft['revision'],
            source_hash=self.api._basis(f.employee['id']),confirmed=True)
        self.trip=self.api.trip_action(f.technician,self.draft['id'],'submit',self.submit_command)['result']
        return self.trip

    def approval(self, trip=None, previous=None):
        f=self.f;trip=trip or self.trip
        self.preview_input=dict(employee_id=f.employee['id'],trip_refs=[_ref(trip)],period_from='2026-10-26',period_to='2026-10-26',
            settlement_unit='trip',tax_choice='tax_free_only',requested_meal_minor=0,requested_lodging_minor=0,
            correction_of=_ref(previous) if previous else None,review_note='Independent complete route and private car evidence checked')
        self.preview=self.api.preview(f.owner,self.preview_input)
        self.approve_command=dict(self.preview_input,id=previous['id'] if previous else rid(),request_id=rid(),
            revision=previous['revision'] if previous else 0,source_hash=self.preview['source_hash'],
            preview_hash=self.preview['preview_hash'],confirmed=True)
        self.settlement=self.api.approve(f.owner,self.approve_command)['result']
        return self.settlement


class MileageBusinessTests(unittest.TestCase):
    def setUp(self):
        self.x=MileageFixture(self);self.f=self.x.f;self.api=self.x.api

    def failure(self,status,callback):
        with self.assertRaises(Problem) as caught:callback()
        self.assertEqual(caught.exception.status,status,caught.exception.message)

    def test_actual_own_submission_independent_approval_and_unchanged_receipts(self):
        x=self.x;f=self.f;trip=x.submitted();settlement=x.approval()
        self.assertEqual(settlement['calculation']['totals']['tax_free_minor'],3000)
        self.assertFalse(settlement['calculation']['payroll_required'])
        self.assertFalse(settlement['calculation']['days'][0]['letter_m'])
        self.assertEqual(self.api.save_trip(f.technician,x.draft_command)['result'],x.draft)
        self.assertEqual(self.api.trip_action(f.technician,trip['id'],'submit',x.submit_command)['result'],trip)
        self.assertEqual(self.api.approve(f.owner,x.approve_command)['result'],settlement)
        self.assertEqual(self.api.status(f.owner,x.approve_command['request_id'])['result'],settlement)
        pdf,_=self.api.export(f.owner,settlement['id'],1,'pdf');self.assertTrue(pdf.startswith(b'%PDF-'))
        self.assertEqual(self.api.export(f.owner,settlement['id'],1,'pdf')[0],pdf)
        self.assertEqual(self.api.listing(f.owner,'trip',f.employee['id'])['items'],[trip])
        self.assertEqual(f.api.listing(f.owner,'trip',f.employee['id'])['items'],[])
        self.assertEqual(f.api.listing(f.owner,'settlement',f.employee['id'])['items'],[])
        self.failure(409,lambda:f.api.preview(f.owner,x.preview_input))
        from travel_payroll_sources import travel_payroll_source
        self.failure(409,lambda:travel_payroll_source(f.office,f.owner,_ref(settlement),'2026-10'))
        self.failure(409,lambda:f.api.save_trip(f.technician,dict(x.input,request_id=rid(),revision=trip['revision'])))
        self.assertTrue(validate_integrity(f.office))
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_no_payment_before_approval_no_self_approval_and_no_double_person_day(self):
        x=self.x;f=self.f;x.submitted()
        body=deepcopy(x.input);body['request_id']=rid();body['id']=rid()
        self.failure(400,lambda:self.api.save_trip(f.technician,dict(body,details=dict(body['details'],
            mileage=dict(body['details']['mileage'],vehicle_kind='employer_car')))))
        proposal=dict(employee_id=f.employee['id'],trip_refs=[_ref(x.trip)],period_from='2026-10-26',period_to='2026-10-26',
            settlement_unit='trip',tax_choice='tax_free_only',requested_meal_minor=0,requested_lodging_minor=0,correction_of=None,review_note='Self review prohibited')
        preview=self.api.preview(f.owner,proposal)
        self.failure(403,lambda:self.api.approve(f.technician,dict(proposal,id=rid(),request_id=rid(),revision=0,
            source_hash=preview['source_hash'],preview_hash=preview['preview_hash'],confirmed=True)))
        x.approval()
        preview=self.api.preview(f.owner,proposal)
        self.assertFalse(preview['can_approve'])
        self.failure(409,lambda:self.api.approve(f.owner,dict(proposal,id=rid(),request_id=rid(),revision=0,
            source_hash=preview['source_hash'],preview_hash=preview['preview_hash'],confirmed=True)))
        self.assertEqual(f.office.db.execute('SELECT COUNT(*) FROM business_travel_payments').fetchone()[0],0)

    def test_actual_partial_cash_euer_and_private_boundary(self):
        x=self.x;f=self.f;x.submitted();settlement=x.approval()
        payment_command=f.payment(settlement,1000);first=record_payment(self.api,f.owner,payment_command)['result']
        self.assertEqual(record_payment(self.api,f.owner,payment_command)['result'],first)
        second=record_payment(self.api,f.owner,f.payment(settlement,2000))['result']
        public=public_source(f.office,first['id'])
        for secret in ('SYNTHETIC-1','Actual domestic customer measurement',self.x.evidence['filename']):
            self.assertNotIn(secret,canonical(public))
        ledger=finance.TravelFinanceTests('runTest');ledger.f=f;ledger.office=f.office;ledger.owner=f.owner
        ledger.euer=EuerAccounting(f.office,clock=lambda:f.now)
        for payment in (first,second):ledger.post('travel_cash',ledger.payload(payment))
        self.assertEqual(ledger.euer.report(f.owner,2026)['totals']['confirmed_expenses'],'30.00')
        self.failure(409,lambda:record_payment(self.api,f.owner,f.payment(settlement,1)))
        self.assertTrue(validate_integrity(f.office));self.assertTrue(restore_horizon(f.office))
        self.assertEqual(f.api.listing(f.owner,'payment',f.employee['id'])['items'],[])

    def test_new_payment_rechecks_originals_and_rejects_advances_and_legacy_write_path(self):
        x=self.x;f=self.f;x.submitted();settlement=x.approval()
        self.failure(400,lambda:record_payment(self.api,f.owner,f.payment(settlement,1000,paid_on='2026-10-25')))
        self.failure(409,lambda:record_payment(f.api,f.owner,f.payment(settlement,1000)))
        self.api.trip_action(f.owner,x.trip['id'],'reject',dict(request_id=rid(),employee_id=f.employee['id'],
            revision=x.trip['revision'],source_hash=self.api._basis(f.employee['id']),confirmed=True,reason='Changed actual route evidence'))
        self.failure(409,lambda:record_payment(self.api,f.owner,f.payment(settlement,1000)))
        self.assertEqual(f.office.db.execute('SELECT COUNT(*) FROM business_travel_payments').fetchone()[0],0)

    def test_default_v3_still_calculates_after_new_v4_and_keeps_both_originals(self):
        x=self.x;f=self.f;x.submitted();mileage=x.approval()
        body=f.trip_body()
        body['details']['departed_at']='2026-10-27T08:00:00+01:00';body['details']['returned_at']='2026-10-27T18:00:00+01:00'
        body['details']['segments'][0].update({'from':body['details']['departed_at'],'to':body['details']['returned_at']})
        draft=f.api.save_trip(f.technician,body)['result']
        trip=f.api.trip_action(f.technician,draft['id'],'submit',dict(request_id=rid(),employee_id=f.employee['id'],revision=1,
            source_hash=f.api._basis(f.employee['id']),confirmed=True))['result']
        command=f.approval(trip,period_from='2026-10-27',period_to='2026-10-27')
        legacy=f.api.approve(f.owner,command)['result']
        self.assertEqual(legacy['calculation']['rule_version'],'de_travel_2026_v3')
        self.assertEqual(legacy['calculation']['totals']['tax_free_minor'],1400)
        self.assertEqual(legacy['sources']['history_trips'],[])
        self.assertEqual(f.api.listing(f.owner,'settlement',f.employee['id'])['items'],[legacy])
        self.assertEqual(self.api.listing(f.owner,'settlement',f.employee['id'])['items'],[mileage])
        self.assertEqual(f.api.approve(f.owner,command)['result'],legacy)
        self.assertEqual(self.api.approve(f.owner,x.approve_command)['result'],mileage)
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_same_actual_route_original_cannot_be_claimed_by_another_employee(self):
        x=self.x;f=self.f;x.submitted();x.approval()
        user_id=f.office.add_user('other-mileage@example.test','Synthetic-other-mileage-123','technician')
        employee=f.planning.save_employee(f.owner,dict(request_id=rid(),user_id=user_id,name='Other synthetic employee',
            weekly_minutes=1200,hourly_cost_minor=2000,employment_from='2026-01-01',employment_to=None))
        originals=[]
        for original in (x.vehicle,x.evidence):
            raw=f.hr.file_content(f.owner,original['id'])[0]
            originals.append(f.hr.upload(f.owner,dict(request_id=rid(),employee_id=employee['id'],purpose='personnel',
                owner_visible=True,filename=original['filename'],media_type=original['media_type'],content_base64=base64.b64encode(raw).decode())))
        sites=[]
        for original in (f.home,f.place):
            sites.append(f.api.save_site(f.owner,dict(request_id=rid(),employee_id=employee['id'],id=rid(),revision=0,
                status='active',correction_reason='',details=dict(original['details'],source_file_ids=[originals[1]['id']])) )['result'])
        body=deepcopy(x.input);body.update(request_id=rid(),employee_id=employee['id'],id=rid(),revision=0)
        body['details'].update(home_site_ref=_ref(sites[0]),source_file_ids=[v['id'] for v in originals])
        m=body['details']['mileage'];m.update(vehicle_file_id=originals[0]['id'],declaration_file_id=originals[1]['id'])
        for index,leg in enumerate(m['legs']):
            leg.update(id=rid(),from_site_ref=_ref(sites[index]),to_site_ref=_ref(sites[1-index]),evidence_file_id=originals[1]['id'])
        draft=self.api.save_trip(f.owner,body)['result']
        trip=self.api.trip_action(f.owner,draft['id'],'submit',dict(request_id=rid(),employee_id=employee['id'],revision=1,
            source_hash=self.api._basis(employee['id']),confirmed=True))['result']
        preview=self.api.preview(f.owner,dict(x.preview_input,employee_id=employee['id'],trip_refs=[_ref(trip)]))
        self.assertFalse(preview['can_approve'])
        blocker=next(v for v in preview['blockers'] if v['code']=='mileage_original_already_settled')
        self.assertIsNone(blocker['source_ref'])

    def test_negative_correction_preserves_actual_cash_until_real_refund(self):
        x=self.x;f=self.f;x.submitted();old=x.approval()
        first_command=f.payment(old,3000);first=record_payment(self.api,f.owner,first_command)['result']
        ledger=finance.TravelFinanceTests('runTest');ledger.f=f;ledger.office=f.office;ledger.owner=f.owner
        ledger.euer=EuerAccounting(f.office,clock=lambda:f.now)
        ledger.post('travel_cash',ledger.payload(first))
        self.assertEqual(ledger.euer.report(f.owner,2026)['totals']['confirmed_expenses'],'30.00')
        old_pdf=self.api.export(f.owner,old['id'],1,'pdf')[0]
        rejected=self.api.trip_action(f.owner,x.trip['id'],'reject',dict(request_id=rid(),employee_id=f.employee['id'],
            revision=x.trip['revision'],source_hash=self.api._basis(f.employee['id']),confirmed=True,
            reason='Independent correction of overstated original distance'))['result']
        changed=deepcopy(x.input);changed.update(request_id=rid(),revision=rejected['revision'],correction_reason='Documented actual shorter route')
        for leg in changed['details']['mileage']['legs']:leg['distance_m']=25000
        x.input=changed;x.submitted();corrected=x.approval(previous=old)
        self.assertEqual(corrected['calculation']['totals']['overpaid_minor'],1500)
        self.assertEqual(public_source(f.office,first['id'])['cash_movements'][0]['amount'],'30.00')
        self.assertEqual(ledger.euer.report(f.owner,2026)['totals']['confirmed_expenses'],'30.00')
        self.assertEqual(record_payment(self.api,f.owner,first_command)['result'],first)
        refund=record_payment(self.api,f.owner,f.payment(corrected,1500,kind='repayment'))['result']
        self.assertEqual(public_source(f.office,refund['id'])['cash_movements'][0]['direction'],'in')
        ledger.post('travel_cash',ledger.payload(refund))
        self.assertEqual(ledger.euer.report(f.owner,2026)['totals']['confirmed_expenses'],'15.00')
        self.assertEqual(self.api.export(f.owner,old['id'],1,'pdf')[0],old_pdf)
        self.assertTrue(validate_integrity(f.office))

    def test_false_declaration_and_fresh_privacy_rights_and_http_shapes(self):
        x=self.x;f=self.f;x.input['details']['mileage']['no_other_reimbursement']=False;x.submitted()
        proposal=dict(employee_id=f.employee['id'],trip_refs=[_ref(x.trip)],period_from='2026-10-26',period_to='2026-10-26',
            settlement_unit='trip',tax_choice='tax_free_only',requested_meal_minor=0,requested_lodging_minor=0,correction_of=None,review_note='Missing actual completeness evidence')
        result,status,mime=dispatch(f.office,f.owner,'/personnel/travel/mileage/settlements/preview','POST',proposal)
        self.assertFalse(result['can_approve']);self.assertEqual(status,200)
        self.assertIn('mileage_no_other_reimbursement_missing',[v['code'] for v in result['blockers']])
        self.failure(409,lambda:self.api.approve(f.owner,dict(proposal,id=rid(),request_id=rid(),revision=0,
            source_hash=result['source_hash'],preview_hash=result['preview_hash'],confirmed=True)))
        uid=f.office.add_user('mileage-finance@example.test','Synthetic-Mileage-only-123','accountant')
        actor=dict(f.office.db.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone())
        self.failure(403,lambda:self.api.get(actor,'trip',x.trip['id']))
        f.office.db.execute('UPDATE users SET active=0 WHERE id=?',(f.owner['id'],))
        self.failure(401,lambda:self.api.get(f.owner,'trip',x.trip['id']))


if __name__=='__main__':unittest.main()
