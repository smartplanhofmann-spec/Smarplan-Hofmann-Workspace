"""Exact documentary refund origins on guarded, disposable PostgreSQL.

Uses genuine invoice issuance, MFA and the restricted runtime role. No old
payment, OP, cash or component proof is rewritten; no capacity is released.
"""
from decimal import Decimal
import hashlib
import importlib
import json
import unittest
from unittest.mock import patch
import uuid

import psycopg
from psycopg import sql

import business_schema
from business_finance import Finance
from core import Problem, canonical
from online import release, test_business_journey_pg as journey
from online import test_postgres_accounting_components_integration as components_fixture
from online import test_postgres_accounting_integration as accounting_fixture
from online.store import PostgresOffice, migrate


request = journey.request


@unittest.skipUnless(journey.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class RefundOriginsPostgres(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module('business_accounting_refunds')
        self.fixture = components_fixture.ComponentsPostgres(methodName='runTest')
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.office = self.fixture.office
        self.runtime = self.fixture.runtime
        self.owner = self.fixture.owner
        self.call = self.fixture.call
        self.api = self.module.RefundOrigins(self.office)

    def seed_lots(self, amounts=('39.67', '39.67', '39.66'), *, cash_date=None):
        lots = []
        for amount in amounts:
            payment, event, cash_body = self.fixture.cash(amount, cash_date=cash_date)
            component, command = self.fixture.confirm(event)
            lots.append(dict(payment=payment, event=event, cash_body=cash_body,
                             component=component, command=command))
        return lots

    def refund(self, amount, *, cash_date=None, document=None, assigned=None):
        return self.fixture.cash(amount, kind='refund', cash_date=cash_date,
                                 document=document, assigned=assigned)

    def path(self, event):
        return '/business/accounting/refunds/events/' + event['id']

    def proposal(self, event, selected, *, token='owner', portion_id=None):
        path = self.path(event)
        state = self.call('GET', path, token=token).json
        portions = self.call('GET', path + '/portions', token=token).json['items']
        portion = next(row for row in portions if row['portion_id'] == portion_id) if portion_id else portions[0]
        candidates = self.call('GET', path + '/origins?portion_id=' + portion['portion_id'], token=token).json['items']
        origins = []
        for component, amount in selected:
            candidate = next(row for row in candidates if row['entry_id'] == component['id']
                             and row['group_id'] == component['lines'][0]['group_id'])
            self.assertEqual(candidate['component_sequence'], component['sequence'])
            self.assertEqual((candidate['rate'], candidate['category'], candidate['tax_reason']), ('19', 'S', ''))
            origins.append(dict(entry_id=candidate['entry_id'], group_id=candidate['group_id'],
                                lot_state_hash=candidate['lot_state_hash'], amount=amount))
        body = dict(source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
            portion_id=portion['portion_id'], portion_state_hash=portion['portion_state_hash'], origins=origins,
            reason='Synthetic explicitly selected refund origins')
        preview = self.call('POST', path + '/preview', body, token=token).json
        return preview, request(**body, preview_hash=preview['preview_hash'], confirmation=True)

    def confirm(self, event, selected, **kwargs):
        preview, command = self.proposal(event, selected, **kwargs)
        entry = self.call('POST', self.path(event) + '/confirm', command,
                          token=kwargs.get('token', 'owner'), status=201).json
        return entry, command

    def frozen_sources(self):
        fingerprints = release.snapshot_fingerprint(journey.DSN)
        return {table: value for table, value in fingerprints.items()
                if table in accounting_fixture.SOURCE_TABLES or
                table.startswith('business_accounting_') and not table.startswith('business_accounting_refund_')}

    def test_whole_refund_once_exact_middle_lot_no_old_bytes_op_or_capacity_changes(self):
        lots = self.seed_lots()
        payment, event, cash_body = self.refund('39.67')
        before = self.frozen_sources()
        c1 = self.fixture.module.restore_horizon(self.office)
        op = Finance(self.office).open_items(self.owner)
        snapshot = release.snapshot_fingerprint(journey.DSN)
        preview, command = self.proposal(event, [(lots[1]['component'], '39.67')])
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), snapshot)
        self.assertEqual((preview['net'], preview['tax']), ('33.33', '6.34'))
        allocation = self.office.db.execute('SELECT id FROM business_payment_allocations WHERE payment_id=?', (payment['id'],)).fetchone()
        portion_id = hashlib.sha256(canonical(dict(kind='original_refund_allocation', id=allocation['id'])).encode()).hexdigest()
        self.assertEqual(preview['portion']['portion_id'], portion_id)
        entry = self.call('POST', self.path(event) + '/confirm', command, status=201).json
        self.assertFalse(entry['capacity_released'])
        self.assertEqual(self.call('POST', self.path(event) + '/confirm', command, status=201).json, entry)
        self.call('POST', self.path(event) + '/confirm', {**command, 'request_id': uuid.uuid4().hex}, status=409)
        self.call('POST', self.path(event) + '/confirm', {**command, 'reason': 'Changed synthetic request'}, status=409)
        user, token = self.fixture.bookkeeper()
        self.call('POST', self.path(event) + '/confirm', {**command, 'request_id': uuid.uuid4().hex}, token=token, status=409)
        # Permission grants above intentionally change only access metadata.
        self.assertEqual(self.frozen_sources(), before)
        self.assertEqual(Finance(self.office).open_items(self.owner), op)
        self.assertEqual(self.fixture.module.restore_horizon(self.office), c1)
        self.assertEqual(self.fixture.accounting.Accounting(self.office).import_payment(self.owner, cash_body), event)
        for lot in lots:
            self.assertEqual(self.fixture.api.confirm(self.owner, lot['event']['id'], lot['command']), lot['component'])
        self.assertIsNone(self.office.db.execute('SELECT reverses FROM business_payments WHERE id=?', (payment['id'],)).fetchone()['reverses'])
        reopened = PostgresOffice(self.runtime)
        try:
            self.assertEqual(self.module.RefundOrigins(reopened).confirm(self.owner, event['id'], command), entry)
            self.assertTrue(self.module.validate_integrity(reopened))
            business_schema.validate_integrity(reopened)
        finally:
            reopened.db.close()

    def test_two_same_group_lots_keep_different_cents_across_three_partial_refunds(self):
        lots = self.seed_lots()
        first, second = (row['component'] for row in lots[:2])
        self.assertEqual(first['lines'][0]['group_id'], second['lines'][0]['group_id'])
        self.assertEqual((first['tax'], second['tax']), ('6.33', '6.34'))
        results = []
        for amount, each, expected in (('26.44', '13.22', ('22.22', '4.22')),
                                      ('26.44', '13.22', ('22.21', '4.23')),
                                      ('26.46', '13.23', ('22.24', '4.22'))):
            _, event, _ = self.refund(amount)
            before = self.frozen_sources()
            entry, command = self.confirm(event, [(second, each), (first, each)])
            self.assertEqual((entry['net'], entry['tax']), expected)
            self.assertEqual(len(entry['lines']), 2)
            self.assertEqual([line['entry_id'] for line in entry['lines']], sorted([first['id'], second['id']]))
            self.assertEqual(self.frozen_sources(), before)
            results.append((event, entry, command))
        self.assertEqual(sum(Decimal(entry['net']) for _, entry, _ in results), Decimal('66.67'))
        self.assertEqual(sum(Decimal(entry['tax']) for _, entry, _ in results), Decimal('12.67'))
        for line in results[-1][1]['lines']:
            self.assertEqual((line['remaining_gross'], line['remaining_net'], line['remaining_tax']), ('0.00', '0.00', '0.00'))
        for event, entry, command in results:
            self.assertEqual(self.api.confirm(self.owner, event['id'], command), entry)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_two_connections_cannot_bind_same_refund_portion_twice(self):
        lot = self.seed_lots()[1]['component']
        _, event, _ = self.refund('20.00')
        _, command = self.proposal(event, [(lot, '20.00')])
        commands = [command, {**command, 'request_id': uuid.uuid4().hex}]
        results = self.fixture.compete([lambda office, body=body:
            self.module.RefundOrigins(office).confirm(self.owner, event['id'], body) for body in commands])
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        self.assertEqual(self.api.history(self.owner, event['id'])['total'], 1)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_two_refunds_compete_for_same_origin_lot_across_independent_connections(self):
        lot = self.seed_lots()[1]['component']
        events = [self.refund('39.67')[1] for _ in range(2)]
        commands = [(event, self.proposal(event, [(lot, '39.67')])[1]) for event in events]
        before = self.frozen_sources()
        results = self.fixture.compete([lambda office, event=event, body=body:
            self.module.RefundOrigins(office).confirm(self.owner, event['id'], body) for event, body in commands])
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        self.assertEqual(sum(self.api.history(self.owner, event['id'])['total'] for event in events), 1)
        self.assertEqual(self.frozen_sources(), before)
        self.assertEqual(Finance(self.office)._payment_sum(self.fixture.invoice['id']), Decimal('39.66'))
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_real_sql_failure_rolls_back_and_runtime_cannot_rewrite_or_truncate_refunds(self):
        lots = self.seed_lots()
        _, event, _ = self.refund('20.00')
        _, body = self.proposal(event, [(lots[0]['component'], '10.00'), (lots[1]['component'], '10.00')])
        table = 'business_accounting_refund_requests'
        with psycopg.connect(journey.DSN) as admin:
            admin.execute('SET LOCAL ROLE "smartplan-migrator"')
            admin.execute("CREATE FUNCTION synthetic_refund_failure() RETURNS trigger LANGUAGE plpgsql AS $$ "
                "BEGIN RAISE EXCEPTION 'synthetic refund receipt failure'; END; $$")
            admin.execute(sql.SQL('CREATE TRIGGER synthetic_refund_failure BEFORE INSERT ON {} '
                'FOR EACH ROW EXECUTE FUNCTION synthetic_refund_failure()').format(sql.Identifier(table)))
        before = release.snapshot_fingerprint(journey.DSN)
        try:
            with self.assertRaisesRegex(psycopg.Error, 'synthetic refund receipt failure'):
                self.api.confirm(self.owner, event['id'], body)
            self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
        finally:
            with psycopg.connect(journey.DSN) as admin:
                admin.execute('SET LOCAL ROLE "smartplan-migrator"')
                admin.execute(sql.SQL('DROP TRIGGER synthetic_refund_failure ON {}').format(sql.Identifier(table)))
                admin.execute('DROP FUNCTION synthetic_refund_failure()')
        self.api.confirm(self.owner, event['id'], body)
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
            with psycopg.connect(journey.DSN) as admin:
                for statement in statements[:2]:
                    with self.assertRaises(psycopg.Error):
                        with admin.transaction():
                            admin.execute('SET LOCAL ROLE "smartplan-migrator"')
                            admin.execute(statement)
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
        self.assertTrue(business_schema.require_runtime_security(self.office))
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_later_origin_project_extension_hides_refund_history_and_replay(self):
        payment, origin, _ = self.fixture.cash('130.00', assigned='59.50')
        component, _ = self.fixture.confirm(origin)
        _, event, _ = self.refund('20.00')
        user, token = self.fixture.bookkeeper()
        entry, command = self.confirm(event, [(component, '20.00')], token=token)
        other = self.fixture.other_project()
        invoice = self.fixture.issue(other)
        self.fixture.assign(payment, document=invoice['id'], amount='70.50')
        for suffix in ('', '/portions', '/history'):
            self.call('GET', self.path(event) + suffix, token=token, status=404)
        self.call('POST', self.path(event) + '/confirm', command, token=token, status=404)
        self.call('POST', '/assignments', {'project_id': other, 'user_id': user})
        self.assertEqual(self.call('POST', self.path(event) + '/confirm', command, token=token, status=201).json, entry)
        self.fixture.permission(user, 'finance.write', effect='deny', revision=1)
        self.call('POST', self.path(event) + '/confirm', command, token=token, status=403)
        self.assertEqual(self.call('GET', self.path(event) + '/history', token=token).json['items'], [entry])

    def test_cash_date_and_historical_cancel_rules_do_not_use_component_creation_time(self):
        _, origin, _ = self.fixture.cash('59.50', cash_date='2020-01-02')
        _, early_refund, _ = self.refund('10.00', cash_date='2020-01-01')
        _, valid_refund, _ = self.refund('10.00', cash_date='2020-01-02')
        # Both refunds precede creation of the documentary component entry.
        component, _ = self.fixture.confirm(origin)
        early_portion = self.api.portions(self.owner, early_refund['id'])['items'][0]
        self.assertEqual(self.api.origins(self.owner, early_refund['id'], early_portion['portion_id'])['items'], [])
        valid_preview, command = self.proposal(valid_refund, [(component, '10.00')])
        state = self.api.state(self.owner, early_refund['id'])
        invalid = {key: value for key, value in command.items() if key not in ('request_id', 'preview_hash', 'confirmation')}
        invalid.update(source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
                       portion_id=early_portion['portion_id'], portion_state_hash=early_portion['portion_state_hash'])
        self.call('POST', self.path(early_refund) + '/preview', invalid, status=409)
        draft = self.call('POST', '/business/documents/' + self.fixture.invoice['id'] + '/cancel',
            request(revision=self.fixture.invoice['revision'], reason='Synthetic cancellation after true incoming lot')).json
        self.call('POST', '/business/documents/' + draft['id'] + '/finalize', request(revision=draft['revision']))
        before = self.frozen_sources()
        entry, body = self.confirm(valid_refund, [(component, '10.00')])
        self.assertEqual(entry['lines'][0]['origin_cash_date'], '2020-01-02')
        self.assertEqual(self.frozen_sources(), before)
        self.assertEqual(self.api.confirm(self.owner, valid_refund['id'], body), entry)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_originally_private_origin_is_not_offered_and_hides_a_later_binding(self):
        payment = self.fixture.payment_record('receipt', '40.00', [])
        origin = self.call('POST', '/business/accounting/events/import-payment',
            self.fixture.import_body(source=self.fixture.payment_source(payment['id'])), status=201).json
        self.fixture.assign(payment, amount='40.00')
        component, _ = self.fixture.confirm(origin)
        _, event, _ = self.refund('20.00')
        _, token = self.fixture.bookkeeper()
        portion = self.call('GET', self.path(event) + '/portions', token=token).json['items'][0]
        self.assertEqual(self.call('GET', self.path(event) + '/origins?portion_id=' + portion['portion_id'],
                                  token=token).json['items'], [])
        _, command = self.proposal(event, [(component, '20.00')])
        self.call('POST', self.path(event) + '/confirm', command, token=token, status=403)
        self.call('POST', self.path(event) + '/confirm', command, status=201)
        for suffix in ('', '/portions', '/history'):
            self.call('GET', self.path(event) + suffix, token=token, status=403)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_global_lot_aggregate_includes_inaccessible_refund_without_its_ids(self):
        lot = self.seed_lots(('119.00',))[0]['component']
        other = self.fixture.other_project()
        invoice = self.fixture.issue(other)
        self.fixture.payment_record('receipt', '10.00', [(invoice['id'], '10.00')])
        payment = self.fixture.payment_record('refund', '30.00',
            [(self.fixture.invoice['id'], '20.00'), (invoice['id'], '10.00')])
        hidden = self.call('POST', '/business/accounting/events/import-payment',
            self.fixture.import_body(source=self.fixture.payment_source(payment['id'])), status=201).json
        portion = next(row for row in self.api.portions(self.owner, hidden['id'])['items']
                       if row['document_id'] == self.fixture.invoice['id'])
        entry, command = self.confirm(hidden, [(lot, '20.00')], portion_id=portion['portion_id'])
        _, visible, _ = self.refund('20.00')
        _, token = self.fixture.bookkeeper()
        self.call('GET', self.path(hidden), token=token, status=404)
        portion = self.call('GET', self.path(visible) + '/portions', token=token).json['items'][0]
        candidates = self.call('GET', self.path(visible) + '/origins?portion_id=' + portion['portion_id'], token=token).json
        origin = next(row for row in candidates['items'] if row['entry_id'] == lot['id'])
        self.assertEqual((origin['returned_amount'], origin['remaining_amount']), ('20.00', '99.00'))
        encoded = json.dumps(candidates)
        for forbidden in (payment['id'], hidden['id'], entry['id'], command['request_id'], self.owner['id']):
            self.assertNotIn(forbidden, encoded)
        entry, _ = self.confirm(visible, [(lot, '20.00')], token=token)
        self.assertEqual(entry['lines'][0]['gross_before'], '20.00')
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_bound_refund_does_not_reopen_c1_capacity_or_hide_unallocated_remainder(self):
        lot = self.seed_lots(('119.00',))[0]['component']
        _, event, _ = self.refund('30.00', assigned='20.00')
        # Finance permits a real replacement receipt; its component pool stays exhausted.
        _, replacement, _ = self.fixture.cash('20.00')
        c1 = self.fixture.module.restore_horizon(self.office)
        entry, _ = self.confirm(event, [(lot, '20.00')])
        state = self.api.state(self.owner, event['id'])
        self.assertEqual((state['origin_documented_amount'], state['origin_unresolved_amount'], state['unallocated_amount']),
                         ('20.00', '10.00', '10.00'))
        self.assertFalse(state['capacity_released'])
        self.assertFalse(entry['capacity_released'])
        portion = self.fixture.api.portions(self.owner, replacement['id'])['items'][0]
        self.assertFalse(portion['eligible'])
        self.assertEqual(portion['groups'][0]['remaining_gross'], '0.00')
        self.assertEqual(self.fixture.module.restore_horizon(self.office), c1)
        self.assertEqual(Finance(self.office)._payment_sum(self.fixture.invoice['id']), Decimal('119.00'))
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_real_restore_keeps_origins_and_requires_current_horizon_before_replay(self):
        lot = self.seed_lots()[1]['component']
        _, event, cash_body = self.refund('39.67')
        entry, command = self.confirm(event, [(lot, '39.67')])
        horizon = business_schema.financial_accounting_horizon(self.office)
        self.assertGreaterEqual(horizon['schema_version'], 4)
        self.assertEqual(horizon['refunds']['table_counts'], dict(business_accounting_refund_entries=1,
            business_accounting_refund_lines=1, business_accounting_refund_requests=1))
        before = release.snapshot_fingerprint(journey.DSN)
        self.office.db.close()
        for _ in range(2):
            migrate(journey.DSN, owner_role='smartplan-migrator', compatibility_mode='business', require_business_modules=True)
            self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
        with components_fixture.disposable_restore(self.runtime) as (target, runtime, report):
            restored = PostgresOffice(runtime)
            try:
                api = self.module.RefundOrigins(restored)
                self.assertEqual(api.history(self.owner, event['id'])['items'], [entry])
                self.assertFalse(api.state(self.owner, event['id'])['writes_allowed'])
                self.assertEqual(business_schema.financial_accounting_horizon(restored), horizon)
                with self.assertRaises(Problem) as blocked:
                    api.confirm(self.owner, event['id'], command)
                self.assertEqual(blocked.exception.status, 409)
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
                old = {**evidence, 'schema': 4, 'accounting_horizon': dict(schema_version=3,
                    **{key: horizon[key] for key in ('prejournal', 'allocations', 'components')})}
                wrong = {**evidence, 'accounting_horizon': {**horizon,
                    'refunds': {**horizon['refunds'], 'sha256': '0' * 64}}}
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
                self.assertEqual(self.module.RefundOrigins(restored).confirm(self.owner, event['id'], command), entry)
                self.assertEqual(self.fixture.accounting.Accounting(restored).import_payment(self.owner, cash_body), event)
                self.assertTrue(self.module.validate_integrity(restored))
                business_schema.validate_integrity(restored)
            finally:
                restored.db.close()
            self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)


@unittest.skipUnless(journey.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class RefundMigrationPostgres(unittest.TestCase):
    def test_c1_migration_preserves_every_old_row_and_schema4_receipt_cannot_unlock_new_restore(self):
        full = business_schema.registry()
        prior = tuple(spec for spec in full if spec.name not in ('business_accounting_refunds', 'business_accounting_capacity', 'business_accounting_refunds_v2', 'business_accounting_profile', 'business_accounting_euer', 'business_payroll_cash', 'business_bank_reconciliation', 'business_travel_allowances', 'business_accounting_openings', 'business_accounting_asset_openings', 'business_accounting_open_items'))
        fixture = components_fixture.ComponentsPostgres(methodName='runTest')
        self.addCleanup(fixture.doCleanups)
        with patch.object(business_schema, 'registry', return_value=prior), \
                patch.object(business_schema, 'MODULE_NAMES', tuple(spec.name for spec in prior)):
            fixture.setUp()
            _, origin, _ = fixture.cash('119.00')
            component, component_body = fixture.confirm(origin)
            _, refund_event, _ = fixture.cash('20.00', kind='refund')
            horizon = business_schema.financial_accounting_horizon(fixture.office)
            self.assertEqual(horizon['schema_version'], 3)
            before = release.snapshot_fingerprint(journey.DSN)
            fixture.office.db.close()
            with components_fixture.disposable_restore(fixture.runtime) as (target, runtime, report):
                operator = PostgresOffice(target)
                try:
                    evidence = components_fixture.evidence_for(operator, report)
                    self.assertEqual(evidence['schema'], 4)
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
                        self.assertGreaterEqual(business_schema.financial_accounting_horizon(operator)['schema_version'], 4)
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
            self.assertEqual(dict(schema_version=3, **{key: current[key] for key in ('prejournal', 'allocations', 'components')}), horizon)
            self.assertEqual(fixture.module.DocumentComponents(office).confirm(fixture.owner, origin['id'], component_body), component)
            self.assertEqual(importlib.import_module('business_accounting_refunds').RefundOrigins(office).state(
                fixture.owner, refund_event['id'])['origin_documented_amount'], '0.00')
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
