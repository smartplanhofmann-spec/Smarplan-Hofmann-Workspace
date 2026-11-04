"""R2 HTTP/MFA boundaries and additive schema-7 local restore verification.

All records are synthetic. Only legacy SQLite invoice issuance uses the
explicit SyntheticDocuments fixture; real PostgreSQL issuance is separate.
No bank, tax service, external provider or non-test database is contacted.
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
import business_schema
from core import Office, Problem
from restore import restore
from online import test_accounting_capacity_http as capacity
from online import test_accounting_journey as journey


PREFIX = '/business/accounting/refunds/v2/events/'
TABLES = tuple('business_accounting_refunds_v2_' + name for name in
               ('handoffs', 'entries', 'lines', 'requests', 'releases'))


class AccountingRefundsV2HTTPTests(unittest.TestCase):
    setUp = capacity.AccountingCapacityHTTPTests.setUp
    new_company = capacity.AccountingCapacityHTTPTests.new_company
    open_app = capacity.AccountingCapacityHTTPTests.open_app
    call = capacity.AccountingCapacityHTTPTests.call
    login = capacity.AccountingCapacityHTTPTests.login
    user = capacity.AccountingCapacityHTTPTests.user
    permission = capacity.AccountingCapacityHTTPTests.permission
    payment = capacity.AccountingCapacityHTTPTests.payment
    account_record = capacity.AccountingCapacityHTTPTests.account_record
    source = capacity.AccountingCapacityHTTPTests.source
    import_body = capacity.AccountingCapacityHTTPTests.import_body
    legacy_sources = capacity.AccountingCapacityHTTPTests.legacy_sources
    report = capacity.AccountingCapacityHTTPTests.report
    report_hash = staticmethod(capacity.AccountingCapacityHTTPTests.report_hash)
    require_reconciliation = capacity.AccountingCapacityHTTPTests.require_reconciliation
    imported_payment = capacity.AccountingCapacityHTTPTests.imported_payment
    synthetic_invoice = capacity.AccountingCapacityHTTPTests.synthetic_invoice
    assignment = capacity.AccountingCapacityHTTPTests.assignment
    component_command = capacity.AccountingCapacityHTTPTests.component_command
    origin_case = capacity.AccountingCapacityHTTPTests.origin_case
    imported_refund = capacity.AccountingCapacityHTTPTests.imported_refund
    refund_command = capacity.AccountingCapacityHTTPTests.refund_command
    receipt = capacity.AccountingCapacityHTTPTests.receipt
    released_origin = capacity.AccountingCapacityHTTPTests.released_origin
    capacity_command = capacity.AccountingCapacityHTTPTests.capacity_command

    def reused_origin(self):
        origin, returned = self.released_origin()
        unused, event = self.receipt(origin['invoice'])
        path, command = self.capacity_command(event)
        entry = self.call(self.company, path + '/confirm', command, status=201).json
        return origin, returned, dict(event=event, path=path, command=command, entry=entry)

    def r2_command(self, event, *, chosen=None, company=None):
        company = company or self.company
        path = PREFIX + event['id']
        state = self.call(company, path).json
        portion = next(value for value in self.call(company, path + '/portions').json['items']
                       if value['eligible'] and value['writer'] == 'r2')
        origins = self.call(company, path + '/origins?portion_id=' + portion['portion_id']).json['items']
        if chosen is None:
            chosen = [(next(value for value in origins if value['origin_version'] == 'c2'), portion['amount'])]
        body = dict(source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
            portion_id=portion['portion_id'], portion_state_hash=portion['portion_state_hash'], action=portion['action'],
            origins=[dict(origin_version=value['origin_version'], entry_id=value['entry_id'], group_id=value['group_id'],
                          lot_state_hash=value['lot_state_hash'], amount=amount) for value, amount in chosen],
            reason='Synthetic explicit versioned refund origin decision')
        preview = self.call(company, path + '/preview', body).json
        return path, journey.request(**body, preview_hash=preview['preview_hash'], confirmation=True)

    def rebound(self):
        origin, returned, reused = self.reused_origin()
        unused, event = self.imported_refund(origin['invoice'], '10.00')
        path, command = self.r2_command(event)
        entry = self.call(self.company, path + '/confirm', command, status=201).json
        return origin, returned, reused, dict(event=event, path=path, command=command, entry=entry)

    @staticmethod
    def historical_h5(horizon):
        return dict(schema_version=5, **{key: horizon[key] for key in
                    ('prejournal', 'allocations', 'components', 'refunds', 'capacity')})

    def test_binding_then_actual_capacity_reuse_changes_only_the_corresponding_horizons(self):
        origin, returned, reused = self.reused_origin()
        unused, event = self.imported_refund(origin['invoice'], '10.00')
        legacy_path, legacy_command = self.refund_command(event)
        path, command = self.r2_command(event)
        office = self.company['office']
        before = business_schema.financial_accounting_horizon(office)
        sources = self.legacy_sources(self.company)
        open_items = self.call(self.company, '/business/finance/open-items').json
        unchanged = '\n'.join(office.db.iterdump())
        self.call(self.company, path)
        self.call(self.company, path + '/portions')
        self.call(self.company, path + '/history')
        self.assertEqual('\n'.join(office.db.iterdump()), unchanged)
        entry = self.call(self.company, path + '/confirm', command, status=201).json
        self.assertEqual((entry['amount'], entry['net'], entry['tax']), ('10.00', '8.40', '1.60'))
        self.assertEqual(entry['action'], 'takeover_and_bind')
        self.assertEqual(entry['lines'][0]['origin_version'], 'c2')
        self.assertFalse(entry['capacity_released'])
        self.assertFalse(entry['tax_result_available'])
        after = business_schema.financial_accounting_horizon(office)
        self.assertEqual(after['schema_version'], 13)
        self.assertEqual(set(after), {'schema_version', 'prejournal', 'allocations', 'components', 'refunds', 'capacity', 'refunds_v2', 'profile', 'euer', 'payroll_cash', 'bank_reconciliation', 'travel_cash', 'opening_balances', 'historical_assets'})
        self.assertEqual(self.historical_h5(before), self.historical_h5(after))
        self.assertNotEqual(before['refunds_v2']['sha256'], after['refunds_v2']['sha256'])
        self.assertEqual(after['refunds_v2']['table_counts'], {table: (0 if table.endswith('_releases') else 1) for table in TABLES})
        self.assertEqual(self.legacy_sources(self.company), sources)
        self.assertEqual(self.call(self.company, '/business/finance/open-items').json, open_items)
        self.assertEqual(self.call(self.company, returned['path'] + '/confirm', returned['command'], status=201).json, returned['entry'])
        self.assertEqual(self.call(self.company, reused['path'] + '/confirm', reused['command'], status=201).json, reused['entry'])
        self.assertEqual(self.call(self.company, path + '/confirm', command, status=201).json, entry)
        owner = office.user(self.company['token'])
        business_schema.set_feature_flag(office, owner, 'accounting_refund_origins_v2', False)
        denied = self.call(self.company, legacy_path + '/confirm', legacy_command, status=409)
        self.assertEqual(denied.json.get('request_resolution'), 'not_accepted')
        self.assertEqual(self.call(self.company, returned['path'] + '/confirm', returned['command'], status=201).json, returned['entry'])
        business_schema.set_feature_flag(office, owner, 'accounting_refund_origins_v2', True)
        unused, replacement = self.receipt(origin['invoice'], '10.00')
        cpath, ccommand = self.capacity_command(replacement)
        before_reuse = business_schema.financial_accounting_horizon(office)
        self.call(self.company, cpath + '/confirm', ccommand, status=201)
        after_reuse = business_schema.financial_accounting_horizon(office)
        for key in ('prejournal', 'allocations', 'components', 'refunds'):
            self.assertEqual(before_reuse[key], after_reuse[key])
        self.assertNotEqual(before_reuse['capacity'], after_reuse['capacity'])
        self.assertEqual(after_reuse['refunds_v2']['table_counts'], {table: 1 for table in TABLES})
        self.assertEqual(self.call(self.company, path + '/confirm', command, status=201).json, entry)
        self.assertFalse(entry['capacity_released'])

    def test_legacy_portion_routes_to_r1_and_consolidated_state_does_not_rewrite_its_history(self):
        origin = self.origin_case()
        unused, event = self.imported_refund(origin['invoice'], '10.00')
        path = PREFIX + event['id']
        portion = self.call(self.company, path + '/portions').json['items'][0]
        self.assertEqual((portion['writer'], portion['action']), ('r1', 'bind_legacy'))
        self.assertIsNone(portion['capacity_ownership_id'])
        self.assertIsNone(portion['ownership_id'])
        self.assertTrue(self.call(self.company, path).json['eligible'])
        self.call(self.company, path + '/origins?portion_id=' + portion['portion_id'], status=409)
        legacy_path, command = self.refund_command(event)
        entry = self.call(self.company, legacy_path + '/confirm', command, status=201).json
        state = self.call(self.company, path).json
        self.assertEqual((state['origin_documented_amount'], state['origin_unresolved_amount']), ('10.00', '0.00'))
        self.assertEqual(self.call(self.company, path + '/history').json['items'], [])
        self.assertEqual(self.call(self.company, legacy_path + '/history').json['items'], [entry])
        self.assertEqual(self.call(self.company, legacy_path + '/confirm', command, status=201).json, entry)

    def test_current_schema_requires_complete_exact_scope_even_when_all_new_tables_are_empty(self):
        office = self.company['office']
        self.require_reconciliation(office)
        report = self.report(office)
        self.assertEqual(report['schema'], 14)
        self.assertEqual(report['accounting_horizon']['refunds_v2']['table_counts'], {table: 0 for table in TABLES})
        before = '\n'.join(office.db.iterdump())
        invalid = [{**report, 'schema': 6, 'accounting_horizon': self.historical_h5(report['accounting_horizon'])},
                   {**report, 'schema': 10}, {**report, 'schema': True}]
        for changes in ({'schema_version': True}, {'schema_version': 2}, {'sha256': '0' * 64},
                        {'table_counts': {}}, {'table_counts': {table: True for table in TABLES}},
                        {'table_counts': {table: -1 for table in TABLES}},
                        {'table_counts': {**{table: 0 for table in TABLES}, 'future_table': 0}}, {'extra': None}):
            candidate = deepcopy(report)
            candidate['accounting_horizon']['refunds_v2'].update(changes)
            invalid.append(candidate)
        for key in ('prejournal', 'allocations', 'components', 'refunds', 'capacity'):
            candidate = deepcopy(report)
            candidate['accounting_horizon'][key]['sha256'] = '0' * 64
            invalid.append(candidate)
        for candidate in invalid:
            with self.assertRaises((Problem, ValueError)):
                business_schema.reconcile_local_financial_restore(office, candidate, self.report_hash(candidate), application_stopped=True)
            self.assertEqual('\n'.join(office.db.iterdump()), before)
        approved = business_schema.reconcile_local_financial_restore(office, report, self.report_hash(report), application_stopped=True)
        self.account_record(self.company, 'AFTER-R2-RELEASE')
        current = '\n'.join(office.db.iterdump())
        self.assertEqual(business_schema.reconcile_local_financial_restore(office, report, self.report_hash(report), application_stopped=True), approved)
        self.assertEqual('\n'.join(office.db.iterdump()), current)

    def test_successful_schema6_report_and_old_c2_proofs_survive_migration_but_not_a_new_restore(self):
        old_registry = tuple(spec for spec in business_schema.registry() if spec.name not in ('business_accounting_refunds_v2', 'business_accounting_profile', 'business_accounting_euer', 'business_payroll_cash', 'business_bank_reconciliation', 'business_travel_allowances', 'business_accounting_openings', 'business_accounting_asset_openings'))
        with patch.object(business_schema, 'registry', return_value=old_registry):
            company = self.new_company('historical-refunds-v2')
            account = self.account_record(company)
            with patch.object(self, 'company', company), patch.object(self, 'account', account):
                origin, returned, reused = self.reused_origin()
            office = company['office']
            old_rows = {table: sorted(tuple(row) for row in office.db.execute('SELECT * FROM ' + table)) for table in capacity.TABLES}
            proof = json.loads(office.db.execute('SELECT proof_json FROM business_accounting_capacity_entries').fetchone()[0])
            self.assertEqual(proof['schema_version'], 1)
            self.assertNotIn('r2_sequence', proof)
            self.require_reconciliation(office)
            report = self.report(office)
            self.assertEqual(report['schema'], 6)
            h5 = business_schema.financial_accounting_horizon(office)
            digest = self.report_hash(report)
            approved = business_schema.reconcile_local_financial_restore(office, report, digest, application_stopped=True)
        business_schema.ensure_schema(office)
        business_schema.ensure_schema(office)
        h6 = business_schema.financial_accounting_horizon(office)
        self.assertEqual(h6['schema_version'], 13)
        self.assertEqual(self.historical_h5(h6), h5)
        self.assertEqual(h6['refunds_v2']['table_counts'], {table: 0 for table in TABLES})
        self.assertEqual({table: sorted(tuple(row) for row in office.db.execute('SELECT * FROM ' + table)) for table in capacity.TABLES}, old_rows)
        self.assertEqual(self.call(company, reused['path'] + '/confirm', reused['command'], status=201).json, reused['entry'])
        before = '\n'.join(office.db.iterdump())
        self.assertEqual(business_schema.reconcile_local_financial_restore(office, report, digest, application_stopped=True), approved)
        self.assertEqual('\n'.join(office.db.iterdump()), before)
        saved = backup(self.directory / 'historical-refunds-v2.sqlite3', self.directory / 'historical-r2-backup.sqlite3')
        restored = Office(restore(saved, self.directory / 'historical-r2-restored.sqlite3'))
        self.addCleanup(restored.db.close)
        restore_id = business_schema.state(restored)['restore_id']
        before = '\n'.join(restored.db.iterdump())
        for stale in (report, {**report, 'restore_id': restore_id}):
            with self.assertRaises((Problem, ValueError)):
                business_schema.reconcile_local_financial_restore(restored, stale, self.report_hash(stale), application_stopped=True)
            self.assertEqual('\n'.join(restored.db.iterdump()), before)
        self.assertEqual(business_schema.financial_accounting_horizon(restored), h6)
        self.assertTrue(business_schema.state(restored)['financial_reconciliation_required'])

    def test_real_restore_preserves_r2_release_claims_and_requires_current_operator_evidence(self):
        origin, returned, reused, bound = self.rebound()
        unused, receipt = self.receipt(origin['invoice'], '10.00')
        cpath, ccommand = self.capacity_command(receipt)
        centry = self.call(self.company, cpath + '/confirm', ccommand, status=201).json
        unused, pending_event = self.imported_refund(origin['invoice'], '5.00')
        pending_path, pending_command = self.r2_command(pending_event)
        office = self.company['office']
        horizon = business_schema.financial_accounting_horizon(office)
        old_sources = self.legacy_sources(self.company)
        saved = backup(self.directory / 'alpha.sqlite3', self.directory / 'r2-backup.sqlite3')
        target = restore(saved, self.directory / 'r2-restored.sqlite3')
        restored = Office(target); self.addCleanup(restored.db.close)
        company = {**self.company, 'office': restored}
        self.open_app(company)
        company['token'] = self.login(company, 'owner@example.test', 'Synthetic-accounting-owner-password-123', advance=True)
        self.assertEqual(business_schema.financial_accounting_horizon(restored), horizon)
        self.assertFalse(self.call(company, bound['path']).json['writes_allowed'])
        self.assertEqual(self.call(company, bound['path'] + '/history').json['items'], [bound['entry']])
        for path, command in ((bound['path'], bound['command']), (pending_path, pending_command),
                              (returned['path'], returned['command']), (cpath, ccommand)):
            response = self.call(company, path + '/confirm', command, status=409)
            self.assertNotIn('request_resolution', response.json)
        report = self.report(restored)
        evidence = self.directory / 'r2-review.json'
        raw = (json.dumps(report, indent=2) + '\n').encode()
        evidence.write_bytes(raw); evidence.chmod(0o600)
        office.db.close(); restored.db.close()
        script = Path(__file__).resolve().parents[2] / 'scripts' / 'reconcile-accounting-restore.py'
        args = [sys.executable, str(script), '--database', str(target)]
        before = hashlib.sha256(target.read_bytes()).hexdigest()
        inspected = subprocess.run(args + ['--inspect'], capture_output=True, text=True, timeout=20)
        self.assertEqual(inspected.returncode, 0, inspected.stderr)
        inspection = json.loads(inspected.stdout)
        self.assertEqual(inspection['evidence_schema'], 14)
        self.assertEqual(inspection['accounting_horizon'], horizon)
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), before)
        stale = {**report, 'schema': 6, 'accounting_horizon': self.historical_h5(horizon)}
        old_evidence = self.directory / 'r2-obsolete-review.json'
        old_evidence.write_text(json.dumps(stale)); old_evidence.chmod(0o600)
        rejected = subprocess.run(args + ['--evidence', str(old_evidence), '--application-stopped'], capture_output=True, text=True, timeout=20)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), before)
        accepted = subprocess.run(args + ['--evidence', str(evidence), '--application-stopped'], capture_output=True, text=True, timeout=20)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        replay = subprocess.run(args + ['--evidence', str(evidence), '--application-stopped'], capture_output=True, text=True, timeout=20)
        self.assertEqual(replay.returncode, 0, replay.stderr)
        self.assertEqual(json.loads(replay.stdout), json.loads(accepted.stdout))
        reopened = Office(target); self.addCleanup(reopened.db.close)
        company['office'] = reopened; self.open_app(company)
        self.assertEqual(business_schema.financial_accounting_horizon(reopened), horizon)
        self.assertEqual(self.legacy_sources(company), old_sources)
        for path, command, entry in ((bound['path'], bound['command'], bound['entry']),
                                     (returned['path'], returned['command'], returned['entry']), (cpath, ccommand, centry)):
            self.assertEqual(self.call(company, path + '/confirm', command, status=201).json, entry)
        self.call(company, pending_path + '/confirm', pending_command, status=201)
        self.assertEqual(self.call(company, bound['path'] + '/confirm', bound['command'], status=201).json, bound['entry'])

    def test_partial_r2_or_complete_loss_with_proof2_never_falls_back_or_repairs_on_read(self):
        from business_accounting_refunds_v2 import installed
        for corruption in ('one-table', 'marker', 'all-tables-and-marker'):
            with self.subTest(corruption=corruption):
                company = self.new_company('r2-corrupt-' + corruption)
                account = self.account_record(company)
                with patch.object(self, 'company', company), patch.object(self, 'account', account):
                    self.reused_origin()
                office = company['office']
                proof = json.loads(office.db.execute('SELECT proof_json FROM business_accounting_capacity_entries').fetchone()[0])
                self.assertEqual(proof['schema_version'], 2)
                with office.db:
                    if corruption != 'marker':
                        names = ('business_accounting_refunds_v2_requests',) if corruption == 'one-table' else (
                            'business_accounting_refunds_v2_releases', 'business_accounting_refunds_v2_requests',
                            'business_accounting_refunds_v2_lines', 'business_accounting_refunds_v2_handoffs',
                            'business_accounting_refunds_v2_entries')
                        for name in names:
                            office.db.execute('DROP TABLE ' + name)
                    if corruption != 'one-table':
                        office.db.execute("DELETE FROM business_schema_migrations WHERE module='business_accounting_refunds_v2'")
                before = '\n'.join(office.db.iterdump())
                with self.assertRaises((Problem, ValueError, RuntimeError)):
                    installed(office)
                with self.assertRaises((Problem, ValueError, RuntimeError)):
                    business_schema.financial_accounting_horizon(office)
                self.assertEqual('\n'.join(office.db.iterdump()), before)

    def test_resolution_marker_requires_proven_absent_receipt_and_survives_compatibility_gate(self):
        origin, returned, reused, bound = self.rebound()
        path, command = bound['path'], bound['command']
        changed = self.call(self.company, path + '/confirm', {**command, 'reason': 'Different accepted request body'}, status=409)
        self.assertNotIn('request_resolution', changed.json)
        new_id = self.call(self.company, path + '/confirm', {**command, 'request_id': uuid.uuid4().hex}, status=409)
        self.assertEqual(new_id.json.get('request_resolution'), 'not_accepted')
        business_schema.set_mode(self.company['office'], 'legacy')
        for command_path, pending in ((path, command), (returned['path'], returned['command']), (reused['path'], reused['command'])):
            response = self.call(self.company, command_path + '/confirm', pending, status=409)
            self.assertNotIn('request_resolution', response.json)
        business_schema.set_mode(self.company['office'], 'business')
        self.assertEqual(self.call(self.company, path + '/confirm', command, status=201).json, bound['entry'])
        self.assertEqual(self.call(self.company, returned['path'] + '/confirm', returned['command'], status=201).json, returned['entry'])

    def test_strict_methods_queries_payloads_and_customer_offline_tokens(self):
        origin, unused_returned, unused_reused = self.reused_origin()
        unused, event = self.imported_refund(origin['invoice'], '10.00')
        path, command = self.r2_command(event)
        before = '\n'.join(self.company['office'].db.iterdump())
        for suffix in ('?company_id=foreign', '/portions?limit=101', '/history?limit=1&limit=2',
                       '/history?offset=-1', '/origins', '/origins?portion_id=' + command['portion_id'] + '&sort=amount'):
            self.call(self.company, path + suffix, status=400)
        self.call(self.company, path + '/confirm', method='GET', status=405)
        self.call(self.company, path, {'unexpected': True}, method='GET', status=400)
        self.call(self.company, path + '/confirm?unexpected=1', command, status=400)
        for body in ({**command, '_query': {}}, {**command, 'actor': {'role': 'owner'}},
                     {**command, 'action': 'bind_legacy'},
                     {**command, 'origins': [{**command['origins'][0], 'origin_version': 'c3'}]}):
            self.call(self.company, path + '/confirm', body, status=400)
        self.assertEqual('\n'.join(self.company['office'].db.iterdump()), before)
        offline = self.call(self.company, '/offline/access', {}, status=201).json['token']
        for token in (None, offline, 'SPPT_' + 'p' * 43, 'SPPI_' + 'i' * 43):
            self.call(self.company, path, token=token, status=(401, 403))
        unused, token = self.user(self.company)
        self.call(self.company, path, token=token, status=403)
        self.assertEqual(self.call(self.company, path + '/history').json['items'], [])


if __name__ == '__main__':
    unittest.main()
