"""Documentary whole-portion cent allocation using isolated archived invoices.

SyntheticDocuments only seeds test SQLite invoice archives. Production issuer,
runtime privileges and separate-connection races are exercised by the PG suite.
"""
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
import unittest
from unittest.mock import patch
import uuid

import test_business_accounting as cash_fixture
import test_business_accounting_allocations as allocation_fixture
from business_accounting import restore_horizon as cash_horizon
from business_accounting_allocations import restore_horizon as allocation_horizon
from business_accounting_components import (DocumentComponents, dispatch, installed, methods, protected_tables, restore_horizon, validate_integrity)
from business_documents import render_prepared
from core import Problem, canonical


class ComponentTests(unittest.TestCase):
    actor = cash_fixture.AccountingTests.actor
    req = cash_fixture.AccountingTests.req
    legacy_req = cash_fixture.AccountingTests.legacy_req
    problem = cash_fixture.AccountingTests.problem
    grant = cash_fixture.AccountingTests.grant
    payment = cash_fixture.AccountingTests.payment
    payment_source = cash_fixture.AccountingTests.payment_source
    import_body = cash_fixture.AccountingTests.import_body
    snapshot = cash_fixture.AccountingTests.snapshot
    receipt = cash_fixture.AccountingTests.receipt
    review_body = cash_fixture.AccountingTests.review_body
    receipt_source = cash_fixture.AccountingTests.receipt_source
    payout_body = cash_fixture.AccountingTests.payout_body
    imported = allocation_fixture.AllocationTests.imported
    preview_body = allocation_fixture.AllocationTests.preview_body
    command = allocation_fixture.AllocationTests.command
    bookkeeper = allocation_fixture.AllocationTests.bookkeeper

    def setUp(self):
        allocation_fixture.AllocationTests.setUp(self)
        self.components = DocumentComponents(self.office, clock=self.clock)

    def invoice(self, project=None, net='100.00', rate='19', positions=None, kind='invoice'):
        draft = self.docs.create(self.owner, self.legacy_req(project_id=project or self.project, kind=kind, issue_date='2026-11-01', due_date='2026-11-10',
            buyer=dict(name='Synthetic buyer', address_line='Buyer street', postal_code='10117', city='Berlin', country='DE'),
            positions=positions or [dict(description='Synthetic source', quantity='1', unit='m', unit_price_net=net, tax_rate=rate)]))
        return self.docs.finalize(self.owner, draft['id'], render_prepared(self.docs.prepare_finalization(self.owner, draft['id'], draft['revision'])), uuid.uuid4().hex)

    def incoming(self):
        receipt = self.receipt()
        self.finance.review_receipt(self.owner, receipt['id'], self.review_body(revision=1, net='100.00', tax='19.00', gross='119.00'))
        return receipt

    def customer_event(self, invoice, amount='39.67', actor=None):
        return self.imported(amount=amount, allocations=[dict(document_id=invoice['id'], amount=amount)], actor=actor)[1]

    def body(self, event, *, actor=None, portion_id=None, groups=None):
        actor = actor or self.owner
        state = self.components.state(actor, event['id'])
        portions = self.components.portions(actor, event['id'])['items']
        portion = next(value for value in portions if value['portion_id'] == portion_id) if portion_id else portions[0]
        return dict(source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
            portion_id=portion['portion_id'], portion_state_hash=portion['portion_state_hash'],
            groups=groups if groups is not None else [dict(group_id=portion['groups'][0]['group_id'], amount=portion['amount'])],
            reason='Documented synthetic allocation')

    def confirm_body(self, event, **kwargs):
        body = self.body(event, **kwargs)
        preview = self.components.preview(kwargs.get('actor') or self.owner, event['id'], body)
        return self.req(**body, preview_hash=preview['preview_hash'])

    def test_original_three_cash_portions_round_exactly_without_changing_old_ledgers(self):
        invoice = self.invoice()
        events = [self.customer_event(invoice, amount) for amount in ('39.67', '39.67', '39.66')]
        old_tables = ('business_payments', 'business_payment_allocations', 'business_accounting_cash_events', 'business_accounting_source_links',
                      'business_accounting_allocation_entries', 'business_document_archives', 'business_finance_requests')
        old = self.snapshot(old_tables); h1 = cash_horizon(self.office); a1 = allocation_horizon(self.office)
        results = []
        for event in events:
            body = self.confirm_body(event); entry = self.components.confirm(self.owner, event['id'], body)
            self.assertEqual(self.components.confirm(self.owner, event['id'], body), entry)
            self.assertEqual(self.api.event(self.owner, event['id']), event)
            results.append((entry['net'], entry['tax']))
            self.assertEqual(self.components.state(self.owner, event['id'])['blocked_reason'], 'fully_documented')
        self.assertEqual(results, [('33.34', '6.33'), ('33.33', '6.34'), ('33.33', '6.33')])
        self.assertEqual(old, self.snapshot(old_tables)); self.assertEqual(h1, cash_horizon(self.office)); self.assertEqual(a1, allocation_horizon(self.office))
        self.assertTrue(validate_integrity(self.office))

    def test_supplier_three_payouts_use_one_review_pool_and_no_guessed_rate(self):
        receipt = self.incoming()
        events = [self.api.payout(self.owner, self.payout_body(receipt, amount=amount)) for amount in ('39.67', '39.67', '39.66')]
        self.assertEqual(self.receipt_source(receipt)['blocked_reason'], 'paid')
        values = []
        for event in events:
            portion = self.components.portions(self.owner, event['id'])['items'][0]
            self.assertTrue(portion['eligible'])
            self.assertEqual([portion['groups'][0][key] for key in ('rate', 'category', 'reason')], [None, None, None])
            entry = self.components.confirm(self.owner, event['id'], self.confirm_body(event))
            values.append((entry['net'], entry['tax']))
        self.assertEqual(values, [('33.34', '6.33'), ('33.33', '6.34'), ('33.33', '6.33')])
        self.assertTrue(validate_integrity(self.office))

    def test_additional_allocation_has_distinct_stable_portion_and_does_not_rewrite_original(self):
        invoice = self.invoice(); payment, event = self.imported(amount='130.00', allocations=[dict(document_id=invoice['id'], amount='59.50')])
        first_body = self.confirm_body(event); first = self.components.confirm(self.owner, event['id'], first_body)
        extra = self.alloc.assign(self.owner, payment['id'], self.command(payment, invoice, '59.50'))
        portions = self.components.portions(self.owner, event['id'])['items']
        self.assertEqual([value['kind'] for value in portions], ['additional_allocation'])
        self.assertEqual(self.components.confirm(self.owner, event['id'], first_body), first)
        second = self.components.confirm(self.owner, event['id'], self.confirm_body(event))
        self.assertEqual((first['amount'], second['amount']), ('59.50', '59.50'))
        self.assertNotEqual(first['portion']['portion_id'], second['portion']['portion_id'])
        state = self.components.state(self.owner, event['id'])
        self.assertEqual((state['documented_amount'], state['undocumented_amount'], state['unallocated_amount'], state['blocked_reason']),
                         ('119.00', '11.00', '11.00', 'unallocated'))
        self.assertEqual(self.api.event(self.owner, event['id']), event)
        self.assertEqual(self.alloc.history(self.owner, payment['id'])['items'], [extra])
        self.assertTrue(validate_integrity(self.office))

    def test_multigroup_requires_exact_explicit_distribution_and_hides_zero_groups(self):
        positions = [dict(description='Standard', quantity='1', unit='m', unit_price_net='100.00', tax_rate='19'),
                     dict(description='Reduced', quantity='1', unit='m', unit_price_net='50.00', tax_rate='7'),
                     dict(description='Free', quantity='1', unit='m', unit_price_net='0.00', tax_rate='0')]
        invoice = self.invoice(positions=positions); event = self.customer_event(invoice, '172.50')
        groups = self.components.portions(self.owner, event['id'])['items'][0]['groups']
        self.assertEqual(len(groups), 2)
        body = self.body(event, groups=[dict(group_id=value['group_id'], amount=value['gross']) for value in reversed(groups)])
        self.problem(400, self.components.preview, self.owner, event['id'], {**body, 'groups': body['groups'][:1]})
        preview = self.components.preview(self.owner, event['id'], body)
        self.assertEqual((preview['net'], preview['tax']), ('150.00', '22.50'))
        self.assertEqual([value['group_id'] for value in preview['lines']], sorted(value['group_id'] for value in groups))
        command = self.req(**body, preview_hash=preview['preview_hash'])
        result = self.components.confirm(self.owner, event['id'], command)
        self.assertEqual(self.components.confirm(self.owner, event['id'], command), result)
        self.problem(409, self.components.confirm, self.owner, event['id'], {**command, 'groups': list(reversed(command['groups']))})
        proof = json.loads(self.office.db.execute('SELECT proof_json FROM business_accounting_component_entries').fetchone()[0])
        self.assertEqual(len(proof['basis']), 3)
        self.assertTrue(validate_integrity(self.office))

    def test_refund_does_not_free_documentary_group_capacity(self):
        invoice = self.invoice(); first = self.customer_event(invoice, '119.00')
        self.components.confirm(self.owner, first['id'], self.confirm_body(first))
        refund, refund_event = self.imported(amount='119.00', kind='refund', allocations=[dict(document_id=invoice['id'], amount='119.00')])
        self.assertEqual(self.components.state(self.owner, refund_event['id'])['blocked_reason'], 'refund_origin_unresolved')
        second = self.customer_event(invoice, '119.00')
        state = self.components.state(self.owner, second['id'])
        self.assertEqual((state['eligible'], state['blocked_reason']), (False, 'group_capacity_exceeded'))
        self.assertEqual(self.api.event(self.owner, second['id']), second)
        self.assertEqual(self.finance.open_items(self.owner)['items'][0]['open'], '0.00')
        self.problem(409, self.components.preview, self.owner, second['id'], self.body(second))
        self.assertTrue(validate_integrity(self.office))

    def test_new_review_blocks_only_new_components_not_history_or_identical_replay(self):
        receipt = self.incoming()
        first = self.api.payout(self.owner, self.payout_body(receipt, amount='59.50'))
        second = self.api.payout(self.owner, self.payout_body(receipt, amount='59.50'))
        body = self.confirm_body(first); entry = self.components.confirm(self.owner, first['id'], body)
        self.finance.review_receipt(self.owner, receipt['id'], self.review_body(revision=2, net='200.00', tax='38.00', gross='238.00'))
        self.api.update_account(self.owner, self.account['id'], self.req(revision=1, name='Inactive bank', active=False))
        self.assertEqual(self.components.confirm(self.owner, first['id'], body), entry)
        self.assertEqual(self.components.history(self.owner, first['id'])['items'], [entry])
        self.assertEqual(self.components.state(self.owner, second['id'])['blocked_reason'], 'review_changed')
        self.problem(409, self.components.preview, self.owner, second['id'], self.body(second))
        self.assertTrue(validate_integrity(self.office))

    def test_later_credit_preserves_historical_entry_but_blocks_new_portion(self):
        invoice = self.invoice(); first = self.customer_event(invoice, '59.50'); second = self.customer_event(invoice, '59.50')
        body = self.confirm_body(first); entry = self.components.confirm(self.owner, first['id'], body)
        draft = self.docs.cancel(self.owner, invoice['id'], self.legacy_req(revision=invoice['revision'], reason='Synthetic cancellation'))
        self.docs.finalize(self.owner, draft['id'], render_prepared(self.docs.prepare_finalization(self.owner, draft['id'], draft['revision'])), uuid.uuid4().hex)
        self.assertEqual(self.components.confirm(self.owner, first['id'], body), entry)
        self.assertEqual(self.components.state(self.owner, second['id'])['blocked_reason'], 'unsupported_document')
        self.assertTrue(validate_integrity(self.office))

    def test_preview_is_readonly_and_semantic_portion_unique_across_request_ids(self):
        invoice = self.invoice(); event = self.customer_event(invoice); body = self.body(event)
        tables = tuple(row[0] for row in self.office.db.execute("SELECT name FROM sqlite_master WHERE type='table'"))
        before = self.snapshot(tables); preview = self.components.preview(self.owner, event['id'], body)
        self.assertEqual(self.snapshot(tables), before)
        command = self.req(**body, preview_hash=preview['preview_hash'])
        self.components.confirm(self.owner, event['id'], command)
        self.problem(409, self.components.confirm, self.owner, event['id'], {**command, 'request_id': uuid.uuid4().hex})
        self.assertEqual(len(self.components.history(self.owner, event['id'])['items']), 1)

    def test_global_pool_race_stale_preview_and_audit_failure_are_atomic(self):
        invoice = self.invoice(); events = [self.customer_event(invoice) for unused in range(2)]
        commands = [self.confirm_body(event) for event in events]
        def run(index):
            try:
                return self.components.confirm(self.owner, events[index]['id'], commands[index])
            except Problem as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, (0, 1)))
        self.assertEqual(sum(isinstance(value, dict) for value in results), 1); self.assertIn(409, results)
        loser = events[0 if results[0] == 409 else 1]
        pending = self.confirm_body(loser); before = restore_horizon(self.office)
        with patch.object(self.office, 'audit', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.components.confirm(self.owner, loser['id'], pending)
        self.assertEqual(restore_horizon(self.office), before)

    def test_fresh_project_scope_expansion_and_revocation_apply_to_old_replay(self):
        actor = self.bookkeeper(); invoice = self.invoice(); other = self.invoice(project=self.same_project)
        payment, event = self.imported(amount='100.00', allocations=[dict(document_id=invoice['id'], amount='20.00')], actor=actor)
        body = self.confirm_body(event, actor=actor); entry = self.components.confirm(actor, event['id'], body)
        self.office.assign(self.owner, self.same_project, actor['id'])
        self.alloc.assign(actor, payment['id'], self.command(payment, other, '20.00', actor=actor))
        self.assertEqual(self.components.confirm(actor, event['id'], body), entry)
        self.office.assign(self.owner, self.same_project, actor['id'], remove=True)
        self.problem(404, self.components.confirm, actor, event['id'], body)
        self.problem(404, self.components.history, actor, event['id'])
        self.office.assign(self.owner, self.same_project, actor['id'])
        self.grant(actor, 'accounting.prepare', effect='deny', revision=1)
        self.problem(403, self.components.confirm, actor, event['id'], body)
        self.assertEqual(self.components.history(actor, event['id'])['items'], [entry])

    def test_private_payment_remains_private_but_authorized_pool_aggregate_is_global(self):
        actor = self.bookkeeper(); invoice = self.invoice()
        private, hidden = self.imported(amount='39.67')
        self.alloc.assign(self.owner, private['id'], self.command(private, invoice, '39.67'))
        hidden_entry = self.components.confirm(self.owner, hidden['id'], self.confirm_body(hidden))
        visible = self.customer_event(invoice, actor=actor)
        listed = self.components.portions(actor, visible['id'])
        self.assertEqual(listed['items'][0]['groups'][0]['documented_gross'], '39.67')
        for hidden_id in (private['id'], hidden['id'], hidden_entry['id'], self.owner['id']):
            self.assertNotIn(hidden_id, json.dumps(listed))
        self.problem(403, self.components.state, actor, hidden['id'])
        entry = self.components.confirm(actor, visible['id'], self.confirm_body(visible, actor=actor))
        self.assertEqual((entry['net'], entry['tax']), ('33.33', '6.34'))

    def test_mixed_customer_source_is_readable_but_explicitly_unresolved(self):
        first = self.invoice(); other = self.invoice(project=self.other_project)
        unused, event = self.imported(amount='20.00', allocations=[dict(document_id=first['id'], amount='10.00'), dict(document_id=other['id'], amount='10.00')])
        self.assertEqual(self.components.state(self.owner, event['id'])['blocked_reason'], 'source_customer_unresolved')
        self.assertEqual(len(self.components.portions(self.owner, event['id'])['items']), 2)
        self.problem(409, self.components.preview, self.owner, event['id'], self.body(event))

    def test_append_only_all_three_tables_reject_replace_and_scalar_corruption_is_conflict(self):
        invoice = self.invoice(); event = self.customer_event(invoice); body = self.confirm_body(event)
        self.components.confirm(self.owner, event['id'], body)
        for table in protected_tables():
            row = dict(self.office.db.execute('SELECT * FROM ' + table).fetchone()); columns = list(row)
            for sql in ('UPDATE ' + table + ' SET ' + columns[0] + '=' + columns[0], 'DELETE FROM ' + table):
                with self.assertRaises(sqlite3.IntegrityError), self.office.db:
                    self.office.db.execute(sql)
            variants = [row]
            if 'id' in row:
                variants.append({**row, 'id': uuid.uuid4().hex})
            elif 'request_id' in row:
                variants.append({**row, 'request_id': uuid.uuid4().hex})
            for value in variants:
                with self.assertRaises(sqlite3.IntegrityError), self.office.db:
                    self.office.db.execute('INSERT OR REPLACE INTO ' + table + '(' + ','.join(columns) + ') VALUES(' + ','.join('?' for unused in columns) + ')',
                                           tuple(value[key] for key in columns))
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_accounting_component_lines_update_guard')
            self.office.db.execute("UPDATE business_accounting_component_lines SET net='99.00'")
        self.problem(409, self.components.history, self.owner, event['id'])
        self.problem(409, self.components.confirm, self.owner, event['id'], body)
        with self.assertRaises(ValueError):
            restore_horizon(self.office)

    def test_exact_input_contract_and_transport_filters(self):
        invoice = self.invoice(); event = self.customer_event(invoice); body = self.body(event)
        prefix = '/accounting/components/events/' + event['id']
        self.assertEqual(methods(prefix), 'GET'); self.assertEqual(methods(prefix+'/confirm'), 'POST')
        for changes in ({'amount': '1.00'}, {'expected_revision': True}, {'reason': 'bad\nreason'}, {'groups': []},
                        {'groups': body['groups']*2}, {'groups': [dict(body['groups'][0], amount='0.00')]},
                        {'groups': [dict(body['groups'][0], amount='NaN')]}, {'groups': [dict(body['groups'][0], amount='1.001')]}):
            self.problem(400, self.components.preview, self.owner, event['id'], {**body, **changes})
        self.problem(400, dispatch, self.office, self.owner, prefix, 'GET', {'unknown': True})
        self.problem(400, dispatch, self.office, self.owner, prefix+'/portions', 'GET', {'_query': {'limit': ['1','2']}})
        self.problem(400, dispatch, self.office, self.owner, prefix+'/preview', 'POST', {**body, '_query': {}})
        self.problem(400, self.components.portions, self.owner, event['id'], 101)
        self.assertEqual(self.components.portions(self.owner, event['id'], offset=100000)['items'], [])
        self.assertTrue(installed(self.office))

    def rewrite_component(self, entry, body, line):
        """Explicit corrupt-database fixture; recomputes incidental JSON hashes."""
        from business_accounting_components import _sha
        changed = dict(entry, lines=[line], amount=line['amount'], net=line['net'], tax=line['tax'])
        changed['preview_hash'] = _sha(canonical(self.components._preview_from_entry(changed)))
        request = dict(body, preview_hash=changed['preview_hash'], groups=[dict(group_id=line['group_id'], amount=line['amount'])])
        with self.office.db:
            for table in protected_tables():
                self.office.db.execute('DROP TRIGGER IF EXISTS ' + table + '_update_guard')
            self.office.db.execute('UPDATE business_accounting_component_entries SET entry_json=?,entry_sha256=? WHERE id=?',
                                   (canonical(changed), _sha(canonical(changed)), entry['id']))
            self.office.db.execute('UPDATE business_accounting_component_lines SET ' + ','.join(key+'=?' for key in line if key != 'group_id') + ' WHERE entry_id=?',
                                   tuple(value for key,value in line.items() if key != 'group_id') + (entry['id'],))
            self.office.db.execute('UPDATE business_accounting_component_requests SET request_json=?,request_hash=? WHERE entry_id=?',
                                   (canonical(request), self.components._request_hash(entry['event_id'], request), entry['id']))
        return request

    def test_last_entry_cannot_claim_a_self_consistent_but_nonexistent_previous_pool(self):
        from business_accounting_components import _line
        invoice = self.invoice(); event = self.customer_event(invoice); body = self.confirm_body(event)
        entry = self.components.confirm(self.owner, event['id'], body)
        row = self.office.db.execute('SELECT basis_json FROM business_accounting_component_lines WHERE entry_id=?', (entry['id'],)).fetchone()
        fake = _line(json.loads(row[0]), 3967, 3967)
        changed_request = self.rewrite_component(entry, body, fake)
        self.problem(409, self.components.history, self.owner, event['id'])
        self.problem(409, self.components.confirm, self.owner, event['id'], changed_request)
        with self.assertRaises(ValueError):
            validate_integrity(self.office)

    def test_foreign_pool_entry_must_still_represent_its_whole_source_portion(self):
        from business_accounting_components import _line
        invoice = self.invoice(); first = self.customer_event(invoice); second = self.customer_event(invoice)
        body = self.confirm_body(first); entry = self.components.confirm(self.owner, first['id'], body)
        basis = json.loads(self.office.db.execute('SELECT basis_json FROM business_accounting_component_lines WHERE entry_id=?', (entry['id'],)).fetchone()[0])
        self.rewrite_component(entry, body, _line(basis, 0, 1000))
        self.problem(409, self.components.portions, self.owner, second['id'])
        self.problem(409, self.components.state, self.owner, second['id'])


if __name__ == '__main__':
    unittest.main()
