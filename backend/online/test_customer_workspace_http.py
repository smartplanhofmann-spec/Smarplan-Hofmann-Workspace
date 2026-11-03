"""Customer project access through real MFA, separate credentials and restore."""
import base64
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
import unittest
import uuid

import business_schema
from business_customer_workspace import CustomerWorkspace, MAX_UPLOAD
from core import Office
from online import test_portal_http as fixture
from online.web import create_app
from restore import restore
from test_business_customer_workspace import png


class CustomerWorkspaceHTTPTests(unittest.TestCase):
    setUp = fixture.PortalHTTPTests.setUp
    staff_call = fixture.PortalHTTPTests.staff_call
    req = staticmethod(fixture.PortalHTTPTests.req)

    def call(self, path, body=None, **options):
        method = options.get('method') or ('POST' if body is not None or options.get('raw') is not None else 'GET')
        if path.startswith('/customer-workspace') and method == 'POST' and options.get('origin', 'configured') is not None:
            origin = options.get('origin', 'configured')
            headers = dict(options.get('headers') or {})
            headers.setdefault('Origin', self.origin if origin == 'configured' else origin)
            options['headers'] = headers
        return fixture.PortalHTTPTests.call(self, path, body, **options)

    def access(self):
        project = self.staff_call('/projects', {'name': 'Freigegebenes Projekt', 'customer': 'Synthetischer Kunde'}, status=201).json['id']
        state = self.staff_call('/business/customer-workspace?project_id='+project).json
        command = self.req(project_id=project, customer_id=state['project']['customer_id'], recipient_name='Kundin',
            recipient_email='customer@example.test', expires_in_days=7, allow_upload=True, confirmation=True)
        result = self.staff_call('/business/customer-workspace/grants', command, status=201).json
        invitation = dict(grant_id=result['grant']['id'], key=parse_qs(urlsplit(result['portal_url']).fragment)['key'][0])
        token = self.call('/customer-workspace/sessions', invitation, status=201).json['token']
        return dict(project=project, customer=state['project']['customer_id'], grant=result['grant']['id'],
            invitation=invitation, token=token, command=command)

    def upload(self, access, **changes):
        content = png()
        command = self.req(filename='kundenfoto.png', media_type='image/png', size=len(content),
            sha256=hashlib.sha256(content).hexdigest(), content_base64=base64.b64encode(content).decode(), note='Bitte prüfen.')
        command.update(changes)
        result = self.call('/customer-workspace/uploads', command, token=access['token'], status=201).json
        return result, command, content

    def test_actual_upload_review_accept_publish_download_and_identical_replies(self):
        access = self.access()
        publication = self.req(project_id=access['project'], customer_id=access['customer'], expected_revision=0,
            title='Ausführung', description='Am Dienstag ist der Eingang erforderlich.', status_label='Geplant',
            start_date=None, end_date=None, confirmation=True)
        self.staff_call('/business/customer-workspace/publications', publication, status=201)
        uploaded, command, content = self.upload(access)
        self.assertEqual(self.call('/customer-workspace/uploads', command, token=access['token'], status=201).json, uploaded)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_media').fetchone()[0], 0)
        private = '/business/customer-workspace/uploads/'+uploaded['id']+'/content'
        self.assertEqual(self.staff_call(private).data, content)
        accept = self.req(classification='operational', confirmation=True)
        accepted = self.staff_call('/business/customer-workspace/uploads/'+uploaded['id']+'/accept', accept, status=201).json
        self.assertEqual(self.staff_call('/business/customer-workspace/uploads/'+uploaded['id']+'/accept', accept, status=201).json, accepted)
        view = self.staff_call('/business/customer-workspace?project_id='+access['project']).json
        source = next(item for item in view['source_files'] if item['source_id'] == accepted['media_id'])
        original = '/business/customer-workspace/sources/media/'+accepted['media_id']+'/content?project_id='+access['project']
        self.assertEqual(self.staff_call(original).data, content)
        release = self.req(project_id=access['project'], customer_id=access['customer'], source_kind='media', source_id=accepted['media_id'],
            source_sha256=source['sha256'], title='Geprüftes Kundenfoto', confirmation=True)
        published = self.staff_call('/business/customer-workspace/files', release, status=201).json
        public = self.call('/customer-workspace/workspace', token=access['token']).json
        self.assertEqual(public['project']['id'], access['project'])
        self.assertEqual(public['files'][0]['id'], published['id'])
        self.assertEqual(public['uploads'][0]['status'], 'accepted')
        self.assertNotIn('source_files', public)
        self.assertNotIn('grants', public)
        download = self.call('/customer-workspace/files/'+published['id']+'/content', token=access['token'])
        self.assertEqual(download.data, content)
        self.assertIn('attachment;', download.headers['Content-Disposition'])
        self.assertEqual(download.mimetype, 'image/png')
        business_schema.validate_integrity(self.office)

    def test_no_credential_family_can_cross_and_public_paths_remain_strict(self):
        access = self.access()
        existing_offer = fixture.PortalHTTPTests.access(self)
        self.call('/customer-workspace/workspace', token=existing_offer['token'], status=401)
        self.call('/customer-workspace/sessions', existing_offer['invitation'], status=401)
        self.assertEqual(self.call('/portal/offer', token=existing_offer['token']).json['offer']['id'], existing_offer['offer']['id'])
        for token in (self.staff, 'SPPT_'+'a'*43, 'SPPI_'+'a'*43, 'SPCI_'+'a'*43, 'offline_'+'a'*43):
            self.call('/customer-workspace/workspace', token=token, status=401)
        self.call('/portal/offer', token=access['token'], status=401)
        self.call('/projects', token=access['token'], status=401)
        self.call('/business/finance/open-items', token=access['token'], status=401)
        self.call('/customer-workspace/workspace?project_id='+access['project'], token=access['token'], status=400)
        self.call('/customer-workspace/workspace', {}, token=access['token'], method='GET', status=400)
        self.call('/customer-workspace/workspace', {}, token=access['token'], status=405)
        self.call('/customer-workspace/sessions', access['invitation'], token=self.staff, status=401)
        self.call('/customer-workspace/sessions', access['invitation'], origin=None, status=403)
        self.call('/customer-workspace/logout', {}, token=access['token'], origin='https://foreign.example.test', status=403)
        self.staff_call('/business/customer-workspace/grants?unexpected=1', access['command'], status=400)
        self.staff_call('/business/customer-workspace/grants', {**access['command'], 'injected': True}, status=400)

    def test_duplicate_nonfinite_compressed_and_malformed_customer_uploads_fail_closed(self):
        access = self.access()
        self.call('/customer-workspace/sessions', raw='{"grant_id":"'+access['grant']+'","grant_id":"'+access['grant']+'","key":"'+access['invitation']['key']+'"}', status=400)
        self.call('/customer-workspace/uploads', raw='{"request_id":NaN}', token=access['token'], status=400)
        self.call('/customer-workspace/logout', {}, token=access['token'], headers={'Content-Encoding': 'gzip'}, status=400)
        self.call('/customer-workspace/logout', raw='{}', mimetype='text/plain', token=access['token'], status=415)
        self.call('/customer-workspace/uploads', self.req(filename='../bad.png', media_type='image/png', size=1,
            sha256='a'*64, content_base64='YQ==', note=''), token=access['token'], status=400)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_customer_uploads').fetchone()[0], 0)

    def test_separate_company_database_never_accepts_other_company_links_tokens_or_originals(self):
        from cryptography.fernet import Fernet
        access = self.access()
        uploaded, _, _ = self.upload(access)
        second = Office(self.directory/'separate-company.sqlite3')
        self.addCleanup(second.db.close)
        other_actor = dict(id=second.add_user('second-company@example.test', 'Synthetic-other-owner-password', 'owner'), role='owner')
        other_project = second.add_project(other_actor, 'Separate company project', 'Separate company customer')
        other_app = create_app(office=second, key=Fernet.generate_key(), host='portal.example.test', storage_config={})
        api = CustomerWorkspace(second)
        grant = api.create_grant(other_actor, self.req(project_id=other_project,
            customer_id=api.view_staff(other_actor, other_project)['project']['customer_id'],
            recipient_name='Separate recipient', recipient_email='separate@example.test',
            expires_in_days=7, allow_upload=False, confirmation=True))
        invitation = dict(grant_id=grant['grant']['id'], key=parse_qs(urlsplit(grant['portal_url']).fragment)['key'][0])
        session = self.call('/customer-workspace/sessions', invitation, client=other_app.test_client(), status=201).json
        self.call('/customer-workspace/workspace', token=access['token'], client=other_app.test_client(), status=401)
        self.call('/customer-workspace/sessions', access['invitation'], client=other_app.test_client(), status=401)
        self.call('/customer-workspace/uploads/'+uploaded['id']+'/content', token=session['token'], client=other_app.test_client(), status=404)
        self.call('/customer-workspace/workspace', token=session['token'], status=401)
        self.call('/customer-workspace/sessions', invitation, status=401)
        self.assertEqual(self.call('/customer-workspace/workspace', token=session['token'], client=other_app.test_client()).json['project']['id'], other_project)

    def test_large_supported_upload_uses_bounded_customer_limit_not_staff_json_limit(self):
        access = self.access()
        # A valid, bounded PDF envelope exercises the real >1 MiB HTTP boundary.
        content = b'%PDF-1.4\n'+b'\n%synthetic bounded fixture'*50000+b'\n%%EOF'
        self.assertGreater(len(content), 1_000_000)
        self.assertLess(len(content), MAX_UPLOAD)
        body = self.req(filename='synthetic-large.pdf', media_type='application/pdf', size=len(content),
            sha256=hashlib.sha256(content).hexdigest(), content_base64=base64.b64encode(content).decode(), note='Synthetischer Transporttest')
        result = self.call('/customer-workspace/uploads', body, token=access['token'], status=201).json
        self.assertEqual(self.call('/customer-workspace/uploads/'+result['id']+'/content', token=access['token']).data, content)

    def test_modulpause_stops_new_work_but_allows_explicit_revocation(self):
        access = self.access()
        state = self.staff_call('/business/organization').json
        modules = {key: dict(visible=value['visibility_override'], enabled=value['enabled']) for key, value in state['modules'].items()}
        modules['documents']['enabled'] = False
        self.staff_call('/business/organization', self.req(revision=state['revision'], needs=state['needs'], modules=modules))
        self.assertFalse(self.call('/customer-workspace/workspace', token=access['token']).json['uploads_allowed'])
        self.staff_call('/business/customer-workspace/grants', access['command'], status=423)
        self.staff_call('/business/customer-workspace/grants/'+access['grant']+'/revoke', self.req(reason='Zugang sperren'), status=201)
        self.call('/customer-workspace/workspace', token=access['token'], status=401)

    def test_actual_restore_retains_originals_and_receipts_but_revokes_all_customer_access(self):
        access = self.access()
        uploaded, command, content = self.upload(access)
        accepted = self.staff_call('/business/customer-workspace/uploads/'+uploaded['id']+'/accept', self.req(classification='restricted', confirmation=True), status=201).json
        before = dict(self.office.db.execute('SELECT * FROM business_customer_uploads WHERE id=?', (uploaded['id'],)).fetchone())
        receipt = dict(self.office.db.execute('SELECT * FROM business_customer_upload_requests WHERE upload_id=?', (uploaded['id'],)).fetchone())
        destination = self.directory/'restored.sqlite3'
        restore(self.path, destination)
        restored = Office(destination)
        self.addCleanup(restored.db.close)
        app = create_app(office=restored, key=self.key, host='portal.example.test', storage_config={})
        self.call('/customer-workspace/workspace', token=access['token'], client=app.test_client(), status=401)
        self.call('/customer-workspace/sessions', access['invitation'], client=app.test_client(), status=401)
        self.assertEqual(dict(restored.db.execute('SELECT * FROM business_customer_uploads WHERE id=?', (uploaded['id'],)).fetchone()), before)
        self.assertEqual(dict(restored.db.execute('SELECT * FROM business_customer_upload_requests WHERE upload_id=?', (uploaded['id'],)).fetchone()), receipt)
        self.assertEqual(bytes(restored.db.execute('SELECT original FROM business_media WHERE id=?', (accepted['media_id'],)).fetchone()['original']), content)
        self.assertEqual(restored.db.execute('SELECT COUNT(*) FROM business_customer_sessions').fetchone()[0], 0)
        business_schema.validate_integrity(restored)


if __name__ == '__main__':
    unittest.main()
