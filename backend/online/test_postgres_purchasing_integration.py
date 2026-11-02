"""Real purchasing transactions, privileges and additive migration on PostgreSQL.

Only the explicitly guarded disposable loopback smartplan_check database is
used. No supplier, payment, mail or production system is contacted.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import threading
import unittest
from unittest.mock import patch
import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

import business_schema
from business_documents import Documents, render_prepared
from business_inventory import BusinessInventory
from business_purchasing import Purchasing, protected_tables, validate_integrity
from core import Problem
from online import release, test_online as base, test_business_journey_pg as journey
from online.store import migrate, PostgresOffice


@unittest.skipUnless(journey.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class PurchasingPostgres(unittest.TestCase):
    call = journey.BusinessJourneyPostgres.call
    login = journey.BusinessJourneyPostgres.login

    def setUp(self):
        journey.BusinessJourneyPostgres.setUp(self)
        self.owner = self.office.user(self.token)
        self.project = self.call('POST', '/projects', {'name': 'Synthetic purchasing project',
            'customer': 'Synthetic customer'}, status=201).json['id']
        self.location = self.call('POST', '/business/inventory/locations',
            journey.request(name='Synthetic stock'), status=201).json
        self.article = self.call('POST', '/business/articles', journey.request(code='PG-MATERIAL',
            name='Synthetic material', kind='material', unit='C62', unit_price_net='5.00',
            cost_price_net='2.00', tax_rate='19', currency='EUR', active=True)).json
        self.order = self.new_order()
        self.path = '/business/purchasing/orders/' + self.order['id']

    def new_order(self, *, items=None):
        return self.call('POST', '/business/inventory/orders', journey.request(project_id=self.project,
            supplier_name='Synthetic supplier', status='approved',
            items=items or [{'article_id': self.article['id'], 'quantity': '5'}]), status=201).json

    def confirmation(self, order=None):
        order = order or self.order
        return journey.request(source_revision=order['revision'], expected_receipt_revision=0,
            order_reference='SYNTHETIC-ORDER', ordered_on=self.today, confirmation=True)

    def receipt(self, **changes):
        values = dict(source_revision=self.order['revision'], expected_receipt_revision=0,
            receipt_reference='SYNTHETIC-DELIVERY-1', received_on=self.today, location_id=self.location['id'],
            lines=[{'line_index': 0, 'quantity': '2', 'unit_cost_net': '3.50'}])
        values.update(changes)
        return journey.request(**values)

    def counts(self):
        tables = (*protected_tables(), 'business_stock_movements', 'audit')
        return {name: self.office.db.execute('SELECT COUNT(*) FROM ' + name).fetchone()[0] for name in tables}

    def test_http_partial_final_restart_replay_integrity_and_runtime_ledger_grants(self):
        self.assertTrue(business_schema.require_runtime_security(self.office))
        confirmation = self.confirmation()
        confirmed = self.call('POST', self.path + '/confirm', confirmation).json
        self.assertEqual((confirmed['status'], confirmed['delivery_status']), ('ordered', 'not_sent'))
        first_body = self.receipt()
        first = self.call('POST', self.path + '/receipts', first_body, status=201).json
        partial = self.call('GET', self.path).json
        self.assertEqual((partial['status'], partial['items'][0]['remaining_quantity']), ('partially_received', '3.0000'))
        last = self.call('POST', self.path + '/receipts', self.receipt(expected_receipt_revision=1,
            receipt_reference='SYNTHETIC-DELIVERY-2',
            lines=[{'line_index': 0, 'quantity': '3', 'unit_cost_net': '4.00'}]), status=201).json
        before = self.counts()
        self.assertEqual(self.call('POST', self.path + '/receipts', first_body, status=201).json, first)
        self.assertEqual(self.call('POST', self.path + '/confirm', confirmation).json, confirmed)
        self.assertEqual(self.counts(), before)
        for table in protected_tables():
            for command in ('DELETE FROM ' + table, 'UPDATE ' + table + ' SET ' +
                            ('order_id=order_id' if table == 'business_purchase_confirmations' else
                             'id=id' if table == 'business_purchase_receipts' else
                             'receipt_id=receipt_id' if table == 'business_purchase_receipt_lines' else 'user_id=user_id'),
                            'TRUNCATE ' + table):
                with self.subTest(table=table, command=command), self.assertRaises(psycopg.errors.InsufficientPrivilege), self.office.db:
                    self.office.db.execute(command)
        reopened = PostgresOffice(self.office.db.dsn)
        try:
            actor = reopened.user(self.token)
            service = Purchasing(reopened)
            self.assertEqual(service.get(actor, self.order['id'])['status'], 'received')
            self.assertEqual(service.receipts(actor, self.order['id'])['items'], [first, last])
            stock = BusinessInventory(reopened).balance(actor, self.location['id'], self.article['id'])
            self.assertEqual((stock['on_hand'], stock['stock_value_net']), ('5.0000', '19.00'))
            self.assertTrue(validate_integrity(reopened))
            business_schema.validate_integrity(reopened)
        finally:
            reopened.db.close()

    def test_separate_connections_competing_for_last_delivery_commit_once(self):
        self.call('POST', self.path + '/confirm', self.confirmation())
        self.call('POST', self.path + '/receipts', self.receipt(), status=201)
        commands = [self.receipt(expected_receipt_revision=1, receipt_reference='LAST-' + suffix,
                    lines=[{'line_index': 0, 'quantity': '3', 'unit_cost_net': '4.00'}]) for suffix in ('A', 'B')]
        ready = threading.Barrier(2)

        def receive(body):
            worker = PostgresOffice(self.office.db.dsn)
            try:
                ready.wait(timeout=5)
                try:
                    return 201, Purchasing(worker).receive(self.owner, self.order['id'], body)
                except Problem as error:
                    return error.status, None
            finally:
                worker.db.close()

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(receive, commands))
        self.assertEqual(sorted(result[0] for result in results), [201, 409])
        self.assertEqual(self.counts()['business_purchase_receipts'], 2)
        self.assertEqual(self.counts()['business_stock_movements'], 2)
        stock = BusinessInventory(self.office).balance(self.owner, self.location['id'], self.article['id'])
        self.assertEqual((stock['on_hand'], stock['stock_value_net']), ('5.0000', '19.00'))
        self.assertTrue(validate_integrity(self.office))

    def test_failure_after_first_stock_post_rolls_back_header_lines_stock_and_receipt(self):
        second_article = self.call('POST', '/business/articles', journey.request(code='PG-SECOND',
            name='Second synthetic material', kind='material', unit='C62', unit_price_net='6.00',
            cost_price_net='3.00', tax_rate='19', currency='EUR', active=True)).json
        order = self.new_order(items=[{'article_id': self.article['id'], 'quantity': '2'},
                                      {'article_id': second_article['id'], 'quantity': '2'}])
        api = Purchasing(self.office)
        api.confirm(self.owner, order['id'], self.confirmation(order))
        body = self.receipt(source_revision=order['revision'], lines=[
            {'line_index': 0, 'quantity': '2', 'unit_cost_net': '3.50'},
            {'line_index': 1, 'quantity': '2', 'unit_cost_net': '4.00'}])
        before, original, calls = self.counts(), api.inventory._post_move, []

        def interrupted(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise RuntimeError('Synthetic failure after the first real PostgreSQL stock movement')
            return original(*args, **kwargs)

        with patch.object(api.inventory, '_post_move', side_effect=interrupted), self.assertRaises(RuntimeError):
            api.receive(self.owner, order['id'], body)
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.counts(), before)
        self.assertEqual(BusinessInventory(self.office).balance(
            self.owner, self.location['id'], self.article['id'])['on_hand'], '0.0000')
        self.assertEqual(len(api.receive(self.owner, order['id'], body)['lines']), 2)
        self.assertEqual(self.counts()['business_stock_movements'], before['business_stock_movements'] + 2)
        self.assertTrue(validate_integrity(self.office))

    def test_permission_revocation_is_fresh_before_idempotent_receipt_replay(self):
        user = self.call('POST', '/users', {'email': 'receiver@example.test',
            'password': 'Synthetic-receiver-password-123', 'role': 'technician'}, status=201).json['id']
        self.call('POST', '/assignments', {'project_id': self.project, 'user_id': user})
        grants = {}
        for permission in ('inventory.write', 'finance.write'):
            grants[permission] = self.call('POST', '/business/settings/permissions', journey.request(
                user_id=user, permission=permission, scope='*', effect='allow', revision=0)).json
        token = self.login('receiver@example.test', 'Synthetic-receiver-password-123')
        self.call('POST', self.path + '/confirm', self.confirmation())
        body = self.receipt()
        received = self.call('POST', self.path + '/receipts', body, token=token, status=201).json
        self.assertNotIn('unit_cost_net', received['lines'][0])
        before = self.counts()
        self.call('POST', '/business/settings/permissions', journey.request(user_id=user,
            permission='finance.write', scope='*', effect='deny', revision=grants['finance.write']['revision']))
        after_denial = self.counts()
        self.call('POST', self.path + '/receipts', body, token=token, status=403)
        self.assertEqual(self.counts(), after_denial)
        self.assertEqual(after_denial['business_purchase_receipts'], before['business_purchase_receipts'])
        self.call('POST', '/assignments', {'project_id': self.project, 'user_id': user, 'remove': True})
        self.call('GET', self.path, token=token, status=404)


@unittest.skipUnless(journey.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class PurchasingMigrationPostgres(unittest.TestCase):
    def test_additive_migration_preserves_real_issued_invoice_pdf_numbers_and_audit(self):
        prior = tuple(spec for spec in business_schema.registry() if spec.name != 'business_purchasing')
        with patch.object(business_schema, 'registry', return_value=prior):
            base.reset()
            bootstrap = PostgresOffice(journey.DSN)
            try:
                owner_id = bootstrap.add_user('migration@example.test', 'Synthetic-migration-password-123', 'owner')
                owner = dict(bootstrap.db.execute('SELECT * FROM users WHERE id=?', (owner_id,)).fetchone())
                project = bootstrap.add_project(owner, 'Synthetic prior project', 'Synthetic prior customer')
            finally:
                bootstrap.db.close()
            with psycopg.connect(journey.DSN) as connection:
                if not connection.execute("SELECT 1 FROM pg_roles WHERE rolname='smartplan-online'").fetchone():
                    connection.execute('CREATE ROLE "smartplan-online" LOGIN')
                connection.execute(sql.SQL('ALTER ROLE "smartplan-online" PASSWORD {}').format(
                    sql.Literal('synthetic-business-runtime-only')))
            release.secure_database(journey.DSN, test_mode=True)
            runtime_dsn = make_conninfo(journey.DSN, user='smartplan-online', password='synthetic-business-runtime-only')
            office = PostgresOffice(runtime_dsn)
            try:
                api = Documents(office, clock=lambda: datetime(2030, 1, 10, 12, tzinfo=timezone.utc))
                api.save_settings(owner, journey.request(revision=0, company_name='Synthetic Seller GmbH',
                    address_line='Synthetic Street 1', postal_code='10115', city='Berlin', country='DE',
                    vat_id='DE123456789', email='seller@example.test', issuer_mode='own', issuing_enabled=True,
                    cutover_ack=True, cutover_date='2029-01-01', einvoice_format='none'))
                draft = api.create(owner, journey.request(project_id=project, kind='invoice',
                    title='Synthetic prior invoice', issue_date='2030-01-10', due_date='2030-01-24',
                    buyer={'name': 'Synthetic Buyer', 'address_line': 'Synthetic Street 2',
                           'postal_code': '10117', 'city': 'Berlin', 'country': 'DE', 'email': 'buyer@example.test'},
                    positions=[{'description': 'Synthetic service', 'quantity': '1', 'unit': 'HUR',
                                'unit_price_net': '100.00', 'tax_rate': '19', 'kind': 'labor'}]))
                prepared = api.prepare_finalization(owner, draft['id'], draft['revision'])
                issued = api.finalize(owner, draft['id'], render_prepared(prepared), uuid.uuid4().hex)
                self.assertEqual(issued['archive_security'], 'postgresql_runtime_separated')
                original_pdf = api.archive(owner, draft['id'], 'pdf')
                self.assertTrue(original_pdf.startswith(b'%PDF-'))
                before = release.snapshot_fingerprint(journey.DSN)
                self.assertNotIn('business_purchase_receipts', before)
            finally:
                office.db.close()
        migrate(journey.DSN, owner_role='smartplan-migrator', compatibility_mode='business', require_business_modules=True)
        release.secure_database(journey.DSN, test_mode=True)
        after = release.snapshot_fingerprint(journey.DSN)
        for table, fingerprint in before.items():
            if table != 'business_schema_migrations':
                self.assertEqual(after[table], fingerprint, table)
        office = PostgresOffice(runtime_dsn)
        try:
            self.assertTrue(business_schema.require_runtime_security(office))
            api = Documents(office)
            self.assertEqual(api.get(owner, draft['id']), issued)
            self.assertEqual(api.archive(owner, draft['id'], 'pdf'), original_pdf)
            self.assertEqual(office.db.execute('SELECT COUNT(*) FROM business_purchase_receipts').fetchone()[0], 0)
            self.assertTrue(validate_integrity(office))
            business_schema.validate_integrity(office)
        finally:
            office.db.close()


if __name__ == '__main__':
    unittest.main()
