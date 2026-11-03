"""A real persisted customer publication/inbox/acceptance workflow."""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
import uuid

from PIL import Image

import business_schema
from business_customer_workspace import CustomerWorkspace, validate_integrity
from business_operations import BusinessOperations
from core import Office, Problem


def request(**body):
    return dict(request_id=uuid.uuid4().hex, **body)


def png():
    stream = io.BytesIO()
    Image.new('RGB', (3, 3), '#b1c2d3').save(stream, format='PNG')
    return stream.getvalue()


class CustomerWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='synthetic-customer-workspace-')
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)/'office.sqlite3'
        self.office = Office(self.path)
        self.addCleanup(lambda: self.office.db.close())
        self.office.portal_origin = 'https://portal.example.test'
        self.owner = dict(id=self.office.add_user('owner@example.test', 'Synthetic-owner-password', 'owner'), role='owner')
        self.other = dict(id=self.office.add_user('other@example.test', 'Synthetic-other-password', 'technician'), role='technician')
        self.project = self.office.add_project(self.owner, 'Synthetisches Projekt', 'Synthetischer Kunde')
        self.private = self.office.add_project(self.owner, 'Privates Projekt', 'Anderer Kunde')
        self.api = CustomerWorkspace(self.office)
        self.content = png()

    def problem(self, status, function, *args):
        with self.assertRaises(Problem) as caught:
            function(*args)
        self.assertEqual(caught.exception.status, status, caught.exception.message)

    def binding(self, project=None):
        return self.api._project(project or self.project)

    def grant(self, *, project=None, email='customer@example.test', upload=True):
        current = self.binding(project)
        body = request(project_id=current['id'], customer_id=current['customer_id'], recipient_name='Kundin',
            recipient_email=email, expires_in_days=7, allow_upload=upload, confirmation=True)
        result = self.api.create_grant(self.owner, body)
        parts = parse_qs(urlsplit(result['portal_url']).fragment)
        session = self.api.open_session(result['grant']['id'], parts['key'][0])
        return result, body, session['token'], parts['key'][0]

    def upload(self, token, **changes):
        body = request(filename='Synthetisches Foto.png', media_type='image/png', size=len(self.content),
            sha256=hashlib.sha256(self.content).hexdigest(), content_base64=base64.b64encode(self.content).decode(),
            note='Bitte bei der Ausführung beachten.')
        body.update(changes)
        return self.api.upload(token, body), body

    def publication(self, **changes):
        current = self.binding()
        body = request(project_id=self.project, customer_id=current['customer_id'], expected_revision=0,
            title='Freigegebener Baufortschritt', description='Montage am Dienstag. Bitte Zugang bereitstellen.',
            status_label='Ausführung geplant', start_date='2026-11-03', end_date='2026-11-04', confirmation=True)
        body.update(changes)
        return self.api.publish(self.owner, body), body

    def accept(self, upload_id, **changes):
        body = request(confirmation=True, classification='operational')
        body.update(changes)
        return self.api.accept_upload(self.owner, upload_id, body), body

    def publish_media(self, media_id):
        current = self.binding()
        body = request(project_id=self.project, customer_id=current['customer_id'], source_kind='media',
            source_id=media_id, source_sha256=hashlib.sha256(self.content).hexdigest(), title='Freigegebenes Kundenfoto', confirmation=True)
        return self.api.publish_file(self.owner, body), body

    def test_whole_publication_inbox_acceptance_download_revocation_and_restart(self):
        grant, _, token, _ = self.grant()
        publication, publish_request = self.publication()
        public = self.api.view(token)
        self.assertEqual(public['grant_id'], grant['grant']['id'])
        self.assertEqual(public['project']['id'], self.project)
        self.assertEqual(public['publication']['description'], publication['description'])
        self.assertNotIn('customer_id', public['publication'])
        self.assertEqual(self.api.publish(self.owner, publish_request), publication)
        uploaded, upload_request = self.upload(token, note='  Originalhinweis mit Leerraum.\n')
        self.assertEqual(uploaded['status'], 'received')
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_media').fetchone()[0], 0)
        self.assertEqual(self.api.upload(token, upload_request), uploaded)
        self.assertEqual(self.api.staff_content(self.owner, 'uploads', uploaded['id'])[0], self.content)
        accepted, accept_request = self.accept(uploaded['id'])
        self.assertEqual(self.api.accept_upload(self.owner, uploaded['id'], accept_request), accepted)
        self.assertEqual(self.api.accept_upload(self.owner, uploaded['id'], request(confirmation=True, classification='operational')), accepted)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_media').fetchone()[0], 1)
        self.assertEqual(self.api.view(token)['files'], [])
        released, release_request = self.publish_media(accepted['media_id'])
        self.assertEqual(self.api.publish_file(self.owner, release_request), released)
        self.assertEqual(self.api.content(token, 'files', released['id'])[0], self.content)
        self.assertEqual(self.api.view(token)['uploads'][0]['status'], 'accepted')
        validate_integrity(self.office)
        business_schema.validate_integrity(self.office)
        self.office.db.close()
        self.office = Office(self.path)
        self.office.portal_origin = 'https://portal.example.test'
        self.api = CustomerWorkspace(self.office)
        self.assertEqual(self.api.upload(token, upload_request)['id'], uploaded['id'])
        self.assertEqual(self.api.content(token, 'files', released['id'])[0], self.content)
        self.api.revoke_file(self.owner, released['id'], request(reason='Korrigierte Freigabe folgt.'))
        self.problem(404, self.api.content, token, 'files', released['id'])
        self.assertEqual(self.api.content(token, 'uploads', uploaded['id'])[0], self.content)
        self.api.revoke_grant(self.owner, grant['grant']['id'], request(reason='Projekt beendet.'))
        self.problem(401, self.api.view, token)
        validate_integrity(self.office)

    def test_grant_reply_never_persists_or_replays_secret_and_old_token_types_are_rejected(self):
        grant, command, token, secret = self.grant()
        replay = self.api.create_grant(self.owner, command)
        self.assertFalse(replay['link_available'])
        self.assertNotIn('portal_url', replay)
        rows = '\n'.join(row[0] for row in self.office.db.execute('SELECT result_json FROM business_customer_staff_requests'))
        self.assertNotIn(secret, rows)
        for prefix in ('SPPI_', 'SPPT_', 'offline_', 'SPIX_'):
            self.problem(401, self.api.view, prefix+'a'*43)
            self.problem(401, self.api.open_session, grant['grant']['id'], prefix+'a'*43)
        self.assertTrue(self.api.view(token)['uploads_allowed'])

    def test_two_recipients_share_only_published_files_not_each_others_inbox(self):
        _, _, first, _ = self.grant()
        _, _, second, _ = self.grant(email='second@example.test')
        uploaded, _ = self.upload(first)
        self.assertEqual(self.api.view(second)['uploads'], [])
        self.problem(404, self.api.content, second, 'uploads', uploaded['id'])
        accepted, _ = self.accept(uploaded['id'])
        released, _ = self.publish_media(accepted['media_id'])
        self.assertEqual(self.api.content(second, 'files', released['id'])[0], self.content)
        _, _, foreign, _ = self.grant(project=self.private, email='foreign@example.test')
        self.problem(404, self.api.content, foreign, 'files', released['id'])
        self.problem(404, self.api.content, foreign, 'uploads', uploaded['id'])

    def test_customer_change_and_fresh_employee_rights_block_repeated_writes(self):
        _, command, token, _ = self.grant()
        uploaded, upload_command = self.upload(token)
        current = self.binding(self.private)
        with self.office.db:
            self.office.db.execute('UPDATE projects SET customer_id=? WHERE id=?', (current['customer_id'], self.project))
        self.problem(401, self.api.view, token)
        self.problem(401, self.api.upload, token, upload_command)
        self.problem(409, self.api.create_grant, self.owner, command)
        self.problem(409, self.api.accept_upload, self.owner, uploaded['id'], request(confirmation=True, classification='operational'))
        with self.office.db:
            self.office.db.execute("UPDATE users SET role='viewer' WHERE id=?", (self.owner['id'],))
        self.problem(404, self.api.create_grant, self.owner, command)

    def test_pause_stops_upload_and_replays_but_current_revoke_remains_possible(self):
        grant, command, token, _ = self.grant()
        _, upload_request = self.upload(token)
        from business_organization import Organization
        organization = Organization(self.office)
        state = organization.get(self.owner)
        state['modules']['documents']['enabled'] = False
        organization.save(self.owner, request(revision=state['revision'], needs=state['needs'],
            modules={key: dict(visible=value['visibility_override'], enabled=value['enabled']) for key, value in state['modules'].items()}))
        self.assertFalse(self.api.view(token)['uploads_allowed'])
        self.problem(423, self.api.upload, token, upload_request)
        self.problem(423, self.api.create_grant, self.owner, command)
        self.api.revoke_grant(self.owner, grant['grant']['id'], request(reason='Zugang trotz Modulpause widerrufen.'))
        self.problem(401, self.api.view, token)

    def test_unsupported_or_changed_uploads_never_create_partial_inbox_records(self):
        _, _, token, _ = self.grant(upload=False)
        self.problem(403, self.upload, token)
        _, _, token, _ = self.grant(email='uploader@example.test')
        uploaded, body = self.upload(token)
        for changes in ({'note': 'Anderer Inhalt'}, {'size': len(self.content)+1}, {'sha256': '0'*64}):
            self.problem(409, self.api.upload, token, {**body, **changes})
        for changes in ({'media_type': 'image/svg+xml'}, {'media_type': []}, {'filename': '../fremd.png'}, {'filename': '\ud800.png'}, {'content_base64': 'not base64'}, {'note': '\ud800'}):
            self.problem(400, self.api.upload, token, {**body, **changes, 'request_id': uuid.uuid4().hex})
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_customer_uploads').fetchone()[0], 1)
        self.assertEqual(self.api.view(token)['uploads'][0]['id'], uploaded['id'])

    def test_acceptance_is_atomic_and_cannot_reclassify_an_existing_import(self):
        _, _, token, _ = self.grant()
        uploaded, _ = self.upload(token)
        body = request(confirmation=True, classification='restricted')
        with patch.object(BusinessOperations, 'complete_media', side_effect=Problem(409, 'synthetic validation failure')):
            self.problem(409, self.api.accept_upload, self.owner, uploaded['id'], body)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_media').fetchone()[0], 0)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_customer_acceptances').fetchone()[0], 0)
        result = self.api.accept_upload(self.owner, uploaded['id'], body)
        self.assertEqual(result['classification'], 'restricted')
        self.problem(409, self.api.accept_upload, self.owner, uploaded['id'], request(confirmation=True, classification='operational'))
        validate_integrity(self.office)

    def test_published_versions_are_concurrent_safe_and_immutable_even_under_replace(self):
        current = self.binding()
        commands = [request(project_id=self.project, customer_id=current['customer_id'], expected_revision=0,
            title='Freigabe '+str(index), description='Geprüfter Text', status_label='', start_date=None, end_date=None, confirmation=True) for index in range(2)]
        def publish(body):
            try:
                return self.api.publish(self.owner, body)
            except Problem as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(publish, commands))
        self.assertEqual(sum(isinstance(value, dict) for value in results), 1)
        self.assertIn(409, results)
        row = dict(self.office.db.execute('SELECT * FROM business_customer_publications').fetchone())
        for statement, parameters in [('UPDATE business_customer_publications SET payload_json=? WHERE id=?', ('{}', row['id'])),
                ('DELETE FROM business_customer_publications WHERE id=?', (row['id'],)),
                ('INSERT OR REPLACE INTO business_customer_publications('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')', tuple(row.values()))]:
            with self.assertRaises(sqlite3.DatabaseError), self.office.db:
                self.office.db.execute(statement, parameters)
        validate_integrity(self.office)

    def test_private_personnel_media_is_never_a_publishable_source(self):
        _, _, token, _ = self.grant()
        uploaded, _ = self.upload(token)
        accepted, _ = self.accept(uploaded['id'], classification='personnel')
        self.assertNotIn(accepted['media_id'], [item['source_id'] for item in self.api.view_staff(self.owner, self.project)['source_files']])
        self.problem(409, self.publish_media, accepted['media_id'])

    def test_internal_classification_rights_apply_to_accepted_inbox_and_released_copies(self):
        from business_foundation import BusinessFoundation
        self.office.assign(self.owner, self.project, self.other['id'])
        BusinessFoundation(self.office).save_grant(self.owner, request(user_id=self.other['id'],
            permission='portal.manage', scope=self.project, effect='allow', revision=0))
        _, _, token, _ = self.grant()
        uploaded, _ = self.upload(token)
        self.assertEqual(self.api.view_staff(self.other, self.project)['uploads'][0]['id'], uploaded['id'])
        accepted, _ = self.accept(uploaded['id'], classification='financial')
        published, _ = self.publish_media(accepted['media_id'])
        current = self.api.view_staff(self.other, self.project)
        self.assertEqual(current['uploads'], [])
        self.assertEqual(current['files'], [])
        self.assertNotIn(accepted['media_id'], [item['source_id'] for item in current['source_files']])
        self.problem(403, self.api.staff_content, self.other, 'uploads', uploaded['id'])
        self.problem(403, self.api.staff_content, self.other, 'files', published['id'])
        self.assertEqual(self.api.content(token, 'files', published['id'])[0], self.content)
        self.assertEqual(self.api.content(token, 'uploads', uploaded['id'])[0], self.content)

    def test_restore_validation_rejects_retargeted_receipts_and_rehashed_extra_publication_fields(self):
        _, _, token, _ = self.grant()
        uploaded, _ = self.upload(token)
        accepted, _ = self.accept(uploaded['id'])
        self.publish_media(accepted['media_id'])
        project = self.binding()
        publication = self.api.publish(self.owner, request(project_id=self.project, customer_id=project['customer_id'],
            expected_revision=0, title='Nur freigegebene Information', description='Geprüfter Inhalt',
            status_label='', start_date=None, end_date=None, confirmation=True))
        for kind in ('receipt', 'publication'):
            # Deliberately damaged restore candidates bypass owner-side guards;
            # the independent semantic verifier must still reject them.
            self.office.db.execute('BEGIN')
            try:
                if kind == 'receipt':
                    self.office.db.execute('DROP TRIGGER business_customer_staff_requests_update_guard')
                    self.office.db.execute("UPDATE business_customer_staff_requests SET result_json='{}' WHERE operation='accept'")
                else:
                    self.office.db.execute('DROP TRIGGER business_customer_publications_update_guard')
                    changed = json.dumps({**publication, 'internal_notes': 'Must never enter a public snapshot'}, sort_keys=True, separators=(',', ':'))
                    self.office.db.execute('UPDATE business_customer_publications SET payload_json=?,sha256=?', (changed, hashlib.sha256(changed.encode()).hexdigest()))
                with self.assertRaisesRegex(ValueError, 'Invalid customer workspace history'):
                    validate_integrity(self.office)
            finally:
                self.office.db.rollback()
        validate_integrity(self.office)


if __name__ == '__main__':
    unittest.main()
