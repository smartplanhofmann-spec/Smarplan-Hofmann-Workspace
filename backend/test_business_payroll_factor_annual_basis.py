"""Actual factor/P4 originals need an explicit V2 annual source contract."""
from copy import deepcopy
import unittest

from core import Problem
from business_payroll_facts import reference
from business_payroll_annual_basis import PayrollAnnualBasis,validate_annual_sources
from business_payroll_factor_annual_basis import FactorAnnualBasis
from payroll_factor_annual_basis_2026 import RULE_VERSION
from test_business_payroll import rid
import test_business_payroll_factor_entitlements as original
import test_business_payroll_annual_basis as annual_fixture


class FactorAnnualTests(unittest.TestCase):
    def setUp(self):
        self.fixture=original.FactorEntitlementFixture('runTest');self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.fixture.unpaid();self.f=self.fixture.f;body=self.fixture.proposal()
        preview=self.fixture.api.preview(self.f.owner,body)
        self.case=self.fixture.api.save(self.f.owner,dict(body,request_id=rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash']))
        self.api=FactorAnnualBasis(self.f.office,clock=lambda:self.f.now)
        self.details=dict(employer_identity_ref=reference(self.f.identity),verification_note='Actual original factor/P4 planned current month with explicit V2 contract',
            year=2026,coverage_to='2026-10-31',as_of_date='2026-10-31',payroll_run_refs=[],payroll_payment_refs=[],
            imported_period_refs=[],imported_one_off_refs=[],current_calculation_case_ref=reference(self.case),
            gaps=[dict(start='2026-01-01',end='2026-09-30',reason='not_employed',evidence_ref=self.fixture.original)],completeness_confirmed=True)

    def proposal(self):
        return dict(employee_id=self.f.employee['id'],employee_revision=self.f.employee['revision'],kind='annual_basis',details=deepcopy(self.details),source_file_ids=[self.fixture.original['id']])

    def save(self):
        proposal=self.proposal();preview=self.api.preview(self.f.owner,proposal)
        body=dict(proposal,request_id=rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
        return self.api.save(self.f.owner,body),body,preview

    def test_actual_v2_saved_plan_binds_original_case_and_leaves_v1_guard_unchanged(self):
        old=PayrollAnnualBasis(self.f.office,clock=lambda:self.f.now)
        with self.assertRaises(Problem) as caught:old.preview(self.f.owner,self.proposal())
        self.assertEqual(caught.exception.status,409)
        saved,body,preview=self.save()
        self.assertEqual(saved['plan']['rule_version'],RULE_VERSION)
        self.assertEqual(saved['sources']['current_calculation_case'],self.case)
        self.assertEqual(saved['sources']['current_calculation_case']['sources']['profiles'][0]['profile']['tax_factor'],'0.753')
        self.assertEqual(saved['plan']['running_taxable_minor'],self.case['plan']['gross_minor'])
        self.assertTrue(validate_annual_sources(self.f.office,saved))
        self.assertEqual(self.api.save(self.f.owner,body),saved)
        self.assertEqual(old.get(self.f.owner,saved['id']),saved)
        with self.assertRaises(Problem) as caught:old.save(self.f.owner,body)
        self.assertEqual(caught.exception.status,409)

    def test_current_case_revision_change_blocks_new_use_and_preserves_original_receipt(self):
        saved,body,_=self.save();proposal=self.fixture.proposal()
        proposal['details']['verification_note']='Actual source review corrected'
        preview=self.fixture.api.preview(self.f.owner,proposal)
        self.fixture.api.save(self.f.owner,dict(proposal,id=self.case['id'],request_id=rid(),revision=1,status='active',confirmed=True,preview_hash=preview['preview_hash'],correction_reason='Changed actual source review'))
        with self.assertRaises(Problem) as caught:self.api._reference(self.f.employee['id'],reference(saved),'annual_basis',fresh=True)
        self.assertEqual(caught.exception.status,409)
        self.assertEqual(self.api.save(self.f.owner,body),saved)
        self.assertTrue(validate_annual_sources(self.f.office,saved))

    def earning(self):
        self.f.original=self.fixture.original
        old=PayrollAnnualBasis(self.f.office,clock=lambda:self.f.now)
        details=annual_fixture.PayrollAnnualBasisTests.claim_details(self.f,self.fixture.terms,'Actual factor bonus original')
        proposal=dict(self.proposal(),kind='one_off_earning',details=details)
        preview=old.preview(self.f.owner,proposal)
        body=dict(proposal,request_id=rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
        return old.save(self.f.owner,body),body,old

    def composition_source(self,*,previous_running_minor=12000000):
        basis,_,_=self.save();earning,_,_=self.earning()
        details=annual_fixture.PayrollAnnualBasisTests.forecast_details(self.f,basis,earning,self.fixture.terms)
        if previous_running_minor:
            details.update(previous_employers=[dict(employer_name='Actual synthetic previous employer',employer_tax_number='111/222/33333',
                start='2026-01-01',end='2026-09-30',running_taxable_minor=previous_running_minor,other_paid_minor=0,evidence_ref=self.fixture.original)],no_previous_employer_ref=None)
        proposal=dict(self.proposal(),kind='annual_tax_forecast',details=details)
        preview=self.api.preview(self.f.owner,proposal)
        forecast=self.api.save(self.f.owner,dict(proposal,request_id=rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash']))
        return dict(schema_version=1,source_contract_version=2,rule_version='de_2026_factor_claims_oneoff_v15',
            employee_id=self.f.employee['id'],month='2026-10',running_calculation_case=self.case,
            one_off_earning=earning,current_annual_basis=basis,previous_annual_basis=None,annual_tax_forecast=forecast)

    def test_actual_forecast_binds_v2_basis_future_contracts_and_original_factor_identity(self):
        basis,_,_=self.save();earning,_,old=self.earning()
        details=annual_fixture.PayrollAnnualBasisTests.forecast_details(self.f,basis,earning,self.fixture.terms)
        proposal=dict(self.proposal(),kind='annual_tax_forecast',details=details)
        with self.assertRaises(Problem) as caught:old.preview(self.f.owner,proposal)
        self.assertEqual(caught.exception.status,409)
        preview=self.api.preview(self.f.owner,proposal)
        body=dict(proposal,request_id=rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
        saved=self.api.save(self.f.owner,body)
        self.assertEqual(saved['plan']['annual_pay_before_minor'],self.case['plan']['gross_minor']+1000000)
        self.assertEqual(saved['plan']['one_off_minor'],50000)
        self.assertEqual(saved['plan']['factor_profile_ref'],reference(self.case['sources']['profiles'][0]))
        self.assertEqual(saved['sources']['annual_basis'],basis)
        self.assertTrue(validate_annual_sources(self.f.office,saved))

    def test_same_original_command_cannot_replay_across_v1_and_v2_route_contracts(self):
        earning,body,old=self.earning()
        self.assertEqual(old.save(self.f.owner,body),earning)
        with self.assertRaises(Problem) as caught:self.api.save(self.f.owner,body)
        self.assertEqual(caught.exception.status,409)


if __name__=='__main__':unittest.main()
