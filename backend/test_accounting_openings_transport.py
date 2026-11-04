"""Synthetic opening-original transport boundaries in local HTTP and MFA API."""
import base64
import hashlib
import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
import uuid

from business_accounting import Accounting
from core import Office
from onedrive import OneDrive
from server import make_handler
from online import test_accounting_journey as journey


class OpeningTransportCases:
    path = '/business/accounting/opening-balances'

    def test_strict_framing_is_rejected_before_any_opening_original_is_saved(self):
        before = self.office.db.total_changes
        self.assertEqual(self.raw('GET')[0], 200)
        self.assertEqual(self.raw('GET', body=b'{}')[0], 400)
        self.assertEqual(self.raw('GET', '?account_id=a&account_id=b')[0], 400)
        for route in ('/preview', '/confirm', '/originals'):
            with self.subTest(route=route):
                self.assertEqual(self.raw('GET', route)[0], 405)
                self.assertEqual(self.raw('POST', route + '?unexpected=1', b'{}')[0], 400)
                self.assertEqual(self.raw('POST', route, b'{"request_id":"a","request_id":"b"}')[0], 400)
                self.assertEqual(self.raw('POST', route, b'[]')[0], 400)
        self.assertEqual(self.office.db.total_changes, before)

    def test_maximum_original_roundtrips_once_and_oversize_is_rejected(self):
        raw = b'%PDF-1.4\n' + b'S' * (5 * 1024 * 1024 - 15) + b'\n%%EOF'
        self.assertEqual(len(raw), 5 * 1024 * 1024)
        body = dict(request_id=uuid.uuid4().hex, account_id=self.account['id'],
                    filename='synthetic-opening.pdf', media_type='application/pdf',
                    content_base64=base64.b64encode(raw).decode())
        status, _, payload = self.raw('POST', '/originals', json.dumps(body).encode())
        self.assertEqual(status, 201, payload[:200])
        original = json.loads(payload)
        self.assertEqual(original['size'], len(raw))
        self.assertEqual(original['sha256'], hashlib.sha256(raw).hexdigest())
        before = self.office.db.total_changes
        status, _, payload = self.raw('POST', '/originals', json.dumps(body).encode())
        self.assertEqual(status, 201)
        self.assertEqual(json.loads(payload), original)
        self.assertEqual(self.office.db.total_changes, before)
        status, headers, payload = self.raw('GET', '/originals/' + original['id'])
        self.assertEqual(status, 200)
        self.assertEqual(payload, raw)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(headers['Content-Type'], 'application/pdf')
        self.assertTrue(headers['Content-Disposition'].startswith('attachment;'))
        oversized = body | dict(request_id=uuid.uuid4().hex,
            content_base64=base64.b64encode(raw + b'x').decode())
        self.assertEqual(self.raw('POST', '/originals', json.dumps(oversized).encode())[0], 413)
        self.assertEqual(self.office.db.total_changes, before)


class OpeningLocalTransportTests(OpeningTransportCases, unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='synthetic-opening-http-')
        self.addCleanup(temporary.cleanup)
        self.office = Office(Path(temporary.name) / 'office.db')
        self.addCleanup(self.office.db.close)
        email, password = 'owner@example.test', 'Synthetic-password-123'
        actor = dict(id=self.office.add_user(email, password, 'owner'))
        self.token = self.office.login(email, password)
        self.account = Accounting(self.office).create_account(actor, dict(request_id=uuid.uuid4().hex,
            code='LOCAL', name='Synthetic money account', kind='bank', confirmation=True))
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.office, OneDrive(self.office)))
        worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(worker.join)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def raw(self, method, suffix='', body=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        try:
            connection.request(method, '/api' + self.path + suffix, body=body,
                headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'})
            reply = connection.getresponse()
            if reply.status == 200 and '/originals/' in suffix:
                self.assertEqual(len(reply.headers.get_all('Content-Disposition')), 1)
            return reply.status, dict(reply.getheaders()), reply.read()
        finally:
            connection.close()


class OpeningMFATransportTests(OpeningTransportCases, unittest.TestCase):
    new_company = journey.AccountingJourneyTests.new_company
    open_app = journey.AccountingJourneyTests.open_app
    call = journey.AccountingJourneyTests.call
    login = journey.AccountingJourneyTests.login
    account_record = journey.AccountingJourneyTests.account_record

    def setUp(self):
        journey.AccountingJourneyTests.setUp(self)
        self.office = self.company['office']

    def raw(self, method, suffix='', body=None):
        reply = self.company['client'].open('/api/v1' + self.path + suffix, method=method,
            base_url='https://' + self.company['host'], data=body,
            headers={'Authorization': 'Bearer ' + self.company['token'], 'Content-Type': 'application/json'})
        return reply.status_code, dict(reply.headers), reply.data

    def test_mfa_api_requires_json_media_type_before_original_acceptance(self):
        before = self.office.db.total_changes
        reply = self.company['client'].post('/api/v1' + self.path + '/originals',
            base_url='https://' + self.company['host'], data='{}',
            headers={'Authorization': 'Bearer ' + self.company['token'], 'Content-Type': 'text/plain'})
        self.assertEqual(reply.status_code, 415)
        self.assertEqual(self.office.db.total_changes, before)


if __name__ == '__main__':
    unittest.main()
