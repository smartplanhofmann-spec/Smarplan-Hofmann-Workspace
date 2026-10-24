"""Synthetic inbox, explicit handover and MIME safety against real SQLite."""
from email.message import EmailMessage
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

from core import Office, Problem
from inquiries import Inquiries, MAX_EML_BYTES, MAX_MESSAGE, ensure_sqlite_schema, parse_eml


def request_id():
    return uuid.uuid4().hex


class InquiryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.office = Office(Path(self.temp.name) / 'office.sqlite3')
        self.office.add_user('owner@example.test', 'Synthetic-owner-password-123', 'owner')
        self.actor = self.office.user(self.office.login('owner@example.test', 'Synthetic-owner-password-123'))
        ensure_sqlite_schema(self.office)
        self.now = '2026-10-24T12:00:00+00:00'
        self.inquiries = Inquiries(self.office, clock=lambda: self.now)

    def tearDown(self):
        self.office.db.close()
        self.temp.cleanup()

    def body(self, **changes):
        return {'request_id': request_id(), 'source': 'manual', 'subject': 'Synthetische Anfrage',
                'message': 'Bitte Rückruf zum synthetischen Testvorhaben.', **changes}

    def create(self, **changes):
        return self.inquiries.create(self.actor, self.body(**changes))

    def assert_problem(self, status, action):
        with self.assertRaises(Problem) as caught:
            action()
        self.assertEqual(caught.exception.status, status)

    def count(self, table):
        self.assertIn(table, {'customers', 'projects', 'inquiries', 'inquiry_requests', 'audit'})
        return self.office.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]

    def customer(self, **changes):
        return self.office.create_customer(self.actor, {'name': 'Synthetischer Kunde', **changes})

    def test_manual_inbox_is_real_durable_and_never_creates_a_customer_implicitly(self):
        created = self.create(sender_name='Testsender', sender_email='test@example.test')
        self.assertEqual(created['status'], 'new')
        self.assertEqual(created['received_at'], self.now)
        self.assertEqual(created['candidate_customers'], [])
        self.assertIsNone(created['customer_id'])
        self.assertIsNone(created['project_id'])
        self.assertEqual(self.count('customers'), 0)
        self.assertEqual(self.count('projects'), 0)
        self.assertEqual(Inquiries(self.office).get(self.actor, created['id']), created)
        listed = self.inquiries.list(self.actor)
        self.assertEqual(listed[0]['id'], created['id'])
        self.assertNotIn('message', listed[0])
        self.assertNotIn('provenance', listed[0])
        self.assertEqual(listed[0]['message_preview'], created['message'])
        ensure_sqlite_schema(self.office)
        self.assertEqual(self.count('inquiries'), 1)

    def test_inbox_and_customer_suggestions_are_owner_only_and_recheck_active_role(self):
        created = self.create()
        for role in ('manager', 'technician', 'accountant'):
            uid = self.office.add_user(role + '@example.test', 'Synthetic-role-password-123', role)
            actor = {'id': uid, 'role': role}
            for action in (
                lambda: self.inquiries.list(actor),
                lambda: self.inquiries.get(actor, created['id']),
                lambda: self.inquiries.create(actor, self.body()),
                lambda: self.inquiries.connections(actor),
                lambda: self.inquiries.update(actor, created['id'], {'request_id': request_id(), 'revision': 1, 'status': 'review'}),
                lambda: self.inquiries.convert(actor, created['id'], {'request_id': request_id(), 'revision': 1,
                                                                     'project_name': 'Nicht zulässig', 'customer': {'name': 'Nicht zulässig'}}),
            ):
                self.assert_problem(403, action)
        with self.office.db:
            self.office.db.execute('UPDATE users SET active=0 WHERE id=?', (self.actor['id'],))
        self.assert_problem(403, lambda: self.inquiries.get(self.actor, created['id']))

    def test_candidates_use_exact_normalized_contacts_and_keep_ambiguity_explicit(self):
        first = self.customer(name='Firma A', email='Contact@example.test', phone='+49 123 456789')
        second = self.customer(name='Firma B', email='contact@example.test', phone='0049 123 456789')
        archived = self.customer(name='Firma C', email='contact@example.test', active=False)
        self.customer(name='Firma D', email='other@example.test', phone='0123 456789')
        created = self.create(sender_email='CONTACT@example.test', sender_phone='+49 (123) 456789')
        candidates = created['candidate_customers']
        self.assertEqual({row['id'] for row in candidates}, {first['id'], second['id']})
        self.assertTrue(all(row['match_reasons'] == ['email', 'phone'] for row in candidates))
        self.assertNotIn(archived['id'], {row['id'] for row in candidates})
        self.assertIsNone(created['customer_id'])
        self.assertEqual(self.count('customers'), 4)

    def test_source_identity_and_lost_create_response_are_retry_safe_across_owners(self):
        body = self.body(source='gmail', source_account='inbox@example.test', source_id='provider-message-17')
        first = self.inquiries.create(self.actor, body)
        self.now = '2026-10-25T14:00:00+00:00'
        self.assertEqual(self.inquiries.create(self.actor, body), first)
        uid = self.office.add_user('second-owner@example.test', 'Synthetic-second-owner-123', 'owner')
        other_actor = {'id': uid, 'role': 'owner'}
        duplicate = self.inquiries.create(other_actor, {**body, 'request_id': request_id()})
        self.assertEqual(duplicate['id'], first['id'])
        self.assertEqual(self.count('inquiries'), 1)
        self.assertEqual(self.office.db.execute("SELECT COUNT(*) FROM audit WHERE action='inquiry.created'").fetchone()[0], 1)
        self.assert_problem(409, lambda: self.inquiries.create(self.actor, {**body, 'message': 'Geänderter Inhalt'}))
        self.assert_problem(409, lambda: self.inquiries.create(self.actor, {**body, 'request_id': request_id(), 'message': 'Anderer Inhalt'}))
        separate = self.inquiries.create(self.actor, {**body, 'request_id': request_id(), 'source_account': 'other@example.test'})
        self.assertNotEqual(separate['id'], first['id'])

    def test_followups_are_revisioned_retry_safe_and_do_not_force_a_fixed_workflow(self):
        entry = self.create()
        body = {'request_id': request_id(), 'revision': 1, 'status': 'offer', 'review_method': 'zoom',
                'next_action': 'Unterlagen prüfen', 'due_date': '2026-10-30', 'sevdesk_url': 'https://my.sevdesk.de/angebote/17'}
        saved = self.inquiries.update(self.actor, entry['id'], body)
        self.assertEqual(saved['revision'], 2)
        self.assertEqual(saved['status'], 'offer')
        self.assertEqual(saved['review_method'], 'zoom')
        self.assertEqual(self.inquiries.update(self.actor, entry['id'], body), saved)
        self.assert_problem(409, lambda: self.inquiries.update(self.actor, entry['id'], {**body, 'request_id': request_id()}))
        back = self.inquiries.update(self.actor, entry['id'], {'request_id': request_id(), 'revision': 2,
                                                               'status': 'callback', 'review_method': 'on_site'})
        self.assertEqual(back['status'], 'callback')
        self.assertEqual(len(self.inquiries.list(self.actor, status='callback')), 1)

    def test_acceptance_is_optional_but_when_recorded_requires_an_explicit_channel(self):
        entry = self.create()
        self.assert_problem(400, lambda: self.inquiries.update(self.actor, entry['id'],
            {'request_id': request_id(), 'revision': 1, 'status': 'accepted'}))
        accepted = self.inquiries.update(self.actor, entry['id'], {'request_id': request_id(), 'revision': 1,
                                                                  'status': 'accepted', 'acceptance_channel': 'phone'})
        self.assertEqual(accepted['acceptance_channel'], 'phone')
        self.assertEqual(accepted['status'], 'accepted')

    def test_new_enquiry_can_become_a_project_without_inventing_an_acceptance(self):
        customer = self.customer()
        entry = self.create()
        body = {'request_id': request_id(), 'revision': 1, 'project_name': 'Erstklärung vor Ort', 'customer_id': customer['id']}
        result = self.inquiries.convert(self.actor, entry['id'], body)
        self.assertEqual(result['inquiry']['status'], 'converted')
        self.assertEqual(result['inquiry']['acceptance_channel'], '')
        self.assertEqual(result['inquiry']['review_method'], '')
        self.assertEqual(result['project']['customer_id'], customer['id'])
        self.assertEqual(result['inquiry']['project_id'], result['project']['id'])
        self.assertEqual(self.inquiries.convert(self.actor, entry['id'], body), result)
        self.assertEqual(self.count('projects'), 1)
        self.assertEqual(self.count('customers'), 1)
        self.assert_problem(409, lambda: self.inquiries.convert(self.actor, entry['id'], {**body, 'request_id': request_id()}))

    def test_explicit_new_customer_handover_reuses_customer_deduplication(self):
        existing = self.customer(name='Firma Muster', address='Musterweg 1')
        entry = self.create()
        duplicate = {'request_id': request_id(), 'revision': 1, 'project_name': 'Neues Vorhaben',
                     'customer': {'name': '  FIRMA MUSTER ', 'address': 'musterweg 1'}}
        self.assert_problem(409, lambda: self.inquiries.convert(self.actor, entry['id'], duplicate))
        self.assertEqual(self.count('projects'), 0)
        created = self.inquiries.convert(self.actor, entry['id'], {**duplicate, 'request_id': request_id(),
            'customer': {'name': 'Neuer bestätigter Kunde', 'email': 'new@example.test', 'address': 'Musterweg 7'}})
        self.assertNotEqual(created['project']['customer_id'], existing['id'])
        self.assertEqual(self.count('customers'), 2)

    def test_failed_handover_rolls_back_customer_project_status_and_receipt(self):
        entry = self.create()
        counts = {table: self.count(table) for table in ('customers', 'projects', 'audit', 'inquiry_requests')}
        original = self.office.audit

        def fail_last(actor, action, identifier):
            if action == 'inquiry.converted':
                raise RuntimeError('Synthetic failure after all handover inserts')
            return original(actor, action, identifier)

        with patch.object(self.office, 'audit', side_effect=fail_last):
            with self.assertRaises(RuntimeError):
                self.inquiries.convert(self.actor, entry['id'], {'request_id': request_id(), 'revision': 1,
                    'project_name': 'Synthetisches Projekt', 'customer': {'name': 'Synthetischer neuer Kunde'}})
        self.assertEqual({table: self.count(table) for table in counts}, counts)
        self.assertEqual(self.inquiries.get(self.actor, entry['id'])['revision'], 1)
        self.assertEqual(self.inquiries.get(self.actor, entry['id'])['status'], 'new')

    def test_nested_operation_does_not_prematurely_commit_the_request_transaction(self):
        self.office.db.execute('BEGIN')
        self.create()
        self.assertTrue(self.office.db.in_transaction)
        self.office.db.rollback()
        self.assertEqual(self.count('inquiries'), 0)
        self.assertEqual(self.count('inquiry_requests'), 0)

    def test_declined_enquiry_requires_explicit_reactivation_before_handover(self):
        entry = self.create()
        declined = self.inquiries.update(self.actor, entry['id'], {'request_id': request_id(), 'revision': 1, 'status': 'declined'})
        body = {'request_id': request_id(), 'revision': declined['revision'], 'project_name': 'Klären',
                'customer': {'name': 'Testkunde'}}
        self.assert_problem(409, lambda: self.inquiries.convert(self.actor, entry['id'], body))
        reopened = self.inquiries.update(self.actor, entry['id'], {'request_id': request_id(), 'revision': declined['revision'],
                                                                 'status': 'review'})
        result = self.inquiries.convert(self.actor, entry['id'], {**body, 'request_id': request_id(), 'revision': reopened['revision']})
        self.assertEqual(result['inquiry']['acceptance_channel'], '')

    def test_eml_prefers_plain_text_preserves_provenance_and_does_not_import_attachment_bytes(self):
        mail = EmailMessage()
        mail['From'] = 'Synthetischer Sender <sender@example.test>'
        mail['Subject'] = 'Aufmaß – synthetische Anfrage'
        mail['Message-ID'] = '<synthetic-mail-42@example.test>'
        mail['Date'] = 'Sat, 24 Oct 2026 14:00:00 +0200'
        mail.set_content('Guten Tag, bitte Unterlagen prüfen.\nSynthetischer Text.')
        mail.add_alternative('<html><script>private-script</script><p>HTML Alternative</p></html>', subtype='html')
        mail.add_attachment(b'PRIVATE_ATTACHMENT_BYTES_7359', maintype='application', subtype='pdf', filename='../../Plan.pdf')
        raw = mail.as_bytes()
        entry = self.inquiries.import_eml(self.actor, raw, request_id=request_id(), source_account='synthetic-import')
        self.assertEqual(entry['source'], 'import')
        self.assertIn('Unterlagen prüfen', entry['message'])
        self.assertNotIn('HTML Alternative', entry['message'])
        self.assertNotIn('private-script', entry['message'])
        self.assertEqual(entry['received_at'], '2026-10-24T12:00:00+00:00')
        self.assertEqual(entry['provenance']['attachments'][0]['filename'], 'Plan.pdf')
        self.assertEqual(entry['provenance']['attachments'][0]['size'], len(b'PRIVATE_ATTACHMENT_BYTES_7359'))
        stored = self.office.db.execute('SELECT message,provenance FROM inquiries').fetchone()
        self.assertNotIn('PRIVATE_ATTACHMENT_BYTES_7359', stored['message'] + stored['provenance'])
        self.assertEqual(self.count('customers'), 0)

    def test_html_only_eml_is_plain_text_with_no_executable_or_remote_content(self):
        mail = EmailMessage()
        mail['From'] = 'sender@example.test'
        mail['Subject'] = 'Synthetisches HTML'
        mail.set_content('<p>Aufmaß &amp; Termin</p><script>alert("secret")</script>'
                         '<iframe src="https://example.test/private">hidden</iframe>'
                         '<img src="https://example.test/tracker"><p>Bitte Rückruf</p>', subtype='html')
        entry = self.inquiries.import_eml(self.actor, mail.as_bytes(), request_id=request_id())
        self.assertIn('Aufmaß & Termin', entry['message'])
        self.assertIn('Bitte Rückruf', entry['message'])
        for forbidden in ('<', 'secret', 'hidden', 'https://'):
            self.assertNotIn(forbidden, entry['message'])

    def test_eml_without_date_or_message_id_remains_stable_across_retry_and_reimport(self):
        raw = b'From: sender@example.test\nSubject: Synthetic no date\n\nTest message without a provider date.'
        key = request_id()
        first = self.inquiries.import_eml(self.actor, raw, request_id=key)
        self.now = '2026-10-30T17:30:00+00:00'
        self.assertEqual(self.inquiries.import_eml(self.actor, raw, request_id=key), first)
        again = self.inquiries.import_eml(self.actor, raw, request_id=request_id())
        self.assertEqual(again['id'], first['id'])
        self.assertEqual(again['received_at'], first['received_at'])
        self.assertEqual(self.count('inquiries'), 1)

    def test_invalid_data_is_rejected_without_mutating_business_records(self):
        entry = self.create()
        for change in ({'source': []}, {'sender_email': 'invalid'}, {'subject': 'bad\nheader'},
                       {'received_at': '2026-10-24T12:00:00'}, {'message': 'x' * (MAX_MESSAGE + 1)},
                       {'request_id': 'bad'}, {'status': 'accepted'}, {'source_account': ''}):
            self.assert_problem(400, lambda change=change: self.inquiries.create(self.actor, self.body(**change)))
        for change in ({'due_date': '2026-02-30'}, {'due_date': '24.10.2026'}, {'status': []},
                       {'status': 'converted'}, {'revision': True}, {'review_method': 'invented'},
                       {'sevdesk_url': 'https://sevdesk.de.evil.test/path'}, {'sevdesk_url': 'javascript:alert(1)'},
                       {'sevdesk_url': 'https://user:secret@my.sevdesk.de/path'}):
            self.assert_problem(400, lambda change=change: self.inquiries.update(self.actor, entry['id'],
                {'request_id': request_id(), 'revision': 1, **change}))
        self.assert_problem(413, lambda: self.inquiries.import_eml(self.actor, b'x' * (MAX_EML_BYTES + 1), request_id=request_id()))
        duplicate_header = b'From: a@example.test\nFrom: b@example.test\nSubject: X\n\nSynthetischer Text'
        self.assert_problem(400, lambda: parse_eml(duplicate_header, received_at=self.now))
        self.assertEqual(self.count('inquiries'), 1)
        self.assertEqual(self.count('projects'), 0)
        self.assertEqual(self.count('customers'), 0)

    def test_connection_status_never_claims_a_live_mailbox_from_manual_imports(self):
        self.create(source='gmail', source_account='synthetic@example.test', source_id='gmail-test-1')
        state = self.inquiries.connections(self.actor)
        self.assertFalse(state['automatic_ingestion'])
        self.assertTrue(state['manual_import']['eml'])
        self.assertTrue(all(provider['state'] == 'not_connected' for provider in state['providers']))


if __name__ == '__main__':
    unittest.main()
