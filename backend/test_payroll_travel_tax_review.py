"""Independent legal-boundary review of Root's pure travel tax helper.

Expectations follow the current equal-state decree (REVOSax 16974 I.2),
DRV Contributions 2026 section 5.4 and separately calculated cent products.
No provider or company data is used; actual source resolution is another layer.
"""
from copy import deepcopy
import unittest

from core import Problem
from payroll_travel_tax_2026 import calculate_flat_travel_tax

POLICY=dict(id='1'*32,revision=2,content_hash='a'*64)
TRAVEL=dict(id='2'*32,revision=1,content_hash='b'*64)
PROOF=dict(id='3'*32,revision=1,content_hash='c'*64)


def context(**changes):
    return dict(policy_ref=deepcopy(POLICY),filing_period_from='2026-10-01',
        filing_period_to='2026-12-31',payroll_month='2026-12',
        taxation_recorded_on='2026-12-31',tax_certificate_issued_on=None,
        eligible_limit_minor=12347,eligible_source_refs=[deepcopy(TRAVEL)],
        church_rate_region='standard',church_method_applies_to_all=True,
        church_membership_evidence=None,employee_deduction_authorization=None)|changes


def compute(**changes):
    return calculate_flat_travel_tax(12347,**(dict(federal_state='BW',church_tax=False,
        church_method='simplified',employer_bears_tax=True,evidence=context())|changes))


class IndependentTravelTaxReview(unittest.TestCase):
    def test_official_employee_declaration_is_valid_evidence_when_official_data_missing(self):
        # Equal-state decree I.2.b explicitly allows its attached signed model.
        proof=dict(kind='official_employee_declaration',reference=PROOF)
        for member,church in [(False,0),(True,246)]:
            with self.subTest(member=member):
                result=compute(church_method='evidence',church_tax=member,
                    evidence=context(church_membership_evidence=proof))
                self.assertTrue(result['can_calculate'])
                self.assertEqual(church,result['church_tax_minor'])

    def test_documented_unknown_membership_uses_general_rate_not_zero_or_simplified_rate(self):
        # Equal-state decree I.2.d expressly provides the general-rate branch.
        proof=dict(kind='unknown_membership_general_rate',reference=PROOF)
        result=compute(federal_state='BE',church_method='evidence',church_tax=None,
            evidence=context(church_membership_evidence=proof))
        self.assertTrue(result['can_calculate'])
        self.assertEqual((900,3086,169,277,3532),tuple(result[key] for key in
            ('church_rate_basis_points','wage_tax_minor','solidarity_minor','church_tax_minor','statutory_employer_due_minor')))

    def test_unproven_unknown_still_blocks_instead_of_becoming_no_church_tax(self):
        for proof in (None,dict(kind='elstam',reference=PROOF)):
            result=compute(church_method='evidence',church_tax=None,
                evidence=context(church_membership_evidence=proof))
            self.assertFalse(result['can_calculate'])
            self.assertIsNone(result['church_tax_minor'])

    def test_explicit_unknown_proof_cannot_contradict_known_membership(self):
        proof=dict(kind='unknown_membership_general_rate',reference=PROOF)
        for member in (False,True):
            with self.subTest(member=member),self.assertRaises(Problem):
                compute(church_method='evidence',church_tax=member,
                    evidence=context(church_membership_evidence=proof))
        declaration=dict(kind='official_employee_declaration',reference=PROOF)
        missing=compute(church_method='evidence',church_tax=None,
            evidence=context(church_membership_evidence=declaration))
        self.assertFalse(missing['can_calculate'])
        self.assertIsNone(missing['church_tax_minor'])

    def test_fractional_cent_components_never_use_commercial_or_combined_rounding(self):
        result=compute()
        # EUR123.47 -> EUR30.8675 -> 3086ct LSt; Soli169.73ct, KiSt138.87ct.
        self.assertEqual((3086,169,138,3393),tuple(result[key] for key in
            ('wage_tax_minor','solidarity_minor','church_tax_minor','statutory_employer_due_minor')))
        self.assertEqual(12347,result['employee_cash_after_flat_tax_minor'])

    def test_earlier_certificate_controls_social_exemption_even_before_february(self):
        cases=[('2027-01-11',True,0),('2027-01-13',False,12347)]
        for booked,exempt,social in cases:
            with self.subTest(booked=booked):
                result=compute(evidence=context(taxation_recorded_on=booked,
                    tax_certificate_issued_on='2027-01-12'))
                self.assertTrue(result['can_calculate'])
                self.assertEqual(exempt,result['social_exempt'])
                self.assertEqual(social,result['social_gross_minor'])
                self.assertEqual(3393,result['statutory_employer_due_minor'])
                self.assertEqual('2027-01-12',result['social_exemption_conditions']['deadline'])

    def test_late_certificate_never_extends_february_social_deadline(self):
        before=compute(evidence=context(taxation_recorded_on='2027-02-28',tax_certificate_issued_on='2027-03-02'))
        after=compute(evidence=context(taxation_recorded_on='2027-03-01',tax_certificate_issued_on='2027-03-02'))
        self.assertTrue(before['social_exempt']);self.assertFalse(after['social_exempt'])
        self.assertEqual(before['statutory_employer_due_minor'],after['statutory_employer_due_minor'])
        self.assertEqual('2027-02-28',after['social_exemption_conditions']['deadline'])

    def test_quarter_policy_is_same_across_months_and_membership(self):
        december=compute()
        october=compute(church_tax=True,evidence=context(payroll_month='2026-10',taxation_recorded_on='2026-10-31'))
        self.assertEqual(december['policy_key'],october['policy_key'])
        self.assertEqual(december['policy_choice_hash'],october['policy_choice_hash'])
        self.assertNotEqual(december['source_hash'],october['source_hash'])
        changed=compute(church_method='evidence',evidence=context(church_membership_evidence=dict(kind='elstam',reference=PROOF)))
        self.assertEqual(december['policy_key'],changed['policy_key'])
        self.assertNotEqual(december['policy_choice_hash'],changed['policy_choice_hash'])

    def test_capacity_and_source_revision_are_material_even_when_tax_equal(self):
        source=compute()
        revised=compute(evidence=context(eligible_source_refs=[dict(TRAVEL,revision=2)]))
        self.assertEqual(source['statutory_employer_due_minor'],revised['statutory_employer_due_minor'])
        self.assertNotEqual(source['source_hash'],revised['source_hash'])
        over=compute(evidence=context(eligible_limit_minor=12346))
        self.assertFalse(over['can_calculate']);self.assertIsNone(over['wage_tax_minor'])
        self.assertIsNone(over['social_gross_minor'])

    def test_economic_transfer_preserves_all_employer_tax_debt_components(self):
        ordinary=compute()
        shifted=compute(employer_bears_tax=False,evidence=context(employee_deduction_authorization=PROOF))
        for key in ('wage_tax_minor','solidarity_minor','church_tax_minor','statutory_employer_due_minor'):
            self.assertEqual(ordinary[key],shifted[key])
        self.assertEqual((0,3393,8954),tuple(shifted[key] for key in
            ('employer_total_minor','employee_tax_minor','employee_cash_after_flat_tax_minor')))

    def test_wrong_jurisdiction_and_boolean_reference_revision_are_rejected(self):
        for values in (context(church_rate_region='ni_ev_westfalen'),
            context(policy_ref=dict(POLICY,revision=True)),
            context(eligible_source_refs=[dict(TRAVEL,revision=True)])):
            with self.subTest(values=values),self.assertRaises(Problem):compute(evidence=values)


if __name__=='__main__':unittest.main()
