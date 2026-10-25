"""Real public HTTPS Flask intake, private configuration and durable receipts."""
import os
import unittest
from unittest.mock import patch
import uuid

from business_schema import set_feature_flag
import test_workspace_api as workspace_fixture


class ContactIntakeHttpTests(workspace_fixture.WorkspaceHttpFlow, unittest.TestCase):
    setUp = workspace_fixture.WorkspaceApiTests.setUp
    tearDown = workspace_fixture.WorkspaceApiTests.tearDown
    open_app = workspace_fixture.WorkspaceApiTests.open_app

    def configure(self):
        for flag in ('external.website_form', 'external.website_leads', 'external.lead_autoreply'):
            set_feature_flag(self.office, self.owner, flag, True)
        adapter = self.call('POST', '/business/adapters', {
            'request_id': uuid.uuid4().hex, 'name': 'Synthetic public website',
            'profile': 'website_lead_v1', 'enabled': True,
            'secret_ref': 'SMARTPLAN_CONTACT_TEST_SECRET'}, status=201).json
        environment = patch.dict(os.environ, {
            'SMARTPLAN_CONTACT_ADAPTER_ID': adapter['id'],
            'SMARTPLAN_CONTACT_ALLOWED_ORIGINS': 'https://office.example.test',
            'SMARTPLAN_CONTACT_TEST_SECRET': 'SPLD_' + 's' * 43,
            'SMARTPLAN_SMTP_FROM': 'reply@example.test',
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.call('POST', '/business/adapters/' + adapter['id'] + '/reply-template', {
            'request_id': uuid.uuid4().hex, 'revision': 0, 'approved': True, 'enabled': True,
            'subject': 'Ihre Anfrage',
            'text': 'Guten Tag {sender_name}, wir melden uns zur Klärung. Dies ist keine Auftragsbestätigung.'})
        return adapter

    def form(self):
        return {'request_id': uuid.uuid4().hex, 'subject': 'Synthetic site request',
                'message': 'Please call back, no order.', 'sender_name': 'Synthetic sender',
                'sender_email': 'sender@example.test', 'sender_phone': '', 'website': '',
                'privacy_notice_version': 'synthetic-v1'}

    def test_public_form_needs_no_office_token_and_retries_one_inquiry_with_unsent_reply(self):
        self.configure()
        body = self.form()
        origin = {'Origin': 'https://office.example.test'}
        first = self.call('POST', '/intake/contact', body, token=None, headers=origin, status=201).json
        again = self.call('POST', '/intake/contact', body, token=None, headers=origin, status=201).json
        self.assertEqual(first, again)
        self.assertEqual(first['status'], 'received')
        self.assertEqual(first['reply_status'], 'pending')
        self.assertFalse(first['accepted_by_server'])
        self.assertNotIn('SPLD_', str(first))
        self.assertEqual(self.office.db.execute('SELECT count(*) FROM inquiries').fetchone()[0], 1)
        self.assertEqual(self.office.db.execute('SELECT count(*) FROM business_lead_reply_outbox').fetchone()[0], 1)
        self.call('POST', '/intake/contact', {**body, 'message': 'Changed after confirmation'},
                  token=None, headers=origin, status=409)

    def test_untrusted_origins_spam_and_oversized_bodies_never_write_inquiries(self):
        self.configure()
        body = self.form()
        for origin in ('', 'null', 'http://office.example.test', 'https://unrelated.example.test'):
            self.call('POST', '/intake/contact', body, token=None, headers={'Origin': origin}, status=403)
        self.call('POST', '/intake/contact', {**body, 'website': 'https://spam.example.test'},
                  token=None, headers={'Origin': 'https://office.example.test'}, status=400)
        self.call('POST', '/intake/contact', {**body, 'message': 'x' * 33000},
                  token=None, headers={'Origin': 'https://office.example.test'}, status=413)
        self.assertEqual(self.office.db.execute('SELECT count(*) FROM inquiries').fetchone()[0], 0)

    def test_private_lead_endpoint_has_a_dedicated_key_and_uuid_source(self):
        adapter = self.configure()
        message = {key: value for key, value in self.form().items()
                   if key not in ('request_id', 'website')}
        message['external_id'] = uuid.uuid4().hex
        path = '/intake/leads/' + adapter['id']
        self.call('POST', path, message, token=self.token, status=401)
        self.call('POST', path, message, token='SPIN_' + 's' * 43, status=401)
        result = self.call('POST', path, message, token='SPLD_' + 's' * 43, status=201).json
        self.assertEqual(set(result), {'id', 'status'})
        self.call('POST', '/intake/leads/not-an-id', message, token='SPLD_' + 's' * 43, status=404)


if __name__ == '__main__':
    unittest.main()
