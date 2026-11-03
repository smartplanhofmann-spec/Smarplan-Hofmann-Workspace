"""Real private P2 sources, immutable v5 cases and policy acceptance receipts."""
from copy import deepcopy
import json
import sqlite3
import unittest
from unittest.mock import patch

import business_schema
import business_payroll_calculation_cases as cases
from business_payroll_facts import reference
from business_personnel_workflow import _sha
from core import canonical
from test_business_payroll import rid
import test_business_payroll_facts as fixture


class CalculationCaseTests(unittest.TestCase):
    def setUp(self):
        names=business_schema.MODULE_NAMES
        for name in ('business_payroll_entitlements','business_payroll_calculation_cases'):
            if name not in names:names+=(name,)
        registry=patch.object(business_schema,'MODULE_NAMES',names);registry.start();self.addCleanup(registry.stop)
        self.f=fixture.PayrollFactTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.api=cases.PayrollCalculationCases(self.f.office,clock=lambda:self.f.now)
        self.base,_,_=self.f.period()

    def details(self):
        return dict(month='2026-10',period_case_ref=reference(self.base),employment_terms_refs=[reference(self.base['sources']['employment_terms'])],
            profile_refs=[reference(self.f.data['profile'])],identity_refs=[reference(self.f.identity)],segment_events=[],thirty_day_rule=None,
            entitlement_case_refs=[],travel_settlement_refs=[],flat_tax_decision=None,verification_note='Actual synthetic sources inspected')

    def request(self,details=None):
        f=self.f
        data=dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],kind='calculation_case',
            rule_version=cases.CALCULATION_RULE_VERSION,source_contract_version=1,details=details or self.details(),source_file_ids=[f.data['file']['id']])
        preview=self.api.preview(f.owner,data)
        return dict(data,request_id=rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash']),preview

    def policy(self,*,method='simplified',**changes):
        data=dict(employee_id=None,employee_revision=None,kind='travel_tax_policy',rule_version=cases.POLICY_RULE_VERSION,
            source_contract_version=1,source_file_ids=[self.f.data['file']['id']],details=dict(filing_period_from='2026-10-01',filing_period_to='2026-12-31',
            federal_state='BW',church_method=method,church_rate_region='standard',church_method_applies_to_all=True,
            employer_bears_tax=True,verification_note='Actual synthetic employer policy')|changes)
        preview=self.api.preview(self.f.owner,data)
        body=dict(data,request_id=rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
        return self.api.save(self.f.owner,body),body

    def test_exact_actual_sources_and_original_command_survive_void_and_pause(self):
        body,preview=self.request();saved=self.api.save(self.f.owner,body)
        self.assertEqual(saved['plan']['gross_minor'],33068);self.assertTrue(saved['plan']['can_calculate'])
        self.assertNotIn('accepted_command',saved)
        self.assertEqual(json.loads(self.api._row(saved['id'],saved['revision'])['payload_json'])['accepted_command'],body)
        self.assertEqual(saved['sources']['period_case'],self.base)
        self.assertEqual(self.api.resolve_calculation_case(self.f.owner,self.f.employee['id'],reference(saved)),saved)
        self.assertEqual(self.api.save(self.f.owner,body),saved)
        archived=self.api.save(self.f.owner,body|dict(request_id=rid(),id=saved['id'],revision=1,status='void',correction_reason='Actual synthetic withdrawal'))
        self.assertEqual(archived['sources'],saved['sources']);self.assertEqual(archived['plan'],saved['plan'])
        self.f.pause();self.assertEqual(self.api.save(self.f.owner,body),saved)
        self.f.problem(423,lambda:self.api.save(self.f.owner,body|dict(request_id=rid())))
        self.assertTrue(cases.validate_integrity(self.f.office));self.assertTrue(business_schema.validate_integrity(self.f.office))
        self.assertEqual(self.api.get(self.f.owner,saved['id'],True)['items'],[saved,archived])

    def test_private_self_access_and_missing_source_hash_fail_before_computation(self):
        body,_=self.request();saved=self.api.save(self.f.owner,body)
        self.f.problem(403,lambda:self.api.get(self.f.technician,saved['id']))
        self.f.problem(403,lambda:self.api.resolve_calculation_case(self.f.technician,self.f.employee['id'],reference(saved)))
        wrong=self.details();wrong['period_case_ref']['content_hash']='0'*64
        self.f.problem(409,lambda:self.request(wrong))
        wrong=self.details();wrong['gross_minor']=1
        self.f.problem(400,lambda:self.request(wrong))

    def test_current_source_revision_drift_blocks_new_use_preserves_historical_case(self):
        body,_=self.request();saved=self.api.save(self.f.owner,body);term=self.base['sources']['employment_terms']
        self.f.api.save(self.f.owner,self.f.body('employment_terms',term['details']|dict(proration_method='contractual_30_days'),
            id=term['id'],revision=term['revision'],correction_reason='Actual contract method changed'))
        self.f.problem(409,lambda:self.api.resolve_calculation_case(self.f.owner,self.f.employee['id'],reference(saved)))
        self.assertEqual(self.api.save(self.f.owner,body),saved)
        self.assertEqual(self.api.resolve_calculation_case(self.f.owner,self.f.employee['id'],reference(saved),fresh=False),saved)
        self.assertTrue(cases.validate_integrity(self.f.office))

    def test_policy_is_global_has_original_receipt_and_prevents_per_employee_switch(self):
        saved,body=self.policy();self.assertIsNone(saved['employee_id']);self.assertIsNone(saved['plan'])
        self.assertEqual(saved,self.api.save(self.f.owner,body))
        self.f.problem(409,lambda:self.policy(method='evidence',filing_period_from='2026-11-01',filing_period_to='2026-11-30'))
        self.f.problem(403,lambda:self.api.records(self.f.technician,{},policies=True))
        self.assertEqual(self.api.records(self.f.owner,{},policies=True)['items'],[saved])
        self.assertTrue(cases.validate_integrity(self.f.office))

    def test_changed_accepted_employee_revision_is_rejected_even_if_hashes_rebuilt(self):
        body,_=self.request();saved=self.api.save(self.f.owner,body)
        self.f.employee=self.f.call(self.f.planning,'save_employee',self.f.owner,dict(request_id=rid(),id=self.f.employee['id'],
            revision=self.f.employee['revision'],name=self.f.employee['name']))
        row=dict(self.f.office.db.execute('SELECT * FROM business_payroll_calculation_case_events WHERE id=?',(saved['id'],)).fetchone())
        payload=json.loads(row['payload_json']);payload['accepted_command']['employee_revision']=self.f.employee['revision']
        sources=json.loads(row['sources_json']);envelope={key:value for key,value in row.items() if key not in ('payload_json','sources_json','content_hash')}
        envelope.update(payload=payload,sources=sources);envelope['command_hash']=_sha(['calculation_fact.saved:calculation_case',payload['accepted_command']])
        self.f.office.db.execute('DROP TRIGGER business_payroll_calculation_case_events_update_guard')
        self.f.office.db.execute('UPDATE business_payroll_calculation_case_events SET payload_json=?,command_hash=?,content_hash=? WHERE id=?',
            (canonical(payload),envelope['command_hash'],_sha(envelope),saved['id']))
        with self.assertRaises(ValueError):cases.validate_integrity(self.f.office)

    def test_database_guards_and_nonce_content_conflict_are_real(self):
        body,_=self.request();saved=self.api.save(self.f.owner,body)
        with self.assertRaises(sqlite3.IntegrityError):self.f.office.db.execute('DELETE FROM business_payroll_calculation_case_events WHERE id=?',(saved['id'],))
        self.f.problem(409,lambda:self.api.save(self.f.owner,body|dict(confirmed=True,details=body['details']|dict(verification_note='Different accepted command'))))
        self.assertTrue(cases.validate_integrity(self.f.office))

    def test_actual_unpaid_claim_reduces_contract_without_fake_work_time(self):
        from business_payroll_entitlements import PayrollEntitlements
        from payroll_calculations_2026 import calculate_calculation_source
        f=self.f;claims=PayrollEntitlements(f.office,clock=lambda:f.now)
        original=dict(id=f.data['file']['id'],revision=1,content_hash=f.data['file']['content_hash'])
        details=dict(case_key=rid(),employment_terms_ref=reference(self.base['sources']['employment_terms']),work_schedule_refs=[],
            preparation_refs=[],agreement_refs=[reference(f.data['agreement'])],sickness_history_ref=None,
            input=dict(**{'from':'2026-10-20','to':'2026-10-24'},employment_to=None,employment_continues=True,no_wage_claim=True,
                intervening_paid_days=[],evidence_refs=[original],exceptions=[]),verification_note='Actual five unpaid days')
        request=dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],kind='unpaid_continuation',details=details,source_file_ids=[original['id']])
        preview=claims.preview(f.owner,request)
        claim=claims.save(f.owner,dict(request,request_id=rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash']))
        case_details=self.details();case_details['entitlement_case_refs']=[reference(claim)]
        before=[dict(row) for row in f.office.db.execute('SELECT * FROM business_time_days')]
        body,_=self.request(case_details);saved=self.api.save(f.owner,body)
        result=calculate_calculation_source(saved['sources'],rule_version=saved['rule_version'],source_contract_version=saved['source_contract_version'])
        self.assertTrue(result['payroll_calculation_complete'],result['blockers']);self.assertEqual(result['gross_minor'],23342)
        self.assertEqual(result['period_details']['social_periods'][0]['days'],17)
        self.assertEqual(before,[dict(row) for row in f.office.db.execute('SELECT * FROM business_time_days')])
        self.assertTrue(cases.validate_integrity(f.office))

    def actual_flat_travel(self):
        from business_travel_allowances import TravelAllowances
        import test_business_travel_allowances as travel_fixture
        f=self.f;travel=travel_fixture.TravelWorkflowTests('runTest')
        for key in ('office','employee','owner','technician','project','hr','now'):setattr(travel,key,getattr(f,key))
        travel.api=TravelAllowances(f.office,clock=lambda:f.now)
        travel.file=travel.upload(purpose='expense_receipt',visible=True,actor=f.technician)
        travel.home=travel.save_site('home');travel.place=travel.save_site('external_fixed')
        trip=travel.api.save_trip(f.technician,travel.trip_body(requested_meal_minor=1800,tax_choice='flat_25'))['result']
        trip=travel.api.trip_action(f.technician,trip['id'],'submit',dict(request_id=rid(),employee_id=f.employee['id'],revision=trip['revision'],
            source_hash=travel.api._basis(f.employee['id']),confirmed=True))['result']
        return travel.api.approve(f.owner,travel.approval(trip,requested_meal_minor=1800,tax_choice='flat_25',payroll_month='2026-10'))['result']

    def test_actual_travel_policy_has_planned_context_not_a_fictitious_tax_booking(self):
        f=self.f;settlement=self.actual_flat_travel();policy,_=self.policy();details=self.details()
        details.update(travel_settlement_refs=[reference(settlement)],flat_tax_decision=dict(policy_ref=reference(policy),
            church_membership_evidence=None,employee_deduction_file_ref=None,tax_certificate_file_ref=None,
            tax_certificate_issued_on=None,record_on_finalize=True))
        body,preview=self.request(details);saved=self.api.save(f.owner,body);flat=saved['sources']['flat_travel_tax']
        self.assertEqual(flat['recording_context'],dict(planned_recording_on='2026-11-03',actual_recorded=False))
        self.assertEqual(flat['calculation']['statutory_employer_due_minor'],109)
        self.assertEqual(flat['parameters']['evidence']['eligible_limit_minor'],400)
        self.assertEqual(flat['parameters']['evidence']['eligible_source_refs'],[reference(settlement)])
        # This source fixture is a minijob: recording a correct travel source
        # does not pretend the still-unsupported combined mini tax rule exists.
        self.assertFalse(saved['plan']['can_calculate'])
        f.now=f.now.replace(day=4)
        f.problem(409,lambda:self.api.resolve_calculation_case(f.owner,f.employee['id'],reference(saved)))
        self.assertEqual(self.api.save(f.owner,body),saved)
        self.assertEqual(self.api.resolve_calculation_case(f.owner,f.employee['id'],reference(saved),fresh=False),saved)
        self.assertTrue(cases.validate_integrity(f.office))


if __name__=='__main__':unittest.main()
