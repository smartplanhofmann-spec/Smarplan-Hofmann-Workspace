"""Synthetic SQLite persistence, permissions, document scopes and privacy."""
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch
import uuid

from core import Office, Problem
from business_foundation import (BusinessFoundation, ensure_sqlite_schema, permissions,
    require_permission, validate_integrity, methods, dispatch, reapply_privacy_checkpoint)
from project_workspace import ProjectWorkspace


def request(**values):
    return {'request_id': uuid.uuid4().hex, **values}


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic-foundation-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'office.db'
        self.office = Office(self.path)
        self.addCleanup(lambda: self.office.db.close())
        ensure_sqlite_schema(self.office)
        self.api = BusinessFoundation(self.office)
        self.owner = self.actor('owner')
        self.customer = self.office.create_customer(self.owner, {'name': 'Synthetic existing customer', 'email': 'existing@example.test', 'notes': 'OWNER CUSTOMER NOTE'})
        self.project = self.office.add_project(self.owner, 'Synthetic project', customer_id=self.customer['id'])
        self.other = self.office.add_project(self.owner, 'Other synthetic project', 'Other synthetic customer')
        self.manager, self.tech, self.accountant = (self.actor(role, self.project) for role in ('manager', 'technician', 'accountant'))

    def actor(self, role, project=None):
        email = role + '-' + uuid.uuid4().hex[:8] + '@example.test'
        actor = {'id': self.office.add_user(email, 'Synthetic-password-123', role), 'email': email, 'role': role}
        if project:
            self.office.assign(self.owner, project, actor['id'])
        return actor

    def problem(self, status, action):
        with self.assertRaises(Problem) as failure:
            action()
        self.assertEqual(failure.exception.status, status)

    def grant(self, actor, permission, *, scope='*', effect='allow', revision=0):
        return self.api.save_grant(self.owner, request(user_id=actor['id'], permission=permission,
                                                      scope=scope, effect=effect, revision=revision))

    def classify(self, actor, project, kind, identifier, data):
        current = self.api.classification(actor, project, kind, identifier)
        return self.api.classify(actor, project, kind, identifier,
            {**data, 'expected_source_fingerprint': data.get('expected_source_fingerprint', current['source_fingerprint'])})

    def contact_body(self, suffix='one'):
        return request(name='Synthetic detailed customer ' + suffix, email=suffix + '@example.test',
                       kinds=['customer', 'supplier'], tags=['building', 'service'],
                       persons=[{'name': 'Synthetic billing person ' + suffix, 'role_label': 'Billing',
                                 'email': 'billing-' + suffix + '@example.test', 'phone': '+49 000 222222'}],
                       addresses=[{'purpose': 'billing', 'street': 'Synthetic road 17', 'postal_code': '00000',
                                   'city': 'Synthetic city', 'country': 'DE'}])

    def link(self, category='document'):
        with self.office.lock, self.office.db:
            return ProjectWorkspace(self.office).save_item(self.owner, self.project, 'links',
                request(title='SYNTHETIC PRIVATE LINK', category=category, url='https://example.test/doc'))

    def test_current_role_assignment_and_permission_defaults_are_enforced(self):
        self.assertIn('planning.write', permissions(self.office, self.manager))
        for name in ('finance.read', 'personnel.read', 'personnel.manage', 'planning.override'):
            self.problem(403, lambda: require_permission(self.office, self.manager, name, self.project))
        self.assertEqual(require_permission(self.office, self.tech, 'documents.write', self.project)['id'], self.tech['id'])
        self.problem(404, lambda: require_permission(self.office, self.tech, 'documents.read', self.other))
        self.office.assign(self.owner, self.project, self.tech['id'], remove=True)
        self.problem(404, lambda: require_permission(self.office, self.tech, 'documents.read', self.project))
        with self.office.db:
            self.office.db.execute('UPDATE users SET active=0 WHERE id=?', (self.manager['id'],))
        self.problem(401, lambda: self.api.pipeline(self.manager))

    def test_scoped_grants_and_denies_cannot_grant_an_unassigned_project(self):
        self.grant(self.manager, 'finance.read', scope=self.project)
        require_permission(self.office, self.manager, 'finance.read', self.project)
        self.problem(404, lambda: require_permission(self.office, self.manager, 'finance.read', self.other))
        denied = self.grant(self.manager, 'documents.write', scope=self.project, effect='deny')
        self.problem(403, lambda: require_permission(self.office, self.manager, 'documents.write', self.project))
        self.grant(self.manager, 'documents.write', scope=self.project, revision=denied['revision'])
        require_permission(self.office, self.manager, 'documents.write', self.project)
        self.problem(403, lambda: self.api.save_grant(self.manager, request(user_id=self.tech['id'],
            permission='finance.read', scope='*', effect='allow', revision=0)))
        self.grant(self.manager, 'finance.read', effect='deny')
        self.problem(403, lambda: require_permission(self.office, self.manager, 'finance.read', self.project))

    def test_contacts_keep_legacy_ids_relational_children_and_reference_only_receipts(self):
        body = self.contact_body()
        contact = self.api.save_contact(self.owner, body)
        self.assertEqual(self.api.save_contact(self.owner, body), contact)
        self.assertEqual(self.office.customer(self.owner, contact['id'])['email'], 'one@example.test')
        self.assertEqual(contact['kinds'], ['customer', 'supplier'])
        self.assertEqual(len(contact['persons']), 1)
        self.assertEqual(self.api.contacts(self.owner, kind='supplier')['items'], [contact])
        saved = self.office.db.execute('SELECT result_json FROM business_foundation_requests WHERE request_id=?', (body['request_id'],)).fetchone()[0]
        self.assertEqual(json.loads(saved), {'id': contact['id']})
        self.assertNotIn('example.test', saved)
        self.office.db.close()
        self.office = Office(self.path)
        self.api = BusinessFoundation(self.office)
        self.assertEqual(self.api.contact(self.owner, contact['id']), contact)
        self.assertTrue(validate_integrity(self.office))

    def test_contact_scope_and_internal_notes_do_not_become_a_global_addressbook(self):
        self.assertEqual([c['id'] for c in self.api.contacts(self.manager)['items']], [self.customer['id']])
        self.assertEqual(self.api.contacts(self.tech)['items'], [])
        self.assertNotIn('notes', self.api.contact(self.accountant, self.customer['id']))
        self.problem(403, lambda: self.api.save_contact(self.manager, self.contact_body('unauthorized')))
        self.grant(self.tech, 'contacts.read', scope=self.project)
        self.assertEqual(self.api.contact(self.tech, self.customer['id'])['email'], 'existing@example.test')
        self.assertNotIn('notes', self.api.contact(self.tech, self.customer['id']))

    def test_legacy_contact_extension_and_conflicts_preserve_stammdaten_and_history(self):
        legacy = self.api.contact(self.owner, self.customer['id'])
        self.assertEqual(legacy['revision'], 0)
        update = request(revision=0, name='Synthetic renamed customer', persons=[{'name': 'New synthetic person'}])
        changed = self.api.save_contact(self.owner, update, self.customer['id'])
        self.assertEqual(self.office.project(self.owner, self.project)['customer'], changed['name'])
        self.problem(409, lambda: self.api.save_contact(self.owner, request(revision=0, name='Stale'), self.customer['id']))
        self.problem(409, lambda: self.api.save_contact(self.owner, {**update, 'name': 'Changed same request'}, self.customer['id']))
        self.problem(409, lambda: self.api.save_contact(self.owner, request(name=changed['name'])))

    def test_real_legacy_customer_update_invalidates_open_business_revision_and_preserves_children(self):
        current = self.api.save_contact(self.owner, self.contact_body('legacy-race'))
        self.office.update_customer(self.owner, current['id'], {'name': 'Confirmed legacy change'})
        changed = self.api.contact(self.owner, current['id'])
        self.assertEqual(changed['revision'], current['revision'] + 1)
        self.assertEqual(changed['persons'], current['persons'])
        self.assertEqual(changed['addresses'], current['addresses'])
        self.problem(409, lambda: self.api.save_contact(self.owner,
            request(revision=current['revision'], name='Old open business form'), current['id']))
        self.assertEqual(self.api.contact(self.owner, current['id'])['name'], 'Confirmed legacy change')
        self.office.update_customer(self.owner, self.customer['id'], {'phone': '+49 000 555555'})
        self.assertEqual(self.api.contact(self.owner, self.customer['id'])['revision'], 1)
        self.problem(409, lambda: self.api.save_contact(self.owner, request(revision=0, name='Stale legacy baseline'), self.customer['id']))

    def test_down_legacy_edit_up_preserves_confirmed_contact_change_against_stale_business_editor(self):
        import business_foundation as foundation
        import business_schema as schema
        specs = (schema.ModuleSpec('business_foundation', 1, lambda: foundation),)
        with patch.object(schema, 'registry', return_value=specs):
            office = Office(Path(self.temp.name) / 'down-contact.db')
            self.addCleanup(office.db.close)
            schema.ensure_schema(office)
            actor = {'id': office.add_user('down-owner@example.test', 'Synthetic-password-123', 'owner'),
                     'email': 'down-owner@example.test', 'role': 'owner'}
            service = BusinessFoundation(office)
            contact = service.save_contact(actor, self.contact_body('down-source'))
            schema.set_mode(office, 'legacy')
            office.update_customer(actor, contact['id'], {'name': 'Confirmed change in return mode'})
            schema.set_mode(office, 'business')
            self.problem(409, lambda: service.save_contact(actor,
                request(revision=contact['revision'], name='Stale business snapshot'), contact['id']))
            self.assertEqual(service.contact(actor, contact['id'])['name'], 'Confirmed change in return mode')

    def test_contact_child_ids_cannot_be_transplanted_or_late_failure_partially_saved(self):
        first = self.api.save_contact(self.owner, self.contact_body('first'))
        second_body = self.contact_body('second')
        second_body['persons'][0]['id'] = first['persons'][0]['id']
        self.problem(409, lambda: self.api.save_contact(self.owner, second_body))
        before = self.api.contact(self.owner, first['id'])
        audit = self.office.audit
        def fail(actor, action, identifier):
            if action == 'business.contact.updated':
                raise RuntimeError('Synthetic rollback')
            return audit(actor, action, identifier)
        with patch.object(self.office, 'audit', side_effect=fail):
            with self.assertRaises(RuntimeError):
                self.api.save_contact(self.owner, request(revision=1, name='Must roll back'), first['id'])
        self.assertEqual(self.api.contact(self.owner, first['id']), before)

    def test_custom_statuses_allow_arbitrary_movement_without_inventing_acceptance(self):
        a = self.api.save_status(self.owner, request(name='First clarification', position=1))
        b = self.api.save_status(self.owner, request(name='Paused by customer', terminal=True, position=2))
        first = self.api.save_project(self.owner, self.project, request(revision=0, status_id=b['id']))
        back = self.api.save_project(self.manager, self.project, request(revision=first['revision'], status_id=a['id']))
        self.assertEqual(back['status']['id'], a['id'])
        self.assertNotIn('acceptance_channel', back)
        self.assertEqual(self.office.project(self.owner, self.project)['id'], self.project)
        self.problem(403, lambda: self.api.save_status(self.manager, request(name='No admin grant')))
        self.problem(409, lambda: self.api.save_project(self.owner, self.project, request(revision=0, status_id=a['id'])))

    def test_archived_status_preserves_current_project_and_cannot_be_newly_assigned(self):
        status = self.api.save_status(self.owner, request(name='Historic custom status'))
        self.api.save_project(self.owner, self.project, request(revision=0, status_id=status['id']))
        self.api.save_status(self.owner, request(revision=1, active=False), status['id'])
        self.assertFalse(self.api.project(self.owner, self.project)['status']['active'])
        self.problem(409, lambda: self.api.save_project(self.owner, self.other, request(revision=0, status_id=status['id'])))

    def test_shared_description_is_canonical_and_legacy_edits_cannot_be_silently_overwritten(self):
        with self.office.db:
            ProjectWorkspace(self.office).save_profile(self.owner, self.project, request(revision=0,
                description='Existing native description', site_address='Existing native address'))
        profile = self.api.project(self.owner, self.project)
        self.assertEqual((profile['description'], profile['site_address'], profile['workspace_revision']),
                         ('Existing native description', 'Existing native address', 1))
        changed = self.api.save_project(self.manager, self.project, request(revision=0, workspace_revision=1,
            description='Shared updated description'))
        self.assertEqual(ProjectWorkspace(self.office).profile(self.owner, self.project)['description'], changed['description'])
        with self.office.db:
            ProjectWorkspace(self.office).save_profile(self.owner, self.project, request(revision=2, description='Newer native edit'))
        self.problem(409, lambda: self.api.save_project(self.owner, self.project, request(revision=changed['revision'],
            workspace_revision=2, description='Old cached description')))
        self.assertEqual(self.api.project(self.owner, self.project)['description'], 'Newer native edit')

    def test_classification_get_returns_current_revision_without_document_urls_and_requires_classify_right(self):
        link = self.link()
        path = '/documents/link/' + link['id'] + '/classification'
        record, status, media = dispatch(self.office, self.owner, path, 'GET', {})
        self.assertEqual((status, media, record['revision'], record['classification']), (200, 'application/json', 0, 'unclassified'))
        self.assertNotIn('https://', json.dumps(record))
        self.problem(403, lambda: dispatch(self.office, self.tech, path, 'GET', {}))
        self.classify(self.owner, self.project, 'link', link['id'], request(revision=0, classification='operational'))
        record, _, _ = dispatch(self.office, self.owner, path, 'GET', {})
        self.assertEqual(record['revision'], 1)
        self.assertTrue(record['release_current'])

    def test_unknown_original_links_are_not_team_released_and_financial_floor_is_enforced(self):
        link = self.link()
        self.assertFalse(self.api.can_read_document(self.tech, self.project, 'link', link['id']))
        self.assertFalse(self.api.can_read_document(self.accountant, self.project, 'link', link['id']))
        self.assertTrue(self.api.can_read_document(self.owner, self.project, 'link', link['id']))
        released = self.classify(self.owner, self.project, 'link', link['id'], request(revision=0, classification='operational'))
        self.assertEqual(released['classification'], 'operational')
        self.assertTrue(self.api.can_read_document(self.tech, self.project, 'link', link['id']))
        invoice = self.link('invoice')
        self.problem(400, lambda: self.classify(self.owner, self.project, 'link', invoice['id'], request(revision=0, classification='operational')))
        self.assertFalse(self.api.can_read_document(self.tech, self.project, 'link', invoice['id'], category='document'))
        self.problem(403, lambda: self.classify(self.tech, self.project, 'link', link['id'], request(revision=1, classification='financial')))
        self.classify(self.owner, self.project, 'link', invoice['id'], request(revision=0, classification='restricted'))
        self.assertFalse(self.api.can_read_document(self.accountant, self.project, 'link', invoice['id']))

    def test_financial_release_requires_owner_classification_before_assigned_accountant_access(self):
        invoice = self.link('invoice')
        self.assertFalse(self.api.can_read_document(self.accountant, self.project, 'link', invoice['id']))
        self.classify(self.owner, self.project, 'link', invoice['id'], request(revision=0, classification='financial'))
        self.assertTrue(self.api.can_read_document(self.accountant, self.project, 'link', invoice['id']))
        self.assertFalse(self.api.can_read_document(self.tech, self.project, 'link', invoice['id']))
        self.office.assign(self.owner, self.project, self.accountant['id'], remove=True)
        self.assertFalse(self.api.can_read_document(self.accountant, self.project, 'link', invoice['id']))

    def test_mail_classification_only_changes_visibility_not_original_upload_identity_or_bytes(self):
        from inbound_connectors import InboundConnectors
        from inquiries import Inquiries
        from inquiry_attachments import InquiryAttachments
        import hashlib
        connector = InboundConnectors(self.office)
        issued = connector.issue(self.owner, {'name': 'Synthetic mail classifier', 'source_account': 'inbox@example.test'})
        envelope = {'source_account': 'inbox@example.test', 'source_id': 'synthetic-classification-17',
                    'subject': 'Synthetic original', 'message': 'Synthetic classification contract only'}
        receipt = connector.receive_gmail(issued['token'], envelope)
        converted = Inquiries(self.office).convert(self.owner, receipt['id'], request(revision=1,
            project_name='Synthetic classified project', customer_id=self.customer['id']))
        project = converted['project']['id']
        self.office.assign(self.owner, project, self.tech['id'])
        attachments = InquiryAttachments(self.office)
        source = b'SYNTHETIC PRIVATE ORIGINAL BYTES'
        manifest = {'source_account': envelope['source_account'], 'source_id': envelope['source_id'], 'attachments': [{
            'source_attachment_id': 'opaque/provider==17', 'filename': 'Synthetic original.pdf', 'media_type': 'application/pdf',
            'size': len(source), 'sha256': hashlib.sha256(source).hexdigest()}]}
        row = attachments.announce(issued['token'], manifest)['files'][0]
        attachments.put_chunk(issued['token'], row['id'], 0, source)
        attachments.complete(issued['token'], row['id'])
        before = attachments.announce(issued['token'], manifest)
        self.assertFalse(self.api.can_read_document(self.tech, project, 'mail', row['id']))
        self.classify(self.owner, project, 'mail', row['id'], request(revision=0, classification='operational'))
        self.assertTrue(self.api.can_read_document(self.tech, project, 'mail', row['id']))
        self.assertEqual(attachments.announce(issued['token'], manifest), before)
        self.assertEqual(attachments.content_inquiry(self.owner, receipt['id'], row['id'])[0], source)
        self.assertEqual(connector.receive_gmail(issued['token'], envelope)['id'], receipt['id'])

    def test_changing_an_approved_link_invalidates_its_release_even_with_the_same_category(self):
        link = self.link()
        old_source = self.api.classification(self.owner, self.project, 'link', link['id'])['source_fingerprint']
        decision = request(revision=0, classification='operational', expected_source_fingerprint=old_source)
        self.classify(self.owner, self.project, 'link', link['id'], decision)
        stale_dialog = request(revision=1, classification='operational', expected_source_fingerprint=old_source)
        self.assertTrue(self.api.can_read_document(self.tech, self.project, 'link', link['id']))
        with self.office.db:
            ProjectWorkspace(self.office).save_item(self.owner, self.project, 'links',
                request(revision=link['revision'], url='https://example.test/changed-private-file'), link['id'])
        self.assertFalse(self.api.can_read_document(self.tech, self.project, 'link', link['id']))
        self.problem(409, lambda: self.classify(self.owner, self.project, 'link', link['id'], decision))
        self.problem(409, lambda: self.classify(self.owner, self.project, 'link', link['id'], stale_dialog))
        stale_replay = self.api.classification(self.owner, self.project, 'link', link['id'])
        self.assertEqual(stale_replay['classification'], 'unclassified')
        self.assertFalse(stale_replay['release_current'])
        self.classify(self.owner, self.project, 'link', link['id'], request(revision=1, classification='operational'))
        self.assertTrue(self.api.can_read_document(self.tech, self.project, 'link', link['id']))

    def test_restricted_message_replay_does_not_survive_owner_downgrade(self):
        self.office.assign(self.owner, self.project, self.owner['id'])
        body = request(project_id=self.project, text='OWNER ONLY SYNTHETIC DISCUSSION', visibility='restricted')
        self.api.post_message(self.owner, body)
        with self.office.db:
            self.office.db.execute("UPDATE users SET role='manager' WHERE id=?", (self.owner['id'],))
        self.problem(403, lambda: self.api.post_message(self.owner, body))

    def test_invalid_typed_payloads_return_problems_without_mutating_business_data(self):
        for extra in ({'kinds': [{}]}, {'kinds': []}, {'tags': [False]}, {'entity_type': []},
                      {'persons': [{'name': 'Synthetic', 'email': 'invalid'}]},
                      {'addresses': [{'country': 'Germany'}]}, {'name': '\ud800'}):
            with self.subTest(extra=repr(extra)):
                self.problem(400, lambda: self.api.save_contact(self.owner, {**self.contact_body(), **extra}))
        self.problem(400, lambda: self.api.save_project(self.owner, self.project, request(revision=False)))
        self.problem(400, lambda: self.api.save_contact(self.owner, request(revision=False), self.customer['id']))
        self.problem(400, lambda: self.api.contacts(self.owner, kind=[]))
        self.problem(400, lambda: self.api.post_message(self.owner, request(project_id=self.project, text='Synthetic', visibility={})))
        self.assertTrue(validate_integrity(self.office))

    def test_feed_filters_finance_and_personnel_before_limit_and_checks_replay_revocation(self):
        body = request(project_id=self.project, text='Synthetic operational discussion')
        msg = self.api.post_message(self.manager, body)
        self.assertEqual(self.api.post_message(self.manager, body), msg)
        with self.office.db:
            self.api.event(self.owner, self.project, 'invoice.finalized', 'PRIVATE FINANCIAL SUM 12345', visibility='financial')
            self.api.event(self.owner, self.project, 'absence.recorded', 'PRIVATE PERSONNEL DATA', visibility='personnel')
        visible = self.api.feed(self.tech, self.project, limit=1)['items']
        self.assertEqual([row['id'] for row in visible], [msg['id']])
        self.assertNotIn('PRIVATE', json.dumps(visible))
        grant = self.grant(self.manager, 'finance.read', scope=self.project)
        financial = request(project_id=self.project, text='Confirmed finance discussion', visibility='financial')
        self.api.post_message(self.manager, financial)
        self.grant(self.manager, 'finance.read', scope=self.project, effect='deny', revision=grant['revision'])
        self.problem(403, lambda: self.api.post_message(self.manager, financial))

    def test_outer_transaction_does_not_commit_on_nested_business_operations(self):
        self.office.db.execute('BEGIN')
        saved = self.api.save_contact(self.owner, self.contact_body('outer'))
        self.assertTrue(self.office.db.in_transaction)
        self.office.db.rollback()
        self.assertIsNone(self.office.db.execute('SELECT id FROM customers WHERE id=?', (saved['id'],)).fetchone())

    def test_export_is_authorized_explicitly_scoped_and_honest_about_remaining_sources(self):
        self.problem(403, lambda: self.api.export_contact(self.manager, self.customer['id']))
        exported = self.api.export_contact(self.owner, self.customer['id'])
        self.assertEqual(exported['status'], 'review_required')
        self.assertEqual(exported['contact']['id'], self.customer['id'])
        self.assertEqual([p['id'] for p in exported['projects']], [self.project])
        self.assertNotIn('Other synthetic customer', json.dumps(exported))
        self.assertTrue(exported['limitations'])

    def test_linked_contact_erasure_is_blocked_without_fabricated_success(self):
        outcome = self.api.erase_contact(self.owner, self.customer['id'], request(revision=0, confirmed=True))
        self.assertEqual(outcome['status'], 'blocked')
        self.assertTrue(outcome['blockers'])
        self.assertEqual(self.office.customer(self.owner, self.customer['id'])['email'], 'existing@example.test')

    def test_missing_independent_checkpoint_blocks_even_an_isolated_contact(self):
        contact = self.api.save_contact(self.owner, self.contact_body('checkpoint-missing'))
        module = types.SimpleNamespace(checkpoint_before_erasure=lambda *args: (_ for _ in ()).throw(Problem(409, 'not configured')))
        with patch.dict(sys.modules, {'business_schema': module}):
            result = self.api.erase_contact(self.owner, contact['id'], request(revision=1, confirmed=True))
        self.assertEqual(result['status'], 'blocked')
        self.assertTrue(self.api.contact(self.owner, contact['id'])['email'])

    def test_isolated_contact_erasure_clears_personal_children_and_receipts_never_restore_details(self):
        create = self.contact_body('isolated')
        contact = self.api.save_contact(self.owner, create)
        decision = request(revision=1, confirmed=True)
        checkpoint = types.SimpleNamespace(checkpoint_before_erasure=lambda *args: {'digest': 'a' * 64})
        with patch.dict(sys.modules, {'business_schema': checkpoint}):
            result = self.api.erase_contact(self.owner, contact['id'], decision)
            self.assertEqual(self.api.erase_contact(self.owner, contact['id'], decision), result)
        self.assertEqual(result['status'], 'erased')
        erased = self.api.save_contact(self.owner, create)
        self.assertFalse(erased['active'])
        self.assertEqual((erased['email'], erased['phone'], erased['notes'], erased['persons'], erased['addresses']), ('', '', '', [], []))
        self.assertNotIn('isolated@example.test', json.dumps([dict(r) for r in self.office.db.execute('SELECT * FROM business_foundation_requests')]))
        self.assertTrue(validate_integrity(self.office))

    def test_a_new_snapshot_copy_blocks_erasure_instead_of_leaving_hidden_pii(self):
        contact = self.api.save_contact(self.owner, self.contact_body('snapshot'))
        with self.office.db:
            self.office.db.execute('CREATE TABLE synthetic_saved_payload(payload TEXT)')
            self.office.db.execute('INSERT INTO synthetic_saved_payload(payload) VALUES(?)', (json.dumps({'customer': contact['id'], 'email': contact['email']}),))
        result = self.api.erase_contact(self.owner, contact['id'], request(revision=1, confirmed=True))
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('Weitere historische', ' '.join(result['blockers']))

    def test_restore_reapplies_only_safe_isolated_decisions_and_keeps_ids(self):
        contact = self.api.save_contact(self.owner, self.contact_body('restore'))
        module = types.SimpleNamespace(privacy_subject_hash=lambda identifier: 'hash:' + identifier)
        with patch.dict(sys.modules, {'business_schema': module}):
            event = {'operation': 'anonymize_customer', 'subject_hash': 'hash:' + contact['id']}
            self.assertTrue(reapply_privacy_checkpoint(self.office, event))
            self.assertTrue(reapply_privacy_checkpoint(self.office, event))
            with self.assertRaises(ValueError):
                reapply_privacy_checkpoint(self.office, {'operation': 'anonymize_customer', 'subject_hash': 'hash:' + self.customer['id']})
        self.assertEqual(self.api.contact(self.owner, contact['id'])['id'], contact['id'])
        self.assertFalse(self.api.contact(self.owner, contact['id'])['active'])

    @unittest.skipUnless(os.name == 'posix', 'Actual private checkpoint is a Hetzner/POSIX server acceptance; Windows local erasure stays blocked')
    def test_actual_independent_checkpoint_restores_older_database_without_personal_reanimation(self):
        import business_foundation as foundation
        import business_schema as schema
        root = Path(self.temp.name) / 'privacy-integration'
        root.mkdir(mode=0o700)
        key = root / 'synthetic.key'
        key.write_bytes(b'x' * 32)
        key.chmod(0o600)
        settings = {'SMARTPLAN_PRIVACY_CHECKPOINT_FILE': str(root / 'independent.json'),
                    'SMARTPLAN_PRIVACY_CHECKPOINT_KEY_FILE': str(key),
                    'SMARTPLAN_PRIVACY_INSTALLATION_ID': 'f' * 32}
        specs = (schema.ModuleSpec('business_foundation', 1, lambda: foundation),)
        with patch.dict(os.environ, settings), patch.object(schema, 'registry', return_value=specs):
            office = Office(root / 'live.db')
            self.addCleanup(office.db.close)
            schema.ensure_schema(office)
            actor = {'id': office.add_user('privacy-owner@example.test', 'Synthetic-password-123', 'owner'),
                     'email': 'privacy-owner@example.test', 'role': 'owner'}
            service = BusinessFoundation(office)
            create = self.contact_body('real-checkpoint')
            contact = service.save_contact(actor, create)
            schema.initialize_privacy_checkpoint(office)
            older = sqlite3.connect(root / 'older.db')
            older.row_factory = sqlite3.Row
            self.addCleanup(older.close)
            office.db.backup(older)
            outcome = service.erase_contact(actor, contact['id'], request(revision=1, confirmed=True))
            self.assertEqual(outcome['status'], 'erased')
            self.assertEqual(older.execute('SELECT email FROM customers WHERE id=?', (contact['id'],)).fetchone()[0], contact['email'])
            restored = types.SimpleNamespace(db=older, lock=threading.RLock())
            schema.privacy_restore_guard(restored)
            self.assertEqual(older.execute('SELECT email FROM customers WHERE id=?', (contact['id'],)).fetchone()[0], '')
            self.assertTrue(validate_integrity(restored))
            replay = BusinessFoundation(restored).save_contact(actor, create)
            self.assertEqual(replay['id'], contact['id'])
            self.assertEqual(replay['email'], '')
            self.assertNotIn(contact['email'], (root / 'independent.json').read_text())

    def test_route_contracts_and_readonly_integrity(self):
        self.assertEqual(methods('/contacts/' + self.customer['id'] + '/export'), 'GET')
        self.assertEqual(methods('/documents/mail/' + uuid.uuid4().hex + '/classification'), 'GET, POST')
        self.assertIsNone(methods('/intake/gmail'))
        body, status, mime = dispatch(self.office, self.owner, '/contacts', 'GET', {})
        self.assertEqual((status, mime), (200, 'application/json'))
        self.assertIn('items', body)
        self.assertTrue(validate_integrity(self.office))
        self.assertIsNone(dispatch(self.office, self.owner, '/unknown', 'GET', {}))
        status = self.api.save_status(self.owner, request(name='Synthetic validator status'))
        with self.office.db:
            self.office.db.execute('UPDATE business_project_statuses SET color=? WHERE id=?', ('invalid', status['id']))
        with self.assertRaises(ValueError):
            validate_integrity(self.office)


if __name__ == '__main__':
    unittest.main(verbosity=2)
