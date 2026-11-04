"""Independent actual-domain checks for historical asset carryover integration."""
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import types
import unittest
import uuid

import business_schema
from core import Problem, canonical
from business_accounting_euer import guard_statements as euer_guards
from business_accounting_asset_openings import INPUT, public_source, validate_integrity
import test_business_accounting_asset_openings as workflow_fixture
from test_accounting_asset_opening_rules_independent_review import documented


class IndependentHistoricalAssetWorkflowReview(unittest.TestCase):
    def setUp(self):
        self.f = workflow_fixture.HistoricalAssetWorkflow('runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.office, self.owner, self.api, self.euer = self.f.office, self.f.owner, self.f.api, self.f.euer

    def reject(self, call, *args):
        with self.assertRaises(Problem) as caught: call(*args)
        self.assertEqual(caught.exception.status, 409, caught.exception.message)
        return caught.exception

    def test_actual_export_from_frozen_pre_asset_source_stays_byte_identical_after_new_afa(self):
        # Read the exact committed predecessor module. Do not synthesize an old
        # report by deleting fields from a new response or rewriting its hashes.
        repository = Path(__file__).resolve().parents[1]
        legacy_path = repository / 'docs/evidence/historical-assets-independent-2026-11-04/legacy-euer-source-before-historical.txt'
        old_source = legacy_path.read_text()
        self.assertNotIn('opening_depreciation', old_source)
        module = types.ModuleType('_independent_pre_asset_euer')
        exec(compile(old_source, str(legacy_path), 'exec'), module.__dict__)
        current = self.euer.api
        try:
            self.euer.api = module.EuerAccounting(self.office, clock=self.euer.fixture.clock)
            saved = self.euer.post('export', dict(year=2026))
            old_artifact = self.euer.api.exported(self.owner, saved['id'])
            self.assertNotIn('historical_assets', old_artifact['report'])
        finally:
            self.euer.api = current
        entry, _ = self.f.save()
        self.euer.post('opening_depreciation', self.f.depreciation_payload(entry))
        new_artifact = current.exported(self.owner, saved['id'])
        self.assertEqual(new_artifact, old_artifact)
        self.assertEqual(new_artifact['csv'].encode(), old_artifact['csv'].encode())
        self.assertNotIn('historical_assets', new_artifact['report'])
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_same_year_cutover_posts_only_remaining_original_quota_and_preserves_dependency_order(self):
        self.euer.configure(bookkeeping_start='2026-07-17')
        asset = documented(acquired='2026-03-31', cutover='2026-07-17', already=10000, inventory_number='m-001')
        before = self.euer.api.report(self.owner, 2026)
        entry, _ = self.f.save(asset=asset)
        after_carry = self.euer.api.report(self.owner, 2026)
        self.assertEqual(after_carry['totals']['confirmed_expenses'], before['totals']['confirmed_expenses'])
        self.assertEqual(after_carry['cash_movements'], before['cash_movements'])
        self.reject(self.euer.api.preview, self.owner, self.euer.body('opening_depreciation', self.f.depreciation_payload(entry, 2027)))
        first = self.euer.post('opening_depreciation', self.f.depreciation_payload(entry, 2026))
        second = self.euer.post('opening_depreciation', self.f.depreciation_payload(entry, 2027))
        self.assertEqual(first['effect']['details']['amount'], '900.00')
        self.assertEqual(second['effect']['details']['amount'], '1200.00')
        self.reject(self.euer.api.preview, self.owner, self.euer.body('reverse', dict(entry_id=first['id'])))
        self.euer.post('reverse', dict(entry_id=second['id']))
        self.euer.post('reverse', dict(entry_id=first['id']))
        self.assertEqual(self.euer.api.report(self.owner, 2026)['totals']['confirmed_expenses'], '0.00')
        self.assertEqual(self.euer.api.report(self.owner, 2027)['totals']['confirmed_expenses'], '0.00')
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_each_documented_old_rounding_posts_its_actual_residual_without_rewriting_old_amounts(self):
        for index, (rounding, remaining) in enumerate([
            ('cumulative_months_half_up', '33.33'), ('annual_half_up', '33.34'), ('monthly_half_up', '33.28'),
        ]):
            key = f'cent-{index}'
            value = documented(basis=10000, rounding=rounding, inventory_number=key)
            entry, _ = self.f.save(key=key, asset=value, position=f'Original cent-method row {index}')
            before = deepcopy(entry['asset'])
            post = self.euer.post('opening_depreciation', self.f.depreciation_payload(entry))
            self.assertEqual(post['effect']['details']['amount'], remaining)
            self.assertEqual(post['effect']['details']['closing_book_value'], '0.00')
            self.assertEqual(public_source(self.office, entry['id'])['asset'], before)
        report = self.euer.api.report(self.owner, 2026)
        self.assertEqual(report['totals']['confirmed_expenses'], '99.95')
        self.assertEqual(report['totals']['confirmed_input_vat'], '0.00')
        self.assertEqual(report['cash_movements'], [])
        self.assertTrue(validate_integrity(self.office))

    def test_zero_rounded_rate_keeps_original_asset_without_missing_or_fictitious_afa(self):
        entry, _ = self.f.save(asset=documented(basis=1, life=1200, acquired='2024-01-01',
                                               rounding='monthly_half_up', inventory_number='m-001'))
        report = self.euer.api.report(self.owner, 2026)
        self.assertEqual(report['historical_assets'][0]['continuation']['amount'], '0.00')
        self.assertFalse(any('depreciation_missing' in item['code'] for item in report['issues']))
        self.assertEqual(report['historical_assets'][0]['continuation']['opening_book_value'], '0.01')
        self.assertEqual(report['totals']['confirmed_expenses'], '0.00')
        self.reject(self.euer.api.preview, self.owner, self.euer.body('opening_depreciation', self.f.depreciation_payload(entry)))
        self.assertEqual(self.euer.api.state(self.owner)['revision'], 0)

    def test_duplicate_original_position_stays_blocked_until_explicit_void_without_changing_old_replay(self):
        first, command = self.f.save()
        other_original = self.f.original('other-inventory')[0]
        other = self.f.body(key='other-inventory', original=other_original, position=' ＡSSET REGISTER ROW1 ')
        self.reject(self.api.preview, self.owner, other)
        state = self.api.state(self.owner)
        void = {key: first[key] for key in INPUT}
        void.update(expected_revision=state['revision'], state_hash=state['state_hash'], status='void', reason='Independent explicit source withdrawal')
        self.api.confirm(self.owner, self.f.command(void))
        second, _ = self.f.save(key='other-inventory', original=other_original, position=' ＡSSET REGISTER ROW1 ')
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(self.api.confirm(self.owner, command), first)
        self.assertEqual([row['status'] for row in self.api.history(self.owner, first['asset_key'])['items']], ['active', 'void'])
        self.assertTrue(business_schema.validate_integrity(self.office))


    def test_rehashed_new_export_rejects_changed_or_missing_historical_projection(self):
        entry, _ = self.f.save()
        self.euer.post('opening_depreciation', self.f.depreciation_payload(entry))
        exported = self.euer.post('export', dict(year=2026))
        original_row = dict(self.office.db.execute('SELECT * FROM business_euer_entries WHERE id=?', (exported['id'],)).fetchone())
        original_receipt = dict(self.office.db.execute('SELECT * FROM business_euer_requests WHERE entry_id=?', (exported['id'],)).fetchone())
        digest = lambda value: hashlib.sha256(value.encode()).hexdigest()

        def write(entry_json, command_json):
            # Simulate a rehashed imported snapshot, then restore the exact
            # immutability guards. A missing trigger must not be the rejection.
            for table in ['business_euer_entries', 'business_euer_requests']:
                self.office.db.execute(f'DROP TRIGGER {table}_update_guard')
            self.office.db.execute('UPDATE business_euer_entries SET entry_json=?,entry_sha256=? WHERE id=?',
                                   (entry_json, digest(entry_json), exported['id']))
            self.office.db.execute('UPDATE business_euer_requests SET request_json=?,request_hash=? WHERE entry_id=?',
                                   (command_json, digest(command_json), exported['id']))
            for statement in euer_guards('sqlite'): self.office.db.execute(statement)

        for alteration in ['changed_asset', 'changed_continuation', 'empty_projection', 'removed_projection']:
            with self.subTest(alteration=alteration):
                changed = json.loads(original_row['entry_json'])
                report = changed['artifact']['report']
                if alteration == 'changed_asset': report['historical_assets'][0]['asset']['opening_book_value'] = '999.99'
                elif alteration == 'changed_continuation': report['historical_assets'][0]['continuation']['amount'] = '0.00'
                elif alteration == 'empty_projection': report['historical_assets'] = []
                else: report.pop('historical_assets')
                changed['artifact']['report_sha256'] = digest(canonical(report))
                # CSV contains journal postings; those exact amounts remain
                # unchanged in this attack. Rehash the entire accepted envelope.
                changed['artifact']['csv_sha256'] = digest(changed['artifact']['csv'])
                preview = {key: value for key, value in changed.items() if key not in
                           ('id', 'sequence', 'previous_hash', 'created_by', 'created_at', 'preview_hash')}
                preview.update(expected_revision=changed['sequence']-1, state_hash=changed['previous_hash'])
                changed['preview_hash'] = digest(canonical(preview))
                command = json.loads(original_receipt['request_json'])
                command['preview_hash'] = changed['preview_hash']
                try:
                    write(canonical(changed), canonical(command))
                    with self.assertRaises(Problem) as caught: self.euer.api._ledger()
                    self.assertEqual(caught.exception.status, 409)
                finally:
                    write(original_row['entry_json'], original_receipt['request_json'])
        self.assertEqual(self.euer.api.exported(self.owner, exported['id'])['report'], exported['artifact']['report'])
        self.assertTrue(business_schema.validate_integrity(self.office))

    def receipt_source(self):
        receipt = self.euer.incoming(net='100.00', tax='19.00', gross='119.00')
        self.euer.post('input_vat', self.euer.vat_payload(receipt, amount='19.00'))
        raw, media = self.euer.fixture.finance.receipt_original(self.owner, receipt['id'])
        original = self.api.upload_original(self.owner, dict(request_id=uuid.uuid4().hex, asset_key='m-001',
                    filename='exact-incoming-original.pdf', media_type=media, content_base64=base64.b64encode(raw).decode()))
        source = self.euer.api._receipt_source(self.owner, receipt['id'])
        payload = dict(receipt_id=receipt['id'], source_hash=source['source_hash'], description='Independent ordinary acquisition',
                       business_basis='100.00', use_start='2026-11-01', life_months=36, account='0440')
        return original, payload

    def test_existing_new_acquisition_blocks_same_original_as_historical_asset(self):
        original, payload = self.receipt_source()
        self.euer.post('asset', payload)
        body = self.f.body(original=original, asset=documented(basis=10000, inventory_number='m-001'))
        self.reject(self.api.preview, self.owner, body)
        self.assertEqual(self.api.state(self.owner)['items'], [])

    def test_historical_asset_blocks_same_original_as_new_acquisition(self):
        original, payload = self.receipt_source()
        self.f.save(original=original, asset=documented(basis=10000, inventory_number='m-001'))
        self.reject(self.euer.api.preview, self.owner, self.euer.body('asset', payload))
        self.assertFalse(any(entry['effect'] and entry['effect']['operation'] == 'asset'
                             for entry in self.euer.api._ledger()['entries']))
        self.assertTrue(business_schema.validate_integrity(self.office))


if __name__ == '__main__': unittest.main()
