"""Repeated actual net adjustments after an evidenced repayment preserve money."""
from copy import deepcopy
import unittest

import business_schema
from business_payroll_facts import reference
from core import Problem
from test_business_payroll import rid
from test_business_payroll_positive_corrections import PositiveCorrectionFixture
import test_business_payroll_source5_repayments as repayment_fixture


class AdjustmentFixture(PositiveCorrectionFixture):
    repayment = repayment_fixture.ActualSource5RepaymentWorkflow.repayment

    def mixed_prefix(self):
        self.positive_payment, details = self.repayment()
        self.payment, self.payment_command = self.f.save_account(self.f.data, 'payment', details)
        return self.run, self.payment

    def adjust(self, amount, *, capture_sources=False):
        inputs = self.correction_input(amount)
        inputs['settlement_review'].update(schema_version=3,
            contract='source5_actual_net_adjustment_review_v1')
        if capture_sources:
            from business_payroll_multiple_cases import PayrollMultipleCases
            self.adjustment_sources = PayrollMultipleCases(self.f.office, clock=self.f.hr.clock).sources(
                self.f.owner, dict(employee_id=self.f.employee['id'], month='2026-10'))
        self.adjustment_input = deepcopy(inputs)
        self.preview = self.f.payroll.preview(self.f.owner, inputs)
        self.command = dict(inputs, request_id=rid(), preview_hash=self.preview['preview_hash'],
            accepted_scope=self.preview['calculation']['scope'], confirmed=True,
            id=self.run['id'], revision=self.run['revision'],
            correction_reason='Separately evidenced actual net adjustment after repayment')
        self.prior_run, self.prior_payment = deepcopy(self.run), deepcopy(self.payment)
        self.run = self.f.payroll.finalize(self.f.owner, self.command)
        details = deepcopy(self.payment['details'])
        details.update(run_id=self.run['id'], run_revision=self.run['revision'],
            payment_source_schema_version=5, prior_payment_ref=reference(self.payment))
        transition = self.run['settlement_transition']
        if transition['net_delta_minor']:
            index = len(details['payments'])
            details['payments'].append(dict(paid_on='2026-11-03',
                amount_minor=transition['net_delta_minor'],
                payment_reference='SYN-ACTUAL-ADJUSTMENT-'+str(self.run['revision'])))
            details['settlement_allocations'].append(dict(payment_index=index, running_minor=0,
                one_off_allocations=[dict(event_key=transition['event_key'], net_minor=transition['net_delta_minor'])]))
        self.adjustment_details = deepcopy(details)
        return details


class ActualSource5AdjustmentWorkflow(AdjustmentFixture):
    def test_repeat_positive_negative_and_zero_adjustment_keep_the_complete_signed_prefix(self):
        original, paid = self.mixed_prefix()
        original_pdf = self.f.payroll.export(self.f.owner, original['id'], 'pdf')[0]
        histories = [deepcopy(paid)]
        for amount, expected in ((1500000, 1000), (2000000, -1000), (2000000, 0)):
            details = self.adjust(amount)
            self.assertEqual(self.run['settlement_transition']['net_delta_minor'], expected)
            self.assertEqual(self.run['settlement_transition']['schema_version'], 3)
            self.assertEqual(details['payments'][:len(self.payment['details']['payments'])], self.payment['details']['payments'])
            from payroll_multiple_adjustments import build_payment_plan, validate_transition
            from business_personnel_workflow import _sha
            for change in ('prefix', 'direction', 'early', 'future', 'null_pair', 'bool'):
                value = deepcopy(details)
                if change == 'prefix': value['payments'][0]['amount_minor'] += 1
                elif change in ('early', 'future'):
                    value['payments'][-1]['paid_on'] = '2026-11-02' if change == 'early' else '2026-11-04'
                elif change in ('direction', 'bool') and expected:
                    value['payments'][-1]['amount_minor'] = -expected if change == 'direction' else True
                    value['settlement_allocations'][-1]['one_off_allocations'][0]['net_minor'] = value['payments'][-1]['amount_minor']
                else:
                    # Even a pair summing to zero invents additional cash and
                    # violates the single actually evidenced direction.
                    for extra in (1, -1):
                        index = len(value['payments'])
                        value['payments'].append(dict(paid_on='2026-11-03', amount_minor=extra,
                            payment_reference='FORBIDDEN-ZERO-PAIR-'+str(index)))
                        value['settlement_allocations'].append(dict(payment_index=index, running_minor=0,
                            one_off_allocations=[dict(event_key=self.run['settlement_transition']['event_key'], net_minor=extra)]))
                with self.subTest(delta=expected, change=change), self.assertRaises(Problem):
                    build_payment_plan(self.run, payments=value['payments'], allocations=value['settlement_allocations'],
                        as_of='2026-11-03', prior_settlement=dict(run=self.prior_run, payment=self.prior_payment))
            changed = deepcopy(self.run['settlement_transition'])
            changed['settlement_review'].update(schema_version=2, contract='source5_actual_net_repayment_review_v1')
            changed['transition_hash'] = _sha({k:v for k,v in changed.items() if k != 'transition_hash'})
            with self.assertRaises(Problem): validate_transition(changed)
            for version in (1, 2, 3, 4):
                with self.subTest(version=version), self.assertRaises(Problem):
                    self.f.account_api()._normalize(self.f.employee['id'], 'payment',
                        dict(details, payment_source_schema_version=version))
            self.payment, command = self.f.save_account(self.f.data, 'payment', details)
            plan = self.payment['sources']['single_payment_plan']
            self.assertEqual(plan['schema_version'], 5)
            self.assertEqual(plan['net_delta_minor'], expected)
            self.assertEqual(plan['new_payment_indexes'], [] if not expected else [len(details['payments'])-1])
            self.assertEqual(plan['actual_payment_created'], False)
            self.assertEqual(self.f.account_api().save(self.f.owner, command), self.payment)
            self.assertEqual(self.f.payroll.finalize(self.f.owner, self.command), self.run)
            histories.append(deepcopy(self.payment))
        self.assertEqual(histories[-1]['details']['payments'], histories[-2]['details']['payments'])
        for prior in histories:
            self.assertEqual(self.payment['details']['payments'][:len(prior['details']['payments'])], prior['details']['payments'])
        self.assertEqual(self.f.payroll.export(self.f.owner, original['id'], 'pdf', revision=str(original['revision']))[0], original_pdf)
        self.assertTrue(business_schema.validate_integrity(self.f.office))
        # A successful graph never survives into the next independent read.
        # Corrupting an actual old row must invalidate the full latest chain.
        from unittest.mock import patch
        from business_payroll import Payroll
        original = self.initial_run
        read = Payroll._row
        def corrupt(api, object_id, kind, revision=None):
            row = read(api, object_id, kind, revision)
            if object_id == original['id'] and kind == 'run' and revision == original['revision']:
                return dict(row, content_hash='0'*64)
            return row
        # SQLite correctly prohibits modifying the immutable archive. Inject
        # a corrupt original read explicitly rather than weakening its trigger.
        with patch.object(Payroll, '_row', new=corrupt):
            with self.assertRaises(Problem): self.f.payroll._verify_calculation_record(self.run)
        self.f.payroll._verify_calculation_record(self.run)

    def test_new_mixed_contract_cannot_replace_the_original_positive_or_first_repayment_contract(self):
        self.first()
        inputs = self.correction_input(1500000)
        inputs['settlement_review'].update(schema_version=3, contract='source5_actual_net_adjustment_review_v1')
        with self.assertRaises(Problem): self.f.payroll.preview(self.f.owner, inputs)


if __name__ == '__main__':
    unittest.main()
