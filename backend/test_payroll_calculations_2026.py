"""V5 composition: independent money conservation and actual source boundaries."""
from copy import deepcopy
import hashlib
import unittest

from core import Problem,canonical
from payroll_calculations_2026 import build_calculation_plan,calculate_calculation_source,CALCULATION_RULE_VERSION
from payroll_periods_2026 import build_period_plan,calculate_period_source
from payroll_segments_2026 import reference
from payroll_travel_tax_2026 import calculate_flat_travel_tax
from test_payroll_periods_2026 import period_snapshot
from test_payroll_claims_composition_2026 import fact
from test_payroll_entitlements_2026 import unpaid
from test_payroll_travel_tax_2026 import evidence


def source(**options):
    old=period_snapshot(**(dict(month='2026-11',start='2026-01-01',end=None,amount=500000,method='calendar_days_actual')|options))
    base=dict(id='0'*32,revision=1,content_hash='0'*64,employee_id=old['employee_id'],kind='period_case',status='active',
        details=old['case_details'],sources=old,plan=build_period_plan(old))
    return dict(schema_version=1,source_contract_version=1,rule_version=CALCULATION_RULE_VERSION,employee_id=old['employee_id'],
        month=old['month'],period_case=base,employment_terms=[old['employment_terms']],profiles=old['profiles'],identities=old['identities'],
        segment_events=[],thirty_day_rule=None,entitlements=[],travel_sources=[],flat_travel_tax=None,source_files=[])


def plan(value):return build_calculation_plan(value,rule_version=CALCULATION_RULE_VERSION,source_contract_version=1)
def calculate(value):return calculate_calculation_source(value,rule_version=CALCULATION_RULE_VERSION,source_contract_version=1)


def travel(value,*,individual=0,flat=0,benefit=0,m=False):
    ref=dict(id='4'*32,revision=1,content_hash='4'*64);allocations=[]
    for kind,amount in (('individual_taxable_payroll',individual),('flat_taxable_payroll',flat),('benefit_in_kind_non_cash',benefit)):
        if amount:allocations.append(dict(key=ref['id']+':'+kind,kind=kind,month=value['month'],amount_minor=amount,source_hash=ref['content_hash']))
    result=dict(kind='travel_allowances',schema_version=1,employee_id=value['employee_id'],month=value['month'],settlement_ref=ref,
        rule_version='de_travel_2026_v2',rule_hash='5'*64,allocations=allocations,tax_free_external_minor=2800,
        flat_taxable_payroll_minor=flat,individual_taxable_payroll_minor=individual,benefit_in_kind_non_cash_minor=benefit,letter_m=m)
    result['source_hash']=hashlib.sha256(canonical(result).encode()).hexdigest();value['travel_sources']=[result]
    return ref


def flat_policy(value,*,shift=False,recorded='2026-11-03'):
    adapter=value['travel_sources'][0];ref=adapter['settlement_ref']
    args=dict(federal_state='BW',church_tax=False,church_method='simplified',employer_bears_tax=not shift,
        evidence=evidence(eligible_limit_minor=adapter['flat_taxable_payroll_minor'],eligible_source_refs=[ref],
            taxation_recorded_on=recorded,employee_deduction_authorization=ref if shift else None))
    value['flat_travel_tax']=dict(parameters=args,calculation=calculate_flat_travel_tax(adapter['flat_taxable_payroll_minor'],**args),
        recording_context=dict(planned_recording_on=recorded,actual_recorded=False),policy=args['evidence']['policy_ref'],membership_identity=None,source_files=[])


class CompositeCalculationTests(unittest.TestCase):
    def test_single_full_month_matches_old_frozen_arithmetic_and_official_tax(self):
        value=source();before=deepcopy(value);result=calculate(value);old=calculate_period_source(value['period_case']['sources'])
        self.assertTrue(result['payroll_calculation_complete']);self.assertEqual(result['scope'],'regular_standard_segments')
        self.assertEqual(result['individual_wage_tax_minor'],78241)
        self.assertEqual(result['employee_social_total_minor'],108750)
        self.assertEqual(result['net_minor'],313009)
        for key in ('gross_minor','employee_contributions','employer_contributions','employer_levies','net_minor','payout_minor'):
            self.assertEqual(result[key],old[key],key)
        self.assertEqual(value,before)

    def test_explicit_rule_and_source_contract_never_fall_back_to_latest(self):
        value=source()
        for rule,contract in (('de_2026_periods_pap_v4',1),(CALCULATION_RULE_VERSION,2),(CALCULATION_RULE_VERSION,True)):
            with self.subTest(rule=rule,contract=contract),self.assertRaises(Problem):
                build_calculation_plan(value,rule_version=rule,source_contract_version=contract)

    def test_wage_change_has_two_entitlements_one_cap_and_one_tax_period(self):
        value=source(month='2026-07',amount=300000);old=value['period_case']['sources']
        right=deepcopy(old['preparation']['snapshot']['agreements'][0]);right.update(id='1'*32,content_hash='1'*64,effective_from='2026-07-16',amount_minor=400000)
        old['preparation']['snapshot']['agreements'].append(right)
        value['employment_terms'][0]['details']['agreement_refs'].append(reference(right))
        result=calculate(value)
        self.assertTrue(result['payroll_calculation_complete'],result['blockers']);self.assertEqual(result['gross_minor'],351613)
        details=result['period_details'];self.assertEqual(len(details['tax_periods']),1);self.assertEqual(len(details['social_periods']),1)
        self.assertEqual(details['social_periods'][0]['caps']['health_minor'],581250)
        self.assertEqual(details['social_periods'][0]['gross_minor'],351613)

    def test_tax_class_change_uses_end_features_without_fabricated_sv_split(self):
        value=source();left=value['profiles'][0];right=deepcopy(left)
        right.update(id='1'*32,content_hash='1'*64);right['profile'].update(effective_from='2026-11-16',tax_class=6)
        value['profiles'].append(right);identity=deepcopy(value['identities'][0]);identity.update(id='2'*32,content_hash='2'*64)
        identity['details'].update(profile_id=right['id'],valid_from='2026-11-16');value['identities'].append(identity)
        value['segment_events']=[dict(kind='tax_features_change',effective_from='2026-11-16',before_profile_ref=reference(left),
            after_profile_ref=reference(right),source_file_ids=['3'*32],reason='Actual ELStAM change')]
        result=calculate(value);self.assertTrue(result['payroll_calculation_complete'],result['blockers'])
        self.assertEqual(len(result['period_details']['social_periods']),1)
        self.assertEqual(result['period_details']['tax_periods'][0]['profile_ref'],reference(right))
        self.assertEqual(result['period_details']['tax_calculations'][0]['calculation']['inputs']['gross_minor'],500000)
        value['segment_events'][0]['kind']='data_correction'
        with self.assertRaises(Problem):plan(value)

    def test_unpaid_days_reduce_money_without_reducing_monthly_tax_or_continuing_sv(self):
        value=source(amount=300000);value['entitlements']=[fact('unpaid_continuation',unpaid('2026-11-10','2026-11-20'),value['employment_terms'][0])]
        result=calculate(value)
        self.assertTrue(result['payroll_calculation_complete'],result['blockers']);self.assertEqual(result['gross_minor'],190000)
        self.assertEqual(result['period_details']['social_periods'][0]['days'],30)
        self.assertEqual(result['period_details']['tax_periods'][0]['lzz'],2)

    def test_expired_unpaid_continuation_reduces_actual_sv_only(self):
        value=source(amount=300000);value['entitlements']=[fact('unpaid_continuation',unpaid('2026-10-05','2026-11-30'),value['employment_terms'][0])]
        result=calculate(value)
        self.assertTrue(result['payroll_calculation_complete'],result['blockers']);self.assertEqual(result['gross_minor'],0)
        social=result['period_details']['social_periods'];self.assertEqual([(v['start'],v['end'],v['days']) for v in social],[('2026-11-01','2026-11-04',4)])
        self.assertEqual(result['period_details']['tax_periods'][0]['tax_days'],30);self.assertEqual(result['payout_minor'],0)

    def test_m_only_has_no_extra_salary_and_duplicate_adapter_fails(self):
        value=source();travel(value,m=True);result=calculate(value)
        self.assertTrue(result['payroll_calculation_complete']);self.assertEqual(result['gross_minor'],500000)
        self.assertEqual(result['payout_minor'],313009);self.assertTrue(result['period_details']['travel']['letter_m'])
        value['travel_sources']*=2
        with self.assertRaises(Problem):calculate(value)

    def test_taxable_travel_and_non_cash_meal_are_in_tax_sv_with_exact_net_deduction(self):
        value=source(amount=498000);travel(value,individual=1500,benefit=500,m=True)
        result=calculate(value);self.assertTrue(result['payroll_calculation_complete'],result['blockers'])
        self.assertEqual(result['gross_minor'],500000);self.assertEqual(result['individual_wage_tax_minor'],78241)
        self.assertEqual(result['employee_social_total_minor'],108750)
        self.assertEqual((result['net_minor'],result['net_deductions_minor'],result['payout_minor']),(313009,500,312509))
        self.assertEqual(result['period_details']['travel']['tax_free_external_minor'],2800)

    def test_flat_travel_is_paid_once_without_individual_tax_or_timely_sv(self):
        value=source();travel(value,flat=1400);flat_policy(value)
        result=calculate(value);self.assertTrue(result['payroll_calculation_complete'],result['blockers'])
        self.assertEqual((result['gross_minor'],result['individual_wage_tax_minor'],result['employee_social_total_minor'],result['payout_minor']),
            (501400,78241,108750,314409))
        self.assertEqual(result['employer_flat_tax_minor'],384)
        self.assertEqual(result['period_details']['social_periods'][0]['gross_minor'],500000)
        self.assertEqual(result['period_details']['tax_periods'][0]['gross_minor'],500000)

    def test_authorized_flat_tax_shift_changes_cash_not_statutory_employer_liability(self):
        value=source();travel(value,flat=1400);flat_policy(value,shift=True)
        result=calculate(value)
        self.assertEqual((result['net_minor'],result['net_deductions_minor'],result['payout_minor'],result['employer_flat_tax_minor']),
            (314409,384,314025,384))
        self.assertEqual(result['employee_tax_minor'],78241)

    def test_late_flat_tax_keeps_individual_tax_separate_but_adds_actual_sv(self):
        value=source();travel(value,flat=1400);flat_policy(value,recorded='2027-03-01')
        result=calculate(value);self.assertTrue(result['payroll_calculation_complete'],result['blockers'])
        self.assertEqual(result['period_details']['social_periods'][0]['gross_minor'],501400)
        self.assertEqual(result['period_details']['tax_periods'][0]['gross_minor'],500000)
        self.assertEqual(result['individual_wage_tax_minor'],78241)
        self.assertGreater(result['employee_social_total_minor'],108750)

    def test_unconfirmed_travel_policy_or_manipulated_capacity_never_yields_net(self):
        value=source();travel(value,flat=1400);result=calculate(value)
        self.assertFalse(result['payroll_calculation_complete']);self.assertIsNone(result['net_minor'])
        flat_policy(value);value['flat_travel_tax']['parameters']['evidence']['eligible_limit_minor']=999999
        with self.assertRaises(Problem):calculate(value)


if __name__=='__main__':unittest.main()
