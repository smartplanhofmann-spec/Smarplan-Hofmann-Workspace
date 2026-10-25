"""Pre-change HTTP contracts for the existing Gmail-to-project workflow.

Only synthetic data and SQLite/Flask fixtures are used. This module deliberately
adds no new product dependency and does not inherit another test class's tests.
"""
import unittest
from unittest.mock import patch
import uuid

import test_inquiry_attachments_api as attachments_fixture
import test_plan_imports as imports_fixture
import test_workspace_api as workspace_fixture
from inquiry_attachments import CHUNK_SIZE


class BusinessIntakeContractTests(attachments_fixture.AttachmentHttpFlow, unittest.TestCase):
    setUp = workspace_fixture.WorkspaceApiTests.setUp
    tearDown = imports_fixture.PlanImportApiTests.tearDown
    open_app = imports_fixture.PlanImportApiTests.open_app

    def count(self, table):
        # Table names come exclusively from fixed strings in this test module.
        return self.office.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]

    def conversion(self, suffix='one'):
        entry = self.call('GET', self.inquiry_path).json
        return {'request_id': uuid.uuid4().hex, 'revision': entry['revision'],
                'project_name': 'Synthetic confirmed project ' + suffix,
                'customer': {'name': 'Synthetic confirmed new customer ' + suffix,
                             'email': self.envelope['sender_email'],
                             'address': 'Synthetic address ' + suffix,
                             'phone': '+49 000 1234567'}}

    def assert_receipt(self, response, identifier=None):
        self.assertEqual(set(response), {'id', 'status', 'ingested_at'})
        self.assertEqual(response['status'], 'received')
        self.assertRegex(response['id'], r'^[a-f0-9]{32}$')
        self.assertTrue(response['ingested_at'])
        if identifier is not None:
            self.assertEqual(response['id'], identifier)

    def project_files(self, project):
        return self.call('GET', '/projects/' + project + '/mail-attachments').json

    def test_old_client_new_confirmed_customer_project_and_originals_survive_lost_ack_and_reopen(self):
        before = {table: self.count(table) for table in ('customers', 'projects')}
        first = self.start_message()
        self.assert_receipt(first)
        self.assertEqual({table: self.count(table) for table in before}, before)
        png, pdf = attachments_fixture.large_png(), attachments_fixture.synthetic_pdf()
        descriptors = [self.descriptor(png), self.descriptor(
            pdf, source_attachment_id='provider/original==two', filename='Synthetic original.pdf',
            media_type='application/pdf')]
        files = self.announce(descriptors)['files']
        for row, content in zip(files, (png, pdf)):
            self.finish_file(row, content)
        manifest = self.attachment_manifest(descriptors)
        completed = self.call('POST', self.intake, manifest, token=self.connector['token'], status=201).json
        self.assertEqual((completed['status'], completed['ready_count']), ('complete', 2))
        body = self.conversion()
        # The first committed result is intentionally ignored by the simulated
        # client; only a later retry is used to continue its workflow.
        committed = self.call('POST', self.inquiry_path + '/convert', body).json
        self.reopen()
        repeated = self.call('POST', self.inquiry_path + '/convert', body).json
        self.assertEqual(repeated, committed)
        self.assertEqual(repeated['inquiry']['status'], 'converted')
        self.assertEqual(repeated['inquiry']['acceptance_channel'], '')
        self.assertEqual(repeated['project']['customer_id'], repeated['inquiry']['customer_id'])
        for table in before:
            self.assertEqual(self.count(table), before[table] + 1)
        project = repeated['project']['id']
        documents = self.project_files(project)
        self.assertEqual([row['id'] for row in documents['files']], [row['id'] for row in files])
        for row, content in zip(documents['files'], (png, pdf)):
            self.assertEqual(row['inquiry_id'], first['id'])
            self.assertEqual(row['sha256'], attachments_fixture.sha(content))
            self.assert_download(self.call('GET', '/projects/' + project + '/mail-attachments/' + row['id'] + '/content'),
                                 content, row['filename'])
        # An old bot retries only its unchanged seven-field body. This neither
        # resets the converted inquiry nor grants it customer/project reads.
        self.assert_receipt(self.call('POST', '/intake/gmail', self.envelope,
                                     token=self.connector['token'], status=201).json, first['id'])
        current = self.call('GET', self.inquiry_path).json
        self.assertEqual((current['status'], current['project_id'], current['customer_id']),
                         ('converted', project, repeated['inquiry']['customer_id']))
        self.assertEqual(current['revision'], repeated['inquiry']['revision'])
        self.assertEqual(self.call('POST', self.intake, manifest, token=self.connector['token'], status=201).json, completed)
        self.call('POST', self.inquiry_path + '/convert', {**body, 'request_id': uuid.uuid4().hex}, status=409)
        self.call('GET', '/customers', token=self.connector['token'], status=401)
        self.call('GET', self.inquiry_path, token=self.connector['token'], status=401)

    def test_project_can_be_created_before_manifest_and_later_originals_keep_the_same_link(self):
        first = self.start_message(source_id='synthetic-before-manifest')
        converted = self.call('POST', self.inquiry_path + '/convert', self.conversion('unannounced')).json
        project = converted['project']['id']
        pending = self.project_files(project)
        self.assertEqual((pending['expected_count'], pending['unannounced_count']), (None, 1))
        self.assertEqual(pending['files'], [])
        self.reopen()
        original = attachments_fixture.synthetic_pdf()
        row = self.announce([self.descriptor(original, media_type='application/pdf', filename='Late original.pdf')])['files'][0]
        self.finish_file(row, original)
        ready = self.project_files(project)
        self.assertEqual((ready['status'], ready['ready_count'], ready['unannounced_count']), ('complete', 1, 0))
        self.assertEqual((ready['files'][0]['id'], ready['files'][0]['inquiry_id']), (row['id'], first['id']))
        self.assert_download(self.call('GET', '/projects/' + project + '/mail-attachments/' + row['id'] + '/content'),
                             original, row['filename'])
        self.assertEqual(self.call('GET', self.inquiry_path).json['acceptance_channel'], '')

    def test_project_with_partial_upload_resumes_after_rotation_without_new_business_records(self):
        self.start_message(source_id='synthetic-during-upload')
        original = attachments_fixture.large_png()
        self.assertGreater(len(original), CHUNK_SIZE)
        descriptor = self.descriptor(original)
        row = self.announce([descriptor])['files'][0]
        self.call('PUT', self.upload_path(row['id']) + '/chunks/1', original[CHUNK_SIZE:],
                  token=self.connector['token'], mime='application/octet-stream')
        converted = self.call('POST', self.inquiry_path + '/convert', self.conversion('partial')).json
        project = converted['project']['id']
        pending = self.project_files(project)
        self.assertEqual((pending['status'], pending['pending_count'], pending['ready_count']), ('uploading', 1, 0))
        self.call('GET', '/projects/' + project + '/mail-attachments/' + row['id'] + '/content', status=409)
        before = {table: self.count(table) for table in ('inquiries', 'customers', 'projects', 'inquiry_attachments')}
        self.reopen()
        self.connector = self.issue_gmail()
        resumed = self.announce([descriptor])['files'][0]
        self.assertEqual((resumed['id'], resumed['received_chunks']), (row['id'], [1]))
        self.call('PUT', self.upload_path(row['id']) + '/chunks/0', original[:CHUNK_SIZE],
                  token=self.connector['token'], mime='application/octet-stream')
        self.call('POST', self.upload_path(row['id']) + '/complete', {}, token=self.connector['token'])
        self.assertEqual({table: self.count(table) for table in before}, before)
        ready = self.project_files(project)
        self.assertEqual((ready['status'], ready['ready_count'], ready['pending_count']), ('complete', 1, 0))
        self.assert_download(self.call('GET', '/projects/' + project + '/mail-attachments/' + row['id'] + '/content'),
                             original, row['filename'])

    def test_late_http_conversion_failure_rolls_back_new_customer_project_and_preserves_originals(self):
        self.start_message()
        original = attachments_fixture.synthetic_pdf()
        row = self.announce([self.descriptor(original, filename='Kept original.pdf', media_type='application/pdf')])['files'][0]
        self.finish_file(row, original)
        tables = ('customers', 'projects', 'inquiries', 'inquiry_requests', 'audit',
                  'inquiry_attachment_sets', 'inquiry_attachments', 'inquiry_attachment_chunks')
        before = {table: self.count(table) for table in tables}
        inquiry_before = self.call('GET', self.inquiry_path).json
        body = self.conversion('rollback')
        audit = self.office.audit

        def fail_after_all_business_writes(actor, action, identifier):
            if action == 'inquiry.converted':
                raise RuntimeError('SYNTHETIC PRIVATE FAILURE must not be reflected')
            return audit(actor, action, identifier)

        with patch.object(self.office, 'audit', side_effect=fail_after_all_business_writes):
            failed = self.call('POST', self.inquiry_path + '/convert', body, status=500)
        self.assertEqual(failed.json, {'error': 'Interner Fehler'})
        self.assertEqual({table: self.count(table) for table in tables}, before)
        self.assertEqual(self.call('GET', self.inquiry_path).json, inquiry_before)
        self.assert_download(self.call('GET', self.inquiry_file(row['id']) + '/content'), original, row['filename'])
        self.reopen()
        retry = self.call('POST', self.inquiry_path + '/convert', body).json
        self.assertEqual(retry['inquiry']['status'], 'converted')
        self.assertEqual(self.count('customers'), before['customers'] + 1)
        self.assertEqual(self.count('projects'), before['projects'] + 1)

    def test_legacy_manifest_meanings_and_credentials_remain_distinct(self):
        self.start_message()
        absent = self.call('GET', self.inquiry_path).json['attachments']
        self.assertEqual((absent['status'], absent['expected_count']), ('not_announced', None))
        empty = self.announce([])
        self.assertEqual((empty['status'], empty['expected_count'], empty['ready_count'], empty['files']),
                         ('complete', 0, 0, []))
        self.assertEqual(self.announce([]), empty)
        self.call('POST', self.intake, self.attachment_manifest([self.descriptor(b'synthetic')]),
                  token=self.connector['token'], status=409)
        self.call('POST', self.intake, self.attachment_manifest([]), token=self.token, status=401)
        self.call('POST', '/intake/gmail', self.envelope, token=self.token, status=401)
        self.call('POST', '/intake/gmail', {**self.envelope, 'customer_id': uuid.uuid4().hex},
                  token=self.connector['token'], status=400)
        for role in ('manager', 'technician', 'accountant'):
            _, token = self.add_actor(role, assign=False)
            self.call('GET', self.inquiry_path, token=token, status=403)
            self.call('GET', self.inquiry_path + '/attachments', token=token, status=403)
            self.call('POST', self.inquiry_path + '/convert', self.conversion(role), token=token, status=403)
        self.assert_receipt(self.call('POST', '/intake/gmail', self.envelope,
                                     token=self.connector['token'], status=201).json, self.inquiry)


if __name__ == '__main__':
    unittest.main(verbosity=2)
