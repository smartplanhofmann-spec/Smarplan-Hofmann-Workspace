"""Refund origin HTTP boundaries and versioned local restore reconciliation.

Uses real Flask/MFA/SQLite requests with the existing explicit synthetic
invoice issuer. Real PostgreSQL issuance/roles are a separate integration
check. No provider, bank, customer records or live database is involved.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import uuid

from backup import backup
from business_accounting import restore_horizon as prejournal_horizon
from business_accounting_allocations import restore_horizon as allocation_horizon
from business_accounting_components import restore_horizon as component_horizon
import business_schema
from core import Office, Problem
from restore import restore
from online import test_accounting_components_http as component_fixture
from online import test_accounting_journey as journey


REFUND_TABLES = ('business_accounting_refund_entries', 'business_accounting_refund_lines',
                 'business_accounting_refund_requests')


class AccountingRefundHTTPTests(unittest.TestCase):
    setUp = component_fixture.AccountingComponentHTTPTests.setUp
    new_company = component_fixture.AccountingComponentHTTPTests.new_company
    open_app = component_fixture.AccountingComponentHTTPTests.open_app
    call = component_fixture.AccountingComponentHTTPTests.call
    login = component_fixture.AccountingComponentHTTPTests.login
    user = component_fixture.AccountingComponentHTTPTests.user
    permission = component_fixture.AccountingComponentHTTPTests.permission
    payment = component_fixture.AccountingComponentHTTPTests.payment
    account_record = component_fixture.AccountingComponentHTTPTests.account_record
    source = component_fixture.AccountingComponentHTTPTests.source
    import_body = component_fixture.AccountingComponentHTTPTests.import_body
    legacy_sources = component_fixture.AccountingComponentHTTPTests.legacy_sources
    report = component_fixture.AccountingComponentHTTPTests.report
    report_hash = staticmethod(component_fixture.AccountingComponentHTTPTests.report_hash)
    require_reconciliation = component_fixture.AccountingComponentHTTPTests.require_reconciliation
    imported_payment = component_fixture.AccountingComponentHTTPTests.imported_payment
    synthetic_invoice = component_fixture.AccountingComponentHTTPTests.synthetic_invoice
    assignment = component_fixture.AccountingComponentHTTPTests.assignment
    component_command = component_fixture.AccountingComponentHTTPTests.component_command

    def origin_case(self):
        payment, event = self.imported_payment()
        invoice = self.synthetic_invoice()
        allocation_path, allocation_command, allocation_entry = self.assignment(payment, invoice)
        path, command = self.component_command(event)
        entry = self.call(self.company, path + '/confirm', command, status=201).json
        return dict(payment=payment, event=event, invoice=invoice, component_path=path, component_command=command,
            component_entry=entry, allocation_path=allocation_path, allocation_command=allocation_command,
            allocation_entry=allocation_entry)

    def imported_refund(self, invoice, amount='20.00'):
        payment = self.call(self.company, '/business/finance/payments', journey.request(
            source_id='synthetic-refund-origin-' + uuid.uuid4().hex, kind='refund', amount=amount,
            currency='EUR', booking_date='2026-11-02', reference='Synthetic actual customer refund',
            allocations=[dict(document_id=invoice['id'], amount=amount)]), status=200).json
        source = self.source(self.company, 'payments', payment['id'])
        event = self.call(self.company, '/business/accounting/events/import-payment', self.import_body(source), status=201).json
        return payment, event

    def refund_command(self, event, company=None):
        company = company or self.company
        path = '/business/accounting/refunds/events/' + event['id']
        state = self.call(company, path).json
        portion = next(item for item in self.call(company, path + '/portions').json['items'] if item['eligible'])
        origin = self.call(company, path + '/origins?portion_id=' + portion['portion_id']).json['items'][0]
        body = dict(source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
            portion_id=portion['portion_id'], portion_state_hash=portion['portion_state_hash'],
            origins=[dict(entry_id=origin['entry_id'], group_id=origin['group_id'], lot_state_hash=origin['lot_state_hash'], amount=portion['amount'])],
            reason='Synthetic explicit refund source review; capacity remains unreleased')
        preview = self.call(company, path + '/preview', body).json
        return path, journey.request(**body, preview_hash=preview['preview_hash'], confirmation=True)

    @staticmethod
    def historical_h3(horizon):
        return dict(schema_version=3, prejournal=horizon['prejournal'], allocations=horizon['allocations'], components=horizon['components'])

    def test_refund_binding_changes_only_r1_and_preserves_finance_e1a_c1_and_old_replays(self):
        origin = self.origin_case()
        _, event = self.imported_refund(origin['invoice'])
        path, command = self.refund_command(event)
        office = self.company['office']
        before = business_schema.financial_accounting_horizon(office)
        original_sources = self.legacy_sources(self.company)
        payments = self.call(self.company, '/business/finance/payments').json
        open_items = self.call(self.company, '/business/finance/open-items').json
        old_component_state = self.call(self.company, origin['component_path']).json
        self.assertEqual(before['schema_version'], 13)
        self.assertEqual(set(before), {'schema_version', 'prejournal', 'allocations', 'components', 'refunds', 'capacity', 'refunds_v2', 'profile', 'euer', 'payroll_cash', 'bank_reconciliation', 'travel_cash', 'opening_balances', 'historical_assets'})
        entry = self.call(self.company, path + '/confirm', command, status=201).json
        self.assertFalse(entry['capacity_released'])
        self.assertFalse(entry['tax_result_available'])
        self.assertEqual((entry['amount'], entry['net'], entry['tax']), ('20.00', '16.81', '3.19'))
        self.assertEqual(entry['lines'][0]['component_sequence'], origin['component_entry']['sequence'])
        basis = origin['component_entry']['portion']['groups'][0]
        self.assertEqual({key: entry['lines'][0][key] for key in ('rate', 'category', 'tax_reason')},
                         dict(rate=basis['rate'], category=basis['category'], tax_reason=basis['reason']))
        self.assertEqual(self.call(self.company, path + '/confirm', command, status=201).json, entry)
        after = business_schema.financial_accounting_horizon(office)
        self.assertEqual(self.historical_h3(after), self.historical_h3(before))
        self.assertEqual(after['capacity'], before['capacity'])
        self.assertEqual(after['refunds_v2'], before['refunds_v2'])
        self.assertNotEqual(after['refunds']['sha256'], before['refunds']['sha256'])
        self.assertEqual(after['refunds']['table_counts'], {table: 1 for table in REFUND_TABLES})
        self.assertEqual(self.legacy_sources(self.company), original_sources)
        self.assertEqual(self.call(self.company, '/business/finance/payments').json, payments)
        self.assertEqual(self.call(self.company, '/business/finance/open-items').json, open_items)
        self.assertEqual(self.call(self.company, '/business/accounting/events/' + event['id']).json, event)
        self.assertEqual(self.call(self.company, '/business/accounting/events/' + origin['event']['id']).json, origin['event'])
        self.assertEqual(self.call(self.company, origin['component_path']).json, old_component_state)
        self.assertEqual(self.call(self.company, origin['component_path'] + '/confirm', origin['component_command'], status=201).json, origin['component_entry'])
        self.assertEqual(self.call(self.company, origin['allocation_path'] + '/assign', origin['allocation_command'], status=201).json, origin['allocation_entry'])
        before_read = '\n'.join(office.db.iterdump())
        self.assertEqual(business_schema.financial_accounting_horizon(office), after)
        self.assertEqual('\n'.join(office.db.iterdump()), before_read)

    def test_new_operator_release_requires_complete_current_scope_even_for_empty_refund_scope(self):
        office = self.company['office']
        self.require_reconciliation(office)
        report = self.report(office)
        self.assertEqual(report['schema'], 14)
        self.assertEqual(report['accounting_horizon']['refunds']['table_counts'], {table: 0 for table in REFUND_TABLES})
        before = '\n'.join(office.db.iterdump())
        h3 = self.historical_h3(report['accounting_horizon'])
        invalid = [{**report, 'schema': 4, 'accounting_horizon': h3},
            {**report, 'schema': 3, 'accounting_horizon': {key: value for key, value in h3.items() if key != 'components'} | {'schema_version': 2}},
            {**report, 'schema': 10},
            {**report, 'accounting_external_review': {**report['accounting_external_review'], 'reviewed_since_backup': False}}]
        for changes in ({'schema_version': True}, {'schema_version': 2}, {'sha256': '0' * 64},
                        {'table_counts': {}}, {'table_counts': {table: True for table in REFUND_TABLES}},
                        {'table_counts': {table: -1 for table in REFUND_TABLES}},
                        {'table_counts': {**{table: 0 for table in REFUND_TABLES}, 'unregistered_table': 0}}, {'extra': None}):
            candidate = deepcopy(report)
            candidate['accounting_horizon']['refunds'].update(changes)
            invalid.append(candidate)
        for key in ('prejournal', 'allocations', 'components'):
            candidate = deepcopy(report)
            candidate['accounting_horizon'][key]['sha256'] = '0' * 64
            invalid.append(candidate)
        for candidate in invalid:
            with self.assertRaises((Problem, ValueError)):
                business_schema.reconcile_local_financial_restore(office, candidate, self.report_hash(candidate), application_stopped=True)
            self.assertEqual('\n'.join(office.db.iterdump()), before)
        approved = business_schema.reconcile_local_financial_restore(office, report, self.report_hash(report), application_stopped=True)
        self.account_record(self.company, 'AFTER-REFUND-RELEASE')
        current = '\n'.join(office.db.iterdump())
        self.assertEqual(business_schema.reconcile_local_financial_restore(office, report, self.report_hash(report),
                                                                         application_stopped=True), approved)
        self.assertEqual('\n'.join(office.db.iterdump()), current)

    def test_schema4_receipt_survives_real_migration_but_cannot_unlock_a_new_restore(self):
        old_registry = tuple(spec for spec in business_schema.registry() if spec.name not in ('business_accounting_refunds', 'business_accounting_capacity', 'business_accounting_refunds_v2', 'business_accounting_profile', 'business_accounting_euer', 'business_payroll_cash', 'business_bank_reconciliation', 'business_travel_allowances', 'business_accounting_openings', 'business_accounting_asset_openings'))
        with patch.object(business_schema, 'registry', return_value=old_registry):
            company = self.new_company('historical-refunds')
            account = self.account_record(company)
            with patch.object(self, 'company', company), patch.object(self, 'account', account):
                origin = self.origin_case()
            office = company['office']
            self.require_reconciliation(office)
            report = self.report(office)
            self.assertEqual(report['schema'], 4)
            h3 = business_schema.financial_accounting_horizon(office)
            self.assertEqual(h3['schema_version'], 3)
            digest = self.report_hash(report)
            approved = business_schema.reconcile_local_financial_restore(office, report, digest, application_stopped=True)
            originals = self.legacy_sources(company)
        business_schema.ensure_schema(office)
        business_schema.ensure_schema(office)
        h4 = business_schema.financial_accounting_horizon(office)
        self.assertEqual(h4['schema_version'], 13)
        self.assertEqual(self.historical_h3(h4), h3)
        self.assertEqual(self.legacy_sources(company), originals)
        self.assertEqual(self.call(company, origin['component_path'] + '/confirm', origin['component_command'], status=201).json, origin['component_entry'])
        before = '\n'.join(office.db.iterdump())
        self.assertEqual(business_schema.reconcile_local_financial_restore(office, report, digest, application_stopped=True), approved)
        self.assertEqual('\n'.join(office.db.iterdump()), before)
        altered = {**report, 'reviewed_by': 'Different historical reviewer'}
        with self.assertRaises(Problem):
            business_schema.reconcile_local_financial_restore(office, altered, self.report_hash(altered), application_stopped=True)
        saved = backup(self.directory / 'historical-refunds.sqlite3', self.directory / 'historical-refunds-backup.sqlite3')
        restored = Office(restore(saved, self.directory / 'historical-refunds-restored.sqlite3'))
        self.addCleanup(restored.db.close)
        restore_id = business_schema.state(restored)['restore_id']
        self.assertNotEqual(restore_id, report['restore_id'])
        before = '\n'.join(restored.db.iterdump())
        for stale in (report, {**report, 'restore_id': restore_id}):
            with self.assertRaises((Problem, ValueError)):
                business_schema.reconcile_local_financial_restore(restored, stale, self.report_hash(stale), application_stopped=True)
            self.assertEqual('\n'.join(restored.db.iterdump()), before)
        self.assertTrue(business_schema.state(restored)['financial_reconciliation_required'])
        self.assertEqual(business_schema.financial_accounting_horizon(restored), h4)

    def test_real_restore_blocks_new_and_replayed_refunds_until_current_schema_cli_release(self):
        origin = self.origin_case()
        _, first = self.imported_refund(origin['invoice'])
        path, command = self.refund_command(first)
        entry = self.call(self.company, path + '/confirm', command, status=201).json
        _, second = self.imported_refund(origin['invoice'], '10.00')
        second_path, second_command = self.refund_command(second)
        office = self.company['office']
        horizon = business_schema.financial_accounting_horizon(office)
        originals = self.legacy_sources(self.company)
        saved = backup(self.directory / 'alpha.sqlite3', self.directory / 'refunds-backup.sqlite3')
        target = restore(saved, self.directory / 'refunds-restored.sqlite3')
        restored = Office(target)
        self.addCleanup(restored.db.close)
        self.assertEqual(business_schema.financial_accounting_horizon(restored), horizon)
        company = {**self.company, 'office': restored}
        self.open_app(company)
        company['token'] = self.login(company, 'owner@example.test', 'Synthetic-accounting-owner-password-123', advance=True)
        self.assertFalse(self.call(company, path).json['writes_allowed'])
        self.assertEqual(self.call(company, path + '/history').json['items'], [entry])
        self.call(company, path + '/confirm', command, status=409)
        self.call(company, second_path + '/confirm', second_command, status=409)
        report = self.report(restored)
        evidence = self.directory / 'refunds-review.json'
        raw = (json.dumps(report, indent=2) + '\n').encode()
        evidence.write_bytes(raw)
        evidence.chmod(0o600)
        office.db.close()
        restored.db.close()
        script = Path(__file__).resolve().parents[2] / 'scripts' / 'reconcile-accounting-restore.py'
        args = [sys.executable, str(script), '--database', str(target)]
        before = hashlib.sha256(target.read_bytes()).hexdigest()
        inspected = subprocess.run(args + ['--inspect'], capture_output=True, text=True, timeout=15)
        self.assertEqual(inspected.returncode, 0, inspected.stderr)
        snapshot = json.loads(inspected.stdout)
        self.assertEqual(snapshot['evidence_schema'], 14)
        self.assertEqual(snapshot['accounting_horizon'], horizon)
        self.assertTrue(snapshot['financial_reconciliation_required'])
        for field in ('schema', 'reviewed_by', 'accounting_reconciled', 'accounting_external_review'):
            self.assertNotIn(field, snapshot)
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), before)
        missing = self.directory / 'refund-inspect-must-not-create.sqlite3'
        self.assertNotEqual(subprocess.run([sys.executable, str(script), '--database', str(missing), '--inspect'],
            capture_output=True, text=True, timeout=15).returncode, 0)
        self.assertFalse(missing.exists())
        stale = {**report, 'schema': 4, 'accounting_horizon': self.historical_h3(horizon)}
        old_evidence = self.directory / 'obsolete-refunds-review.json'
        old_evidence.write_text(json.dumps(stale), encoding='utf-8')
        old_evidence.chmod(0o600)
        rejected = subprocess.run(args + ['--evidence', str(old_evidence), '--application-stopped'],
                                  capture_output=True, text=True, timeout=15)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), before)
        released = subprocess.run(args + ['--evidence', str(evidence), '--application-stopped'],
                                  capture_output=True, text=True, timeout=15)
        self.assertEqual(released.returncode, 0, released.stderr)
        self.assertEqual(json.loads(released.stdout)['evidence_sha256'], hashlib.sha256(raw).hexdigest())
        replay = subprocess.run(args + ['--evidence', str(evidence), '--application-stopped'], capture_output=True, text=True, timeout=15)
        self.assertEqual(replay.returncode, 0, replay.stderr)
        self.assertEqual(json.loads(replay.stdout), json.loads(released.stdout))
        reopened = Office(target)
        self.addCleanup(reopened.db.close)
        company['office'] = reopened
        self.open_app(company)
        self.assertEqual(business_schema.financial_accounting_horizon(reopened), horizon)
        self.assertEqual(self.call(company, path + '/confirm', command, status=201).json, entry)
        self.assertEqual(self.legacy_sources(company), originals)
        self.assertEqual(self.call(company, '/business/accounting/events/' + first['id']).json, first)
        self.call(company, second_path + '/confirm', second_command, status=201)
        self.assertEqual(self.call(company, path + '/confirm', command, status=201).json, entry)

    def test_partial_refund_installation_never_falls_back_or_repairs_the_old_horizons(self):
        for corruption in ('one-table', 'all-tables', 'marker'):
            with self.subTest(corruption=corruption):
                company = self.new_company('damaged-refund-' + corruption)
                office = company['office']
                h1, a1, c1 = prejournal_horizon(office), allocation_horizon(office), component_horizon(office)
                with office.db:
                    if corruption == 'marker':
                        office.db.execute("DELETE FROM business_schema_migrations WHERE module='business_accounting_refunds'")
                    else:
                        for table in (('business_accounting_refund_requests',) if corruption == 'one-table' else
                                      ('business_accounting_refund_requests', 'business_accounting_refund_lines', 'business_accounting_refund_entries')):
                            office.db.execute('DROP TABLE ' + table)
                before = '\n'.join(office.db.iterdump())
                with self.assertRaises((Problem, ValueError, RuntimeError)):
                    business_schema.financial_accounting_horizon(office)
                self.assertEqual('\n'.join(office.db.iterdump()), before)
                self.assertEqual(prejournal_horizon(office), h1)
                self.assertEqual(allocation_horizon(office), a1)
                self.assertEqual(component_horizon(office), c1)

    def test_private_origin_access_is_checked_before_candidates_preview_and_bound_history(self):
        origin = self.origin_case()
        _, event = self.imported_refund(origin['invoice'])
        path, command = self.refund_command(event)
        user, token = self.user(self.company)
        for permission in ('accounting.read', 'accounting.prepare'):
            self.permission(self.company, user, permission)
        self.call(self.company, path, token=token)
        portion = self.call(self.company, path + '/portions', token=token).json['items'][0]
        candidates = self.call(self.company, path + '/origins?portion_id=' + portion['portion_id'], token=token).json
        self.assertEqual(candidates, dict(items=[], total=0, next_offset=None, scope='authorized_sources'))
        body = {key: value for key, value in command.items() if key not in ('request_id', 'preview_hash', 'confirmation')}
        self.call(self.company, path + '/preview', body, token=token, status=(403, 404))
        self.call(self.company, path + '/confirm', command, status=201)
        for suffix in ('', '/history', '/portions', '/origins?portion_id=' + portion['portion_id']):
            self.call(self.company, path + suffix, token=token, status=(403, 404))
        self.call(self.company, path + '/confirm', command, token=token, status=(403, 404))

    def test_methods_parameters_and_customer_or_offline_tokens_cannot_access_refund_sources(self):
        origin = self.origin_case()
        _, event = self.imported_refund(origin['invoice'])
        path, command = self.refund_command(event)
        for suffix in ('?company_id=foreign', '/history?limit=1&limit=2', '/portions?limit=101',
                       '/origins', '/origins?portion_id=' + command['portion_id'] + '&sort=amount'):
            self.call(self.company, path + suffix, status=400)
        self.call(self.company, path + '/confirm', method='GET', status=405)
        self.call(self.company, path, {'unexpected': True}, method='GET', status=400)
        for data in ({**command, '_query': {}}, {**command, 'actor': {'role': 'owner'}}):
            self.call(self.company, path + '/confirm', data, status=400)
        self.call(self.company, path + '/confirm?unexpected=1', command, status=400)
        offline = self.call(self.company, '/offline/access', {}, status=201).json['token']
        for token in (None, offline, 'SPPT_' + 'p' * 43, 'SPPI_' + 'i' * 43):
            self.call(self.company, path, token=token, status=(401, 403))
        _, token = self.user(self.company)
        self.call(self.company, path, token=token, status=403)
        self.assertEqual(self.call(self.company, path + '/history').json['items'], [])


if __name__ == '__main__':
    unittest.main()
