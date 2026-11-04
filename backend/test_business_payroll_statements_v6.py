"""Actual Source4 employee projection: year split without private annual evidence."""
import copy
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from core import canonical
from business_foundation import BusinessFoundation
from business_personnel_workflow import _sha
from business_payroll_facts import reference
from business_payroll_statements import PayrollStatements, project, render_pdf, ROOT, CONTRIBUTIONS
from test_business_payroll import rid
import test_business_payroll_oneoff_runs as oneoff_fixture
import test_business_payroll_statements as statement_fixture
import test_business_payroll_periods as periods


class OneoffStatementTests(unittest.TestCase):
    def setUp(self):
        self.fixture = oneoff_fixture.OneoffRunWorkflow('runTest'); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.f = self.fixture.f
        self.case, _ = self.fixture.workflow(flat_travel=True, shifted=True)
        self.api = PayrollStatements(self.f.office)
        running = self.case['sources']['calculation_source']['running_calculation_case']
        inputs = dict(source_schema_version=3, employee_id=self.f.employee['id'], calculation_case_ref=reference(running))
        self.old = self.f.payroll.finalize(self.f.owner, periods.command(self.f.payroll, self.f.owner, inputs))
        self.before = self.api.get(self.f.technician, self.old['id'])['statement']
        self.before_pdf = render_pdf(self.before)
        self.command = self.fixture.command(self.case, id=self.old['id'], revision=1,
            correction_reason='Actual separately evidenced one-off earning added')
        self.run = self.f.payroll.finalize(self.f.owner, self.command)

    def deny_own(self):
        BusinessFoundation(self.f.office).save_grant(self.f.owner, dict(request_id=rid(),
            user_id=self.f.technician['id'], permission='time.own', scope='*', effect='deny', revision=0))

    def assert_private_free(self, value):
        forbidden = {'sources', 'source', 'profile', 'profiles', 'preparation', 'policy', 'source_refs',
            'source_files', 'source_file_ids', 'identity_ref', 'reason', 'verification_note', 'accepted_command',
            'created_by', 'annual_pay_before_minor', 'annual_tax_before_minor', 'annual_tax_after_minor',
            'annual_basis_ref', 'annual_tax_forecast_ref', 'earning_ref', 'current_annual_basis_ref',
            'previous_annual_basis_ref', 'assigned_period_ref', 'branch_bases', 'care_adjustments'}
        if isinstance(value, dict):
            self.assertFalse(set(value) & forbidden)
            for item in value.values(): self.assert_private_free(item)
        elif isinstance(value, list):
            for item in value: self.assert_private_free(item)

    def test_actual_own_bonus_travel_deductions_and_frozen_v5_history(self):
        f = self.f; value = self.api.get(f.technician, self.run['id'])['statement']
        self.assertEqual(3, value['schema_version'])
        self.assertEqual(50000, value['one_off_summary']['amount_minor'])
        self.assertEqual(10875, value['one_off_summary']['employee_social_total_minor'])
        self.assertEqual((2026, 2026, False), tuple(value['one_off_summary'][k] for k in ('tax_year', 'social_year', 'march_clause')))
        self.assertEqual(109, value['calculation']['net_deductions_minor'])
        self.assertEqual(self.before['calculation']['payout_minor'] + 39125, value['calculation']['payout_minor'])
        self.assertEqual(1400, value['travel_summary']['tax_free_external_minor'])
        self.assert_private_free(value)
        pdf = self.api.export(f.technician, self.run['id'], dict(revision='2', statement_hash=value['statement_hash']))[0]
        self.assertIn(b'Einmalzahlung / sonstiger Bezug', pdf)
        self.assertEqual(_sha(pdf), value['pdf_sha256'])
        private = self.fixture.source
        for item in (self.case['id'], private['one_off_earning']['id'], private['current_annual_basis']['id'],
                     private['annual_tax_forecast']['id'], f.original['id'], self.case['details']['verification_note']):
            self.assertNotIn(item, canonical(value)); self.assertNotIn(item.encode(), pdf)
        self.assertEqual([value], self.api.records(f.technician)['items'])
        self.assertEqual([self.before, value], self.api.get(f.technician, self.run['id'], history=True)['items'])
        self.assertEqual(self.before, self.api.get(f.technician, self.run['id'], dict(revision='1'))['statement'])
        self.assertEqual(self.before_pdf, self.api.export(f.technician, self.run['id'],
            dict(revision='1', statement_hash=self.before['statement_hash']))[0])
        self.assertEqual(self.run, f.payroll.finalize(f.owner, self.command))

    def test_actual_missing_claim_consumption_fails_all_current_own_routes(self):
        f = self.f; value = self.api.get(f.technician, self.run['id'])['statement']
        f.office.db.execute('DROP TRIGGER business_payroll_oneoff_consumptions_delete_guard')
        f.office.db.execute('DELETE FROM business_payroll_oneoff_consumptions')
        for read in (lambda: self.api.records(f.technician),
                     lambda: self.api.get(f.technician, self.run['id']),
                     lambda: self.api.get(f.technician, self.run['id'], history=True),
                     lambda: self.api.export(f.technician, self.run['id'], dict(revision='2', statement_hash=value['statement_hash']))):
            f.problem(500, read)
        self.assertEqual(self.before, self.api.get(f.technician, self.run['id'], dict(revision='1'))['statement'])

    def test_positive_allowlist_discards_private_additions_at_all_oneoff_layers(self):
        changed = copy.deepcopy(self.run); before = project(changed)
        extra = changed['calculation']['one_off_details']
        for layer in (extra, extra['assignment'], extra['social'], extra['tax'], extra['social']['employee_contributions']):
            layer['private_annual_original'] = 'must never leave'
        changed['source']['one_off_case']['diagnosis'] = 'private'
        self.assertEqual(before, project(changed))

    def test_actual_march_clause_retains_2026_tax_and_2025_social_only(self):
        case = oneoff_fixture.OneoffRunWorkflow('runTest'); case.setUp(); self.addCleanup(case.doCleanups)
        case.source = case.c.source(january=True, previous=True, bonus=200000)
        details = case.details() | dict(previous_annual_basis_ref=reference(case.source['previous_annual_basis']))
        command, _ = case.request(details); saved = case.api.save(case.f.owner, command)
        run = case.f.payroll.finalize(case.f.owner, case.command(saved))
        value = PayrollStatements(case.f.office).get(case.f.technician, run['id'])['statement']
        self.assertEqual((2026, 2025, True), tuple(value['one_off_summary'][k] for k in ('tax_year', 'social_year', 'march_clause')))
        self.assertEqual(1100, value['one_off_summary']['employee_contributions']['health_additional'])
        self.assert_private_free(value)


class OneoffStatementHTTP(unittest.TestCase):
    http = statement_fixture.PayrollStatementHTTP.http

    def setUp(self):
        self.fixture = OneoffStatementTests('runTest'); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups); self.f = self.fixture.f
        from onedrive import OneDrive
        from server import make_handler
        self.token = self.f.office.login('technician@example.test', 'Synthetic-technician-password-123')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.f.office, OneDrive(self.f.office)))
        worker = threading.Thread(target=self.server.serve_forever, daemon=True); worker.start()
        self.addCleanup(worker.join); self.addCleanup(self.server.server_close); self.addCleanup(self.server.shutdown)

    def test_actual_http_own_history_pdf_denies_private_annual_case_and_original(self):
        f = self.f; path = ROOT + '/' + self.fixture.run['id']
        value = self.http(ROOT)['items'][0]; self.fixture.assert_private_free(value)
        self.assertEqual(value, self.http(path)['statement'])
        self.assertEqual([self.fixture.before, value], self.http(path + '/history')['items'])
        query = '?revision=2&statement_hash=' + value['statement_hash']
        self.assertEqual(value['pdf_sha256'], _sha(self.http(path + '/pdf' + query, raw=True)))
        for private in ('/payroll/runs/' + self.fixture.run['id'],
                        '/payroll/runs/' + self.fixture.run['id'] + '/pdf?revision=2',
                        '/payroll/one-off-cases/' + self.fixture.case['id'],
                        '/personnel/files/' + f.original['id'] + '/content',
                        '/payroll/annual-facts/' + self.fixture.fixture.source['current_annual_basis']['id'],
                        '/payroll/one-off-cases/sources?employee_id=' + f.employee['id'] + '&month=2026-10'):
            self.http(private, 403)
        other_id = f.office.add_user('foreign-oneoff-statement@example.test', 'Synthetic-foreign-person-123', 'technician')
        f.problem(403, lambda: self.fixture.api.get(dict(id=other_id, role='technician'), self.fixture.run['id']))
        self.fixture.deny_own(); self.http(path, 403); self.http(path + '/pdf' + query, 403, raw=True)


class HistoricalStatementBytes(unittest.TestCase):
    def test_existing_schema1_and_schema2_fixture_pdf_bytes_are_unchanged(self):
        root = Path(__file__).resolve().parents[1] / 'app/test/fixtures'
        old = json.loads((root / 'payroll_statements.json').read_text())
        values = [old['statement'], old['partial'], json.loads((root / 'payroll_statements_v5.json').read_text())]
        for statement in values:
            # The early JSON fixture sorts object keys. Restore project()'s
            # fixed contribution order, which generated its frozen PDF bytes.
            parts = statement['calculation']['employee_contributions']
            if parts is not None:
                statement['calculation']['employee_contributions'] = {key: parts[key] for key in CONTRIBUTIONS}
            content = render_pdf(statement)
            self.assertEqual(statement['pdf_sha256'], _sha(content))
            self.assertEqual(statement['pdf_size'], len(content))


if __name__ == '__main__': unittest.main()
