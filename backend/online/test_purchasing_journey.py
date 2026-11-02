"""Independent acceptance C through real Flask routes and persisted test data.

No supplier, payment, message, external API or production service is contacted.
SQLite exercises the shared domain and HTTP contracts; PostgreSQL acceptance
is a separate suite. A local order confirmation never claims a supplier send.
"""
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
import uuid

from cryptography.fernet import Fernet

from core import Office
from online.auth import totp
from online.web import create_app


def request(**value):
    return {'request_id': uuid.uuid4().hex, **value}


class PurchasingJourneyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic-purchasing-journey-')
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / 'company.sqlite3'
        self.office = Office(self.database)
        self.addCleanup(lambda: self.office.db.close())
        self.office.db.executescript('''
          CREATE TABLE mfa(user_id TEXT PRIMARY KEY REFERENCES users(id),secret TEXT NOT NULL,
            last_step BIGINT NOT NULL DEFAULT -1,recovery TEXT NOT NULL);
          CREATE TABLE auth_challenges(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),
            credential TEXT NOT NULL,secret TEXT NOT NULL,expiry DOUBLE PRECISION NOT NULL,
            failures INTEGER NOT NULL DEFAULT 0);
          CREATE TABLE login_limits(key TEXT PRIMARY KEY,failures INTEGER NOT NULL,reset_at DOUBLE PRECISION NOT NULL);
        ''')
        self.office.add_user('owner@example.test', 'Synthetic-owner-password-123', 'owner')
        self.key = Fernet.generate_key()
        self.open_app()
        self.token = self.login('owner@example.test', 'Synthetic-owner-password-123')
        self.project = self.call('/projects', {'name': 'Synthetischer Kundenauftrag',
            'customer': 'Synthetischer Betreiber'}, status=201).json['id']
        self.location = self.call('/business/inventory/locations', request(name='Synthetisches Hauptlager'), status=201).json
        self.article = self.article_record('SYN-DEVICE')

    def open_app(self):
        self.client = create_app(office=self.office, key=self.key, host='purchasing.example.test',
                                 storage_config={}).test_client()

    def call(self, path, body=None, *, token='owner', status=200, method=None):
        token = self.token if token == 'owner' else token
        reply = self.client.open('/api/v1' + path, method=method or ('POST' if body is not None else 'GET'),
            base_url='https://purchasing.example.test', json=body,
            headers={'Authorization': 'Bearer ' + token} if token else {})
        self.assertEqual(reply.status_code, status, (path, reply.data[:350]))
        return reply

    def login(self, email, password):
        pending = self.call('/login', {'email': email, 'password': password}, token=None).json
        result = self.call('/login/verify', {'challenge': pending['challenge'],
            'code': totp(pending['enrollment']['secret'], int(time.time() // 30))}, token=None).json
        return result['token']

    def article_record(self, code):
        return self.call('/business/articles', request(code=code, name='Synthetisches Steuergerät ' + code,
            kind='material', unit='Stk', unit_price_net='20.0000', cost_price_net='9.0000',
            tax_rate='19', tax_category='S', currency='EUR', active=True)).json

    def order(self, *, project=None, items=None, confirm=True):
        order = self.call('/business/inventory/orders', request(project_id=project or self.project,
            supplier_name='Synthetischer Lieferant GmbH', status='approved',
            items=items or [{'article_id': self.article['id'], 'quantity': '10.0000'}]), status=201).json
        value = self.call('/business/purchasing/orders/' + order['id']).json
        if confirm:
            value = self.call('/business/purchasing/orders/' + order['id'] + '/confirm',
                request(source_revision=value['source_revision'], expected_receipt_revision=0,
                        order_reference='SYN-BEST-' + order['id'][:8], ordered_on='2026-11-01', confirmation=True)).json
        return value

    def receipt_body(self, order, quantity='3.0000', price='10.2500', **changes):
        return request(source_revision=order['source_revision'], expected_receipt_revision=order['receipt_revision'],
            receipt_reference='SYN-LIEF-' + uuid.uuid4().hex[:8], received_on='2026-11-02',
            location_id=self.location['id'], lines=[{'line_index': 0, 'quantity': quantity,
                                                   'unit_cost_net': price}], **changes)

    def stock(self, article=None):
        return self.call('/business/inventory/stock?location_id=' + self.location['id'] +
                         '&article_id=' + (article or self.article)['id']).json

    def costs(self):
        return self.call('/business/projects/' + self.project + '/costs').json

    def grant(self, user, permission, *, effect='allow', revision=0):
        return self.call('/business/settings/permissions', request(user_id=user, permission=permission,
            scope='*', effect=effect, revision=revision)).json

    def test_partial_and_final_delivery_issue_valuation_and_signed_maintenance_survive_restart(self):
        order = self.order()
        order_path = '/business/purchasing/orders/' + order['id']
        self.assertEqual((order['status'], order['delivery_status'], order['receipt_revision']), ('ordered', 'not_sent', 0))
        self.assertEqual(self.stock()['on_hand'], '0.0000')
        partial_body = self.receipt_body(order)
        partial = self.call(order_path + '/receipts', partial_body, status=201).json
        self.assertEqual(self.call(order_path + '/receipts', partial_body, status=201).json, partial)
        order = self.call(order_path).json
        self.assertEqual((order['status'], order['items'][0]['received_quantity'], order['items'][0]['remaining_quantity']),
                         ('partially_received', '3.0000', '7.0000'))
        self.assertEqual((self.stock()['on_hand'], self.stock()['stock_value_net']), ('3.0000', '30.75'))
        self.assertEqual(self.costs()['material_actual_net'], '0.00')
        duplicate = dict(partial_body, request_id=uuid.uuid4().hex, expected_receipt_revision=order['receipt_revision'])
        self.call(order_path + '/receipts', duplicate, status=409)
        stale = dict(self.receipt_body(order), expected_receipt_revision=0)
        self.call(order_path + '/receipts', stale, status=409)
        final = self.call(order_path + '/receipts', self.receipt_body(order, '7.0000', '12.0000'), status=201).json
        order = self.call(order_path).json
        self.assertEqual((order['status'], order['receipt_revision'], order['items'][0]['remaining_quantity']), ('received', 2, '0.0000'))
        self.assertEqual(self.stock()['stock_value_net'], '114.75')
        self.assertEqual(self.costs()['material_actual_net'], '0.00')
        self.assertEqual(len(self.call(order_path + '/receipts').json['items']), 2)
        for receipt in (partial, final):
            movement = self.call('/business/inventory/movements/' + receipt['lines'][0]['movement_id']).json
            self.assertEqual(movement['kind'], 'receive')
            self.assertEqual(movement['quantity'], receipt['lines'][0]['quantity'])
            self.assertEqual(movement['cost_net'], receipt['lines'][0]['cost_net'])

        # An article price change must not revalue stock already received.
        self.call('/business/articles/' + self.article['id'], request(revision=self.article['revision'], cost_price_net='99.0000'))
        issue_body = request(kind='issue', article_id=self.article['id'], from_location_id=self.location['id'],
                             project_id=self.project, quantity='4.0000')
        issue = self.call('/business/inventory/movements', issue_body, status=201).json
        self.assertEqual(self.call('/business/inventory/movements', issue_body, status=201).json, issue)
        self.assertEqual((issue['unit_cost_net'], issue['cost_net']), ('11.4750', '45.9000'))
        self.assertEqual((self.stock()['on_hand'], self.stock()['stock_value_net']), ('6.0000', '68.85'))
        costs = self.costs()
        self.assertEqual((costs['material_actual_net'], costs['actual_net']), ('45.90', '45.90'))
        self.assertEqual([row['id'] for row in costs['material_movements']], [issue['id']])

        asset = self.call('/business/assets', request(project_id=self.project, name=self.article['name'],
            serial_number='SYN-GERAET-001', notes='Bestellung ' + order['id'] + '; Entnahme ' + issue['id']), status=201).json
        contract = self.call('/business/maintenance/contracts', request(project_id=self.project, asset_id=asset['id'],
            title='Synthetische regelmäßige Prüfung', anchor_date='2026-11-02', interval_unit='months', interval_count=12), status=201).json
        schedule = request(project_id=self.project, as_of='2026-11-02')
        visits = self.call('/business/maintenance/schedule', schedule).json
        self.assertEqual(self.call('/business/maintenance/schedule', schedule).json, visits)
        self.assertEqual(self.call('/business/maintenance/schedule', request(project_id=self.project, as_of='2026-11-02')).json['items'], [])
        self.assertEqual(len(visits['items']), 1)
        visit = visits['items'][0]
        self.assertEqual(visit['contract_id'], contract['id'])
        report = self.call('/business/service-reports', request(project_id=self.project,
            title='Synthetischer Wartungsbericht', description='Funktionsprüfung des gelieferten Geräts'), status=201).json
        signed = self.call('/business/service-reports/' + report['id'] + '/sign', request(project_id=self.project,
            revision=report['revision'], expected_hash=report['content_hash'], signer='Synthetischer Betreiber',
            strokes=[[[0.1, 0.2], [0.8, 0.6]]])).json
        pdf = self.call('/business/service-reports/' + report['id'] + '/pdf').data
        completed = self.call('/business/maintenance/visits/' + visit['id'] + '/complete', request(project_id=self.project,
            revision=visit['revision'], report_id=signed['id'])).json
        self.assertEqual(completed['report_pdf_sha256'], hashlib.sha256(pdf).hexdigest())

        self.office.db.close()
        self.office = Office(self.database)
        self.open_app()
        self.assertEqual(self.call(order_path).json['status'], 'received')
        self.assertEqual(len(self.call(order_path + '/receipts').json['items']), 2)
        self.assertEqual(self.stock()['on_hand'], '6.0000')
        self.assertEqual(self.costs()['actual_net'], '45.90')
        history = self.call('/business/maintenance/history?project_id=' + self.project + '&asset_id=' + asset['id']).json['items']
        self.assertEqual([(item['id'], item['status']) for item in history], [(visit['id'], 'completed')])
        self.assertEqual(history[0]['asset_snapshot']['serial_number'], 'SYN-GERAET-001')
        self.assertEqual(self.call('/business/service-reports/' + report['id'] + '/pdf').data, pdf)
        from business_schema import validate_integrity
        self.assertTrue(validate_integrity(self.office))

    def test_receipt_prices_and_order_scope_are_checked_on_reads_writes_and_replay(self):
        order = self.order()
        path = '/business/purchasing/orders/' + order['id']
        user = self.call('/users', {'email': 'receiver@example.test', 'password': 'Synthetic-receiver-password-123',
            'role': 'technician'}, status=201).json['id']
        self.call('/assignments', {'project_id': self.project, 'user_id': user})
        token = self.login('receiver@example.test', 'Synthetic-receiver-password-123')
        body = self.receipt_body(order)
        self.call(path + '/receipts', body, token=token, status=403)
        self.grant(user, 'inventory.write')
        self.call(path + '/receipts', body, token=token, status=403)
        self.grant(user, 'finance.write')
        receipt = self.call(path + '/receipts', body, token=token, status=201).json
        self.assertNotIn('unit_cost_net', json.dumps(receipt))
        self.assertNotIn('cost_net', json.dumps(self.call(path + '/receipts', token=token).json))
        self.grant(user, 'finance.write', effect='deny', revision=1)
        self.call(path + '/receipts', body, token=token, status=403)
        self.assertEqual(len(self.call(path + '/receipts').json['items']), 1)
        other = self.call('/projects', {'name': 'Vertraulicher anderer Auftrag', 'customer': 'Anderer Kunde'}, status=201).json['id']
        foreign = self.order(project=other)
        listing = self.call('/business/purchasing/orders', token=token).json['items']
        self.assertEqual([row['id'] for row in listing], [order['id']])
        self.call('/business/purchasing/orders/' + foreign['id'], token=token, status=404)
        self.call('/business/purchasing/orders/' + foreign['id'] + '/receipts', token=token, status=404)
        self.call('/assignments', {'project_id': self.project, 'user_id': user, 'remove': True})
        self.call(path, token=token, status=404)
        self.call(path + '/receipts', body, token=token, status=404)

    def test_overdelivery_batch_and_changed_article_unit_leave_stock_unchanged(self):
        other_article = self.article_record('SYN-SPARE')
        order = self.order(items=[{'article_id': self.article['id'], 'quantity': '10'},
                                  {'article_id': other_article['id'], 'quantity': '5'}])
        path = '/business/purchasing/orders/' + order['id']
        body = self.receipt_body(order)
        body['lines'] = [{'line_index': 0, 'quantity': '1', 'unit_cost_net': '1'},
                         {'line_index': 1, 'quantity': '6', 'unit_cost_net': '1'}]
        self.call(path + '/receipts', body, status=409)
        self.assertEqual((self.stock()['on_hand'], self.stock(other_article)['on_hand']), ('0.0000', '0.0000'))
        self.assertEqual(self.call(path).json['receipt_revision'], 0)
        self.assertEqual(self.call(path + '/receipts').json['items'], [])
        self.call('/business/articles/' + self.article['id'], request(revision=self.article['revision'], unit='m'), status=409)
        # Old databases may already contain an inconsistent article unit. Only
        # this synthetic legacy fixture bypasses the new catalog update guard.
        with self.office.db:
            row = self.office.db.execute('SELECT payload_json FROM business_articles WHERE id=?', (self.article['id'],)).fetchone()
            payload = dict(json.loads(row['payload_json']), unit='m')
            self.office.db.execute('UPDATE business_articles SET payload_json=? WHERE id=?',
                                   (json.dumps(payload), self.article['id']))
        self.call(path + '/receipts', self.receipt_body(order), status=409)
        self.assertEqual(self.stock()['on_hand'], '0.0000')
        self.assertEqual(self.call(path + '/receipts').json['items'], [])

    def test_disabled_material_stops_confirm_and_receipts_but_keeps_history_readable(self):
        order = self.order()
        path = '/business/purchasing/orders/' + order['id']
        receipt = self.call(path + '/receipts', self.receipt_body(order), status=201).json
        pending = self.order(confirm=False)
        organization = self.call('/business/organization').json
        modules = {name: {'visible': value['visibility_override'], 'enabled': value['enabled']}
                   for name, value in organization['modules'].items()}
        modules['material']['enabled'] = False
        self.call('/business/organization', request(revision=organization['revision'], needs=organization['needs'], modules=modules))
        current = self.call(path).json
        self.call(path + '/receipts', self.receipt_body(current), status=423)
        self.call('/business/purchasing/orders/' + pending['id'] + '/confirm', request(
            source_revision=pending['source_revision'], expected_receipt_revision=0,
            order_reference='SYN-DISABLED', ordered_on='2026-11-01', confirmation=True), status=423)
        self.assertEqual(self.call(path + '/receipts').json['items'], [receipt])
        self.assertEqual(self.stock()['on_hand'], '3.0000')


if __name__ == '__main__':
    unittest.main()
