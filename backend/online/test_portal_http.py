"""Portal transport, committed abuse counters and actual SQLite disaster restore.

Synthetic data only. Staff login uses real MFA; customer routes use only their
separate credentials. Company/customer/adoption journeys live in their own suite.
"""
from datetime import datetime, timedelta
import hashlib
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
import uuid

from cryptography.fernet import Fernet

from backend.backup import backup
import business_schema
from business_portal import Portal
from core import Office
from online.auth import totp
from online.portal import MAX_BODY_BYTES, REQUESTS_PER_WINDOW, SESSIONS_PER_WINDOW, DECISIONS_PER_WINDOW
from online.test_instance_isolation import MFA_SCHEMA
from online.web import create_app
from backend.restore import restore


class PortalHTTPTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='synthetic-portal-boundary-')
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.path = self.directory / 'company.sqlite3'
        self.office = Office(self.path)
        self.addCleanup(self.office.db.close)
        self.office.db.executescript(MFA_SCHEMA)
        self.office.add_user('owner@example.test', 'Synthetic-portal-owner-password-123', 'owner')
        self.key = Fernet.generate_key()
        self.origin = 'https://portal.example.test'
        self.app = create_app(office=self.office, key=self.key, host='portal.example.test', storage_config={})
        self.client = self.app.test_client()
        pending = self.call('/login', {'email': 'owner@example.test',
            'password': 'Synthetic-portal-owner-password-123'}).json
        self.assertNotIn('token', pending)
        self.staff = self.call('/login/verify', {'challenge': pending['challenge'],
            'code': totp(pending['enrollment']['secret'], int(time.time() // 30))}).json['token']

    def call(self, path, body=None, *, token=None, status=200, method=None,
             origin='configured', headers=None, raw=None, mimetype='application/json',
             base_url=None, client=None):
        method = method or ('POST' if body is not None or raw is not None else 'GET')
        request_headers = dict(headers or {})
        if path.startswith('/portal') and method == 'POST' and origin is not None:
            request_headers['Origin'] = self.origin if origin == 'configured' else origin
        if token is not None:
            request_headers['Authorization'] = 'Bearer ' + token
        arguments = {'data': raw, 'content_type': mimetype} if raw is not None else {'json': body}
        response = (client or self.client).open('/api/v1' + path, method=method,
            base_url=base_url or self.origin, headers=request_headers, **arguments)
        self.assertEqual(response.status_code, status, (method, path, response.status_code))
        self.assertEqual(response.headers.get('Cache-Control'), 'no-store')
        self.assertEqual(response.headers.get('Referrer-Policy'), 'no-referrer')
        self.assertNotIn('Set-Cookie', response.headers)
        self.assertNotIn('Access-Control-Allow-Origin', response.headers)
        return response

    def staff_call(self, path, body=None, **options):
        return self.call(path, body, token=self.staff, **options)

    @staticmethod
    def req(**values):
        return {'request_id': uuid.uuid4().hex, **values}

    def access(self):
        self.staff_call('/business/commercial/settings', self.req(revision=0,
            company_name='Synthetic seller', address_line='Synthetic seller street 1',
            postal_code='10115', city='Berlin', country='DE', vat_id='DE123456789',
            email='seller@example.test', issuing_enabled=False, issuer_mode='own', einvoice_format='none'))
        project = self.staff_call('/projects', {'name': 'Synthetic project', 'customer': 'Synthetic buyer'}, status=201).json['id']
        draft = self.staff_call('/business/documents', self.req(project_id=project, kind='offer',
            title='Synthetic offer', issue_date='2026-11-02', due_date='2026-11-16',
            buyer={'name': 'Synthetic buyer', 'address_line': 'Synthetic buyer street 2',
                   'postal_code': '10117', 'city': 'Berlin', 'country': 'DE'},
            positions=[{'description': 'Synthetic service', 'quantity': '1', 'unit': 'C62',
                        'unit_price_net': '100.00', 'tax_rate': '19'}])).json
        final = self.staff_call('/business/documents/' + draft['id'] + '/finalize',
            self.req(revision=draft['revision'])).json
        source = self.staff_call('/business/portal/grants?offer_id=' + final['id']).json['source']
        grant = self.staff_call('/business/portal/grants', self.req(
            **{key: source[key] for key in ('offer_id', 'source_revision', 'content_hash', 'pdf_hash')},
            recipient_name='Synthetic buyer representative', recipient_email='buyer@example.test',
            expires_in_days=7, confirmation=True), status=201).json
        invitation = {'grant_id': grant['grant']['id'],
                      'key': parse_qs(urlsplit(grant['portal_url']).fragment)['key'][0]}
        session = self.call('/portal/sessions', invitation, status=201).json
        return dict(grant=grant['grant'], invitation=invitation, token=session['token'],
                    expires_at=session['expires_at'], source=source, offer=final)

    def test_strict_json_rejects_ambiguous_nonfinite_compressed_and_oversized_inputs(self):
        invalid = [('{', 'application/json', {}, 400),
            ('[]', 'application/json', {}, 400),
            ('{"grant_id":"x","grant_id":"y","key":"z"}', 'application/json', {}, 400),
            ('{"grant_id":"x","key":NaN}', 'application/json', {}, 400),
            ('{"grant_id":"x","key":Infinity}', 'application/json', {}, 400),
            ('{"grant_id":"x","key":{"secret":1,"secret":2}}', 'application/json', {}, 400),
            ('{"grant_id":"x","key":"z","customer_id":"x"}', 'application/json', {}, 400),
            ('{}', 'text/plain', {}, 415),
            ('{}', 'application/json', {'Content-Encoding': 'gzip'}, 400),
            (b'\xff', 'application/json', {}, 400),
            ('[' * 1500 + ']' * 1500, 'application/json', {}, 400),
            (' ' * (MAX_BODY_BYTES + 1), 'application/json', {}, 413)]
        for index, (raw, mimetype, headers, status) in enumerate(invalid):
            with self.subTest(case=index):
                # Distinct synthetic peers test parser behavior independently
                # of the stricter ten-attempt session admission budget.
                self.call('/portal/sessions', raw=raw, mimetype=mimetype,
                    headers={**headers, 'X-Forwarded-For': '192.0.2.' + str(index + 1)}, status=status)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_portal_sessions').fetchone()[0], 0)

    def test_origin_host_methods_query_and_body_are_closed_with_security_headers(self):
        for origin in (None, 'null', 'http://portal.example.test', 'https://foreign.example.test',
                       self.origin + '/', self.origin + ':443'):
            self.call('/portal/logout', {}, origin=origin, status=403)
        self.call('/portal/offer', headers={'Origin': 'https://foreign.example.test'}, status=403)
        self.call('/portal/offer', base_url='http://portal.example.test', status=400)
        self.call('/portal/offer', base_url='https://foreign.example.test', status=400)
        for method in ('POST', 'HEAD', 'OPTIONS', 'PATCH', 'DELETE'):
            response = self.call('/portal/offer', method=method, status=405)
            self.assertEqual(response.headers['Allow'], 'GET')
        self.call('/portal/offer?offer_id=a&offer_id=b', status=400)
        self.call('/portal/offer/pdf?token=SPPT_synthetic', status=400)
        self.call('/portal/offer', raw='{}', method='GET', status=400)
        self.call('/portal/sessions', method='GET', status=405)
        self.call('/portal', status=404)
        self.call('/portal/admin', status=404)
        self.call('/portal/offer', token='SPPT_' + 'a' * 43, status=401)
        for filename in ('portal.html', 'portal.js', 'portal.css'):
            with self.client.get('/office/' + filename, base_url=self.origin) as response:
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
                self.assertIn("frame-ancestors 'none'", response.headers['Content-Security-Policy'])
                self.assertNotIn("'unsafe-inline'", response.headers['Content-Security-Policy'])
                self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(self.client.get('/office/business_portal.py', base_url=self.origin).status_code, 404)

    def test_hmac_rate_limits_commit_before_auth_json_origin_and_trust_only_proxy_peer(self):
        stamp = 1_800_000_001
        peer = '203.0.113.7'
        with patch('business_portal.time.time', return_value=stamp):
            for index in range(SESSIONS_PER_WINDOW):
                headers = {'X-Forwarded-For': '198.51.100.' + str(index) + ', ' + peer}
                self.call('/portal/sessions', raw='{}', headers=headers, status=400)
            limited = self.call('/portal/sessions', raw='{}',
                headers={'X-Forwarded-For': 'different-untrusted-prefix, ' + peer}, status=429)
            self.assertIn('Retry-After', limited.headers)
            counters = self.office.db.execute('SELECT * FROM business_portal_rate_counters').fetchall()
            self.assertEqual(sorted(row['attempts'] for row in counters), [11, 11])
            self.assertTrue(all(len(row['key_hash']) == 64 for row in counters))
            self.assertFalse(self.office.db.in_transaction)
            self.assertNotIn(peer, repr([tuple(row) for row in counters]))
            self.call('/portal/sessions', raw='{}', headers={'X-Forwarded-For': '203.0.113.8'}, status=400)
        with patch('business_portal.time.time', return_value=stamp + 61):
            self.call('/portal/sessions', raw='{}', headers={'X-Forwarded-For': peer}, status=400)

        # Authentication and Origin failures also consume committed budgets.
        with patch('business_portal.time.time', return_value=stamp + 121):
            for _ in range(DECISIONS_PER_WINDOW):
                self.call('/portal/offer/decision', {}, origin=None, status=403)
            self.call('/portal/offer/decision', {}, origin=None, status=429)
        with patch('business_portal.time.time', return_value=stamp + 181):
            for _ in range(REQUESTS_PER_WINDOW):
                self.call('/portal/offer', status=401)
            self.call('/portal/offer', status=429)

    def test_expiry_logout_and_explicit_token_prefixes_are_enforced_through_http(self):
        access = self.access()
        self.call('/portal/offer', token=access['token'])
        self.call('/portal/offer', token=self.staff, status=401)
        self.call('/portal/offer', token=access['invitation']['key'], status=401)
        self.call('/projects', token=access['token'], status=401)
        self.call('/portal/sessions', access['invitation'], token=self.staff, status=401)
        future = datetime.fromisoformat(access['expires_at']) + timedelta(seconds=1)
        with patch('business_portal.Portal', return_value=Portal(self.office, clock=lambda: future)):
            self.call('/portal/offer', token=access['token'], status=401)
            self.call('/portal/offer/pdf', token=access['token'], status=401)
        future = datetime.fromisoformat(access['grant']['expires_at']) + timedelta(seconds=1)
        with patch('business_portal.Portal', return_value=Portal(self.office, clock=lambda: future)):
            self.call('/portal/sessions', access['invitation'], status=401)
        self.call('/portal/logout', {}, token=access['token'])
        self.call('/portal/logout', {}, token=access['token'])
        self.call('/portal/offer', token=access['token'], status=401)
        reopened = self.call('/portal/sessions', access['invitation'], status=201).json['token']
        self.call('/portal/offer', token=reopened)

    def test_previous_registry_returns_503_without_request_migration_or_internal_details(self):
        previous = tuple(spec for spec in business_schema.registry() if spec.name != 'business_portal')
        with patch.object(business_schema, 'registry', return_value=previous):
            old = Office(self.directory / 'old-registry.sqlite3')
        self.addCleanup(old.db.close)
        old.db.executescript(MFA_SCHEMA)
        old_client = create_app(office=old, key=self.key, host='portal.example.test', storage_config={}).test_client()
        before = '\n'.join(old.db.iterdump())
        response = self.call('/portal/sessions', {}, status=503, client=old_client)
        self.assertEqual(response.json, {'error': 'Portal vorübergehend nicht verfügbar.'})
        self.assertEqual('\n'.join(old.db.iterdump()), before)
        self.assertIsNone(old.db.execute("SELECT name FROM sqlite_master WHERE name='business_portal_rate_counters'").fetchone())
        # A genuine legacy-only installation is a distinct unavailable case.
        with patch('business_schema.ensure_sqlite_schema'):
            legacy = Office(self.directory / 'legacy.sqlite3')
        self.addCleanup(legacy.db.close)
        legacy.db.executescript(MFA_SCHEMA)
        legacy_client = create_app(office=legacy, key=self.key, host='portal.example.test', storage_config={}).test_client()
        legacy_before = '\n'.join(legacy.db.iterdump())
        self.call('/portal/offer', status=404, client=legacy_client)
        self.assertEqual('\n'.join(legacy.db.iterdump()), legacy_before)
        self.assertEqual('\n'.join(old.db.iterdump()), before)

    def test_actual_sqlite_restore_revokes_old_backup_links_but_retains_recorded_decision_and_original_pdf(self):
        access = self.access()
        viewed = self.call('/portal/offer', token=access['token']).json
        decision_body = self.req(content_hash=viewed['offer']['content_hash'], pdf_hash=viewed['offer']['pdf_hash'],
            decision='accepted', declared_name='Synthetic buyer representative',
            statement_version=viewed['statements']['version'], confirmation=True)
        decision = self.call('/portal/offer/decision', decision_body, token=access['token'], status=201).json
        adoption = self.staff_call('/business/portal/offers/' + access['offer']['id'] + '/adopt', self.req(
            decision_id=decision['id'], confirmation=True,
            **{key: access['source'][key] for key in ('source_revision', 'content_hash', 'pdf_hash')}), status=201).json
        preserved_tables = ('business_documents', 'business_document_archives', 'business_document_numbers',
            'business_portal_grants', 'business_portal_decisions', 'business_portal_adoptions')
        expected = {name: [tuple(row) for row in self.office.db.execute('SELECT * FROM ' + name)] for name in preserved_tables}
        pdf = self.call('/portal/offer/pdf', token=access['token']).data
        saved = backup(self.path, self.directory / 'backup.sqlite3')
        self.staff_call('/business/portal/grants/' + access['grant']['id'] + '/revoke',
            self.req(reason='Synthetic revocation after backup', confirmation=True))
        restored_path = restore(saved, self.directory / 'restored.sqlite3')
        restored = Office(restored_path)
        self.addCleanup(restored.db.close)
        self.assertTrue(business_schema.validate_integrity(restored))
        for name, rows in expected.items():
            self.assertEqual([tuple(row) for row in restored.db.execute('SELECT * FROM ' + name)], rows, name)
        for name in ('sessions', 'business_portal_sessions', 'business_portal_rate_counters'):
            self.assertEqual(restored.db.execute('SELECT COUNT(*) FROM ' + name).fetchone()[0], 0, name)
        self.assertEqual(restored.db.execute('SELECT active FROM business_portal_principals').fetchone()[0], 0)
        revoked = restored.db.execute('SELECT * FROM business_portal_revocations').fetchone()
        self.assertEqual((revoked['kind'], revoked['revoked_by']), ('restore', None))
        self.assertEqual(restored.db.execute('SELECT document_id FROM business_portal_adoptions').fetchone()[0], adoption['document_id'])
        self.assertEqual(restored.db.execute('SELECT pdf FROM business_document_archives WHERE document_id=?',
            (access['offer']['id'],)).fetchone()[0], pdf)
        restored_client = create_app(office=restored, key=self.key, host='portal.example.test', storage_config={}).test_client()
        self.call('/portal/offer', token=access['token'], status=401, client=restored_client)
        self.call('/portal/sessions', access['invitation'], status=401, client=restored_client)
        self.call('/projects', token=self.staff, status=401, client=restored_client)
        # The backup and original archive are not rewritten by restore.
        self.assertEqual(hashlib.sha256(pdf).hexdigest(), access['source']['pdf_hash'])
        self.assertEqual(self.office.db.execute('SELECT pdf FROM business_document_archives WHERE document_id=?',
            (access['offer']['id'],)).fetchone()[0], pdf)

    def test_restore_sanitizer_failure_removes_only_new_target_and_preserves_source_access(self):
        access = self.access()
        saved = backup(self.path, self.directory / 'backup.sqlite3')
        saved_hash = hashlib.sha256(saved.read_bytes()).hexdigest()
        target = self.directory / 'failed-restore.sqlite3'
        with patch('business_portal.sanitize_after_restore', side_effect=RuntimeError('Synthetic restore failure')):
            with self.assertRaisesRegex(RuntimeError, 'Synthetic restore failure'):
                restore(saved, target)
        self.assertFalse(target.exists())
        self.assertEqual(hashlib.sha256(saved.read_bytes()).hexdigest(), saved_hash)
        self.call('/portal/offer', token=access['token'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_portal_revocations').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
