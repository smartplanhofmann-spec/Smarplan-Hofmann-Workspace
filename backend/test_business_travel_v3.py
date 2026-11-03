"""Isolated v3 integration with real private files and immutable stored history.

Only these tests select the new default; production remains v2 until the
separate client/review rollout has completed.
"""
import json
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from core import canonical
from business_travel_allowances import validate_integrity,_ref
from test_business_planning import BusinessFixture,rid
import test_business_travel_allowances as travel_fixture
from test_payroll_travel_mixed_2026 import session
from travel_allowance_cash import record_payment,public_source
from business_personnel_workflow import _sha


class TravelV3WorkflowTests(BusinessFixture,unittest.TestCase):
    setUp=travel_fixture.TravelWorkflowTests.setUp
    upload=travel_fixture.TravelWorkflowTests.upload
    save_site=travel_fixture.TravelWorkflowTests.save_site
    trip_body=travel_fixture.TravelWorkflowTests.trip_body
    approval=travel_fixture.TravelWorkflowTests.approval
    payment=travel_fixture.TravelWorkflowTests.payment

    def v3(self):
        context=ExitStack()
        context.enter_context(patch('payroll_travel_2026.RULE_VERSION','de_travel_2026_v3'))
        context.enter_context(patch('business_travel_allowances.RULE_VERSION','de_travel_2026_v3'))
        return context

    def mixed_body(self,proof=None):
        proof=proof or self.upload(purpose='expense_receipt',visible=True,actor=self.technician,marker=rid().encode())
        points=[session(900,'2026-10-26','08:00','12:00','business'),session(901,'2026-10-26','13:00','15:00','private')]
        for point in points:point['source_file_ids']=[proof['id']]
        d=dict(method='documented_program_ratio',program_sessions=points,program_complete=True,
            cost_allocation_reviewed=True,source_file_ids=[proof['id']],review_note='Original complete actual programme checked.')
        body=self.trip_body(mixed_assessment=d,private_intervals=[{k:points[1][k] for k in ('from','to')}],requested_meal_minor=933)
        return body,proof

    def submit_body(self,body):
        draft=self.api.save_trip(self.technician,body)['result']
        submit=dict(request_id=rid(),employee_id=self.employee['id'],revision=draft['revision'],source_hash=self.api._basis(self.employee['id']),confirmed=True)
        return self.api.trip_action(self.technician,draft['id'],'submit',submit)['result']

    @patch('payroll_travel_2026.RULE_VERSION','de_travel_2026_v2')
    @patch('business_travel_allowances.RULE_VERSION','de_travel_2026_v2')
    def test_program_originals_reconstruct_after_default_switch_with_actual_payment(self):
        body,proof=self.mixed_body()
        with self.v3():
            trip=self.submit_body(body)
            self.assertEqual({f['id'] for f in trip['sources']['files']},{self.file['id'],proof['id']})
            self.assertEqual(trip['rule_version'],'de_travel_2026_v3')
            command=self.approval(trip,requested_meal_minor=933);settlement=self.api.approve(self.owner,command)['result']
            self.assertEqual(settlement['calculation']['totals']['tax_free_minor'],933)
            self.assertEqual(settlement['calculation']['mixed_program_sources'][0]['source_file_ids'],[proof['id']])
            self.assertEqual(len(settlement['calculation']['ground_calendar_sources']),1)
        # Restoring the active v2 default never reinterprets stored v3 results.
        self.assertTrue(validate_integrity(self.office))
        original=self.api.export(self.owner,settlement['id'],1,'json')[0]
        pay=self.payment(settlement,933);paid=record_payment(self.api,self.owner,pay)
        self.assertEqual(public_source(self.office,paid['target_id'])['cash_movements'][0]['amount'],'9.33')
        self.assertTrue(validate_integrity(self.office))
        self.assertEqual(self.api.export(self.owner,settlement['id'],1,'json')[0],original)
        self.assertEqual(self.api.status(self.owner,command['request_id'])['result'],settlement)

    def test_missing_or_private_program_original_is_not_an_accepted_source(self):
        body,_=self.mixed_body()
        body['details']['mixed_assessment']['program_sessions'][0]['source_file_ids']=[rid()]
        with self.v3():self.problem(404,lambda:self.api.save_trip(self.technician,body))
        hidden=self.upload(purpose='personnel',visible=False,actor=self.owner,marker=rid().encode())
        body,_=self.mixed_body(hidden)
        with self.v3():self.problem(403,lambda:self.api.save_trip(self.technician,body))

    def test_forged_program_metadata_is_detected_even_after_payload_rehash(self):
        body,_=self.mixed_body()
        with self.v3():
            trip=self.submit_body(body);settlement=self.api.approve(self.owner,self.approval(trip,requested_meal_minor=933))['result']
        self.office.db.execute('DROP TRIGGER business_travel_settlements_update_guard')
        row=self.api._row('settlement',settlement['id']);payload=json.loads(row['payload_json'])
        payload['calculation']['mixed_program_sources'][0]['business_seconds']+=3600
        self.office.db.execute('UPDATE business_travel_settlements SET payload_json=?,content_hash=? WHERE id=?',(canonical(payload),_sha(payload),settlement['id']))
        with self.assertRaises(ValueError):validate_integrity(self.office)

    @patch('payroll_travel_2026.RULE_VERSION','de_travel_2026_v2')
    @patch('business_travel_allowances.RULE_VERSION','de_travel_2026_v2')
    def test_v2_default_accepts_only_draft_facts_and_keeps_explicit_mixed_blocker(self):
        body,_=self.mixed_body();trip=self.submit_body(body)
        self.assertEqual(trip['rule_version'],'de_travel_2026_v2')
        command=self.approval(trip,requested_meal_minor=933)
        self.problem(409,lambda:self.api.approve(self.owner,command))
        self.assertTrue(validate_integrity(self.office))

    def test_null_program_object_is_a_validation_error_not_server_failure(self):
        body=self.trip_body(mixed_assessment=None)
        self.problem(400,lambda:self.api.save_trip(self.technician,body))

    @patch('payroll_travel_2026.RULE_VERSION','de_travel_2026_v2')
    @patch('business_travel_allowances.RULE_VERSION','de_travel_2026_v2')
    def test_catalog_and_calculation_use_the_same_explicit_version_hash(self):
        from payroll_travel_rates_2026 import catalog
        from payroll_travel_2026 import rule_metadata
        self.assertEqual(catalog()['rule_version'],'de_travel_2026_v2')
        with self.v3():
            body,_=self.mixed_body()
            _,_,calculation=self.api._trip_details(self.technician,self.employee,body['details'])
            self.assertEqual({k:catalog()[k] for k in ('rule_version','rule_hash','table_hash')},rule_metadata())
            self.assertEqual(calculation['rule_hash'],catalog()['rule_hash'])

    def test_explicit_invalid_historical_version_never_chooses_the_active_default(self):
        from payroll_travel_2026 import rule_metadata,calculate
        for version in ('',False,0,[],{},'de_travel_unknown'):
            self.problem(409,lambda:rule_metadata(version))
            self.problem(409,lambda:calculate([],[],rule_version=version))


if __name__=='__main__':unittest.main()
