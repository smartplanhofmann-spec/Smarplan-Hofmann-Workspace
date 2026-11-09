"""Bound company journal metadata and original project receipts over real MFA/HTTP.

Only synthetic local SQLite companies are used. Native persistence and actual
process recreation are tested independently in the application suite.
"""
import hashlib
import json
import os
import unittest
import uuid

from core import canonical
from online import test_instance_isolation as isolation_fixture


@unittest.skipUnless(os.name == 'posix', 'Private POSIX server storage required')
class ProjectCreationJournalHttpTests(unittest.TestCase):
    setUp = isolation_fixture.InstanceIsolationTests.setUp
    fixture = isolation_fixture.InstanceIsolationTests.fixture
    bind = isolation_fixture.InstanceIsolationTests.bind
    app = isolation_fixture.InstanceIsolationTests.app
    request = isolation_fixture.InstanceIsolationTests.request
    login = isolation_fixture.InstanceIsolationTests.login
    start = isolation_fixture.InstanceIsolationTests.start

    def create(self, company):
        body = dict(request_id=uuid.uuid4().hex, name='Synthetic restart project',
                    customer='Synthetic restart customer')
        result = self.request(company, '/projects', body, token=company['token'], status=201).json
        expected = dict(body, customer_id=None)
        fingerprint = hashlib.sha256(canonical(dict(operation='core.project.create:v1', data=expected)).encode()).hexdigest()
        return body, result, fingerprint

    def test_two_bound_scopes_and_receipt_survive_rename_and_exact_retry(self):
        first, second = [self.start(value) for value in self.company]
        for current, foreign in ((first, second), (second, first)):
            meta = self.request(current, '/business/capabilities', token=current['token']).json
            actor = current['office'].user(current['token'])
            scope = dict(schema_version=1, instance_id=current['instance_id'], account_id=actor['id'])
            self.assertIn('project_creation_journal', meta['features'])
            self.assertEqual(meta['project_creation_scope'], scope)
            body, result, fingerprint = self.create(current)
            path = '/business/project-creations/' + body['request_id']
            receipt = self.request(current, path, token=current['token']).json
            self.assertEqual(receipt, dict(scope, request_id=body['request_id'],
                request_hash=fingerprint, project_id=result['id']))
            # Current project names are editable, never a reconstructed input.
            with current['office'].db:
                current['office'].db.execute('UPDATE projects SET name=? WHERE id=?',
                    ('Synthetic renamed project', result['id']))
            self.assertEqual(self.request(current, path, token=current['token']).json, receipt)
            self.assertEqual(self.request(current, '/projects', body, token=current['token'], status=201).json, result)
            self.assertEqual(self.request(current, path, token=current['token']).json, receipt)
            self.request(foreign, path, token=foreign['token'], status=404)
            self.assertNotIn(str(current['root']), json.dumps(receipt))
            self.assertNotIn('vault_fingerprint', receipt)
            self.assertNotIn('public_host', receipt)
            self.assertEqual(current['office'].db.execute('SELECT COUNT(*) FROM projects').fetchone()[0], 2)

    def test_unbound_instance_does_not_advertise_or_return_journal(self):
        company = self.company[0]
        company['client'] = self.app(company, instance_id=None).test_client()
        company['token'] = self.login(company)
        meta = self.request(company, '/business/capabilities', token=company['token']).json
        self.assertIn('project_creation_receipts', meta['features'])
        self.assertNotIn('project_creation_journal', meta['features'])
        self.assertNotIn('project_creation_scope', meta)
        self.request(company, '/business/project-creations/' + uuid.uuid4().hex,
            token=company['token'], status=409)

    def test_receipt_is_own_owner_only_with_fresh_identity_and_strict_http_shape(self):
        company = self.start(self.company[0])
        body, _, _ = self.create(company)
        path = '/business/project-creations/' + body['request_id']
        owner = company['office'].user(company['token'])
        self.request(company, path, token=None, status=401)
        self.request(company, path + '?instance_id=' + company['instance_id'], token=company['token'], status=400)
        self.request(company, path, {}, token=company['token'], status=405)
        other = self.request(company, '/users', dict(email='other-owner@example.test',
            password='Synthetic-other-password-123', role='owner'), token=company['token'], status=201).json['id']
        other_token = self.login(company, 'other-owner@example.test', 'Synthetic-other-password-123')
        self.assertNotEqual(other, owner['id'])
        self.request(company, path, token=other_token, status=404)
        with company['office'].db:
            company['office'].db.execute("UPDATE users SET role='technician' WHERE id=?", (owner['id'],))
        self.request(company, path, token=company['token'], status=403)
        with company['office'].db:
            company['office'].db.execute('UPDATE users SET active=0 WHERE id=?', (owner['id'],))
        self.request(company, path, token=company['token'], status=401)
        self.request(company, '/business/capabilities', token=company['token'], status=401)

    def test_narrow_offline_token_never_receives_scope_or_project_receipt(self):
        company = self.start(self.company[0])
        body, _, _ = self.create(company)
        grant = self.request(company, '/business/offline/access', {}, token=company['token'], status=201).json
        meta = self.request(company, '/business/capabilities', token=grant['token']).json
        self.assertEqual(meta['features'], [])
        self.assertNotIn('project_creation_scope', meta)
        self.request(company, '/business/project-creations/' + body['request_id'], token=grant['token'], status=403)

    def test_malformed_or_missing_original_is_never_reconstructed(self):
        company = self.start(self.company[0])
        body, result, fingerprint = self.create(company)
        path = '/business/project-creations/' + body['request_id']
        for invalid in ({}, {'id': result['id'], 'name': 'extra'}, {'id': 'not-an-id'}, [], None):
            with self.subTest(invalid=invalid), company['office'].db:
                company['office'].db.execute('UPDATE business_foundation_requests SET result_json=? WHERE request_id=?',
                    (json.dumps(invalid), body['request_id']))
            self.request(company, path, token=company['token'], status=409)
        with company['office'].db:
            company['office'].db.execute('UPDATE business_foundation_requests SET result_json=?,request_hash=? WHERE request_id=?',
                (canonical(result), 'not-a-hash', body['request_id']))
        self.request(company, path, token=company['token'], status=409)
        with company['office'].db:
            company['office'].db.execute('UPDATE business_foundation_requests SET result_json=?,request_hash=? WHERE request_id=?',
                (canonical({'id': uuid.uuid4().hex}), fingerprint, body['request_id']))
        self.request(company, path, token=company['token'], status=404)


if __name__ == '__main__':
    unittest.main()
