"""Synthetic mail-to-project attachment workflows through real Flask and SQL.

Only the separate PostgreSQL case needs services. Fixture helpers are composed;
importing their modules does not inherit or rediscover their existing tests.
"""
import hashlib
import io
import unittest
from urllib.parse import quote
import uuid

from psycopg.conninfo import conninfo_to_dict

import test_online as pg_fixture
import test_plan_imports as import_fixture
import test_workspace_api as workspace_fixture
from inquiry_attachments import CHUNK_SIZE
import plan_access


if pg_fixture.DSN and conninfo_to_dict(pg_fixture.DSN).get('host') not in ('127.0.0.1', 'localhost'):
    raise RuntimeError('Attachment HTTP tests require the disposable loopback smartplan_check database.')


def request_id():
    return uuid.uuid4().hex


def sha(data):
    return hashlib.sha256(data).hexdigest()


def large_png():
    result = io.BytesIO()
    import_fixture.Image.new('RGB', (320, 320), 'white').save(result, format='PNG', compress_level=0)
    return result.getvalue()


def synthetic_pdf():
    result = io.BytesIO()
    document = import_fixture.canvas.Canvas(result)
    document.drawString(40, 700, 'Synthetic attachment acceptance; no real customer information.')
    document.save()
    return result.getvalue()


class AttachmentHttpFlow(workspace_fixture.WorkspaceHttpFlow):
    """HTTP helpers and a shared workflow, intentionally without test methods."""

    intake = '/intake/gmail/attachments'

    def start_message(self, **changes):
        self.connector = self.issue_gmail()
        self.envelope = self.gmail_message(**changes)
        receipt = self.call('POST', '/intake/gmail', self.envelope, token=self.connector['token'], status=201).json
        self.assertEqual(set(receipt), {'id', 'status', 'ingested_at'})
        self.assertEqual(receipt['status'], 'received')
        self.inquiry = receipt['id']
        self.inquiry_path = '/inquiries/' + self.inquiry
        return receipt

    def descriptor(self, content, **changes):
        return {'source_attachment_id': 'provider/Attachment==17', 'filename': 'Aufmaß EG – Plan.png',
                'media_type': 'image/png', 'size': len(content), 'sha256': sha(content), **changes}

    def attachment_manifest(self, files):
        return {'source_account': self.envelope['source_account'], 'source_id': self.envelope['source_id'],
                'attachments': files}

    def announce(self, files, *, token=None):
        return self.call('POST', self.intake, self.attachment_manifest(files),
                         token=token or self.connector['token'], status=201).json

    def upload_path(self, attachment_id):
        return self.intake + '/' + attachment_id

    def inquiry_file(self, attachment_id):
        return self.inquiry_path + '/attachments/' + attachment_id

    def finish_file(self, row, content):
        path = self.upload_path(row['id'])
        for index, start in enumerate(range(0, len(content), CHUNK_SIZE)):
            self.call('PUT', path + '/chunks/' + str(index), content[start:start + CHUNK_SIZE],
                      token=self.connector['token'], mime='application/octet-stream')
        return self.call('POST', path + '/complete', {}, token=self.connector['token']).json

    def convert_message(self):
        customer = self.call('POST', '/customers', {
            'name': 'Synthetischer Kunde der Anhangabnahme', 'email': self.envelope['sender_email'],
        }, status=201).json
        entry = self.call('GET', self.inquiry_path).json
        self.assertEqual([row['id'] for row in entry['candidate_customers']], [customer['id']])
        converted = self.call('POST', self.inquiry_path + '/convert', {
            'request_id': request_id(), 'revision': entry['revision'],
            'project_name': 'Synthetisches Projekt mit Originaldokumenten', 'customer_id': customer['id'],
        }).json
        self.assertEqual(converted['inquiry']['acceptance_channel'], '')
        self.project = converted['project']['id']
        return '/projects/' + self.project

    def release_original(self, attachment_id):
        path = '/business/documents/mail/' + attachment_id + '/classification'
        current = self.call('GET', path).json
        return self.call('POST', path, {'request_id': request_id(), 'revision': current['revision'],
            'expected_source_fingerprint': current['source_fingerprint'], 'classification': 'operational'}).json

    def assert_download(self, response, content, filename):
        self.assertEqual(response.mimetype, 'application/octet-stream')
        self.assertEqual(response.data, content)
        self.assertEqual(sha(response.data), sha(content))
        self.assertEqual(response.headers['Content-Disposition'],
                         'attachment; filename="smartplan-anhang"; filename*=UTF-8\'\'' + quote(filename, safe=''))
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response.headers['Referrer-Policy'], 'no-referrer')

    def full_attachment_workflow(self):
        ready = self.client.get('/ready', base_url='https://office.example.test')
        self.assertEqual(ready.status_code, 200)
        self.assertIn('mail_attachments', ready.json['capabilities'])
        customers_before = len(self.call('GET', '/customers').json)
        self.start_message()
        entry = self.call('GET', self.inquiry_path).json
        self.assertEqual(entry['attachments']['status'], 'not_announced')
        self.assertIsNone(entry['attachments']['expected_count'])
        self.assertEqual(self.call('GET', self.inquiry_path + '/attachments').json, entry['attachments'])
        self.assertEqual(len(self.call('GET', '/customers').json), customers_before)
        png, pdf = large_png(), synthetic_pdf()
        self.assertGreater(len(png), CHUNK_SIZE)
        descriptors = [self.descriptor(png), self.descriptor(
            pdf, source_attachment_id='provider/Attachment==18', filename='Unterlagen – synthetisch.pdf', media_type='application/pdf')]
        manifest = self.attachment_manifest(descriptors)
        announced = self.announce(descriptors)
        self.assertEqual((announced['status'], announced['expected_count'], announced['ready_count']), ('uploading', 2, 0))
        self.assertEqual(announced['total_bytes'], len(png) + len(pdf))
        self.assertEqual(announced['chunk_size'], CHUNK_SIZE)
        first, second = announced['files']
        first_path = self.upload_path(first['id'])
        # The second PNG chunk arrives first; complete and downloads stay blocked.
        self.call('PUT', first_path + '/chunks/1', png[CHUNK_SIZE:], token=self.connector['token'], mime='application/octet-stream')
        self.call('POST', first_path + '/complete', {}, token=self.connector['token'], status=409)
        self.call('GET', self.inquiry_file(first['id']) + '/content', status=409)
        self.finish_file(second, pdf)
        partial = self.call('GET', self.inquiry_path + '/attachments').json
        self.assertEqual((partial['status'], partial['ready_count']), ('uploading', 1))
        self.reopen()
        resumed = self.call('POST', self.intake, manifest, token=self.connector['token'], status=201).json
        self.assertEqual([row['id'] for row in resumed['files']], [first['id'], second['id']])
        self.assertEqual(resumed['files'][0]['received_chunks'], [1])
        self.assertEqual(resumed['files'][1]['status'], 'ready')
        self.assertEqual(self.announce(list(reversed(descriptors))), resumed)
        self.call('PUT', first_path + '/chunks/0', png[:CHUNK_SIZE], token=self.connector['token'], mime='application/octet-stream')
        complete = self.call('POST', first_path + '/complete', {}, token=self.connector['token']).json
        self.assertEqual(complete['status'], 'ready')
        self.assertEqual(self.call('POST', first_path + '/complete', {}, token=self.connector['token']).json, complete)
        for row, content in ((first, png), (second, pdf)):
            self.assert_download(self.call('GET', self.inquiry_file(row['id']) + '/content'), content, row['filename'])
        summary = self.call('GET', self.inquiry_path).json['attachments']
        self.assertEqual((summary['status'], summary['ready_count']), ('complete', 2))
        self.assertTrue(all('received_chunks' not in row for row in summary['files']))
        base = self.convert_message()
        technician_id, technician = self.add_actor('technician')
        self.assertEqual(self.call('GET', base + '/mail-attachments', token=technician).json['files'], [])
        self.call('GET', base + '/mail-attachments/' + first['id'] + '/content', token=technician, status=404)
        for row in (first, second):
            self.release_original(row['id'])
        documents = self.call('GET', base + '/mail-attachments', token=technician).json
        self.assertEqual((documents['ready_count'], documents['pending_count'], documents['unannounced_count']), (2, 0, 0))
        self.assertEqual({row['inquiry_id'] for row in documents['files']}, {self.inquiry})
        self.assertTrue(all(row['subject'] == self.envelope['subject'] for row in documents['files']))
        self.call('GET', self.inquiry_path + '/attachments', token=technician, status=403)
        project_file = base + '/mail-attachments/' + first['id']
        self.assert_download(self.call('GET', project_file + '/content', token=technician), png, first['filename'])
        copy_request = {'request_id': request_id(), 'page': 0, 'title': 'Originalplan aus E-Mail'}
        copied = self.call('POST', project_file + '/plan-import', copy_request, token=technician, status=201).json
        self.assertEqual(copied['status'], 'queued')
        self.assertEqual(copied['sha256'], sha(png))
        self.assertEqual(self.call('POST', project_file + '/plan-import', copy_request, token=technician, status=201).json, copied)
        import_path = base + '/plan-imports/' + copied['id']
        self.assertEqual(self.call('GET', import_path + '/source', token=technician).data, png)
        self.call('POST', base + '/plan-imports/delete', {'request_id': request_id(), 'id': copied['id']}, token=technician)
        self.call('GET', import_path + '/source', token=technician, status=410)
        self.call('POST', project_file + '/plan-import', copy_request, token=technician, status=410)
        self.assert_download(self.call('GET', project_file + '/content', token=technician), png, first['filename'])
        # Removing another original neither removes the surviving original nor revives a plan source.
        delete_path = self.inquiry_file(second['id']) + '/delete'
        deleted = self.call('POST', delete_path, {}).json
        self.assertTrue(deleted['deleted'])
        self.assertEqual(self.call('POST', delete_path, {}).json, deleted)
        self.call('GET', self.inquiry_file(second['id']) + '/content', status=410)
        self.call('PUT', self.upload_path(second['id']) + '/chunks/0', pdf,
                  token=self.connector['token'], mime='application/octet-stream', status=410)
        self.call('POST', self.upload_path(second['id']) + '/complete', {}, token=self.connector['token'], status=410)
        self.reopen()
        tombstone = self.call('POST', self.intake, manifest, token=self.connector['token'], status=201).json
        self.assertEqual((tombstone['status'], tombstone['ready_count'], tombstone['deleted_count']), ('complete', 1, 1))
        self.assertEqual(tombstone['files'][1]['status'], 'deleted')
        self.assertEqual(tombstone['files'][1]['received_chunks'], [])
        documents = self.call('GET', base + '/mail-attachments', token=technician).json
        self.assertEqual([row['id'] for row in documents['files']], [first['id']])
        self.assertEqual(documents['deleted_count'], 0)  # Team counts cover released, visible files only.
        self.assertEqual(self.call('GET', base + '/mail-attachments').json['deleted_count'], 1)
        self.assertEqual(self.call('GET', project_file + '/content', token=technician).data, png)
        self.call('POST', '/assignments', {'project_id': self.project, 'user_id': technician_id, 'remove': True})
        self.call('GET', project_file + '/content', token=technician, status=404)


class InquiryAttachmentApiTests(AttachmentHttpFlow, unittest.TestCase):
    setUp = workspace_fixture.WorkspaceApiTests.setUp
    tearDown = import_fixture.PlanImportApiTests.tearDown
    open_app = import_fixture.PlanImportApiTests.open_app

    def test_full_mfa_mail_originals_project_import_and_independent_deletions(self):
        self.full_attachment_workflow()

    def test_empty_manifest_is_explicit_while_body_only_messages_remain_unannounced(self):
        self.start_message()
        self.assertEqual(self.call('GET', self.inquiry_path).json['attachments']['status'], 'not_announced')
        empty = self.announce([])
        self.assertEqual((empty['status'], empty['expected_count'], empty['total_bytes'], empty['files']), ('complete', 0, 0, []))
        self.assertEqual(self.call('GET', self.inquiry_path + '/attachments').json['expected_count'], 0)
        self.call('POST', self.intake, self.attachment_manifest([self.descriptor(import_fixture.png())]),
                  token=self.connector['token'], status=409)
        legacy = self.call('POST', '/intake/gmail', {**self.envelope, 'source_id': 'synthetic-body-only-18'},
                           token=self.connector['token'], status=201).json
        summary = self.call('GET', '/inquiries/' + legacy['id']).json['attachments']
        self.assertEqual((summary['status'], summary['expected_count']), ('not_announced', None))

    def test_normal_sessions_offline_keys_and_import_keys_keep_their_distinct_scopes(self):
        self.start_message()
        source = import_fixture.png()
        row = self.announce([self.descriptor(source)])['files'][0]
        self.finish_file(row, source)
        base = self.convert_message()
        project_file = base + '/mail-attachments/' + row['id']
        normal_paths = [self.inquiry_path + '/attachments', self.inquiry_file(row['id']) + '/content',
                        base + '/mail-attachments', project_file + '/content']
        for path in normal_paths:
            self.call('GET', path, token=None, status=401)
            self.call('GET', path, token=self.connector['token'], status=401)
        self.call('GET', '/customers', token=self.connector['token'], status=401)
        self.call('GET', '/inbound/gmail/tokens', token=self.connector['token'], status=401)
        with self.office.lock, self.office.db:
            old_offline = plan_access.issue(self.office, self.owner)['token']
        new_offline = self.call('POST', '/offline/access', {}, status=201).json['token']
        for token in (old_offline, new_offline):
            for path in normal_paths:
                self.call('GET', path, token=token, status=403)
            self.call('POST', project_file + '/plan-import', {'request_id': request_id(), 'page': 0, 'title': 'Forbidden'},
                      token=token, status=403)
            self.call('POST', self.intake, self.attachment_manifest([self.descriptor(source)]), token=token, status=401)
        for token in (None, self.token):
            self.call('POST', self.intake, self.attachment_manifest([self.descriptor(source)]), token=token, status=401)
            self.call('PUT', self.upload_path(row['id']) + '/chunks/0', source, token=token,
                      mime='application/octet-stream', status=401)
            self.call('POST', self.upload_path(row['id']) + '/complete', {}, token=token, status=401)
        # There is no bot download API to discover with the delivery credential.
        self.call('GET', self.upload_path(row['id']) + '/content', token=self.connector['token'], status=404)

    def test_rotated_key_resumes_but_foreign_owner_or_mailbox_keys_cannot_touch_originals(self):
        self.start_message()
        source = import_fixture.png()
        manifest = self.attachment_manifest([self.descriptor(source)])
        row = self.announce(manifest['attachments'])['files'][0]
        rotated = self.call('POST', '/inbound/gmail/tokens', {
            'name': 'Rotated attachment token', 'source_account': self.envelope['source_account'],
        }, status=201).json['token']
        self.assertEqual(self.call('POST', self.intake, manifest, token=rotated, status=201).json['files'][0]['id'], row['id'])
        _, second_owner = self.add_actor('owner', assign=False)
        other = self.call('POST', '/inbound/gmail/tokens', {
            'name': 'Second owner token', 'source_account': self.envelope['source_account'],
        }, token=second_owner, status=201).json['token']
        self.assertEqual(self.call('POST', '/intake/gmail', self.envelope, token=other, status=201).json['id'], self.inquiry)
        self.call('POST', self.intake, manifest, token=other, status=404)
        self.call('PUT', self.upload_path(row['id']) + '/chunks/0', source, token=other,
                  mime='application/octet-stream', status=404)
        wrong = self.call('POST', '/inbound/gmail/tokens', {
            'name': 'Another mailbox', 'source_account': 'other@example.test',
        }, status=201).json['token']
        self.call('POST', self.intake, manifest, token=wrong, status=403)
        self.call('POST', self.upload_path(row['id']) + '/complete', {}, token=wrong, status=404)
        self.call('POST', '/inbound/gmail/tokens/' + self.connector['id'] + '/revoke', {})
        self.call('PUT', self.upload_path(row['id']) + '/chunks/0', source,
                  token=self.connector['token'], mime='application/octet-stream', status=401)
        self.call('PUT', self.upload_path(row['id']) + '/chunks/0', source, token=rotated, mime='application/octet-stream')
        self.call('POST', self.upload_path(row['id']) + '/complete', {}, token=rotated)

    def test_project_accountant_and_unassigned_users_cannot_copy_or_delete_and_role_changes_apply(self):
        self.start_message()
        source = import_fixture.png()
        row = self.announce([self.descriptor(source)])['files'][0]
        self.finish_file(row, source)
        base = self.convert_message()
        project_file = base + '/mail-attachments/' + row['id']
        accountant_id, accountant = self.add_actor('accountant')
        technician_id, technician = self.add_actor('technician')
        _, outsider = self.add_actor('technician', assign=False)
        self.call('GET', project_file + '/content', token=accountant, status=404)
        self.release_original(row['id'])
        self.call('GET', project_file + '/content', token=accountant)
        self.call('POST', project_file + '/plan-import', {'request_id': request_id(), 'page': 0, 'title': 'Forbidden'},
                  token=accountant, status=403)
        self.call('POST', self.inquiry_file(row['id']) + '/delete', {}, token=accountant, status=403)
        self.call('GET', base + '/mail-attachments', token=outsider, status=404)
        other_project = self.call('POST', '/projects', {'name': 'Anderes Projekt', 'customer': 'Synthetischer anderer Kunde'}, status=201).json['id']
        self.call('GET', '/projects/' + other_project + '/mail-attachments/' + row['id'] + '/content', status=404)
        with self.office.db:
            # Keep this session row deliberately: route authorization must see today's role.
            self.office.db.execute("UPDATE users SET role='accountant' WHERE id=?", (technician_id,))
        self.call('GET', project_file + '/content', token=technician)
        self.call('POST', project_file + '/plan-import', {'request_id': request_id(), 'page': 0, 'title': 'Forbidden'},
                  token=technician, status=403)
        self.call('POST', '/users/' + accountant_id, {'active': False})
        self.call('GET', project_file + '/content', token=accountant, status=401)
        with self.office.db:
            self.office.db.execute("UPDATE users SET role='manager' WHERE id=?", (self.owner_id,))
        self.call('POST', self.intake, self.attachment_manifest([self.descriptor(source)]), token=self.connector['token'], status=401)

    def test_binary_upload_json_validation_and_methods_have_bounded_http_failures(self):
        self.start_message()
        source = large_png()
        row = self.announce([self.descriptor(source)])['files'][0]
        chunk = self.upload_path(row['id']) + '/chunks/0'
        self.call('PUT', chunk, source[:CHUNK_SIZE], token=self.connector['token'], mime='application/json', status=415)
        self.call('PUT', chunk, source[:CHUNK_SIZE], token=self.connector['token'], mime='application/octet-stream',
                  headers={'Content-Encoding': 'gzip'}, status=400)
        self.call('PUT', chunk, b'x' * (CHUNK_SIZE + 1), token=self.connector['token'], mime='application/octet-stream', status=413)
        self.call('PUT', chunk, b'x', token=self.connector['token'], mime='application/octet-stream', status=400)
        self.call('PUT', self.upload_path(row['id']) + '/chunks/999', b'x', token=self.connector['token'],
                  mime='application/octet-stream', status=400)
        for raw, mime, status in ((b'[]', 'application/json', 400), (b'{', 'application/json', 400),
                                  (b'plain', 'text/plain', 415)):
            self.call('POST', self.intake, raw, token=self.connector['token'], mime=mime, status=status)
        self.call('POST', self.intake, {'oversized': 'x' * 1_000_000}, token=self.connector['token'], status=413)
        self.call('POST', self.upload_path(row['id']) + '/complete', {'status': 'ready'}, token=self.connector['token'], status=400)
        self.call('POST', self.inquiry_file(row['id']) + '/delete', {'unexpected': True}, status=400)
        for path, allowed in ((self.inquiry_path + '/attachments', 'GET'),
                              (self.inquiry_file(row['id']) + '/content', 'GET'),
                              (self.inquiry_file(row['id']) + '/delete', 'POST')):
            response = self.call('DELETE', path, status=405)
            self.assertEqual(response.headers['Allow'], allowed)
        self.assertEqual(self.app.config['MAX_CONTENT_LENGTH'], 1_000_000)
        summary = self.call('GET', self.inquiry_path + '/attachments').json
        self.assertEqual((summary['status'], summary['ready_count']), ('uploading', 0))

    def test_corrupted_stored_chunk_returns_generic_500_without_download_bytes_or_filename(self):
        self.start_message()
        source = import_fixture.png()
        row = self.announce([self.descriptor(source)])['files'][0]
        self.finish_file(row, source)
        base = self.convert_message()
        with self.office.db:
            self.office.db.execute('UPDATE inquiry_attachment_chunks SET sha256=? WHERE attachment_id=?', ('0' * 64, row['id']))
        for path in (self.inquiry_file(row['id']) + '/content', base + '/mail-attachments/' + row['id'] + '/content'):
            response = self.call('GET', path, status=500)
            self.assertEqual(response.json, {'error': 'Interner Fehler'})
            self.assertEqual(response.mimetype, 'application/json')
            self.assertNotIn('Content-Disposition', response.headers)
            self.assertNotIn(source, response.data)
            self.assertNotIn(row['filename'].encode(), response.data)

    def test_wrong_full_hash_stays_unconfirmed_and_failed_confirmations_are_rate_limited(self):
        self.start_message()
        source = import_fixture.png()
        row = self.announce([self.descriptor(source, sha256='0' * 64)])['files'][0]
        self.call('PUT', self.upload_path(row['id']) + '/chunks/0', source,
                  token=self.connector['token'], mime='application/octet-stream')
        with self.office.db:
            self.office.db.execute('UPDATE inquiry_attachment_limits SET window_count=599')
        self.call('POST', self.upload_path(row['id']) + '/complete', {}, token=self.connector['token'], status=409)
        throttled = self.call('POST', self.upload_path(row['id']) + '/complete', {}, token=self.connector['token'], status=429)
        self.assertEqual(throttled.headers['Retry-After'], '300')
        self.call('GET', self.inquiry_file(row['id']) + '/content', status=409)
        self.assertEqual(self.call('GET', self.inquiry_path + '/attachments').json['ready_count'], 0)


@unittest.skipUnless(pg_fixture.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class PostgresInquiryAttachmentApiTests(AttachmentHttpFlow, unittest.TestCase):
    def setUp(self):
        pg_fixture.OnlineApiTests.setUp(self)
        self.postgres = True
        self.token = self.mfa_login()
        self.owner = self.office.user(self.token)

    def tearDown(self):
        try:
            self.office.db.close()
        finally:
            pg_fixture.reset()

    def test_real_postgres_two_file_mail_project_and_plan_source_survive_reconnect(self):
        self.full_attachment_workflow()


if __name__ == '__main__':
    unittest.main(verbosity=2)
