"""Independent v7 review: accepted sources, adversarial bindings and invariants.

No new payroll/tax formula is reproduced here. Source fixtures use actual private
domain acceptance; the v7 receipt events remain explicitly planned proposals.
"""
from copy import deepcopy
import unittest

from core import Problem, canonical
from payroll_annual_basis_2026 import build_annual_plan
from payroll_multiple_oneoff_2026 import calculate_multiple_source, MULTIPLE_RULE_VERSION, select_monthly_assignment
from payroll_oneoff_composition_2026 import MONEY_FIELDS
import test_payroll_multiple_oneoff_2026 as fixtures
import test_payroll_oneoff_2026 as social
import test_payroll_oneoff_composition_2026 as single


def calculate(source):
    return calculate_multiple_source(source, rule_version=MULTIPLE_RULE_VERSION, source_contract_version=1)


class IndependentMultipleReview(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.CanonicalMultipleComposition('runTest')
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)

    def assertRejected(self, source):
        with self.assertRaises(Problem) as caught:calculate(source)
        self.assertIn(caught.exception.status,(400,409))

    def test_complete_prior_year_single_keeps_all_v6_money_and_no_writes(self):
        source,original=self.fixture.source(january=True,bonus=200000,previous=True)
        tables=('business_payroll_events','business_payroll_cash_batches','business_euer_entries','business_payroll_annual_events')
        counts=lambda:{name:self.fixture.f.office.db.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in tables}
        before=counts(); serialized=canonical(source); result=calculate(source); old=single.calculate(original)
        self.assertTrue(result['payroll_calculation_complete'])
        self.assertEqual(result['multiple_one_off_details']['social_month_group']['assignment']['social_year'],2025)
        self.assertEqual(result['multiple_one_off_details']['single_original_calculation'],old)
        for field in MONEY_FIELDS+('gross_minor',):self.assertEqual(result[field],old[field],field)
        self.assertEqual(canonical(source),serialized);self.assertEqual(counts(),before)

    def test_two_dated_partial_events_preserve_remainder_order_and_all_unknown_net_fields(self):
        source,_=self.fixture.source();part=source['components'][0];receipt=part['planned_receipts'][0]
        part['planned_receipts']=[dict(receipt,event_key='a'*32,receipt_date='2026-10-20',gross_minor=10000),
            dict(receipt,event_key='b'*32,gross_minor=15000)]
        source['annual_tax_forecasts']=[]
        before=canonical(source);result=calculate(source);detail=result['multiple_one_off_details']
        self.assertEqual(detail['components'][0]['remaining_claim_minor'],25000)
        self.assertEqual(detail['amount_minor'],25000)
        self.assertEqual([item['receipt_date'] for item in detail['receipt_events']],['2026-10-20','2026-10-31'])
        self.assertFalse(result['payroll_calculation_complete']);self.assertFalse(result['social_contributions_available'])
        for field in MONEY_FIELDS:self.assertIsNone(result[field],field)
        self.assertIsNone(detail['tax_groups']);self.assertFalse(detail['actual_payment_created'])
        self.assertFalse(detail['claim_consumption_created']);self.assertEqual(canonical(source),before)
        part['planned_receipts'].reverse();self.assertEqual(calculate(source),result)

    def test_one_event_identity_cannot_be_shared_between_two_accepted_claims(self):
        source,_=self.fixture.source();self.fixture.additional(source)
        source['components'][1]['planned_receipts'][0]['event_key']=source['components'][0]['planned_receipts'][0]['event_key']
        self.assertRejected(source)

    def test_sum_of_distinct_partial_receipts_cannot_overdraw_original_claim_by_one_cent(self):
        source,_=self.fixture.source();part=source['components'][0];receipt=part['planned_receipts'][0]
        part['planned_receipts']=[dict(receipt,event_key='a'*32,gross_minor=25000),dict(receipt,event_key='b'*32,gross_minor=25001)]
        self.assertRejected(source)

    def test_employee_month_cutoff_and_current_case_original_are_bound(self):
        source,_=self.fixture.source();cases=[]
        bad=deepcopy(source);bad['employee_id']='f'*32;cases.append(bad)
        bad=deepcopy(source);bad['running_calculation_case']['employee_id']='f'*32;cases.append(bad)
        bad=deepcopy(source);bad['components'][0]['earning']['employee_id']='f'*32;cases.append(bad)
        bad=deepcopy(source);bad['components'][0]['planned_receipts'][0]['receipt_date']='2026-11-01';cases.append(bad)
        bad=deepcopy(source);bad['components'][0]['planned_receipts'][0]['receipt_date']='2026-10-30';cases.append(bad)
        bad=deepcopy(source);bad['current_annual_basis']['sources']['current_calculation_case']['id']='f'*32;cases.append(bad)
        for index,bad in enumerate(cases):
            with self.subTest(index=index):self.assertRejected(bad)

    def test_rebuilt_foreign_employer_claim_plan_does_not_override_group_employer(self):
        source,_=self.fixture.source();earning=source['components'][0]['earning']
        earning['sources']['identity']=deepcopy(earning['sources']['identity'])
        earning['sources']['identity']['details']['employer_name']='Different synthetic legal employer'
        earning['plan']=build_annual_plan(earning['sources'])
        source['annual_tax_forecasts']=[]
        self.assertRejected(source)

    def test_rebuilt_current_projection_cannot_invent_social_room(self):
        source,_=self.fixture.source();basis=source['current_annual_basis']
        basis['sources']['internal_periods'][0]['periods'][0]['branches']['health']['contributed_minor']=0
        basis['plan']=build_annual_plan(basis['sources']);source['annual_tax_forecasts']=[]
        self.assertRejected(source)

    def test_existing_forecast_cannot_be_assigned_to_second_accepted_claim(self):
        source,_=self.fixture.source();forecast=deepcopy(source['annual_tax_forecasts'][0]);self.fixture.additional(source)
        forecast['event_key']=source['components'][1]['planned_receipts'][0]['event_key']
        source['annual_tax_forecasts']=[forecast]
        self.assertRejected(source)

    def test_original_hash_revision_and_duplicate_proof_are_not_free_flags(self):
        source,_=self.fixture.source();cases=[]
        bad=deepcopy(source);bad['completeness']['evidence_ref']=dict(bad['completeness']['evidence_ref'],content_hash='0'*64);cases.append(bad)
        bad=deepcopy(source);receipt=bad['components'][0]['planned_receipts'][0];receipt['document_refs']=[dict(receipt['document_refs'][0],revision=2)];cases.append(bad)
        bad=deepcopy(source);receipt=bad['components'][0]['planned_receipts'][0];receipt['document_refs']*=2;cases.append(bad)
        bad=deepcopy(source);bad['components'][0]['planned_receipts'][0]['actual_paid']=True;cases.append(bad)
        for index,bad in enumerate(cases):
            with self.subTest(index=index):self.assertRejected(bad)

    def test_prior_minijob_history_is_explicit_blocker_not_empty_prior_employment(self):
        source,_=self.fixture.source(january=True,bonus=200000,previous='minijob')
        result=calculate(source)
        self.assertIn('multiple_oneoff_mixed_sections_required',[value['code'] for value in result['blockers']])
        self.assertIsNone(result['multiple_one_off_details']['social_month_group'])
        self.assertFalse(result['payroll_calculation_complete']);self.assertIsNone(result['net_minor'])


class IndependentMonthlyRoomReview(unittest.TestCase):
    def assign(self,current,previous,events):
        return select_monthly_assignment(receipt_events=events,current_room=current,previous_room=previous,
            current_period_ref=social.ref(701),previous_period_ref=social.ref(702),
            mandatory_statutory_health=True,previous_year_employment=True)

    def test_prior_other_month_consumption_remains_in_whole_month_assignment(self):
        current=social.room(social.basis(2026,'2026-03-31',500000))
        original=social.basis(2025,'2025-12-31',500000);previous=social.room(original)
        events=fixtures.events(350000,350000)
        before=self.assign(current,previous,events)
        original['prior_one_offs'].append(dict(source_ref=social.ref(999),section_key='regular',assigned_period_end='2025-12-31',
            bases_minor=dict(health=200000,care=200000,pension=200000,unemployment=200000)))
        after=self.assign(current,social.room(original),events)
        self.assertEqual(before['assignment']['social_year'],2025);self.assertEqual(after['assignment']['social_year'],2025)
        self.assertEqual(after['gross_minor'],before['gross_minor'])
        self.assertEqual(before['assignment']['bases_minor']['health']-after['assignment']['bases_minor']['health'],200000)
        self.assertEqual(before['assignment']['bases_minor']['pension'],after['assignment']['bases_minor']['pension'])
        self.assertIsNone(after['component_allocations'])

    def test_previous_year_room_cannot_belong_to_different_person_or_employer(self):
        current=social.room(social.basis(2026,'2026-03-31',500000));previous=social.room(social.basis(2025,'2025-12-31',500000))
        for key in ('employee_id','employer_key','section_key'):
            bad=deepcopy(previous);bad[key]='different-synthetic-source'
            with self.subTest(key=key),self.assertRaises(Problem):self.assign(current,bad,fixtures.events())


if __name__=='__main__':unittest.main()
