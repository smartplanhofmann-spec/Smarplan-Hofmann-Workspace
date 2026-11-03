"""Exact reusable documentary cents over genuine isolated C1/R1 fixtures."""
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
import unittest
from unittest.mock import patch
import uuid

import test_business_accounting_refunds as refund_fixture
from business_accounting import restore_horizon as h1
from business_accounting_allocations import restore_horizon as a1
from business_accounting_components import restore_horizon as c1
from business_accounting_refunds import restore_horizon as r1
from business_accounting_capacity import (ReusableDocumentComponents, protected_tables, restore_horizon, validate_integrity, _sha)
from core import Problem, canonical


class CapacityTests(unittest.TestCase):
    for _name, _value in vars(refund_fixture.RefundTests).items():
        if not _name.startswith('_') and not _name.startswith('test_') and _name != 'setUp':
            locals()[_name] = _value

    def setUp(self):
        refund_fixture.RefundTests.setUp(self)
        self.capacity = ReusableDocumentComponents(self.office, clock=self.clock)

    def capacity_body(self, event, *, actor=None, document_id=None, groups=None):
        actor = actor or self.owner
        state = self.capacity.state(actor, event['id'])
        portions = self.capacity.portions(actor, event['id'])['items']
        portion = next(value for value in portions if value['document_id'] == document_id) if document_id else portions[0]
        return dict(source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
            portion_id=portion['portion_id'], portion_state_hash=portion['portion_state_hash'], action=portion['action'],
            groups=groups or [dict(group_id=portion['groups'][0]['group_id'], amount=portion['amount'])], reason='Explicit synthetic reuse')

    def capacity_command(self, event, **kwargs):
        body = self.capacity_body(event, **kwargs)
        preview = self.capacity.preview(kwargs.get('actor') or self.owner, event['id'], body)
        return self.req(**body, preview_hash=preview['preview_hash'])

    def bound_return(self, invoice, amount, *, origin=None, cash_date='2026-11-02'):
        unused, event = self.cash_event(invoice, amount, kind='refund', cash_date=cash_date)
        choices = [(origin['id'], origin['lines'][0]['group_id'], amount)] if origin else None
        command = self.binding_command(event, choices)
        return event, self.refunds.confirm(self.owner, event['id'], command)

    def first_reuse(self, *, returned='40.00', consumed='10.00', income_date='2026-11-02', refund_date='2026-11-02'):
        invoice = self.invoice(); unused, unused_event, origin = self.income(invoice, '119.00', cash_date=income_date)
        self.bound_return(invoice, returned, origin=origin, cash_date=refund_date)
        unused, event = self.cash_event(invoice, consumed, cash_date=refund_date)
        command = self.capacity_command(event)
        entry = self.capacity.confirm(self.owner, event['id'], command)
        return invoice, origin, event, entry, command

    def test_middle_lot_exact_cents_old_bytes_horizons_and_replay(self):
        invoice = self.invoice(); income = [self.income(invoice, value) for value in ('39.67', '39.67', '39.66')]
        origin = income[1][2]; self.assertEqual(origin['tax'], '6.34')
        self.bound_return(invoice, '39.67', origin=origin)
        unused, event = self.cash_event(invoice, '39.67')
        old_tables = ('business_payments', 'business_payment_allocations', 'business_accounting_cash_events', 'business_accounting_source_links',
            'business_accounting_component_entries', 'business_accounting_component_lines', 'business_accounting_component_requests',
            'business_accounting_refund_entries', 'business_accounting_refund_lines', 'business_accounting_refund_requests',
            'business_document_archives', 'business_finance_requests')
        old = self.snapshot(old_tables); horizons = h1(self.office), a1(self.office), c1(self.office), r1(self.office)
        all_tables = tuple(row[0] for row in self.office.db.execute("SELECT name FROM sqlite_master WHERE type='table'"))
        before = self.snapshot(all_tables); command = self.capacity_command(event)
        self.assertEqual(before, self.snapshot(all_tables))
        entry = self.capacity.confirm(self.owner, event['id'], command)
        self.assertEqual((entry['net'], entry['tax']), ('33.33', '6.34'))
        self.assertEqual(entry['capacity_changes'][0]['basis'], dict(net='33.33', tax='6.34', gross='39.67'))
        self.assertEqual(self.capacity.confirm(self.owner, event['id'], command), entry)
        self.assertEqual(old, self.snapshot(old_tables)); self.assertEqual(horizons, (h1(self.office), a1(self.office), c1(self.office), r1(self.office)))
        self.assertEqual(self.capacity.state(self.owner, event['id'])['documented_amount'], '39.67')
        self.problem(409, self.capacity.confirm, self.owner, event['id'], {**command, 'request_id': uuid.uuid4().hex})
        self.assertTrue(validate_integrity(self.office))

    def test_successor_carries_actual_remaining_cents_and_does_not_reset_without_returns(self):
        invoice, origin, first, entry, command = self.first_reuse(returned='39.67', consumed='10.00')
        self.assertEqual((entry['net'], entry['tax']), ('8.40', '1.60'))
        self.bound_return(invoice, '20.00', origin=origin)
        unused, event = self.cash_event(invoice, '5.00')
        second = self.capacity.confirm(self.owner, event['id'], self.capacity_command(event))
        change = second['capacity_changes'][0]
        self.assertEqual(change['carry'], dict(net='24.94', tax='4.73', gross='29.67'))
        self.assertEqual(change['returned'], dict(net='16.80', tax='3.20', gross='20.00'))
        self.assertEqual(change['basis'], dict(net='41.74', tax='7.93', gross='49.67'))
        unused, third_event = self.cash_event(invoice, '7.00')
        third = self.capacity.confirm(self.owner, third_event['id'], self.capacity_command(third_event))
        self.assertEqual(third['capacity_changes'], [])
        self.assertEqual(third['lines'][0]['segment_id'], second['lines'][0]['segment_id'])
        self.assertEqual(third['lines'][0]['gross_before'], '5.00')
        self.bound_return(invoice, '30.00', origin=origin)
        unused, fourth_event = self.cash_event(invoice, '15.00')
        fourth = self.capacity.confirm(self.owner, fourth_event['id'], self.capacity_command(fourth_event))
        self.assertEqual(fourth['capacity_changes'][0]['carry']['gross'], '37.67')
        self.assertEqual(fourth['capacity_changes'][0]['basis']['gross'], '67.67')
        self.assertEqual(self.capacity.confirm(self.owner, first['id'], command), entry)
        self.assertTrue(validate_integrity(self.office))

    def test_unimported_and_unbound_finance_refunds_block_first_release(self):
        invoice = self.invoice(); unused, unused_event, origin = self.income(invoice, '119.00')
        self.bound_return(invoice, '20.00', origin=origin)
        payment = self.payment(kind='refund', amount='10.00', allocations=[dict(document_id=invoice['id'], amount='10.00')])
        unused, event = self.cash_event(invoice, '20.00')
        portion = self.capacity.portions(self.owner, event['id'])['items'][0]
        self.assertEqual((portion['action'], portion['blocked_reason']), (None, 'refund_origin_unresolved'))
        imported = self.api.import_payment(self.owner, self.import_body(payment))
        self.assertEqual(self.capacity.portions(self.owner, event['id'])['items'][0]['blocked_reason'], 'refund_origin_unresolved')
        self.refunds.confirm(self.owner, imported['id'], self.binding_command(imported))
        entry = self.capacity.confirm(self.owner, event['id'], self.capacity_command(event))
        self.assertEqual(entry['capacity_changes'][0]['basis']['gross'], '30.00')
        self.assertTrue(validate_integrity(self.office))

    def test_later_unresolved_refund_keeps_current_capacity_and_invalidates_new_preview(self):
        invoice, origin, unused, unused_entry, unused_command = self.first_reuse()
        unused, event = self.cash_event(invoice, '10.00')
        stale = self.capacity_command(event)
        unresolved = self.payment(kind='refund', amount='10.00', allocations=[dict(document_id=invoice['id'], amount='10.00')])
        self.bound_return(invoice, '5.00', origin=origin)
        before = restore_horizon(self.office)
        self.problem(409, self.capacity.confirm, self.owner, event['id'], stale)
        self.assertEqual(restore_horizon(self.office), before)
        portion = self.capacity.portions(self.owner, event['id'])['items'][0]
        self.assertEqual((portion['action'], portion['pending_blocked_reason']), ('document_current', 'refund_origin_unresolved'))
        self.assertEqual(portion['groups'][0]['pending_returns']['gross'], '5.00')
        entry = self.capacity.confirm(self.owner, event['id'], self.capacity_command(event))
        self.assertEqual(entry['capacity_changes'], [])
        self.assertTrue(validate_integrity(self.office))

    def test_dates_keep_older_current_capacity_but_do_not_release_future_returns(self):
        invoice, origin, unused, unused_entry, unused_command = self.first_reuse(
            returned='20.00', consumed='10.00', income_date='2026-01-01', refund_date='2026-01-10')
        self.bound_return(invoice, '5.00', origin=origin, cash_date='2026-01-20')
        unused, event = self.cash_event(invoice, '5.00', cash_date='2026-01-15')
        portion = self.capacity.portions(self.owner, event['id'])['items'][0]
        self.assertEqual(portion['pending_blocked_reason'], 'receipt_before_capacity')
        self.assertEqual(portion['groups'][0]['offered_capacity']['gross'], '10.00')
        entry = self.capacity.confirm(self.owner, event['id'], self.capacity_command(event))
        self.assertEqual(entry['capacity_changes'], [])
        self.assertTrue(validate_integrity(self.office))

    def test_empty_carry_does_not_retain_an_unrelated_later_date(self):
        invoice, origin, unused, unused_entry, unused_command = self.first_reuse(
            returned='20.00', consumed='20.00', income_date='2026-01-01', refund_date='2026-01-20')
        self.bound_return(invoice, '5.00', origin=origin, cash_date='2026-01-10')
        unused, event = self.cash_event(invoice, '5.00', cash_date='2026-01-10')
        entry = self.capacity.confirm(self.owner, event['id'], self.capacity_command(event))
        self.assertEqual(entry['capacity_changes'][0]['not_before_date'], '2026-01-10')
        self.assertEqual(entry['capacity_changes'][0]['carry'], dict(net='0.00', tax='0.00', gross='0.00'))
        self.assertTrue(validate_integrity(self.office))

    def test_whole_invoice_multigroup_handoff_and_audit_failure_are_atomic(self):
        positions = [dict(description='Standard', quantity='1', unit='m', unit_price_net='100.00', tax_rate='19'),
                     dict(description='Reduced', quantity='1', unit='m', unit_price_net='50.00', tax_rate='7'),
                     dict(description='Zero', quantity='1', unit='m', unit_price_net='0.00', tax_rate='0')]
        invoice = self.invoice(positions=positions); unused, income = self.cash_event(invoice, '172.50')
        groups = self.components.portions(self.owner, income['id'])['items'][0]['groups']
        by_rate = {group['rate']: group for group in groups}
        origin = self.components.confirm(self.owner, income['id'], self.component_confirm_body(income,
            groups=[dict(group_id=group['group_id'], amount=group['gross']) for group in groups]))
        unused, refund = self.cash_event(invoice, '30.00', kind='refund')
        self.refunds.confirm(self.owner, refund['id'], self.binding_command(refund,
            [(origin['id'], by_rate['19']['group_id'], '20.00'), (origin['id'], by_rate['7']['group_id'], '10.00')]))
        unused, event = self.cash_event(invoice, '30.00')
        command = self.capacity_command(event, groups=[dict(group_id=by_rate['19']['group_id'], amount='20.00'),
                                                     dict(group_id=by_rate['7']['group_id'], amount='10.00')])
        before = self.snapshot(protected_tables())
        with patch.object(self.office, 'audit', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaisesRegex(RuntimeError, 'Synthetic audit failure'):
                self.capacity.confirm(self.owner, event['id'], command)
        self.assertEqual(self.snapshot(protected_tables()), before)
        entry = self.capacity.confirm(self.owner, event['id'], command)
        self.assertEqual(len(entry['capacity_changes']), 3)
        self.assertEqual(sum(change['basis']['gross'] == '0.00' for change in entry['capacity_changes']), 1)
        self.assertEqual(entry['sequence'], 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_accounting_capacity_handoffs').fetchone()[0], 1)
        self.assertTrue(validate_integrity(self.office))

    def test_legacy_and_current_compete_for_one_whole_portion_and_legacy_replay_survives(self):
        invoice = self.invoice(); unused, initial = self.cash_event(invoice, '50.00')
        legacy_command = self.component_confirm_body(initial)
        origin = self.components.confirm(self.owner, initial['id'], legacy_command)
        self.bound_return(invoice, '20.00', origin=origin)
        unused, event = self.cash_event(invoice, '30.00')
        current_command = self.capacity_command(event); old_command = self.component_confirm_body(event)
        def confirm(which):
            try:
                return (self.capacity if which else self.components).confirm(self.owner, event['id'], current_command if which else old_command)
            except Problem as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(confirm, (0, 1)))
        self.assertEqual(sum(isinstance(value, dict) for value in results), 1)
        self.assertIn(409, results)
        self.assertEqual(self.components.confirm(self.owner, initial['id'], legacy_command), origin)
        if not self.office.db.execute('SELECT 1 FROM business_accounting_capacity_handoffs').fetchone():
            unused, following = self.cash_event(invoice, '10.00')
            self.capacity.confirm(self.owner, following['id'], self.capacity_command(following))
        unused, following = self.cash_event(invoice, '5.00')
        # Preparing a fresh C1 write is permanently denied for this invoice.
        self.problem(409, self.components.preview, self.owner, following['id'], self.body(following))
        self.assertEqual(self.components.confirm(self.owner, initial['id'], legacy_command), origin)
        self.assertTrue(validate_integrity(self.office))

    def test_scope_expansion_hides_historical_capacity_and_replay(self):
        actor = self.bookkeeper(); invoice = self.invoice(); other = self.invoice(project=self.same_project)
        payment, unused, origin = self.income(invoice, '119.00', total='129.00')
        self.bound_return(invoice, '20.00', origin=origin)
        unused, event = self.cash_event(invoice, '10.00', actor=actor)
        command = self.capacity_command(event, actor=actor)
        entry = self.capacity.confirm(actor, event['id'], command)
        self.office.assign(self.owner, self.same_project, actor['id'])
        self.alloc.assign(self.owner, payment['id'], self.command(payment, other, '10.00'))
        self.assertEqual(self.capacity.confirm(actor, event['id'], command), entry)
        self.office.assign(self.owner, self.same_project, actor['id'], remove=True)
        for method in (self.capacity.state, self.capacity.portions, self.capacity.history):
            self.problem(404, method, actor, event['id'])
        self.problem(404, self.capacity.confirm, actor, event['id'], command)
        self.assertEqual(self.capacity.history(self.owner, event['id'])['items'], [entry])

    def test_missing_new_return_rights_keeps_current_capacity_without_foreign_details(self):
        actor = self.bookkeeper()
        invoice, origin, unused, unused_entry, unused_command = self.first_reuse()
        other = self.invoice(project=self.same_project); unused, unused_event, other_origin = self.income(other, '119.00')
        payment = self.payment(kind='refund', amount='15.00', allocations=[dict(document_id=invoice['id'], amount='10.00'),
                                                                        dict(document_id=other['id'], amount='5.00')])
        refund = self.api.import_payment(self.owner, self.import_body(payment))
        command = self.binding_command(refund, [(origin['id'], origin['lines'][0]['group_id'], '10.00')], document_id=invoice['id'])
        hidden = self.refunds.confirm(self.owner, refund['id'], command)
        self.refunds.confirm(self.owner, refund['id'], self.binding_command(refund,
            [(other_origin['id'], other_origin['lines'][0]['group_id'], '5.00')], document_id=other['id']))
        unused, event = self.cash_event(invoice, '5.00', actor=actor)
        portion = self.capacity.portions(actor, event['id'])['items'][0]
        self.assertEqual((portion['action'], portion['pending_blocked_reason']), ('document_current', 'source_access_required'))
        for value in (payment['id'], refund['id'], hidden['id'], command['request_id'], command['reason']):
            self.assertNotIn(value, json.dumps(portion))
        entry = self.capacity.confirm(actor, event['id'], self.capacity_command(event, actor=actor))
        self.assertEqual(entry['capacity_changes'], [])
        self.assertTrue(validate_integrity(self.office))

    def test_forged_consistent_line_before_is_rejected_despite_rehashed_response_and_receipt(self):
        unused, unused_origin, event, entry, body = self.first_reuse()
        forged = json.loads(canonical(entry)); line = forged['lines'][0]
        # Same amount/net/tax and a self-consistent extra prior gross/net cent.
        for key in ('gross_before', 'gross_after', 'net_before', 'net_after'):
            cents = int(line[key].replace('.', ''))+1; line[key] = f'{cents//100}.{cents%100:02d}'
        for key in ('remaining_gross', 'remaining_net'):
            cents = int(line[key].replace('.', ''))-1; line[key] = f'{cents//100}.{cents%100:02d}'
        forged['preview_hash'] = _sha(canonical(self.capacity._preview_from_entry(forged)))
        command = dict(body, preview_hash=forged['preview_hash'])
        with self.office.db:
            for table in protected_tables():
                self.office.db.execute('DROP TRIGGER '+table+'_update_guard')
            self.office.db.execute('UPDATE business_accounting_capacity_entries SET entry_json=?,entry_sha256=? WHERE id=?',
                (canonical(forged), _sha(canonical(forged)), entry['id']))
            self.office.db.execute('UPDATE business_accounting_capacity_lines SET '+','.join(key+'=?' for key in line if key not in ('group_id', 'segment_id'))+' WHERE entry_id=?',
                tuple(value for key, value in line.items() if key not in ('group_id', 'segment_id'))+(entry['id'],))
            self.office.db.execute('UPDATE business_accounting_capacity_requests SET request_json=?,request_hash=? WHERE entry_id=?',
                (canonical(command), self.capacity._request_hash(event['id'], command), entry['id']))
        self.problem(409, self.capacity.history, self.owner, event['id'])
        self.problem(409, self.capacity.confirm, self.owner, event['id'], command)
        with self.assertRaises(ValueError):
            validate_integrity(self.office)

    def test_new_legacy_line_after_handoff_is_an_integrity_failure(self):
        invoice = self.invoice(); unused, unused_event, origin = self.income(invoice, '50.00')
        self.bound_return(invoice, '20.00', origin=origin)
        unused, event = self.cash_event(invoice, '20.00')
        self.capacity.confirm(self.owner, event['id'], self.capacity_command(event))
        unused, later = self.cash_event(invoice, '10.00')
        with patch('business_accounting_capacity.require_legacy_writer'):
            self.components.confirm(self.owner, later['id'], self.component_confirm_body(later))
        self.problem(409, self.capacity.history, self.owner, event['id'])
        with self.assertRaises(ValueError):
            validate_integrity(self.office)

    def test_sqlite_update_delete_and_replace_guards_protect_every_new_table(self):
        self.first_reuse()
        before = self.snapshot(protected_tables())
        for table in protected_tables():
            row = dict(self.office.db.execute('SELECT * FROM '+table+' LIMIT 1').fetchone()); columns = list(row)
            with self.assertRaises(sqlite3.IntegrityError), self.office.db:
                self.office.db.execute('UPDATE '+table+' SET '+columns[0]+'='+columns[0])
            with self.assertRaises(sqlite3.IntegrityError), self.office.db:
                self.office.db.execute('DELETE FROM '+table)
            with self.assertRaises(sqlite3.IntegrityError), self.office.db:
                self.office.db.execute('INSERT OR REPLACE INTO '+table+'('+','.join(columns)+') VALUES('+','.join('?' for unused in columns)+')', tuple(row.values()))
        self.assertEqual(self.snapshot(protected_tables()), before)
        self.assertTrue(validate_integrity(self.office))

    def test_unused_historical_group_still_requires_all_of_its_carried_source_rights(self):
        actor = self.bookkeeper(); other = self.invoice(project=self.same_project)
        invoice = self.invoice(positions=[dict(description='Standard', quantity='1', unit='m', unit_price_net='100.00', tax_rate='19'),
                                         dict(description='Reduced', quantity='1', unit='m', unit_price_net='50.00', tax_rate='7')])
        unused, first_income = self.cash_event(invoice, '119.00')
        groups = self.components.portions(self.owner, first_income['id'])['items'][0]['groups']
        by_rate = {value['rate']: value['group_id'] for value in groups}
        first_origin = self.components.confirm(self.owner, first_income['id'], self.component_confirm_body(first_income,
            groups=[dict(group_id=by_rate['19'], amount='119.00')]))
        other_payment, second_income = self.cash_event(invoice, '53.50', total='63.50')
        second_origin = self.components.confirm(self.owner, second_income['id'], self.component_confirm_body(second_income,
            groups=[dict(group_id=by_rate['7'], amount='53.50')]))
        self.bound_return(invoice, '20.00', origin=first_origin)
        self.bound_return(invoice, '10.00', origin=second_origin)
        unused, first = self.cash_event(invoice, '10.00')
        self.capacity.confirm(self.owner, first['id'], self.capacity_command(first, groups=[dict(group_id=by_rate['19'], amount='10.00')]))
        unused, second = self.cash_event(invoice, '5.00')
        command = self.capacity_command(second, actor=actor, groups=[dict(group_id=by_rate['19'], amount='5.00')])
        entry = self.capacity.confirm(actor, second['id'], command)
        self.assertEqual(entry['capacity_changes'], [])
        self.assertEqual(len(entry['portion']['groups']), 2)
        access_ids = json.loads(self.office.db.execute('SELECT access_segments_json FROM business_accounting_capacity_entries WHERE id=?', (entry['id'],)).fetchone()[0])
        self.assertEqual(len(access_ids), 2)
        self.alloc.assign(self.owner, other_payment['id'], self.command(other_payment, other, '10.00'))
        for method in (self.capacity.state, self.capacity.portions, self.capacity.history):
            self.problem(404, method, actor, second['id'])
        self.problem(404, self.capacity.confirm, actor, second['id'], command)
        self.assertEqual(self.capacity.history(self.owner, second['id'])['items'], [entry])

    def test_only_post_receipt_definitively_unaccepted_conflicts_have_resolution_marker(self):
        invoice = self.invoice(); unused, initial = self.cash_event(invoice, '50.00')
        old_command = self.component_confirm_body(initial)
        origin = self.components.confirm(self.owner, initial['id'], old_command)
        self.bound_return(invoice, '20.00', origin=origin)
        unused, event = self.cash_event(invoice, '20.00')
        legacy_pending = self.component_confirm_body(event)
        command = self.capacity_command(event)
        entry = self.capacity.confirm(self.owner, event['id'], command)
        with self.assertRaises(Problem) as caught:
            self.components.confirm(self.owner, event['id'], legacy_pending)
        self.assertEqual((caught.exception.status, caught.exception.request_resolution), (409, 'not_accepted'))
        with self.assertRaises(Problem) as caught:
            self.capacity.confirm(self.owner, event['id'], {**command, 'request_id':uuid.uuid4().hex})
        self.assertEqual((caught.exception.status, caught.exception.request_resolution), (409, 'not_accepted'))
        with self.assertRaises(Problem) as caught:
            self.capacity.confirm(self.owner, event['id'], {**command, 'reason':'Different original payload'})
        self.assertEqual(caught.exception.status, 409); self.assertIsNone(caught.exception.request_resolution)
        for api, target, body in ((self.components, initial, old_command), (self.capacity, event, command)):
            with patch.object(api, '_gate', side_effect=Problem(409, 'Synthetic operator gate')):
                with self.assertRaises(Problem) as caught:
                    api.confirm(self.owner, target['id'], body)
            self.assertEqual(caught.exception.status, 409); self.assertIsNone(caught.exception.request_resolution)
        self.assertEqual(self.components.confirm(self.owner, initial['id'], old_command), origin)
        self.assertEqual(self.capacity.confirm(self.owner, event['id'], command), entry)


if __name__ == '__main__':
    unittest.main()
