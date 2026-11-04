"""Independent V2 review: actual accepted sources and original external anchors."""
from copy import deepcopy
import json
import unittest
import uuid

from core import Problem, canonical
from accounting_year_package_v1 import sha
from accounting_year_package_v2 import build_selected
from accounting_year_verify_v1 import verify as verify_v1
from accounting_year_verify_v2 import verify
from business_foundation import BusinessFoundation
from business_accounting_year_openings import YearValues, TABLES
import test_accounting_year_package as originals
import test_accounting_year_package_v2 as fixture


class IndependentYearPackageV2(unittest.TestCase):
    def setUp(self):
        self.case = fixture.YearPackageCarryover('runTest')
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.f = self.case.f
        self.office, self.owner = self.f.office, self.f.owner

    def package(self, export=None):
        export = export or self.f.f.euer.post('export', {'year': 2026})
        raw, manifest = build_selected(self.office, self.owner, export['id'])
        return export, raw, manifest, originals.YearPackageTests.files(raw)

    def changed(self, raw, change):
        def callback(files):
            nodes = json.loads(files['proofs.json'])
            change(nodes, files)
            files['proofs.json'] = canonical(nodes).encode()
        return originals.YearPackageTests.changed(raw, callback, rehash=True)

    def reject_structure_and_original_anchor(self, raw, changed):
        self.assertNotEqual(raw, changed)
        with self.assertRaises(ValueError):
            verify(changed, sha(raw))
        # Separate check: even a hypothetically substituted outside anchor must
        # still pass the explicitly implemented internal structural guards.
        with self.assertRaises(ValueError):
            verify(changed, sha(changed))

    def test_actual_old_and_new_halves_keep_exact_annual_sum_and_opening_money(self):
        opening, _ = self.f.f.f.save(amount='1000.00')
        entry, _, export = self.case.complete()
        before = self.office.db.total_changes
        _, raw, manifest, files = self.package(export)
        self.assertEqual(self.office.db.total_changes, before)
        report = json.loads(files['report.json'])
        self.assertEqual(report['totals']['confirmed_expenses'], '119.00')
        self.assertEqual(report['totals']['confirmed_input_vat'], '19.00')
        self.assertEqual(report['totals']['euer_surplus'], '-119.00')
        self.assertEqual([m['amount'] for m in report['cash_movements']], ['59.50'])
        self.assertEqual(files['postings.csv'], export['artifact']['csv'].encode())
        self.assertEqual(report, export['artifact']['report'])
        cash = self.f.f.f.api.liquidity(self.owner, '2026-11-04')
        self.assertEqual(cash['accounts'][0]['calculated_balance'], '940.50')
        self.assertEqual(self.f.f.f.api._ledger()['current'][self.f.f.f.account['id']], opening)
        proofs = json.loads(files['proofs.json'])['nodes']
        year = next(n['payload']['entry'] for n in proofs if n['kind'] == 'year_values')
        self.assertEqual(year, entry)
        self.assertEqual([p['date'] for p in year['details']['historical_postings']],
                         ['2026-08-20', '2026-08-20', '2026-06-11'])
        result = verify(raw, sha(raw))
        self.assertTrue(result['verified'])
        self.assertFalse(result['intrinsic_dependency_closure'])
        self.assertEqual(manifest['required_trust'], 'separately_authenticated_archive_sha256')
        for anchor in (None, '', 'a' * 64):
            with self.subTest(anchor=anchor), self.assertRaises(ValueError):
                verify(raw, anchor)

    def test_actual_previous_year_vat_is_not_reclaimed_with_current_year_supplier_cash(self):
        # Create a distinct genuine original; immutable invoice dates of the
        # existing 2026 original cannot be renamed to make a 2025 fixture.
        self.f.f.save('item', self.f.old['entity_key'], dict(self.f.old['payload'], status='void'))
        record = self.f.f.item('independent-previous-vat', 'payable')
        record.update(invoice_date='2025-06-10', service_date='2025-06-10', invoice_received_date='2025-06-11', history_through='2026-10-31')
        record['prior_input_vat'].update(entitlement_date='2025-06-11', declared_period='2025-06', deducted_on='2025-07-10')
        record['prior_payments'] = [dict(date='2026-08-20', reference='Actual historical half', gross='59.50', net='50.00', tax='9.50', proof=record['cutover_proof'])]
        old, _ = self.f.f.save('item', 'independent-previous-vat', record)
        self.f.old = old
        self.f.payload['sources'][0].update(entry_id=old['id'], entry_hash=old['content_hash'])
        self.f.payload['controls'] = self.f.payload['controls'][:2]
        _, _, export = self.case.complete()
        _, raw, _, files = self.package(export)
        report = json.loads(files['report.json'])
        self.assertEqual(report['totals']['confirmed_expenses'], '119.00')
        self.assertEqual(report['totals']['confirmed_input_vat'], '0.00')
        self.assertEqual([m['amount'] for m in report['cash_movements']], ['59.50'])
        self.assertFalse(any(row['ledger'] == 'vat' for row in report['postings']))
        proofs = json.loads(files['proofs.json'])['nodes']
        year = next(n['payload']['entry'] for n in proofs if n['kind'] == 'year_values')
        self.assertEqual(year['resolved_sources'][0]['record']['prior_input_vat']['declared_period'], '2025-06')
        self.assertTrue(verify(raw, sha(raw))['verified'])

    def test_actual_closed_trade_adds_old_expense_but_no_second_money_movement(self):
        record = deepcopy(self.f.old['payload'])
        record.update(external_id='independent-settled', counterparty_key='independent-supplier', invoice_number='INDEPENDENT-CLOSED')
        record['invoice_proof'] = self.f.original('independent closed invoice')
        record['cutover_proof'] = self.f.original('independent closed bank payment')
        record['prior_input_vat']['proof'] = self.f.original('independent already deducted VAT')
        record['prior_payments'][0].update(gross='119.00', net='100.00', tax='19.00', proof=record['cutover_proof'])
        self.f.payload['sources'].append(dict(kind='closed_trade', record=record,
            accounts=self.f.rules.source['accounts'], cash_entry_keys=['INDEPENDENT-PAID-1'], vat_entry_key='INDEPENDENT-VAT-1'))
        for row, amount in zip(self.f.payload['controls'], ('-150.00', '-28.50', '-38.00')):
            row['amount'] = amount
        _, _, export = self.case.complete()
        _, raw, _, files = self.package(export)
        report = json.loads(files['report.json'])
        self.assertEqual(report['totals']['confirmed_expenses'], '238.00')
        self.assertEqual(report['totals']['confirmed_input_vat'], '38.00')
        self.assertEqual([m['amount'] for m in report['cash_movements']], ['59.50'])
        self.assertTrue(verify(raw, sha(raw))['verified'])
        def cross_settled(proofs, files):
            node = next(n for n in proofs['nodes'] if n['kind'] == 'year_values')
            source = next(s for s in node['payload']['entry']['resolved_sources'] if s['kind'] == 'closed_trade')
            source['cash_entry_keys'] = ['DIFFERENT-OLD-JOURNAL-ROW']
            node['payload_sha256'] = sha(node['payload'])
        self.reject_structure_and_original_anchor(raw, self.changed(raw, cross_settled))

    def test_actual_three_revisions_require_original_void_and_acceptance_history(self):
        entry, original_command = self.f.save()
        posted = self.f.classify(entry)
        old_export, old_raw, _, _ = self.package()
        self.f.f.euer.post('reverse', {'entry_id': posted['id']})
        self.f.save(dict(self.f.payload, status='void'))
        payload = deepcopy(self.f.payload)
        payload['ledger_proof'] = self.f.original('independent revision three reviewed full journal')
        current, _ = self.f.save(payload)
        self.f.classify(current)
        _, raw, _, files = self.package()
        self.assertEqual(build_selected(self.office, self.owner, old_export['id'])[0], old_raw)
        self.assertEqual(self.f.api.confirm(self.owner, original_command), entry)
        revisions = [n['payload']['entry']['revision'] for n in json.loads(files['proofs.json'])['nodes'] if n['kind'] == 'year_values']
        self.assertEqual(sorted(revisions), [1, 2, 3])
        def remove_void(proofs, files):
            gone = {n['id'] for n in proofs['nodes'] if n['kind'] == 'year_values' and n['payload']['entry']['revision'] == 2}
            self.assertEqual(len(gone), 1)
            proofs['nodes'] = [n for n in proofs['nodes'] if n['id'] not in gone]
            for node in proofs['nodes']:
                node['links'] = [ref for ref in node['links'] if ref not in gone]
        self.reject_structure_and_original_anchor(raw, self.changed(raw, remove_void))

    def test_actual_mixed_report_rechecks_one_project_source_without_global_right_loss(self):
        entry, _ = self.f.save()
        self.f.classify(entry)
        self.f.f.euer.incoming()  # Real unclassified invoice in the retained report.
        export, _, _, _ = self.package()
        uid = self.office.add_user('independent-v2-reader@example.test', 'Synthetic-only-reader-password-123', 'accountant')
        actor = dict(id=uid, role='owner')  # Current persisted rights, not this supplied role, must decide.
        foundation = BusinessFoundation(self.office)
        for permission in ('accounting.read', 'finance.read'):
            foundation.save_grant(self.owner, dict(request_id=uuid.uuid4().hex, user_id=uid,
                permission=permission, effect='allow', scope='*', revision=0))
        project = self.f.f.euer.fixture.project
        self.office.assign(self.owner, project, uid)
        before = build_selected(self.office, actor, export['id'])[0]
        foundation.save_grant(self.owner, dict(request_id=uuid.uuid4().hex, user_id=uid,
            permission='finance.read', effect='deny', scope=project, revision=0))
        YearValues(self.office)._access(actor)  # The global year-values right remains valid.
        for call in (lambda:build_selected(self.office, actor, export['id']),
                     lambda:self.f.f.euer.api.year_evidence(actor, export['id'])):
            with self.assertRaises(Problem) as caught:
                call()
            self.assertEqual(caught.exception.status, 403)
        self.assertTrue(verify(before, sha(before))['verified'])

    def test_live_missing_acceptance_rejects_new_download_but_old_archive_remains_verifiable(self):
        _, _, export = self.case.complete()
        _, raw, _, _ = self.package(export)
        original = self.f.payload['ledger_proof']['original_id']
        self.office.db.execute('DROP TRIGGER ' + TABLES[2] + '_delete_guard')
        deleted = self.office.db.execute("DELETE FROM " + TABLES[2] + " WHERE operation='original' AND result_json LIKE ?", ('%' + original + '%',))
        self.assertEqual(deleted.rowcount, 1)
        with self.assertRaises(Problem):
            build_selected(self.office, self.owner, export['id'])
        self.assertTrue(verify(raw, sha(raw))['verified'])

    def test_removed_period_journal_and_crossed_acceptance_fail_even_rehashed_envelopes(self):
        _, _, export = self.case.complete()
        _, raw, _, _ = self.package(export)
        def missing_journal(proofs, files):
            node = next(n for n in proofs['nodes'] if n['kind'] == 'year_values')
            name = 'originals/' + node['payload']['entry']['payload']['ledger_proof']['sha256'] + '.bin'
            del files[name]
            for row in proofs['nodes']:
                row['originals'] = [v for v in row['originals'] if v != name]
            manifest = json.loads(files['manifest.json'])
            manifest['originals'] = [v for v in manifest['originals'] if v['path'] != name]
            files['manifest.json'] = canonical(manifest).encode()
        def crossed_acceptance(proofs, files):
            node = next(n for n in proofs['nodes'] if n['kind'] == 'year_values')
            node['payload']['acceptance']['user_id'] = 'f' * 32
            node['payload_sha256'] = sha(node['payload'])
        for mutate in (missing_journal, crossed_acceptance):
            with self.subTest(mutate=mutate.__name__):
                self.reject_structure_and_original_anchor(raw, self.changed(raw, mutate))

    def test_partial_original_coverage_cannot_be_presented_as_completed_year(self):
        payload = deepcopy(self.f.payload)
        payload['coverage'] = {'from': '2026-08-01', 'through': '2026-10-31'}
        payload['controls'] = payload['controls'][:2]
        entry, _ = self.f.save(payload)
        self.f.classify(entry)
        _, raw, _, files = self.package()
        report = json.loads(files['report.json'])
        self.assertFalse(report['complete_for_recorded_sources'])
        self.assertIsNone(report['totals']['euer_surplus'])
        self.assertEqual(report['historical_year_values']['coverage'], payload['coverage'])
        self.assertFalse(verify(raw, sha(raw))['original_year_complete'])
        def falsify(files):
            value = json.loads(files['report.json'])
            value['historical_year_values']['coverage']['from'] = '2026-01-01'
            value['complete_for_recorded_sources'] = True
            files['report.json'] = canonical(value).encode()
            manifest = json.loads(files['manifest.json'])
            manifest.update(report_sha256=sha(files['report.json']), original_year_complete=True)
            files['manifest.json'] = canonical(manifest).encode()
        changed = originals.YearPackageTests.changed(raw, falsify, rehash=True)
        self.reject_structure_and_original_anchor(raw, changed)

    def test_earlier_v1_stays_exact_after_real_new_profile_and_year_original(self):
        old = originals.YearPackageTests('runTest')
        old.setUp()
        self.addCleanup(old.doCleanups)
        export, _, _ = old.year()
        raw, manifest = build_selected(old.office, old.owner, export['id'])
        self.assertEqual(manifest['format'], 'smartplan-year-evidence-v1')
        old.f.configure(vat_effective_from='2025-01-01', bookkeeping_start='2026-11-01')
        import base64
        YearValues(old.office).upload_original(old.owner, dict(request_id=uuid.uuid4().hex,
            entity_key='2026', filename='later.pdf', media_type='application/pdf',
            content_base64=base64.b64encode(b'%PDF-1.4\nSynthetic later independent complete journal\n%%EOF').decode()))
        self.assertEqual(build_selected(old.office, old.owner, export['id']), (raw, manifest))
        self.assertTrue(verify_v1(raw, sha(raw))['verified'])
        with self.assertRaises(ValueError):
            verify(raw, sha(raw))


if __name__ == '__main__':
    unittest.main()
