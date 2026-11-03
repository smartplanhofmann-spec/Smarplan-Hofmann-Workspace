"""Actual local HTTP payload boundaries and private payroll fact replay."""
import http.client
from http.server import ThreadingHTTPServer
import json
import threading
import unittest
from unittest.mock import patch

import business_api
from business_payroll_facts import reference
from onedrive import OneDrive
from server import make_handler
import test_business_payroll_facts as domain


class PayrollFactsLocalHTTP(domain.monthly.BusinessFixture, unittest.TestCase):
    case = domain.PayrollFactTests.case
    identity_details = domain.PayrollFactTests.identity_details
    save_account = domain.PayrollFactTests.save_account
    account_api = domain.PayrollFactTests.account_api
    terms_details = domain.PayrollFactTests.terms_details
    body = domain.PayrollFactTests.body
    period_details = domain.PayrollFactTests.period_details
    preview_body = domain.PayrollFactTests.preview_body
    pause = domain.PayrollFactTests.pause

    def setUp(self):
        domain.PayrollFactTests.setUp(self)
        modules = business_api.MODULES
        if 'business_payroll_facts' not in modules:
            modules += ('business_payroll_facts',)
        patched = patch.object(business_api, 'MODULES', modules); patched.start(); self.addCleanup(patched.stop)
        self.token = self.office.login('owner@example.test', 'Synthetic-owner-password-123')
        self.tech_token = self.office.login('technician@example.test', 'Synthetic-technician-password-123')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.office, OneDrive(self.office)))
        worker = threading.Thread(target=self.server.serve_forever, daemon=True); worker.start()
        self.addCleanup(worker.join); self.addCleanup(self.server.server_close); self.addCleanup(self.server.shutdown)

    def http(self, method, path, data=None, *, status=200, token=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        try:
            connection.request(method, '/api/business' + path, json.dumps(data).encode() if data is not None else None,
                {'Authorization': 'Bearer ' + (token or self.token), 'Content-Type': 'application/json'} | (headers or {}))
            response = connection.getresponse(); raw = response.read()
            self.assertEqual(response.status, status, raw[:350])
            return json.loads(raw)
        finally:
            connection.close()

    def test_actual_http_period_preview_confirm_history_and_paused_original_ack(self):
        source = self.http('GET', '/payroll/facts/sources?employee_id=' + self.employee['id'])
        self.assertEqual(source['employee']['revision'], self.employee['revision'])
        terms_body = self.body('employment_terms', self.terms_details())
        terms = self.http('POST', '/payroll/facts', terms_body)
        details = self.period_details(terms)
        preview = self.http('POST', '/payroll/periods/preview', self.preview_body(details))
        self.assertTrue(preview['can_calculate'])
        command = self.body('period_case', details, preview_hash=preview['preview_hash'])
        saved = self.http('POST', '/payroll/facts', command)
        self.assertEqual(self.http('POST', '/payroll/facts', command), saved)
        self.assertEqual(self.http('GET', '/payroll/facts/' + saved['id'] + '/history')['items'], [saved])
        self.assertEqual(reference(self.http('GET', '/payroll/facts/' + saved['id'])), reference(saved))
        self.pause()
        self.assertEqual(self.http('POST', '/payroll/facts', command), saved)
        self.http('POST', '/payroll/facts', command | dict(request_id=domain.monthly.rid()), status=423)

    def test_strict_http_unknown_fields_queries_methods_size_and_private_self_access(self):
        path = '/payroll/facts/sources?employee_id=' + self.employee['id']
        self.http('GET', path, token=self.tech_token, status=403)
        self.http('GET', path, {}, status=400)
        self.http('GET', path + '&ignored=1', status=400)
        self.http('POST', '/payroll/facts?ignored=1', {}, status=400)
        self.http('POST', '/payroll/facts', {}, headers={'Content-Length': '1000001'}, status=413)
        self.http('POST', '/payroll/facts', self.body('employment_terms', self.terms_details()) | dict(social_days=17), status=400)
        self.http('POST', '/payroll/facts', self.body('employment_terms', self.terms_details()), token=self.tech_token, status=403)
        self.assertEqual(self.http('GET', '/payroll/facts?employee_id=' + self.employee['id'])['items'], [])


if __name__ == '__main__':
    unittest.main()
