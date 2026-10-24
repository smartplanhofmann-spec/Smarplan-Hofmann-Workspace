"""Disposable PostgreSQL acceptance for schema-6 external integrations.

All provider identities, ciphertexts, payloads and document sources are synthetic.
The named loopback source/candidate guard runs before any connection. Reuse test
helpers by composition so no older acceptance tests are discovered twice.
"""
import hashlib
import json
import time
import unittest

from cryptography.fernet import Fernet
import psycopg

from core import Problem, canonical, digest
from external_integrations import ExternalIntegrations, validate_integrity
from integration_bridge import IntegrationBridgeJobs, validate_integrity as validate_bridge
from online import release
from online import test_release as base_fixture
from online import test_release_attachments as attachment_fixture
from online import test_release_workspace as workspace_fixture
from online.restore import restore
from online.store import PostgresOffice, SCHEMA_VERSION


INTEGRATION_TABLES = frozenset(base_fixture.V6_TABLES)
RESTORE_RESET_TABLES = attachment_fixture.RESTORE_RESET_TABLES | frozenset(('external_bridge_jobs', 'external_bridge_limits'))


@unittest.skipUnless(base_fixture.DSN, 'SMARTPLAN_TEST_DSN is required for disposable PostgreSQL tests')
class IntegrationRelease(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base_fixture.CandidateRelease.setUpClass()

    @classmethod
    def tearDownClass(cls):
        base_fixture.CandidateRelease.tearDownClass()

    def setUp(self):
        self.new_fixture()
        self.assertEqual(SCHEMA_VERSION, 6)

    def new_fixture(self):
        self.legacy = attachment_fixture.AttachmentRelease('runTest')
        self.legacy.setUp()
        self.addCleanup(self.legacy.doCleanups)
        self.source, self.candidate = self.legacy.source, self.legacy.candidate
        self.actor, self.project = self.legacy.actor, self.legacy.project
        self.base = self.legacy.fixture.fixture

    def assert_legacy_preserved(self, dsn, data, *, revoked=False):
        self.legacy.fixture.assert_security_preserved(dsn, data['security'], sessions=not revoked)
        self.legacy.fixture.assert_workspace_preserved(dsn, data['workspace'], revoked=revoked)
        self.legacy.assert_attachments_preserved(dsn, data)

    def seed_integrations(self):
        legacy = self.legacy.seed_attachments()
        vault = Fernet(Fernet.generate_key())
        payloads = {
            'sevdesk': dict(contact={'id': '101', 'name': 'Fiktiver Kontakt'},
                            offers=[dict(id='201', kind='offer', number='TEST-A201', title='Fiktives Angebot',
                                         total_gross='123.45', currency='EUR', status='unknown')],
                            invoices=[dict(id='301', kind='invoice', number='TEST-R301', title='Fiktive Rechnung',
                                           total_gross='123.45', currency='EUR', status='unknown')]),
            'google_calendar': dict(calendar={'id': 'calendar@example.test', 'name': 'Fiktiver Kalender'},
                                   events=[dict(id='synthetic-event-1', title='Fiktiver Termin',
                                                start='2026-10-25T09:00:00+01:00', end='2026-10-25T10:00:00+01:00',
                                                all_day=False, time_zone='Europe/Berlin', status='confirmed')]),
            'onedrive': dict(folder={'id': 'synthetic-folder', 'drive_id': 'synthetic-drive',
                                    'name': 'Fiktiver Ordner', 'path': '/Synthetic',
                                    'url': 'https://onedrive.live.com/?id=synthetic-folder'},
                            files=[dict(id='synthetic-file', drive_id='synthetic-drive', parent_id='synthetic-folder',
                                        rev='synthetic-rev17', size=4, name='synthetic.txt',
                                        path='/Synthetic/synthetic.txt', media_type='text/plain',
                                        url='https://onedrive.live.com/?id=synthetic-file')]),
        }
        selections = {
            'sevdesk': dict(contact_id='101', offer_ids=['201'], invoice_ids=['301']),
            'google_calendar': dict(calendar_id='calendar@example.test', event_ids=['synthetic-event-1']),
            'onedrive': dict(folder_id='synthetic-folder', drive_id='synthetic-drive'),
        }
        remotes = {'sevdesk': '101', 'google_calendar': 'calendar@example.test', 'onedrive': 'synthetic-folder'}
        office = PostgresOffice(self.source)
        connections, connection_requests, binding_requests, snapshots, pending, bridge = {}, {}, {}, {}, {}, {}
        plaintext = {}
        now = time.time()
        legacy_storage = Fernet(legacy['security']['key']).encrypt(canonical(dict(
            access_token='synthetic-legacy-appfolder-access', refresh_token='synthetic-legacy-appfolder-refresh',
            expires_at=now + 300, client_id='synthetic-legacy-client')).encode()).decode()
        try:
            with office.lock, office.db:
                domain = ExternalIntegrations(office)
                office.db.execute("INSERT INTO secrets(name,value) VALUES('onedrive',?)", (legacy_storage,))
                for provider in ('sevdesk', 'google_calendar', 'onedrive'):
                    credential = canonical(dict(access_token='synthetic-access-' + provider,
                                                refresh_token='synthetic-refresh-' + provider))
                    if provider == 'onedrive':
                        credential = canonical(dict(mode='mailbot', proof='synthetic-confirmed-bot-connection'))
                    config = canonical(dict(client_id='synthetic-client-' + provider,
                                            client_secret='synthetic-client-secret-' + provider))
                    args = dict(credential=vault.encrypt(credential.encode()).decode(),
                                identity={'id': 'synthetic-account-' + provider, 'label': 'Fiktives ' + provider},
                                expected_generation=0, request_id=workspace_fixture.request_id())
                    if provider != 'sevdesk':
                        if provider == 'onedrive':
                            config = canonical(dict(mode='mailbot', label='Fiktiver vorhandener Bot'))
                        args['config'] = vault.encrypt(config.encode()).decode()
                    connection_requests[provider] = args
                    connection = domain.put_connection(self.actor, provider, **args)
                    self.assertEqual((connection['generation'], connection['state']), (1, 'connected'))
                    connections[provider] = connection
                    plaintext[provider] = dict(config=config, credential=credential)
                    revision = 0
                    if provider == 'onedrive':
                        old = domain.bind(self.actor, self.project, provider, 'synthetic-previous-folder',
                                          {'folder_id': 'synthetic-previous-folder', 'drive_id': 'synthetic-drive'}, generation=1, revision=0,
                                          request_id=workspace_fixture.request_id())
                        revision = old['revision']
                    bind_args = dict(generation=1, revision=revision,
                                     request_id=workspace_fixture.request_id())
                    binding = domain.bind(self.actor, self.project, provider, remotes[provider], selections[provider], **bind_args)
                    binding_requests[provider] = dict(remote=remotes[provider], data=selections[provider], args=bind_args)
                    snapshots[provider] = domain.save_snapshot(
                        self.actor, self.project, provider, payloads[provider], generation=1,
                        revision=binding['revision'], synced_at='2026-10-25T12:34:56+00:00')
                    if provider == 'google_calendar':
                        state_hash = hashlib.sha256((provider + ':' + workspace_fixture.request_id()).encode()).hexdigest()
                        pending[provider] = domain.put_oauth(
                            self.actor, provider, state_hash=state_hash,
                            session_hash=digest(legacy['security']['normal']), config_hash=connection['config_hash'],
                            payload=vault.encrypt(b'synthetic-pkce-verifier-and-callback-context').decode(),
                            generation=1, expires_at=time.time() + 590)
                    if provider in ('google_calendar', 'onedrive'):
                        jobs = IntegrationBridgeJobs(office, clock=lambda: now)
                        catalog_payload = dict(identity=connection['identity'], **(
                            {'calendars': [payloads[provider]['calendar']]} if provider == 'google_calendar'
                            else {'folders': [payloads[provider]['folder']]}))
                        catalog = jobs.queue(self.actor, provider, 'catalog', generation=1)
                        catalog = jobs.complete(self.actor, provider, catalog['id'], generation=1,
                                                payload=catalog_payload, source_id='synthetic-catalog-' + provider)
                        resource = remotes[provider] if provider == 'google_calendar' else canonical(selections[provider])
                        failed = jobs.queue(self.actor, provider, 'resource', generation=1, resource=resource)
                        jobs.complete(self.actor, provider, failed['id'], generation=1, payload={},
                                      source_id='synthetic-failure-' + provider, error_code='provider_unavailable')
                        queued = jobs.queue(self.actor, provider, 'resource', generation=1, resource=resource)
                        snapshot_job = jobs.queue(self.actor, provider, 'snapshot', generation=1, resource=resource,
                                                  project_id=self.project, revision=binding['revision'], selection=selections[provider])
                        snapshot_job = jobs.complete(self.actor, provider, snapshot_job['id'], generation=1,
                                                     payload=payloads[provider], source_id='synthetic-snapshot-' + provider)
                        jobs.touch(self.actor, provider, digest('synthetic-bot-key'))
                        bridge[provider] = dict(catalog=catalog, queued=queued, failed_id=failed['id'],
                                                snapshot=snapshot_job, catalog_payload=catalog_payload)
                self.assertTrue(validate_integrity(office))
                validate_bridge(office)
        finally:
            office.db.close()
        return dict(legacy=legacy, vault=vault, plaintext=plaintext, connections=connections,
                    connection_requests=connection_requests, binding_requests=binding_requests,
                    snapshots=snapshots, pending=pending, bridge=bridge, now=now, legacy_storage=legacy_storage)

    def assert_integrations_preserved(self, dsn, data):
        office = PostgresOffice(dsn)
        try:
            with office.lock, office.db:
                domain = ExternalIntegrations(office)
                for provider, expected in data['connections'].items():
                    current = domain.connection(self.actor, provider)
                    self.assertEqual(current, expected)
                    self.assertEqual(data['vault'].decrypt(current['credential'].encode()).decode(), data['plaintext'][provider]['credential'])
                    if current['config'] is not None:
                        self.assertEqual(data['vault'].decrypt(current['config'].encode()).decode(), data['plaintext'][provider]['config'])
                    self.assertEqual(domain.snapshot(self.actor, self.project, provider), data['snapshots'][provider])
                    self.assertEqual(domain.put_connection(self.actor, provider, **data['connection_requests'][provider]), expected)
                    request = data['binding_requests'][provider]
                    replay = domain.bind(self.actor, self.project, provider, request['remote'], request['data'], **request['args'])
                    self.assertEqual(replay['revision'], data['snapshots'][provider]['binding']['revision'])
                self.assertEqual(office.db.execute('SELECT COUNT(*) FROM external_oauth_states').fetchone()[0], 1)
                self.assertEqual(office.db.execute("SELECT value FROM secrets WHERE name='onedrive'").fetchone()[0], data['legacy_storage'])
                jobs = IntegrationBridgeJobs(office, clock=lambda: data['now'])
                for provider, expected in data['bridge'].items():
                    self.assertEqual([job['id'] for job in jobs.pending(self.actor, provider, 1)], [expected['queued']['id']])
                    self.assertEqual(jobs.job(self.actor, provider, expected['failed_id'], generation=1)['status'], 'failed')
                    replay = jobs.complete(self.actor, provider, expected['catalog']['id'], generation=1,
                                           payload=expected['catalog_payload'], source_id='synthetic-catalog-' + provider)
                    self.assertTrue(replay['duplicate'])
                    self.assertEqual(jobs.job(self.actor, provider, expected['snapshot']['id'], generation=1)['status'], 'completed')
                self.assertTrue(validate_integrity(office))
                validate_bridge(office)
        finally:
            office.db.close()

    def test_schema5_candidate_preserves_mfa_receipts_originals_and_adds_only_empty_integration_tables(self):
        data = self.legacy.seed_attachments()
        self.base.source_version(5)
        before = release.snapshot_fingerprint(self.source)
        sequences = release.sequence_state(self.source)
        self.assertTrue(INTEGRATION_TABLES.isdisjoint(before))
        prepared = self.base.prepare()
        after = release.snapshot_fingerprint(self.candidate)
        self.assertEqual((prepared['source_schema'], prepared['target_schema']), (5, 6))
        self.assertEqual(prepared['tables'], before)
        self.assertEqual(set(after) - set(before), INTEGRATION_TABLES)
        for table, fingerprint in before.items():
            if table != 'smartplan_schema':
                self.assertEqual(after[table], fingerprint, table)
        for table in INTEGRATION_TABLES:
            self.assertEqual(after[table]['rows'], 0, table)
        self.assert_legacy_preserved(self.candidate, data)
        self.assertEqual(release.sequence_state(self.candidate), sequences)
        self.assertEqual(release.snapshot_fingerprint(self.candidate), after)
        self.assertEqual(release.snapshot_fingerprint(self.source), before)

    def test_restore_upgrades_genuine_schema3_4_5_backups_without_changing_their_active_sources(self):
        for index, version in enumerate((3, 4, 5)):
            with self.subTest(source_schema=version):
                if index:
                    self.new_fixture()
                if version == 5:
                    data = self.legacy.seed_attachments()
                    security, workspace = data['security'], data['workspace']
                else:
                    security = self.legacy.fixture.seed_security()
                    self.base.seed_imports()
                    workspace = self.legacy.fixture.seed_workspace() if version == 4 else None
                self.base.source_version(version)
                before = release.snapshot_fingerprint(self.source)
                saved = release.backup(self.source, self.base.temp.name)
                restore(saved, self.source, self.candidate)
                after = release.snapshot_fingerprint(self.candidate)
                for table, fingerprint in before.items():
                    if table in RESTORE_RESET_TABLES:
                        self.assertEqual(after[table]['rows'], 0, table)
                    elif table not in ('smartplan_schema', 'inbound_import_tokens'):
                        self.assertEqual(after[table], fingerprint, table)
                for table in set(after) - set(before):
                    self.assertEqual(after[table]['rows'], 0, table)
                with psycopg.connect(self.candidate) as connection:
                    self.assertEqual(connection.execute('SELECT version FROM smartplan_schema').fetchone()[0], 6)
                self.legacy.fixture.assert_security_preserved(self.candidate, security, sessions=False)
                if workspace is not None:
                    self.legacy.fixture.assert_workspace_preserved(self.candidate, workspace, revoked=True)
                if version == 5:
                    self.legacy.assert_attachments_preserved(self.candidate, data)
                self.assertEqual(release.snapshot_fingerprint(self.source), before)

    def test_schema6_candidate_preserves_all_connections_selected_snapshots_oauth_states_and_retry_receipts(self):
        data = self.seed_integrations()
        before = release.snapshot_fingerprint(self.source)
        self.assertTrue(all(before[table]['rows'] > 0 for table in INTEGRATION_TABLES))
        prepared = self.base.prepare()
        self.assertEqual((prepared['source_schema'], prepared['target_schema']), (6, 6))
        self.assertEqual(prepared['tables'], before)
        self.assertEqual(release.snapshot_fingerprint(self.candidate), before)
        self.assert_legacy_preserved(self.candidate, data['legacy'])
        self.assert_integrations_preserved(self.candidate, data)
        self.assertEqual(release.snapshot_fingerprint(self.candidate), before)
        self.assertEqual(release.snapshot_fingerprint(self.source), before)

    def test_explicit_restore_disconnects_external_accounts_without_losing_business_data_or_reviving_old_requests(self):
        data = self.seed_integrations()
        before = release.snapshot_fingerprint(self.source)
        saved = release.backup(self.source, self.base.temp.name)
        restore(saved, self.source, self.candidate)
        after = release.snapshot_fingerprint(self.candidate)
        for table, fingerprint in before.items():
            if table in RESTORE_RESET_TABLES or table in ('external_snapshots', 'external_oauth_states'):
                self.assertEqual(after[table]['rows'], 0, table)
            elif table not in ('external_connections', 'external_project_links', 'inbound_import_tokens'):
                self.assertEqual(after[table], fingerprint, table)
        office = PostgresOffice(self.candidate)
        try:
            with office.lock, office.db:
                domain = ExternalIntegrations(office)
                for provider, old in data['connections'].items():
                    current = domain.connection(self.actor, provider)
                    self.assertEqual(current['id'], old['id'])
                    self.assertEqual(current['generation'], old['generation'] + 1)
                    self.assertEqual(current['state'], 'disconnected')
                    self.assertFalse(current['configured'])
                    self.assertFalse(current['connected'])
                    for key in ('config', 'credential', 'identity'):
                        self.assertIsNone(current[key])
                    link = domain.binding(self.actor, self.project, provider)
                    self.assertFalse(link['active'])
                    self.assertIsNone(link['remote'])
                    self.assertIsNone(link['data'])
                    self.assertEqual(link['generation'], current['generation'])
                    self.assertEqual(link['revision'], data['snapshots'][provider]['binding']['revision'] + 1)
                    self.assertIsNone(domain.snapshot(self.actor, self.project, provider)['data'])
                    with self.assertRaises(Problem) as stale_connection:
                        domain.put_connection(self.actor, provider, **data['connection_requests'][provider])
                    self.assertEqual(stale_connection.exception.status, 409)
                    request = data['binding_requests'][provider]
                    with self.assertRaises(Problem) as stale_binding:
                        domain.bind(self.actor, self.project, provider, request['remote'], request['data'], **request['args'])
                    self.assertEqual(stale_binding.exception.status, 409)
                for state in data['pending'].values():
                    with self.assertRaises(Problem) as stale_callback:
                        domain.consume_oauth(state['state_hash'])
                    self.assertEqual(stale_callback.exception.status, 400)
                self.assertEqual(office.db.execute("SELECT value FROM secrets WHERE name='onedrive'").fetchone()[0], data['legacy_storage'])
                self.assertTrue(validate_integrity(office))
                validate_bridge(office)
        finally:
            office.db.close()
        self.assert_legacy_preserved(self.candidate, data['legacy'], revoked=True)
        self.assertEqual(release.snapshot_fingerprint(self.candidate), after)
        self.assertEqual(release.snapshot_fingerprint(self.source), before)

    def test_corrupt_snapshot_checksum_rejects_candidate_and_preserves_every_source_row(self):
        self.seed_integrations()
        with psycopg.connect(self.source) as connection:
            connection.execute("UPDATE external_snapshots SET payload_sha256=%s WHERE provider='onedrive'", ('0' * 64,))
        before = release.snapshot_fingerprint(self.source)
        with self.assertRaises(ValueError):
            self.base.prepare()
        self.assertEqual(release.snapshot_fingerprint(self.source), before)

    def test_restore_validates_selected_source_before_sanitizer_can_erase_corrupt_snapshot(self):
        self.seed_integrations()
        with psycopg.connect(self.source) as connection:
            payload = json.loads(connection.execute("SELECT payload_json FROM external_snapshots WHERE provider='onedrive'").fetchone()[0])
            payload['folder']['id'] = 'synthetic-foreign-folder'
            encoded = canonical(payload)
            connection.execute("UPDATE external_snapshots SET payload_json=%s,payload_sha256=%s WHERE provider='onedrive'",
                               (encoded, digest(encoded)))
        before = release.snapshot_fingerprint(self.source)
        saved = release.backup(self.source, self.base.temp.name)
        with self.assertRaises(ValueError):
            restore(saved, self.source, self.candidate)
        # The valid dump/hash cannot hide a selection mismatch. Integrity must
        # reject the separate target before any credential/state sanitization.
        self.assertEqual(release.snapshot_fingerprint(self.candidate), before)
        self.assertEqual(release.snapshot_fingerprint(self.source), before)

    def test_restore_rejects_corrupt_bridge_receipt_before_transient_cleanup(self):
        data = self.seed_integrations()
        with psycopg.connect(self.source) as connection:
            connection.execute('UPDATE external_bridge_jobs SET payload_sha256=%s WHERE id=%s',
                               ('0' * 64, data['bridge']['onedrive']['catalog']['id']))
        before = release.snapshot_fingerprint(self.source)
        saved = release.backup(self.source, self.base.temp.name)
        with self.assertRaises(ValueError):
            restore(saved, self.source, self.candidate)
        self.assertEqual(release.snapshot_fingerprint(self.candidate), before)
        self.assertEqual(release.snapshot_fingerprint(self.source), before)


if __name__ == '__main__':
    unittest.main()
