"""Real local HTTP framing checks for strict accounting APIs; no invoice fixture."""
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import uuid

from business_accounting import Accounting
from business_finance import Finance
from core import Office
from onedrive import OneDrive
from server import make_handler


class AllocationLocalTransportTests(unittest.TestCase):
    actions = ('/preview', '/assign')
    entries_table = 'business_accounting_allocation_entries'
    components = False
    refunds = False
    refunds_v2 = False
    capacity = False
    payment_kind = 'receipt'

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='synthetic-allocation-local-http-')
        self.addCleanup(temporary.cleanup)
        self.office = Office(Path(temporary.name) / 'office.db')
        self.addCleanup(self.office.db.close)
        email = 'operator@example.test'
        actor = dict(id=self.office.add_user(email, 'Synthetic-password-123', 'owner'), email=email, role='owner')
        self.token = self.office.login(email, 'Synthetic-password-123')
        account = Accounting(self.office).create_account(actor, dict(request_id=uuid.uuid4().hex,
            code='LOCAL', name='Synthetic local cash', kind='cash', confirmation=True))
        payment = Finance(self.office).record_payment(actor, dict(request_id=uuid.uuid4().hex,
            source_id=uuid.uuid4().hex, kind=self.payment_kind, amount='10.00', currency='EUR',
            booking_date='2026-11-02', reference='Synthetic receipt', allocations=[]))
        source = Accounting(self.office).payment_sources(actor)['items'][0]
        event = Accounting(self.office).import_payment(actor, dict(request_id=uuid.uuid4().hex,
            payment_id=payment['id'], source_hash=source['source_hash'], account_id=account['id'],
            account_revision=account['revision'], cash_date='2026-11-02', evidence_reference='LOCAL-01', confirmation=True))
        self.path = '/api/business/accounting/allocations/payments/' + payment['id']
        if self.components:
            self.path = '/api/business/accounting/components/events/' + event['id']
        if self.refunds:
            self.path = '/api/business/accounting/refunds/events/' + event['id']
        if self.capacity:
            self.path = '/api/business/accounting/components/v2/events/' + event['id']
        if self.refunds_v2:
            self.path = '/api/business/accounting/refunds/v2/events/' + event['id']
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.office, OneDrive(self.office)))
        worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(worker.join)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)

    def call(self, method, suffix='', body=None, status=200, extra_headers=None):
        headers = {'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'}
        headers.update(extra_headers or {})
        request = urllib.request.Request(self.base + self.path + suffix, method=method,
            headers=headers, data=None if body is None else json.dumps(body).encode())
        try:
            response = urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            self.assertEqual(response.status, status)
            return json.loads(response.read())

    def test_get_bodies_and_post_filters_are_not_silently_discarded(self):
        before = self.office.db.total_changes
        self.assertEqual(self.call('GET')['unallocated_amount'], '10.00')
        for body in ({}, {'unexpected': True}):
            self.assertIn('Anfragekörper', self.call('GET', body=body, status=400)['error'])
        self.assertIn('Anfragekörper', self.call('GET', status=400,
            extra_headers={'Transfer-Encoding': 'chunked'})['error'])
        for route in self.actions:
            for query in ('?unexpected=1', '?limit=1&limit=2'):
                self.assertIn('Filter', self.call('POST', route + query, {}, 400)['error'])
        self.assertEqual(self.office.db.total_changes, before)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM ' + self.entries_table).fetchone()[0], 0)


class ComponentsLocalTransportTests(AllocationLocalTransportTests):
    actions = ('/preview', '/confirm')
    entries_table = 'business_accounting_component_entries'
    components = True

    def test_only_proven_unaccepted_conflict_has_resolution_on_local_wire(self):
        from business_schema import set_mode
        state = self.call('GET')
        body = dict(source_hash=state['source_hash'], expected_revision=state['revision'],
            state_hash=state['state_hash'], portion_id='a' * 64, portion_state_hash='b' * 64,
            groups=[dict(group_id='c' * 64, amount='10.00')], reason='Synthetic local rejection',
            request_id=uuid.uuid4().hex, preview_hash='d' * 64, confirmation=True)
        if self.capacity:
            body['action'] = 'document_current'
        before = self.office.db.total_changes
        rejected = self.call('POST', '/confirm', body, 409)
        self.assertEqual(rejected['request_resolution'], 'not_accepted')
        self.assertEqual(self.office.db.total_changes, before)
        set_mode(self.office, 'legacy')
        blocked = self.call('POST', '/confirm', body, 409)
        self.assertNotIn('request_resolution', blocked)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM ' + self.entries_table).fetchone()[0], 0)


class RefundsLocalTransportTests(AllocationLocalTransportTests):
    actions = ('/preview', '/confirm')
    entries_table = 'business_accounting_refund_entries'
    refunds = True
    payment_kind = 'refund'


class VersionedRefundsLocalTransportTests(RefundsLocalTransportTests):
    entries_table = 'business_accounting_refunds_v2_entries'
    refunds_v2 = True


class CapacityLocalTransportTests(ComponentsLocalTransportTests):
    actions = ('/preview', '/confirm')
    entries_table = 'business_accounting_capacity_entries'
    capacity = True


if __name__ == '__main__':
    unittest.main()
