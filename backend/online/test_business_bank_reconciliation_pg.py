"""Real MFA/HTTP, competing PostgreSQL writers and original-preserving restore.

Only the existing guarded disposable loopback fixture is reset. All bank files,
identities and payments are synthetic; no provider or external bank is called.
"""
import base64
import calendar
from concurrent.futures import ThreadPoolExecutor
import threading
import unittest
import uuid

import psycopg

import business_schema
from business_bank_reconciliation import BankReconciliation,TABLES,_sha,validate_integrity,restore_horizon,validate_period_closure_proof
from business_foundation import BusinessFoundation
from core import Problem
from online import test_business_accounting_euer_pg as euer,release
from online.store import PostgresOffice
from online.test_postgres_accounting_components_integration import disposable_restore,evidence_for,approve
import test_business_bank_reconciliation as domain

fixture=euer.fixture
req=euer.req


@unittest.skipUnless(fixture.DSN,'Disposable loopback PostgreSQL fixture required')
class BankReconciliationPostgres(unittest.TestCase):
    setUp=euer.EuerPostgres.setUp
    reopen=euer.EuerPostgres.reopen
    login=euer.EuerPostgres.login
    call=euer.EuerPostgres.call
    profile=euer.EuerPostgres.profile
    post=euer.EuerPostgres.post
    project=euer.EuerPostgres.project
    issuer=euer.EuerPostgres.issuer
    invoice=euer.EuerPostgres.invoice
    payment=euer.EuerPostgres.payment
    source=euer.EuerPostgres.source
    document=euer.EuerPostgres.document
    cash=euer.EuerPostgres.cash
    file=domain.BankTests.file

    def setup_bank(self):
        self.actor=self.office.user(self.token);self.profile();project=self.project();self.issuer()
        account=self.call('POST','/business/accounting/accounts',req(confirmation=True,code='BANK',name='Synthetic controlled bank',kind='bank'),status=201).json
        invoice=self.invoice(project,'100.00');payment=self.payment(invoice,'119.00')
        source=next(item for item in self.call('GET','/business/accounting/sources/payments').json['items'] if item['payment_id']==payment['id'])
        event=self.call('POST','/business/accounting/events/import-payment',req(confirmation=True,payment_id=payment['id'],source_hash=source['source_hash'],account_id=account['id'],account_revision=1,cash_date=self.today,evidence_reference='Synthetic bank transfer'),status=201).json
        self.document(event);self.post('cash',self.cash(event))
        binding=self.call('POST','/business/bank/accounts',req(account_id=account['id'],account_revision=1,revision=0,iban='DE89370400440532013000',label='Synthetic bank',active=True,coverage_from=self.today[:7]+'-01',coverage_to=None,reason='')).json
        return account,event,binding

    def statement(self,account,binding,amounts,*,prefix='TX'):
        rows=[dict(transaction_id=prefix+str(index+1),booking_date=self.today,value_date=self.today,amount=value,currency='EUR',counterparty='Synthetic payer '+str(index),reference='=Synthetic original '+str(index)) for index,value in enumerate(amounts)]
        original=self.file(rows);total=sum(int(value.replace('.','')) for value in amounts)
        end=calendar.monthrange(int(self.today[:4]),int(self.today[5:7]))[1]
        body=dict(account_id=account['id'],account_revision=1,bank_revision=binding['revision'],statement_reference='Synthetic-'+uuid.uuid4().hex,period_from=self.today[:7]+'-01',period_to=self.today[:7]+'-'+str(end),opening_balance='0.00',closing_balance=str(total//100)+'.'+str(total%100).zfill(2),filename='synthetic-bank.csv',delimiter=';',content_base64=base64.b64encode(original).decode(),complete_statement_confirmed=True)
        preview=self.call('POST','/business/bank/import/preview',body).json;self.assertTrue(preview['can_import'])
        command=req(**body,preview_hash=preview['preview_hash'],confirmation=True)
        return self.call('POST','/business/bank/statements',command).json,command,original

    def match_command(self,transaction_id,amount):
        candidate=self.call('GET','/business/bank/transactions/'+transaction_id+'/candidates').json
        source=candidate['items'][0]['source']
        body=dict(revision=candidate['current']['revision'],links=[dict(source_kind=source['source_kind'],source_id=source['source_id'],source_hash=source['source_hash'],amount=amount,date_difference_reason='')],reason='Synthetic original explicitly compared')
        preview=self.call('POST','/business/bank/transactions/'+transaction_id+'/preview',body).json
        return req(**body,preview_hash=preview['preview_hash'],confirmation=True)

    def report(self,account,statement):
        body=dict(account_id=account['id'],period=self.today[:7],statement_ids=[statement['statement']['id']],reason='Synthetic complete original and existing cash reviewed')
        preview=self.call('POST','/business/bank/reconciliations/preview',body).json
        command=req(**body,preview_hash=preview['preview_hash'],confirmation=True)
        return self.call('POST','/business/bank/reconciliations',command).json,command

    def test_actual_http_period_proof_correction_permissions_and_immutable_receipts(self):
        account,event,binding=self.setup_bank();statement,import_command,original=self.statement(account,binding,['119.00']);identifier=statement['lines'][0]['transaction_id']
        path='/business/bank/transactions/'+identifier;command=self.match_command(identifier,'119.00');saved=self.call('POST',path+'/matches',command).json
        report,report_command=self.report(account,statement);self.assertTrue(report['record']['payload']['complete'])
        close=dict(period=self.today[:7],action='close',expected_period_revision=0,attestation=dict(bank_reconciled=True,originals_complete=True,special_cases_reviewed=True))
        closed,_=self.post('period',close);proof=closed['control']['bank_reconciliation'];self.assertTrue(validate_period_closure_proof(self.office,proof,self.today[:7]))
        correction=dict(revision=1,links=[],reason='Synthetic correction must first reopen')
        self.call('POST',path+'/preview',correction,status=409)
        self.post('period',dict(close,action='reopen',expected_period_revision=1))
        preview=self.call('POST',path+'/preview',correction).json;self.call('POST',path+'/matches',req(**correction,preview_hash=preview['preview_hash'],confirmation=True))
        self.assertTrue(validate_period_closure_proof(self.office,proof,self.today[:7]))
        current=self.call('GET','/business/bank/reconciliations/'+report['record']['id']).json;self.assertFalse(current['current'])
        state=self.call('GET','/business/accounting/euer').json
        self.call('POST','/business/accounting/euer/preview',dict(operation='period',payload=dict(close,expected_period_revision=2),expected_revision=state['revision'],state_hash=state['state_hash'],reason='Cannot silently reuse old bank proof',evidence_reference='Synthetic current review'),status=409)
        for kind in ('json','csv','pdf'):
            content=self.call('GET','/business/bank/reconciliations/'+report['record']['id']+'/'+kind).data
            self.assertEqual(_sha(content),report['exports'][kind]['sha256'])
        tech=self.call('POST','/users',dict(email='bank-tech@example.test',password='Synthetic-technician-password-123',role='technician'),status=201).json
        token=self.login('bank-tech@example.test','Synthetic-technician-password-123')
        for permission in ('bank.read','bank.prepare','accounting.read','accounting.prepare','finance.read','finance.write'):
            BusinessFoundation(self.office).save_grant(self.actor,req(user_id=tech['id'],permission=permission,scope='*',effect='allow',revision=0))
        empty,c,_=self.statement(account,binding,[],prefix='EMPTY')
        repeated={key:value for key,value in c.items() if key not in ('request_id','preview_hash','confirmation')}
        repeated_preview=self.call('POST','/business/bank/import/preview',repeated,token=token).json
        delegated=req(**repeated,preview_hash=repeated_preview['preview_hash'],confirmation=True);accepted=self.call('POST','/business/bank/statements',delegated,token=token).json
        self.assertEqual(accepted,empty)
        BusinessFoundation(self.office).save_grant(self.actor,req(user_id=tech['id'],permission='bank.prepare',scope='*',effect='deny',revision=1))
        denied=self.call('POST','/business/bank/statements',delegated,token=token,status=403).json;self.assertNotIn('request_resolution',denied)
        BusinessFoundation(self.office).save_grant(self.actor,req(user_id=tech['id'],permission='bank.read',scope='*',effect='deny',revision=1))
        self.call('GET','/business/bank/statements/'+empty['statement']['id']+'/original',token=token,status=403)
        self.call('POST',path+'/matches?ignored=1',command,status=400)
        device=self.call('POST','/business/offline/access',{},status=201).json['token'];self.call('GET','/business/bank/accounts',token=device,status=403)
        self.reopen()
        self.assertEqual(self.call('POST',path+'/matches',command).json,saved)
        self.assertEqual(self.call('POST','/business/bank/statements',import_command).json,statement)
        self.assertEqual(self.call('POST','/business/bank/reconciliations',report_command).json,report)
        self.assertEqual(self.call('GET','/business/bank/statements/'+statement['statement']['id']+'/original').data,original)
        self.assertTrue(validate_integrity(self.office));business_schema.validate_integrity(self.office)

    def test_competing_capacity_and_imports_use_real_independent_connections(self):
        account,event,binding=self.setup_bank();statement,command,unused=self.statement(account,binding,['80.00','80.00'])
        identifiers=[line['transaction_id'] for line in statement['lines']];commands=[self.match_command(identifier,'80.00') for identifier in identifiers]
        barrier=threading.Barrier(2)
        def worker(index):
            office=PostgresOffice(self.runtime)
            try:
                barrier.wait(timeout=10)
                try:BankReconciliation(office).save_match(self.actor,identifiers[index],commands[index]);return 200
                except Problem as error:return error.status
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(worker,range(2)))
        self.assertEqual(sorted(results),[200,409]);self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_bank_match_events').fetchone()[0],1)
        body={key:value for key,value in command.items() if key not in ('request_id','preview_hash','confirmation')};body['content_base64']=base64.b64encode(b'\xef\xbb\xbf'+base64.b64decode(body['content_base64'])).decode();body['statement_reference']='Concurrent distinct original'
        preview=self.call('POST','/business/bank/import/preview',body).json;import_command=req(**body,preview_hash=preview['preview_hash'],confirmation=True);barrier=threading.Barrier(2)
        def importer(index):
            office=PostgresOffice(self.runtime)
            try:barrier.wait(timeout=10);return BankReconciliation(office).import_statement(self.actor,import_command)
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:receipts=list(pool.map(importer,range(2)))
        self.assertEqual(receipts[0],receipts[1]);self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_bank_transactions').fetchone()[0],2)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_bank_statements').fetchone()[0],2)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_accounting_cash_events').fetchone()[0],1)
        for table in TABLES:
            column=self.office.db.execute('SELECT * FROM '+table+' LIMIT 1').description[0].name
            for sql in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table,'TRUNCATE '+table):
                with self.subTest(sql=sql),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db:self.office.db.execute(sql)
        self.assertTrue(validate_integrity(self.office));business_schema.validate_integrity(self.office)

    def test_real_dump_restore_binds_originals_reports_and_separate_operator_approval(self):
        account,event,binding=self.setup_bank();statement,import_command,original=self.statement(account,binding,['119.00']);identifier=statement['lines'][0]['transaction_id'];command=self.match_command(identifier,'119.00')
        BankReconciliation(self.office).save_match(self.actor,identifier,command);report,report_command=self.report(account,statement)
        before=restore_horizon(self.office);self.assertEqual(business_schema.financial_accounting_horizon(self.office)['schema_version'],13)
        fingerprints=release.snapshot_fingerprint(fixture.DSN);self.office.db.close()
        with disposable_restore(self.runtime) as (target,target_runtime,restored_report):
            restored=PostgresOffice(target_runtime)
            try:
                api=BankReconciliation(restored);self.assertEqual(restore_horizon(restored),before)
                self.assertEqual(api.original(self.actor,statement['statement']['id'])[0],original)
                self.assertEqual(api.reconciliation(self.actor,report['record']['id'])['record'],report['record'])
                evidence=evidence_for(restored,restored_report);self.assertEqual(evidence['schema'],14)
                with self.assertRaises(Problem) as caught:api.import_statement(self.actor,import_command)
                self.assertEqual(caught.exception.status,409)
                with self.assertRaises(Problem) as caught:approve(restored,evidence)
                self.assertEqual(caught.exception.status,403)
                restored.db.close()
                operator=PostgresOffice(target)
                try:approve(operator,evidence)
                finally:operator.db.close()
                restored=PostgresOffice(target_runtime);api=BankReconciliation(restored)
                self.assertEqual(api.import_statement(self.actor,import_command),statement)
                self.assertEqual(api.save_reconciliation(self.actor,report_command),report)
                self.assertTrue(validate_integrity(restored));business_schema.validate_integrity(restored)
                after=release.snapshot_fingerprint(target)
                for table in TABLES:self.assertEqual(after[table],fingerprints[table])
            finally:restored.db.close()


if __name__=='__main__':unittest.main()
