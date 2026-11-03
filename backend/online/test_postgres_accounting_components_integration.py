"""Documentary cents with real PostgreSQL issuance, MFA and separated roles.

Only the guarded disposable loopback fixture is reset. These tests neither
create tax results nor call financial providers; old cash and archive proofs
must survive every component operation unchanged.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import importlib
import json
import tempfile
import unittest
from unittest.mock import patch
import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

import business_schema
from business_documents import Documents
from business_finance import Finance
from core import Problem
from online import release, test_business_journey_pg as journey
from online import test_postgres_accounting_integration as accounting_fixture
from online import test_postgres_accounting_allocations_integration as allocation_fixture
from online.backup import backup
from online.restore import complete_restore, restore
from online.store import PostgresOffice, migrate


request = journey.request


def evidence_for(office, report):
    horizon = business_schema.financial_accounting_horizon(office)
    return dict(schema=horizon['schema_version'] + 1, restore_id=report['restore_id'],
        reviewed_by='Synthetic independent component operator',
        reviewed_at=datetime.now(timezone.utc).isoformat(), outbound_reconciled=True,
        number_horizons=[dict(company_id=row['company_id'], series=row['series'], year=row['year'],
            last_value=row['next_value'] - 1) for row in office.db.execute('SELECT * FROM business_document_counters')],
        accounting_horizon=horizon, accounting_reconciled=True,
        accounting_external_review=dict(reviewed_since_backup=True,
            evidence_sha256=hashlib.sha256(b'Synthetic independent documentary cents evidence').hexdigest(),
            note='Synthetic cash, allocation and component evidence independently reviewed.'))


def approve(office, evidence):
    digest = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()
    return business_schema.reconcile_financial_restore(office, evidence, digest)


@contextmanager
def disposable_restore(runtime):
    """Create/drop only our new, guarded target; never reuse an existing DB."""
    target = make_conninfo(journey.DSN, dbname='smartplan_release_check')
    target_runtime = make_conninfo(runtime, dbname='smartplan_release_check')
    release.validate_dsns(journey.DSN, target, test_mode=True)
    with psycopg.connect(journey.DSN, autocommit=True) as admin:
        if admin.execute("SELECT 1 FROM pg_database WHERE datname='smartplan_release_check'").fetchone():
            raise RuntimeError('Disposable restore target exists; preserve and inspect it.')
        admin.execute('CREATE DATABASE smartplan_release_check OWNER "smartplan-migrator" TEMPLATE template0')
    try:
        with tempfile.TemporaryDirectory(prefix='synthetic-component-restore-') as directory:
            report = restore(backup(journey.DSN, directory), journey.DSN, target,
                             privileged_operator=True, test_mode=True)
        verifier = PostgresOffice(target_runtime, allow_restore_pending=True)
        try:
            complete_restore(verifier)
        finally:
            verifier.db.close()
        yield target, target_runtime, report
    finally:
        with psycopg.connect(journey.DSN, autocommit=True) as admin:
            admin.execute('DROP DATABASE smartplan_release_check')


@unittest.skipUnless(journey.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class ComponentsPostgres(unittest.TestCase):
    call = journey.BusinessJourneyPostgres.call
    login = journey.BusinessJourneyPostgres.login
    payment_record = accounting_fixture.AccountingPostgres.payment_record
    new_account = accounting_fixture.AccountingPostgres.new_account
    payment_source = accounting_fixture.AccountingPostgres.payment_source
    receipt_source = accounting_fixture.AccountingPostgres.receipt_source
    receipt_record = accounting_fixture.AccountingPostgres.receipt_record
    payout_body = accounting_fixture.AccountingPostgres.payout_body
    import_body = accounting_fixture.AccountingPostgres.import_body
    permission = accounting_fixture.AccountingPostgres.permission
    compete = allocation_fixture.AllocationPostgres.compete
    other_project = allocation_fixture.AllocationPostgres.other_project
    bookkeeper = allocation_fixture.AllocationPostgres.bookkeeper

    def setUp(self):
        self.module = importlib.import_module('business_accounting_components')
        self.accounting = importlib.import_module('business_accounting')
        self.allocations = importlib.import_module('business_accounting_allocations')
        journey.BusinessJourneyPostgres.setUp(self)
        self.owner = self.office.user(self.token)
        self.runtime = self.office.db.dsn
        self.project = self.call('POST', '/projects', {'name': 'Synthetic component project',
            'customer': 'Synthetic component customer'}, status=201).json['id']
        self.call('POST', '/business/settings/branding', accounting_fixture.issuer_settings(self.today))
        self.invoice = self.issue(self.project)
        self.account = self.new_account('SYNTHETIC-COMPONENTS')
        self.api = self.module.DocumentComponents(self.office)

    def issue(self, project, positions=None):
        body = accounting_fixture.invoice_data(project, self.today)
        if positions is not None:
            body['positions'] = positions
        draft = self.call('POST', '/business/documents', body).json
        final = self.call('POST', '/business/documents/' + draft['id'] + '/finalize',
                          request(revision=draft['revision'])).json
        self.assertEqual((final['status'], final['archive_security']), ('final', 'postgresql_runtime_separated'))
        return final

    def cash(self, amount, *, document=None, assigned=None, kind='receipt', cash_date=None):
        document = document or self.invoice['id']
        payment = self.payment_record(kind, amount, [(document, assigned or amount)])
        body = self.import_body(source=self.payment_source(payment['id']),
                                **({'cash_date': cash_date} if cash_date else {}))
        event = self.call('POST', '/business/accounting/events/import-payment', body, status=201).json
        return payment, event, body

    def path(self, event):
        return '/business/accounting/components/events/' + event['id']

    def proposal(self, event, *, portion_id=None, groups=None, token='owner'):
        path = self.path(event)
        state = self.call('GET', path, token=token).json
        portions = self.call('GET', path + '/portions', token=token).json['items']
        portion = next((row for row in portions if row['portion_id'] == portion_id), None) if portion_id else portions[0]
        self.assertIsNotNone(portion)
        if groups is None:
            self.assertEqual(len(portion['groups']), 1)
            groups = [{'group_id': portion['groups'][0]['group_id'], 'amount': portion['amount']}]
        body = dict(source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
            portion_id=portion['portion_id'], portion_state_hash=portion['portion_state_hash'], groups=groups,
            reason='Synthetic explicit documentary cent distribution')
        preview = self.call('POST', path + '/preview', body, token=token).json
        return preview, request(**body, preview_hash=preview['preview_hash'], confirmation=True)

    def confirm(self, event, **kwargs):
        preview, body = self.proposal(event, **kwargs)
        entry = self.call('POST', self.path(event) + '/confirm', body,
                          token=kwargs.get('token', 'owner'), status=201).json
        return entry, body

    def assign(self, payment, *, document=None, amount):
        path = '/business/accounting/allocations/payments/' + payment['id']
        state = self.call('GET', path).json
        candidates = self.call('GET', path + '/candidates').json['items']
        candidate = next(row for row in candidates if row['document_id'] == (document or self.invoice['id']))
        body = dict(source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
            customer_id=candidate['customer_id'], document_id=candidate['document_id'],
            document_state_hash=candidate['document_state_hash'], amount=amount,
            reason='Synthetic additional immutable source portion')
        preview = self.call('POST', path + '/preview', body).json
        return self.call('POST', path + '/assign',
            request(**body, preview_hash=preview['preview_hash'], confirmation=True), status=201).json

    def old_fingerprints(self):
        values = release.snapshot_fingerprint(journey.DSN)
        return {name: fingerprint for name, fingerprint in values.items()
                if name.startswith('business_accounting_') and not name.startswith('business_accounting_component_')
                or name in accounting_fixture.SOURCE_TABLES}

    def test_three_payments_cumulative_cents_are_frozen_without_op_or_archive_changes(self):
        rows = [self.cash(amount, cash_date=day) for amount, day in
                (('39.67', self.today), ('39.67', '2020-01-01'), ('39.66', self.today))]
        before = self.old_fingerprints()
        op = Finance(self.office).open_items(self.owner)
        original_horizon = self.accounting.restore_horizon(self.office)
        entries = []
        for (_, event, _), expected in zip(rows, (('33.34', '6.33'), ('33.33', '6.34'), ('33.33', '6.33'))):
            snapshot = release.snapshot_fingerprint(journey.DSN)
            preview, body = self.proposal(event)
            self.assertEqual(release.snapshot_fingerprint(journey.DSN), snapshot)
            self.assertEqual((preview['net'], preview['tax']), expected)
            entry = self.call('POST', self.path(event) + '/confirm', body, status=201).json
            self.assertEqual(self.call('POST', self.path(event) + '/confirm', body, status=201).json, entry)
            entries.append((event, entry, body))
        self.assertEqual(self.old_fingerprints(), before)
        self.assertEqual(Finance(self.office).open_items(self.owner), op)
        self.assertEqual(self.accounting.restore_horizon(self.office), original_horizon)
        reopened = PostgresOffice(self.runtime)
        try:
            api = self.module.DocumentComponents(reopened)
            for event, entry, body in entries:
                self.assertEqual(api.confirm(self.owner, event['id'], body), entry)
                self.assertEqual(api.history(self.owner, event['id'])['items'], [entry])
            self.assertTrue(self.module.validate_integrity(reopened))
            business_schema.validate_integrity(reopened)
        finally:
            reopened.db.close()

    def test_explicit_multiple_groups_share_pool_between_original_and_additional_portions(self):
        invoice = self.issue(self.project, [
            dict(description='Synthetic standard group', quantity='1', unit='C62', unit_price_net='100.00', tax_rate='19'),
            dict(description='Synthetic reduced group', quantity='1', unit='C62', unit_price_net='50.00', tax_rate='7'),
            dict(description='Synthetic zero amount group', quantity='1', unit='C62', unit_price_net='0.00', tax_rate='0')])
        payment, event, _ = self.cash('172.50', document=invoice['id'], assigned='86.25')
        added = self.assign(payment, document=invoice['id'], amount='86.25')
        portions = self.call('GET', self.path(event) + '/portions').json['items']
        self.assertEqual({row['kind'] for row in portions}, {'original_allocation', 'additional_allocation'})
        self.assertEqual(len({row['portion_id'] for row in portions}), 2)
        original = self.office.db.execute('SELECT id FROM business_payment_allocations WHERE payment_id=?', (payment['id'],)).fetchone()['id']
        expected_ids = {hashlib.sha256(json.dumps(dict(kind=kind, id=identifier), sort_keys=True,
            separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
            for kind, identifier in (('original_allocation', original), ('additional_allocation', added['id']))}
        self.assertEqual({row['portion_id'] for row in portions}, expected_ids)
        pool_ids = {group['group_id'] for group in portions[0]['groups']}
        self.assertEqual({group['group_id'] for group in portions[1]['groups']}, pool_ids)
        self.assertEqual(len(pool_ids), 2)
        before = self.old_fingerprints()
        for portion in portions:
            amounts = [{'group_id': group['group_id'], 'amount': '59.50' if group['rate'] == '19' else '26.75'}
                       for group in portion['groups']]
            entry, _ = self.confirm(event, portion_id=portion['portion_id'], groups=amounts)
            self.assertEqual((entry['amount'], entry['net'], entry['tax']), ('86.25', '75.00', '11.25'))
        state = self.call('GET', self.path(event)).json
        self.assertEqual((state['revision'], state['documented_amount'], state['undocumented_amount']), (2, '172.50', '0.00'))
        self.assertEqual(self.old_fingerprints(), before)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_separate_connections_cannot_confirm_same_whole_portion_twice(self):
        _, event, _ = self.cash('59.50')
        _, body = self.proposal(event)
        commands = [body, {**body, 'request_id': uuid.uuid4().hex}]
        result = self.compete([lambda office, command=command: self.module.DocumentComponents(office).confirm(
            self.owner, event['id'], command) for command in commands])
        self.assertEqual(sorted(status for status, _ in result), [200, 409])
        self.assertEqual(self.api.history(self.owner, event['id'])['total'], 1)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_real_postgresql_cent_values_exceed_integer32_without_rounding_or_storage_loss(self):
        invoice = self.issue(self.project, [dict(description='Synthetic large integer-cent evidence',
            quantity='1', unit='C62', unit_price_net='700000000.00', tax_rate='19')])
        _, event, _ = self.cash('833000000.00', document=invoice['id'])
        before = self.old_fingerprints()
        entry, body = self.confirm(event)
        self.assertEqual((entry['amount'], entry['net'], entry['tax']),
                         ('833000000.00', '700000000.00', '133000000.00'))
        self.assertEqual(entry['lines'][0]['remaining_gross'], '0.00')
        self.assertEqual(self.api.confirm(self.owner, event['id'], body), entry)
        self.assertEqual(self.old_fingerprints(), before)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_separate_events_compete_for_last_group_cent_despite_existing_refunds(self):
        invoice = self.issue(self.project, [dict(description='Synthetic exact half cent', quantity='1',
            unit='C62', unit_price_net='0.01', tax_rate='100')])
        events = []
        for index in range(3):
            _, event, _ = self.cash('0.01', document=invoice['id'])
            events.append(event)
            if index < 2:
                self.payment_record('refund', '0.01', [(invoice['id'], '0.01')])
        first, _ = self.confirm(events[0])
        self.assertEqual((first['net'], first['tax']), ('0.00', '0.01'))
        commands = [(event, self.proposal(event)[1]) for event in events[1:]]
        before = self.old_fingerprints()
        result = self.compete([lambda office, event=event, command=command:
            self.module.DocumentComponents(office).confirm(self.owner, event['id'], command)
            for event, command in commands])
        self.assertEqual(sorted(status for status, _ in result), [200, 409])
        winner = next(entry for status, entry in result if status == 200)
        self.assertEqual((winner['net'], winner['tax']), ('0.01', '0.00'))
        self.assertEqual(self.old_fingerprints(), before)
        self.assertEqual(Finance(self.office)._payment_sum(invoice['id']), Decimal('0.01'))
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_runtime_acl_and_sql_failure_roll_back_lines_receipt_and_audit(self):
        _, event, _ = self.cash('59.50')
        _, body = self.proposal(event)
        table = 'business_accounting_component_requests'
        with psycopg.connect(journey.DSN) as admin:
            admin.execute('SET LOCAL ROLE "smartplan-migrator"')
            admin.execute("CREATE FUNCTION synthetic_component_failure() RETURNS trigger LANGUAGE plpgsql AS $$ "
                "BEGIN RAISE EXCEPTION 'synthetic component receipt failure'; END; $$")
            admin.execute(sql.SQL('CREATE TRIGGER synthetic_component_failure BEFORE INSERT ON {} '
                'FOR EACH ROW EXECUTE FUNCTION synthetic_component_failure()').format(sql.Identifier(table)))
        before = release.snapshot_fingerprint(journey.DSN)
        try:
            with self.assertRaisesRegex(psycopg.Error, 'synthetic component receipt failure'):
                self.api.confirm(self.owner, event['id'], body)
            self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
        finally:
            with psycopg.connect(journey.DSN) as admin:
                admin.execute('SET LOCAL ROLE "smartplan-migrator"')
                admin.execute(sql.SQL('DROP TRIGGER synthetic_component_failure ON {}').format(sql.Identifier(table)))
                admin.execute('DROP FUNCTION synthetic_component_failure()')
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

    def test_new_project_scope_revokes_component_reads_and_exact_replay(self):
        payment, event, _ = self.cash('130.00', assigned='59.50')
        user, token = self.bookkeeper()
        entry, body = self.confirm(event, token=token)
        other = self.other_project()
        invoice = self.issue(other)
        self.assign(payment, document=invoice['id'], amount='70.50')
        for suffix in ('', '/portions', '/history'):
            self.call('GET', self.path(event) + suffix, token=token, status=404)
        self.call('POST', self.path(event) + '/confirm', body, token=token, status=404)
        self.call('POST', '/assignments', {'project_id': other, 'user_id': user})
        self.assertEqual(self.call('POST', self.path(event) + '/confirm', body, token=token, status=201).json, entry)
        self.permission(user, 'finance.write', effect='deny', revision=1)
        self.call('POST', self.path(event) + '/confirm', body, token=token, status=403)
        self.assertEqual(self.call('GET', self.path(event) + '/history', token=token).json['items'], [entry])

    def test_supplier_review_change_blocks_new_components_but_preserves_old_replay(self):
        original = Documents(self.office).archive(self.owner, self.invoice['id'], 'pdf')
        self.incoming = self.receipt_record(original)
        events = [self.call('POST', '/business/accounting/events/payout', self.payout_body(), status=201).json
                  for _ in range(2)]
        self.call('POST', '/business/accounting/accounts/' + self.account['id'], request(
            revision=self.account['revision'], name='Synthetic inactive settled account', active=False, confirmation=True))
        entry, body = self.confirm(events[0])
        self.assertEqual((entry['net'], entry['tax']), ('50.00', '9.50'))
        for group in entry['portion']['groups']:
            self.assertIsNone(group['rate']); self.assertIsNone(group['category']); self.assertIsNone(group['reason'])
        second_preview, second_body = self.proposal(events[1])
        self.assertEqual((second_preview['net'], second_preview['tax']), ('50.00', '9.50'))
        self.assertEqual(second_preview['lines'][0]['gross_before'], '59.50')
        self.call('POST', '/business/finance/receipts/' + self.incoming['id'],
            accounting_fixture.review_data(self.today, revision=self.incoming['revision']))
        portions = self.call('GET', self.path(events[1]) + '/portions').json['items']
        self.assertEqual(len(portions), 1)
        self.assertFalse(portions[0]['eligible'])
        self.assertEqual(portions[0]['blocked_reason'], 'review_changed')
        self.call('POST', self.path(events[1]) + '/confirm', second_body, status=409)
        self.assertEqual(self.call('POST', self.path(events[0]) + '/confirm', body, status=201).json, entry)
        self.assertEqual(self.api.history(self.owner, events[0]['id'])['items'], [entry])
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_private_payment_contributes_capacity_without_leaking_foreign_source_ids(self):
        private = self.payment_record('receipt', '20.00', [])
        private_event = self.call('POST', '/business/accounting/events/import-payment',
            self.import_body(source=self.payment_source(private['id'])), status=201).json
        self.assign(private, amount='20.00')
        private_entry, _ = self.confirm(private_event)
        _, public_event, _ = self.cash('20.00')
        user, token = self.bookkeeper()
        self.call('GET', self.path(private_event), token=token, status=403)
        portions = self.call('GET', self.path(public_event) + '/portions', token=token).json
        group = portions['items'][0]['groups'][0]
        self.assertEqual((group['documented_gross'], group['remaining_gross']), ('20.00', '99.00'))
        encoded = json.dumps(portions)
        for forbidden in (private['id'], private_event['id'], private_entry['id'], self.owner['id']):
            self.assertNotIn(forbidden, encoded)
        entry, _ = self.confirm(public_event, token=token)
        self.assertEqual(entry['lines'][0]['gross_before'], '20.00')
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_refund_and_new_receipt_change_finance_but_do_not_reopen_documented_pool(self):
        _, event, _ = self.cash('119.00')
        entry, body = self.confirm(event)
        refund, refund_event, _ = self.cash('19.00', kind='refund')
        state = self.api.state(self.owner, refund_event['id'])
        self.assertEqual((state['source_kind'], state['blocked_reason']), ('customer_refund', 'refund_origin_unresolved'))
        _, replacement, _ = self.cash('19.00')
        portion = self.api.portions(self.owner, replacement['id'])['items'][0]
        self.assertFalse(portion['eligible'])
        self.assertEqual(portion['groups'][0]['remaining_gross'], '0.00')
        before = self.old_fingerprints()
        state = self.api.state(self.owner, replacement['id'])
        invalid = dict(source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
            portion_id=portion['portion_id'], portion_state_hash=portion['portion_state_hash'],
            groups=[dict(group_id=portion['groups'][0]['group_id'], amount='19.00')], reason='Synthetic cannot reuse refunded cents')
        self.call('POST', self.path(replacement) + '/preview', invalid, status=409)
        self.assertEqual(self.api.confirm(self.owner, event['id'], body), entry)
        self.assertEqual(self.old_fingerprints(), before)
        self.assertEqual(Finance(self.office)._payment_sum(self.invoice['id']), Decimal('119.00'))
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_actual_restore_preserves_components_and_requires_current_horizon(self):
        _, event, cash_body = self.cash('119.00')
        entry, body = self.confirm(event)
        horizon = business_schema.financial_accounting_horizon(self.office)
        self.assertGreaterEqual(horizon['schema_version'], 3)
        self.assertEqual(horizon['components']['table_counts'], {
            'business_accounting_component_entries': 1, 'business_accounting_component_lines': 1,
            'business_accounting_component_requests': 1})
        before = release.snapshot_fingerprint(journey.DSN)
        self.office.db.close()
        for _ in range(2):
            migrate(journey.DSN, owner_role='smartplan-migrator', compatibility_mode='business', require_business_modules=True)
            self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
        with disposable_restore(self.runtime) as (target, runtime, report):
            restored = PostgresOffice(runtime)
            try:
                api = self.module.DocumentComponents(restored)
                self.assertFalse(api.state(self.owner, event['id'])['writes_allowed'])
                self.assertEqual(api.history(self.owner, event['id'])['items'], [entry])
                self.assertEqual(business_schema.financial_accounting_horizon(restored), horizon)
                with self.assertRaises(Problem) as denied:
                    api.confirm(self.owner, event['id'], body)
                self.assertEqual(denied.exception.status, 409)
            finally:
                restored.db.close()
            frozen = release.snapshot_fingerprint(target)
            for table, fingerprint in before.items():
                if table.startswith('business_accounting_') or table in accounting_fixture.SOURCE_TABLES:
                    self.assertEqual(frozen[table], fingerprint, table)
            operator = PostgresOffice(target)
            try:
                evidence = evidence_for(operator, report)
                self.assertEqual(evidence['schema'], horizon['schema_version'] + 1)
                old = {**evidence, 'schema': 3, 'accounting_horizon':
                    dict(schema_version=2, prejournal=horizon['prejournal'], allocations=horizon['allocations'])}
                wrong = {**evidence, 'accounting_horizon': {**horizon,
                    'components': {**horizon['components'], 'sha256': '0' * 64}}}
                for invalid in (old, wrong):
                    with self.assertRaises((Problem, ValueError)):
                        approve(operator, invalid)
                    self.assertEqual(release.snapshot_fingerprint(target), frozen)
                approved = approve(operator, evidence)
                self.assertEqual(approve(operator, evidence), approved)
            finally:
                operator.db.close()
            restored = PostgresOffice(runtime)
            try:
                self.assertEqual(self.module.DocumentComponents(restored).confirm(self.owner, event['id'], body), entry)
                self.assertEqual(self.accounting.Accounting(restored).import_payment(self.owner, cash_body), event)
                self.assertTrue(self.module.validate_integrity(restored))
                business_schema.validate_integrity(restored)
            finally:
                restored.db.close()
            self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)


@unittest.skipUnless(journey.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class ComponentMigrationPostgres(unittest.TestCase):
    def test_prior_e1b1_migration_preserves_all_bytes_and_schema3_receipt_cannot_unlock_new_restore(self):
        prior = tuple(spec for spec in business_schema.registry() if spec.name not in
                      ('business_accounting_components', 'business_accounting_refunds', 'business_accounting_capacity', 'business_accounting_refunds_v2', 'business_accounting_profile', 'business_accounting_euer', 'business_payroll_cash', 'business_bank_reconciliation', 'business_travel_allowances'))
        fixture = allocation_fixture.AllocationPostgres(methodName='runTest')
        self.addCleanup(fixture.doCleanups)
        with patch.object(business_schema, 'registry', return_value=prior), \
                patch.object(business_schema, 'MODULE_NAMES', tuple(spec.name for spec in prior)):
            fixture.setUp()
            entry = fixture.api.assign(fixture.owner, fixture.payment['id'], fixture.proposal()[2])
            horizon = business_schema.financial_accounting_horizon(fixture.office)
            self.assertEqual(horizon['schema_version'], 2)
            before = release.snapshot_fingerprint(journey.DSN)
            fixture.office.db.close()
            with disposable_restore(fixture.runtime) as (target, runtime, report):
                operator = PostgresOffice(target)
                try:
                    evidence = evidence_for(operator, report)
                    self.assertEqual(evidence['schema'], 3)
                    approved = approve(operator, evidence)
                finally:
                    operator.db.close()
                old_target = release.snapshot_fingerprint(target)
                # This inner patch temporarily restores the full registry, while
                # the surrounding context retains the real pre-component schema.
                full = self.current_registry
                with patch.object(business_schema, 'registry', return_value=full), \
                        patch.object(business_schema, 'MODULE_NAMES', tuple(spec.name for spec in full)):
                    migrated_target = None
                    for _ in range(2):
                        migrate(target, owner_role='smartplan-migrator', compatibility_mode='business', require_business_modules=True)
                        snapshot = release.snapshot_fingerprint(target)
                        if migrated_target is not None:
                            self.assertEqual(snapshot, migrated_target)
                        migrated_target = snapshot
                    after_target = release.snapshot_fingerprint(target)
                    for table, fingerprint in old_target.items():
                        if table != 'business_schema_migrations':
                            self.assertEqual(after_target[table], fingerprint, table)
                    operator = PostgresOffice(target)
                    try:
                        self.assertGreaterEqual(business_schema.financial_accounting_horizon(operator)['schema_version'], 3)
                        self.assertEqual(approve(operator, evidence), approved)
                    finally:
                        operator.db.close()
                    self.assertEqual(release.snapshot_fingerprint(target), after_target)
        migrated_source = None
        for _ in range(2):
            migrate(journey.DSN, owner_role='smartplan-migrator', compatibility_mode='business', require_business_modules=True)
            snapshot = release.snapshot_fingerprint(journey.DSN)
            if migrated_source is not None:
                self.assertEqual(snapshot, migrated_source)
            migrated_source = snapshot
        release.secure_database(journey.DSN, test_mode=True)
        after = release.snapshot_fingerprint(journey.DSN)
        for table, fingerprint in before.items():
            if table != 'business_schema_migrations':
                self.assertEqual(after[table], fingerprint, table)
        office = PostgresOffice(fixture.runtime)
        try:
            current = business_schema.financial_accounting_horizon(office)
            self.assertEqual(dict(schema_version=2, prejournal=current['prejournal'], allocations=current['allocations']), horizon)
            self.assertEqual(fixture.module.PaymentAllocations(office).history(fixture.owner, fixture.payment['id'])['items'], [entry])
            self.assertEqual(fixture.accounting.Accounting(office).import_payment(fixture.owner, fixture.cash_body), fixture.cash)
            self.assertTrue(importlib.import_module('business_accounting_components').validate_integrity(office))
        finally:
            office.db.close()
        with disposable_restore(fixture.runtime) as (target, runtime, new_report):
            self.assertNotEqual(new_report['restore_id'], evidence['restore_id'])
            operator = PostgresOffice(target)
            try:
                frozen = release.snapshot_fingerprint(target)
                for invalid in (evidence, {**evidence, 'restore_id': new_report['restore_id']}):
                    with self.assertRaises((Problem, ValueError)):
                        approve(operator, invalid)
                    self.assertEqual(release.snapshot_fingerprint(target), frozen)
                self.assertEqual(evidence_for(operator, new_report)['schema'], current['schema_version'] + 1)
                approve(operator, evidence_for(operator, new_report))
            finally:
                operator.db.close()
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), after)

    def setUp(self):
        self.current_registry = business_schema.registry()
