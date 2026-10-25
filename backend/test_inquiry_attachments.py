"""Real SQLite attachment state, permissions and atomic copies; synthetic only."""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import uuid

from core import Office, Problem
from inbound_connectors import InboundConnectors
from inquiries import Inquiries
import inquiry_attachments as domain
from inquiry_attachments import InquiryAttachments, CHUNK_SIZE, ensure_sqlite_schema, validate_integrity


PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6'
                       'N2sAAAAASUVORK5CYII=')


def sha(data):
    return hashlib.sha256(data).hexdigest()


class InquiryAttachmentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='smartplan-inquiry-attachments-')
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / 'office.db'
        self.office = Office(self.path)
        self.addCleanup(self.office.db.close)
        ensure_sqlite_schema(self.office)
        self.now = [2000.0]
        uid = self.office.add_user('owner@example.test', 'Synthetic-owner-password-123', 'owner')
        self.owner = dict(id=uid, email='owner@example.test', role='owner')
        self.inbound = InboundConnectors(self.office, clock=lambda: self.now[0])
        self.grant = self.inbound.issue(self.owner, {'name': 'Synthetic attachment uploader', 'source_account': 'office@example.test'})
        self.token = self.grant['token']
        self.source_id = 'synthetic-message-17'
        self.inquiry = self.body(self.source_id)
        self.api = InquiryAttachments(self.office, clock=lambda: self.now[0])

    def body(self, source_id, *, token=None):
        return self.inbound.receive_gmail(token or self.token, {
            'source_account': 'office@example.test', 'source_id': source_id,
            'subject': 'Synthetische Anfrage zum Aufmaß', 'message': 'Nur synthetische Testdaten.',
            'sender_email': 'synthetic-customer@example.test', 'received_at': '2026-10-24T09:00:00+02:00',
        })['id']

    def descriptor(self, content=PNG, **changes):
        return {'source_attachment_id': 'opaque/provider/Attachment==17', 'filename': 'Aufmaß.png',
                'media_type': 'image/png', 'size': len(content), 'sha256': sha(content), **changes}

    def manifest(self, files=None, **changes):
        return {'source_account': 'office@example.test', 'source_id': self.source_id,
                'attachments': files if files is not None else [self.descriptor()], **changes}

    def upload(self, content=PNG, **changes):
        announced = self.api.announce(self.token, self.manifest([self.descriptor(content, **changes)]))
        identifier = announced['files'][0]['id']
        for index, start in enumerate(range(0, len(content), CHUNK_SIZE)):
            self.api.put_chunk(self.token, identifier, index, content[start:start + CHUNK_SIZE])
        return self.api.complete(self.token, identifier)

    def actor(self, role, *, project=None):
        email = role + '-' + uuid.uuid4().hex[:8] + '@example.test'
        uid = self.office.add_user(email, 'Synthetic-member-password-123', role)
        actor = dict(id=uid, email=email, role=role)
        if project is not None:
            self.office.assign(self.owner, project, uid)
        return actor

    def convert(self, inquiry=None):
        current = Inquiries(self.office).get(self.owner, inquiry or self.inquiry)
        return Inquiries(self.office).convert(self.owner, current['id'], {
            'request_id': uuid.uuid4().hex, 'revision': current['revision'],
            'project_name': 'Synthetische Erstklärung',
            'customer': {'name': 'Synthetischer Kunde ' + uuid.uuid4().hex[:8]},
        })['project']['id']

    def problem(self, status, action):
        with self.assertRaises(Problem) as caught:
            action()
        self.assertEqual(caught.exception.status, status, caught.exception.message)
        return caught.exception

    def release_operational(self, project, identifier):
        from business_foundation import BusinessFoundation
        service = BusinessFoundation(self.office)
        current = service.classification(self.owner, project, 'mail', identifier)
        return service.classify(self.owner, project, 'mail', identifier, {
            'request_id': uuid.uuid4().hex, 'revision': current['revision'],
            'expected_source_fingerprint': current['source_fingerprint'], 'classification': 'operational'})

    def test_explicit_empty_manifest_differs_from_not_announced_and_never_becomes_editable(self):
        before = self.api.for_inquiry(self.owner, self.inquiry)
        self.assertEqual((before['status'], before['expected_count'], before['files']), ('not_announced', None, []))
        announced = self.api.announce(self.token, self.manifest([]))
        self.assertEqual((announced['status'], announced['expected_count'], announced['total_bytes']), ('complete', 0, 0))
        self.assertEqual(announced['chunk_size'], CHUNK_SIZE)
        self.assertEqual(self.api.announce(self.token, self.manifest([])), announced)
        self.assertEqual(self.api.summary(self.inquiry)['expected_count'], 0)
        self.problem(409, lambda: self.api.announce(self.token, self.manifest()))
        self.assertTrue(validate_integrity(self.office))

    def test_manifest_order_is_irrelevant_source_ids_are_opaque_and_original_metadata_is_immutable(self):
        files = [self.descriptor(source_attachment_id='Opaque ID==/A'),
                 self.descriptor(source_attachment_id='opaque id==/a', filename='Zweite Datei.png')]
        first = self.api.announce(self.token, self.manifest(files))
        second = self.api.announce(self.token, self.manifest(list(reversed(files))))
        self.assertEqual(second, first)
        self.assertEqual({row['source_attachment_id'] for row in first['files']}, {row['source_attachment_id'] for row in files})
        for field, value in (('filename', 'Anderer Name.png'), ('size', 1), ('sha256', '0' * 64),
                             ('media_type', 'application/pdf'), ('source_attachment_id', 'new-id')):
            changed = [{**files[0], field: value}, files[1]]
            self.problem(409, lambda: self.api.announce(self.token, self.manifest(changed)))
        self.assertEqual(self.office.db.execute("SELECT COUNT(*) FROM audit WHERE action='inquiry_attachments.announced'").fetchone()[0], 1)

    def test_chunks_resume_out_of_order_and_complete_is_idempotent_across_database_reopen(self):
        content = b'Synthetic original:' + b'z' * (CHUNK_SIZE + 31)
        manifest = self.manifest([self.descriptor(content, media_type='application/octet-stream')])
        identifier = self.api.announce(self.token, manifest)['files'][0]['id']
        self.api.put_chunk(self.token, identifier, 1, content[CHUNK_SIZE:])
        self.problem(409, lambda: self.api.complete(self.token, identifier))
        self.problem(409, lambda: self.api.content_inquiry(self.owner, self.inquiry, identifier))
        self.assertTrue(validate_integrity(self.office))
        second = Office(self.path)
        self.addCleanup(second.db.close)
        ensure_sqlite_schema(second)
        resumed_api = InquiryAttachments(second, clock=lambda: self.now[0])
        resumed = resumed_api.announce(self.token, manifest)
        self.assertEqual(resumed['files'][0]['id'], identifier)
        self.assertEqual(resumed['files'][0]['received_chunks'], [1])
        resumed_api.put_chunk(self.token, identifier, 0, content[:CHUNK_SIZE])
        ready = resumed_api.complete(self.token, identifier)
        self.assertEqual(ready['status'], 'ready')
        self.assertEqual(resumed_api.complete(self.token, identifier), ready)
        self.assertEqual(resumed_api.put_chunk(self.token, identifier, 0, content[:CHUNK_SIZE]), ready)
        self.assertEqual(self.api.content_inquiry(self.owner, self.inquiry, identifier)[0], content)
        self.assertNotIn('received_chunks', self.api.for_inquiry(self.owner, self.inquiry)['files'][0])
        self.assertEqual(self.office.db.execute("SELECT COUNT(*) FROM audit WHERE action='inquiry_attachment.ready'").fetchone()[0], 1)

    def test_chunk_lengths_indices_and_complete_original_hash_are_enforced(self):
        content = b'x' * CHUNK_SIZE + b'tail'
        identifier = self.api.announce(self.token, self.manifest([self.descriptor(content, sha256='0' * 64)]))['files'][0]['id']
        for index, data, status in ((True, content[:CHUNK_SIZE], 400), (-1, b'x', 400), (2, b'x', 400),
                                    (0, b'x', 400), (1, b'x' * 5, 400), (0, b'x' * (CHUNK_SIZE + 1), 413),
                                    (0, bytearray(content[:CHUNK_SIZE]), 400)):
            self.problem(status, lambda: self.api.put_chunk(self.token, identifier, index, data))
        self.api.put_chunk(self.token, identifier, 0, content[:CHUNK_SIZE])
        self.problem(409, lambda: self.api.put_chunk(self.token, identifier, 0, b'y' * CHUNK_SIZE))
        self.api.put_chunk(self.token, identifier, 1, content[CHUNK_SIZE:])
        self.problem(409, lambda: self.api.complete(self.token, identifier))
        self.assertEqual(self.api.for_inquiry(self.owner, self.inquiry)['files'][0]['status'], 'uploading')
        self.assertTrue(validate_integrity(self.office))

    def test_invalid_manifest_values_are_rejected_without_reserving_bytes(self):
        for field, values in (
                ('filename', ('', ' ', '.', '..', '../Plan.pdf', 'dir\\Plan.pdf', 'line\r\ninjection', 'nul\x00.png', 'a' * 201)),
                ('source_attachment_id', ('', 'tab\tid', 'line\nid', '\ud800', 'a' * 2049)),
                ('media_type', ('image', 'image/png; charset=utf-8', 'image/ p', 'image/\n', 'x' * 101)),
                ('size', (0, -1, True, 1.5, '10')),
                ('sha256', ('0' * 63, 'G' * 64, None))):
            for value in values:
                with self.subTest(field=field, value=repr(value)):
                    self.problem(400, lambda: self.api.announce(self.token, self.manifest([{**self.descriptor(), field: value}])))
        for data in ({**self.manifest(), 'customer_id': 'a' * 32}, self.manifest(attachments=None),
                     self.manifest(source_id='<mail@example.test>'), self.manifest(source_account='invalid')):
            self.problem(400, lambda: self.api.announce(self.token, data))
        self.problem(400, lambda: self.api.announce(self.token, self.manifest([self.descriptor(), self.descriptor()])))
        self.problem(413, lambda: self.api.announce(self.token, self.manifest([self.descriptor(size=domain.MAX_FILE_BYTES + 1)])))
        self.problem(413, lambda: self.api.announce(self.token, self.manifest([
            self.descriptor(source_attachment_id=str(index)) for index in range(31)])))
        self.problem(413, lambda: self.api.announce(self.token, self.manifest([
            self.descriptor(source_attachment_id=str(index), size=domain.MAX_FILE_BYTES) for index in range(4)])))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiry_attachment_sets').fetchone()[0], 0)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiry_attachment_limits').fetchone()[0], 0)

    def test_token_rotation_resumes_but_wrong_account_owner_scope_or_body_cannot_write(self):
        self.problem(404, lambda: self.api.announce(self.token, self.manifest(source_id='missing-body')))
        first = self.api.announce(self.token, self.manifest())
        rotated = self.inbound.issue(self.owner, {'name': 'Rotated', 'source_account': 'office@example.test'})['token']
        self.assertEqual(self.api.announce(rotated, self.manifest()), first)
        other = self.actor('owner')
        other_token = self.inbound.issue(other, {'name': 'Other owner', 'source_account': 'office@example.test'})['token']
        # Body deduplication across owners does not transfer upload ownership.
        self.assertEqual(self.body(self.source_id, token=other_token), self.inquiry)
        self.problem(404, lambda: self.api.announce(other_token, self.manifest()))
        self.problem(404, lambda: self.api.put_chunk(other_token, first['files'][0]['id'], 0, PNG))
        wrong = self.inbound.issue(self.owner, {'name': 'Wrong mailbox', 'source_account': 'other@example.test'})['token']
        self.problem(403, lambda: self.api.announce(wrong, self.manifest()))
        self.problem(404, lambda: self.api.complete(wrong, first['files'][0]['id']))
        self.problem(401, lambda: self.api.for_inquiry(self.token, self.inquiry))
        self.problem(401, lambda: self.office.user(self.token))

    def test_upload_credentials_recheck_expiry_revocation_and_current_owner_role(self):
        identifier = self.api.announce(self.token, self.manifest())['files'][0]['id']
        self.now[0] += 90 * 86400
        self.problem(401, lambda: self.api.put_chunk(self.token, identifier, 0, PNG))
        self.now[0] = 2000.0
        self.inbound.revoke(self.owner, self.grant['id'])
        self.problem(401, lambda: self.api.complete(self.token, identifier))
        active = self.inbound.issue(self.owner, {'name': 'Active', 'source_account': 'office@example.test'})['token']
        with self.office.db:
            self.office.db.execute("UPDATE users SET role='technician' WHERE id=?", (self.owner['id'],))
        self.problem(401, lambda: self.api.put_chunk(active, identifier, 0, PNG))
        with self.office.db:
            self.office.db.execute("UPDATE users SET role='owner',active=0 WHERE id=?", (self.owner['id'],))
        self.problem(401, lambda: self.api.announce(active, self.manifest()))

    def test_upload_rate_is_separate_from_body_rate_persists_and_resets_without_reupload(self):
        identifier = self.api.announce(self.token, self.manifest())['files'][0]['id']
        with self.office.db:
            self.office.db.execute('UPDATE inquiry_attachment_limits SET window_count=599')
        self.api.put_chunk(self.token, identifier, 0, PNG)
        self.problem(429, lambda: self.api.complete(self.token, identifier))
        self.assertEqual(self.office.db.execute('SELECT window_count FROM inbound_import_tokens').fetchone()[0], 1)
        self.now[0] += 60
        self.assertEqual(self.api.complete(self.token, identifier)['status'], 'ready')
        self.assertEqual(self.office.db.execute('SELECT window_count FROM inquiry_attachment_limits').fetchone()[0], 1)

    def test_failed_full_hash_confirmation_consumes_rate_without_marking_ready(self):
        row = self.api.announce(self.token, self.manifest([self.descriptor(sha256='0' * 64)]))['files'][0]
        self.api.put_chunk(self.token, row['id'], 0, PNG)
        with self.office.db:
            self.office.db.execute('UPDATE inquiry_attachment_limits SET window_count=599')
        self.problem(409, lambda: self.api.complete(self.token, row['id']))
        self.assertEqual(self.office.db.execute('SELECT window_count FROM inquiry_attachment_limits').fetchone()[0], 600)
        self.problem(429, lambda: self.api.complete(self.token, row['id']))
        self.assertEqual(self.api.summary(self.inquiry)['files'][0]['status'], 'uploading')

    def test_unknown_file_attempts_count_to_600_but_invalid_keys_never_get_a_counter(self):
        unknown = 'f' * 32
        invalid = 'SPIN_' + 'X' * 43
        self.problem(401, lambda: self.api.complete(invalid, unknown))
        self.problem(401, lambda: self.api.put_chunk(invalid, unknown, 0, PNG))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiry_attachment_limits').fetchone()[0], 0)
        for index in range(domain.MAX_UPLOAD_OPS_PER_MINUTE):
            if index % 2:
                self.problem(404, lambda: self.api.complete(self.token, unknown))
            else:
                self.problem(404, lambda: self.api.put_chunk(self.token, unknown, 0, PNG))
        self.assertEqual(self.office.db.execute('SELECT window_count FROM inquiry_attachment_limits').fetchone()[0], 600)
        self.problem(429, lambda: self.api.complete(self.token, unknown))
        self.problem(429, lambda: self.api.put_chunk(self.token, unknown, 0, PNG))
        self.problem(401, lambda: self.api.complete(invalid, unknown))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiry_attachment_limits').fetchone()[0], 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiry_attachments').fetchone()[0], 0)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiry_attachment_chunks').fetchone()[0], 0)

    def test_own_deleted_file_attempts_consume_rate_and_never_restore_bytes(self):
        row = self.upload()
        self.api.remove_inquiry(self.owner, self.inquiry, row['id'])
        before = self.office.db.execute('SELECT window_count FROM inquiry_attachment_limits').fetchone()[0]
        self.problem(410, lambda: self.api.complete(self.token, row['id']))
        self.problem(410, lambda: self.api.put_chunk(self.token, row['id'], 0, PNG))
        self.assertEqual(self.office.db.execute('SELECT window_count FROM inquiry_attachment_limits').fetchone()[0], before + 2)
        with self.office.db:
            self.office.db.execute('UPDATE inquiry_attachment_limits SET window_count=599')
        self.problem(410, lambda: self.api.complete(self.token, row['id']))
        self.problem(429, lambda: self.api.put_chunk(self.token, row['id'], 0, PNG))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiry_attachment_chunks').fetchone()[0], 0)
        self.assertEqual(self.api.summary(self.inquiry)['deleted_count'], 1)

    def test_foreign_file_attempts_consume_only_the_authenticated_callers_rate(self):
        row = self.upload()
        other = self.actor('owner')
        grant = self.inbound.issue(other, {'name': 'Foreign scoped uploader', 'source_account': 'office@example.test'})
        self.problem(404, lambda: self.api.complete(grant['token'], row['id']))
        self.problem(404, lambda: self.api.put_chunk(grant['token'], row['id'], 0, PNG))
        self.assertEqual(self.office.db.execute('SELECT window_count FROM inquiry_attachment_limits WHERE token_id=?',
                                               (grant['id'],)).fetchone()[0], 2)
        self.assertEqual(self.office.db.execute('SELECT window_count FROM inquiry_attachment_limits WHERE token_id=?',
                                               (self.grant['id'],)).fetchone()[0], 3)
        with self.office.db:
            self.office.db.execute('UPDATE inquiry_attachment_limits SET window_count=599 WHERE token_id=?', (grant['id'],))
        self.problem(404, lambda: self.api.put_chunk(grant['token'], row['id'], 0, PNG))
        self.problem(429, lambda: self.api.complete(grant['token'], row['id']))
        self.assertEqual(self.api.content_inquiry(self.owner, self.inquiry, row['id'])[0], PNG)

    def test_reserved_quota_counts_uploading_files_and_deletion_releases_it_without_manifest_mutation(self):
        second_id = self.body('synthetic-message-18')
        del second_id
        manifest = self.manifest([self.descriptor(b'12345678')])
        with patch.object(domain, 'MAX_RESERVED_BYTES', 12):
            identifier = self.api.announce(self.token, manifest)['files'][0]['id']
            self.problem(413, lambda: self.api.announce(self.token, self.manifest(
                [self.descriptor(b'87654321')], source_id='synthetic-message-18')))
            before = dict(self.office.db.execute('SELECT * FROM inquiry_attachment_sets').fetchone())
            self.api.remove_inquiry(self.owner, self.inquiry, identifier)
            self.api.announce(self.token, self.manifest([self.descriptor(b'87654321')], source_id='synthetic-message-18'))
            after = dict(self.office.db.execute('SELECT * FROM inquiry_attachment_sets WHERE inquiry_id=?', (self.inquiry,)).fetchone())
            self.assertEqual(after, before)
            self.assertTrue(validate_integrity(self.office))

    def test_concurrent_connections_cannot_reserve_beyond_quota_or_duplicate_the_same_manifest(self):
        self.body('synthetic-message-18')
        other = Office(self.path)
        self.addCleanup(other.db.close)
        ensure_sqlite_schema(other)
        second_api = InquiryAttachments(other, clock=lambda: self.now[0])
        barrier = threading.Barrier(2)

        def announce(args):
            api, source = args
            barrier.wait(timeout=5)
            try:
                return api.announce(self.token, self.manifest([self.descriptor(b'12345678')], source_id=source))
            except Problem as error:
                return error.status

        with patch.object(domain, 'MAX_RESERVED_BYTES', 12), ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(announce, [(self.api, self.source_id), (second_api, 'synthetic-message-18')]))
        self.assertEqual(sum(isinstance(result, dict) for result in results), 1)
        self.assertIn(413, results)
        winner = self.source_id if isinstance(results[0], dict) else 'synthetic-message-18'
        with ThreadPoolExecutor(max_workers=2) as workers:
            retries = list(workers.map(announce, [(self.api, winner), (second_api, winner)]))
        self.assertEqual(retries[0], retries[1])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiry_attachments').fetchone()[0], 1)

    def test_delete_purges_bytes_once_and_delayed_uploads_never_revive_original(self):
        ready = self.upload()
        request = self.manifest()
        first = self.api.remove_inquiry(self.owner, self.inquiry, ready['id'])
        self.assertEqual(self.api.remove_inquiry(self.owner, self.inquiry, ready['id']), first)
        resumed = self.api.announce(self.token, request)
        self.assertEqual((resumed['status'], resumed['deleted_count'], resumed['files'][0]['status']), ('complete', 1, 'deleted'))
        self.assertEqual(resumed['files'][0]['received_chunks'], [])
        self.assertEqual(self.api.for_inquiry(self.owner, self.inquiry)['files'], [])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiry_attachment_chunks').fetchone()[0], 0)
        self.problem(410, lambda: self.api.put_chunk(self.token, ready['id'], 0, PNG))
        self.problem(410, lambda: self.api.complete(self.token, ready['id']))
        self.problem(410, lambda: self.api.content_inquiry(self.owner, self.inquiry, ready['id']))
        self.assertEqual(self.office.db.execute("SELECT COUNT(*) FROM audit WHERE action='inquiry_attachment.deleted'").fetchone()[0], 1)
        self.assertTrue(validate_integrity(self.office))

    def test_inbox_is_owner_only_project_files_require_converted_link_and_fresh_assigned_role(self):
        ready = self.upload()
        project = self.convert()
        unrelated = self.office.add_project(self.owner, 'Anderes Projekt', 'Anderer synthetischer Kunde')
        actors = [self.actor(role, project=project) for role in ('manager', 'technician', 'accountant')]
        for actor in actors:
            self.problem(403, lambda: self.api.for_inquiry(actor, self.inquiry))
            self.problem(403, lambda: self.api.remove_inquiry(actor, self.inquiry, ready['id']))
            self.problem(404, lambda: self.api.content_project(actor, project, ready['id']))
            self.assertEqual(self.api.for_project(actor, project)['files'], [])
        self.release_operational(project, ready['id'])
        for actor in actors:
            self.assertEqual(self.api.content_project(actor, project, ready['id'])[0], PNG)
            self.assertEqual(self.api.for_project(actor, project)['ready_count'], 1)
            self.problem(404, lambda: self.api.content_project(actor, unrelated, ready['id']))
            self.office.assign(self.owner, project, actor['id'], remove=True)
            self.problem(404, lambda: self.api.content_project(actor, project, ready['id']))
        self.problem(404, lambda: self.api.content_project(self.owner, unrelated, ready['id']))
        stale_owner = dict(self.owner)
        with self.office.db:
            self.office.db.execute("UPDATE users SET role='technician' WHERE id=?", (self.owner['id'],))
        self.problem(404, lambda: self.api.for_project(stale_owner, project))
        with self.office.db:
            self.office.db.execute('UPDATE users SET active=0 WHERE id=?', (self.owner['id'],))
        self.problem(401, lambda: self.api.for_project(stale_owner, project))

    def test_project_aggregation_tracks_partial_and_undeclared_messages_without_guessing_none(self):
        ready = self.upload()
        project = self.convert()
        unknown_id = self.body('synthetic-message-18')
        self.convert(unknown_id)
        with self.office.db:
            self.office.db.execute('UPDATE inquiries SET project_id=? WHERE id=?', (project, unknown_id))
        current = self.api.for_project(self.owner, project)
        self.assertEqual((current['expected_count'], current['unannounced_count'], current['ready_count']), (None, 1, 1))
        self.assertEqual(current['files'][0]['inquiry_id'], self.inquiry)
        self.assertIn('subject', current['files'][0])
        partial = self.api.announce(self.token, self.manifest(source_id='synthetic-message-18'))['files'][0]
        current = self.api.for_project(self.owner, project)
        self.assertEqual((current['expected_count'], current['unannounced_count'], current['pending_count']), (2, 0, 1))
        self.assertEqual(current['status'], 'uploading')
        self.api.remove_inquiry(self.owner, unknown_id, partial['id'])
        current = self.api.for_project(self.owner, project)
        self.assertEqual((current['status'], current['ready_count'], current['deleted_count']), ('complete', 1, 1))
        self.assertEqual([row['id'] for row in current['files']], [ready['id']])

    def test_late_announce_complete_and_delete_failures_rollback_rows_quota_and_audit(self):
        original = self.office.audit

        def fail(action):
            def audit(actor, event, identifier):
                if event == action:
                    raise RuntimeError('Synthetic late failure')
                return original(actor, event, identifier)
            return audit

        with patch.object(self.office, 'audit', side_effect=fail('inquiry_attachments.announced')):
            with self.assertRaises(RuntimeError):
                self.api.announce(self.token, self.manifest())
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiry_attachment_sets').fetchone()[0], 0)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiry_attachment_limits').fetchone()[0], 0)
        identifier = self.api.announce(self.token, self.manifest())['files'][0]['id']
        self.api.put_chunk(self.token, identifier, 0, PNG)
        with patch.object(self.office, 'audit', side_effect=fail('inquiry_attachment.ready')):
            with self.assertRaises(RuntimeError):
                self.api.complete(self.token, identifier)
        self.assertEqual(self.api.summary(self.inquiry)['files'][0]['status'], 'uploading')
        self.api.complete(self.token, identifier)
        with patch.object(self.office, 'audit', side_effect=fail('inquiry_attachment.deleted')):
            with self.assertRaises(RuntimeError):
                self.api.remove_inquiry(self.owner, self.inquiry, identifier)
        self.assertEqual(self.api.content_inquiry(self.owner, self.inquiry, identifier)[0], PNG)
        self.assertTrue(validate_integrity(self.office))

    def test_nested_operation_preserves_caller_transaction_until_its_rollback(self):
        self.office.db.execute('BEGIN')
        self.api.announce(self.token, self.manifest())
        self.assertTrue(self.office.db.in_transaction)
        self.office.db.rollback()
        self.assertEqual(self.api.summary(self.inquiry)['status'], 'not_announced')
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM inquiry_attachment_limits').fetchone()[0], 0)

    def test_copy_is_real_atomic_idempotent_plan_source_and_attachment_deletion_does_not_delete_plan(self):
        from online.plan_imports import PlanImports, ensure_sqlite_schema as ensure_imports
        ensure_imports(self.office)
        ready = self.upload()
        project = self.convert()
        actor = self.actor('technician', project=project)
        request = dict(request_id=uuid.uuid4().hex, page=0, title='Plan aus Originalanhang')
        self.problem(404, lambda: self.api.copy_to_plan(actor, project, ready['id'], request))
        self.release_operational(project, ready['id'])
        first = self.api.copy_to_plan(actor, project, ready['id'], request)
        self.assertEqual(first['status'], 'queued')
        self.assertEqual(self.api.copy_to_plan(actor, project, ready['id'], request), first)
        self.assertEqual(PlanImports(self.office).source(actor, project, first['id'])[0], PNG)
        self.assertEqual(self.api.content_project(actor, project, ready['id'])[0], PNG)
        self.problem(409, lambda: self.api.copy_to_plan(actor, project, ready['id'], {**request, 'title': 'Changed'}))
        accountant = self.actor('accountant', project=project)
        self.problem(403, lambda: self.api.copy_to_plan(accountant, project, ready['id'], request))
        self.api.remove_inquiry(self.owner, self.inquiry, ready['id'])
        self.assertEqual(PlanImports(self.office).source(actor, project, first['id'])[0], PNG)
        # Project readers receive no existence/tombstone detail for an original
        # that is no longer released. Owner inbox and bot tombstones stay410.
        self.problem(404, lambda: self.api.copy_to_plan(actor, project, ready['id'], request))
        self.assertTrue(validate_integrity(self.office))

    def test_copy_request_is_bound_to_attachment_even_when_two_originals_are_identical(self):
        from online.plan_imports import PlanImports, ensure_sqlite_schema as ensure_imports
        ensure_imports(self.office)
        files = [self.descriptor(source_attachment_id=str(index)) for index in range(2)]
        announced = self.api.announce(self.token, self.manifest(files))
        for row in announced['files']:
            self.api.put_chunk(self.token, row['id'], 0, PNG)
            self.api.complete(self.token, row['id'])
        project = self.convert()
        request = dict(request_id=uuid.uuid4().hex, page=0, title='Originalplan')
        first, second = announced['files']
        job = self.api.copy_to_plan(self.owner, project, first['id'], request)
        self.problem(409, lambda: self.api.copy_to_plan(self.owner, project, second['id'], request))
        with self.office.lock, self.office.db:
            PlanImports(self.office).delete(self.owner, project, {'request_id': uuid.uuid4().hex, 'id': job['id']})
        self.problem(410, lambda: self.api.copy_to_plan(self.owner, project, first['id'], request))
        self.assertEqual(self.api.content_project(self.owner, project, first['id'])[0], PNG)

    def test_copy_fails_cleanly_without_online_package_and_never_partially_queues_on_failure(self):
        ready = self.upload()
        project = self.convert()
        request = dict(request_id=uuid.uuid4().hex, page=0, title='Plan')
        with patch.dict(sys.modules, {'online.plan_imports': None}):
            self.problem(409, lambda: self.api.copy_to_plan(self.owner, project, ready['id'], request))
        from online.plan_imports import ensure_sqlite_schema as ensure_imports
        ensure_imports(self.office)
        original = self.office.audit

        def interrupt(actor, action, identifier):
            if action == 'inquiry_attachment.plan_copied':
                raise RuntimeError('Synthetic failure after complete plan source')
            return original(actor, action, identifier)

        with patch.object(self.office, 'audit', side_effect=interrupt):
            with self.assertRaises(RuntimeError):
                self.api.copy_to_plan(self.owner, project, ready['id'], request)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM plan_imports').fetchone()[0], 0)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM plan_import_chunks').fetchone()[0], 0)
        self.assertEqual(self.api.content_project(self.owner, project, ready['id'])[0], PNG)

    def test_integrity_rejects_modified_manifest_or_partial_chunks_and_ready_hashes(self):
        content = b'a' * CHUNK_SIZE + b'tail'
        row = self.upload(content)
        mutations = [
            ('UPDATE inquiry_attachment_sets SET manifest_hash=?', ('0' * 64,)),
            ('UPDATE inquiry_attachment_sets SET expected_count=2', ()),
            ('UPDATE inquiry_attachment_sets SET created_at=?', (float('inf'),)),
            ('UPDATE inquiry_attachment_chunks SET data=? WHERE chunk_index=1', (b'fake',)),
            ('UPDATE inquiry_attachment_chunks SET chunk_index=2 WHERE chunk_index=1', ()),
            ('DELETE FROM inquiry_attachment_chunks WHERE chunk_index=1', ()),
        ]
        for query, values in mutations:
            with self.subTest(query=query):
                self.office.db.execute('BEGIN')
                self.office.db.execute(query, values)
                with self.assertRaises(ValueError):
                    validate_integrity(self.office)
                self.office.db.rollback()
                self.assertTrue(validate_integrity(self.office))
        self.office.db.execute('BEGIN')
        self.office.db.execute("UPDATE inquiry_attachments SET status='uploading' WHERE id=?", (row['id'],))
        self.office.db.execute('UPDATE inquiry_attachment_chunks SET sha256=? WHERE chunk_index=1', ('0' * 64,))
        with self.assertRaises(ValueError):
            validate_integrity(self.office)
        self.office.db.rollback()
        self.office.db.execute('BEGIN')
        self.office.db.execute('UPDATE inquiry_attachment_chunks SET data=?,sha256=? WHERE chunk_index=1', (b'fake', sha(b'fake')))
        self.problem(409, lambda: self.api.content_inquiry(self.owner, self.inquiry, row['id']))
        with self.assertRaises(ValueError):
            validate_integrity(self.office)
        self.office.db.rollback()

    def test_integrity_rejects_deleted_bytes_or_orphan_files_and_global_overreservation(self):
        ready = self.upload()
        self.api.remove_inquiry(self.owner, self.inquiry, ready['id'])
        self.office.db.execute('BEGIN')
        self.office.db.execute('INSERT INTO inquiry_attachment_chunks(attachment_id,chunk_index,data,sha256,size) VALUES(?,?,?,?,?)',
                               (ready['id'], 0, PNG, sha(PNG), len(PNG)))
        with self.assertRaises(ValueError):
            validate_integrity(self.office)
        self.office.db.rollback()
        other = self.body('synthetic-message-18')
        self.office.db.execute('BEGIN')
        self.office.db.execute('UPDATE inquiry_attachments SET inquiry_id=? WHERE id=?', (other, ready['id']))
        with self.assertRaises(ValueError):
            validate_integrity(self.office)
        self.office.db.rollback()
        self.api.announce(self.token, self.manifest(source_id='synthetic-message-18'))
        with patch.object(domain, 'MAX_RESERVED_BYTES', len(PNG) - 1):
            with self.assertRaises(ValueError):
                validate_integrity(self.office)
        self.assertTrue(validate_integrity(self.office))

    def test_schema_is_additive_and_binary_type_is_not_arbitrary_sql(self):
        ensure_sqlite_schema(self.office)
        ensure_sqlite_schema(self.office)
        tables = {row[0] for row in self.office.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({'inquiry_attachment_sets', 'inquiry_attachments', 'inquiry_attachment_chunks',
                         'inquiry_attachment_limits'} <= tables)
        self.assertIn('data BYTEA NOT NULL', '\n'.join(domain.schema_statements()))
        self.assertIn('data BLOB NOT NULL', '\n'.join(domain.schema_statements('BLOB')))
        with self.assertRaises(ValueError):
            domain.schema_statements('BLOB; DROP TABLE users')


if __name__ == '__main__':
    unittest.main(verbosity=2)
