"""Actual private overlapping sickness originals and bound regular absence."""
from copy import deepcopy
import unittest

import business_payroll_entitlements as claims
from business_payroll_facts import reference
from payroll_entitlement_dispatch import build_entitlement_plan
from payroll_sickness_phases_2026 import SICKNESS_PHASE_RULE_VERSION
import test_business_payroll_sickness_v2 as v2_fixture
from test_business_payroll import rid


class SicknessPhasesPrivateTests(unittest.TestCase):
    def setUp(self):
        self.fixture=v2_fixture.SicknessVersionHistoryTests('runTest');self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.f=self.fixture.f

    def details(self):
        details=self.fixture.details();value=details['input'];first=value['episodes'][0];first['to']='2026-12-05'
        added=dict(deepcopy(first),id=rid(),continuation_group=rid(),**{'from':'2026-11-20','to':'2026-12-31'},
            onset='during_existing_au',first_scheduled_day=None,recovery_before=False)
        value['episodes'].append(added)
        value['prevention_cases']=[dict(id=rid(),episode_ids=[first['id'],added['id']],evidence_refs=[self.f.original])]
        return details

    def test_new_v3_original_replay_and_explicit_historical_reconstruction(self):
        saved,body,preview=self.f.save('sickness_history',self.details())
        self.assertEqual(saved['plan']['rule_version'],SICKNESS_PHASE_RULE_VERSION)
        self.assertEqual(saved['plan']['prevention_cases'][0]['statutory_deadline'],'2026-12-26')
        self.assertEqual([21,21],[item['entitlement_calendar_days'] for item in saved['plan']['episodes']])
        self.assertEqual(saved['plan'],build_entitlement_plan(saved['sources'],SICKNESS_PHASE_RULE_VERSION))
        self.f.pause();self.assertEqual(saved,self.f.claims.save(self.f.owner,body))
        self.assertTrue(claims.validate_integrity(self.f.office))

    def test_v2_to_v3_correction_keeps_both_original_versions(self):
        original,command,_=self.f.save('sickness_history',self.fixture.details())
        details=self.details();details['case_key']=original['details']['case_key']
        body,_=self.f.request('sickness_history',details)
        body.update(id=original['id'],revision=1,correction_reason='Belegten Hinzutritt als weitere Originalfassung ergänzen')
        current=self.f.claims.save(self.f.owner,body)
        self.assertEqual([original,current],self.f.claims.get(self.f.owner,original['id'],True)['items'])
        self.assertEqual(original,self.f.claims.save(self.f.owner,command))
        self.assertEqual(current['plan']['rule_version'],SICKNESS_PHASE_RULE_VERSION)
        self.assertTrue(claims.validate_integrity(self.f.office))

    def test_regular_absence_binds_exact_phase_history_once_and_preserves_exhaustion(self):
        f=self.f;history,_,_=f.save('sickness_history',self.details())
        schedule=f.schedule('2026-12');preparation=f.absence_preparation('2026-12-24','2026-12-28','sick')
        details=f.details();details.update(work_schedule_refs=[reference(schedule)],preparation_refs=[reference(preparation)],sickness_history_ref=reference(history))
        details['input']=dict(kind='sickness',hourly_rate_minor=1800,evidence_refs=[f.original],days=[
            dict(date=current,scheduled_regular_seconds=28800,worked_regular_seconds=0,
                entitled=paid,absence_is_only_cause=True,holiday_adjacent_unexcused=None,evidence_refs=[f.original])
            for current,paid in [('2026-12-24',True),('2026-12-28',False)]])
        saved,_,_=f.save('regular_absence',details)
        self.assertEqual(14400,saved['plan']['gross_minor'])
        self.assertEqual(history,saved['sources']['sickness_history'])
        self.assertTrue(claims.validate_integrity(f.office))
        details['input']['days'][1]['entitled']=True
        f.problem(409,lambda:f.request('regular_absence',details))

    def test_prevention_case_evidence_must_be_actual_bound_original(self):
        details=self.details();details['input']['prevention_cases'][0]['evidence_refs'][0]=dict(self.f.original,content_hash='0'*64)
        self.f.problem(409,lambda:self.f.request('sickness_history',details))


if __name__=='__main__':unittest.main()
