"""Independent E1b-1 journeys over real loopback HTTPS and password/TOTP MFA.

All company/customer/payment data is synthetic. Only the saved legacy invoice
fixture uses the existing, explicitly test-only SyntheticDocuments issuer.
The application, MFA, source/target permissions, assignment and finance routes
are not patched. Production PostgreSQL issuance is tested separately. TLS uses
an explicitly trusted synthetic CA, with certificate and hostname verification.
No banking, email, tax service or other external provider is contacted.
"""
from datetime import datetime, timedelta, timezone
import http.client
import json
import socket
import ssl
import threading
from types import SimpleNamespace
import unittest
import uuid

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from werkzeug.serving import WSGIRequestHandler, make_server

from business_documents import render_prepared
from business_tests.test_documents import SyntheticDocuments, seed_synthetic_issuer
from online import test_accounting_journey as journey
from online.storage import Storage
from online.web import create_app


request = journey.request
PREFIX = '/business/accounting/allocations/payments/'


def seed_legacy_invoice(office, actor, project, *, net='100.00'):
    """Explicit SQLite-only stored-fixture creation; never patches HTTP policy."""
    documents = SyntheticDocuments(office)
    with office.lock, office.db:
        if documents.settings(actor)['revision'] == 0:
            documents.save_settings(actor, request(revision=0,
                company_name='Synthetic allocation fixture seller',
                address_line='Synthetic seller street 1', postal_code='10115',
                city='Berlin', country='DE', vat_id='DE123456789',
                email='seller@example.test', issuer_mode='own', issuing_enabled=False,
                cutover_ack=True, cutover_date='2026-01-01', einvoice_format='none'))
            seed_synthetic_issuer(documents, actor)
        draft = documents.create(actor, request(project_id=project, kind='invoice',
            title='Synthetic stored allocation invoice', issue_date='2026-11-02',
            due_date='2026-11-02', buyer={'name': 'Synthetic allocation customer',
                'address_line': 'Synthetic buyer street 2', 'postal_code': '10117',
                'city': 'Berlin', 'country': 'DE', 'email': 'buyer@example.test'},
            positions=[{'description': 'Synthetic service', 'quantity': '1',
                'unit': 'HUR', 'unit_price_net': net, 'tax_rate': '19', 'kind': 'labor'}]))
        prepared = documents.prepare_finalization(actor, draft['id'], draft['revision'])
    rendered = render_prepared(prepared)
    with office.lock, office.db:
        return documents.finalize(actor, draft['id'], rendered, uuid.uuid4().hex)


class QuietRequestHandler(WSGIRequestHandler):
    def log(self, type, message, *args):
        pass


class AccountingAllocationsJourneyTests(unittest.TestCase):
    # Borrow setup helpers, not E1a test cases. Every call uses our socket adapter.
    base_setup = journey.AccountingJourneyTests.setUp
    new_company = journey.AccountingJourneyTests.new_company
    login = journey.AccountingJourneyTests.login
    user = journey.AccountingJourneyTests.user
    permission = journey.AccountingJourneyTests.permission
    account_record = journey.AccountingJourneyTests.account_record
    source = journey.AccountingJourneyTests.source
    import_body = journey.AccountingJourneyTests.import_body
    prepare_user = journey.AccountingJourneyTests.prepare_user
    legacy_sources = journey.AccountingJourneyTests.legacy_sources

    def setUp(self):
        self.base_setup()
        self.office = self.company['office']
        self.owner = self.office.user(self.company['token'])
        self.invoice = seed_legacy_invoice(self.office, self.owner, self.company['project'])
        self.customer = self.invoice['customer_id']

    def open_app(self, company, *, storage=None):
        storage = storage or Storage(company['office'], company['key'], company['host'],
            config={'server': {'path': str(company['root'])}})
        app = create_app(office=company['office'], key=company['key'], host=company['host'],
            instance_id=company['instance_id'], storage=storage)
        now = datetime.now(timezone.utc)
        ca_key, server_key = (rsa.generate_private_key(public_exponent=65537, key_size=2048)
                              for _ in range(2))
        ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Synthetic E1b test CA')])
        ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
            .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .sign(ca_key, hashes.SHA256()))
        cert = (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, company['host'])]))
            .issuer_name(ca_name).public_key(server_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(company['host'])]), critical=False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(ca_key, hashes.SHA256()))
        ca_path, cert_path, key_path = [self.directory / (company['label'] + suffix)
            for suffix in ('-ca.pem', '-server.pem', '-server.key')]
        ca_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(server_key.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        key_path.chmod(0o600)
        server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_context.load_cert_chain(cert_path, key_path)
        company['tls'] = ssl.create_default_context(cafile=str(ca_path))
        self.assertTrue(company['tls'].check_hostname)
        self.assertEqual(company['tls'].verify_mode, ssl.CERT_REQUIRED)
        server = make_server('127.0.0.1', 0, app, ssl_context=server_context,
                             request_handler=QuietRequestHandler)
        company['server'] = server
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def close():
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
        self.addCleanup(close)

    def call(self, company, path, body=None, *, token='owner', status=200, method=None):
        token = company.get('token') if token == 'owner' else token
        method = method or ('POST' if body is not None else 'GET')
        payload = json.dumps(body).encode() if body is not None else b''
        headers = [method + ' /api/v1' + path + ' HTTP/1.1', 'Host: ' + company['host'],
                   'Connection: close', 'Content-Length: ' + str(len(payload))]
        if body is not None:
            headers += ['Content-Type: application/json']
        if token:
            headers += ['Authorization: Bearer ' + token]
        with socket.create_connection(('127.0.0.1', company['server'].server_port), timeout=10) as raw:
            with company['tls'].wrap_socket(raw, server_hostname=company['host']) as connection:
                self.assertIsNotNone(connection.cipher())
                connection.sendall(('\r\n'.join(headers) + '\r\n\r\n').encode('ascii') + payload)
                response = http.client.HTTPResponse(connection)
                response.begin()
                result = SimpleNamespace(status_code=response.status, headers=dict(response.getheaders()),
                                         data=response.read())
        # Never print bearer/challenge responses or stored original bytes.
        self.assertIn(result.status_code, status if isinstance(status, tuple) else (status,),
                      (method, path, result.status_code))
        result.json = (json.loads(result.data) if
            result.headers.get('Content-Type', '').startswith('application/json') else None)
        return result

    def project_invoice(self, *, same_customer=True):
        body = {'name': 'Synthetic extra allocation project'}
        body.update({'customer_id': self.customer} if same_customer else {'customer': 'Synthetic other customer'})
        project = self.call(self.company, '/projects', body, status=201).json['id']
        return project, seed_legacy_invoice(self.office, self.owner, project)

    def payment_record(self, *, amount='119.00', kind='receipt', allocations=(), token='owner'):
        body = request(source_id='synthetic-e1b-' + uuid.uuid4().hex, kind=kind, amount=amount,
            currency='EUR', booking_date='2026-11-02', reference='Synthetic confirmed E1b payment',
            allocations=[{'document_id': identifier, 'amount': value} for identifier, value in allocations])
        return self.call(self.company, '/business/finance/payments', body, token=token).json, body

    def imported(self, payment, *, token='owner'):
        source = self.source(self.company, 'payments', payment['id'], token=token)
        body = self.import_body(source)
        event = self.call(self.company, '/business/accounting/events/import-payment',
                          body, token=token, status=201).json
        return source, event, body

    def state(self, payment, *, token='owner'):
        return self.call(self.company, PREFIX + payment['id'], token=token).json

    def preview_body(self, payment, invoice=None, *, amount='47.60', token='owner'):
        invoice = invoice or self.invoice
        state = self.state(payment, token=token)
        candidates = self.call(self.company, PREFIX + payment['id'] + '/candidates', token=token).json
        candidate = next(row for row in candidates['items'] if row['document_id'] == invoice['id'])
        return {'source_hash': state['source_hash'], 'expected_revision': state['revision'],
            'state_hash': state['state_hash'], 'customer_id': candidate['customer_id'],
            'document_id': invoice['id'], 'document_state_hash': candidate['document_state_hash'],
            'amount': amount, 'reason': 'Synthetic explicitly confirmed allocation'}

    def confirmed(self, payment, body, *, token='owner'):
        preview = self.call(self.company, PREFIX + payment['id'] + '/preview', body, token=token).json
        command = request(**body, preview_hash=preview['preview_hash'], confirmation=True)
        entry = self.call(self.company, PREFIX + payment['id'] + '/assign', command,
                          token=token, status=201).json
        return entry, command

    def open_item(self, invoice, *, token='owner'):
        rows = self.call(self.company, '/business/finance/open-items?project_id=' + invoice['project_id'],
                         token=token).json['items']
        return next(row for row in rows if row['id'] == invoice['id'])

    def database(self):
        return '\n'.join(self.office.db.iterdump())

    def test_partial_assignment_updates_effective_finance_but_not_e1a_or_original_rows(self):
        payment, _ = self.payment_record(allocations=[(self.invoice['id'], '11.90')])
        source, event, import_command = self.imported(payment)
        original_rows = self.legacy_sources(self.company)
        archive = self.call(self.company, '/business/documents/' + self.invoice['id'] + '/pdf').data
        self.call(self.company, '/business/accounting/accounts/' + self.account['id'], request(
            revision=self.account['revision'], name=self.account['name'],
            active=False, confirmation=True))
        body = self.preview_body(payment)
        entry, command = self.confirmed(payment, body)
        self.assertEqual((entry['revision'], entry['amount'], entry['open_after']), (1, '47.60', '59.50'))
        state = self.state(payment)
        self.assertEqual((state['allocated_amount'], state['unallocated_amount'], state['revision']),
                         ('59.50', '59.50', 1))
        self.assertEqual(state['allocations'], [{'document_id': self.invoice['id'], 'amount': '59.50'}])
        self.assertEqual(state['source_hash'], source['source_hash'])
        self.assertFalse(state['tax_result_available'])
        self.assertEqual(state['scope'], 'authorized_sources')
        self.assertEqual(self.legacy_sources(self.company), original_rows)
        self.assertEqual(self.call(self.company, '/business/accounting/events/' + event['id']).json, event)
        self.assertEqual(self.call(self.company, '/business/accounting/events/import-payment',
                                  import_command, status=201).json, event)
        self.assertEqual(self.call(self.company, PREFIX + payment['id'] + '/assign', command, status=201).json, entry)
        listed = self.call(self.company, '/business/finance/payments').json['items'][0]
        self.assertEqual((listed['allocations'], listed['unallocated']), (state['allocations'], '59.50'))
        self.assertEqual(self.open_item(self.invoice)['open'], '59.50')
        self.payment_record(kind='refund', amount='11.90', allocations=[(self.invoice['id'], '11.90')])
        self.assertEqual(self.open_item(self.invoice)['open'], '71.40')
        self.assertEqual(self.state(payment)['unallocated_amount'], '59.50')
        self.assertEqual(self.call(self.company, PREFIX + payment['id'] + '/assign', command, status=201).json, entry)
        self.assertEqual(self.call(self.company, '/business/documents/' + self.invoice['id'] + '/pdf').data, archive)

    def test_every_original_and_new_project_is_required_but_authorized_op_stays_complete(self):
        project_b, invoice_b = self.project_invoice()
        user, token = self.user(self.company)
        self.prepare_user(self.company, user)
        self.call(self.company, '/assignments', {'project_id': project_b, 'user_id': user})
        payment, payment_command = self.payment_record(amount='100.00',
            allocations=[(self.invoice['id'], '10.00')], token=token)
        _, event, import_command = self.imported(payment, token=token)
        body = self.preview_body(payment, invoice_b, amount='20.00', token=token)
        entry, command = self.confirmed(payment, body, token=token)
        self.permission(self.company, user, 'finance.read', effect='deny', scope=project_b)
        for path, payload in ((PREFIX + payment['id'], None),
                (PREFIX + payment['id'] + '/history', None),
                (PREFIX + payment['id'] + '/assign', command),
                ('/business/accounting/events/' + event['id'], None),
                ('/business/accounting/events/import-payment', import_command),
                ('/business/finance/payments', payment_command)):
            self.call(self.company, path, payload, token=token, status=(403, 404))
        self.assertNotIn(payment['id'], [row['id'] for row in
            self.call(self.company, '/business/finance/payments', token=token).json['items']])
        self.assertNotIn(payment['id'], [row['payment_id'] for row in
            self.call(self.company, '/business/accounting/sources/payments', token=token).json['items']])
        self.assertEqual((self.open_item(self.invoice, token=token)['paid'],
                          self.open_item(self.invoice, token=token)['open']), ('10.00', '109.00'))
        self.permission(self.company, user, 'finance.read', scope=project_b, revision=1)
        self.assertEqual(self.call(self.company, PREFIX + payment['id'] + '/assign', command,
                                  token=token, status=201).json, entry)
        self.permission(self.company, user, 'finance.write', effect='deny', scope=project_b)
        self.assertFalse(self.state(payment, token=token)['writes_allowed'])
        self.call(self.company, PREFIX + payment['id'] + '/history', token=token)
        for suffix, payload in (('/candidates', None), ('/preview', body), ('/assign', command)):
            self.call(self.company, PREFIX + payment['id'] + suffix, payload, token=token, status=403)

    def test_originally_private_payment_does_not_become_public_after_project_assignment(self):
        user, token = self.user(self.company)
        self.prepare_user(self.company, user)
        payment, _ = self.payment_record(amount='70.00')
        self.imported(payment)
        self.confirmed(payment, self.preview_body(payment, amount='40.00'))
        self.call(self.company, PREFIX + payment['id'], token=token, status=(403, 404))
        self.assertEqual(self.call(self.company, '/business/finance/payments', token=token).json['items'], [])
        self.assertEqual(self.call(self.company, '/business/accounting/sources/payments', token=token).json['items'], [])
        own, _ = self.payment_record(amount='30.00', token=token)
        self.imported(own, token=token)
        entry, _ = self.confirmed(own, self.preview_body(own, amount='30.00', token=token), token=token)
        self.assertEqual(entry['created_by'], user)
        other, other_token = self.user(self.company, 'other-bookkeeper')
        self.prepare_user(self.company, other)
        self.call(self.company, PREFIX + own['id'], token=other_token, status=(403, 404))
        self.assertEqual(self.state(own)['unallocated_amount'], '0.00')

    def test_state_candidates_history_and_preview_are_read_only_and_reject_unknown_inputs(self):
        _, second = self.project_invoice()
        payment, _ = self.payment_record()
        self.imported(payment)
        body = self.preview_body(payment)
        before = self.database()
        self.state(payment)
        first = self.call(self.company, PREFIX + payment['id'] + '/candidates?limit=1&offset=0').json
        following = self.call(self.company, PREFIX + payment['id'] + '/candidates?limit=1&offset=1').json
        self.assertEqual((first['total'], first['next_offset'], following['next_offset']), (2, 1, None))
        self.assertEqual({first['items'][0]['document_id'], following['items'][0]['document_id']},
                         {self.invoice['id'], second['id']})
        candidate_keys = {'document_id', 'number', 'project_id', 'customer_id', 'buyer_name',
            'gross', 'paid', 'credited', 'open', 'payload_sha256', 'pdf_sha256', 'document_state_hash'}
        self.assertEqual(set(first['items'][0]), candidate_keys)
        self.call(self.company, PREFIX + payment['id'] + '/history')
        preview = self.call(self.company, PREFIX + payment['id'] + '/preview', body).json
        self.assertEqual((preview['amount'], preview['open_after']), ('47.60', '71.40'))
        self.assertEqual(self.database(), before)
        for suffix in ('?project_id=' + self.company['project'], '/candidates?customer_id=' + self.customer,
                '/candidates?limit=1&limit=2', '/history?limit=101', '/history?offset=-1',
                '/history?offset=100001', '/candidates?offset=0&unknown=yes'):
            self.call(self.company, PREFIX + payment['id'] + suffix, status=400)
        for change in ({'unexpected': True}, {'request_id': uuid.uuid4().hex}, {'amount': 47.60},
                {'amount': '47.6'}, {'amount': '0.00'}, {'expected_revision': True},
                {'reason': 'Two\nlines'}, {'confirmation': True}):
            self.call(self.company, PREFIX + payment['id'] + '/preview', {**body, **change}, status=400)
        self.call(self.company, PREFIX + payment['id'], {'unexpected': True}, method='GET', status=400)
        for query in ('?unexpected=1', '?limit=1&limit=2'):
            self.call(self.company, PREFIX + payment['id'] + '/preview' + query, body, status=400)
            self.call(self.company, PREFIX + payment['id'] + '/assign' + query,
                request(**body, preview_hash=preview['preview_hash'], confirmation=True), status=400)
        self.call(self.company, PREFIX + payment['id'] + '/assign',
                  request(**body, preview_hash=preview['preview_hash'], confirmation=False), status=400)
        self.assertEqual(self.database(), before)

    def test_stale_target_customer_mismatch_and_old_finance_receipt_cannot_overallocate(self):
        first, _ = self.payment_record(amount='100.00')
        second, _ = self.payment_record(amount='100.00')
        self.imported(first)
        self.imported(second)
        first_body = self.preview_body(first, amount='80.00')
        second_body = self.preview_body(second, amount='80.00')
        second_preview = self.call(self.company, PREFIX + second['id'] + '/preview', second_body).json
        first_entry, first_command = self.confirmed(first, first_body)
        before = self.database()
        self.call(self.company, PREFIX + second['id'] + '/assign', request(**second_body,
            preview_hash=second_preview['preview_hash'], confirmation=True), status=409)
        too_much = self.preview_body(second, amount='39.01')
        self.call(self.company, PREFIX + second['id'] + '/preview', too_much, status=409)
        overpay = request(source_id='synthetic-overpay-' + uuid.uuid4().hex, kind='receipt', amount='40.00',
            currency='EUR', booking_date='2026-11-02', reference='Rejected overpayment',
            allocations=[{'document_id': self.invoice['id'], 'amount': '40.00'}])
        self.call(self.company, '/business/finance/payments', overpay, status=409)
        self.assertEqual(self.database(), before)
        self.payment_record(amount='40.00', allocations=[(self.invoice['id'], '39.00')])
        self.assertEqual(self.open_item(self.invoice)['open'], '0.00')
        self.assertEqual(self.call(self.company, PREFIX + first['id'] + '/assign',
                                  first_command, status=201).json, first_entry)
        _, foreign = self.project_invoice(same_customer=False)
        foreign_source, _ = self.payment_record(amount='100.00')
        self.imported(foreign_source)
        foreign_candidate = self.preview_body(foreign_source, foreign, amount='1.00')
        self.call(self.company, PREFIX + first['id'] + '/preview',
            {**foreign_candidate, **{key: self.state(first)[key] for key in ('source_hash', 'state_hash')},
             'expected_revision': self.state(first)['revision']}, status=409)

    def test_target_write_scope_and_global_accounting_rights_are_checked_fresh_before_replay(self):
        user, token = self.user(self.company)
        self.prepare_user(self.company, user)
        project_b, invoice_b = self.project_invoice()
        self.call(self.company, '/assignments', {'project_id': project_b, 'user_id': user})
        payment, _ = self.payment_record(allocations=[(self.invoice['id'], '10.00')])
        self.imported(payment)
        body = self.preview_body(payment, invoice_b, amount='20.00')
        self.permission(self.company, user, 'finance.write', effect='deny', scope=project_b)
        candidates = self.call(self.company, PREFIX + payment['id'] + '/candidates', token=token).json
        self.assertNotIn(invoice_b['id'], [row['document_id'] for row in candidates['items']])
        self.call(self.company, PREFIX + payment['id'] + '/preview', body, token=token, status=(403, 404))
        self.permission(self.company, user, 'finance.write', scope=project_b, revision=1)
        _, command = self.confirmed(payment, body, token=token)
        self.permission(self.company, user, 'accounting.prepare', effect='deny', revision=1)
        self.assertFalse(self.state(payment, token=token)['writes_allowed'])
        self.call(self.company, PREFIX + payment['id'] + '/assign', command, token=token, status=403)
        self.permission(self.company, user, 'accounting.read', effect='deny', revision=1)
        self.call(self.company, PREFIX + payment['id'], token=token, status=403)
        self.call(self.company, PREFIX + payment['id'] + '/history', token=token, status=403)


if __name__ == '__main__':
    unittest.main()
