"""Independent real-journal counterexamples for travel payment/history rules."""
import json
import unittest

from core import Problem, canonical
from business_personnel_workflow import _sha
from business_travel_allowances import validate_integrity, _ref
from travel_allowance_cash import record_payment, public_source
from test_business_planning import BusinessFixture, rid
import test_business_travel_allowances as fixtures


class TravelIndependentWorkflowTests(BusinessFixture, unittest.TestCase):
    setUp = fixtures.TravelWorkflowTests.setUp
    upload = fixtures.TravelWorkflowTests.upload
    save_site = fixtures.TravelWorkflowTests.save_site
    trip_body = fixtures.TravelWorkflowTests.trip_body
    submitted = fixtures.TravelWorkflowTests.submitted
    approval = fixtures.TravelWorkflowTests.approval
    payment = fixtures.TravelWorkflowTests.payment

    def settled(self):
        source = self.submitted()
        command = self.approval(source)
        return source, command, self.api.approve(self.owner,command)['result']

    def test_payment_replay_checks_current_financial_rights_before_original_receipt(self):
        _,_,settlement = self.settled()
        body = self.payment(settlement)
        receipt = record_payment(self.api,self.owner,body)
        self.office.db.execute("UPDATE users SET role='technician' WHERE id=?",(self.owner['id'],))
        self.problem(403,lambda:record_payment(self.api,self.owner,body))
        self.office.db.execute("UPDATE users SET role='owner' WHERE id=?",(self.owner['id'],))
        self.assertEqual(record_payment(self.api,self.owner,body),receipt)

    def test_void_retains_original_and_reserves_the_real_payment_evidence(self):
        _,_,settlement = self.settled()
        body = self.payment(settlement)
        first = record_payment(self.api,self.owner,body)
        original = public_source(self.office,first['target_id'],1)
        void = dict(body,request_id=rid(),revision=1,action='void',
            correction_reason='Documentary duplicate, no refund occurred',source_hash=self.api._basis(self.employee['id']))
        record_payment(self.api,self.owner,void)
        self.assertEqual(public_source(self.office,first['target_id'])['cash_movements'],[])
        self.assertEqual(public_source(self.office,first['target_id'],1),original)
        duplicate = dict(body,request_id=rid(),id=rid(),source_hash=self.api._basis(self.employee['id']))
        self.problem(409,lambda:record_payment(self.api,self.owner,duplicate))
        self.assertTrue(validate_integrity(self.office))

    def test_correcting_payout_cannot_make_existing_actual_refunds_exceed_payouts(self):
        _,_,settlement = self.settled()
        body = self.payment(settlement)
        record_payment(self.api,self.owner,body)
        record_payment(self.api,self.owner,self.payment(settlement,1000,kind='repayment'))
        correction = dict(body,request_id=rid(),revision=1,action='correct',amount_minor=500,
            correction_reason='Correct original transcription amount',source_hash=self.api._basis(self.employee['id']))
        self.problem(409,lambda:record_payment(self.api,self.owner,correction))
        self.assertTrue(validate_integrity(self.office))

    def test_void_of_payout_cannot_leave_unbacked_actual_refunds(self):
        _,_,settlement = self.settled()
        body = self.payment(settlement)
        record_payment(self.api,self.owner,body)
        record_payment(self.api,self.owner,self.payment(settlement,700,kind='repayment'))
        void = dict(body,request_id=rid(),revision=1,action='void',
            correction_reason='Erroneous original entry',source_hash=self.api._basis(self.employee['id']))
        self.problem(409,lambda:record_payment(self.api,self.owner,void))

    def test_lower_corrected_settlement_does_not_advertise_another_payout(self):
        source,_,settlement = self.settled()
        record_payment(self.api,self.owner,self.payment(settlement))
        command = self.approval(source,correction_of=_ref(settlement),requested_meal_minor=700)
        command.update(id=settlement['id'],revision=settlement['revision'])
        corrected = self.api.approve(self.owner,command)['result']
        self.assertFalse(corrected['calculation']['can_pay'])
        self.assertEqual(corrected['calculation']['totals']['remaining_minor'],0)
        self.assertTrue(validate_integrity(self.office))

    def test_rehashed_employee_snapshot_cannot_invent_an_unrelated_identity_revision(self):
        _,_,settlement = self.settled()
        row = self.api._row('settlement',settlement['id'],1)
        payload = json.loads(row['payload_json'])
        payload['sources']['employee'].update(name='Invented historical identity',user_id='e'*32,revision=999)
        for name in ('business_travel_settlements_update_guard','business_travel_requests_update_guard'):
            self.office.db.execute('DROP TRIGGER '+name)
        self.office.db.execute('UPDATE business_travel_settlements SET payload_json=?,content_hash=? WHERE id=? AND revision=1',
            (canonical(payload),_sha(payload),settlement['id']))
        changed = self.api._get('settlement',settlement['id'],1)
        self.office.db.execute('UPDATE business_travel_requests SET result_hash=? WHERE target_id=?',(_sha(changed),settlement['id']))
        with self.assertRaises(ValueError):validate_integrity(self.office)

    def test_payment_original_digest_binding_is_checked_independently_of_row_hashes(self):
        _,_,settlement = self.settled()
        record_payment(self.api,self.owner,self.payment(settlement))
        self.office.db.execute('DROP TRIGGER business_travel_evidence_update_guard')
        self.office.db.execute('UPDATE business_travel_evidence SET original_sha256=?',('0'*64,))
        with self.assertRaises(ValueError):validate_integrity(self.office)

