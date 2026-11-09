"""Real MFA/application HTTP for the explicit opt-in mileage contract."""
from copy import deepcopy
import json
import unittest

from business_travel_allowances import _ref
from business_travel_mileage import MileageTravel, RULE_VERSION
from test_business_travel_mileage import MileageFixture
from test_business_planning import rid
from online import test_business_travel_http as existing
from online.test_instance_isolation import MFA_SCHEMA
from online.web import create_app


class MileageHttpTests(unittest.TestCase):
    call=existing.TravelHttpTests.call
    login=existing.TravelHttpTests.login

    def setUp(self):
        self.x=MileageFixture(self);self.f=self.x.f;self.office=self.f.office
        self.office.db.executescript(MFA_SCHEMA)
        self.app=create_app(office=self.office,key=self.f.key,host='travel.example.test',storage=self.f.storage,instance_id=self.f.instance)
        self.client=self.app.test_client();self.token=None
        self.token=self.login('owner@example.test','Synthetic-owner-password-123')
        self.tech=self.login('technician@example.test','Synthetic-technician-password-123')

    def test_real_mfa_http_original_review_cash_and_legacy_separation(self):
        prefix='/business/personnel/travel/mileage';x=self.x;f=self.f
        self.assertEqual(self.call('GET',prefix+'/catalog',token=self.tech).json['rule_version'],RULE_VERSION)
        body=x.input
        draft=self.call('POST',prefix+'/trips',body,token=self.tech).json
        self.assertEqual(self.call('POST',prefix+'/trips',body,token=self.tech).json,draft)
        sources=self.call('GET',prefix+'/sources?employee_id='+f.employee['id'],token=self.tech).json
        submit=dict(request_id=rid(),employee_id=f.employee['id'],revision=1,source_hash=sources['source_hash'],confirmed=True)
        trip=self.call('POST',prefix+'/trips/'+body['id']+'/submit',submit,token=self.tech).json['result']
        preview_body=dict(employee_id=f.employee['id'],trip_refs=[_ref(trip)],period_from='2026-10-26',period_to='2026-10-26',
            settlement_unit='trip',tax_choice='tax_free_only',requested_meal_minor=0,requested_lodging_minor=0,
            correction_of=None,review_note='Actual independent HTTP mileage evidence review')
        preview=self.call('POST',prefix+'/settlements/preview',preview_body).json
        command=dict(preview_body,request_id=rid(),id=rid(),revision=0,source_hash=preview['source_hash'],preview_hash=preview['preview_hash'],confirmed=True)
        settlement=self.call('POST',prefix+'/settlements',command).json['result']
        self.assertEqual(settlement['calculation']['totals']['tax_free_minor'],3000)
        payroll_sources=self.call('GET','/business/payroll/calculation-cases/sources?employee_id='+f.employee['id']+'&month=2026-10').json
        self.assertNotIn(settlement['id'],[x['id'] for x in payroll_sources['travel_settlements']])
        self.call('POST','/business/personnel/travel/settlements/preview',preview_body,status=409)
        self.assertEqual(self.call('GET','/business/personnel/travel/settlements?employee_id='+f.employee['id']).json['items'],[])
        self.assertEqual(self.call('GET',prefix+'/requests/'+command['request_id']).json['result'],settlement)
        pdf=self.call('GET',prefix+'/settlements/'+settlement['id']+'/export?format=pdf&revision=1').data
        self.assertTrue(pdf.startswith(b'%PDF'))
        payment=f.payment(settlement,1000)
        accepted=self.call('POST',prefix+'/payments',payment).json
        self.assertEqual(self.call('POST',prefix+'/payments',payment).json,accepted)
        payroll_sources=self.call('GET','/business/payroll/calculation-cases/sources?employee_id='+f.employee['id']+'&month=2026-10').json
        self.assertNotIn(accepted['target_id'],[x['id'] for x in payroll_sources['travel_payment_proofs']])
        self.call('POST','/business/personnel/travel/payments',f.payment(settlement,1000),status=409)
        public=self.call('GET','/business/personnel/travel/financial/'+accepted['target_id']).json
        self.assertEqual(public['cash_movements'][0]['amount'],'10.00')
        self.assertNotIn('SYNTHETIC-1',json.dumps(public))

    def test_real_http_strict_shapes_and_fresh_revocation_on_original_retry(self):
        prefix='/business/personnel/travel/mileage'
        draft=self.call('POST',prefix+'/trips',self.x.input,token=self.tech).json
        self.call('POST',prefix+'/trips?extra=1',self.x.input,token=self.tech,status=400)
        self.call('GET',prefix+'/catalog?extra=1',token=self.tech,status=400)
        self.call('POST',prefix+'/catalog',{},status=405)
        bad=deepcopy(self.x.input);bad['request_id']=rid();bad['id']=rid();bad['details']['mileage']['legs'][0]['distance_m']=True
        self.call('POST',prefix+'/trips',bad,token=self.tech,status=400)
        self.office.db.execute('UPDATE users SET active=0 WHERE id=?',(self.f.technician['id'],))
        self.call('POST',prefix+'/trips',self.x.input,token=self.tech,status=401)
        self.office.db.execute('UPDATE users SET active=1 WHERE id=?',(self.f.technician['id'],))
        self.assertEqual(self.call('POST',prefix+'/trips',self.x.input,token=self.tech).json,draft)


if __name__=='__main__':unittest.main()
