"""Independent published amounts, calendar boundaries and meal calculations."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

from core import Problem
from payroll_travel_2026 import calculate,three_month,time_options,moment
from payroll_travel_rates_2026 import RATES,country_rate


def site(n,kind='external_fixed',country='Deutschland',region=None,**changes):
    details=dict(name='Synthetic workplace',kind=kind,address='Synthetic address',rate_id=country_rate(country,region)['id'],
        timezone='Europe/Berlin',effective_from='2026-01-01',effective_to=None,assignment_basis='Explicit evidence',
        regular_days_per_week=2,history_complete_from='2025-09-01',prior_visit_dates=[],source_file_ids=['f'*32])
    details.update(changes)
    return dict(id=hex(n)[2:].zfill(32),revision=1,content_hash=hex(n)[2:].zfill(64),details=details)


def ref(value):return {k:value[k] for k in ('id','revision','content_hash')}


def trip(n,start,end,place,home,*,nights=None,meals=None,requested=0):
    return dict(id=hex(n)[2:].zfill(32),revision=1,content_hash=hex(n)[2:].zfill(64),details=dict(
        purpose='Synthetic actual business travel',project_id=None,departed_at=start,returned_at=end,timezone='Europe/Berlin',
        source_file_ids=['f'*32],home_site_ref=ref(home),first_workplace_ref=None,
        segments=[dict(id='e'*32,**{'from':start,'to':end},site_ref=ref(place),activity='work',transport='ground',necessary_stopover=False)],
        overnights=nights or [],meals=meals or [],expense_refs=[],requested_meal_minor=requested,requested_lodging_minor=0,
        tax_choice='tax_free_only',private_intervals=[]))


def meal(kind='breakfast',on='2026-02-03',own=0,price=1500,**changes):
    return dict(id=hashlib.sha256((kind+on).encode()).hexdigest()[:32],date=on,kind=kind,provider='employer_arranged',offered=True,is_meal=True,
        price_minor=price,employee_paid_minor=own,replacement_for=None,source_file_ids=['f'*32])|changes


def night(place,on):
    return dict(id=hashlib.sha256((place['id']+on).encode()).hexdigest()[:32],date=on,site_ref=ref(place),claim_method='none',provided_by='employer',expense_ref=None)


class TravelRulesTests(unittest.TestCase):
    def setUp(self):self.home=site(1,'home');self.place=site(2)
    def test_complete_published_214_rates_and_independent_control_values(self):
        source=json.loads((Path(__file__).parent.parent/'docs/evidence/travel-rates-2026-transcription.json').read_text())
        self.assertEqual(len(RATES),215);self.assertEqual(len({r['id'] for r in RATES}),215)
        for actual,expected in zip(RATES[1:],source['rates']):
            self.assertEqual(actual,{k:expected[k] for k in actual})
        for country,region,wanted in [('Belgien',None,(5900,4000,14100)),('Schweiz','Bern',(8200,5500,19500)),
                ('Schweiz','Genf',(7000,4700,19700)),('Luxemburg',None,(6300,4200,13900)),('Österreich',None,(5000,3300,11700))]:
            got=country_rate(country,region);self.assertEqual(tuple(got[k] for k in ('full_minor','short_minor','lodging_minor')),wanted)
        self.assertEqual(country_rate('Mikronesien'),country_rate('Philippinen'))
        with self.assertRaises(Problem):country_rate('Unknown country')
        with self.assertRaises(Problem):country_rate('Schweiz')
    def test_eight_hours_is_not_more_than_eight_and_explicit_breakfast_reduction(self):
        for finish,wanted in [('16:00',0),('16:01',1400)]:
            value=trip(3,'2026-02-03T08:00:00+01:00','2026-02-03T'+finish+':00+01:00',self.place,self.home,requested=wanted)
            result=calculate([value],[self.home,self.place]);self.assertEqual(result['totals']['tax_free_minor'],wanted);self.assertTrue(result['can_approve'])
        value['details']['meals']=[meal()];value['details']['requested_meal_minor']=840
        result=calculate([value],[self.home,self.place]);self.assertEqual(result['days'][0]['meal_reduction_minor'],560)
        self.assertEqual(result['totals']['tax_free_minor'],840)
        value['details']['meals']=[meal(own=200)];value['details']['requested_meal_minor']=1040
        self.assertEqual(calculate([value],[self.home,self.place])['totals']['tax_free_minor'],1040)
    def test_full_calendar_day_and_all_meals_can_reduce_only_to_zero(self):
        value=trip(3,'2026-02-02T18:00:00+01:00','2026-02-04T08:00:00+01:00',self.place,self.home,
            nights=[night(self.place,'2026-02-02'),night(self.place,'2026-02-03')],
            meals=[meal(k) for k in ('breakfast','lunch','dinner')],requested=2800)
        result=calculate([value],[self.home,self.place]);middle=result['days'][1]
        self.assertEqual((middle['base_minor'],middle['meal_reduction_minor'],middle['meal_allowance_minor']),(2800,2800,0))
        self.assertEqual(result['totals']['tax_free_minor'],2800)
        value['details']['overnights'][0].update(claim_method='flat',provided_by='employee',accommodation_kind='lodging')
        value['details']['requested_lodging_minor']=2000
        self.assertEqual(calculate([value],[self.home,self.place])['totals']['lodging_allowance_minor'],2000)
    def test_bmf_2026_strasbourg_home_copenhagen_is_35_euros(self):
        france=site(4,country='Frankreich',region='im Übrigen');denmark=site(5,country='Dänemark')
        first=trip(6,'2026-02-02T08:00:00+01:00','2026-02-03T15:00:00+01:00',france,self.home,
            nights=[night(france,'2026-02-02')],meals=[meal()],requested=3600)
        second=trip(7,'2026-02-03T16:00:00+01:00','2026-02-04T18:00:00+01:00',denmark,self.home,
            nights=[night(denmark,'2026-02-03')],requested=8500)
        result=calculate([first,second],[self.home,france,denmark],settlement_unit='combined_period')
        tuesday=next(d for d in result['days'] if d['date']=='2026-02-03')
        self.assertEqual((tuesday['full_minor'],tuesday['base_minor'],tuesday['meal_reduction_minor'],tuesday['meal_allowance_minor']),(7500,5000,1500,3500))
        self.assertEqual(result['totals']['tax_free_minor'],12100)
    def test_three_calendar_months_and_28_full_absent_days(self):
        fixed=site(2,regular_days_per_week=3,prior_visit_dates=['2026-01-05','2026-02-01','2026-03-01','2026-03-28'])
        self.assertTrue(three_month(fixed,'2026-04-04',['2026-04-04'])['eligible'])
        self.assertFalse(three_month(fixed,'2026-04-05',['2026-04-05'])['eligible'])
        fixed['details']['prior_visit_dates']=['2026-01-05','2026-02-01','2026-03-01','2026-03-28','2026-04-05']
        self.assertFalse(three_month(fixed,'2026-05-03',['2026-05-03'])['eligible'])
        restarted=three_month(fixed,'2026-05-04',['2026-05-04'])
        self.assertTrue(restarted['eligible']);self.assertEqual(restarted['reset_on'],'2026-05-04')
        fixed['details']['regular_days_per_week']=2
        self.assertTrue(three_month(fixed,'2026-08-01',['2026-08-01'])['eligible'])
    def test_real_dst_gap_and_fold_are_not_guessed(self):
        self.assertEqual(time_options('2026-03-29T02:30','Europe/Berlin')['options'],[])
        options=time_options('2026-10-25T02:30','Europe/Berlin')['options'];self.assertEqual(len(options),2)
        self.assertEqual({o['offset'] for o in options},{'+01:00','+02:00'})
        self.assertEqual(len(time_options('2026-10-26T02:30','Europe/Berlin')['options']),1)
        with self.assertRaises(Problem):moment('2026-03-29T02:30:00+01:00','Europe/Berlin')
    def test_overlapping_trips_and_unprocessed_tax_are_not_accepted(self):
        value=trip(3,'2026-02-03T08:00:00+01:00','2026-02-03T18:00:00+01:00',self.place,self.home,requested=1800)
        result=calculate([value],[self.home,self.place]);self.assertFalse(result['can_approve'])
        self.assertIn('requested_above_tax_free',[b['code'] for b in result['blockers']])
        result=calculate([value],[self.home,self.place],tax_choice='flat_25')
        self.assertEqual(result['totals']['flat_taxable_minor'],400);self.assertTrue(result['can_approve'])
        self.assertTrue(result['payroll_required']);self.assertFalse(result['can_pay'])
        other=copy.deepcopy(value);other.update(id='8'*32,content_hash='8'*64)
        with self.assertRaises(Problem):calculate([value,other],[self.home,self.place],settlement_unit='combined_period')

