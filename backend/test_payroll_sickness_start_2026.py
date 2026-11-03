"""Published employment commencement and original medical history boundaries."""
from copy import deepcopy
import hashlib
import unittest

from core import Problem,canonical
from payroll_sickness_start_2026 import derive_sickness_start as calculate
from payroll_sickness_2026 import derive_sickness_entitlement
from test_payroll_sickness_phases_2026 import history,joined
from test_payroll_entitlements_2026 import episode,sickness,REF


def commencement(last='2026-10-31'):
    source=history([episode('2026-09-25',last,onset='before_employment')],start='2026-10-01')
    source['employment_commencement']=dict(contract_concluded_on='2026-09-16',evidence_refs=[REF])
    return source


class SicknessStartTests(unittest.TestCase):
    def test_published_ikk_contract_september16_au25_start_october1_paid29_to31(self):
        source=commencement();before=deepcopy(source);plan=calculate(source);row=plan['episodes'][0]
        self.assertEqual(('2026-09-25','2026-10-28','2026-10-29','2026-10-31',3),
            tuple(row[k] for k in ('from_date','waiting_period_end','entitlement_from','entitlement_to','entitlement_calendar_days')))
        self.assertEqual('2026-09-25',plan['prevention_cases'][0]['original_au_from'])
        self.assertEqual('2026-10-01',plan['phases'][0]['from_date'])
        self.assertEqual([dict(episode_id='d'*32,from_date='2026-09-25',to_date='2026-09-30',employment_wage_entitlement=False)],plan['preemployment_periods'])
        self.assertEqual(source,before)

    def test_full_period_starts_after_waiting_without_preemployment_consumption(self):
        row=calculate(commencement('2026-12-31'))['episodes'][0]
        self.assertEqual(('2026-10-29','2026-12-09',42,0),
            tuple(row[k] for k in ('entitlement_from','entitlement_to','entitlement_calendar_days','prior_used_days')))

    def test_hourly_preemployment_has_no_invented_scheduled_day(self):
        source=commencement();source['pay_basis']='hourly';row=calculate(source)['episodes'][0]
        self.assertEqual(3,row['entitlement_calendar_days'])
        self.assertIsNone(source['episodes'][0]['first_scheduled_day'])

    def test_joined_after_commencement_preserves_common_case_deadline(self):
        source=commencement();added=joined('2026-10-20','2026-12-31',identity='e',group='f')
        source['episodes'].append(added);source['prevention_cases'][0]['episode_ids'].append(added['id'])
        plan=calculate(source)
        self.assertEqual([3,39],[row['entitlement_calendar_days'] for row in plan['episodes']])
        self.assertEqual('2026-12-09',plan['prevention_cases'][0]['statutory_deadline'])

    def test_unproven_contract_or_ended_preemployment_or_wrong_onset_is_rejected(self):
        variants=[]
        for concluded in ('2026-09-25','2026-09-26','2026-10-01'):
            s=commencement();s['employment_commencement']['contract_concluded_on']=concluded;variants.append(s)
        s=commencement('2026-09-30');variants.append(s)
        s=commencement();s['episodes'][0]['onset']='before_work';variants.append(s)
        for source in variants:
            with self.subTest(source=source),self.assertRaises(Problem):calculate(source)

    def test_original_dates_and_contract_evidence_are_bound_to_hash(self):
        source=commencement();plan=calculate(source)
        self.assertEqual(hashlib.sha256(canonical(source).encode()).hexdigest(),plan['source_hash'])
        changed=deepcopy(source);changed['episodes'][0]['from']='2026-09-24';other=calculate(changed)
        self.assertNotEqual(plan['source_hash'],other['source_hash'])
        self.assertEqual(plan['legal_projection_hash'],other['legal_projection_hash'])
        self.assertNotEqual(plan['plan_hash'],other['plan_hash'])

    def test_hourly_au_only_on_free_days_remains_explicit_unresolved_case(self):
        # There is no actual missed shift. Do not substitute Sunday/Monday or
        # quietly assume recurrence consumption without a verified source rule.
        source=sickness(episode('2026-08-01','2026-08-02',onset='non_workday'),pay_basis='hourly')
        with self.assertRaises(Problem):derive_sickness_entitlement(source)
        self.assertIsNone(source['episodes'][0]['first_scheduled_day'])


if __name__=='__main__':unittest.main()
