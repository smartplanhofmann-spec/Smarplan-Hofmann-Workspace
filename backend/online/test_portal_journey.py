"""Independent offer-portal journeys through real HTTP, MFA and SQLite archives.

Only synthetic companies and customers are used. Eight journeys use Flask's
HTTPS-aware test client; the ninth uses a real loopback TLS socket with an
explicitly trusted synthetic CA and hostname verification. Final offers use
the normal Documents policy and renderer, without owner impersonation in the
customer API. PostgreSQL, deployed proxy and browser acceptance are separate.
"""
import hashlib
import http.client
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import socket
import ssl
import tempfile
import threading
import time
import unittest
from urllib.parse import parse_qs, urlsplit
import uuid

from cryptography.fernet import Fernet
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from werkzeug.serving import make_server

from core import Office
from backend.backup import backup
from backend.restore import restore
from online.auth import totp
from online.instance import bind
from online.storage import Storage
from online.test_instance_isolation import MFA_SCHEMA
from online.web import create_app


def request(**values):
    return {'request_id': uuid.uuid4().hex, **values}


class PortalJourneyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic-portal-journey-')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.company = self.new_company('alpha')

    def new_company(self, label):
        office = Office(self.directory / (label + '.sqlite3'))
        self.addCleanup(office.db.close)
        office.db.executescript(MFA_SCHEMA)
        office.add_user('owner@example.test', 'Synthetic-portal-owner-password-123', 'owner')
        company = dict(label=label, office=office, host=label + '.example.test',
                       key=Fernet.generate_key(), instance_id=uuid.uuid4().hex,
                       root=self.directory / (label + '-files'), mfa={})
        storage = Storage(office, company['key'], company['host'],
                          config={'server': {'path': str(company['root'])}})
        bind(office, company['instance_id'], company['host'], company['key'], storage)
        self.open_app(company, storage=storage)
        company['token'] = self.login(company, 'owner@example.test', 'Synthetic-portal-owner-password-123')
        self.call(company, '/business/commercial/settings', request(revision=0,
            company_name='Synthetic ' + label + ' company', address_line='Synthetic seller street 1',
            postal_code='10115', city='Berlin', country='DE', vat_id='DE123456789',
            email=label + '@example.test', issuing_enabled=False, issuer_mode='own', einvoice_format='none'))
        preview = self.call(company, '/business/commercial/pricing/preview', request(
            base_cost_net='13.37', labor_hours='2', hourly_cost_net='31.89',
            overhead_percent='17', markup_percent='29', quantity='1', kind='material', unit='C62')).json
        article = self.call(company, '/business/articles', request(code='INTERNAL-COST-' + label,
            name='Portal-visible equipment', pricing=preview['inputs'],
            pricing_hash=preview['preview_hash'], price_confirmation=True)).json
        company['customers'] = []
        for label in ('One', 'Two'):
            name = 'Synthetic ' + company['label'] + ' buyer ' + label
            project = self.call(company, '/projects', {'name': name + ' project', 'customer': name}, status=201).json['id']
            draft = self.call(company, '/business/documents', request(project_id=project, kind='offer',
                title='Synthetic offer for ' + name, issue_date='2026-11-02', due_date='2026-11-16',
                buyer={'name': name, 'address_line': 'Synthetic buyer street 2', 'postal_code': '10117',
                       'city': 'Berlin', 'country': 'DE', 'email': label.lower() + '@example.test'},
                intro='Synthetic public introduction', notes='Synthetic public terms',
                positions=[{'article_id': article['id'], 'article_revision': article['revision'], 'quantity': '1'}])).json
            final = self.call(company, '/business/documents/' + draft['id'] + '/finalize',
                              request(revision=draft['revision'])).json
            self.assertEqual(final['status'], 'final')
            self.assertIn('pricing_snapshot', final['positions'][0])
            pdf = self.call(company, '/business/documents/' + final['id'] + '/pdf').data
            self.assertTrue(pdf.startswith(b'%PDF-'))
            company['customers'].append(dict(project=project, offer=final, pdf=pdf, name=name))
        return company

    def open_app(self, company, *, storage=None):
        storage = storage or Storage(company['office'], company['key'], company['host'],
            config={'server': {'path': str(company['root'])}})
        company['app'] = create_app(office=company['office'], key=company['key'], host=company['host'],
                                   instance_id=company['instance_id'], storage=storage)
        company['client'] = company['app'].test_client()

    def call(self, company, path, body=None, *, token='owner', status=200, method=None,
             origin='configured', headers=None, host=None):
        token = company.get('token') if token == 'owner' else token
        method = method or ('POST' if body is not None else 'GET')
        request_headers = {'Authorization': 'Bearer ' + token} if token else {}
        if path.startswith('/portal/') and method == 'POST' and origin is not None:
            request_headers['Origin'] = 'https://' + company['host'] if origin == 'configured' else origin
        request_headers.update(headers or {})
        response = company['client'].open('/api/v1' + path, method=method,
            base_url='https://' + (host or company['host']), json=body, headers=request_headers)
        # Failure diagnostics deliberately omit tokens, invitation URLs and bodies.
        self.assertEqual(response.status_code, status, (method, path, response.status_code))
        return response

    def login(self, company, email, password, *, advance=False):
        pending = self.call(company, '/login', {'email': email, 'password': password}, token=None).json
        self.assertNotIn('token', pending)
        if pending.get('enrollment'):
            company['mfa'][email] = pending['enrollment']['secret']
        code = totp(company['mfa'][email], int(time.time() // 30) + int(advance))
        return self.call(company, '/login/verify', {'challenge': pending['challenge'], 'code': code}, token=None).json['token']

    def source(self, company, customer):
        return self.call(company, '/business/portal/grants?offer_id=' + customer['offer']['id']).json['source']

    def grant(self, company, customer, *, token='owner'):
        source = self.source(company, customer)
        body = request(**{key: source[key] for key in ('offer_id', 'source_revision', 'content_hash', 'pdf_hash')},
            recipient_name=customer['name'], recipient_email='recipient@example.test',
            expires_in_days=7, confirmation=True)
        result = self.call(company, '/business/portal/grants', body, token=token, status=201).json
        self.assertTrue(result['link_available'])
        parts = urlsplit(result['portal_url'])
        self.assertEqual(parts.scheme + '://' + parts.netloc, 'https://' + company['host'])
        self.assertEqual((parts.path, parts.query), ('/office/portal.html', ''))
        fragment = parse_qs(parts.fragment)
        self.assertEqual(set(fragment), {'grant', 'key'})
        self.assertEqual(fragment['grant'], [result['grant']['id']])
        return dict(result=result, body=body, id=result['grant']['id'], key=fragment['key'][0], source=source)

    def session(self, company, grant):
        return self.call(company, '/portal/sessions', {'grant_id': grant['id'], 'key': grant['key']},
                         token=None, status=201).json['token']

    def decide(self, company, token, *, decision='accepted'):
        view = self.call(company, '/portal/offer', token=token).json
        body = request(content_hash=view['offer']['content_hash'], pdf_hash=view['offer']['pdf_hash'],
            decision=decision, declared_name='Synthetic customer representative',
            statement_version=view['statements']['version'], confirmation=True)
        result = self.call(company, '/portal/offer/decision', body, token=token, status=201).json
        return body, result

    def adoption_body(self, grant, decision):
        return request(decision_id=decision['id'], confirmation=True,
            **{key: grant['source'][key] for key in ('source_revision', 'content_hash', 'pdf_hash')})

    def permission(self, company, user, name, project, *, effect='allow', revision=0):
        return self.call(company, '/business/settings/permissions', request(user_id=user, permission=name,
            scope=project, effect=effect, revision=revision)).json

    def test_two_customers_and_two_bound_company_databases_isolate_tokens_sources_and_original_pdfs(self):
        first, second = self.company, self.new_company('beta')
        grants = [(first, self.grant(first, customer)) for customer in first['customers']]
        grants.append((second, self.grant(second, second['customers'][0])))
        tokens = [self.session(company, grant) for company, grant in grants]
        for (company, grant), token in zip(grants, tokens):
            view = self.call(company, '/portal/offer', token=token).json
            self.assertEqual(view['offer']['id'], grant['source']['offer_id'])
            self.assertEqual(view['offer']['content_hash'], grant['source']['content_hash'])
            self.assertTrue(view['actions_allowed'])
            forbidden = {'cost_price_net', 'unit_cost_net', 'pricing_snapshot', 'components',
                'source_articles', 'source_id', 'source_revision', 'source_hash', 'article_id',
                'article_revision', 'margin_percent', 'profit_net', 'hourly_cost_net', 'cost_known',
                'issuer_mode', 'issuing_enabled', 'cutover_ack', 'einvoice_format', 'project_id', 'customer_id'}
            def check(value):
                if isinstance(value, dict):
                    self.assertFalse(set(value) & forbidden, 'Internal source or financial field in customer DTO')
                    for child in value.values(): check(child)
                elif isinstance(value, list):
                    for child in value: check(child)
            check(view['offer'])
            download = self.call(company, '/portal/offer/pdf', token=token)
            original = next(customer['pdf'] for customer in company['customers']
                            if customer['offer']['id'] == grant['source']['offer_id'])
            self.assertEqual(download.data, original)
            self.assertEqual(hashlib.sha256(download.data).hexdigest(), grant['source']['pdf_hash'])
            self.assertIn('attachment', download.headers['Content-Disposition'])
            self.assertEqual(download.headers['Cache-Control'], 'no-store')
            self.assertNotIn('Set-Cookie', download.headers)
            self.call(company, '/projects', token=token, status=401)
            self.call(company, '/portal/offer?offer_id=' + uuid.uuid4().hex, token=token, status=400)
            self.call(company, '/portal/projects', token=token, status=404)
        self.call(first, '/portal/offer', token=tokens[2], status=401)
        self.call(second, '/portal/offer', token=tokens[0], status=401)
        self.call(first, '/portal/offer', token=first['token'], status=401)
        grant = self.call(first, '/offline/access/v2', {}, status=201).json
        binding = grant['binding']['instance_id'] + ':' + grant['binding']['account_id']
        self.call(first, '/portal/offer', token=grant['token'],
                  headers={'X-Smartplan-Offline-Binding': binding}, status=401)
        self.call(first, '/portal/sessions', {'grant_id': grants[1][1]['id'], 'key': grants[0][1]['key']},
                  token=None, status=401)
        self.call(first, '/portal/offer', token=tokens[0], host=second['host'], status=400)

    def test_one_time_staff_link_receipt_customer_decision_and_adoption_are_immutable_and_idempotent(self):
        company, customer = self.company, self.company['customers'][0]
        grant = self.grant(company, customer)
        repeated = self.call(company, '/business/portal/grants', grant['body'], status=201).json
        self.assertEqual(repeated['grant'], grant['result']['grant'])
        self.assertFalse(repeated['link_available'])
        self.assertNotIn('portal_url', repeated)
        token = self.session(company, grant)
        before = self.call(company, '/portal/offer', token=token).json
        self.assertIsNone(before['decision'])
        self.call(company, '/portal/offer/pdf', token=token)
        self.assertEqual(company['office'].db.execute('SELECT COUNT(*) FROM business_portal_decisions').fetchone()[0], 0)
        bad = request(content_hash='0' * 64, pdf_hash=grant['source']['pdf_hash'], decision='accepted',
            declared_name='Synthetic customer', statement_version=before['statements']['version'], confirmation=True)
        self.call(company, '/portal/offer/decision', bad, token=token, status=409)
        body, decision = self.decide(company, token)
        self.assertEqual(self.call(company, '/portal/offer/decision', body, token=token, status=201).json, decision)
        self.call(company, '/portal/offer/decision', {**body, 'decision': 'declined'}, token=token, status=409)
        self.call(company, '/portal/offer/decision', {**body, 'request_id': uuid.uuid4().hex}, token=token, status=409)
        self.assertEqual(decision['statement_text'], before['statements']['accepted'])
        self.assertEqual(company['office'].db.execute('SELECT COUNT(*) FROM business_portal_decisions').fetchone()[0], 1)
        adoption_body = self.adoption_body(grant, decision)
        path = '/business/portal/offers/' + customer['offer']['id'] + '/adopt'
        adoption = self.call(company, path, adoption_body, status=201).json
        self.assertEqual(self.call(company, path, adoption_body, status=201).json, adoption)
        self.call(company, path, {**adoption_body, 'request_id': uuid.uuid4().hex}, status=409)
        target = self.call(company, '/business/documents/' + adoption['document_id']).json
        self.assertEqual((target['kind'], target['status'], target['project_id']),
                         ('order_confirmation', 'draft', customer['project']))
        self.assertEqual(self.call(company, '/business/documents/' + customer['offer']['id']).json, customer['offer'])
        self.assertEqual(self.call(company, '/business/documents/' + customer['offer']['id'] + '/pdf').data, customer['pdf'])
        dump = '\n'.join(company['office'].db.iterdump())
        self.assertFalse(grant['key'] in dump, 'Invitation secret persisted')
        self.assertFalse(token in dump, 'Portal session secret persisted')
        self.open_app(company)
        after = self.call(company, '/portal/offer', token=token).json
        self.assertEqual(after['decision'], decision)
        self.assertFalse(after['actions_allowed'])

    def test_known_customer_binding_change_and_revocation_reject_sessions_and_decision_replay(self):
        company, first, second = self.company, *self.company['customers']
        grant = self.grant(company, first)
        token = self.session(company, grant)
        body, decision = self.decide(company, token, decision='declined')
        second_customer = self.source(company, second)['customer_id']
        self.call(company, '/projects/' + first['project'] + '/customer', {'customer_id': second_customer})
        self.call(company, '/portal/offer', token=token, status=401)
        self.call(company, '/portal/offer/pdf', token=token, status=401)
        self.call(company, '/portal/offer/decision', body, token=token, status=401)
        self.call(company, '/projects/' + first['project'] + '/customer', {'customer_id': grant['source']['customer_id']})
        self.assertEqual(self.call(company, '/portal/offer', token=token).json['decision'], decision)
        self.call(company, '/business/portal/grants/' + grant['id'] + '/revoke',
                  request(reason='Synthetic explicit revocation', confirmation=True))
        self.call(company, '/portal/offer/decision', body, token=token, status=401)
        self.call(company, '/portal/sessions', {'grant_id': grant['id'], 'key': grant['key']}, token=None, status=401)

    def test_adoption_rollback_and_existing_manual_order_never_duplicate_targets(self):
        company, first, second = self.company, *self.company['customers']
        grant = self.grant(company, first)
        _, decision = self.decide(company, self.session(company, grant))
        body = self.adoption_body(grant, decision)
        path = '/business/portal/offers/' + first['offer']['id'] + '/adopt'
        before = company['office'].db.execute('SELECT COUNT(*) FROM business_documents').fetchone()[0]
        company['office'].db.execute("CREATE TRIGGER synthetic_portal_adoption_failure BEFORE INSERT ON business_portal_adoptions "
            "BEGIN SELECT RAISE(ABORT,'synthetic adoption failure'); END")
        self.call(company, path, body, status=500)
        self.assertEqual(company['office'].db.execute('SELECT COUNT(*) FROM business_documents').fetchone()[0], before)
        self.assertEqual(company['office'].db.execute('SELECT COUNT(*) FROM business_portal_adoptions').fetchone()[0], 0)
        company['office'].db.execute('DROP TRIGGER synthetic_portal_adoption_failure')
        self.call(company, path, body, status=201)
        manual = self.call(company, '/business/documents/' + second['offer']['id'] + '/convert',
            request(revision=second['offer']['revision'], target_kind='order_confirmation')).json
        other = self.grant(company, second)
        _, accepted = self.decide(company, self.session(company, other))
        self.call(company, '/business/portal/offers/' + second['offer']['id'] + '/adopt',
                  self.adoption_body(other, accepted), status=409)
        self.assertEqual(self.call(company, '/business/documents/' + manual['id']).json, manual)

    def test_origin_token_boundary_and_failed_session_attempts_are_enforced(self):
        company, customer = self.company, self.company['customers'][0]
        grant = self.grant(company, customer)
        payload = {'grant_id': grant['id'], 'key': grant['key']}
        self.call(company, '/portal/sessions', payload, token=None, origin=None, status=403)
        self.call(company, '/portal/sessions', payload, token=None, origin='https://foreign.example.test', status=403)
        self.call(company, '/portal/sessions', payload, token=company['token'], status=401)
        self.call(company, '/portal/sessions', {**payload, 'customer_id': uuid.uuid4().hex}, token=None, status=400)
        for _ in range(6):
            self.call(company, '/portal/sessions', {**payload, 'key': 'SPPI_' + 'x' * 43}, token=None, status=401)
        self.call(company, '/portal/sessions', payload, token=None, status=429)
        self.assertEqual(company['office'].db.execute('SELECT COUNT(*) FROM business_portal_sessions').fetchone()[0], 0)

    def test_fresh_staff_permissions_precede_saved_grant_and_adoption_receipts(self):
        company, customer = self.company, self.company['customers'][0]
        email, password = 'manager@example.test', 'Synthetic-portal-manager-password-123'
        user = self.call(company, '/users', {'email': email, 'password': password, 'role': 'manager'}, status=201).json['id']
        self.call(company, '/assignments', {'project_id': customer['project'], 'user_id': user})
        token = self.login(company, email, password)
        for permission in ('portal.manage', 'finance.read', 'finance.write'):
            self.permission(company, user, permission, customer['project'])
        grant = self.grant(company, customer, token=token)
        self.permission(company, user, 'portal.manage', customer['project'], effect='deny', revision=1)
        self.call(company, '/business/portal/grants', grant['body'], token=token, status=403)
        self.call(company, '/business/portal/grants?offer_id=' + customer['offer']['id'], token=token, status=403)
        self.permission(company, user, 'portal.manage', customer['project'], revision=2)
        repeated = self.call(company, '/business/portal/grants', grant['body'], token=token, status=201).json
        self.assertFalse(repeated['link_available'])
        _, decision = self.decide(company, self.session(company, grant))
        body = self.adoption_body(grant, decision)
        path = '/business/portal/offers/' + customer['offer']['id'] + '/adopt'
        adoption = self.call(company, path, body, token=token, status=201).json
        self.permission(company, user, 'finance.write', customer['project'], effect='deny', revision=1)
        self.call(company, path, body, token=token, status=403)
        self.assertEqual(company['office'].db.execute('SELECT COUNT(*) FROM business_portal_adoptions').fetchone()[0], 1)
        self.assertEqual(self.call(company, '/business/documents/' + adoption['document_id']).json['status'], 'draft')

    def test_disabled_documents_keep_history_and_security_revocation_available(self):
        from business_schema import set_mode
        company, customer = self.company, self.company['customers'][0]
        grant = self.grant(company, customer)
        token = self.session(company, grant)
        view = self.call(company, '/portal/offer', token=token).json
        body = request(content_hash=view['offer']['content_hash'], pdf_hash=view['offer']['pdf_hash'],
            decision='accepted', declared_name='Synthetic customer',
            statement_version=view['statements']['version'], confirmation=True)
        organization = self.call(company, '/business/organization').json
        modules = {name: {'visible': value['visibility_override'], 'enabled': value['enabled']}
                   for name, value in organization['modules'].items()}
        modules['documents']['enabled'] = False
        self.call(company, '/business/organization', request(revision=organization['revision'],
                  needs=organization['needs'], modules=modules))
        self.assertFalse(self.call(company, '/portal/offer', token=token).json['actions_allowed'])
        self.assertEqual(self.call(company, '/portal/offer/pdf', token=token).data, customer['pdf'])
        self.call(company, '/portal/offer/decision', body, token=token, status=423)
        self.call(company, '/business/portal/grants', grant['body'], status=423)
        set_mode(company['office'], 'legacy')
        revoked = self.call(company, '/business/portal/grants/' + grant['id'] + '/revoke',
                            request(reason='Synthetic security revocation', confirmation=True)).json
        self.assertEqual(revoked['status'], 'revoked')
        self.call(company, '/portal/offer', token=token, status=401)
        self.assertTrue(self.call(company, '/portal/logout', {}, token=token).json['logged_out'])

    def test_actual_sqlite_restore_kills_old_link_and_session_but_retains_accepted_source(self):
        company, customer = self.company, self.company['customers'][0]
        grant = self.grant(company, customer)
        portal_token = self.session(company, grant)
        _, decision = self.decide(company, portal_token)
        source_path = self.directory / 'alpha.sqlite3'
        old_backup = backup(source_path, self.directory / 'before-revocation.sqlite3')
        self.call(company, '/business/portal/grants/' + grant['id'] + '/revoke',
                  request(reason='Synthetic revocation after backup', confirmation=True))
        restored = restore(old_backup, self.directory / 'restored-alpha.sqlite3')
        office = Office(restored)
        self.addCleanup(office.db.close)
        clone = {**company, 'office': office}
        self.open_app(clone)
        self.call(clone, '/projects', token=company['token'], status=401)
        self.call(clone, '/portal/offer', token=portal_token, status=401)
        self.call(clone, '/portal/sessions', {'grant_id': grant['id'], 'key': grant['key']}, token=None, status=401)
        clone['token'] = self.login(clone, 'owner@example.test', 'Synthetic-portal-owner-password-123', advance=True)
        history = self.call(clone, '/business/portal/grants?offer_id=' + customer['offer']['id']).json
        self.assertEqual(history['decision'], decision)
        self.assertEqual(history['items'][0]['revocation']['kind'], 'restore')
        self.assertIsNone(history['items'][0]['revocation']['revoked_by'])
        self.assertFalse(history['items'][0]['principal']['active'])
        self.assertEqual(self.call(clone, '/business/documents/' + customer['offer']['id']).json, customer['offer'])
        self.assertEqual(self.call(clone, '/business/documents/' + customer['offer']['id'] + '/pdf').data, customer['pdf'])

    def test_real_tls_socket_trusts_only_synthetic_ca_and_correct_hostname(self):
        company, customer = self.company, self.company['customers'][0]
        grant = self.grant(company, customer)
        now = datetime.now(timezone.utc)
        ca_key, server_key = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
        ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Synthetic portal test CA')])
        ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
              .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
              .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=1))
              .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
              .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                  key_encipherment=False, data_encipherment=False, key_agreement=False,
                  key_cert_sign=True, crl_sign=True, encipher_only=None, decipher_only=None), critical=True)
              .sign(ca_key, hashes.SHA256()))
        server_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, company['host'])])
        certificate = (x509.CertificateBuilder().subject_name(server_name).issuer_name(ca_name)
              .public_key(server_key.public_key()).serial_number(x509.random_serial_number())
              .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=1))
              .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
              .add_extension(x509.SubjectAlternativeName([x509.DNSName(company['host'])]), critical=False)
              .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
              .sign(ca_key, hashes.SHA256()))
        ca_path, cert_path, key_path = [self.directory / name for name in ('test-ca.pem', 'server.pem', 'server.key')]
        ca_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
        cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(server_key.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        key_path.chmod(0o600)
        server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_context.load_cert_chain(cert_path, key_path)
        trusted = ssl.create_default_context(cafile=str(ca_path))
        self.assertEqual(trusted.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(trusted.check_hostname)
        server = make_server('127.0.0.1', 0, company['app'], ssl_context=server_context)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            def tls_request(path, *, body=None, token=None):
                payload = json.dumps(body).encode('utf-8') if body is not None else b''
                method = 'POST' if body is not None else 'GET'
                headers = [method + ' /api/v1/portal/' + path + ' HTTP/1.1',
                    'Host: ' + company['host'], 'Connection: close',
                    'Content-Length: ' + str(len(payload))]
                if body is not None:
                    headers += ['Content-Type: application/json', 'Origin: https://' + company['host']]
                if token:
                    headers.append('Authorization: Bearer ' + token)
                with socket.create_connection(('127.0.0.1', server.server_port), timeout=5) as raw:
                    with trusted.wrap_socket(raw, server_hostname=company['host']) as connection:
                        self.assertIsNotNone(connection.cipher())
                        connection.sendall(('\r\n'.join(headers) + '\r\n\r\n').encode('ascii') + payload)
                        response = http.client.HTTPResponse(connection)
                        response.begin()
                        return response.status, dict(response.getheaders()), response.read()

            for context, hostname in ((ssl.create_default_context(), company['host']),
                                      (trusted, 'different.example.test')):
                with self.subTest(hostname=hostname), self.assertRaises(ssl.SSLCertVerificationError):
                    with socket.create_connection(('127.0.0.1', server.server_port), timeout=5) as raw:
                        with context.wrap_socket(raw, server_hostname=hostname):
                            self.fail('Untrusted certificate or wrong hostname was accepted')
            status, _, raw = tls_request('sessions', body={'grant_id': grant['id'], 'key': grant['key']})
            self.assertEqual(status, 201)
            token = json.loads(raw)['token']
            status, headers, raw = tls_request('offer', token=token)
            self.assertEqual(status, 200)
            self.assertEqual(headers['Cache-Control'], 'no-store')
            view = json.loads(raw)
            self.assertEqual(view['offer']['id'], customer['offer']['id'])
            status, _, raw = tls_request('offer/pdf', token=token)
            self.assertEqual((status, raw), (200, customer['pdf']))
            status, _, raw = tls_request('offer/decision', token=token, body=request(
                content_hash=view['offer']['content_hash'], pdf_hash=view['offer']['pdf_hash'],
                decision='accepted', declared_name='Synthetic TLS customer',
                statement_version=view['statements']['version'], confirmation=True))
            self.assertEqual(status, 201)
            self.assertEqual(json.loads(raw)['decision'], 'accepted')
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        self.assertFalse(thread.is_alive())


if __name__ == '__main__':
    unittest.main()
