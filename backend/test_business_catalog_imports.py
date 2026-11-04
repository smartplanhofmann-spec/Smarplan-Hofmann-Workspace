"""Actual catalog bytes, additive history and acceptance; synthetic data only."""
import base64
import io
import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch
import uuid
import zipfile

from core import Office, Problem
from business_tests.test_documents import DocumentsFixture
from business_adapters import Adapters, ensure_sqlite_schema, _hash
import business_catalog_imports as catalog


RAW = b'code;name;unit;cost_price_net;unit_price_net;tax_rate\r\nSYN-17;Synthetic valve;ST;12.50;20.00;19\r\n'


class CatalogImportsTests(DocumentsFixture, unittest.TestCase):
    def setUp(self):
        import business_schema
        prior = tuple(spec for spec in business_schema.registry() if spec.name != 'business_catalog_imports')
        with patch.object(business_schema, 'registry', return_value=prior):
            super().setUp()
        ensure_sqlite_schema(self.office)
        self.adapters = Adapters(self.office)
        self.catalog = catalog.CatalogImports(self.office)
        self.adapter = self.adapters.save(self.owner, self.request(name='Synthetic source', profile='catalog_csv_v1', enabled=True))

    def install(self):
        with self.office.db:
            for statement in catalog.schema_statements('BLOB') + catalog.guard_statements('sqlite'):
                self.office.db.execute(statement)

    def request(self, **values):
        return dict(request_id=uuid.uuid4().hex, **values)

    def body(self, raw=RAW, **values):
        return self.request(content_base64=base64.b64encode(raw).decode(), filename='synthetic.csv', **values)

    def stage(self, body=None):
        return self.adapters.import_data(self.owner, self.adapter['id'], body or self.body())

    def error(self, status, fn, *args):
        with self.assertRaises(Problem) as raised:
            fn(*args)
        self.assertEqual(raised.exception.status, status)

    def test_actual_original_history_exact_replay_after_reopen_and_bound_acceptance(self):
        self.install()
        body = self.body()
        run = self.stage(body)
        self.assertEqual(run['original'], dict(available=True, filename='synthetic.csv', size=len(RAW), sha256=_hash(RAW)))
        self.assertIsNone(run['acceptance'])
        self.assertEqual(self.stage(body), run)
        result, status, media_type = self.catalog.original(self.owner, run['id'])
        self.assertEqual((bytes(result), status, media_type, result.filename), (RAW, 200, 'application/octet-stream', 'synthetic.csv'))
        command = self.request(confirmed=True)
        accepted = self.adapters.apply_catalog(self.owner, run['id'], command)
        self.assertEqual(accepted['acceptance']['source_sha256'], _hash(RAW))
        self.assertEqual(accepted['acceptance']['request_id'], command['request_id'])
        self.assertEqual(len(accepted['acceptance']['articles']), 1)
        self.assertEqual(self.adapters.apply_catalog(self.owner, run['id'], command), accepted)
        self.assertTrue(catalog.validate_integrity(self.office))
        reopened = Office(Path(self.temp.name) / 'office.db')
        self.addCleanup(reopened.db.close)
        self.assertEqual(Adapters(reopened).import_data(self.owner, self.adapter['id'], body), accepted)
        self.assertEqual(catalog.CatalogImports(reopened).detail(self.owner, run['id']), accepted)
        history = self.catalog.history(self.owner, self.adapter['id'], {'_query': {'limit': '1', 'offset': '0'}})
        self.assertEqual((history['total'], history['limit'], history['offset']), (1, 1, 0))
        self.assertEqual(history['items'][0]['row_count'], 1)
        self.assertNotIn('rows', history['items'][0])
        self.assertNotIn('request_json', json.dumps(history))

    def test_additive_legacy_marker_preserves_exact_old_rows_receipts_and_missing_original(self):
        staged = self.stage()
        applied = self.stage(self.body(RAW.replace(b'SYN-17', b'SYN-18')))
        self.adapters.apply_catalog(self.owner, applied['id'], self.request(confirmed=True))
        before_runs = [tuple(row) for row in self.office.db.execute('SELECT * FROM business_adapter_runs ORDER BY id')]
        before_requests = [tuple(row) for row in self.office.db.execute('SELECT * FROM business_adapter_requests ORDER BY request_id')]
        self.install()
        self.assertEqual(before_runs, [tuple(row) for row in self.office.db.execute('SELECT * FROM business_adapter_runs ORDER BY id')])
        self.assertEqual(before_requests, [tuple(row) for row in self.office.db.execute('SELECT * FROM business_adapter_requests ORDER BY request_id')])
        for item in (staged, applied):
            self.assertEqual(self.catalog.detail(self.owner, item['id'])['original'], dict(available=False, reason='legacy_original_not_stored'))
            self.error(404, self.catalog.original, self.owner, item['id'])
        accepted = self.adapters.apply_catalog(self.owner, staged['id'], self.request(confirmed=True))
        self.assertFalse(accepted['acceptance']['original_available'])
        self.assertTrue(catalog.validate_integrity(self.office))

    def test_fresh_global_settings_and_finance_rights_required_for_every_read(self):
        self.install()
        run = self.stage()
        user = dict(id=uuid.uuid4().hex, role='accountant', email='synthetic-accountant@example.test')
        with self.office.db:
            self.office.db.execute('INSERT INTO users(id,email,role,active) VALUES(?,?,?,1)', tuple(user[key] for key in ('id', 'email', 'role')))
        for fn, args in ((self.catalog.detail, (run['id'],)), (self.catalog.original, (run['id'],)), (self.catalog.history, (self.adapter['id'], {}))):
            self.error(403, fn, user, *args)
        with self.office.db:
            self.office.db.execute("INSERT INTO business_permission_grants(id,user_id,permission,scope,effect,revision,updated_by,updated_at) VALUES(?,?,?,'*','allow',1,?,?)", (uuid.uuid4().hex, user['id'], 'settings.manage', self.owner['id'], '2026-11-04'))
        self.assertEqual(self.catalog.detail(user, run['id'])['id'], run['id'])
        with self.office.db:
            self.office.db.execute("INSERT INTO business_permission_grants(id,user_id,permission,scope,effect,revision,updated_by,updated_at) VALUES(?,?,?,'*','deny',1,?,?)", (uuid.uuid4().hex, user['id'], 'finance.read', self.owner['id'], '2026-11-04'))
        self.error(403, self.catalog.original, user, run['id'])
        with self.office.db:
            self.office.db.execute('UPDATE users SET active=0 WHERE id=?', (user['id'],))
        self.error(401, self.catalog.detail, user, run['id'])

    def test_strict_history_query_filename_and_size_reject_without_writes(self):
        self.install()
        for query in ({'wat': '1'}, {'limit': '51'}, {'limit': '0'}, {'offset': '-1'}, {'offset': 1}, {'limit': '01'}):
            self.error(400, self.catalog.history, self.owner, self.adapter['id'], {'_query': query})
        for name in ('../secret.csv', 'a\\b.csv', '', 'x\n.csv', '.' , 'x' * 201):
            body = self.body(); body['filename'] = name
            self.error(400, self.stage, body)
        self.error(413, self.stage, self.body(b'x' * (2 * 1024 * 1024 + 1)))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_adapter_runs').fetchone()[0], 0)
        self.error(400, catalog.dispatch, self.office, self.owner, '/adapters/imports/' + 'a' * 32, 'GET', {'_query': {'extra': '1'}})

    def test_original_and_acceptance_are_atomic_with_existing_requests(self):
        self.install()
        body = self.body()
        with patch.object(self.adapters, '_remember', side_effect=RuntimeError('synthetic failure after original')):
            with self.assertRaises(RuntimeError):
                self.stage(body)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_catalog_originals').fetchone()[0], 0)
        run = self.stage(body)
        command = self.request(confirmed=True)
        with patch.object(self.adapters, '_remember', side_effect=RuntimeError('synthetic failure after acceptance')):
            with self.assertRaises(RuntimeError):
                self.adapters.apply_catalog(self.owner, run['id'], command)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_catalog_acceptances').fetchone()[0], 0)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_articles').fetchone()[0], 0)
        self.assertEqual(self.catalog.detail(self.owner, run['id'])['status'], 'staged')
        self.adapters.apply_catalog(self.owner, run['id'], command)
        self.assertTrue(catalog.validate_integrity(self.office))

    def test_immutable_storage_and_tampered_new_original_fail_closed(self):
        self.install()
        run = self.stage()
        for statement, values in (("UPDATE business_catalog_originals SET filename='changed' WHERE run_id=?", (run['id'],)),
                                  ('DELETE FROM business_catalog_originals WHERE run_id=?', (run['id'],))):
            with self.assertRaises(sqlite3.IntegrityError), self.office.db:
                self.office.db.execute(statement, values)
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_catalog_originals_update_guard')
            self.office.db.execute('UPDATE business_catalog_originals SET content=? WHERE run_id=?', (RAW + b'changed', run['id']))
        self.error(409, self.catalog.original, self.owner, run['id'])
        self.error(409, self.adapters.apply_catalog, self.owner, run['id'], self.request(confirmed=True))
        with self.assertRaises(ValueError):
            catalog.validate_integrity(self.office)

    def test_missing_new_original_never_looks_like_legacy_import(self):
        self.install()
        run = self.stage()
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_catalog_originals_delete_guard')
            self.office.db.execute('DELETE FROM business_catalog_originals WHERE run_id=?', (run['id'],))
        self.error(409, self.catalog.detail, self.owner, run['id'])
        with self.assertRaises(ValueError):
            catalog.validate_integrity(self.office)

    def test_lost_acceptance_and_rebound_article_version_fail_closed(self):
        self.install()
        run = self.stage()
        accepted = self.adapters.apply_catalog(self.owner, run['id'], self.request(confirmed=True))
        article = accepted['acceptance']['articles'][0]
        self.call('save_article', self.request(revision=article['revision'], unit_price_net='999.99'), article['article_id'])
        row = self.office.db.execute('SELECT * FROM business_catalog_acceptances WHERE run_id=?', (run['id'],)).fetchone()
        forged = json.loads(row['payload_json'])
        forged['articles'][0]['revision'] += 1
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_catalog_acceptances_update_guard')
            self.office.db.execute('UPDATE business_catalog_acceptances SET payload_json=?,sha256=? WHERE run_id=?', (json.dumps(forged), _hash(forged), run['id']))
        self.error(409, self.catalog.detail, self.owner, run['id'])
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_catalog_acceptances_delete_guard')
            self.office.db.execute('DELETE FROM business_catalog_acceptances WHERE run_id=?', (run['id'],))
        self.error(409, self.catalog.original, self.owner, run['id'])

    def test_v1_equivalent_base64_spelling_keeps_exact_command_fingerprint(self):
        self.install()
        body = self.body()
        alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
        # RAW has one padding quantum; non-zero unused pad bits still decode to
        # the exact bytes under the already shipped v1 decoder.
        encoded = body['content_base64']
        self.assertTrue(encoded.endswith('=='))
        changed = alphabet[alphabet.index(encoded[-3]) + 1]
        body['content_base64'] = encoded[:-3] + changed + '=='
        self.assertEqual(base64.b64decode(body['content_base64'], validate=True), RAW)
        run = self.stage(body)
        self.assertEqual(self.stage(body), run)
        self.assertTrue(catalog.validate_integrity(self.office))

    def test_datanorm_actual_cp850_and_explicit_mapping_survive_article_changes(self):
        self.install()
        adapter = self.adapters.save(self.owner, self.request(name='Synthetic DATANORM', profile='datanorm_a14_cp850_v1', enabled=True))
        raw = 'A;N;SYN-D;;Überwurf;synthetisch;2;1;ST;12345;;;;\r\n'.encode('cp850')
        run = self.adapters.import_data(self.owner, adapter['id'], self.body(raw))
        self.assertEqual(bytes(self.catalog.original(self.owner, run['id'])[0]), raw)
        command = self.request(confirmed=True, price_scale='0.01', target_price='purchase_net', tax_rate='19')
        applied = self.adapters.apply_catalog(self.owner, run['id'], command)
        self.assertEqual(applied['acceptance']['price_mapping'], dict(price_scale='0.01', target_price='purchase_net', tax_rate='19'))
        article = applied['acceptance']['articles'][0]
        self.call('save_article', self.request(revision=article['revision'], unit_price_net='99.99'), article['article_id'])
        self.assertEqual(self.catalog.detail(self.owner, run['id']), applied)
        self.assertTrue(catalog.validate_integrity(self.office))

    def test_company_archive_contains_exact_original_blob(self):
        from company_export_archive import build, structure, verify
        self.install()
        run = self.stage()
        self.adapters.apply_catalog(self.owner, run['id'], self.request(confirmed=True))
        inventory = structure(self.office)
        raw, manifest = build(self.office, instance_id='1' * 32, export_id='2' * 32, created_at='2026-11-04T12:00:00+00:00', created_by=self.owner['id'], reason='Synthetic catalog proof', inventory=inventory)
        verify(raw, instance_id='1' * 32)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            row = json.loads(archive.read('data/business_catalog_originals.jsonl').decode())
            self.assertEqual(archive.read(row['content']['$file']), RAW)
            self.assertEqual(row['sha256'], _hash(RAW))

    def test_readonly_preview_matches_actual_create_update_and_noop_payloads(self):
        self.install()
        run = self.stage()
        before_changes = self.office.db.total_changes
        preview = self.catalog.preview(self.owner, run['id'], {})
        self.assertEqual(self.office.db.total_changes, before_changes)
        self.assertEqual(preview['preview_sha256'], _hash({key: value for key, value in preview.items() if key != 'preview_sha256'}))
        self.assertEqual(preview['rows'][0]['action'], 'create')
        self.assertIsNone(preview['rows'][0]['before'])
        accepted = self.adapters.apply_catalog(self.owner, run['id'], self.request(confirmed=True))
        aid = accepted['result']['article_ids'][0]
        actual = lambda: json.loads(self.office.db.execute('SELECT payload_json FROM business_articles WHERE id=?', (aid,)).fetchone()[0])
        self.assertEqual(preview['rows'][0]['after'], actual())
        edited = self.call('save_article', self.request(revision=1, cost_known=False), aid)
        run = self.stage()
        before_changes = self.office.db.total_changes
        preview = self.catalog.preview(self.owner, run['id'], {})
        self.assertEqual(self.office.db.total_changes, before_changes)
        self.assertEqual(preview['rows'][0]['action'], 'noop')
        self.assertFalse(preview['rows'][0]['after']['cost_known'])
        self.assertEqual(preview['rows'][0]['before'], preview['rows'][0]['after'])
        accepted = self.adapters.apply_catalog(self.owner, run['id'], self.request(confirmed=True))
        self.assertEqual(preview['rows'][0]['after'], actual())
        self.assertEqual(accepted['acceptance']['articles'][0]['revision'], edited['revision'])
        changed = self.stage(self.body(RAW.replace(b'12.50', b'13.00')))
        preview = self.catalog.preview(self.owner, changed['id'], {})
        self.assertEqual(preview['rows'][0]['action'], 'update')
        self.assertTrue(preview['rows'][0]['after']['cost_known'])
        self.adapters.apply_catalog(self.owner, changed['id'], self.request(confirmed=True))
        self.assertEqual(preview['rows'][0]['after'], actual())

    def test_preview_refuses_stale_original_target_and_same_source_manual_price_conflict(self):
        self.install()
        run = self.stage()
        aid = self.adapters.apply_catalog(self.owner, run['id'], self.request(confirmed=True))['result']['article_ids'][0]
        staged = self.stage()
        self.call('save_article', self.request(revision=1, unit_price_net='99'), aid)
        before_changes = self.office.db.total_changes
        self.error(409, self.catalog.preview, self.owner, staged['id'], {})
        self.assertEqual(self.office.db.total_changes, before_changes)
        staged = self.stage()
        self.error(409, self.catalog.preview, self.owner, staged['id'], {})
        self.error(409, self.adapters.apply_catalog, self.owner, staged['id'], self.request(confirmed=True))

    def test_datanorm_preview_exact_mapping_and_counterprice_match_actual_v1_payload(self):
        self.install()
        adapter = self.adapters.save(self.owner, self.request(name='Synthetic DATANORM preview', profile='datanorm_a14_cp850_v1', enabled=True))
        raw = b'A;N;SYN-D;;Synthetic;preview;2;1;ST;15;;;;\r\n'
        run = self.adapters.import_data(self.owner, adapter['id'], self.body(raw))
        mapping = dict(price_scale='0.0001', target_price='purchase_net', tax_rate='19')
        preview = self.catalog.preview(self.owner, run['id'], mapping)
        self.assertEqual(preview['rows'][0]['after']['cost_price_net'], '0.0002')
        aid = self.adapters.apply_catalog(self.owner, run['id'], self.request(confirmed=True, **mapping))['result']['article_ids'][0]
        self.call('save_article', self.request(revision=1, unit_price_net='73.50'), aid)
        run = self.adapters.import_data(self.owner, adapter['id'], self.body(raw))
        preview = self.catalog.preview(self.owner, run['id'], mapping)
        self.assertEqual(preview['rows'][0]['after']['unit_price_net'], '73.50')
        self.adapters.apply_catalog(self.owner, run['id'], self.request(confirmed=True, **mapping))
        actual = json.loads(self.office.db.execute('SELECT payload_json FROM business_articles WHERE id=?', (aid,)).fetchone()[0])
        self.assertEqual(preview['rows'][0]['after'], actual)
        for data in ({}, dict(mapping, request_id=uuid.uuid4().hex), dict(mapping, price_scale='0')):
            new = self.adapters.import_data(self.owner, adapter['id'], self.body(raw))
            self.error(400, self.catalog.preview, self.owner, new['id'], data)

    def test_preview_post_is_readonly_after_module_deactivation_and_global_compatibility_mode(self):
        import business_api
        import business_schema
        from business_organization import Organization, NEEDS, MODULES
        business_schema.ensure_schema(self.office, activate=True)
        run = self.stage()
        organization = Organization(self.office)
        organization.save(self.owner, self.request(revision=0, needs=dict(NEEDS),
            modules={key: dict(visible=None, enabled=key != 'documents') for key in MODULES}))
        path = '/business/adapters/imports/' + run['id'] + '/catalog-preview'
        before_changes = self.office.db.total_changes
        preview, status, media_type = business_api.dispatch(self.office, self.owner, path, 'POST', {})
        self.assertEqual((status, media_type), (200, 'application/json'))
        self.assertEqual(self.office.db.total_changes, before_changes)
        self.error(423, business_api.dispatch, self.office, self.owner, '/business/adapters/imports/' + run['id'] + '/apply', 'POST', self.request(confirmed=True))
        business_schema.set_mode(self.office, 'legacy')
        before_changes = self.office.db.total_changes
        self.assertEqual(business_api.dispatch(self.office, self.owner, path, 'POST', {})[0], preview)
        self.assertEqual(self.office.db.total_changes, before_changes)

    def test_preview_requires_both_read_permissions_but_not_finance_write(self):
        self.install()
        run = self.stage()
        user = dict(id=uuid.uuid4().hex, role='manager', email='synthetic-preview-reader@example.test')
        with self.office.db:
            self.office.db.execute('INSERT INTO users(id,email,role,active) VALUES(?,?,?,1)', tuple(user[key] for key in ('id', 'email', 'role')))
            for permission in ('settings.manage', 'finance.read'):
                self.office.db.execute("INSERT INTO business_permission_grants(id,user_id,permission,scope,effect,revision,updated_by,updated_at) VALUES(?,?,?,'*','allow',1,?,?)", (uuid.uuid4().hex, user['id'], permission, self.owner['id'], '2026-11-04'))
        self.assertEqual(self.catalog.preview(user, run['id'], {})['rows'][0]['action'], 'create')
        self.error(403, self.adapters.apply_catalog, user, run['id'], self.request(confirmed=True))
        with self.office.db:
            self.office.db.execute("UPDATE business_permission_grants SET effect='deny' WHERE user_id=? AND permission='finance.read'", (user['id'],))
        self.error(403, self.catalog.preview, user, run['id'], {})


class CatalogMigrationTests(unittest.TestCase):
    def test_new_module_installs_after_frozen_adapters_and_replays_without_rewriting_checksums(self):
        import tempfile
        import business_schema
        with tempfile.TemporaryDirectory(prefix='catalog-migration-') as folder:
            modules = business_schema.registry()
            before = tuple(spec for spec in modules if spec.name != 'business_catalog_imports')
            with patch.object(business_schema, 'registry', return_value=before):
                office = Office(Path(folder) / 'office.db')
            self.addCleanup(office.db.close)
            business_schema.ensure_schema(office, registry=before, activate=True)
            checksums = [tuple(row) for row in office.db.execute('SELECT * FROM business_schema_migrations ORDER BY module')]
            business_schema.ensure_schema(office, registry=modules, activate=True)
            self.assertEqual(checksums, [tuple(row) for row in office.db.execute("SELECT * FROM business_schema_migrations WHERE module!='business_catalog_imports' ORDER BY module")])
            business_schema.ensure_schema(office, registry=modules, activate=True)
            self.assertTrue(business_schema.validate_integrity(office, registry=modules))
            self.assertIn('business_catalog_imports', business_schema.state(office)['capabilities'])
