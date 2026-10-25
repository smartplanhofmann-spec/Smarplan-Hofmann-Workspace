"""Independent HTTP boundary review: real auth, device grants and SQL data.

Fixtures only provide synthetic accounts and upload helpers. No authorization,
domain operation, rendering, database or HTTP handler is replaced by a fake.
The one race barrier wraps the real dispatcher before its fresh domain check.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
import threading
import unittest
from unittest.mock import patch
import uuid

import business_api
from business_schema import set_mode
from core import digest
import plan_access
from server import make_handler
import test_business_planning_time_api as time_fixture
import test_inquiry_attachments_api as attachment_fixture
import test_plan_imports as plan_fixture


def rid():
    return uuid.uuid4().hex


class BusinessBoundaryReviewTests(attachment_fixture.AttachmentHttpFlow, unittest.TestCase):
    setUp = time_fixture.BusinessPlanningTimeApiTests.setUp

    def grant(self, scopes, *, token='owner'):
        actor = self.office.user(self.token if token == 'owner' else token)
        with self.office.lock, self.office.db:
            return plan_access.issue(self.office, actor, workspace=True, business=True,
                                     business_capabilities=scopes)['token']

    def stamp(self, *, action='start', entry=None, at=None, **changes):
        return {'request_id': rid(), 'entry_id': entry or rid(), 'project_id': self.project,
                'device_id': 'synthetic-boundary-device', 'sequence': 1, 'revision': 0,
                'action': action, 'occurred_at': (at or datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
                **changes}

    def photo(self, *, token='owner', **changes):
        content = plan_fixture.png()
        body = {'request_id': rid(), 'project_id': self.project, 'filename': 'Synthetic site photo.png',
                'media_type': 'image/png', 'size': len(content), 'sha256': hashlib.sha256(content).hexdigest(),
                **changes}
        row = self.call('POST', '/business/media', body, token=token, status=201).json
        path = '/business/media/' + row['id']
        self.call('POST', path + '/chunks/0', {'content_base64': base64.b64encode(content).decode()}, token=token)
        completed = self.call('POST', path + '/complete', {'request_id': rid()}, token=token).json
        return path, completed, content

    def permission(self, user, permission, effect, *, scope='*', revision=0):
        return self.call('POST', '/business/settings/permissions', {'request_id': rid(), 'user_id': user,
            'permission': permission, 'scope': scope, 'effect': effect, 'revision': revision}).json

    def classify(self, kind, identifier, classification):
        path = '/business/documents/' + kind + '/' + identifier + '/classification'
        current = self.call('GET', path).json
        return self.call('POST', path, {'request_id': rid(), 'revision': current['revision'],
            'expected_source_fingerprint': current['source_fingerprint'],
            'classification': classification}).json

    def test_field_only_device_can_finish_own_photo_but_never_time_finance_hr_or_foreign_photos(self):
        offline = self.grant(['field_media'])
        caps = self.call('GET', '/business/capabilities', token=offline).json
        self.assertEqual(caps['capabilities'], ['business_operations'])
        self.assertEqual(caps['active_capabilities'], ['business_operations'])
        self.assertEqual(caps['read_capabilities'], ['business_operations'])
        self.assertEqual(caps['global_permissions'], caps['permissions'])
        self.assertFalse(any(permission.startswith(('finance.', 'personnel.', 'settings.', 'privacy.'))
                             for permission in caps['permissions']))
        self.assertNotIn('restore_id', caps)
        path, row, content = self.photo(token=offline)
        self.assertEqual(self.call('GET', path + '/content', token=offline).data, content)
        self.assertEqual(self.call('GET', path, token=offline).json['id'], row['id'])
        foreign, _, _ = self.photo(token=self.technician)
        self.call('GET', foreign + '/content', token=offline, status=404)
        for target in ('/business/time/entries', '/business/time/entries/' + rid(),
                       '/business/employees', '/business/documents', '/business/finance/payments',
                       '/business/receipt-media', '/business/media?project_id=' + self.project):
            with self.subTest(path=target):
                self.call('GET', target, token=offline, status=403)
        self.call('POST', '/business/time/events', self.stamp(), token=offline, status=403)
        self.call('POST', path, {'request_id': rid(), 'revision': row['revision'],
                  'caption': 'No offline annotation mutation'}, token=offline, status=403)
        for changes in ({'purpose': 'receipt'}, {'classification': 'personnel'},
                        {'media_type': 'application/pdf'}, {'purpose': 'document'}):
            with self.subTest(changes=changes):
                self.call('POST', '/business/media', {'request_id': rid(), 'project_id': self.project,
                    'filename': 'Do not upload protected data.png', 'media_type': 'image/png',
                    'size': 1, 'sha256': '0' * 64, **changes}, token=offline, status=403)

    def test_time_only_owner_device_response_is_minimized_even_when_owner_has_all_hr_rights(self):
        self.call('POST', '/business/employees', {'request_id': rid(), 'user_id': self.owner_id,
            'name': 'Synthetic owner employee', 'hourly_cost_minor': 987654, 'weekly_minutes': 2400}, status=201)
        offline = self.grant(['time_events'])
        body = self.stamp()
        started = self.call('POST', '/business/time/events', body, token=offline).json
        self.assertEqual(set(started), {'entry', 'event_id', 'request_id', 'idempotent'})
        current = self.call('GET', '/business/time/entries/' + body['entry_id'], token=offline).json
        self.assertEqual(current['id'], body['entry_id'])
        self.assertNotIn('987654', json.dumps(started))
        for forbidden in ('hourly_cost_minor', 'supplement_percent', 'corrections', 'position', 'location'):
            self.assertNotIn(forbidden, json.dumps(current))
        self.assertIn('hourly_cost_minor', self.call('GET', '/business/time/entries/' + body['entry_id']).json)
        self.call('POST', '/business/media', {'request_id': rid()}, token=offline, status=403)
        tech_body = self.stamp()
        self.call('POST', '/business/time/events', tech_body, token=self.technician)
        self.call('GET', '/business/time/entries/' + tech_body['entry_id'], token=offline, status=404)
        self.call('POST', '/business/time/events', self.stamp(employee_id=self.employee['id']), token=offline, status=403)

    def test_business_prefix_without_matching_issued_database_scope_never_authorizes(self):
        token = self.grant(['time_events'], token=self.technician)
        self.call('GET', '/business/capabilities', token=token)
        with self.office.lock, self.office.db:
            self.office.db.execute('DELETE FROM business_device_grants WHERE token_hash=?', (digest(token),))
        self.call('POST', '/business/time/events', self.stamp(), token=token, status=403)
        self.call('GET', '/business/capabilities', token=token, status=403)
        # Its separately issued original plan grant still authenticates; the
        # absence of a Business receipt cannot silently widen that grant.
        self.call('GET', '/projects/' + self.project + '/plans', token=token)
        token = self.grant(['time_events'], token=self.technician)
        with self.office.lock, self.office.db:
            self.office.db.execute('UPDATE business_device_grants SET user_id=? WHERE token_hash=?',
                                   (self.owner_id, digest(token)))
        self.call('POST', '/business/time/events', self.stamp(), token=token, status=403)
        forged = self.call('POST', '/offline/access', {}, token=self.technician, status=201).json['token']
        forged = forged.replace(plan_access.WORKSPACE_PREFIX, plan_access.BUSINESS_PREFIX, 1)
        self.call('POST', '/business/time/events', self.stamp(), token=forged, status=401)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_time_events').fetchone()[0], 0)

    def test_legacy_workspace_and_gmail_ingress_credentials_cannot_enter_business_namespace(self):
        legacy = self.call('POST', '/offline/access', {}, token=self.technician, status=201).json['token']
        connector = self.issue_gmail()['token']
        for token, status in ((legacy, 403), (connector, 401)):
            for method, path, data in (('GET', '/business/capabilities', None),
                    ('POST', '/business/time/events', self.stamp()),
                    ('POST', '/business/media', {'request_id': rid()}),
                    ('POST', '/business/offline/access', {})):
                with self.subTest(path=path, credential_status=status):
                    self.call(method, path, data, token=token, status=status)
        self.call('GET', '/projects/' + self.project + '/workspace', token=legacy)

    def test_scoped_capabilities_and_denial_are_fresh_before_retry_and_do_not_change_grant_scopes(self):
        self.permission(self.technician_id, 'finance.read', 'allow', scope=self.project)
        scoped = self.call('GET', '/business/capabilities?project_id=' + self.project, token=self.technician).json
        self.assertIn('finance.read', scoped['permissions'])
        self.assertNotIn('finance.read', scoped['global_permissions'])
        offline = self.grant(['time_events'], token=self.technician)
        body = self.stamp()
        self.call('POST', '/business/time/events', body, token=offline)
        self.permission(self.technician_id, 'time.own', 'deny', scope=self.project)
        self.call('POST', '/business/time/events', body, token=offline, status=403)
        self.call('GET', '/business/time/entries/' + body['entry_id'], token=offline, status=403)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_time_events').fetchone()[0], 1)
        self.permission(self.technician_id, 'finance.read', 'deny')
        current = self.call('GET', '/business/capabilities?project_id=' + self.project, token=self.technician).json
        self.assertNotIn('finance.read', current['permissions'])
        other = self.call('POST', '/projects', {'name': 'Synthetic inaccessible project', 'customer': 'Other'}, status=201).json['id']
        self.call('GET', '/business/capabilities?project_id=' + other, token=self.technician, status=404)

    def test_role_permission_revoked_after_http_auth_before_domain_mutation_is_effective(self):
        entered, resume = threading.Event(), threading.Event()
        original = business_api.dispatch
        body = self.stamp()
        def barrier(*args, **kwargs):
            if args[1]['id'] == self.technician_id and args[2] == '/business/time/events':
                entered.set()
                if not resume.wait(3):
                    raise RuntimeError('Synthetic boundary race timed out')
            return original(*args, **kwargs)
        def post():
            with self.app.test_client() as client:
                return client.post('/api/v1/business/time/events', json=body,
                    base_url='https://office.example.test', headers={'Authorization': 'Bearer ' + self.technician})
        with patch.object(business_api, 'dispatch', side_effect=barrier):
            with ThreadPoolExecutor(max_workers=1) as executor:
                pending = executor.submit(post)
                try:
                    self.assertTrue(entered.wait(3))
                    self.permission(self.technician_id, 'time.own', 'deny', scope=self.project)
                finally:
                    resume.set()
                response = pending.result(timeout=4)
        self.assertEqual(response.status_code, 403, response.data)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_time_events').fetchone()[0], 0)

    def test_project_hr_deny_hides_cost_snapshot_while_own_operational_time_stays_readable(self):
        self.permission(self.technician_id, 'personnel.read', 'allow')
        body = self.stamp()
        self.call('POST', '/business/time/events', body, token=self.technician)
        path = '/business/time/entries/' + body['entry_id']
        self.assertEqual(self.call('GET', path, token=self.technician).json['hourly_cost_minor'], 3500)
        self.permission(self.technician_id, 'personnel.read', 'deny', scope=self.project)
        current = self.call('GET', path, token=self.technician).json
        self.assertEqual(current['id'], body['entry_id'])
        self.assertNotIn('hourly_cost_minor', current)
        self.assertNotIn('supplement_percent', current)
        self.assertNotIn('hourly_cost_minor', json.dumps(self.call('GET', '/business/time/entries', token=self.technician).json))
        employees = self.call('GET', '/business/employees?project_id=' + self.project, token=self.technician).json
        self.assertNotIn('hourly_cost_minor', json.dumps(employees))
        calendar = self.call('GET', '/business/planning/calendar?project_id=' + self.project, token=self.technician).json
        self.assertNotIn('hourly_cost_minor', json.dumps(calendar))

    def test_project_planning_deny_also_filters_global_calendar_collection(self):
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        item = self.call('POST', '/business/appointments', {'request_id': rid(), 'project_id': self.project,
            'title': 'Synthetic denied-project visit', 'start_at': tomorrow.isoformat(),
            'end_at': (tomorrow + timedelta(hours=1)).isoformat(), 'employee_ids': [self.employee['id']],
            'resource_ids': [], 'timezone': 'Europe/Berlin'}, status=201).json
        query = '?from=' + tomorrow.date().isoformat() + '&to=' + tomorrow.date().isoformat()
        before = self.call('GET', '/business/planning/calendar' + query, token=self.technician).json
        self.assertEqual([row['id'] for row in before['appointments']], [item['id']])
        self.permission(self.technician_id, 'planning.read', 'deny', scope=self.project)
        self.call('GET', '/business/planning/calendar' + query + '&project_id=' + self.project,
                  token=self.technician, status=403)
        after = self.call('GET', '/business/planning/calendar' + query, token=self.technician).json
        self.assertEqual(after['appointments'], [])
        self.assertNotIn('Synthetic denied-project visit', json.dumps(after))

    def test_native_http_adapter_uses_database_field_scope_and_minimum_operation_surface(self):
        token = self.grant(['field_media'])
        http = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.office, None))
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            def request(method, path, body=None, access=token):
                conn = HTTPConnection('127.0.0.1', http.server_port, timeout=3)
                try:
                    headers = {'Authorization': 'Bearer ' + access}
                    if body is not None:
                        headers['Content-Type'] = 'application/json'
                    conn.request(method, '/api' + path, body=json.dumps(body).encode() if body is not None else None, headers=headers)
                    response = conn.getresponse()
                    return response.status, json.loads(response.read())
                finally:
                    conn.close()
            status, caps = request('GET', '/business/capabilities')
            self.assertEqual(status, 200)
            self.assertEqual(caps['capabilities'], ['business_operations'])
            self.assertEqual(request('POST', '/business/time/events', self.stamp())[0], 403)
            self.assertEqual(request('GET', '/business/employees')[0], 403)
            with self.office.lock, self.office.db:
                self.office.db.execute('DELETE FROM business_device_grants WHERE token_hash=?', (digest(token),))
            self.assertEqual(request('GET', '/business/capabilities')[0], 403)
        finally:
            http.shutdown()
            thread.join(timeout=2)
            http.server_close()

    def test_explicit_plan_copy_is_separate_release_but_new_financial_original_copy_is_blocked(self):
        self.start_message(source_id='synthetic-independent-plan-release')
        raw = attachment_fixture.synthetic_pdf()
        item = self.announce([self.descriptor(raw, media_type='application/pdf', filename='Synthetic source.pdf')])['files'][0]
        self.finish_file(item, raw)
        base = self.convert_message()
        self.call('POST', '/assignments', {'project_id': self.project, 'user_id': self.technician_id})
        self.classify('mail', item['id'], 'operational')
        file = base + '/mail-attachments/' + item['id']
        body = {'request_id': rid(), 'page': 0, 'title': 'Consciously released operative plan copy'}
        copied = self.call('POST', file + '/plan-import', body, status=201).json
        source = base + '/plan-imports/' + copied['id'] + '/source'
        self.assertEqual(self.call('GET', source, token=self.technician).data, raw)
        self.classify('mail', item['id'], 'financial')
        self.call('GET', file + '/content', token=self.technician, status=404)
        self.call('POST', file + '/plan-import', body, token=self.technician, status=404)
        self.call('POST', file + '/plan-import', {**body, 'request_id': rid()}, status=403)
        # The contract makes this previously explicit plan release independent
        # of a later original classification. It is not a generic copy bypass.
        self.assertEqual(self.call('GET', source, token=self.technician).data, raw)
        set_mode(self.office, 'legacy')
        self.call('GET', file + '/content', token=self.technician, status=404)
        self.call('POST', file + '/plan-import', {**body, 'request_id': rid()}, status=403)
        self.assertEqual(self.call('GET', source, token=self.technician).data, raw)

    def test_down_mode_preserves_authorized_exact_archive_but_stops_writes_and_honors_revocation(self):
        today = datetime.now(timezone.utc).date().isoformat()
        self.call('POST', '/business/commercial/settings', {'request_id': rid(), 'revision': 0,
            'company_name': 'Synthetic boundary seller', 'address_line': 'Teststraße1',
            'postal_code': '10115', 'city': 'Berlin', 'country': 'DE', 'vat_id': 'DE123456789',
            'email': 'seller@example.test', 'phone': '+4930123456', 'iban': 'DE89370400440532013000',
            'issuer_mode': 'own', 'issuing_enabled': False, 'cutover_ack': True,
            'cutover_date': '2020-01-01', 'einvoice_format': 'none'})
        # Genuine HTTP policy: SQLite can finalize an offer, never an invoice.
        # Actual invoice archives/role separation are covered by the PG suite.
        body = {'request_id': rid(), 'project_id': self.project, 'kind': 'offer',
            'title': 'Synthetic private boundary offer', 'issue_date': today, 'due_date': today,
            'buyer_reference': 'SYNTHETIC-BUYER', 'buyer': {'name': 'Synthetic buyer',
                'address_line': 'Testweg2', 'postal_code': '10117', 'city': 'Berlin',
                'country': 'DE', 'email': 'buyer@example.test'},
            'positions': [{'description': 'Synthetic service', 'quantity': '1', 'unit': 'HUR',
                'unit_price_net': '99.99', 'tax_rate': '19', 'kind': 'labor'}]}
        draft = self.call('POST', '/business/documents', body).json
        document = self.call('POST', '/business/documents/' + draft['id'] + '/finalize',
                             {'request_id': rid(), 'revision': draft['revision']}).json
        path = '/business/documents/' + document['id'] + '/pdf'
        original = self.call('GET', path).data
        _, accountant = self.add_actor('accountant')
        self.assertEqual(self.call('GET', path, token=accountant).data, original)
        self.call('GET', path, token=self.technician, status=403)
        device = self.grant(['time_events'])
        self.call('GET', path, token=device, status=403)
        set_mode(self.office, 'legacy')
        caps = self.call('GET', '/business/capabilities').json
        self.assertTrue(caps['readonly'])
        self.assertEqual(caps['active_capabilities'], [])
        self.assertIn('business_documents', caps['capabilities'])
        self.assertEqual(self.call('GET', path, token=accountant).data, original)
        self.call('POST', '/business/documents', {**body, 'request_id': rid()}, status=409)
        self.call('POST', '/business/time/events', self.stamp(), token=device, status=409)
        accountant_id = self.office.user(accountant)['id']
        self.call('POST', '/assignments', {'project_id': self.project, 'user_id': accountant_id, 'remove': True})
        self.call('GET', path, token=accountant, status=404)
        self.assertEqual(self.call('GET', path).data, original)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_document_numbers').fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
