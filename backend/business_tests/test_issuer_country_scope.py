"""The German first version must not issue with an unsupported issuer country."""
import unittest
import uuid

from core import Problem
from business_tests import test_documents as fixture
import business_country_rules as rules
import business_documents as documents


class IssuerCountryScopeTests(fixture.DocumentsFixture, unittest.TestCase):
    def change_country(self, country):
        _, revision = self.api._settings_row()
        self.call('save_settings', dict(request_id=uuid.uuid4().hex,
            revision=revision, country=country, issuing_enabled=False))
        return fixture.seed_synthetic_issuer(self.api, self.owner)

    def test_unsupported_issuer_country_cannot_consume_a_number_or_archive(self):
        self.settings()
        for country in ('AT', 'CH', 'US'):
            with self.subTest(country=country):
                self.change_country(country)
                document = self.draft(kind='invoice')
                with self.assertRaises(Problem) as raised:
                    self.api.prepare_finalization(self.owner, document['id'], document['revision'])
                self.assertEqual(raised.exception.status, 409)
                self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_document_numbers').fetchone()[0], 0)
                self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_document_archives').fetchone()[0], 0)

    def test_exact_country_domain_currency_dispatch_never_borrows_a_package(self):
        selected = rules.resolve(domain='commercial_invoice', country='DE', currency='EUR')
        selected['country'] = 'CH'
        self.assertEqual(rules.resolve(domain='commercial_invoice', country='DE', currency='EUR')['country'], 'DE')
        for changes in (dict(country='de'), dict(country='AT'), dict(currency='CHF'),
                        dict(domain='payroll'), dict(country=True), dict(currency=None)):
            with self.subTest(changes=changes), self.assertRaises(Problem):
                rules.resolve(**(dict(domain='commercial_invoice', country='DE', currency='EUR') | changes))

    def test_fresh_country_change_blocks_already_rendered_candidate(self):
        self.settings()
        document = self.draft(kind='invoice')
        prepared = self.api.prepare_finalization(self.owner, document['id'], document['revision'])
        rendered = documents.render_prepared(prepared)
        self.change_country('AT')
        with self.assertRaises(Problem) as raised:
            self.call('finalize', document['id'], rendered, uuid.uuid4().hex)
        self.assertEqual(raised.exception.status, 409)
        self.assertEqual(self.call('get', document['id'])['status'], 'draft')
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_document_numbers').fetchone()[0], 0)

    def test_existing_archive_and_exact_finalization_receipt_survive_country_change(self):
        self.settings()
        document = self.draft(kind='invoice')
        prepared = self.api.prepare_finalization(self.owner, document['id'], document['revision'])
        rendered = documents.render_prepared(prepared)
        request = uuid.uuid4().hex
        original = self.call('finalize', document['id'], rendered, request)
        archive = self.call('archive', document['id'])
        self.change_country('CH')
        self.assertEqual(self.call('archive', document['id']), archive)
        self.assertEqual(self.call('finalize', document['id'], rendered, request), original)
        self.assertEqual(self.call('get', document['id'])['issuer']['country'], 'DE')
        self.assertTrue(documents.validate_integrity(self.office))

    def test_foreign_customer_address_does_not_select_the_issuer_rules(self):
        self.settings()
        for country in ('AT', 'CH'):
            document = self.draft(kind='invoice', buyer=dict(name='Synthetic foreign customer',
                address_line='Synthetic customer street', postal_code='0000', city='Synthetic city', country=country))
            prepared = self.api.prepare_finalization(self.owner, document['id'], document['revision'])
            self.assertEqual(prepared['snapshot']['issuer']['country'], 'DE')
            self.assertEqual(prepared['snapshot']['buyer']['country'], country)

    def test_descriptive_scope_is_fresh_and_never_grants_issuing_permission(self):
        original = self.call('rule_scope')
        self.assertTrue(original['supported_issuer'])
        self.assertFalse(self.call('settings')['issuing_enabled'])
        self.settings()
        supported = self.call('rule_scope')
        self.assertTrue(supported['supported_issuer'])
        self.assertEqual(supported['selected']['contract'], 'de_commercial_invoice_eur_v1')
        self.change_country('AT')
        unsupported = self.call('rule_scope')
        self.assertFalse(unsupported['supported_issuer'])
        self.assertIsNone(unsupported['selected'])
        self.assertGreater(unsupported['settings_revision'], supported['settings_revision'])


if __name__ == '__main__':
    unittest.main()
