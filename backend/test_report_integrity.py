"""Legacy report archives: detect corruption and recover a lost sign response."""
import hashlib
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

from core import Office, Problem, canonical, digest, make_pdf
from onedrive import OneDrive
from server import make_handler


STROKES = [[[0.1, 0.2], [0.6, 0.8], [0.9, 0.3]]]


class ReportIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'reports.sqlite3'
        self.office = Office(self.path)
        self.owner_id = self.office.add_user('owner@example.test', 'Synthetic-owner-password', 'owner')
        self.tech_id = self.office.add_user('tech@example.test', 'Synthetic-tech-password', 'technician')
        self.owner = dict(self.office.db.execute('SELECT * FROM users WHERE id=?', (self.owner_id,)).fetchone())
        self.tech = dict(self.office.db.execute('SELECT * FROM users WHERE id=?', (self.tech_id,)).fetchone())
        self.project = self.office.add_project(self.owner, 'Synthetisches Projekt', 'Archivkunde')
        self.private = self.office.add_project(self.owner, 'Anderes Projekt', 'Anderer Kunde')
        self.office.assign(self.owner, self.project, self.tech_id)
        self.report = self.office.draft(self.tech, self.project, 'Servicebericht', 'Leistung geprüft.')

    def tearDown(self):
        self.office.db.close()
        self.temp.cleanup()

    def sign(self, actor=None, **changes):
        values = dict(expected_hash=self.report['content_hash'], signer='Synthetischer Kunde', strokes=STROKES)
        values.update(changes)
        return self.office.sign(actor or self.tech, self.report['id'], **values)

    def archive(self):
        return dict(self.office.db.execute('SELECT * FROM reports WHERE id=?', (self.report['id'],)).fetchone())

    def replace_payload(self, value):
        with self.office.db:
            self.office.db.execute('UPDATE reports SET payload=? WHERE id=?', (value, self.report['id']))

    def assert_problem(self, status, action):
        with self.assertRaises(Problem) as error:
            action()
        self.assertEqual(error.exception.status, status)

    def assert_corruption_rejected(self):
        before = self.archive()
        with patch('core.make_pdf', side_effect=AssertionError('An archive must never be regenerated')):
            for action in (
                lambda: self.office.report(self.tech, self.report['id']),
                lambda: self.office.reports(self.tech, self.project),
                lambda: self.office.pdf(self.tech, self.report['id']),
                self.sign,
            ):
                self.assert_problem(500, action)
        self.assertEqual(self.archive(), before)

    def test_content_identity_and_project_corruption_fail_on_every_read_and_sign_path(self):
        for mutation in ('description', 'content_hash', 'project_id', 'id'):
            with self.subTest(mutation=mutation):
                value = json.loads(canonical(self.report))
                if mutation == 'description':
                    value['content']['description'] = 'Unbemerkte Änderung'
                elif mutation == 'project_id':
                    # Even a self-consistent content hash may not move a snapshot
                    # to a different project than the authorization row.
                    value['content']['project_id'] = self.private
                    value['content_hash'] = digest(canonical(value['content']))
                else:
                    value[mutation] = '0' * 64
                self.replace_payload(canonical(value))
                self.assert_corruption_rejected()

    def test_malformed_and_incomplete_payloads_are_integrity_errors(self):
        for payload in ('{', 'null', '[]', '1', '{}', '{"content":[]}'):
            with self.subTest(payload=payload):
                self.replace_payload(payload)
                self.assert_corruption_rejected()

    def test_missing_empty_or_corrupt_signed_pdf_is_never_regenerated(self):
        self.sign()
        archived = self.archive()
        for pdf, checksum in (
            (None, archived['pdf_hash']),
            (None, None),
            (b'', hashlib.sha256(b'').hexdigest()),
            (b'altered bytes', archived['pdf_hash']),
            (archived['pdf'], None),
            (archived['pdf'], '0' * 64),
        ):
            with self.subTest(pdf_length=len(pdf) if pdf is not None else None, checksum=checksum):
                with self.office.db:
                    self.office.db.execute('UPDATE reports SET pdf=?,pdf_hash=? WHERE id=?',
                                           (pdf, checksum, self.report['id']))
                self.assert_corruption_rejected()

    def test_signed_status_cannot_be_downgraded_while_retaining_archive(self):
        signed = self.sign()
        signed['status'] = 'draft'
        self.replace_payload(canonical(signed))
        self.assert_corruption_rejected()

    def test_incomplete_signed_metadata_and_invalid_strokes_fail_closed(self):
        signed = self.sign()
        for field, value in (('signer', None), ('signed_at', ''), ('signed_by', None),
                             ('strokes', []), ('strokes', [[[True, 0], [1, 1]]])):
            with self.subTest(field=field, value=value):
                changed = {**signed, field: value}
                self.replace_payload(canonical(changed))
                self.assert_corruption_rejected()

    def test_legacy_archive_survives_restart_and_customer_rename_without_rewriting(self):
        # Construct the pre-change format directly, including its original JSON
        # formatting. Opening it must neither upgrade the payload nor rerender.
        legacy = {**self.report, 'status': 'signed', 'signer': 'Archivkunde',
                  'strokes': STROKES, 'signed_at': '2026-10-14T09:00:00+00:00',
                  'signed_by': self.tech_id}
        pdf = make_pdf(legacy)
        with self.office.db:
            self.office.db.execute('UPDATE reports SET payload=?,pdf=?,pdf_hash=? WHERE id=?',
                                   (json.dumps(legacy, indent=2), pdf, hashlib.sha256(pdf).hexdigest(), self.report['id']))
        archived = self.archive()
        self.office.db.close()
        self.office = Office(self.path)
        with self.office.db:
            self.office.db.execute('UPDATE projects SET name=?,customer=? WHERE id=?',
                                   ('Neuer Projektname', 'Neuer Kundenname', self.project))
        with patch('core.make_pdf', side_effect=AssertionError('Archive was rerendered')):
            self.assertEqual(self.office.report(self.tech, self.report['id']), legacy)
            self.assertEqual(self.office.reports(self.tech, self.project), [legacy])
            self.assertEqual(self.office.pdf(self.tech, self.report['id']), pdf)
        self.assertEqual(self.archive(), archived)

    def test_identical_sign_retry_after_restart_returns_original_archive_once(self):
        signed = self.sign()
        archived = self.archive()
        self.office.db.close()
        self.office = Office(self.path)
        with patch('core.make_pdf', side_effect=AssertionError('Retry rerendered the signature')):
            self.assertEqual(self.sign(), signed)
        self.assertEqual(self.archive(), archived)
        count = self.office.db.execute('SELECT COUNT(*) FROM audit WHERE action=? AND object_id=?',
                                       ('report.signed', self.report['id'])).fetchone()[0]
        self.assertEqual(count, 1)

    def test_retry_rejects_different_actor_content_name_ink_or_revoked_access(self):
        self.sign()
        archived = self.archive()
        for kwargs in (
            {'actor': self.owner}, {'expected_hash': '0' * 64},
            {'signer': 'Anderer Kunde'}, {'strokes': [[[0.2, 0.2], [0.6, 0.8]]]},
        ):
            with self.subTest(kwargs=kwargs):
                self.assert_problem(409, lambda: self.sign(**kwargs))
        self.office.assign(self.owner, self.project, self.tech_id, remove=True)
        self.assert_problem(404, self.sign)
        self.assertEqual(self.archive(), archived)

    def test_concurrent_identical_requests_commit_one_signature(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.sign(), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(self.office.db.execute(
            'SELECT COUNT(*) FROM audit WHERE action=? AND object_id=?',
            ('report.signed', self.report['id'])).fetchone()[0], 1)

    def test_access_is_checked_before_disclosing_corruption(self):
        self.replace_payload('{')
        self.office.assign(self.owner, self.project, self.tech_id, remove=True)
        for action in (
            lambda: self.office.report(self.tech, self.report['id']),
            lambda: self.office.reports(self.tech, self.project),
            lambda: self.office.pdf(self.tech, self.report['id']),
            self.sign,
        ):
            self.assert_problem(404, action)

    def test_http_retry_reopens_the_same_signed_snapshot_and_pdf(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.office, OneDrive(self.office)))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        token = self.office.login('tech@example.test', 'Synthetic-tech-password')
        base = f'http://127.0.0.1:{server.server_port}/api/reports/{self.report["id"]}'

        def request(suffix='', body=None):
            data = canonical(body).encode() if body is not None else None
            req = Request(base + suffix, data=data, headers={
                'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
            with urlopen(req, timeout=5) as response:
                return response.read()

        try:
            body = dict(content_hash=self.report['content_hash'], signer='Synthetischer Kunde', strokes=STROKES)
            first = json.loads(request('/sign', body))
            pdf = request('/pdf')
            # The caller can resend the same intent after losing this response.
            self.assertEqual(json.loads(request('/sign', body)), first)
            self.assertEqual(json.loads(request()), first)
            self.assertEqual(request('/pdf'), pdf)
            self.assertTrue(pdf.startswith(b'%PDF'))
        finally:
            server.shutdown()
            server.server_close()
            worker.join()


if __name__ == '__main__':
    unittest.main()
