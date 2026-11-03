"""Independent v3 review: published rules, literal cents and real clock facts.

BMF 25.11.2020 Rz90/example59 and LStR2026 R40.2(4) were read
independently. Expected figures below are hand-derived, not calculator output.
"""
import copy
from datetime import date, timedelta
import unittest

from payroll_travel_2026_v3 import calculate
from payroll_travel_2026_v1 import calculate as historical_v1
from payroll_travel_2026_v2 import calculate as historical_v2
from payroll_travel_ground_2026 import resolve_ground_calendar
from test_payroll_travel_2026 import site, trip, meal, night, ref


def programme(value, periods):
    sessions = [dict(id=f'{10000+i:032x}', **{'from':a, 'to':b},
                     kind=kind, source_file_ids=['f'*32])
                for i,(a,b,kind) in enumerate(periods)]
    value['details']['private_intervals'] = [
        {k:s[k] for k in ('from','to')} for s in sessions if s['kind']=='private']
    value['details']['mixed_assessment'] = dict(
        method='documented_program_ratio',program_sessions=sessions,
        program_complete=True,cost_allocation_reviewed=True,
        source_file_ids=['f'*32],review_note='Independent programme proof.')
    return value


class TravelV3IndependentReview(unittest.TestCase):
    def setUp(self):
        self.home=site(9901,'home');self.place=site(9902)
        self.sites=[self.home,self.place]

    def daily(self,n=9903,start='08:00',end='18:00',requested=0):
        return trip(n,'2026-02-03T'+start+':00+01:00',
                    '2026-02-03T'+end+':00+01:00',self.place,self.home,requested=requested)

    def test_published_example_59_literal_seven_day_vector(self):
        days=[str(date(2026,2,2)+timedelta(days=n)) for n in range(7)]
        value=trip(9903,days[0]+'T12:00:00+01:00',days[-1]+'T12:00:00+01:00',
                   self.place,self.home,nights=[night(self.place,d) for d in days[:-1]],requested=140)
        value['details']['meals']=[meal('dinner',days[0])]+[
            meal(k,d) for d in days[1:-1] for k in ('breakfast','dinner')]+[meal('breakfast',days[-1])]
        programme(value,[(d+'T'+a+':00+01:00',d+'T'+b+':00+01:00',k)
                         for d in days[1:-1] for a,b,k in
                         [('08:00','12:00','business'),('13:00','17:00','private')]])
        result=calculate([value],self.sites)
        self.assertTrue(result['can_approve'],result['blockers'])
        self.assertEqual([d['meal_allowance_minor'] for d in result['days']],[0,0,0,0,0,0,140])
        self.assertEqual(result['totals']['tax_free_minor'],140)

    def test_25_percent_ceiling_uses_unreduced_business_share_exact_cent(self):
        value=programme(self.daily(),[
            ('2026-02-03T08:00:00+01:00','2026-02-03T12:00:00+01:00','business'),
            ('2026-02-03T13:00:00+01:00','2026-02-03T15:00:00+01:00','private')])
        value['details']['meals']=[meal('breakfast')]
        # 14 EUR * 2/3 -> 9.33; minus full 5.60 = 3.73 tax free.
        # R40.2(4) caps the taxable flat-rate part at 9.33, not 3.73.
        for requested,expected in [(1305,(373,932,0)),(1306,(373,933,0)),(1307,(373,933,1))]:
            result=calculate([value],self.sites,tax_choice='flat_25',requested_meal_minor=requested)
            self.assertTrue(result['can_approve'],result['blockers'])
            self.assertEqual(tuple(result['totals'][k] for k in
                                   ('tax_free_minor','flat_taxable_minor','individual_taxable_minor')),expected)

    def test_full_breakfast_reduction_does_not_expand_pauschal_ceiling(self):
        value=self.daily(requested=2241);value['details']['meals']=[meal('breakfast')]
        result=calculate([value],self.sites,tax_choice='flat_25')
        self.assertEqual(tuple(result['totals'][k] for k in
                               ('tax_free_minor','flat_taxable_minor','individual_taxable_minor')),(840,1400,1))

    def test_same_ratio_multiple_short_trips_aggregate_absence_and_round_once(self):
        one=programme(self.daily(start='08:00',end='13:00'),[
            ('2026-02-03T08:00:00+01:00','2026-02-03T10:00:00+01:00','business'),
            ('2026-02-03T11:00:00+01:00','2026-02-03T12:00:00+01:00','private')])
        two=programme(self.daily(9904,start='15:00',end='20:00'),[
            ('2026-02-03T15:00:00+01:00','2026-02-03T17:00:00+01:00','business'),
            ('2026-02-03T18:00:00+01:00','2026-02-03T19:00:00+01:00','private')])
        result=calculate([one,two],self.sites,settlement_unit='combined_period',requested_meal_minor=933)
        self.assertTrue(result['can_approve'],result['blockers'])
        self.assertEqual(len(result['days']),1)
        self.assertEqual((result['days'][0]['absence_seconds'],result['totals']['meal_allowance_minor']),(36000,933))

    def test_lodging_excess_cannot_be_relabelled_flat_meal_payment(self):
        value=self.daily(requested=1400);value['details']['requested_lodging_minor']=1400
        result=calculate([value],self.sites,tax_choice='flat_25')
        self.assertEqual((result['totals']['tax_free_minor'],result['totals']['flat_taxable_minor'],
                          result['totals']['individual_taxable_minor']),(1400,0,1400))

    def test_dst_short_and_long_calendar_days_preserve_actual_seconds(self):
        for on,offset_start,offset_end,seconds in [
                ('2026-03-29','+01:00','+02:00',82800),('2026-10-25','+02:00','+01:00',90000)]:
            tomorrow=str(date.fromisoformat(on)+timedelta(days=1))
            value=trip(9903,on+'T00:00:00'+offset_start,tomorrow+'T00:00:00'+offset_end,self.place,self.home)
            result=resolve_ground_calendar(value,self.sites)
            self.assertEqual(list(result['days']),[on])
            self.assertEqual(result['days'][on]['absence_seconds'],seconds)

    def test_westbound_midnight_repeated_date_is_not_double_counted(self):
        east=site(9905,country='Finnland',timezone='Europe/Helsinki')
        west=site(9906,country='Schweden',timezone='Europe/Stockholm')
        value=trip(9903,'2026-02-02T22:00:00+01:00','2026-02-03T02:00:00+01:00',east,self.home)
        original=value['details']['segments'][0]
        value['details']['segments']=[dict(original,**{'to':'2026-02-02T23:30:00+01:00'}),
            dict(original,id='a'*32,site_ref=ref(west),**{'from':'2026-02-02T23:30:00+01:00'})]
        result=resolve_ground_calendar(value,[self.home,east,west])
        self.assertEqual([(k,v['absence_seconds']) for k,v in result['days'].items()],
                         [('2026-02-02',5400),('2026-02-03',9000)])

    def test_historical_delegation_exact_equality_and_inputs_immutable(self):
        value=self.daily(requested=840);value['details']['meals']=[meal('breakfast')]
        original=copy.deepcopy((value,self.sites))
        for version,calculator in [('de_travel_2026_v1',historical_v1),('de_travel_2026_v2',historical_v2)]:
            self.assertEqual(calculate([value],self.sites,rule_version=version),calculator([value],self.sites))
        calculate([value],self.sites)
        self.assertEqual((value,self.sites),original)


if __name__=='__main__':unittest.main()
