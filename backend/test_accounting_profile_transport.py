"""Actual local HTTP profile framing and original acknowledgements, no tax defaults."""
from http.server import ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
import uuid

from business_accounting import Accounting
from core import Office
from onedrive import OneDrive
from server import make_handler
import test_accounting_allocation_transport as transport_helpers


class ProfileLocalTransportTests(unittest.TestCase):
    call = transport_helpers.AllocationLocalTransportTests.call

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='synthetic-profile-local-http-')
        self.addCleanup(temporary.cleanup)
        self.office = Office(Path(temporary.name) / 'office.db')
        self.addCleanup(self.office.db.close)
        email = 'profile-owner@example.test'
        self.actor = dict(id=self.office.add_user(email, 'Synthetic-password-123', 'owner'),
                          email=email, role='owner')
        self.token = self.office.login(email, 'Synthetic-password-123')
        self.path = '/api/business/accounting/profile'
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.office, OneDrive(self.office)))
        worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(worker.join)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)

    def body(self, state, reason='Synthetic explicit owner statement'):
        return dict(expected_revision=state['revision'], state_hash=state['state_hash'],
                    profile=dict(legal_form='sole_proprietorship', accounting_method='euer',
                                 vat_regime=None, vat_timing=None, vat_effective_from=None,
                                 bookkeeping_start=None), reason=reason,
                    evidence_reference='Synthetic owner statement 01')

    def confirm_body(self, body, preview):
        return dict(body, request_id=uuid.uuid4().hex, preview_hash=preview['preview_hash'], confirmation=True)

    def test_actual_local_framing_and_reads_cannot_create_a_profile(self):
        before = self.office.db.total_changes
        self.assertEqual(self.call('GET')['preparation_status'], 'unrecorded')
        self.assertEqual(self.call('GET', '/history')['items'], [])
        for body in ({}, {'unexpected': True}):
            self.assertIn('Anfragekörper', self.call('GET', body=body, status=400)['error'])
        self.assertIn('Anfragekörper', self.call('GET', status=400,
                      extra_headers={'Transfer-Encoding': 'chunked'})['error'])
        for route in ('/preview', '/confirm'):
            for query in ('?unexpected=1', '?limit=1&limit=2'):
                self.assertIn('Filter', self.call('POST', route + query, {}, 400)['error'])
            self.call('GET', route, status=405)
        self.call('GET', '/history?limit=1&limit=2', status=400)
        self.call('GET', '?unexpected=1', status=400)
        self.assertEqual(self.office.db.total_changes, before)

    def test_unknown_fields_stay_unknown_and_old_success_replays_after_a_new_version(self):
        old_status = Accounting(self.office).status(self.actor)
        body = self.body(self.call('GET'))
        before = self.office.db.total_changes
        preview = self.call('POST', '/preview', body)
        self.assertEqual(self.office.db.total_changes, before)
        original = self.confirm_body(body, preview)
        first = self.call('POST', '/confirm', original, 201)
        self.assertEqual(first['profile'], body['profile'])
        state = self.call('GET')
        self.assertEqual(state['revision'], 1)
        self.assertEqual(state['preparation_status'], 'recorded')
        self.assertFalse(state['tax_result_available'])
        second_body = self.body(state, 'Synthetic later review without tax assumptions')
        second_preview = self.call('POST', '/preview', second_body)
        second = self.call('POST', '/confirm', self.confirm_body(second_body, second_preview), 201)
        self.assertEqual(second['revision'], 2)
        before = self.office.db.total_changes
        self.assertEqual(self.call('POST', '/confirm', original, 201), first)
        self.assertEqual(self.office.db.total_changes, before)
        self.assertEqual(self.call('GET', '/history')['items'], [second, first])
        self.assertEqual(Accounting(self.office).status(self.actor), old_status)

    def test_only_absent_receipt_conflict_carries_local_not_accepted_marker(self):
        from business_schema import set_mode
        body = self.body(self.call('GET'))
        preview = self.call('POST', '/preview', body)
        original = self.confirm_body(body, preview)
        self.call('POST', '/confirm', original, 201)
        stale = dict(original, request_id=uuid.uuid4().hex)
        before = self.office.db.total_changes
        self.assertEqual(self.call('POST', '/confirm', stale, 409)['request_resolution'], 'not_accepted')
        self.assertNotIn('request_resolution', self.call('POST', '/confirm', dict(original, reason='Changed body'), 409))
        self.assertEqual(self.office.db.total_changes, before)
        set_mode(self.office, 'legacy')
        self.assertNotIn('request_resolution', self.call('POST', '/confirm', original, 409))


if __name__ == '__main__':
    unittest.main()
