"""Signed device captures through real MFA, HTTP, SQLite, restore and TLS.

All customers and documents are synthetic. The render barrier calls the real
renderer and only schedules a concurrent permission change; no domain, auth or
transport behavior is mocked. No provider or external network is contacted.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import uuid

import business_api
import business_operations
import business_schema
from core import Office, canonical, digest
import plan_access
from restore import restore
from online.web import create_app
from online import test_accounting_journey as journey
from online import test_accounting_allocations_journey as tls_fixture
from online import test_business_planning_time_api as fixture
from online.test_workspace_api import WorkspaceHttpFlow


PATH = '/business/service-reports/offline'


def rid():
    return uuid.uuid4().hex


def capture_body(office, actor, project_id):
    project = office.project(actor, project_id)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    body = dict(request_id=rid(), entry_id=rid(), project_id=project_id,
        content=dict(title=' Synthetisches Geräteprotokoll ',
            description='Gemessene Leistung: Größe 3 m²\nUnveränderter Inhalt.', notes=' Gerät vor Ort geprüft. ',
            project_name=project['name'], customer=project['customer'],
            captured_at=(now - timedelta(minutes=10)).isoformat()),
        signer=' Synthetischer Kunde ', strokes=[[[0.1, 0.2], [0.8, 0.7]]],
        signed_at=(now - timedelta(minutes=5)).isoformat())
    body['content_hash'] = hashlib.sha256(canonical([body['entry_id'], project_id, body['content']]).encode()).hexdigest()
    return body


class OfflineReportsHttpTests(WorkspaceHttpFlow, unittest.TestCase):
    setUp = fixture.BusinessPlanningTimeApiTests.setUp

    def grant(self, *, token='owner', scopes=None):
        if scopes is None:
            return self.call('POST', '/business/offline/access', {}, token=token, status=201).json
        actor = self.office.user(self.token if token == 'owner' else token)
        with self.office.lock, self.office.db:
            return plan_access.issue(self.office, actor, workspace=True, business=True,
                                     business_capabilities=scopes)

    def capture(self, *, token='owner', body=None):
        body = body or capture_body(self.office, self.owner, self.project)
        return self.call('POST', PATH, body, token=token, status=201).json, body

    def permission(self, permission, effect, *, scope='*', revision=0):
        return self.call('POST', '/business/settings/permissions', dict(request_id=rid(),
            user_id=self.technician_id, permission=permission, effect=effect, scope=scope, revision=revision)).json

    def module(self, enabled):
        current = self.call('GET', '/business/organization').json
        modules = {key: dict(visible=value['visibility_override'], enabled=value['enabled'])
                   for key, value in current['modules'].items()}
        modules['documents']['enabled'] = enabled
        return self.call('POST', '/business/organization', dict(request_id=rid(),
            revision=current['revision'], needs=current['needs'], modules=modules)).json

    def test_frozen_capture_receipt_and_pdf_are_one_integrated_archive(self):
        grant = self.grant()
        self.assertIn('offline_reports', grant['capabilities'])
        self.assertEqual(grant['report_project_ids'], [self.project])
        self.assertTrue(grant['report_writes_enabled'])
        row, body = self.capture(token=grant['token'])
        path = '/business/service-reports/' + row['id']
        self.assertEqual((row['status'], row['revision']), ('signed', 2))
        self.assertEqual(row['offline_capture']['content'], body['content'])
        self.assertEqual(row['signer'], body['signer'])
        self.assertEqual(row['strokes'], body['strokes'])
        original = self.call('GET', path + '/pdf', token=grant['token']).data
        self.assertTrue(original.startswith(b'%PDF'))
        self.assertEqual(hashlib.sha256(original).hexdigest(), row['pdf_sha256'])
        before = self.office.db.total_changes
        self.assertEqual(self.capture(token=grant['token'], body=body)[0], row)
        self.assertEqual(self.office.db.total_changes, before)
        self.assertEqual(self.call('GET', path, token=grant['token']).json, row)
        self.assertEqual(self.call('GET', path + '/pdf').data, original)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM reports').fetchone()[0], 0)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_operation_versions WHERE object_id=?', (row['id'],)).fetchone()[0], 2)
        self.call('POST', PATH, dict(body, signer='Changed signature'), token=grant['token'], status=409)
        self.call('POST', PATH, dict(body, request_id=rid()), token=grant['token'], status=409)
        self.call('POST', path, dict(request_id=rid(), project_id=self.project, revision=2, title='Changed'), status=409)
        self.assertEqual(self.call('GET', path + '/pdf', token=grant['token']).data, original)
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_old_tokens_and_narrow_report_token_cannot_open_other_business_routes(self):
        body = capture_body(self.office, self.owner, self.project)
        old = self.grant(scopes=['time_events', 'field_media'])['token']
        self.call('POST', PATH, body, token=old, status=403)
        legacy = self.call('POST', '/offline/access', {}, status=201).json['token']
        self.call('POST', PATH, body, token=legacy, status=403)
        report = self.grant(scopes=['offline_reports'])['token']
        row, _ = self.capture(token=report, body=body)
        root = '/business/service-reports/' + row['id']
        for path in ('/business/service-reports', '/business/documents', '/business/finance/payments',
                     '/business/employees', '/business/receipt-media', '/business/media',
                     '/business/time/entries', '/reports/' + row['id'], '/projects/' + self.project + '/reports'):
            with self.subTest(path=path):
                self.call('GET', path, token=report, status=403)
        for path in (root, root + '/sign', '/business/media', '/business/time/events', '/business/offline/access'):
            with self.subTest(path=path):
                self.call('POST', path, {}, token=report, status=403)
        metadata = self.call('GET', '/business/capabilities', token=report).json
        self.assertEqual(metadata['capabilities'], ['business_operations'])
        self.assertEqual(metadata['report_project_ids'], [self.project])
        self.assertFalse(any(item.startswith(('finance.', 'personnel.', 'settings.')) for item in metadata['permissions']))
        self.assertNotIn('organization', metadata)
        self.assertNotIn('report_project_ids', self.call('GET', '/business/capabilities', token=old).json)

    def test_capture_get_and_pdf_are_own_only_and_project_permissions_are_fresh(self):
        own = self.grant(token=self.technician)['token']
        row, body = self.capture(token=own)
        path = '/business/service-reports/' + row['id']
        other = self.grant()['token']
        for target in (path, path + '/pdf', '/business/service-reports/' + rid()):
            self.call('GET', target, token=other, status=403)
        # Even an own, normally signed online report is outside this capability.
        draft = self.call('POST', '/business/service-reports', dict(request_id=rid(), project_id=self.project,
            title='Normal online report', description='Synthetic online draft'), token=self.technician, status=201).json
        self.call('GET', '/business/service-reports/' + draft['id'], token=own, status=403)
        self.permission('documents.read', 'deny', scope=self.project)
        self.assertEqual(self.call('GET', '/business/capabilities', token=own).json['report_project_ids'], [])
        self.call('GET', path, token=own, status=403)
        self.call('GET', path + '/pdf', token=own, status=403)
        self.call('POST', PATH, body, token=own, status=403)
        self.permission('documents.read', 'allow', scope=self.project, revision=1)
        self.call('POST', '/assignments', dict(project_id=self.project, user_id=self.technician_id, remove=True))
        self.call('GET', path, token=own, status=403)
        self.call('POST', PATH, body, token=own, status=403)

    def test_project_scoped_grant_and_write_revocation_are_enforced_server_side(self):
        self.permission('documents.write', 'deny', scope=self.project)
        disabled = self.grant(token=self.technician)
        self.assertNotIn('offline_reports', disabled['capabilities'])
        self.assertEqual(disabled['report_project_ids'], [])
        self.permission('documents.write', 'allow', scope=self.project, revision=1)
        enabled = self.grant(token=self.technician)
        self.assertEqual(enabled['report_project_ids'], [self.project])
        row, body = self.capture(token=enabled['token'])
        self.permission('documents.write', 'deny', revision=0)
        self.call('POST', PATH, body, token=enabled['token'], status=403)
        self.assertEqual(self.call('GET', '/business/capabilities', token=enabled['token']).json['report_project_ids'], [])
        self.assertEqual(self.call('GET', '/business/service-reports/' + row['id'], token=enabled['token']).json, row)

    def test_pause_retains_project_hints_and_original_command_can_retry_after_resume(self):
        grant = self.grant(token=self.technician)
        row, body = self.capture(token=grant['token'])
        pending = capture_body(self.office, self.owner, self.project)
        self.module(False)
        metadata = self.call('GET', '/business/capabilities', token=grant['token']).json
        self.assertEqual(metadata['report_project_ids'], [self.project])
        self.assertFalse(metadata['report_writes_enabled'])
        for command in (body, pending):
            self.call('POST', PATH, command, token=grant['token'], status=423)
        self.assertEqual(self.call('GET', '/business/service-reports/' + row['id'], token=grant['token']).json, row)
        self.assertNotIn('offline_reports', self.grant(token=self.technician)['capabilities'])
        self.module(True)
        self.assertTrue(self.call('GET', '/business/capabilities', token=grant['token']).json['report_writes_enabled'])
        self.assertEqual(self.capture(token=grant['token'], body=body)[0], row)
        self.capture(token=grant['token'], body=pending)
        business_schema.set_mode(self.office, 'legacy')
        metadata = self.call('GET', '/business/capabilities', token=grant['token']).json
        self.assertFalse(metadata['report_writes_enabled'])
        self.assertEqual(metadata['report_project_ids'], [self.project])
        self.call('POST', PATH, body, token=grant['token'], status=409)

    def test_ambiguous_json_query_get_body_and_extra_capture_fields_never_write(self):
        token = self.grant()['token']
        body = capture_body(self.office, self.owner, self.project)
        before = self.office.db.total_changes
        self.call('POST', PATH + '?ignored=1', body, token=token, status=400)
        self.call('POST', PATH, dict(body, ignored=True), token=token, status=400)
        raw = canonical(body)
        for invalid in ('{"request_id":"duplicate",' + raw[1:], '{"x":NaN}', '[1]', '\ufeff' + raw):
            self.call('POST', PATH, invalid.encode(), token=token, mime='application/json', status=400)
        for target in ('/business/service-reports/' + body['entry_id'], '/business/service-reports/' + body['entry_id'] + '/pdf'):
            self.call('GET', target, {}, token=token, status=400)
        self.assertEqual(self.office.db.total_changes, before)
        row, _ = self.capture(token=token, body=body)
        self.call('GET', '/business/service-reports/' + row['id'] + '?project_id=' + self.project, token=token, status=400)

    def test_render_does_not_hold_global_lock_and_final_recheck_stops_revoked_write(self):
        token = self.grant(token=self.technician)['token']
        body = capture_body(self.office, self.owner, self.project)
        rendering, proceed = threading.Event(), threading.Event()
        real = business_operations._render_pdf
        def barrier(value):
            rendering.set()
            if not proceed.wait(5):
                raise AssertionError('Permission change could not acquire Office lock during render')
            return real(value)
        with ThreadPoolExecutor(max_workers=2) as executor, patch('business_operations._render_pdf', side_effect=barrier):
            response = executor.submit(self.call, 'POST', PATH, body, token=token, status=403)
            self.assertTrue(rendering.wait(5))
            denied = executor.submit(self.permission, 'documents.write', 'deny', scope=self.project)
            try:
                denied.result(timeout=4)
            finally:
                proceed.set()
            response.result(timeout=10)
        self.assertIsNone(self.office.db.execute('SELECT id FROM business_operation_entries WHERE id=?', (body['entry_id'],)).fetchone())
        self.assertIsNone(self.office.db.execute('SELECT request_id FROM business_operations_requests WHERE request_id=?', (body['request_id'],)).fetchone())

    def test_restore_keeps_exact_capture_pdf_and_receipt_but_revokes_device_token(self):
        token = self.grant()['token']
        row, body = self.capture(token=token)
        path = '/business/service-reports/' + row['id']
        original = self.call('GET', path + '/pdf', token=token).data
        source = Path(self.temporary.name) / 'office.db'
        destination = restore(source, Path(self.temporary.name) / 'restored.db')
        restored = Office(destination)
        self.addCleanup(restored.db.close)
        self.assertTrue(business_schema.validate_integrity(restored))
        self.office = restored
        self.app = create_app(office=restored, key=self.key, host='office.example.test')
        self.client = self.app.test_client()
        self.call('POST', PATH, body, token=token, status=401)
        self.token = restored.login('owner@example.test', 'Owner-password-123')
        renewed = self.grant()['token']
        self.assertEqual(self.capture(token=renewed, body=body)[0], row)
        self.assertEqual(self.call('GET', path + '/pdf', token=renewed).data, original)
        self.assertEqual(restored.db.execute('SELECT COUNT(*) FROM business_operation_entries').fetchone()[0], 1)
        self.assertEqual(restored.db.execute('SELECT financial_reconciliation_required FROM business_restore_state').fetchone()[0], 1)


class OfflineReportsTlsTests(unittest.TestCase):
    new_company = journey.AccountingJourneyTests.new_company
    login = journey.AccountingJourneyTests.login
    open_app = tls_fixture.AccountingAllocationsJourneyTests.open_app
    call = tls_fixture.AccountingAllocationsJourneyTests.call

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='synthetic-offline-report-tls-')
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.company = self.new_company('offline-report')

    def test_actual_trusted_tls_normal_mfa_retry_and_integrated_archive(self):
        company = self.company
        token = self.call(company, '/business/offline/access', {}, status=201).json['token']
        actor = company['office'].user(company['token'])
        body = capture_body(company['office'], actor, company['project'])
        row = self.call(company, PATH, body, token=token, status=201).json
        self.assertEqual(self.call(company, PATH, body, token=token, status=201).json, row)
        pdf = self.call(company, '/business/service-reports/' + row['id'] + '/pdf', token=token).data
        self.assertEqual(hashlib.sha256(pdf).hexdigest(), row['pdf_sha256'])
        self.call(company, '/business/service-reports', token=token, status=403)
        self.call(company, '/business/employees', token=token, status=403)
        self.call(company, '/offline/logout', {}, token=token)
        self.call(company, PATH, body, token=token, status=401)


if __name__ == '__main__':
    unittest.main()
