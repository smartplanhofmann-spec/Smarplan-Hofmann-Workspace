"""Actual restricted PostgreSQL issuing, MFA and changed issuer scope."""
import unittest
import uuid

import business_documents as documents
import business_schema
from core import Problem
from online import test_business_journey_pg as fixture


@unittest.skipUnless(fixture.DSN, 'Guarded disposable loopback PostgreSQL required')
class CommercialCountryScopePostgres(unittest.TestCase):
    setUp = fixture.BusinessJourneyPostgres.setUp
    login = fixture.BusinessJourneyPostgres.login
    call = fixture.BusinessJourneyPostgres.call

    def settings(self, country):
        prior = self.call('GET', '/business/commercial/settings').json
        return self.call('POST', '/business/commercial/settings', dict(
            request_id=uuid.uuid4().hex, revision=prior['revision'],
            company_name='Synthetic country scope seller', address_line='Synthetic seller street',
            postal_code='10115', city='Berlin', country=country, vat_id='DE123456789',
            issuer_mode='own', issuing_enabled=True, cutover_ack=True,
            cutover_date=self.today, einvoice_format='none')).json

    def draft(self):
        owner = self.office.user(self.token)
        project = self.office.add_project(owner, 'Synthetic country scope', 'Synthetic customer')
        return self.call('POST', '/business/documents', dict(request_id=uuid.uuid4().hex,
            project_id=project, kind='invoice', title='Synthetic country test',
            issue_date=self.today, due_date=self.today,
            buyer=dict(name='Synthetic customer',address_line='Synthetic customer street',
                postal_code='10117',city='Berlin',country='DE'),
            positions=[dict(description='Synthetic service',quantity='1',unit='HUR',
                unit_price_net='100.00',tax_rate='19',kind='labor')])).json

    def test_actual_unsupported_issuer_does_not_consume_number_and_de_can_issue(self):
        self.assertTrue(business_schema.require_runtime_security(self.office))
        for country in ('AT','CH'):
            self.settings(country)
            draft = self.draft()
            scope = self.call('GET','/business/commercial/rule-scope').json
            self.assertFalse(scope['supported_issuer'])
            self.call('POST','/business/documents/'+draft['id']+'/finalize',
                dict(request_id=uuid.uuid4().hex,revision=draft['revision']),status=409)
            self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_document_numbers').fetchone()[0],0)
            self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_document_archives').fetchone()[0],0)
        self.settings('DE')
        draft = self.draft()
        path = '/business/documents/'+draft['id']
        command = dict(request_id=uuid.uuid4().hex,revision=draft['revision'])
        accepted = self.call('POST',path+'/finalize',command).json
        self.assertTrue(accepted['number'].endswith('-000001'))
        archive = self.call('GET',path+'/pdf').data
        self.settings('AT')
        self.assertEqual(self.call('POST',path+'/finalize',command).json,accepted)
        self.assertEqual(self.call('GET',path+'/pdf').data,archive)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_document_numbers').fetchone()[0],1)
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_actual_country_change_between_render_and_commit_blocks_artifact(self):
        self.settings('DE')
        draft = self.draft();owner=self.office.user(self.token);api=documents.Documents(self.office)
        prepared=api.prepare_finalization(owner,draft['id'],draft['revision'])
        rendered=documents.render_prepared(prepared)
        self.settings('CH')
        with self.assertRaises(Problem) as error:
            api.finalize(owner,draft['id'],rendered,uuid.uuid4().hex)
        self.assertEqual(error.exception.status,409)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_document_numbers').fetchone()[0],0)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_document_archives').fetchone()[0],0)
        self.assertEqual(self.call('GET','/business/documents/'+draft['id']).json['status'],'draft')
        self.assertTrue(business_schema.validate_integrity(self.office))


if __name__ == '__main__':
    unittest.main()
