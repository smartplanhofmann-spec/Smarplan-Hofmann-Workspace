"""Independent regression cases from the commercial/finance peer review."""
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
import unittest
import uuid

from core import Problem
import business_finance as finance
from business_delivery import DeliveryReceipt
from test_documents import DocumentsFixture


class CommercialFinancePeerTests(DocumentsFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        with self.office.db:
            for statement in finance.schema_statements('BLOB') + finance.guard_statements('sqlite'):
                self.office.db.execute(statement)
        self.finance = finance.Finance(self.office, clock=lambda: datetime(2030, 3, 1, 12, tzinfo=timezone.utc))
        self.settings()

    def actor(self, role, *, assigned=True):
        identifier = self.office.add_user(role + '-' + uuid.uuid4().hex[:8] + '@example.test', 'Synthetic-review-password-123', role)
        actor = {'id': identifier, 'role': role}
        if assigned:
            self.office.assign(self.owner, self.project, identifier)
        return actor

    def test_global_commercial_and_finance_lists_filter_foreign_projects_without_failing(self):
        own = self.issue(self.draft(kind='invoice'))
        foreign_project = self.office.add_project(self.owner, 'Private foreign project', 'Private foreign customer')
        foreign = self.issue(self.draft(project_id=foreign_project, kind='invoice', title='PRIVATE FOREIGN FINANCIAL DETAIL'))
        accountant = self.actor('accountant')
        for name, callback in (
                ('documents', lambda: self.api.list(accountant)),
                ('open_items', lambda: self.finance.open_items(accountant))):
            with self.subTest(collection=name):
                rows = callback()['items']
                self.assertEqual([item['id'] for item in rows], [own['id']])
                self.assertNotIn(foreign['id'], str(rows))
                self.assertNotIn('PRIVATE FOREIGN', str(rows))

    def test_payment_retry_rechecks_revoked_project_scope_before_returning_receipt(self):
        document = self.issue(self.draft(kind='invoice'))
        accountant = self.actor('accountant')
        body = {'request_id': uuid.uuid4().hex, 'source_id': 'synthetic-bank-' + uuid.uuid4().hex,
                'amount': '10.00', 'currency': 'EUR', 'booking_date': '2030-02-01',
                'allocations': [{'document_id': document['id'], 'amount': '10.00'}]}
        saved = self.finance.record_payment(accountant, body)
        self.assertEqual(self.finance.record_payment(accountant, body), saved)
        self.office.assign(self.owner, self.project, accountant['id'], True)
        with self.assertRaises(Problem) as caught:
            self.finance.record_payment(accountant, body)
        self.assertEqual(caught.exception.status, 404)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_payments').fetchone()[0], 1)

    def test_technician_cannot_blind_sign_financial_offer_without_read_permission(self):
        offer = self.issue(self.draft(kind='offer'))
        technician = self.actor('technician')
        with self.assertRaises(Problem) as caught:
            self.api.sign(technician, offer['id'], {'request_id': uuid.uuid4().hex, 'revision': offer['revision'],
                'level': 'simple', 'confirmation': True, 'signer': 'Synthetic signer', 'strokes': [[[0, 0], [1, 1]]]})
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_document_signatures').fetchone()[0], 0)

    def test_credit_note_uses_explicit_current_issue_date_without_backdating_original(self):
        original = self.issue(self.draft(kind='invoice', issue_date='2029-12-31', due_date='2030-01-14'))
        credit = self.call('cancel', original['id'], {'request_id': uuid.uuid4().hex, 'revision': original['revision'],
            'reason': 'Synthetic reviewed cancellation'})
        self.assertEqual(credit['issue_date'], '2030-01-10')
        self.assertEqual(self.call('get', original['id'])['issue_date'], '2029-12-31')

    def test_late_smtp_acceptance_is_not_lost_when_operator_reconciles_during_io(self):
        document = self.issue(self.draft(kind='invoice'))
        preview = self.call('email_preview', document['id'])
        peer = self
        class ConcurrentOperatorTransport:
            def send(self, job):
                outbox = peer.office.db.execute('SELECT id FROM business_document_outbox WHERE operation_id=?', (job['operation_id'],)).fetchone()
                try:
                    peer.api.reconcile_mail(peer.owner, document['id'], {
                        'request_id': uuid.uuid4().hex, 'outbox_id': outbox['id'], 'operation_id': job['operation_id'],
                        'outcome': 'not_sent', 'confirmation': True, 'proof': 'Synthetic concurrent operator trace'})
                except Problem as error:
                    # Rejecting an in-flight override is also a valid solution.
                    peer.assertEqual(error.status, 409)
                return DeliveryReceipt('accepted', job['operation_id'], receipt_id='a' * 64, accepted_by_server=True)
        result = self.api.send_mail(self.owner, document['id'], {'request_id': uuid.uuid4().hex,
            'revision': document['revision'], 'preview_sha256': preview['preview_sha256'], 'confirmation': True},
            transport=ConcurrentOperatorTransport())
        self.assertEqual(result['status'], 'accepted')
        self.assertTrue(result['accepted_by_server'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_document_mail_receipts WHERE status=?', ('accepted',)).fetchone()[0], 1)

    def test_cancellation_credit_cannot_issue_a_different_amount_than_its_original_invoice(self):
        original = self.issue(self.draft(kind='invoice'))
        credit = self.call('cancel', original['id'], {'request_id': uuid.uuid4().hex, 'revision': original['revision'],
            'reason': 'Synthetic full cancellation'})
        try:
            altered = self.call('update', credit['id'], {'request_id': uuid.uuid4().hex, 'revision': credit['revision'],
                'positions': [{'description': 'Altered cancellation', 'quantity': '1', 'unit': 'C62',
                               'unit_price_net': '0.01', 'tax_rate': '19', 'kind': 'material'}]})
        except Problem as error:
            self.assertIn(error.status, (400, 409))
        else:
            with self.assertRaises(Problem) as caught:
                self.issue(altered)
            self.assertIn(caught.exception.status, (400, 409))

    def test_unlinked_credit_is_not_issued_as_an_untracked_cancellation(self):
        with self.assertRaises(Problem) as caught:
            self.issue(self.draft(kind='credit_note'))
        self.assertIn(caught.exception.status, (400, 409))

    def test_crashed_sender_can_be_reconciled_after_its_bounded_delivery_window(self):
        document = self.issue(self.draft(kind='invoice'))
        preview = self.call('email_preview', document['id'])
        body = {'request_id': uuid.uuid4().hex, 'revision': document['revision'],
                'preview_sha256': preview['preview_sha256'], 'confirmation': True}
        class CrashedWorker:
            def send(self, job):
                raise SystemExit('Synthetic worker terminated after durable claim, before SMTP')
        with self.assertRaises(SystemExit):
            self.api.send_mail(self.owner, document['id'], body, transport=CrashedWorker())
        outbox = self.office.db.execute('SELECT * FROM business_document_outbox WHERE document_id=?', (document['id'],)).fetchone()
        old = self.api.clock()
        self.api.clock = lambda: old + timedelta(minutes=5)
        result = self.api.reconcile_mail(self.owner, document['id'], {'request_id': uuid.uuid4().hex,
            'outbox_id': outbox['id'], 'operation_id': outbox['operation_id'], 'outcome': 'not_sent',
            'confirmation': True, 'proof': 'Synthetic externally verified no SMTP attempt after terminated worker'})
        self.assertEqual(result['status'], 'not_sent')

    def test_smtp_io_releases_office_lock_and_late_revocation_hides_response_but_keeps_acceptance(self):
        document = self.issue(self.draft(kind='invoice'))
        preview = self.call('email_preview', document['id'])
        peer = self
        class IndependentRevocationTransport:
            def send(self, job):
                def revoke():
                    peer.assertTrue(peer.office.lock.acquire(timeout=2), 'SMTP IO retained the Office lock')
                    try:
                        with peer.office.db:
                            peer.office.db.execute('UPDATE users SET active=0 WHERE id=?', (peer.owner['id'],))
                    finally:
                        peer.office.lock.release()
                with ThreadPoolExecutor(max_workers=1) as executor:
                    executor.submit(revoke).result(timeout=3)
                return DeliveryReceipt('accepted', job['operation_id'], receipt_id='b' * 64, accepted_by_server=True)
        with self.assertRaises(Problem) as caught:
            self.api.send_mail(self.owner, document['id'], {'request_id': uuid.uuid4().hex,
                'revision': document['revision'], 'preview_sha256': preview['preview_sha256'], 'confirmation': True},
                transport=IndependentRevocationTransport())
        self.assertEqual(caught.exception.status, 401)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_document_mail_receipts WHERE status=?', ('accepted',)).fetchone()[0], 1)

    def test_real_official_validator_accepts_incremental_invoice_chain_and_bound_credit(self):
        from business_einvoice import build_xrechnung, validate_xrechnung
        def positions(amount):
            return [{'description': 'Synthetic cumulative site service', 'quantity': '1', 'unit': 'HUR',
                     'unit_price_net': amount, 'tax_rate': '19', 'kind': 'labor'}]
        first = self.issue(self.draft(kind='advance_invoice', positions=positions('100')))
        second = self.issue(self.draft(kind='cumulative_invoice', positions=positions('200'), previous_document_ids=[first['id']]))
        final = self.issue(self.draft(kind='final_invoice', positions=positions('300'), previous_document_ids=[second['id']]))
        credit = self.call('cancel', second['id'], {'request_id': uuid.uuid4().hex, 'revision': second['revision'],
            'reason': 'Synthetic reviewed cancellation of incremental liability'})
        prepared = self.api.prepare_finalization(self.owner, credit['id'], credit['revision'])
        for snapshot in (second, final, prepared['snapshot']):
            with self.subTest(kind=snapshot['kind']):
                self.assertEqual(snapshot['totals']['gross'], '119.00')
                self.assertTrue(validate_xrechnung(build_xrechnung(snapshot))['accepted'])


if __name__ == '__main__':
    unittest.main()
