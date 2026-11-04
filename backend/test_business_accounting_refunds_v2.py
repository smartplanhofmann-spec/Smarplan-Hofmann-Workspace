"""The isolated exact R2 request contract; no installed module or fake ledger."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
from unittest.mock import patch
import unittest
import uuid

import test_business_accounting_capacity as capacity_fixture
from business_accounting_refunds_v2 import VersionedRefundOrigins, _origin_key, validate_integrity, protected_tables, restore_horizon
from business_accounting_refunds import RefundOrigins
from business_accounting_components import _sha
from core import Problem, canonical


def origin(**changes):
    return {**dict(origin_version='c1', entry_id='a'*32, group_id='b'*64, lot_state_hash='c'*64, amount='13.22'), **changes}


def preview():
    return dict(source_hash='d'*64, expected_revision=0, state_hash='e'*64, portion_id='f'*64, portion_state_hash='0'*64,
                origins=[origin()], reason='Exact selected documentary origin', action='takeover_and_bind')


def command():
    return dict(preview(), request_id='1'*32, preview_hash='2'*64, confirmation=True)


class VersionedRefundInputTests(unittest.TestCase):
    def bad(self, data, *, confirm=False):
        with self.assertRaises(Problem) as error:
            VersionedRefundOrigins._inputs(data, confirm)
        self.assertEqual(error.exception.status, 400)

    def test_mixed_versions_can_select_the_same_raw_id_and_group_as_distinct_lots(self):
        data = preview()
        data['origins'].append({**origin(), 'origin_version':'c2'})
        before = deepcopy(data)
        VersionedRefundOrigins._inputs(data)
        self.assertEqual(data, before)
        self.assertNotEqual(_origin_key(data['origins'][0]), _origin_key(data['origins'][1]))

    def test_duplicate_versioned_lot_is_rejected_even_if_amount_or_state_hash_differs(self):
        for extra in (origin(), {**origin(), 'amount':'10.00'}, {**origin(), 'lot_state_hash':'9'*64}):
            with self.subTest(extra=extra):
                self.bad({**preview(), 'origins':[origin(), extra]})

    def test_multiple_lots_of_the_same_group_and_version_are_explicitly_valid(self):
        data = preview(); data['origins'].append({**origin(), 'entry_id':'3'*32, 'amount':'26.45'})
        VersionedRefundOrigins._inputs(data)

    def test_unknown_missing_or_wrongly_nested_fields_are_rejected(self):
        data = preview()
        for key in data:
            with self.subTest(missing=key):
                self.bad({name:value for name, value in data.items() if name != key})
        self.bad({**data, 'capacity_released':True})
        self.bad({**data, 'origins':[{**origin(), 'refund_version':'r2'}]})
        self.bad({**data, 'origins':[{key:value for key, value in origin().items() if key != 'origin_version'}]})
        self.bad({**data, 'origins':('c1', 'a'*32, 'b'*64)})
        self.bad([data])

    def test_only_explicit_current_refund_actions_are_accepted(self):
        VersionedRefundOrigins._inputs(preview())
        VersionedRefundOrigins._inputs({**preview(), 'action':'bind_current'})
        for value in ('bind_legacy', 'takeover_and_document', 'r2', '', None, True):
            with self.subTest(action=value):
                self.bad({**preview(), 'action':value})

    def test_exact_version_and_lowercase_identifiers_are_required(self):
        for key, values in (('origin_version', ('C1', 'r1', 'c3', None, True)),
                            ('entry_id', ('A'*32, 'a'*31, 'a'*33, None)),
                            ('group_id', ('B'*64, 'b'*63, 'b'*65, None)),
                            ('lot_state_hash', ('C'*64, 'c'*63, 'c'*65, None))):
            for value in values:
                with self.subTest(field=key, value=value):
                    self.bad({**preview(), 'origins':[{**origin(), key:value}]})

    def test_exact_positive_bounded_cent_inputs_exclude_floats_zero_and_precision_loss(self):
        for amount in ('0.01', '999999999.99'):
            VersionedRefundOrigins._inputs({**preview(), 'origins':[{**origin(), 'amount':amount}]})
        for amount in ('0.00', '-1.00', '1.0', '01.00', '1.001', '1e2', '1000000000.00', 13.22, 1, True, None):
            with self.subTest(amount=amount):
                self.bad({**preview(), 'origins':[{**origin(), 'amount':amount}]})

    def test_origin_count_is_bounded_without_silent_truncation(self):
        origins = [{**origin(), 'entry_id':f'{index:032x}'} for index in range(500)]
        VersionedRefundOrigins._inputs({**preview(), 'origins':origins})
        self.bad({**preview(), 'origins':[]})
        self.bad({**preview(), 'origins':origins+[{**origin(), 'entry_id':f'{500:032x}'}]})

    def test_revision_hash_reason_and_confirmation_keep_the_strict_existing_contract(self):
        for revision in (-1, True, False, 1.0, '0', None):
            with self.subTest(revision=revision):
                self.bad({**preview(), 'expected_revision':revision})
        for field in ('source_hash', 'state_hash', 'portion_id', 'portion_state_hash'):
            self.bad({**preview(), field:'A'*64})
        for reason in ('', ' ', 'x'*1001, 'two\nlines', '\x00', '\x7f', '\ud800', None):
            with self.subTest(reason=repr(reason)):
                self.bad({**preview(), 'reason':reason})
        VersionedRefundOrigins._inputs({**preview(), 'reason':'x'*1000})
        VersionedRefundOrigins._inputs(command(), True)
        self.bad(command())
        self.bad(preview(), confirm=True)
        for value in (False, 1, 'true', None):
            self.bad({**command(), 'confirmation':value}, confirm=True)

    def test_request_digest_preserves_version_order_event_and_exact_original_content(self):
        event = '4'*32; data = command()
        data['origins'].append({**origin(), 'origin_version':'c2'})
        before = deepcopy(data)
        digest = VersionedRefundOrigins._request_hash(event, data)
        self.assertEqual(digest, VersionedRefundOrigins._request_hash(event, deepcopy(data)))
        self.assertNotEqual(digest, VersionedRefundOrigins._request_hash('5'*32, data))
        self.assertNotEqual(digest, VersionedRefundOrigins._request_hash(event, {**data, 'origins':list(reversed(data['origins']))}))
        self.assertNotEqual(digest, VersionedRefundOrigins._request_hash(event, {**data, 'action':'bind_current'}))
        self.assertNotEqual(digest, RefundOrigins._request_hash(event, data))
        self.assertEqual(data, before)


class VersionedRefundDomainTests(unittest.TestCase):
    for _name, _value in vars(capacity_fixture.CapacityTests).items():
        if not _name.startswith('_') and not _name.startswith('test_') and _name != 'setUp':
            locals()[_name] = _value

    def setUp(self):
        capacity_fixture.CapacityTests.setUp(self)
        self.r2 = VersionedRefundOrigins(self.office, clock=self.clock)

    def versioned_body(self, event, choices, *, actor=None, document_id=None):
        actor = actor or self.owner
        state = self.r2.state(actor, event['id']); portions = self.r2.portions(actor, event['id'])['items']
        portion = next(value for value in portions if value['document_id'] == document_id) if document_id else portions[0]
        candidates = self.r2.origins(actor, event['id'], portion['portion_id'])['items']
        origins = []
        for version, entry_id, group_id, amount in choices:
            candidate = next(value for value in candidates if _origin_key(value) == (version, entry_id, group_id))
            origins.append(dict(origin_version=version, entry_id=entry_id, group_id=group_id, lot_state_hash=candidate['lot_state_hash'], amount=amount))
        return dict(source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
            portion_id=portion['portion_id'], portion_state_hash=portion['portion_state_hash'], action=portion['action'],
            origins=origins, reason='Explicit mixed version documentary return')

    def versioned_command(self, event, choices, **kwargs):
        data = self.versioned_body(event, choices, **kwargs)
        preview = self.r2.preview(kwargs.get('actor') or self.owner, event['id'], data)
        return self.req(**data, preview_hash=preview['preview_hash'])

    def mixed_seed(self):
        invoice = self.invoice(); lots = [self.income(invoice, value)[2] for value in ('39.67', '39.67', '39.66')]
        middle = lots[1]; first_refund, first_return = self.bound_return(invoice, '13.22', origin=middle)
        unused, receipt = self.cash_event(invoice, '13.22')
        positive_command = self.capacity_command(receipt)
        reused = self.capacity.confirm(self.owner, receipt['id'], positive_command)
        self.assertEqual((reused['net'], reused['tax']), ('11.11', '2.11'))
        return invoice, middle, first_refund, first_return, receipt, reused, positive_command

    def test_mixed_original_and_reused_lots_keep_exact_cents_through_two_new_cycles(self):
        invoice, middle, old_refund, old_return, receipt, reused, positive_command = self.mixed_seed()
        unused, refund = self.cash_event(invoice, '26.44', kind='refund')
        group_id = middle['lines'][0]['group_id']
        command = self.versioned_command(refund, [('c1', middle['id'], group_id, '13.22'), ('c2', reused['id'], group_id, '13.22')])
        before = self.snapshot(tuple(row[0] for row in self.office.db.execute("SELECT name FROM sqlite_master WHERE type='table'")))
        self.r2.preview(self.owner, refund['id'], {key:value for key, value in command.items() if key not in ('request_id', 'preview_hash', 'confirmation')})
        self.assertEqual(before, self.snapshot(tuple(row[0] for row in self.office.db.execute("SELECT name FROM sqlite_master WHERE type='table'"))))
        entry = self.r2.confirm(self.owner, refund['id'], command)
        self.assertEqual((entry['net'], entry['tax']), ('22.21', '4.23'))
        self.assertEqual([value['origin_version'] for value in entry['lines']], ['c1', 'c2'])
        self.assertEqual(entry['lines'][0]['tax'], '2.12')
        self.assertEqual(self.r2.confirm(self.owner, refund['id'], command), entry)
        self.assertEqual(self.capacity.confirm(self.owner, receipt['id'], positive_command), reused)
        for unused_cycle in range(2):
            unused, receipt = self.cash_event(invoice, '26.44')
            current = self.capacity.confirm(self.owner, receipt['id'], self.capacity_command(receipt))
            self.assertEqual((current['net'], current['tax']), ('22.21', '4.23'))
            unused, later_refund = self.cash_event(invoice, '26.44', kind='refund')
            later = self.r2.confirm(self.owner, later_refund['id'], self.versioned_command(later_refund,
                [('c2', current['id'], group_id, '26.44')]))
            self.assertEqual((later['net'], later['tax']), ('22.21', '4.23'))
            self.assertTrue(validate_integrity(self.office))
        self.assertEqual(self.r2.confirm(self.owner, refund['id'], command), entry)
        self.assertEqual(self.refunds.history(self.owner, old_refund['id'])['items'], [old_return])
        self.assertEqual(self.components.history(self.owner, middle['event_id'])['items'], [middle])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_accounting_refunds_v2_releases').fetchone()[0], 3)

    def test_original_c1_counter_reaches_its_exact_full_cents_across_versions(self):
        invoice, middle, unused, old, unused_receipt, unused_reused, unused_command = self.mixed_seed()
        group = middle['lines'][0]['group_id']; returned = []
        for amount in ('13.22', '13.23'):
            unused, event = self.cash_event(invoice, amount, kind='refund')
            returned.append(self.r2.confirm(self.owner, event['id'], self.versioned_command(event, [('c1', middle['id'], group, amount)])))
        self.assertEqual([(entry['net'], entry['tax']) for entry in returned], [('11.10', '2.12'), ('11.12', '2.11')])
        self.assertEqual(returned[-1]['lines'][0]['remaining_gross'], '0.00')
        self.assertEqual(sum(int(entry['tax'].replace('.', '')) for entry in [old]+returned), 634)
        self.assertTrue(validate_integrity(self.office))

    def test_unknown_finance_refund_blocks_new_capacity_but_not_negative_handoff(self):
        invoice, middle, unused, unused_old, unused_receipt, reused, unused_command = self.mixed_seed()
        unknown = self.payment(kind='refund', amount='5.00', allocations=[dict(document_id=invoice['id'], amount='5.00')])
        unused, event = self.cash_event(invoice, '10.00', kind='refund')
        group = middle['lines'][0]['group_id']
        entry = self.r2.confirm(self.owner, event['id'], self.versioned_command(event, [('c2', reused['id'], group, '10.00')]))
        self.assertEqual(entry['action'], 'takeover_and_bind')
        unused, receipt = self.cash_event(invoice, '10.00')
        portion = self.capacity.portions(self.owner, receipt['id'])['items'][0]
        self.assertEqual((portion['action'], portion['blocked_reason']), (None, 'refund_origin_unresolved'))
        imported = self.api.import_payment(self.owner, self.import_body(unknown))
        self.r2.confirm(self.owner, imported['id'], self.versioned_command(imported, [('c1', middle['id'], group, '5.00')]))
        positive = self.capacity.confirm(self.owner, receipt['id'], self.capacity_command(receipt))
        self.assertEqual(positive['capacity_changes'][0]['returned']['gross'], '15.00')
        self.assertTrue(validate_integrity(self.office))

    def test_mixed_handoff_audit_failure_rolls_back_every_new_row_and_retry(self):
        invoice, middle, unused, unused_old, unused_receipt, reused, unused_command = self.mixed_seed()
        unused, event = self.cash_event(invoice, '26.44', kind='refund'); group = middle['lines'][0]['group_id']
        command = self.versioned_command(event, [('c1', middle['id'], group, '13.22'), ('c2', reused['id'], group, '13.22')])
        before = self.snapshot(protected_tables())
        with patch.object(self.office, 'audit', side_effect=RuntimeError('Synthetic mixed refund failure')):
            with self.assertRaisesRegex(RuntimeError, 'Synthetic mixed refund failure'):
                self.r2.confirm(self.owner, event['id'], command)
        self.assertEqual(self.snapshot(protected_tables()), before)
        self.assertEqual(self.r2.confirm(self.owner, event['id'], command)['sequence'], 1)
        self.assertTrue(validate_integrity(self.office))

    def test_r1_and_r2_compete_for_one_whole_portion_and_preserve_accepted_r1_replay(self):
        invoice, middle, old_event, old_entry, unused_receipt, unused_reused, unused_command = self.mixed_seed()
        old_body = json.loads(self.office.db.execute('SELECT request_json FROM business_accounting_refund_requests WHERE entry_id=?', (old_entry['id'],)).fetchone()[0])
        unused, event = self.cash_event(invoice, '5.00', kind='refund'); group = middle['lines'][0]['group_id']
        legacy = self.binding_command(event, [(middle['id'], group, '5.00')])
        current = self.versioned_command(event, [('c1', middle['id'], group, '5.00')])
        def run(which):
            try:
                return (self.r2 if which else self.refunds).confirm(self.owner, event['id'], current if which else legacy)
            except Problem as error:
                return error.status, error.request_resolution
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, (0, 1)))
        self.assertEqual(sum(isinstance(value, dict) for value in results), 1)
        self.assertIn((409, 'not_accepted'), results)
        self.assertEqual(self.refunds.confirm(self.owner, old_event['id'], old_body), old_entry)
        self.assertTrue(validate_integrity(self.office))

    def test_r1_candidates_use_full_positive_event_capacity_source_hull(self):
        actor = self.bookkeeper(); self.office.assign(self.owner, self.same_project, actor['id'])
        invoice_a = self.invoice(); invoice_b = self.invoice(project=self.same_project)
        hidden_project = self.office.add_project(self.owner, 'Hidden carried source', customer_id=self.customer)
        hidden_invoice = self.invoice(project=hidden_project)
        origin_payment, unused_event, origin_b = self.income(invoice_b, '119.00', total='129.00')
        self.bound_return(invoice_b, '10.00', origin=origin_b)
        payment = self.payment(amount='10.00', allocations=[dict(document_id=invoice_a['id'], amount='5.00'), dict(document_id=invoice_b['id'], amount='5.00')])
        positive = self.api.import_payment(self.owner, self.import_body(payment))
        portion_a = next(value for value in self.components.portions(self.owner, positive['id'])['items'] if value['document_id'] == invoice_a['id'])
        origin_a = self.components.confirm(self.owner, positive['id'], self.component_confirm_body(positive, portion_id=portion_a['portion_id']))
        self.capacity.confirm(self.owner, positive['id'], self.capacity_command(positive, document_id=invoice_b['id']))
        unused, refund_a = self.cash_event(invoice_a, '5.00', kind='refund')
        portion = self.refunds.portions(actor, refund_a['id'])['items'][0]
        self.assertTrue(self.refunds.origins(actor, refund_a['id'], portion['portion_id'])['items'])
        command = self.binding_command(refund_a, [(origin_a['id'], origin_a['lines'][0]['group_id'], '5.00')])
        self.alloc.assign(self.owner, origin_payment['id'], self.command(origin_payment, hidden_invoice, '10.00'))
        self.assertEqual(self.refunds.origins(actor, refund_a['id'], portion['portion_id'])['items'], [])
        self.problem(404, self.refunds.preview, actor, refund_a['id'], {key:value for key, value in command.items() if key not in ('request_id', 'preview_hash', 'confirmation')})
        self.assertTrue(validate_integrity(self.office))

    def test_real_pre_r2_migration_preserves_v1_rows_and_exact_old_replays(self):
        import business_schema
        full = business_schema.registry(); previous = tuple(value for value in full if value.name not in ('business_accounting_refunds_v2', 'business_accounting_profile', 'business_accounting_euer', 'business_payroll_cash', 'business_bank_reconciliation', 'business_travel_allowances', 'business_accounting_openings'))
        old = VersionedRefundDomainTests('runTest'); self.addCleanup(old.doCleanups)
        with patch.object(business_schema, 'registry', return_value=previous):
            old.setUp()
            invoice, middle, refund, returned, receipt, reused, positive_command = old.mixed_seed()
            proof = json.loads(old.office.db.execute('SELECT proof_json FROM business_accounting_capacity_entries WHERE id=?', (reused['id'],)).fetchone()[0])
            self.assertEqual(proof['schema_version'], 1)
            tables = ('business_accounting_capacity_entries', 'business_accounting_capacity_segments', 'business_accounting_capacity_handoffs',
                      'business_accounting_capacity_releases', 'business_accounting_capacity_lines', 'business_accounting_capacity_requests',
                      'business_accounting_refund_entries', 'business_accounting_refund_lines', 'business_accounting_refund_requests')
            before = old.snapshot(tables)
        business_schema.ensure_schema(old.office, activate=True)
        self.assertEqual(old.snapshot(tables), before)
        self.assertEqual(old.capacity.confirm(old.owner, receipt['id'], positive_command), reused)
        unused, new_refund = old.cash_event(invoice, '26.44', kind='refund'); group = middle['lines'][0]['group_id']
        old.r2.confirm(old.owner, new_refund['id'], old.versioned_command(new_refund,
            [('c1', middle['id'], group, '13.22'), ('c2', reused['id'], group, '13.22')]))
        unused, next_receipt = old.cash_event(invoice, '26.44')
        entry = old.capacity.confirm(old.owner, next_receipt['id'], old.capacity_command(next_receipt))
        self.assertEqual((entry['net'], entry['tax']), ('22.21', '4.23'))
        self.assertEqual(old.capacity.confirm(old.owner, receipt['id'], positive_command), reused)
        self.assertEqual(old.office.db.execute('SELECT entry_json FROM business_accounting_capacity_entries WHERE id=?', (reused['id'],)).fetchone()[0], canonical(reused))
        self.assertTrue(validate_integrity(old.office))

    def test_later_r1_gate_binding_cannot_be_forged_into_an_earlier_observed_prefix(self):
        from accounting_joint_ledger import combined_sources
        from business_accounting_capacity import ReusableDocumentComponents
        invoice, origin, unused, unused_entry, unused_command = self.first_reuse(
            returned='20.00', consumed='10.00', income_date='2026-01-01', refund_date='2026-01-10')
        self.bound_return(invoice, '5.00', origin=origin, cash_date='2026-01-20')
        unused, event = self.cash_event(invoice, '5.00', cash_date='2026-01-15')
        body = self.capacity_command(event); entry = self.capacity.confirm(self.owner, event['id'], body)
        rows = self.office.db.execute('SELECT * FROM business_accounting_capacity_entries ORDER BY sequence').fetchall()
        previous, prior_proof = self.capacity._basic(rows[0]); ledger = self.capacity._empty_ledger()
        self.capacity._apply(rows[0], previous, prior_proof, ledger, validate_rows=True)
        sources = combined_sources(self.capacity._sources({}), self.r2._empty_ledger())
        proof = json.loads(rows[1]['proof_json']); proof['r1_sequence'] = 1
        context, raw = self.capacity._historical_source(rows[1], proof)
        original_check = ReusableDocumentComponents._validate_gate_snapshot
        def old_unbounded_check(api, document_id, gate, source, *, r1_sequence=None):
            return original_check(api, document_id, gate, source)
        with patch.object(ReusableDocumentComponents, '_validate_gate_snapshot', old_unbounded_check):
            portion, forged_proof = self.capacity._plan(None, context, raw, ledger, sources, historical=proof)
        forged = dict(entry, portion=portion)
        forged['preview_hash'] = _sha(canonical(self.capacity._preview_from_entry(forged)))
        command = dict(body, portion_state_hash=portion['portion_state_hash'], preview_hash=forged['preview_hash'])
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_accounting_capacity_entries_update_guard')
            self.office.db.execute('DROP TRIGGER business_accounting_capacity_requests_update_guard')
            self.office.db.execute('UPDATE business_accounting_capacity_entries SET entry_json=?,entry_sha256=?,proof_json=? WHERE id=?',
                (canonical(forged), _sha(canonical(forged)), canonical(forged_proof), entry['id']))
            self.office.db.execute('UPDATE business_accounting_capacity_requests SET request_json=?,request_hash=? WHERE entry_id=?',
                (canonical(command), self.capacity._request_hash(event['id'], command), entry['id']))
        # The old unbounded reader accepts this otherwise fully consistent forgery.
        with patch.object(ReusableDocumentComponents, '_validate_gate_snapshot', old_unbounded_check):
            self.assertEqual(len(self.capacity._ledger({})['rows']), 2)
        self.problem(409, self.capacity.history, self.owner, event['id'])
        self.problem(409, self.capacity.confirm, self.owner, event['id'], command)

    def test_rehashed_r2_prior_cents_are_reconstructed_from_actual_claims(self):
        invoice, middle, unused, unused_old, unused_receipt, reused, unused_command = self.mixed_seed()
        unused, event = self.cash_event(invoice, '10.00', kind='refund'); group = middle['lines'][0]['group_id']
        body = self.versioned_command(event, [('c2', reused['id'], group, '10.00')]); entry = self.r2.confirm(self.owner, event['id'], body)
        forged = deepcopy(entry); line = forged['lines'][0]
        for key in ('gross_before', 'gross_after', 'net_before', 'net_after', 'remaining_gross', 'remaining_net'):
            cents = int(line[key].replace('.', ''))+(-1 if key.startswith('remaining') else 1)
            line[key] = f'{cents//100}.{cents%100:02d}'
        forged['preview_hash'] = _sha(canonical(self.r2._preview_from_entry(forged)))
        command = dict(body, preview_hash=forged['preview_hash'])
        with self.office.db:
            for table in protected_tables():
                self.office.db.execute('DROP TRIGGER '+table+'_update_guard')
            self.office.db.execute('UPDATE business_accounting_refunds_v2_entries SET entry_json=?,entry_sha256=? WHERE id=?',
                (canonical(forged), _sha(canonical(forged)), entry['id']))
            fields = ('gross_before', 'gross_after', 'net_before', 'net_after', 'remaining_gross', 'remaining_net')
            self.office.db.execute('UPDATE business_accounting_refunds_v2_lines SET '+','.join(key+'=?' for key in fields)+' WHERE entry_id=?',
                tuple(line[key] for key in fields)+(entry['id'],))
            self.office.db.execute('UPDATE business_accounting_refunds_v2_requests SET request_json=?,request_hash=? WHERE entry_id=?',
                (canonical(command), self.r2._request_hash(event['id'], command), entry['id']))
        self.problem(409, self.r2.history, self.owner, event['id'])
        self.problem(409, self.r2.confirm, self.owner, event['id'], command)
        with self.assertRaises(ValueError):
            validate_integrity(self.office)

    def test_r2_cannot_claim_zero_c2_head_when_its_required_handoff_already_exists(self):
        invoice, middle, unused, unused_old, unused_receipt, reused, unused_command = self.mixed_seed()
        unused, event = self.cash_event(invoice, '5.00', kind='refund'); group = middle['lines'][0]['group_id']
        entry = self.r2.confirm(self.owner, event['id'], self.versioned_command(event, [('c2', reused['id'], group, '5.00')]))
        proof = json.loads(self.office.db.execute('SELECT proof_json FROM business_accounting_refunds_v2_entries WHERE id=?', (entry['id'],)).fetchone()[0])
        proof['c2_sequence'] = 0
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_accounting_refunds_v2_entries_update_guard')
            self.office.db.execute('UPDATE business_accounting_refunds_v2_entries SET proof_json=? WHERE id=?', (canonical(proof), entry['id']))
        self.problem(409, self.r2.history, self.owner, event['id'])

    def test_new_refund_timestamp_requires_canonical_utc_even_when_hashes_match(self):
        invoice, middle, unused, unused_old, unused_receipt, reused, unused_command = self.mixed_seed()
        unused, event = self.cash_event(invoice, '5.00', kind='refund'); group = middle['lines'][0]['group_id']
        entry = self.r2.confirm(self.owner, event['id'], self.versioned_command(event, [('c2', reused['id'], group, '5.00')]))
        original = dict(self.office.db.execute('SELECT * FROM business_accounting_refunds_v2_entries WHERE id=?', (entry['id'],)).fetchone())
        for stamp in ('2026-11-02T13:00:00+01:00', '2026-11-02T12:00:00', '2026-11-02', 'invalid'):
            forged = dict(entry, created_at=stamp)
            row = dict(original, created_at=stamp, entry_json=canonical(forged), entry_sha256=_sha(canonical(forged)))
            with self.subTest(stamp=stamp):
                self.problem(409, self.r2._basic, row)

    def test_versioned_branch_foreign_keys_guards_and_absent_module_fail_closed(self):
        import business_accounting_refunds_v2 as module
        invoice, middle, unused, unused_old, unused_receipt, reused, unused_command = self.mixed_seed()
        unused, event = self.cash_event(invoice, '5.00', kind='refund'); group = middle['lines'][0]['group_id']
        entry = self.r2.confirm(self.owner, event['id'], self.versioned_command(event, [('c2', reused['id'], group, '5.00')]))
        unused, receipt = self.cash_event(invoice, '5.00')
        self.capacity.confirm(self.owner, receipt['id'], self.capacity_command(receipt))
        original = dict(self.office.db.execute('SELECT * FROM business_accounting_refunds_v2_lines WHERE entry_id=?', (entry['id'],)).fetchone())
        for updates in (dict(origin_entry_id='9'*32, origin_c2_entry_id=None),
                        dict(origin_entry_id='9'*32, origin_c2_entry_id='9'*32),
                        dict(origin_entry_id='9'*32, origin_c1_entry_id=middle['id'], origin_c2_entry_id='9'*32)):
            row = dict(original, **updates)
            with self.subTest(updates=updates), self.assertRaises(sqlite3.IntegrityError), self.office.db:
                self.office.db.execute('INSERT INTO business_accounting_refunds_v2_lines('+','.join(row)+') VALUES('+','.join('?' for unused in row)+')', tuple(row.values()))
        before = self.snapshot(protected_tables())
        for table in protected_tables():
            row = dict(self.office.db.execute('SELECT * FROM '+table+' LIMIT 1').fetchone()); column = next(iter(row))
            with self.assertRaises(sqlite3.IntegrityError), self.office.db:
                self.office.db.execute('UPDATE '+table+' SET '+column+'='+column)
            with self.assertRaises(sqlite3.IntegrityError), self.office.db:
                self.office.db.execute('DELETE FROM '+table)
            with self.assertRaises(sqlite3.IntegrityError), self.office.db:
                self.office.db.execute('INSERT OR REPLACE INTO '+table+'('+','.join(row)+') VALUES('+','.join('?' for unused in row)+')', tuple(row.values()))
        self.assertEqual(before, self.snapshot(protected_tables()))
        self.assertTrue(validate_integrity(self.office))
        self.office.db.execute('PRAGMA foreign_keys=OFF')
        with self.office.db:
            for table in reversed(protected_tables()):
                self.office.db.execute('DROP TABLE '+table)
            self.office.db.execute("DELETE FROM business_schema_migrations WHERE module='business_accounting_refunds_v2'")
        self.problem(409, module.installed, self.office)
        self.problem(409, self.capacity._ledger, {})



if __name__ == '__main__':
    unittest.main()
