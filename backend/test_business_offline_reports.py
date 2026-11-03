"""Frozen device service captures use the existing archive, never a second copy."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

from core import Office, Problem, canonical
from business_operations import BusinessOperations, validate_integrity, own_offline_report


class OfflineServiceReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'synthetic.sqlite3'
        self.office = Office(self.path)
        self.addCleanup(lambda: self.office.db.close())
        self.owner = self.actor('owner')
        self.tech = self.actor('technician')
        self.project = self.office.add_project(self.owner, 'Prüfprojekt ä', 'Synthetischer Kunde')
        self.office.assign(self.owner, self.project, self.tech['id'])
        self.api = BusinessOperations(self.office, clock=lambda: datetime(2026, 11, 3, 12, tzinfo=timezone.utc))

    def actor(self, role):
        email = uuid.uuid4().hex + '@example.test'
        return dict(id=self.office.add_user(email, 'Synthetic-password-123', role), email=email, role=role)

    def body(self):
        entry = uuid.uuid4().hex
        content = dict(title='  Wartungsprotokoll ä  ', description='Geprüft.\nUnveränderter Inhalt.', notes='',
                       project_name='Prüfprojekt ä', customer='Synthetischer Kunde', captured_at='2026-11-03T10:00:00.000Z')
        return dict(request_id=uuid.uuid4().hex, entry_id=entry, content=content,
                    content_hash=hashlib.sha256(canonical([entry, self.project, content]).encode()).hexdigest(),
                    signer=' Synthetischer Kunde ', strokes=[[[0.1, 0.2], [0.8, 0.7]]],
                    signed_at='2026-11-03T10:05:00.000Z')

    def capture(self, body, actor=None):
        return self.api.capture_offline(actor or self.tech, self.project, body)

    def error(self, status, action):
        with self.assertRaises(Problem) as caught:
            action()
        self.assertEqual(caught.exception.status, status, caught.exception.message)

    def counts(self):
        return [self.office.db.execute('SELECT COUNT(*) FROM ' + name).fetchone()[0]
                for name in ('business_operation_entries', 'business_operation_versions', 'business_operations_requests')]

    def test_offline_capture_archives_exact_content_two_revisions_and_original_pdf(self):
        body = self.body()
        result = self.capture(body)
        self.assertEqual((result['id'], result['status'], result['revision']), (body['entry_id'], 'signed', 2))
        self.assertEqual(result['title'], body['content']['title'])
        self.assertEqual(result['signer'], body['signer'])
        self.assertEqual(result['offline_capture']['content'], body['content'])
        self.assertEqual(result['signed_at'], body['signed_at'])
        self.assertEqual(result['offline_capture']['received_at'], '2026-11-03T12:00:00+00:00')
        pdf = self.api.entry_pdf(self.tech, self.project, result['id'])
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertEqual(hashlib.sha256(pdf).hexdigest(), result['pdf_sha256'])
        self.assertIn(b'Ger', pdf)
        self.assertEqual(self.counts(), [1, 2, 1])
        self.assertTrue(validate_integrity(self.office))
        self.assertTrue(own_offline_report(self.office, self.tech, result['id']))
        self.assertFalse(own_offline_report(self.office, self.owner, result['id']))

    def test_lost_ack_restart_and_project_rename_return_original_without_rendering(self):
        body = self.body()
        result = self.capture(body)
        pdf = self.api.entry_pdf(self.tech, self.project, result['id'])
        self.office.db.execute('UPDATE projects SET name=?,customer=? WHERE id=?', ('Renamed', 'Renamed', self.project))
        self.office.db.commit()
        self.office.db.close()
        self.office = Office(self.path)
        self.api = BusinessOperations(self.office)
        with patch('business_operations._render_pdf', side_effect=AssertionError('Replay must not render')):
            self.assertEqual(self.capture(body), result)
            self.assertEqual(self.api.entry_pdf(self.tech, self.project, result['id']), pdf)
        self.assertEqual(self.counts(), [1, 2, 1])
        self.assertEqual(self.office.db.execute("SELECT COUNT(*) FROM audit WHERE action='business.entry.offline.captured'").fetchone()[0], 1)

    def test_changed_request_id_ink_actor_content_and_foreign_identity_are_rejected(self):
        body = self.body()
        self.capture(body)
        for field, value in (('request_id', uuid.uuid4().hex), ('signer', 'Changed'),
                             ('strokes', [[[0.2, 0.2], [0.8, 0.8]]]), ('entry_id', uuid.uuid4().hex)):
            self.error(409, lambda field=field, value=value: self.capture({**body, field: value}))
        self.error(409, lambda: self.capture(body, self.owner))
        self.assertEqual(self.counts(), [1, 2, 1])

    def test_initial_snapshot_conflict_does_not_rewrite_or_create_capture(self):
        body = self.body()
        self.office.db.execute('UPDATE projects SET customer=? WHERE id=?', ('Changed', self.project))
        self.error(409, lambda: self.capture(body))
        self.assertEqual(self.counts(), [0, 0, 0])

    def test_revoked_access_and_role_are_checked_before_every_receipt(self):
        body = self.body()
        self.capture(body)
        self.office.assign(self.owner, self.project, self.tech['id'], remove=True)
        self.error(404, lambda: self.capture(body))
        self.office.assign(self.owner, self.project, self.tech['id'])
        self.office.db.execute('UPDATE users SET active=0 WHERE id=?', (self.tech['id'],))
        self.error(401, lambda: self.capture(body))

    def test_module_gate_blocks_even_identical_receipt_until_reenabled(self):
        body = self.body()
        self.capture(body)
        with patch('business_organization.require_active', side_effect=Problem(423, 'Disabled')):
            self.error(423, lambda: self.capture(body))

    def test_permission_revocation_during_rendering_commits_nothing(self):
        from business_operations import _render_pdf
        body = self.body()
        def render(value):
            pdf = _render_pdf(value)
            self.office.assign(self.owner, self.project, self.tech['id'], remove=True)
            return pdf
        with patch('business_operations._render_pdf', side_effect=render):
            self.error(404, lambda: self.capture(body))
        self.assertEqual(self.counts(), [0, 0, 0])

    def test_partial_storage_failure_rolls_back_archive_versions_and_receipt(self):
        body = self.body()
        original = self.api._version
        def version(kind, value):
            if value['revision'] == 2:
                raise RuntimeError('Synthetic disk failure')
            original(kind, value)
        with patch.object(self.api, '_version', side_effect=version):
            with self.assertRaises(RuntimeError):
                self.capture(body)
        self.assertEqual(self.counts(), [0, 0, 0])
        self.capture(body)
        self.assertEqual(self.counts(), [1, 2, 1])

    def test_concurrent_capture_is_one_archive_and_one_receipt(self):
        body = self.body()
        with ThreadPoolExecutor(max_workers=2) as workers:
            values = list(workers.map(lambda _: self.capture(body), range(2)))
        self.assertEqual(values[0], values[1])
        self.assertEqual(self.counts(), [1, 2, 1])

    def test_malformed_hash_times_shapes_and_signature_are_rejected(self):
        for field, value in (('content_hash', '0' * 64), ('signed_at', '2026-11-03T09:59:00Z'),
                ('signed_at', '2026-11-03T12:06:00Z'), ('signed_at', '2026-11-03T10:05:00'),
                ('strokes', [[[True, 0.2], [0.8, 0.7]]]), ('signer', '\ud800')):
            body = {**self.body(), field: value}
            self.error(409 if field == 'content_hash' else 400, lambda: self.capture(body))
        body = self.body()
        body['content']['untrusted_extra'] = 'ignored?'
        self.error(400, lambda: self.capture(body))
        self.assertEqual(self.counts(), [0, 0, 0])

    def test_archive_metadata_content_and_pdf_corruption_fail_closed(self):
        body = self.body()
        result = self.capture(body)
        archived = dict(self.office.db.execute('SELECT * FROM business_operation_entries WHERE id=?', (result['id'],)).fetchone())
        for mutation in ('received_at', 'request_hash', 'signer', 'content', 'pdf'):
            value = json.loads(archived['payload_json'])
            if mutation in ('received_at', 'request_hash'):
                value['offline_capture'][mutation] = 'invalid'
            elif mutation == 'signer':
                value['signer'] = 'Different signer'
            elif mutation == 'content':
                value['offline_capture']['content']['description'] = 'Changed'
            self.office.db.execute('UPDATE business_operation_entries SET payload_json=?,pdf=? WHERE id=?',
                (canonical(value), b'corrupt' if mutation == 'pdf' else archived['pdf'], result['id']))
            for action in (lambda: self.api.get_entry(self.tech, self.project, result['id']),
                           lambda: self.api.entry_pdf(self.tech, self.project, result['id']),
                           lambda: self.capture(body)):
                self.error(500, action)
            with self.assertRaises(ValueError):
                validate_integrity(self.office)
        self.office.db.execute('UPDATE business_operation_entries SET payload_json=?,pdf=? WHERE id=?',
            (archived['payload_json'], archived['pdf'], result['id']))
        self.assertTrue(validate_integrity(self.office))


if __name__ == '__main__':
    unittest.main()
