"""Actual full financial restore: old V1, year-journal V2, cash, sources and events."""
import base64
from copy import deepcopy
import unittest
import uuid
import tempfile
from types import MethodType

from online import test_accounting_open_items_pg as item_pg_fixture
from business_accounting_open_items import OpeningItems, TABLES as OPEN_ITEM_TABLES

from online.instance import bind
from online.storage import Storage
from online.web import create_app

from business_company_events import CompanyEvents, TABLES as EVENT_TABLES

import business_schema
import business_catalog_imports as catalog
import business_catalog_prices as prices
from business_documents import Documents
from test_business_catalog_prices import raw, row
import business_accounting_asset_openings as assets
import business_accounting_openings as openings
import business_payroll_multiple_cases as multiple
from business_accounting_euer import EuerAccounting
from accounting_year_verify_v1 import verify as verify_year_archive
from accounting_year_verify_v2 import verify as verify_year_archive_v2
from business_accounting_year_openings import YearValues, TABLES as YEAR_TABLES, restore_horizon as year_horizon
from online import test_accounting_year_openings_pg as year_fixture
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
class YearValuesFullFinancialRestore(unittest.TestCase):
    def test_one_filled_restore_keeps_old_v1_new_v2_original_year_cents_and_existing_families(self):
        f = payroll_fixture.MultiplePayrollPostgres('runTest')
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.actor = f.owner
        directory = tempfile.TemporaryDirectory(prefix='synthetic-shared-events-')
        self.addCleanup(directory.cleanup)
        storage_config = {'server': {'path': directory.name + '/company'}}
        instance_id = uuid.uuid4().hex
        operator = PostgresOffice(payroll_fixture.fixture.DSN)
        try:
            bind(operator, instance_id, 'office.example.test', f.key,
                 Storage(operator, f.key, 'office.example.test', config=storage_config))
        finally:
            operator.db.close()
        f.office.db.close()
        f.office = PostgresOffice(f.runtime)
        self.addCleanup(f.office.db.close)
        f.app = create_app(office=f.office, key=f.key, host='office.example.test',
                          instance_id=instance_id, storage_config=storage_config)
        f.client = f.app.test_client()
        data = f.workflow()
        run = f.call('POST', '/business/payroll/runs', data['run_command']).json
        payroll_pdf = Payroll(f.office).export(f.owner, run['id'], 'pdf')[0]
        consumption = multiple._consumption_row(f.office, run)

        f.year = int(f.today[:4])
        state = f.call('GET', '/business/accounting/profile').json
        profile = dict(expected_revision=state['revision'], state_hash=state['state_hash'],
            reason='Synthetic shared historical original activity', evidence_reference='Synthetic old method originals',
            profile=dict(legal_form='sole_proprietorship', accounting_method='euer', vat_regime='regular',
                vat_timing='cash', vat_effective_from=str(f.year-1)+'-01-01', bookkeeping_start=str(f.year)+'-11-01'))
        preview = f.call('POST', '/business/accounting/profile/preview', profile).json
        f.call('POST', '/business/accounting/profile/confirm', payroll_fixture.req(**profile,
            confirmation=True, preview_hash=preview['preview_hash']), status=201)
        f.uploads = []
        f.original = MethodType(item_pg_fixture.OpeningItemPostgres.original, f)
        f.command = MethodType(item_pg_fixture.OpeningItemPostgres.command, f)
        f.post = MethodType(asset_fixture.euer.EuerPostgres.post, f)
        f.account = f.call('POST', '/business/accounting/accounts', payroll_fixture.req(
            confirmation=True, code='SHARED', name='Synthetic shared opening', kind='bank'), status=201).json
        opening_original, _, opening_bytes = opening_fixture.OpeningBalancesPostgres.original(f)
        state = f.call('GET', opening_fixture.BASE).json
        opening_body = dict(expected_revision=state['revision'], state_hash=state['state_hash'],
            account_id=f.account['id'], account_revision=f.account['revision'], profile_ref=state['profile_ref'],
            status='active', opening_date='2026-11-01', amount='1000.00',
            reason='Synthetic original actual balance immediately before November cutover',
            source=dict(kind='original', original_id=opening_original['id'], sha256=opening_original['sha256'],
                        evidence_type='account_statement', at_start_of_day=True))
        opening_preview = f.call('POST', opening_fixture.BASE + '/preview', opening_body).json
        opening_command = payroll_fixture.req(**opening_body, confirmation=True, preview_hash=opening_preview['preview_hash'])
        opening = f.call('POST', opening_fixture.BASE + '/confirm', opening_command, status=201).json

        asset_original, _, asset_bytes = asset_fixture.HistoricalAssetPostgres.original(f)
        state = f.call('GET', asset_fixture.BASE).json
        asset_body = dict(expected_revision=state['revision'], state_hash=state['state_hash'],
            asset_key='m-001', profile_ref=state['profile_ref'], opening_date='2026-11-01', status='active',
            reason='Synthetic original annual depreciation not yet entered before software cutover',
            asset=asset_fixture.asset(acquired_on='2024-01-03', use_start='2024-01-03'),
            source=dict(original_id=asset_original['id'], sha256=asset_original['sha256'],
                        position='Historic register row1', history_through='2026-10-31'))
        self.assertEqual(asset_body['asset']['depreciation_in_start_year'], '0.00')
        asset_preview = f.call('POST', asset_fixture.BASE + '/preview', asset_body).json
        asset_command = payroll_fixture.req(**asset_body, confirmation=True, preview_hash=asset_preview['preview_hash'])
        asset = f.call('POST', asset_fixture.BASE + '/confirm', asset_command, status=201).json
        source = assets.public_source(f.office, asset['id'])
        depreciation, depreciation_command = asset_fixture.euer.EuerPostgres.post(f, 'opening_depreciation', dict(
            asset_entry_id=asset['id'], source_hash=source['source_hash'], year=int(f.today[:4]), account='6220'))
        helper = item_pg_fixture.item_fixture.OpeningItemWorkflow('runTest'); helper.original = f.original
        old_item_payload = helper.item('old-item', 'payable')
        old_item_payload['history_through'] = '2026-10-31'
        old_item_command = f.command('item', 'old-item', old_item_payload)
        old_item = f.call('POST', item_pg_fixture.BASE + '/confirm', old_item_command, status=201).json
        old_payment_command = item_pg_fixture.OpeningItemPostgres.payment_command(f, old_item)
        old_payment = f.call('POST', '/business/accounting/open-items/confirm', old_payment_command, status=201).json
        old_post, old_post_command = item_pg_fixture.OpeningItemPostgres.classify(f, old_payment)
        export, export_command = asset_fixture.euer.EuerPostgres.post(f, 'export', dict(year=int(f.today[:4])))
        artifact = EuerAccounting(f.office).exported(f.owner, export['id'])
        year_metadata = EuerAccounting(f.office).year_evidence(f.owner, export['id'])
        year_archive = bytes(EuerAccounting(f.office).year_evidence(f.owner, export['id'], archive=True))
        self.assertEqual(year_metadata['export_id'], export['id'])
        self.assertTrue(verify_year_archive(year_archive, year_metadata['sha256'])['verified'])
        with self.assertRaises(ValueError):
            verify_year_archive(year_archive)
        self.assertEqual(artifact['report']['historical_assets'][0]['continuation']['amount'], '1200.00')
        self.assertEqual(artifact['report']['totals']['confirmed_input_vat'], '0.00')
        self.assertEqual(artifact['report']['totals']['confirmed_expenses'], '1319.00')


        self.assertEqual(year_metadata['format'], 'smartplan-year-evidence-v1')
        self.assertFalse(year_metadata['original_year_complete'])
        self.assertTrue(any(issue['code']=='partial_period_profile_coverage' for issue in artifact['report']['issues']))
        # A genuinely separate June invoice, original August half payment and
        # separately exercised June VAT entitlement become the old-year source.
        carry_payload = helper.item('carry-item', 'payable')
        carry_payload.update(invoice_date='2026-06-10', service_date='2026-06-10',
            invoice_received_date='2026-06-11', history_through='2026-10-31')
        carry_payload['prior_input_vat'].update(entitlement_date='2026-06-11', declared_period='2026-06', deducted_on='2026-07-10')
        carry_payload['prior_payments'] = [dict(date='2026-08-20', reference='Actual original August part',
            gross='59.50', net='50.00', tax='9.50', proof=carry_payload['cutover_proof'])]
        carry_command = f.command('item', 'carry-item', carry_payload)
        carry_item = f.call('POST', item_pg_fixture.BASE + '/confirm', carry_command, status=201).json
        year_bytes = b'%PDF-1.4\nSynthetic independently retained complete Jan-Oct original journal\n%%EOF'
        year_upload = payroll_fixture.req(entity_key='2026', filename='whole-prior-journal.pdf',
            media_type='application/pdf', content_base64=base64.b64encode(year_bytes).decode())
        year_original = f.call('POST', year_fixture.BASE + '/originals', year_upload, status=201).json
        f.payload = dict(status='active', coverage={'from':'2026-01-01','through':'2026-10-31'},
            sources=[dict(kind='opening_item', entry_id=carry_item['id'], entry_hash=carry_item['content_hash'],
                accounts=dict(net='5400', tax='1406', input_vat='1406'), cash_entry_keys=['JOINT-AUGUST-1'], vat_entry_key='JOINT-JUNE-1')],
            controls=[dict(ledger='euer', category='materials', account='5400', amount='-50.00'),
                dict(ledger='euer', category='paid_input_vat', account='1406', amount='-9.50'),
                dict(ledger='vat', category='input_vat', account='1406', amount='-19.00')],
            ledger_proof=dict(original_id=year_original['id'], sha256=year_original['sha256']),
            attestations=dict(continuous_method=True, original_journal_complete=True, no_unsupported_values=True))
        year_command = year_fixture.YearValuesPostgres.year_command(f)
        year_entry = f.call('POST', year_fixture.BASE + '/confirm', year_command, status=201).json
        year_post, year_post_command = year_fixture.YearValuesPostgres.classify(f, year_entry)
        carry_payment_command = item_pg_fixture.OpeningItemPostgres.payment_command(f, carry_item, '59.50')
        carry_payment = f.call('POST', item_pg_fixture.BASE + '/confirm', carry_payment_command, status=201).json
        carry_post, carry_post_command = item_pg_fixture.OpeningItemPostgres.classify(f, carry_payment)
        v2_export, v2_export_command = f.post('export', dict(year=2026))
        v2_artifact = EuerAccounting(f.office).exported(f.owner, v2_export['id'])
        v2_metadata = EuerAccounting(f.office).year_evidence(f.owner, v2_export['id'])
        v2_archive = bytes(EuerAccounting(f.office).year_evidence(f.owner, v2_export['id'], archive=True))
        self.assertEqual(v2_metadata['format'], 'smartplan-year-evidence-v2')
        self.assertTrue(v2_metadata['original_year_complete'])
        self.assertTrue(verify_year_archive_v2(v2_archive, v2_metadata['sha256'])['verified'])
        self.assertFalse(verify_year_archive_v2(v2_archive, v2_metadata['sha256'])['intrinsic_dependency_closure'])
        with self.assertRaises(ValueError): verify_year_archive_v2(v2_archive)
        totals = v2_artifact['report']['totals']
        self.assertEqual((totals['confirmed_expenses'], totals['confirmed_input_vat'], totals['euer_surplus']), ('1438.00', '19.00', '-1438.00'))
        self.assertEqual(sorted(m['amount'] for m in v2_artifact['report']['cash_movements']), ['119.00', '59.50'])
        self.assertEqual([(p['date'], p['amount']) for p in year_post['postings']],
                         [('2026-08-20','-50.00'),('2026-08-20','-9.50'),('2026-06-11','-19.00')])
        self.assertFalse(any(p['ledger']=='vat' and p['category']=='input_vat' for p in old_post['postings']+carry_post['postings']))
        liquidity = openings.OpeningBalances(f.office).liquidity(f.owner, '2026-11-04')
        money = next(row for row in liquidity['accounts'] if row['account']['id']==f.account['id'])
        self.assertEqual((money['opening_balance'], money['outflows'], money['calculated_balance']), ('1000.00','178.50','821.50'))
        self.assertEqual(EuerAccounting(f.office).exported(f.owner, export['id']), artifact)
        self.assertEqual(bytes(EuerAccounting(f.office).year_evidence(f.owner, export['id'], archive=True)), year_archive)
        original_year_scope = year_horizon(f.office)

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
        for index in range(2):
            f.call('POST', '/projects/' + project + '/tasks', payroll_fixture.req(
                title='Synthetic shared overdue ' + str(index), details='Actual original task',
                due_date='2026-11-01', priority='normal', status='todo', assignee_id=f.owner['id']), status=201)
        event_api = CompanyEvents(f.office)
        f.call('POST', '/business/company-events/rules', payroll_fixture.req(
            id=uuid.uuid4().hex, revision=0, title='Synthetic shared event rule', enabled=True,
            project_ids=[project], trigger='task.overdue', action='task.create', mode='approval',
            conditions=[], template=dict(title='Synthetic reviewed follow-up', details='Fixed original',
                priority='normal', due_days=None), responsible_id=f.owner['id'], confirmation=True))
        event_run = event_api.scan(f.owner, payroll_fixture.req(limit=100, after=None))
        event_plans = [event_api.plan(f.owner, key) for item in event_run['items'] for key in item['plan_ids']]
        self.assertEqual(len(event_plans), 2)
        completed, pending = event_plans
        for plan in event_plans:
            event_api.decide(f.owner, plan['id'], True, payroll_fixture.req(
                plan_sha256=plan['sha256'], reason='Synthetic original reviewed', confirmation=True))
        event_command = payroll_fixture.req(plan_sha256=completed['sha256'], confirmation=True)
        event_accepted = event_api.execute(f.owner, completed['id'], event_command)
        self.assertEqual(event_accepted['status'], 'succeeded')
        task_count = f.office.db.execute('SELECT COUNT(*) FROM workspace_items').fetchone()[0]
        horizon = business_schema.financial_accounting_horizon(f.office)
        self.assertEqual(horizon['schema_version'], 15)
        self.assertEqual(horizon['year_values'], original_year_scope)
        fingerprints = release.snapshot_fingerprint(payroll_fixture.fixture.DSN)
        f.office.db.close()

        with disposable_restore(f.runtime) as (target, runtime, report):
            restored = PostgresOffice(runtime)
            try:
                self.assertTrue(business_schema.validate_integrity(restored))
                event_api = CompanyEvents(restored)
                self.assertEqual(event_api.execute(f.owner, completed['id'], event_command)['outcome'], event_accepted['outcome'])
                self.assertEqual(event_api.plan(f.owner, pending['id'])['status'], 'suspended_after_restore')
                with self.assertRaises(Problem) as blocked_event:
                    event_api.scan(f.owner, payroll_fixture.req(limit=100, after=None))
                self.assertEqual(blocked_event.exception.status, 409)
                self.assertEqual(assets.HistoricalAssets(restored).original(f.owner, asset_original['id'])[0], asset_bytes)
                for original, upload, raw_original in f.uploads:
                    self.assertEqual(OpeningItems(restored).original(f.owner, original['id'])[0], raw_original)
                self.assertEqual(openings.OpeningBalances(restored).original(f.owner, opening_original['id'])[0], opening_bytes)
                self.assertEqual(catalog.CatalogImports(restored).original(f.owner, imported['id'])[0], catalog_bytes)
                self.assertEqual(prices.CatalogPrices(restored).original(f.owner, staged['id'])[0], price_bytes)
                self.assertEqual(prices.validate_snapshot(restored, document_price), document_price)
                self.assertEqual(Documents(restored).get(f.owner, document['id']), document)
                self.assertEqual(Payroll(restored).export(f.owner, run['id'], 'pdf')[0], payroll_pdf)
                self.assertEqual(EuerAccounting(restored).exported(f.owner, export['id']), artifact)
                self.assertEqual(EuerAccounting(restored).year_evidence(f.owner, export['id']), year_metadata)
                self.assertEqual(bytes(EuerAccounting(restored).year_evidence(f.owner, export['id'], archive=True)), year_archive)
                self.assertEqual(YearValues(restored).original(f.owner, year_original['id'])[0], year_bytes)
                self.assertEqual(EuerAccounting(restored).exported(f.owner, v2_export['id']), v2_artifact)
                self.assertEqual(EuerAccounting(restored).year_evidence(f.owner, v2_export['id']), v2_metadata)
                self.assertEqual(bytes(EuerAccounting(restored).year_evidence(f.owner, v2_export['id'], archive=True)), v2_archive)
                self.assertFalse(openings.OpeningBalances(restored).liquidity(f.owner, '2026-11-04')['complete_for_recorded_accounts'])
                with self.assertRaises(Problem) as denied_year:
                    YearValues(restored).confirm(f.owner, year_command)
                self.assertEqual(denied_year.exception.status, 409)
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
                old = deepcopy(evidence); old['schema'] = 15
                old['accounting_horizon'].pop('year_values'); old['accounting_horizon']['schema_version'] = 14
                business_schema._validate_financial_accounting_horizon(old['accounting_horizon'], 15)
                wrong = deepcopy(evidence); wrong['accounting_horizon']['year_values']['sha256'] = '0'*64
                before = release.snapshot_fingerprint(target)
                for bad in (old, wrong):
                    with self.assertRaises((Problem, ValueError)): approve(operator, bad)
                    self.assertEqual(release.snapshot_fingerprint(target), before)
                self.assertTrue(approve(operator, evidence)['reconciled'])
            finally:
                operator.db.close()
            restored = PostgresOffice(runtime)
            try:
                self.assertEqual(YearValues(restored).confirm(f.owner, year_command), year_entry)
                self.assertEqual(YearValues(restored).upload_original(f.owner, year_upload), year_original)
                self.assertEqual(OpeningItems(restored).confirm(f.owner, carry_command), carry_item)
                self.assertEqual(OpeningItems(restored).confirm(f.owner, carry_payment_command), carry_payment)
                for expected, command in ((year_post,year_post_command),(carry_post,carry_post_command),(v2_export,v2_export_command)):
                    self.assertEqual(EuerAccounting(restored).confirm(f.owner, command), expected)
                self.assertEqual(EuerAccounting(restored).exported(f.owner, v2_export['id']), v2_artifact)
                self.assertEqual(EuerAccounting(restored).year_evidence(f.owner, v2_export['id']), v2_metadata)
                self.assertEqual(bytes(EuerAccounting(restored).year_evidence(f.owner, v2_export['id'], archive=True)), v2_archive)
                self.assertEqual(year_horizon(restored), original_year_scope)
                self.assertEqual(openings.OpeningBalances(restored).liquidity(f.owner, '2026-11-04'), liquidity)
                self.assertEqual(assets.HistoricalAssets(restored).confirm(f.owner, asset_command), asset)
                self.assertEqual(openings.OpeningBalances(restored).confirm(f.owner, opening_command), opening)
                self.assertEqual(OpeningItems(restored).confirm(f.owner, old_item_command), old_item)
                self.assertEqual(OpeningItems(restored).confirm(f.owner, old_payment_command), old_payment)
                self.assertEqual(EuerAccounting(restored).confirm(f.owner, old_post_command), old_post)
                self.assertEqual(Adapters(restored).apply_catalog(f.owner, imported['id'], catalog_command), accepted)
                self.assertEqual(prices.CatalogPrices(restored).apply(f.owner, staged['id'], price_command), price_accepted)
                self.assertEqual(Documents(restored).create(f.owner, document_command), document)
                self.assertEqual(Payroll(restored).finalize(f.owner, data['run_command']), run)
                self.assertEqual(multiple._consumption_row(restored, run), consumption)
                self.assertEqual(EuerAccounting(restored).confirm(f.owner, depreciation_command), depreciation)
                self.assertEqual(EuerAccounting(restored).confirm(f.owner, export_command), export)
                self.assertEqual(EuerAccounting(restored).exported(f.owner, export['id']), artifact)
                self.assertEqual(EuerAccounting(restored).year_evidence(f.owner, export['id']), year_metadata)
                self.assertEqual(bytes(EuerAccounting(restored).year_evidence(f.owner, export['id'], archive=True)), year_archive)
                event_api = CompanyEvents(restored)
                self.assertEqual(event_api.execute(f.owner, completed['id'], event_command)['outcome'], event_accepted['outcome'])
                self.assertEqual(event_api.plan(f.owner, pending['id'])['status'], 'suspended_after_restore')
                self.assertEqual(restored.db.execute('SELECT COUNT(*) FROM workspace_items').fetchone()[0], task_count)
                actual = release.snapshot_fingerprint(target)
                for table in EVENT_TABLES:
                    if table != 'business_company_event_suspensions':
                        self.assertEqual(actual[table], fingerprints[table], table)
                for table in YEAR_TABLES + OPEN_ITEM_TABLES + prices.TABLES + assets.TABLES + openings.TABLES + catalog.TABLES + multiple.TABLES + PAYROLL_TABLES + (
                        'business_euer_entries', 'business_euer_requests', 'business_articles', 'business_document_versions'):
                    self.assertEqual(actual[table], fingerprints[table], table)
                self.assertTrue(business_schema.validate_integrity(restored))
            finally:
                restored.db.close()
