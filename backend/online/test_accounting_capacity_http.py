"""Actual HTTP/MFA and local operator checks for additive component capacity.

Only the saved legacy SQLite invoices use the explicit SyntheticDocuments
fixture. No productive issuer gate, source right or financial write gate is
patched. Genuine PostgreSQL issuance and runtime roles have separate tests.
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
import business_schema
from core import Office, Problem
from backend.restore import restore
from online import test_accounting_refunds_http as refunds
from online import test_accounting_journey as journey


PREFIX = '/business/accounting/components/v2/events/'
TABLES = tuple('business_accounting_capacity_' + name for name in
               ('handoffs', 'segments', 'releases', 'entries', 'lines', 'requests'))


class AccountingCapacityHTTPTests(unittest.TestCase):
    setUp = refunds.AccountingRefundHTTPTests.setUp
    new_company = refunds.AccountingRefundHTTPTests.new_company
    open_app = refunds.AccountingRefundHTTPTests.open_app
    call = refunds.AccountingRefundHTTPTests.call
    login = refunds.AccountingRefundHTTPTests.login
    user = refunds.AccountingRefundHTTPTests.user
    permission = refunds.AccountingRefundHTTPTests.permission
    payment = refunds.AccountingRefundHTTPTests.payment
    account_record = refunds.AccountingRefundHTTPTests.account_record
    source = refunds.AccountingRefundHTTPTests.source
    import_body = refunds.AccountingRefundHTTPTests.import_body
    legacy_sources = refunds.AccountingRefundHTTPTests.legacy_sources
    report = refunds.AccountingRefundHTTPTests.report
    report_hash = staticmethod(refunds.AccountingRefundHTTPTests.report_hash)
    require_reconciliation = refunds.AccountingRefundHTTPTests.require_reconciliation
    imported_payment = refunds.AccountingRefundHTTPTests.imported_payment
    synthetic_invoice = refunds.AccountingRefundHTTPTests.synthetic_invoice
    assignment = refunds.AccountingRefundHTTPTests.assignment
    component_command = refunds.AccountingRefundHTTPTests.component_command
    origin_case = refunds.AccountingRefundHTTPTests.origin_case
    imported_refund = refunds.AccountingRefundHTTPTests.imported_refund
    refund_command = refunds.AccountingRefundHTTPTests.refund_command

    def receipt(self, invoice, amount='20.00'):
        payment = self.call(self.company, '/business/finance/payments', journey.request(
            source_id='synthetic-capacity-receipt-' + uuid.uuid4().hex, kind='receipt', amount=amount,
            currency='EUR', booking_date='2026-11-02', reference='Synthetic replacement customer payment',
            allocations=[dict(document_id=invoice['id'], amount=amount)])).json
        source = self.source(self.company, 'payments', payment['id'])
        event = self.call(self.company, '/business/accounting/events/import-payment', self.import_body(source), status=201).json
        return payment, event

    def released_origin(self):
        origin = self.origin_case()
        unused_payment, event = self.imported_refund(origin['invoice'])
        path, command = self.refund_command(event)
        entry = self.call(self.company, path + '/confirm', command, status=201).json
        return origin, dict(event=event, path=path, command=command, entry=entry)

    def capacity_command(self, event, company=None):
        company = company or self.company
        path = PREFIX + event['id']
        state = self.call(company, path).json
        portion = next(value for value in self.call(company, path + '/portions').json['items']
                       if value['eligible'] and value['writer'] == 'c2')
        self.assertEqual(len(portion['groups']), 1)
        body = dict(source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
            portion_id=portion['portion_id'], portion_state_hash=portion['portion_state_hash'], action=portion['action'],
            groups=[dict(group_id=portion['groups'][0]['group_id'], amount=portion['amount'])],
            reason='Synthetic explicit reuse of exact returned documentary cents')
        preview = self.call(company, path + '/preview', body).json
        return path, journey.request(**body, preview_hash=preview['preview_hash'], confirmation=True)

    @staticmethod
    def historical_h4(horizon):
        return dict(schema_version=4, **{key: horizon[key] for key in
                    ('prejournal', 'allocations', 'components', 'refunds')})

    def test_takeover_changes_only_capacity_keeps_old_receipts_and_rejects_unaccepted_old_command(self):
        origin, refund = self.released_origin()
        unused, event = self.receipt(origin['invoice'])
        old_path, old_command = self.component_command(event)
        path, command = self.capacity_command(event)
        office = self.company['office']
        before = business_schema.financial_accounting_horizon(office)
        sources = self.legacy_sources(self.company)
        open_items = self.call(self.company, '/business/finance/open-items').json
        unchanged = '\n'.join(office.db.iterdump())
        self.call(self.company, path)
        self.call(self.company, path + '/history')
        self.call(self.company, path + '/portions')
        self.assertEqual('\n'.join(office.db.iterdump()), unchanged)
        entry = self.call(self.company, path + '/confirm', command, status=201).json
        self.assertEqual((entry['amount'], entry['net'], entry['tax']), ('20.00', '16.81', '3.19'))
        self.assertEqual(entry['action'], 'takeover_and_document')
        self.assertFalse(entry['tax_result_available'])
        self.assertEqual(entry['tax_status'], 'unconfigured')
        after = business_schema.financial_accounting_horizon(office)
        self.assertEqual(after['schema_version'], 15)
        self.assertEqual(set(after), {'schema_version', 'prejournal', 'allocations', 'components', 'refunds', 'capacity', 'refunds_v2', 'profile', 'euer', 'payroll_cash', 'bank_reconciliation', 'travel_cash', 'opening_balances', 'historical_assets','opening_items','year_values'})
        self.assertEqual(self.historical_h4(before), self.historical_h4(after))
        self.assertEqual(after['refunds_v2'], before['refunds_v2'])
        self.assertNotEqual(before['capacity']['sha256'], after['capacity']['sha256'])
        self.assertEqual(after['capacity']['table_counts'], {table: 1 for table in TABLES})
        self.assertEqual(self.legacy_sources(self.company), sources)
        self.assertEqual(self.call(self.company, '/business/finance/open-items').json, open_items)
        self.assertEqual(self.call(self.company, path + '/history').json['items'], [entry])
        self.assertEqual(self.call(self.company, path + '/confirm', command, status=201).json, entry)
        self.assertEqual(self.call(self.company, origin['component_path'] + '/confirm', origin['component_command'], status=201).json,
                         origin['component_entry'])
        self.assertEqual(self.call(self.company, refund['path'] + '/confirm', refund['command'], status=201).json, refund['entry'])
        self.assertFalse(refund['entry']['capacity_released'])
        current = '\n'.join(office.db.iterdump())
        rejected = self.call(self.company, old_path + '/confirm', old_command, status=409)
        self.assertEqual(rejected.json.get('request_resolution'), 'not_accepted')
        rejected = self.call(self.company, path + '/confirm', {**command, 'request_id': uuid.uuid4().hex}, status=409)
        self.assertEqual(rejected.json.get('request_resolution'), 'not_accepted')
        changed = self.call(self.company, path + '/confirm', {**command, 'reason': 'Changed request under accepted ID'}, status=409)
        self.assertNotIn('request_resolution', changed.json)
        self.assertEqual('\n'.join(office.db.iterdump()), current)

    def test_current_schema_is_required_even_for_empty_scope_and_malformed_subhorizons_never_write(self):
        office = self.company['office']
        self.require_reconciliation(office)
        report = self.report(office)
        self.assertEqual(report['schema'], 16)
        self.assertEqual(report['accounting_horizon']['capacity']['table_counts'], {table: 0 for table in TABLES})
        before = '\n'.join(office.db.iterdump())
        invalid = [{**report, 'schema': 5, 'accounting_horizon': self.historical_h4(report['accounting_horizon'])},
                   {**report, 'schema': 10}, {**report, 'schema': True}]
        for changes in ({'schema_version': True}, {'schema_version': 2}, {'sha256': '0' * 64},
                        {'table_counts': {}}, {'table_counts': {table: True for table in TABLES}},
                        {'table_counts': {table: -1 for table in TABLES}},
                        {'table_counts': {**{table: 0 for table in TABLES}, 'future_table': 0}}, {'extra': None}):
            candidate = deepcopy(report)
            candidate['accounting_horizon']['capacity'].update(changes)
            invalid.append(candidate)
        for key in ('prejournal', 'allocations', 'components', 'refunds'):
            candidate = deepcopy(report)
            candidate['accounting_horizon'][key]['sha256'] = '0' * 64
            invalid.append(candidate)
        for candidate in invalid:
            with self.assertRaises((Problem, ValueError)):
                business_schema.reconcile_local_financial_restore(office, candidate, self.report_hash(candidate), application_stopped=True)
            self.assertEqual('\n'.join(office.db.iterdump()), before)
        released = business_schema.reconcile_local_financial_restore(office, report, self.report_hash(report), application_stopped=True)
        self.account_record(self.company, 'AFTER-CAPACITY-RELEASE')
        current = '\n'.join(office.db.iterdump())
        self.assertEqual(business_schema.reconcile_local_financial_restore(office, report, self.report_hash(report), application_stopped=True), released)
        self.assertEqual('\n'.join(office.db.iterdump()), current)

    def test_successful_schema5_receipt_replays_after_migration_but_never_unlocks_new_restore(self):
        old_registry = tuple(spec for spec in business_schema.registry() if spec.name not in ('business_accounting_capacity', 'business_accounting_refunds_v2', 'business_accounting_profile', 'business_accounting_euer', 'business_payroll_cash', 'business_bank_reconciliation', 'business_travel_allowances', 'business_accounting_openings', 'business_accounting_asset_openings', 'business_accounting_open_items','business_accounting_year_openings'))
        with patch.object(business_schema, 'registry', return_value=old_registry):
            company = self.new_company('historical-capacity')
            account = self.account_record(company)
            with patch.object(self, 'company', company), patch.object(self, 'account', account):
                origin, refund = self.released_origin()
            office = company['office']
            self.require_reconciliation(office)
            report = self.report(office)
            self.assertEqual(report['schema'], 5)
            h4 = business_schema.financial_accounting_horizon(office)
            digest = self.report_hash(report)
            released = business_schema.reconcile_local_financial_restore(office, report, digest, application_stopped=True)
        business_schema.ensure_schema(office)
        business_schema.ensure_schema(office)
        h5 = business_schema.financial_accounting_horizon(office)
        self.assertEqual(h5['schema_version'], 15)
        self.assertEqual(self.historical_h4(h5), h4)
        self.assertEqual(h5['capacity']['table_counts'], {table: 0 for table in TABLES})
        self.assertEqual(self.call(company, refund['path'] + '/confirm', refund['command'], status=201).json, refund['entry'])
        before = '\n'.join(office.db.iterdump())
        self.assertEqual(business_schema.reconcile_local_financial_restore(office, report, digest, application_stopped=True), released)
        self.assertEqual('\n'.join(office.db.iterdump()), before)
        saved = backup(self.directory / 'historical-capacity.sqlite3', self.directory / 'capacity-historical-backup.sqlite3')
        restored = Office(restore(saved, self.directory / 'capacity-historical-restored.sqlite3'))
        self.addCleanup(restored.db.close)
        restore_id = business_schema.state(restored)['restore_id']
        self.assertNotEqual(restore_id, report['restore_id'])
        before = '\n'.join(restored.db.iterdump())
        for stale in (report, {**report, 'restore_id': restore_id}):
            with self.assertRaises((Problem, ValueError)):
                business_schema.reconcile_local_financial_restore(restored, stale, self.report_hash(stale), application_stopped=True)
            self.assertEqual('\n'.join(restored.db.iterdump()), before)
        self.assertEqual(business_schema.financial_accounting_horizon(restored), h5)
        self.assertTrue(business_schema.state(restored)['financial_reconciliation_required'])

    def test_actual_restore_blocks_new_and_replayed_capacity_until_current_schema_operator_release(self):
        origin, refund = self.released_origin()
        unused, first = self.receipt(origin['invoice'])
        path, command = self.capacity_command(first)
        entry = self.call(self.company, path + '/confirm', command, status=201).json
        unused, second = self.receipt(origin['invoice'], '10.00')
        second_path, second_command = self.capacity_command(second)
        office = self.company['office']
        horizon = business_schema.financial_accounting_horizon(office)
        original_sources = self.legacy_sources(self.company)
        saved = backup(self.directory / 'alpha.sqlite3', self.directory / 'capacity-backup.sqlite3')
        target = restore(saved, self.directory / 'capacity-restored.sqlite3')
        restored = Office(target)
        self.addCleanup(restored.db.close)
        company = {**self.company, 'office': restored}
        self.open_app(company)
        company['token'] = self.login(company, 'owner@example.test', 'Synthetic-accounting-owner-password-123', advance=True)
        self.assertEqual(business_schema.financial_accounting_horizon(restored), horizon)
        self.assertFalse(self.call(company, path).json['writes_allowed'])
        self.assertEqual(self.call(company, path + '/history').json['items'], [entry])
        for command_path, pending in ((path, command), (second_path, second_command)):
            response = self.call(company, command_path + '/confirm', pending, status=409)
            self.assertNotIn('request_resolution', response.json)
        report = self.report(restored)
        evidence = self.directory / 'capacity-review.json'
        raw = (json.dumps(report, indent=2) + '\n').encode()
        evidence.write_bytes(raw); evidence.chmod(0o600)
        office.db.close(); restored.db.close()
        script = Path(__file__).resolve().parents[2] / 'scripts' / 'reconcile-accounting-restore.py'
        args = [sys.executable, str(script), '--database', str(target)]
        before = hashlib.sha256(target.read_bytes()).hexdigest()
        inspected = subprocess.run(args + ['--inspect'], capture_output=True, text=True, timeout=15)
        self.assertEqual(inspected.returncode, 0, inspected.stderr)
        inspection = json.loads(inspected.stdout)
        self.assertEqual(inspection['evidence_schema'], 16)
        self.assertEqual(inspection['accounting_horizon'], horizon)
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), before)
        stale = {**report, 'schema': 5, 'accounting_horizon': self.historical_h4(horizon)}
        obsolete = self.directory / 'capacity-obsolete-review.json'
        obsolete.write_text(json.dumps(stale)); obsolete.chmod(0o600)
        rejected = subprocess.run(args + ['--evidence', str(obsolete), '--application-stopped'], capture_output=True, text=True, timeout=15)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), before)
        accepted = subprocess.run(args + ['--evidence', str(evidence), '--application-stopped'], capture_output=True, text=True, timeout=15)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        replay = subprocess.run(args + ['--evidence', str(evidence), '--application-stopped'], capture_output=True, text=True, timeout=15)
        self.assertEqual(replay.returncode, 0, replay.stderr)
        self.assertEqual(json.loads(replay.stdout), json.loads(accepted.stdout))
        reopened = Office(target); self.addCleanup(reopened.db.close)
        company['office'] = reopened; self.open_app(company)
        self.assertEqual(business_schema.financial_accounting_horizon(reopened), horizon)
        self.assertEqual(self.call(company, path + '/confirm', command, status=201).json, entry)
        self.assertEqual(self.call(company, refund['path'] + '/confirm', refund['command'], status=201).json, refund['entry'])
        self.assertEqual(self.legacy_sources(company), original_sources)
        self.call(company, second_path + '/confirm', second_command, status=201)
        self.assertEqual(self.call(company, path + '/confirm', command, status=201).json, entry)

    def test_partial_capacity_installation_cannot_downgrade_horizon_or_repair_on_read(self):
        for corruption in ('one-table', 'all-tables', 'marker'):
            with self.subTest(corruption=corruption):
                company = self.new_company('capacity-corrupt-' + corruption)
                office = company['office']
                old = self.historical_h4(business_schema.financial_accounting_horizon(office))
                with office.db:
                    if corruption == 'marker':
                        office.db.execute("DELETE FROM business_schema_migrations WHERE module='business_accounting_capacity'")
                    else:
                        names = ('business_accounting_capacity_requests',) if corruption == 'one-table' else (
                            'business_accounting_capacity_requests', 'business_accounting_capacity_lines',
                            'business_accounting_capacity_releases', 'business_accounting_capacity_segments',
                            'business_accounting_capacity_handoffs', 'business_accounting_capacity_entries')
                        for name in names:
                            office.db.execute('DROP TABLE ' + name)
                before = '\n'.join(office.db.iterdump())
                with self.assertRaises((Problem, ValueError, RuntimeError)):
                    business_schema.financial_accounting_horizon(office)
                self.assertEqual('\n'.join(office.db.iterdump()), before)
                from business_accounting_refunds import restore_horizon
                self.assertEqual(restore_horizon(office), old['refunds'])

    def test_strict_http_method_query_payload_and_offline_boundaries(self):
        origin, unused = self.released_origin()
        unused, event = self.receipt(origin['invoice'])
        path, command = self.capacity_command(event)
        before = '\n'.join(self.company['office'].db.iterdump())
        for suffix in ('?company_id=foreign', '/history?limit=1&limit=2', '/portions?limit=101',
                       '/portions?offset=-1', '/history?sort=amount'):
            self.call(self.company, path + suffix, status=400)
        self.call(self.company, path + '/confirm', method='GET', status=405)
        self.call(self.company, path, {'unexpected': True}, method='GET', status=400)
        for body in ({**command, '_query': {}}, {**command, 'actor': {'role': 'owner'}},
                     {**command, 'action': 'document_legacy'}):
            self.call(self.company, path + '/confirm', body, status=400)
        self.call(self.company, path + '/confirm?unexpected=1', command, status=400)
        self.assertEqual('\n'.join(self.company['office'].db.iterdump()), before)
        grant = self.call(self.company, '/offline/access/v2', {}, status=201).json
        offline = grant['token']
        offline_origin = grant['binding']['instance_id'] + ':' + grant['binding']['account_id']
        # A real accepted bound device reaches its normal project route before
        # accounting denial; a missing-origin rejection would not prove this ACL.
        self.call(self.company, '/projects', token=offline, offline_origin=offline_origin)
        for token in (None, offline, 'SPPT_' + 'p' * 43, 'SPPI_' + 'i' * 43):
            self.call(self.company, path, token=token, offline_origin=offline_origin if token == offline else None,
                      status=403 if token == offline else (401, 403))
        unused, token = self.user(self.company)
        self.call(self.company, path, token=token, status=403)
        self.assertEqual(self.call(self.company, path + '/history').json['items'], [])

    def test_mode_gate_cannot_resolve_lost_accepted_c1_or_c2_acknowledgements(self):
        origin, unused_refund = self.released_origin()
        unused, event = self.receipt(origin['invoice'])
        path, command = self.capacity_command(event)
        entry = self.call(self.company, path + '/confirm', command, status=201).json
        # The client may not have received either original confirmation. A
        # compatibility gate runs before receipt lookup and cannot disprove it.
        business_schema.set_mode(self.company['office'], 'legacy')
        for command_path, pending in ((path, command), (origin['component_path'], origin['component_command'])):
            response = self.call(self.company, command_path + '/confirm', pending, status=409)
            self.assertNotIn('request_resolution', response.json)
        business_schema.set_mode(self.company['office'], 'business')
        self.assertEqual(self.call(self.company, path + '/confirm', command, status=201).json, entry)
        self.assertEqual(self.call(self.company, origin['component_path'] + '/confirm',
                                  origin['component_command'], status=201).json, origin['component_entry'])


if __name__ == '__main__':
    unittest.main()
