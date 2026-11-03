"""Additional payment allocation under real PostgreSQL roles and transactions.

Only the guarded disposable loopback database is used. Real invoice issuance,
MFA, preserved E1a proofs and immutable export bytes are exercised without a
bank/provider or any tax calculation.
"""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from datetime import datetime, timezone
import hashlib
import importlib
import json
import tempfile
import threading
import unittest
from unittest.mock import patch
import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

import business_schema
from business_adapters import Adapters
from business_documents import Documents, render_prepared
from business_finance import Finance
from core import Problem
from online import release, test_online as base, test_business_journey_pg as journey
from online.backup import backup
from online.restore import complete_restore, restore
from online.store import PostgresOffice, migrate
from online import test_postgres_accounting_integration as accounting_fixture
from online.test_postgres_accounting_integration import issuer_settings, invoice_data


request = journey.request


@unittest.skipUnless(journey.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class AllocationPostgres(unittest.TestCase):
    call = accounting_fixture.AccountingPostgres.call
    login = accounting_fixture.AccountingPostgres.login
    issue = accounting_fixture.AccountingPostgres.issue
    payment_record = accounting_fixture.AccountingPostgres.payment_record
    new_account = accounting_fixture.AccountingPostgres.new_account
    payment_source = accounting_fixture.AccountingPostgres.payment_source
    import_body = accounting_fixture.AccountingPostgres.import_body
    permission = accounting_fixture.AccountingPostgres.permission

    def setUp(self):
        self.module = importlib.import_module('business_accounting_allocations')
        self.accounting = importlib.import_module('business_accounting')
        journey.BusinessJourneyPostgres.setUp(self)
        self.owner = self.office.user(self.token)
        self.runtime = self.office.db.dsn
        self.project = self.call('POST', '/projects', {'name': 'Synthetic allocation project',
            'customer': 'Synthetic allocation customer'}, status=201).json['id']
        self.call('POST', '/business/settings/branding', issuer_settings(self.today))
        self.invoice = self.issue(self.project)
        self.pdf = Documents(self.office).archive(self.owner, self.invoice['id'], 'pdf')
        self.payment = self.payment_record('receipt', '130.00', [(self.invoice['id'], '59.50')])
        self.account = self.new_account('SYNTHETIC-ALLOCATION')
        self.cash_body = self.import_body()
        self.cash = self.call('POST', '/business/accounting/events/import-payment', self.cash_body, status=201).json
        self.api = self.module.PaymentAllocations(self.office)
        self.path = '/business/accounting/allocations/payments/' + self.payment['id']

    def proposal(self, *, payment=None, document=None, amount='59.50', token='owner'):
        payment = payment or self.payment['id']
        document = document or self.invoice['id']
        path = '/business/accounting/allocations/payments/' + payment
        state = self.call('GET', path, token=token).json
        candidates = self.call('GET', path + '/candidates', token=token).json['items']
        candidate = next(item for item in candidates if item['document_id'] == document)
        body = dict(source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
            customer_id=candidate['customer_id'], document_id=document, document_state_hash=candidate['document_state_hash'],
            amount=amount, reason='Synthetic explicit allocation evidence')
        preview = self.call('POST', path + '/preview', body, token=token).json
        return body, preview, request(**body, preview_hash=preview['preview_hash'], confirmation=True)

    def other_project(self):
        project = self.call('POST', '/projects', {'name': 'Other synthetic allocation project',
            'customer': 'Other temporary synthetic customer'}, status=201).json['id']
        self.call('POST', '/projects/' + project + '/customer', {'customer_id': self.invoice['customer_id']})
        return project

    def bookkeeper(self):
        user = self.call('POST', '/users', {'email': 'allocation@example.test',
            'password': 'Synthetic-allocation-password-123', 'role': 'technician'}, status=201).json['id']
        self.call('POST', '/assignments', {'project_id': self.project, 'user_id': user})
        for name in ('accounting.read', 'accounting.prepare', 'finance.read', 'finance.write'):
            self.permission(user, name)
        return user, self.login('allocation@example.test', 'Synthetic-allocation-password-123')

    def test_http_preview_assign_replay_effective_op_and_export_preserve_original_e1a(self):
        self.assertTrue(business_schema.require_runtime_security(self.office))
        before = release.snapshot_fingerprint(journey.DSN)
        _, preview, body = self.proposal()
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
        self.assertEqual((preview['unallocated_before'], preview['unallocated_after'], preview['open_after']),
                         ('70.50', '11.00', '0.00'))
        entry = self.call('POST', self.path + '/assign', body, status=201).json
        self.assertEqual(self.call('POST', self.path + '/assign', body, status=201).json, entry)
        self.call('POST', self.path + '/assign', {**body, 'request_id': uuid.uuid4().hex}, status=409)
        state = self.call('GET', self.path).json
        self.assertEqual((state['revision'], state['allocated_amount'], state['unallocated_amount']), (1, '119.00', '11.00'))
        self.assertEqual(state['source_hash'], self.cash['source']['source_hash'])
        self.assertEqual(self.call('POST', '/business/accounting/events/import-payment', self.cash_body, status=201).json, self.cash)
        self.assertEqual(self.call('GET', '/business/accounting/events/' + self.cash['id']).json, self.cash)
        finance = Finance(self.office)
        payment = next(row for row in finance.payments(self.owner)['items'] if row['id'] == self.payment['id'])
        self.assertEqual(payment['allocations'], [{'document_id': self.invoice['id'], 'amount': '119.00'}])
        self.assertEqual(payment['unallocated'], '11.00')
        item = next(row for row in finance.open_items(self.owner)['items'] if row['id'] == self.invoice['id'])
        self.assertEqual((item['paid'], item['open']), ('119.00', '0.00'))
        adapters = Adapters(self.office)
        adapter = adapters.save(self.owner, request(name='Synthetic effective payment export', profile='lexware_review_json_v1', enabled=True))
        exported = adapters.export_data(self.owner, adapter['id'], request(document_ids=[self.invoice['id']],
            include_payments=True, mapping={self.invoice['id']: {'remote_contact_id': 'SYNTHETIC-CONTACT'}}))
        import base64
        payload = json.loads(base64.b64decode(exported['result']['artifact_base64']))
        self.assertEqual(payload['payments_snapshot'][0]['selected_allocation_total'], '119.00')
        self.payment_record('refund', '19.00', [(self.invoice['id'], '19.00')])
        self.assertEqual(self.api.state(self.owner, self.payment['id'])['unallocated_amount'], '11.00')
        self.assertEqual(finance._payment_sum(self.invoice['id']), Decimal('100.00'))
        after = release.snapshot_fingerprint(journey.DSN)
        for table, fingerprint in before.items():
            if table.startswith('business_accounting_') and not table.startswith('business_accounting_allocation_'):
                self.assertEqual(after[table], fingerprint, table)
        self.assertEqual(Documents(self.office).archive(self.owner, self.invoice['id'], 'pdf'), self.pdf)
        self.assertTrue(self.module.validate_integrity(self.office))
        self.assertTrue(self.accounting.validate_integrity(self.office))

    def test_new_project_revokes_payment_event_and_frozen_export_scope_but_not_invoice_aggregate(self):
        user, token = self.bookkeeper()
        actor = self.office.user(token)
        adapters = Adapters(self.office)
        adapter = adapters.save(self.owner, request(name='Synthetic historical payment export', profile='lexware_review_json_v1', enabled=True))
        export_body = request(document_ids=[self.invoice['id']], include_payments=True,
            mapping={self.invoice['id']: {'remote_contact_id': 'SYNTHETIC-CONTACT'}})
        exported = adapters.export_data(actor, adapter['id'], export_body)
        original_cash = self.call('GET', '/business/accounting/events/' + self.cash['id'], token=token).json
        other = self.other_project()
        invoice = self.issue(other)
        _, _, command = self.proposal(document=invoice['id'], amount='70.50')
        self.call('POST', self.path + '/assign', command, status=201)
        for path in (self.path, '/business/accounting/events/' + self.cash['id']):
            self.call('GET', path, token=token, status=404)
        self.assertNotIn(self.payment['id'], [row['id'] for row in Finance(self.office).payments(actor)['items']])
        self.assertNotIn(self.cash['id'], [row['id'] for row in self.accounting.Accounting(self.office).events(actor)['items']])
        for read in (lambda: adapters.export_data(actor, adapter['id'], export_body), lambda: adapters._run(exported['id'], actor)):
            with self.assertRaises(Problem) as denied:
                read()
            self.assertIn(denied.exception.status, (403, 404))
        item = next(row for row in Finance(self.office).open_items(actor)['items'] if row['id'] == self.invoice['id'])
        self.assertEqual((item['paid'], item['open']), ('59.50', '59.50'))
        self.call('POST', '/assignments', {'project_id': other, 'user_id': user})
        self.assertEqual(adapters.export_data(actor, adapter['id'], export_body), exported)
        self.assertEqual(self.call('GET', '/business/accounting/events/' + self.cash['id'], token=token).json, original_cash)
        self.assertEqual(self.call('POST', self.path + '/assign', command, status=201).json['amount'], '70.50')
        # Originally private payments stay private even after assignment to A.
        private = self.payment_record('receipt', '10.00', [])
        source = self.payment_source(private['id'])
        cash = self.accounting.Accounting(self.office).import_payment(self.owner, self.import_body(source=source))
        _, _, assign = self.proposal(payment=private['id'], amount='10.00')
        self.api.assign(self.owner, private['id'], assign)
        with self.assertRaises(Problem) as private_denied:
            self.accounting.Accounting(self.office).event(actor, cash['id'])
        self.assertEqual(private_denied.exception.status, 403)

    def compete(self, operations):
        barrier = threading.Barrier(len(operations))
        def run(operation):
            office = PostgresOffice(self.runtime)
            try:
                barrier.wait(timeout=5)
                try:
                    return 200, operation(office)
                except Problem as error:
                    return error.status, None
            finally:
                office.db.close()
        with ThreadPoolExecutor(max_workers=len(operations)) as workers:
            return list(workers.map(run, operations))

    def test_two_connections_cannot_allocate_same_source_rest_to_different_invoices(self):
        first, second = self.issue(self.project), self.issue(self.project)
        commands = [self.proposal(document=invoice['id'], amount='70.50')[2] for invoice in (first, second)]
        results = self.compete([lambda office, command=command: self.module.PaymentAllocations(office).assign(
            self.owner, self.payment['id'], command) for command in commands])
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        self.assertEqual(self.api.state(self.owner, self.payment['id'])['unallocated_amount'], '0.00')
        self.assertEqual(self.api.history(self.owner, self.payment['id'])['total'], 1)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_additional_allocation_and_legacy_receipt_compete_for_same_invoice_rest(self):
        command = self.proposal()[2]
        payment_body = request(source_id='synthetic-parallel-receipt', kind='receipt', amount='59.50',
            currency='EUR', booking_date=self.today, reference='Synthetic parallel source',
            allocations=[{'document_id': self.invoice['id'], 'amount': '59.50'}])
        results = self.compete([
            lambda office: self.module.PaymentAllocations(office).assign(self.owner, self.payment['id'], command),
            lambda office: Finance(office).record_payment(self.owner, payment_body)])
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        self.assertEqual(Finance(self.office)._payment_sum(self.invoice['id']), Decimal('119.00'))
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_refund_race_uses_effective_paid_and_changes_frozen_preview_state(self):
        command = self.proposal()[2]
        refund_body = request(source_id='synthetic-parallel-refund', kind='refund', amount='59.50',
            currency='EUR', booking_date=self.today, reference='Synthetic parallel refund',
            allocations=[{'document_id': self.invoice['id'], 'amount': '59.50'}])
        results = self.compete([
            lambda office: self.module.PaymentAllocations(office).assign(self.owner, self.payment['id'], command),
            lambda office: Finance(office).record_payment(self.owner, refund_body)])
        self.assertEqual(results[1][0], 200)
        self.assertIn(results[0][0], (200, 409))
        self.assertEqual(Finance(self.office)._payment_sum(self.invoice['id']),
                         Decimal('59.50') if results[0][0] == 200 else Decimal('0.00'))
        if results[0][0] == 409:
            self.api.assign(self.owner, self.payment['id'], self.proposal()[2])
        self.assertEqual(Finance(self.office)._payment_sum(self.invoice['id']), Decimal('59.50'))
        refunds = [request(**{**refund_body, 'request_id': uuid.uuid4().hex,
                              'source_id': 'synthetic-next-refund-' + str(index)}) for index in range(2)]
        more = self.compete([lambda office, body=body: Finance(office).record_payment(self.owner, body) for body in refunds])
        self.assertEqual(sorted(status for status, _ in more), [200, 409])
        self.assertEqual(Finance(self.office)._payment_sum(self.invoice['id']), Decimal('0.00'))
        self.assertEqual(self.api.state(self.owner, self.payment['id'])['unallocated_amount'], '11.00')
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_runtime_acl_and_real_failure_after_entry_roll_back_history_request_and_audit(self):
        command = self.proposal()[2]
        request_table = next(table for table in self.module.protected_tables() if table.endswith('_requests'))
        with psycopg.connect(journey.DSN) as admin:
            admin.execute('SET LOCAL ROLE "smartplan-migrator"')
            admin.execute("CREATE FUNCTION synthetic_allocation_failure() RETURNS trigger LANGUAGE plpgsql AS $$ "
                          "BEGIN RAISE EXCEPTION 'synthetic allocation receipt failure'; END; $$")
            admin.execute(sql.SQL('CREATE TRIGGER synthetic_allocation_failure BEFORE INSERT ON {} '
                'FOR EACH ROW EXECUTE FUNCTION synthetic_allocation_failure()').format(sql.Identifier(request_table)))
        before = release.snapshot_fingerprint(journey.DSN)
        try:
            with self.assertRaisesRegex(psycopg.Error, 'synthetic allocation receipt failure'):
                self.api.assign(self.owner, self.payment['id'], command)
            self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
        finally:
            with psycopg.connect(journey.DSN) as admin:
                admin.execute(sql.SQL('DROP TRIGGER synthetic_allocation_failure ON {}').format(sql.Identifier(request_table)))
                admin.execute('DROP FUNCTION synthetic_allocation_failure()')
        self.api.assign(self.owner, self.payment['id'], command)
        before = release.snapshot_fingerprint(journey.DSN)
        for table in self.module.protected_tables():
            self.assertGreater(self.office.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0], 0)
            column = self.office.db.execute('SELECT * FROM ' + table + ' LIMIT 1').description[0].name
            for statement in ('UPDATE ' + table + ' SET ' + column + '=' + column, 'DELETE FROM ' + table, 'TRUNCATE ' + table):
                with self.subTest(statement=statement), self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db:
                        self.office.db.execute(statement)
            with psycopg.connect(journey.DSN, autocommit=True) as admin:
                for statement in ('UPDATE ' + table + ' SET ' + column + '=' + column, 'DELETE FROM ' + table):
                    with self.assertRaises(psycopg.Error):
                        with admin.transaction():
                            admin.execute('SET LOCAL ROLE "smartplan-migrator"')
                            admin.execute(statement)
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_real_restore_preserves_assignments_and_requires_current_horizon(self):
        command = self.proposal()[2]
        entry = self.api.assign(self.owner, self.payment['id'], command)
        horizon = business_schema.financial_accounting_horizon(self.office)
        self.assertGreaterEqual(horizon['schema_version'], 2)
        before = release.snapshot_fingerprint(journey.DSN)
        self.office.db.close()
        migrate(journey.DSN, owner_role='smartplan-migrator', compatibility_mode='business', require_business_modules=True)
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
        target = make_conninfo(journey.DSN, dbname='smartplan_release_check')
        runtime = make_conninfo(self.runtime, dbname='smartplan_release_check')
        release.validate_dsns(journey.DSN, target, test_mode=True)
        with psycopg.connect(journey.DSN, autocommit=True) as admin:
            if admin.execute("SELECT 1 FROM pg_database WHERE datname='smartplan_release_check'").fetchone():
                raise RuntimeError('Disposable restore target exists; preserve and inspect it.')
            admin.execute('CREATE DATABASE smartplan_release_check OWNER "smartplan-migrator" TEMPLATE template0')
        try:
            with tempfile.TemporaryDirectory(prefix='synthetic-allocation-restore-') as directory:
                report = restore(backup(journey.DSN, directory), journey.DSN, target, privileged_operator=True, test_mode=True)
            verifier = PostgresOffice(runtime, allow_restore_pending=True)
            try:
                complete_restore(verifier)
            finally:
                verifier.db.close()
            restored = PostgresOffice(runtime)
            try:
                api = self.module.PaymentAllocations(restored)
                self.assertFalse(api.state(self.owner, self.payment['id'])['writes_allowed'])
                self.assertEqual(api.history(self.owner, self.payment['id'])['items'], [entry])
                self.assertEqual(business_schema.financial_accounting_horizon(restored), horizon)
                with self.assertRaises(Problem) as denied:
                    api.assign(self.owner, self.payment['id'], command)
                self.assertEqual(denied.exception.status, 409)
            finally:
                restored.db.close()
            frozen = release.snapshot_fingerprint(target)
            for table, fingerprint in before.items():
                if table.startswith('business_accounting_') or table in (
                    'business_documents', 'business_document_archives', 'business_payments', 'business_payment_allocations'):
                    self.assertEqual(frozen[table], fingerprint, table)
            operator = PostgresOffice(target)
            try:
                evidence = dict(schema=horizon['schema_version'] + 1, restore_id=report['restore_id'], reviewed_by='Synthetic operator',
                    reviewed_at=datetime.now(timezone.utc).isoformat(), outbound_reconciled=True,
                    number_horizons=[dict(company_id=row['company_id'], series=row['series'], year=row['year'],
                        last_value=row['next_value'] - 1) for row in operator.db.execute('SELECT * FROM business_document_counters')],
                    accounting_horizon=horizon, accounting_reconciled=True,
                    accounting_external_review=dict(reviewed_since_backup=True,
                        evidence_sha256=hashlib.sha256(b'Synthetic independent allocation reconciliation').hexdigest(),
                        note='Synthetic payment, original allocations and new assignments reviewed since backup.'))
                old = {**evidence, 'schema': 2, 'accounting_horizon': horizon['prejournal']}
                wrong = {**evidence, 'accounting_horizon': {**horizon,
                    'allocations': {**horizon['allocations'], 'sha256': '0' * 64}}}
                for invalid in (old, wrong):
                    with self.assertRaises((Problem, ValueError)):
                        business_schema.reconcile_financial_restore(operator, invalid, 'b' * 64)
                    self.assertEqual(release.snapshot_fingerprint(target), frozen)
                digest = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()
                approved = business_schema.reconcile_financial_restore(operator, evidence, digest)
                self.assertEqual(business_schema.reconcile_financial_restore(operator, evidence, digest), approved)
            finally:
                operator.db.close()
            restored = PostgresOffice(runtime)
            try:
                api = self.module.PaymentAllocations(restored)
                self.assertEqual(api.assign(self.owner, self.payment['id'], command), entry)
                self.assertEqual(self.accounting.Accounting(restored).import_payment(self.owner, self.cash_body), self.cash)
                self.assertEqual(Finance(restored)._payment_sum(self.invoice['id']), Decimal('119.00'))
                self.assertTrue(self.module.validate_integrity(restored))
                business_schema.validate_integrity(restored)
            finally:
                restored.db.close()
            self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
        finally:
            with psycopg.connect(journey.DSN, autocommit=True) as admin:
                admin.execute('DROP DATABASE smartplan_release_check')


@unittest.skipUnless(journey.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class AllocationMigrationPostgres(unittest.TestCase):
    def test_additive_migration_retains_existing_e1a_proofs_invoice_and_payment_bytes(self):
        accounting = importlib.import_module('business_accounting')
        allocations = importlib.import_module('business_accounting_allocations')
        prior = tuple(spec for spec in business_schema.registry() if spec.name not in
                      ('business_accounting_allocations', 'business_accounting_components', 'business_accounting_refunds', 'business_accounting_capacity'))
        with patch.object(business_schema, 'registry', return_value=prior):
            base.reset()
            bootstrap = PostgresOffice(journey.DSN)
            try:
                owner_id = bootstrap.add_user('allocation-migration@example.test', 'Synthetic-migration-password-123', 'owner')
                actor = dict(bootstrap.db.execute('SELECT * FROM users WHERE id=?', (owner_id,)).fetchone())
                project = bootstrap.add_project(actor, 'Synthetic prior allocation project', 'Synthetic customer')
            finally:
                bootstrap.db.close()
            with psycopg.connect(journey.DSN) as admin:
                if not admin.execute("SELECT 1 FROM pg_roles WHERE rolname='smartplan-online'").fetchone():
                    admin.execute('CREATE ROLE "smartplan-online" LOGIN')
                admin.execute(sql.SQL('ALTER ROLE "smartplan-online" PASSWORD {}').format(sql.Literal('synthetic-business-runtime-only')))
            release.secure_database(journey.DSN, test_mode=True)
            runtime = make_conninfo(journey.DSN, user='smartplan-online', password='synthetic-business-runtime-only')
            office = PostgresOffice(runtime)
            try:
                clock = lambda: datetime(2030, 1, 10, 12, tzinfo=timezone.utc)
                documents = Documents(office, clock=clock)
                documents.save_settings(actor, issuer_settings('2030-01-10'))
                draft = documents.create(actor, invoice_data(project, '2030-01-10'))
                prepared = documents.prepare_finalization(actor, draft['id'], draft['revision'])
                invoice = documents.finalize(actor, draft['id'], render_prepared(prepared), uuid.uuid4().hex)
                self.assertEqual(invoice['archive_security'], 'postgresql_runtime_separated')
                pdf = documents.archive(actor, invoice['id'], 'pdf')
                payment = Finance(office, clock=clock).record_payment(actor, request(source_id='synthetic-prior-allocation',
                    kind='receipt', amount='130.00', currency='EUR', booking_date='2030-01-10', reference='Synthetic prior payment',
                    allocations=[{'document_id': invoice['id'], 'amount': '59.50'}]))
                api = accounting.Accounting(office, clock=clock)
                account = api.create_account(actor, request(code='SYNTHETIC-PRIOR', name='Synthetic prior account',
                    kind='bank', confirmation=True))
                source = api.payment_sources(actor)['items'][0]
                body = request(payment_id=payment['id'], source_hash=source['source_hash'], account_id=account['id'],
                    account_revision=account['revision'], cash_date='2030-01-10',
                    evidence_reference='SYNTHETIC-PRIOR-PAYMENT', confirmation=True)
                event = api.import_payment(actor, body)
                horizon = accounting.restore_horizon(office)
                self.assertIsNone(allocations.restore_horizon(office))
                before = release.snapshot_fingerprint(journey.DSN)
            finally:
                office.db.close()
        migrate(journey.DSN, owner_role='smartplan-migrator', compatibility_mode='business', require_business_modules=True)
        release.secure_database(journey.DSN, test_mode=True)
        after = release.snapshot_fingerprint(journey.DSN)
        for table, fingerprint in before.items():
            if table != 'business_schema_migrations':
                self.assertEqual(after[table], fingerprint, table)
        migrate(journey.DSN, owner_role='smartplan-migrator', compatibility_mode='business', require_business_modules=True)
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), after)
        office = PostgresOffice(runtime)
        try:
            self.assertTrue(business_schema.require_runtime_security(office))
            self.assertEqual(accounting.Accounting(office).import_payment(actor, body), event)
            self.assertEqual(accounting.restore_horizon(office), horizon)
            self.assertEqual(Documents(office).get(actor, invoice['id']), invoice)
            self.assertEqual(Documents(office).archive(actor, invoice['id'], 'pdf'), pdf)
            state = allocations.PaymentAllocations(office).state(actor, payment['id'])
            self.assertEqual((state['revision'], state['unallocated_amount'], state['source_hash']),
                             (0, '70.50', source['source_hash']))
            self.assertTrue(allocations.validate_integrity(office))
            business_schema.validate_integrity(office)
        finally:
            office.db.close()


if __name__ == '__main__':
    unittest.main()
