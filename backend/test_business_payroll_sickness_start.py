"""Actual private employment commencement originals, no invented shift facts."""
from copy import deepcopy
import unittest

import business_payroll_entitlements as claims
import test_business_payroll_sickness_v2 as v2_fixture
from test_business_payroll import rid


class SicknessStartPrivateTests(unittest.TestCase):
    def setUp(self):
        self.fixture=v2_fixture.SicknessVersionHistoryTests('runTest');self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.f=self.fixture.f

    def details(self):
        details=self.f.details('sickness_history');source=details['input'];source['pay_basis']='hourly'
        first=source['episodes'][0];first.update(**{'from':'2026-10-10','to':'2026-12-31'},onset='before_employment')
        source.update(prevention_cases=[dict(id=rid(),episode_ids=[first['id']],evidence_refs=[self.f.original])],
            employment_commencement=dict(contract_concluded_on='2026-10-01',evidence_refs=[self.f.original]))
        return details

    def test_actual_preemployment_original_and_contract_bound_without_fake_shift(self):
        saved,command,_=self.f.save('sickness_history',self.details())
        self.assertEqual('de_2026_sickness_start_v4',saved['plan']['rule_version'])
        row=saved['plan']['episodes'][0]
        self.assertEqual(('2026-10-10','2026-11-12','2026-12-23',42),
            tuple(row[k] for k in ('from_date','entitlement_from','entitlement_to','entitlement_calendar_days')))
        self.assertIsNone(saved['details']['input']['episodes'][0]['first_scheduled_day'])
        self.f.pause();self.assertEqual(saved,self.f.claims.save(self.f.owner,command))
        self.assertTrue(claims.validate_integrity(self.f.office))

    def test_correction_keeps_original_au_and_new_contract_proof_hash_distinct(self):
        first,original,_=self.f.save('sickness_history',self.details())
        details=deepcopy(first['details']);details['input']['employment_commencement']['contract_concluded_on']='2026-10-02'
        command,_=self.f.request('sickness_history',details)
        command.update(id=first['id'],revision=1,correction_reason='Belegtes Vertragsdatum ausdrücklich korrigieren')
        second=self.f.claims.save(self.f.owner,command)
        self.assertEqual(first['plan']['episodes'],second['plan']['episodes'])
        self.assertNotEqual(first['plan']['plan_hash'],second['plan']['plan_hash'])
        self.assertEqual(first,self.f.claims.save(self.f.owner,original))
        self.assertTrue(claims.validate_integrity(self.f.office))

    def test_contract_evidence_cannot_be_replaced_by_an_unbound_file(self):
        details=self.details();details['input']['employment_commencement']['evidence_refs']=[dict(self.f.original,id=rid())]
        self.f.problem(409,lambda:self.f.request('sickness_history',details))


if __name__=='__main__':unittest.main()
