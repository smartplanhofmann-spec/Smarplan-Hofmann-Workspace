"""Actual private v1/v2 source histories, corrections and fresh-use boundary."""
from copy import deepcopy
import unittest
from unittest.mock import patch

import business_payroll_entitlements as claims
from business_payroll_facts import reference
import payroll_entitlements_2026 as v1
from payroll_sickness_2026 import SICKNESS_RULE_VERSION
import test_business_payroll_entitlements as fixture
from test_business_payroll import rid


class SicknessVersionHistoryTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.PayrollEntitlementTests('runTest')
        self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.hourly()

    def details(self):
        value=self.f.details('sickness_history')
        value['input']['pay_basis']='hourly'
        value['input']['episodes'][0].update(**{'from':'2026-11-14','to':'2026-12-31'},
            onset='non_workday',first_scheduled_day='2026-11-16')
        return value

    def legacy(self):
        # Produce an actual previously accepted v1 event with the frozen
        # builder. It is then read under the real new dispatcher, not mocked.
        with patch.object(claims,'build_entitlement_plan',v1.build_entitlement_plan):
            return self.f.save('sickness_history',self.details())

    def test_new_preview_and_acceptance_use_v2_and_keep_original_shift(self):
        saved,body,preview=self.f.save('sickness_history',self.details())
        self.assertEqual(SICKNESS_RULE_VERSION,saved['plan']['rule_version'])
        self.assertEqual(preview['plan'],saved['plan'])
        self.assertEqual(('2026-11-15','2026-12-26'),tuple(saved['plan']['episodes'][0][key]
            for key in ('entitlement_from','entitlement_to')))
        self.assertEqual('2026-11-16',saved['details']['input']['episodes'][0]['first_scheduled_day'])
        self.assertEqual(saved,self.f.claims.save(self.f.owner,body))
        self.assertTrue(claims.validate_integrity(self.f.office))

    def test_old_boundary_is_readable_and_replayable_but_not_newly_applied(self):
        saved,body,_=self.legacy();before=deepcopy(saved)
        self.assertEqual(v1.ENTITLEMENT_RULE_VERSION,saved['plan']['rule_version'])
        self.assertEqual('2026-12-27',saved['plan']['episodes'][0]['entitlement_to'])
        self.assertEqual(saved,self.f.claims.get(self.f.owner,saved['id']))
        self.assertEqual(saved,self.f.claims.resolve_entitlement_case(self.f.owner,self.f.employee['id'],reference(saved),fresh=False))
        self.f.problem(409,lambda:self.f.claims.resolve_entitlement_case(self.f.owner,self.f.employee['id'],reference(saved)))
        self.f.pause()
        self.assertEqual(saved,self.f.claims.save(self.f.owner,body))
        self.assertTrue(claims.validate_integrity(self.f.office))
        self.assertEqual(saved,before)

    def test_explicit_correction_to_v2_preserves_first_revision_and_receipt(self):
        old,original,_=self.legacy()
        body,preview=self.f.request('sickness_history',old['details'])
        body.update(id=old['id'],revision=1,correction_reason='Belegte Folgetagsregel auf neue Fassung anwenden')
        revised=self.f.claims.save(self.f.owner,body)
        self.assertEqual((2,SICKNESS_RULE_VERSION),(revised['revision'],revised['plan']['rule_version']))
        self.assertEqual('2026-12-26',revised['plan']['episodes'][0]['entitlement_to'])
        self.assertEqual([old,revised],self.f.claims.get(self.f.owner,old['id'],True)['items'])
        self.assertEqual(old,self.f.claims.save(self.f.owner,original))
        self.assertEqual(revised,self.f.claims.resolve_entitlement_case(self.f.owner,self.f.employee['id'],reference(revised)))
        self.assertTrue(claims.validate_integrity(self.f.office))

    def test_void_of_old_original_does_not_recalculate_under_current_rule(self):
        old,body,_=self.legacy()
        void=self.f.claims.save(self.f.owner,dict(body,request_id=rid(),id=old['id'],revision=1,
            status='void',correction_reason='Historischen Nachweis zurücknehmen'))
        self.assertEqual(old['plan'],void['plan'])
        self.assertEqual(old['sources'],void['sources'])
        self.assertEqual(old,self.f.claims.save(self.f.owner,body))
        self.assertTrue(claims.validate_integrity(self.f.office))

    def test_indirect_old_history_in_regular_absence_is_also_not_newly_applied(self):
        f=self.f;history,_,_=self.legacy()
        schedule=f.schedule('2026-11');preparation=f.absence_preparation('2026-11-16','2026-11-16','sick')
        details=f.details()
        details.update(work_schedule_refs=[reference(schedule)],preparation_refs=[reference(preparation)],
            sickness_history_ref=reference(history))
        details['input']=dict(kind='sickness',hourly_rate_minor=1800,evidence_refs=[f.original],days=[
            dict(date='2026-11-16',scheduled_regular_seconds=28800,worked_regular_seconds=0,
                entitled=True,absence_is_only_cause=True,holiday_adjacent_unexcused=None,evidence_refs=[f.original])])
        with patch.object(claims,'requires_current_sickness_rule',return_value=False):
            old,body,_=f.save('regular_absence',details)
        self.assertEqual(old,f.claims.save(f.owner,body))
        self.assertTrue(claims.validate_integrity(f.office))
        self.assertEqual(old,f.claims.resolve_entitlement_case(f.owner,f.employee['id'],reference(old),fresh=False))
        f.problem(409,lambda:f.claims.resolve_entitlement_case(f.owner,f.employee['id'],reference(old)))
        f.problem(409,lambda:f.request('regular_absence',details))


if __name__=='__main__':unittest.main()
