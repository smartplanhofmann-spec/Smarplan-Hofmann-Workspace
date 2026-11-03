"""Real restricted PostgreSQL inventory ledger and dump/restore evidence."""
import unittest

import business_schema
from online import test_business_asset_provenance_pg as pg
from online import test_business_inventory_counts_http as http
from online.store import PostgresOffice
from online.web import create_app
from online.test_postgres_accounting_components_integration import disposable_restore
from business_inventory_counts import protected_tables


@unittest.skipUnless(pg.pg.fixture.DSN,'Disposable loopback PostgreSQL required')
class InventoryCountPostgres(unittest.TestCase):
    setUp=pg.AssetDeliveryPostgresTests.setUp
    reopen=pg.AssetDeliveryPostgresTests.reopen
    call=pg.AssetDeliveryPostgresTests.call
    login=pg.AssetDeliveryPostgresTests.login
    article_record=pg.AssetDeliveryPostgresTests.article_record

    def test_real_mfa_http_runtime_acl_restart_and_dump_restore(self):
        # A fresh operational identity has no financial approval or price read.
        self.call('/users',dict(email='inventory-counter@example.test',password='Synthetic-counter-password-123',role='technician'),status=201)
        owner_secret,owner_step=self.secret,self.last_step
        self.secret=None; self.last_step=-1
        self.tech_token=self.login('inventory-counter@example.test','Synthetic-counter-password-123')
        self.secret,self.last_step=owner_secret,owner_step
        command,result=http.InventoryCountHttpTests.workflow(self)
        self.assertEqual(self.office.db.execute('SELECT current_user').fetchone()[0],'smartplan-online')
        self.assertTrue(business_schema.require_runtime_security(self.office))
        snapshots={table:[dict(row) for row in self.office.db.execute('SELECT * FROM '+table)] for table in protected_tables()}
        for table in protected_tables():
            with self.assertRaises(Exception):
                with self.office.db:self.office.db.execute('DELETE FROM '+table)
        self.reopen()
        path='/business/inventory/counts/'+result['id']
        self.assertEqual(self.call(path+'/approve',command).json,result)
        token,runtime=self.token,self.runtime
        self.office.db.close()
        with disposable_restore(runtime) as (_,restored_runtime,_report):
            self.office=PostgresOffice(restored_runtime)
            try:
                self.app=create_app(office=self.office,key=self.key,host='office.example.test',storage_config={})
                self.client=self.app.test_client()
                self.call(path,token=token,status=401)
                self.token=self.login('order-owner@example.test','Synthetic-owner-password-123')
                self.assertEqual(self.call(path+'/approve',command).json,result)
                for table,rows in snapshots.items():
                    self.assertEqual([dict(row) for row in self.office.db.execute('SELECT * FROM '+table)],rows)
                self.assertTrue(business_schema.validate_integrity(self.office))
                self.assertTrue(business_schema.require_runtime_security(self.office))
            finally:self.office.db.close()


if __name__=='__main__':unittest.main()
