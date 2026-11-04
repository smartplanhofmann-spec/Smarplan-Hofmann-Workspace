"""Synthetic opening balances: real PostgreSQL ACLs, MFA/HTTP and dump/restore.

Only the existing guarded disposable loopback smartplan_check fixture is reset.
No bank, authority, external service or production instance is contacted.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import threading
import unittest
import uuid

import psycopg

import business_schema
from business_accounting_euer import EuerAccounting
from business_accounting_openings import OpeningBalances, TABLES, restore_horizon, validate_integrity
from core import Problem, canonical
from online import test_business_accounting_euer_pg as euer, release
from online.store import PostgresOffice
from online.test_postgres_accounting_components_integration import disposable_restore, evidence_for, approve


fixture = euer.fixture
req = euer.req
BASE = '/business/accounting/opening-balances'


@unittest.skipUnless(fixture.DSN, 'Disposable loopback PostgreSQL fixture required')
class OpeningBalancesPostgres(unittest.TestCase):
    reopen = euer.EuerPostgres.reopen
    login = euer.EuerPostgres.login
    call = euer.EuerPostgres.call
    profile = euer.EuerPostgres.profile
    post = euer.EuerPostgres.post
    project = euer.EuerPostgres.project
    issuer = euer.EuerPostgres.issuer
    invoice = euer.EuerPostgres.invoice
    payment = euer.EuerPostgres.payment
    source = euer.EuerPostgres.source
    document = euer.EuerPostgres.document
    cash = euer.EuerPostgres.cash

    def setUp(self):
        euer.EuerPostgres.setUp(self)
        self.actor = self.office.user(self.token)
        self.assertEqual(self.office.db.execute('SELECT current_user').fetchone()[0], 'smartplan-online')
        self.assertTrue(business_schema.require_runtime_security(self.office))
        self.profile()
        self.account = self.call('POST', '/business/accounting/accounts', req(
            confirmation=True, code='OPENING', name='Synthetic opening account', kind='bank'), status=201).json

    def original(self):
        raw = b'%PDF-1.4\nSynthetic opening evidence retained exactly\n%%EOF'
        command = req(account_id=self.account['id'], filename='synthetic-opening.pdf',
            media_type='application/pdf', content_base64=base64.b64encode(raw).decode())
        original = self.call('POST', BASE + '/originals', command, status=201).json
        return original, command, raw

    def command(self, original, amount='500.00'):
        state = self.call('GET', BASE).json
        body = dict(expected_revision=state['revision'], state_hash=state['state_hash'],
            account_id=self.account['id'], account_revision=self.account['revision'],
            profile_ref=state['profile_ref'], status='active', opening_date=self.today[:4] + '-01-01',
            amount=amount, reason='Synthetic original at the exact bookkeeping start reviewed',
            source=dict(kind='original', original_id=original['id'], sha256=original['sha256'],
                        evidence_type='account_statement', at_start_of_day=True))
        preview = self.call('POST', BASE + '/preview', body).json
        return req(**body, preview_hash=preview['preview_hash'], confirmation=True)

    def compete(self, commands):
        barrier = threading.Barrier(2)
        def worker(command):
            office = PostgresOffice(self.runtime)
            try:
                pid = office.db.execute('SELECT pg_backend_pid()').fetchone()[0]
                barrier.wait(timeout=15)
                try:
                    return pid, 201, OpeningBalances(office).confirm(self.actor, command)
                except Problem as error:
                    return pid, error.status, error.request_resolution
            finally:
                office.db.close()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(worker, commands))
        self.assertNotEqual(results[0][0], results[1][0])
        return [(status, value) for _, status, value in results]

    def assert_scope(self, counts):
        scope = restore_horizon(self.office)
        self.assertEqual(set(scope), {'schema_version', 'table_counts', 'sha256'})
        self.assertEqual(scope['schema_version'], 1)
        self.assertEqual(scope['table_counts'], dict(zip(TABLES, counts)))
        self.assertRegex(scope['sha256'], r'^[a-f0-9]{64}$')
        current = business_schema.financial_accounting_horizon(self.office)
        self.assertEqual(current['schema_version'], 15)
        self.assertEqual(current['opening_balances'], scope)
        return scope

    def test_identical_commands_on_distinct_connections_keep_one_event_and_one_receipt(self):
        original, _, _ = self.original()
        command = self.command(original)
        results = self.compete([command, command])
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0][0], 201)
        self.assert_scope((1, 1, 2))
        self.assertEqual(self.call('POST', BASE + '/confirm', command, status=201).json, results[0][1])
        self.assertTrue(validate_integrity(self.office))

    def test_distinct_commands_on_same_state_accept_one_and_reject_stale_competitor(self):
        original, _, _ = self.original()
        commands = [self.command(original, amount) for amount in ('500.00', '-100.00')]
        results = self.compete(commands)
        self.assertEqual(sorted(status for status, _ in results), [201, 409])
        self.assertEqual(next(value for status, value in results if status == 409), 'not_accepted')
        winner = next(value for status, value in results if status == 201)
        self.assertIn(winner['amount'], ('500.00', '-100.00'))
        self.assert_scope((1, 1, 2))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_accounting_cash_events').fetchone()[0], 0)
        self.assertTrue(validate_integrity(self.office))

    def test_original_request_binding_and_all_three_tables_are_append_only_under_runtime(self):
        original, upload, raw = self.original()
        command = self.command(original)
        accepted = self.call('POST', BASE + '/confirm', command, status=201).json
        scope = self.assert_scope((1, 1, 2))
        self.assertEqual(self.call('GET', BASE + '/originals/' + original['id']).data, raw)
        self.assertEqual(original['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(self.call('POST', BASE + '/originals', upload, status=201).json, original)
        changed = upload | dict(content_base64=base64.b64encode(raw + b'changed').decode())
        self.call('POST', BASE + '/originals', changed, status=409)
        self.call('POST', BASE + '/confirm', command | dict(amount='501.00'), status=409)
        self.assertEqual(restore_horizon(self.office), scope)
        for table in TABLES:
            column = self.office.db.execute('SELECT * FROM ' + table + ' LIMIT 1').description[0].name
            for statement in ('UPDATE ' + table + ' SET ' + column + '=' + column,
                              'DELETE FROM ' + table, 'TRUNCATE ' + table):
                with self.subTest(table=table, statement=statement):
                    with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                        with self.office.db:
                            self.office.db.execute(statement)
        self.assertEqual(restore_horizon(self.office), scope)
        self.reopen()
        self.assertEqual(self.call('POST', BASE + '/confirm', command, status=201).json, accepted)
        self.assertEqual(self.call('GET', BASE + '/originals/' + original['id']).data, raw)
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_dump_restore_binds_original_and_old_euer_export_to_explicit_report13(self):
        project = self.project(); self.issuer()
        invoice = self.invoice(project, '100.00'); payment = self.payment(invoice, '119.00')
        source = next(item for item in self.call('GET', '/business/accounting/sources/payments').json['items']
                      if item['payment_id'] == payment['id'])
        event = self.call('POST', '/business/accounting/events/import-payment', req(confirmation=True,
            payment_id=payment['id'], source_hash=source['source_hash'], account_id=self.account['id'],
            account_revision=self.account['revision'], cash_date=self.today,
            evidence_reference='Synthetic actual bank payment after opening'), status=201).json
        self.document(event); self.post('cash', self.cash(event))
        exported, export_command = self.post('export', dict(year=int(self.today[:4])))
        old_export = self.call('GET', '/business/accounting/euer/exports/' + exported['id']).json
        original, upload, raw = self.original(); command = self.command(original)
        accepted = self.call('POST', BASE + '/confirm', command, status=201).json
        opening_scope = self.assert_scope((1, 1, 2))
        self.assertEqual(self.call('GET', '/business/accounting/euer/exports/' + exported['id']).json, old_export)
        liquidity = self.call('GET', BASE + '/liquidity?as_of=' + self.today).json
        self.assertEqual(liquidity['balance_total'], '619.00')
        source_fingerprints = release.snapshot_fingerprint(fixture.DSN)
        self.office.db.close()
        with disposable_restore(self.runtime) as (target, runtime, report):
            restored = PostgresOffice(runtime)
            try:
                api = OpeningBalances(restored)
                self.assertEqual(restore_horizon(restored), opening_scope)
                self.assertEqual(api.original(self.actor, original['id'])[0], raw)
                self.assertEqual(EuerAccounting(restored).exported(self.actor, exported['id']), old_export)
                with self.assertRaises(Problem) as blocked:
                    api.confirm(self.actor, command)
                self.assertEqual(blocked.exception.status, 409)
                with self.assertRaises(Problem) as blocked:
                    api.upload_original(self.actor, upload)
                self.assertEqual(blocked.exception.status, 409)
                pending = api.liquidity(self.actor, self.today)
                self.assertFalse(pending['complete_for_recorded_accounts'])
                self.assertIsNone(pending['balance_total'])
                self.assertIn('restore_reconciliation_pending', [item['code'] for item in pending['issues']])
                evidence = evidence_for(restored, report)
                self.assertEqual(evidence['schema'], 16)
                self.assertEqual(evidence['accounting_horizon']['opening_balances'], opening_scope)
                with self.assertRaises(Problem) as denied:
                    approve(restored, evidence)
                self.assertEqual(denied.exception.status, 403)
            finally:
                restored.db.close()
            operator = PostgresOffice(target)
            try:
                old = deepcopy(evidence)
                old['schema'] = 12
                old['accounting_horizon'].pop('year_values')
                old['accounting_horizon'].pop('opening_balances')
                old['accounting_horizon'].pop('opening_items');old['accounting_horizon'].pop('historical_assets')
                old['accounting_horizon']['schema_version'] = 11
                business_schema._validate_financial_accounting_horizon(old['accounting_horizon'], 12)
                before = release.snapshot_fingerprint(target)
                for invalid in (old, deepcopy(evidence)):
                    if invalid is not old:
                        invalid['accounting_horizon']['opening_balances']['sha256'] = '0' * 64
                    with self.assertRaises((ValueError, Problem)):
                        approve(operator, invalid)
                    self.assertEqual(release.snapshot_fingerprint(target), before)
                approved = approve(operator, evidence)
                self.assertTrue(approved['reconciled'])
                self.assertEqual(approve(operator, evidence), approved)
            finally:
                operator.db.close()
            restored = PostgresOffice(runtime)
            try:
                api = OpeningBalances(restored)
                self.assertEqual(api.confirm(self.actor, command), accepted)
                self.assertEqual(api.upload_original(self.actor, upload), original)
                self.assertEqual(api.original(self.actor, original['id'])[0], raw)
                self.assertEqual(api.liquidity(self.actor, self.today)['balance_total'], '619.00')
                self.assertEqual(EuerAccounting(restored).confirm(self.actor, export_command), exported)
                self.assertEqual(canonical(EuerAccounting(restored).exported(self.actor, exported['id'])), canonical(old_export))
                self.assertEqual(restore_horizon(restored), opening_scope)
                self.assertTrue(business_schema.validate_integrity(restored))
                fingerprints = release.snapshot_fingerprint(target)
                for table in TABLES + ('business_euer_entries', 'business_euer_requests'):
                    self.assertEqual(fingerprints[table], source_fingerprints[table])
            finally:
                restored.db.close()


if __name__ == '__main__':
    unittest.main()
