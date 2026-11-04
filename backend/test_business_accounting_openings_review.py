"""Independent opening-balance boundaries using actual accepted money sources."""
import base64
import unittest
import uuid

import business_schema
from business_accounting_euer import EuerAccounting
from business_accounting_openings import OpeningBalances, validate_integrity
from business_accounting_profile import AccountingPreparationProfile
from core import Problem, canonical
import test_business_accounting_euer as euer_fixture
import test_business_bank_reconciliation as bank_fixture
from test_accounting_openings_registration import require_review


class OpeningIndependentReview(unittest.TestCase):
    configure=euer_fixture.EuerWorkflowTests.configure

    def setUp(self):
        self.w=bank_fixture.BankTests('runTest');self.w.setUp();self.addCleanup(self.w.doCleanups)
        self.f=self.w.fixture;self.office=self.f.office;self.owner=self.f.owner
        self.profile=AccountingPreparationProfile(self.office,clock=self.f.clock)
        self.configure(bookkeeping_start='2026-11-01')
        self.api=OpeningBalances(self.office,clock=self.f.clock)
        self.euer=EuerAccounting(self.office,clock=self.f.clock)

    def original(self,actor=None):
        return self.api.upload_original(actor or self.owner,dict(request_id=uuid.uuid4().hex,account_id=self.f.account['id'],
            filename='review-opening.pdf',media_type='application/pdf',
            content_base64=base64.b64encode(b'%PDF-1.4\nIndependent actual opening original\n%%EOF').decode()))

    def body(self,original,amount='100.00',actor=None):
        state=self.api.state(actor or self.owner)
        return dict(expected_revision=state['revision'],state_hash=state['state_hash'],account_id=self.f.account['id'],
            account_revision=self.f.account['revision'],profile_ref=state['profile_ref'],status='active',
            opening_date='2026-11-01',amount=amount,reason='Independent original and beginning-of-day scope reviewed',
            source=dict(kind='original',original_id=original['id'],sha256=original['sha256'],evidence_type='account_statement',at_start_of_day=True))

    def opening(self,amount='100.00',actor=None):
        actor=actor or self.owner;original=self.original(actor);body=self.body(original,amount,actor)
        preview=self.api.preview(actor,body);command=body|dict(request_id=uuid.uuid4().hex,confirmation=True,preview_hash=preview['preview_hash'])
        return self.api.confirm(actor,command),command,original

    def account(self,report):
        return next(item for item in report['accounts'] if item['account']['id']==self.f.account['id'])

    def test_start_day_is_included_prior_cash_not_counted_twice_and_euer_stays_identical(self):
        before=self.euer.report(self.owner,2026);entry,command,_=self.opening()
        self.assertEqual(before,self.euer.report(self.owner,2026))
        prior=self.w.cash('10.00',day='2026-10-31');start=self.w.cash('20.00',day='2026-11-01');later=self.w.cash('5.00',day='2026-11-02')
        result=self.account(self.api.liquidity(self.owner,'2026-11-02'))
        self.assertEqual(result['balance'],'125.00')
        self.assertEqual({value['source_id'] for value in result['movements']},{start['id'],later['id']})
        self.assertEqual(self.api.confirm(self.owner,command),entry)
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_bank_connection_added_after_confirmation_cannot_hide_conflicting_first_balance(self):
        self.opening();self.w.cash('20.00',day='2026-11-01')
        self.w.save_statement(self.w.rows('20.00',day='2026-11-01'),period_from='2026-11-01',period_to='2026-11-02',
            opening_balance='101.00',closing_balance='121.00')
        result=self.account(self.api.liquidity(self.owner,'2026-11-02'))
        self.assertIsNone(result['balance'])
        self.assertIn('bank_statement_connection_mismatch',[value['code'] for value in result['issues']])
        self.assertEqual(result['calculated_balance'],'120.00')

    def test_new_profile_does_not_relabel_old_opening_or_mutate_original_receipt(self):
        entry,command,_=self.opening();saved=canonical(entry)
        self.configure(bookkeeping_start='2026-10-01')
        result=self.account(self.api.liquidity(self.owner,'2026-11-02'))
        self.assertIsNone(result['balance']);self.assertIn('opening_profile_changed',[value['code'] for value in result['issues']])
        self.assertEqual(canonical(self.api.confirm(self.owner,command)),saved)

    def test_closed_period_blocks_new_opening_revision_but_preserves_original_replay(self):
        entry,command,original=self.opening()
        statement,_=self.w.save_statement([],opening_balance='100.00',closing_balance='100.00')
        self.w.report([statement])
        state=self.euer.state(self.owner)
        body=dict(operation='period',payload=dict(period='2026-11',action='close',expected_period_revision=0,
            attestation=dict(bank_reconciled=True,originals_complete=True,special_cases_reviewed=True)),
            expected_revision=state['revision'],state_hash=state['state_hash'],reason='Actual independent November closing',
            evidence_reference='Actual bank report and original reviewed')
        preview=self.euer.preview(self.owner,body)
        self.euer.confirm(self.owner,body|dict(request_id=uuid.uuid4().hex,confirmation=True,preview_hash=preview['preview_hash']))
        with self.assertRaises(Problem) as blocked:self.api.preview(self.owner,self.body(original))
        self.assertEqual(blocked.exception.status,409);self.assertIn('EÜR-Perioden',blocked.exception.message)
        self.assertEqual(self.api.confirm(self.owner,command),entry)

    def test_current_bank_rights_apply_to_original_history_liquidity_and_accepted_replay(self):
        actor=self.f.actor('technician')
        for permission in ('accounting.read','finance.read','bank.read','accounting.admin','accounting.prepare','finance.write'):
            self.f.grant(actor,permission)
        entry,command,original=self.opening(actor=actor)
        self.f.grant(actor,'bank.read',effect='deny',revision=1)
        for operation in (lambda:self.api.original(actor,original['id']),lambda:self.api.history(actor,self.f.account['id']),
                lambda:self.api.liquidity(actor,'2026-11-02'),lambda:self.api.confirm(actor,command)):
            with self.subTest(operation=operation):
                with self.assertRaises(Problem) as denied:operation()
                self.assertEqual(denied.exception.status,403)

    def test_pending_financial_restore_does_not_advertise_reconciled_liquidity(self):
        entry,command,_=self.opening();require_review(self.office)
        self.assertIn('restore_reconciliation_pending',[value['code'] for value in self.euer.report(self.owner,2026)['issues']])
        report=self.api.liquidity(self.owner,'2026-11-02')
        self.assertFalse(report['complete_for_recorded_accounts'])
        self.assertIsNone(report['balance_total'])
        self.assertIn('restore_reconciliation_pending',[value['code'] for value in report['issues']])
        with self.assertRaises(Problem) as denied:self.api.confirm(self.owner,command)
        self.assertEqual(denied.exception.status,409)

    def test_missing_original_acceptance_receipt_blocks_fresh_liquidity_and_replay(self):
        entry,command,_=self.opening()
        self.office.db.execute('DROP TRIGGER business_accounting_opening_requests_delete_guard')
        self.office.db.execute("DELETE FROM business_accounting_opening_requests WHERE operation='original'")
        for operation in (lambda:self.api.liquidity(self.owner,'2026-11-02'),lambda:self.api.confirm(self.owner,command)):
            with self.subTest(operation=operation):
                with self.assertRaises(Problem) as rejected:operation()
                self.assertEqual(rejected.exception.status,409)
        with self.assertRaises(ValueError):validate_integrity(self.office)


if __name__=='__main__':unittest.main()
