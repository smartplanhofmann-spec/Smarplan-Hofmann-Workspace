"""Independent clock-boundary facts: no duplicated or invented elapsed time."""
import unittest
from payroll_travel_ground_2026 import resolve_ground_calendar
from payroll_travel_2026_v3 import calculate
from test_payroll_travel_2026 import site,trip,ref


class GroundCalendarTests(unittest.TestCase):
    def setUp(self):
        self.home=site(601,'home');self.de=site(602,country='Schweden',timezone='Europe/Stockholm');self.fi=site(603,country='Finnland',timezone='Europe/Helsinki')

    def journey(self):
        value=trip(604,'2026-02-02T22:00:00+01:00','2026-02-03T03:00:00+01:00',self.de,self.home)
        first=value['details']['segments'][0]
        value['details']['segments']=[dict(first,**{'to':'2026-02-02T23:30:00+01:00'}),dict(first,id='a'*32,**{'from':'2026-02-02T23:30:00+01:00'},site_ref=ref(self.fi))]
        return value

    def test_ground_clock_change_allocates_each_real_second_once_to_local_date(self):
        result=resolve_ground_calendar(self.journey(),[self.home,self.de,self.fi])
        self.assertEqual(list(result['days']),['2026-02-02','2026-02-03'])
        self.assertEqual([d['absence_seconds'] for d in result['days'].values()],[5400,12600])
        self.assertEqual(result['days']['2026-02-02']['last_site_ref'],ref(self.de))
        self.assertEqual(result['days']['2026-02-03']['last_site_ref'],ref(self.fi))

    def test_westbound_repeated_date_remains_one_day_with_real_union_duration(self):
        value=self.journey();a,b=value['details']['segments'];a['site_ref']=ref(self.fi);b['site_ref']=ref(self.de)
        result=resolve_ground_calendar(value,[self.home,self.de,self.fi])
        self.assertEqual(len(result['days']),2);self.assertEqual(sum(d['absence_seconds'] for d in result['days'].values()),18000)
        self.assertEqual(result['days']['2026-02-02']['absence_seconds'],5400)

    def test_existing_flight_facts_are_not_reinterpreted_as_ground_calendar(self):
        value=self.journey();value['details']['segments'][0]['transport']='flight'
        self.assertIsNone(resolve_ground_calendar(value,[self.home,self.de,self.fi]))

    def test_complete_v3_night_work_uses_actual_swedish_day_without_clock_time_invention(self):
        value=self.journey();value['details']['departed_at']='2026-02-02T19:00:00+01:00';value['details']['segments'][0]['from']=value['details']['departed_at']
        value['details']['returned_at']='2026-02-03T03:30:00+01:00';value['details']['segments'][1]['to']=value['details']['returned_at']
        value['details']['requested_meal_minor']=4400
        result=calculate([value],[self.home,self.de,self.fi])
        self.assertTrue(result['can_approve'],result['blockers'])
        self.assertEqual([(d['date'],d['absence_seconds'],d['base_minor']) for d in result['days']],[('2026-02-02',16200,4400),('2026-02-03',14400,0)])
        self.assertEqual(result['days'][0]['country'],'Schweden')
        self.assertEqual(sum(d['absence_seconds'] for d in result['days']),30600)
