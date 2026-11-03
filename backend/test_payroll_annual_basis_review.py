"""Independent real-domain review of tax/SV year separation and old receipts."""
import unittest

import business_payroll_annual_basis as annual
from business_payroll_facts import reference
import test_business_payroll_annual_basis as fixtures


class AnnualBasisIndependentReview(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.PayrollAnnualBasisTests();self.f.setUp()
        self.addCleanup(self.f.doCleanups);self.addCleanup(self.f.tearDown)
        self.f.regular_contract();self.terms,_=self.f.terms()

    def december(self,received='2025-12-31'):
        d=self.f.imported_details()
        d.update(period_start='2025-12-01',period_end='2025-12-31',employment_from='2025-12-01',employment_to='2025-12-31',
            original_payroll_reference='Actual December 2025 prior-employment original',original_rule_version='Documented 2025 original')
        for b in d['branches'].values():b['eligible_intervals'][0].update(start='2025-12-01',end='2025-12-31')
        d['running_receipts'][0]['received_on']=received
        return self.f.save(details=d)[0]

    def january_bonus(self,period):
        return self.f.save('imported_one_off',dict(employer_identity_ref=reference(self.f.identity),verification_note='Actual prior-year social assignment and January receipt checked',
            receipt_date='2026-01-15',amount_minor=50000,assigned_period_ref=reference(period),section_key='regular',
            bases_minor={k:50000 for k in annual.BRANCHES},original_reference='January actual bonus assigned to December 2025',document_refs=[self.f.original]))[0]

    def prior_basis(self,period,bonuses=()):
        return self.f.basis_details(period,year=2025,coverage_to='2025-12-31',as_of_date='2026-01-21',
            imported_one_off_refs=[reference(b) for b in bonuses],gaps=[dict(start='2025-01-01',end='2025-11-30',reason='not_employed',evidence_ref=self.f.original)])

    def forecast(self):
        period,_,_=self.f.save();basis,_,_=self.f.save('annual_basis',self.f.basis_details(period))
        earning,_,_=self.f.save('one_off_earning',self.f.claim_details(self.terms))
        return self.f.forecast_details(basis,earning,self.terms)

    def test_known_current_tax_receipt_assigned_to_previous_social_year_cannot_be_omitted(self):
        bonus=self.january_bonus(self.december());details=self.forecast()
        # Confirmed before the fix: omission was accepted as700000 rather than
        #750000. A missing known original must now require an explicit source.
        self.f.problem(409,lambda:self.f.request('annual_tax_forecast',details))
        _,preview=self.f.request('annual_tax_forecast',details|dict(other_tax_receipt_refs=[reference(bonus)]))
        self.assertEqual(preview['plan']['annual_pay_before_minor'],750000)
        self.assertEqual(preview['plan']['additional_evidenced_tax_receipts_minor'],50000)

    def test_actual_bonus_uses_2025_social_caps_but_2026_tax_year(self):
        period=self.december();bonus=self.january_bonus(period)
        basis,_,_=self.f.save('annual_basis',self.prior_basis(period,[bonus]))
        room=basis['plan']['section_rooms']['regular']
        #2025 monthly KV5512.50/RV8050.00 less1000 running and500 bonus.
        self.assertEqual((room['health']['sv_days'],room['health']['room_minor']),(30,401250))
        self.assertEqual(room['pension']['room_minor'],655000)
        self.assertEqual(bonus['plan']['tax_year'],2026)
        self.assertEqual(bonus['plan']['social_year'],2025)
        self.assertEqual(basis['plan']['running_taxable_minor'],100000)
        self.assertEqual(basis['plan']['earlier_other_taxable_minor'],0)
        self.assertTrue(annual.validate_integrity(self.f.office))

    def test_later_known_original_requires_new_basis_without_rewriting_accepted_receipt(self):
        period=self.december();basis,command,_=self.f.save('annual_basis',self.prior_basis(period))
        self.assertEqual(basis['plan']['section_rooms']['regular']['health']['room_minor'],451250)
        bonus=self.january_bonus(period)
        self.f.problem(409,lambda:self.f.annual.resolve(self.f.owner,self.f.employee['id'],reference(basis)))
        self.assertEqual(self.f.annual.save(self.f.owner,command),basis)
        body,_=self.f.request('annual_basis',self.prior_basis(period,[bonus]))
        revised=self.f.annual.save(self.f.owner,body|dict(id=basis['id'],revision=basis['revision'],correction_reason='Newly entered original January receipt explicitly included'))
        self.assertEqual(revised['plan']['section_rooms']['regular']['health']['room_minor'],401250)
        self.assertEqual(self.f.annual.save(self.f.owner,command),basis)
        self.assertTrue(annual.validate_integrity(self.f.office))

    def test_january21_running_receipt_stays_in_prior_tax_year_and_is_not_added_again(self):
        period=self.december(received='2026-01-21')
        old,_,_=self.f.save('annual_basis',self.prior_basis(period))
        self.assertEqual(old['plan']['running_taxable_minor'],100000)
        details=self.forecast();_,preview=self.f.request('annual_tax_forecast',details)
        self.assertEqual(preview['plan']['annual_pay_before_minor'],700000)
        self.f.problem(409,lambda:self.f.request('annual_tax_forecast',details|dict(other_tax_receipt_refs=[reference(period)])))


if __name__=='__main__':unittest.main()
