"""Synthetic archived invoices; real domain transactions, source and ACL proofs.

Invoice issuance uses the repository's explicitly isolated SQLite test adapter.
The independent PG suite exercises the production issuer and cross-process lock.
"""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json
import sqlite3
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

import test_business_accounting as fixture
from business_accounting import restore_horizon as old_horizon
from business_accounting_allocations import (PaymentAllocations, dispatch, effective_allocations, effective_paid,
    installed, methods, protected_tables, restore_horizon, validate_integrity)
from business_documents import render_prepared
from business_foundation import BusinessFoundation
from business_tests.test_documents import SyntheticDocuments, seed_synthetic_issuer
from core import Problem


class AllocationTests(unittest.TestCase):
    actor = fixture.AccountingTests.actor
    req = fixture.AccountingTests.req
    legacy_req = fixture.AccountingTests.legacy_req
    problem = fixture.AccountingTests.problem
    grant = fixture.AccountingTests.grant
    payment = fixture.AccountingTests.payment
    payment_source = fixture.AccountingTests.payment_source
    import_body = fixture.AccountingTests.import_body
    snapshot = fixture.AccountingTests.snapshot

    def setUp(self):
        fixture.AccountingTests.setUp(self)
        self.alloc = PaymentAllocations(self.office, clock=self.clock)
        self.docs = SyntheticDocuments(self.office, clock=self.clock)
        self.docs.save_settings(self.owner, self.legacy_req(revision=0, company_name='Synthetic issuer', address_line='Synthetic street',
            postal_code='10115', city='Berlin', country='DE', vat_id='DE123456789', issuer_mode='own', issuing_enabled=False,
            cutover_ack=True, cutover_date='2026-01-01'))
        seed_synthetic_issuer(self.docs, self.owner)
        self.customer = self.office.db.execute('SELECT customer_id FROM projects WHERE id=?', (self.project,)).fetchone()[0]
        self.same_project = self.office.add_project(self.owner, 'Second project, same customer', customer_id=self.customer)

    def invoice(self, project=None, amount='100.00', kind='invoice'):
        draft = self.docs.create(self.owner, self.legacy_req(project_id=project or self.project, kind=kind, issue_date='2026-11-01',
            due_date='2026-11-10', buyer=dict(name='Synthetic buyer', address_line='Buyer street', postal_code='10117', city='Berlin', country='DE'),
            positions=[dict(description='Synthetic supply', quantity='1', unit='m', unit_price_net=amount, tax_rate='0')]))
        return self.docs.finalize(self.owner, draft['id'], render_prepared(self.docs.prepare_finalization(self.owner, draft['id'], draft['revision'])), uuid.uuid4().hex)

    def imported(self, amount='100.00', allocations=None, actor=None, kind='receipt'):
        payment = self.payment(actor=actor, amount=amount, allocations=allocations, kind=kind)
        event = self.api.import_payment(self.owner, self.import_body(payment))
        return payment, event

    def preview_body(self, payment, invoice, amount='10.00', actor=None):
        actor = actor or self.owner
        state = self.alloc.state(actor, payment['id'])
        candidate = next(value for value in self.alloc.candidates(actor, payment['id'])['items'] if value['document_id'] == invoice['id'])
        return dict(source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
            customer_id=candidate['customer_id'], document_id=invoice['id'], document_state_hash=candidate['document_state_hash'], amount=amount,
            reason='Explicit synthetic customer matching')

    def command(self, payment, invoice, amount='10.00', actor=None):
        body = self.preview_body(payment, invoice, amount, actor)
        preview = self.alloc.preview(actor or self.owner, payment['id'], body)
        return self.req(**body, preview_hash=preview['preview_hash'])

    def bookkeeper(self):
        for permission in ('accounting.read', 'accounting.prepare', 'finance.read', 'finance.write'):
            self.grant(self.tech, permission)
        return self.tech

    def test_preview_is_readonly_and_assign_keeps_e1a_sources_horizon_and_original_response(self):
        invoice = self.invoice(); payment, event = self.imported()
        source = self.payment_source(payment); old = old_horizon(self.office)
        before = self.snapshot(('business_payments', 'business_payment_allocations', 'business_finance_requests'))
        body = self.preview_body(payment, invoice, '40.00')
        whole_before = self.snapshot(tuple(row[0] for row in self.office.db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")))
        preview = self.alloc.preview(self.owner, payment['id'], body)
        self.assertEqual(self.snapshot(tuple(whole_before)), whole_before)
        command = self.req(**body, preview_hash=preview['preview_hash'])
        entry = self.alloc.assign(self.owner, payment['id'], command)
        self.assertEqual(self.alloc.assign(self.owner, payment['id'], command), entry)
        self.assertEqual(old_horizon(self.office), old)
        self.assertEqual(self.api.event(self.owner, event['id']), event)
        self.assertEqual(self.payment_source(payment), source)
        self.assertEqual(self.snapshot(tuple(before)), before)
        state = self.alloc.state(self.owner, payment['id'])
        self.assertEqual((state['revision'], state['customer_id'], state['unallocated_amount']), (1, self.customer, '60.00'))
        self.assertEqual(effective_paid(self.office, invoice['id']), Decimal('40.00'))
        self.assertTrue(validate_integrity(self.office))

    def test_partial_rest_repeated_same_invoice_and_refund_do_not_reopen_source_budget(self):
        invoice = self.invoice(); payment, _ = self.imported()
        first = self.alloc.assign(self.owner, payment['id'], self.command(payment, invoice, '40.00'))
        second = self.alloc.assign(self.owner, payment['id'], self.command(payment, invoice, '60.00'))
        self.assertEqual(effective_allocations(self.office, payment['id']), [dict(document_id=invoice['id'], amount='100.00')])
        self.assertEqual(self.alloc.history(self.owner, payment['id'], limit=1)['items'], [second])
        self.assertEqual(self.alloc.history(self.owner, payment['id'], limit=1, offset=1)['items'], [first])
        self.payment(amount='15.00', kind='refund', allocations=[dict(document_id=invoice['id'], amount='15.00')])
        state = self.alloc.state(self.owner, payment['id'])
        self.assertEqual((state['blocked_reason'], state['unallocated_amount']), ('fully_allocated', '0.00'))
        self.assertEqual(effective_paid(self.office, invoice['id']), Decimal('85.00'))
        self.assertEqual(self.finance.open_items(self.owner)['items'][0]['open'], '15.00')
        self.assertTrue(validate_integrity(self.office))

    def test_legacy_payment_and_assign_compete_for_same_invoice_in_both_orders(self):
        invoice = self.invoice(); payment, _ = self.imported()
        body = self.command(payment, invoice, '70.00')
        receipt_body = self.legacy_req(source_id='legacy-race', amount='60.00', kind='receipt', currency='EUR', booking_date='2026-11-02',
                                      reference='Synthetic competing receipt', allocations=[dict(document_id=invoice['id'], amount='60.00')])
        self.finance.record_payment(self.owner, receipt_body)
        self.problem(409, self.alloc.assign, self.owner, payment['id'], body)
        body = self.command(payment, invoice, '40.00')
        self.alloc.assign(self.owner, payment['id'], body)
        self.assertEqual(self.finance.record_payment(self.owner, receipt_body)['amount'], '60.00')  # Historical replay before new OP check.
        self.problem(409, self.finance.record_payment, self.owner, {**receipt_body, 'request_id': uuid.uuid4().hex, 'source_id': 'new-excess'})
        second_invoice = self.invoice(); other, _ = self.imported()
        self.alloc.assign(self.owner, other['id'], self.command(other, second_invoice, '70.00'))
        self.problem(409, self.payment, None, '40.00', 'receipt', [dict(document_id=second_invoice['id'], amount='40.00')])
        self.assertEqual(effective_paid(self.office, second_invoice['id']), Decimal('70.00'))

    def test_revision_target_and_preview_hashes_reject_stale_or_changed_confirmation(self):
        invoice = self.invoice(); payment, _ = self.imported()
        body = self.command(payment, invoice, '20.00')
        for changes in ({'amount': '21.00'}, {'preview_hash': '0'*64}, {'source_hash': '0'*64}, {'expected_revision': 1}, {'state_hash': '0'*64}):
            self.problem(409, self.alloc.assign, self.owner, payment['id'], {**body, **changes})
        other = self.invoice(project=self.other_project)
        self.problem(409, self.alloc.preview, self.owner, payment['id'], {**self.preview_body(payment, other), 'customer_id': self.customer})
        self.alloc.assign(self.owner, payment['id'], body)
        self.problem(409, self.alloc.assign, self.owner, payment['id'], {**body, 'request_id': uuid.uuid4().hex})
        self.assertEqual(self.alloc.state(self.owner, payment['id'])['revision'], 1)

    def test_first_assignment_binds_customer_and_wrong_customer_candidates_disappear(self):
        invoice = self.invoice(); other = self.invoice(project=self.other_project); payment, _ = self.imported()
        self.assertIsNone(self.alloc.state(self.owner, payment['id'])['customer_id'])
        self.assertEqual(self.alloc.candidates(self.owner, payment['id'])['total'], 2)
        old_other = self.preview_body(payment, other)
        self.alloc.assign(self.owner, payment['id'], self.command(payment, invoice))
        self.assertEqual([value['document_id'] for value in self.alloc.candidates(self.owner, payment['id'])['items']], [invoice['id']])
        newstate = self.alloc.state(self.owner, payment['id'])
        self.problem(409, self.alloc.preview, self.owner, payment['id'], {**old_other, 'state_hash': newstate['state_hash'], 'expected_revision': 1})

    def test_unassigned_original_privacy_survives_assignment_and_all_new_projects_required_on_replays(self):
        actor = self.bookkeeper(); invoice = self.invoice(); second = self.invoice(project=self.same_project)
        payment, event = self.imported()
        body = self.command(payment, invoice)
        self.alloc.assign(self.owner, payment['id'], body)
        self.problem(403, self.alloc.state, actor, payment['id'])
        self.assertEqual(self.finance.payments(actor)['items'], [])
        self.problem(403, self.api.event, actor, event['id'])
        self.office.assign(self.owner, self.same_project, actor['id'])
        original = self.legacy_req(source_id='shared-source', amount='100.00', kind='receipt', currency='EUR', booking_date='2026-11-02', reference='Shared',
                                   allocations=[dict(document_id=invoice['id'], amount='10.00')])
        shared = self.finance.record_payment(actor, original)
        imported = self.api.import_payment(actor, self.import_body(shared))
        command = self.command(shared, second, actor=actor)
        entry = self.alloc.assign(actor, shared['id'], command)
        self.office.assign(self.owner, self.same_project, actor['id'], remove=True)
        self.problem(404, self.alloc.assign, actor, shared['id'], command)
        self.problem(404, self.finance.record_payment, actor, original)
        self.problem(404, self.api.event, actor, imported['id'])
        self.assertEqual(self.finance.payments(actor)['items'], [])
        # Authorized invoice aggregate still includes a now-hidden complete payment.
        self.assertEqual(self.finance.open_items(actor)['items'][0]['paid'], '20.00')
        self.office.assign(self.owner, self.same_project, actor['id'])
        self.assertEqual(self.alloc.assign(actor, shared['id'], command), entry)
        self.grant(actor, 'accounting.prepare', effect='deny', revision=1)
        self.problem(403, self.alloc.assign, actor, shared['id'], command)
        self.assertFalse(self.alloc.state(actor, shared['id'])['writes_allowed'])

    def test_target_read_deny_is_not_overridden_by_write_allow_or_global_permissions(self):
        actor = self.bookkeeper(); first = self.invoice(); target = self.invoice(project=self.same_project)
        self.office.assign(self.owner, self.same_project, actor['id'])
        payment, _ = self.imported(allocations=[dict(document_id=first['id'], amount='5.00')])
        body = self.preview_body(payment, target, actor=actor)
        for permission, effect in (('finance.read', 'deny'), ('finance.write', 'allow')):
            BusinessFoundation(self.office).save_grant(self.owner, self.legacy_req(user_id=actor['id'], permission=permission, scope=self.same_project,
                effect=effect, revision=0))
        self.assertNotIn(target['id'], json.dumps(self.alloc.candidates(actor, payment['id'])))
        self.problem(403, self.alloc.preview, actor, payment['id'], body)

    def test_old_successful_entry_replays_after_refund_credit_and_inactive_account(self):
        invoice = self.invoice(); payment, _ = self.imported()
        body = self.command(payment, invoice, '30.00'); entry = self.alloc.assign(self.owner, payment['id'], body)
        self.payment(amount='10.00', kind='refund', allocations=[dict(document_id=invoice['id'], amount='10.00')])
        cancelled = self.docs.cancel(self.owner, invoice['id'], self.legacy_req(revision=invoice['revision'], reason='Synthetic cancellation'))
        self.docs.finalize(self.owner, cancelled['id'], render_prepared(self.docs.prepare_finalization(self.owner, cancelled['id'], cancelled['revision'])), uuid.uuid4().hex)
        self.api.update_account(self.owner, self.account['id'], self.req(revision=1, name='Archived account', active=False))
        self.assertEqual(self.alloc.assign(self.owner, payment['id'], body), entry)
        self.assertTrue(validate_integrity(self.office))
        self.assertEqual(self.alloc.candidates(self.owner, payment['id'])['items'], [])
        self.assertEqual(self.alloc.history(self.owner, payment['id'])['items'], [entry])

    def test_repeated_invoice_proofs_are_flat_and_bounded(self):
        invoice = self.invoice(); payment, _ = self.imported()
        for unused in range(20):
            self.alloc.assign(self.owner, payment['id'], self.command(payment, invoice, '1.00'))
        rows = self.office.db.execute('SELECT document_proof_json FROM business_accounting_allocation_entries ORDER BY revision').fetchall()
        sizes = [len(value[0]) for value in rows]
        self.assertLess(sizes[-1], sizes[0] + 20*600)
        self.assertLess(sum(sizes), 400000)
        last = json.loads(rows[-1][0])
        self.assertEqual(len(last['additional']), 19)
        self.assertNotIn('document_proof_json', json.dumps(last['additional']))
        self.assertTrue(validate_integrity(self.office))

    def test_atomic_race_and_rollback_leave_no_half_history(self):
        invoice = self.invoice(); payment, _ = self.imported(); body = self.command(payment, invoice, '60.00')
        def assign(request_id):
            try:
                return self.alloc.assign(self.owner, payment['id'], {**body, 'request_id': request_id})
            except Problem as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(assign, [uuid.uuid4().hex, uuid.uuid4().hex]))
        self.assertEqual(sum(isinstance(value, dict) for value in result), 1)
        self.assertIn(409, result)
        pending = self.command(payment, invoice, '10.00')
        horizon = restore_horizon(self.office)
        with patch.object(self.office, 'audit', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.alloc.assign(self.owner, payment['id'], pending)
        self.assertEqual(restore_horizon(self.office), horizon)

    def test_append_only_replace_guards_and_tamper_fail_closed(self):
        invoice = self.invoice(); payment, _ = self.imported(); body = self.command(payment, invoice)
        self.alloc.assign(self.owner, payment['id'], body)
        for table in protected_tables():
            row = dict(self.office.db.execute('SELECT * FROM ' + table).fetchone()); columns = list(row)
            for statement in ('UPDATE ' + table + ' SET ' + columns[0] + '=' + columns[0], 'DELETE FROM ' + table):
                with self.assertRaises(sqlite3.IntegrityError), self.office.db:
                    self.office.db.execute(statement)
            for variant in (row, {**row, **({'id': uuid.uuid4().hex} if 'id' in row else {'request_id': uuid.uuid4().hex})}):
                with self.assertRaises(sqlite3.IntegrityError), self.office.db:
                    self.office.db.execute('INSERT OR REPLACE INTO ' + table + '(' + ','.join(columns) + ') VALUES(' + ','.join('?' for unused in columns) + ')',
                                           tuple(variant[key] for key in columns))
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_accounting_allocation_entries_update_guard')
            self.office.db.execute("UPDATE business_accounting_allocation_entries SET revision='broken'")
        self.problem(409, self.alloc.state, self.owner, payment['id'])
        self.problem(409, self.alloc.assign, self.owner, payment['id'], body)
        with self.assertRaises(ValueError):
            restore_horizon(self.office)

    def test_validation_routing_pagination_and_unsupported_payment(self):
        invoice = self.invoice(); payment, _ = self.imported(); prefix = '/accounting/allocations/payments/' + payment['id']
        self.assertEqual(methods(prefix), 'GET'); self.assertEqual(methods(prefix + '/assign'), 'POST')
        self.assertEqual(dispatch(self.office, self.owner, prefix, 'GET', {})[0]['revision'], 0)
        self.problem(400, dispatch, self.office, self.owner, prefix, 'GET', {'_query': {'unknown': 'x'}})
        self.problem(400, dispatch, self.office, self.owner, prefix + '/candidates', 'GET', {'_query': {'limit': ['1', '2']}})
        body = self.preview_body(payment, invoice)
        self.problem(400, dispatch, self.office, self.owner, prefix + '/preview', 'POST', {**body, '_query': {}})
        for changes in ({'amount': '1.001'}, {'amount': 'NaN'}, {'amount': 1}, {'expected_revision': True}, {'reason': 'bad\ntext'}, {'extra': True}):
            self.problem(400, self.alloc.preview, self.owner, payment['id'], {**body, **changes})
        self.problem(400, self.alloc.candidates, self.owner, payment['id'], 101)
        self.assertEqual(self.alloc.candidates(self.owner, payment['id'], offset=100000)['items'], [])
        refund, _ = self.imported(kind='refund')
        self.assertEqual(self.alloc.state(self.owner, refund['id'])['blocked_reason'], 'unsupported_payment')
        self.assertEqual(self.alloc.candidates(self.owner, refund['id'])['items'], [])
        self.assertTrue(installed(self.office))

    def test_equal_open_with_different_payment_and_refund_still_invalidates_target_hash(self):
        invoice = self.invoice(); payment, _ = self.imported(); body = self.command(payment, invoice)
        self.payment(amount='5.00', allocations=[dict(document_id=invoice['id'], amount='5.00')])
        self.payment(amount='5.00', kind='refund', allocations=[dict(document_id=invoice['id'], amount='5.00')])
        self.assertEqual(self.finance.open_items(self.owner)['items'][0]['open'], '100.00')
        self.problem(409, self.alloc.assign, self.owner, payment['id'], body)
        self.assertEqual(self.alloc.state(self.owner, payment['id'])['revision'], 0)

    def test_corrupted_scalar_never_enters_effective_projection_or_new_invoice_proof(self):
        invoice = self.invoice(); payment, _ = self.imported(); body = self.command(payment, invoice)
        self.alloc.assign(self.owner, payment['id'], body)
        other, _ = self.imported()
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_accounting_allocation_entries_update_guard')
            self.office.db.execute("UPDATE business_accounting_allocation_entries SET amount='99.00'")
        self.problem(409, effective_paid, self.office, invoice['id'])
        self.problem(409, effective_allocations, self.office, payment['id'])
        self.problem(409, self.finance.open_items, self.owner)
        self.problem(409, self.alloc.candidates, self.owner, other['id'])
        self.problem(409, self.alloc.assign, self.owner, payment['id'], body)

    def test_partial_installation_and_missing_migration_marker_are_never_empty_ledgers(self):
        db = sqlite3.connect(':memory:'); self.addCleanup(db.close); db.row_factory = sqlite3.Row
        office = SimpleNamespace(db=db, lock=threading.RLock())
        self.assertFalse(installed(office)); self.assertIsNone(restore_horizon(office))
        db.execute('CREATE TABLE ' + protected_tables()[0] + '(id TEXT)')
        self.problem(409, installed, office)
        db.execute('CREATE TABLE ' + protected_tables()[1] + '(id TEXT)')
        self.problem(409, installed, office)

    def test_stored_source_corruption_does_not_precede_complete_project_authorization(self):
        first = self.invoice(); other = self.invoice(project=self.same_project); actor = self.bookkeeper()
        payment, _ = self.imported(allocations=[dict(document_id=first['id'], amount='1.00'), dict(document_id=other['id'], amount='1.00')])
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_payments_update_guard')
            self.office.db.execute("UPDATE business_payments SET amount='NaN' WHERE id=?", (payment['id'],))
        self.problem(404, self.alloc.state, actor, payment['id'])
        self.problem(409, self.alloc.state, self.owner, payment['id'])

    def test_large_legacy_cent_values_remain_valid_in_shared_projection(self):
        invoice = self.invoice(amount='1000000000.00')
        payment = self.payment(amount='1000000000.00', allocations=[dict(document_id=invoice['id'], amount='1000000000.00')])
        self.assertEqual(effective_paid(self.office, invoice['id']), Decimal('1000000000.00'))
        self.assertEqual(effective_allocations(self.office, payment['id'])[0]['amount'], '1000000000.00')
        self.assertEqual(self.finance.open_items(self.owner)['items'][0]['open'], '0.00')

    def test_dunning_snapshots_use_effective_ledger_and_stale_approval_is_rejected(self):
        from datetime import datetime, timezone
        from business_finance import default_rules
        invoice = self.invoice(); payment, _ = self.imported()
        self.finance.clock = lambda: datetime(2026, 12, 20, tzinfo=timezone.utc)
        rules = default_rules(); rules['enabled'] = True
        self.finance.save_settings(self.owner, self.legacy_req(revision=0, **rules))
        proposal = self.finance.propose(self.owner, self.legacy_req(document_ids=[invoice['id']]))['items'][0]
        self.assertEqual(proposal['open'], '100.00')
        self.alloc.assign(self.owner, payment['id'], self.command(payment, invoice))
        self.problem(409, self.finance.approve, self.owner, proposal['id'], self.req())
        current = self.finance.propose(self.owner, self.legacy_req(document_ids=[invoice['id']]))['items'][0]
        self.assertEqual((current['paid'], current['open']), ('10.00', '90.00'))


class AllocationMigrationTests(unittest.TestCase):
    def test_preallocation_schema_migrates_twice_preserving_signed_reports_and_final_invoice_sources(self):
        import business_schema
        old_registry = tuple(spec for spec in business_schema.registry() if spec.name not in ('business_accounting_allocations', 'business_accounting_components', 'business_accounting_refunds', 'business_accounting_capacity', 'business_accounting_refunds_v2', 'business_accounting_profile', 'business_accounting_euer', 'business_payroll_cash', 'business_bank_reconciliation', 'business_travel_allowances', 'business_accounting_openings'))
        fixture_case = AllocationTests('runTest'); self.addCleanup(fixture_case.doCleanups)
        with patch.object(business_schema, 'registry', return_value=old_registry):
            fixture_case.setUp()
            invoice = fixture_case.invoice()
            payment, event = fixture_case.imported(allocations=[dict(document_id=invoice['id'], amount='10.00')])
            report = fixture_case.office.draft(fixture_case.owner, fixture_case.project, 'Servicebericht', 'Synthetic preserved report')
            fixture_case.office.sign(fixture_case.owner, report['id'], report['content_hash'], 'Synthetic signer', [[[0.1,0.2],[0.8,0.9]]])
            pdf = fixture_case.office.pdf(fixture_case.owner, report['id'])
            before = fixture_case.snapshot(('reports', 'business_documents', 'business_document_archives', 'business_payments',
                'business_payment_allocations', 'business_accounting_cash_events', 'business_accounting_source_links'))
            old = old_horizon(fixture_case.office)
            self.assertIsNone(restore_horizon(fixture_case.office))
        for unused in range(2):
            business_schema.ensure_schema(fixture_case.office, activate=True)
            self.assertEqual(fixture_case.snapshot(tuple(before)), before)
            self.assertEqual(fixture_case.office.pdf(fixture_case.owner, report['id']), pdf)
            self.assertEqual(old_horizon(fixture_case.office), old)
            self.assertEqual(fixture_case.api.event(fixture_case.owner, event['id']), event)
            self.assertEqual(fixture_case.alloc.state(fixture_case.owner, payment['id'])['revision'], 0)
            self.assertTrue(validate_integrity(fixture_case.office))


if __name__ == '__main__':
    unittest.main()
