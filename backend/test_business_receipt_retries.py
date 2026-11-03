"""Original receipt replies retain their identity and current financial rights."""
import base64
import hashlib
from pathlib import Path
import tempfile
import unittest
import uuid

import business_api
from business_finance import Finance
from business_foundation import BusinessFoundation
from business_operations import BusinessOperations
from business_organization import Organization
from core import Office, Problem
from test_business_operations import PNG


def command(**values):
    return dict(request_id=uuid.uuid4().hex, **values)


class ReceiptRetryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.office = Office(Path(directory.name) / 'receipts.sqlite3')
        self.addCleanup(self.office.db.close)
        self.owner = self.actor('owner')
        self.worker = self.actor('technician')
        self.project = self.office.add_project(self.owner, 'Synthetisches Projekt', 'Testkunde')
        self.office.assign(self.owner, self.project, self.worker['id'])
        self.finance = Finance(self.office)
        for permission in ('finance.read', 'finance.write', 'finance.approve'):
            self.grant(permission)

    def actor(self, role):
        email = uuid.uuid4().hex + '@example.test'
        return dict(id=self.office.add_user(email, 'Synthetic-receipt-password-123', role), role=role, email=email)

    def grant(self, permission, effect='allow', revision=0):
        return BusinessFoundation(self.office).save_grant(self.owner, command(
            user_id=self.worker['id'], permission=permission, scope='*', effect=effect, revision=revision))

    def capture(self):
        body = command(project_id=self.project, filename='beleg.png', media_type='image/png',
                       original_base64=base64.b64encode(PNG).decode())
        return self.finance.capture_receipt(self.worker, body), body

    def review(self, revision=0, **changes):
        return command(revision=revision, vendor='Synthetischer Lieferant', invoice_number='TEST-1',
                       issue_date='2026-11-03', net='100.00', tax='19.00', gross='119.00',
                       currency='EUR', status='reviewed', note='', **changes)

    def test_identical_lost_capture_and_review_replies_never_duplicate_or_change_original(self):
        receipt, capture = self.capture()
        self.assertEqual(self.finance.capture_receipt(self.worker, capture), receipt)
        review = self.review()
        first = self.finance.review_receipt(self.worker, receipt['id'], review)
        revised = self.review(revision=1)
        revised['note'] = 'Begründete neue Prüfung'
        second = self.finance.review_receipt(self.worker, receipt['id'], revised)
        self.assertEqual(second['revision'], 2)
        self.assertEqual(self.finance.review_receipt(self.worker, receipt['id'], review), first)
        self.assertEqual(self.finance.receipt_original(self.worker, receipt['id'])[0], PNG)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_incoming_receipts').fetchone()[0], 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_receipt_reviews').fetchone()[0], 2)

    def test_successful_review_replay_checks_revoked_read_permission_again(self):
        receipt, _ = self.capture()
        body = self.review()
        self.finance.review_receipt(self.worker, receipt['id'], body)
        self.grant('finance.read', 'deny', revision=1)
        with self.assertRaises(Problem) as caught:
            self.finance.review_receipt(self.worker, receipt['id'], body)
        self.assertEqual(caught.exception.status, 403)
        self.assertIsNone(caught.exception.request_resolution)
        self.grant('finance.read', 'allow', revision=2)
        self.assertEqual(self.finance.review_receipt(self.worker, receipt['id'], body)['revision'], 1)

    def test_only_a_missing_receipt_stale_revision_is_marked_not_accepted(self):
        receipt, _ = self.capture()
        first = self.review()
        self.finance.review_receipt(self.worker, receipt['id'], first)
        stale = self.review()
        with self.assertRaises(Problem) as caught:
            self.finance.review_receipt(self.worker, receipt['id'], stale)
        self.assertEqual((caught.exception.status, caught.exception.request_resolution), (409, 'not_accepted'))
        changed_committed = dict(first, note='Anderer Inhalt mit bereits verwendeter Kennung')
        with self.assertRaises(Problem) as caught:
            self.finance.review_receipt(self.worker, receipt['id'], changed_committed)
        self.assertEqual(caught.exception.status, 409)
        self.assertIsNone(caught.exception.request_resolution)

    def test_unfinished_original_cannot_capture_a_receipt_or_leave_an_uncertain_ack(self):
        media = BusinessOperations(self.office).new_media(self.worker, self.project, command(
            purpose='receipt', filename='beleg.png', media_type='image/png', size=len(PNG),
            sha256=hashlib.sha256(PNG).hexdigest()))
        body = command(project_id=self.project, media_id=media['id'])
        with self.assertRaises(Problem) as caught:
            self.finance.capture_receipt(self.worker, body)
        self.assertEqual((caught.exception.status, caught.exception.request_resolution), (409, 'not_accepted'))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_incoming_receipts').fetchone()[0], 0)
        self.assertIsNone(self.office.db.execute('SELECT 1 FROM business_finance_requests WHERE request_id=?',
                                                (body['request_id'],)).fetchone())

    def test_paused_finance_blocks_original_upload_but_not_existing_receipt_read(self):
        receipt, _ = self.capture()
        organization = Organization(self.office)
        current = organization.get(self.owner)
        modules = {key: dict(visible=value['visibility_override'], enabled=value['enabled'])
                   for key, value in current['modules'].items()}
        modules['finance']['enabled'] = False
        organization.save(self.owner, command(revision=current['revision'], needs=current['needs'], modules=modules))
        with self.assertRaises(Problem) as caught:
            business_api.dispatch(self.office, self.worker, '/business/receipt-media', 'POST', command(
                project_id=self.project, filename='beleg.png', media_type='image/png', size=len(PNG),
                sha256=hashlib.sha256(PNG).hexdigest()))
        self.assertEqual(caught.exception.status, 423)
        self.assertEqual(self.finance.receipt(self.worker, receipt['id'])['id'], receipt['id'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_media').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
