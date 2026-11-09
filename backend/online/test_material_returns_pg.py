"""Real restricted PostgreSQL material returns, restart, concurrency and restore."""
from concurrent.futures import ThreadPoolExecutor
import threading
import unittest

import business_schema
from online import test_business_asset_provenance_pg as fixture
from online import test_material_returns_http as http
from online.store import PostgresOffice
from online.web import create_app
from online.test_postgres_accounting_components_integration import disposable_restore


@unittest.skipUnless(fixture.pg.fixture.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class MaterialReturnPostgresTests(unittest.TestCase):
    setUp=fixture.AssetDeliveryPostgresTests.setUp
    reopen=fixture.AssetDeliveryPostgresTests.reopen
    call=fixture.AssetDeliveryPostgresTests.call
    login=fixture.AssetDeliveryPostgresTests.login
    article_record=fixture.AssetDeliveryPostgresTests.article_record
    stock=fixture.AssetDeliveryPostgresTests.stock
    costs=fixture.AssetDeliveryPostgresTests.costs
    initial_issue=http.MaterialReturnHttpTests.initial_issue
    return_body=http.MaterialReturnHttpTests.return_body
    movement_rows=http.MaterialReturnHttpTests.movement_rows
    workflow=http.MaterialReturnHttpTests.workflow

    def test_real_runtime_returns_restart_dump_restore_and_historical_replay(self):
        self.assertEqual(self.office.db.execute('SELECT current_user').fetchone()[0],'smartplan-online')
        self.assertTrue(business_schema.require_runtime_security(self.office))
        command,first,issue=self.workflow()
        rows=self.movement_rows()
        state=(self.stock(),self.costs())
        for sql in ['DELETE FROM business_stock_movements',
                    'UPDATE business_stock_movements SET note=note']:
            with self.assertRaises(Exception):
                with self.office.db:self.office.db.execute(sql)
        self.reopen()
        self.assertEqual(self.call('/business/inventory/movements',command,status=201).json,first)
        self.assertEqual((self.stock(),self.costs()),state)
        self.assertEqual(self.movement_rows(),rows)
        previous_token,runtime=self.token,self.runtime
        self.office.db.close()
        with disposable_restore(runtime) as (_,restored_runtime,_):
            self.office=PostgresOffice(restored_runtime)
            try:
                self.app=create_app(office=self.office,key=self.key,host='office.example.test',storage_config={})
                self.client=self.app.test_client()
                self.call('/business/inventory/movements/'+issue['id'],token=previous_token,status=401)
                self.token=self.login('order-owner@example.test','Synthetic-owner-password-123')
                self.assertEqual(self.call('/business/inventory/movements',command,status=201).json,first)
                self.assertEqual(self.call('/business/inventory/movements/'+issue['id']).json,issue)
                self.assertEqual((self.stock(),self.costs()),state)
                self.assertEqual(self.movement_rows(),rows)
                self.assertTrue(business_schema.validate_integrity(self.office))
                self.assertTrue(business_schema.require_runtime_security(self.office))
            finally:self.office.db.close()

    test_real_rounding_remainder=http.MaterialReturnHttpTests.test_final_return_carries_original_rounding_remainder
    test_real_fresh_rights_and_price_redaction=http.MaterialReturnHttpTests.test_current_project_write_rights_and_price_redaction_apply_to_original_retry
    test_real_unaccepted_conflict_and_nonce_collision=http.MaterialReturnHttpTests.test_explicit_unaccepted_conflict_never_labels_an_accepted_nonce_collision

    def test_two_runtime_connections_cannot_return_more_than_original_issue(self):
        issue=self.initial_issue()
        barrier=threading.Barrier(2)
        commands=[self.return_body(issue,'4') for _ in range(2)]
        def attempt(command):
            office=PostgresOffice(self.runtime)
            try:
                app=create_app(office=office,key=self.key,host='office.example.test',storage_config={})
                client=app.test_client()
                barrier.wait(timeout=20)
                response=client.post('/api/v1/business/inventory/movements',json=command,
                    base_url='https://office.example.test',headers={'Authorization':'Bearer '+self.token})
                return response.status_code,response.json
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,commands))
        self.assertEqual(sorted(result[0] for result in results),[201,409])
        rejected=next(payload for status,payload in results if status==409)
        self.assertEqual(rejected.get('request_resolution'),'not_accepted')
        rows=[row for row in self.movement_rows() if row['reversal_of']==issue['id']]
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['quantity'],'4.0000')
        self.assertEqual((self.stock()['on_hand'],self.costs()['material_actual_net']),('8.0000','20.00'))
        self.assertEqual(self.call('/business/inventory/movements/'+issue['id']).json,issue)
        self.assertTrue(business_schema.validate_integrity(self.office))


if __name__=='__main__':unittest.main()
