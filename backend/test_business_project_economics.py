"""Source classification, corrections and project financial separation.

SQLite uses genuine receipt and cost flows. The commercial invoice fixture is
explicitly SyntheticDocuments; actual issuing-role checks belong to PostgreSQL.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import uuid

from core import Office, Problem
from business_accounting import Accounting
from business_finance import Finance
from business_foundation import BusinessFoundation
from business_inventory import BusinessInventory
from business_project_economics import ProjectEconomics, validate_integrity, dispatch
from business_documents import Documents


class ProjectEconomicsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'economics.db'
        self.office = Office(self.path); self.addCleanup(self.office.db.close)
        self.owner = self.actor('owner'); self.tech = self.actor('technician')
        self.project = self.office.add_project(self.owner, 'Synthetic fit-out', 'Synthetic client')
        self.other = self.office.add_project(self.owner, 'Private project', 'Private client')
        self.office.assign(self.owner, self.project, self.tech['id'])
        self.api = ProjectEconomics(self.office)
        self.finance = Finance(self.office)
        self.inventory = BusinessInventory(self.office)

    def actor(self, role):
        email = uuid.uuid4().hex + '@example.test'
        return dict(id=self.office.add_user(email, 'Synthetic-password-123', role), role=role, email=email)

    def request(self, **values):
        return dict(request_id=uuid.uuid4().hex, **values)

    def receipt(self, net='100.00', tax='19.00', gross='119.00', *, project=None, reviewed=True):
        receipt = self.finance.capture_receipt(self.owner, self.request(project_id=project or self.project,
            filename='synthetic-supplier.pdf', media_type='application/pdf',
            original_base64=base64.b64encode(('%PDF-1.4\nSynthetic '+uuid.uuid4().hex).encode()).decode()))
        return self.review(receipt, net=net, tax=tax, gross=gross) if reviewed else receipt

    def review(self, receipt, *, net='100.00', tax='19.00', gross='119.00', status='reviewed'):
        current = self.finance.receipt(self.owner, receipt['id'])
        return self.finance.review_receipt(self.owner, receipt['id'], self.request(revision=current['revision'],
            vendor='Synthetic supplier', invoice_number='SYN-'+receipt['id'], issue_date='2026-11-01',
            net=net, tax=tax, gross=gross, currency='EUR', status=status, note='Original checked.'))

    def inputs(self, receipt, *, expected=0, allocations=None):
        return dict(project_id=self.project, receipt_id=receipt['id'], source_revision=receipt['revision'],
            expected_revision=expected, allocations=allocations if allocations is not None else
            [dict(category='external_service', amount_net=receipt['net'])], reason='Verified project cost, exact source reviewed.')

    def confirm(self, receipt, **values):
        body = self.inputs(receipt, **values); preview = self.api.preview(self.owner, body)
        command = self.request(**body, preview_hash=preview['preview_hash'])
        return self.api.confirm(self.owner, command), command

    def problem(self, status, call, *args):
        with self.assertRaises(Problem) as caught: call(*args)
        self.assertEqual(caught.exception.status, status, caught.exception.message)
        return caught.exception

    def grant(self, permission, *, effect='allow', revision=0, scope=None):
        return BusinessFoundation(self.office).save_grant(self.owner, self.request(user_id=self.tech['id'],
            permission=permission, scope=scope or self.project, effect=effect, revision=revision))

    def test_verified_supplier_cost_is_not_cash_and_unclassified_sources_block_profit(self):
        receipt = self.receipt()
        before = self.api.summary(self.owner, self.project)
        self.assertIsNone(before['result']['document_net_contribution'])
        self.assertEqual('receipt_unclassified', before['issues'][0]['code'])
        entry, command = self.confirm(receipt)
        summary = self.api.summary(self.owner, self.project)
        self.assertEqual(('100.00', '100.00'), (summary['costs']['external_service_net'], summary['costs']['total_net']))
        self.assertEqual('-100.00', summary['result']['document_net_contribution'])
        self.assertEqual('0.00', summary['payments']['supplier_outflows_gross'])
        self.assertFalse(summary['tax_result_available'])
        self.assertEqual('recorded_sources_only', summary['result']['scope'])
        self.assertEqual(entry, self.api.confirm(self.owner, command))
        self.assertEqual(1, self.office.db.execute('SELECT COUNT(*) FROM business_project_cost_versions').fetchone()[0])
        self.assertEqual(0, self.office.db.execute('SELECT COUNT(*) FROM business_accounting_cash_events').fetchone()[0])
        validate_integrity(self.office)

    def test_review_changes_keep_history_and_require_explicit_correction_then_rejection_exclusion(self):
        receipt = self.receipt(); first, first_command = self.confirm(receipt)
        revised = self.review(receipt, net='120.00', tax='22.80', gross='142.80')
        stale = self.api.summary(self.owner, self.project)
        self.assertEqual('100.00', stale['costs']['external_service_net'])
        self.assertIsNone(stale['result']['document_net_contribution'])
        self.assertEqual('receipt_source_changed', stale['issues'][0]['code'])
        second, _ = self.confirm(revised, expected=1)
        self.assertEqual('120.00', self.api.summary(self.owner, self.project)['costs']['external_service_net'])
        self.assertEqual(first, self.api.confirm(self.owner, first_command))
        rejected = self.review(revised, net='120.00', tax='22.80', gross='142.80', status='rejected')
        self.problem(409, self.api.preview, self.owner, self.inputs(rejected, expected=2))
        third, _ = self.confirm(rejected, expected=2, allocations=[dict(category='excluded', amount_net='120.00')])
        self.assertEqual('0.00', self.api.summary(self.owner, self.project)['costs']['total_net'])
        self.assertEqual([first, second, third], self.api.history(self.owner, self.project, receipt['id'])['items'])
        validate_integrity(self.office)

    def test_exact_split_avoids_counting_stock_receipt_again_and_tracks_negative_change_order(self):
        article = Documents(self.office).save_article(self.owner, self.request(code='SYN', name='Synthetic cable', kind='material',
            unit='m', unit_price_net='20.0000', cost_price_net='10.0000', tax_rate='19', currency='EUR', active=True))
        location = self.inventory.save_location(self.owner, self.request(name='Test store'))
        self.inventory.move(self.owner, self.request(kind='receive', article_id=article['id'], to_location_id=location['id'], quantity='2', unit_cost_net='10.0000'))
        self.inventory.move(self.owner, self.request(kind='issue', project_id=self.project, article_id=article['id'], from_location_id=location['id'], quantity='2'))
        self.inventory.save_budget(self.owner, self.project, self.request(revision=0, material_net='30.00', labor_net='0.00', machine_net='20.00', other_net='100.00'))
        self.inventory.add_change_order(self.owner, self.project, self.request(title='Reduced scope', amount_net='-10.00', approved=True))
        receipt = self.receipt()
        self.confirm(receipt, allocations=[dict(category='stock_material', amount_net='20.00'), dict(category='external_service', amount_net='50.00'),
            dict(category='machine', amount_net='10.00'), dict(category='other', amount_net='15.00'), dict(category='excluded', amount_net='5.00')])
        summary = self.api.summary(self.owner, self.project)
        self.assertEqual('95.00', summary['costs']['total_net'])
        self.assertEqual('140.00', summary['budget']['total_net'])
        self.assertEqual('45.00', summary['budget']['remaining_net'])
        self.assertEqual(5, len(summary['sources']['receipt_allocations']))
        self.assertEqual(1, len(summary['sources']['material_movements']))

    def test_pending_original_and_cent_mismatches_cannot_be_silently_excluded(self):
        receipt = self.receipt(reviewed=False)
        self.problem(409, self.api.preview, self.owner, self.inputs(dict(receipt, revision=1, net='100.00')))
        receipt = self.review(receipt)
        for rows in ([dict(category='other', amount_net='99.99')], [dict(category='other', amount_net='100.001')],
                     [dict(category='other', amount_net='50.00'), dict(category='other', amount_net='50.00')]):
            with self.assertRaises(Problem): self.api.preview(self.owner, self.inputs(receipt, allocations=rows))
        self.assertEqual(0, self.office.db.execute('SELECT COUNT(*) FROM business_project_cost_versions').fetchone()[0])
        zero = self.receipt(net='0.00', tax='0.00', gross='0.00')
        entry, _ = self.confirm(zero, allocations=[])
        self.assertEqual([], entry['allocations'])

    def test_conflict_marker_is_only_for_absent_receipt_and_rights_are_fresh_on_replay(self):
        receipt = self.receipt(); inputs = self.inputs(receipt); preview = self.api.preview(self.owner, inputs)
        command = self.request(**inputs, preview_hash=preview['preview_hash'])
        first, _ = self.confirm(receipt)
        conflict = self.problem(409, self.api.confirm, self.owner, command)
        self.assertEqual('not_accepted', conflict.request_resolution)
        for permission in ('finance.read', 'finance.write', 'finance.approve'): self.grant(permission)
        tech_inputs = self.inputs(receipt, expected=1)
        preview = self.api.preview(self.tech, tech_inputs); tech_command = self.request(**tech_inputs, preview_hash=preview['preview_hash'])
        self.api.confirm(self.tech, tech_command)
        conflict = self.problem(409, self.api.confirm, self.tech, dict(tech_command, reason='Changed original command'))
        self.assertIsNone(conflict.request_resolution)
        self.grant('finance.approve', effect='deny', revision=1)
        self.problem(403, self.api.confirm, self.tech, tech_command)
        self.assertEqual(2, self.office.db.execute('SELECT COUNT(*) FROM business_project_cost_versions').fetchone()[0])

    def test_unassigned_and_foreign_project_sources_are_not_consumed(self):
        private = self.receipt(project=self.other)
        self.problem(404, self.api.preview, self.owner, self.inputs(private))
        self.grant('finance.read')
        self.assertEqual([], self.api.sources(self.tech, self.project)['items'])
        self.problem(404, self.api.summary, self.tech, self.other)
        summary = self.api.summary(self.tech, self.project)
        self.assertIsNone(summary['payments']['supplier_outflows_gross'])
        self.assertIsNone(summary['payments']['cash_balance_gross'])
        self.assertFalse(summary['payments']['complete'])

    def test_parallel_confirmation_creates_one_entry_and_survives_restart(self):
        receipt = self.receipt(); inputs = self.inputs(receipt); preview = self.api.preview(self.owner, inputs)
        command = self.request(**inputs, preview_hash=preview['preview_hash'])
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.api.confirm(self.owner, command), range(4)))
        self.assertTrue(all(value == results[0] for value in results))
        other = Office(self.path)
        try:
            self.assertEqual(results[0], ProjectEconomics(other).confirm(self.owner, command))
            validate_integrity(other)
        finally: other.db.close()

    def test_confirm_rollback_and_immutable_replace_guards(self):
        receipt = self.receipt(); inputs = self.inputs(receipt); preview = self.api.preview(self.owner, inputs)
        command = self.request(**inputs, preview_hash=preview['preview_hash'])
        with patch.object(self.office, 'audit', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError): self.api.confirm(self.owner, command)
        self.assertEqual(0, self.office.db.execute('SELECT COUNT(*) FROM business_project_cost_versions').fetchone()[0])
        entry = self.api.confirm(self.owner, command)
        for query in ('DELETE FROM business_project_cost_versions', "UPDATE business_project_cost_versions SET revision=99"):
            with self.assertRaises(sqlite3.IntegrityError), self.office.db: self.office.db.execute(query)
        row = dict(self.office.db.execute('SELECT * FROM business_project_cost_versions WHERE id=?', (entry['id'],)).fetchone())
        with self.assertRaises(sqlite3.IntegrityError), self.office.db:
            self.office.db.execute('INSERT OR REPLACE INTO business_project_cost_versions('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')', tuple(row.values()))
        validate_integrity(self.office)

    def test_duplicate_query_foreign_filter_and_wrong_method_are_rejected(self):
        for data in ({'_query': {'project_id': [self.project, self.other]}}, {'_query': {'project_id': self.project, 'user_id': self.tech['id']}},
                     {'_query': {'project_id': self.project}, 'body': {}}):
            self.problem(400, dispatch, self.office, self.owner, '/project-economics', 'GET', data)
        self.problem(405, dispatch, self.office, self.owner, '/project-economics', 'POST', {})

    def test_approved_time_without_historical_cost_rate_never_becomes_zero_cost_profit(self):
        from business_planning import Planning
        from business_time import TimeTracking
        moment = datetime(2026, 10, 26, 20, tzinfo=timezone.utc)
        employee = Planning(self.office, clock=lambda: moment).save_employee(self.owner, self.request(
            user_id=self.tech['id'], name='Unpriced employee', weekly_minutes=2400))
        timer = TimeTracking(self.office, clock=lambda: moment); entry_id = uuid.uuid4().hex
        for sequence, (action, at) in enumerate((('start', '08:00:00'), ('stop', '10:00:00')), 1):
            timer.event(self.tech, self.request(entry_id=entry_id, project_id=self.project, device_id='synthetic-cost',
                sequence=sequence, revision=sequence-1, action=action, occurred_at='2026-10-26T'+at+'+01:00'))
        summary = timer.summary(self.owner, dict(employee_id=employee['id'], **{'from': '2026-10-26', 'to': '2026-10-26'}))
        timer.approve_day(self.owner, '2026-10-26', self.request(employee_id=employee['id'], revision=summary['days'][0]['revision']))
        result = self.api.summary(self.owner, self.project)
        self.assertFalse(result['result']['complete_for_recorded_sources'])
        self.assertIsNone(result['result']['document_net_contribution'])
        self.assertEqual('missing_labor_rates', result['issues'][0]['code'])

    def test_module_pause_keeps_sources_readable_but_blocks_old_success_replay(self):
        from business_organization import Organization
        receipt = self.receipt(); entry, command = self.confirm(receipt)
        organization = Organization(self.office)
        state = organization.get(self.owner)
        body = dict(request_id=uuid.uuid4().hex, revision=state['revision'], needs=state['needs'],
            modules={key: dict(visible=item['visibility_override'], enabled=item['enabled']) for key, item in state['modules'].items()})
        body['modules']['finance']['enabled'] = False
        organization.save(self.owner, body)
        self.problem(423, self.api.confirm, self.owner, command)
        self.assertEqual(entry, self.api.history(self.owner, self.project, receipt['id'])['items'][0])

    def test_changed_archived_cost_is_rejected_in_summary_history_and_replay(self):
        receipt = self.receipt(); entry, command = self.confirm(receipt)
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_project_cost_versions_update_guard')
            value = json.loads(self.office.db.execute('SELECT entry_json FROM business_project_cost_versions WHERE id=?', (entry['id'],)).fetchone()[0])
            value['allocations'][0]['amount_net'] = '0.01'
            self.office.db.execute('UPDATE business_project_cost_versions SET entry_json=? WHERE id=?', (json.dumps(value), entry['id']))
        for function, arguments in ((self.api.summary, (self.owner, self.project)),
                (self.api.history, (self.owner, self.project, receipt['id'])), (self.api.confirm, (self.owner, command))):
            self.problem(409, function, *arguments)
        with self.assertRaises(ValueError): validate_integrity(self.office)

    def test_restored_financial_state_does_not_claim_verified_cash_balance(self):
        from restore import restore
        receipt = self.receipt(); self.confirm(receipt)
        destination = Path(self.temp.name) / 'restored.db'
        restore(self.path, destination)
        restored = Office(destination)
        self.addCleanup(restored.db.close)
        result = ProjectEconomics(restored).summary(self.owner, self.project)
        self.assertFalse(result['payments']['complete'])
        self.assertIsNone(result['payments']['cash_balance_gross'])
        self.assertIn('cash_restore_reconciliation_pending', [item['code'] for item in result['issues']])

    def test_duplicate_original_cannot_be_classified_twice_under_different_receipt_ids(self):
        receipt = self.receipt(); self.confirm(receipt)
        original, _ = self.finance.receipt_original(self.owner, receipt['id'])
        duplicate = self.finance.capture_receipt(self.owner, self.request(project_id=self.project,
            filename='duplicate.pdf', media_type='application/pdf', original_base64=base64.b64encode(original).decode()))
        duplicate = self.review(duplicate)
        error = self.problem(409, self.api.preview, self.owner, self.inputs(duplicate))
        self.assertIn('bereits eingeordnet', error.message)
        self.confirm(duplicate, allocations=[dict(category='excluded', amount_net='100.00')])
        summary = self.api.summary(self.owner, self.project)
        self.assertEqual('100.00', summary['costs']['total_net'])
        self.assertTrue(summary['result']['complete_for_recorded_sources'])
        validate_integrity(self.office)

    def test_large_valid_finance_receipts_keep_exact_decimal_sum(self):
        for _ in range(2):
            receipt = self.receipt(net='9999999999999.00', tax='0.00', gross='9999999999999.00')
            self.confirm(receipt)
        summary = self.api.summary(self.owner, self.project)
        self.assertEqual('19999999999998.00', summary['costs']['total_net'])
        self.assertEqual('-19999999999998.00', summary['result']['document_net_contribution'])
        validate_integrity(self.office)


if __name__ == '__main__':
    unittest.main()
