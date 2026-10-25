"""Project-scoped billing snapshots; synthetic contacts only, no provider IO."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from core import Office, Problem
from business_foundation import BusinessFoundation, methods, dispatch


def request(**values):
    return {'request_id': uuid.uuid4().hex, **values}


class BillingFixture:
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='synthetic-billing-contact-')
        self.addCleanup(self.temporary.cleanup)
        self.office = Office(Path(self.temporary.name) / 'office.db')
        self.addCleanup(self.office.db.close)
        self.api = BusinessFoundation(self.office)
        self.owner = self.actor('owner')
        self.customer = self.api.save_contact(self.owner, request(
            name='Synthetic Buyer GmbH', email='main@example.test', contact='Synthetic main contact',
            address='Unstructured legacy address, must not become postal code or city',
            notes='SECRET OWNER NOTE',
            persons=[{'name': 'Synthetic Billing Person', 'role_label': 'Buchhaltung', 'email': 'billing@example.test', 'phone': 'SECRET BILLING PHONE'},
                     {'name': 'SECRET PRIVATE PERSON', 'role_label': 'Privat', 'email': 'private@example.test', 'phone': 'SECRET PRIVATE PHONE'}],
            addresses=[{'purpose': 'site', 'label': 'SECRET SITE LABEL', 'street': 'SECRET SITE STREET', 'postal_code': '99999', 'city': 'SECRET SITE CITY', 'country': 'DE'},
                       {'purpose': 'billing', 'label': 'Synthetic billing', 'street': 'Synthetic Billing Road 17', 'postal_code': '10117', 'city': 'Berlin', 'country': 'DE'}]))
        self.project = self.office.add_project(self.owner, 'Synthetic customer project', customer_id=self.customer['id'])
        self.other = self.office.add_project(self.owner, 'Other synthetic project', 'Other synthetic customer')
        self.accountant = self.actor('accountant', self.project)

    def actor(self, role, project=None):
        email = role + '-' + uuid.uuid4().hex[:8] + '@example.test'
        identifier = self.office.add_user(email, 'Synthetic-password-123', role)
        actor = {'id': identifier, 'email': email, 'role': role}
        if project:
            self.office.assign(self.owner, project, identifier)
        return actor

    def problem(self, status, action):
        with self.assertRaises(Problem) as failure:
            action()
        self.assertEqual(failure.exception.status, status)

    def update(self, **changes):
        current = self.api.contact(self.owner, self.customer['id'])
        self.customer = self.api.save_contact(self.owner, request(revision=current['revision'], **changes), self.customer['id'])
        return self.customer


class BillingContactTests(BillingFixture, unittest.TestCase):
    def test_current_structured_billing_snapshot_is_minimal_and_entirely_read_only(self):
        changes = self.office.db.total_changes
        value = self.api.billing_contact(self.accountant, self.project)
        self.assertEqual(value['buyer'], {'name': 'Synthetic Buyer GmbH', 'contact_name': 'Synthetic Billing Person',
            'address_line': 'Synthetic Billing Road 17', 'postal_code': '10117', 'city': 'Berlin', 'country': 'DE',
            'email': 'billing@example.test', 'vat_id': '', 'endpoint_id': '', 'endpoint_scheme': ''})
        self.assertEqual(value['contact_id'], self.customer['id'])
        self.assertEqual(value['contact_revision'], self.customer['revision'])
        self.assertRegex(value['source_fingerprint'], r'^[a-f0-9]{64}$')
        self.assertEqual(value, self.api.billing_contact(self.accountant, self.project))
        self.assertTrue(value['completeness']['ready_for_invoice'])
        self.assertEqual(value['completeness']['status'], 'complete')
        self.assertIn('vat_id', value['completeness']['optional_unavailable'])
        self.assertNotIn('SECRET', json.dumps(value))
        self.assertNotIn('private@example.test', json.dumps(value))
        self.assertEqual(self.office.db.total_changes, changes)

    def test_snapshot_refresh_observes_current_contact_revision_without_mutating_an_older_copy(self):
        first = self.api.billing_contact(self.owner, self.project)
        addresses = self.customer['addresses']
        addresses[1]['street'] = 'Synthetic updated billing road 18'
        self.update(name='Synthetic Updated Buyer GmbH', addresses=addresses)
        second = self.api.billing_contact(self.owner, self.project)
        self.assertGreater(second['contact_revision'], first['contact_revision'])
        self.assertNotEqual(second['source_fingerprint'], first['source_fingerprint'])
        self.assertEqual(first['buyer']['name'], 'Synthetic Buyer GmbH')
        self.assertEqual(second['buyer']['address_line'], 'Synthetic updated billing road 18')
        self.office.update_customer(self.owner, self.customer['id'], {'name': 'Synthetic Legacy Confirmed Change'})
        self.assertGreater(self.api.billing_contact(self.owner, self.project)['contact_revision'], second['contact_revision'])

    def test_multiple_billing_addresses_need_explicit_selection_and_foreign_or_site_ids_are_never_used(self):
        addresses = self.customer['addresses'] + [{'purpose': 'billing', 'label': 'Second billing', 'street': 'Synthetic Other Billing 2', 'postal_code': '20202', 'city': 'Synthetic town', 'country': 'DE'}]
        self.update(addresses=addresses)
        ambiguous = self.api.billing_contact(self.owner, self.project)
        self.assertEqual(ambiguous['buyer']['address_line'], '')
        self.assertEqual(ambiguous['completeness']['status'], 'selection_required')
        self.assertFalse(ambiguous['completeness']['ready_for_invoice'])
        self.assertEqual(len(ambiguous['address_options']), 2)
        chosen = ambiguous['address_options'][1]['id']
        selected = self.api.billing_contact(self.owner, self.project, address_id=chosen)
        self.assertEqual(selected['buyer']['address_line'], 'Synthetic Other Billing 2')
        self.assertTrue(selected['completeness']['ready_for_invoice'])
        self.problem(404, lambda: self.api.billing_contact(self.owner, self.project, address_id=self.customer['addresses'][0]['id']))
        self.problem(404, lambda: self.api.billing_contact(self.owner, self.other, address_id=chosen))

    def test_legacy_address_is_not_split_and_site_address_does_not_fill_billing_gaps(self):
        self.update(addresses=[self.customer['addresses'][0]], persons=[])
        value = self.api.billing_contact(self.owner, self.project)
        self.assertEqual(value['buyer']['address_line'], self.customer['address'])
        self.assertEqual((value['buyer']['postal_code'], value['buyer']['city'], value['buyer']['country']), ('', '', ''))
        self.assertEqual(value['completeness']['address_status'], 'legacy_unstructured')
        self.assertEqual(set(value['completeness']['missing_fields']), {'postal_code', 'city', 'country'})
        self.assertFalse(value['completeness']['ready_for_invoice'])
        self.assertNotIn('SECRET SITE', json.dumps(value))

    def test_fresh_finance_scope_denies_unassigned_roles_revoked_grants_and_inactive_actors(self):
        manager = self.actor('manager', self.project)
        self.problem(403, lambda: self.api.billing_contact(manager, self.project))
        self.problem(404, lambda: self.api.billing_contact(self.accountant, self.other))
        grant = self.api.save_grant(self.owner, request(user_id=manager['id'], permission='finance.read', scope=self.project, effect='allow', revision=0))
        self.api.billing_contact(manager, self.project)
        self.api.save_grant(self.owner, request(user_id=manager['id'], permission='finance.read', scope=self.project, effect='deny', revision=grant['revision']))
        self.problem(403, lambda: self.api.billing_contact(manager, self.project))
        self.office.assign(self.owner, self.project, self.accountant['id'], remove=True)
        self.problem(404, lambda: self.api.billing_contact(self.accountant, self.project))
        with self.office.db:
            self.office.db.execute('UPDATE users SET active=0 WHERE id=?', (manager['id'],))
        self.problem(401, lambda: self.api.billing_contact(manager, self.project))

    def test_billing_person_ambiguity_does_not_choose_a_private_or_arbitrary_recipient(self):
        people = self.customer['persons'] + [{'name': 'Second Billing Person', 'role_label': 'Billing', 'email': 'second-billing@example.test', 'phone': ''}]
        self.update(persons=people)
        value = self.api.billing_contact(self.owner, self.project)
        self.assertIsNone(value['selected_person_id'])
        self.assertEqual(value['buyer']['contact_name'], '')
        self.assertEqual(value['buyer']['email'], 'main@example.test')
        self.assertEqual(value['completeness']['person_status'], 'selection_required')
        self.assertEqual({p['name'] for p in value['person_options']}, {'Synthetic Billing Person', 'Second Billing Person'})
        self.assertNotIn('private@example.test', json.dumps(value))
        selected = self.api.billing_contact(self.owner, self.project, person_id=self.customer['persons'][2]['id'])
        self.assertEqual(selected['buyer']['email'], 'second-billing@example.test')
        self.problem(404, lambda: self.api.billing_contact(self.owner, self.other, person_id=self.customer['persons'][2]['id']))

    def test_archived_unlinked_or_erased_contacts_have_explicit_honest_completeness(self):
        self.update(active=False)
        value = self.api.billing_contact(self.owner, self.project)
        self.assertFalse(value['completeness']['ready_for_invoice'])
        self.assertIn('contact_archived', value['completeness']['warnings'])
        with self.office.db:
            self.office.db.execute('UPDATE projects SET customer_id=NULL WHERE id=?', (self.other,))
        unlinked = self.api.billing_contact(self.owner, self.other)
        self.assertIsNone(unlinked['contact_id'])
        self.assertIsNone(unlinked['contact_revision'])
        self.assertIn('contact_not_linked', unlinked['completeness']['warnings'])
        with self.office.db:
            self.office.db.execute('UPDATE business_contact_extras SET erased_at=? WHERE customer_id=?', ('2030-01-01T00:00:00Z', self.customer['id']))
        self.problem(404, lambda: self.api.billing_contact(self.owner, self.project))

    def test_existing_document_buyer_snapshot_is_never_rewritten_by_contact_refresh(self):
        from business_documents import Documents
        snapshot = self.api.billing_contact(self.owner, self.project)
        with self.office.lock, self.office.db:
            document = Documents(self.office).create(self.owner, request(project_id=self.project, kind='offer',
                issue_date='2030-01-10', due_date='2030-01-24', buyer=snapshot['buyer'],
                positions=[{'description': 'Synthetic service', 'quantity': '1', 'unit': 'HUR', 'unit_price_net': '10', 'tax_rate': '19'}]))
        self.update(name='Synthetic later customer name')
        self.api.billing_contact(self.owner, self.project)
        self.assertEqual(Documents(self.office).get(self.owner, document['id'])['buyer'], document['buyer'])

    def test_actual_document_creation_without_buyer_uses_structured_current_contact_once(self):
        from business_documents import Documents
        body = request(project_id=self.project, kind='offer', issue_date='2030-01-10', due_date='2030-01-24',
            positions=[{'description': 'Synthetic automatic billing source', 'quantity': '1', 'unit': 'HUR', 'unit_price_net': '10', 'tax_rate': '19'}])
        with self.office.lock, self.office.db:
            document = Documents(self.office).create(self.owner, body)
        self.assertEqual(document['buyer']['address_line'], 'Synthetic Billing Road 17')
        self.assertEqual(document['buyer']['postal_code'], '10117')
        self.assertEqual(document['buyer']['contact_name'], 'Synthetic Billing Person')
        self.assertEqual(document['buyer']['email'], 'billing@example.test')
        self.update(name='Synthetic changed after create')
        with self.office.lock, self.office.db:
            replay = Documents(self.office).create(self.owner, body)
        self.assertEqual(replay['id'], document['id'])
        self.assertEqual(replay['buyer'], document['buyer'])


ONLINE_AVAILABLE = bool(importlib.util.find_spec('flask') and importlib.util.find_spec('psycopg'))


@unittest.skipUnless(ONLINE_AVAILABLE, 'Real Flask route checks require the separately locked online dependencies')
class BillingContactHttpTests(BillingFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        from cryptography.fernet import Fernet
        from online.web import create_app
        self.app = create_app(office=self.office, key=Fernet.generate_key(), host='office.example.test')
        self.client = self.app.test_client()
        self.token = self.office.login(self.accountant['email'], 'Synthetic-password-123')

    def get(self, path='', *, status=200, method='GET'):
        response = self.client.open('/api/v1/business/projects/' + self.project + '/billing-contact' + path,
            method=method, base_url='https://office.example.test', headers={'Authorization': 'Bearer ' + self.token})
        self.assertEqual(response.status_code, status, response.get_data(as_text=True))
        return response

    def test_real_http_route_exposes_current_revision_and_hash_with_no_cache_or_mutation(self):
        before = self.office.db.total_changes
        first = self.get()
        self.assertEqual(first.headers['Cache-Control'], 'no-store')
        self.assertEqual(first.json['buyer']['postal_code'], '10117')
        self.assertEqual(self.office.db.total_changes, before)
        self.update(name='Synthetic HTTP confirmed change')
        second = self.get()
        self.assertGreater(second.json['contact_revision'], first.json['contact_revision'])
        self.assertNotEqual(second.json['source_fingerprint'], first.json['source_fingerprint'])
        self.get(method='POST', status=405)

    def test_real_http_scope_and_fresh_role_revocation_are_enforced(self):
        self.get()
        with self.office.db:
            self.office.db.execute("UPDATE users SET role='technician' WHERE id=?", (self.accountant['id'],))
        self.get(status=403)
        with self.office.db:
            self.office.db.execute("UPDATE users SET role='accountant' WHERE id=?", (self.accountant['id'],))
        self.office.assign(self.owner, self.project, self.accountant['id'], remove=True)
        self.get(status=404)

    def test_real_http_selection_is_source_scoped_and_rejects_unknown_query_fields(self):
        value = self.get().json
        self.get('?address_id=' + value['selected_address_id'])
        self.get('?address_id=' + uuid.uuid4().hex, status=404)
        self.get('?address_id=broken', status=400)
        self.get('?include_private_notes=true', status=400)
        self.assertEqual(methods('/projects/' + self.project + '/billing-contact'), 'GET')


if __name__ == '__main__':
    unittest.main()
