"""Independent complete-calculator checks of the isolated transport helper."""
import copy
import unittest
from payroll_travel_2026 import calculate
from payroll_travel_rates_2026 import country_rate
from test_payroll_travel_2026 import site,trip,night,ref,meal


class IntegratedTravelRules(unittest.TestCase):
    def setUp(self):
        self.home=site(501,'home');self.port=site(502);self.sea=site(503,'mobile',country='Luxemburg');self.oslo=site(504,country='Norwegen')

    def voyage(self):
        value=trip(505,'2026-02-02T12:00:00+01:00','2026-02-04T10:00:00+01:00',self.sea,self.home,
            nights=[night(self.sea,'2026-02-02'),night(self.sea,'2026-02-03')],requested=12700)
        segment=value['details']['segments'][0];segment.update(activity='transit',transport='ship')
        value['details']['transport_facts']=[dict(id='a'*32,kind='ship',segment_ids=[segment['id']],departure_site_ref=ref(self.port),arrival_site_ref=ref(self.oslo),role='passenger',high_seas_segment_ids=[segment['id']],source_file_ids=['f'*32])]
        return value

    def test_full_claim_has_14_63_50_and_one_meal_reduction_using_the_sea_rate(self):
        value=self.voyage();value['details']['meals']=[meal(on='2026-02-03')];value['details']['requested_meal_minor']=11440
        result=calculate([value],[self.home,self.port,self.sea,self.oslo])
        self.assertTrue(result['can_approve'],result['blockers']);self.assertEqual([d['base_minor'] for d in result['days']],[1400,6300,5000])
        self.assertEqual(result['days'][1]['meal_reduction_minor'],1260)
        self.assertEqual(result['totals']['tax_free_minor'],11440);self.assertTrue(result['payroll_required']);self.assertFalse(result['can_pay'])
        self.assertEqual(len(result['transport_sources']),1)

    def test_qualified_german_high_seas_crew_changes_only_sea_day(self):
        value=self.voyage();value['details']['transport_facts'][0]['role']='german_merchant_crew';value['details']['requested_meal_minor']=9200
        result=calculate([value],[self.home,self.port,self.sea,self.oslo])
        self.assertTrue(result['can_approve'],result['blockers']);self.assertEqual([d['base_minor'] for d in result['days']],[1400,2800,5000])

    def test_ship_cabin_is_not_an_ordinary_lodging_allowance_without_actual_other_lodging(self):
        value=self.voyage();value['details']['overnights'][0].update(claim_method='flat',provided_by='employee',accommodation_kind='ship_cabin')
        result=calculate([value],[self.home,self.port,self.sea,self.oslo])
        self.assertFalse(result['can_approve']);self.assertIn('vehicle_lodging_not_eligible',[b['code'] for b in result['blockers']])
        value['details']['overnights'][0]['other_lodging_started_or_finished']=True
        result=calculate([value],[self.home,self.port,self.sea,self.oslo])
        self.assertTrue(result['can_approve'],result['blockers']);self.assertEqual(result['totals']['lodging_allowance_minor'],13900)

    def test_v1_remains_frozen_and_does_not_reinterpret_a_new_ship_proof(self):
        value=self.voyage()
        latest=calculate([value],[self.home,self.port,self.sea,self.oslo])
        original=calculate([value],[self.home,self.port,self.sea,self.oslo],rule_version='de_travel_2026_v1')
        self.assertEqual(latest['days'][0]['base_minor'],1400);self.assertEqual(original['days'][0]['base_minor'],4200)
        self.assertNotIn('transport_sources',original);self.assertNotEqual(latest['rule_hash'],original['rule_hash'])

    def test_unrelated_hotel_cannot_substantiate_an_overnight_never_visited(self):
        value=self.voyage();value['details']['overnights'][0]['site_ref']=ref(self.oslo)
        result=calculate([value],[self.home,self.port,self.sea,self.oslo])
        self.assertFalse(result['can_approve']);self.assertIn('overnight_location_missing',[b['code'] for b in result['blockers']])

    def test_bmf_replacement_breakfast_with_real_own_charge_and_self_purchase(self):
        original=meal(on='2026-02-03');replacement=meal(on='2026-02-03',id='9'*32,price=1600,own=600,replacement_for=original['id'])
        value=trip(509,'2026-02-03T08:00:00+01:00','2026-02-03T18:00:00+01:00',self.port,self.home,requested=1400,meals=[original,replacement])
        result=calculate([value],[self.home,self.port]);self.assertTrue(result['can_approve']);self.assertEqual(result['days'][0]['meal_reduction_minor'],0)
        value['details']['meals'][1]['provider']='self';value['details']['requested_meal_minor']=840
        result=calculate([value],[self.home,self.port]);self.assertEqual(result['days'][0]['meal_reduction_minor'],560)

    def test_bmf_combined_replacement_lunch_over_60_is_actual_benefit_without_m(self):
        original=meal(kind='lunch',on='2026-02-03',price=3000);replacement=meal(kind='lunch',on='2026-02-03',id='9'*32,price=3500,replacement_for=original['id'])
        value=trip(510,'2026-02-03T08:00:00+01:00','2026-02-03T18:00:00+01:00',self.port,self.home,requested=1400,meals=[original,replacement])
        result=calculate([value],[self.home,self.port]);self.assertTrue(result['can_approve']);day=result['days'][0]
        self.assertEqual((day['meal_reduction_minor'],day['benefit_in_kind_minor'],day['letter_m']),(0,6500,False))
        self.assertFalse(result['can_pay'])

    def test_full_long_flight_journey_applies_austria_only_to_actual_intermediate_flight_day(self):
        plane=site(511,'mobile');tokyo=site(512,country='Japan',region='Tokio',timezone='Asia/Tokyo')
        value=trip(513,'2026-02-02T21:00:00+01:00','2026-02-06T08:00:00+01:00',plane,self.home,requested=19700,
            nights=[night(plane,'2026-02-02'),night(plane,'2026-02-03'),night(tokyo,'2026-02-04'),night(plane,'2026-02-05')])
        template=value['details']['segments'][0]
        outbound=dict(template,id='1'*32,**{'to':'2026-02-04T14:00:00+09:00'},activity='transit',transport='flight')
        work=dict(template,id='2'*32,**{'from':outbound['to'],'to':'2026-02-05T20:00:00+09:00'},site_ref=ref(tokyo))
        inbound=dict(template,id='3'*32,**{'from':work['to']},activity='transit',transport='flight')
        value['details']['segments']=[outbound,work,inbound]
        value['details']['transport_facts']=[dict(id='4'*32,kind='flight',legs=[dict(segment_id=outbound['id'],departure_site_ref=ref(self.port),arrival_site_ref=ref(tokyo))],stopovers=[],source_file_ids=['f'*32]),
            dict(id='5'*32,kind='flight',legs=[dict(segment_id=inbound['id'],departure_site_ref=ref(tokyo),arrival_site_ref=ref(self.port))],stopovers=[],source_file_ids=['f'*32])]
        result=calculate([value],[self.home,self.port,plane,tokyo])
        self.assertTrue(result['can_approve'],result['blockers']);self.assertEqual([d['base_minor'] for d in result['days']],[1400,5000,5000,5000,3300])
        self.assertEqual([d['country'] for d in result['days']],['Deutschland','Österreich','Japan','Japan','Japan'])

    def test_taxable_lodging_excess_is_not_relabelled_as_flat_taxable_meal_allowance(self):
        value=trip(514,'2026-02-03T08:00:00+01:00','2026-02-03T18:00:00+01:00',self.port,self.home,requested=0)
        value['details']['requested_lodging_minor']=1800
        result=calculate([value],[self.home,self.port],tax_choice='flat_25')
        self.assertEqual((result['totals']['tax_free_minor'],result['totals']['flat_taxable_minor'],result['totals']['individual_taxable_minor']),(1400,0,400))
