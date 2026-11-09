"""One customer order through real PostgreSQL, MFA and HTTP contracts.

Synthetic, disposable loopback database only; the shared fixture validates the
DSN before resetting it. No supplier, email, bank or other provider is called.
The capture submission represents an already frozen offline client command;
real Flutter persistence/restart and device acceptance are separate evidence.
Project costs below cover posted material and approved time, not every cost type.
"""
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import io
import time
import unittest
from urllib.parse import parse_qs, urlsplit
import uuid
from zoneinfo import ZoneInfo

from cryptography.fernet import Fernet
from PIL import Image
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

import business_schema
from core import canonical
from online import release, test_business_journey_pg as fixture
from online.auth import totp
from online.store import PostgresOffice, migrate
from online.web import create_app


ORIGIN = 'https://office.example.test'
request = fixture.request


def sha(value):
    return hashlib.sha256(value).hexdigest()


@unittest.skipUnless(fixture.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class CustomerExecutionJourneyPostgres(unittest.TestCase):
    def setUp(self):
        # Same guarded role/migration setup as BusinessJourneyPostgres. Keep the
        # synthetic encryption key explicitly so reopening is a real restart.
        with psycopg.connect(fixture.DSN, autocommit=True, connect_timeout=5) as connection:
            connection.execute('DROP SCHEMA public CASCADE')
            connection.execute('CREATE SCHEMA public')
        migrate(fixture.DSN, compatibility_mode='business', require_business_modules=True)
        bootstrap = PostgresOffice(fixture.DSN)
        try:
            bootstrap.add_user('order-owner@example.test', 'Synthetic-owner-password-123', 'owner')
        finally:
            bootstrap.db.close()
        with psycopg.connect(fixture.DSN, connect_timeout=5) as connection:
            if not connection.execute("SELECT 1 FROM pg_roles WHERE rolname='smartplan-online'").fetchone():
                connection.execute('CREATE ROLE "smartplan-online" LOGIN')
            connection.execute(sql.SQL('ALTER ROLE "smartplan-online" PASSWORD {}').format(
                sql.Literal('synthetic-business-runtime-only')))
        release.secure_database(fixture.DSN, test_mode=True)
        self.runtime = make_conninfo(fixture.DSN, user='smartplan-online',
                                    password='synthetic-business-runtime-only')
        self.key = Fernet.generate_key()
        self.token = None
        self.reopen()
        self.token = self.login('order-owner@example.test', 'Synthetic-owner-password-123')
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        self.today = self.now.date().isoformat()

    def reopen(self):
        if hasattr(self, 'office'):
            self.office.db.close()
        self.office = PostgresOffice(self.runtime)
        self.addCleanup(self.office.db.close)
        self.app = create_app(office=self.office, key=self.key, host='office.example.test',
                              storage_config={})
        self.client = self.app.test_client()

    def call(self, method, path, body=None, *, token='owner', status=200, mime=None, offline_origin=None):
        bearer = self.token if token == 'owner' else token
        headers = {'Authorization': 'Bearer ' + bearer} if bearer else {}
        if offline_origin is not None:
            headers['X-Smartplan-Offline-Binding'] = offline_origin
        if path.startswith('/portal/') and method == 'POST':
            headers['Origin'] = ORIGIN
        arguments = {'json': body} if isinstance(body, dict) else {'data': body}
        response = self.client.open('/api/v1' + path, method=method, base_url=ORIGIN,
            headers=headers, content_type=mime, **arguments)
        # Never include invitation links, device credentials or response bodies
        # in assertion diagnostics.
        self.assertEqual(response.status_code, status, (method, path, response.status_code))
        return response

    def login(self, email, password):
        pending = self.call('POST', '/login', {'email': email, 'password': password}, token=None).json
        self.assertTrue(pending['mfa_required'])
        self.assertNotIn('token', pending)
        return self.call('POST', '/login/verify', {'challenge': pending['challenge'],
            'code': totp(pending['enrollment']['secret'], int(time.time() // 30))}, token=None).json['token']

    def workflow(self):
        self.assertEqual(self.office.db.execute('SELECT current_user').fetchone()[0], 'smartplan-online')
        self.assertTrue(business_schema.require_runtime_security(self.office))

        connector = self.call('POST', '/inbound/gmail/tokens', {
            'name': 'Synthetic order intake', 'source_account': 'order-inbox@example.test',
            'expires_days': 7}, status=201).json
        envelope = {'source_account': 'order-inbox@example.test', 'source_id': 'synthetic-order-message-1',
            'subject': 'Synthetic equipment installation inquiry', 'message': 'Please prepare an offer.',
            'sender_name': 'Synthetic Order Buyer', 'sender_email': 'order-buyer@example.test',
            'received_at': self.now.isoformat()}
        intake = self.call('POST', '/intake/gmail', envelope, token=connector['token'], status=201).json
        self.assertEqual(self.call('POST', '/intake/gmail', envelope,
                                  token=connector['token'], status=201).json, intake)
        self.call('GET', '/inquiries/' + intake['id'], token=connector['token'], status=401)
        inquiry = self.call('GET', '/inquiries/' + intake['id']).json
        conversion_body = request(revision=inquiry['revision'], project_name='Synthetic accepted customer order',
            customer={'name': envelope['sender_name'], 'email': envelope['sender_email'],
                      'address': 'Synthetic buyer street 2'})
        conversion = self.call('POST', '/inquiries/' + intake['id'] + '/convert', conversion_body).json
        self.assertEqual(self.call('POST', '/inquiries/' + intake['id'] + '/convert', conversion_body).json,
                         conversion)
        project, customer = conversion['project']['id'], conversion['project']['customer_id']
        self.assertEqual(conversion['inquiry']['status'], 'converted')
        self.assertTrue(customer)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM projects').fetchone()[0], 1)

        raw_catalog = (b'code;name;unit;cost_price_net;unit_price_net;tax_rate\n'
                       b'SYN-ORDER-DEVICE;Synthetic installed device;C62;12.50;50.00;19\n')
        adapter = self.call('POST', '/business/adapters', request(name='Synthetic local supplier CSV',
            profile='catalog_csv_v1', enabled=True), status=201).json
        import_body = request(content_base64=base64.b64encode(raw_catalog).decode())
        staged = self.call('POST', '/business/adapters/' + adapter['id'] + '/import',
                           import_body, status=201).json
        self.assertEqual((staged['status'], staged['source_sha256']), ('staged', sha(raw_catalog)))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_articles').fetchone()[0], 0)
        self.assertEqual(self.call('POST', '/business/adapters/' + adapter['id'] + '/import',
                                  import_body, status=201).json, staged)
        apply_body = request(confirmed=True)
        apply_path = '/business/adapters/imports/' + staged['id'] + '/apply'
        applied = self.call('POST', apply_path, apply_body).json
        self.assertEqual(self.call('POST', apply_path, apply_body).json, applied)
        self.assertEqual(len(applied['result']['article_ids']), 1)
        article = self.call('GET', '/business/articles/' + applied['result']['article_ids'][0]).json
        self.assertEqual((article['code'], article['unit']), ('SYN-ORDER-DEVICE', 'C62'))

        settings = self.call('GET', '/business/settings/branding').json
        self.call('POST', '/business/settings/branding', request(revision=settings['revision'],
            company_name='Synthetic Order Seller', address_line='Synthetic seller street 1',
            postal_code='10115', city='Berlin', country='DE', vat_id='DE123456789',
            email='seller@example.test', issuer_mode='own', issuing_enabled=True,
            cutover_ack=True, cutover_date=self.today, einvoice_format='none'))
        offer_draft = self.call('POST', '/business/documents', request(project_id=project, kind='offer',
            title='Synthetic equipment supply and installation', issue_date=self.today,
            due_date=(self.now.date() + timedelta(days=14)).isoformat(),
            buyer={'name': envelope['sender_name'], 'address_line': 'Synthetic buyer street 2',
                   'postal_code': '10117', 'city': 'Berlin', 'country': 'DE',
                   'email': envelope['sender_email']},
            positions=[{'article_id': article['id'], 'article_revision': article['revision'], 'quantity': '2'}])).json
        offer_path = '/business/documents/' + offer_draft['id']
        offer = self.call('POST', offer_path + '/finalize', request(revision=offer_draft['revision'])).json
        self.assertEqual((offer['totals']['net'], offer['totals']['gross']), ('100.00', '119.00'))
        offer_pdf = self.call('GET', offer_path + '/pdf').data
        source = self.call('GET', '/business/portal/grants?offer_id=' + offer['id']).json['source']
        grant = self.call('POST', '/business/portal/grants', request(
            **{key: source[key] for key in ('offer_id', 'source_revision', 'content_hash', 'pdf_hash')},
            recipient_name=envelope['sender_name'], recipient_email=envelope['sender_email'],
            expires_in_days=7, confirmation=True), status=201).json
        link = urlsplit(grant['portal_url'])
        self.assertEqual(link.scheme + '://' + link.netloc, ORIGIN)
        fragment = parse_qs(link.fragment)
        portal_token = self.call('POST', '/portal/sessions', {'grant_id': grant['grant']['id'],
            'key': fragment['key'][0]}, token=None, status=201).json['token']
        public = self.call('GET', '/portal/offer', token=portal_token).json
        self.assertEqual(self.call('GET', '/portal/offer/pdf', token=portal_token).data, offer_pdf)
        self.assertNotIn('project_id', public['offer'])
        self.assertNotIn('cost_price_net', canonical(public))
        self.call('GET', '/business/documents', token=portal_token, status=401)
        decision_body = request(content_hash=source['content_hash'], pdf_hash=source['pdf_hash'],
            decision='accepted', declared_name='Synthetic Order Buyer',
            statement_version=public['statements']['version'], confirmation=True)
        decision = self.call('POST', '/portal/offer/decision', decision_body,
                             token=portal_token, status=201).json
        self.assertEqual(self.call('POST', '/portal/offer/decision', decision_body,
                                  token=portal_token, status=201).json, decision)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_documents').fetchone()[0], 1)
        adoption_body = request(decision_id=decision['id'], confirmation=True,
            **{key: source[key] for key in ('source_revision', 'content_hash', 'pdf_hash')})
        adoption_path = '/business/portal/offers/' + offer['id'] + '/adopt'
        adoption = self.call('POST', adoption_path, adoption_body, status=201).json
        self.assertEqual(self.call('POST', adoption_path, adoption_body, status=201).json, adoption)
        self.assertEqual(adoption['project_id'], project)
        order_path = '/business/documents/' + adoption['document_id']
        order_draft = self.call('GET', order_path).json
        order = self.call('POST', order_path + '/finalize', request(revision=order_draft['revision'])).json
        self.assertEqual((order['project_id'], order['customer_id'], order['converted_from']),
                         (project, customer, offer['id']))
        self.assertEqual(order['positions'], offer['positions'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM projects').fetchone()[0], 1)

        technician = self.call('POST', '/users', {'email': 'order-tech@example.test',
            'password': 'Synthetic-tech-password-123', 'role': 'technician'}, status=201).json['id']
        tech_token = self.login('order-tech@example.test', 'Synthetic-tech-password-123')
        self.call('POST', '/assignments', {'project_id': project, 'user_id': technician})
        employee = self.call('POST', '/business/employees', request(user_id=technician,
            name='Synthetic installation technician', weekly_minutes=2400,
            hourly_cost_minor=3500), status=201).json
        visit_start = self.now - timedelta(minutes=40)
        appointment_body = request(project_id=project, title='Synthetic accepted installation',
            start_at=visit_start.isoformat(), end_at=(visit_start + timedelta(hours=1)).isoformat(),
            timezone='Europe/Berlin', employee_ids=[employee['id']], resource_ids=[])
        appointment = self.call('POST', '/business/appointments', appointment_body, status=201).json
        self.assertEqual(self.call('POST', '/business/appointments', appointment_body, status=201).json,
                         appointment)
        self.assertEqual(appointment['conflicts'], [])
        appointment_snapshot = self.call('GET', '/business/appointments/' + appointment['id']).json
        self.assertEqual(appointment_snapshot['project_id'], project)
        grant = self.call('POST', '/business/offline/access', {}, token=tech_token, status=201).json
        self.assertTrue({'time_events', 'field_media', 'offline_reports'} <= set(grant['capabilities']))
        device_token = grant['token']
        self.call('GET', '/business/finance/payments', token=device_token, status=403)

        entry_id = uuid.uuid4().hex
        start, stop = self.now - timedelta(minutes=40), self.now - timedelta(minutes=10)
        for sequence, (action, instant) in enumerate((('start', start), ('stop', stop)), 1):
            body = request(entry_id=entry_id, device_id='synthetic-order-device', sequence=sequence,
                revision=sequence - 1, project_id=project, action=action, occurred_at=instant.isoformat())
            result = self.call('POST', '/business/time/events', body, token=device_token).json
            repeat = self.call('POST', '/business/time/events', body, token=device_token).json
            self.assertEqual(repeat['event_id'], result['event_id'])
        first_day = start.astimezone(ZoneInfo('Europe/Berlin')).date().isoformat()
        last_day = stop.astimezone(ZoneInfo('Europe/Berlin')).date().isoformat()
        summary = self.call('GET', '/business/time/summary?employee_id=' + employee['id'] +
                           '&from=' + first_day + '&to=' + last_day).json
        self.assertEqual(summary['net_seconds'], 1800)
        for day in summary['days']:
            if day['worked_seconds']:
                self.call('POST', '/business/time/days/' + day['date'] + '/approve',
                          request(employee_id=employee['id'], revision=day['revision']))

        location = self.call('POST', '/business/inventory/locations', request(name='Synthetic van'), status=201).json
        purchase = self.call('POST', '/business/inventory/orders', request(project_id=project,
            supplier_name='Synthetic device supplier', status='approved',
            items=[dict(article_id=article['id'], quantity='2')]), status=201).json
        purchase_path = '/business/purchasing/orders/' + purchase['id']
        ordered = self.call('GET', purchase_path).json
        self.call('POST', purchase_path + '/confirm', request(source_revision=ordered['source_revision'],
            expected_receipt_revision=0, order_reference='SYN-ORDER-DEVICE-PURCHASE',
            ordered_on=self.today, confirmation=True))
        deliveries = []
        for index in range(2):
            ordered = self.call('GET', purchase_path).json
            receipt_body = request(source_revision=ordered['source_revision'],
                expected_receipt_revision=ordered['receipt_revision'], receipt_reference='SYN-DELIVERY-' + str(index),
                received_on=self.today, location_id=location['id'],
                lines=[dict(line_index=0, quantity='1', unit_cost_net='12.50')])
            receipt = self.call('POST', purchase_path + '/receipts', receipt_body, status=201).json
            self.assertEqual(self.call('POST', purchase_path + '/receipts', receipt_body, status=201).json, receipt)
            deliveries.append(receipt)
            ordered = self.call('GET', purchase_path).json
            self.assertEqual(ordered['items'][0]['received_quantity'], str(index+1)+'.0000')
            self.assertEqual(ordered['items'][0]['remaining_quantity'], str(1-index)+'.0000')
        issue_body = request(kind='issue', article_id=article['id'], from_location_id=location['id'],
                             project_id=project, quantity='2')
        issue = self.call('POST', '/business/inventory/movements', issue_body, status=201).json
        self.assertEqual(self.call('POST', '/business/inventory/movements', issue_body, status=201).json, issue)
        costs_path = '/business/projects/' + project + '/costs'
        costs = self.call('GET', costs_path).json
        self.assertEqual((costs['material_actual_net'], costs['labor_actual_net'], costs['actual_net']),
                         ('25.00', '17.50', '42.50'))
        self.assertEqual(costs['cost_basis'], 'posted_material_and_approved_time')
        self.assertEqual([row['id'] for row in costs['material_movements']], [issue['id']])
        self.assertEqual({row['entry_id'] for row in costs['approved_times']}, {entry_id})

        photo_buffer = io.BytesIO()
        Image.new('RGB', (40, 30), 'white').save(photo_buffer, format='PNG')
        photo = photo_buffer.getvalue()
        media_body = request(project_id=project, filename='synthetic-installed-equipment.png',
            media_type='image/png', size=len(photo), sha256=sha(photo))
        media = self.call('POST', '/business/media', media_body, token=device_token, status=201).json
        media_path = '/business/media/' + media['id']
        self.assertEqual(self.call('POST', '/business/media', media_body,
                                  token=device_token, status=201).json['id'], media['id'])
        chunk = {'content_base64': base64.b64encode(photo).decode()}
        self.call('POST', media_path + '/chunks/0', chunk, token=device_token)
        self.call('POST', media_path + '/chunks/0', chunk, token=device_token)
        complete_body = request()
        completed = self.call('POST', media_path + '/complete', complete_body, token=device_token).json
        self.assertEqual(self.call('POST', media_path + '/complete', complete_body,
                                  token=device_token).json, completed)
        self.assertEqual(self.call('GET', media_path + '/content', token=device_token).data, photo)

        report_id = uuid.uuid4().hex
        content = {'title': 'Synthetic installation acceptance',
            'description': 'Two supplied devices installed and checked.',
            'notes': 'Synthetic customer confirmed the documented installation.',
            'project_name': conversion['project']['name'], 'customer': envelope['sender_name'],
            'captured_at': (self.now - timedelta(minutes=3)).isoformat()}
        capture_body = request(entry_id=report_id, project_id=project, content=content,
            content_hash=sha(canonical([report_id, project, content]).encode()),
            signer='Synthetic Order Buyer', strokes=[[[0.1, 0.2], [0.8, 0.6]]],
            signed_at=(self.now - timedelta(minutes=2)).isoformat())
        capture_path = '/business/service-reports/offline'
        signed = self.call('POST', capture_path, capture_body, token=device_token, status=201).json
        self.assertEqual(self.call('POST', capture_path, capture_body,
                                  token=device_token, status=201).json, signed)
        self.assertEqual((signed['id'], signed['project_id'], signed['status'], signed['revision']),
                         (report_id, project, 'signed', 2))
        self.assertEqual(signed['offline_capture']['content'], content)
        self.assertEqual(signed['offline_capture']['content_hash'], capture_body['content_hash'])
        report_path = '/business/service-reports/' + report_id
        report_pdf = self.call('GET', report_path + '/pdf', token=device_token).data
        self.assertTrue(report_pdf.startswith(b'%PDF-'))
        self.assertEqual(sha(report_pdf), signed['pdf_sha256'])

        invoice_body = request(revision=order['revision'], target_kind='invoice')
        invoice_draft = self.call('POST', order_path + '/convert', invoice_body).json
        self.assertEqual(self.call('POST', order_path + '/convert', invoice_body).json, invoice_draft)
        invoice_path = '/business/documents/' + invoice_draft['id']
        final_body = request(revision=invoice_draft['revision'])
        invoice = self.call('POST', invoice_path + '/finalize', final_body).json
        self.assertEqual(self.call('POST', invoice_path + '/finalize', final_body).json, invoice)
        self.assertEqual((invoice['status'], invoice['project_id'], invoice['customer_id'],
                          invoice['converted_from'], invoice['totals']['gross']),
                         ('final', project, customer, order['id'], '119.00'))
        self.assertEqual(invoice['positions'], offer['positions'])
        invoice_pdf = self.call('GET', invoice_path + '/pdf').data
        payments = []
        for suffix, amount, outstanding in (('part', '10.00', '109.00'), ('balance', '109.00', '0.00')):
            body = request(source_id='synthetic-order-bank-' + suffix, kind='receipt', amount=amount,
                currency='EUR', booking_date=self.today, reference='Synthetic ' + suffix + ' payment',
                allocations=[{'document_id': invoice['id'], 'amount': amount}])
            payment = self.call('POST', '/business/finance/payments', body).json
            self.assertEqual(self.call('POST', '/business/finance/payments', body).json, payment)
            payments.append((body, payment))
            items = self.call('GET', '/business/finance/open-items?project_id=' + project).json['items']
            row = next(item for item in items if item['id'] == invoice['id'])
            self.assertEqual(row['open'], outstanding)
        self.assertEqual(row['paid'], '119.00')
        self.assertEqual(self.call('GET', costs_path).json, costs)

        self.reopen()
        self.assertTrue(business_schema.require_runtime_security(self.office))
        self.assertEqual(self.call('GET', '/inquiries/' + intake['id']).json['project_id'], project)
        self.assertEqual(self.call('GET', offer_path).json, offer)
        self.assertEqual(self.call('GET', offer_path + '/pdf').data, offer_pdf)
        self.assertEqual(self.call('POST', adoption_path, adoption_body, status=201).json, adoption)
        self.assertEqual(self.call('GET', '/business/appointments/' + appointment['id']).json,
                         appointment_snapshot)
        self.assertEqual(self.call('GET', costs_path).json, costs)
        self.assertEqual(self.call('GET', media_path + '/content', token=device_token).data, photo)
        self.assertEqual(self.call('GET', report_path, token=device_token).json, signed)
        self.assertEqual(self.call('POST', capture_path, capture_body, token=device_token, status=201).json, signed)
        self.assertEqual(self.call('GET', report_path + '/pdf', token=device_token).data, report_pdf)
        self.assertEqual(self.call('GET', invoice_path).json, invoice)
        self.assertEqual(self.call('GET', invoice_path + '/pdf').data, invoice_pdf)
        for body, payment in payments:
            self.assertEqual(self.call('POST', '/business/finance/payments', body).json, payment)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM projects').fetchone()[0], 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_portal_adoptions').fetchone()[0], 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_operation_entries').fetchone()[0], 1)
        self.assertTrue(business_schema.validate_integrity(self.office))

        # Fresh source rights also govern an identical frozen capture replay.
        self.call('POST', '/assignments', {'project_id': project, 'user_id': technician, 'remove': True})
        self.call('POST', capture_path, capture_body, token=device_token, status=403)
        self.call('GET', report_path + '/pdf', token=device_token, status=403)
        self.assertEqual(self.call('GET', report_path + '/pdf').data, report_pdf)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_operation_entries').fetchone()[0], 1)
        self.assertTrue(business_schema.validate_integrity(self.office))

        return dict(project=project,customer=customer,inquiry=intake,article=article,location=location,
            purchase=purchase,deliveries=deliveries,issue=issue,costs=costs,time_entry_id=entry_id,
            signed=signed,report_pdf=report_pdf,photo=photo,media=media,invoice=invoice,
            invoice_pdf=invoice_pdf,payments=payments,tech_token=tech_token,device_token=device_token)

    def test_inquiry_catalog_portal_execution_capture_invoice_and_settlement_survive_restart(self):
        self.workflow()


if __name__ == '__main__':
    unittest.main()
