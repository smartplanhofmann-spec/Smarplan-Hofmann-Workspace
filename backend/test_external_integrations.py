"""Real SQLite integration epochs, scoped snapshots and single-use OAuth state."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid

from cryptography.fernet import Fernet

from core import Office, Problem, canonical, digest
from external_integrations import ExternalIntegrations, ensure_sqlite_schema, validate_integrity, sanitize_after_restore


def request_id():
    return uuid.uuid4().hex


class ExternalIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='smartplan-external-integrations-')
        self.addCleanup(self.temporary.cleanup)
        self.office = Office(Path(self.temporary.name) / 'office.db')
        self.addCleanup(self.office.db.close)
        self.now = [time.time()]
        self.vault = Fernet(Fernet.generate_key())
        uid = self.office.add_user('owner@example.test', 'Synthetic-owner-password-123', 'owner')
        self.owner = dict(id=uid, email='owner@example.test', role='owner')
        self.session = self.office.login('owner@example.test', 'Synthetic-owner-password-123')
        self.project = self.office.add_project(self.owner, 'Synthetic project', 'Synthetic customer')
        self.other = self.office.add_project(self.owner, 'Other synthetic project', 'Other synthetic customer')
        self.api = ExternalIntegrations(self.office, clock=lambda: self.now[0])

    def cipher(self, value='synthetic-provider-secret'):
        return self.vault.encrypt(value.encode()).decode()

    def call(self, method, *args, **kwargs):
        with self.office.lock, self.office.db:
            return getattr(self.api, method)(*args, **kwargs)

    def problem(self, status, action):
        with self.assertRaises(Problem) as caught:
            action()
        self.assertEqual(caught.exception.status, status, caught.exception.message)

    def actor(self, role, *, assigned=True):
        email = role + '-' + request_id()[:8] + '@example.test'
        uid = self.office.add_user(email, 'Synthetic-member-password-123', role)
        actor = dict(id=uid, email=email, role=role)
        if assigned:
            self.office.assign(self.owner, self.project, uid)
        return actor

    def connect(self, provider='onedrive', *, owner=None, account='synthetic-account', request=None):
        owner = owner or self.owner
        current = self.call('connection', owner, provider)
        values = dict(credential=self.cipher(), identity={'id': account, 'label': 'Synthetic account'},
                      expected_generation=current['generation'], request_id=request or request_id())
        if provider != 'sevdesk':
            values['config'] = self.cipher(canonical({'mode': 'bot', 'token_hash': digest('synthetic-bot-token')})
                                           if provider == 'onedrive' else 'synthetic-oauth-client-configuration')
        return self.call('put_connection', owner, provider, **values)

    def selection(self, provider):
        return {
            'onedrive': ('synthetic-folder', {'folder_id': 'synthetic-folder', 'drive_id': 'synthetic-drive'}),
            'sevdesk': ('contact-17', {'contact_id': 'contact-17', 'offer_ids': ['offer-17'], 'invoice_ids': ['invoice-17']}),
            'google_calendar': ('calendar@example.test', {'calendar_id': 'calendar@example.test', 'event_ids': ['event-17']}),
        }[provider]

    def payload(self, provider):
        if provider == 'onedrive':
            return {'folder': {'id': 'synthetic-folder', 'drive_id': 'synthetic-drive', 'name': 'Synthetic folder', 'path': '/Synthetic'},
                    'files': [{'id': 'synthetic-file', 'drive_id': 'synthetic-drive', 'parent_id': 'synthetic-folder',
                               'name': 'synthetic.txt', 'path': '/Synthetic/synthetic.txt', 'rev': 'synthetic-etag-17',
                               'size': 4, 'media_type': 'text/plain',
                               'url': 'https://onedrive.live.com/?id=synthetic-file'}]}
        if provider == 'google_calendar':
            return {'calendar': {'id': 'calendar@example.test', 'name': 'Synthetic calendar', 'time_zone': 'Europe/Berlin'},
                    'events': [{'id': 'event-17', 'title': 'Synthetic all-day survey', 'description': '',
                                'start': '2030-12-12', 'end': '2030-12-13', 'all_day': True,
                                'time_zone': 'Europe/Berlin', 'location': 'Synthetic site', 'status': 'confirmed',
                                'url': 'https://calendar.google.com/calendar/event?eid=synthetic'}]}
        return {'contact': {'id': 'contact-17', 'name': 'Synthetic contact'},
                'offers': [{'id': 'offer-17', 'kind': 'offer', 'number': 'SYN-17', 'title': 'Synthetic offer',
                            'status': 'unknown-17', 'status_label': 'Unbekannter Status (17)', 'date': '2030-12-12',
                            'total_gross': '1234.50', 'currency': 'EUR', 'url': 'https://my.sevdesk.de/#/offers/17'}],
                'invoices': [{'id': 'invoice-17', 'kind': 'invoice', 'number': 'SYN-18', 'title': 'Synthetic invoice',
                              'status': 'draft', 'status_label': 'Entwurf', 'date': '2030-12-13',
                              'total_gross': '7.00', 'currency': 'EUR', 'url': 'https://my.sevdesk.de/#/invoices/17'}]}

    def bind(self, provider='onedrive', *, project=None, connection=None, request=None, revision=0):
        connection = connection or self.connect(provider)
        remote, selection = self.selection(provider)
        return self.call('bind', self.owner, project or self.project, provider, remote, selection,
                         generation=connection['generation'], revision=revision, request_id=request or request_id())

    def snapshot(self, provider='onedrive', *, project=None, binding=None, actor=None, payload=None):
        project = project or self.project
        binding = binding or self.bind(provider, project=project)
        return self.call('save_snapshot', actor or self.owner, project, provider, payload or self.payload(provider),
                         generation=binding['generation'], revision=binding['revision'], synced_at='2030-12-12T10:00:00+01:00')

    def oauth(self, *, provider='google_calendar', state_hash=None):
        connection = self.call('connection', self.owner, provider)
        if not connection['config']:
            connection = self.call('put_connection', self.owner, provider, config=self.cipher('Synthetic client config'),
                                   expected_generation=connection['generation'], request_id=request_id())
        values = dict(state_hash=state_hash or digest(request_id()), session_hash=digest(self.session),
                      config_hash=connection['config_hash'], payload=self.cipher('synthetic-PKCE-verifier'),
                      generation=connection['generation'], expires_at=self.now[0] + 600)
        self.call('put_oauth', self.owner, provider, **values)
        return values

    def test_unconfigured_connections_and_unlinked_projects_have_no_fabricated_data(self):
        for provider in ('onedrive', 'google_calendar', 'sevdesk'):
            row = self.call('connection', self.owner, provider)
            self.assertEqual((row['generation'], row['state'], row['connected']), (0, 'disconnected', False))
            self.assertIsNone(row['credential'])
            self.assertIsNone(self.call('binding', self.owner, self.project, provider))
            snapshot = self.call('snapshot', self.owner, self.project, provider)
            self.assertEqual((snapshot['state'], snapshot['data'], snapshot['synced_at']), ('unlinked', None, None))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM external_connections').fetchone()[0], 0)

    def test_configuration_is_encrypted_and_does_not_connect_until_identity_is_confirmed(self):
        cipher = self.cipher('synthetic-client-secret')
        configured = self.call('put_connection', self.owner, 'google_calendar', config=cipher,
                               expected_generation=0, request_id=request_id())
        self.assertEqual((configured['state'], configured['generation'], configured['connected']), ('configured', 1, False))
        self.assertEqual(configured['config_hash'], hashlib.sha256(cipher.encode()).hexdigest())
        self.problem(400, lambda: self.call('put_connection', self.owner, 'google_calendar', credential=self.cipher(),
                                           expected_generation=1, request_id=request_id()))
        connected = self.call('put_connection', self.owner, 'google_calendar', credential=self.cipher(),
                              identity={'id': 'synthetic-calendar', 'label': 'Synthetic primary calendar'},
                              expected_generation=1, request_id=request_id())
        self.assertEqual((connected['generation'], connected['state']), (2, 'connected'))
        stored = str([dict(row) for row in self.office.db.execute('SELECT * FROM external_connections')])
        self.assertNotIn('synthetic-client-secret', stored)
        self.assertTrue(validate_integrity(self.office))

    def test_connect_retries_survive_randomized_encryption_without_changing_generation_twice(self):
        identifier = request_id()
        semantic = digest('synthetic-exact-connect-request')
        first = self.call('put_connection', self.owner, 'sevdesk', credential=self.cipher(), identity={'id': 'account-A', 'label': 'A'},
                          expected_generation=0, request_id=identifier, request_hash=semantic)
        repeated = self.call('put_connection', self.owner, 'sevdesk', credential=self.cipher(), identity={'id': 'account-A', 'label': 'A'},
                             expected_generation=0, request_id=identifier, request_hash=semantic)
        self.assertEqual(repeated, first)
        self.assertEqual(first['generation'], 1)
        self.problem(409, lambda: self.call('put_connection', self.owner, 'sevdesk', credential=self.cipher(),
                                           identity={'id': 'account-B', 'label': 'B'}, request_id=identifier,
                                           request_hash=digest('different-request')))
        receipt = self.office.db.execute('SELECT result_json FROM external_requests').fetchone()[0]
        self.assertEqual(set(json.loads(receipt)), {'connection_id', 'generation'})
        self.assertNotIn(first['credential'], receipt)
        self.call('disconnect', self.owner, 'sevdesk', request_id(), expected_generation=1)
        self.problem(409, lambda: self.call('put_connection', self.owner, 'sevdesk', credential=self.cipher(),
                                           identity={'id': 'account-A', 'label': 'A'}, expected_generation=0,
                                           request_id=identifier, request_hash=semantic))

    def test_expected_generation_prevents_stale_network_completion_from_replacing_new_account(self):
        first = self.connect()
        self.problem(409, lambda: self.call('put_connection', self.owner, 'onedrive', credential=self.cipher(),
                                           identity={'id': 'account-B', 'label': 'B'}, expected_generation=0, request_id=request_id()))
        self.assertEqual(self.call('connection', self.owner, 'onedrive'), first)

    def test_finance_roles_are_enforced_with_fresh_assignments_and_no_forged_owner_bypass(self):
        self.snapshot('sevdesk')
        self.snapshot('onedrive')
        for role in ('technician', 'manager', 'accountant'):
            actor = self.actor(role)
            self.assertIsNotNone(self.call('snapshot', actor, self.project, 'onedrive')['data'])
            self.problem(403, lambda: self.call('connection', actor, 'onedrive'))
            if role == 'accountant':
                self.assertEqual(self.call('snapshot', actor, self.project, 'sevdesk')['data']['offers'][0]['total_gross'], '1234.50')
            else:
                self.problem(403, lambda: self.call('snapshot', actor, self.project, 'sevdesk'))
                self.problem(403, lambda: self.call('project_connection', actor, self.project, 'sevdesk'))
            self.problem(403, lambda: self.call('unlink', actor, self.project, 'onedrive', generation=1, revision=1, request_id=request_id()))
            self.office.assign(self.owner, self.project, actor['id'], remove=True)
            self.problem(404, lambda: self.call('snapshot', actor, self.project, 'onedrive'))
        outsider = self.actor('technician', assigned=False)
        forged = {**outsider, 'role': 'owner'}
        self.problem(404, lambda: self.call('snapshot', forged, self.project, 'onedrive'))
        self.problem(403, lambda: self.call('connection', forged, 'onedrive'))
        self.problem(401, lambda: self.call('snapshot', 'SPIN_synthetic', self.project, 'onedrive'))

    def test_account_switch_hides_old_link_ids_and_destroys_every_prior_snapshot(self):
        connection = self.connect()
        first = self.bind(connection=connection)
        other = self.bind(project=self.other, connection=connection)
        self.snapshot(binding=first)
        self.snapshot(project=self.other, binding=other)
        switched = self.call('put_connection', self.owner, 'onedrive', credential=self.cipher('new-account-secret'),
                             identity={'id': 'account-B', 'label': 'B'}, expected_generation=1, request_id=request_id())
        self.assertEqual(switched['generation'], 2)
        for project in (self.project, self.other):
            link = self.call('binding', self.owner, project, 'onedrive')
            self.assertEqual((link['state'], link['remote'], link['data']), ('stale', None, None))
            self.assertIsNone(self.call('snapshot', self.owner, project, 'onedrive')['data'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM external_snapshots').fetchone()[0], 0)
        self.problem(409, lambda: self.snapshot(binding=first))
        self.problem(409, lambda: self.call('refresh_credential', self.owner, 'onedrive', self.cipher(), generation=1))
        self.assertTrue(validate_integrity(self.office))

    def test_relink_revision_guards_slow_snapshots_and_errors_and_idempotent_receipts(self):
        connection = self.connect()
        operation = request_id()
        first = self.bind(connection=connection, request=operation)
        self.snapshot(binding=first)
        remote, selection = self.selection('onedrive')
        self.assertEqual(self.call('bind', self.owner, self.project, 'onedrive', remote, selection,
                                   generation=1, revision=0, request_id=operation), first)
        current = self.bind(connection=connection, revision=1)
        self.assertEqual(current['revision'], 2)
        self.assertIsNone(self.call('snapshot', self.owner, self.project, 'onedrive')['data'])
        self.problem(409, lambda: self.snapshot(binding=first))
        self.problem(409, lambda: self.call('record_error', self.owner, self.project, 'onedrive', 'timeout', generation=1, revision=1))
        self.problem(409, lambda: self.call('bind', self.owner, self.project, 'onedrive', remote, selection,
                                           generation=1, revision=0, request_id=operation))

    def test_unlink_is_retry_safe_revisioned_and_cannot_be_undone_by_late_sync(self):
        binding = self.bind()
        self.snapshot(binding=binding)
        identifier = request_id()
        removed = self.call('unlink', self.owner, self.project, 'onedrive', generation=1, revision=1, request_id=identifier)
        self.assertEqual((removed['revision'], removed['state'], removed['data']), (2, 'unlinked', None))
        self.assertEqual(self.call('unlink', self.owner, self.project, 'onedrive', generation=1, revision=1, request_id=identifier), removed)
        self.problem(409, lambda: self.snapshot(binding=binding))
        self.assertIsNone(self.call('snapshot', self.owner, self.project, 'onedrive')['data'])
        self.assertTrue(validate_integrity(self.office))

    def test_refresh_keeps_same_account_epoch_and_confirmed_project_data(self):
        binding = self.bind()
        before = self.snapshot(binding=binding)
        technician = self.actor('technician')
        refreshed = self.call('refresh_credential', technician, 'onedrive', self.cipher('refreshed-secret'),
                              generation=1, project_id=self.project, revision=1)
        self.assertEqual(refreshed['generation'], 1)
        self.assertEqual(self.call('snapshot', technician, self.project, 'onedrive')['data'], before['data'])
        self.problem(403, lambda: self.call('refresh_credential', technician, 'onedrive', self.cipher(), generation=1))
        self.problem(404, lambda: self.call('refresh_credential', technician, 'onedrive', self.cipher(),
                                           generation=1, project_id=self.other, revision=1))

    def test_bot_key_rotation_preserves_account_generation_project_links_and_confirmed_metadata(self):
        for provider in ('google_calendar', 'onedrive'):
            binding = self.bind(provider)
            before = self.snapshot(provider, binding=binding)
            connection = self.call('connection', self.owner, provider)
            if provider == 'google_calendar':
                self.oauth(provider=provider)
            renewed = self.cipher(canonical({'mode': 'bot', 'token_hash': digest('renewed-synthetic-key')}))
            result = self.call('rotate_bridge_config', self.owner, provider, renewed, generation=1)
            for key in ('id', 'owner_id', 'generation', 'credential', 'identity', 'state'):
                self.assertEqual(result[key], connection[key])
            self.assertEqual(result['config'], renewed)
            self.assertEqual(self.call('snapshot', self.owner, self.project, provider), before)
            self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM external_oauth_states WHERE provider=?', (provider,)).fetchone()[0], 0)
            self.assertEqual(self.call('rotate_bridge_config', self.owner, provider, renewed, generation=1), result)
        self.assertEqual(self.office.db.execute("SELECT COUNT(*) FROM audit WHERE action='integration.bridge_key.rotated'").fetchone()[0], 2)
        self.assertTrue(validate_integrity(self.office))

    def test_bot_key_rotation_requires_original_active_owner_existing_config_and_current_generation(self):
        self.problem(409, lambda: self.call('rotate_bridge_config', self.owner, 'onedrive', self.cipher(), generation=0))
        self.connect()
        other = self.actor('owner')
        technician = self.actor('technician')
        self.problem(403, lambda: self.call('rotate_bridge_config', other, 'onedrive', self.cipher(), generation=1))
        self.problem(403, lambda: self.call('rotate_bridge_config', technician, 'onedrive', self.cipher(), generation=1))
        self.problem(409, lambda: self.call('rotate_bridge_config', self.owner, 'onedrive', self.cipher(), generation=0))
        self.problem(400, lambda: self.call('rotate_bridge_config', self.owner, 'sevdesk', self.cipher(), generation=0))
        self.problem(400, lambda: self.call('rotate_bridge_config', self.owner, 'onedrive', None, generation=1))
        with self.office.db:
            self.office.db.execute("UPDATE users SET role='manager' WHERE id=?", (self.owner['id'],))
        self.problem(403, lambda: self.call('rotate_bridge_config', self.owner, 'onedrive', self.cipher(), generation=1))

    def test_bridge_issue_markers_are_terminal_owner_scoped_references_without_key_material(self):
        marker, semantic_hash = request_id(), digest('synthetic-key-issue-request')
        self.problem(409, lambda: self.call('remember_bridge_issue', self.owner, 'onedrive', marker, semantic_hash))
        self.connect()
        other, technician = self.actor('owner'), self.actor('technician')
        self.problem(403, lambda: self.call('remember_bridge_issue', other, 'onedrive', marker, semantic_hash))
        self.problem(403, lambda: self.call('remember_bridge_issue', technician, 'onedrive', marker, semantic_hash))
        self.problem(400, lambda: self.call('remember_bridge_issue', self.owner, 'sevdesk', marker, semantic_hash))
        self.problem(400, lambda: self.call('remember_bridge_issue', self.owner, 'onedrive', marker, 'invalid-hash'))
        connection = self.call('connection', self.owner, 'onedrive')
        before = self.office.db.execute('SELECT COUNT(*) FROM external_requests').fetchone()[0]
        result = self.call('remember_bridge_issue', self.owner, 'onedrive', marker, semantic_hash)
        self.assertEqual(result, {'connection_id': connection['id'], 'generation': connection['generation']})
        receipt = dict(self.office.db.execute('SELECT * FROM external_requests WHERE request_id=?', (marker,)).fetchone())
        self.assertEqual((receipt['provider'], receipt['operation'], receipt['project_id']), ('onedrive', 'connection', None))
        self.assertEqual(json.loads(receipt['result_json']), result)
        self.assertNotIn(connection['config'], str(receipt))
        self.assertNotIn(connection['credential'], str(receipt))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM external_requests').fetchone()[0], before + 1)
        self.problem(409, lambda: self.call('remember_bridge_issue', self.owner, 'onedrive', marker, semantic_hash))
        self.problem(409, lambda: self.call('remember_bridge_issue', self.owner, 'onedrive', marker, digest('changed-request')))
        self.call('put_connection', self.owner, 'onedrive', credential=self.cipher('new-generation-credential'),
                  identity={'id': 'synthetic-account', 'label': 'Synthetic account'}, expected_generation=1)
        self.problem(409, lambda: self.call('remember_bridge_issue', self.owner, 'onedrive', marker, semantic_hash))
        self.assertEqual(dict(self.office.db.execute('SELECT * FROM external_requests WHERE request_id=?', (marker,)).fetchone()), receipt)
        with self.office.lock, self.office.db:
            sanitize_after_restore(self.office)
        self.assertEqual(dict(self.office.db.execute('SELECT * FROM external_requests WHERE request_id=?', (marker,)).fetchone()), receipt)
        self.assertTrue(validate_integrity(self.office))
        with self.office.db:
            self.office.db.execute("UPDATE users SET role='manager' WHERE id=?", (self.owner['id'],))
        self.problem(403, lambda: self.call('remember_bridge_issue', self.owner, 'onedrive', request_id(), semantic_hash))

    def test_deactivated_original_owner_masks_cached_data_and_credentials_before_refresh_or_publish(self):
        binding = self.bind()
        self.snapshot(binding=binding)
        technician = self.actor('technician')
        replacement = self.actor('owner')
        with self.office.db:
            self.office.db.execute('UPDATE users SET active=0 WHERE id=?', (self.owner['id'],))
        view = self.call('project_connection', technician, self.project, 'onedrive')
        self.assertEqual((view['state'], view['connected'], view['credential'], view['identity']), ('reauth_required', False, None, None))
        self.assertIsNone(self.call('snapshot', technician, self.project, 'onedrive')['data'])
        self.problem(409, lambda: self.call('refresh_credential', technician, 'onedrive', self.cipher(),
                                           generation=1, project_id=self.project, revision=1))
        self.problem(409, lambda: self.snapshot(binding=binding, actor=technician))
        self.assertTrue(validate_integrity(self.office))
        new = self.connect(owner=replacement, account='replacement-account')
        self.assertEqual((new['owner_id'], new['generation']), (replacement['id'], 2))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM external_snapshots').fetchone()[0], 0)

    def test_transient_errors_only_show_prior_confirmed_data_for_the_same_active_epoch(self):
        binding = self.bind()
        confirmed = self.snapshot(binding=binding)
        failed = self.call('record_error', self.owner, self.project, 'onedrive', 'timeout', generation=1, revision=1)
        self.assertEqual((failed['state'], failed['error'], failed['data']), ('stale', 'timeout', confirmed['data']))
        technician = self.actor('technician')
        revoked = self.call('invalidate_connection', technician, 'onedrive', generation=1, project_id=self.project, revision=1)
        self.assertEqual((revoked['generation'], revoked['state'], revoked['credential']), (2, 'reauth_required', None))
        self.assertIsNone(self.call('snapshot', technician, self.project, 'onedrive')['data'])
        self.assertTrue(validate_integrity(self.office))

    def test_snapshots_cannot_smuggle_unselected_documents_events_or_other_folder_ids(self):
        for provider in ('sevdesk', 'google_calendar', 'onedrive'):
            binding = self.bind(provider)
            good = self.snapshot(provider, binding=binding)
            bad = deepcopy(self.payload(provider))
            if provider == 'sevdesk':
                bad['invoices'][0]['id'] = 'unselected-invoice'
            elif provider == 'google_calendar':
                bad['events'][0]['id'] = 'unselected-event'
            else:
                bad['folder']['id'] = 'another-folder'
            self.problem(409, lambda: self.snapshot(provider, binding=binding, payload=bad))
            self.assertEqual(self.call('snapshot', self.owner, self.project, provider)['data'], good['data'])
        bad_money = self.payload('sevdesk')
        bad_money['offers'][0]['total_gross'] = 1234.50
        self.problem(400, lambda: self.call('save_snapshot', self.owner, self.project, 'sevdesk', bad_money,
                                           generation=1, revision=1, synced_at='2030-12-12T09:00:00Z'))

    def test_json_limits_wrong_metadata_membership_and_credentials_are_rejected_without_cache_changes(self):
        binding = self.bind()
        for field, value, status in (('drive_id', 'wrong-drive', 409), ('parent_id', 'wrong-parent', 409),
                                     ('size', True, 400), ('rev', '', 400), ('url', 'https://example.test/private-file', 400)):
            bad = self.payload('onedrive')
            bad['files'][0][field] = value
            self.problem(status, lambda: self.snapshot(binding=binding, payload=bad))
        bad = self.payload('onedrive')
        bad['files'][0]['content_hash'] = 'b' * 64
        self.problem(400, lambda: self.snapshot(binding=binding, payload=bad))
        bad = self.payload('onedrive')
        bad['files'][0]['access_token'] = 'never-store-this'
        self.problem(400, lambda: self.snapshot(binding=binding, payload=bad))
        bad = self.payload('onedrive')
        bad['folder']['name'] = 'x' * (2 * 1024 * 1024)
        self.problem(413, lambda: self.snapshot(binding=binding, payload=bad))
        self.assertIsNone(self.call('snapshot', self.owner, self.project, 'onedrive')['data'])
        self.problem(400, lambda: self.call('put_connection', self.owner, 'sevdesk', credential='plaintext-token',
                                           identity={'id': 'one', 'label': 'One'}, request_id=request_id()))

    def test_onedrive_snapshot_accepts_a_large_bounded_metadata_list_without_invented_hashes(self):
        binding = self.bind()
        payload = self.payload('onedrive')
        original = payload['files'][0]
        payload['files'] = [{**original, 'id': 'file-' + str(index), 'name': f'file-{index}.txt',
                             'path': f'/Synthetic/file-{index}.txt',
                             'url': f'https://onedrive.live.com/?id=synthetic-file-{index}'} for index in range(501)]
        saved = self.snapshot(binding=binding, payload=payload)
        self.assertEqual(len(saved['data']['files']), 501)
        self.assertTrue(validate_integrity(self.office))

    def test_malformed_selected_ids_return_safe_validation_errors_without_snapshot_mutations(self):
        for provider in ('sevdesk', 'google_calendar'):
            binding = self.bind(provider)
            payload = self.payload(provider)
            items = payload['offers'] if provider == 'sevdesk' else payload['events']
            items[0]['id'] = {'not': 'an-opaque-id'}
            self.problem(400, lambda: self.snapshot(provider, binding=binding, payload=payload))
            self.assertIsNone(self.call('snapshot', self.owner, self.project, provider)['data'])

    def test_oauth_state_is_encrypted_session_bound_and_consumed_exactly_once(self):
        values = self.oauth()
        stored = dict(self.office.db.execute('SELECT * FROM external_oauth_states').fetchone())
        self.assertNotIn(self.session, str(stored))
        self.assertNotIn('synthetic-PKCE-verifier', str(stored))
        pending = self.call('consume_oauth', values['state_hash'])
        self.assertTrue(pending['valid'])
        self.assertEqual(pending['actor']['id'], self.owner['id'])
        self.assertEqual(self.vault.decrypt(pending['payload'].encode()).decode(), 'synthetic-PKCE-verifier')
        self.problem(400, lambda: self.call('consume_oauth', values['state_hash']))
        self.assertTrue(validate_integrity(self.office))

    def test_expired_or_logged_out_oauth_is_consumed_without_returning_verifier_or_configuration(self):
        for expire in (False, True):
            values = self.oauth()
            if expire:
                self.now[0] += 601
            else:
                with self.office.db:
                    self.office.db.execute('DELETE FROM sessions WHERE token=?', (digest(self.session),))
            pending = self.call('consume_oauth', values['state_hash'])
            self.assertFalse(pending['valid'])
            self.assertIsNone(pending['payload'])
            self.assertIsNone(pending['connection'])
            self.problem(400, lambda: self.call('consume_oauth', values['state_hash']))
            self.session = self.office.login('owner@example.test', 'Synthetic-owner-password-123')

    def test_oauth_config_switch_purges_pending_state_and_role_change_never_authorizes_it(self):
        values = self.oauth()
        self.call('put_connection', self.owner, 'google_calendar', config=self.cipher('new-client-config'),
                  expected_generation=1, request_id=request_id())
        self.problem(400, lambda: self.call('consume_oauth', values['state_hash']))
        values = self.oauth()
        with self.office.db:
            self.office.db.execute("UPDATE users SET role='manager' WHERE id=?", (self.owner['id'],))
        pending = self.call('consume_oauth', values['state_hash'])
        self.assertFalse(pending['valid'])
        self.assertIsNone(pending['payload'])

    def test_oauth_live_state_budget_is_bounded_and_expired_rows_allow_new_flow(self):
        for _ in range(20):
            self.oauth()
        self.problem(429, self.oauth)
        self.now[0] += 601
        self.oauth()
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM external_oauth_states').fetchone()[0], 1)
        self.assertTrue(validate_integrity(self.office))

    def test_restore_erases_all_external_access_and_old_receipts_cannot_reactivate_it(self):
        identifier = request_id()
        connection = self.connect(request=identifier)
        binding = self.bind(connection=connection)
        self.snapshot(binding=binding)
        self.oauth()
        before = {table: self.office.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]
                  for table in ('audit', 'external_requests')}
        with self.office.lock, self.office.db:
            self.assertTrue(validate_integrity(self.office))
            sanitize_after_restore(self.office)
        for provider in ('onedrive', 'google_calendar'):
            current = self.call('connection', self.owner, provider)
            self.assertIsNone(current['config'])
            self.assertIsNone(current['credential'])
            self.assertIsNone(current['identity'])
            self.assertEqual(current['state'], 'disconnected')
        link = self.call('binding', self.owner, self.project, 'onedrive')
        self.assertEqual((link['active'], link['revision'], link['data']), (False, 2, None))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM external_oauth_states').fetchone()[0], 0)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM external_snapshots').fetchone()[0], 0)
        self.assertEqual({table: self.office.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0] for table in before}, before)
        self.assertTrue(validate_integrity(self.office))
        self.problem(409, lambda: self.call('put_connection', self.owner, 'onedrive', config=connection['config'],
                                           credential=connection['credential'], identity=connection['identity'],
                                           expected_generation=0, request_id=identifier))

    def test_integrity_detects_snapshot_hash_selection_and_receipt_corruption(self):
        binding = self.bind()
        self.snapshot(binding=binding)
        changes = [
            ('UPDATE external_snapshots SET payload_sha256=?', ('0' * 64,)),
            ('UPDATE external_snapshots SET revision=2', ()),
            ('UPDATE external_project_links SET selection_json=?', (canonical({'folder_id': 'another-folder'}),)),
            ('UPDATE external_requests SET result_json=?', (canonical({'connection_id': 'a' * 32, 'generation': 99}),)),
            ('UPDATE external_connections SET credential_cipher=?', ('plaintext-secret',)),
        ]
        for query, values in changes:
            with self.subTest(query=query):
                self.office.db.execute('BEGIN')
                self.office.db.execute(query, values)
                with self.assertRaises(ValueError):
                    validate_integrity(self.office)
                self.office.db.rollback()
                self.assertTrue(validate_integrity(self.office))

    def test_late_failure_rolls_back_new_account_snapshot_invalidation_and_receipts(self):
        binding = self.bind()
        confirmed = self.snapshot(binding=binding)
        counts = {table: self.office.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]
                  for table in ('audit', 'external_requests')}
        with patch.object(self.office, 'audit', side_effect=RuntimeError('Synthetic late audit failure')):
            with self.assertRaises(RuntimeError):
                self.call('put_connection', self.owner, 'onedrive', credential=self.cipher(),
                          identity={'id': 'new-account', 'label': 'New'}, expected_generation=1, request_id=request_id())
        self.assertEqual(self.call('connection', self.owner, 'onedrive')['generation'], 1)
        self.assertEqual(self.call('snapshot', self.owner, self.project, 'onedrive')['data'], confirmed['data'])
        self.assertEqual({table: self.office.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0] for table in counts}, counts)
        self.assertTrue(validate_integrity(self.office))

    def test_explicit_caller_transaction_can_rollback_binding_and_receipt_together(self):
        connection = self.connect()
        self.office.db.execute('BEGIN')
        remote, selection = self.selection('onedrive')
        self.api.bind(self.owner, self.project, 'onedrive', remote, selection,
                      generation=connection['generation'], revision=0, request_id=request_id())
        self.assertTrue(self.office.db.in_transaction)
        self.office.db.rollback()
        self.assertIsNone(self.call('binding', self.owner, self.project, 'onedrive'))
        ensure_sqlite_schema(self.office)
        self.assertTrue(validate_integrity(self.office))


if __name__ == '__main__':
    unittest.main(verbosity=2)
