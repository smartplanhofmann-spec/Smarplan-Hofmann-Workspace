"""Stored-export authorization boundary; real allocation rights are tested on PG.

The historical export fixture contains synthetic payment IDs, not issued
invoices. Only the authorization hook is substituted in these focused tests.
"""
import base64
import hashlib
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import uuid

from business_adapters import Adapters
from core import Office, Problem, canonical


class StoredExportPaymentScope(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='synthetic-export-payment-scope-')
        self.addCleanup(temporary.cleanup)
        self.office = Office(Path(temporary.name) / 'office.db')
        self.addCleanup(self.office.db.close)
        self.owner = dict(id=self.office.add_user('export@example.test', 'Synthetic-export-password-123', 'owner'),
                          role='owner', email='export@example.test')
        self.api = Adapters(self.office)
        self.adapter = self.api.save(self.owner, dict(request_id=uuid.uuid4().hex, name='Synthetic historical export',
            profile='lexware_review_json_v1', enabled=True))
        self.payments = [uuid.uuid4().hex, uuid.uuid4().hex]
        self.body = dict(request_id=uuid.uuid4().hex, document_ids=[], mapping={}, include_payments=True)
        self.run_id = uuid.uuid4().hex
        raw = canonical(dict(profile='lexware_review_json_v1', documents=[],
            payments_snapshot=[dict(id=identifier) for identifier in self.payments])).encode()
        self.result = dict(artifact_base64=base64.b64encode(raw).decode(), sha256=hashlib.sha256(raw).hexdigest(),
                           sources=[], media_type='application/json', filename='synthetic-historical.json')
        with self.office.db:
            self.office.db.execute('INSERT INTO business_adapter_runs(id,adapter_id,profile,status,source_sha256,'
                'rows_json,rows_sha256,result_json,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                (self.run_id, self.adapter['id'], 'lexware_review_json_v1', 'exported', self.result['sha256'],
                 '[]', hashlib.sha256(b'[]').hexdigest(), canonical(self.result), self.owner['id'], '2026-11-02T12:00:00+00:00'))
            request, digest, _ = self.api._request(self.owner, 'export:' + self.adapter['id'], self.body)
            self.api._remember(self.owner, request, digest, {'id': self.run_id})
        self.access = Mock(return_value=self.owner)
        replacement = SimpleNamespace(require_effective_payment_access=self.access)
        self.override = patch.dict(sys.modules, business_accounting_allocations=replacement)
        self.override.start()
        self.addCleanup(self.override.stop)

    def test_replay_rechecks_every_payment_from_frozen_artifact_without_changing_bytes(self):
        before = dict(self.office.db.execute('SELECT * FROM business_adapter_runs WHERE id=?', (self.run_id,)).fetchone())
        saved = self.api.export_data(self.owner, self.adapter['id'], self.body)
        self.assertEqual(saved['result'], self.result)
        self.assertEqual([call.args[2] for call in self.access.call_args_list], self.payments)
        self.assertEqual(dict(self.office.db.execute('SELECT * FROM business_adapter_runs WHERE id=?', (self.run_id,)).fetchone()), before)

    def test_revoked_new_project_denies_replay_and_any_direct_export_run_read(self):
        self.access.side_effect = Problem(404, 'Synthetic project no longer available')
        for read in (lambda: self.api.export_data(self.owner, self.adapter['id'], self.body),
                     lambda: self.api._run(self.run_id, self.owner)):
            with self.assertRaises(Problem) as denied:
                read()
            self.assertEqual(denied.exception.status, 404)

    def test_export_run_cannot_be_returned_without_actor(self):
        with self.assertRaises(Problem) as denied:
            self.api._run(self.run_id)
        self.assertEqual(denied.exception.status, 403)
        self.access.assert_not_called()

    def test_modified_historical_artifact_fails_closed_before_publication(self):
        changed = dict(self.result, artifact_base64=base64.b64encode(b'{}').decode())
        with self.office.db:
            self.office.db.execute('UPDATE business_adapter_runs SET result_json=? WHERE id=?',
                                   (canonical(changed), self.run_id))
        with self.assertRaises(Problem) as invalid:
            self.api.export_data(self.owner, self.adapter['id'], self.body)
        self.assertEqual(invalid.exception.status, 409)
        self.access.assert_not_called()


if __name__ == '__main__':
    unittest.main()
