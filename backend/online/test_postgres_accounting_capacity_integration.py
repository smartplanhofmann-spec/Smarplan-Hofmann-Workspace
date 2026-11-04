"""Exact reusable component cents on real, guarded disposable PostgreSQL.

Production invoice issuance, normal MFA, restricted runtime roles and genuine
dump/restore remain in use. No provider, bank or non-test database is touched.
"""
from decimal import Decimal
import importlib
import json
import unittest
from unittest.mock import patch
import uuid

import psycopg
from psycopg import sql

import business_schema
from business_finance import Finance
from business_organization import Organization
from core import Problem
from online import release, test_business_journey_pg as journey
from online import test_postgres_accounting_components_integration as components_fixture
from online import test_postgres_accounting_refunds_integration as refunds_fixture
from online import test_postgres_accounting_integration as accounting_fixture
from online.store import PostgresOffice, migrate


request = journey.request


@unittest.skipUnless(journey.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class ComponentCapacityPostgres(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module('business_accounting_capacity')
        self.refunds = refunds_fixture.RefundOriginsPostgres(methodName='runTest')
        self.addCleanup(self.refunds.doCleanups)
        self.refunds.setUp()
        self.components = self.refunds.fixture
        self.office = self.refunds.office
        self.runtime = self.refunds.runtime
        self.owner = self.refunds.owner
        self.call = self.refunds.call
        self.api = self.module.ReusableDocumentComponents(self.office)

    def path(self, event):
        return '/business/accounting/components/v2/events/' + event['id']

    def proposal(self, event, *, groups=None, token='owner', portion_id=None):
        path = self.path(event)
        state = self.call('GET', path, token=token).json
        portions = self.call('GET', path + '/portions', token=token).json['items']
        portion = next(row for row in portions if row['portion_id'] == portion_id) if portion_id else portions[0]
        if groups is None:
            self.assertEqual(len(portion['groups']), 1)
            groups = [dict(group_id=portion['groups'][0]['group_id'], amount=portion['amount'])]
        body = dict(source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
            portion_id=portion['portion_id'], portion_state_hash=portion['portion_state_hash'],
            action=portion['action'], groups=groups, reason='Synthetic explicit reuse of exact documentary cents')
        preview = self.call('POST', path + '/preview', body, token=token).json
        return preview, request(**body, preview_hash=preview['preview_hash'], confirmation=True)

    def confirm(self, event, **kwargs):
        preview, command = self.proposal(event, **kwargs)
        entry = self.call('POST', self.path(event) + '/confirm', command,
                          token=kwargs.get('token', 'owner'), status=201).json
        return entry, command

    def bind_refund(self, event, selected):
        """Select real R1 origins, including multiple groups of one original lot."""
        path = self.refunds.path(event)
        state = self.call('GET', path).json
        portion = self.call('GET', path + '/portions').json['items'][0]
        origins = self.call('GET', path + '/origins?portion_id=' + portion['portion_id']).json['items']
        chosen = []
        for entry, group_id, amount in selected:
            origin = next(row for row in origins if row['entry_id'] == entry['id'] and row['group_id'] == group_id)
            chosen.append(dict(entry_id=origin['entry_id'], group_id=origin['group_id'],
                               lot_state_hash=origin['lot_state_hash'], amount=amount))
        body = dict(source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
            portion_id=portion['portion_id'], portion_state_hash=portion['portion_state_hash'],
            origins=chosen, reason='Synthetic exact selected original component cents')
        preview = self.call('POST', path + '/preview', body).json
        command = request(**body, preview_hash=preview['preview_hash'], confirmation=True)
        return self.call('POST', path + '/confirm', command, status=201).json, command

    def old_fingerprints(self):
        return {table: value for table, value in release.snapshot_fingerprint(journey.DSN).items()
                if table in accounting_fixture.SOURCE_TABLES or
                table.startswith('business_accounting_') and not table.startswith('business_accounting_capacity_')}

    def counts(self):
        return {name: self.office.db.execute('SELECT COUNT(*) FROM ' + name).fetchone()[0]
                for name in self.module.protected_tables()}

    def set_finance_enabled(self, enabled):
        api = Organization(self.office)
        value = api.get(self.owner)
        modules = {name: dict(visible=item['visibility_override'],
                             enabled=enabled if name == 'finance' else item['enabled'])
                   for name, item in value['modules'].items()}
        api.save(self.owner, request(revision=value['revision'], needs=value['needs'], modules=modules))

    def ready_middle_lot(self):
        lots = self.refunds.seed_lots()
        _, refund, _ = self.refunds.refund('39.67')
        returned, return_command = self.refunds.confirm(refund, [(lots[1]['component'], '39.67')])
        _, event, import_command = self.components.cash('39.67')
        return lots, refund, returned, return_command, event, import_command

    def test_exact_middle_lot_reuse_preserves_every_old_financial_byte_and_replay(self):
        lots, refund, returned, return_command, event, import_command = self.ready_middle_lot()
        frozen = self.old_fingerprints()
        op = Finance(self.office).open_items(self.owner)
        old_horizon = business_schema.financial_accounting_horizon(self.office)
        snapshot = release.snapshot_fingerprint(journey.DSN)
        preview, command = self.proposal(event)
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), snapshot)
        self.assertEqual((preview['amount'], preview['net'], preview['tax']), ('39.67', '33.33', '6.34'))
        self.assertEqual(command['action'], 'takeover_and_document')
        entry = self.call('POST', self.path(event) + '/confirm', command, status=201).json
        self.assertEqual(self.call('POST', self.path(event) + '/confirm', command, status=201).json, entry)
        self.call('POST', self.path(event) + '/confirm', {**command, 'request_id': uuid.uuid4().hex}, status=409)
        self.call('POST', self.path(event) + '/confirm', {**command, 'reason': 'Changed request'}, status=409)
        self.assertEqual(set(self.counts().values()), {1})
        self.assertEqual(self.old_fingerprints(), frozen)
        self.assertEqual(Finance(self.office).open_items(self.owner), op)
        after = business_schema.financial_accounting_horizon(self.office)
        for key in ('prejournal', 'allocations', 'components', 'refunds'):
            self.assertEqual(after[key], old_horizon[key], key)
        self.assertNotEqual(after['capacity'], old_horizon['capacity'])
        self.assertEqual(self.refunds.api.confirm(self.owner, refund['id'], return_command), returned)
        for lot in lots:
            self.assertEqual(self.components.api.confirm(self.owner, lot['event']['id'], lot['command']), lot['component'])
        self.assertEqual(self.components.accounting.Accounting(self.office).import_payment(self.owner, import_command), event)
        reopened = PostgresOffice(self.runtime)
        try:
            self.assertEqual(self.module.ReusableDocumentComponents(reopened).confirm(self.owner, event['id'], command), entry)
            self.assertTrue(self.module.validate_integrity(reopened))
            business_schema.validate_integrity(reopened)
        finally:
            reopened.db.close()

    def test_two_partial_returns_use_exact_successor_remainder_without_losing_a_cent(self):
        middle = self.refunds.seed_lots()[1]['component']
        _, refund_one, _ = self.refunds.refund('20.00')
        self.refunds.confirm(refund_one, [(middle, '20.00')])
        _, first, _ = self.components.cash('10.00')
        first_entry, first_command = self.confirm(first)
        self.assertEqual((first_entry['net'], first_entry['tax']), ('8.40', '1.60'))
        _, refund_two, _ = self.refunds.refund('19.67')
        self.refunds.confirm(refund_two, [(middle, '19.67')])
        _, second, _ = self.components.cash('29.67')
        before = self.old_fingerprints()
        second_entry, _ = self.confirm(second)
        self.assertEqual((second_entry['net'], second_entry['tax']), ('24.93', '4.74'))
        self.assertEqual((sum(Decimal(row['net']) for row in (first_entry, second_entry)),
                          sum(Decimal(row['tax']) for row in (first_entry, second_entry))),
                         (Decimal('33.33'), Decimal('6.34')))
        self.assertNotEqual(first_entry['lines'][0]['segment_id'], second_entry['lines'][0]['segment_id'])
        self.assertEqual(self.counts()['business_accounting_capacity_segments'], 2)
        self.assertEqual(self.counts()['business_accounting_capacity_releases'], 2)
        self.assertEqual(second_entry['lines'][0]['remaining_gross'], '0.00')
        self.assertEqual(self.old_fingerprints(), before)
        self.assertEqual(self.api.confirm(self.owner, first['id'], first_command), first_entry)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_two_connections_cannot_consume_the_same_whole_portion_twice(self):
        _, _, _, _, event, _ = self.ready_middle_lot()
        _, command = self.proposal(event)
        bodies = [command, {**command, 'request_id': uuid.uuid4().hex}]
        results = self.components.compete([lambda office, body=body:
            self.module.ReusableDocumentComponents(office).confirm(self.owner, event['id'], body) for body in bodies])
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        self.assertEqual(self.api.history(self.owner, event['id'])['total'], 1)
        self.assertEqual(set(self.counts().values()), {1})
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_old_writer_competes_with_atomic_handoff_for_the_same_portion(self):
        lot = self.refunds.seed_lots(('59.50',))[0]['component']
        _, refund, _ = self.refunds.refund('20.00')
        self.refunds.confirm(refund, [(lot, '20.00')])
        _, event, _ = self.components.cash('20.00')
        _, old_command = self.components.proposal(event)
        _, new_command = self.proposal(event)
        results = self.components.compete([
            lambda office: self.components.module.DocumentComponents(office).confirm(self.owner, event['id'], old_command),
            lambda office: self.module.ReusableDocumentComponents(office).confirm(self.owner, event['id'], new_command)])
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        c1_count = self.components.api.history(self.owner, event['id'])['total']
        c2_count = self.api.history(self.owner, event['id'])['total']
        self.assertEqual(c1_count + c2_count, 1)
        self.assertEqual(self.counts()['business_accounting_capacity_handoffs'], c2_count)
        if c1_count:
            self.assertEqual(self.components.api.confirm(self.owner, event['id'], old_command), results[0][1])
            with self.assertRaises(Problem) as blocked:
                self.api.confirm(self.owner, event['id'], new_command)
        else:
            self.assertEqual(self.api.confirm(self.owner, event['id'], new_command), results[1][1])
            with self.assertRaises(Problem) as blocked:
                self.components.api.confirm(self.owner, event['id'], old_command)
        self.assertEqual(blocked.exception.status, 409)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_distinct_receipts_compete_for_one_handoff_and_share_one_exact_segment(self):
        lot = self.refunds.seed_lots()[1]['component']
        _, refund, _ = self.refunds.refund('39.67')
        self.refunds.confirm(refund, [(lot, '39.67')])
        events = [self.components.cash(amount)[1] for amount in ('19.83', '19.84')]
        commands = [self.proposal(event)[1] for event in events]
        results = self.components.compete([
            lambda office, event=event, body=body:
                self.module.ReusableDocumentComponents(office).confirm(self.owner, event['id'], body)
            for event, body in zip(events, commands)])
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        self.assertEqual(self.counts()['business_accounting_capacity_handoffs'], 1)
        self.assertEqual(self.counts()['business_accounting_capacity_releases'], 1)
        entries = [value for status, value in results if status == 200]
        losing = next(index for index, (status, _) in enumerate(results) if status == 409)
        entry, body = self.confirm(events[losing])
        self.assertEqual(body['action'], 'document_current')
        self.assertEqual(entry['capacity_changes'], [])
        entries.append(entry)
        self.assertEqual(sum(Decimal(value['net']) for value in entries), Decimal('33.33'))
        self.assertEqual(sum(Decimal(value['tax']) for value in entries), Decimal('6.34'))
        self.assertEqual(len({value['lines'][0]['segment_id'] for value in entries}), 1)
        self.assertEqual(self.counts()['business_accounting_capacity_segments'], 1)
        self.assertEqual(self.counts()['business_accounting_capacity_releases'], 1)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_finance_refund_absent_from_prejournal_blocks_new_release_until_fully_bound(self):
        lots = self.refunds.seed_lots()
        _, bound, _ = self.refunds.refund('20.00')
        self.refunds.confirm(bound, [(lots[1]['component'], '20.00')])
        unknown = self.components.payment_record('refund', '1.00', [(self.components.invoice['id'], '1.00')])
        _, event, _ = self.components.cash('20.00')
        for imported in (False, True):
            portion = self.call('GET', self.path(event) + '/portions').json['items'][0]
            self.assertEqual(portion['refund_status'], 'unresolved')
            self.assertFalse(portion['eligible'])
            self.assertEqual(set(self.counts().values()), {0})
            if not imported:
                cash_body = self.components.import_body(source=self.components.payment_source(unknown['id']))
                unknown_event = self.call('POST', '/business/accounting/events/import-payment', cash_body, status=201).json
        self.refunds.confirm(unknown_event, [(lots[0]['component'], '1.00')])
        entry, command = self.confirm(event)
        self.assertEqual(entry['amount'], '20.00')
        self.assertEqual(self.counts()['business_accounting_capacity_releases'], 2)
        # A later unresolved refund changes no already released cents and cannot
        # make this historical, already accepted response disappear.
        self.components.payment_record('refund', '1.00', [(self.components.invoice['id'], '1.00')])
        _, remaining_event, _ = self.components.cash('1.00')
        portion = self.call('GET', self.path(remaining_event) + '/portions').json['items'][0]
        self.assertEqual(portion['refund_status'], 'unresolved')
        self.assertTrue(portion['eligible'])
        self.assertEqual(portion['action'], 'document_current')
        self.confirm(remaining_event)
        self.assertEqual(self.counts()['business_accounting_capacity_releases'], 2)
        self.assertEqual(self.api.confirm(self.owner, event['id'], command), entry)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_concurrent_new_finance_refund_cannot_be_ignored_by_handoff(self):
        _, _, _, _, event, _ = self.ready_middle_lot()
        _, command = self.proposal(event)
        body = request(source_id='synthetic-concurrent-refund', kind='refund', amount='1.00', currency='EUR',
            booking_date=self.components.today, reference='Synthetic concurrent refund',
            allocations=[dict(document_id=self.components.invoice['id'], amount='1.00')])
        results = self.components.compete([
            lambda office: self.module.ReusableDocumentComponents(office).confirm(self.owner, event['id'], command),
            lambda office: Finance(office).record_payment(self.owner, body)])
        self.assertEqual(results[1][0], 200)
        self.assertIn(results[0][0], (200, 409))
        if results[0][0] == 200:
            # Handoff linearized before the new refund; its accepted evidence
            # remains valid, without automatically releasing the later refund.
            self.assertEqual(self.api.confirm(self.owner, event['id'], command), results[0][1])
            self.assertEqual(self.counts()['business_accounting_capacity_releases'], 1)
        else:
            self.assertEqual(set(self.counts().values()), {0})
            self.assertEqual(self.api.portions(self.owner, event['id'])['items'][0]['refund_status'], 'unresolved')
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_later_origin_scope_extension_hides_history_and_exact_replay(self):
        payment, origin, _ = self.components.cash('130.00', assigned='119.00')
        lot, _ = self.components.confirm(origin)
        _, refund, _ = self.refunds.refund('20.00')
        self.refunds.confirm(refund, [(lot, '20.00')])
        _, event, _ = self.components.cash('20.00')
        user, token = self.components.bookkeeper()
        entry, command = self.confirm(event, token=token)
        other = self.components.other_project()
        invoice = self.components.issue(other)
        self.components.assign(payment, document=invoice['id'], amount='11.00')
        for suffix in ('', '/portions', '/history'):
            self.call('GET', self.path(event) + suffix, token=token, status=404)
        self.call('POST', self.path(event) + '/confirm', command, token=token, status=404)
        self.call('POST', '/assignments', {'project_id': other, 'user_id': user})
        self.assertEqual(self.call('POST', self.path(event) + '/confirm', command, token=token, status=201).json, entry)
        self.components.permission(user, 'finance.write', effect='deny', revision=1)
        self.call('POST', self.path(event) + '/confirm', command, token=token, status=403)
        self.assertEqual(self.call('GET', self.path(event) + '/history', token=token).json['items'], [entry])

    def test_unused_prior_group_still_requires_its_complete_historical_origin_scope(self):
        invoice = self.components.issue(self.components.project, positions=[
            dict(description='Synthetic standard group', quantity='1', unit='HUR', unit_price_net='100.00', tax_rate='19', kind='labor'),
            dict(description='Synthetic reduced group', quantity='1', unit='HUR', unit_price_net='50.00', tax_rate='7', kind='labor')])
        _, origin_a, _ = self.components.cash('119.00', document=invoice['id'])
        portion = self.components.api.portions(self.owner, origin_a['id'])['items'][0]
        by_rate = {group['rate']: group['group_id'] for group in portion['groups']}
        lot_a, _ = self.components.confirm(origin_a, groups=[dict(group_id=by_rate['19'], amount='119.00')])
        payment_b, origin_b, _ = self.components.cash('60.00', document=invoice['id'], assigned='53.50')
        lot_b, _ = self.components.confirm(origin_b, groups=[dict(group_id=by_rate['7'], amount='53.50')])
        _, refund_a, _ = self.refunds.refund('10.00', document=invoice['id'])
        self.bind_refund(refund_a, [(lot_a, by_rate['19'], '10.00')])
        _, refund_b, _ = self.refunds.refund('10.00', document=invoice['id'])
        self.bind_refund(refund_b, [(lot_b, by_rate['7'], '10.00')])
        user, token = self.components.bookkeeper()
        _, first, _ = self.components.cash('5.00', document=invoice['id'])
        self.confirm(first, groups=[dict(group_id=by_rate['19'], amount='5.00')], token=token)
        _, second, _ = self.components.cash('5.00', document=invoice['id'])
        entry, command = self.confirm(second, groups=[dict(group_id=by_rate['19'], amount='5.00')], token=token)
        self.assertEqual(entry['capacity_changes'], [])
        self.assertEqual([line['group_id'] for line in entry['lines']], [by_rate['19']])
        # E2 does not consume or create B. Nevertheless its bound whole-invoice
        # prior-segment proof retains B and therefore B's complete source scope.
        other = self.components.other_project()
        other_invoice = self.components.issue(other)
        self.components.assign(payment_b, document=other_invoice['id'], amount='6.50')
        for suffix in ('', '/portions', '/history'):
            self.call('GET', self.path(second) + suffix, token=token, status=404)
        self.call('POST', self.path(second) + '/confirm', command, token=token, status=404)
        self.call('POST', '/assignments', {'project_id': other, 'user_id': user})
        self.assertEqual(self.call('POST', self.path(second) + '/confirm', command, token=token, status=201).json, entry)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_future_return_stays_pending_while_older_confirmed_capacity_remains_usable(self):
        lot = self.refunds.seed_lots(('119.00',), cash_date='2020-01-01')[0]['component']
        _, first_refund, _ = self.refunds.refund('20.00', cash_date='2020-01-10')
        self.refunds.confirm(first_refund, [(lot, '20.00')])
        _, too_early, _ = self.components.cash('10.00', cash_date='2020-01-09')
        early = self.api.portions(self.owner, too_early['id'])['items'][0]
        self.assertFalse(early['eligible'])
        self.assertEqual(early['pending_blocked_reason'], 'receipt_before_capacity')
        _, first, _ = self.components.cash('10.00', cash_date='2020-01-10')
        self.confirm(first)
        _, later_refund, _ = self.refunds.refund('5.00', cash_date='2020-01-20')
        self.refunds.confirm(later_refund, [(lot, '5.00')])
        _, later, _ = self.components.cash('5.00', cash_date='2020-01-15')
        portion = self.api.portions(self.owner, later['id'])['items'][0]
        group = portion['groups'][0]
        self.assertTrue(portion['eligible'])
        self.assertEqual(portion['pending_blocked_reason'], 'receipt_before_capacity')
        self.assertEqual(group['current_capacity']['gross'], '10.00')
        self.assertEqual(group['pending_returns']['gross'], '5.00')
        self.assertEqual(group['offered_capacity']['gross'], '10.00')
        self.assertEqual(group['pending_returns']['not_before_date'], '2020-01-20')
        self.assertEqual(group['transition'], 'none')
        entry, _ = self.confirm(later)
        self.assertEqual(entry['capacity_changes'], [])
        self.assertEqual(self.counts()['business_accounting_capacity_segments'], 1)
        self.assertEqual(self.counts()['business_accounting_capacity_releases'], 1)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_multigroup_sql_and_audit_failures_leave_no_handoff_claim_or_partial_line(self):
        invoice = self.components.issue(self.components.project, positions=[
            dict(description='Synthetic standard group', quantity='1', unit='HUR', unit_price_net='100.00', tax_rate='19', kind='labor'),
            dict(description='Synthetic reduced group', quantity='1', unit='HUR', unit_price_net='50.00', tax_rate='7', kind='labor')])
        _, origin, _ = self.components.cash('172.50', document=invoice['id'])
        portion = self.components.api.portions(self.owner, origin['id'])['items'][0]
        groups = [dict(group_id=g['group_id'], amount=g['gross']) for g in portion['groups']]
        lot, _ = self.components.confirm(origin, groups=groups)
        by_rate = {g['rate']: g['group_id'] for g in portion['groups']}
        _, refund, _ = self.refunds.refund('80.00', document=invoice['id'])
        self.bind_refund(refund, [(lot, by_rate['19'], '60.00'), (lot, by_rate['7'], '20.00')])
        _, event, _ = self.components.cash('80.00', document=invoice['id'])
        allocations = [dict(group_id=by_rate['19'], amount='60.00'), dict(group_id=by_rate['7'], amount='20.00')]
        _, command = self.proposal(event, groups=allocations)
        for table in ('business_accounting_capacity_handoffs', 'business_accounting_capacity_lines',
                      'business_accounting_capacity_requests'):
            with self.subTest(table=table):
                with psycopg.connect(journey.DSN) as admin:
                    admin.execute('SET LOCAL ROLE "smartplan-migrator"')
                    admin.execute("CREATE FUNCTION synthetic_capacity_failure() RETURNS trigger LANGUAGE plpgsql AS $$ "
                        "BEGIN RAISE EXCEPTION 'synthetic capacity write failure'; END; $$")
                    condition = sql.SQL(' WHEN (NEW.group_id={})').format(sql.Literal(sorted(by_rate.values())[-1])) \
                        if table.endswith('_lines') else sql.SQL('')
                    admin.execute(sql.SQL('CREATE TRIGGER synthetic_capacity_failure BEFORE INSERT ON {} '
                        'FOR EACH ROW{} EXECUTE FUNCTION synthetic_capacity_failure()').format(sql.Identifier(table), condition))
                before = release.snapshot_fingerprint(journey.DSN)
                try:
                    with self.assertRaisesRegex(psycopg.Error, 'synthetic capacity write failure'):
                        self.api.confirm(self.owner, event['id'], command)
                    self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
                    self.assertEqual(set(self.counts().values()), {0})
                finally:
                    with psycopg.connect(journey.DSN) as admin:
                        admin.execute('SET LOCAL ROLE "smartplan-migrator"')
                        admin.execute(sql.SQL('DROP TRIGGER synthetic_capacity_failure ON {}').format(sql.Identifier(table)))
                        admin.execute('DROP FUNCTION synthetic_capacity_failure()')
        before = release.snapshot_fingerprint(journey.DSN)
        with patch.object(self.office, 'audit', side_effect=RuntimeError('synthetic final audit failure')):
            with self.assertRaisesRegex(RuntimeError, 'synthetic final audit failure'):
                self.api.confirm(self.owner, event['id'], command)
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
        entry = self.api.confirm(self.owner, event['id'], command)
        self.assertEqual(len(entry['lines']), 2)
        self.assertEqual(self.counts(), dict(business_accounting_capacity_handoffs=1,
            business_accounting_capacity_segments=2, business_accounting_capacity_releases=2,
            business_accounting_capacity_entries=1, business_accounting_capacity_lines=2,
            business_accounting_capacity_requests=1))
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_guarded_rows_runtime_ddl_and_finance_pause_do_not_reopen_old_writer(self):
        lot = self.refunds.seed_lots(('59.50',))[0]['component']
        _, refund, _ = self.refunds.refund('20.00')
        self.refunds.confirm(refund, [(lot, '20.00')])
        _, event, _ = self.components.cash('20.00')
        _, old_command = self.components.proposal(event)
        entry, command = self.confirm(event)
        before = release.snapshot_fingerprint(journey.DSN)
        for table in self.module.protected_tables():
            column = next(iter(self.office.db.execute('SELECT * FROM ' + table + ' LIMIT 1').fetchone().keys()))
            statements = (sql.SQL('UPDATE {} SET {}={}').format(sql.Identifier(table), sql.Identifier(column), sql.Identifier(column)),
                          sql.SQL('DELETE FROM {}').format(sql.Identifier(table)), sql.SQL('TRUNCATE {}').format(sql.Identifier(table)))
            with psycopg.connect(self.runtime) as runtime:
                for statement in statements:
                    with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                        with runtime.transaction():
                            runtime.execute(statement)
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with runtime.transaction():
                        runtime.execute('CREATE TABLE synthetic_forbidden_capacity_ddl(id TEXT)')
            with psycopg.connect(journey.DSN) as admin:
                for statement in statements[:2]:
                    with self.assertRaises(psycopg.Error):
                        with admin.transaction():
                            admin.execute('SET LOCAL ROLE "smartplan-migrator"')
                            admin.execute(statement)
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
        self.set_finance_enabled(False)
        self.assertFalse(self.api.state(self.owner, event['id'])['writes_allowed'])
        with self.assertRaises(Problem) as paused:
            self.api.confirm(self.owner, event['id'], command)
        self.assertEqual(paused.exception.status, 423)
        paused_response = self.call('POST', self.path(event) + '/confirm', command, status=423).json
        self.assertNotIn('request_resolution', paused_response)
        self.assertEqual(self.api.history(self.owner, event['id'])['items'], [entry])
        self.set_finance_enabled(True)
        with self.assertRaises(Problem) as old_blocked:
            self.components.api.confirm(self.owner, event['id'], old_command)
        self.assertEqual(old_blocked.exception.status, 409)
        old_response = self.call('POST', self.components.path(event) + '/confirm', old_command, status=409).json
        self.assertEqual(old_response['request_resolution'], 'not_accepted')
        self.assertEqual(self.api.confirm(self.owner, event['id'], command), entry)
        self.assertTrue(business_schema.require_runtime_security(self.office))

    def test_real_dump_restore_requires_current_horizon_and_preserves_exact_old_and_new_proofs(self):
        _, _, _, _, event, import_command = self.ready_middle_lot()
        entry, command = self.confirm(event)
        horizon = business_schema.financial_accounting_horizon(self.office)
        self.assertGreaterEqual(horizon['schema_version'], 5)
        self.assertEqual(horizon['capacity']['table_counts'], self.counts())
        before = release.snapshot_fingerprint(journey.DSN)
        self.office.db.close()
        for _ in range(2):
            migrate(journey.DSN, owner_role='smartplan-migrator', compatibility_mode='business', require_business_modules=True)
            self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
        with components_fixture.disposable_restore(self.runtime) as (target, runtime, report):
            restored = PostgresOffice(runtime)
            try:
                api = self.module.ReusableDocumentComponents(restored)
                self.assertEqual(api.history(self.owner, event['id'])['items'], [entry])
                self.assertFalse(api.state(self.owner, event['id'])['writes_allowed'])
                self.assertEqual(business_schema.financial_accounting_horizon(restored), horizon)
                with self.assertRaises(Problem) as blocked:
                    api.confirm(self.owner, event['id'], command)
                self.assertEqual(blocked.exception.status, 409)
                self.assertIsNone(blocked.exception.request_resolution)
            finally:
                restored.db.close()
            frozen = release.snapshot_fingerprint(target)
            for table, value in before.items():
                if table in accounting_fixture.SOURCE_TABLES or table.startswith('business_accounting_'):
                    self.assertEqual(frozen[table], value, table)
            operator = PostgresOffice(target)
            try:
                evidence = components_fixture.evidence_for(operator, report)
                self.assertEqual(evidence['schema'], horizon['schema_version'] + 1)
                old = {**evidence, 'schema': 5, 'accounting_horizon': dict(schema_version=4,
                    **{key: horizon[key] for key in ('prejournal', 'allocations', 'components', 'refunds')})}
                wrong = {**evidence, 'accounting_horizon': {**horizon,
                    'capacity': {**horizon['capacity'], 'sha256': '0' * 64}}}
                for invalid in (old, wrong):
                    with self.assertRaises((Problem, ValueError)):
                        components_fixture.approve(operator, invalid)
                    self.assertEqual(release.snapshot_fingerprint(target), frozen)
                approved = components_fixture.approve(operator, evidence)
                self.assertEqual(components_fixture.approve(operator, evidence), approved)
            finally:
                operator.db.close()
            restored = PostgresOffice(runtime)
            try:
                self.assertEqual(self.module.ReusableDocumentComponents(restored).confirm(self.owner, event['id'], command), entry)
                self.assertEqual(self.components.accounting.Accounting(restored).import_payment(self.owner, import_command), event)
                self.assertTrue(self.module.validate_integrity(restored))
                business_schema.validate_integrity(restored)
            finally:
                restored.db.close()
            self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)


@unittest.skipUnless(journey.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class CapacityMigrationPostgres(unittest.TestCase):
    def test_r1_migration_preserves_old_rows_and_schema5_replay_cannot_unlock_a_new_restore(self):
        full = business_schema.registry()
        prior = tuple(spec for spec in full if spec.name not in ('business_accounting_capacity', 'business_accounting_refunds_v2', 'business_accounting_profile', 'business_accounting_euer', 'business_payroll_cash', 'business_bank_reconciliation', 'business_travel_allowances', 'business_accounting_openings', 'business_accounting_asset_openings', 'business_accounting_open_items'))
        fixture = refunds_fixture.RefundOriginsPostgres(methodName='runTest')
        self.addCleanup(fixture.doCleanups)
        with patch.object(business_schema, 'registry', return_value=prior), \
                patch.object(business_schema, 'MODULE_NAMES', tuple(spec.name for spec in prior)):
            fixture.setUp()
            lot = fixture.seed_lots()[1]['component']
            _, refund, _ = fixture.refund('39.67')
            returned, return_command = fixture.confirm(refund, [(lot, '39.67')])
            _, replacement, _ = fixture.fixture.cash('39.67')
            horizon = business_schema.financial_accounting_horizon(fixture.office)
            self.assertEqual(horizon['schema_version'], 4)
            before = release.snapshot_fingerprint(journey.DSN)
            fixture.office.db.close()
            with components_fixture.disposable_restore(fixture.runtime) as (target, runtime, report):
                operator = PostgresOffice(target)
                try:
                    evidence = components_fixture.evidence_for(operator, report)
                    self.assertEqual(evidence['schema'], 5)
                    approved = components_fixture.approve(operator, evidence)
                finally:
                    operator.db.close()
                old_target = release.snapshot_fingerprint(target)
                with patch.object(business_schema, 'registry', return_value=full), \
                        patch.object(business_schema, 'MODULE_NAMES', tuple(spec.name for spec in full)):
                    migrate(target, owner_role='smartplan-migrator', compatibility_mode='business', require_business_modules=True)
                    upgraded = release.snapshot_fingerprint(target)
                    migrate(target, owner_role='smartplan-migrator', compatibility_mode='business', require_business_modules=True)
                    self.assertEqual(release.snapshot_fingerprint(target), upgraded)
                    for table, value in old_target.items():
                        if table != 'business_schema_migrations':
                            self.assertEqual(upgraded[table], value, table)
                    operator = PostgresOffice(target)
                    try:
                        self.assertGreaterEqual(business_schema.financial_accounting_horizon(operator)['schema_version'], 5)
                        self.assertEqual(components_fixture.approve(operator, evidence), approved)
                    finally:
                        operator.db.close()
                    self.assertEqual(release.snapshot_fingerprint(target), upgraded)
        migrate(journey.DSN, owner_role='smartplan-migrator', compatibility_mode='business', require_business_modules=True)
        after = release.snapshot_fingerprint(journey.DSN)
        migrate(journey.DSN, owner_role='smartplan-migrator', compatibility_mode='business', require_business_modules=True)
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), after)
        for table, value in before.items():
            if table != 'business_schema_migrations':
                self.assertEqual(after[table], value, table)
        release.secure_database(journey.DSN, test_mode=True)
        office = PostgresOffice(fixture.runtime)
        try:
            current = business_schema.financial_accounting_horizon(office)
            self.assertEqual(dict(schema_version=4,
                **{key: current[key] for key in ('prejournal', 'allocations', 'components', 'refunds')}), horizon)
            self.assertEqual(fixture.module.RefundOrigins(office).confirm(fixture.owner, refund['id'], return_command), returned)
            capacity = importlib.import_module('business_accounting_capacity').ReusableDocumentComponents(office)
            self.assertEqual(capacity.portions(fixture.owner, replacement['id'])['items'][0]['action'], 'takeover_and_document')
            business_schema.validate_integrity(office)
        finally:
            office.db.close()
        with components_fixture.disposable_restore(fixture.runtime) as (target, runtime, report):
            self.assertNotEqual(report['restore_id'], evidence['restore_id'])
            operator = PostgresOffice(target)
            try:
                frozen = release.snapshot_fingerprint(target)
                for invalid in (evidence, {**evidence, 'restore_id': report['restore_id']}):
                    with self.assertRaises((Problem, ValueError)):
                        components_fixture.approve(operator, invalid)
                    self.assertEqual(release.snapshot_fingerprint(target), frozen)
                latest = components_fixture.evidence_for(operator, report)
                self.assertEqual(latest['schema'], business_schema.financial_accounting_horizon(operator)['schema_version'] + 1)
                components_fixture.approve(operator, latest)
            finally:
                operator.db.close()
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), after)


if __name__ == '__main__':
    unittest.main()
