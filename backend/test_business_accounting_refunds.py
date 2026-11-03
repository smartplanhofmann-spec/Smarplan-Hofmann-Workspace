"""Exact whole-refund origin binding, isolated SQLite archives and real domain APIs.

The existing explicit SyntheticDocuments fixture issues test invoice archives;
the independent PostgreSQL suite exercises production runtime/issuer policy.
"""
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
import unittest
from unittest.mock import patch
import uuid

import test_business_accounting_components as component_fixture
from business_accounting import restore_horizon as h1
from business_accounting_allocations import restore_horizon as a1
from business_accounting_components import restore_horizon as c1
from business_accounting_refunds import (RefundOrigins, dispatch, installed, methods, protected_tables, restore_horizon, validate_integrity)
from business_documents import render_prepared
from core import Problem, canonical


class RefundTests(unittest.TestCase):
    actor = component_fixture.ComponentTests.actor
    req = component_fixture.ComponentTests.req
    legacy_req = component_fixture.ComponentTests.legacy_req
    problem = component_fixture.ComponentTests.problem
    grant = component_fixture.ComponentTests.grant
    payment = component_fixture.ComponentTests.payment
    payment_source = component_fixture.ComponentTests.payment_source
    import_body = component_fixture.ComponentTests.import_body
    snapshot = component_fixture.ComponentTests.snapshot
    imported = component_fixture.ComponentTests.imported
    preview_body = component_fixture.ComponentTests.preview_body
    command = component_fixture.ComponentTests.command
    bookkeeper = component_fixture.ComponentTests.bookkeeper
    invoice = component_fixture.ComponentTests.invoice
    body = component_fixture.ComponentTests.body
    component_confirm_body = component_fixture.ComponentTests.confirm_body
    receipt = component_fixture.ComponentTests.receipt
    review_body = component_fixture.ComponentTests.review_body
    receipt_source = component_fixture.ComponentTests.receipt_source
    payout_body = component_fixture.ComponentTests.payout_body

    def setUp(self):
        component_fixture.ComponentTests.setUp(self)
        self.refunds = RefundOrigins(self.office, clock=self.clock)

    def cash_event(self, invoice, amount, *, kind='receipt', actor=None, cash_date='2026-11-02', total=None):
        actor = actor or self.owner
        payment = self.payment(actor=actor, amount=total or amount, kind=kind,
                               allocations=[dict(document_id=invoice['id'], amount=amount)])
        event = self.api.import_payment(actor, self.import_body(payment, cash_date=cash_date))
        return payment, event

    def income(self, invoice, amount='39.67', *, actor=None, cash_date='2026-11-02', total=None):
        payment, event = self.cash_event(invoice, amount, actor=actor, cash_date=cash_date, total=total)
        command = self.component_confirm_body(event, actor=actor or self.owner)
        entry = self.components.confirm(actor or self.owner, event['id'], command)
        return payment, event, entry

    def binding_body(self, event, choices=None, *, actor=None, document_id=None):
        actor = actor or self.owner
        state = self.refunds.state(actor, event['id'])
        portions = self.refunds.portions(actor, event['id'])['items']
        portion = next(value for value in portions if value['document_id'] == document_id) if document_id else portions[0]
        origins = self.refunds.origins(actor, event['id'], portion['portion_id'])['items']
        if choices is None:
            choices = [(origins[0]['entry_id'], origins[0]['group_id'], portion['amount'])]
        selected = []
        for entry_id, group_id, amount in choices:
            origin = next(value for value in origins if (value['entry_id'], value['group_id']) == (entry_id, group_id))
            selected.append(dict(entry_id=entry_id, group_id=group_id, lot_state_hash=origin['lot_state_hash'], amount=amount))
        return dict(source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
            portion_id=portion['portion_id'], portion_state_hash=portion['portion_state_hash'], origins=selected,
            reason='Explicit synthetic refund origin')

    def binding_command(self, event, choices=None, **kwargs):
        body = self.binding_body(event, choices, **kwargs)
        preview = self.refunds.preview(kwargs.get('actor') or self.owner, event['id'], body)
        return self.req(**body, preview_hash=preview['preview_hash'])

    def test_two_distinct_lots_same_group_return_exact_cumulative_cents_and_no_old_effects(self):
        invoice = self.invoice()
        income = [self.income(invoice, amount) for amount in ('39.67', '39.67', '39.66')]
        first, second = income[0][2], income[1][2]
        self.assertEqual((first['tax'], second['tax']), ('6.33', '6.34'))
        group_id = first['lines'][0]['group_id']; self.assertEqual(second['lines'][0]['group_id'], group_id)
        events = [self.cash_event(invoice, amount, kind='refund')[1] for amount in ('26.44', '26.44', '26.46')]
        old_tables = ('business_payments', 'business_payment_allocations', 'business_accounting_cash_events', 'business_accounting_source_links',
                      'business_accounting_component_entries', 'business_accounting_component_lines', 'business_accounting_component_requests',
                      'business_document_archives', 'business_finance_requests')
        before = self.snapshot(old_tables); horizons = (h1(self.office), a1(self.office), c1(self.office))
        results = []
        for index, event in enumerate(events):
            each = '13.22' if index < 2 else '13.23'
            choices = [(first['id'], group_id, each), (second['id'], group_id, each)]
            body = self.binding_command(event, choices)
            entry = self.refunds.confirm(self.owner, event['id'], body)
            self.assertEqual(self.refunds.confirm(self.owner, event['id'], body), entry)
            self.assertFalse(entry['capacity_released']); self.assertFalse(entry['tax_result_available'])
            self.assertEqual(entry['lines'][0]['rate'], '19'); self.assertEqual(entry['lines'][0]['category'], 'S')
            results.append((entry['net'], entry['tax']))
            self.assertEqual(self.refunds.state(self.owner, event['id'])['blocked_reason'], 'fully_documented')
        self.assertEqual(results, [('22.22', '4.22'), ('22.21', '4.23'), ('22.24', '4.22')])
        self.assertEqual(self.snapshot(old_tables), before)
        self.assertEqual((h1(self.office), a1(self.office), c1(self.office)), horizons)
        new_income = self.cash_event(invoice, '79.34')[1]
        self.assertEqual(self.components.state(self.owner, new_income['id'])['blocked_reason'], 'group_capacity_exceeded')
        self.assertTrue(validate_integrity(self.office))

    def test_preview_is_readonly_and_whole_refund_portion_unique_across_actors_and_requests(self):
        invoice = self.invoice(); self.income(invoice, '119.00'); unused, event = self.cash_event(invoice, '20.00', kind='refund')
        actor = self.bookkeeper(); body = self.binding_body(event)
        tables = tuple(row[0] for row in self.office.db.execute("SELECT name FROM sqlite_master WHERE type='table'"))
        before = self.snapshot(tables); preview = self.refunds.preview(self.owner, event['id'], body)
        self.assertEqual(self.snapshot(tables), before)
        command = self.req(**body, preview_hash=preview['preview_hash'])
        self.refunds.confirm(self.owner, event['id'], command)
        self.problem(409, self.refunds.confirm, self.owner, event['id'], {**command, 'request_id': uuid.uuid4().hex})
        self.problem(409, self.refunds.confirm, actor, event['id'], {**command, 'request_id': uuid.uuid4().hex})
        self.assertEqual(self.refunds.state(actor, event['id'])['origin_documented_amount'], '20.00')

    def test_competing_refunds_share_real_global_origin_budget_and_stale_preview_rolls_back(self):
        invoice = self.invoice(); unused, unused_event, first = self.income(invoice)
        self.income(invoice, '79.33')
        events = [self.cash_event(invoice, '39.67', kind='refund')[1] for unused in range(2)]
        choice = [(first['id'], first['lines'][0]['group_id'], '39.67')]
        commands = [self.binding_command(event, choice) for event in events]
        def run(index):
            try:
                return self.refunds.confirm(self.owner, events[index]['id'], commands[index])
            except Problem as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, (0,1)))
        self.assertEqual(sum(isinstance(value, dict) for value in results), 1); self.assertIn(409, results)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_accounting_refund_entries').fetchone()[0], 1)
        self.assertTrue(validate_integrity(self.office))

    def test_audit_failure_rolls_back_entries_lines_receipts_and_sequence(self):
        invoice = self.invoice(); self.income(invoice); unused, event = self.cash_event(invoice, '20.00', kind='refund')
        command = self.binding_command(event); before = restore_horizon(self.office)
        with patch.object(self.office, 'audit', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.refunds.confirm(self.owner, event['id'], command)
        self.assertEqual(restore_horizon(self.office), before)
        entry = self.refunds.confirm(self.owner, event['id'], command)
        self.assertEqual(entry['sequence'], 1)

    def test_source_cash_date_matters_and_later_component_creation_or_cancellation_does_not(self):
        invoice = self.invoice()
        unused, origin_event = self.cash_event(invoice, '119.00', cash_date='2026-10-30')
        unused, refund_event = self.cash_event(invoice, '20.00', kind='refund', cash_date='2026-10-31')
        # The refund already exists before the documentary origin is created.
        self.components.confirm(self.owner, origin_event['id'], self.component_confirm_body(origin_event))
        draft = self.docs.cancel(self.owner, invoice['id'], self.legacy_req(revision=invoice['revision'], reason='Synthetic cancellation'))
        self.docs.finalize(self.owner, draft['id'], render_prepared(self.docs.prepare_finalization(self.owner, draft['id'], draft['revision'])), uuid.uuid4().hex)
        body = self.binding_command(refund_event); entry = self.refunds.confirm(self.owner, refund_event['id'], body)
        self.assertEqual(entry['lines'][0]['origin_cash_date'], '2026-10-30')
        self.api.update_account(self.owner, self.account['id'], self.req(revision=1, name='Inactive account', active=False))
        self.assertEqual(self.refunds.confirm(self.owner, refund_event['id'], body), entry)
        self.assertTrue(validate_integrity(self.office))

    def test_later_origin_cash_date_and_wrong_invoice_never_match(self):
        invoice = self.invoice(); other = self.invoice(project=self.same_project)
        unused, unused_event, origin = self.income(invoice, cash_date='2026-11-02')
        unused, event = self.cash_event(invoice, '20.00', kind='refund', cash_date='2026-11-01')
        portion = self.refunds.portions(self.owner, event['id'])['items'][0]
        self.assertEqual(self.refunds.origins(self.owner, event['id'], portion['portion_id'])['items'], [])
        # A valid body/lot hash from another cash event cannot bypass date checks.
        unused, valid = self.cash_event(invoice, '10.00', kind='refund')
        body = self.binding_body(valid)
        state = self.refunds.state(self.owner, event['id'])
        changed = {**body, 'source_hash': state['source_hash'], 'state_hash': state['state_hash'], 'portion_id': portion['portion_id'],
                   'portion_state_hash': portion['portion_state_hash'], 'origins': [{**body['origins'][0], 'amount': '20.00'}]}
        self.problem(409, self.refunds.preview, self.owner, event['id'], changed)
        self.income(other)
        unused, other_refund = self.cash_event(other, '10.00', kind='refund')
        own = self.binding_body(other_refund)
        self.problem(409, self.refunds.preview, self.owner, other_refund['id'], {**own, 'origins': body['origins']})

    def test_scope_expansion_revocation_hides_bound_refund_and_unbound_candidates(self):
        actor = self.bookkeeper(); invoice = self.invoice(); other = self.invoice(project=self.same_project)
        payment, origin_event, unused = self.income(invoice, total='49.67', actor=actor)
        unused, refund = self.cash_event(invoice, '10.00', kind='refund', actor=actor)
        command = self.binding_command(refund, actor=actor); entry = self.refunds.confirm(actor, refund['id'], command)
        unused, pending = self.cash_event(invoice, '10.00', kind='refund', actor=actor)
        pending_command = self.binding_command(pending, actor=actor)
        self.office.assign(self.owner, self.same_project, actor['id'])
        self.alloc.assign(actor, payment['id'], self.command(payment, other, '10.00', actor=actor))
        self.assertEqual(self.refunds.confirm(actor, refund['id'], command), entry)
        self.office.assign(self.owner, self.same_project, actor['id'], remove=True)
        for method in (self.refunds.state, self.refunds.history, self.refunds.portions):
            self.problem(404, method, actor, refund['id'])
        self.problem(404, self.refunds.confirm, actor, refund['id'], command)
        self.assertEqual(self.refunds.state(actor, pending['id'])['origin_documented_amount'], '0.00')
        portion = self.refunds.portions(actor, pending['id'])['items'][0]
        self.assertEqual(self.refunds.origins(actor, pending['id'], portion['portion_id'])['items'], [])
        self.problem(404, self.refunds.preview, actor, pending['id'], {key: value for key, value in pending_command.items() if key not in ('request_id', 'preview_hash', 'confirmation')})
        self.problem(404, self.refunds.confirm, actor, pending['id'], pending_command)

    def test_original_private_origin_stays_private_even_when_invoice_is_visible(self):
        actor = self.bookkeeper(); invoice = self.invoice()
        payment, event = self.imported(amount='39.67')
        self.alloc.assign(self.owner, payment['id'], self.command(payment, invoice, '39.67'))
        self.components.confirm(self.owner, event['id'], self.component_confirm_body(event))
        unused, refund = self.cash_event(invoice, '10.00', kind='refund')
        portion = self.refunds.portions(actor, refund['id'])['items'][0]
        self.assertEqual(self.refunds.origins(actor, refund['id'], portion['portion_id'])['items'], [])
        command = self.binding_command(refund)
        self.problem(403, self.refunds.confirm, actor, refund['id'], command)
        self.refunds.confirm(self.owner, refund['id'], command)
        self.problem(403, self.refunds.state, actor, refund['id'])

    def test_foreign_refund_claims_reduce_public_lot_without_exposing_foreign_sources(self):
        actor = self.bookkeeper(); invoice = self.invoice(); other = self.invoice(project=self.same_project)
        unused, unused_event, origin = self.income(invoice, '119.00'); self.income(other, '119.00')
        hidden_payment = self.payment(amount='30.00', kind='refund', allocations=[dict(document_id=invoice['id'], amount='20.00'), dict(document_id=other['id'], amount='10.00')])
        hidden = self.api.import_payment(self.owner, self.import_body(hidden_payment))
        command = self.binding_command(hidden, document_id=invoice['id'])
        claimed = self.refunds.confirm(self.owner, hidden['id'], command)
        unused, visible = self.cash_event(invoice, '10.00', kind='refund', actor=actor)
        portion = self.refunds.portions(actor, visible['id'])['items'][0]
        public = self.refunds.origins(actor, visible['id'], portion['portion_id'])
        self.assertEqual((public['items'][0]['returned_amount'], public['items'][0]['remaining_amount']), ('20.00', '99.00'))
        for identifier in (hidden_payment['id'], hidden['id'], claimed['id'], command['request_id'], self.owner['id']):
            self.assertNotIn(identifier, json.dumps(public))
        self.assertNotIn(command['reason'], json.dumps(public))
        self.refunds.confirm(actor, visible['id'], self.binding_command(visible, actor=actor))
        self.assertTrue(validate_integrity(self.office))

    def test_mixed_customer_and_unallocated_refunds_are_preserved_unresolved(self):
        invoice = self.invoice(); other = self.invoice(project=self.other_project)
        self.income(invoice); self.income(other)
        payment = self.payment(amount='20.00', kind='refund', allocations=[dict(document_id=invoice['id'], amount='10.00'), dict(document_id=other['id'], amount='10.00')])
        event = self.api.import_payment(self.owner, self.import_body(payment))
        self.assertEqual(self.refunds.state(self.owner, event['id'])['blocked_reason'], 'source_customer_unresolved')
        for portion in self.refunds.portions(self.owner, event['id'])['items']:
            self.assertEqual(self.refunds.origins(self.owner, event['id'], portion['portion_id'])['items'], [])
        private = self.payment(amount='10.00', kind='refund'); unallocated = self.api.import_payment(self.owner, self.import_body(private))
        state = self.refunds.state(self.owner, unallocated['id'])
        self.assertEqual((state['blocked_reason'], state['origin_unresolved_amount'], state['unallocated_amount']), ('unallocated', '10.00', '10.00'))
        self.assertFalse(state['capacity_released'])

    def test_fresh_global_permissions_and_exact_input_contract(self):
        actor = self.bookkeeper(); invoice = self.invoice(); self.income(invoice)
        unused, event = self.cash_event(invoice, '20.00', kind='refund', actor=actor)
        body = self.binding_body(event, actor=actor)
        for changes in ({'amount':'1.00'}, {'expected_revision':True}, {'origins':[]}, {'origins':body['origins']*2}, {'reason':'bad\nreason'},
                        {'origins':[{**body['origins'][0], 'amount':'NaN'}]}, {'origins':[{**body['origins'][0], 'amount':'0.00'}]}):
            self.problem(400, self.refunds.preview, actor, event['id'], {**body, **changes})
        self.problem(400, self.refunds.preview, actor, event['id'], {**body, 'origins':[{**body['origins'][0], 'amount':'19.99'}]})
        prefix = '/accounting/refunds/events/'+event['id']
        self.assertEqual(methods(prefix+'/confirm'), 'POST')
        self.problem(400, dispatch, self.office, actor, prefix, 'GET', {'unknown': True})
        self.problem(400, dispatch, self.office, actor, prefix+'/origins', 'GET', {'_query':{}})
        self.problem(400, dispatch, self.office, actor, prefix+'/origins', 'GET', {'_query':{'portion_id':[body['portion_id'],body['portion_id']]}})
        self.problem(400, dispatch, self.office, actor, prefix+'/preview', 'POST', {**body, '_query':{}})
        command = self.binding_command(event, actor=actor); entry = self.refunds.confirm(actor, event['id'], command)
        self.grant(actor, 'accounting.prepare', effect='deny', revision=1)
        self.problem(403, self.refunds.confirm, actor, event['id'], command)
        self.assertEqual(self.refunds.history(actor, event['id'])['items'], [entry])
        self.assertFalse(self.refunds.state(actor, event['id'])['writes_allowed'])
        self.assertTrue(installed(self.office))

    def test_append_only_guards_reject_sqlite_replace_for_all_unique_keys(self):
        invoice = self.invoice(); self.income(invoice); unused, event = self.cash_event(invoice, '20.00', kind='refund')
        self.refunds.confirm(self.owner, event['id'], self.binding_command(event))
        before = self.snapshot(protected_tables())
        self.office.db.execute('PRAGMA recursive_triggers=OFF')
        for table in protected_tables():
            row = dict(self.office.db.execute('SELECT * FROM '+table).fetchone()); columns = list(row)
            for sql in ('UPDATE '+table+' SET '+columns[0]+'='+columns[0], 'DELETE FROM '+table):
                with self.assertRaises(sqlite3.IntegrityError), self.office.db:
                    self.office.db.execute(sql)
            variants = [row]
            if table.endswith('_entries'):
                # Preserve only refund_allocation_id as a unique collision.
                variants.append({**row, 'id':uuid.uuid4().hex, 'sequence':2, 'revision':2, 'portion_id':'f'*64})
                variants.append({**row, 'id':uuid.uuid4().hex})
            if table.endswith('_requests'):
                variants.append({**row, 'request_id':uuid.uuid4().hex})
            for value in variants:
                with self.assertRaises(sqlite3.IntegrityError), self.office.db:
                    self.office.db.execute('INSERT OR REPLACE INTO '+table+'('+','.join(columns)+') VALUES('+','.join('?' for unused in columns)+')',
                                           tuple(value[key] for key in columns))
        self.assertEqual(self.snapshot(protected_tables()), before)
        self.assertTrue(validate_integrity(self.office))

    def rewrite_return(self, entry, body, line):
        """Corrupt database fixture, deliberately recomputing incidental hashes."""
        from business_accounting_refunds import _sha
        changed = dict(entry, lines=[line], amount=line['amount'], net=line['net'], tax=line['tax'])
        changed['preview_hash'] = _sha(canonical(self.refunds._preview_from_entry(changed)))
        command = dict(body, preview_hash=changed['preview_hash'], origins=[{key:line[key] for key in ('entry_id','group_id','lot_state_hash','amount')}])
        with self.office.db:
            for table in protected_tables():
                self.office.db.execute('DROP TRIGGER IF EXISTS '+table+'_update_guard')
            self.office.db.execute('UPDATE business_accounting_refund_entries SET entry_json=?,entry_sha256=? WHERE id=?',
                                   (canonical(changed), _sha(canonical(changed)), entry['id']))
            fields = ('amount','net','tax','gross_before','gross_after','net_before','net_after','tax_before','tax_after',
                      'remaining_gross','remaining_net','remaining_tax')
            self.office.db.execute('UPDATE business_accounting_refund_lines SET '+','.join(key+'=?' for key in fields)+' WHERE entry_id=?',
                                   tuple(line[key] for key in fields)+(entry['id'],))
            self.office.db.execute('UPDATE business_accounting_refund_requests SET request_json=?,request_hash=? WHERE entry_id=?',
                                   (canonical(command), self.refunds._request_hash(entry['event_id'], command), entry['id']))
        return command

    def test_last_return_cannot_invent_self_consistent_prior_lot_claims(self):
        from business_accounting_refunds import _line, _origin
        invoice = self.invoice(); self.income(invoice); unused, event = self.cash_event(invoice, '20.00', kind='refund')
        command = self.binding_command(event); entry = self.refunds.confirm(self.owner, event['id'], command)
        lot = self.refunds._lot(entry['lines'][0]['entry_id'], entry['lines'][0]['group_id'], {})
        fake = _line(_origin(lot, 3, []), 2000)
        changed = self.rewrite_return(entry, command, fake)
        self.problem(409, self.refunds.history, self.owner, event['id'])
        self.problem(409, self.refunds.confirm, self.owner, event['id'], changed)
        with self.assertRaises(ValueError):
            validate_integrity(self.office)

    def test_forged_shortened_whole_portion_is_rejected_even_by_other_lot_read(self):
        from business_accounting_refunds import _line, _origin
        invoice = self.invoice(); self.income(invoice)
        unused, event = self.cash_event(invoice, '20.00', kind='refund'); unused, other = self.cash_event(invoice, '10.00', kind='refund')
        command = self.binding_command(event); entry = self.refunds.confirm(self.owner, event['id'], command)
        lot = self.refunds._lot(entry['lines'][0]['entry_id'], entry['lines'][0]['group_id'], {})
        self.rewrite_return(entry, command, _line(_origin(lot, 0, []), 1000))
        self.problem(409, self.refunds.state, self.owner, other['id'])
        self.problem(409, self.refunds.history, self.owner, event['id'])

    def test_boolean_stored_proof_version_is_not_an_integer_schema_version(self):
        invoice = self.invoice(); self.income(invoice); unused, event = self.cash_event(invoice, '20.00', kind='refund')
        command = self.binding_command(event); entry = self.refunds.confirm(self.owner, event['id'], command)
        proof = json.loads(self.office.db.execute('SELECT proof_json FROM business_accounting_refund_entries WHERE id=?', (entry['id'],)).fetchone()[0])
        proof['schema_version'] = True
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_accounting_refund_entries_update_guard')
            self.office.db.execute('UPDATE business_accounting_refund_entries SET proof_json=? WHERE id=?', (canonical(proof), entry['id']))
        self.problem(409, self.refunds.history, self.owner, event['id'])
        self.problem(409, self.refunds.confirm, self.owner, event['id'], command)

    def test_missing_stored_origin_line_is_conflict_but_unknown_new_lot_is_not_found(self):
        invoice = self.invoice(); self.income(invoice); unused, event = self.cash_event(invoice, '20.00', kind='refund')
        body = self.binding_body(event)
        self.problem(404, self.refunds.preview, self.owner, event['id'], {**body, 'origins':[{**body['origins'][0], 'group_id':'e'*64}]})
        command = self.binding_command(event); entry = self.refunds.confirm(self.owner, event['id'], command)
        self.office.db.execute('PRAGMA foreign_keys=OFF')
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_accounting_component_lines_delete_guard')
            self.office.db.execute('DELETE FROM business_accounting_component_lines WHERE entry_id=? AND group_id=?',
                                   (entry['lines'][0]['entry_id'], entry['lines'][0]['group_id']))
        self.problem(409, self.refunds.history, self.owner, event['id'])
        self.problem(409, self.refunds.confirm, self.owner, event['id'], command)

    def test_horizon_and_previews_do_not_rewrite_prior_refund_or_cash_proofs(self):
        invoice = self.invoice(); self.income(invoice); unused, first = self.cash_event(invoice, '10.00', kind='refund')
        unused, second = self.cash_event(invoice, '10.00', kind='refund')
        body = self.binding_command(first); entry = self.refunds.confirm(self.owner, first['id'], body)
        before = self.snapshot(protected_tables()); horizon = restore_horizon(self.office)
        self.refunds.state(self.owner, first['id']); self.refunds.history(self.owner, first['id'])
        self.refunds.preview(self.owner, second['id'], self.binding_body(second))
        self.assertEqual(self.snapshot(protected_tables()), before); self.assertEqual(restore_horizon(self.office), horizon)
        self.refunds.confirm(self.owner, second['id'], self.binding_command(second))
        self.assertEqual(self.refunds.confirm(self.owner, first['id'], body), entry)
        self.assertEqual(self.refunds.history(self.owner, first['id'])['items'], [entry])


if __name__ == '__main__':
    unittest.main()
