"""V7 canonical drafts and independently derived KBS/PAP grouping boundaries.

Composition fixtures use accepted private v5/annual originals. New receipt
events are explicitly drafts, not fabricated accepted payments or consumption.
"""
from copy import deepcopy
import unittest

from core import Problem,canonical
from business_payroll_facts import reference
from payroll_multiple_oneoff_2026 import (
    MULTIPLE_RULE_VERSION,calculate_multiple_source,select_monthly_assignment)
from payroll_pap_oneoff_2026 import calculate_standard_one_off_tax
from test_business_payroll import rid
import test_payroll_oneoff_2026 as social_fixture
import test_payroll_oneoff_composition_2026 as source_fixture


def calculate(source,**changes):
    return calculate_multiple_source(source,**(dict(rule_version=MULTIPLE_RULE_VERSION,source_contract_version=1)|changes))


def events(a=150000,b=100000,month='2026-03'):
    return [dict(component_key='1'*32,event_key='a'*32,receipt_date=month+'-10',gross_minor=a),
        dict(component_key='2'*32,event_key='b'*32,receipt_date=month+'-25',gross_minor=b)]


class PublishedMultipleBoundaries(unittest.TestCase):
    def assign(self,group,current=None,previous=None):
        current=current or social_fixture.room(social_fixture.basis(2026,'2026-03-31',500000))
        previous=previous or social_fixture.room(social_fixture.basis(2025,'2025-12-31',500000))
        return select_monthly_assignment(receipt_events=group,current_room=current,previous_room=previous,
            current_period_ref=social_fixture.ref(701),previous_period_ref=social_fixture.ref(702),
            mandatory_statutory_health=True,previous_year_employment=True)

    def test_kbs_s19_whole_march_month_moves_even_when_first_bonus_alone_fits(self):
        single=self.assign(events()[:1]);combined=self.assign(events())
        self.assertEqual(single['assignment']['social_year'],2026)
        self.assertEqual(combined['gross_minor'],250000)
        self.assertEqual(combined['assignment']['social_year'],2025)
        self.assertEqual(combined['assignment']['bases_minor'],dict.fromkeys(('health','care','pension','unemployment'),250000))

    def test_exact_monthly_health_boundary_and_one_cent_above(self):
        exact=self.assign(events(b=93750));above=self.assign(events(b=93751))
        self.assertEqual((exact['assignment']['social_year'],exact['gross_minor']),(2026,243750))
        self.assertEqual((above['assignment']['social_year'],above['gross_minor']),(2025,243751))

    def test_later_running_correction_changes_entire_groups_social_year(self):
        original=self.assign(events(b=90000))
        basis=social_fixture.basis(2026,'2026-03-31',500000)
        for branch in basis['periods'][-1]['branches'].values():branch['contributed_minor']+=10000
        corrected=self.assign(events(b=90000),current=social_fixture.room(basis))
        self.assertEqual(original['assignment']['social_year'],2026)
        self.assertEqual(corrected['assignment']['social_year'],2025)
        self.assertEqual(corrected['gross_minor'],original['gross_minor'])

    def test_may_group_has_independent_health_and_pension_limits(self):
        current=social_fixture.room(social_fixture.basis(2026,'2026-05-31',500000))
        group=self.assign(events(500000,100000,month='2026-05'),current=current)
        self.assertEqual(group['assignment']['bases_minor'],dict(health=406250,care=406250,pension=600000,unemployment=600000))
        self.assertFalse(group['assignment']['march_clause'])

    def test_april_receipt_does_not_become_march_clause_from_prior_assignment_period(self):
        march=self.assign([dict(item,receipt_date='2026-03-31') for item in events()])
        april=self.assign([dict(item,receipt_date='2026-04-01') for item in events()])
        self.assertTrue(march['assignment']['march_clause']);self.assertFalse(april['assignment']['march_clause'])
        self.assertEqual(april['assignment']['assigned_period_end'],'2026-03-31')
        self.assertEqual(april['assignment']['bases_minor']['health'],243750)

    def test_input_order_is_not_a_statutory_grouping_rule(self):
        self.assertEqual(self.assign(events()),self.assign(list(reversed(events()))))
        with self.assertRaises(Problem):self.assign([events()[0],events()[0]])
        with self.assertRaises(Problem):self.assign([events()[0],dict(events()[1],receipt_date='2026-04-01')])
        with self.assertRaises(Problem):self.assign([dict(events()[0],gross_minor=True)])

    def test_pap_published_solidarity_counterexample_forbids_assumed_additivity(self):
        args=dict(tax_class=1,children_half_units=0,additional_health_percent='2.90',saxony=False,
            childless_surcharge=True,care_child_discounts=0,church_member=False,annual_allowance_minor=0,annual_addition_minor=0)
        first=calculate_standard_one_off_tax(annual_pay_before_minor=8750000,one_off_minor=250000,**args)
        second=calculate_standard_one_off_tax(annual_pay_before_minor=9000000,one_off_minor=250000,**args)
        grouped=calculate_standard_one_off_tax(annual_pay_before_minor=8750000,one_off_minor=500000,**args)
        self.assertEqual((first['annual_tax_before_minor'],first['annual_tax_after_minor'],second['annual_tax_after_minor']),(1848600,1943800,2039000))
        self.assertEqual((first['STS'],second['STS'],grouped['STS']),(95200,95200,190400))
        self.assertEqual((first['SOLZS'],second['SOLZS'],grouped['SOLZS']),(0,5236,10472))
        self.assertNotEqual(first['SOLZS']+second['SOLZS'],grouped['SOLZS'])


class CanonicalMultipleComposition(unittest.TestCase):
    def setUp(self):
        self.c=source_fixture.OneoffCompositionTests('runTest');self.c.setUp();self.addCleanup(self.c.doCleanups)
        self.f=self.c.f

    def source(self,original_source=None,**changes):
        old=original_source if original_source is not None else self.c.source(**changes)
        earning=old['one_off_earning'];event=rid()
        result=dict(schema_version=1,source_contract_version=1,rule_version=MULTIPLE_RULE_VERSION,
            employee_id=old['employee_id'],month=old['month'],running_calculation_case=old['running_calculation_case'],
            components=[dict(component_key=earning['id'],earning=earning,planned_receipts=[dict(event_key=event,
                receipt_date=earning['details']['planned_receipt_date'],gross_minor=earning['details']['amount_minor'],document_refs=[self.f.original])])],
            current_annual_basis=old['current_annual_basis'],previous_annual_basis=old['previous_annual_basis'],
            annual_tax_forecasts=[dict(event_key=event,annual_tax_forecast=old['annual_tax_forecast'])],
            completeness=dict(month_events_complete=True,evidence_ref=self.f.original))
        return result,old

    def additional(self,source,amount=100000):
        original=source['components'][0]['earning'];details=deepcopy(original['details'])
        details.update(amount_minor=amount,claim_reference='Actual independently accepted second contractual bonus')
        earning,_,_=self.f.save('one_off_earning',details)
        source['components'].append(dict(component_key=earning['id'],earning=earning,planned_receipts=[dict(event_key=rid(),
            receipt_date=details['planned_receipt_date'],gross_minor=amount,document_refs=[self.f.original])]))
        source['annual_tax_forecasts']=[]

    def test_one_complete_original_claim_preserves_every_v6_money_amount(self):
        source,old=self.source(flat_travel=True,shifted=True);before=canonical(source)
        result=calculate(source);original=source_fixture.calculate(old)
        self.assertTrue(result['payroll_calculation_complete'])
        self.assertEqual(result['multiple_one_off_details']['single_original_calculation'],original)
        self.assertEqual(result['running_calculation'],original['running_calculation'])
        for key in ('gross_minor','net_minor','payout_minor','individual_wage_tax_minor','solidarity_minor','employee_social_total_minor',
                'employer_social_total_minor','employer_flat_tax_minor','employer_total_excluding_accident_insurance_minor'):
            self.assertEqual(result[key],original[key],key)
        self.assertEqual(canonical(source),before)

    def test_two_actual_claim_originals_same_day_have_social_group_but_no_invented_tax_or_net(self):
        source,_=self.source(january=True,bonus=100000,previous=True);self.additional(source,64860)
        before=canonical(source);result=calculate(source);details=result['multiple_one_off_details']
        self.assertEqual(details['social_month_group']['assignment']['social_year'],2025)
        self.assertEqual(details['social_month_group']['gross_minor'],164860)
        self.assertEqual(result['gross_minor'],329376)
        self.assertFalse(result['payroll_calculation_complete']);self.assertFalse(result['social_contributions_available'])
        for field in ('net_minor','individual_wage_tax_minor','employee_social_total_minor','employer_social_total_minor','payout_minor'):
            self.assertIsNone(result[field],field)
        self.assertIsNone(details['tax_groups']);self.assertIsNone(details['social_month_group']['component_allocations'])
        self.assertIn('multiple_oneoff_tax_grouping_unresolved',[value['code'] for value in result['blockers']])
        source['components'].reverse();self.assertEqual(calculate(source),result)
        source['components'].reverse();self.assertEqual(canonical(source),before)

    def test_partial_claim_has_explicit_unpaid_remainder_and_no_invented_fulfillment(self):
        source,_=self.source();source['components'][0]['planned_receipts'][0]['gross_minor']=10000
        result=calculate(source)
        self.assertEqual(result['multiple_one_off_details']['components'][0]['remaining_claim_minor'],40000)
        self.assertFalse(result['payroll_calculation_complete']);self.assertIsNone(result['net_minor'])
        self.assertFalse(result['multiple_one_off_details']['actual_payment_created'])
        self.assertFalse(result['multiple_one_off_details']['claim_consumption_created'])

    def test_two_planned_events_for_one_claim_do_not_duplicate_claim_or_claim_full_payment(self):
        source,_=self.source();part=source['components'][0];first=part['planned_receipts'][0]
        first['gross_minor']=20000;part['planned_receipts'].append(dict(first,event_key=rid(),gross_minor=30000))
        result=calculate(source)
        self.assertEqual(len(result['multiple_one_off_details']['components']),1)
        self.assertEqual(len(result['multiple_one_off_details']['receipt_events']),2)
        self.assertEqual(result['multiple_one_off_details']['amount_minor'],50000)
        self.assertIsNone(result['net_minor'])

    def test_duplicates_overconsumption_false_completeness_and_unknown_payment_flags_fail(self):
        source,_=self.source();cases=[]
        bad=deepcopy(source);bad['components'].append(deepcopy(bad['components'][0]));cases.append(bad)
        bad=deepcopy(source);bad['components'][0]['planned_receipts'][0]['gross_minor']+=1;cases.append(bad)
        bad=deepcopy(source);bad['completeness']['month_events_complete']=False;cases.append(bad)
        bad=deepcopy(source);bad['components'][0]['planned_receipts'][0]['actual_paid']=True;cases.append(bad)
        bad=deepcopy(source);bad['components'][0]['component_key']=rid();cases.append(bad)
        bad=deepcopy(source);bad['components'][0]['planned_receipts'][0]['document_refs'][0]['content_hash']='0'*64;cases.append(bad)
        for index,bad in enumerate(cases):
            with self.subTest(index=index),self.assertRaises(Problem):calculate(bad)
        for changes in (dict(rule_version='de_2026_oneoff_composition_v6'),dict(source_contract_version=True),dict(source_contract_version=2)):
            with self.subTest(changes=changes),self.assertRaises(Problem):calculate(source,**changes)

    def test_group_threshold_needs_proven_prior_year_instead_of_silently_zero_room(self):
        source,_=self.source(january=True,bonus=100000);self.additional(source,100000)
        result=calculate(source)
        self.assertIsNone(result['multiple_one_off_details']['social_month_group'])
        self.assertIn('previous_year_evidence_required',[value['code'] for value in result['blockers']])
        self.assertIsNone(result['net_minor'])


class ActualSource4Successor(unittest.TestCase):
    source=CanonicalMultipleComposition.source

    def test_paid_source4_prior_month_compact_annual_original_is_usable_in_v7(self):
        import business_schema
        import test_business_payroll_oneoff_annual as actual_fixture
        workflow=actual_fixture.OneoffAnnualWorkflow('runTest');workflow.setUp();self.addCleanup(workflow.doCleanups)
        self.f=workflow.f
        _,_,old_run,old_payment=workflow.first()
        case,_,run,payment,basis,_=workflow.successor('2026-11',[old_run],[old_payment])
        compact=basis['sources']['payroll_runs'][0]
        self.assertEqual(compact['projection_format'],'source4_annual_reference_v1')
        self.assertEqual(compact['source'],dict(source_schema_version=4,month='2026-10'))
        self.assertNotIn('calculation',compact)
        source,_=self.source(original_source=case['sources']['calculation_source'])
        result=calculate(source)
        self.assertTrue(result['payroll_calculation_complete'])
        self.assertEqual(result['multiple_one_off_details']['single_original_calculation'],run['calculation'])
        self.assertEqual(result['multiple_one_off_details']['social_month_group']['assignment']['bases_minor'],
            dict.fromkeys(('health','care','pension','unemployment'),50000))
        self.assertTrue(business_schema.validate_integrity(self.f.office))


if __name__=='__main__':unittest.main()
