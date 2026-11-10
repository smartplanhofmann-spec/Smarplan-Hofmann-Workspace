"""Actual V15 originals and receipts; no free annual totals reach the API."""
from copy import deepcopy
import unittest

from core import Problem
from business_payroll_facts import reference
from business_payroll_oneoff_cases import PayrollOneoffCases,validate_case_sources
from business_payroll_factor_oneoff_cases import FactorOneoffCases
from payroll_factor_oneoff_composition_2026 import RULE_VERSION
from test_business_payroll import rid
import test_business_payroll_factor_annual_basis as original


class FactorOneoffCaseTests(unittest.TestCase):
    def setUp(self):
        self.fixture=original.FactorAnnualTests('runTest');self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.f=self.fixture.f;self.source=self.fixture.composition_source();self.api=FactorOneoffCases(self.f.office,clock=lambda:self.f.now)

    def proposal(self):
        source=self.source
        return dict(employee_id=self.f.employee['id'],employee_revision=self.f.employee['revision'],kind='one_off_case',rule_version=RULE_VERSION,source_contract_version=2,source_file_ids=[self.fixture.fixture.original['id']],
            details=dict(month='2026-10',running_calculation_case_ref=reference(source['running_calculation_case']),one_off_earning_ref=reference(source['one_off_earning']),current_annual_basis_ref=reference(source['current_annual_basis']),previous_annual_basis_ref=None,annual_tax_forecast_ref=reference(source['annual_tax_forecast']),verification_note='Actual factor, P4, bonus, V2 annual basis and prior-employer certificate checked'))

    def saved(self):
        proposal=self.proposal();preview=self.api.preview(self.f.owner,proposal)
        body=dict(proposal,request_id=rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
        return self.api.save(self.f.owner,body),body,preview

    def test_actual_original_case_exact_receipt_and_old_reader_validation(self):
        saved,body,preview=self.saved()
        self.assertTrue(preview['plan']['payroll_calculation_complete']);self.assertGreater(saved['plan']['one_off_details']['tax']['STS'],0)
        self.assertEqual(saved['sources']['calculation_source'],self.source)
        self.assertEqual(self.api.save(self.f.owner,body),saved)
        self.assertEqual(PayrollOneoffCases(self.f.office).get(self.f.owner,saved['id']),saved)
        self.assertTrue(validate_case_sources(self.f.office,saved))
        self.assertEqual(PayrollOneoffCases(self.f.office).resolve_one_off_case(self.f.owner,self.f.employee['id'],reference(saved)),saved)

    def test_same_bonus_claim_does_not_create_another_case_under_a_new_nonce(self):
        saved,body,_=self.saved()
        with self.assertRaises(Problem) as caught:self.api.save(self.f.owner,dict(body,request_id=rid()))
        self.assertEqual(caught.exception.status,409)
        self.assertEqual(len(self.api.records(self.f.owner,dict(employee_id=self.f.employee['id']))['items']),1)

    def test_fresh_forecast_correction_blocks_new_use_preserves_original_replay(self):
        saved,body,_=self.saved();forecast=self.source['annual_tax_forecast'];details=deepcopy(forecast['details']);details['verification_note']='Actual prior-employer original reviewed again'
        proposal=dict(employee_id=self.f.employee['id'],employee_revision=self.f.employee['revision'],kind='annual_tax_forecast',details=details,source_file_ids=[self.fixture.fixture.original['id']])
        preview=self.fixture.api.preview(self.f.owner,proposal)
        self.fixture.api.save(self.f.owner,dict(proposal,id=forecast['id'],revision=1,request_id=rid(),status='active',confirmed=True,preview_hash=preview['preview_hash'],correction_reason='Actual original source review corrected'))
        with self.assertRaises(Problem) as caught:self.api.resolve_one_off_case(self.f.owner,self.f.employee['id'],reference(saved))
        self.assertEqual(caught.exception.status,409);self.assertEqual(self.api.save(self.f.owner,body),saved)


if __name__=='__main__':unittest.main()
