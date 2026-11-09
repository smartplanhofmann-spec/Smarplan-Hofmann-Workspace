"""Real MFA/HTTP and local operator boundaries for documentary components.

Supplier evidence uses ordinary SQLite finance routes. The separate customer
fixture explicitly uses the existing SyntheticDocuments issuer; PostgreSQL
issuance policy and runtime/operator roles have their own integration suite.
No provider, bank, real customer or live database is involved.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from backend.backup import backup
from business_accounting import restore_horizon as prejournal_horizon
from business_accounting_allocations import restore_horizon as allocation_horizon
import business_schema
from core import Office, Problem
from backend.restore import restore
from online import test_accounting_allocations_http as allocation_fixture
from online import test_accounting_http as operator_fixture
from online import test_accounting_journey as journey


COMPONENT_TABLES = ('business_accounting_component_entries', 'business_accounting_component_lines',
                    'business_accounting_component_requests')


class AccountingComponentHTTPTests(unittest.TestCase):
    setUp = operator_fixture.AccountingHTTPTests.setUp
    new_company = operator_fixture.AccountingHTTPTests.new_company
    open_app = operator_fixture.AccountingHTTPTests.open_app
    call = operator_fixture.AccountingHTTPTests.call
    login = operator_fixture.AccountingHTTPTests.login
    user = operator_fixture.AccountingHTTPTests.user
    permission = operator_fixture.AccountingHTTPTests.permission
    payment = operator_fixture.AccountingHTTPTests.payment
    incoming = operator_fixture.AccountingHTTPTests.incoming
    account_record = operator_fixture.AccountingHTTPTests.account_record
    source = operator_fixture.AccountingHTTPTests.source
    payout_body = operator_fixture.AccountingHTTPTests.payout_body
    import_body = operator_fixture.AccountingHTTPTests.import_body
    legacy_sources = operator_fixture.AccountingHTTPTests.legacy_sources
    report = operator_fixture.AccountingHTTPTests.report
    report_hash = staticmethod(operator_fixture.AccountingHTTPTests.report_hash)
    require_reconciliation = operator_fixture.AccountingHTTPTests.require_reconciliation
    imported_payment = allocation_fixture.AccountingAllocationHTTPTests.imported_payment
    synthetic_invoice = allocation_fixture.AccountingAllocationHTTPTests.synthetic_invoice
    assignment = allocation_fixture.AccountingAllocationHTTPTests.assignment

    def supplier_payout(self, company=None, *, receipt=None, amount='59.50'):
        company = company or self.company
        if receipt is None:
            receipt, _ = self.incoming(company)
        source = self.source(company, 'receipts', receipt['id'])
        body = self.payout_body(source, amount=amount)
        event = self.call(company, '/business/accounting/events/payout', body, status=201).json
        return receipt, event

    def component_command(self, event, company=None):
        company = company or self.company
        prefix = '/business/accounting/components/events/' + event['id']
        state = self.call(company, prefix).json
        portions = self.call(company, prefix + '/portions').json
        portion = next(value for value in portions['items'] if value['eligible'])
        self.assertEqual(len(portion['groups']), 1)
        body = dict(source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
            portion_id=portion['portion_id'], portion_state_hash=portion['portion_state_hash'],
            groups=[dict(group_id=portion['groups'][0]['group_id'], amount=portion['amount'])],
            reason='Synthetic explicit documentary distribution; no tax approval')
        preview = self.call(company, prefix + '/preview', body).json
        return prefix, journey.request(**body, preview_hash=preview['preview_hash'], confirmation=True)

    @staticmethod
    def old_horizon(horizon):
        return dict(schema_version=2, prejournal=horizon['prejournal'], allocations=horizon['allocations'])

    def test_payout_and_customer_components_change_only_c1_and_preserve_historical_responses(self):
        receipt, payout = self.supplier_payout()
        payment, customer_event = self.imported_payment()
        invoice = self.synthetic_invoice()
        allocation_path, allocation_command, allocation_entry = self.assignment(payment, invoice)
        office = self.company['office']
        before = business_schema.financial_accounting_horizon(office)
        before_sources = self.legacy_sources(self.company)
        old_cash, old_allocations = prejournal_horizon(office), allocation_horizon(office)
        frozen_e1a = {event['id']: self.call(self.company, '/business/accounting/events/' + event['id']).json
                      for event in (payout, customer_event)}
        self.assertEqual(before['schema_version'], 15)
        self.assertEqual(set(before), {'schema_version', 'prejournal', 'allocations', 'components', 'refunds', 'capacity', 'refunds_v2', 'profile', 'euer', 'payroll_cash', 'bank_reconciliation', 'travel_cash', 'opening_balances', 'historical_assets','opening_items','year_values'})
        for event in (payout, customer_event):
            path, command = self.component_command(event)
            entry = self.call(self.company, path + '/confirm', command, status=201).json
            self.assertEqual((entry['amount'], entry['net'], entry['tax']), ('59.50', '50.00', '9.50'))
            self.assertEqual(self.call(self.company, path + '/confirm', command, status=201).json, entry)
            self.assertEqual(self.call(self.company, path + '/history').json['items'], [entry])
        after = business_schema.financial_accounting_horizon(office)
        self.assertEqual(after['prejournal'], old_cash)
        self.assertEqual(after['allocations'], old_allocations)
        self.assertEqual(after['refunds'], before['refunds'])
        self.assertEqual(after['capacity'], before['capacity'])
        self.assertEqual(after['refunds_v2'], before['refunds_v2'])
        self.assertEqual(self.old_horizon(after), self.old_horizon(before))
        self.assertEqual(after['components']['table_counts'], {table: 2 for table in COMPONENT_TABLES})
        self.assertNotEqual(after['components']['sha256'], before['components']['sha256'])
        self.assertEqual(self.legacy_sources(self.company), before_sources)
        for event in (payout, customer_event):
            self.assertEqual(self.call(self.company, '/business/accounting/events/' + event['id']).json, frozen_e1a[event['id']])
        self.assertEqual(self.call(self.company, allocation_path + '/assign', allocation_command, status=201).json, allocation_entry)
        before_read = '\n'.join(office.db.iterdump())
        self.assertEqual(business_schema.financial_accounting_horizon(office), after)
        self.assertEqual('\n'.join(office.db.iterdump()), before_read)

    def test_new_operator_release_requires_complete_current_scope_even_for_empty_components(self):
        office = self.company['office']
        self.require_reconciliation(office)
        report = self.report(office)
        self.assertEqual(report['schema'], 16)
        self.assertEqual(report['accounting_horizon']['components']['table_counts'], {table: 0 for table in COMPONENT_TABLES})
        before = '\n'.join(office.db.iterdump())
        invalid = [
            {**report, 'schema': 3, 'accounting_horizon': self.old_horizon(report['accounting_horizon'])},
            {**report, 'schema': 2, 'accounting_horizon': report['accounting_horizon']['prejournal']},
            {**report, 'schema': 10},
            {**report, 'accounting_external_review': {**report['accounting_external_review'], 'reviewed_since_backup': False}},
        ]
        for changes in ({'schema_version': True}, {'schema_version': 2}, {'sha256': '0' * 64},
                        {'table_counts': {}}, {'table_counts': {table: True for table in COMPONENT_TABLES}},
                        {'table_counts': {table: -1 for table in COMPONENT_TABLES}},
                        {'table_counts': {**{table: 0 for table in COMPONENT_TABLES}, 'future_table': 0}},
                        {'unexpected': None}):
            changed = deepcopy(report)
            changed['accounting_horizon']['components'].update(changes)
            invalid.append(changed)
        for component in ('prejournal', 'allocations'):
            changed = deepcopy(report)
            changed['accounting_horizon'][component]['sha256'] = '0' * 64
            invalid.append(changed)
        for candidate in invalid:
            with self.subTest(schema=candidate['schema'], horizon=candidate['accounting_horizon']):
                with self.assertRaises((Problem, ValueError)):
                    business_schema.reconcile_local_financial_restore(office, candidate, self.report_hash(candidate), application_stopped=True)
                self.assertEqual('\n'.join(office.db.iterdump()), before)
        approved = business_schema.reconcile_local_financial_restore(office, report, self.report_hash(report), application_stopped=True)
        self.account_record(self.company, 'AFTER-RELEASE')
        current_rows = '\n'.join(office.db.iterdump())
        self.assertEqual(business_schema.reconcile_local_financial_restore(office, report, self.report_hash(report),
                                                                         application_stopped=True), approved)
        self.assertEqual('\n'.join(office.db.iterdump()), current_rows)

    def test_schema3_receipt_survives_real_migration_but_cannot_unlock_a_new_restore(self):
        old_registry = tuple(spec for spec in business_schema.registry()
                             if spec.name not in ('business_accounting_components', 'business_accounting_refunds', 'business_accounting_capacity', 'business_accounting_refunds_v2', 'business_accounting_profile', 'business_accounting_euer', 'business_payroll_cash', 'business_bank_reconciliation', 'business_travel_allowances', 'business_accounting_openings', 'business_accounting_asset_openings', 'business_accounting_open_items','business_accounting_year_openings'))
        with patch.object(business_schema, 'registry', return_value=old_registry):
            company = self.new_company('historical-components')
            account = self.account_record(company)
            payment, event = self.imported_payment(company, account)
            with patch.object(self, 'company', company):
                path, command, entry = self.assignment(payment, self.synthetic_invoice())
            office = company['office']
            self.require_reconciliation(office)
            report = self.report(office)
            self.assertEqual(report['schema'], 3)
            h2 = business_schema.financial_accounting_horizon(office)
            self.assertEqual(h2['schema_version'], 2)
            digest = self.report_hash(report)
            prior = business_schema.reconcile_local_financial_restore(office, report, digest, application_stopped=True)
            frozen_sources = self.legacy_sources(company)
        business_schema.ensure_schema(office)
        business_schema.ensure_schema(office)
        current_horizon = business_schema.financial_accounting_horizon(office)
        self.assertEqual(current_horizon['schema_version'], 15)
        self.assertEqual(self.old_horizon(current_horizon), h2)
        self.assertEqual(self.legacy_sources(company), frozen_sources)
        self.assertEqual(self.call(company, path + '/assign', command, status=201).json, entry)
        self.assertEqual(self.call(company, '/business/accounting/events/' + event['id']).json, event)
        before = '\n'.join(office.db.iterdump())
        self.assertEqual(business_schema.reconcile_local_financial_restore(office, report, digest, application_stopped=True), prior)
        self.assertEqual('\n'.join(office.db.iterdump()), before)
        changed = {**report, 'reviewed_by': 'Changed reviewer'}
        with self.assertRaises(Problem):
            business_schema.reconcile_local_financial_restore(office, changed, self.report_hash(changed), application_stopped=True)
        saved = backup(self.directory / 'historical-components.sqlite3', self.directory / 'historical-components-backup.sqlite3')
        restored = Office(restore(saved, self.directory / 'historical-components-restored.sqlite3'))
        self.addCleanup(restored.db.close)
        restore_id = business_schema.state(restored)['restore_id']
        self.assertNotEqual(restore_id, report['restore_id'])
        frozen_restore = '\n'.join(restored.db.iterdump())
        for obsolete in (report, {**report, 'restore_id': restore_id}):
            with self.assertRaises((Problem, ValueError)):
                business_schema.reconcile_local_financial_restore(restored, obsolete, self.report_hash(obsolete), application_stopped=True)
            self.assertEqual('\n'.join(restored.db.iterdump()), frozen_restore)
        self.assertTrue(business_schema.state(restored)['financial_reconciliation_required'])
        self.assertEqual(business_schema.financial_accounting_horizon(restored), current_horizon)

    def test_real_restore_blocks_new_and_replayed_components_until_read_only_inspect_and_current_scope_release(self):
        receipt, first = self.supplier_payout()
        path, command = self.component_command(first)
        entry = self.call(self.company, path + '/confirm', command, status=201).json
        _, second = self.supplier_payout(receipt=receipt)
        second_path, second_command = self.component_command(second)
        office = self.company['office']
        horizon = business_schema.financial_accounting_horizon(office)
        sources = self.legacy_sources(self.company)
        saved = backup(self.directory / 'alpha.sqlite3', self.directory / 'components-backup.sqlite3')
        target = restore(saved, self.directory / 'components-restored.sqlite3')
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
        evidence = self.directory / 'components-review.json'
        raw = (json.dumps(report, indent=2) + '\n').encode()
        evidence.write_bytes(raw)
        evidence.chmod(0o600)
        restored.db.close()
        office.db.close()
        script = Path(__file__).resolve().parents[2] / 'scripts' / 'reconcile-accounting-restore.py'
        args = [sys.executable, str(script), '--database', str(target)]
        before = hashlib.sha256(target.read_bytes()).hexdigest()
        inspected = subprocess.run(args + ['--inspect'], capture_output=True, text=True, timeout=15)
        self.assertEqual(inspected.returncode, 0, inspected.stderr)
        snapshot = json.loads(inspected.stdout)
        self.assertEqual(snapshot['evidence_schema'], horizon['schema_version'] + 1)
        self.assertEqual(snapshot['accounting_horizon'], horizon)
        self.assertTrue(snapshot['financial_reconciliation_required'])
        for field in ('schema', 'reviewed_by', 'accounting_reconciled', 'accounting_external_review'):
            self.assertNotIn(field, snapshot)
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), before)
        missing = self.directory / 'never-created-components.sqlite3'
        rejected = subprocess.run([sys.executable, str(script), '--database', str(missing), '--inspect'],
                                  capture_output=True, text=True, timeout=15)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertFalse(missing.exists())
        old = {**report, 'schema': 3, 'accounting_horizon': self.old_horizon(horizon)}
        obsolete = self.directory / 'obsolete-components-review.json'
        obsolete.write_text(json.dumps(old), encoding='utf-8')
        obsolete.chmod(0o600)
        rejected = subprocess.run(args + ['--evidence', str(obsolete), '--application-stopped'],
                                  capture_output=True, text=True, timeout=15)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), before)
        completed = subprocess.run(args + ['--evidence', str(evidence), '--application-stopped'],
                                   capture_output=True, text=True, timeout=15)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)['evidence_sha256'], hashlib.sha256(raw).hexdigest())
        replay = subprocess.run(args + ['--evidence', str(evidence), '--application-stopped'], capture_output=True, text=True, timeout=15)
        self.assertEqual(replay.returncode, 0, replay.stderr)
        self.assertEqual(json.loads(replay.stdout), json.loads(completed.stdout))
        reopened = Office(target)
        self.addCleanup(reopened.db.close)
        company['office'] = reopened
        self.open_app(company)
        self.assertEqual(business_schema.financial_accounting_horizon(reopened), horizon)
        self.assertEqual(self.call(company, path + '/confirm', command, status=201).json, entry)
        self.assertEqual(self.legacy_sources(company), sources)
        self.assertEqual(self.call(company, '/business/accounting/events/' + first['id']).json, first)
        self.call(company, second_path + '/confirm', second_command, status=201)

    def test_partial_component_installation_never_falls_back_or_repairs_a_horizon(self):
        for corruption in ('one_table_missing', 'all_tables_missing', 'marker_missing'):
            with self.subTest(corruption=corruption):
                company = self.new_company('damaged-' + corruption.replace('_', '-'))
                office = company['office']
                h1, a1 = prejournal_horizon(office), allocation_horizon(office)
                with office.db:
                    if corruption == 'marker_missing':
                        office.db.execute("DELETE FROM business_schema_migrations WHERE module='business_accounting_components'")
                    else:
                        for table in (('business_accounting_component_requests',) if corruption == 'one_table_missing' else
                                      ('business_accounting_component_requests', 'business_accounting_component_lines', 'business_accounting_component_entries')):
                            office.db.execute('DROP TABLE ' + table)
                before = '\n'.join(office.db.iterdump())
                with self.assertRaises((Problem, ValueError, RuntimeError)):
                    business_schema.financial_accounting_horizon(office)
                self.assertEqual('\n'.join(office.db.iterdump()), before)
                self.assertEqual(prejournal_horizon(office), h1)
                self.assertEqual(allocation_horizon(office), a1)

    def test_methods_parameters_and_nonstaff_tokens_do_not_open_documentary_sources(self):
        _, event = self.supplier_payout()
        path, command = self.component_command(event)
        self.call(self.company, path + '?company_id=foreign', status=400)
        self.call(self.company, path + '/history?limit=1&limit=2', status=400)
        self.call(self.company, path + '/portions?limit=101', status=400)
        self.call(self.company, path + '/confirm', method='GET', status=405)
        self.call(self.company, path, {'unexpected': True}, method='GET', status=400)
        self.call(self.company, path + '/confirm?unexpected=1', command, status=400)
        self.call(self.company, path + '/confirm', {**command, 'actor': {'role': 'owner'}}, status=400)
        grant = self.call(self.company, '/offline/access/v2', {}, status=201).json
        offline = grant['token']
        offline_origin = grant['binding']['instance_id'] + ':' + grant['binding']['account_id']
        # A real accepted bound device reaches its normal project route before
        # accounting denial; a missing-origin rejection would not prove this ACL.
        self.call(self.company, '/projects', token=offline, offline_origin=offline_origin)
        for token in (None, offline, 'SPPT_' + 'p' * 43, 'SPPI_' + 'i' * 43):
            self.call(self.company, path, token=token, offline_origin=offline_origin if token == offline else None,
                      status=403 if token == offline else (401, 403))
        user, token = self.user(self.company)
        self.call(self.company, path, token=token, status=403)
        self.permission(self.company, user, 'accounting.read')
        self.call(self.company, path + '/history', token=token)
        self.call(self.company, path + '/confirm', command, token=token, status=403)
        self.assertEqual(self.call(self.company, path + '/history').json['items'], [])


if __name__ == '__main__':
    unittest.main()
