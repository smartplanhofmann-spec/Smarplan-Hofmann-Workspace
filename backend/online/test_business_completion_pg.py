"""Focused completion acceptance on real Flask/PostgreSQL, synthetic data only.

Reuse the guarded journey setup by method assignment, without inheriting or
rerunning its Gmail journey. The real smartplan-online role and Documents policy
remain active; no SMTP, provider account or external transport is configured.
"""
from datetime import timedelta
import hashlib
import json
import unittest

import business_schema
from core import canonical
from online import test_business_journey_pg as journey


@unittest.skipUnless(journey.DSN, 'Disposable SMARTPLAN_TEST_DSN not configured')
class BusinessCompletionPostgres(unittest.TestCase):
    setUp = journey.BusinessJourneyPostgres.setUp
    call = journey.BusinessJourneyPostgres.call
    login = journey.BusinessJourneyPostgres.login

    def linked_project(self):
        self.assertEqual(self.office.db.execute('SELECT current_user').fetchone()[0], 'smartplan-online')
        self.assertTrue(business_schema.require_runtime_security(self.office))
        contact = self.call('POST', '/business/contacts', journey.request(
            name='Synthetic Completion Buyer GmbH', email='main@example.test',
            address='Unstructured legacy address', notes='PRIVATE CONTACT NOTE',
            persons=[{'name': 'Synthetic Billing Person', 'role_label': 'Buchhaltung',
                      'email': 'billing@example.test', 'phone': 'PRIVATE PHONE'},
                     {'name': 'PRIVATE PERSON', 'role_label': 'Privat',
                      'email': 'private@example.test', 'phone': ''}],
            addresses=[{'purpose': 'site', 'label': 'PRIVATE SITE', 'street': 'PRIVATE STREET',
                        'postal_code': '99999', 'city': 'PRIVATE CITY', 'country': 'DE'},
                       {'purpose': 'billing', 'label': 'Synthetic billing address',
                        'street': 'Synthetic Billing Road 17', 'postal_code': '10117',
                        'city': 'Berlin', 'country': 'DE'}]), status=201).json
        project = self.call('POST', '/projects', {'name': 'Synthetic completion project',
                            'customer_id': contact['id']}, status=201).json['id']
        return contact, project

    def document_body(self, project, **changes):
        return journey.request(project_id=project, kind='offer', issue_date=self.today,
            due_date=(self.now + timedelta(days=14)).date().isoformat(), **changes)

    def document_hash(self, identifier):
        row = self.office.db.execute('SELECT payload_json,payload_sha256 FROM business_documents WHERE id=?',
                                     (identifier,)).fetchone()
        self.assertEqual(hashlib.sha256(row['payload_json'].encode()).hexdigest(), row['payload_sha256'])
        return row['payload_sha256']

    def test_billing_snapshot_and_timeline_use_canonical_live_project_data(self):
        contact, project = self.linked_project()
        billing_path = '/business/projects/' + project + '/billing-contact'
        billing = self.call('GET', billing_path).json
        self.assertEqual((billing['contact_id'], billing['contact_revision']), (contact['id'], contact['revision']))
        self.assertEqual((billing['buyer']['contact_name'], billing['buyer']['email']),
                         ('Synthetic Billing Person', 'billing@example.test'))
        self.assertEqual((billing['buyer']['address_line'], billing['buyer']['postal_code'], billing['buyer']['city']),
                         ('Synthetic Billing Road 17', '10117', 'Berlin'))
        self.assertTrue(billing['completeness']['ready_for_invoice'])
        self.assertRegex(billing['source_fingerprint'], r'^[a-f0-9]{64}$')
        self.assertNotIn('PRIVATE', json.dumps(billing))
        self.assertNotIn('private@example.test', json.dumps(billing))

        body = self.document_body(project, positions=[{'description': 'Synthetic service', 'quantity': '1',
            'unit': 'HUR', 'unit_price_net': '10.00', 'tax_rate': '19'}])
        document = self.call('POST', '/business/documents', body).json
        self.assertEqual(document['buyer'], billing['buyer'])
        original_hash = self.document_hash(document['id'])
        changed_contact = self.call('POST', '/business/contacts/' + contact['id'], journey.request(
            revision=contact['revision'], name='Synthetic Later Buyer GmbH')).json
        current = self.call('GET', billing_path).json
        self.assertEqual(current['contact_revision'], changed_contact['revision'])
        self.assertNotEqual(current['source_fingerprint'], billing['source_fingerprint'])
        replay = self.call('POST', '/business/documents', body).json
        self.assertEqual((replay['id'], replay['buyer'], self.document_hash(document['id'])),
                         (document['id'], document['buyer'], original_hash))

        workspace_path = '/projects/' + project + '/workspace'
        profile = self.call('GET', workspace_path).json['profile']
        saved = self.call('POST', workspace_path, journey.request(revision=profile['revision'],
            start_date='2026-12-31', end_date='2027-01-02', description='PRIVATE PROJECT DESCRIPTION')).json
        timeline_path = '/business/planning/timeline?from=2027-01-01&to=2027-12-31&project_id=' + project
        bar = self.call('GET', timeline_path).json['items'][0]
        self.assertEqual((bar['id'], bar['revision'], bar['start_date'], bar['end_date']),
                         (project, saved['revision'], '2026-12-31', '2027-01-02'))
        self.assertNotIn('PRIVATE', json.dumps(bar))
        dates_path = '/business/planning/projects/' + project + '/dates'
        self.call('POST', dates_path, journey.request(revision=profile['revision'],
                  start_date='2027-01-05', end_date='2027-01-06'), status=409)
        moved = self.call('POST', dates_path, journey.request(revision=bar['revision'],
                          start_date='2027-01-05', end_date='2027-01-06')).json
        canonical_profile = self.call('GET', workspace_path).json['profile']
        self.assertEqual((moved['revision'], moved['start_date'], moved['end_date']),
                         (canonical_profile['revision'], canonical_profile['start_date'], canonical_profile['end_date']))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_appointments').fetchone()[0], 0)

    def test_decimal_and_metric_sources_freeze_into_real_drafts_with_fresh_revision_and_rbac_checks(self):
        _, project = self.linked_project()
        article = self.call('POST', '/business/articles', journey.request(name='Synthetic BOM component',
            kind='material', unit='C62', unit_price_net='8.00', cost_price_net='5.00', tax_rate='19')).json
        pricing = self.call('POST', '/business/commercial/pricing/preview', journey.request(project_id=project,
            base_cost_net='10', labor_hours='2', hourly_cost_net='20', overhead_percent='10', markup_percent='20',
            markup_amount='1', surcharge_percent='5', surcharge_amount='2', quantity='2',
            components=[{'article_id': article['id'], 'article_revision': article['revision'], 'quantity': '2'}])).json
        self.assertEqual((pricing['unit_cost_net'], pricing['unit_price_net'], pricing['totals']['net'], pricing['totals']['tax']),
                         ('66.00', '85.50', '171.00', '32.49'))
        self.assertEqual(hashlib.sha256(canonical({k: v for k, v in pricing.items() if k != 'preview_hash'}).encode()).hexdigest(),
                         pricing['preview_hash'])
        calculated_body = self.document_body(project, positions=[{'description': 'Synthetic calculated service',
            'quantity': '2', 'pricing': pricing['inputs'], 'pricing_hash': pricing['preview_hash'], 'price_confirmation': True}])
        calculated = self.call('POST', '/business/documents', calculated_body).json
        self.assertEqual(calculated['positions'][0]['pricing_snapshot'], pricing)
        calculated_hash = self.document_hash(calculated['id'])
        changed_article = self.call('POST', '/business/articles/' + article['id'],
            journey.request(revision=article['revision'], cost_price_net='7.00')).json
        count = self.office.db.execute('SELECT COUNT(*) FROM business_documents').fetchone()[0]
        self.call('POST', '/business/documents', {**calculated_body, 'request_id': journey.request()['request_id']}, status=409)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_documents').fetchone()[0], count)
        self.assertEqual(self.document_hash(calculated['id']), calculated_hash)

        source = self.call('POST', '/business/measurements', journey.request(project_id=project,
            title='Synthetic measured area', lines=[{'description': 'Synthetic rectangle', 'unit': 'm2', 'formula': 'a*b',
            'variables': {'a': {'value': '2.2', 'unit': 'm'}, 'b': {'value': '3.1', 'unit': 'm'}}}]), status=201).json
        selection = dict(project_id=project, measurement_id=source['id'], measurement_revision=source['revision'],
            measurement_hash=source['content_hash'], lines=[{'line_index': 0, 'unit_price_net': '25.50', 'tax_rate': '19'}])
        preview = self.call('POST', '/business/commercial/measurement-preview', journey.request(**selection)).json
        self.assertEqual((preview['positions'][0]['quantity'], preview['positions'][0]['unit'], preview['positions'][0]['net']),
                         ('6.8200', 'MTK', '173.91'))
        transfer = {**selection, 'preview_hash': preview['preview_hash'], 'quantity_confirmation': True, 'price_confirmation': True}
        measured_body = self.document_body(project, positions=[], measurement_imports=[transfer])
        measured = self.call('POST', '/business/documents', measured_body).json
        position = measured['positions'][0]
        snapshot = position['measurement_snapshot']
        self.assertTrue(snapshot['confirmed'])
        self.assertEqual((position['source_revision'], position['source_hash']), (source['revision'], source['content_hash']))
        self.assertEqual(hashlib.sha256(canonical({k: v for k, v in snapshot.items() if k != 'sha256'}).encode()).hexdigest(), snapshot['sha256'])
        measured_hash = self.document_hash(measured['id'])
        self.call('POST', '/business/measurements/' + source['id'], journey.request(project_id=project,
            revision=source['revision'], title='Synthetic updated area', lines=source['lines']))
        self.call('POST', '/business/documents', {**measured_body, 'request_id': journey.request()['request_id']}, status=409)
        self.assertEqual(self.document_hash(measured['id']), measured_hash)

        email, password = 'completion-manager@example.test', 'Synthetic-manager-password-123'
        manager = self.call('POST', '/users', {'email': email, 'password': password, 'role': 'manager'}, status=201).json['id']
        self.call('POST', '/assignments', {'project_id': project, 'user_id': manager})
        grant = self.call('POST', '/business/settings/permissions', journey.request(user_id=manager,
            permission='finance.read', scope=project, effect='allow', revision=0)).json
        token = self.login(email, password)
        plain_price = journey.request(project_id=project, base_cost_net='5.00')
        self.call('POST', '/business/commercial/pricing/preview', plain_price, token=token)
        self.call('GET', '/business/projects/' + project + '/billing-contact', token=token)
        self.call('GET', '/business/documents/' + measured['id'], token=token)
        # Project finance access does not grant the global live cost catalogue,
        # even with a valid article ID and its current revision.
        self.call('GET', '/business/articles/' + article['id'], token=token, status=403)
        self.call('POST', '/business/commercial/pricing/preview', journey.request(project_id=project,
            components=[{'article_id': article['id'], 'article_revision': changed_article['revision'], 'quantity': '1'}]),
            token=token, status=403)
        self.call('POST', '/business/settings/permissions', journey.request(user_id=manager,
            permission='finance.read', scope=project, effect='deny', revision=grant['revision']))
        self.call('POST', '/business/commercial/pricing/preview', plain_price, token=token, status=403)
        self.call('GET', '/business/projects/' + project + '/billing-contact', token=token, status=403)
        self.call('GET', '/business/documents/' + measured['id'], token=token, status=403)
        self.assertEqual(self.document_hash(measured['id']), measured_hash)
        self.assertTrue(business_schema.validate_integrity(self.office))


if __name__ == '__main__':
    unittest.main()
