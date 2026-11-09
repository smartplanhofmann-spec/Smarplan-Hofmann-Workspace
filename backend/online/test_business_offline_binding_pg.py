"""Real PostgreSQL origin grants, legacy preservation and restore revocation."""
import time
import unittest
from unittest.mock import patch
import uuid

import business_schema
import plan_access
from business_offline_binding import TABLE, legacy_lookup
from core import Problem, canonical, digest
from online import release, test_business_company_handover_pg as bound
from online.store import PostgresOffice, migrate
from online.test_postgres_accounting_components_integration import disposable_restore, evidence_for, approve


@unittest.skipUnless(bound.fixture.fixture.DSN, 'Guarded disposable loopback PostgreSQL required')
class OfflineBindingPostgres(unittest.TestCase):
    setUp = bound.CompanyHandoverPostgres.setUp
    reopen = bound.CompanyHandoverPostgres.reopen
    login = bound.CompanyHandoverPostgres.login
    call = bound.CompanyHandoverPostgres.call

    def request_with_grant(self, method, path, token, *, origin=None, body=None, status=200):
        headers = {'Authorization': 'Bearer '+token}
        if origin is not None:
            headers['X-Smartplan-Offline-Binding'] = origin
        response = self.client.open('/api/v1'+path, method=method,
                                    base_url='https://office.example.test', headers=headers,
                                    **({'json': body} if body is not None else {}))
        self.assertEqual(response.status_code, status, response.get_data(as_text=True))
        return response

    def legacy_row(self):
        token = 'offline_workspace_'+uuid.uuid4().hex
        actor = self.office.db.execute('SELECT * FROM users WHERE id=?', (self.owner['id'],)).fetchone()
        with self.office.db:
            self.office.db.execute('INSERT INTO plan_sessions(token,user_id,expiry,credential) VALUES(?,?,?,?)',
                (digest(token), actor['id'], time.time()+3600, plan_access.credential(actor)))
        return token

    def test_bound_grant_header_original_lookup_and_actual_restore_revocation(self):
        project = self.office.add_project(self.owner, 'Synthetic offline project', customer='Synthetic customer')
        context = self.call('GET', '/offline/context').json
        self.assertEqual(context['mode'], 'bound_v2')
        self.assertEqual(context['binding']['instance_id'], self.instance)
        legacy = self.legacy_row()
        self.request_with_grant('GET', '/projects', legacy, status=409)
        grant = self.call('POST', '/offline/access/v2', {}, status=201).json
        origin = self.instance+':'+self.owner['id']
        self.assertEqual(grant['binding'], context['binding'])
        self.request_with_grant('GET', '/projects', grant['token'], status=403)
        self.request_with_grant('GET', '/projects', grant['token'], origin='f'*32+':'+self.owner['id'], status=403)
        self.request_with_grant('GET', '/projects', grant['token'], origin=origin)
        command = dict(request_id=uuid.uuid4().hex, title='Original offline plan',
                       walls=[dict(id='wall', points=[[1.0, -0.0], [1e-6, 2.0]])])
        path = '/projects/'+project+'/plans'
        original = self.request_with_grant('POST', path, grant['token'], origin=origin, body=command, status=201).json
        self.assertEqual(self.request_with_grant('POST', path, grant['token'], origin=origin,
                                              body=command, status=201).json, original)
        lookup = dict(schema_version=1, nonce=uuid.uuid4().hex, kind='plan_write',
                      project_id=project, plan_id=None, command_json=canonical(command))
        verified = self.call('POST', '/business/offline/recovery/lookup', lookup).json
        self.assertEqual(verified['original'], original)
        before = release.snapshot_fingerprint(bound.fixture.fixture.DSN)
        self.assertEqual(self.call('POST', '/business/offline/recovery/lookup', lookup).json, verified)
        after = release.snapshot_fingerprint(bound.fixture.fixture.DSN)
        for table in ('projects', 'plan_versions', 'plan_requests'):
            self.assertEqual(before[table], after[table])
        self.assertTrue(business_schema.validate_integrity(self.office))
        self.office.db.close()
        with disposable_restore(self.runtime) as (target, runtime, report):
            operator = PostgresOffice(target)
            try:
                approve(operator, evidence_for(operator, report))
            finally:
                operator.db.close()
            restored = PostgresOffice(runtime)
            try:
                self.assertEqual(restored.db.execute('SELECT COUNT(*) FROM '+TABLE).fetchone()[0], 0)
                self.assertEqual(restored.db.execute('SELECT COUNT(*) FROM plan_sessions').fetchone()[0], 0)
                with self.assertRaises(Problem) as denied:
                    plan_access.user(restored, grant['token'])
                self.assertEqual(denied.exception.status, 401)
                self.assertEqual(legacy_lookup(restored, self.owner, lookup)['original'], original)
                self.assertEqual(restored.save_plan(self.owner, project, command), original)
                self.assertTrue(business_schema.validate_integrity(restored))
            finally:
                restored.db.close()

    def test_additive_migration_preserves_legacy_rows_but_never_authorizes_them(self):
        self.office.db.close()
        full = business_schema.registry()
        prior = tuple(spec for spec in full if spec.name != 'business_offline_binding')
        self.assertEqual(len(prior), len(full)-1)
        with patch.object(business_schema, 'registry', return_value=prior), \
             patch.object(business_schema, 'MODULE_NAMES', tuple(spec.name for spec in prior)):
            self.setUp()
            token = self.legacy_row()
            before = release.snapshot_fingerprint(bound.fixture.fixture.DSN)
            self.office.db.close()
        migrate(bound.fixture.fixture.DSN, owner_role='smartplan-migrator',
                compatibility_mode='business', require_business_modules=True)
        after = release.snapshot_fingerprint(bound.fixture.fixture.DSN)
        for table, fingerprint in before.items():
            if table not in ('business_schema_migrations', 'business_schema_state', 'business_schema_events'):
                self.assertEqual(after[table], fingerprint, table)
        release.secure_database(bound.fixture.fixture.DSN, test_mode=True)
        self.reopen()
        self.request_with_grant('GET', '/projects', token, status=409)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM plan_sessions WHERE token=?',
                                               (digest(token),)).fetchone()[0], 1)
        self.assertEqual(self.call('POST', '/offline/access/v2', {}, status=201).json['binding']['instance_id'],
                         self.instance)
