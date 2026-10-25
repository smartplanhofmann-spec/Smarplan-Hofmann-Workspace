"""One complete synthetic business journey through real Flask and PostgreSQL.

Only SMARTPLAN_TEST_DSN for the disposable, loopback smartplan_check database
is accepted. The fixture resets that database's public schema. No provider or
SMTP connection is made, and the actual production Documents policy is used.
"""
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
import time
import unittest
import uuid
from zoneinfo import ZoneInfo

from cryptography.fernet import Fernet
from PIL import Image
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

import business_documents
import business_schema
from business_time import TimeTracking
from online import release
from online.auth import totp
from online.store import PostgresOffice, migrate
from online.web import create_app


DSN = os.environ.get('SMARTPLAN_TEST_DSN')
if DSN:
    # Reuse the operator's complete guard, before any connection or schema reset.
    release.validate_dsns(DSN, make_conninfo(DSN, dbname='smartplan_release_check'), test_mode=True)


def request(**values):
    return {'request_id': uuid.uuid4().hex, **values}


def sha(value):
    return hashlib.sha256(value).hexdigest()


@unittest.skipUnless(DSN, 'SMARTPLAN_TEST_DSN not configured')
class BusinessJourneyPostgres(unittest.TestCase):
    def setUp(self):
        with psycopg.connect(DSN, autocommit=True, connect_timeout=5) as connection:
            connection.execute('DROP SCHEMA public CASCADE')
            connection.execute('CREATE SCHEMA public')
        migrate(DSN, compatibility_mode='business', require_business_modules=True)
        bootstrap = PostgresOffice(DSN)
        try:
            bootstrap.add_user('journey-owner@example.test', 'Synthetic-owner-password-123', 'owner')
        finally:
            bootstrap.db.close()
        with psycopg.connect(DSN, connect_timeout=5) as connection:
            if not connection.execute("SELECT 1 FROM pg_roles WHERE rolname='smartplan-online'").fetchone():
                connection.execute('CREATE ROLE "smartplan-online" LOGIN')
            connection.execute(sql.SQL('ALTER ROLE "smartplan-online" PASSWORD {}').format(
                sql.Literal('synthetic-business-runtime-only')))
        # No application connection is alive while ownership/ACLs are installed.
        release.secure_database(DSN, test_mode=True)
        runtime = make_conninfo(DSN, user='smartplan-online', password='synthetic-business-runtime-only')
        self.office = PostgresOffice(runtime)
        self.addCleanup(self.office.db.close)
        self.app = create_app(office=self.office, key=Fernet.generate_key(), host='office.example.test')
        self.client = self.app.test_client()
        self.token = None
        self.token = self.login('journey-owner@example.test', 'Synthetic-owner-password-123')
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        self.today = self.now.date().isoformat()

    def call(self, method, path, body=None, *, token='owner', status=200, mime=None):
        bearer = self.token if token == 'owner' else token
        headers = {'Authorization': 'Bearer ' + bearer} if bearer else {}
        arguments = {'json': body} if isinstance(body, dict) else {'data': body}
        response = self.client.open('/api/v1' + path, method=method,
            base_url='https://office.example.test', headers=headers, content_type=mime, **arguments)
        self.assertEqual(response.status_code, status, (method, path, response.data[:500]))
        return response

    def login(self, email, password):
        pending = self.call('POST', '/login', {'email': email, 'password': password}, token=None).json
        self.assertTrue(pending['mfa_required'])
        self.assertNotIn('token', pending)
        return self.call('POST', '/login/verify', {'challenge': pending['challenge'],
            'code': totp(pending['enrollment']['secret'], int(time.time() // 30))}, token=None).json['token']

    def test_inbound_original_to_project_work_invoice_payment_and_hashed_export(self):
        self.assertEqual(self.office.db.execute('SELECT current_user').fetchone()[0], 'smartplan-online')
        self.assertTrue(business_schema.require_runtime_security(self.office))
        connector = self.call('POST', '/inbound/gmail/tokens', {
            'name': 'Synthetic journey Gmail bridge', 'source_account': 'journey-inbox@example.test',
            'expires_days': 7}, status=201).json
        self.assertTrue(connector['token'].startswith('SPIN'))
        envelope = {'source_account': 'journey-inbox@example.test', 'source_id': 'synthetic-journey-message-1',
            'subject': 'Synthetic installation inquiry', 'message': 'Synthetic request for a quotation; no acceptance.',
            'sender_name': 'Synthetic Journey Buyer', 'sender_email': 'journey-buyer@example.test',
            'received_at': self.now.isoformat()}
        intake = self.call('POST', '/intake/gmail', envelope, token=connector['token'], status=201).json
        self.assertEqual(self.call('POST', '/intake/gmail', envelope, token=connector['token'], status=201).json, intake)
        # The import-only token cannot read even the inquiry it just created.
        self.call('GET', '/inquiries/' + intake['id'], token=connector['token'], status=401)

        image = io.BytesIO()
        Image.new('RGB', (40, 30), 'white').save(image, format='PNG')
        original = image.getvalue()
        announced = self.call('POST', '/intake/gmail/attachments', {
            'source_account': envelope['source_account'], 'source_id': envelope['source_id'],
            'attachments': [{'source_attachment_id': 'synthetic-provider-attachment-1',
                'filename': 'synthetic-original.png', 'media_type': 'image/png',
                'size': len(original), 'sha256': sha(original)}]}, token=connector['token'], status=201).json
        attachment = announced['files'][0]
        upload_path = '/intake/gmail/attachments/' + attachment['id']
        for _ in range(2):
            self.call('PUT', upload_path + '/chunks/0', original, token=connector['token'],
                      mime='application/octet-stream')
        self.assertEqual(self.call('POST', upload_path + '/complete', {}, token=connector['token']).json['status'], 'ready')
        inquiry_path = '/inquiries/' + intake['id']
        inquiry = self.call('GET', inquiry_path).json
        conversion = request(revision=inquiry['revision'], project_name='Synthetic journey project',
            customer={'name': 'Synthetic Journey Buyer', 'email': envelope['sender_email'], 'address': 'Synthetic buyer street 2'})
        converted = self.call('POST', inquiry_path + '/convert', conversion).json
        self.assertEqual(self.call('POST', inquiry_path + '/convert', conversion).json, converted)
        self.assertEqual(converted['inquiry']['status'], 'converted')
        project = converted['project']['id']
        customer = converted['project']['customer_id']
        self.assertTrue(customer)
        source_path = '/projects/' + project + '/mail-attachments/' + attachment['id'] + '/content'
        self.assertEqual(self.call('GET', source_path).data, original)

        technician = self.call('POST', '/users', {'email': 'journey-tech@example.test',
            'password': 'Synthetic-tech-password-123', 'role': 'technician'}, status=201).json['id']
        technician_token = self.login('journey-tech@example.test', 'Synthetic-tech-password-123')
        self.call('POST', '/assignments', {'project_id': project, 'user_id': technician})
        employee = self.call('POST', '/business/employees', request(user_id=technician,
            name='Synthetic technician', weekly_minutes=2400, hourly_cost_minor=3500), status=201).json
        tomorrow = (self.now + timedelta(days=1)).replace(hour=10, minute=0, second=0)
        appointment = self.call('POST', '/business/appointments', request(project_id=project,
            title='Synthetic installation visit', start_at=tomorrow.isoformat(),
            end_at=(tomorrow + timedelta(hours=1)).isoformat(), timezone='Europe/Berlin',
            employee_ids=[employee['id']], resource_ids=[]), status=201).json
        self.assertEqual(self.call('GET', '/business/appointments/' + appointment['id']).json['project_id'], project)

        entry_id = uuid.uuid4().hex
        start, stop = self.now - timedelta(minutes=40), self.now - timedelta(minutes=10)
        for sequence, (action, instant) in enumerate((('start', start), ('stop', stop)), 1):
            self.call('POST', '/business/time/events', request(entry_id=entry_id, device_id='synthetic-journey-device',
                sequence=sequence, revision=sequence - 1, project_id=project, action=action,
                occurred_at=instant.isoformat()), token=technician_token)
        first_day = start.astimezone(ZoneInfo('Europe/Berlin')).date().isoformat()
        last_day = stop.astimezone(ZoneInfo('Europe/Berlin')).date().isoformat()
        summary_path = '/business/time/summary?employee_id=' + employee['id'] + '&from=' + first_day + '&to=' + last_day
        summary = self.call('GET', summary_path).json
        self.assertEqual(summary['net_seconds'], 1800)
        for day in summary['days']:
            if day['worked_seconds']:
                approved = self.call('POST', '/business/time/days/' + day['date'] + '/approve',
                    request(employee_id=employee['id'], revision=day['revision'])).json
                self.assertEqual(approved['status'], 'approved')
        owner = self.office.user(self.token)
        costs = TimeTracking(self.office).approved_costs(owner, project)
        self.assertEqual(costs['total_cost_minor'], 1750)
        self.assertTrue(costs['complete'])

        checklist = self.call('POST', '/business/checklists', request(project_id=project,
            title='Synthetic installation acceptance', items=[{'key': 'safe', 'label': 'Synthetic circuit checked',
                'required': True, 'type': 'boolean'}]), status=201).json
        run = self.call('POST', '/business/checklists/' + checklist['id'] + '/start', request()).json
        self.call('POST', '/business/checklists/' + run['id'] + '/answers', request(revision=1, answers={'safe': True}))
        report = self.call('POST', '/business/checklists/' + run['id'] + '/report', request()).json
        signed = self.call('POST', '/business/service-reports/' + report['id'] + '/sign', request(
            revision=report['revision'], expected_hash=report['content_hash'], signer='Synthetic Journey Buyer',
            strokes=[[[0.1, 0.2], [0.8, 0.6]]])).json
        report_pdf = self.call('GET', '/business/service-reports/' + report['id'] + '/pdf').data
        self.assertTrue(report_pdf.startswith(b'%PDF-'))
        self.assertEqual(sha(report_pdf), signed['pdf_sha256'])

        settings = self.call('GET', '/business/settings/branding').json
        self.call('POST', '/business/settings/branding', request(revision=settings['revision'],
            company_name='Synthetic Journey Seller GmbH', address_line='Synthetic seller street 1',
            postal_code='10115', city='Berlin', country='DE', vat_id='DE123456789',
            email='seller@example.test', issuer_mode='own', issuing_enabled=True,
            cutover_ack=True, cutover_date=self.today, einvoice_format='none'))
        offer = self.call('POST', '/business/documents', request(project_id=project, kind='offer',
            title='Synthetic installation offer', issue_date=self.today,
            due_date=(self.now.date() + timedelta(days=14)).isoformat(), buyer_reference='SYNTHETIC-JOURNEY',
            buyer={'name': 'Synthetic Journey Buyer', 'address_line': 'Synthetic buyer street 2',
                'postal_code': '10117', 'city': 'Berlin', 'country': 'DE', 'email': envelope['sender_email']},
            positions=[{'description': 'Synthetic installation', 'quantity': '2', 'unit': 'HUR',
                'unit_price_net': '50.00', 'tax_rate': '19', 'kind': 'labor'}])).json
        order = self.call('POST', '/business/documents/' + offer['id'] + '/convert', request(
            revision=offer['revision'], target_kind='order_confirmation')).json
        invoice = self.call('POST', '/business/documents/' + order['id'] + '/convert', request(
            revision=order['revision'], target_kind='invoice')).json
        self.assertEqual((order['kind'], invoice['kind']), ('order_confirmation', 'invoice'))
        self.assertEqual(invoice['positions'], offer['positions'])
        final_request = request(revision=invoice['revision'])
        invoice_path = '/business/documents/' + invoice['id']
        final = self.call('POST', invoice_path + '/finalize', final_request).json
        self.assertEqual(self.call('POST', invoice_path + '/finalize', final_request).json, final)
        self.assertEqual((final['status'], final['customer_id'], final['totals']['gross']), ('final', customer, '119.00'))
        self.assertEqual(final['archive_security'], 'postgresql_runtime_separated')
        self.assertEqual(final['number'], 'RE-' + self.today[:4] + '-000001')
        pdf = self.call('GET', invoice_path + '/pdf').data
        archive = self.office.db.execute('SELECT * FROM business_document_archives WHERE document_id=?', (invoice['id'],)).fetchone()
        self.assertTrue(pdf.startswith(b'%PDF-'))
        self.assertEqual(sha(pdf), archive['pdf_sha256'])
        self.assertEqual(sha(archive['payload_json'].encode()), archive['payload_sha256'])

        payment_body = request(source_id='synthetic-journey-bank-1', kind='receipt', amount='10.00',
            currency='EUR', booking_date=self.today, reference='Synthetic part payment',
            allocations=[{'document_id': invoice['id'], 'amount': '10.00'}])
        payment = self.call('POST', '/business/finance/payments', payment_body).json
        self.assertEqual(self.call('POST', '/business/finance/payments', payment_body).json, payment)
        outstanding = self.call('GET', '/business/finance/open-items?project_id=' + project).json['items']
        self.assertEqual(len(outstanding), 1)
        self.assertEqual((outstanding[0]['id'], outstanding[0]['paid'], outstanding[0]['open']), (invoice['id'], '10.00', '109.00'))

        adapter = self.call('POST', '/business/adapters', request(name='Synthetic local accounting review',
            profile='lexware_review_json_v1', enabled=True), status=201).json
        export_body = request(document_ids=[invoice['id']], include_payments=True,
            mapping={invoice['id']: {'remote_contact_id': 'SYNTHETIC-CONTACT'}})
        exported = self.call('POST', '/business/adapters/' + adapter['id'] + '/export', export_body, status=201).json
        self.assertEqual(self.call('POST', '/business/adapters/' + adapter['id'] + '/export', export_body, status=201).json, exported)
        artifact = base64.b64decode(exported['result']['artifact_base64'], validate=True)
        self.assertEqual(sha(artifact), exported['result']['sha256'])
        exported_data = json.loads(artifact)
        self.assertFalse(exported_data['native_api_payload'])
        self.assertFalse(exported_data['live_synchronized'])
        self.assertEqual(exported_data['documents'][0]['source_sha256'], archive['payload_sha256'])
        self.assertEqual(exported_data['payments_snapshot'][0]['selected_allocation_total'], '10.00')
        # Payments and export must not alter either original or frozen archive.
        self.assertEqual(sha(self.call('GET', source_path).data), sha(original))
        self.assertEqual(self.call('GET', invoice_path + '/pdf').data, pdf)
        self.assertTrue(business_documents.validate_integrity(self.office))


if __name__ == '__main__':
    unittest.main()
