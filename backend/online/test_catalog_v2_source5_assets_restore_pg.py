"""Populated dated-price/document, asset, opening and Source5 restore together."""
import base64
from copy import deepcopy
import unittest

import business_schema
import business_catalog_imports as catalog
import business_catalog_prices as prices
from business_documents import Documents
from test_business_catalog_prices import raw, row
import business_accounting_asset_openings as assets
import business_accounting_openings as openings
import business_payroll_multiple_cases as multiple
from business_accounting_euer import EuerAccounting
from business_adapters import Adapters
from business_payroll import Payroll, TABLES as PAYROLL_TABLES
from core import Problem
from online import release
from online import test_accounting_asset_openings_pg as asset_fixture
from online import test_business_accounting_openings_pg as opening_fixture
from online import test_business_payroll_multiple_pg as payroll_fixture
from online.store import PostgresOffice
from online.test_postgres_accounting_components_integration import disposable_restore, evidence_for, approve


@unittest.skipUnless(payroll_fixture.fixture.DSN, 'Guarded disposable PostgreSQL required')
class CatalogV2AssetsSource5Restore(unittest.TestCase):
    def test_populated_shared_restore_preserves_all_originals_and_requires_complete_financial_scope(self):
        f = payroll_fixture.MultiplePayrollPostgres('runTest')
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.actor = f.owner
        data = f.workflow()
        run = f.call('POST', '/business/payroll/runs', data['run_command']).json
        payroll_pdf = Payroll(f.office).export(f.owner, run['id'], 'pdf')[0]
        consumption = multiple._consumption_row(f.office, run)

        asset_fixture.euer.EuerPostgres.profile(f)
        f.account = f.call('POST', '/business/accounting/accounts', payroll_fixture.req(
            confirmation=True, code='SHARED', name='Synthetic shared opening', kind='bank'), status=201).json
        opening_original, _, opening_bytes = opening_fixture.OpeningBalancesPostgres.original(f)
        opening_command = opening_fixture.OpeningBalancesPostgres.command(f, opening_original)
        opening = f.call('POST', opening_fixture.BASE + '/confirm', opening_command, status=201).json

        asset_original, _, asset_bytes = asset_fixture.HistoricalAssetPostgres.original(f)
        asset_command = asset_fixture.HistoricalAssetPostgres.command(f, asset_original)
        asset = f.call('POST', asset_fixture.BASE + '/confirm', asset_command, status=201).json
        source = assets.public_source(f.office, asset['id'])
        depreciation, depreciation_command = asset_fixture.euer.EuerPostgres.post(f, 'opening_depreciation', dict(
            asset_entry_id=asset['id'], source_hash=source['source_hash'], year=int(f.today[:4]), account='6220'))
        export, export_command = asset_fixture.euer.EuerPostgres.post(f, 'export', dict(year=int(f.today[:4])))
        artifact = EuerAccounting(f.office).exported(f.owner, export['id'])
        self.assertEqual(artifact['report']['historical_assets'][0]['continuation']['amount'], '1200.00')

        adapter = f.call('POST', '/business/adapters', payroll_fixture.req(
            name='Synthetic shared catalog', profile='catalog_csv_v1', enabled=True), status=201).json
        catalog_bytes = b'code;name;unit;cost_price_net;unit_price_net;tax_rate\nSHARED;Synthetic item;ST;10;15;19\n'
        imported = f.call('POST', '/business/adapters/' + adapter['id'] + '/import', payroll_fixture.req(
            filename='synthetic-shared.csv', content_base64=base64.b64encode(catalog_bytes).decode()), status=201).json
        catalog_command = payroll_fixture.req(confirmed=True)
        accepted = f.call('POST', '/business/adapters/imports/' + imported['id'] + '/apply', catalog_command).json
        price_source = f.call('POST', '/business/catalog-prices/sources', payroll_fixture.req(
            name='Synthetic shared dated source', reference='SYN-SHARED-V2')).json
        price_bytes = raw(row(code='SHARED-V2'), row(code='SHARED-V2', price_id='dec', amount='12', start='2026-12-01', end=''))
        staged = f.call('POST', '/business/catalog-prices/sources/' + price_source['id'] + '/imports', payroll_fixture.req(
            catalog_revision='SYN-SHARED-1', filename='shared-dated.csv',
            content_base64=base64.b64encode(price_bytes).decode())).json
        decisions = dict(expected_source_version=prices.CatalogPrices(f.office).source(price_source['id'])['source_version'],
            replacements={}, bindings={'SHARED-V2': dict(action='create', article_id=None,
            article_revision=None, expected_binding_revision=0, confirm_name_difference=False)})
        checked = f.call('POST', '/business/catalog-prices/imports/' + staged['id'] + '/preview', decisions).json
        price_command = payroll_fixture.req(**decisions, preview_sha256=checked['preview_sha256'], confirmation=True)
        price_accepted = f.call('POST', '/business/catalog-prices/imports/' + staged['id'] + '/apply', price_command).json
        proof = price_accepted['prices'][0]
        selection = dict(price_id=proof['price_id'], price_revision=proof['revision'], price_sha256=proof['sha256'], effective_on='2026-11-04')
        project = f.call('POST', '/projects', dict(name='Synthetic shared dated offer', customer='Synthetic customer'), status=201).json['id']
        document_command = payroll_fixture.req(project_id=project, kind='offer', title='Synthetic dated shared offer',
            issue_date='2026-11-04', due_date='2026-11-30', buyer=dict(name='Synthetic Buyer', address_line='Testweg 1',
            postal_code='10115', city='Berlin', country='DE', email='buyer@example.test'), positions=[dict(
            article_id=price_accepted['bindings'][0]['article_id'], article_revision=1, quantity='3', catalog_price_selection=selection)])
        document = f.call('POST', '/business/documents', document_command).json
        self.assertEqual(document['totals']['net'], '30.00')
        document_price = document['positions'][0]['catalog_price_snapshot']
        horizon = business_schema.financial_accounting_horizon(f.office)
        self.assertEqual(horizon['schema_version'], 15)
        fingerprints = release.snapshot_fingerprint(payroll_fixture.fixture.DSN)
        f.office.db.close()

        with disposable_restore(f.runtime) as (target, runtime, report):
            restored = PostgresOffice(runtime)
            try:
                self.assertTrue(business_schema.validate_integrity(restored))
                self.assertEqual(assets.HistoricalAssets(restored).original(f.owner, asset_original['id'])[0], asset_bytes)
                self.assertEqual(openings.OpeningBalances(restored).original(f.owner, opening_original['id'])[0], opening_bytes)
                self.assertEqual(catalog.CatalogImports(restored).original(f.owner, imported['id'])[0], catalog_bytes)
                self.assertEqual(prices.CatalogPrices(restored).original(f.owner, staged['id'])[0], price_bytes)
                self.assertEqual(prices.validate_snapshot(restored, document_price), document_price)
                self.assertEqual(Documents(restored).get(f.owner, document['id']), document)
                self.assertEqual(Payroll(restored).export(f.owner, run['id'], 'pdf')[0], payroll_pdf)
                self.assertEqual(EuerAccounting(restored).exported(f.owner, export['id']), artifact)
                evidence = evidence_for(restored, report)
                self.assertEqual(evidence['schema'], 16)
                self.assertEqual(evidence['accounting_horizon'], horizon)
                for api, command in ((assets.HistoricalAssets(restored), asset_command),
                                     (openings.OpeningBalances(restored), opening_command)):
                    with self.assertRaises(Problem) as denied:
                        api.confirm(f.owner, command)
                    self.assertEqual(denied.exception.status, 409)
            finally:
                restored.db.close()
            operator = PostgresOffice(target)
            try:
                old = deepcopy(evidence)
                old['schema'] = 13
                old['accounting_horizon'].pop('year_values')
                old['accounting_horizon'].pop('opening_items')
                old['accounting_horizon'].pop('historical_assets')
                old['accounting_horizon']['schema_version'] = 12
                business_schema._validate_financial_accounting_horizon(old['accounting_horizon'], 13)
                before = release.snapshot_fingerprint(target)
                with self.assertRaises((Problem, ValueError)):
                    approve(operator, old)
                self.assertEqual(release.snapshot_fingerprint(target), before)
                self.assertTrue(approve(operator, evidence)['reconciled'])
            finally:
                operator.db.close()
            restored = PostgresOffice(runtime)
            try:
                self.assertEqual(assets.HistoricalAssets(restored).confirm(f.owner, asset_command), asset)
                self.assertEqual(openings.OpeningBalances(restored).confirm(f.owner, opening_command), opening)
                self.assertEqual(Adapters(restored).apply_catalog(f.owner, imported['id'], catalog_command), accepted)
                self.assertEqual(prices.CatalogPrices(restored).apply(f.owner, staged['id'], price_command), price_accepted)
                self.assertEqual(Documents(restored).create(f.owner, document_command), document)
                self.assertEqual(Payroll(restored).finalize(f.owner, data['run_command']), run)
                self.assertEqual(multiple._consumption_row(restored, run), consumption)
                self.assertEqual(EuerAccounting(restored).confirm(f.owner, depreciation_command), depreciation)
                self.assertEqual(EuerAccounting(restored).confirm(f.owner, export_command), export)
                self.assertEqual(EuerAccounting(restored).exported(f.owner, export['id']), artifact)
                actual = release.snapshot_fingerprint(target)
                for table in prices.TABLES + assets.TABLES + openings.TABLES + catalog.TABLES + multiple.TABLES + PAYROLL_TABLES + (
                        'business_euer_entries', 'business_euer_requests', 'business_articles', 'business_document_versions'):
                    self.assertEqual(actual[table], fingerprints[table], table)
                self.assertTrue(business_schema.validate_integrity(restored))
            finally:
                restored.db.close()
