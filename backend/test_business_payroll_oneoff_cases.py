"""Actual private v6 cases, immutable receipts and unique claim identities."""
from copy import deepcopy
import json
import sqlite3
import unittest
from unittest.mock import patch

import business_schema
import business_payroll_oneoff_cases as cases
from business_payroll_facts import reference
from business_personnel_workflow import _sha
from core import canonical
from test_business_payroll import rid
import test_payroll_oneoff_composition_2026 as fixture


class OneoffCaseWorkflow(unittest.TestCase):
    def setUp(self):
        names = business_schema.MODULE_NAMES
        if 'business_payroll_oneoff_cases' not in names: names += ('business_payroll_oneoff_cases',)
        registry = patch.object(business_schema, 'MODULE_NAMES', names); registry.start(); self.addCleanup(registry.stop)
        self.c = fixture.OneoffCompositionTests('runTest'); self.c.setUp(); self.addCleanup(self.c.doCleanups)
        self.f = self.c.f; self.source = self.c.source()
        self.api = cases.PayrollOneoffCases(self.f.office, clock=lambda: self.f.now)

    def details(self):
        source = self.source
        return dict(month=source['month'], running_calculation_case_ref=reference(source['running_calculation_case']),
            one_off_earning_ref=reference(source['one_off_earning']), current_annual_basis_ref=reference(source['current_annual_basis']),
            previous_annual_basis_ref=None, annual_tax_forecast_ref=reference(source['annual_tax_forecast']),
            verification_note='Actual synthetic originals for unique current one-off claim inspected')

    def request(self, details=None, **changes):
        f = self.f
        proposal = dict(employee_id=f.employee['id'], employee_revision=f.employee['revision'],
            kind=cases.KIND, rule_version=cases.RULE_VERSION, source_contract_version=1,
            details=details or self.details(), source_file_ids=[f.original['id']])
        preview = self.api.preview(f.owner, proposal)
        command = proposal | dict(request_id=rid(), revision=0, status='active', confirmed=True,
            preview_hash=preview['preview_hash']) | changes
        return command, preview

    def test_actual_originals_plan_and_receipt_have_no_payroll_cash_or_euer_effect(self):
        f = self.f
        before = {name:f.office.db.execute('SELECT COUNT(*) FROM ' + name).fetchone()[0]
            for name in ('business_payroll_events','business_payroll_cash_batches','business_euer_entries')}
        body, preview = self.request(); saved = self.api.save(f.owner, body)
        self.assertTrue(preview['can_calculate']); self.assertEqual(saved['sources']['calculation_source'], self.source)
        self.assertEqual(saved['sources']['source_files'][0]['content_hash'], f.original['content_hash'])
        self.assertEqual(saved['sources']['employee']['revision'], f.employee['revision'])
        self.assertEqual(saved['plan'], fixture.calculate(self.source))
        self.assertNotIn('accepted_command', saved)
        self.assertEqual(self.api.save(f.owner, body), saved)
        self.assertEqual(self.api.resolve_one_off_case(f.owner, f.employee['id'], reference(saved)), saved)
        self.assertEqual(before, {name:f.office.db.execute('SELECT COUNT(*) FROM ' + name).fetchone()[0] for name in before})
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_same_claim_new_request_is_rejected_without_second_case_or_receipt(self):
        f = self.f; body, _ = self.request(); saved = self.api.save(f.owner, body)
        f.problem(409, lambda: self.api.save(f.owner, body | dict(request_id=rid())))
        self.assertEqual(self.api.get(f.owner, saved['id'], True)['items'], [saved])
        self.assertEqual(f.office.db.execute('SELECT COUNT(*) FROM ' + cases.TABLES[1]).fetchone()[0], 1)

    def test_correction_void_original_replay_and_pause_preserve_bound_claim(self):
        f = self.f; body, _ = self.request(); saved = self.api.save(f.owner, body)
        changed, _ = self.request(self.details() | dict(verification_note='Protected original reviewed again'),
            id=saved['id'], revision=1, correction_reason='Original review corrected')
        revised = self.api.save(f.owner, changed)
        archived = self.api.save(f.owner, changed | dict(request_id=rid(), revision=2, status='void',
            correction_reason='One-off claim withdrawn from this planned calculation'))
        self.assertEqual(self.api.get(f.owner, saved['id'], True)['items'], [saved,revised,archived])
        f.pause(); self.assertEqual(self.api.save(f.owner, body), saved)
        f.problem(423, lambda: self.api.save(f.owner, body | dict(request_id=rid())))
        self.assertTrue(cases.validate_integrity(f.office))

    def test_actual_forecast_correction_invalidates_fresh_use_but_original_receipt_survives(self):
        f = self.f; body, _ = self.request(); saved = self.api.save(f.owner, body)
        forecast = self.source['annual_tax_forecast']; details = deepcopy(forecast['details'])
        details['verification_note'] = 'Actual annual original reviewed and corrected'
        annual_command, _ = f.request('annual_tax_forecast', details)
        f.annual.save(f.owner, annual_command | dict(id=forecast['id'], revision=forecast['revision'],
            correction_reason='Actual original review corrected'))
        f.problem(409, lambda: self.api.resolve_one_off_case(f.owner, f.employee['id'], reference(saved)))
        self.assertEqual(self.api.save(f.owner, body), saved)
        self.assertTrue(cases.validate_integrity(f.office))

    def test_fresh_personnel_rights_are_required_for_private_source_and_original_replay(self):
        f = self.f; body, _ = self.request(); saved = self.api.save(f.owner, body)
        f.problem(403, lambda: self.api.sources(f.technician, dict(employee_id=f.employee['id'], month='2026-10')))
        with f.office.db: f.office.db.execute("UPDATE users SET role='accountant' WHERE id=?", (f.owner['id'],))
        for action in (lambda:self.api.get(f.owner, saved['id']), lambda:self.api.save(f.owner, body)):
            f.problem(403, action)

    def test_rehashed_nonce_without_original_receipt_is_not_valid_archive(self):
        f = self.f; body, _ = self.request(); saved = self.api.save(f.owner, body)
        row = dict(self.api._row(saved['id'], 1)); payload = json.loads(row['payload_json'])
        payload['accepted_command']['request_id'] = rid(); envelope = {key:value for key,value in row.items()
            if key not in ('payload_json','sources_json','content_hash')}
        envelope.update(payload=payload, sources=json.loads(row['sources_json']))
        envelope['command_hash'] = _sha(['one_off_case.saved', payload['accepted_command']])
        f.office.db.execute('DROP TRIGGER business_payroll_oneoff_case_events_update_guard')
        f.office.db.execute('UPDATE ' + cases.TABLES[0] + ' SET payload_json=?,command_hash=?,content_hash=? WHERE id=?',
            (canonical(payload), envelope['command_hash'], _sha(envelope), saved['id']))
        with self.assertRaises(ValueError): cases.validate_case_sources(f.office, self.api._get(saved['id']))

    def test_original_guards_source_catalog_and_strict_client_shape(self):
        f = self.f; body, _ = self.request(); saved = self.api.save(f.owner, body)
        catalog = self.api.sources(f.owner, dict(employee_id=f.employee['id'], month='2026-10'))
        self.assertEqual(catalog['one_off_cases'], [saved]); self.assertEqual(catalog['month'], '2026-10')
        self.assertIn(self.source['running_calculation_case'], catalog['calculation_cases'])
        # Allocation rows are created only by actual Finalize; the source-only
        # fixture leaves that table empty, so row-level DELETE guards cannot fire.
        for table in cases.TABLES[:2]:
            with self.assertRaises(sqlite3.IntegrityError): f.office.db.execute('DELETE FROM ' + table)
        f.problem(400, lambda: self.api.save(f.owner, body | dict(annual_pay_before_minor=0)))
        f.problem(400, lambda: self.api.sources(f.owner, dict(employee_id=f.employee['id'], month='2026-10', ignored=True)))
        f.problem(409, lambda: self.api.save(f.owner, body | dict(request_id=rid(), preview_hash='0' * 64)))


if __name__ == '__main__': unittest.main()
