"""Separate actual transfer dates, exact private allocation, retained paid v5."""
from copy import deepcopy
import unittest

import business_schema
from business_payroll_facts import reference
from core import Problem,canonical
from payroll_multiple_oneoff_2026 import calculate_multiple_source,MULTIPLE_RULE_VERSION
from payroll_multiple_payments import build_single_payment_plan
import test_business_payroll_accounts as accounts_fixture
import test_business_payroll_periods as running_fixture
import test_payroll_multiple_oneoff_2026 as source_fixture


class SingleBonusPaymentAllocation(unittest.TestCase):
    def setUp(self):
        self.c=source_fixture.CanonicalMultipleComposition('runTest');self.c.setUp();self.addCleanup(self.c.doCleanups)
        self.f=self.c.f;self.source,_=self.c.source()
        self.calc=calculate_multiple_source(self.source,rule_version=MULTIPLE_RULE_VERSION,source_contract_version=1)
        self.event=self.calc['multiple_one_off_details']['receipt_events'][0]
        running=self.calc['running_calculation'];self.running_due=running['net_minor']-running['net_deductions_minor']
        self.bonus_due=self.calc['net_minor']-self.calc['net_deductions_minor']-self.running_due

    def split(self,running_date='2026-10-30'):
        payments=[dict(paid_on=running_date,amount_minor=self.running_due,payment_reference='SYN-ACTUAL-RUNNING-TRANSFER'),
            dict(paid_on='2026-10-31',amount_minor=self.bonus_due,payment_reference='SYN-ACTUAL-BONUS-TRANSFER')]
        allocations=[dict(payment_index=0,running_minor=self.running_due,one_off_allocations=[]),
            dict(payment_index=1,running_minor=0,one_off_allocations=[dict(event_key=self.event['event_key'],net_minor=self.bonus_due)])]
        return payments,allocations

    def plan(self,payments,allocations,**changes):
        return build_single_payment_plan(self.source,payments=payments,allocations=allocations,as_of='2026-11-03',**changes)

    def prior(self,running_date='2026-10-30'):
        f=self.f;inputs=dict(source_schema_version=3,employee_id=f.employee['id'],
            calculation_case_ref=reference(self.source['running_calculation_case']))
        run=f.payroll.finalize(f.owner,running_fixture.command(f.payroll,f.owner,inputs))
        parts=self.split(running_date)[0][:1]
        details=accounts_fixture.PayrollAccountTests.payment_details(f,run,f.identity,payments=parts)
        payment,_=f.save_account(f.data,'payment',details)
        return dict(run=run,payment=payment)

    def test_actual_paid_running_v5_on_30th_and_bonus_on_31st_remain_separate(self):
        prior=self.prior();payments,allocations=self.split();before=canonical(dict(source=self.source,prior=prior,payments=payments,allocations=allocations))
        tables=('business_payroll_events','business_payroll_account_events','business_payroll_cash_batches')
        counts={table:self.f.office.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in tables}
        result=self.plan(payments,allocations,prior_settlement=prior)
        self.assertEqual(result['one_off_net_minor'],39125)
        self.assertEqual(result['preserved_prior_payment_indexes'],[0]);self.assertEqual(result['new_payment_indexes'],[1])
        self.assertEqual(result['payments'][0],prior['payment']['details']['payments'][0])
        self.assertEqual(result['payments'][0]['paid_on'],'2026-10-30');self.assertEqual(result['payments'][1]['paid_on'],'2026-10-31')
        self.assertEqual(counts,{table:self.f.office.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in tables})
        self.assertEqual(canonical(dict(source=self.source,prior=prior,payments=payments,allocations=allocations)),before)
        self.assertTrue(business_schema.validate_integrity(self.f.office))

    def test_one_combined_transfer_is_one_money_part_with_two_exact_private_allocations(self):
        total=self.running_due+self.bonus_due
        payments=[dict(paid_on='2026-10-31',amount_minor=total,payment_reference='SYN-ONE-COMBINED-TRANSFER')]
        allocations=[dict(payment_index=0,running_minor=self.running_due,
            one_off_allocations=[dict(event_key=self.event['event_key'],net_minor=self.bonus_due)])]
        result=self.plan(payments,allocations)
        self.assertEqual(result['total_net_minor'],total);self.assertEqual(len(result['payments']),1)
        self.assertEqual(result['new_payment_indexes'],[0])
        self.assertFalse(result['cash_import_created']);self.assertFalse(result['actual_payment_created'])

    def test_wrong_bonus_date_missing_net_cent_and_future_part_are_rejected(self):
        for change in ('bonus_date','missing_cent','future'):
            payments,allocations=self.split()
            if change=='bonus_date':payments[1]['paid_on']='2026-10-30'
            elif change=='future':payments[0]['paid_on']='2026-11-04'
            else:allocations[1]['one_off_allocations'][0]['net_minor']-=1
            with self.subTest(change=change),self.assertRaises(Problem):self.plan(payments,allocations)

    def test_original_v5_paid_part_cannot_be_shifted_combined_or_relabelled(self):
        prior=self.prior(running_date='2026-10-31')
        for change in ('date','combined','target'):
            payments,allocations=self.split(running_date='2026-10-31')
            if change=='date':payments[0]['paid_on']='2026-10-30'
            elif change=='combined':
                payments=[dict(payments[0],amount_minor=self.running_due+self.bonus_due)]
                allocations=[dict(payment_index=0,running_minor=self.running_due,
                    one_off_allocations=[dict(event_key=self.event['event_key'],net_minor=self.bonus_due)])]
            else:
                allocations[0].update(running_minor=self.running_due-self.bonus_due,
                    one_off_allocations=[dict(event_key=self.event['event_key'],net_minor=self.bonus_due)])
                allocations[1].update(running_minor=self.bonus_due,one_off_allocations=[])
            with self.subTest(change=change),self.assertRaises(Problem):self.plan(payments,allocations,prior_settlement=prior)

    def test_exact_transfer_identity_cannot_be_duplicated_for_two_cash_parts(self):
        payments,allocations=self.split()
        payments=[dict(payments[0],amount_minor=1000),dict(payments[0],amount_minor=self.running_due-1000),payments[1]]
        allocations=[dict(payment_index=0,running_minor=1000,one_off_allocations=[]),
            dict(payment_index=1,running_minor=self.running_due-1000,one_off_allocations=[]),dict(allocations[1],payment_index=2)]
        with self.assertRaises(Problem):self.plan(payments,allocations)

    def test_invented_prior_running_calculation_cannot_authorize_transfer_reuse(self):
        prior=self.prior();payments,allocations=self.split();prior=deepcopy(prior)
        prior['run']['calculation']['net_minor']+=1;prior['payment']['sources']['run']=deepcopy(prior['run'])
        with self.assertRaises(Problem):self.plan(payments,allocations,prior_settlement=prior)

    def test_unresolved_multiple_or_partial_gross_never_becomes_a_payment_plan(self):
        payments,allocations=self.split();self.source['components'][0]['planned_receipts'][0]['gross_minor']-=1
        with self.assertRaises(Problem):self.plan(payments,allocations)
        self.source['components'][0]['planned_receipts'][0]['gross_minor']+=1
        self.c.additional(self.source,amount=10000)
        with self.assertRaises(Problem):self.plan(payments,allocations)


if __name__=='__main__':unittest.main()
