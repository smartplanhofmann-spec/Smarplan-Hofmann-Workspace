"""Real SQLite inquiry intake plus synthetic Apps Script execution; no network."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from core import Office, Problem
import inquiries
from inbound_connectors import InboundConnectors, ensure_sqlite_schema, MAX_PER_MINUTE, MAX_ACTIVE_TOKENS


class InboundConnectorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='smartplan-inbound-test-')
        self.addCleanup(self.temporary.cleanup)
        self.office = Office(Path(self.temporary.name) / 'office.db')
        self.addCleanup(self.office.db.close)
        inquiries.ensure_sqlite_schema(self.office)
        ensure_sqlite_schema(self.office)
        identifier = self.office.add_user('owner@example.test', 'Synthetic-owner-password-123', 'owner')
        self.owner = {'id': identifier, 'email': 'owner@example.test', 'role': 'owner'}
        self.now = [1000.0]
        self.connector = InboundConnectors(self.office, clock=lambda: self.now[0])

    def issue(self, **changes):
        return self.connector.issue(self.owner, {'name': 'Synthetic Gmail bridge', 'source_account': 'office@example.test', **changes})

    def envelope(self, **changes):
        return {'source_account': 'office@example.test', 'source_id': '18deadbeef01',
                'subject': 'Synthetic callback request', 'message': 'Bitte um Rückruf zum fiktiven Aufmaß.',
                'sender_name': 'Synthetic sender', 'sender_email': 'sender@example.test', **changes}

    def problem(self, status, operation):
        with self.assertRaises(Problem) as caught:
            operation()
        self.assertEqual(caught.exception.status, status)
        return caught.exception

    def test_issue_returns_raw_token_once_and_database_and_list_contain_only_hash_metadata(self):
        issued = self.issue(source_account='OFFICE@EXAMPLE.TEST')
        token = issued['token']
        self.assertRegex(token, r'^SPIN_[A-Za-z0-9_-]{43}$')
        row = self.office.db.execute('SELECT * FROM inbound_import_tokens').fetchone()
        self.assertEqual(row['token_hash'], hashlib.sha256(token.encode()).hexdigest())
        self.assertNotIn(token, json.dumps(dict(row)))
        self.assertEqual(row['source_account'], 'office@example.test')
        metadata = self.connector.list(self.owner)
        self.assertEqual(metadata, [{key: value for key, value in issued.items() if key != 'token'}])
        self.assertNotIn('token_hash', metadata[0])
        self.assertIsNone(metadata[0]['last_used_at'])
        self.assertEqual(datetime.fromisoformat(issued['expires_at']).timestamp() - self.now[0], 90 * 86400)
        self.assertNotIn(token, str([dict(row) for row in self.office.db.execute('SELECT * FROM audit')]))

    def test_real_inquiry_is_new_and_retries_after_clock_advance_and_token_rotation_dedupe(self):
        first = self.issue()
        original = self.connector.receive_gmail(first['token'], self.envelope())
        self.assertEqual(set(original), {'id', 'status', 'ingested_at'})
        self.assertEqual(original['status'], 'received')
        self.now[0] += 3600
        second = self.connector.receive_gmail(first['token'], self.envelope())
        replacement = self.issue()
        third = self.connector.receive_gmail(replacement['token'], self.envelope())
        self.assertEqual((second['id'], third['id']), (original['id'], original['id']))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiries').fetchone()[0], 1)
        row = self.office.db.execute('SELECT * FROM inquiries').fetchone()
        self.assertEqual((row['source'], row['source_account'], row['source_id'], row['status']),
                         ('gmail', 'office@example.test', '18deadbeef01', 'new'))
        self.assertIsNone(row['customer_id'])
        self.assertIsNone(row['project_id'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM projects').fetchone()[0], 0)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM customers').fetchone()[0], 0)
        self.assertTrue(self.connector.list(self.owner)[0]['last_used_at'])

    def test_revoked_expired_or_no_longer_owner_tokens_fail_closed(self):
        issued = self.issue(expires_days=1)
        self.now[0] += 86400
        self.problem(401, lambda: self.connector.receive_gmail(issued['token'], self.envelope()))
        active = self.issue()
        revoked = self.connector.revoke(self.owner, active['id'])
        self.assertEqual(self.connector.revoke(self.owner, active['id']), revoked)
        self.problem(401, lambda: self.connector.receive_gmail(active['token'], self.envelope()))
        remaining = self.issue()
        with self.office.db:
            self.office.db.execute("UPDATE users SET role='technician' WHERE id=?", (self.owner['id'],))
        self.problem(401, lambda: self.connector.receive_gmail(remaining['token'], self.envelope()))
        self.problem(403, lambda: self.connector.list(self.owner))
        with self.office.db:
            self.office.db.execute("UPDATE users SET role='owner',active=0 WHERE id=?", (self.owner['id'],))
        self.problem(401, lambda: self.connector.receive_gmail(remaining['token'], self.envelope()))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiries').fetchone()[0], 0)

    def test_token_does_not_authenticate_as_office_or_manage_or_read_any_inquiries(self):
        issued = self.issue()
        self.problem(401, lambda: self.office.user(issued['token']))
        self.problem(401, lambda: self.connector.list(issued['token']))
        self.problem(401, lambda: self.connector.revoke(issued['token'], issued['id']))
        self.connector.receive_gmail(issued['token'], self.envelope())
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0], 0)
        self.assertFalse(hasattr(self.connector, 'get_inquiry'))

    def test_bound_mailbox_and_payload_fields_prevent_cross_account_or_workflow_injection(self):
        issued = self.issue()
        for envelope, status in ((self.envelope(source_account='other@example.test'), 403),
                                 (self.envelope(source='whatsapp'), 400),
                                 (self.envelope(status='accepted'), 400),
                                 (self.envelope(customer_id='a' * 32), 400),
                                 (self.envelope(attachments=[{'data': 'not permitted'}]), 400),
                                 (self.envelope(message='x' * 40001), 400),
                                 (self.envelope(message='ä' * 100001), 413)):
            with self.subTest(status=status, keys=list(envelope)):
                self.problem(status, lambda: self.connector.receive_gmail(issued['token'], envelope))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiries').fetchone()[0], 0)
        self.assertIsNone(self.connector.list(self.owner)[0]['last_used_at'])

    def test_same_source_message_id_with_mutated_content_is_rejected_without_success_timestamp(self):
        issued = self.issue()
        self.connector.receive_gmail(issued['token'], self.envelope(received_at='2026-10-24T09:00:00+02:00'))
        before = self.connector.list(self.owner)[0]['last_used_at']
        self.now[0] += 10
        self.problem(409, lambda: self.connector.receive_gmail(issued['token'], self.envelope(
            received_at='2026-10-24T09:00:00+02:00', message='Different immutable message')))
        self.assertEqual(self.connector.list(self.owner)[0]['last_used_at'], before)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiries').fetchone()[0], 1)

    def test_owner_can_list_revoke_only_own_tokens_and_input_lifetime_is_bounded(self):
        issued = self.issue()
        second_id = self.office.add_user('second@example.test', 'Second-owner-password-123', 'owner')
        other = {'id': second_id, 'email': 'second@example.test', 'role': 'owner'}
        self.assertEqual(self.connector.list(other), [])
        self.problem(404, lambda: self.connector.revoke(other, issued['id']))
        for value in (True, 0, 366, 1.5):
            self.problem(400, lambda: self.issue(expires_days=value))

    def test_intake_rate_is_bounded_and_resumes_without_duplicate_inquiries(self):
        issued = self.issue()
        for _ in range(MAX_PER_MINUTE):
            self.connector.receive_gmail(issued['token'], self.envelope())
        self.problem(429, lambda: self.connector.receive_gmail(issued['token'], self.envelope()))
        self.now[0] += 60
        self.connector.receive_gmail(issued['token'], self.envelope())
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiries').fetchone()[0], 1)

    def test_interrupted_delivery_rolls_back_inquiry_and_success_timestamp_together(self):
        issued = self.issue()
        original = inquiries.Inquiries.create
        def interrupted(instance, actor, data):
            original(instance, actor, data)
            raise RuntimeError('Synthetic publication interruption')
        with patch.object(inquiries.Inquiries, 'create', interrupted):
            with self.assertRaisesRegex(RuntimeError, 'Synthetic publication interruption'):
                self.connector.receive_gmail(issued['token'], self.envelope())
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiries').fetchone()[0], 0)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiry_requests').fetchone()[0], 0)
        self.assertIsNone(self.connector.list(self.owner)[0]['last_used_at'])
        self.assertEqual(self.office.db.execute('SELECT window_count FROM inbound_import_tokens').fetchone()[0], 0)

    def test_active_token_limit_allows_replacement_after_revocation(self):
        tokens = [self.issue() for _ in range(MAX_ACTIVE_TOKENS)]
        self.problem(409, self.issue)
        self.connector.revoke(self.owner, tokens[0]['id'])
        replacement = self.issue()
        self.assertNotEqual(replacement['id'], tokens[0]['id'])


class AppsScriptSyntheticTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is required for the local synthetic Apps Script harness')
    def test_readonly_gmail_and_https_retry_cursor_contract(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(['node', str(root / 'integrations/google_apps_script/test_gmail.js')],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('6 synthetic Apps Script checks passed', result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
