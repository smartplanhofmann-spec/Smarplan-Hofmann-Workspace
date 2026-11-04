"""Real isolated opening balances; no provider, real account or tax posting."""
import base64
from copy import deepcopy
from datetime import datetime, timezone
import json
import sqlite3
import unittest
from unittest.mock import patch
import uuid

import business_schema
from business_accounting_openings import OpeningBalances, BASE, INPUT, TABLES, dispatch, profile_reference, restore_horizon, validate_integrity
from business_bank_reconciliation import BankReconciliation, HEADERS
from business_operations import transaction
from core import Problem, canonical
import test_business_accounting_euer as euer_fixture


class OpeningWorkflow(unittest.TestCase):
    def setUp(self):
        self.fixture = euer_fixture.EuerWorkflowTests('runTest'); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.office = self.fixture.office; self.owner = self.fixture.owner
        self.cash = self.fixture.fixture.api; self.account = self.fixture.fixture.account
        self.now = datetime(2026, 12, 31, 12, tzinfo=timezone.utc)
        self.api = OpeningBalances(self.office, clock=lambda: self.now)

    def request(self, **value):
        return dict(request_id=uuid.uuid4().hex, **value)

    def failure(self, status, method, *args):
        with self.assertRaises(Problem) as caught:
            method(*args)
        self.assertEqual(caught.exception.status, status, caught.exception.message)
        return caught.exception

    def original(self, account=None, marker='opening'):
        account = account or self.account
        raw = ('%PDF-1.4\nSynthetic original ' + marker + '\n%%EOF\n').encode()
        command = self.request(account_id=account['id'], filename='synthetic-opening.pdf', media_type='application/pdf', content_base64=base64.b64encode(raw).decode())
        return self.api.upload_original(self.owner, command), command, raw

    def body(self, amount='1000.00', account=None, source=None, status='active', **changes):
        account = account or self.account; state = self.api.state(self.owner)
        if source is None:
            original, _, _ = self.original(account)
            source = dict(kind='original', original_id=original['id'], sha256=original['sha256'],
                          evidence_type='cash_count' if account['kind'] == 'cash' else 'account_statement', at_start_of_day=True)
        return dict(expected_revision=state['revision'], state_hash=state['state_hash'], account_id=account['id'], account_revision=account['revision'],
                    profile_ref=state['profile_ref'], status=status, opening_date=state['profile']['profile']['bookkeeping_start'],
                    amount=amount, source=source, reason='Synthetic original and exact opening balance reviewed') | changes

    def command(self, body):
        preview = self.api.preview(self.owner, body)
        return self.request(**body, confirmation=True, preview_hash=preview['preview_hash'])

    def save(self, **changes):
        command = self.command(self.body(**changes))
        return self.api.confirm(self.owner, command), command

    def bank_statement(self, opening='1000.00', closing=None, start='2026-01-01', end='2026-01-31'):
        bank = BankReconciliation(self.office, clock=lambda: self.now)
        if not self.office.db.execute('SELECT 1 FROM business_bank_account_versions WHERE account_id=?', (self.account['id'],)).fetchone():
            binding = bank.save_account(self.owner, self.request(account_id=self.account['id'], account_revision=1, revision=0,
                iban='DE89370400440532013000', label='Synthetic bank evidence', active=True, coverage_from='2025-01-01', coverage_to=None, reason=''))
        else:
            binding = bank._account(self.account['id'])
        raw = (';'.join(HEADERS) + '\n').encode()
        body = dict(account_id=self.account['id'], account_revision=1, bank_revision=binding['revision'], statement_reference='Synthetic-' + uuid.uuid4().hex,
                    period_from=start, period_to=end, opening_balance=opening, closing_balance=closing or opening, filename='synthetic.csv', delimiter=';',
                    content_base64=base64.b64encode(raw).decode(), complete_statement_confirmed=True)
        preview = bank.preview_import(self.owner, body)
        self.assertTrue(preview['can_import'], preview['errors'])
        return bank.import_statement(self.owner, self.request(**body, confirmation=True, preview_hash=preview['preview_hash']))['statement']

    def test_no_opening_is_unknown_but_explicit_zero_is_a_real_evidenced_state(self):
        empty = self.api.liquidity(self.owner, '2026-11-02')
        self.assertIsNone(empty['balance_total']); self.assertIsNone(empty['accounts'][0]['balance'])
        self.assertIsNone(empty['known_balance_sum']); self.assertEqual(empty['known_account_count'], 0)
        self.assertEqual(empty['accounts'][0]['issues'], [dict(code='opening_balance_missing')])
        saved, command = self.save(amount='0.00')
        self.assertEqual(self.api.liquidity(self.owner, '2026-11-02')['balance_total'], '0.00')
        self.assertFalse(saved['cash_flow_created']); self.assertFalse(saved['tax_postings_created'])
        self.assertEqual(saved['balance_timing'], 'start_of_day'); self.assertEqual(saved['timezone'], 'Europe/Berlin')
        self.assertEqual(self.api.confirm(self.owner, command), saved)

    def test_1000_plus_actual_119_minus_actual_59_50_is_1059_50_without_euer_income(self):
        f = self.fixture
        income = f.sale(); f.post('cash', f.cash_payload(income))
        receipt = f.incoming(); f.post('input_vat', f.vat_payload(receipt)); expense = f.payout(receipt)
        f.post('cash', f.cash_payload(expense, 'materials'))
        before = f.api.report(self.owner, 2026)
        export = f.post('export', dict(year=2026)); artifact = f.api.exported(self.owner, export['id'])
        counts = {table: self.office.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0] for table in
                  ('business_accounting_cash_events', 'business_euer_entries', 'business_incoming_receipts', 'business_payments')}
        saved, _ = self.save()
        result = self.api.liquidity(self.owner, '2026-11-02')
        self.assertEqual((result['accounts'][0]['inflows'], result['accounts'][0]['outflows'], result['balance_total']), ('119.00', '59.50', '1059.50'))
        self.assertEqual(f.api.report(self.owner, 2026)['totals'], before['totals'])
        self.assertEqual(f.api.exported(self.owner, export['id']), artifact)
        self.assertEqual(counts, {table: self.office.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0] for table in counts})
        self.assertTrue(validate_integrity(self.office)); self.assertTrue(business_schema.validate_integrity(self.office))

    def test_bank_negative_cash_nonnegative_and_exact_signed_cent_contract(self):
        self.save(amount='-120.01')
        self.assertEqual(self.api.liquidity(self.owner, '2026-11-02')['balance_total'], '-120.01')
        cash = self.cash.create_account(self.owner, dict(self.request(code='CASH', name='Synthetic counted cash', kind='cash'), confirmation=True))
        self.failure(400, self.api.preview, self.owner, self.body(amount='-0.01', account=cash))
        for amount in ('-0.00', '+1.00', '1', '01.00', '1.001', '1,00', 0, True):
            self.failure(400, self.api.preview, self.owner, self.body(amount=amount, account=cash))
        self.save(amount='0.00', account=cash)
        self.assertTrue(self.api.liquidity(self.owner, '2026-11-02')['complete_for_recorded_accounts'])

    def test_existing_bank_opening_and_previous_closing_are_derived_exactly(self):
        before = self.bank_statement(opening='-100.00', start='2025-12-01', end='2025-12-31')
        current = self.bank_statement(opening='-100.00')
        sources = self.api.sources(self.owner, self.account['id'])
        self.assertEqual(len(sources['bank_statements']), 2)
        for source in sources['bank_statements']:
            body = self.body(amount='-100.00', source=source['source'])
            self.api.preview(self.owner, body)
            self.failure(409, self.api.preview, self.owner, dict(body, amount='-99.99'))
        source = dict(kind='bank_statement', statement_id=current['id'], content_hash=current['content_hash'], balance_side='opening')
        saved, _ = self.save(amount='-100.00', source=source)
        result = self.api.liquidity(self.owner, '2026-01-31')
        self.assertEqual(result['balance_total'], '-100.00')
        self.assertTrue(all(item['matches'] for item in result['accounts'][0]['bank_connections']))
        self.assertEqual(saved['source_proof']['statement_id'], current['id'])

    def test_present_bank_connection_blocks_conflicting_manual_original_and_later_conflict_is_visible(self):
        body = self.body(amount='1000.00')
        self.bank_statement(opening='900.00')
        self.failure(409, self.api.preview, self.owner, body)
        self.save(amount='900.00', source=body['source'])
        self.bank_statement(opening='899.00', start='2026-02-01', end='2026-02-28')
        result = self.api.liquidity(self.owner, '2026-02-28')
        self.assertIsNone(result['balance_total']); self.assertIsNone(result['accounts'][0]['balance'])
        self.assertEqual(result['accounts'][0]['calculated_balance'], '900.00')
        self.assertTrue(any(item['code'] == 'bank_statement_connection_mismatch' for item in result['accounts'][0]['issues']))

    def test_start_day_is_included_earlier_cash_is_not_added_twice(self):
        f = self.fixture
        old = f.incoming(day='2026-10-31'); f.payout(old, day='2026-11-01')
        income = f.sale()
        self.assertEqual(income['cash_date'], '2026-11-02')
        f.configure(bookkeeping_start='2026-11-02')
        self.save(amount='1000.00')
        current = self.api.liquidity(self.owner, '2026-11-02')
        self.assertEqual(current['balance_total'], '1119.00')
        self.assertEqual(len(current['accounts'][0]['movements']), 1)
        prior = self.api.liquidity(self.owner, '2026-11-01')
        self.assertIsNone(prior['balance_total'])
        self.assertEqual(prior['accounts'][0]['issues'], [dict(code='as_of_before_opening')])

    def test_late_previous_period_statement_is_checked_against_the_opening(self):
        self.save(amount='1000.00')
        self.bank_statement(opening='900.00', start='2025-12-01', end='2025-12-31')
        result = self.api.liquidity(self.owner, '2026-01-01')
        self.assertIsNone(result['balance_total']); self.assertIsNone(result['known_balance_sum'])
        self.assertEqual(result['accounts'][0]['calculated_balance'], '1000.00')
        self.assertEqual(result['accounts'][0]['issues'][0]['balance_side'], 'closing')

    def test_negative_recorded_cash_balance_stays_an_explicit_review_case(self):
        account = self.cash.create_account(self.owner, dict(self.request(code='COUNTED', name='Synthetic cash account', kind='cash'), confirmation=True))
        self.save(account=account, amount='10.00')
        receipt = self.fixture.incoming(net='59.50', tax='0.00', gross='59.50')
        body = self.fixture.external_payload(receipt, amount='59.50', category='owner_withdrawal', day='2026-11-02')
        body.update(account_id=account['id'], account_revision=account['revision'])
        self.fixture.post('external_cash', body)
        result = self.api.liquidity(self.owner, '2026-11-02')
        row = next(item for item in result['accounts'] if item['account']['id'] == account['id'])
        self.assertEqual(row['calculated_balance'], '-49.50'); self.assertIsNone(row['balance'])
        self.assertEqual(row['issues'], [dict(code='cash_balance_negative')])

    def test_unknown_unimported_payment_remains_visible_and_prevents_complete_liquidity(self):
        self.save()
        self.fixture.fixture.payment()
        result = self.api.liquidity(self.owner, '2026-11-02')
        self.assertIsNone(result['balance_total'])
        self.assertEqual(result['known_balance_sum'], '1000.00')
        self.assertEqual(result['unresolved_cash_sources'][0]['code'], 'cash_import_missing')

    def test_correction_void_and_original_replay_preserve_previous_history(self):
        first, first_command = self.save()
        second, _ = self.save(amount='1001.00')
        body = {key: second[key] for key in INPUT}
        state = self.api.state(self.owner); body.update(expected_revision=state['revision'], state_hash=state['state_hash'], status='void', reason='Synthetic reviewed reversal')
        third = self.api.confirm(self.owner, self.command(body))
        self.assertEqual(third['revision'], 3)
        self.assertIsNone(self.api.liquidity(self.owner, '2026-11-02')['balance_total'])
        self.assertEqual(self.api.confirm(self.owner, first_command), first)
        self.assertEqual(self.api.history(self.owner, self.account['id'])['items'][:2], [first, second])
        self.assertTrue(validate_integrity(self.office))

    def test_profile_and_account_changes_require_fresh_explicit_correction_but_not_historical_replay(self):
        first, command = self.save()
        self.fixture.configure(bookkeeping_start='2026-02-01')
        self.assertEqual(self.api.confirm(self.owner, command), first)
        self.assertIsNone(self.api.liquidity(self.owner, '2026-11-02')['balance_total'])
        self.failure(409, self.api.preview, self.owner, self.body(opening_date='2026-01-01'))
        self.save(amount='1010.00')
        self.assertEqual(self.api.liquidity(self.owner, '2026-11-02')['balance_total'], '1010.00')
        self.cash.update_account(self.owner, self.account['id'], dict(self.request(revision=1, name='Corrected bank label', active=True), confirmation=True))
        self.failure(409, self.api.preview, self.owner, self.body())
        self.assertEqual(self.api.confirm(self.owner, command), first)

    def test_later_closed_euer_period_blocks_restatement_not_read_only_original_replay(self):
        first, command = self.save()
        self.fixture.post('period', dict(period='2026-11', action='close', expected_period_revision=0,
            attestation=dict(bank_reconciled=True, originals_complete=True, special_cases_reviewed=True)))
        self.failure(409, self.api.preview, self.owner, self.body(amount='1001.00'))
        self.assertEqual(self.api.confirm(self.owner, command), first)
        self.fixture.post('period', dict(period='2026-11', action='reopen', expected_period_revision=1,
            attestation=dict(bank_reconciled=False, originals_complete=False, special_cases_reviewed=False)))
        self.save(amount='1001.00')

    def test_stale_preview_and_request_id_changes_cannot_overwrite_a_committed_balance(self):
        body = self.body(); stale = self.command(body)
        saved, command = self.save(amount='2.00')
        error = self.failure(409, self.api.confirm, self.owner, stale)
        self.assertEqual(error.request_resolution, 'not_accepted')
        changed = dict(command, amount='3.00')
        self.failure(409, self.api.confirm, self.owner, changed)
        self.assertEqual(self.api.state(self.owner)['items'], [saved])

    def test_failed_audit_rolls_back_balance_receipt_and_all_cash_tables(self):
        command = self.command(self.body())
        with patch.object(self.office, 'audit', side_effect=RuntimeError('Synthetic interrupted commit')):
            with self.assertRaises(RuntimeError):
                self.api.confirm(self.owner, command)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_accounting_opening_events').fetchone()[0], 0)
        self.assertEqual(self.office.db.execute("SELECT COUNT(*) FROM business_accounting_opening_requests WHERE operation='confirm'").fetchone()[0], 0)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_accounting_cash_events').fetchone()[0], 0)
        self.api.confirm(self.owner, command)

    def test_original_is_retained_account_bound_deduplicated_and_private(self):
        original, command, raw = self.original()
        self.assertEqual(self.api.upload_original(self.owner, command), original)
        self.assertEqual(self.api.upload_original(self.owner, dict(command, request_id=uuid.uuid4().hex)), original)
        content, status, mime = dispatch(self.office, self.owner, BASE + '/originals/' + original['id'], 'GET', {})
        self.assertEqual((bytes(content), status, mime), (raw, 200, 'application/pdf'))
        self.assertEqual(content.filename, 'synthetic-opening.pdf')
        self.failure(403, self.api.original, self.fixture.fixture.tech, original['id'])
        other = self.cash.create_account(self.owner, dict(self.request(code='OTHER', name='Other account', kind='cash'), confirmation=True))
        self.failure(409, self.api.preview, self.owner, self.body(account=other, source=dict(kind='original', original_id=original['id'], sha256=original['sha256'], evidence_type='cash_count', at_start_of_day=True)))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_accounting_opening_originals').fetchone()[0], 1)
        self.assertTrue(validate_integrity(self.office))

    def test_known_permission_revocation_blocks_replay_and_originals(self):
        f = self.fixture.fixture
        actor = f.tech
        for permission in ('accounting.read', 'finance.read', 'bank.read', 'accounting.admin', 'accounting.prepare', 'finance.write'):
            f.grant(actor, permission)
        command = self.command(self.body()); saved = self.api.confirm(actor, command)
        self.assertEqual(self.api.confirm(actor, command), saved)
        f.grant(actor, 'accounting.admin', effect='deny', revision=1)
        self.failure(403, self.api.confirm, actor, command)
        f.grant(actor, 'bank.read', effect='deny', revision=1)
        self.failure(403, self.api.state, actor)
        self.failure(403, self.api.original, actor, saved['source']['original_id'])

    def test_binary_and_receipt_tampering_are_not_hidden_by_replay_or_restore(self):
        saved, command = self.save()
        original = saved['source']['original_id']
        with transaction(self.office):
            self.office.db.execute('DROP TRIGGER business_accounting_opening_originals_update_guard')
            self.office.db.execute('UPDATE business_accounting_opening_originals SET original=? WHERE id=?', (b'%PDF-1.4\nChanged\n%%EOF', original))
        self.failure(409, self.api.confirm, self.owner, command)
        with self.assertRaises(ValueError):
            restore_horizon(self.office)

    def test_future_stichtag_and_wrong_date_do_not_create_a_real_balance(self):
        self.now = datetime(2026, 1, 1, 0, tzinfo=timezone.utc)
        self.failure(400, self.api.liquidity, self.owner, '2026-01-02')
        self.failure(409, self.api.preview, self.owner, self.body(opening_date='2025-12-31'))
        self.fixture.configure(bookkeeping_start='2026-01-02')
        self.failure(409, self.api.preview, self.owner, self.body())


if __name__ == '__main__':
    unittest.main()
