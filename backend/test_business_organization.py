"""Company setup, permissions and durable history with synthetic records only."""
import copy
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import uuid

import business_api
import business_schema
from business_foundation import BusinessFoundation
from business_organization import Organization, validate_integrity
from core import Office, Problem


class OrganizationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='synthetic-organization-')
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / 'office.db'
        self.office = Office(self.path)
        self.addCleanup(lambda: self.office.db.close())
        self.owner = self.actor('owner')
        self.tech = self.actor('technician')
        self.organization = Organization(self.office)

    def actor(self, role):
        email = role + '@example.test'
        return dict(id=self.office.add_user(email, 'Synthetic-password-123', role), email=email, role=role)

    def body(self):
        value = self.organization.get(self.owner)
        return dict(request_id=uuid.uuid4().hex, revision=value['revision'], needs=value['needs'],
            modules={key: dict(visible=item['visibility_override'], enabled=item['enabled'])
                     for key, item in value['modules'].items()})

    def call(self, path, method='GET', data=None, actor=None):
        return business_api.dispatch(self.office, actor or self.owner, '/business' + path, method, data or {})[0]

    def employee(self):
        return self.call('/employees', 'POST', dict(request_id=uuid.uuid4().hex,
            user_id=self.tech['id'], name='Synthetic employee'))

    def problem(self, status, action):
        with self.assertRaises(Problem) as caught:
            action()
        self.assertEqual(caught.exception.status, status)

    def test_single_company_suggestions_follow_employee_creation_without_changing_rights(self):
        before = self.call('/organization')
        self.assertFalse(before['configured'])
        self.assertFalse(before['modules']['personnel']['visible'])
        self.assertTrue(before['modules']['personnel']['enabled'])
        self.employee()
        after = self.call('/organization')
        self.assertTrue(after['modules']['personnel']['suggested'])
        self.assertTrue(after['modules']['personnel']['visible'])
        self.assertEqual(after['active_employee_count'], 1)
        metadata = self.call('/capabilities', actor=self.tech)
        self.assertNotIn('personnel.manage', metadata['permissions'])
        self.assertNotIn('active_employee_count', metadata['organization'])
        self.assertNotIn('needs', metadata['organization'])
        self.problem(403, lambda: self.call('/organization', actor=self.tech))

    def test_manual_visibility_survives_employees_and_database_restart(self):
        body = self.body()
        body['modules']['personnel']['visible'] = False
        self.call('/organization', 'POST', body)
        saved = self.employee()
        self.office.db.close()
        self.office = Office(self.path)
        self.organization = Organization(self.office)
        view = self.call('/organization')
        self.assertFalse(view['modules']['personnel']['visible'])
        self.assertTrue(view['modules']['personnel']['suggested'])
        self.assertEqual(self.call('/employees')['items'][0]['id'], saved['id'])
        automatic = self.body()
        automatic['modules']['personnel']['visible'] = None
        self.assertTrue(self.call('/organization', 'POST', automatic)['modules']['personnel']['visible'])
        validate_integrity(self.office)

    def test_deactivation_blocks_direct_writes_but_preserves_authorized_history(self):
        employee = self.employee()
        body = self.body()
        body['modules']['personnel'] = dict(visible=False, enabled=False)
        self.call('/organization', 'POST', body)
        self.assertEqual(self.call('/employees')['items'][0]['id'], employee['id'])
        self.problem(423, lambda: self.call('/employees', 'POST', dict(request_id=uuid.uuid4().hex,
            user_id=self.owner['id'], name='Must not be created')))
        self.problem(423, lambda: self.call('/time/events', 'POST', {'request_id': uuid.uuid4().hex}))
        self.assertEqual(self.office.db.execute('SELECT count(*) FROM business_employees').fetchone()[0], 1)
        enabled = self.body()
        enabled['modules']['personnel']['enabled'] = True
        self.call('/organization', 'POST', enabled)
        self.assertEqual(self.call('/employees')['items'][0]['id'], employee['id'])

    def test_visibility_does_not_grant_financial_or_personnel_access(self):
        body = self.body()
        for value in body['modules'].values():
            value['visible'] = True
        self.call('/organization', 'POST', body)
        self.problem(403, lambda: self.call('/finance/open-items', actor=self.tech))
        self.problem(403, lambda: self.call('/employees', 'POST', dict(request_id=uuid.uuid4().hex,
            user_id=self.tech['id'], name='Unauthorized'), actor=self.tech))
        self.problem(403, lambda: self.call('/organization', 'POST', body, actor=self.tech))

    def test_disabled_module_cannot_be_written_through_adapter_helpers(self):
        body = self.body()
        body['modules']['documents']['enabled'] = False
        self.call('/organization', 'POST', body)
        for path in ('/articles', '/documents', '/adapters/imports/' + 'a' * 32 + '/apply',
                     '/adapters/imports/' + 'a' * 32 + '/offer'):
            with self.subTest(path=path):
                self.problem(423, lambda: self.call(path, 'POST', {'request_id': uuid.uuid4().hex}))

    def test_committed_time_retry_survives_deactivation_new_event_waits_until_reenabled(self):
        employee = self.employee()
        project = self.office.add_project(self.owner, 'Synthetic time project', 'Synthetic customer')
        self.office.assign(self.owner, project, self.tech['id'])
        start = dict(request_id=uuid.uuid4().hex, entry_id=uuid.uuid4().hex, employee_id=employee['id'],
                     device_id=uuid.uuid4().hex, project_id=project, action='start',
                     occurred_at='2026-11-02T08:00:00+00:00', sequence=1, revision=0)
        saved = self.call('/time/events', 'POST', start, actor=self.tech)
        body = self.body()
        body['modules']['personnel']['enabled'] = False
        self.call('/organization', 'POST', body)
        replay = self.call('/time/events', 'POST', start, actor=self.tech)
        self.assertTrue(replay['idempotent'])
        self.assertEqual(replay['entry']['id'], saved['entry']['id'])
        changed = dict(start, occurred_at='2026-11-02T07:00:00+00:00')
        self.problem(409, lambda: self.call('/time/events', 'POST', changed, actor=self.tech))
        stop = dict(start, request_id=uuid.uuid4().hex, action='stop', sequence=2, revision=1,
                    occurred_at='2026-11-02T09:00:00+00:00')
        self.problem(423, lambda: self.call('/time/events', 'POST', stop, actor=self.tech))
        body = self.body()
        body['modules']['personnel']['enabled'] = True
        self.call('/organization', 'POST', body)
        finished = self.call('/time/events', 'POST', stop, actor=self.tech)
        self.assertEqual(finished['entry']['status'], 'stopped')
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_time_events').fetchone()[0], 2)

    def test_granted_settings_right_is_rechecked_before_replay(self):
        foundation = BusinessFoundation(self.office)
        grant = foundation.save_grant(self.owner, dict(request_id=uuid.uuid4().hex, revision=0,
            user_id=self.tech['id'], permission='settings.manage', scope='*', effect='allow'))
        body = self.body()
        self.call('/organization', 'POST', body, actor=self.tech)
        foundation.save_grant(self.owner, dict(request_id=uuid.uuid4().hex, revision=grant['revision'],
            user_id=self.tech['id'], permission='settings.manage', scope='*', effect='deny'))
        self.problem(403, lambda: self.call('/organization', 'POST', body, actor=self.tech))

    def test_lost_response_retry_cannot_overwrite_a_later_version(self):
        body = self.body()
        first = self.call('/organization', 'POST', body)
        changed = self.body()
        changed['modules']['finance']['visible'] = False
        second = self.call('/organization', 'POST', changed)
        repeated = self.call('/organization', 'POST', body)
        self.assertEqual(first, repeated)
        self.assertEqual(second, self.call('/organization'))
        conflict = copy.deepcopy(body)
        conflict['needs']['has_employees'] = True
        self.problem(409, lambda: self.call('/organization', 'POST', conflict))
        stale = copy.deepcopy(body)
        stale['request_id'] = uuid.uuid4().hex
        self.problem(409, lambda: self.call('/organization', 'POST', stale))
        self.assertEqual(self.office.db.execute('SELECT count(*) FROM business_organization_events').fetchone()[0], 2)

    def test_invalid_choices_are_rejected_atomically(self):
        for key, value in [('revision', True), ('needs', {}), ('modules', {}), ('request_id', 'invalid')]:
            with self.subTest(key=key):
                body = self.body()
                body[key] = value
                self.problem(400, lambda: self.call('/organization', 'POST', body))
        for value in [0, 'automatic', [], {}]:
            body = self.body()
            body['modules']['finance']['visible'] = value
            self.problem(400, lambda: self.call('/organization', 'POST', body))
        self.assertEqual(self.call('/organization')['revision'], 0)

    def test_receipt_failure_rolls_back_config_history_and_audit(self):
        self.office.db.execute("CREATE TRIGGER synthetic_fail_organization BEFORE INSERT ON business_organization_requests "
                               "BEGIN SELECT RAISE(ABORT,'synthetic failed write'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.call('/organization', 'POST', self.body())
        self.assertEqual(self.call('/organization')['revision'], 0)
        self.assertEqual(self.office.db.execute('SELECT count(*) FROM business_organization_events').fetchone()[0], 0)
        self.assertEqual(self.office.db.execute("SELECT count(*) FROM audit WHERE action='organization.settings.changed'").fetchone()[0], 0)

    def test_legacy_mode_allows_history_not_settings_changes(self):
        self.call('/organization', 'POST', self.body())
        business_schema.set_mode(self.office, 'legacy')
        self.assertEqual(self.call('/organization')['revision'], 1)
        self.problem(409, lambda: self.call('/organization', 'POST', self.body()))

    def test_offline_tokens_do_not_receive_or_change_company_configuration(self):
        metadata, _, _ = business_api.dispatch(self.office, self.owner, '/business/capabilities', 'GET', {},
                                               offline=True, offline_capabilities=['time_events'])
        self.assertNotIn('organization', metadata)
        for method in ('GET', 'POST'):
            self.problem(403, lambda: business_api.dispatch(self.office, self.owner, '/business/organization', method,
                self.body() if method == 'POST' else {}, offline=True, offline_capabilities=['time_events']))

    def test_corrupted_configuration_history_fails_validation(self):
        self.call('/organization', 'POST', self.body())
        with self.office.db:
            self.office.db.execute("UPDATE business_organization_settings SET needs_json='{}'")
        with self.assertRaises(ValueError):
            validate_integrity(self.office)

    def test_new_module_migration_preserves_existing_schema_seven_records(self):
        old_specs = tuple(spec for spec in business_schema.registry()
                          if spec.name not in ('business_organization', 'business_instance'))
        old_path = Path(self.temporary.name) / 'previous-seven.db'
        with patch.object(business_schema, 'registry', return_value=old_specs):
            old = Office(old_path)
            actor = dict(id=old.add_user('legacy@example.test', 'Synthetic-password-123', 'owner'), role='owner')
            project = old.add_project(actor, 'Synthetic retained project', 'Synthetic retained customer')
            draft = old.draft(actor, project, 'Servicebericht', 'Synthetic retained signed description')
            signed = old.sign(actor, draft['id'], draft['content_hash'], 'Synthetic signer', [[[0.1, 0.2], [0.8, 0.9]]])
            original_pdf = old.pdf(actor, signed['id'])
            original_payload = old.db.execute('SELECT payload FROM reports WHERE id=?', (signed['id'],)).fetchone()[0]
            old.db.close()
        migrated = Office(old_path)
        self.addCleanup(migrated.db.close)
        self.assertEqual(migrated.pdf(actor, signed['id']), original_pdf)
        self.assertEqual(migrated.db.execute('SELECT payload FROM reports WHERE id=?', (signed['id'],)).fetchone()[0], original_payload)
        self.assertEqual(Organization(migrated).get(actor)['revision'], 0)
        business_schema.validate_integrity(migrated)


if __name__ == '__main__':
    unittest.main()
