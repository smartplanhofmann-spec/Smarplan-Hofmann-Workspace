"""Actual later positive Source5 settlements preserve the original gross date."""
from copy import deepcopy
import unittest

import business_schema
from core import Problem
from test_business_payroll import rid
from test_business_payroll_positive_corrections import PositiveCorrectionFixture


class PositivePaymentDateWorkflow(PositiveCorrectionFixture):
    def later_details(self, paid_on='2026-11-02'):
        value = self.payment_details('ACTUAL-LATER-POSITIVE-TRANSFER-'+paid_on)
        value['payment_source_schema_version'] = 3
        value['payments'][-1]['paid_on'] = paid_on
        return value

    def test_later_actual_transfer_has_new_plan_and_only_its_own_cash_day(self):
        original, paid = self.first(cash=True)
        original_pdf = self.f.payroll.export(self.f.owner, original['id'], 'pdf')[0]
        self.correction()
        details = self.later_details()
        current, command = self.f.save_account(self.f.data, 'payment', details)
        plan = current['sources']['single_payment_plan']
        self.assertEqual(plan['schema_version'], 3)
        self.assertEqual(plan['contract'], 'source5_positive_net_correction_v3')
        self.assertEqual(plan['settlement_date_basis'], 'actual_positive_transfer_2026')
        self.assertEqual(plan['bonus_receipt_date'], '2026-10-31')
        self.assertEqual(plan['payments'][-1]['paid_on'], '2026-11-02')
        self.assertEqual(plan['payments'][:2], paid['details']['payments'])
        self.assertEqual(plan['allocations'][:2], paid['details']['settlement_allocations'])
        self.assertEqual(plan['new_payment_indexes'], [2])
        body = self.finance.body(current)
        body['sources'][0]['payment_indexes'] = [2]
        batch = self.finance.import_cash(body)
        self.assertEqual(len(batch['public_source']['cash_movements']), 1)
        self.assertEqual(batch['public_source']['cash_movements'][0]['date'], '2026-11-02')
        self.assertEqual(batch['public_source']['cash_movements'][0]['amount'], '39.00')
        self.assertEqual(current['sources']['run']['calculation']['multiple_one_off_details']['receipt_events'],
            original['calculation']['multiple_one_off_details']['receipt_events'])
        self.assertEqual(self.f.account_api().save(self.f.owner, command), current)
        self.assertEqual(self.f.payroll.export(self.f.owner, original['id'], 'pdf', revision=str(original['revision']))[0], original_pdf)
        self.assertTrue(business_schema.validate_integrity(self.f.office))

    def test_old_same_day_contract_and_new_date_guards_remain_distinct(self):
        self.first();self.correction()
        proposed = self.later_details()
        cases = [dict(proposed, payment_source_schema_version=2)]
        for day in ('2026-10-30', '2026-11-04', '2027-01-01'):
            changed=deepcopy(proposed);changed['payments'][-1]['paid_on']=day;cases.append(changed)
        for value in cases:
            with self.subTest(value=value['payments'][-1]['paid_on'],version=value['payment_source_schema_version']), self.assertRaises(Problem):
                self.f.save_account(self.f.data,'payment',value)
        accepted,command=self.f.save_account(self.f.data,'payment',proposed)
        self.assertEqual(self.f.account_api().save(self.f.owner,command),accepted)

    def test_two_later_corrections_preserve_the_entire_v3_prefix_and_actual_days(self):
        self.first(cash=True)
        self.correction(1500000)
        paid,old_command=self.f.save_account(self.f.data,'payment',self.later_details('2026-11-01'))
        self.payment=paid
        first=self.finance.body(paid);first['sources'][0]['payment_indexes']=[2]
        self.finance.import_cash(first)
        old=deepcopy(paid)
        self.correction(1000000)
        proposed=self.later_details('2026-11-02')
        invalid=deepcopy(proposed);invalid['payments'][-1]['paid_on']='2026-10-31'
        with self.assertRaises(Problem):self.f.save_account(self.f.data,'payment',invalid)
        downgrade=deepcopy(proposed);downgrade['payment_source_schema_version']=2
        with self.assertRaises(Problem):self.f.save_account(self.f.data,'payment',downgrade)
        current,command=self.f.save_account(self.f.data,'payment',proposed)
        self.assertEqual(current['details']['payments'][:3],old['details']['payments'])
        self.assertEqual(current['sources']['single_payment_plan']['new_payment_indexes'],[3])
        last=self.finance.body(current);last['sources'][0]['payment_indexes']=[3]
        batch=self.finance.import_cash(last)
        self.assertEqual(batch['public_source']['cash_movements'][0]['date'],'2026-11-02')
        self.assertEqual(batch['public_source']['cash_movements'][0]['amount'],'29.00')
        self.assertEqual(self.f.account_api().save(self.f.owner,old_command),old)
        self.assertTrue(business_schema.validate_integrity(self.f.office))


if __name__ == '__main__':
    unittest.main()
