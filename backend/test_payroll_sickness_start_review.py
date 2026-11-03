"""Independent commencement calendar and original-evidence checks.

Expected dates are calculated here by counting the statutory 28/42 days,
not by calling a second payroll component as an oracle.
"""
from copy import deepcopy
import unittest
from core import Problem
from payroll_sickness_start_2026 import derive_sickness_start

PROOF={'id':'a'*32,'revision':1,'content_hash':'b'*64}
def cause(identity,first,last,onset='before_employment'):
    return {'id':identity*32,'from':first,'to':last,'onset':onset,
        'first_scheduled_day':None,'continuation_group':'c'*32,
        'recovery_before':True,'unculpable':True,'evidence_refs':[PROOF]}
def history(start,first,last,contract):
    episode=cause('d',first,last)
    return {'employment_from':start,'employment_to':None,'pay_basis':'monthly',
        'complete_from':start,'complete_through':'2026-12-31','history_evidence_refs':[PROOF],
        'episodes':[episode], 'prevention_cases':[{'id':'1'*32,'episode_ids':[episode['id']],'evidence_refs':[PROOF]}],
        'employment_commencement':{'contract_concluded_on':contract,'evidence_refs':[PROOF]}}

class CommencementIndependentReview(unittest.TestCase):
    def test_month_end_waiting_and_full_42_calendar_days(self):
        source=history('2026-01-31','2026-01-27','2026-05-01','2026-01-20')
        old=deepcopy(source);plan=derive_sickness_start(source);row=plan['episodes'][0]
        self.assertEqual(('2026-02-27','2026-02-28','2026-04-10',42),
            tuple(row[k] for k in ('waiting_period_end','entitlement_from','entitlement_to','entitlement_calendar_days')))
        self.assertEqual(source,old)
        self.assertEqual('2026-01-27',row['from_date'])
        self.assertTrue(all(p['from_date']>='2026-01-31' for p in plan['phases']))

    def test_illness_ends_inside_waiting_period_no_wage_claim(self):
        source=history('2026-03-01','2026-02-26','2026-03-15','2026-02-20')
        row=derive_sickness_start(source)['episodes'][0]
        self.assertEqual(0,row['entitlement_calendar_days'])
        self.assertIsNone(row['entitlement_from']);self.assertIsNone(row['entitlement_to'])
        self.assertEqual('2026-03-28',row['waiting_period_end'])

    def test_original_ikk_three_days_reduce_later_same_illness_to_39(self):
        source=history('2026-10-01','2026-09-25','2026-10-31','2026-09-16')
        later=cause('e','2026-11-10','2026-12-31','before_work')
        source['episodes'].append(later)
        source['prevention_cases'].append({'id':'2'*32,'episode_ids':[later['id']],'evidence_refs':[PROOF]})
        left,right=derive_sickness_start(source)['episodes']
        self.assertEqual(('2026-10-29','2026-10-31',3),(left['entitlement_from'],left['entitlement_to'],left['entitlement_calendar_days']))
        self.assertEqual((3,'2026-11-10','2026-12-18',39),
            (right['prior_used_days'],right['entitlement_from'],right['entitlement_to'],right['entitlement_calendar_days']))
        self.assertEqual(42,left['entitlement_calendar_days']+right['entitlement_calendar_days'])

    def test_original_contract_proof_is_required_and_independently_bound(self):
        source=history('2026-03-01','2026-02-26','2026-05-31','2026-02-20')
        first=derive_sickness_start(source)
        amended=deepcopy(source);amended['employment_commencement']['evidence_refs']=[dict(PROOF,content_hash='f'*64)]
        second=derive_sickness_start(amended)
        self.assertNotEqual(first['source_hash'],second['source_hash'])
        self.assertEqual(first['legal_projection_hash'],second['legal_projection_hash'])
        self.assertNotEqual(first['plan_hash'],second['plan_hash'])
        for field,value in [('contract_concluded_on','2026-02-26'),('evidence_refs',[])]:
            bad=deepcopy(source);bad['employment_commencement'][field]=value
            with self.subTest(field=field),self.assertRaises(Problem):derive_sickness_start(bad)

if __name__=='__main__':unittest.main()
