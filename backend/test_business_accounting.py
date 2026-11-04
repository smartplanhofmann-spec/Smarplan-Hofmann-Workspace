"""E1a source-bound EUR cash history on isolated synthetic SQLite databases.

Most cases use the production Finance API with real PDF receipt originals.
The invoice-source case explicitly reuses the existing SyntheticDocuments
SQLite fixture; actual invoice issuance/runtime separation is tested on PG.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
import uuid

from core import Office, Problem
from business_accounting import Accounting, dispatch, methods, protected_tables, restore_horizon, validate_integrity
from business_finance import Finance
from business_foundation import BusinessFoundation
from business_schema import ensure_schema


class AccountingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='synthetic-accounting-')
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'office.db'
        # Historical overpayment is seeded under the actual pre-E1b registry;
        # fresh payments after the additive migration obey the new OP bound.
        import business_schema
        historical = self._testMethodName == 'test_invoice_payment_snapshot_is_stable_overpayment_is_preserved_and_all_projects_required'
        previous = tuple(spec for spec in business_schema.registry() if spec.name not in ('business_accounting_allocations', 'business_accounting_components', 'business_accounting_refunds', 'business_accounting_capacity', 'business_accounting_refunds_v2', 'business_accounting_profile', 'business_accounting_euer', 'business_payroll_cash', 'business_bank_reconciliation', 'business_travel_allowances', 'business_accounting_openings', 'business_accounting_asset_openings', 'business_accounting_open_items'))
        if historical:
            self._historical_registry = patch.object(business_schema, 'registry', return_value=previous)
            self._historical_registry.start()
            self.addCleanup(self._historical_registry.stop)
        self.office = Office(self.path)
        self.addCleanup(self.office.db.close)
        ensure_schema(self.office, activate=True)
        self.owner = self.actor('owner'); self.tech = self.actor('technician'); self.other_actor = self.actor('accountant')
        self.project = self.office.add_project(self.owner, 'Synthetic project', 'Synthetic customer')
        self.other_project = self.office.add_project(self.owner, 'Private project', 'Private customer')
        self.office.assign(self.owner, self.project, self.tech['id'])
        self.clock = lambda: datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
        self.api = Accounting(self.office, clock=self.clock)
        self.finance = Finance(self.office, clock=self.clock)
        self.account = self.api.create_account(self.owner, self.req(code='BANK', name='Synthetic bank account', kind='bank'))

    def actor(self, role):
        email = uuid.uuid4().hex + '@example.test'
        return dict(id=self.office.add_user(email, 'Synthetic-password-123', role), role=role, email=email)

    def req(self, **data):
        return dict(request_id=uuid.uuid4().hex, confirmation=True, **data)

    def legacy_req(self, **data):
        return dict(request_id=uuid.uuid4().hex, **data)

    def problem(self, status, method, *args):
        with self.assertRaises(Problem) as caught:
            method(*args)
        self.assertEqual(caught.exception.status, status, caught.exception.message)

    def grant(self, actor, permission, *, effect='allow', revision=0):
        return BusinessFoundation(self.office).save_grant(self.owner, self.legacy_req(user_id=actor['id'], permission=permission,
            scope='*', effect=effect, revision=revision))

    def reader(self, actor=None, *, prepare=False):
        actor = actor or self.tech
        for permission in ('accounting.read', 'finance.read') + (('accounting.prepare',) if prepare else ()):
            self.grant(actor, permission)
        return actor

    def payment(self, actor=None, amount='119.00', kind='receipt', allocations=None):
        return self.finance.record_payment(actor or self.owner, self.legacy_req(source_id='source-' + uuid.uuid4().hex, kind=kind,
            amount=amount, currency='EUR', booking_date='2026-11-01', reference='Synthetic payment', allocations=allocations or []))

    def payment_source(self, payment, actor=None):
        return next(value for value in self.api.payment_sources(actor or self.owner)['items'] if value['payment_id'] == payment['id'])

    def import_body(self, payment, **changes):
        source = self.payment_source(payment)
        return self.req(**{**dict(payment_id=payment['id'], source_hash=source['source_hash'], account_id=self.account['id'],
            account_revision=self.account['revision'], cash_date='2026-11-02', evidence_reference='Bank record ' + uuid.uuid4().hex), **changes})

    def receipt(self, *, project=True, actor=None, original=None):
        if original is None:
            from reportlab.pdfgen.canvas import Canvas
            output = io.BytesIO(); pdf = Canvas(output)
            pdf.drawString(40, 700, 'Synthetic supplier receipt ' + uuid.uuid4().hex); pdf.save()
            original = output.getvalue()
        source = self.finance.capture_receipt(actor or self.owner, self.legacy_req(project_id=self.project if project else None,
            filename='synthetic-incoming.pdf', media_type='application/pdf', original_base64=base64.b64encode(original).decode()))
        self.finance.review_receipt(actor or self.owner, source['id'], self.review_body())
        return source

    def review_body(self, **changes):
        return self.legacy_req(**{**dict(revision=0, vendor='Synthetic supplier', invoice_number='SYN-1', issue_date='2026-10-30',
            net='50.00', tax='9.50', gross='59.50', currency='EUR', status='reviewed', note='Reviewed synthetic source'), **changes})

    def receipt_source(self, receipt, actor=None):
        return next(value for value in self.api.receipt_sources(actor or self.owner)['items'] if value['receipt_id'] == receipt['id'])

    def payout_body(self, receipt, **changes):
        source = self.receipt_source(receipt)
        return self.req(**{**dict(receipt_id=receipt['id'], source_hash=source['source_hash'], review_revision=source['review_revision'],
            review_sha256=source['review_sha256'], original_sha256=source['original_sha256'], account_id=self.account['id'],
            account_revision=self.account['revision'], expected_cash_revision=source['cash_revision'], amount='20.00',
            cash_date='2026-11-02', evidence_reference='Supplier transfer ' + uuid.uuid4().hex, reference='Synthetic partial payment'), **changes})

    def snapshot(self, tables):
        return {table: sorted((tuple(row) for row in self.office.db.execute('SELECT * FROM ' + table)), key=repr) for table in tables}

    def test_accounts_are_explicit_versioned_and_old_replays_never_change(self):
        body = self.req(code='CASH', name='Synthetic till', kind='cash')
        account = self.api.create_account(self.owner, body)
        self.assertEqual(self.api.create_account(self.owner, body), account)
        self.problem(409, self.api.create_account, self.owner, self.req(code='cash', name='Duplicate', kind='cash'))
        update = self.req(revision=1, name='Renamed till', active=False)
        changed = self.api.update_account(self.owner, account['id'], update)
        self.assertEqual((changed['revision'], changed['active'], changed['code']), (2, False, 'CASH'))
        self.assertEqual(self.api.create_account(self.owner, body), account)
        self.assertEqual(self.api.update_account(self.owner, account['id'], update), changed)
        self.problem(409, self.api.update_account, self.owner, account['id'], self.req(revision=1, name='Stale', active=True))
        self.problem(400, self.api.update_account, self.owner, account['id'], {**update, 'code': 'CHANGED'})
        self.assertEqual([value['code'] for value in self.api.accounts(self.owner)['items']], ['BANK', 'CASH'])
        self.assertTrue(validate_integrity(self.office))

    def test_unallocated_receipt_refund_imports_preserve_legacy_rows_and_no_tax_result(self):
        payment = self.payment(); refund = self.payment(amount='10.00', kind='refund')
        before = self.snapshot(('business_payments', 'business_payment_allocations', 'business_finance_requests'))
        body = self.import_body(payment)
        event = self.api.import_payment(self.owner, body)
        self.assertEqual(self.api.import_payment(self.owner, body), event)
        self.assertEqual(event['source']['snapshot']['unallocated'], '119.00')
        self.assertEqual(event['source']['snapshot']['booking_date'], '2026-11-01')
        self.assertEqual(event['cash_date'], '2026-11-02')
        self.assertEqual(event['classification_status'], 'unclassified')
        self.assertEqual(event['unresolved_reasons'], ['tax_profile_unconfigured'])
        other_account = self.api.create_account(self.owner, self.req(code='OTHER', name='Other account', kind='bank'))
        self.problem(409, self.api.import_payment, self.owner, {**body, 'request_id': uuid.uuid4().hex, 'account_id': other_account['id']})
        out = self.api.import_payment(self.owner, self.import_body(refund))
        self.assertEqual((out['direction'], out['amount']), ('out', '10.00'))
        self.assertEqual(out['unresolved_reasons'], ['tax_profile_unconfigured', 'refund_origin_unresolved'])
        self.assertEqual(self.payment_source(payment)['linked_event_id'], event['id'])
        self.assertFalse(self.api.events(self.owner)['tax_result_available'])
        self.assertFalse(self.api.status(self.owner)['tax_result_available'])
        self.assertEqual(before, self.snapshot(tuple(before)))
        self.assertTrue(validate_integrity(self.office))

    def test_receipt_partial_and_rest_payouts_use_original_versions_and_exact_decimal_budget(self):
        receipt = self.receipt()
        before = self.snapshot(('business_incoming_receipts', 'business_receipt_reviews', 'business_payments'))
        first = self.api.payout(self.owner, self.payout_body(receipt))
        second_account = self.api.create_account(self.owner, self.req(code='CASH', name='Synthetic till', kind='cash'))
        second = self.api.payout(self.owner, self.payout_body(receipt, account_id=second_account['id']))
        self.problem(409, self.api.payout, self.owner, self.payout_body(receipt, amount='19.51'))
        third = self.api.payout(self.owner, self.payout_body(receipt, amount='19.50'))
        source = self.receipt_source(receipt)
        self.assertEqual((source['cash_revision'], source['paid_amount'], source['remaining_amount'], source['payable'], source['blocked_reason']),
                         (3, '59.50', '0.00', False, 'paid'))
        for event in (first, second, third):
            self.assertEqual(event['source']['snapshot']['review_revision'], 1)
            self.assertNotIn('cash_revision', event['source']['snapshot'])
            self.assertNotIn('original', event['source']['snapshot'])
            self.assertEqual(event['direction'], 'out')
        self.assertEqual(before, self.snapshot(tuple(before)))
        self.assertTrue(validate_integrity(self.office))

    def test_review_change_and_inactive_account_preserve_historical_read_and_successful_retry(self):
        receipt = self.receipt(); body = self.payout_body(receipt)
        event = self.api.payout(self.owner, body)
        self.finance.review_receipt(self.owner, receipt['id'], self.review_body(revision=1, vendor='Revised supplier', net='10.00', tax='0.00', gross='10.00'))
        self.api.update_account(self.owner, self.account['id'], self.req(revision=1, name='Renamed inactive bank', active=False))
        self.assertEqual(self.api.event(self.owner, event['id']), event)
        self.assertEqual(self.api.payout(self.owner, body), event)
        self.problem(409, self.api.payout, self.owner, {**body, 'request_id': uuid.uuid4().hex})
        current = self.receipt_source(receipt)
        self.assertEqual((current['review_revision'], current['blocked_reason'], current['remaining_amount']), (2, 'review_changed', '0.00'))
        self.assertEqual(event['source']['snapshot']['vendor'], 'Synthetic supplier')
        self.assertEqual(event['account']['revision'], 1)
        self.assertTrue(validate_integrity(self.office))

    def test_same_original_under_another_receipt_never_creates_a_second_payment_budget(self):
        original = self.receipt(project=False)
        self.api.payout(self.owner, self.payout_body(original))
        pdf = self.finance.receipt_original(self.owner, original['id'])[0]
        duplicate = self.receipt(original=pdf)
        actor = self.reader(prepare=True)
        visible = self.api.receipt_sources(actor)
        self.assertEqual([item['receipt_id'] for item in visible['items']], [duplicate['id']])
        row = visible['items'][0]
        self.assertEqual((row['blocked_reason'], row['paid_amount'], row['cash_revision']), ('duplicate_original', '0.00', 0))
        self.assertNotIn(original['id'], json.dumps(visible))
        self.problem(409, self.api.payout, actor, self.payout_body(duplicate))
        self.assertEqual(self.api.events(actor)['items'], [])

    def test_accounts_and_cash_replay_require_fresh_global_and_original_source_rights(self):
        actor = self.reader(prepare=True)
        receipt = self.receipt(); body = self.payout_body(receipt)
        event = self.api.payout(actor, body)
        self.grant(actor, 'accounting.prepare', effect='deny', revision=1)
        self.problem(403, self.api.payout, actor, body)
        self.grant(actor, 'accounting.prepare', revision=2)
        self.office.assign(self.owner, self.project, actor['id'], remove=True)
        self.problem(404, self.api.payout, actor, body)
        self.problem(404, self.api.event, actor, event['id'])
        self.assertEqual(self.api.events(actor)['total'], 0)
        self.office.assign(self.owner, self.project, actor['id'])
        self.grant(actor, 'finance.read', effect='deny', revision=1)
        self.problem(403, self.api.events, actor)
        self.problem(403, self.api.accounts, actor)
        self.problem(403, self.api.status, actor)
        self.problem(403, self.api.payout, actor, body)

    def test_project_scoped_accounting_grants_and_private_sources_do_not_expand_access(self):
        self.grant(self.tech, 'finance.read')
        with self.office.db:
            self.office.db.execute('INSERT INTO business_permission_grants(id,user_id,permission,scope,effect,revision,updated_by,updated_at) VALUES(?,?,?,?,?,1,?,?)',
                (uuid.uuid4().hex, self.tech['id'], 'accounting.read', self.project, 'allow', self.owner['id'], self.api.now()))
        self.problem(403, self.api.status, self.tech)
        self.grant(self.tech, 'accounting.read')
        private_payment = self.payment(); private_receipt = self.receipt(project=False)
        self.assertEqual(self.api.payment_sources(self.tech)['total'], 0)
        self.assertEqual(self.api.receipt_sources(self.tech)['total'], 0)
        self.grant(self.tech, 'accounting.prepare')
        self.problem(403, self.api.import_payment, self.tech, self.import_body(private_payment))
        self.problem(403, self.api.payout, self.tech, self.payout_body(private_receipt))

    def test_conflicting_partial_payouts_on_two_connections_have_one_winner(self):
        receipt = self.receipt()
        bodies = [self.payout_body(receipt, amount='40.00'), self.payout_body(receipt, amount='40.00')]
        other = Office(self.path); barrier = threading.Barrier(2)
        def run(args):
            api, body = args
            barrier.wait(timeout=5)
            try:
                return api.payout(self.owner, body)
            except Problem as error:
                return error.status
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(run, ((self.api, bodies[0]), (Accounting(other, clock=self.clock), bodies[1]))))
        finally:
            other.db.close()
        self.assertEqual(sum(isinstance(item, dict) for item in results), 1)
        self.assertIn(409, results)
        self.assertEqual(self.receipt_source(receipt)['paid_amount'], '40.00')
        self.assertTrue(validate_integrity(self.office))

    def test_reference_deduplication_is_account_wide_across_both_entry_paths(self):
        payment = self.payment(); receipt = self.receipt()
        self.api.import_payment(self.owner, self.import_body(payment, evidence_reference='  BANK  Straße-17  '))
        body = self.payout_body(receipt, evidence_reference='bank STRASSE-17')
        self.problem(409, self.api.payout, self.owner, body)
        cash = self.api.create_account(self.owner, self.req(code='TILL', name='Till', kind='cash'))
        event = self.api.payout(self.owner, {**body, 'account_id': cash['id']})
        self.assertEqual(event['account']['id'], cash['id'])

    def test_final_audit_failure_rolls_back_event_source_original_binding_and_receipt(self):
        receipt = self.receipt(); body = self.payout_body(receipt)
        tables = protected_tables() + ('audit',)
        before = self.snapshot(tables)
        original = self.office.audit
        def fail(actor, action, target):
            if action == 'business.accounting.payout_recorded':
                raise RuntimeError('Synthetic audit failure')
            return original(actor, action, target)
        with patch.object(self.office, 'audit', side_effect=fail), self.assertRaises(RuntimeError):
            self.api.payout(self.owner, body)
        self.assertEqual(self.snapshot(tables), before)
        self.assertEqual(self.api.payout(self.owner, body)['sequence'], 1)
        self.assertTrue(validate_integrity(self.office))

    def test_read_only_horizon_is_stable_and_historical_review_changes_do_not_rewrite_it(self):
        receipt = self.receipt(); self.api.payout(self.owner, self.payout_body(receipt))
        first = restore_horizon(self.office)
        before = self.snapshot(protected_tables())
        trace = []; self.office.db.set_trace_callback(trace.append)
        try:
            self.assertEqual(restore_horizon(self.office), first)
        finally:
            self.office.db.set_trace_callback(None)
        self.assertFalse(any(value.lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'BEGIN', 'COMMIT')) for value in trace))
        self.assertEqual(self.snapshot(protected_tables()), before)
        self.finance.review_receipt(self.owner, receipt['id'], self.review_body(revision=1, vendor='Updated after cash'))
        self.assertEqual(restore_horizon(self.office), first)
        self.assertEqual((first['accounts_count'], first['account_versions_count'], first['cash_events_count'], first['source_links_count'], first['max_sequence']), (1,1,1,1,1))

    def test_append_only_and_all_legacy_unique_source_keys_reject_sqlite_replace(self):
        receipt = self.receipt(); payment = self.payment()
        self.api.payout(self.owner, self.payout_body(receipt)); self.api.import_payment(self.owner, self.import_body(payment))
        before = self.snapshot(protected_tables())
        for table in protected_tables() + ('business_payments', 'business_incoming_receipts', 'business_receipt_reviews'):
            row = dict(self.office.db.execute('SELECT * FROM ' + table + ' LIMIT 1').fetchone())
            columns = list(row)
            variants = [row]
            if 'id' in row and table not in ('business_incoming_receipts',):
                variants.append({**row, 'id': uuid.uuid4().hex})
            for variant in variants:
                with self.subTest(table=table), self.assertRaises(sqlite3.IntegrityError):
                    with self.office.db:
                        self.office.db.execute('INSERT OR REPLACE INTO ' + table + '(' + ','.join(columns) + ') VALUES(' + ','.join('?' for _ in columns) + ')',
                                               tuple(variant[key] for key in columns))
            if table in protected_tables():
                for sql in ('UPDATE ' + table + ' SET ' + columns[0] + '=' + columns[0], 'DELETE FROM ' + table):
                    with self.assertRaises(sqlite3.IntegrityError):
                        with self.office.db:
                            self.office.db.execute(sql)
        self.assertEqual(self.snapshot(protected_tables()), before)
        self.assertTrue(validate_integrity(self.office))

    def test_tampered_historical_original_blocks_event_replay_and_operator_horizon(self):
        receipt = self.receipt(); body = self.payout_body(receipt); event = self.api.payout(self.owner, body)
        with self.office.db:
            for row in self.office.db.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='business_incoming_receipts'").fetchall():
                self.office.db.execute('DROP TRIGGER ' + row['name'])
            self.office.db.execute('UPDATE business_incoming_receipts SET original=? WHERE id=?', (b'%PDF-tampered', receipt['id']))
        self.problem(409, self.api.event, self.owner, event['id'])
        self.problem(409, self.api.payout, self.owner, body)
        with self.assertRaises(ValueError):
            restore_horizon(self.office)

    def test_malformed_stored_sources_are_conflicts_on_read_and_historical_replay(self):
        payment = self.payment(); receipt = self.receipt()
        import_body = self.import_body(payment); payout_body = self.payout_body(receipt)
        imported = self.api.import_payment(self.owner, import_body)
        paid = self.api.payout(self.owner, payout_body)
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_payments_update_guard')
            self.office.db.execute('DROP TRIGGER business_receipt_reviews_update_guard')
            self.office.db.execute('UPDATE business_payments SET amount=? WHERE id=?', ('NaN', payment['id']))
            damaged = '{malformed-json'
            self.office.db.execute('UPDATE business_receipt_reviews SET payload_json=?,payload_sha256=? WHERE receipt_id=?',
                                   (damaged, hashlib.sha256(damaged.encode()).hexdigest(), receipt['id']))
        self.problem(409, self.api.event, self.owner, imported['id'])
        self.problem(409, self.api.import_payment, self.owner, import_body)
        self.problem(409, self.api.event, self.owner, paid['id'])
        self.problem(409, self.api.payout, self.owner, payout_body)
        with self.assertRaises(ValueError):
            validate_integrity(self.office)

    def test_rejected_unreviewed_and_zero_receipts_are_not_payout_candidates(self):
        receipt = self.receipt()
        self.finance.review_receipt(self.owner, receipt['id'], self.review_body(revision=1, status='rejected'))
        self.assertEqual(self.api.receipt_sources(self.owner)['items'], [])
        self.finance.review_receipt(self.owner, receipt['id'], self.review_body(revision=2, net='0.00', tax='0.00', gross='0.00'))
        self.assertEqual(self.api.receipt_sources(self.owner)['items'], [])

    def test_contract_invalid_amounts_filters_and_stale_sources_do_not_mutate(self):
        from business_api import query_data
        receipt = self.receipt(); body = self.payout_body(receipt)
        for amount in ('0.00', '-1.00', '1', '1.0', '01.00', '1.001', '1e2', 'NaN', '1000000000.00', 1.0, True):
            self.problem(400, self.api.payout, self.owner, {**body, 'amount': amount})
        for change in ({'review_sha256': '0'*64}, {'original_sha256': '0'*64}, {'source_hash': '0'*64},
                       {'review_revision': 2}, {'account_revision': 2}, {'expected_cash_revision': 1}):
            self.problem(409, self.api.payout, self.owner, {**body, **change})
        for change in ({'confirmation': False}, {'company_id': 'other'}, {'reference': 'bad\nvalue'}, {'cash_date': '2026-02-30'}, {'account_revision': True}):
            self.problem(400, self.api.payout, self.owner, {**body, **change})
        path = '/accounting/events'
        for query in ({'project_id': self.project}, {'limit': '0'}, {'limit': '101'}, {'offset': '100001'}, {'offset': '-1'}, {'limit': True}, {'limit': ['1']}):
            self.problem(400, dispatch, self.office, self.owner, path, 'GET', {'_query': query})
        self.problem(400, query_data, [('limit','1'),('limit','2')])
        self.problem(405, dispatch, self.office, self.owner, path, 'POST', {})
        self.assertEqual(methods('/accounting/accounts'), 'GET, POST')
        self.assertEqual(self.api.events(self.owner)['total'], 0)

    def test_pagination_only_counts_visible_sources_and_event_order_is_stable(self):
        actor = self.reader(self.other_actor, prepare=True)
        payments = [self.payment(actor, amount='1.00') for _ in range(3)]
        self.payment(self.owner, amount='999.00')
        first = self.api.payment_sources(actor, limit=2)
        second = self.api.payment_sources(actor, limit=2, offset=2)
        self.assertEqual((first['total'], first['next_offset'], second['next_offset']), (3, 2, None))
        self.assertEqual([row['payment_id'] for row in first['items'] + second['items']], sorted(value['id'] for value in payments))
        for payment in payments:
            self.api.import_payment(actor, self.import_body(payment))
        listed = self.api.events(actor, limit=2)
        self.assertEqual([row['sequence'] for row in listed['items']], [3, 2])
        self.assertEqual(self.api.events(actor, offset=100000)['items'], [])

    def test_invoice_payment_snapshot_is_stable_overpayment_is_preserved_and_all_projects_required(self):
        # Explicit reuse of an existing synthetic invoice-policy fixture. The
        # production invoice finalizer is exercised under real PG in its suite.
        from business_tests.test_documents import SyntheticDocuments, seed_synthetic_issuer
        from business_documents import render_prepared
        documents = SyntheticDocuments(self.office, clock=self.clock)
        documents.save_settings(self.owner, self.legacy_req(revision=0, company_name='Synthetic issuer', address_line='Test street',
            postal_code='10115', city='Berlin', country='DE', vat_id='DE123456789', issuer_mode='own', issuing_enabled=False,
            cutover_ack=True, cutover_date='2026-01-01'))
        seed_synthetic_issuer(documents, self.owner)
        invoices = []
        for project in (self.project, self.other_project):
            draft = documents.create(self.owner, self.legacy_req(project_id=project, kind='invoice', issue_date='2026-11-01',
                buyer=dict(name='Synthetic buyer', address_line='Test buyer street', postal_code='10117', city='Berlin', country='DE'),
                positions=[dict(description='Synthetic supply', quantity='1', unit='m', unit_price_net='10.00', tax_rate='0')]))
            prepared = documents.prepare_finalization(self.owner, draft['id'], draft['revision'])
            invoices.append(documents.finalize(self.owner, draft['id'], render_prepared(prepared), uuid.uuid4().hex))
        payment = self.payment(amount='50.00', allocations=[dict(document_id=value['id'], amount='25.00') for value in invoices])
        source = self.payment_source(payment)
        self.assertEqual(source['amount'], '50.00')
        self.assertEqual(source['unallocated'], '0.00')
        self.assertEqual([value['document_id'] for value in source['allocations']], sorted(value['id'] for value in invoices))
        event = self.api.import_payment(self.owner, self.import_body(payment))
        preserved = self.snapshot(('business_payments', 'business_payment_allocations', 'business_accounting_cash_events', 'business_accounting_source_links'))
        self._historical_registry.stop()
        ensure_schema(self.office, activate=True)
        self.assertEqual(self.snapshot(tuple(preserved)), preserved)
        self.assertEqual(self.api.event(self.owner, event['id']), event)
        self.payment(amount='1.00', kind='refund', allocations=[dict(document_id=invoices[0]['id'], amount='1.00')])
        self.assertEqual(self.payment_source(payment)['source_hash'], source['source_hash'])
        actor = self.reader(prepare=True)
        self.assertEqual(self.api.payment_sources(actor)['total'], 1)  # Only the one-project refund is readable.
        self.problem(404, self.api.event, actor, event['id'])
        self.assertTrue(validate_integrity(self.office))


class AccountingMigrationTests(unittest.TestCase):
    def test_schema7_migration_preserves_signed_history_payments_and_receipt_originals(self):
        import business_schema
        with tempfile.TemporaryDirectory() as temporary:
            previous = tuple(spec for spec in business_schema.registry() if spec.name not in ('business_accounting', 'business_accounting_allocations', 'business_accounting_components', 'business_accounting_refunds', 'business_accounting_capacity', 'business_accounting_refunds_v2', 'business_accounting_profile', 'business_accounting_euer', 'business_payroll_cash', 'business_bank_reconciliation', 'business_travel_allowances', 'business_accounting_openings', 'business_accounting_asset_openings', 'business_accounting_open_items'))
            with patch.object(business_schema, 'registry', return_value=previous):
                office = Office(Path(temporary) / 'previous.db')
                try:
                    owner = dict(id=office.add_user('owner@example.test','Synthetic-password-123','owner'), role='owner')
                    project = office.add_project(owner, 'Old project', 'Old customer')
                    report = office.draft(owner, project, 'Servicebericht', 'Preserved legacy report')
                    signed = office.sign(owner, report['id'], report['content_hash'], 'Synthetic signer', [[[0.1,0.2],[0.8,0.9]]])
                    original_pdf = office.pdf(owner, report['id'])
                    finance = Finance(office)
                    payment = finance.record_payment(owner, dict(request_id=uuid.uuid4().hex, source_id='existing-payment', amount='50.00',
                        currency='EUR', booking_date='2026-11-01', reference='Historical payment', allocations=[]))
                    receipt = finance.capture_receipt(owner, dict(request_id=uuid.uuid4().hex, project_id=project, filename='old.pdf',
                        media_type='application/pdf', original_base64=base64.b64encode(original_pdf).decode()))
                    tables = [row[0] for row in office.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
                              if not row[0].startswith('business_schema_')]
                    snapshot = lambda: {table: sorted((tuple(row) for row in office.db.execute('SELECT * FROM ' + table)), key=repr) for table in tables}
                    before = snapshot()
                    self.assertIsNone(restore_horizon(office))
                except BaseException:
                    office.db.close()
                    raise
            try:
                ensure_schema(office); ensure_schema(office)
                self.assertEqual(snapshot(), before)
                self.assertEqual(office.report(owner, report['id']), signed)
                self.assertEqual(office.pdf(owner, report['id']), original_pdf)
                self.assertEqual(finance.receipt_original(owner, receipt['id'])[0], original_pdf)
                self.assertEqual(Accounting(office).payment_sources(owner)['items'][0]['payment_id'], payment['id'])
                self.assertEqual(Accounting(office).events(owner)['total'], 0)
                self.assertTrue(validate_integrity(office))
            finally:
                office.db.close()


if __name__ == '__main__':
    unittest.main()
