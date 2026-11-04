"""Real dated catalog MFA/HTTP, separated runtime, contention and dump/restore."""
import base64
from concurrent.futures import ThreadPoolExecutor
import unittest

import psycopg
from core import Problem
import business_catalog_prices as prices
import business_schema
from online import release, test_customer_execution_journey_pg as fixture
from online.store import PostgresOffice
from online.test_postgres_accounting_components_integration import disposable_restore
from test_business_catalog_prices import raw, row


@unittest.skipUnless(fixture.fixture.DSN,'Disposable loopback SMARTPLAN_TEST_DSN required')
class DatedCatalogPostgres(unittest.TestCase):
    def setUp(self):
        f=self.f=fixture.CustomerExecutionJourneyPostgres('runTest')
        f.setUp();self.addCleanup(f.doCleanups)
        self.owner=f.office.user(f.token)
        self.source=f.call('POST','/business/catalog-prices/sources',fixture.request(name='Synthetic PostgreSQL dated source',reference='SYN-PG-DATED')).json

    def stage(self,original=None,revision='SYN-1'):
        body=fixture.request(catalog_revision=revision,filename='dated-source.csv',content_base64=base64.b64encode(original or raw(row())).decode())
        return self.f.call('POST','/business/catalog-prices/sources/'+self.source['id']+'/imports',body).json

    def prepare(self,staged):
        decisions=dict(expected_source_version=prices.CatalogPrices(self.f.office).source(self.source['id'])['source_version'],replacements={},
            bindings={item['code']:dict(action='create',article_id=None,article_revision=None,expected_binding_revision=0,confirm_name_difference=False) for item in staged['rows']})
        checked=self.f.call('POST','/business/catalog-prices/imports/'+staged['id']+'/preview',decisions).json
        return fixture.request(**decisions,preview_sha256=checked['preview_sha256'],confirmation=True)

    def test_actual_original_readonly_preview_acceptance_revision_and_runtime_guards(self):
        original=raw(row(),row(price_id='dec',amount='12',start='2026-12-01',end=''))
        original+=b'\n'*(2097152-len(original))
        staged=self.stage(original)
        before=self.f.office.db.execute('SELECT COUNT(*) FROM audit').fetchone()[0]
        body=self.prepare(staged)
        self.assertEqual(self.f.office.db.execute('SELECT COUNT(*) FROM audit').fetchone()[0],before)
        path='/business/catalog-prices/imports/'+staged['id']
        result=self.f.call('POST',path+'/apply',body).json
        self.assertEqual(self.f.call('POST',path+'/apply',body).json,result)
        self.assertEqual(self.f.call('GET',path+'/original').data,original)
        article_id=result['bindings'][0]['article_id']
        for day,expected in (('2026-11-30','10.00'),('2026-12-01','12')):
            candidates=self.f.call('POST','/business/catalog-prices/candidates',dict(article_id=article_id,price_role='sales_net',effective_on=day)).json
            chosen=[item for item in candidates['items'] if item['status']=='eligible']
            self.assertEqual(len(chosen),1);self.assertEqual(chosen[0]['price']['price_net'],expected)
        for table in prices.TABLES:
            for dsn in (self.f.runtime,fixture.fixture.DSN):
                with self.assertRaises(psycopg.Error),psycopg.connect(dsn) as connection:
                    connection.execute('DELETE FROM '+table)
        self.assertTrue(business_schema.require_runtime_security(self.f.office))
        prices.validate_integrity(self.f.office)
        self.f.reopen()
        self.assertEqual(self.f.call('GET',path).json['application'],result)
        self.assertEqual(self.f.call('GET',path+'/original').data,original)

    def test_two_independent_runtime_connections_serialize_same_nonce_and_source_revision(self):
        staged=self.stage()
        command=self.prepare(staged)
        def apply(args):
            office=PostgresOffice(self.f.runtime)
            try:
                try:return prices.CatalogPrices(office).apply(self.owner,*args)
                except Problem as error:return error.status
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(apply,[(staged['id'],command)]*2))
        self.assertIsInstance(results[0],dict);self.assertEqual(results[0],results[1])
        first=self.stage(raw(row(code='RACE-A',price_id='race-a')),revision='SYN-2')
        second=self.stage(raw(row(code='RACE-B',price_id='race-b')),revision='SYN-3')
        commands=[(value['id'],self.prepare(value)) for value in (first,second)]
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(apply,commands))
        self.assertEqual(results.count(409),1)
        self.assertEqual(sum(isinstance(value,dict) for value in results),1)
        self.assertEqual(self.f.office.db.execute('SELECT COUNT(*) FROM business_catalog_price_applications').fetchone()[0],2)
        prices.validate_integrity(self.f.office)

    def test_actual_dump_restore_preserves_original_frozen_document_price_and_exact_receipts(self):
        original=raw(row(),row(price_id='dec',amount='12',start='2026-12-01',end=''))
        staged=self.stage(original)
        command=self.prepare(staged)
        accepted=self.f.call('POST','/business/catalog-prices/imports/'+staged['id']+'/apply',command).json
        article_id=accepted['bindings'][0]['article_id']
        proof=accepted['prices'][0]
        selection=dict(price_id=proof['price_id'],price_revision=proof['revision'],price_sha256=proof['sha256'],effective_on='2026-11-04')
        project=self.f.call('POST','/projects',dict(name='Synthetic dated restore project',customer='Synthetic customer'),status=201).json['id']
        document=self.f.call('POST','/business/documents',fixture.request(project_id=project,kind='offer',title='Synthetic dated offer',issue_date='2026-11-04',due_date='2026-11-30',
            buyer=dict(name='Synthetic Buyer',address_line='Testweg 1',postal_code='10115',city='Berlin',country='DE',email='buyer@example.test'),
            positions=[dict(article_id=article_id,article_revision=1,quantity='3',catalog_price_selection=selection)])).json
        self.assertEqual(document['totals']['net'],'30.00')
        original_snapshot=document['positions'][0]['catalog_price_snapshot']
        fingerprints=release.snapshot_fingerprint(fixture.fixture.DSN)
        self.f.office.db.close()
        with disposable_restore(self.f.runtime) as (target,runtime,report):
            office=PostgresOffice(runtime)
            try:
                self.assertTrue(business_schema.validate_integrity(office))
                self.assertEqual(prices.CatalogPrices(office).original(self.owner,staged['id'])[0],original)
                self.assertEqual(prices.validate_snapshot(office,original_snapshot),original_snapshot)
                before=release.snapshot_fingerprint(target)
                self.assertEqual(prices.CatalogPrices(office).apply(self.owner,staged['id'],command),accepted)
                self.assertEqual(release.snapshot_fingerprint(target),before)
                after=release.snapshot_fingerprint(target)
                for table in prices.TABLES+('business_articles','business_document_versions'):
                    self.assertEqual(after[table],fingerprints[table],table)
            finally:office.db.close()


if __name__=='__main__':unittest.main()
