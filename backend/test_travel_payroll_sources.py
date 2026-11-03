"""One immutable owner for tax-free travel cash and taxable payroll components."""
import unittest
from business_travel_allowances import _ref,validate_integrity
from travel_allowance_cash import record_payment
from travel_payroll_sources import travel_payroll_source
from test_business_planning import BusinessFixture,rid
import test_business_travel_allowances as fixture


class TravelPayrollSources(BusinessFixture,unittest.TestCase):
    setUp=fixture.TravelWorkflowTests.setUp
    upload=fixture.TravelWorkflowTests.upload
    save_site=fixture.TravelWorkflowTests.save_site
    trip_body=fixture.TravelWorkflowTests.trip_body
    approval=fixture.TravelWorkflowTests.approval
    payment=fixture.TravelWorkflowTests.payment

    def submitted(self,**changes):
        value=self.api.save_trip(self.technician,self.trip_body(**changes))['result']
        return self.api.trip_action(self.technician,value['id'],'submit',dict(request_id=rid(),employee_id=self.employee['id'],revision=value['revision'],source_hash=self.api._basis(self.employee['id']),confirmed=True))['result']

    def test_flat_taxed_cash_belongs_only_to_payroll_and_requires_an_explicit_month(self):
        trip=self.submitted(requested_meal_minor=1800,tax_choice='flat_25')
        missing=self.approval(trip,requested_meal_minor=1800,tax_choice='flat_25')
        self.problem(409,lambda:self.api.approve(self.owner,missing))
        command=self.approval(trip,requested_meal_minor=1800,tax_choice='flat_25',payroll_month='2026-10')
        value=self.api.approve(self.owner,command)['result'];source=travel_payroll_source(self.office,self.owner,_ref(value),'2026-10')
        self.assertEqual((source['tax_free_external_minor'],source['flat_taxable_payroll_minor'],source['individual_taxable_payroll_minor'],source['benefit_in_kind_non_cash_minor']),(1400,400,0,0))
        self.assertTrue(value['calculation']['can_approve']);self.assertFalse(value['calculation']['can_pay'])
        self.problem(409,lambda:record_payment(self.api,self.owner,self.payment(value,1400)))
        self.assertTrue(validate_integrity(self.office))

    def test_letter_m_only_is_frozen_in_actual_meal_month_and_never_adds_payroll_cash(self):
        meal=dict(id=rid(),date='2026-10-26',kind='breakfast',provider='employer_arranged',offered=True,is_meal=True,price_minor=1500,employee_paid_minor=0,replacement_for=None,source_file_ids=[self.file['id']])
        trip=self.submitted(meals=[meal],requested_meal_minor=840)
        value=self.api.approve(self.owner,self.approval(trip,requested_meal_minor=840))['result']
        source=travel_payroll_source(self.office,self.owner,_ref(value),'2026-10')
        self.assertTrue(source['letter_m']);self.assertEqual(source['allocations'],[])
        self.assertEqual(source['tax_free_external_minor'],840)
        self.problem(409,lambda:travel_payroll_source(self.office,self.owner,_ref(value),'2026-11'))
        self.assertTrue(validate_integrity(self.office))
