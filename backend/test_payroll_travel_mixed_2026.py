"""Published BMF example59 and negative evidence tests for isolated travelv3."""
import copy
from datetime import date,timedelta
import unittest

from core import Problem
from payroll_travel_2026_v3 import calculate
from payroll_travel_mixed_2026 import resolve_mixed_program,prorate_minor
from test_payroll_travel_2026 import site,trip,meal,night,ref


def session(n,on,start,end,kind):
    return dict(id=hex(n)[2:].zfill(32),**{'from':f'{on}T{start}:00+01:00','to':f'{on}T{end}:00+01:00'},kind=kind,source_file_ids=['f'*32])


def mixed(value,sessions):
    value['details']['mixed_assessment']=dict(method='documented_program_ratio',program_sessions=sessions,
        program_complete=True,cost_allocation_reviewed=True,source_file_ids=['f'*32],review_note='Original programme and separate cost documents reviewed.')
    value['details']['private_intervals']=[{k:s[k] for k in ('from','to')} for s in sessions if s['kind']=='private']
    return value


class MixedTravelTests(unittest.TestCase):
    def setUp(self):self.home=site(701,'home');self.place=site(702)
    def week(self):
        first=date(2026,2,2);days=[str(first+timedelta(days=n)) for n in range(7)]
        value=trip(703,days[0]+'T12:00:00+01:00',days[-1]+'T12:00:00+01:00',self.place,self.home,
            nights=[night(self.place,d) for d in days[:-1]],requested=140)
        value['details']['meals']=[meal('dinner',days[0])]+[meal(k,d) for d in days[1:-1] for k in ('breakfast','dinner')]+[meal('breakfast',days[-1])]
        sessions=[]
        for i,d in enumerate(days[1:-1]):
            sessions.extend([session(800+i*2,d,'08:00','12:00','business'),session(801+i*2,d,'13:00','17:00','private')])
        return mixed(value,sessions)
    def daily(self):
        return mixed(trip(704,'2026-02-03T08:00:00+01:00','2026-02-03T18:00:00+01:00',self.place,self.home),
            [session(900,'2026-02-03','08:00','12:00','business'),session(901,'2026-02-03','13:00','15:00','private')])
    def test_bmf_example59_50_percent_before_full_meal_reduction_is_140_cents(self):
        value=self.week();before=copy.deepcopy(value);result=calculate([value],[self.home,self.place])
        self.assertTrue(result['can_approve'],result['blockers'])
        self.assertEqual([d['base_minor'] for d in result['days']],[700,1400,1400,1400,1400,1400,700])
        self.assertEqual([d['meal_allowance_minor'] for d in result['days']],[0,0,0,0,0,0,140])
        self.assertEqual(result['totals']['tax_free_minor'],140)
        self.assertEqual(result['totals']['benefit_in_kind_minor'],0)
        self.assertTrue(all(d['letter_m'] for d in result['days']))
        self.assertEqual(value,before)
    def test_program_share_excludes_rest_and_rounds_half_up_only_at_final_cent(self):
        value=self.daily();result=resolve_mixed_program(value)
        self.assertEqual((result['numerator'],result['denominator']),(2,3))
        self.assertEqual((result['business_seconds'],result['private_seconds']),(14400,7200))
        self.assertEqual(prorate_minor(1400,2,3),933)
        self.assertEqual(prorate_minor(1,1,2),1)
        value['details']['meals']=[meal('breakfast')]
        result=calculate([value],[self.home,self.place])
        self.assertEqual((result['days'][0]['base_minor'],result['days'][0]['meal_reduction_minor'],result['days'][0]['meal_allowance_minor']),(933,560,373))
    def test_full_day_two_thirds_then_full_lunch_reduction_is_747(self):
        value=self.week();value['details']['meals']=[meal('lunch')]
        for s in value['details']['mixed_assessment']['program_sessions']:
            if s['kind']=='private':s['to']=s['to'].replace('17:00','15:00')
        value['details']['private_intervals']=[{k:s[k] for k in ('from','to')} for s in value['details']['mixed_assessment']['program_sessions'] if s['kind']=='private']
        result=calculate([value],[self.home,self.place])
        self.assertEqual(result['days'][1]['meal_allowance_minor'],747)
    def test_private_clock_time_alone_never_guesses_a_ratio(self):
        value=self.daily();del value['details']['mixed_assessment']
        result=calculate([value],[self.home,self.place])
        self.assertFalse(result['can_approve']);self.assertIn('mixed_travel_assessment',[b['code'] for b in result['blockers']])
        self.assertEqual(result['totals']['meal_allowance_minor'],0)
    def test_programme_and_cost_reviews_must_both_be_completed(self):
        for flag,code in [('program_complete','mixed_program_incomplete'),('cost_allocation_reviewed','mixed_cost_allocation_unreviewed')]:
            value=self.daily();value['details']['mixed_assessment'][flag]=False
            result=calculate([value],[self.home,self.place])
            self.assertFalse(result['can_approve']);self.assertIn(code,[b['code'] for b in result['blockers']])
    def test_business_session_cannot_relabel_explicit_private_time(self):
        value=self.daily();value['details']['mixed_assessment']['program_sessions'][0]['to']='2026-02-03T14:00:00+01:00'
        with self.assertRaises(Problem):resolve_mixed_program(value)
    def test_missing_work_segment_or_private_evidence_is_rejected(self):
        value=self.daily();value['details']['segments'][0]['activity']='stay'
        with self.assertRaises(Problem):resolve_mixed_program(value)
        value=self.daily();value['details']['private_intervals']=[]
        with self.assertRaises(Problem):resolve_mixed_program(value)
    def test_overlapping_programme_or_duplicate_ids_are_rejected(self):
        value=self.daily();program=value['details']['mixed_assessment']['program_sessions'];program.append(dict(program[0],id='a'*32))
        with self.assertRaises(Problem):resolve_mixed_program(value)
        value=self.daily();program=value['details']['mixed_assessment']['program_sessions'];program[1]['id']=program[0]['id']
        with self.assertRaises(Problem):resolve_mixed_program(value)
    def test_private_extension_cannot_disappear_from_programme(self):
        value=self.daily();value['details']['private_intervals'][0]['to']='2026-02-03T18:00:00+01:00'
        result=calculate([value],[self.home,self.place])
        self.assertFalse(result['can_approve']);self.assertIn('mixed_private_program_missing',[b['code'] for b in result['blockers']])
    def test_lodging_share_is_applied_but_actual_cost_allocation_stays_separate(self):
        value=self.week();value['details']['overnights'][0].update(claim_method='flat',provided_by='employee',accommodation_kind='lodging')
        value['details']['requested_lodging_minor']=1000
        result=calculate([value],[self.home,self.place])
        self.assertTrue(result['can_approve'],result['blockers']);self.assertEqual(result['totals']['lodging_allowance_minor'],1000)
    def test_conflicting_same_day_trip_shares_require_evidenced_day_allocation(self):
        value=self.daily();other=trip(705,'2026-02-03T19:00:00+01:00','2026-02-03T23:00:00+01:00',self.place,self.home)
        result=calculate([value,other],[self.home,self.place],settlement_unit='combined_period')
        self.assertFalse(result['can_approve']);self.assertIn('mixed_day_allocation_required',[b['code'] for b in result['blockers']])
    def test_original_programme_proof_and_review_note_bind_the_facts_hash(self):
        value=self.daily();before=resolve_mixed_program(value)['facts_hash']
        value['details']['mixed_assessment']['program_sessions'][0]['source_file_ids']=['a'*32]
        self.assertNotEqual(before,resolve_mixed_program(value)['facts_hash'])
        before=resolve_mixed_program(value)['facts_hash'];value['details']['mixed_assessment']['review_note']='Second original record reviewed.'
        self.assertNotEqual(before,resolve_mixed_program(value)['facts_hash'])
    def test_frozen_v2_still_blocks_mixed_programmes_without_silent_recalculation(self):
        result=calculate([self.week()],[self.home,self.place],rule_version='de_travel_2026_v2')
        self.assertEqual(result['rule_version'],'de_travel_2026_v2');self.assertFalse(result['can_approve'])
        self.assertIn('mixed_travel_assessment',[b['code'] for b in result['blockers']])


if __name__=='__main__':unittest.main()
