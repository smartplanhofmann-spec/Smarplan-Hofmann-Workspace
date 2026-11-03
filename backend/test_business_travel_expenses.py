"""Real old-expense/new-travel source ownership, without invented money flows."""
import unittest
from unittest.mock import patch
from business_travel_allowances import _ref,validate_integrity
from business_personnel_workflow import _sha
from travel_allowance_cash import record_payment,public_source
from test_business_planning import BusinessFixture,rid
import test_business_travel_allowances as fixtures


class TravelExpenseTests(BusinessFixture,unittest.TestCase):
    setUp=fixtures.TravelWorkflowTests.setUp
    upload=fixtures.TravelWorkflowTests.upload
    save_site=fixtures.TravelWorkflowTests.save_site
    trip_body=fixtures.TravelWorkflowTests.trip_body
    approval=fixtures.TravelWorkflowTests.approval
    payment=fixtures.TravelWorkflowTests.payment
    submitted=fixtures.TravelWorkflowTests.submitted

    def expense(self,paid=False):
        original=self.upload(purpose='expense_receipt',visible=True,actor=self.technician,marker=rid().encode())
        expense=self.hr.save_expense(self.technician,dict(request_id=rid(),employee_id=self.employee['id'],revision=0,purpose='Actual train ticket',
            start_date='2026-10-26',end_date='2026-10-26',items=[dict(date='2026-10-26',description='Train ticket',amount_minor=2000,currency='EUR',receipt_file_id=original['id'],project_id=self.project)]))
        expense=self.hr.expense_action(self.technician,expense['id'],'submit',dict(request_id=rid(),revision=expense['revision']))
        expense=self.hr.expense_action(self.owner,expense['id'],'approve',dict(request_id=rid(),revision=expense['revision'],reason='Verified original train ticket'))
        if paid:expense=self.hr.expense_action(self.owner,expense['id'],'reimburse',dict(request_id=rid(),revision=expense['revision'],payment_reference='Historical actual reimbursement '+rid(),paid_on='2026-10-27',amount_minor=2000,confirmed=True))
        return expense,original

    def settle(self,expense,original,business=2000,private=0):
        allocation=dict(expense_ref=_ref(expense),receipt_file_id=original['id'],kind='transport',business_minor=business,private_minor=private,provided_minor=0,review_note='Reviewed actual business ticket and explicit private part')
        draft=self.api.save_trip(self.technician,self.trip_body(expense_refs=[_ref(expense)],expense_allocations=[allocation]))['result']
        trip=self.api.trip_action(self.technician,draft['id'],'submit',dict(request_id=rid(),employee_id=self.employee['id'],revision=draft['revision'],source_hash=self.api._basis(self.employee['id']),confirmed=True))['result']
        return self.api.approve(self.owner,self.approval(trip))['result']

    def test_unpaid_actual_expense_and_allowance_share_one_source_reserved_against_old_payment(self):
        expense,original=self.expense();settlement=self.settle(expense,original,1500,500)
        self.assertEqual(settlement['calculation']['totals']['tax_free_minor'],2900)
        self.assertEqual(settlement['calculation']['totals']['expense_allowance_minor'],1500)
        self.problem(409,lambda:self.hr.expense_action(self.owner,expense['id'],'reimburse',dict(request_id=rid(),revision=expense['revision'],payment_reference='No double payout',paid_on='2026-10-27',amount_minor=2000,confirmed=True)))
        paid=record_payment(self.api,self.owner,self.payment(settlement,2900))['result']
        self.assertEqual(public_source(self.office,paid['id'])['cash_movements'][0]['amount'],'29.00')
        self.assertTrue(validate_integrity(self.office))

    def test_existing_actual_expense_reimbursement_is_bound_and_not_paid_again(self):
        expense,original=self.expense(paid=True);settlement=self.settle(expense,original)
        totals=settlement['calculation']['totals'];self.assertEqual((totals['tax_free_minor'],totals['already_paid_minor'],totals['remaining_minor']),(3400,2000,1400))
        self.problem(409,lambda:record_payment(self.api,self.owner,self.payment(settlement,1401)))
        record_payment(self.api,self.owner,self.payment(settlement,1400))
        self.assertTrue(validate_integrity(self.office))
        self.hr.expense_action(self.owner,expense['id'],'reverse-reimbursement',dict(request_id=rid(),revision=expense['revision'],payment_reference='Actual refund '+rid(),paid_on='2026-10-28',amount_minor=2000,confirmed=True))
        self.problem(409,lambda:record_payment(self.api,self.owner,self.payment(settlement,1)))

    def test_unclassified_or_duplicate_original_cannot_be_approved(self):
        expense,original=self.expense()
        draft=self.api.save_trip(self.technician,self.trip_body(expense_refs=[_ref(expense)]))['result']
        trip=self.api.trip_action(self.technician,draft['id'],'submit',dict(request_id=rid(),employee_id=self.employee['id'],revision=draft['revision'],source_hash=self.api._basis(self.employee['id']),confirmed=True))['result']
        self.problem(409,lambda:self.api.approve(self.owner,self.approval(trip)))

    def test_frozen_v1_original_survives_new_v2_rules_and_later_payment(self):
        from payroll_travel_2026_v1 import calculate as original
        def old(*args,**kwargs):kwargs.pop('rule_version',None);return original(*args,**kwargs)
        with patch('business_travel_allowances.calculate',side_effect=old):
            trip=self.submitted();command=self.approval(trip);accepted=self.api.approve(self.owner,command)
        self.assertEqual(accepted['result']['calculation']['rule_version'],'de_travel_2026_v1')
        record_payment(self.api,self.owner,self.payment(accepted['result']))
        self.assertEqual(self.api.status(self.owner,command['request_id']),accepted)
        self.assertTrue(validate_integrity(self.office))

    def adoption(self,expense,settlement,index=0):
        payment=expense['payments'][index]
        return self.payment(settlement,payment['amount_minor'],action='adopt_legacy',kind=payment['kind'],paid_on=payment['paid_on'],reference=payment['reference'],
            legacy_payment=dict(expense_ref=_ref(expense),payment_index=index,payment_hash=_sha(payment)))

    def test_explicit_legacy_adoption_adds_finance_proof_without_another_disbursement(self):
        expense,original=self.expense(paid=True);settlement=self.settle(expense,original)
        body=self.adoption(expense,settlement);adopted=record_payment(self.api,self.owner,body)
        self.assertEqual(record_payment(self.api,self.owner,body),adopted)
        self.assertEqual(public_source(self.office,adopted['target_id'])['cash_movements'][0]['amount'],'20.00')
        record_payment(self.api,self.owner,self.payment(settlement,1400))
        self.problem(409,lambda:record_payment(self.api,self.owner,self.payment(settlement,1)))
        self.problem(409,lambda:record_payment(self.api,self.owner,self.adoption(expense,settlement)))
        self.assertEqual(self.hr._latest(expense['id'],'expense'),expense)
        self.assertTrue(validate_integrity(self.office))

    def test_legacy_documentary_void_preserves_original_payment_and_prevents_second_identity(self):
        expense,original=self.expense(paid=True);settlement=self.settle(expense,original)
        body=self.adoption(expense,settlement);first=record_payment(self.api,self.owner,body)
        historical=public_source(self.office,first['target_id'],1)
        void=body|dict(request_id=rid(),revision=1,action='void',correction_reason='Wrong documentary financial attribution; original expense remains actually reimbursed',source_hash=self.api._basis(self.employee['id']))
        record_payment(self.api,self.owner,void)
        self.assertEqual(public_source(self.office,first['target_id'])['cash_movements'],[])
        self.assertEqual(public_source(self.office,first['target_id'],1),historical)
        self.assertEqual(self.hr._latest(expense['id'],'expense'),expense)
        self.problem(409,lambda:record_payment(self.api,self.owner,self.adoption(expense,settlement)))
        self.assertTrue(validate_integrity(self.office))

    def test_legacy_amount_date_and_source_digest_cannot_be_invented(self):
        expense,original=self.expense(paid=True);settlement=self.settle(expense,original)
        for change in (dict(amount_minor=1999),dict(paid_on='2026-10-28'),dict(reference='Different payment'),dict(kind='repayment')):
            self.problem(409,lambda:record_payment(self.api,self.owner,self.adoption(expense,settlement)|change))
        body=self.adoption(expense,settlement);body['legacy_payment']['payment_hash']='0'*64
        self.problem(409,lambda:record_payment(self.api,self.owner,body))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_travel_payments').fetchone()[0],0)
