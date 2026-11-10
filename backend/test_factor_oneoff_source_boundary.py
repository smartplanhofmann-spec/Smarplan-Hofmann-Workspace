"""Existing annual V1 must not silently admit a new factor monthly case."""
import json
import unittest

from core import Problem
from business_payroll_annual_basis import PayrollAnnualBasis
from business_payroll_facts import reference
from test_business_payroll import rid
import test_business_payroll_factor_entitlements as original


class FactorOneoffSourceBoundary(unittest.TestCase):
    def test_actual_factor_original_stays_outside_the_old_planned_annual_contract(self):
        fixture=original.FactorEntitlementFixture('runTest');fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.unpaid();f=fixture.f;body=fixture.proposal()
        preview=fixture.api.preview(f.owner,body)
        self.assertTrue(preview['can_calculate'])
        case=fixture.api.save(f.owner,dict(body,request_id=rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash']))
        annual=PayrollAnnualBasis(f.office,clock=lambda:f.now)
        details=dict(employer_identity_ref=reference(f.identity),verification_note='Actual factor/P4 original, explicitly not a V5 shadow projection',
            year=2026,coverage_to='2026-10-31',as_of_date='2026-10-31',payroll_run_refs=[],payroll_payment_refs=[],
            imported_period_refs=[],imported_one_off_refs=[],current_calculation_case_ref=reference(case),
            gaps=[dict(start='2026-01-01',end='2026-09-30',reason='not_employed',evidence_ref=fixture.original)],completeness_confirmed=True)
        proposal=dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],kind='annual_basis',details=details,source_file_ids=[fixture.original['id']])
        before={table:f.office.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in ('business_payroll_events','business_payroll_annual_events','business_payroll_cash_batches')}
        with self.assertRaises(Problem) as caught:annual.preview(f.owner,proposal)
        self.assertEqual(caught.exception.status,409)
        self.assertIn('eigenen Jahresvorschauvertrag',caught.exception.message)
        self.assertEqual(before,{table:f.office.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in before})
        self.assertEqual(fixture.api.get(f.owner,case['id'])['sources']['profiles'][0]['profile']['tax_factor'],'0.753')
        print(json.dumps(dict(existing_rule=case['rule_version'],actual_old_annual_rejection=caught.exception.status,message=caught.exception.message,no_annual_or_cash_mutation=True),ensure_ascii=False))


if __name__=='__main__':unittest.main()
