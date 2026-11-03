"""Actual private P2/v4 runs expose only an authorized employee statement."""
import copy
import http.client
from http.server import ThreadingHTTPServer
import json
import threading
import unittest
from unittest.mock import patch

from core import Problem, canonical
from business_foundation import BusinessFoundation
from business_personnel_workflow import _sha
from business_payroll_statements import PayrollStatements, project, render_pdf, dispatch, ROOT
import test_business_payroll_periods as periods
import test_business_payroll as monthly


class PayrollStatementTests(unittest.TestCase):
    def setUp(self):
        self.case = periods.PayrollPeriodWorkflowTests('runTest')
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.f = self.case.f
        self.api = PayrollStatements(self.f.office)
        self.fact, _, _ = self.f.period()
        self.inputs = periods.inputs(self.f.employee['id'], self.fact)
        self.run = self.f.payroll.finalize(self.f.owner, periods.command(self.f.payroll, self.f.owner, self.inputs))

    def deny_own(self):
        BusinessFoundation(self.f.office).save_grant(self.f.owner, dict(request_id=monthly.rid(), user_id=self.f.technician['id'],
            permission='time.own', scope='*', effect='deny', revision=0))

    def assert_private_free(self, value):
        forbidden = {'source', 'sources', 'profile', 'profiles', 'preparation', 'period_case', 'employment_terms',
            'work_schedule', 'entitlement_decisions', 'verification_note', 'reason', 'correction_reason',
            'source_files', 'source_file_ids', 'identity_refs', 'tax_identifier', 'birth_date', 'created_by'}
        if isinstance(value, dict):
            self.assertFalse(set(value) & forbidden, set(value) & forbidden)
            for nested in value.values():
                self.assert_private_free(nested)
        elif isinstance(value, list):
            for nested in value:
                self.assert_private_free(nested)

    def get(self, actor=None, revision=None):
        return self.api.get(actor or self.f.technician, self.run['id'], {} if revision is None else dict(revision=str(revision)))

    def test_actual_own_statement_has_full_values_but_no_private_sources_or_original(self):
        f = self.f
        page = self.api.records(f.technician, dict(employee_id=f.employee['id']))
        self.assertEqual(page['items'], [self.get()['statement']])
        self.assertTrue(page['can_export'])
        statement = page['items'][0]
        self.assertEqual(statement['calculation']['net_minor'], self.run['calculation']['net_minor'])
        self.assertEqual(statement['period_summary']['social_periods'][0]['days'], 17)
        self.assert_private_free(page)
        self.assertFalse(self.f.data['file']['owner_visible'])
        for read in (lambda: f.payroll.get(f.technician, 'run', self.run['id']),
                     lambda: f.api.sources(f.technician, dict(employee_id=f.employee['id'])),
                     lambda: f.payroll.export(f.technician, self.run['id'], 'pdf')):
            f.problem(403, read)
        base = {key: value for key, value in statement.items() if key not in ('statement_hash', 'pdf_sha256', 'pdf_size')}
        self.assertEqual(_sha(base), statement['statement_hash'])
        pdf, mime = self.api.export(f.technician, self.run['id'], dict(revision='1', statement_hash=statement['statement_hash']))
        self.assertEqual(mime, 'application/pdf')
        self.assertEqual(_sha(pdf), statement['pdf_sha256'])
        self.assertEqual(len(pdf), statement['pdf_size'])
        self.assertEqual(pdf, render_pdf(statement))
        self.assertNotEqual(_sha(pdf), self.run['pdf_sha256'])
        for private in ('Belegter individueller Teilentgeltvertrag', f.data['file']['id'], self.fact['id']):
            self.assertNotIn(private.encode(), pdf)

    def test_fresh_own_person_mapping_foreign_person_and_role_revocation(self):
        f = self.f
        uid = f.office.add_user('other-statement@example.test', 'Synthetic-other-person-123', 'technician')
        other = dict(id=uid, role='owner')  # Forged stale role must never elevate.
        f.problem(403, lambda: self.get(other))
        f.problem(403, lambda: self.api.records(other, dict(employee_id=f.employee['id'])))
        self.deny_own()
        f.problem(403, self.get)
        f.problem(403, lambda: self.api.get(f.technician, self.run['id'], history=True))
        with f.office.db:
            f.office.db.execute('UPDATE users SET active=0 WHERE id=?', (f.technician['id'],))
        f.problem(401, self.get)

    def test_actual_role_revocation_during_pdf_render_prevents_return(self):
        statement = self.get()['statement']
        real = render_pdf
        def revoke(value):
            content = real(value)
            self.deny_own()
            return content
        with patch('business_payroll_statements.render_pdf', side_effect=revoke):
            self.f.problem(403, lambda: self.api.export(self.f.technician, self.run['id'],
                dict(revision='1', statement_hash=statement['statement_hash'])))

    def test_canonical_employee_account_mapping_rejects_reassignment_and_foreign_access(self):
        f = self.f
        previous = self.get()['statement']
        uid = f.office.add_user('new-employee-account@example.test', 'Synthetic-new-account-123', 'technician')
        f.problem(409, lambda: f.call(f.planning, 'save_employee', f.owner, dict(request_id=monthly.rid(), id=f.employee['id'],
            revision=f.employee['revision'], user_id=uid)))
        self.assertEqual(self.get()['statement'], previous)
        foreign = dict(id=uid, role='technician')
        f.problem(403, lambda: self.get(foreign))
        f.problem(403, lambda: self.api.export(foreign, self.run['id'],
            dict(revision='1', statement_hash=previous['statement_hash'])))

    def test_exact_historical_statement_pdf_survives_correction_current_name_and_pause(self):
        f = self.f
        before = self.get()['statement']
        pdf = self.api.export(f.technician, self.run['id'], dict(revision='1', statement_hash=before['statement_hash']))[0]
        details = dict(self.fact['details'], verification_note='Private updated entitlement source review')
        preview = f.api.preview(f.owner, f.preview_body(details))
        corrected_fact = f.api.save(f.owner, f.body('period_case', details, id=self.fact['id'], revision=1,
            correction_reason='Private historical source explanation', preview_hash=preview['preview_hash']))
        corrected_input = periods.inputs(f.employee['id'], corrected_fact)
        corrected = f.payroll.finalize(f.owner, periods.command(f.payroll, f.owner, corrected_input) |
            dict(id=self.run['id'], revision=1, correction_reason='Private original payroll correction explanation'))
        f.employee = f.call(f.planning, 'save_employee', f.owner, dict(request_id=monthly.rid(), id=f.employee['id'],
            revision=f.employee['revision'], name='New current employee name'))
        f.pause()
        self.assertEqual(self.get(revision=1)['statement'], before)
        self.assertEqual(self.api.export(f.technician, self.run['id'], dict(revision='1', statement_hash=before['statement_hash']))[0], pdf)
        page = self.api.records(f.technician, dict(employee_id=f.employee['id']))
        self.assertEqual(len(page['items']), 1)
        self.assertEqual(page['items'][0]['run_ref']['revision'], 2)
        self.assertEqual(page['items'][0]['run_ref']['content_hash'], corrected['content_hash'])
        history = self.api.get(f.technician, self.run['id'], history=True)
        self.assertEqual([item['run_ref']['revision'] for item in history['items']], [1, 2])
        self.assert_private_free(history)

    def test_strict_revision_hash_export_permission_and_positive_nested_allowlist(self):
        f = self.f
        statement = self.get()['statement']
        for query in ({}, dict(revision='1', statement_hash='f' * 64), dict(revision='0', statement_hash=statement['statement_hash']),
                      dict(revision='1', statement_hash=statement['statement_hash'], employee_id=f.employee['id'])):
            f.problem(409 if query.get('statement_hash') == 'f' * 64 else 400,
                      lambda query=query: self.api.export(f.technician, self.run['id'], query))
        for data in ({'_query': {'ignored': '1'}}, {'revision': '1'}):
            f.problem(400, lambda data=data: dispatch(f.office, f.technician, ROOT, 'GET', data))
        f.problem(405, lambda: dispatch(f.office, f.owner, ROOT, 'POST', {}))
        clone = copy.deepcopy(self.run)
        clone['calculation']['employee_contributions']['private_note'] = 'Should never cross boundary'
        clone['calculation']['period_details']['social_periods'][0]['private_note'] = 'Should never cross boundary'
        self.assert_private_free(project(clone))
        self.assertNotIn('Should never cross boundary', canonical(project(clone)))
        uid = f.office.add_user('statement-reader@example.test', 'Synthetic-staff-reader-123', 'accountant')
        staff = dict(id=uid, role='accountant')
        BusinessFoundation(f.office).save_grant(f.owner, dict(request_id=monthly.rid(), user_id=uid,
            permission='personnel.read', scope='*', effect='allow', revision=0))
        self.assertFalse(self.get(staff)['can_export'])
        f.problem(403, lambda: self.api.export(staff, self.run['id'], dict(revision='1', statement_hash=statement['statement_hash'])))

    def test_v1_partial_scope_keeps_unknown_net_and_private_sources_hidden(self):
        fixture = monthly.PayrollWorkflowTests('runTest')
        fixture.setUp()
        try:
            values = fixture.case('regular', 350000)
            run = fixture.payroll.finalize(fixture.owner, fixture.command(values))
            statement = PayrollStatements(fixture.office).get(fixture.technician, run['id'])['statement']
            self.assertIsNone(statement['calculation']['net_minor'])
            self.assertFalse(statement['calculation']['payroll_calculation_complete'])
            self.assertIsNone(statement['period_summary'])
            self.assert_private_free(statement)
        finally:
            fixture.doCleanups()


class PayrollStatementHTTP(unittest.TestCase):
    def setUp(self):
        self.fixture = PayrollStatementTests('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.f = self.fixture.f
        from onedrive import OneDrive
        from server import make_handler
        self.token = self.f.office.login('technician@example.test', 'Synthetic-technician-password-123')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.f.office, OneDrive(self.f.office)))
        worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(worker.join)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def http(self, path, status=200, *, raw=False, method='GET', body=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=15)
        try:
            connection.request(method, '/api/business' + path, body, {'Authorization':'Bearer ' + self.token})
            response = connection.getresponse()
            value = response.read()
            self.assertEqual(response.status, status, value[:300])
            return value if raw else json.loads(value)
        finally:
            connection.close()

    def test_actual_http_own_pdf_history_private_denial_and_revocation(self):
        object_path = ROOT + '/' + self.fixture.run['id']
        page = self.http(ROOT + '?employee_id=' + self.f.employee['id'])
        statement = page['items'][0]
        self.assertEqual(self.http(object_path)['statement'], statement)
        self.assertEqual(self.http(object_path + '/history')['items'], [statement])
        query = '?revision=1&statement_hash=' + statement['statement_hash']
        pdf = self.http(object_path + '/pdf' + query, raw=True)
        self.assertEqual(_sha(pdf), statement['pdf_sha256'])
        self.http('/payroll/runs/' + self.fixture.run['id'], 403)
        self.http('/payroll/facts/' + self.fixture.fact['id'], 403)
        self.http(ROOT + '?employee_id=' + self.f.employee['id'] + '&ignored=1', 400)
        self.http(object_path + '/pdf?revision=1', 400)
        self.http(ROOT, 405, method='POST', body=b'{}')
        self.fixture.deny_own()
        self.http(object_path, 403)
        self.http(object_path + '/pdf' + query, 403, raw=True)


if __name__ == '__main__':
    unittest.main()
