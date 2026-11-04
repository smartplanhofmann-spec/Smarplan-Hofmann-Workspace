"""Versioned refund/reuse cycles with genuine PostgreSQL issuance and roles.

Only the explicitly guarded disposable loopback database is reset. Invoice
archives, MFA, runtime privileges and dump/restore use production code.
"""
from contextlib import contextmanager
from decimal import Decimal
import importlib
import json
import signal
import unittest
from unittest.mock import patch
import uuid

import psycopg
from psycopg import sql

import business_schema
from business_finance import Finance
from core import Problem
from online import release, test_business_journey_pg as journey
from online import test_postgres_accounting_capacity_integration as capacity_fixture
from online import test_postgres_accounting_components_integration as components_fixture
from online import test_postgres_accounting_integration as accounting_fixture
from online.store import PostgresOffice, migrate

request = journey.request


@contextmanager
def finite_access():
    """An accidentally cyclic access traversal must fail rather than hang CI."""
    def expired(unused_signal, unused_frame):
        raise TimeoutError('Synthetic event authorization cycle did not terminate')
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, 45)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


@unittest.skipUnless(journey.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class VersionedRefundsPostgres(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module('business_accounting_refunds_v2')
        self.capacity = capacity_fixture.ComponentCapacityPostgres(methodName='runTest')
        self.addCleanup(self.capacity.doCleanups)
        self.capacity.setUp()
        self.refunds, self.components = self.capacity.refunds, self.capacity.components
        self.office, self.runtime, self.owner, self.call = (
            self.capacity.office, self.capacity.runtime, self.capacity.owner, self.capacity.call)
        self.api = self.module.VersionedRefundOrigins(self.office)

    def path(self, event):
        return '/business/accounting/refunds/v2/events/' + event['id']

    def proposal(self, event, selected, *, token='owner', document_id=None):
        path = self.path(event)
        state = self.call('GET', path, token=token).json
        portions = self.call('GET', path + '/portions', token=token).json['items']
        portion = next(row for row in portions if row['document_id'] == document_id) if document_id else portions[0]
        origins = self.call('GET', path + '/origins?portion_id=' + portion['portion_id'], token=token).json['items']
        chosen = []
        for selection in selected:
            version, entry, amount = selection[:3]
            group_id = selection[3] if len(selection) == 4 else entry['lines'][0]['group_id']
            origin = next(row for row in origins if (row['origin_version'], row['entry_id'], row['group_id']) ==
                          (version, entry['id'], group_id))
            chosen.append(dict(origin_version=version, entry_id=entry['id'], group_id=group_id,
                               lot_state_hash=origin['lot_state_hash'], amount=amount))
        body = dict(source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
            portion_id=portion['portion_id'], portion_state_hash=portion['portion_state_hash'], action=portion['action'],
            origins=chosen, reason='Synthetic expressly selected versioned refund origins')
        preview = self.call('POST', path + '/preview', body, token=token).json
        return preview, request(**body, preview_hash=preview['preview_hash'], confirmation=True)

    def confirm(self, event, selected, **kwargs):
        preview, command = self.proposal(event, selected, **kwargs)
        entry = self.call('POST', self.path(event) + '/confirm', command,
                          token=kwargs.get('token', 'owner'), status=201).json
        return entry, command

    def seed_partial(self):
        lots = self.refunds.seed_lots()
        _, event, _ = self.refunds.refund('13.22')
        returned, command = self.refunds.confirm(event, [(lots[1]['component'], '13.22')])
        _, receipt, _ = self.components.cash('13.22')
        reused, reuse_command = self.capacity.confirm(receipt)
        self.assertEqual((returned['net'], returned['tax']), ('11.11', '2.11'))
        return dict(lots=lots, refund=event, returned=returned, command=command,
                    receipt=receipt, reused=reused, reuse_command=reuse_command)

    def mixed(self):
        seed = self.seed_partial()
        _, event, _ = self.refunds.refund('26.44')
        selected = [('c1', seed['lots'][1]['component'], '13.22'), ('c2', seed['reused'], '13.22')]
        return seed, event, selected

    def frozen_sources(self):
        return {table: value for table, value in release.snapshot_fingerprint(journey.DSN).items()
                if table in accounting_fixture.SOURCE_TABLES or
                table.startswith('business_accounting_') and not table.startswith('business_accounting_refunds_v2_')}

    def counts(self):
        return {table: self.office.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]
                for table in self.module.protected_tables()}

    def cash_multi(self, kind, allocations):
        amount = format(sum(Decimal(value) for unused, value in allocations), '.2f')
        payment = self.components.payment_record(kind, amount, allocations)
        body = self.components.import_body(source=self.components.payment_source(payment['id']))
        event = self.call('POST', '/business/accounting/events/import-payment', body, status=201).json
        return payment, event, body

    def test_mixed_exact_cents_and_two_further_full_reuse_cycles_preserve_old_proofs(self):
        seed, event, selected = self.mixed()
        frozen = self.frozen_sources()
        op = Finance(self.office).open_items(self.owner)
        snapshot = release.snapshot_fingerprint(journey.DSN)
        preview, command = self.proposal(event, selected)
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), snapshot)
        self.assertEqual((preview['net'], preview['tax']), ('22.21', '4.23'))
        entry = self.call('POST', self.path(event) + '/confirm', command, status=201).json
        self.assertEqual([(line['origin_version'], line['net'], line['tax']) for line in entry['lines']],
                         [('c1', '11.10', '2.12'), ('c2', '11.11', '2.11')])
        self.assertFalse(entry['capacity_released'])
        self.assertEqual(self.frozen_sources(), frozen)
        self.assertEqual(Finance(self.office).open_items(self.owner), op)
        records = [(event, entry, command)]
        _, receipt, _ = self.components.cash('26.44')
        positive, positive_command = self.capacity.confirm(receipt)
        self.assertEqual((positive['net'], positive['tax']), ('22.21', '4.23'))
        self.assertEqual(self.counts()['business_accounting_refunds_v2_releases'], 2)
        for unused_cycle in range(2):
            _, event, _ = self.refunds.refund('26.44')
            frozen = self.frozen_sources()
            entry, command = self.confirm(event, [('c2', positive, '26.44')])
            self.assertEqual((entry['net'], entry['tax']), ('22.21', '4.23'))
            self.assertEqual(self.frozen_sources(), frozen)
            records.append((event, entry, command))
            _, receipt, _ = self.components.cash('26.44')
            positive, positive_command = self.capacity.confirm(receipt)
            self.assertEqual((positive['net'], positive['tax']), ('22.21', '4.23'))
        self.assertEqual(self.counts()['business_accounting_refunds_v2_releases'], 4)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_accounting_capacity_releases').fetchone()[0], 1)
        self.assertEqual(self.refunds.api.confirm(self.owner, seed['refund']['id'], seed['command']), seed['returned'])
        self.assertEqual(self.capacity.api.confirm(self.owner, seed['receipt']['id'], seed['reuse_command']), seed['reused'])
        for event, entry, command in records:
            self.assertEqual(self.api.confirm(self.owner, event['id'], command), entry)
        self.assertEqual(self.capacity.api.confirm(self.owner, receipt['id'], positive_command), positive)
        self.assertTrue(self.module.validate_integrity(self.office))
        business_schema.validate_integrity(self.office)

    def test_c1_cumulative_counter_continues_across_r1_r2_until_exact_original_total(self):
        seed = self.seed_partial(); middle = seed['lots'][1]['component']
        records = []
        for amount, expected in [('13.22', ('11.10', '2.12')), ('13.23', ('11.12', '2.11'))]:
            _, event, _ = self.refunds.refund(amount)
            entry, command = self.confirm(event, [('c1', middle, amount)])
            self.assertEqual((entry['net'], entry['tax']), expected)
            records.append((event, entry, command))
        self.assertEqual(sum(Decimal(value['tax']) for value in [seed['returned'], *(row[1] for row in records)]), Decimal('6.34'))
        self.assertEqual(sum(Decimal(value['net']) for value in [seed['returned'], *(row[1] for row in records)]), Decimal('33.33'))
        self.assertEqual(records[-1][1]['lines'][0]['remaining_gross'], '0.00')
        self.assertEqual(records[0][1]['lines'][0]['gross_before'], '13.22')
        self.assertEqual(records[-1][1]['lines'][0]['gross_after'], '39.67')
        for event, entry, command in records:
            self.assertEqual(self.api.confirm(self.owner, event['id'], command), entry)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_r1_r2_compete_for_one_whole_refund_and_only_one_writer_claims_it(self):
        seed = self.seed_partial(); lot = seed['lots'][0]['component']
        _, event, _ = self.refunds.refund('5.00')
        _, other_refund, _ = self.refunds.refund('1.00')
        _, other_legacy = self.refunds.proposal(other_refund, [(seed['lots'][2]['component'], '1.00')])
        _, old = self.refunds.proposal(event, [(lot, '5.00')])
        _, new = self.proposal(event, [('c1', lot, '5.00')])
        results = self.components.compete([
            lambda office: self.refunds.module.RefundOrigins(office).confirm(self.owner, event['id'], old),
            lambda office: self.module.VersionedRefundOrigins(office).confirm(self.owner, event['id'], new)])
        self.assertEqual(sorted(status for status, unused in results), [200, 409])
        self.assertEqual(self.refunds.api.history(self.owner, event['id'])['total'] + self.api.history(self.owner, event['id'])['total'], 1)
        if results[1][0] == 200:
            response = self.call('POST', self.refunds.path(event) + '/confirm', old, status=409).json
            self.assertEqual(response['request_resolution'], 'not_accepted')
            self.assertEqual(self.api.confirm(self.owner, event['id'], new), results[1][1])
        else:
            self.assertEqual(self.refunds.api.confirm(self.owner, event['id'], old), results[0][1])
            self.call('POST', self.path(event) + '/confirm', new, status=409)
            _, takeover, _ = self.refunds.refund('1.00')
            self.confirm(takeover, [('c1', lot, '1.00')])
        # A different unbound portion and untouched origin lot were both valid
        # before takeover. The invoice-wide writer boundary alone blocks them.
        response = self.call('POST', self.refunds.path(other_refund) + '/confirm', other_legacy, status=409).json
        self.assertEqual(response['request_resolution'], 'not_accepted')
        self.assertEqual(self.refunds.api.history(self.owner, other_refund['id'])['total'], 0)
        self.assertEqual(self.api.history(self.owner, other_refund['id'])['total'], 0)
        self.assertEqual(self.refunds.api.confirm(self.owner, seed['refund']['id'], seed['command']), seed['returned'])
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_two_connections_cannot_bind_same_portion_under_different_request_ids(self):
        seed, event, selected = self.mixed()
        _, body = self.proposal(event, selected)
        commands = [body, {**body, 'request_id': uuid.uuid4().hex}]
        results = self.components.compete([lambda office, command=command:
            self.module.VersionedRefundOrigins(office).confirm(self.owner, event['id'], command) for command in commands])
        self.assertEqual(sorted(status for status, unused in results), [200, 409])
        self.assertEqual(self.counts()['business_accounting_refunds_v2_handoffs'], 1)
        self.assertEqual(self.counts()['business_accounting_refunds_v2_entries'], 1)
        self.assertEqual(self.counts()['business_accounting_refunds_v2_lines'], 2)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_two_refunds_compete_for_the_last_c2_lot_rest(self):
        seed = self.seed_partial()
        events = [self.refunds.refund('13.22')[1] for unused in range(2)]
        commands = [self.proposal(event, [('c2', seed['reused'], '13.22')])[1] for event in events]
        results = self.components.compete([lambda office, event=event, command=command:
            self.module.VersionedRefundOrigins(office).confirm(self.owner, event['id'], command)
            for event, command in zip(events, commands)])
        self.assertEqual(sorted(status for status, unused in results), [200, 409])
        self.assertEqual(sum(self.api.history(self.owner, event['id'])['total'] for event in events), 1)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_competing_positive_receipts_release_mixed_r2_lines_exactly_once(self):
        seed, refund, selected = self.mixed()
        self.confirm(refund, selected)
        events = [self.components.cash('13.22')[1] for unused in range(2)]
        commands = [self.capacity.proposal(event)[1] for event in events]
        results = self.components.compete([lambda office, event=event, command=command:
            self.capacity.module.ReusableDocumentComponents(office).confirm(self.owner, event['id'], command)
            for event, command in zip(events, commands)])
        self.assertEqual(sorted(status for status, unused in results), [200, 409])
        self.assertEqual(self.counts()['business_accounting_refunds_v2_releases'], 2)
        loser = next(index for index, (status, unused) in enumerate(results) if status == 409)
        other, unused = self.capacity.confirm(events[loser])
        self.assertEqual(other['capacity_changes'], [])
        entries = [value for status, value in results if status == 200] + [other]
        self.assertEqual(sum(Decimal(row['net']) for row in entries), Decimal('22.21'))
        self.assertEqual(sum(Decimal(row['tax']) for row in entries), Decimal('4.23'))
        self.assertEqual(len({row['lines'][0]['segment_id'] for row in entries}), 1)
        self.assertEqual(self.counts()['business_accounting_refunds_v2_releases'], 2)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_mixed_handoff_lines_request_and_audit_failures_roll_back_the_whole_command(self):
        seed, event, selected = self.mixed()
        _, command = self.proposal(event, selected)
        for suffix in ('handoffs', 'lines', 'requests'):
            table = 'business_accounting_refunds_v2_' + suffix
            with self.subTest(table=table):
                with psycopg.connect(journey.DSN) as admin:
                    admin.execute('SET LOCAL ROLE "smartplan-migrator"')
                    admin.execute("CREATE FUNCTION synthetic_r2_failure() RETURNS trigger LANGUAGE plpgsql AS $$ "
                        "BEGIN RAISE EXCEPTION 'synthetic mixed refund failure'; END; $$")
                    condition = sql.SQL(" WHEN (NEW.origin_version='c2')") if suffix == 'lines' else sql.SQL('')
                    admin.execute(sql.SQL('CREATE TRIGGER synthetic_r2_failure BEFORE INSERT ON {} FOR EACH ROW{} '
                        'EXECUTE FUNCTION synthetic_r2_failure()').format(sql.Identifier(table), condition))
                before = release.snapshot_fingerprint(journey.DSN)
                try:
                    with self.assertRaisesRegex(psycopg.Error, 'synthetic mixed refund failure'):
                        self.api.confirm(self.owner, event['id'], command)
                    self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
                    self.assertEqual(set(self.counts().values()), {0})
                finally:
                    with psycopg.connect(journey.DSN) as admin:
                        admin.execute('SET LOCAL ROLE "smartplan-migrator"')
                        admin.execute(sql.SQL('DROP TRIGGER synthetic_r2_failure ON {}').format(sql.Identifier(table)))
                        admin.execute('DROP FUNCTION synthetic_r2_failure()')
        before = release.snapshot_fingerprint(journey.DSN)
        with patch.object(self.office, 'audit', side_effect=RuntimeError('synthetic R2 audit failure')):
            with self.assertRaisesRegex(RuntimeError, 'synthetic R2 audit failure'):
                self.api.confirm(self.owner, event['id'], command)
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
        entry = self.api.confirm(self.owner, event['id'], command)
        self.assertEqual(len(entry['lines']), 2)
        self.assertEqual(self.counts()['business_accounting_refunds_v2_entries'], 1)

    def test_positive_sql_failure_rolls_back_new_r2_releaseclaims_and_retry_releases_once(self):
        seed, refund, selected = self.mixed()
        self.confirm(refund, selected)
        _, receipt, _ = self.components.cash('26.44')
        _, command = self.capacity.proposal(receipt)
        table = 'business_accounting_capacity_requests'
        with psycopg.connect(journey.DSN) as admin:
            admin.execute('SET LOCAL ROLE "smartplan-migrator"')
            admin.execute("CREATE FUNCTION synthetic_r2_release_failure() RETURNS trigger LANGUAGE plpgsql AS $$ "
                "BEGIN RAISE EXCEPTION 'synthetic R2 release failure'; END; $$")
            admin.execute(sql.SQL('CREATE TRIGGER synthetic_r2_release_failure BEFORE INSERT ON {} '
                'FOR EACH ROW EXECUTE FUNCTION synthetic_r2_release_failure()').format(sql.Identifier(table)))
        before = release.snapshot_fingerprint(journey.DSN)
        try:
            with self.assertRaisesRegex(psycopg.Error, 'synthetic R2 release failure'):
                self.capacity.api.confirm(self.owner, receipt['id'], command)
            self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
            self.assertEqual(self.counts()['business_accounting_refunds_v2_releases'], 0)
        finally:
            with psycopg.connect(journey.DSN) as admin:
                admin.execute('SET LOCAL ROLE "smartplan-migrator"')
                admin.execute(sql.SQL('DROP TRIGGER synthetic_r2_release_failure ON {}').format(sql.Identifier(table)))
                admin.execute('DROP FUNCTION synthetic_r2_release_failure()')
        entry = self.capacity.api.confirm(self.owner, receipt['id'], command)
        self.assertEqual(self.capacity.api.confirm(self.owner, receipt['id'], command), entry)
        self.assertEqual(self.counts()['business_accounting_refunds_v2_releases'], 2)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_real_nullable_branch_fks_immutable_rows_and_restricted_runtime_roles(self):
        seed, refund, selected = self.mixed()
        entry, unused = self.confirm(refund, selected)
        _, receipt, _ = self.components.cash('26.44')
        self.capacity.confirm(receipt)
        frozen = release.snapshot_fingerprint(journey.DSN)
        rows = self.office.db.execute('SELECT * FROM business_accounting_refunds_v2_lines WHERE entry_id=? ORDER BY origin_version', (entry['id'],)).fetchall()
        for row in rows:
            self.assertEqual(row['origin_' + row['origin_version'] + '_entry_id'], row['origin_entry_id'])
            self.assertIsNone(row['origin_c2_entry_id'] if row['origin_version'] == 'c1' else row['origin_c1_entry_id'])
        sample = dict(rows[0]); columns = list(sample)
        changes = [dict(origin_entry_id=uuid.uuid4().hex, origin_c1_entry_id=None),
                   dict(origin_entry_id=uuid.uuid4().hex, origin_c1_entry_id=uuid.uuid4().hex),
                   dict(group_id='f' * 64), dict(origin_version='c2', origin_c2_entry_id=seed['reused']['id']),
                   dict(origin_version='c2', origin_entry_id=uuid.uuid4().hex,
                        origin_c1_entry_id=None, origin_c2_entry_id=None),
                   dict(origin_version='c2', origin_entry_id=seed['reused']['id'], group_id='f' * 64,
                        origin_c1_entry_id=None, origin_c2_entry_id=seed['reused']['id'])]
        with psycopg.connect(self.runtime) as runtime:
            for change in changes:
                with self.subTest(change=sorted(change)), self.assertRaises(psycopg.IntegrityError):
                    with runtime.transaction():
                        value = sample | change
                        runtime.execute(sql.SQL('INSERT INTO business_accounting_refunds_v2_lines ({}) VALUES ({})').format(
                            sql.SQL(',').join(map(sql.Identifier, columns)), sql.SQL(',').join(sql.Placeholder() for unused in columns)),
                            [value[name] for name in columns])
        release_row = dict(self.office.db.execute('SELECT * FROM business_accounting_refunds_v2_releases '
            "WHERE origin_version='c1'").fetchone())
        release_columns = list(release_row)
        for change in (dict(origin_version='c2'), dict(group_id='f' * 64),
                       dict(refund_entry_id=uuid.uuid4().hex),
                       dict(origin_entry_id=uuid.uuid4().hex, segment_id=uuid.uuid4().hex)):
            with self.subTest(release_change=sorted(change)), psycopg.connect(self.runtime) as runtime:
                with self.assertRaises(psycopg.errors.ForeignKeyViolation):
                    with runtime.transaction():
                        value = release_row | change
                        runtime.execute(sql.SQL('INSERT INTO business_accounting_refunds_v2_releases ({}) VALUES ({})').format(
                            sql.SQL(',').join(map(sql.Identifier, release_columns)),
                            sql.SQL(',').join(sql.Placeholder() for unused in release_columns)),
                            [value[name] for name in release_columns])
        for table in self.module.protected_tables():
            column = next(iter(self.office.db.execute('SELECT * FROM ' + table + ' LIMIT 1').fetchone().keys()))
            statements = [sql.SQL('UPDATE {} SET {}={}').format(sql.Identifier(table), sql.Identifier(column), sql.Identifier(column)),
                          sql.SQL('DELETE FROM {}').format(sql.Identifier(table)), sql.SQL('TRUNCATE {}').format(sql.Identifier(table))]
            with psycopg.connect(self.runtime) as runtime:
                for statement in statements:
                    with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                        with runtime.transaction(): runtime.execute(statement)
            with psycopg.connect(journey.DSN) as admin:
                for statement in statements[:2]:
                    with self.assertRaises(psycopg.Error):
                        with admin.transaction():
                            admin.execute('SET LOCAL ROLE "smartplan-migrator"'); admin.execute(statement)
        with psycopg.connect(self.runtime) as runtime:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with runtime.transaction(): runtime.execute('CREATE TABLE synthetic_forbidden_r2_ddl(id TEXT)')
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), frozen)
        self.assertTrue(business_schema.require_runtime_security(self.office))

    def test_unknown_finance_refund_blocks_reuse_but_not_its_own_r2_clarification(self):
        seed = self.seed_partial()
        _, event, _ = self.refunds.refund('13.22')
        unknown = self.components.payment_record('refund', '1.00', [(self.components.invoice['id'], '1.00')])
        self.confirm(event, [('c2', seed['reused'], '13.22')])
        _, receipt, _ = self.components.cash('13.22')
        portion = self.capacity.api.portions(self.owner, receipt['id'])['items'][0]
        self.assertEqual(portion['pending_blocked_reason'], 'refund_origin_unresolved')
        self.assertFalse(portion['eligible'])
        body = self.components.import_body(source=self.components.payment_source(unknown['id']))
        unknown_event = self.call('POST', '/business/accounting/events/import-payment', body, status=201).json
        self.confirm(unknown_event, [('c1', seed['lots'][0]['component'], '1.00')])
        positive, unused = self.capacity.confirm(receipt)
        self.assertEqual(positive['amount'], '13.22')
        self.assertEqual(self.counts()['business_accounting_refunds_v2_releases'], 2)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_unused_prior_group_scope_is_required_through_a_c2_origin_and_r2_history(self):
        invoice = self.components.issue(self.components.project, positions=[
            dict(description='Synthetic standard group', quantity='1', unit='HUR', unit_price_net='100.00', tax_rate='19', kind='labor'),
            dict(description='Synthetic reduced group', quantity='1', unit='HUR', unit_price_net='50.00', tax_rate='7', kind='labor')])
        _, origin_a, _ = self.components.cash('119.00', document=invoice['id'])
        portion = self.components.api.portions(self.owner, origin_a['id'])['items'][0]
        groups = {group['rate']: group['group_id'] for group in portion['groups']}
        lot_a, unused = self.components.confirm(origin_a, groups=[dict(group_id=groups['19'], amount='119.00')])
        payment_b, origin_b, _ = self.components.cash('60.00', assigned='53.50', document=invoice['id'])
        lot_b, unused = self.components.confirm(origin_b, groups=[dict(group_id=groups['7'], amount='53.50')])
        for lot, rate in [(lot_a, '19'), (lot_b, '7')]:
            _, refund, _ = self.refunds.refund('10.00', document=invoice['id'])
            self.capacity.bind_refund(refund, [(lot, groups[rate], '10.00')])
        user, token = self.components.bookkeeper()
        _, first, _ = self.components.cash('5.00', document=invoice['id'])
        self.capacity.confirm(first, groups=[dict(group_id=groups['19'], amount='5.00')], token=token)
        _, second, _ = self.components.cash('5.00', document=invoice['id'])
        positive, unused = self.capacity.confirm(second, groups=[dict(group_id=groups['19'], amount='5.00')], token=token)
        self.assertEqual(positive['capacity_changes'], [])
        _, refund, _ = self.refunds.refund('5.00', document=invoice['id'])
        entry, command = self.confirm(refund, [('c2', positive, '5.00')], token=token)
        other = self.components.other_project(); other_invoice = self.components.issue(other)
        self.components.assign(payment_b, document=other_invoice['id'], amount='6.50')
        for suffix in ('', '/portions', '/history'):
            self.call('GET', self.path(refund) + suffix, token=token, status=404)
        self.call('POST', self.path(refund) + '/confirm', command, token=token, status=404)
        self.call('POST', '/assignments', {'project_id': other, 'user_id': user})
        self.assertEqual(self.call('POST', self.path(refund) + '/confirm', command, token=token, status=201).json, entry)

    def test_valid_event_authorization_cycle_terminates_and_preserves_exact_replays(self):
        invoice_a = self.components.invoice; invoice_b = self.components.issue(self.components.project)
        positives = {}
        for invoice, replacement in [(invoice_a, '10.00'), (invoice_b, '5.00')]:
            _, origin, _ = self.components.cash('119.00', document=invoice['id'])
            lot, unused = self.components.confirm(origin)
            _, refund, _ = self.refunds.refund('10.00', document=invoice['id'])
            self.capacity.bind_refund(refund, [(lot, lot['lines'][0]['group_id'], '10.00')])
            _, cash, _ = self.components.cash(replacement, document=invoice['id'])
            positives[invoice['id']] = self.capacity.confirm(cash)[0]
        _, refund, _ = self.cash_multi('refund', [(invoice_a['id'], '5.00'), (invoice_b['id'], '5.00')])
        first, first_command = self.confirm(refund, [('c2', positives[invoice_a['id']], '5.00')], document_id=invoice_a['id'])
        _, receipt, _ = self.cash_multi('receipt', [(invoice_a['id'], '5.00'), (invoice_b['id'], '5.00')])
        parts = {row['document_id']: row for row in self.capacity.api.portions(self.owner, receipt['id'])['items']}
        self.capacity.confirm(receipt, portion_id=parts[invoice_a['id']]['portion_id'])
        positive_b, unused = self.capacity.confirm(receipt, portion_id=parts[invoice_b['id']]['portion_id'])
        with finite_access():
            second, second_command = self.confirm(refund, [('c2', positive_b, '5.00')], document_id=invoice_b['id'])
            self.assertEqual(self.api.history(self.owner, refund['id'])['total'], 2)
            self.assertEqual(self.capacity.api.history(self.owner, receipt['id'])['total'], 2)
            self.assertEqual(self.api.confirm(self.owner, refund['id'], first_command), first)
            self.assertEqual(self.api.confirm(self.owner, refund['id'], second_command), second)
            self.assertTrue(self.module.validate_integrity(self.office))
            business_schema.validate_integrity(self.office)

    def test_real_dump_restore_requires_current_horizon_and_binds_r2_releaseclaims(self):
        seed, refund, selected = self.mixed()
        entry, command = self.confirm(refund, selected)
        _, receipt, _ = self.components.cash('26.44')
        positive, positive_command = self.capacity.confirm(receipt)
        horizon = business_schema.financial_accounting_horizon(self.office)
        self.assertGreaterEqual(horizon['schema_version'], 6)
        self.assertEqual(horizon['refunds_v2']['table_counts'], self.counts())
        self.assertEqual(horizon['refunds_v2']['table_counts']['business_accounting_refunds_v2_releases'], 2)
        before = release.snapshot_fingerprint(journey.DSN); self.office.db.close()
        for unused in range(2):
            migrate(journey.DSN, owner_role='smartplan-migrator', compatibility_mode='business', require_business_modules=True)
            self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
        with components_fixture.disposable_restore(self.runtime) as (target, runtime, report):
            restored = PostgresOffice(runtime)
            try:
                api = self.module.VersionedRefundOrigins(restored)
                self.assertEqual(api.history(self.owner, refund['id'])['items'], [entry])
                self.assertEqual(business_schema.financial_accounting_horizon(restored), horizon)
                with self.assertRaises(Problem) as blocked: api.confirm(self.owner, refund['id'], command)
                self.assertEqual(blocked.exception.status, 409)
                self.assertIsNone(blocked.exception.request_resolution)
            finally: restored.db.close()
            frozen = release.snapshot_fingerprint(target)
            for table, value in before.items():
                if table in accounting_fixture.SOURCE_TABLES or table.startswith('business_accounting_'):
                    self.assertEqual(frozen[table], value, table)
            operator = PostgresOffice(target)
            try:
                evidence = components_fixture.evidence_for(operator, report)
                self.assertEqual(evidence['schema'], horizon['schema_version'] + 1)
                old = {**evidence, 'schema': 6, 'accounting_horizon': dict(schema_version=5,
                    **{key: horizon[key] for key in ('prejournal', 'allocations', 'components', 'refunds', 'capacity')})}
                wrong = {**evidence, 'accounting_horizon': {**horizon,
                    'refunds_v2': {**horizon['refunds_v2'], 'sha256': '0' * 64}}}
                for invalid in (old, wrong):
                    with self.assertRaises((Problem, ValueError)): components_fixture.approve(operator, invalid)
                    self.assertEqual(release.snapshot_fingerprint(target), frozen)
                approved = components_fixture.approve(operator, evidence)
                self.assertEqual(components_fixture.approve(operator, evidence), approved)
            finally: operator.db.close()
            restored = PostgresOffice(runtime)
            try:
                self.assertEqual(self.module.VersionedRefundOrigins(restored).confirm(self.owner, refund['id'], command), entry)
                self.assertEqual(self.capacity.module.ReusableDocumentComponents(restored).confirm(self.owner, receipt['id'], positive_command), positive)
                business_schema.validate_integrity(restored)
            finally: restored.db.close()
            self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)


@unittest.skipUnless(journey.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class RefundsV2MigrationPostgres(unittest.TestCase):
    def test_c2_v1_migration_preserves_bytes_and_schema6_receipt_cannot_release_new_restore(self):
        full = business_schema.registry()
        prior = tuple(spec for spec in full if spec.name not in ('business_accounting_refunds_v2', 'business_accounting_profile', 'business_accounting_euer', 'business_payroll_cash', 'business_bank_reconciliation', 'business_travel_allowances', 'business_accounting_openings', 'business_accounting_asset_openings', 'business_accounting_open_items','business_accounting_year_openings'))
        fixture = capacity_fixture.ComponentCapacityPostgres(methodName='runTest'); self.addCleanup(fixture.doCleanups)
        with patch.object(business_schema, 'registry', return_value=prior), \
                patch.object(business_schema, 'MODULE_NAMES', tuple(spec.name for spec in prior)):
            fixture.setUp()
            unused, unused_refund, unused_return, unused_command, receipt, unused_import = fixture.ready_middle_lot()
            positive, positive_command = fixture.confirm(receipt)
            _, refund, _ = fixture.refunds.refund('13.22')
            old_row = dict(fixture.office.db.execute('SELECT * FROM business_accounting_capacity_entries WHERE id=?', (positive['id'],)).fetchone())
            self.assertEqual(json.loads(old_row['proof_json'])['schema_version'], 1)
            horizon = business_schema.financial_accounting_horizon(fixture.office)
            self.assertEqual(horizon['schema_version'], 5)
            before = release.snapshot_fingerprint(journey.DSN); fixture.office.db.close()
            with components_fixture.disposable_restore(fixture.runtime) as (target, runtime, report):
                operator = PostgresOffice(target)
                try:
                    evidence = components_fixture.evidence_for(operator, report)
                    self.assertEqual(evidence['schema'], 6)
                    approved = components_fixture.approve(operator, evidence)
                finally: operator.db.close()
                old_target = release.snapshot_fingerprint(target)
                with patch.object(business_schema, 'registry', return_value=full), \
                        patch.object(business_schema, 'MODULE_NAMES', tuple(spec.name for spec in full)):
                    migrate(target, owner_role='smartplan-migrator', compatibility_mode='business', require_business_modules=True)
                    upgraded = release.snapshot_fingerprint(target)
                    migrate(target, owner_role='smartplan-migrator', compatibility_mode='business', require_business_modules=True)
                    self.assertEqual(release.snapshot_fingerprint(target), upgraded)
                    for table, value in old_target.items():
                        if table != 'business_schema_migrations': self.assertEqual(upgraded[table], value, table)
                    operator = PostgresOffice(target)
                    try:
                        self.assertGreaterEqual(business_schema.financial_accounting_horizon(operator)['schema_version'], 6)
                        self.assertEqual(components_fixture.approve(operator, evidence), approved)
                    finally: operator.db.close()
                    self.assertEqual(release.snapshot_fingerprint(target), upgraded)
        migrate(journey.DSN, owner_role='smartplan-migrator', compatibility_mode='business', require_business_modules=True)
        after = release.snapshot_fingerprint(journey.DSN)
        migrate(journey.DSN, owner_role='smartplan-migrator', compatibility_mode='business', require_business_modules=True)
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), after)
        for table, value in before.items():
            if table != 'business_schema_migrations': self.assertEqual(after[table], value, table)
        release.secure_database(journey.DSN, test_mode=True)
        office = PostgresOffice(fixture.runtime)
        try:
            current = business_schema.financial_accounting_horizon(office)
            self.assertEqual(dict(schema_version=5,
                **{key: current[key] for key in ('prejournal', 'allocations', 'components', 'refunds', 'capacity')}), horizon)
            self.assertEqual(dict(office.db.execute('SELECT * FROM business_accounting_capacity_entries WHERE id=?', (positive['id'],)).fetchone()), old_row)
            self.assertEqual(fixture.module.ReusableDocumentComponents(office).confirm(fixture.owner, receipt['id'], positive_command), positive)
            api = importlib.import_module('business_accounting_refunds_v2').VersionedRefundOrigins(office)
            portion = api.portions(fixture.owner, refund['id'])['items'][0]
            self.assertEqual(portion['action'], 'takeover_and_bind')
            origins = api.origins(fixture.owner, refund['id'], portion['portion_id'])['items']
            self.assertTrue(any(row['origin_version'] == 'c2' and row['entry_id'] == positive['id'] for row in origins))
            business_schema.validate_integrity(office)
        finally: office.db.close()
        with components_fixture.disposable_restore(fixture.runtime) as (target, runtime, report):
            self.assertNotEqual(report['restore_id'], evidence['restore_id'])
            operator = PostgresOffice(target)
            try:
                frozen = release.snapshot_fingerprint(target)
                for invalid in (evidence, {**evidence, 'restore_id': report['restore_id']}):
                    with self.assertRaises((Problem, ValueError)): components_fixture.approve(operator, invalid)
                    self.assertEqual(release.snapshot_fingerprint(target), frozen)
                latest = components_fixture.evidence_for(operator, report)
                self.assertEqual(latest['schema'], business_schema.financial_accounting_horizon(operator)['schema_version'] + 1)
                components_fixture.approve(operator, latest)
            finally: operator.db.close()
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), after)


if __name__ == '__main__':
    unittest.main()
