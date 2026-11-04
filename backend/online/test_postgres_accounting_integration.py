"""Synthetic accounting prejournal on real, separated-runtime PostgreSQL.

Only the guarded disposable loopback smartplan_check fixture is accepted.
Invoices use the real issuance policy. No bank, provider or tax submission is
called; money movements remain unclassified and do not change existing OPs.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
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
from business_documents import Documents, render_prepared
from business_finance import Finance
from core import Problem
from online import release, test_online as base, test_business_journey_pg as journey
from online.backup import backup
from online.restore import complete_restore, restore
from online.store import migrate, PostgresOffice


request = journey.request
SOURCE_TABLES = ('business_documents', 'business_document_archives', 'business_document_numbers',
    'business_document_counters', 'business_payments', 'business_payment_allocations',
    'business_incoming_receipts', 'business_receipt_reviews')


def issuer_settings(day):
    return request(revision=0, company_name='Synthetic accounting seller',
        address_line='Synthetic seller street 1', postal_code='10115', city='Berlin',
        country='DE', vat_id='DE123456789', email='seller@example.test', issuer_mode='own',
        issuing_enabled=True, cutover_ack=True, cutover_date=day, einvoice_format='none')


def invoice_data(project, day):
    return request(project_id=project, kind='invoice', title='Synthetic PostgreSQL accounting invoice',
        issue_date=day, due_date=day, buyer={'name': 'Synthetic accounting buyer',
            'address_line': 'Synthetic buyer street 2', 'postal_code': '10117', 'city': 'Berlin',
            'country': 'DE', 'email': 'buyer@example.test'},
        positions=[{'description': 'Synthetic service', 'quantity': '2', 'unit': 'HUR',
                    'unit_price_net': '50.00', 'tax_rate': '19', 'kind': 'labor'}])


def review_data(day, revision=0, **changes):
    return request(revision=revision, vendor='Synthetic accounting supplier',
        invoice_number='SYNTHETIC-INCOMING', issue_date=day, currency='EUR',
        status='reviewed', note='Synthetic reviewed original',
        **({'net': '100.00', 'tax': '19.00', 'gross': '119.00'} | changes))


@unittest.skipUnless(journey.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class AccountingPostgres(unittest.TestCase):
    login = journey.BusinessJourneyPostgres.login

    def call(self, method, path, body=None, *, token='owner', status=200):
        bearer = self.token if token == 'owner' else token
        response = self.client.open('/api/v1' + path, method=method,
            base_url='https://office.example.test', json=body,
            headers={'Authorization': 'Bearer ' + bearer} if bearer else {})
        self.assertEqual(response.status_code, status, (method, path, response.status_code))
        return response

    def setUp(self):
        self.module = importlib.import_module('business_accounting')
        journey.BusinessJourneyPostgres.setUp(self)
        self.owner = self.office.user(self.token)
        self.runtime = self.office.db.dsn
        self.project = self.call('POST', '/projects', {'name': 'Synthetic accounting project',
            'customer': 'Synthetic accounting customer'}, status=201).json['id']
        self.call('POST', '/business/settings/branding', issuer_settings(self.today))
        self.invoice = self.issue(self.project)
        self.pdf = self.call('GET', '/business/documents/' + self.invoice['id'] + '/pdf').data
        self.payment = self.payment_record('receipt', '119.00', [(self.invoice['id'], '119.00')])
        self.refund = self.payment_record('refund', '11.90', [(self.invoice['id'], '11.90')])
        self.incoming = self.receipt_record(self.pdf)
        self.account = self.new_account('SYNTHETIC-BANK')
        self.api = self.module.Accounting(self.office)

    def issue(self, project):
        draft = self.call('POST', '/business/documents', invoice_data(project, self.today)).json
        final = self.call('POST', '/business/documents/' + draft['id'] + '/finalize',
            request(revision=draft['revision'])).json
        self.assertEqual((final['status'], final['archive_security']), ('final', 'postgresql_runtime_separated'))
        return final

    def payment_record(self, kind, amount, allocations):
        return self.call('POST', '/business/finance/payments', request(
            source_id='synthetic-payment-' + uuid.uuid4().hex, kind=kind, amount=amount,
            currency='EUR', booking_date=self.today, reference='Synthetic original payment',
            allocations=[{'document_id': identifier, 'amount': assigned} for identifier, assigned in allocations])).json

    def receipt_record(self, original):
        captured = self.call('POST', '/business/finance/receipts', request(project_id=self.project,
            filename='synthetic-accounting-original.pdf', media_type='application/pdf',
            original_base64=base64.b64encode(original).decode(), note='Synthetic source original')).json
        return self.call('POST', '/business/finance/receipts/' + captured['id'], review_data(self.today)).json

    def new_account(self, code):
        return self.call('POST', '/business/accounting/accounts', request(code=code,
            name='Synthetic account ' + code, kind='bank', confirmation=True), status=201).json

    def payment_source(self, identifier, *, token='owner'):
        rows = self.call('GET', '/business/accounting/sources/payments', token=token).json['items']
        return next(row for row in rows if row['payment_id'] == identifier)

    def receipt_source(self, identifier=None):
        rows = self.call('GET', '/business/accounting/sources/receipts').json['items']
        return next(row for row in rows if row['receipt_id'] == (identifier or self.incoming['id']))

    def import_body(self, *, source=None, account=None, **changes):
        source = source or self.payment_source(self.payment['id'])
        account = account or self.account
        return request(**(dict(payment_id=source['payment_id'], source_hash=source['source_hash'],
            account_id=account['id'], account_revision=account['revision'], cash_date=self.today,
            evidence_reference='SYNTHETIC-' + uuid.uuid4().hex, confirmation=True) | changes))

    def payout_body(self, *, source=None, account=None, amount='59.50', **changes):
        source = source or self.receipt_source()
        account = account or self.account
        return request(**({key: source[key] for key in
            ('receipt_id', 'source_hash', 'review_revision', 'review_sha256', 'original_sha256')} |
            dict(account_id=account['id'], account_revision=account['revision'],
                 expected_cash_revision=source['cash_revision'], amount=amount, cash_date=self.today,
                 evidence_reference='SYNTHETIC-PAYOUT-' + uuid.uuid4().hex,
                 reference='Synthetic manually confirmed payout', confirmation=True) | changes))

    def fingerprints(self):
        values = release.snapshot_fingerprint(journey.DSN)
        return {table: values[table] for table in SOURCE_TABLES}

    def permission(self, user, name, *, scope='*', effect='allow', revision=0):
        return self.call('POST', '/business/settings/permissions', request(user_id=user,
            permission=name, scope=scope, effect=effect, revision=revision)).json

    def test_real_final_invoice_receipt_and_refund_import_preserve_allocations_op_and_originals(self):
        self.assertTrue(business_schema.require_runtime_security(self.office))
        before = self.fingerprints()
        open_items = Finance(self.office).open_items(self.owner)
        status = self.call('GET', '/business/accounting/status').json
        self.assertEqual((status['profile_status'], status['tax_status'], status['tax_result_available']),
                         ('unconfigured', 'unconfigured', False))
        source = self.payment_source(self.payment['id'])
        self.assertEqual((source['kind'], source['direction'], source['amount'], source['unallocated']),
                         ('receipt', 'in', '119.00', '0.00'))
        self.assertEqual(len(source['allocations']), 1)
        allocation = source['allocations'][0]
        self.assertEqual((allocation['document_id'], allocation['number'], allocation['project_id'], allocation['amount']),
                         (self.invoice['id'], self.invoice['number'], self.project, '119.00'))
        self.assertEqual(allocation['pdf_sha256'], hashlib.sha256(self.pdf).hexdigest())
        body = self.import_body(source=source)
        event = self.call('POST', '/business/accounting/events/import-payment', body, status=201).json
        self.assertEqual(event['source']['snapshot']['allocations'], source['allocations'])
        self.assertEqual(event['classification_status'], 'unclassified')
        self.assertIn('tax_profile_unconfigured', event['unresolved_reasons'])
        self.assertEqual(self.call('POST', '/business/accounting/events/import-payment', body, status=201).json, event)
        self.call('POST', '/business/accounting/events/import-payment',
            {**body, 'request_id': uuid.uuid4().hex}, status=409)
        refund_source = self.payment_source(self.refund['id'])
        refund = self.call('POST', '/business/accounting/events/import-payment',
            self.import_body(source=refund_source), status=201).json
        self.assertEqual((refund['direction'], refund['amount']), ('out', '11.90'))
        self.assertIn('refund_origin_unresolved', refund['unresolved_reasons'])
        self.assertEqual(self.fingerprints(), before)
        self.assertEqual(Finance(self.office).open_items(self.owner), open_items)
        self.assertEqual(Documents(self.office).archive(self.owner, self.invoice['id'], 'pdf'), self.pdf)
        reopened = PostgresOffice(self.runtime)
        try:
            api = self.module.Accounting(reopened)
            self.assertEqual(api.event(self.owner, event['id']), event)
            self.assertEqual(api.import_payment(self.owner, body), event)
            self.assertTrue(self.module.validate_integrity(reopened))
            business_schema.validate_integrity(reopened)
        finally:
            reopened.db.close()

    def test_mixed_project_payment_requires_every_source_and_fresh_global_rights_before_replay(self):
        other = self.call('POST', '/projects', {'name': 'Other synthetic accounting project',
            'customer': 'Other synthetic customer'}, status=201).json['id']
        invoice = self.issue(other)
        mixed = self.payment_record('receipt', '20.00', [(self.invoice['id'], '10.00'), (invoice['id'], '10.00')])
        user = self.call('POST', '/users', {'email': 'accounting@example.test',
            'password': 'Synthetic-accounting-password-123', 'role': 'technician'}, status=201).json['id']
        self.call('POST', '/assignments', {'project_id': self.project, 'user_id': user})
        token = self.login('accounting@example.test', 'Synthetic-accounting-password-123')
        for name in ('accounting.read', 'accounting.prepare'):
            self.call('POST', '/business/settings/permissions', request(user_id=user,
                permission=name, scope=self.project, effect='allow', revision=0), status=400)
        self.permission(user, 'finance.read', scope=self.project)
        self.call('GET', '/business/accounting/status', token=token, status=403)
        grants = {name: self.permission(user, name) for name in ('accounting.read', 'accounting.prepare', 'finance.read')}
        visible = self.call('GET', '/business/accounting/sources/payments', token=token).json
        self.assertEqual(visible['scope'], 'authorized_sources')
        self.assertNotIn('hidden_count', visible)
        self.assertEqual(visible['total'], 2)
        self.assertNotIn(mixed['id'], [row['payment_id'] for row in visible['items']])
        mixed_body = self.import_body(source=self.payment_source(mixed['id']))
        self.call('POST', '/business/accounting/events/import-payment', mixed_body, token=token, status=404)
        self.call('POST', '/assignments', {'project_id': other, 'user_id': user})
        event = self.call('POST', '/business/accounting/events/import-payment', mixed_body, token=token, status=201).json
        self.assertEqual(len(event['source']['snapshot']['allocations']), 2)
        self.call('POST', '/assignments', {'project_id': other, 'user_id': user, 'remove': True})
        self.call('POST', '/business/accounting/events/import-payment', mixed_body, token=token, status=404)
        self.call('GET', '/business/accounting/events/' + event['id'], token=token, status=404)
        self.assertEqual(self.call('GET', '/business/accounting/events', token=token).json['total'], 0)
        own_body = self.import_body()
        self.call('POST', '/business/accounting/events/import-payment', own_body, token=token, status=201)
        self.permission(user, 'accounting.prepare', effect='deny', revision=grants['accounting.prepare']['revision'])
        self.call('POST', '/business/accounting/events/import-payment', own_body, token=token, status=403)
        self.assertEqual(self.api.events(self.owner)['total'], 2)

    def test_partial_payout_frozen_review_account_and_duplicate_original(self):
        before = self.fingerprints()
        body = self.payout_body()
        event = self.call('POST', '/business/accounting/events/payout', body, status=201).json
        self.assertEqual((event['amount'], event['direction']), ('59.50', 'out'))
        source = self.receipt_source()
        self.assertEqual((source['cash_revision'], source['paid_amount'], source['remaining_amount']), (1, '59.50', '59.50'))
        duplicate = self.receipt_record(self.pdf)
        duplicate_source = self.receipt_source(duplicate['id'])
        self.assertEqual((duplicate_source['payable'], duplicate_source['blocked_reason']), (False, 'duplicate_original'))
        self.call('POST', '/business/accounting/events/payout', self.payout_body(source=duplicate_source), status=409)
        changed = self.call('POST', '/business/accounting/accounts/' + self.account['id'], request(
            revision=self.account['revision'], name='Synthetic renamed inactive account', active=False, confirmation=True)).json
        self.assertEqual(changed['revision'], 2)
        self.call('POST', '/business/finance/receipts/' + self.incoming['id'],
            review_data(self.today, revision=1, net='120.00', tax='22.80', gross='142.80'))
        source = self.receipt_source()
        self.assertEqual((source['payable'], source['blocked_reason']), (False, 'review_changed'))
        self.assertEqual(self.call('POST', '/business/accounting/events/payout', body, status=201).json, event)
        self.assertEqual(self.call('GET', '/business/accounting/events/' + event['id']).json, event)
        self.call('POST', '/business/accounting/events/payout', self.payout_body(source=source,
            account=self.new_account('SYNTHETIC-OTHER')), status=409)
        self.assertEqual(Finance(self.office).receipt_original(self.owner, self.incoming['id'])[0], self.pdf)
        after = self.fingerprints()
        for table in SOURCE_TABLES:
            if table not in ('business_incoming_receipts', 'business_receipt_reviews'):
                self.assertEqual(after[table], before[table], table)
        self.assertTrue(self.module.validate_integrity(self.office))

    def compete(self, invoke, values):
        barrier = threading.Barrier(len(values))

        def run(value):
            office = PostgresOffice(self.runtime)
            try:
                barrier.wait(timeout=5)
                try:
                    return 201, invoke(self.module.Accounting(office), value)
                except Problem as error:
                    return error.status, None
            finally:
                office.db.close()

        with ThreadPoolExecutor(max_workers=len(values)) as workers:
            return list(workers.map(run, values))

    def test_separate_connections_same_payment_across_accounts_commit_once(self):
        other = self.new_account('SYNTHETIC-OTHER')
        source = self.payment_source(self.payment['id'])
        before = self.fingerprints()
        results = self.compete(lambda api, body: api.import_payment(self.owner, body),
            [self.import_body(source=source, account=account) for account in (self.account, other)])
        self.assertEqual(sorted(status for status, _ in results), [201, 409])
        self.assertEqual(self.api.events(self.owner)['total'], 1)
        self.assertEqual(self.fingerprints(), before)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_separate_connections_remaining_payout_across_accounts_commit_once(self):
        self.api.payout(self.owner, self.payout_body())
        source = self.receipt_source()
        other = self.new_account('SYNTHETIC-OTHER')
        results = self.compete(lambda api, body: api.payout(self.owner, body),
            [self.payout_body(source=source, account=account) for account in (self.account, other)])
        self.assertEqual(sorted(status for status, _ in results), [201, 409])
        final = self.receipt_source()
        self.assertEqual((final['cash_revision'], final['paid_amount'], final['remaining_amount'], final['blocked_reason']),
                         (2, '119.00', '0.00', 'paid'))
        self.assertEqual(self.api.events(self.owner)['total'], 2)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_separate_connections_account_revision_conflict_preserves_frozen_event(self):
        event = self.api.import_payment(self.owner, self.import_body())
        bodies = [request(revision=1, name='Synthetic changed ' + name, active=True, confirmation=True) for name in ('A', 'B')]
        results = self.compete(lambda api, body: api.update_account(self.owner, self.account['id'], body), bodies)
        self.assertEqual(sorted(status for status, _ in results), [201, 409])
        current = next(row for row in self.api.accounts(self.owner)['items'] if row['id'] == self.account['id'])
        self.assertEqual(current['revision'], 2)
        self.assertEqual(self.api.event(self.owner, event['id']), event)
        self.assertEqual(event['account'], self.account)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_history_runtime_acl_and_migration_role_guards(self):
        self.api.import_payment(self.owner, self.import_body())
        self.api.payout(self.owner, self.payout_body())
        before = release.snapshot_fingerprint(journey.DSN)
        for table in self.module.protected_tables():
            column = self.office.db.execute('SELECT * FROM ' + table + ' LIMIT 1').description[0].name
            self.assertGreater(self.office.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0], 0, table)
            for command in ('UPDATE ' + table + ' SET ' + column + '=' + column,
                            'DELETE FROM ' + table, 'TRUNCATE ' + table):
                with self.subTest(table=table, command=command), self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db:
                        self.office.db.execute(command)
            with psycopg.connect(journey.DSN, autocommit=True) as admin:
                for command in ('UPDATE ' + table + ' SET ' + column + '=' + column, 'DELETE FROM ' + table):
                    with self.subTest(table=table, guard=command), self.assertRaises(psycopg.Error):
                        with admin.transaction():
                            admin.execute('SET LOCAL ROLE "smartplan-migrator"')
                            admin.execute(command)
        for command in ('CREATE TABLE business_forbidden_accounting(id TEXT)',
                        'ALTER TABLE business_accounting_cash_events DISABLE TRIGGER USER',
                        'DROP TABLE business_accounting_cash_events', 'SET ROLE "smartplan-migrator"'):
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with self.office.db:
                    self.office.db.execute(command)
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)

    def test_failure_on_source_link_rolls_back_event_sequence_receipt_and_audit(self):
        body = self.import_body()
        with psycopg.connect(journey.DSN) as admin:
            admin.execute('SET LOCAL ROLE "smartplan-migrator"')
            admin.execute("CREATE FUNCTION synthetic_accounting_failure() RETURNS trigger LANGUAGE plpgsql AS $$ "
                          "BEGIN RAISE EXCEPTION 'synthetic accounting source failure'; END; $$")
            admin.execute('CREATE TRIGGER synthetic_accounting_failure BEFORE INSERT ON business_accounting_source_links '
                          'FOR EACH ROW EXECUTE FUNCTION synthetic_accounting_failure()')
        before = release.snapshot_fingerprint(journey.DSN)
        try:
            with self.assertRaisesRegex(psycopg.Error, 'synthetic accounting source failure'):
                self.api.import_payment(self.owner, body)
            self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
        finally:
            with psycopg.connect(journey.DSN) as admin:
                admin.execute('DROP TRIGGER synthetic_accounting_failure ON business_accounting_source_links')
                admin.execute('DROP FUNCTION synthetic_accounting_failure()')
        event = self.api.import_payment(self.owner, body)
        self.assertEqual(event['sequence'], 1)
        self.assertEqual(self.api.events(self.owner)['total'], 1)
        self.assertTrue(self.module.validate_integrity(self.office))

    def test_normal_migration_retains_events_restore_requires_exact_independent_accounting_reconciliation(self):
        import_body = self.import_body()
        imported = self.api.import_payment(self.owner, import_body)
        payout_body = self.payout_body()
        paid = self.api.payout(self.owner, payout_body)
        refund_body = self.import_body(source=self.payment_source(self.refund['id']))
        remaining_body = self.payout_body()
        horizon = self.module.restore_horizon(self.office)
        self.assertEqual((horizon['schema_version'], horizon['cash_events_count'], horizon['max_sequence']), (1, 2, 2))
        before = release.snapshot_fingerprint(journey.DSN)
        self.office.db.close()
        migrate(journey.DSN, owner_role='smartplan-migrator', compatibility_mode='business', require_business_modules=True)
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
        normal = PostgresOffice(self.runtime)
        try:
            self.assertTrue(self.module.Accounting(normal).status(self.owner)['writes_allowed'])
            self.assertEqual(self.module.Accounting(normal).import_payment(self.owner, import_body), imported)
            self.assertEqual(self.module.restore_horizon(normal), horizon)
        finally:
            normal.db.close()
        target = make_conninfo(journey.DSN, dbname='smartplan_release_check')
        target_runtime = make_conninfo(self.runtime, dbname='smartplan_release_check')
        release.validate_dsns(journey.DSN, target, test_mode=True)
        with psycopg.connect(journey.DSN, autocommit=True) as admin:
            if admin.execute("SELECT 1 FROM pg_database WHERE datname='smartplan_release_check'").fetchone():
                raise RuntimeError('Disposable restore target already exists; preserve and inspect it.')
            admin.execute('CREATE DATABASE smartplan_release_check OWNER "smartplan-migrator" TEMPLATE template0')
        try:
            with tempfile.TemporaryDirectory(prefix='synthetic-accounting-pg-restore-') as directory:
                saved = backup(journey.DSN, directory)
                report = restore(saved, journey.DSN, target, privileged_operator=True, test_mode=True)
            self.assertTrue(report['restore_pending'])
            verifier = PostgresOffice(target_runtime, allow_restore_pending=True)
            try:
                self.assertFalse(complete_restore(verifier)['restore_pending'])
            finally:
                verifier.db.close()
            restored = PostgresOffice(target_runtime)
            try:
                api = self.module.Accounting(restored)
                self.assertTrue(business_schema.require_runtime_security(restored))
                self.assertFalse(api.status(self.owner)['writes_allowed'])
                self.assertEqual(api.event(self.owner, imported['id']), imported)
                self.assertEqual(api.event(self.owner, paid['id']), paid)
                self.assertEqual(self.module.restore_horizon(restored), horizon)
                for operation in (lambda: api.import_payment(self.owner, import_body),
                                  lambda: api.import_payment(self.owner, refund_body),
                                  lambda: api.payout(self.owner, payout_body),
                                  lambda: api.payout(self.owner, remaining_body),
                                  lambda: api.create_account(self.owner, request(code='BLOCKED', name='Blocked',
                                      kind='bank', confirmation=True))):
                    with self.assertRaises(Problem) as blocked:
                        operation()
                    self.assertEqual(blocked.exception.status, 409)
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with restored.db:
                        restored.db.execute('UPDATE business_restore_state SET financial_reconciliation_required=0')
                self.assertEqual(Documents(restored).archive(self.owner, self.invoice['id'], 'pdf'), self.pdf)
            finally:
                restored.db.close()
            restored_snapshot = release.snapshot_fingerprint(target)
            for table, fingerprint in before.items():
                if table.startswith('business_accounting_') or table in SOURCE_TABLES:
                    self.assertEqual(restored_snapshot[table], fingerprint, table)
            self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
            operator = PostgresOffice(target)
            try:
                operator_horizon = business_schema.financial_accounting_horizon(operator)
                evidence = dict(schema=operator_horizon['schema_version'] + 1, restore_id=report['restore_id'], reviewed_by='Synthetic independent operator',
                    reviewed_at=datetime.now(timezone.utc).isoformat(), outbound_reconciled=True,
                    number_horizons=[dict(company_id=row['company_id'], series=row['series'],
                        year=row['year'], last_value=row['next_value'] - 1)
                        for row in operator.db.execute('SELECT * FROM business_document_counters')],
                    accounting_reconciled=True, accounting_horizon=operator_horizon,
                    accounting_external_review=dict(reviewed_since_backup=True,
                        evidence_sha256=hashlib.sha256(b'Synthetic independent fixture evidence; no live payments').hexdigest(),
                        note='Synthetic operator compared the separately retained test payment inputs since backup.'))
                altered_cash = {**horizon, 'cash_events_count': horizon['cash_events_count'] + 1}
                wrong_horizon = {**evidence, 'accounting_horizon':
                    {**operator_horizon, 'prejournal': altered_cash} if operator_horizon['schema_version'] >= 2 else altered_cash}
                wrong_external = {**evidence, 'accounting_external_review': {**evidence['accounting_external_review'],
                                                                           'reviewed_since_backup': False}}
                obsolete = {key: value for key, value in evidence.items() if not key.startswith('accounting_')}
                obsolete['schema'] = 1
                for wrong in (wrong_horizon, wrong_external, obsolete):
                    with self.assertRaises((Problem, ValueError)):
                        business_schema.reconcile_financial_restore(operator, wrong, 'b' * 64)
                    self.assertEqual(release.snapshot_fingerprint(target), restored_snapshot)
                digest = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()
                approved = business_schema.reconcile_financial_restore(operator, evidence, digest)
                self.assertTrue(approved['reconciled'])
                self.assertEqual(business_schema.reconcile_financial_restore(operator, evidence, digest), approved)
            finally:
                operator.db.close()
            after = release.snapshot_fingerprint(target)
            for table, fingerprint in restored_snapshot.items():
                if table not in ('business_restore_state', 'business_financial_reconciliations'):
                    self.assertEqual(after[table], fingerprint, table)
            restored = PostgresOffice(target_runtime)
            try:
                api = self.module.Accounting(restored)
                with self.assertRaises(Problem) as forbidden:
                    business_schema.reconcile_financial_restore(restored, evidence, digest)
                self.assertEqual(forbidden.exception.status, 403)
                self.assertTrue(api.status(self.owner)['writes_allowed'])
                self.assertEqual(api.import_payment(self.owner, import_body), imported)
                self.assertEqual(api.payout(self.owner, payout_body), paid)
                refund = api.import_payment(self.owner, refund_body)
                self.assertEqual((refund['direction'], refund['amount']), ('out', '11.90'))
                with self.assertRaises(Problem) as duplicate:
                    api.import_payment(self.owner, {**refund_body, 'request_id': uuid.uuid4().hex})
                self.assertEqual(duplicate.exception.status, 409)
                api.payout(self.owner, remaining_body)
                self.assertEqual(api.events(self.owner)['total'], 4)
                self.assertTrue(self.module.validate_integrity(restored))
                business_schema.validate_integrity(restored)
            finally:
                restored.db.close()
        finally:
            with psycopg.connect(journey.DSN, autocommit=True) as admin:
                admin.execute('DROP DATABASE smartplan_release_check')


@unittest.skipUnless(journey.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class AccountingMigrationPostgres(unittest.TestCase):
    def test_additive_migration_preserves_prior_final_invoice_payment_original_and_signed_report(self):
        module = importlib.import_module('business_accounting')
        prior = tuple(spec for spec in business_schema.registry()
                      if spec.name not in ('business_accounting', 'business_accounting_allocations', 'business_accounting_components', 'business_accounting_refunds', 'business_accounting_capacity', 'business_accounting_refunds_v2', 'business_accounting_profile', 'business_accounting_euer', 'business_payroll_cash', 'business_bank_reconciliation', 'business_travel_allowances', 'business_accounting_openings', 'business_accounting_asset_openings'))
        with patch.object(business_schema, 'registry', return_value=prior):
            base.reset()
            bootstrap = PostgresOffice(journey.DSN)
            try:
                owner_id = bootstrap.add_user('migration@example.test', 'Synthetic-migration-password-123', 'owner')
                owner = dict(bootstrap.db.execute('SELECT * FROM users WHERE id=?', (owner_id,)).fetchone())
                project = bootstrap.add_project(owner, 'Synthetic prior accounting project', 'Synthetic prior customer')
                report = bootstrap.draft(owner, project, 'Servicebericht', 'Synthetic retained original')
                bootstrap.sign(owner, report['id'], report['content_hash'], 'Synthetic signer', [[[0.1, 0.2], [0.8, 0.7]]])
                report_pdf = bootstrap.pdf(owner, report['id'])
            finally:
                bootstrap.db.close()
            with psycopg.connect(journey.DSN) as admin:
                if not admin.execute("SELECT 1 FROM pg_roles WHERE rolname='smartplan-online'").fetchone():
                    admin.execute('CREATE ROLE "smartplan-online" LOGIN')
                admin.execute(sql.SQL('ALTER ROLE "smartplan-online" PASSWORD {}').format(
                    sql.Literal('synthetic-business-runtime-only')))
            release.secure_database(journey.DSN, test_mode=True)
            runtime = make_conninfo(journey.DSN, user='smartplan-online', password='synthetic-business-runtime-only')
            office = PostgresOffice(runtime)
            try:
                clock = lambda: datetime(2030, 1, 10, 12, tzinfo=timezone.utc)
                api = Documents(office, clock=clock)
                api.save_settings(owner, issuer_settings('2030-01-10'))
                draft = api.create(owner, invoice_data(project, '2030-01-10'))
                prepared = api.prepare_finalization(owner, draft['id'], draft['revision'])
                final = api.finalize(owner, draft['id'], render_prepared(prepared), uuid.uuid4().hex)
                self.assertEqual(final['archive_security'], 'postgresql_runtime_separated')
                pdf = api.archive(owner, draft['id'], 'pdf')
                finance = Finance(office, clock=clock)
                payment = finance.record_payment(owner, request(source_id='synthetic-prior-payment', kind='receipt',
                    amount='59.50', currency='EUR', booking_date='2030-01-10', reference='Synthetic retained payment',
                    allocations=[{'document_id': draft['id'], 'amount': '59.50'}]))
                receipt = finance.capture_receipt(owner, request(project_id=project, filename='synthetic-original.pdf',
                    media_type='application/pdf', original_base64=base64.b64encode(pdf).decode()))
                finance.review_receipt(owner, receipt['id'], review_data('2030-01-10'))
                before = release.snapshot_fingerprint(journey.DSN)
                self.assertNotIn('business_accounting_cash_events', before)
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
            self.assertEqual(Documents(office).get(owner, draft['id']), final)
            self.assertEqual(Documents(office).archive(owner, draft['id'], 'pdf'), pdf)
            self.assertEqual(office.pdf(owner, report['id']), report_pdf)
            self.assertEqual(Finance(office).receipt_original(owner, receipt['id'])[0], pdf)
            self.assertEqual(module.Accounting(office).events(owner)['total'], 0)
            self.assertEqual(module.Accounting(office).payment_sources(owner)['items'][0]['payment_id'], payment['id'])
            self.assertTrue(module.validate_integrity(office))
            business_schema.validate_integrity(office)
        finally:
            office.db.close()


if __name__ == '__main__':
    unittest.main()
