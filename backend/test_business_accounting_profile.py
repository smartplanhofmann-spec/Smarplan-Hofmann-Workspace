"""Explicit preparation profiles on real isolated SQLite business databases."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import uuid

from core import Office, Problem, canonical
from business_accounting import Accounting, _sha
from business_accounting_profile import (AccountingPreparationProfile, dispatch, installed, methods,
    protected_tables, restore_horizon, validate_integrity, _state_hash)
from business_foundation import BusinessFoundation
from business_schema import ensure_schema, set_mode


class PreparationProfileTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='synthetic-preparation-profile-')
        self.addCleanup(temporary.cleanup)
        self.office = Office(Path(temporary.name)/'office.db')
        self.addCleanup(self.office.db.close)
        ensure_schema(self.office, activate=True)
        self.owner = self.actor('owner'); self.reader = self.actor('technician')
        self.clock = lambda: datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
        self.api = AccountingPreparationProfile(self.office, clock=self.clock)

    def actor(self, role):
        email = uuid.uuid4().hex+'@example.test'
        return dict(id=self.office.add_user(email, 'Synthetic-password-123', role), role=role, email=email)

    def problem(self, status, method, *args, resolution=None):
        with self.assertRaises(Problem) as caught:
            method(*args)
        self.assertEqual(caught.exception.status, status, caught.exception.message)
        self.assertEqual(caught.exception.request_resolution, resolution)
        return caught.exception

    def grant(self, name, *, effect='allow', revision=0):
        return BusinessFoundation(self.office).save_grant(self.owner, dict(request_id=uuid.uuid4().hex,
            user_id=self.reader['id'], permission=name, scope='*', effect=effect, revision=revision))

    def snapshot(self, tables=None):
        tables = tables or [row[0] for row in self.office.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return {table: sorted((tuple(row) for row in self.office.db.execute('SELECT * FROM '+table)), key=repr) for table in tables}

    @staticmethod
    def profile(**changes):
        return dict(legal_form='sole_proprietorship', accounting_method='euer', vat_regime=None,
                    vat_timing=None, vat_effective_from=None, bookkeeping_start=None) | changes

    def body(self, **changes):
        state = self.api.state(self.owner)
        return dict(expected_revision=state['revision'], state_hash=state['state_hash'], profile=self.profile(),
                    reason='Explicit preparation facts only', evidence_reference='Owner statement, synthetic fixture') | changes

    def command(self, *, actor=None, **changes):
        body = self.body(**changes); preview = self.api.preview(actor or self.owner, body)
        return dict(body, request_id=uuid.uuid4().hex, preview_hash=preview['preview_hash'], confirmation=True)

    def test_empty_reads_migration_and_preview_never_create_profile_or_tax_defaults(self):
        before = self.snapshot(); state = self.api.state(self.owner)
        self.assertEqual(state, dict(revision=0, state_hash=_state_hash(0), preparation_status='unrecorded',
            current=None, writes_allowed=True, scope='organization_profile', tax_status='unconfigured', tax_result_available=False))
        self.assertEqual(self.api.history(self.owner), dict(items=[], total=0, next_offset=None, scope='organization_profile'))
        body = self.body(); original = deepcopy(body); preview = self.api.preview(self.owner, body)
        self.assertEqual(preview['profile'], self.profile()); self.assertEqual(body, original)
        self.assertEqual(preview['preview_hash'], _sha(canonical({key: value for key, value in preview.items() if key != 'preview_hash'})))
        ensure_schema(self.office, activate=True)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(restore_horizon(self.office)['table_counts'], {table: 0 for table in protected_tables()})
        self.assertEqual(Accounting(self.office).status(self.owner)['profile_status'], 'unconfigured')

    def test_optional_vat_and_dates_are_explicit_independent_facts(self):
        for regime in (None, 'small_business', 'regular'):
            for timing in (None, 'cash', 'accrual'):
                for effective in (None, '2026-01-01'):
                    body = self.body(profile=self.profile(vat_regime=regime, vat_timing=timing,
                                                         vat_effective_from=effective, bookkeeping_start='2026-12-31'))
                    with self.subTest(regime=regime, timing=timing, effective=effective):
                        allowed = (timing is None or regime == 'regular') and (effective is None or regime is not None)
                        if allowed:
                            self.assertEqual(self.api.preview(self.owner, body)['profile'], body['profile'])
                        else:
                            self.problem(400, self.api.preview, self.owner, body)
        for date in ('1900-01-01', '2000-02-29', '2200-12-31'):
            self.api.preview(self.owner, self.body(profile=self.profile(bookkeeping_start=date)))
        for value in ('', '2026-02-29', '2026-1-01', '1899-12-31', '2201-01-01', True, 20260101):
            self.problem(400, self.api.preview, self.owner, self.body(profile=self.profile(bookkeeping_start=value)))

    def test_exact_input_shapes_enums_texts_hashes_and_confirmation(self):
        body = self.body(); command = self.command()
        invalid = [dict(body, extra='no'), {key: value for key, value in body.items() if key != 'profile'},
                   dict(body, expected_revision=True), dict(body, expected_revision=-1), dict(body, expected_revision='0'),
                   dict(body, state_hash='A'*64), dict(body, state_hash=False)]
        for name, values in (('legal_form', ('company', None, False)), ('accounting_method', ('balance', None, False)),
                             ('vat_regime', ('unknown', '', False, 0)), ('vat_timing', ('unknown', '', False, 0))):
            invalid.extend(dict(body, profile=self.profile(**{name: value})) for value in values)
        invalid.extend((dict(body, profile={}), dict(body, profile=dict(self.profile(), extra='no')), dict(body, profile=None)))
        for name, maximum in (('reason', 1000), ('evidence_reference', 200)):
            invalid.extend(dict(body, **{name: value}) for value in ('', '  ', 'a'*(maximum+1), 'line\nbreak', '\x7f', '\ud800', None))
            self.api.preview(self.owner, dict(body, **{name: 'a'*maximum}))
        for data in invalid:
            with self.subTest(data=repr(data)):
                self.problem(400, self.api.preview, self.owner, data)
        for changes in ({'confirmation':False}, {'confirmation':1}, {'request_id':'A'*32}, {'preview_hash':None}, {'extra':False}):
            self.problem(400, self.api.confirm, self.owner, dict(command, **changes))
        spaced = self.body(reason='  Original reason  ', evidence_reference='  Original reference  ')
        preview = self.api.preview(self.owner, spaced)
        self.assertEqual((preview['reason'], preview['evidence_reference']), (spaced['reason'], spaced['evidence_reference']))

    def test_versions_history_and_old_exact_replays_never_rewrite_facts(self):
        first_command = self.command(); first = self.api.confirm(self.owner, first_command)
        first_rows = self.snapshot(protected_tables())
        second_command = self.command(profile=self.profile(vat_regime='regular', vat_timing='cash', vat_effective_from='2026-01-01'),
                                      reason='Later explicitly stated preparation facts')
        second = self.api.confirm(self.owner, second_command)
        self.assertEqual((first['revision'], second['revision']), (1, 2))
        self.assertEqual(first['profile'], self.profile())
        self.assertEqual(self.api.confirm(self.owner, first_command), first)
        self.assertEqual(self.api.confirm(self.owner, second_command), second)
        self.assertEqual(self.api.history(self.owner, 1, 0), dict(items=[second], total=2, next_offset=1, scope='organization_profile'))
        self.assertEqual(self.api.history(self.owner, 1, 1), dict(items=[first], total=2, next_offset=None, scope='organization_profile'))
        self.assertEqual(self.api.state(self.owner)['current'], second)
        for table, rows in first_rows.items():
            self.assertTrue(all(row in self.snapshot((table,))[table] for row in rows))
        self.assertEqual(Accounting(self.office).status(self.owner)['profile_status'], 'unconfigured')
        self.assertTrue(validate_integrity(self.office))

    def test_identical_facts_can_be_explicitly_recorded_again_without_deduplication(self):
        first = self.api.confirm(self.owner, self.command())
        second = self.api.confirm(self.owner, self.command(reason='Another explicit confirmation', evidence_reference='Second owner statement'))
        self.assertEqual(first['profile'], second['profile']); self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(self.api.state(self.owner)['revision'], 2)

    def test_receipt_identity_is_scoped_to_the_fresh_confirming_user(self):
        first_command = self.command(); first = self.api.confirm(self.owner, first_command)
        for permission in ('accounting.read', 'finance.read', 'accounting.admin'):
            self.grant(permission)
        self.problem(409, self.api.confirm, self.reader, first_command, resolution='not_accepted')
        second_command = dict(self.command(actor=self.reader, reason='Own later declaration'), request_id=first_command['request_id'])
        second = self.api.confirm(self.reader, second_command)
        self.assertEqual((first['revision'], second['revision']), (1, 2))
        self.assertEqual(second['created_by'], self.reader['id'])
        self.assertEqual(self.api.confirm(self.owner, first_command), first)
        self.assertEqual(self.api.confirm(self.reader, second_command), second)

    def test_profile_versions_leave_genuine_mixed_refund_and_reuse_evidence_unchanged(self):
        from test_business_accounting_refunds_v2 import VersionedRefundDomainTests
        from business_schema import financial_accounting_horizon, registered_table_names
        fixture = VersionedRefundDomainTests('runTest'); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        invoice, middle, old_refund, old_return, receipt, reused, positive_command = fixture.mixed_seed()
        unused, refund = fixture.cash_event(invoice, '26.44', kind='refund')
        group = middle['lines'][0]['group_id']
        command = fixture.versioned_command(refund, [('c1', middle['id'], group, '13.22'), ('c2', reused['id'], group, '13.22')])
        returned = fixture.r2.confirm(fixture.owner, refund['id'], command)
        unused, next_receipt = fixture.cash_event(invoice, '26.44')
        next_command = fixture.capacity_command(next_receipt)
        next_entry = fixture.capacity.confirm(fixture.owner, next_receipt['id'], next_command)
        old_tables = sorted(registered_table_names()-set(protected_tables()))
        before = fixture.snapshot(old_tables); old_horizon = financial_accounting_horizon(fixture.office)
        profile = AccountingPreparationProfile(fixture.office, clock=fixture.clock)
        for declared in (self.profile(), self.profile(vat_regime='small_business')):
            state = profile.state(fixture.owner)
            body = dict(expected_revision=state['revision'], state_hash=state['state_hash'], profile=declared,
                        reason='Explicit independent preparation facts', evidence_reference='Synthetic owner statement')
            preview = profile.preview(fixture.owner, body)
            profile.confirm(fixture.owner, dict(body, request_id=uuid.uuid4().hex, preview_hash=preview['preview_hash'], confirmation=True))
        self.assertEqual(fixture.snapshot(old_tables), before)
        current_horizon = financial_accounting_horizon(fixture.office)
        self.assertEqual({key: value for key, value in current_horizon.items() if key != 'profile'},
                         {key: value for key, value in old_horizon.items() if key != 'profile'})
        self.assertNotEqual(current_horizon['profile'], old_horizon['profile'])
        self.assertEqual(fixture.r2.confirm(fixture.owner, refund['id'], command), returned)
        self.assertEqual(fixture.capacity.confirm(fixture.owner, next_receipt['id'], next_command), next_entry)
        self.assertEqual(fixture.capacity.confirm(fixture.owner, receipt['id'], positive_command), reused)
        self.assertEqual(fixture.refunds.history(fixture.owner, old_refund['id'])['items'], [old_return])

    def test_current_global_admin_rights_are_required_even_for_an_old_replay(self):
        body = self.body(); self.problem(403, self.api.state, self.reader)
        self.grant('accounting.read'); self.grant('finance.read')
        self.assertFalse(self.api.state(self.reader)['writes_allowed'])
        self.grant('accounting.prepare'); self.grant('finance.write')
        self.problem(403, self.api.preview, self.reader, body)
        self.grant('accounting.admin')
        command = self.command(actor=self.reader); entry = self.api.confirm(self.reader, command)
        self.grant('accounting.admin', effect='deny', revision=1)
        self.problem(403, self.api.confirm, self.reader, command)
        self.assertEqual(self.api.history(self.reader)['items'], [entry])
        self.grant('accounting.admin', revision=2)
        self.assertEqual(self.api.confirm(self.reader, command), entry)
        self.grant('finance.read', effect='deny', revision=1)
        self.problem(403, self.api.history, self.reader)
        self.problem(403, self.api.confirm, self.reader, command)

    def test_mode_finance_and_restore_gates_precede_receipt_and_preserve_history(self):
        from business_organization import Organization, _stored as organization_state
        command = self.command(); entry = self.api.confirm(self.owner, command)
        set_mode(self.office, 'legacy')
        self.assertFalse(self.api.state(self.owner)['writes_allowed'])
        self.assertEqual(self.api.history(self.owner)['items'], [entry])
        self.problem(409, self.api.confirm, self.owner, command)
        set_mode(self.office, 'business')
        organization = organization_state(self.office)
        organization['modules']['finance']['enabled'] = False
        Organization(self.office).save(self.owner, dict(request_id=uuid.uuid4().hex,
            **{key: organization[key] for key in ('revision', 'needs', 'modules')}))
        self.problem(423, self.api.confirm, self.owner, command)
        self.assertFalse(self.api.state(self.owner)['writes_allowed'])
        organization = organization_state(self.office); organization['modules']['finance']['enabled'] = True
        Organization(self.office).save(self.owner, dict(request_id=uuid.uuid4().hex,
            **{key: organization[key] for key in ('revision', 'needs', 'modules')}))
        with self.office.db:
            self.office.db.execute('UPDATE business_restore_state SET financial_reconciliation_required=1,restore_id=?', (uuid.uuid4().hex,))
        self.problem(409, self.api.confirm, self.owner, command)
        self.assertEqual(self.api.history(self.owner)['items'], [entry])
        with self.office.db:
            self.office.db.execute('UPDATE business_restore_state SET financial_reconciliation_required=0')
        self.assertEqual(self.api.confirm(self.owner, command), entry)

    def test_only_definitively_unaccepted_current_conflicts_have_resolution_marker(self):
        first = self.command(); stale = self.command(reason='Competing current confirmation')
        self.api.confirm(self.owner, first)
        self.problem(409, self.api.confirm, self.owner, stale, resolution='not_accepted')
        self.problem(409, self.api.confirm, self.owner, dict(first, reason='Changed accepted request'))
        command = self.command()
        self.problem(409, self.api.confirm, self.owner, dict(command, preview_hash='f'*64), resolution='not_accepted')
        with patch.object(self.api, '_gate', side_effect=Problem(409, 'Synthetic security gate')):
            self.problem(409, self.api.confirm, self.owner, first)

    def test_two_concurrent_confirmations_have_one_winner_and_same_request_replays(self):
        left = self.command(); right = self.command(reason='Concurrent other profile')
        def run(command):
            try:
                return self.api.confirm(self.owner, command)
            except Problem as error:
                return error
        with ThreadPoolExecutor(max_workers=2) as executor:
            values = list(executor.map(run, (left, right)))
        self.assertEqual(sum(isinstance(value, dict) for value in values), 1)
        error = next(value for value in values if isinstance(value, Problem))
        self.assertEqual((error.status, error.request_resolution), (409, 'not_accepted'))
        command = self.command(reason='Concurrent identical request')
        with ThreadPoolExecutor(max_workers=2) as executor:
            values = list(executor.map(run, (command, deepcopy(command))))
        self.assertEqual(values[0], values[1]); self.assertEqual(self.api.state(self.owner)['revision'], 2)

    def test_audit_failure_rolls_back_version_receipt_and_revision_then_allows_retry(self):
        command = self.command(); before = self.snapshot()
        with patch.object(self.office, 'audit', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.api.confirm(self.owner, command)
        self.assertEqual(self.snapshot(), before)
        entry = self.api.confirm(self.owner, command)
        self.assertEqual(entry['revision'], 1); self.assertTrue(validate_integrity(self.office))

    def test_rehashed_fake_previous_head_is_rejected_against_actual_prefix(self):
        self.api.confirm(self.owner, self.command())
        command = self.command(reason='Second profile'); entry = self.api.confirm(self.owner, command)
        fake_hash = _state_hash(1, dict(id='f'*32, entry_sha256='e'*64))
        altered = dict(command, state_hash=fake_hash)
        altered['preview_hash'] = self.api._preview(altered)['preview_hash']
        changed = dict(entry, previous_state_hash=fake_hash, preview_hash=altered['preview_hash'])
        with self.office.db:
            for table in protected_tables():
                self.office.db.execute('DROP TRIGGER '+table+'_update_guard')
            self.office.db.execute('UPDATE business_accounting_profile_versions SET previous_state_hash=?,entry_json=?,entry_sha256=? WHERE id=?',
                (fake_hash, canonical(changed), _sha(canonical(changed)), entry['id']))
            self.office.db.execute('UPDATE business_accounting_profile_requests SET request_json=?,request_hash=? WHERE entry_id=?',
                (canonical(altered), self.api._request_hash(altered), entry['id']))
        self.problem(409, self.api.history, self.owner)
        self.problem(409, self.api.confirm, self.owner, altered)
        with self.assertRaises(ValueError):
            validate_integrity(self.office)

    def test_broken_receipts_revision_gaps_flags_and_timestamps_fail_closed(self):
        command = self.command(); entry = self.api.confirm(self.owner, command)
        mutations = (
            ("UPDATE business_accounting_profile_versions SET revision=2", ()),
            ("DELETE FROM business_accounting_profile_requests", ()),
            ("UPDATE business_accounting_profile_requests SET request_hash=?", ('e'*64,)),
        )
        for sql, arguments in mutations:
            self.office.db.execute('SAVEPOINT synthetic_profile_tamper')
            try:
                for table in protected_tables():
                    for action in ('update', 'delete'):
                        self.office.db.execute('DROP TRIGGER '+table+'_'+action+'_guard')
                self.office.db.execute(sql, arguments)
                self.problem(409, self.api.state, self.owner)
                self.problem(409, self.api.confirm, self.owner, command)
            finally:
                self.office.db.execute('ROLLBACK TO SAVEPOINT synthetic_profile_tamper')
                self.office.db.execute('RELEASE SAVEPOINT synthetic_profile_tamper')
        for changed in (dict(entry, tax_result_available=0), dict(entry, tax_status='configured'),
                        dict(entry, created_at='2026-11-03T13:00:00+01:00'), dict(entry, created_at='2026-11-03')):
            self.office.db.execute('SAVEPOINT synthetic_profile_tamper')
            try:
                self.office.db.execute('DROP TRIGGER business_accounting_profile_versions_update_guard')
                self.office.db.execute('UPDATE business_accounting_profile_versions SET entry_json=?,entry_sha256=?,created_at=?',
                    (canonical(changed), _sha(canonical(changed)), changed['created_at']))
                self.problem(409, self.api.history, self.owner)
            finally:
                self.office.db.execute('ROLLBACK TO SAVEPOINT synthetic_profile_tamper')
                self.office.db.execute('RELEASE SAVEPOINT synthetic_profile_tamper')
        self.assertEqual(self.api.confirm(self.owner, command), entry)

    def test_guards_foreign_keys_and_horizon_protect_both_tables_and_unique_keys(self):
        self.api.confirm(self.owner, self.command()); before = self.snapshot(protected_tables())
        horizon = restore_horizon(self.office)
        for table in protected_tables():
            for statement in ('UPDATE '+table+' SET '+('revision=revision' if table.endswith('versions') else 'entry_id=entry_id'),
                              'DELETE FROM '+table, 'INSERT OR REPLACE INTO '+table+' SELECT * FROM '+table):
                with self.assertRaises(sqlite3.IntegrityError):
                    with self.office.db:
                        self.office.db.execute(statement)
            original = dict(self.office.db.execute('SELECT * FROM '+table).fetchone())
            column = 'id' if table.endswith('versions') else 'request_id'
            changed = dict(original, **{column: uuid.uuid4().hex})
            with self.assertRaises(sqlite3.IntegrityError):
                with self.office.db:
                    self.office.db.execute('INSERT OR REPLACE INTO '+table+' ('+','.join(changed)+') VALUES('+','.join('?' for _ in changed)+')', tuple(changed.values()))
        with self.assertRaises(sqlite3.IntegrityError):
            with self.office.db:
                self.office.db.execute('INSERT INTO business_accounting_profile_requests VALUES(?,?,?,?,?)',
                    (self.owner['id'], uuid.uuid4().hex, '{}', 'a'*64, uuid.uuid4().hex))
        self.assertEqual(self.snapshot(protected_tables()), before); self.assertEqual(restore_horizon(self.office), horizon)
        self.assertTrue(validate_integrity(self.office))

    def test_missing_marker_or_partial_tables_never_looks_like_an_empty_profile(self):
        self.assertTrue(installed(self.office))
        with self.office.db:
            self.office.db.execute("DELETE FROM business_schema_migrations WHERE module='business_accounting_profile'")
        self.problem(409, installed, self.office)
        self.problem(409, self.api.state, self.owner)
        with self.office.db:
            self.office.db.execute('DROP TABLE business_accounting_profile_requests')
        self.problem(409, installed, self.office)
        with self.office.db:
            self.office.db.execute('DROP TABLE business_accounting_profile_versions')
        self.assertFalse(installed(self.office)); self.assertIsNone(restore_horizon(self.office))

    def test_strict_route_method_and_query_contract(self):
        base = '/accounting/profile'
        self.assertEqual(methods(base), 'GET'); self.assertEqual(methods(base+'/confirm'), 'POST')
        self.assertIsNone(methods(base+'/activate')); self.assertIsNone(methods(base+'/'))
        self.problem(405, dispatch, self.office, self.owner, base+'/confirm', 'GET', {})
        for path, method, data in ((base, 'GET', {'extra':1}), (base, 'GET', {'_query':{'limit':'1'}}),
                (base+'/history', 'GET', {'_query':{'limit':True}}), (base+'/history', 'GET', {'_query':{'offset':'-1'}}),
                (base+'/history', 'GET', {'_query':{'limit':'0'}}), (base+'/preview', 'POST', dict(self.body(), _query={}))):
            self.problem(400, dispatch, self.office, self.owner, path, method, data)
        command = self.command(); entry, status, content_type = dispatch(self.office, self.owner, base+'/confirm', 'POST', command)
        self.assertEqual((status, content_type), (201, 'application/json'))
        self.assertEqual(dispatch(self.office, self.owner, base+'/confirm', 'POST', command)[0], entry)


if __name__ == '__main__':
    unittest.main()
