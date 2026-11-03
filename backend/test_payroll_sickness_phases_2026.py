"""Published overlapping-cause examples and independently derived boundaries."""
from copy import deepcopy
import hashlib
import unittest

from core import Problem,canonical
from payroll_sickness_phases_2026 import derive_sickness_phases as calculate
from test_payroll_entitlements_2026 import episode,sickness,REF


def joined(first,last,**kwargs):
    return dict(episode(first,last,onset='during_existing_au',**kwargs),recovery_before=False)


def history(*cases,**kwargs):
    source=sickness(*(value for case in cases for value in case),**kwargs)
    source['prevention_cases']=[dict(id=format(i+1,'032x'),episode_ids=[value['id'] for value in case],evidence_refs=[REF]) for i,case in enumerate(cases)]
    return source


class SicknessPhaseTests(unittest.TestCase):
    def assert_case(self,plan,index,first,last,days):
        case=plan['prevention_cases'][index]
        self.assertEqual((first,last,days),(case['from_date'],case['statutory_deadline'],case['entitlement_calendar_days']))

    def test_tk_published_example_17_no_extension_on_sole_added_cause(self):
        plan=calculate(history([episode('2026-07-01','2026-07-30'),joined('2026-07-20','2026-08-31',identity='e',group='f')]))
        self.assert_case(plan,0,'2026-07-01','2026-08-11',42)
        left,right=plan['episodes']
        self.assertEqual((30,12,'2026-07-31','2026-08-11'),(left['entitlement_calendar_days'],right['entitlement_calendar_days'],right['entitlement_from'],right['entitlement_to']))
        self.assertEqual('2026-07-31',right['twelve_month_anchor'])
        self.assertEqual(4,len(plan['phases']))

    def test_tk_published_example_18_prior_exhaustion_only_applies_after_first_cause_ends(self):
        plan=calculate(history([episode('2026-01-05','2026-02-26')],
            [episode('2026-04-10','2026-05-08',identity='e',group='f'),joined('2026-05-01','2026-05-20',identity='a')]))
        self.assertEqual([42,29,0],[row['entitlement_calendar_days'] for row in plan['episodes']])
        self.assertEqual(42,plan['episodes'][-1]['prior_used_days'])
        self.assertEqual('2026-05-09',plan['episodes'][-1]['responsibility_from'])

    def test_tk_published_example_19_fourteen_remaining_but_only_thirteen_inside_case_cap(self):
        plan=calculate(history([episode('2026-01-05','2026-02-01')],
            [episode('2026-04-10','2026-05-08',identity='e',group='f'),joined('2026-05-01','2026-06-30',identity='a')]))
        self.assertEqual([28,29,13],[row['entitlement_calendar_days'] for row in plan['episodes']])
        row=plan['episodes'][-1]
        self.assertEqual(('2026-05-09','2026-05-21',1),(row['entitlement_from'],row['entitlement_to'],row['remaining_days']))

    def test_ikk_published_example_same_group_returns_after_seven_previous_days(self):
        plan=calculate(history([episode('2026-03-09','2026-03-15')],
            [episode('2026-04-09','2026-05-13',identity='e',group='f'),joined('2026-05-04','2026-05-31',identity='a')]))
        self.assertEqual([7,35,7],[row['entitlement_calendar_days'] for row in plan['episodes']])
        self.assert_case(plan,1,'2026-04-09','2026-05-20',42)

    def test_initial_recurrence_remaining_period_cannot_be_extended_by_new_cause(self):
        plan=calculate(history([episode('2026-01-01','2026-02-04')],
            [episode('2026-04-01','2026-04-10',identity='a'),joined('2026-04-05','2026-05-20',identity='e',group='f')],
            [episode('2026-06-01','2026-07-31',identity='b',group='f')]))
        self.assert_case(plan,1,'2026-04-01','2026-04-07',7)
        self.assertEqual([35,7,0,42],[row['entitlement_calendar_days'] for row in plan['episodes']])
        self.assertIsNone(plan['episodes'][2]['twelve_month_anchor'])
        self.assertEqual('2026-06-01',plan['episodes'][3]['twelve_month_anchor'])

    def test_never_responsible_joined_cause_does_not_consume_or_start_recurrence_clock(self):
        plan=calculate(history([episode('2026-04-01','2026-04-20'),joined('2026-04-05','2026-04-15',identity='e',group='f')],
            [episode('2026-05-01','2026-07-01',identity='a',group='f')]))
        self.assertEqual([20,0,42],[row['entitlement_calendar_days'] for row in plan['episodes']])
        self.assertIsNone(plan['episodes'][1]['responsibility_from'])
        self.assertIsNone(plan['episodes'][1]['twelve_month_anchor'])

    def test_added_cause_six_month_reset_uses_responsibility_start_not_overlap_start(self):
        plan=calculate(history([episode('2026-01-01','2026-01-10',group='f')],
            [episode('2026-07-01','2026-07-10',identity='e'),joined('2026-07-05','2026-09-01',identity='a',group='f')]))
        row=plan['episodes'][-1]
        self.assertEqual(('six_months_without_same_illness','2026-07-11',0),
            (row['reset_reason'],row['twelve_month_anchor'],row['prior_used_days']))

    def test_hourly_free_day_and_waiting_period_preserve_case_clock(self):
        plan=calculate(history([episode('2026-08-01','2026-08-20',onset='non_workday',scheduled='2026-08-03'),
            joined('2026-08-10','2026-10-01',identity='e',group='f')],pay_basis='hourly',start='2026-07-15'))
        self.assert_case(plan,0,'2026-08-01','2026-09-22',42)
        self.assertEqual('2026-08-12',plan['episodes'][0]['entitlement_from'])

    def test_during_work_first_day_is_separate_from_forty_two_calendar_days(self):
        plan=calculate(history([episode('2026-08-03','2026-08-20',onset='during_work'),
            joined('2026-08-10','2026-10-01',identity='e',group='f')],pay_basis='hourly'))
        self.assert_case(plan,0,'2026-08-03','2026-09-14',42)
        self.assertTrue(plan['phases'][0]['first_day_remaining_regular_wage'])
        self.assertFalse(plan['phases'][0]['entitled'])
        self.assertEqual('2026-08-03',plan['phases'][0]['to_date'])

    def test_partition_cannot_split_overlaps_or_repeat_or_omit_originals(self):
        source=history([episode('2026-04-01','2026-04-20'),joined('2026-04-05','2026-05-20',identity='e',group='f')])
        changes=[]
        bad=deepcopy(source);bad['prevention_cases'][0]['episode_ids'].pop();changes.append(bad)
        bad=deepcopy(source);bad['prevention_cases'][0]['episode_ids'].append('d'*32);changes.append(bad)
        bad=deepcopy(source);bad['episodes'][1]['recovery_before']=True;changes.append(bad)
        bad=deepcopy(source);bad['episodes'][1]['from']='2026-04-21';changes.append(bad)
        bad=deepcopy(source);bad['prevention_cases'].append(dict(id='a'*32,episode_ids=['e'*32],evidence_refs=[REF]));bad['prevention_cases'][0]['episode_ids'].pop();changes.append(bad)
        for value in changes:
            with self.subTest(value=value),self.assertRaises(Problem):calculate(value)

    def test_simultaneous_undetermined_responsibility_is_explicitly_rejected(self):
        source=history([episode('2026-04-01','2026-04-20'),joined('2026-04-05','2026-05-20',identity='e',group='f'),
            joined('2026-04-05','2026-05-21',identity='a',group='b')])
        with self.assertRaises(Problem):calculate(source)

    def test_exact_source_hash_and_disjoint_complete_phases(self):
        source=history([episode('2026-04-01','2026-04-20'),joined('2026-04-05','2026-05-20',identity='e',group='f')])
        before=deepcopy(source);plan=calculate(source)
        self.assertEqual(source,before)
        self.assertEqual(hashlib.sha256(canonical(source).encode()).hexdigest(),plan['source_hash'])
        self.assertEqual(hashlib.sha256(canonical({k:v for k,v in plan.items() if k!='plan_hash'}).encode()).hexdigest(),plan['plan_hash'])
        from datetime import date,timedelta
        for a,b in zip(plan['phases'],plan['phases'][1:]):
            self.assertEqual(date.fromisoformat(a['to_date'])+timedelta(days=1),date.fromisoformat(b['from_date']))
        self.assertEqual(('2026-04-01','2026-05-20'),(plan['phases'][0]['from_date'],plan['phases'][-1]['to_date']))

    def test_added_cause_becoming_responsible_inside_waiting_requires_evidenced_anchor(self):
        source=history([episode('2026-09-02','2026-09-10'),joined('2026-09-05','2026-10-31',identity='e',group='f')],start='2026-09-01')
        with self.assertRaisesRegex(Problem,'Zwölfmonatsanker'):calculate(source)


if __name__=='__main__':unittest.main()
