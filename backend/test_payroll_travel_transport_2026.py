"""Derived R9.6(3) transport cases; reviewed source amounts, no real journeys."""
import copy
import unittest

from core import Problem
from payroll_travel_transport_2026 import resolve_transport_days, TRAVEL_TRANSPORT_HASH
from payroll_travel_rates_2026 import rate
from test_payroll_travel_2026 import site, ref


class TravelTransportTests(unittest.TestCase):
    def setUp(self):
        self.serial=200
        self.home=site(201,'home')
        self.de=site(202)
        self.be=site(203,country='Belgien')
        self.tokyo=site(204,country='Japan',region='Tokio',timezone='Asia/Tokyo')
        self.sg=site(205,country='Singapur',timezone='Asia/Singapore')
        self.oslo=site(206,country='Norwegen',timezone='Europe/Oslo')
        self.hawaii=site(207,country='Vereinigte Staaten von Amerika (USA)',region='im Übrigen',timezone='Pacific/Honolulu')
        self.sea=site(208,'mobile',country='Luxemburg')
        self.places=[self.home,self.de,self.be,self.tokyo,self.sg,self.oslo,self.hawaii,self.sea]

    def ident(self):
        self.serial+=1
        return f'{self.serial:032x}'

    def segment(self,start,finish,place,transport='ground',activity='work',necessary=False):
        return dict(id=self.ident(),**{'from':start,'to':finish},site_ref=ref(place),
                    activity=activity,transport=transport,necessary_stopover=necessary)

    def flight(self,legs,stops=None):
        return dict(id=self.ident(),kind='flight',legs=[dict(segment_id=s['id'],departure_site_ref=ref(a),arrival_site_ref=ref(b))
                    for s,a,b in legs],stopovers=stops or [],source_file_ids=['f'*32])

    def ship(self,segments,role='passenger',high=None):
        return dict(id=self.ident(),kind='ship',segment_ids=[s['id'] for s in segments],
                    departure_site_ref=ref(self.de),arrival_site_ref=ref(self.oslo),role=role,
                    high_seas_segment_ids=[s['id'] for s in (high or [])],source_file_ids=['f'*32])

    def journey(self,segments,facts,nights=None):
        return dict(id='a'*32,revision=1,content_hash='a'*64,details=dict(
            departed_at=segments[0]['from'],returned_at=segments[-1]['to'],timezone='Europe/Berlin',
            segments=segments,transport_facts=facts,overnights=nights or []))

    def resolve(self,value):return resolve_transport_days(value,self.places)

    def country(self,result,on):return rate(result['days'][on]['rate_id'])['country']

    def test_ground_trip_needs_no_transport_extension(self):
        value=self.journey([self.segment('2026-02-02T08:00:00+01:00','2026-02-02T18:00:00+01:00',self.be)],[])
        del value['details']['transport_facts']
        result=self.resolve(value)
        self.assertEqual((result['days'],result['calendar_days'],result['blockers']),({},[],[]))
        self.assertEqual(result['transport_rule_hash'],TRAVEL_TRANSPORT_HASH)

    def test_flight_without_required_airport_facts_has_a_concrete_blocker(self):
        value=self.journey([self.segment('2026-02-02T20:00:00+01:00','2026-02-03T01:00:00+01:00',self.be,'flight','transit')],[])
        result=self.resolve(value)
        self.assertEqual([x['code'] for x in result['blockers']],['transport_facts_missing'])

    def test_foreign_country_is_reached_only_on_actual_landing(self):
        flight=self.segment('2026-02-02T20:00:00+01:00','2026-02-03T01:00:00+01:00',self.be,'flight','transit')
        stay=self.segment(flight['to'],'2026-02-04T18:00:00+01:00',self.be)
        result=self.resolve(self.journey([flight,stay],[self.flight([(flight,self.de,self.be)])]))
        self.assertEqual(self.country(result,'2026-02-02'),'Deutschland')
        self.assertEqual(self.country(result,'2026-02-03'),'Belgien')
        self.assertEqual(result['blockers'],[])

    def long_flight(self,necessary=False):
        first=self.segment('2026-02-02T21:00:00+01:00','2026-02-03T18:00:00+08:00',self.sg,'flight','transit')
        second_start='2026-02-04T06:00:00+08:00' if necessary else '2026-02-03T23:00:00+08:00'
        gap=self.segment(first['to'],second_start,self.sg,activity='stay' if necessary else 'transit',necessary=necessary)
        second=self.segment(second_start,'2026-02-04T14:00:00+09:00',self.tokyo,'flight','transit')
        stay=self.segment(second['to'],'2026-02-05T18:00:00+09:00',self.tokyo)
        night=dict(id=self.ident(),date='2026-02-03',site_ref=ref(self.sg),claim_method='none',provided_by='employer',expense_ref=None)
        stops=[dict(after_segment_id=first['id'],overnight_ids=[night['id']])] if necessary else []
        fact=self.flight([(first,self.de,self.sg),(second,self.sg,self.tokyo)],stops)
        return self.journey([first,gap,second,stay],[fact],[night] if necessary else [])

    def test_more_than_two_local_flight_days_uses_austria_for_intermediate_day(self):
        result=self.resolve(self.long_flight())
        self.assertEqual(self.country(result,'2026-02-02'),'Deutschland')
        self.assertEqual(self.country(result,'2026-02-03'),'Österreich')
        self.assertEqual(rate(result['days']['2026-02-03']['rate_id'])['full_minor'],5000)
        self.assertEqual(self.country(result,'2026-02-04'),'Japan')
        self.assertEqual(result['blockers'],[])

    def test_necessary_proved_stopover_night_changes_the_reached_country(self):
        result=self.resolve(self.long_flight(True))
        self.assertEqual(self.country(result,'2026-02-03'),'Singapur')
        self.assertEqual(rate(result['days']['2026-02-03']['rate_id'])['full_minor'],7100)
        self.assertEqual(self.country(result,'2026-02-04'),'Japan')
        self.assertEqual(result['blockers'],[])

    def test_necessary_stopover_without_linked_night_cannot_silently_use_flight_rule(self):
        value=self.long_flight(True);value['details']['transport_facts'][0]['stopovers']=[]
        result=self.resolve(value)
        self.assertIn('transport_stopover_night_missing',[x['code'] for x in result['blockers']])

    def test_wrong_night_date_or_unproved_necessity_is_not_a_valid_stopover(self):
        for mutation in ('date','necessity'):
            value=self.long_flight(True)
            if mutation=='date':value['details']['overnights'][0]['date']='2026-02-02'
            else:value['details']['segments'][1]['necessary_stopover']=False
            with self.subTest(mutation=mutation),self.assertRaises(Problem):self.resolve(value)

    def test_return_to_germany_keeps_last_foreign_workplace(self):
        work=self.segment('2026-02-02T08:00:00+01:00','2026-02-03T14:00:00+01:00',self.be)
        flight=self.segment(work['to'],'2026-02-03T16:00:00+01:00',self.de,'flight','transit')
        home=self.segment(flight['to'],'2026-02-03T18:00:00+01:00',self.home,activity='transit')
        result=self.resolve(self.journey([work,flight,home],[self.flight([(flight,self.be,self.de)])]))
        self.assertEqual(self.country(result,'2026-02-03'),'Belgien')
        self.assertEqual(result['days']['2026-02-03']['reason'],'last_foreign_workplace_return')

    def voyage(self,role='passenger',high=True):
        ship=self.segment('2026-02-02T12:00:00+01:00','2026-02-04T10:00:00+01:00',self.sea,'ship','transit')
        return self.journey([ship],[self.ship([ship],role,[ship] if high else [])])

    def test_ship_uses_embarkation_and_disembarkation_ports_and_luxembourg_at_sea(self):
        result=self.resolve(self.voyage())
        self.assertEqual([self.country(result,d) for d in ('2026-02-02','2026-02-03','2026-02-04')],['Deutschland','Luxemburg','Norwegen'])
        self.assertEqual([rate(result['days'][d]['rate_id'])[key] for d,key in
            [('2026-02-02','short_minor'),('2026-02-03','full_minor'),('2026-02-04','short_minor')]],[1400,6300,5000])

    def test_qualifying_german_crew_on_high_seas_uses_inland_not_luxembourg(self):
        for role in ('german_state_crew','german_merchant_crew'):
            result=self.resolve(self.voyage(role))
            self.assertEqual(rate(result['days']['2026-02-03']['rate_id'])['full_minor'],2800)
            self.assertEqual(self.country(result,'2026-02-04'),'Norwegen')
        result=self.resolve(self.voyage('german_merchant_crew',False))
        self.assertEqual(self.country(result,'2026-02-03'),'Luxemburg')

    def test_repeated_local_date_after_dateline_crossing_is_resolved_once(self):
        before=self.segment('2026-02-01T12:00:00+09:00','2026-02-03T00:00:00+09:00',self.tokyo)
        flight=self.segment(before['to'],'2026-02-02T12:00:00-10:00',self.hawaii,'flight','transit')
        after=self.segment(flight['to'],'2026-02-04T12:00:00-10:00',self.hawaii)
        result=self.resolve(self.journey([before,flight,after],[self.flight([(flight,self.tokyo,self.hawaii)])]))
        self.assertEqual(list(result['days']),['2026-02-02','2026-02-03'])
        self.assertEqual([self.country(result,d) for d in result['days']],['Vereinigte Staaten von Amerika (USA)']*2)
        self.assertEqual(len({x['date'] for x in result['calendar_days']}),2)
        self.assertEqual(result['blockers'],[])
        self.assertEqual(result['calendar_days'][0]['utc_from'],'2026-02-02T10:00:00+00:00')

    def test_rate_id_or_unlinked_timestamp_cannot_be_chosen_in_transport_input(self):
        for added in ({'rate_id':'de_2026'},{'departed_at':'2026-01-01T00:00:00Z'}):
            value=self.voyage();value['details']['transport_facts'][0].update(added)
            with self.assertRaises(Problem):self.resolve(value)

    def test_duplicate_segment_coverage_and_foreign_high_seas_segment_are_rejected(self):
        value=self.voyage();duplicate=copy.deepcopy(value['details']['transport_facts'][0]);duplicate['id']=self.ident()
        value['details']['transport_facts'].append(duplicate)
        with self.assertRaises(Problem):self.resolve(value)
        value=self.voyage();value['details']['transport_facts'][0]['high_seas_segment_ids']=[self.ident()]
        with self.assertRaises(Problem):self.resolve(value)

    def test_source_fact_hash_changes_when_actual_source_or_route_changes(self):
        value=self.voyage();first=self.resolve(value)
        self.assertEqual(self.resolve(copy.deepcopy(value))['facts_hash'],first['facts_hash'])
        value['details']['transport_facts'][0]['source_file_ids']=['d'*32]
        self.assertNotEqual(self.resolve(value)['facts_hash'],first['facts_hash'])

    def test_expired_port_source_blocks_even_when_sea_segment_source_is_current(self):
        self.oslo['details']['effective_to']='2026-02-03'
        result=self.resolve(self.voyage())
        self.assertIn('transport_site_validity',[b['code'] for b in result['blockers']])

    def test_actual_trip_bounds_and_flight_connection_cannot_be_reordered(self):
        value=self.long_flight();value['details']['departed_at']='2026-02-02T20:00:00+01:00'
        with self.assertRaises(Problem):self.resolve(value)
        value=self.long_flight();value['details']['transport_facts'][0]['legs'].reverse()
        with self.assertRaises(Problem):self.resolve(value)

    def test_home_cannot_be_an_airport_or_port_but_first_workplace_can(self):
        for kind in ('flight','ship'):
            for key in ('departure_site_ref','arrival_site_ref'):
                value=self.long_flight() if kind=='flight' else self.voyage()
                fact=value['details']['transport_facts'][0]
                target=fact['legs'][0] if kind=='flight' else fact
                target[key]=ref(self.home)
                with self.subTest(kind=kind,key=key),self.assertRaises(Problem):self.resolve(value)
        self.de['details']['kind']='first_workplace'
        self.assertEqual(self.resolve(self.voyage())['blockers'],[])
        self.assertEqual(self.resolve(self.long_flight())['blockers'],[])

