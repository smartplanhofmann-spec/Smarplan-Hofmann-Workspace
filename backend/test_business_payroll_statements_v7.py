"""Source5 employee-only schema4, actual original verification and frozen history."""
import copy
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer

from core import canonical
from business_foundation import BusinessFoundation
from business_personnel_workflow import _sha
from business_payroll_statements import PayrollStatements, project, render_pdf, ROOT, CONTRIBUTIONS
from test_business_payroll import rid
import test_business_payroll_multiple as actual
import test_business_payroll_statements as http_fixture


class Source5StatementTests(unittest.TestCase):
    def setUp(self):
        self.fixture = actual.MultipleWorkflow('runTest'); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.f = self.fixture.f
        self.state = self.fixture.paid_upgrade()
        self.run, self.old = self.state['run'], self.state['old']
        self.api = PayrollStatements(self.f.office)

    def deny_own(self):
        BusinessFoundation(self.f.office).save_grant(self.f.owner, dict(request_id=rid(),
            user_id=self.f.technician['id'], permission='time.own', scope='*', effect='deny', revision=0))

    def assert_private_free(self, value):
        forbidden = {'source', 'sources', 'source_refs', 'source_files', 'source_file_ids',
            'profile', 'profiles', 'preparation', 'identity', 'identity_ref', 'created_by',
            'reason', 'correction_reason', 'verification_note', 'accepted_command',
            'component_key', 'event_key', 'earning_ref', 'sv_month_group_key', 'tax_groups',
            'current_annual_basis_ref', 'previous_annual_basis_ref', 'annual_tax_forecast_ref',
            'annual_pay_before_minor', 'annual_tax_before_minor', 'annual_tax_after_minor',
            'assigned_period_ref', 'single_original_calculation', 'document_refs', 'settlement_allocations'}
        if isinstance(value, dict):
            self.assertFalse(set(value) & forbidden, set(value) & forbidden)
            for item in value.values(): self.assert_private_free(item)
        elif isinstance(value, list):
            for item in value: self.assert_private_free(item)

    def test_actual_schema4_pdf_json_amounts_and_original_v5_history(self):
        f = self.f; statement = self.api.get(f.technician, self.run['id'])['statement']
        self.assertEqual(4, statement['schema_version'])
        self.assertEqual('de_2026_multiple_oneoff_v7', statement['calculation']['rule_version'])
        self.assertEqual('regular_standard_multiple_oneoff', statement['calculation']['scope'])
        self.assertEqual(50000, statement['one_off_summary']['amount_minor'])
        self.assertEqual('2026-10-31', statement['one_off_summary']['receipt_date'])
        self.assertEqual('not_evidenced_by_calculation', statement['payment_status'])
        self.assertEqual(self.run['calculation']['payout_minor'], statement['calculation']['payout_minor'])
        self.assert_private_free(statement)
        query = dict(revision='2', statement_hash=statement['statement_hash'])
        pdf, pdf_type = self.api.export(f.technician, self.run['id'], query)
        encoded, json_type = self.api.export(f.technician, self.run['id'], query, file_format='json')
        self.assertEqual('application/pdf', pdf_type); self.assertEqual('application/json; charset=utf-8', json_type)
        self.assertEqual(statement, json.loads(encoded)); self.assertEqual(statement['pdf_sha256'], _sha(pdf))
        self.assertIn(b'Einmalzahlung / sonstiger Bezug', pdf)
        source = self.fixture.source
        private_values = [source['components'][0]['component_key'], source['components'][0]['planned_receipts'][0]['event_key'],
            source['components'][0]['earning']['id'], source['current_annual_basis']['id'],
            source['annual_tax_forecasts'][0]['annual_tax_forecast']['id'], f.original['id'],
            self.run['source']['multiple_one_off_case']['id'], self.run['source']['multiple_one_off_case']['details']['verification_note']]
        for secret in private_values:
            self.assertNotIn(secret, canonical(statement)); self.assertNotIn(secret.encode(), pdf); self.assertNotIn(secret.encode(), encoded)
        before = self.api.get(f.technician, self.old['id'], dict(revision='1'))['statement']
        self.assertEqual(2, before['schema_version'])
        self.assertEqual([before, statement], self.api.get(f.technician, self.run['id'], history=True)['items'])
        self.assertEqual(before['pdf_sha256'], _sha(self.api.export(f.technician, self.old['id'],
            dict(revision='1', statement_hash=before['statement_hash']))[0]))

    def test_positive_allowlist_discards_private_extras_at_every_new_source5_layer(self):
        changed = copy.deepcopy(self.run); expected = project(changed)
        extra = changed['calculation']['multiple_one_off_details']; single = extra['single_original_calculation']
        for layer in (changed['source'], extra, extra['components'][0], extra['receipt_events'][0], single,
                      single['one_off_details'], single['one_off_details']['assignment'],
                      single['one_off_details']['social'], single['one_off_details']['tax'],
                      single['one_off_details']['social']['employee_contributions']):
            layer['private_unrelated_annual_original'] = 'SYN-PRIVATE-MUST-NOT-LEAVE'
        self.assertEqual(expected, project(changed)); self.assert_private_free(project(changed))
        self.assertNotIn('SYN-PRIVATE', canonical(project(changed)))

    def test_unsupported_group_never_becomes_an_employee_net_statement(self):
        for mutate in (lambda c: c['multiple_one_off_details']['receipt_events'].append(copy.deepcopy(c['multiple_one_off_details']['receipt_events'][0])),
                       lambda c: c.update(payroll_calculation_complete=False),
                       lambda c: c['multiple_one_off_details']['components'][0].update(remaining_claim_minor=1),
                       lambda c: c.update(payout_minor=c['payout_minor']+1)):
            value = copy.deepcopy(self.run); mutate(value['calculation'])
            self.f.problem(409, lambda: project(value))

    def test_missing_atomic_consumption_denies_own_list_detail_history_pdf_and_json(self):
        f = self.f; statement = self.api.get(f.technician, self.run['id'])['statement']
        f.office.db.execute('DROP TRIGGER business_payroll_multiple_consumptions_delete_guard')
        f.office.db.execute('DELETE FROM business_payroll_multiple_consumptions')
        query = dict(revision='2', statement_hash=statement['statement_hash'])
        for read in (lambda: self.api.records(f.technician), lambda: self.api.get(f.technician, self.run['id']),
                     lambda: self.api.get(f.technician, self.run['id'], history=True),
                     lambda: self.api.export(f.technician, self.run['id'], query),
                     lambda: self.api.export(f.technician, self.run['id'], query, file_format='json')):
            f.problem(500, read)
        self.assertEqual(2, self.api.get(f.technician, self.run['id'], dict(revision='1'))['statement']['schema_version'])

    def test_actual_foreign_user_and_read_revocation_block_own_json_and_pdf(self):
        f = self.f; statement = self.api.get(f.technician, self.run['id'])['statement']
        uid = f.office.add_user('foreign-v7-own@example.test', 'Synthetic-foreign-person-123', 'technician')
        f.problem(403, lambda: self.api.get(dict(id=uid, role='technician'), self.run['id']))
        self.deny_own(); query = dict(revision='2', statement_hash=statement['statement_hash'])
        for read in (lambda: self.api.records(f.technician), lambda: self.api.get(f.technician, self.run['id']),
                     lambda: self.api.export(f.technician, self.run['id'], query),
                     lambda: self.api.export(f.technician, self.run['id'], query, file_format='json')):
            f.problem(403, read)

    def test_read_revocation_during_actual_pdf_generation_cannot_release_export(self):
        statement = self.api.get(self.f.technician, self.run['id'])['statement']
        original = render_pdf
        def revoke(value):
            result = original(value); self.deny_own(); return result
        with patch('business_payroll_statements.render_pdf', side_effect=revoke):
            self.f.problem(403, lambda: self.api.export(self.f.technician, self.run['id'],
                dict(revision='2', statement_hash=statement['statement_hash'])))

    def test_revocation_during_json_projection_cannot_release_export(self):
        statement=self.api.get(self.f.technician,self.run['id'])['statement']
        original=render_pdf
        def revoke(value):
            result=original(value);self.deny_own();return result
        with patch('business_payroll_statements.render_pdf',side_effect=revoke):
            self.f.problem(403,lambda:self.api.export(self.f.technician,self.run['id'],
                dict(revision='2',statement_hash=statement['statement_hash']),file_format='json'))


class Source5StatementHTTP(unittest.TestCase):
    http = http_fixture.PayrollStatementHTTP.http
    def setUp(self):
        self.fixture = Source5StatementTests('runTest'); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups); self.f = self.fixture.f
        from onedrive import OneDrive
        from server import make_handler
        self.token = self.f.office.login('technician@example.test', 'Synthetic-technician-password-123')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.f.office, OneDrive(self.f.office)))
        worker = threading.Thread(target=self.server.serve_forever, daemon=True); worker.start()
        self.addCleanup(worker.join); self.addCleanup(self.server.server_close); self.addCleanup(self.server.shutdown)

    def test_actual_http_own_json_pdf_history_deny_private_source5_originals(self):
        run = self.fixture.run; base = ROOT+'/'+run['id']; value = self.http(base)['statement']
        self.assertEqual(4, value['schema_version']); self.fixture.assert_private_free(value)
        query = '?revision=2&statement_hash='+value['statement_hash']
        self.assertEqual(value, json.loads(self.http(base+'/json'+query, raw=True)))
        self.assertEqual(value['pdf_sha256'], _sha(self.http(base+'/pdf'+query, raw=True)))
        self.assertEqual([2,4], [v['schema_version'] for v in self.http(base+'/history')['items']])
        for private in ('/payroll/runs/'+run['id'], '/payroll/multiple-one-off-cases/'+run['source']['multiple_one_off_case']['id'],
                        '/payroll/multiple-one-off-cases/sources?employee_id='+self.f.employee['id']+'&month=2026-10',
                        '/personnel/files/'+self.f.original['id']+'/content'):
            self.http(private,403)
        self.fixture.deny_own(); self.http(base+'/json'+query,403,raw=True); self.http(base+'/pdf'+query,403,raw=True)


class FrozenStatements(unittest.TestCase):
    def test_existing_schema1_schema2_schema3_pdf_bytes_remain_exact(self):
        root = Path(__file__).resolve().parents[1]/'app/test/fixtures'
        old = json.loads((root/'payroll_statements.json').read_text())
        values=[old['statement'],old['partial'],json.loads((root/'payroll_statements_v5.json').read_text()),json.loads((root/'payroll_statements_v6.json').read_text())['statement']]
        for value in values:
            if value['calculation']['employee_contributions'] is not None:
                value['calculation']['employee_contributions']={key:value['calculation']['employee_contributions'][key] for key in CONTRIBUTIONS}
            if value.get('one_off_summary'):
                value['one_off_summary']['employee_contributions']={key:value['one_off_summary']['employee_contributions'][key] for key in CONTRIBUTIONS}
            content=render_pdf(value);self.assertEqual(value['pdf_sha256'],_sha(content));self.assertEqual(value['pdf_size'],len(content))

if __name__=='__main__':unittest.main()
