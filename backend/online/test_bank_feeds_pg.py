"""Real separated runtime, MFA, unchanged cash originals and full dump/restore."""
import time
import unittest
from cryptography.fernet import Fernet

from online import test_business_bank_reconciliation_pg as existing
from online.bank_feeds_service import BankFeeds, Config
from online.integration_qonto import QontoReader
from online.integration_http import IntegrationHttp
from online.test_integration_qonto import ORG, TOKEN, FROM, TO, org, page, row, response, Opener
from online.test_postgres_accounting_components_integration import disposable_restore
from online.web import create_app
from online.auth import totp
from online.store import PostgresOffice
from business_bank_reconciliation import BankReconciliation, restore_horizon, TABLES
from business_accounting_euer import EuerAccounting
from online import release


@unittest.skipUnless(existing.fixture.DSN,'Disposable loopback SMARTPLAN_TEST_DSN required')
class BankFeedPostgres(unittest.TestCase):
    setUp=existing.BankReconciliationPostgres.setUp
    call=existing.BankReconciliationPostgres.call
    reopen=existing.BankReconciliationPostgres.reopen
    login=existing.BankReconciliationPostgres.login
    profile=existing.BankReconciliationPostgres.profile
    post=existing.BankReconciliationPostgres.post
    project=existing.BankReconciliationPostgres.project
    issuer=existing.BankReconciliationPostgres.issuer
    invoice=existing.BankReconciliationPostgres.invoice
    payment=existing.BankReconciliationPostgres.payment
    source=existing.BankReconciliationPostgres.source
    document=existing.BankReconciliationPostgres.document
    cash=existing.BankReconciliationPostgres.cash
    setup_bank=existing.BankReconciliationPostgres.setup_bank
    statement=existing.BankReconciliationPostgres.statement
    file=existing.BankReconciliationPostgres.file

    def test_actual_runtime_read_does_not_rewrite_cash_originals_and_survives_full_restore(self):
        account,event,binding=self.setup_bank()
        statement,command,original=self.statement(account,binding,['119.00'])
        before=restore_horizon(self.office)
        euer=self.call('GET','/business/accounting/euer').json
        config=Config(ORG,account['id'],TOKEN)
        def service(office):
            return BankFeeds(office,config=lambda:config,reader=QontoReader(http=IntegrationHttp('qonto',opener=Opener(response(org()),response(page([row()])),response(org())))))
        self.app=create_app(office=self.office,key=self.key,host='office.example.test',bank_feeds=service(self.office))
        self.client=self.app.test_client()
        result=self.call('POST','/bank-feeds/qonto/read',dict(updated_from=FROM,updated_to=TO)).json
        self.assertEqual(result['items'][0]['signed_amount_cents'],-43)
        self.assertEqual(before,restore_horizon(self.office));self.assertEqual(euer,self.call('GET','/business/accounting/euer').json)
        self.assertEqual(BankReconciliation(self.office).original(self.actor,statement['statement']['id'])[0],original)
        fingerprints=release.snapshot_fingerprint(existing.fixture.DSN)
        secret=Fernet(self.key).decrypt(self.office.db.execute('SELECT secret FROM mfa WHERE user_id=?',(self.actor['id'],)).fetchone()['secret'].encode()).decode()
        self.office.db.close()
        with disposable_restore(self.runtime) as (target,runtime,report):
            restored=PostgresOffice(runtime)
            try:
                self.assertEqual(before,restore_horizon(restored))
                self.assertEqual(BankReconciliation(restored).original(self.actor,statement['statement']['id'])[0],original)
                app=create_app(office=restored,key=self.key,host='office.example.test',bank_feeds=service(restored));client=app.test_client()
                old=client.get('/api/v1/bank-feeds/qonto/status',headers={'Authorization':'Bearer '+self.token},base_url='https://office.example.test')
                self.assertEqual(old.status_code,401)
                pending=client.post('/api/v1/login',json=dict(email='order-owner@example.test',password='Synthetic-owner-password-123'),base_url='https://office.example.test').json
                token=client.post('/api/v1/login/verify',json=dict(challenge=pending['challenge'],code=totp(secret,int(time.time()//30)+1)),base_url='https://office.example.test').json['token']
                read=client.post('/api/v1/bank-feeds/qonto/read',json=dict(updated_from=FROM,updated_to=TO),headers={'Authorization':'Bearer '+token},base_url='https://office.example.test')
                self.assertEqual(read.status_code,200,read.data[:300]);self.assertEqual(read.json['content_hash'],result['content_hash'])
                after=release.snapshot_fingerprint(target)
                for table in TABLES:self.assertEqual(after[table],fingerprints[table])
            finally:restored.db.close()


if __name__=='__main__':unittest.main()
