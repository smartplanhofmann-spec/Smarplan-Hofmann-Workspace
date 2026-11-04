"""Explicit preparation profiles on isolated PostgreSQL with real runtime roles.

All invoices, cash histories and profiles are synthetic. Only the guarded
loopback fixture is reset; genuine dump/restore uses the existing operator.
"""
import hashlib
import importlib
import json
import unittest
from unittest.mock import patch
import uuid

import psycopg
from psycopg import sql

import business_schema
from business_accounting import Accounting
from business_finance import Finance
from core import Problem, canonical
from online import release, test_business_journey_pg as journey
from online import test_postgres_accounting_components_integration as components_fixture
from online import test_postgres_accounting_refunds_v2_integration as refunds_fixture
from online.store import PostgresOffice, migrate

request = journey.request
PATH = '/business/accounting/profile'
H6_FIELDS = ('prejournal', 'allocations', 'components', 'refunds', 'capacity', 'refunds_v2')


def declared_profile(**changes):
    return dict(legal_form='sole_proprietorship', accounting_method='euer', vat_regime=None,
                vat_timing=None, vat_effective_from=None, bookkeeping_start=None) | changes


def preview_body(state, profile=None, **changes):
    return dict(expected_revision=state['revision'], state_hash=state['state_hash'],
                profile=declared_profile() if profile is None else profile,
                reason='Synthetic expressly confirmed preparation statement',
                evidence_reference='Synthetic owner statement; no authority verification') | changes


@unittest.skipUnless(journey.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class PreparationProfilePostgres(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module('business_accounting_profile')
        self.fixture = refunds_fixture.VersionedRefundsPostgres(methodName='runTest')
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.office, self.runtime, self.owner, self.call = (
            self.fixture.office, self.fixture.runtime, self.fixture.owner, self.fixture.call)
        self.api = self.module.AccountingPreparationProfile(self.office)

    def counts(self):
        return {table: self.office.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]
                for table in self.module.protected_tables()}

    def proposal(self, profile=None, *, token='owner', **changes):
        state = self.call('GET', PATH, token=token).json
        body = preview_body(state, profile, **changes)
        preview = self.call('POST', PATH + '/preview', body, token=token).json
        return preview, request(**body, preview_hash=preview['preview_hash'], confirmation=True)

    def confirm(self, profile=None, *, token='owner', **changes):
        unused, body = self.proposal(profile, token=token, **changes)
        return self.call('POST', PATH + '/confirm', body, token=token, status=201).json, body

    def old_business_fingerprints(self):
        return {table: value for table, value in release.snapshot_fingerprint(journey.DSN).items()
                if table.startswith('business_') and not table.startswith('business_accounting_profile_')}

    def test_empty_reads_and_preview_do_not_infer_or_record_a_profile(self):
        frozen = release.snapshot_fingerprint(journey.DSN)
        state = self.call('GET', PATH).json
        self.assertEqual((state['revision'], state['preparation_status'], state['current']), (0, 'unrecorded', None))
        self.assertEqual((state['scope'], state['tax_status'], state['tax_result_available']),
                         ('organization_profile', 'unconfigured', False))
        self.assertTrue(state['writes_allowed'])
        self.assertEqual(self.call('GET', PATH + '/history').json['items'], [])
        preview, unused = self.proposal()
        self.assertEqual(preview['profile'], declared_profile())
        self.assertEqual(self.counts(), dict(business_accounting_profile_versions=0, business_accounting_profile_requests=0))
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), frozen)
        with patch('accounting_joint_ledger.read_joint_ledger', side_effect=AssertionError('Profile must not read cash ledgers')):
            self.assertTrue(self.module.validate_integrity(self.office))
            horizon = self.module.restore_horizon(self.office)
        expected = dict(schema_version=1, tables={table: [] for table in self.module.protected_tables()})
        self.assertEqual(horizon, dict(schema_version=1, table_counts=self.counts(),
            sha256=hashlib.sha256(canonical(expected).encode()).hexdigest()))
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), frozen)

    def test_new_profile_versions_leave_real_c1_c2_r1_r2_cash_and_old_receipts_unchanged(self):
        seed, refund, selected = self.fixture.mixed()
        returned, return_command = self.fixture.confirm(refund, selected)
        _, receipt, unused = self.fixture.components.cash('26.44')
        positive, positive_command = self.fixture.capacity.confirm(receipt)
        frozen = self.old_business_fingerprints()
        cash = Accounting(self.office).event(self.owner, refund['id'])
        op = Finance(self.office).open_items(self.owner)
        first, first_command = self.confirm()
        second, unused = self.confirm(declared_profile(vat_regime='regular', vat_timing='cash',
            vat_effective_from='2025-01-01', bookkeeping_start='2026-01-01'), reason='Synthetic later declared facts, no tax activation')
        self.assertEqual(first['profile'], declared_profile())
        self.assertEqual((first['revision'], second['revision']), (1, 2))
        self.assertEqual(self.api.confirm(self.owner, first_command), first)
        self.assertEqual(self.api.state(self.owner)['current'], second)
        self.assertEqual(self.api.history(self.owner)['items'], [second, first])
        self.assertEqual(Accounting(self.office).event(self.owner, refund['id']), cash)
        self.assertEqual(Finance(self.office).open_items(self.owner), op)
        self.assertEqual(Accounting(self.office).status(self.owner)['profile_status'], 'unconfigured')
        self.assertEqual(Accounting(self.office).status(self.owner)['tax_status'], 'unconfigured')
        self.assertFalse(Accounting(self.office).status(self.owner)['tax_result_available'])
        self.assertEqual(self.fixture.refunds.api.confirm(self.owner, seed['refund']['id'], seed['command']), seed['returned'])
        self.assertEqual(self.fixture.capacity.api.confirm(self.owner, seed['receipt']['id'], seed['reuse_command']), seed['reused'])
        self.assertEqual(self.fixture.api.confirm(self.owner, refund['id'], return_command), returned)
        self.assertEqual(self.fixture.capacity.api.confirm(self.owner, receipt['id'], positive_command), positive)
        self.assertEqual(self.old_business_fingerprints(), frozen)
        before = release.snapshot_fingerprint(journey.DSN)
        response = self.call('POST', PATH + '/confirm', {**first_command, 'reason': 'Different synthetic request body'}, status=409).json
        self.assertNotIn('request_resolution', response)
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
        with patch('accounting_joint_ledger.read_joint_ledger', side_effect=AssertionError('Profile must not read cash ledgers')):
            self.assertTrue(self.module.validate_integrity(self.office))
            self.assertEqual(self.module.restore_horizon(self.office)['table_counts'], self.counts())

    def test_two_real_connections_cannot_confirm_different_profiles_at_one_revision(self):
        commands = [self.proposal(declared_profile(vat_regime=regime),
            reason='Synthetic concurrent statement ' + str(index))[1] for index, regime in enumerate((None, 'regular'))]
        results = self.fixture.components.compete([lambda office, command=command:
            self.module.AccountingPreparationProfile(office).confirm(self.owner, command) for command in commands])
        self.assertEqual(sorted(status for status, unused in results), [200, 409])
        winner = next(index for index, (status, unused) in enumerate(results) if status == 200)
        self.assertEqual(self.api.confirm(self.owner, commands[winner]), results[winner][1])
        before = release.snapshot_fingerprint(journey.DSN)
        response = self.call('POST', PATH + '/confirm', commands[1 - winner], status=409).json
        self.assertEqual(response['request_resolution'], 'not_accepted')
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
        self.assertEqual(set(self.counts().values()), {1})
        self.assertEqual(self.api.history(self.owner)['total'], 1)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_identical_concurrent_request_writes_once_and_replays_after_new_revision(self):
        unused, command = self.proposal()
        results = self.fixture.components.compete([lambda office:
            self.module.AccountingPreparationProfile(office).confirm(self.owner, command) for unused in range(2)])
        self.assertEqual([status for status, unused in results], [200, 200])
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual(set(self.counts().values()), {1})
        second, unused = self.confirm(reason='Synthetic expressly repeated statement with new reason')
        before = release.snapshot_fingerprint(journey.DSN)
        self.assertEqual(self.call('POST', PATH + '/confirm', command, status=201).json, results[0][1])
        self.assertEqual(self.api.state(self.owner)['current'], second)
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
        self.assertEqual(set(self.counts().values()), {2})

    def test_version_receipt_and_audit_failures_roll_back_the_entire_profile_command(self):
        unused, command = self.proposal()
        for table in self.module.protected_tables():
            with psycopg.connect(journey.DSN) as admin:
                admin.execute('SET LOCAL ROLE "smartplan-migrator"')
                admin.execute("CREATE FUNCTION synthetic_profile_failure() RETURNS trigger LANGUAGE plpgsql AS $$ "
                              "BEGIN RAISE EXCEPTION 'synthetic profile failure'; END; $$")
                admin.execute(sql.SQL('CREATE TRIGGER synthetic_profile_failure BEFORE INSERT ON {} '
                    'FOR EACH ROW EXECUTE FUNCTION synthetic_profile_failure()').format(sql.Identifier(table)))
            frozen = release.snapshot_fingerprint(journey.DSN)
            try:
                with self.subTest(table=table), self.assertRaisesRegex(psycopg.Error, 'synthetic profile failure'):
                    self.api.confirm(self.owner, command)
                self.assertEqual(release.snapshot_fingerprint(journey.DSN), frozen)
                self.assertEqual(set(self.counts().values()), {0})
            finally:
                with psycopg.connect(journey.DSN) as admin:
                    admin.execute('SET LOCAL ROLE "smartplan-migrator"')
                    admin.execute(sql.SQL('DROP TRIGGER synthetic_profile_failure ON {}').format(sql.Identifier(table)))
                    admin.execute('DROP FUNCTION synthetic_profile_failure()')
        frozen = release.snapshot_fingerprint(journey.DSN)
        with patch.object(self.office, 'audit', side_effect=RuntimeError('synthetic profile audit failure')):
            with self.assertRaisesRegex(RuntimeError, 'synthetic profile audit failure'):
                self.api.confirm(self.owner, command)
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), frozen)
        entry = self.api.confirm(self.owner, command)
        self.assertEqual(entry['revision'], 1)
        self.assertEqual(set(self.counts().values()), {1})

    def test_real_foreign_keys_unique_receipts_immutable_history_and_runtime_ddl_limits(self):
        self.confirm()
        frozen = release.snapshot_fingerprint(journey.DSN)
        for table in self.module.protected_tables():
            sample = dict(self.office.db.execute('SELECT * FROM ' + table).fetchone())
            columns = list(sample)
            if table.endswith('_versions'):
                invalid = [(dict(id=uuid.uuid4().hex, revision=2, created_by=uuid.uuid4().hex), psycopg.errors.ForeignKeyViolation),
                           (dict(id=uuid.uuid4().hex), psycopg.errors.UniqueViolation)]
            else:
                invalid = [(dict(request_id=uuid.uuid4().hex, entry_id=uuid.uuid4().hex), psycopg.errors.ForeignKeyViolation),
                           (dict(request_id=uuid.uuid4().hex), psycopg.errors.UniqueViolation)]
            with psycopg.connect(self.runtime) as runtime:
                for changes, error_type in invalid:
                    with self.subTest(table=table, change=sorted(changes)), self.assertRaises(error_type):
                        with runtime.transaction():
                            value = sample | changes
                            runtime.execute(sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(sql.Identifier(table),
                                sql.SQL(',').join(map(sql.Identifier, columns)), sql.SQL(',').join(sql.Placeholder() for unused in columns)),
                                [value[name] for name in columns])
                statements = [sql.SQL('UPDATE {} SET {}={}').format(sql.Identifier(table), sql.Identifier(columns[0]), sql.Identifier(columns[0])),
                              sql.SQL('DELETE FROM {}').format(sql.Identifier(table)), sql.SQL('TRUNCATE {}').format(sql.Identifier(table))]
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
                with runtime.transaction(): runtime.execute('CREATE TABLE synthetic_forbidden_profile_ddl(id TEXT)')
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), frozen)
        self.assertTrue(business_schema.require_runtime_security(self.office))

    def test_fresh_global_admin_and_finance_pause_apply_before_historical_replay(self):
        components = self.fixture.components
        user, token = components.bookkeeper()
        self.assertFalse(self.call('GET', PATH, token=token).json['writes_allowed'])
        self.call('POST', '/business/settings/permissions', request(user_id=user, permission='accounting.admin',
            scope=components.project, effect='allow', revision=0), status=400)
        unused, command = self.proposal()
        frozen = release.snapshot_fingerprint(journey.DSN)
        self.call('POST', PATH + '/confirm', command, token=token, status=403)
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), frozen)
        grant = components.permission(user, 'accounting.admin')
        first = self.call('POST', PATH + '/confirm', command, token=token, status=201).json
        self.assertEqual(first['created_by'], user)
        second, unused = self.confirm(reason='Synthetic subsequent owner version')
        revoked = components.permission(user, 'accounting.admin', effect='deny', revision=grant['revision'])
        frozen = release.snapshot_fingerprint(journey.DSN)
        self.call('POST', PATH + '/confirm', command, token=token, status=403)
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), frozen)
        components.permission(user, 'accounting.admin', revision=revoked['revision'])
        self.fixture.capacity.set_finance_enabled(False)
        self.assertEqual(self.call('GET', PATH + '/history', token=token).json['items'], [second, first])
        self.assertFalse(self.call('GET', PATH, token=token).json['writes_allowed'])
        response = self.call('POST', PATH + '/confirm', command, token=token, status=423).json
        self.assertNotIn('request_resolution', response)
        self.fixture.capacity.set_finance_enabled(True)
        self.assertEqual(self.call('POST', PATH + '/confirm', command, token=token, status=201).json, first)
        self.assertEqual(self.api.state(self.owner)['current'], second)

    def test_real_dump_restore_binds_profile_horizon_and_requires_schema10_even_for_old_replay(self):
        first, command = self.confirm()
        second, unused = self.confirm(declared_profile(vat_regime='small_business', vat_effective_from='2026-01-01'))
        horizon = business_schema.financial_accounting_horizon(self.office)
        self.assertEqual(horizon['schema_version'], 14)
        self.assertEqual(horizon['profile']['table_counts'], self.counts())
        self.assertEqual(set(horizon['profile']['table_counts'].values()), {2})
        before = release.snapshot_fingerprint(journey.DSN); self.office.db.close()
        for unused in range(2):
            migrate(journey.DSN, owner_role='smartplan-migrator', compatibility_mode='business', require_business_modules=True)
            self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
        with components_fixture.disposable_restore(self.runtime) as (target, runtime, report):
            restored = PostgresOffice(runtime)
            try:
                api = self.module.AccountingPreparationProfile(restored)
                self.assertEqual(api.history(self.owner)['items'], [second, first])
                self.assertFalse(api.state(self.owner)['writes_allowed'])
                self.assertEqual(business_schema.financial_accounting_horizon(restored), horizon)
                with self.assertRaises(Problem) as denied: api.confirm(self.owner, command)
                self.assertEqual(denied.exception.status, 409)
                self.assertIsNone(denied.exception.request_resolution)
            finally: restored.db.close()
            frozen = release.snapshot_fingerprint(target)
            for table, value in before.items():
                if table.startswith('business_accounting_'): self.assertEqual(frozen[table], value, table)
            operator = PostgresOffice(target)
            try:
                evidence = components_fixture.evidence_for(operator, report)
                self.assertEqual(evidence['schema'], 15)
                old = {**evidence, 'schema': 7, 'accounting_horizon': dict(schema_version=6,
                    **{key: horizon[key] for key in H6_FIELDS})}
                wrong = {**evidence, 'accounting_horizon': {**horizon, 'profile': {**horizon['profile'], 'sha256': '0' * 64}}}
                for invalid in (old, wrong):
                    with self.assertRaises((Problem, ValueError)): components_fixture.approve(operator, invalid)
                    self.assertEqual(release.snapshot_fingerprint(target), frozen)
                approved = components_fixture.approve(operator, evidence)
                self.assertEqual(components_fixture.approve(operator, evidence), approved)
            finally: operator.db.close()
            restored = PostgresOffice(runtime)
            try:
                api = self.module.AccountingPreparationProfile(restored)
                self.assertEqual(api.confirm(self.owner, command), first)
                self.assertEqual(api.state(self.owner)['current'], second)
                business_schema.validate_integrity(restored)
            finally: restored.db.close()
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)


@unittest.skipUnless(journey.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class ProfileMigrationPostgres(unittest.TestCase):
    def test_real_r2_migration_preserves_all_old_bytes_and_schema7_receipt_cannot_release_new_restore(self):
        full = business_schema.registry()
        prior = tuple(spec for spec in full if spec.name not in ('business_accounting_profile', 'business_accounting_euer', 'business_payroll_cash', 'business_bank_reconciliation', 'business_travel_allowances', 'business_accounting_openings', 'business_accounting_asset_openings', 'business_accounting_open_items'))
        fixture = refunds_fixture.VersionedRefundsPostgres(methodName='runTest'); self.addCleanup(fixture.doCleanups)
        with patch.object(business_schema, 'registry', return_value=prior), \
                patch.object(business_schema, 'MODULE_NAMES', tuple(spec.name for spec in prior)):
            fixture.setUp()
            seed, refund, selected = fixture.mixed()
            returned, return_command = fixture.confirm(refund, selected)
            _, receipt, unused = fixture.components.cash('26.44')
            positive, positive_command = fixture.capacity.confirm(receipt)
            horizon = business_schema.financial_accounting_horizon(fixture.office)
            self.assertEqual(horizon['schema_version'], 6)
            before = release.snapshot_fingerprint(journey.DSN); fixture.office.db.close()
            with components_fixture.disposable_restore(fixture.runtime) as (target, runtime, report):
                operator = PostgresOffice(target)
                try:
                    evidence = components_fixture.evidence_for(operator, report)
                    self.assertEqual(evidence['schema'], 7)
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
                        self.assertEqual(business_schema.financial_accounting_horizon(operator)['schema_version'], 14)
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
        module = importlib.import_module('business_accounting_profile')
        office = PostgresOffice(fixture.runtime)
        try:
            current = business_schema.financial_accounting_horizon(office)
            self.assertEqual(dict(schema_version=6, **{key: current[key] for key in H6_FIELDS}), horizon)
            self.assertEqual(set(current['profile']['table_counts'].values()), {0})
            api = module.AccountingPreparationProfile(office)
            self.assertEqual((api.state(fixture.owner)['current'], api.history(fixture.owner)['total']), (None, 0))
            self.assertEqual(fixture.module.VersionedRefundOrigins(office).confirm(fixture.owner, refund['id'], return_command), returned)
            self.assertEqual(fixture.capacity.module.ReusableDocumentComponents(office).confirm(fixture.owner, receipt['id'], positive_command), positive)
            self.assertEqual(fixture.refunds.module.RefundOrigins(office).confirm(fixture.owner, seed['refund']['id'], seed['command']), seed['returned'])
            business_schema.validate_integrity(office)
        finally: office.db.close()
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), after)
        with components_fixture.disposable_restore(fixture.runtime) as (target, runtime, report):
            self.assertNotEqual(report['restore_id'], evidence['restore_id'])
            operator = PostgresOffice(target)
            try:
                frozen = release.snapshot_fingerprint(target)
                for invalid in (evidence, {**evidence, 'restore_id': report['restore_id']}):
                    with self.assertRaises((Problem, ValueError)): components_fixture.approve(operator, invalid)
                    self.assertEqual(release.snapshot_fingerprint(target), frozen)
                latest = components_fixture.evidence_for(operator, report)
                self.assertEqual(latest['schema'], 15)
                self.assertEqual(set(latest['accounting_horizon']['profile']['table_counts'].values()), {0})
                components_fixture.approve(operator, latest)
            finally: operator.db.close()
            restored = PostgresOffice(runtime)
            try:
                api = module.AccountingPreparationProfile(restored)
                body = preview_body(api.state(fixture.owner))
                preview = api.preview(fixture.owner, body)
                saved = api.confirm(fixture.owner, request(**body, preview_hash=preview['preview_hash'], confirmation=True))
                self.assertEqual(saved['profile'], declared_profile())
                self.assertEqual(saved['revision'], 1)
            finally: restored.db.close()
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), after)


if __name__ == '__main__':
    unittest.main()
