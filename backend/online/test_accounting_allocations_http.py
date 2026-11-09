"""Versioned restore scope and real HTTP boundaries for additive allocations.

Staff uses the real MFA fixture. Allocation mechanics use the repository's
explicit SyntheticDocuments SQLite issuer fixture; actual production invoice
issuance and PostgreSQL operator roles are verified by the separate PG suite.
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
import uuid

from backend.backup import backup
from business_accounting import restore_horizon as prejournal_horizon
import business_schema
from core import Office, Problem
from backend.restore import restore
from online import test_accounting_http as operator_fixture
from online import test_accounting_journey as journey


class AccountingAllocationHTTPTests(unittest.TestCase):
    setUp = operator_fixture.AccountingHTTPTests.setUp
    new_company = operator_fixture.AccountingHTTPTests.new_company
    open_app = operator_fixture.AccountingHTTPTests.open_app
    call = operator_fixture.AccountingHTTPTests.call
    login = operator_fixture.AccountingHTTPTests.login
    user = operator_fixture.AccountingHTTPTests.user
    permission = operator_fixture.AccountingHTTPTests.permission
    payment = operator_fixture.AccountingHTTPTests.payment
    account_record = operator_fixture.AccountingHTTPTests.account_record
    source = operator_fixture.AccountingHTTPTests.source
    import_body = operator_fixture.AccountingHTTPTests.import_body
    legacy_sources = operator_fixture.AccountingHTTPTests.legacy_sources
    report = operator_fixture.AccountingHTTPTests.report
    report_hash = staticmethod(operator_fixture.AccountingHTTPTests.report_hash)
    require_reconciliation = operator_fixture.AccountingHTTPTests.require_reconciliation

    def imported_payment(self, company=None, account=None):
        company = company or self.company
        payment = self.payment(company)
        source = self.source(company, 'payments', payment['id'])
        event = self.call(company, '/business/accounting/events/import-payment',
            self.import_body(source, account=account or self.account), status=201).json
        return payment, event

    def synthetic_invoice(self):
        from business_tests.test_documents import SyntheticDocuments, seed_synthetic_issuer
        from business_documents import render_prepared
        company = self.company
        owner = company['office'].user(company['token'])
        documents = SyntheticDocuments(company['office'])
        documents.save_settings(owner, journey.request(revision=0, company_name='Synthetic seller',
            address_line='Synthetic street 1', postal_code='10115', city='Berlin', country='DE',
            vat_id='DE123456789', email='synthetic@example.test', issuing_enabled=False,
            issuer_mode='own', cutover_ack=True, cutover_date='2026-01-01', einvoice_format='none'))
        seed_synthetic_issuer(documents, owner)
        draft = documents.create(owner, journey.request(project_id=company['project'], kind='invoice',
            title='Synthetic allocation target', issue_date='2026-11-02', due_date='2026-11-16',
            buyer=dict(name='Synthetic customer', address_line='Synthetic street 2', postal_code='10117',
                       city='Berlin', country='DE'),
            positions=[dict(description='Synthetic service', quantity='1', unit='C62', unit_price_net='100.00', tax_rate='19')]))
        prepared = documents.prepare_finalization(owner, draft['id'], draft['revision'])
        return documents.finalize(owner, draft['id'], render_prepared(prepared), uuid.uuid4().hex)

    def assignment(self, payment, invoice):
        prefix = '/business/accounting/allocations/payments/' + payment['id']
        state = self.call(self.company, prefix).json
        candidate = next(item for item in self.call(self.company, prefix + '/candidates').json['items']
                         if item['document_id'] == invoice['id'])
        body = dict(source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
            customer_id=candidate['customer_id'], document_id=invoice['id'], document_state_hash=candidate['document_state_hash'],
            amount='59.50', reason='Synthetic explicit matching of invoice and payment')
        preview = self.call(self.company, prefix + '/preview', body).json
        command = journey.request(**body, preview_hash=preview['preview_hash'], confirmation=True)
        entry = self.call(self.company, prefix + '/assign', command, status=201).json
        return prefix, command, entry

    def test_additional_assignment_changes_only_its_horizon_and_preserves_e1a_source_and_cash_response(self):
        payment, event = self.imported_payment()
        invoice = self.synthetic_invoice()
        office = self.company['office']
        before_sources = self.legacy_sources(self.company)
        before_cash = prejournal_horizon(office)
        before = business_schema.financial_accounting_horizon(office)
        self.assertEqual(set(before), {'schema_version', 'prejournal', 'allocations', 'components', 'refunds', 'capacity', 'refunds_v2', 'profile', 'euer', 'payroll_cash', 'bank_reconciliation', 'travel_cash', 'opening_balances', 'historical_assets','opening_items','year_values'})
        self.assertEqual(before['schema_version'], 15)
        self.assertEqual(before['prejournal'], before_cash)
        self.assertEqual(before_cash['schema_version'], 1)
        _, _, entry = self.assignment(payment, invoice)
        after = business_schema.financial_accounting_horizon(office)
        self.assertEqual(after['prejournal'], before_cash)
        self.assertEqual(after['components'], before['components'])
        self.assertEqual(after['refunds'], before['refunds'])
        self.assertEqual(after['capacity'], before['capacity'])
        self.assertEqual(after['refunds_v2'], before['refunds_v2'])
        self.assertNotEqual(after['allocations']['sha256'], before['allocations']['sha256'])
        self.assertEqual(after['allocations']['table_counts'], {
            'business_accounting_allocation_entries': 1, 'business_accounting_allocation_requests': 1})
        self.assertEqual(self.legacy_sources(self.company), before_sources)
        self.assertEqual(self.call(self.company, '/business/accounting/events/' + event['id']).json, event)
        dump = '\n'.join(office.db.iterdump())
        self.assertEqual(business_schema.financial_accounting_horizon(office), after)
        self.assertEqual('\n'.join(office.db.iterdump()), dump)
        self.assertEqual(entry['amount'], '59.50')

    def test_operator_rejects_downscope_or_incomplete_additional_horizon_even_when_module_is_empty(self):
        office = self.company['office']
        self.require_reconciliation(office)
        report = self.report(office)
        self.assertEqual(report['schema'], 16)
        self.assertTrue(all(count == 0 for count in report['accounting_horizon']['allocations']['table_counts'].values()))
        before = '\n'.join(office.db.iterdump())
        obsolete = {**report, 'schema': 2, 'accounting_horizon': report['accounting_horizon']['prejournal']}
        invalid = [obsolete]
        for change in ({'schema_version': True}, {'sha256': '0' * 64}, {'table_counts': {}},
                       {'table_counts': {'unregistered_table': 0}},
                       {'table_counts': {key: True for key in report['accounting_horizon']['allocations']['table_counts']}}):
            candidate = deepcopy(report)
            candidate['accounting_horizon']['allocations'].update(change)
            invalid.append(candidate)
        wrong_cash = deepcopy(report)
        wrong_cash['accounting_horizon']['prejournal']['sha256'] = '0' * 64
        invalid.append(wrong_cash)
        for candidate in invalid:
            with self.assertRaises((Problem, ValueError)):
                business_schema.reconcile_local_financial_restore(office, candidate, self.report_hash(candidate), application_stopped=True)
            self.assertEqual('\n'.join(office.db.iterdump()), before)
        approved = business_schema.reconcile_local_financial_restore(office, report, self.report_hash(report), application_stopped=True)
        self.assertEqual(approved, business_schema.reconcile_local_financial_restore(office, report,
            self.report_hash(report), application_stopped=True))

    def test_already_approved_schema2_report_replays_after_real_additive_migration_but_cannot_unlock_new_restore(self):
        old_registry = tuple(spec for spec in business_schema.registry()
                             if spec.name not in ('business_accounting_allocations', 'business_accounting_components', 'business_accounting_refunds', 'business_accounting_capacity', 'business_accounting_refunds_v2', 'business_accounting_profile', 'business_accounting_euer', 'business_payroll_cash', 'business_bank_reconciliation', 'business_travel_allowances', 'business_accounting_openings', 'business_accounting_asset_openings', 'business_accounting_open_items','business_accounting_year_openings'))
        with patch.object(business_schema, 'registry', return_value=old_registry):
            company = self.new_company('historical')
            account = self.account_record(company)
            self.imported_payment(company, account)
            office = company['office']
            self.require_reconciliation(office)
            report = self.report(office)
            self.assertEqual(report['schema'], 2)
            self.assertEqual(report['accounting_horizon']['schema_version'], 1)
            digest = self.report_hash(report)
            prior = business_schema.reconcile_local_financial_restore(office, report, digest, application_stopped=True)
            frozen_cash = prejournal_horizon(office)
            frozen_sources = self.legacy_sources(company)
        business_schema.ensure_schema(office)
        business_schema.ensure_schema(office)
        self.assertEqual(prejournal_horizon(office), frozen_cash)
        self.assertEqual(self.legacy_sources(company), frozen_sources)
        self.assertEqual(business_schema.financial_accounting_horizon(office)['schema_version'], 15)
        before_replay = '\n'.join(office.db.iterdump())
        self.assertEqual(business_schema.reconcile_local_financial_restore(office, report, digest,
            application_stopped=True), prior)
        self.assertEqual('\n'.join(office.db.iterdump()), before_replay)
        changed = {**report, 'reviewed_by': 'Different synthetic reviewer'}
        with self.assertRaises(Problem):
            business_schema.reconcile_local_financial_restore(office, changed, self.report_hash(changed), application_stopped=True)
        saved = backup(self.directory / 'historical.sqlite3', self.directory / 'historical-backup.sqlite3')
        restored = Office(restore(saved, self.directory / 'historical-restored.sqlite3'))
        self.addCleanup(restored.db.close)
        self.assertNotEqual(business_schema.state(restored)['restore_id'], report['restore_id'])
        for stale in (report, {**report, 'restore_id': business_schema.state(restored)['restore_id']}):
            with self.assertRaises((Problem, ValueError)):
                business_schema.reconcile_local_financial_restore(restored, stale, self.report_hash(stale), application_stopped=True)
        self.assertTrue(business_schema.state(restored)['financial_reconciliation_required'])
        self.assertEqual(prejournal_horizon(restored), frozen_cash)

    def test_real_restore_and_cli_inspect_bind_both_scopes_and_replay_old_assignment_once(self):
        payment, event = self.imported_payment()
        prefix, command, entry = self.assignment(payment, self.synthetic_invoice())
        office = self.company['office']
        horizon = business_schema.financial_accounting_horizon(office)
        sources = self.legacy_sources(self.company)
        saved = backup(self.directory / 'alpha.sqlite3', self.directory / 'allocation-backup.sqlite3')
        target = restore(saved, self.directory / 'allocation-restored.sqlite3')
        restored = Office(target)
        self.addCleanup(restored.db.close)
        self.assertEqual(business_schema.financial_accounting_horizon(restored), horizon)
        report = self.report(restored)
        company = {**self.company, 'office': restored}
        self.open_app(company)
        company['token'] = self.login(company, 'owner@example.test', 'Synthetic-accounting-owner-password-123', advance=True)
        self.call(company, prefix + '/assign', command, status=409)
        self.assertEqual(self.call(company, prefix + '/history').json['items'], [entry])
        evidence = self.directory / 'allocation-review.json'
        raw = (json.dumps(report, indent=2) + '\n').encode()
        evidence.write_bytes(raw)
        evidence.chmod(0o600)
        restored.db.close()
        office.db.close()
        script = Path(__file__).resolve().parents[2] / 'scripts' / 'reconcile-accounting-restore.py'
        args = [sys.executable, str(script), '--database', str(target)]
        database_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        inspected = subprocess.run(args + ['--inspect'], capture_output=True, text=True, timeout=15)
        self.assertEqual(inspected.returncode, 0, inspected.stderr)
        inspection = json.loads(inspected.stdout)
        self.assertEqual(inspection['evidence_schema'], horizon['schema_version'] + 1)
        self.assertEqual(inspection['accounting_horizon'], horizon)
        self.assertNotIn('accounting_reconciled', inspection)
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), database_hash)
        completed = subprocess.run(args + ['--evidence', str(evidence), '--application-stopped'],
            capture_output=True, text=True, timeout=15)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)['evidence_sha256'], hashlib.sha256(raw).hexdigest())
        reopened = Office(target)
        self.addCleanup(reopened.db.close)
        company['office'] = reopened
        self.open_app(company)
        self.assertEqual(self.call(company, prefix + '/assign', command, status=201).json, entry)
        self.assertEqual(self.call(company, '/business/accounting/events/' + event['id']).json, event)
        self.assertEqual(self.legacy_sources(company), sources)
        self.assertEqual(business_schema.financial_accounting_horizon(reopened), horizon)

    def test_unknown_filters_fields_methods_and_nonstaff_tokens_cannot_access_allocation_routes(self):
        payment, _ = self.imported_payment()
        prefix = '/business/accounting/allocations/payments/' + payment['id']
        self.call(self.company, prefix + '?company_id=foreign', status=400)
        self.call(self.company, prefix + '/history?limit=1&limit=2', status=400)
        self.call(self.company, prefix + '/candidates?limit=101', status=400)
        self.call(self.company, prefix + '/assign', method='GET', status=405)
        self.call(self.company, prefix + '/history', {}, status=405)
        self.call(self.company, prefix + '/preview', {'actor': {'role': 'owner'}}, status=400)
        grant = self.call(self.company, '/offline/access/v2', {}, status=201).json
        offline = grant['token']
        offline_origin = grant['binding']['instance_id'] + ':' + grant['binding']['account_id']
        # A real accepted bound device reaches its normal project route before
        # accounting denial; a missing-origin rejection would not prove this ACL.
        self.call(self.company, '/projects', token=offline, offline_origin=offline_origin)
        for token in (None, offline, 'SPPT_' + 'p' * 43, 'SPPI_' + 'i' * 43):
            self.call(self.company, prefix, token=token, offline_origin=offline_origin if token == offline else None,
                      status=403 if token == offline else (401, 403))
        user, token = self.user(self.company)
        self.call(self.company, prefix, token=token, status=403)
        self.permission(self.company, user, 'accounting.read')
        self.call(self.company, prefix, token=token, status=403)  # Original creator restriction survives.

    def test_partial_installed_allocation_scope_never_falls_back_to_the_old_horizon(self):
        office = self.company['office']
        original = prejournal_horizon(office)
        with office.db:
            office.db.execute('DROP TABLE business_accounting_allocation_requests')
        before = '\n'.join(office.db.iterdump())
        with self.assertRaises((Problem, ValueError, RuntimeError)):
            business_schema.financial_accounting_horizon(office)
        self.assertEqual('\n'.join(office.db.iterdump()), before)
        self.assertEqual(prejournal_horizon(office), original)


if __name__ == '__main__':
    unittest.main()
