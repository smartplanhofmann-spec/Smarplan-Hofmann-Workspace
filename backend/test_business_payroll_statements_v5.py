"""Actual verified source3 run exposes a narrow versioned own statement."""
import copy
import unittest
from unittest.mock import patch

from core import Problem
from business_payroll_facts import reference
from business_payroll_statements import PayrollStatements,project,render_pdf
import test_business_payroll_calculations as calculation_fixture


class CompositeStatementTests(unittest.TestCase):
    def setUp(self):
        self.fixture=calculation_fixture.CalculationPayrollWorkflow('runTest');self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        c=self.fixture;_,settlement=c.travel();policy,_=c.policy(employer_bears_tax=False);f=c.f
        details=c.details();details['travel_settlement_refs']=[reference(settlement)]
        details['flat_tax_decision']=dict(policy_ref=reference(policy),church_membership_evidence=None,
            employee_deduction_file_ref=dict(id=f.data['file']['id'],revision=1,content_hash=f.data['file']['content_hash']),
            tax_certificate_file_ref=None,tax_certificate_issued_on=None,record_on_finalize=True)
        body,_=c.request(details);fact=c.api.save(f.owner,body);self.run=f.payroll.finalize(f.owner,c.command(fact));self.api=PayrollStatements(f.office)

    def test_actual_own_amounts_net_deductions_and_pdf_have_no_source_projection(self):
        f=self.fixture.f;statement=self.api.get(f.technician,self.run['id'])['statement']
        self.assertEqual(statement['schema_version'],2)
        self.assertEqual(statement['calculation']['net_deductions_minor'],109)
        self.assertEqual(statement['calculation']['payout_minor'],172977)
        self.assertEqual(statement['travel_summary']['tax_free_external_minor'],1400)
        self.assertEqual(statement['travel_summary']['employee_flat_tax_deduction_minor'],109)
        self.assertEqual(set(statement['earnings_summary'][0]),{'kind','dates','gross_minor'})
        def narrow(value):
            if isinstance(value,dict):
                self.assertFalse(set(value)&{'sources','source','profile','profiles','policy','source_refs','source_files','source_file_ids','identity_ref','reason','verification_note','accepted_command','created_by'})
                for v in value.values():narrow(v)
            elif isinstance(value,list):
                for v in value:narrow(v)
        narrow(statement)
        pdf=self.api.export(f.technician,self.run['id'],dict(revision='1',statement_hash=statement['statement_hash']))[0]
        self.assertEqual(pdf,render_pdf(statement));self.assertNotIn(f.data['file']['id'].encode(),pdf)
        self.assertEqual(self.api.records(f.technician)['items'],[statement])

    def test_actual_recording_verifier_is_mandatory_on_list_detail_history_and_pdf(self):
        f=self.fixture.f;statement=self.api.get(f.technician,self.run['id'])['statement']
        with patch.object(self.api.payroll,'_verify_calculation_record',side_effect=Problem(500,'Synthetic corrupt actual tax recording')) as check:
            for read in (lambda:self.api.records(f.technician),lambda:self.api.get(f.technician,self.run['id']),
                lambda:self.api.get(f.technician,self.run['id'],history=True),
                lambda:self.api.export(f.technician,self.run['id'],dict(revision='1',statement_hash=statement['statement_hash']))):
                with self.assertRaises(Problem):read()
            self.assertEqual(check.call_count,4)

    def test_positive_projection_ignores_private_additions_at_every_new_layer(self):
        value=copy.deepcopy(self.run);original=project(value)
        value['calculation']['period_details']['travel']['private_reason']='private'
        value['calculation']['period_details']['earnings'][0]['private_reason']='private'
        value['source']['diagnosis']='private'
        self.assertEqual(project(value),original)


if __name__=='__main__':unittest.main()
