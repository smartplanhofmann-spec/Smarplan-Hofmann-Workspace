"""Independent source extraction and counterexamples, not generated from rates.

Source: BMF letter 5 December 2025 (2026 table), BMF 25 November 2020
paragraphs 47, 55, 78, 93; and BGB sections 187/188 for month endings.
The source JSON preserves independently retrieved web PDF text, not PDF bytes.
"""
import copy
import json
from pathlib import Path
import unittest

from payroll_travel_2026 import calculate, three_month
from payroll_travel_rates_2026 import RATES
from test_payroll_travel_2026 import site, trip, meal, night, ref


def independently_extracted_rates():
    source = json.loads((Path(__file__).resolve().parent.parent /
        'docs/evidence/travel-rates-2026-independent-source.json').read_text())
    lines = {row['line']: row['text'] for row in source['lines']}
    labels = []
    for lo, hi in ((144,177),(297,326),(433,467),(574,607),
                   (733,767),(895,929),(1062,1093)):
        for n in range(lo, hi + 1):
            if n in (314,1075,1087):
                labels[-1] += ' ' + lines[n]
            else:
                labels.append(lines[n])
    names = []
    country = None
    for n, label in enumerate(labels):
        if label.startswith('– '):
            names.append((country, label[2:]))
        else:
            country = label
            if n + 1 == len(labels) or not labels[n + 1].startswith('– '):
                names.append((country, None))
    amounts = []
    for lo, hi, lodging_start in ((191,221,223),(340,366,368),
            (481,511,513),(621,654,656),(781,812,814),(943,973,975)):
        for offset, n in enumerate(range(lo, hi + 1)):
            full, short = map(int, lines[n].split())
            amounts.append((full * 100, short * 100,
                            int(lines[lodging_start + offset]) * 100))
    for offset in range(28):
        amounts.append(tuple(int(lines[start + offset]) * 100
                             for start in (1106,1143,1172)))
    assert len(names) == len(amounts) == 214
    return [dict(country=country,region=region,full_minor=amount[0],
                 short_minor=amount[1],lodging_minor=amount[2])
            for (country,region),amount in zip(names,amounts)]


class TravelIndependentRulesTests(unittest.TestCase):
    def setUp(self):
        self.home = site(101, 'home')
        self.place = site(102)

    def test_all_214_country_region_and_642_amount_cells_match_independent_bmf_text(self):
        expected = independently_extracted_rates()
        self.assertEqual(len(RATES[1:]), 214)
        for n, (actual, wanted) in enumerate(zip(RATES[1:], expected), 1):
            with self.subTest(row=n, country=wanted['country'], region=wanted['region']):
                self.assertEqual({k: actual[k] for k in wanted}, wanted)

    def test_two_short_trips_sum_actual_absence_but_not_time_at_home(self):
        first = trip(103,'2026-02-03T07:00:00+01:00','2026-02-03T11:00:00+01:00',self.place,self.home)
        second = trip(104,'2026-02-03T15:00:00+01:00','2026-02-03T19:00:00+01:00',self.place,self.home)
        result = calculate([first,second],[self.home,self.place],settlement_unit='combined_period')
        self.assertEqual(result['days'][0]['base_minor'], 0)
        second['details']['returned_at'] = second['details']['segments'][0]['to'] = '2026-02-03T19:00:01+01:00'
        result = calculate([first,second],[self.home,self.place],settlement_unit='combined_period')
        self.assertEqual(result['days'][0]['absence_seconds'], 8 * 3600 + 1)
        self.assertEqual(result['days'][0]['base_minor'], 1400)

    def test_expired_fixed_site_removes_only_its_time_from_other_customer_work(self):
        fixed = site(105, regular_days_per_week=3,
            prior_visit_dates=['2026-01-05','2026-01-25','2026-02-14','2026-03-06','2026-03-26'])
        value = trip(106,'2026-04-06T07:00:00+02:00','2026-04-06T18:00:00+02:00',fixed,self.home)
        original = value['details']['segments'][0]
        for finish, wanted in [('17:00:00',0),('17:00:01',1400)]:
            value['details']['segments'] = [
                dict(original, id='1'*32, **{'to':'2026-04-06T09:00:00+02:00'}),
                dict(original, id='2'*32, **{'from':'2026-04-06T09:00:00+02:00','to':'2026-04-06T'+finish+'+02:00'}, site_ref=ref(self.place)),
                dict(original, id='3'*32, **{'from':'2026-04-06T'+finish+'+02:00'})]
            result = calculate([value],[self.home,self.place,fixed])
            self.assertEqual(result['days'][0]['base_minor'], wanted)

    def test_partial_night_evidence_does_not_approve_an_entire_four_day_trip(self):
        value = trip(107,'2026-02-02T18:00:00+01:00','2026-02-05T08:00:00+01:00',self.place,self.home,
                     nights=[night(self.place,'2026-02-02')])
        result = calculate([value],[self.home,self.place])
        self.assertFalse(result['can_approve'])
        self.assertIn('overnight_evidence_missing',[x['code'] for x in result['blockers']])

    def test_last_foreign_workplace_determines_single_day_even_after_domestic_work(self):
        belgium = site(108, country='Belgien')
        value = trip(109,'2026-02-03T07:00:00+01:00','2026-02-03T18:00:00+01:00',belgium,self.home)
        first = value['details']['segments'][0]
        value['details']['segments'] = [dict(first,**{'to':'2026-02-03T12:00:00+01:00'}),
            dict(first,id='a'*32,**{'from':'2026-02-03T12:00:00+01:00'},site_ref=ref(self.place))]
        result = calculate([value],[self.home,self.place,belgium])
        self.assertEqual((result['days'][0]['country'],result['days'][0]['base_minor']),('Belgien',4000))

    def test_month_end_three_month_deadline_includes_april_30(self):
        fixed = site(110,regular_days_per_week=3,
            prior_visit_dates=['2026-01-31','2026-02-20','2026-03-12','2026-04-01','2026-04-21'])
        result = three_month(fixed,'2026-04-30',['2026-04-30'])
        self.assertEqual(result['expires_on'],'2026-04-30')
        self.assertTrue(result['eligible'])
        self.assertFalse(three_month(fixed,'2026-05-01',['2026-05-01'])['eligible'])

    def test_over_sixty_euro_reward_meal_does_not_set_letter_m(self):
        value = trip(111,'2026-02-03T08:00:00+01:00','2026-02-03T18:00:00+01:00',self.place,self.home,
                     meals=[meal(price=6001,own=1000)])
        result = calculate([value],[self.home,self.place])
        self.assertEqual(result['days'][0]['benefit_in_kind_minor'],5001)
        self.assertEqual(result['days'][0]['meal_reduction_minor'],0)
        self.assertFalse(result['days'][0]['letter_m'])

    def test_meal_own_payment_cannot_offset_another_meals_reduction(self):
        value = trip(112,'2026-02-02T18:00:00+01:00','2026-02-04T08:00:00+01:00',self.place,self.home,
            nights=[night(self.place,'2026-02-02'),night(self.place,'2026-02-03')],
            meals=[meal('breakfast',own=1000),meal('lunch')])
        result = calculate([value],[self.home,self.place])
        middle = result['days'][1]
        self.assertEqual((middle['base_minor'],middle['meal_reduction_minor'],middle['meal_allowance_minor']),(2800,1120,1680))

    def test_frequency_two_to_three_starts_only_in_may_bmf_example_40(self):
        fixed = site(113,regular_days_per_week=3,effective_from='2026-04-01',
            prior_visit_dates=['2026-04-01','2026-04-13','2026-05-01','2026-05-20','2026-06-08','2026-06-27','2026-07-16'],
            frequency_periods=[dict(**{'from':'2026-04-01','to':'2026-04-30'},days_per_week=2,source_file_ids=['f'*32]),
                               dict(**{'from':'2026-05-01','to':None},days_per_week=3,source_file_ids=['f'*32])])
        result = three_month(fixed,'2026-07-31',['2026-07-31'])
        self.assertEqual((result['started_on'],result['expires_on'],result['eligible']),('2026-05-01','2026-07-31',True))
        self.assertFalse(three_month(fixed,'2026-08-01',['2026-08-01'])['eligible'])

    def test_frequency_three_to_two_does_not_stop_running_period_bmf_example_40(self):
        fixed = site(114,regular_days_per_week=2,effective_from='2026-04-01',
            prior_visit_dates=['2026-04-01','2026-04-13','2026-05-01','2026-05-20','2026-06-08','2026-06-27'],
            frequency_periods=[dict(**{'from':'2026-04-01','to':'2026-04-30'},days_per_week=3,source_file_ids=['f'*32]),
                               dict(**{'from':'2026-05-01','to':None},days_per_week=2,source_file_ids=['f'*32])])
        result = three_month(fixed,'2026-07-01',['2026-07-01'])
        self.assertEqual((result['started_on'],result['expires_on'],result['eligible']),('2026-04-01','2026-06-30',False))

    def test_four_full_weeks_reset_and_new_two_day_pattern_does_not_restart_clock(self):
        fixed = site(115,regular_days_per_week=2,effective_from='2026-01-01',
            prior_visit_dates=['2026-01-05','2026-01-25','2026-02-14','2026-03-06','2026-03-26','2026-04-05'],
            frequency_periods=[dict(**{'from':'2026-01-01','to':'2026-04-30'},days_per_week=3,source_file_ids=['f'*32]),
                               dict(**{'from':'2026-05-01','to':None},days_per_week=2,source_file_ids=['f'*32])])
        self.assertFalse(three_month(fixed,'2026-05-03',['2026-05-03'])['eligible'])
        result = three_month(fixed,'2026-05-04',['2026-05-04'])
        self.assertTrue(result['eligible'])
        self.assertIsNone(result['started_on'])

    def test_time_at_home_is_not_absence_merely_because_segment_is_named_stay(self):
        value = trip(116,'2026-02-03T08:00:00+01:00','2026-02-03T18:00:00+01:00',self.place,self.home,requested=1400)
        original = value['details']['segments'][0]
        value['details']['segments'] = [dict(original,**{'to':'2026-02-03T16:00:00+01:00'}),
            dict(original,id='a'*32,**{'from':'2026-02-03T16:00:00+01:00'},site_ref=ref(self.home),activity='stay')]
        result = calculate([value],[self.home,self.place])
        self.assertTrue(not result['can_approve'] or result['days'][0]['base_minor']==0)

    def test_night_at_home_is_not_an_external_overnight_for_short_arrival_departure(self):
        value = trip(117,'2026-02-02T22:00:00+01:00','2026-02-03T01:00:00+01:00',self.place,self.home,
            nights=[night(self.home,'2026-02-02')],requested=2800)
        result = calculate([value],[self.home,self.place])
        self.assertTrue(not result['can_approve'] or result['totals']['meal_base_minor']==0)

