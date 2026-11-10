"""Pending additive actual Source5 repayments; historical paid prefixes are facts."""
from copy import deepcopy
import unittest

import business_schema
from business_payroll_facts import reference
from core import Problem
from business_personnel_workflow import _sha
from test_business_payroll import rid
from test_business_payroll_positive_corrections import PositiveCorrectionFixture
from test_business_payroll_periods import command


class ActualSource5RepaymentWorkflow(PositiveCorrectionFixture):
    def test_new_repayment_review_cannot_be_rehashed_into_the_old_positive_contract(self):
        from payroll_multiple_corrections import validate_transition_shape
        self.first();run=self.correction()
        transition=deepcopy(run['settlement_transition'])
        transition['settlement_review'].update(schema_version=2,contract='source5_actual_net_repayment_review_v1')
        transition['transition_hash']=_sha({k:v for k,v in transition.items() if k!='transition_hash'})
        with self.assertRaises(Problem):validate_transition_shape(transition)

    def repayment(self, *, capture_sources=False):
        self.initial_run,self.initial_payment=self.first()
        self.correction();prior=self.pay();self.prior_run=deepcopy(self.run)
        inputs=self.correction_input(2000000)
        with self.assertRaises(Problem):
            self.f.payroll.preview(self.f.owner,inputs)
        inputs['settlement_review'].update(schema_version=2,
            contract='source5_actual_net_repayment_review_v1')
        if capture_sources:
            from business_payroll_multiple_cases import PayrollMultipleCases
            self.repayment_sources=PayrollMultipleCases(self.f.office,clock=self.f.hr.clock).sources(
                self.f.owner,dict(employee_id=self.f.employee['id'],month='2026-10'))
        self.repayment_input=deepcopy(inputs)
        self.repayment_preview=self.f.payroll.preview(self.f.owner,inputs)
        proposal=dict(inputs,request_id=rid(),preview_hash=self.repayment_preview['preview_hash'],
            accepted_scope=self.repayment_preview['calculation']['scope'],confirmed=True,
            id=self.run['id'],revision=self.run['revision'],
            correction_reason='Explicit actual employee repayment with unchanged bonus gross')
        self.repayment_command=proposal
        self.run=self.f.payroll.finalize(self.f.owner,proposal)
        details=deepcopy(prior['details']);index=len(details['payments'])
        details.update(run_id=self.run['id'],run_revision=self.run['revision'],
            payment_source_schema_version=4,prior_payment_ref=reference(prior))
        details['payments'].append(dict(paid_on='2026-11-03',amount_minor=-3900,
            payment_reference='SYN-ACTUAL-SEPARATE-REPAYMENT-20261103'))
        details['settlement_allocations'].append(dict(payment_index=index,running_minor=0,
            one_off_allocations=[dict(event_key=self.run['settlement_transition']['event_key'],net_minor=-3900)]))
        return prior,details

    def test_explicit_repayment_version_dates_prefix_and_exact_amount_are_required(self):
        prior,details=self.repayment()
        invalid=[]
        for day in ('2026-10-30','2026-11-04','2027-01-01'):
            changed=deepcopy(details);changed['payments'][-1]['paid_on']=day;invalid.append(changed)
        for version in (1,2,3):
            invalid.append(dict(details,payment_source_schema_version=version))
        changed=deepcopy(details);changed['payments'][-1]['amount_minor']=-3899;invalid.append(changed)
        changed=deepcopy(details);changed['payments'][0]['paid_on']='2026-10-31';invalid.append(changed)
        changed=deepcopy(details);changed['settlement_allocations'][-1]['running_minor']=-3900;invalid.append(changed)
        for value in invalid:
            with self.subTest(day=value['payments'][-1]['paid_on'],version=value['payment_source_schema_version']), self.assertRaises(Problem):
                self.f.save_account(self.f.data,'payment',value)
        paid,_=self.f.save_account(self.f.data,'payment',details)
        self.assertEqual(paid['details']['payments'][:3],prior['details']['payments'])
        self.assertTrue(business_schema.validate_integrity(self.f.office))

    def test_actual_repayment_after_positive_correction_preserves_old_money_and_original_pdf(self):
        original, first_paid = self.first(cash=True)
        original_pdf = self.f.payroll.export(self.f.owner, original['id'], 'pdf')[0]
        self.correction(1000000)
        paid, _ = self.f.save_account(self.f.data, 'payment', self.payment_details())
        self.payment = paid
        addition = self.finance.body(paid)
        addition['sources'][0]['payment_indexes'] = [2]
        self.finance.import_cash(addition)
        prior = deepcopy(paid)
        inputs = self.correction_input(2000000)
        inputs['settlement_review'].update(schema_version=2,
            contract='source5_actual_net_repayment_review_v1')
        preview = self.f.payroll.preview(self.f.owner, inputs)
        proposal = command(self.f.payroll, self.f.owner, inputs) | dict(
            id=self.run['id'], revision=self.run['revision'],
            correction_reason='Corrected actual prior-employer certificate and separately evidenced employee repayment')
        run = self.f.payroll.finalize(self.f.owner, proposal)
        transition = run['settlement_transition']
        self.assertEqual(transition['schema_version'], 2)
        self.assertEqual(transition['net_delta_minor'], -3900)
        self.assertEqual(run['calculation']['gross_minor'], original['calculation']['gross_minor'])
        self.assertEqual(preview['calculation'], run['calculation'])
        details = deepcopy(prior['details'])
        details.update(run_id=run['id'], run_revision=run['revision'],
            payment_source_schema_version=4, prior_payment_ref=reference(prior))
        index = len(details['payments'])
        details['payments'].append(dict(paid_on='2026-11-03', amount_minor=-3900,
            payment_reference='SYN-ACTUAL-EMPLOYEE-REPAYMENT-20261103'))
        details['settlement_allocations'].append(dict(payment_index=index, running_minor=0,
            one_off_allocations=[dict(event_key=transition['event_key'], net_minor=-3900)]))
        current, accepted = self.f.save_account(self.f.data, 'payment', details)
        self.assertEqual(current['sources']['single_payment_plan']['schema_version'], 4)
        self.assertEqual(current['details']['payments'][:index], prior['details']['payments'])
        self.assertEqual(current['details']['settlement_allocations'][:index], prior['details']['settlement_allocations'])
        repayment = self.finance.body(current)
        repayment['sources'][0]['payment_indexes'] = [index]
        batch = self.finance.import_cash(repayment)
        movement = batch['public_source']['cash_movements'][0]
        self.assertEqual(movement['date'], '2026-11-03')
        self.assertEqual(movement['amount'], '39.00')
        self.assertEqual(movement['direction'], 'in')
        self.assertEqual(self.f.account_api().save(self.f.owner, accepted), current)
        self.assertEqual(self.f.payroll.export(self.f.owner, original['id'], 'pdf', revision=str(original['revision']))[0], original_pdf)
        self.assertEqual(first_paid['details']['payments'], prior['details']['payments'][:2])
        self.assertTrue(business_schema.validate_integrity(self.f.office))


if __name__ == '__main__':
    unittest.main()
