"""Synthetic order-to-stock receipts, authorization, replay and concurrency.

No supplier, SMTP, bank or production data is used. Both SQLite connections in
the race test point at this fixture's disposable local database.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
import uuid

from core import Office, Problem, canonical
from business_documents import Documents, schema_statements as document_schema
from business_foundation import schema_statements as foundation_schema
from business_inventory import BusinessInventory, schema_statements as inventory_schema
from business_operations import schema_statements as operation_schema
from business_planning import schema_statements as planning_schema
from business_time import schema_statements as time_schema
from business_purchasing import Purchasing, schema_statements, guard_statements, validate_integrity, dispatch, methods


class PurchasingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / 'office.db'
        self.office = Office(self.database)
        self.addCleanup(self.office.db.close)
        for loader in (foundation_schema, document_schema, operation_schema, planning_schema,
                       time_schema, inventory_schema, schema_statements):
            for statement in loader('BLOB'):
                self.office.db.execute(statement)
        for statement in guard_statements('sqlite'):
            self.office.db.execute(statement)
        self.office.db.commit()
        self.owner = self.actor('owner')
        self.tech = self.actor('technician')
        self.outsider = self.actor('technician')
        self.project = self.office.add_project(self.owner, 'Synthetic purchase project', 'Synthetic customer')
        self.other = self.office.add_project(self.owner, 'Private purchase project', 'Private customer')
        self.office.assign(self.owner, self.project, self.tech['id'])
        self.clock = lambda: datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
        self.inventory = BusinessInventory(self.office, clock=self.clock)
        self.api = Purchasing(self.office, clock=self.clock)
        self.location = self.inventory.save_location(self.owner, self.req(name='Synthetic stock'))
        self.article = Documents(self.office).save_article(self.owner, self.req(
            code='SYN-M', name='Synthetic cable', kind='material', unit='m',
            unit_price_net='5.0000', cost_price_net='2.0000', tax_rate='19',
            tax_category='S', currency='EUR', active=True))
        self.order = self.make_order()

    def actor(self, role):
        email = uuid.uuid4().hex + '@example.test'
        return dict(id=self.office.add_user(email, 'Synthetic-password-123', role), role=role, email=email)

    def req(self, **data):
        return dict(request_id=uuid.uuid4().hex, **data)

    def error(self, status, function, *args):
        with self.assertRaises(Problem) as caught:
            function(*args)
        self.assertEqual(caught.exception.status, status, caught.exception.message)

    def grant(self, actor, *permissions, scope='*'):
        with self.office.db:
            for permission in permissions:
                self.office.db.execute('INSERT INTO business_permission_grants(id,user_id,permission,scope,effect,'
                    'revision,updated_by,updated_at) VALUES(?,?,?,?,?,1,?,?)',
                    (uuid.uuid4().hex, actor['id'], permission, scope, 'allow', self.owner['id'], self.api.now()))

    def make_order(self, *, status='approved', items=None, project=None):
        return self.inventory.save_order(self.owner, self.req(project_id=project or self.project,
            supplier_name='Synthetic supplier', status=status,
            items=items or [{'article_id': self.article['id'], 'quantity': '5'}]))

    def confirmation(self, **changes):
        return self.req(**{**dict(source_revision=self.order['revision'], expected_receipt_revision=0,
            order_reference='PO-17', ordered_on='2026-10-30', confirmation=True), **changes})

    def confirm(self, actor=None):
        return self.api.confirm(actor or self.owner, self.order['id'], self.confirmation())

    def receipt(self, **changes):
        return self.req(**{**dict(source_revision=self.order['revision'], expected_receipt_revision=0,
            receipt_reference='DEL-17', received_on='2026-11-01', location_id=self.location['id'],
            lines=[{'line_index': 0, 'quantity': '2', 'unit_cost_net': '3.5000'}]), **changes})

    def receive(self, **changes):
        return self.api.receive(self.owner, self.order['id'], self.receipt(**changes))

    def counts(self):
        tables = ('business_purchase_confirmations', 'business_purchase_receipts',
                  'business_purchase_receipt_lines', 'business_purchasing_requests', 'business_stock_movements', 'audit')
        return {table: self.office.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0] for table in tables}

    def test_partial_and_remaining_receipts_survive_reopen_without_double_stock(self):
        self.assertEqual(self.api.get(self.owner, self.order['id'])['status'], 'approved')
        confirm_body = self.confirmation()
        confirmed = self.api.confirm(self.owner, self.order['id'], confirm_body)
        self.assertEqual((confirmed['status'], confirmed['receipt_revision'], confirmed['delivery_status']), ('ordered', 0, 'not_sent'))
        body = self.receipt()
        first = self.api.receive(self.owner, self.order['id'], body)
        partial = self.api.get(self.owner, self.order['id'])
        self.assertEqual((partial['status'], partial['receipt_revision']), ('partially_received', 1))
        self.assertEqual(partial['items'][0]['remaining_quantity'], '3.0000')
        second = self.receive(expected_receipt_revision=1, receipt_reference='DEL-18',
            lines=[{'line_index': 0, 'quantity': '3', 'unit_cost_net': '4.0000'}])
        self.assertEqual(second['receipt_revision'], 2)
        self.assertEqual(self.api.receive(self.owner, self.order['id'], body), first)
        self.assertEqual(self.api.confirm(self.owner, self.order['id'], confirm_body), confirmed)
        fresh = Office(self.database)
        self.addCleanup(fresh.db.close)
        reopened = Purchasing(fresh)
        result = reopened.get(self.owner, self.order['id'])
        self.assertEqual((result['status'], result['receipt_revision'], result['delivery_status']), ('received', 2, 'not_sent'))
        self.assertEqual(result['items'][0]['received_quantity'], '5.0000')
        self.assertEqual(reopened.receipts(self.owner, self.order['id'])['items'], [first, second])
        balance = BusinessInventory(fresh).balance(self.owner, self.location['id'], self.article['id'])
        self.assertEqual((balance['on_hand'], balance['stock_value_net']), ('5.0000', '19.00'))
        self.assertTrue(validate_integrity(fresh))

    def test_proposal_must_be_approved_and_external_order_explicitly_confirmed(self):
        draft = self.make_order(status='draft')
        self.assertEqual(self.api.get(self.owner, draft['id'])['status'], 'proposal')
        self.error(409, self.api.confirm, self.owner, draft['id'], self.confirmation())
        self.error(409, self.api.receive, self.owner, self.order['id'], self.receipt())
        self.error(400, self.api.confirm, self.owner, self.order['id'], {**self.confirmation(), 'confirmation': False})
        approved = self.inventory.save_order(self.owner, self.req(revision=draft['revision'], project_id=self.project,
            supplier_name=draft['supplier_name'], items=[{'article_id': self.article['id'], 'quantity': '5'}], status='approved'), draft['id'])
        confirmed = self.api.confirm(self.owner, draft['id'], {**self.confirmation(), 'source_revision': approved['revision']})
        self.assertEqual(confirmed['status'], 'ordered')
        self.assertEqual(confirmed['delivery_status'], 'not_sent')
        self.assertEqual(self.counts()['business_stock_movements'], 0)
        self.error(409, self.api.confirm, self.owner, draft['id'], {**self.confirmation(), 'source_revision': approved['revision']})

    def test_source_and_receipt_revisions_prevent_stale_mutations(self):
        self.error(409, self.api.confirm, self.owner, self.order['id'], {**self.confirmation(), 'source_revision': 99})
        self.error(409, self.api.confirm, self.owner, self.order['id'], {**self.confirmation(), 'expected_receipt_revision': True})
        self.confirm()
        self.receive()
        before = self.counts()
        for changes in ({'expected_receipt_revision': 0}, {'source_revision': 2, 'expected_receipt_revision': 1},
                        {'source_revision': True, 'expected_receipt_revision': 1}):
            self.error(409, self.api.receive, self.owner, self.order['id'], self.receipt(**changes))
        self.assertEqual(self.counts(), before)

    def test_reference_is_unique_per_order_even_with_new_request_and_unicode_spelling(self):
        self.confirm()
        first = self.receive(receipt_reference='BL 17')
        before = self.counts()
        self.error(409, self.api.receive, self.owner, self.order['id'], self.receipt(
            expected_receipt_revision=1, receipt_reference='  ｂｌ  １７  '))
        self.assertEqual(self.counts(), before)
        self.assertEqual(first['receipt_reference'], 'BL 17')
        other_order = self.make_order()
        self.api.confirm(self.owner, other_order['id'], self.confirmation())
        self.api.receive(self.owner, other_order['id'], self.receipt(receipt_reference='BL 17'))
        self.assertEqual(self.counts()['business_purchase_receipts'], 2)

    def test_invalid_lines_and_overdelivery_leave_no_header_or_stock(self):
        self.confirm()
        before = self.counts()
        base = {'line_index': 0, 'quantity': '2', 'unit_cost_net': '3.5'}
        invalid = [[{**base, 'line_index': value}] for value in (-1, 1, True, '0', None)]
        invalid += [[base, base], [], [{}], 'bad', [{**base, 'quantity': '0'}],
            [{**base, 'quantity': '-1'}], [{**base, 'quantity': 2}], [{**base, 'quantity': 'NaN'}],
            [{**base, 'unit_cost_net': '-1'}], [{**base, 'unit_cost_net': 'Infinity'}],
            [{**base, 'unit_cost_net': '0.00001'}], [{**base, 'extra': True}],
            [{'line_index': 0, 'quantity': '1'}]]
        for lines in invalid:
            with self.subTest(lines=lines):
                self.error(400, self.api.receive, self.owner, self.order['id'], self.receipt(lines=lines))
                self.assertEqual(self.counts(), before)
        self.error(409, self.api.receive, self.owner, self.order['id'], self.receipt(lines=[{**base, 'quantity': '6'}]))
        self.error(400, self.api.receive, self.owner, self.order['id'], self.receipt(lines=[{**base, 'unit_cost_net': '999999999999.9999'}]))
        self.assertEqual(self.counts(), before)

    def test_duplicate_article_order_positions_are_distinct_and_bound_by_index(self):
        self.order = self.make_order(items=[{'article_id': self.article['id'], 'quantity': '2'},
                                           {'article_id': self.article['id'], 'quantity': '3'}])
        self.confirm()
        result = self.receive(lines=[{'line_index': 1, 'quantity': '3', 'unit_cost_net': '1.25'}])
        self.assertEqual(result['lines'][0]['line_index'], 1)
        remaining = self.api.get(self.owner, self.order['id'])['items']
        self.assertEqual([item['remaining_quantity'] for item in remaining], ['2.0000', '0.0000'])
        self.assertTrue(validate_integrity(self.office))

    def test_project_scope_applies_to_detail_list_confirmation_receipts_and_replay(self):
        private_order = self.make_order(project=self.other)
        self.confirm()
        self.grant(self.tech, 'inventory.write', 'finance.write', 'finance.approve')
        body = self.receipt()
        self.api.receive(self.tech, self.order['id'], body)
        self.error(404, self.api.get, self.tech, private_order['id'])
        self.error(404, self.api.receipts, self.tech, private_order['id'])
        self.error(404, self.api.confirm, self.tech, private_order['id'], self.confirmation())
        self.error(404, self.api.receive, self.tech, private_order['id'], self.receipt())
        listed = self.api.orders(self.tech)['items']
        self.assertEqual([item['id'] for item in listed], [self.order['id']])
        self.error(404, self.api.get, self.outsider, self.order['id'])
        self.error(400, self.api.receive, self.tech, self.order['id'], {**self.receipt(expected_receipt_revision=1), 'project_id': self.other})
        self.office.assign(self.owner, self.project, self.tech['id'], remove=True)
        self.error(404, self.api.receive, self.tech, self.order['id'], body)
        self.assertEqual(self.api.orders(self.tech)['items'], [])

    def test_finance_write_and_approval_are_rechecked_before_replay(self):
        self.grant(self.tech, 'inventory.write', 'finance.approve')
        confirmation = self.confirmation()
        self.api.confirm(self.tech, self.order['id'], confirmation)
        self.error(403, self.api.receive, self.tech, self.order['id'], self.receipt())
        self.grant(self.tech, 'finance.write')
        receipt = self.receipt()
        self.api.receive(self.tech, self.order['id'], receipt)
        with self.office.db:
            self.office.db.execute("DELETE FROM business_permission_grants WHERE user_id=? AND permission IN ('finance.write','finance.approve')", (self.tech['id'],))
        self.error(403, self.api.receive, self.tech, self.order['id'], receipt)
        self.error(403, self.api.confirm, self.tech, self.order['id'], confirmation)
        self.assertEqual(self.counts()['business_stock_movements'], 1)

    def test_financial_fields_are_redacted_on_read_and_replayed_write(self):
        self.confirm()
        self.grant(self.tech, 'inventory.write', 'finance.write', 'finance.read')
        body = self.receipt()
        first = self.api.receive(self.tech, self.order['id'], body)
        self.assertEqual(first['lines'][0]['cost_net'], '7.0000')
        with self.office.db:
            self.office.db.execute("DELETE FROM business_permission_grants WHERE user_id=? AND permission='finance.read'", (self.tech['id'],))
        replay = self.api.receive(self.tech, self.order['id'], body)
        self.assertEqual(replay['id'], first['id'])
        for value in (replay, self.api.receipts(self.tech, self.order['id']), self.api.get(self.tech, self.order['id']), self.api.orders(self.tech)):
            encoded = json.dumps(value)
            for field in ('unit_cost_net', 'cost_net', 'cost_price_net', 'unit_price_net'):
                self.assertNotIn(field, encoded)
        self.assertTrue(validate_integrity(self.office))

    def test_scoped_grants_and_global_deny_apply(self):
        self.confirm()
        self.grant(self.tech, 'inventory.write', 'finance.write', scope=self.project)
        self.api.receive(self.tech, self.order['id'], self.receipt())
        with self.office.db:
            self.office.db.execute('INSERT INTO business_permission_grants(id,user_id,permission,scope,effect,revision,updated_by,updated_at) '
                'VALUES(?,?,?,?,?,1,?,?)', (uuid.uuid4().hex, self.tech['id'], 'inventory.read', '*', 'deny', self.owner['id'], self.api.now()))
        self.error(403, self.api.get, self.tech, self.order['id'])
        self.error(403, self.api.orders, self.tech, self.project)

    def test_frozen_order_identity_survives_price_name_change_and_receipt_uses_actual_cost(self):
        self.confirm()
        Documents(self.office).save_article(self.owner, self.req(revision=self.article['revision'],
            name='Renamed article', cost_price_net='99.0000'), self.article['id'])
        result = self.receive()
        self.assertEqual(result['lines'][0]['article_name'], 'Synthetic cable')
        self.assertEqual(result['lines'][0]['unit_cost_net'], '3.5000')
        movement = self.office.db.execute('SELECT * FROM business_stock_movements WHERE id=?', (result['lines'][0]['movement_id'],)).fetchone()
        self.assertEqual(json.loads(movement['article_snapshot_json'])['name'], 'Renamed article')
        self.assertEqual(self.api.get(self.owner, self.order['id'])['items'][0]['unit'], 'm')
        self.assertTrue(validate_integrity(self.office))

    def test_legacy_article_unit_or_kind_change_is_rejected_without_conversion(self):
        self.confirm()
        original = self.office.db.execute('SELECT payload_json FROM business_articles WHERE id=?', (self.article['id'],)).fetchone()[0]
        before = self.counts()
        for change in ({'unit': 'piece'}, {'kind': 'machine'}):
            with self.subTest(change=change):
                with self.office.db:
                    self.office.db.execute('UPDATE business_articles SET payload_json=? WHERE id=?',
                        (canonical(dict(json.loads(original), **change)), self.article['id']))
                self.error(409, self.api.receive, self.owner, self.order['id'], self.receipt())
                self.assertEqual(self.counts(), before)

    def test_competing_connections_accept_only_one_receipt_revision(self):
        self.confirm()
        second = Office(self.database)
        self.addCleanup(second.db.close)
        barrier = threading.Barrier(2)
        def run(api):
            barrier.wait(timeout=5)
            try:
                return api.receive(self.owner, self.order['id'], self.receipt(receipt_reference=uuid.uuid4().hex,
                    lines=[{'line_index': 0, 'quantity': '4', 'unit_cost_net': '2'}]))
            except Problem as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, (self.api, Purchasing(second))))
        self.assertEqual(sum(isinstance(value, dict) for value in results), 1)
        self.assertIn(409, results)
        self.assertEqual(self.inventory.balance(self.owner, self.location['id'], self.article['id'])['on_hand'], '4.0000')
        self.assertEqual(self.api.get(self.owner, self.order['id'])['receipt_revision'], 1)
        self.assertTrue(validate_integrity(self.office))

    def test_stock_failure_rolls_back_header_lines_first_movement_request_and_audit(self):
        self.order = self.make_order(items=[{'article_id': self.article['id'], 'quantity': '2'},
                                           {'article_id': self.article['id'], 'quantity': '3'}])
        self.confirm()
        original = self.api.inventory._post_move
        calls = []
        def fail_second(actor, body):
            calls.append(body)
            if len(calls) == 2:
                raise RuntimeError('Synthetic second line failure')
            return original(actor, body)
        before = self.counts()
        with patch.object(self.api.inventory, '_post_move', side_effect=fail_second):
            with self.assertRaises(RuntimeError):
                self.receive(lines=[{'line_index': 0, 'quantity': '1', 'unit_cost_net': '2'},
                                    {'line_index': 1, 'quantity': '1', 'unit_cost_net': '2'}])
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.api.get(self.owner, self.order['id'])['status'], 'ordered')

    def test_final_audit_failure_rolls_back_stock_and_receipt(self):
        self.confirm()
        before = self.counts()
        with patch.object(self.office, 'audit', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.receive()
        self.assertEqual(self.counts(), before)

    def test_source_snapshot_tampering_is_detected(self):
        self.confirm()
        source = json.loads(self.office.db.execute('SELECT payload_json FROM business_purchase_orders WHERE id=?', (self.order['id'],)).fetchone()[0])
        source[0]['quantity'] = '8.0000'
        with self.office.db:
            self.office.db.execute('UPDATE business_purchase_orders SET payload_json=? WHERE id=?', (canonical(source), self.order['id']))
        self.error(500, self.api.get, self.owner, self.order['id'])
        self.error(500, self.api.receive, self.owner, self.order['id'], self.receipt())
        with self.assertRaises(ValueError):
            validate_integrity(self.office)

    def test_append_only_history_rejects_updates_and_deletion(self):
        self.confirm()
        self.receive()
        for table, column in (('business_purchase_confirmations', 'order_reference'),
                              ('business_purchase_receipts', 'receipt_reference'),
                              ('business_purchase_receipt_lines', 'quantity'),
                              ('business_purchasing_requests', 'request_hash')):
            for statement in ('UPDATE ' + table + ' SET ' + column + '=' + column, 'DELETE FROM ' + table):
                with self.subTest(statement=statement):
                    with self.assertRaises(sqlite3.IntegrityError):
                        with self.office.db:
                            self.office.db.execute(statement)
        self.assertTrue(validate_integrity(self.office))

    def test_sqlite_replace_cannot_bypass_any_append_only_key(self):
        self.confirm()
        receipt = self.receive()
        # Explicitly retain SQLite's usual nonrecursive setting: the guard
        # must hold without depending on recursive DELETE triggers.
        self.office.db.execute('PRAGMA recursive_triggers=OFF')
        for table in ('business_purchase_confirmations', 'business_purchase_receipts',
                      'business_purchase_receipt_lines', 'business_purchasing_requests'):
            row = dict(self.office.db.execute('SELECT * FROM ' + table + ' LIMIT 1').fetchone())
            examples = [row]
            if table == 'business_purchase_receipts':
                examples += [{**row, 'id': uuid.uuid4().hex},
                             {**row, 'id': uuid.uuid4().hex, 'receipt_revision': 99}]
            if table == 'business_purchase_receipt_lines':
                examples += [{**row, 'line_index': 1}]
            for value in examples:
                with self.subTest(table=table, value=value):
                    with self.assertRaises(sqlite3.IntegrityError):
                        with self.office.db:
                            self.office.db.execute('INSERT OR REPLACE INTO ' + table + ' (' + ','.join(value)
                                + ') VALUES (' + ','.join('?' for _ in value) + ')', tuple(value.values()))
        self.assertEqual(self.api.receipts(self.owner, self.order['id'])['items'], [receipt])
        self.assertTrue(validate_integrity(self.office))

    def test_integrity_rejects_receipt_stock_mismatch_after_privileged_tampering(self):
        self.confirm()
        receipt = self.receive()
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_purchase_receipt_lines_update_guard')
            self.office.db.execute('UPDATE business_purchase_receipt_lines SET cost_net=? WHERE receipt_id=?', ('8.0000', receipt['id']))
        with self.assertRaises(ValueError):
            validate_integrity(self.office)

    def test_receiving_does_not_charge_project_until_material_is_issued(self):
        self.confirm()
        self.receive(lines=[{'line_index': 0, 'quantity': '5', 'unit_cost_net': '4'}])
        self.assertEqual(self.inventory.cost_report(self.owner, self.project)['material_actual_net'], '0.00')
        issue = self.inventory.move(self.owner, self.req(kind='issue', article_id=self.article['id'],
            from_location_id=self.location['id'], project_id=self.project, quantity='3'))
        self.assertEqual(issue['cost_net'], '12.0000')
        self.assertEqual(self.inventory.cost_report(self.owner, self.project)['material_actual_net'], '12.00')
        self.inventory.move(self.owner, self.req(kind='return', article_id=self.article['id'],
            to_location_id=self.location['id'], project_id=self.project, quantity='1', reversal_of=issue['id']))
        self.assertEqual(self.inventory.cost_report(self.owner, self.project)['material_actual_net'], '8.00')
        self.assertEqual(self.api.get(self.owner, self.order['id'])['status'], 'received')

    def test_reused_request_id_with_different_content_is_rejected(self):
        self.confirm()
        body = self.receipt()
        self.api.receive(self.owner, self.order['id'], body)
        before = self.counts()
        self.error(409, self.api.receive, self.owner, self.order['id'], {**body, 'receipt_reference': 'DIFFERENT'})
        self.assertEqual(self.counts(), before)

    def test_dates_locations_and_unknown_fields_are_validated(self):
        self.error(400, self.api.confirm, self.owner, self.order['id'], {**self.confirmation(), 'ordered_on': '2026-02-30'})
        self.error(400, self.api.confirm, self.owner, self.order['id'], {**self.confirmation(), 'order_reference': 'bad\nreference'})
        self.confirm()
        for changes, status in (({'received_on': '2026-10-29'}, 400), ({'received_on': '2026-11-32'}, 400),
                                ({'location_id': 'f' * 32}, 404), ({'receipt_reference': ''}, 400)):
            self.error(status, self.api.receive, self.owner, self.order['id'], self.receipt(**changes))
        self.inventory.save_location(self.owner, self.req(revision=self.location['revision'], active=False), self.location['id'])
        self.error(404, self.api.receive, self.owner, self.order['id'], self.receipt())
        self.assertEqual(self.counts()['business_stock_movements'], 0)

    def test_dispatch_exposes_only_scoped_contract_and_rejects_wrong_methods(self):
        base = '/purchasing/orders/' + self.order['id']
        self.assertEqual(dispatch(self.office, self.owner, '/purchasing/orders', 'GET', {'_query': {'project_id': self.project}})[0]['items'][0]['id'], self.order['id'])
        self.assertEqual(dispatch(self.office, self.owner, base, 'GET', {})[0]['source_revision'], self.order['revision'])
        self.assertEqual(methods(base + '/receipts'), 'GET, POST')
        self.assertEqual(methods(base + '/confirm'), 'POST')
        self.assertIsNone(methods(base + '/send'))
        self.error(405, dispatch, self.office, self.owner, base, 'POST', {})
        self.error(400, dispatch, self.office, self.owner, '/purchasing/orders', 'GET', {'_query': {'tenant_id': 'other'}})
        self.error(400, dispatch, self.office, self.owner, base, 'GET', {'_query': {'project_id': self.other}})

    def catalogue_article(self, **changes):
        values = dict(code=uuid.uuid4().hex[:8], name='Additional synthetic article', kind='material', unit='C62',
                      unit_price_net='7.50', cost_price_net='4.00', tax_rate='19', tax_category='S', currency='EUR', active=True)
        return Documents(self.office).save_article(self.owner, self.req(**{**values, **changes}))

    def test_catalogue_without_stock_is_available_without_any_financial_read_permission(self):
        from business_foundation import permissions
        self.assertNotIn('finance.read', permissions(self.office, self.tech))
        self.assertEqual(self.counts()['business_stock_movements'], 0)
        expected = {'id': self.article['id'], 'revision': self.article['revision'], 'code': 'SYN-M',
                    'name': 'Synthetic cable', 'kind': 'material', 'unit': 'm', 'active': True}
        for actor in (self.tech, self.owner):
            result = self.api.articles(actor, project_id=self.project)
            self.assertEqual(result, {'items': [expected], 'total': 1, 'next_offset': None})
            self.assertEqual(set(result['items'][0]), {'id', 'revision', 'code', 'name', 'kind', 'unit', 'active'})
        self.error(403, Documents(self.office).articles, self.tech)

    def test_catalogue_active_physical_filter_and_unknown_future_financial_fields_stay_private(self):
        machine = self.catalogue_article(name='Machine', kind='machine')
        self.catalogue_article(name='Inactive', active=False)
        self.catalogue_article(name='Labour', kind='labor', unit='HUR')
        self.catalogue_article(name='Service', kind='service', unit='HUR',
            components=[{'article_id': self.article['id'], 'article_revision': self.article['revision'], 'quantity': '2'}])
        # A future commercial field must not escape an explicit DTO allowlist.
        row = self.office.db.execute('SELECT payload_json FROM business_articles WHERE id=?', (machine['id'],)).fetchone()
        value = json.loads(row['payload_json'])
        value['future_financial_terms'] = {'confidential': 'synthetic-secret-margin'}
        with self.office.db:
            self.office.db.execute('UPDATE business_articles SET payload_json=? WHERE id=?', (canonical(value), machine['id']))
        for actor in (self.owner, self.tech):
            result = self.api.articles(actor, project_id=self.project)
            self.assertEqual({item['id'] for item in result['items']}, {self.article['id'], machine['id']})
            for item in result['items']:
                self.assertEqual(set(item), {'id', 'revision', 'code', 'name', 'kind', 'unit', 'active'})
            encoded = json.dumps(result)
            for private in ('unit_price_net', 'cost_price_net', 'tax_rate', 'currency', 'components', 'pricing',
                            'future_financial_terms', 'synthetic-secret-margin'):
                self.assertNotIn(private, encoded)

    def test_catalogue_unicode_search_and_stable_sorting_are_literal(self):
        first = self.catalogue_article(name='Straße', code='A-17')
        second = self.catalogue_article(name='STRASSE', code='a-17')
        percent = self.catalogue_article(name='Pipe 100%', code='B_20')
        result = self.api.articles(self.tech, project_id=self.project, query='  STRASSE  ')
        self.assertEqual([item['id'] for item in result['items']], sorted([first['id'], second['id']]))
        self.assertEqual(result['total'], 2)
        self.assertEqual(self.api.articles(self.tech, query='a-17')['total'], 2)
        self.assertEqual(self.api.articles(self.tech, query='%')['items'][0]['id'], percent['id'])
        self.assertEqual(self.api.articles(self.tech, query='B_20')['total'], 1)
        self.assertEqual(self.api.articles(self.tech, query="' OR 1=1 --"), {'items': [], 'total': 0, 'next_offset': None})

    def test_catalogue_pages_are_bounded_and_complete_across_sql_batches(self):
        for index in range(260):
            self.catalogue_article(name=f'Batch article {259 - index:03}', code=f'B-{index:03}')
        statements = []
        self.office.db.set_trace_callback(statements.append)
        try:
            first = self.api.articles(self.tech, query='Batch article')
        finally:
            self.office.db.set_trace_callback(None)
        self.assertEqual((len(first['items']), first['total'], first['next_offset']), (100, 260, 100))
        second = self.api.articles(self.tech, query='Batch article', offset=100)
        third = self.api.articles(self.tech, query='Batch article', offset=200)
        all_items = first['items'] + second['items'] + third['items']
        self.assertEqual([item['name'] for item in all_items], [f'Batch article {index:03}' for index in range(260)])
        self.assertEqual(len({item['id'] for item in all_items}), 260)
        self.assertEqual(second['next_offset'], 200)
        self.assertIsNone(third['next_offset'])
        self.assertEqual(self.api.articles(self.tech, query='Batch article', offset=100000),
                         {'items': [], 'total': 260, 'next_offset': None})
        reads = [value for value in statements if 'FROM business_articles' in value]
        self.assertEqual(len(reads), 2)
        self.assertTrue(all('ORDER BY id LIMIT 256' in value for value in reads))

    def test_catalogue_project_scopes_denies_and_revocation_are_fresh(self):
        from business_foundation import BusinessFoundation
        # Accountant lacks inventory.read by default, then receives a grant
        # for exactly one project without gaining a global catalogue grant.
        accountant = self.actor('accountant')
        self.office.assign(self.owner, self.project, accountant['id'])
        self.grant(accountant, 'inventory.read', scope=self.project)
        self.assertEqual(self.api.articles(accountant, project_id=self.project)['total'], 1)
        self.error(403, self.api.articles, accountant)
        self.error(404, lambda: self.api.articles(self.tech, project_id=self.other))
        self.error(404, lambda: self.api.articles(self.outsider, project_id=self.project))
        self.office.assign(self.owner, self.project, accountant['id'], remove=True)
        self.error(404, lambda: self.api.articles(accountant, project_id=self.project))
        grants = BusinessFoundation(self.office)
        grants.save_grant(self.owner, self.req(user_id=self.tech['id'], permission='inventory.read',
            scope=self.project, effect='deny', revision=0))
        self.error(403, lambda: self.api.articles(self.tech, project_id=self.project))
        self.assertEqual(self.api.articles(self.tech)['total'], 1)
        grants.save_grant(self.owner, self.req(user_id=self.tech['id'], permission='inventory.read', scope='*', effect='deny', revision=0))
        self.error(403, self.api.articles, self.tech)
        with self.office.db:
            self.office.db.execute('UPDATE users SET active=0 WHERE id=?', (self.tech['id'],))
        self.error(401, lambda: self.api.articles(self.tech, project_id=self.project))

    def test_catalogue_rejects_unknown_duplicate_nonscalar_and_out_of_bounds_queries(self):
        from business_api import query_data
        path = '/purchasing/articles'
        invalid = ({'limit': '0'}, {'limit': '101'}, {'limit': '-1'}, {'limit': '1.0'}, {'limit': 'True'},
                   {'offset': '-1'}, {'offset': '100001'}, {'offset': '1e2'}, {'offset': '0;DROP TABLE users'},
                   {'project_id': ''}, {'project_id': 'not-an-id'}, {'tenant_id': self.project},
                   {'query': 'x' * 201}, {'query': 'embedded\nnewline'}, {'query': ['first', 'second']},
                   {'limit': ['1', '2']}, {'limit': 2}, {'unknown': ''})
        for query in invalid:
            with self.subTest(query=query):
                self.error(400, dispatch, self.office, self.owner, path, 'GET', {'_query': query})
        for key in ('project_id', 'query', 'limit', 'offset'):
            self.error(400, query_data, [(key, 'first'), (key, 'second')])
        self.error(400, dispatch, self.office, self.owner, path, 'GET', {'_query': [], 'extra': True})
        self.error(400, dispatch, self.office, self.owner, path, 'GET', {'query': 'must-be-query-string'})
        self.error(405, dispatch, self.office, self.owner, path, 'POST', {})
        self.error(400, lambda: self.api.articles(self.owner, limit=True))
        self.error(400, lambda: self.api.articles(self.owner, offset=0.0))
        self.assertEqual(dispatch(self.office, self.tech, path, 'GET', query_data([
            ('project_id', self.project), ('limit', '1'), ('offset', '0'), ('query', 'SYN-M')]))[0]['total'], 1)

    def test_catalogue_read_changes_neither_schema_history_nor_any_existing_data(self):
        import business_schema
        # Pinned to the purchasing v1 DDL/guards shipped at commit 64bdc26.
        expected_checksum = 'c1b29fc07eab7d04ee25bcadc33639206e96ae3b13ec3d9daf400ba1a2ad124d'
        stored = self.office.db.execute("SELECT checksum FROM business_schema_migrations WHERE module='business_purchasing'").fetchone()
        self.assertEqual(stored['checksum'], expected_checksum)
        before_schema = [tuple(row) for row in self.office.db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name').fetchall()]
        tables = [row[0] for row in self.office.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
        snapshot = lambda: {table: sorted((tuple(row) for row in self.office.db.execute('SELECT * FROM ' + table).fetchall()), key=repr) for table in tables}
        before_data = snapshot()
        for actor in (self.owner, self.tech):
            self.api.articles(actor, project_id=self.project, query='SYN')
        business_schema.ensure_schema(self.office)
        self.assertEqual(snapshot(), before_data)
        self.assertEqual([tuple(row) for row in self.office.db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name').fetchall()], before_schema)


class PurchasingMigrationTests(unittest.TestCase):
    def test_existing_schema7_orders_signed_reports_and_invoice_drafts_are_unchanged(self):
        import business_schema
        with tempfile.TemporaryDirectory() as temporary:
            previous_registry = tuple(spec for spec in business_schema.registry()
                                      if spec.name != 'business_purchasing')
            with patch.object(business_schema, 'registry', return_value=previous_registry):
                office = Office(Path(temporary) / 'previous-schema7.db')
            try:
                self.assertEqual(business_schema.state(office, registry=previous_registry)['storage_version'], 7)
                self.assertIsNone(office.db.execute("SELECT name FROM sqlite_master WHERE name='business_purchase_confirmations'").fetchone())
                owner = dict(id=office.add_user('migration@example.test', 'Synthetic-password-123', 'owner'), role='owner')
                project = office.add_project(owner, 'Existing project', 'Existing customer')
                report = office.draft(owner, project, 'Servicebericht', 'Existing signed report must remain byte-identical')
                signed = office.sign(owner, report['id'], report['content_hash'], 'Synthetic signer', [[[0.1, 0.2], [0.8, 0.9]]])
                original_pdf = office.pdf(owner, report['id'])
                documents = Documents(office)
                request = lambda **body: dict(request_id=uuid.uuid4().hex, **body)
                article = documents.save_article(owner, request(code='MIG-1', name='Existing article', kind='material', unit='C62',
                    unit_price_net='12.00', cost_price_net='5.00', tax_rate='19', tax_category='S', currency='EUR', active=True))
                order = BusinessInventory(office).save_order(owner, request(project_id=project, supplier_name='Existing supplier',
                    status='approved', items=[{'article_id': article['id'], 'quantity': '3'}]))
                invoice = documents.create(owner, request(project_id=project, kind='invoice', title='Existing invoice draft',
                    issue_date='2026-11-02', due_date='2026-11-16',
                    buyer=dict(name='Existing buyer', address_line='Synthetic street 1', postal_code='10115',
                               city='Berlin', country='DE', email='buyer@example.test'),
                    positions=[dict(article_id=article['id'], article_revision=article['revision'], quantity='2')]))
                tables = [row[0] for row in office.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
                          if not row[0].startswith('business_schema_')]
                snapshot = lambda: {table: sorted((tuple(row) for row in office.db.execute('SELECT * FROM ' + table).fetchall()), key=repr) for table in tables}
                before = snapshot()
                business_schema.ensure_schema(office)
                self.assertEqual(snapshot(), before)
                self.assertEqual(office.report(owner, report['id']), signed)
                self.assertEqual(office.pdf(owner, report['id']), original_pdf)
                self.assertEqual(documents.get(owner, invoice['id']), invoice)
                self.assertEqual(Purchasing(office).get(owner, order['id'])['status'], 'approved')
                self.assertTrue(validate_integrity(office))
                self.assertTrue(business_schema.validate_integrity(office))
                first_state = business_schema.state(office)
                first_migrations = [tuple(row) for row in office.db.execute('SELECT * FROM business_schema_migrations ORDER BY module').fetchall()]
                business_schema.ensure_schema(office)
                self.assertEqual(business_schema.state(office), first_state)
                self.assertEqual([tuple(row) for row in office.db.execute('SELECT * FROM business_schema_migrations ORDER BY module').fetchall()], first_migrations)
                self.assertEqual(snapshot(), before)
            finally:
                office.db.close()


if __name__ == '__main__':
    unittest.main()
